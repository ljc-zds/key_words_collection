"""Publish validated Google Trends new words to a Feishu spreadsheet."""

from __future__ import annotations

from datetime import datetime, timezone

from keyword_loop.core.publishing.feishu import (
    load_env,
    parse_sheet_id,
    request_json,
    resolve_wiki_node,
    tenant_access_token,
)


NEW_WORD_HEADERS = [
    "关键词", "来源词根", "上级词", "递归层级", "趋势类型", "增长率",
    "前21天平均热度", "gpts前21天平均热度", "首次超过gpts日期",
    "近9天超过次数", "最大领先值", "当前仍高于gpts", "检测规则",
]
RULE = "过去30天：前21天低于 gpts，后9天出现超过"


def _crossing_date(value: object) -> str:
    try:
        return datetime.fromtimestamp(int(str(value)), tz=timezone.utc).date().isoformat()
    except (TypeError, ValueError, OverflowError):
        return ""


def build_new_word_rows(records: list[dict]) -> list[list[object]]:
    """Render new-word checkpoint records into user-facing sheet rows."""
    rows: list[list[object]] = [NEW_WORD_HEADERS]
    for record in records:
        related = record.get("related", {})
        comparison = record.get("comparison", {})
        trend_type = related.get("type", "rising")
        growth = "Breakout" if trend_type == "Breakout" else f"{related.get('growth_percent', '')}%"
        rows.append([
            record.get("candidate", ""), record.get("root", ""), record.get("parent_keyword", ""), record.get("depth", ""),
            trend_type, growth, comparison.get("candidate_baseline_average", ""), comparison.get("gpts_baseline_average", ""),
            _crossing_date(record.get("first_crossing_time")), comparison.get("crossing_count", ""), comparison.get("maximum_difference", ""),
            "是" if comparison.get("still_above_gpts") else "否", RULE,
        ])
    return rows


def publish_new_words(wiki_url: str, records: list[dict], env: dict[str, str] | None = None) -> dict[str, object]:
    """Upsert new words into the chosen Feishu sheet by keyword."""
    token = tenant_access_token(env or load_env())
    node = resolve_wiki_node(wiki_url, token)
    if node.get("obj_type") != "sheet":
        raise RuntimeError(f"new-word destination must be a Feishu spreadsheet, got {node.get('obj_type')}")
    spreadsheet_token = node["obj_token"]
    sheets = request_json(
        f"https://open.feishu.cn/open-apis/sheets/v3/spreadsheets/{spreadsheet_token}/sheets/query",
        method="GET",
        token=token,
    )["data"]["sheets"]
    requested = parse_sheet_id(wiki_url)
    sheet = next((item for item in sheets if item.get("sheet_id") == requested or item.get("title") == requested), None) if requested else sheets[0]
    if sheet is None:
        raise RuntimeError("new-word destination worksheet was not found")
    sheet_id = sheet["sheet_id"]
    existing = request_json(
        f"https://open.feishu.cn/open-apis/sheets/v2/spreadsheets/{spreadsheet_token}/values/{sheet_id}!A1:M5000",
        method="GET",
        token=token,
    )["data"]["valueRange"].get("values", [])
    positions = {str(row[0]).strip().lower(): index + 2 for index, row in enumerate(existing[1:]) if row and row[0]}
    rows = build_new_word_rows(records)
    updates: list[dict[str, object]] = [{"range": f"{sheet_id}!A1:M1", "values": [rows[0]]}]
    append_rows: list[list[object]] = []
    for row in rows[1:]:
        keyword = str(row[0]).strip().lower()
        if keyword in positions:
            updates.append({"range": f"{sheet_id}!A{positions[keyword]}:M{positions[keyword]}", "values": [row]})
        else:
            append_rows.append(row)
    last_row = max((index + 1 for index, row in enumerate(existing) if row and row[0]), default=1)
    if append_rows:
        updates.append({"range": f"{sheet_id}!A{last_row + 1}:M{last_row + len(append_rows)}", "values": append_rows})
    for start in range(0, len(updates), 50):
        request_json(
            f"https://open.feishu.cn/open-apis/sheets/v2/spreadsheets/{spreadsheet_token}/values_batch_update",
            method="POST",
            token=token,
            payload={"valueRanges": updates[start:start + 50]},
        )
    return {"sheet_id": sheet_id, "written": len(rows) - 1, "appended": len(append_rows), "updated": len(rows) - 1 - len(append_rows)}
