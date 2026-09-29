"""Revalidate HJ7cif exact Semrush matches, then compact rejected rows."""

from __future__ import annotations

import json

from keyword_loop.core.publishing.feishu import load_env, publish_wiki, request_json, resolve_wiki_node, tenant_access_token
from keyword_loop.core.data.models import KeywordCandidate
from keyword_loop.core.clients.semrush_browser import SemrushBrowserProvider
from keyword_loop.core.screening.screening import volume_kd_gate
from keyword_loop.core.data.store import KeywordStore
from run_serper_batch import validations_for


WIKI_URL = "https://my.feishu.cn/wiki/VHnXwGzGQiGeUkkgj4tc4kpLnbh?sheet=HJ7cif"
SHEET_ID = "HJ7cif"
TERMS = (
    "connections hint", "convertir pdf a word", "editar pdf", "modifier pdf",
    "nyt connections hints today", "nyt strands hints", "pdf ke word", "pdf ocr",
    "pdf to word free", "wordle hint", "wordle hints",
)


def make_candidate(store: KeywordStore, keyword: str) -> KeywordCandidate:
    row = store.connection.execute(
        "SELECT keyword,volume,kd,intent,market,retrieved_at FROM keywords WHERE keyword=? AND market='global'",
        (keyword,),
    ).fetchone()
    if not row:
        raise RuntimeError(f"missing keyword: {keyword}")
    roots = tuple(x[0] for x in store.connection.execute("SELECT DISTINCT root FROM provenance WHERE keyword=? AND market=?", (row[0], row[4]))) or ("未知",)
    types = tuple(x[0] for x in store.connection.execute("SELECT DISTINCT result_type FROM provenance WHERE keyword=? AND market=?", (row[0], row[4]))) or ("未知",)
    return KeywordCandidate(row[0], int(row[1]), int(row[2]), row[3], row[4], roots, types, row[5])


def enrichment_maps(store: KeywordStore) -> tuple[dict, dict, dict]:
    enrichments, scores, payloads = {}, {}, {}
    for k, _market, score, payload, explanation in store.connection.execute("SELECT keyword,market,score,payload_json,explanation_json FROM kd_enrichment"):
        enrichments[k], scores[k], payloads[k] = tuple(json.loads(explanation)), score, json.loads(payload)
    return enrichments, scores, payloads


def main() -> None:
    env = load_env()
    store = KeywordStore("output/keyword-loop.sqlite3")
    provider = SemrushBrowserProvider(cdp_url="http://127.0.0.1:9222")
    for keyword in TERMS:
        previous = store.validation(keyword, "global", "semrush") or {}
        if previous.get("source") == "cdp_recheck_isolated_page" and previous.get("exact_keyword_found"):
            print(f"{keyword}: cached recheck", flush=True)
            continue
        response = provider.query(keyword)
        exact = next((row for row in response["keywords"] if str(row.get("keyword", "")).strip().casefold() == keyword.casefold()), None)
        if exact is None:
            raise RuntimeError(f"unexpected missing exact result on recheck: {keyword}")
        gate = volume_kd_gate(exact.get("volume"), exact.get("kd"))
        store.record_validation(keyword, "global", "semrush", {
            "exact_keyword_found": True, "source": "cdp_recheck_isolated_page", **exact,
            "gate_decision": gate.decision, "gate_reason": gate.reason,
        })
        if gate.decision == "淘汰":
            store.record_validation(keyword, "global", "manual_prune", {
                "decision": "淘汰", "reason": f"Semrush US 复查后：{gate.reason}", "sheet": SHEET_ID,
            })
        print(f"{keyword}: {gate.decision}", flush=True)

    token = tenant_access_token(env)
    spreadsheet = resolve_wiki_node(WIKI_URL, token)["obj_token"]
    rows = request_json(f"https://open.feishu.cn/open-apis/sheets/v2/spreadsheets/{spreadsheet}/values/{SHEET_ID}!A1:AR5000", method="GET", token=token)["data"]["valueRange"].get("values", [])
    header, existing = rows[0], rows[1:]
    remaining = []
    for row in existing:
        if not row or not row[0]:
            continue
        keyword = " ".join(str(row[0]).lower().split())
        sem = store.validation(keyword, "global", "semrush") or {}
        if sem.get("gate_decision") == "保留":
            remaining.append(keyword)
    candidates = [make_candidate(store, keyword) for keyword in remaining]
    enrichments, scores, payloads = enrichment_maps(store)
    publish_wiki(WIKI_URL, candidates, env=env, enrichments=enrichments, gofei_scores=scores,
                 gofei_payloads=payloads, validations=validations_for(store, candidates))

    # Re-read after publish so compaction keeps the refreshed Semrush cells.
    refreshed = request_json(
        f"https://open.feishu.cn/open-apis/sheets/v2/spreadsheets/{spreadsheet}/values/{SHEET_ID}!A1:AR5000",
        method="GET", token=token,
    )["data"]["valueRange"].get("values", [])
    compacted = [refreshed[0]] + [row for row in refreshed[1:] if row and row[0] and " ".join(str(row[0]).lower().split()) in set(remaining)]
    values_url = f"https://open.feishu.cn/open-apis/sheets/v2/spreadsheets/{spreadsheet}/values"
    request_json(f"{values_url}_batch_update", method="POST", token=token,
                 payload={"valueRanges": [{"range": f"{SHEET_ID}!A1:AR{len(compacted)}", "values": compacted}]})
    if len(refreshed) > len(compacted):
        request_json(f"{values_url}_batch_update", method="POST", token=token,
                     payload={"valueRanges": [{"range": f"{SHEET_ID}!A{len(compacted)+1}:AR{len(refreshed)}", "values": [[""] * 44 for _ in range(len(refreshed) - len(compacted))]}]})
    verified = request_json(f"{values_url}/{SHEET_ID}!A1:A5000", method="GET", token=token)["data"]["valueRange"].get("values", [])
    actual = [str(row[0]).strip().lower() for row in verified[1:] if row and row[0]]
    if set(actual) != set(remaining):
        raise RuntimeError(f"Feishu verification failed: {actual}")
    print({"retained": actual, "removed": len(existing) - len(actual)})


if __name__ == "__main__":
    main()
