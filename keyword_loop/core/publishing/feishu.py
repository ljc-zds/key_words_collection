import json
import os
from pathlib import Path
from urllib.parse import parse_qs, urlparse
from urllib.request import Request, urlopen

from product_hunt.aitdk.product.product_hunt import trusted_ssl_context

from ..screening.explanation import explanation_fields
from ..data.models import KeywordCandidate
from ..sources.rankings import RankedProduct


def parse_wiki_url(url: str) -> str:
    parts = [part for part in urlparse(url).path.split("/") if part]
    if len(parts) != 2 or parts[0] != "wiki":
        raise ValueError("expected a Feishu wiki URL")
    return parts[1]


def parse_sheet_id(url: str) -> str | None:
    """Return the explicit Feishu worksheet id from ``?sheet=...``."""
    values = parse_qs(urlparse(url).query).get("sheet", [])
    return values[0].strip() if values and values[0].strip() else None


def _display(payload: dict, field: str, unavailable: str) -> str:
    value = payload.get(field)
    return unavailable if value is None or value == "" else str(value)


def build_sheet_values(candidates: list[KeywordCandidate], enrichments: dict[str, tuple[str, str, str]] | None = None, gofei_scores: dict[str, float] | None = None, gofei_payloads: dict[str, dict] | None = None, validations: dict[str, dict[str, dict]] | None = None) -> list[list[str]]:
    header = ["关键词", "平均搜索量", "Similarweb KD", "哥飞 KD", "意图", "来源词根", "词表类型", "市场", "获取时间", "审核状态", "关键词含义", "搜索意图解读", "订阅机会", "通用竞争分数", "趋势比例", "趋势估算值", "趋势域名", "链接预算低", "链接预算中", "链接预算高", "目标DR", "哥飞判断依据", "竞争详情", "Semrush搜索量", "Semrush KD", "Semrush CPC", "Semrush意图", "广告竞争度", "SERP特征数", "AI筛选", "AI机会评分", "工具页适配度", "关键词域名适配度", "推荐页面类型", "AI变现方式", "AI判断原因", "Serper前十", "PAA", "相关搜索", "强站数量", "Semrush筛选", "Semrush筛选原因", "意图筛选", "意图筛选说明"]
    rows = []
    for item in candidates:
        explanation = (enrichments or {}).get(item.keyword, explanation_fields(item))
        score = (gofei_scores or {}).get(item.keyword)
        payload = (gofei_payloads or {}).get(item.keyword, {})
        trend, budget = payload.get("keywordTrend") or {}, payload.get("linkBudget") or {}
        reasons = payload.get("reasons") or []
        details = payload.get("details") or []
        detail_text = "；".join(f"{d.get('position','')}: {d.get('domain','')} (DR {d.get('dr','')}, visits {d.get('visits','')})" for d in details if isinstance(d, dict))
        stages = (validations or {}).get(item.keyword, {})
        sem = stages.get("semrush", {})
        ai = stages.get("ai_screen", {})
        # Older runs stored the final AI judgment only as ai_screen. Reuse it
        # for the legacy intent columns so historical rows remain complete.
        intent_gate = stages.get("intent_gate") or ai
        serp = stages.get("serper", {})
        semrush_missing = sem.get("exact_keyword_found") is False
        semrush_value = lambda field: "Semrush未返回精确关键词" if semrush_missing else _display(sem, field, "待Semrush补采")
        top_results = serp.get("organic") or []
        top_text = "；".join(f"{x.get('position','')}: {x.get('title','')} | {x.get('link','')}" for x in top_results if isinstance(x, dict))
        serp_pending = "待Serper采集" if not serp else ""
        related = "；".join(serp.get("related") or [])
        related_display = related or ("待Serper采集" if not serp else "本次SERP未返回相关搜索")
        paa_display = "；".join(serp.get("paa") or []) or ("待Serper采集" if not serp else "本次SERP未返回 PAA")
        rows.append([item.keyword, str(item.average_volume), str(item.kd), "" if score is None else str(score), item.intent or "", ", ".join(item.source_roots), ", ".join(item.result_types), item.market, item.retrieved_at, "待审核", *explanation, _display(payload, "genericScore", "接口未返回"), str(trend.get("ratio", "")), str(trend.get("estimatedValue", "")), str(trend.get("domain", "")), str(budget.get("low", "")), str(budget.get("mid", "")), str(budget.get("high", "")), str(budget.get("targetDr", "")), "；".join(str(x) for x in reasons), detail_text, semrush_value("volume"), semrush_value("kd"), semrush_value("cpc"), semrush_value("intent"), semrush_value("competitive_density"), semrush_value("serp_features"), _display(ai, "decision", "待AI判断"), _display(ai, "score", "待AI二筛"), _display(ai, "tool_page_fit", "待AI二筛"), _display(ai, "exact_match_domain_fit", "待AI二筛"), _display(ai, "recommended_page_type", "待AI二筛"), _display(ai, "monetization", "待AI二筛"), _display(ai, "reason", "待AI二筛"), top_text or serp_pending, paa_display, related_display, _display(serp, "strong_site_count", "待Serper采集"), str(sem.get("gate_decision", "")), str(sem.get("gate_reason", "")), str(intent_gate.get("decision", "")), str(intent_gate.get("reason", ""))])
    return [header] + rows


