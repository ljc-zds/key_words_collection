"""Backfill final AI fields for the keywords currently present in Feishu.

The worksheet is the scope of work. Existing non-legacy AI records are left
unchanged; results are stored in SQLite first and then published by keyword.
"""
from __future__ import annotations

import json
import threading
import argparse
from urllib.parse import urlparse

from keyword_loop.core.clients.ai_screen import AIScreenClient
from keyword_loop.core.publishing.feishu import load_env, request_json, resolve_wiki_node, tenant_access_token
from keyword_loop.core.data.store import KeywordStore

WIKI_URL = "https://my.feishu.cn/wiki/VHnXwGzGQiGeUkkgj4tc4kpLnbh?sheet=e2e503"
DATABASE = "output/keyword-loop.sqlite3"


def sheet_keywords() -> list[tuple[str, str]]:
    token = tenant_access_token(load_env())
    node = resolve_wiki_node(WIKI_URL, token)
    rows = request_json(
        f"https://open.feishu.cn/open-apis/sheets/v2/spreadsheets/{node['obj_token']}/values/e2e503!A2:H5000",
        method="GET", token=token,
    )["data"]["valueRange"].get("values", [])
    return [(" ".join(str(row[0]).lower().split()), str(row[7]) if len(row) > 7 else "global") for row in rows if row and row[0]]


def chunks(items: list[tuple[str, str]], size: int = 10):
    for start in range(0, len(items), size):
        yield items[start:start + size]


def compact_ai_item(keyword: str, semrush: dict, serper: dict, gofei: dict) -> dict:
    """Keep batch input bounded while preserving the signals used for judgment."""
    organic = []
    for row in (serper.get("organic") or [])[:5]:
        if not isinstance(row, dict):
            continue
        organic.append({
            "position": row.get("position"),
            "title": str(row.get("title", ""))[:120],
            "domain": urlparse(str(row.get("link", ""))).netloc,
        })
    trend = gofei.get("keywordTrend") or {}
    budget = gofei.get("linkBudget") or {}
    return {
        "keyword": keyword,
        "semrush": {key: semrush.get(key) for key in ("volume", "kd", "cpc", "intent", "competitive_density", "serp_features", "gate_decision")},
        "serp": {
            "top_results": organic,
            "strong_site_count": serper.get("strong_site_count"),
            "paa": list(serper.get("paa") or [])[:5],
            "related": list(serper.get("related") or [])[:5],
        },
        "gofei": {
            "kd": gofei.get("score"),
            "generic_score": gofei.get("genericScore"),
            "trend": {key: trend.get(key) for key in ("ratio", "estimatedValue", "domain")},
            "link_budget": {key: budget.get(key) for key in ("low", "mid", "high", "targetDr")},
            "reasons": list(gofei.get("reasons") or [])[:3],
        },
    }


def assess_with_heartbeat(client: AIScreenClient, items: list[dict]) -> list[dict]:
    """Keep the long-running batch observable while waiting for its response."""
    result: list[dict] = []
    error: list[Exception] = []
    done = threading.Event()

    def run() -> None:
        try:
            result.extend(client.assess_batch(items, stage="final"))
        except Exception as exc:
            error.append(exc)
        finally:
            done.set()

    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    while not done.wait(10):
        print("ai_batch_waiting=true", flush=True)
    if error:
        raise error[0]
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--single", action="store_true", help="Use one durable AI call per keyword after batch timeout.")
    args = parser.parse_args()
    env = load_env()
    store = KeywordStore(DATABASE)
    pending: list[tuple[str, str]] = []
    for keyword, market in sheet_keywords():
        existing = store.validation(keyword, market, "ai_screen") or {}
        if existing.get("decision") not in {"保留", "淘汰"} or not existing.get("monetization"):
            pending.append((keyword, market))
    client = AIScreenClient(env["OPENAI_API_KEY"], model=env.get("AI_SCREEN_MODEL", "gpt-5.5"), base_url=env.get("AI_SCREEN_BASE_URL", "https://api.openai.com"))
    completed = 0
    for batch in chunks(pending):
        request_items = []
        for keyword, market in batch:
            enrichment = store.connection.execute(
                "SELECT payload_json FROM kd_enrichment WHERE keyword=? AND market=?",
                (keyword, market),
            ).fetchone()
            request_items.append(compact_ai_item(
                keyword,
                store.validation(keyword, market, "semrush") or {},
                store.validation(keyword, market, "serper") or {},
                json.loads(enrichment[0]) if enrichment else {},
            ))
        if args.single:
            for (keyword, market), item in zip(batch, request_items):
                result = client.assess(
                    item["keyword"], {**item["semrush"], "gofei": item["gofei"]}, item["serp"], stage="final"
                )
                store.record_validation(keyword, market, "ai_screen", result)
                store.record_validation(keyword, market, "intent_gate", result)
                completed += 1
                print(f"ai_single_completed={completed}/{len(pending)} keyword={keyword}", flush=True)
            continue
        else:
            results = assess_with_heartbeat(client, request_items)
        for (keyword, market), result in zip(batch, results):
            store.record_validation(keyword, market, "ai_screen", result)
            store.record_validation(keyword, market, "intent_gate", result)
            completed += 1
        print(f"ai_batch_completed={completed}/{len(pending)}", flush=True)
    print(f"ai_backfilled={completed} pending_before={len(pending)}")


if __name__ == "__main__":
    main()
