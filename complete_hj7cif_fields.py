"""Fill only missing final-stage fields for the quality-approved HJ7cif terms."""

from __future__ import annotations

import json
from pathlib import Path

from backfill_existing_feishu import compact_ai_item
from keyword_loop.core.clients.ai_screen import AIScreenClient
from keyword_loop.core.publishing.feishu import load_env, publish_wiki, request_json, resolve_wiki_node, tenant_access_token
from keyword_loop.core.data.models import KeywordCandidate
from keyword_loop.core.clients.serper import SerperClient
from keyword_loop.core.data.store import KeywordStore
from keyword_loop.core.clients.webcafe import WebCafeClient, explain_payload, retrieved_at
from run_serper_batch import validations_for


WIKI_URL = "https://my.feishu.cn/wiki/VHnXwGzGQiGeUkkgj4tc4kpLnbh?sheet=HJ7cif"
DB = Path("output/keyword-loop.sqlite3")


def current_sheet_keywords(env: dict[str, str]) -> list[str]:
    token = tenant_access_token(env)
    spreadsheet = resolve_wiki_node(WIKI_URL, token)["obj_token"]
    rows = request_json(
        f"https://open.feishu.cn/open-apis/sheets/v2/spreadsheets/{spreadsheet}/values/HJ7cif!A2:A5000",
        method="GET", token=token,
    )["data"]["valueRange"].get("values", [])
    return [" ".join(str(row[0]).lower().split()) for row in rows if row and row[0]]


def candidate(store: KeywordStore, keyword: str) -> KeywordCandidate:
    row = store.connection.execute(
        """SELECT keyword, volume, kd, intent, market, retrieved_at FROM keywords
           WHERE keyword=? AND market='global' ORDER BY retrieved_at DESC LIMIT 1""",
        (keyword,),
    ).fetchone()
    if not row:
        raise RuntimeError(f"missing SQLite keyword data: {keyword}")
    roots = tuple(sorted(x[0] for x in store.connection.execute(
        "SELECT DISTINCT root FROM provenance WHERE keyword=? AND market=?", (row[0], row[4])
    ))) or ("未知",)
    types = tuple(sorted(x[0] for x in store.connection.execute(
        "SELECT DISTINCT result_type FROM provenance WHERE keyword=? AND market=?", (row[0], row[4])
    ))) or ("未知",)
    return KeywordCandidate(row[0], int(row[1]), int(row[2]), row[3], row[4], roots, types, row[5])


def all_enrichments(store: KeywordStore) -> tuple[dict, dict, dict]:
    explanations, scores, payloads = {}, {}, {}
    for keyword, market, score, payload_json, explanation_json in store.connection.execute(
        "SELECT keyword, market, score, payload_json, explanation_json FROM kd_enrichment"
    ):
        explanations[keyword] = tuple(json.loads(explanation_json))
        scores[keyword] = score
        payloads[keyword] = json.loads(payload_json)
    return explanations, scores, payloads


def batches(items: list[dict], size: int = 10):
    for start in range(0, len(items), size):
        yield items[start:start + size]


def main() -> None:
    env = load_env()
    store = KeywordStore(DB)
    candidates = [candidate(store, keyword) for keyword in current_sheet_keywords(env)]
    serper = SerperClient(env["SERPER_API_KEY"])
    webcafe = WebCafeClient(env["SEO_WEBCAFE_TOKEN"], interval=7)

    for item in candidates:
        if store.validation(item.keyword, item.market, "serper") is None:
            store.record_validation(item.keyword, item.market, "serper", serper.analyze(item.keyword))
            print(f"serper={item.keyword}", flush=True)
        exists = store.connection.execute(
            "SELECT 1 FROM kd_enrichment WHERE keyword=? AND market=?", (item.keyword, item.market)
        ).fetchone()
        if not exists:
            payload = webcafe.estimate(item.keyword)
            store.record_enrichment(item.keyword, item.market, payload, explain_payload(item.keyword, payload), retrieved_at())
            print(f"gofei={item.keyword}", flush=True)

    ai = AIScreenClient(
        env["OPENAI_API_KEY"], model=env.get("AI_SCREEN_MODEL", "gpt-5.5"),
        base_url=env.get("AI_SCREEN_BASE_URL", "https://api.openai.com"),
    )
    pending = [item for item in candidates if not (store.validation(item.keyword, item.market, "ai_screen") or {}).get("decision")]
    # The configured Responses-compatible endpoint has proven reliable for
    # single JSON objects but intermittently stalls on JSON-array batches.
    # Persist each completed item so the next run always resumes cleanly.
    for index, item in enumerate(pending, 1):
        gofei_row = store.connection.execute(
            "SELECT payload_json FROM kd_enrichment WHERE keyword=? AND market=?", (item.keyword, item.market)
        ).fetchone()
        request_item = compact_ai_item(
            item.keyword, store.validation(item.keyword, item.market, "semrush") or {},
            store.validation(item.keyword, item.market, "serper") or {},
            json.loads(gofei_row[0]) if gofei_row else {},
        )
        result = ai.assess(
            item.keyword, {**request_item["semrush"], "gofei": request_item["gofei"]}, request_item["serp"], stage="final"
        )
        store.record_validation(item.keyword, item.market, "ai_screen", result)
        store.record_validation(item.keyword, item.market, "intent_gate", result)
        print(f"ai_completed={index}/{len(pending)} keyword={item.keyword}", flush=True)

    enrichments, scores, payloads = all_enrichments(store)
    publish_wiki(WIKI_URL, candidates, env=env, enrichments=enrichments, gofei_scores=scores,
                 gofei_payloads=payloads, validations=validations_for(store, candidates))
    print(f"published={len(candidates)}", flush=True)


if __name__ == "__main__":
    main()