def load_env(path: Path = Path(".env")) -> dict[str, str]:
    values = dict(os.environ)
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            if "=" in line and not line.lstrip().startswith("#"):
                key, value = line.split("=", 1)
                values.setdefault(key.strip(), value.strip())
    return values


def request_json(url: str, *, method: str, payload: dict | None = None, token: str | None = None) -> dict:
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    data = json.dumps(payload, ensure_ascii=False).encode() if payload is not None else None
    with urlopen(Request(url, data=data, headers=headers, method=method), context=trusted_ssl_context(), timeout=30) as response:
        result = json.load(response)
    if result.get("code", 0) != 0:
        raise RuntimeError(f"Feishu request failed ({result.get('code', 'unknown')})")
    return result


def tenant_access_token(env: dict[str, str]) -> str:
    try:
        app_id, app_secret = env["FEISHU_APP_ID"], env["FEISHU_APP_SECRET"]
    except KeyError as error:
        raise RuntimeError("FEISHU_APP_ID and FEISHU_APP_SECRET are required") from error
    return request_json("https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal", method="POST", payload={"app_id": app_id, "app_secret": app_secret})["tenant_access_token"]


def resolve_wiki_node(wiki_url: str, token: str) -> dict:
    return request_json(f"https://open.feishu.cn/open-apis/wiki/v2/spaces/get_node?token={parse_wiki_url(wiki_url)}", method="GET", token=token)["data"]["node"]


def publish_sheet(spreadsheet_token: str, sheet_id: str, candidates: list[KeywordCandidate], token: str, enrichments: dict[str, tuple[str, str, str]] | None = None, gofei_scores: dict[str, float] | None = None, gofei_payloads: dict[str, dict] | None = None, validations: dict[str, dict[str, dict]] | None = None) -> None:
    rows = build_sheet_values(candidates, enrichments, gofei_scores, gofei_payloads, validations)
    existing = request_json(f"https://open.feishu.cn/open-apis/sheets/v2/spreadsheets/{spreadsheet_token}/values/{sheet_id}!A1:AR5000", method="GET", token=token)["data"]["valueRange"].get("values", [])
    positions = {str(row[0]).strip().lower(): index + 2 for index, row in enumerate(existing[1:]) if row and row[0]}
    updates: list[dict] = [{"range": f"{sheet_id}!A1:AR1", "values": [rows[0]]}]
    append_rows: list[list[str]] = []
    last_keyword_row = max((index + 1 for index, row in enumerate(existing) if row and row[0]), default=1)
    next_row = max(last_keyword_row + 1, 2)
    for row in rows[1:]:
        key = row[0].strip().lower()
        target = positions.get(key)
        if target is None:
            append_rows.append(row)
        else:
            updates.append({"range": f"{sheet_id}!A{target}:AR{target}", "values": [row]})
    if append_rows:
        updates.append({"range": f"{sheet_id}!A{next_row}:AR{next_row + len(append_rows) - 1}", "values": append_rows})
    for start in range(0, len(updates), 50):
        request_json(f"https://open.feishu.cn/open-apis/sheets/v2/spreadsheets/{spreadsheet_token}/values_batch_update", method="POST", token=token, payload={"valueRanges": updates[start:start + 50]})


def publish_wiki(wiki_url: str, candidates: list[KeywordCandidate], env: dict[str, str] | None = None, enrichments: dict[str, tuple[str, str, str]] | None = None, gofei_scores: dict[str, float] | None = None, gofei_payloads: dict[str, dict] | None = None, validations: dict[str, dict[str, dict]] | None = None) -> None:
    token = tenant_access_token(env or load_env())
    node = resolve_wiki_node(wiki_url, token)
    if node.get("obj_type") != "sheet":
        raise RuntimeError(f"unsupported Feishu wiki object type: {node.get('obj_type')}")
    spreadsheet_token = node["obj_token"]
    sheets = request_json(
        f"https://open.feishu.cn/open-apis/sheets/v3/spreadsheets/{spreadsheet_token}/sheets/query",
        method="GET",
        token=token,
    )["data"]["sheets"]
    if not sheets:
        raise RuntimeError("Feishu spreadsheet has no worksheets")
    requested_sheet = parse_sheet_id(wiki_url)
    sheet = next((item for item in sheets if item.get("sheet_id") == requested_sheet or item.get("title") == requested_sheet), None) if requested_sheet else sheets[0]
    if sheet is None:
        available = ", ".join(f"{item.get('title')}({item.get('sheet_id')})" for item in sheets)
        raise RuntimeError(f"Feishu worksheet not found: {requested_sheet}; available: {available}")
    publish_sheet(spreadsheet_token, sheet["sheet_id"], candidates, token, enrichments, gofei_scores, gofei_payloads, validations)


def load_roots_from_wiki(wiki_url: str, env: dict[str, str] | None = None, preserve_order: bool = False) -> list[str]:
    token = tenant_access_token(env or load_env())
    node = resolve_wiki_node(wiki_url, token)
    if node.get("obj_type") != "sheet":
        raise RuntimeError("root library must be a Feishu spreadsheet")
    spreadsheet_token = node["obj_token"]
    sheet = request_json(f"https://open.feishu.cn/open-apis/sheets/v3/spreadsheets/{spreadsheet_token}/sheets/query", method="GET", token=token)["data"]["sheets"][0]
    values = request_json(f"https://open.feishu.cn/open-apis/sheets/v2/spreadsheets/{spreadsheet_token}/values/{sheet['sheet_id']}!A1:Z1000", method="GET", token=token)["data"]["valueRange"].get("values", [])
    if not values or "英文关键词" not in values[0]:
        raise RuntimeError("root library requires an 英文关键词 column")
    index = values[0].index("英文关键词")
    roots: list[str] = []
    seen: set[str] = set()
    for row in values[1:]:
        if len(row) <= index or not row[index]:
            continue
        root = " ".join(str(row[index]).split()).lower()
        if root and root not in seen:
            seen.add(root)
            roots.append(root)
    return roots if preserve_order else sorted(roots)


def _cell_link(value: object) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, list) and value and isinstance(value[0], dict):
        return str(value[0].get("link", ""))
    if isinstance(value, dict):
        return str(value.get("link", ""))
    return ""


def parse_ranked_products(values: list[list[object]], source_url: str) -> list[RankedProduct]:
    if not values:
        return []
    header = [str(value) for value in values[0]]
    try:
        rank_index = header.index("排名")
        name_index = header.index("产品")
        visits_index = header.index("月访问量")
        growth_index = header.index("月增长")
        link_index = header.index("Toolify详情页")
    except ValueError as error:
        raise RuntimeError("ranking sheet requires 排名, 产品, 月访问量, 月增长, Toolify详情页 columns") from error
    products: list[RankedProduct] = []
    for row in values[1:]:
        if len(row) <= max(rank_index, name_index, visits_index, growth_index, link_index):
            continue
        try:
            rank = int(str(row[rank_index]))
        except ValueError:
            continue
        name, detail_url = str(row[name_index]).strip(), _cell_link(row[link_index])
        if name and detail_url:
            products.append(RankedProduct(name, detail_url, rank, str(row[visits_index]), str(row[growth_index]), "", source_url))
    return sorted(products, key=lambda product: product.rank)


def load_ranked_products_from_wiki(wiki_url: str, sheet_title: str, env: dict[str, str] | None = None) -> list[RankedProduct]:
    token = tenant_access_token(env or load_env())
    node = resolve_wiki_node(wiki_url, token)
    if node.get("obj_type") != "sheet":
        raise RuntimeError("ranking source must be a Feishu spreadsheet")
    spreadsheet_token = node["obj_token"]
    sheets = request_json(f"https://open.feishu.cn/open-apis/sheets/v3/spreadsheets/{spreadsheet_token}/sheets/query", method="GET", token=token)["data"]["sheets"]
    sheet = next((item for item in sheets if item["title"] == sheet_title), None)
    if sheet is None:
        raise RuntimeError(f"ranking worksheet not found: {sheet_title}")
    values = request_json(f"https://open.feishu.cn/open-apis/sheets/v2/spreadsheets/{spreadsheet_token}/values/{sheet['sheet_id']}!A1:Z1000", method="GET", token=token)["data"]["valueRange"].get("values", [])
    return parse_ranked_products(values, wiki_url)
