"""Rebuild existing Feishu keyword rows from the canonical SQLite records.

This intentionally updates rows by keyword and never clears the worksheet.
"""
from __future__ import annotations

import json
import sqlite3
from datetime import date
from pathlib import Path

from keyword_loop.core.publishing.feishu import load_env, publish_wiki, request_json, tenant_access_token, resolve_wiki_node
from keyword_loop.core.data.models import KeywordCandidate

WIKI_URL = "https://my.feishu.cn/wiki/VHnXwGzGQiGeUkkgj4tc4kpLnbh?sheet=e2e503"
DB = Path("output/keyword-loop.sqlite3")


def main() -> None:
    env = load_env()
    token = tenant_access_token(env)
    node = resolve_wiki_node(WIKI_URL, token)
    existing = request_json(
        f"https://open.feishu.cn/open-apis/sheets/v2/spreadsheets/{node['obj_token']}/values/e2e503!A2:A5000",
        method="GET", token=token,
    )["data"]["valueRange"].get("values", [])
    keywords = {" ".join(str(row[0]).lower().split()) for row in existing if row and row[0]}

    db = sqlite3.connect(DB)
    rows = db.execute(
        """SELECT k.keyword,k.volume,k.kd,k.intent,k.market,k.retrieved_at,
                  GROUP_CONCAT(DISTINCT p.root),GROUP_CONCAT(DISTINCT p.result_type)
           FROM keywords k LEFT JOIN provenance p ON p.keyword=k.keyword AND p.market=k.market
           GROUP BY k.keyword,k.market"""
    ).fetchall()
    candidates = [KeywordCandidate(k, v, kd, intent, market, tuple(sorted((roots or "").split(","))),
                                   tuple(sorted((types or "").split(","))), retrieved)
                  for k,v,kd,intent,market,retrieved,roots,types in rows
                  if k in keywords]
    validations: dict[str, dict[str, dict]] = {}
    for k, market in db.execute("SELECT keyword,market FROM keywords WHERE keyword IN (%s)" % ",".join("?"*len(keywords)), tuple(keywords)) if keywords else []:
        stages = {}
        for stage in ("semrush", "serper", "ai_initial", "ai_screen"):
            item = db.execute("SELECT payload_json FROM keyword_validation WHERE keyword=? AND market=? AND stage=?", (k,market,stage)).fetchone()
            if item: stages[stage] = json.loads(item[0])
        validations[k] = stages
    scores, payloads, enrichments = {}, {}, {}
    for k, score, payload, explanation in db.execute("SELECT keyword,score,payload_json,explanation_json FROM kd_enrichment"):
        if k in keywords:
            scores[k] = score; payloads[k] = json.loads(payload); enrichments[k] = tuple(json.loads(explanation))
    publish_wiki(WIKI_URL, candidates, env=env, enrichments=enrichments, gofei_scores=scores,
                 gofei_payloads=payloads, validations=validations)
    print(f"rebuilt={len(candidates)} existing={len(keywords)}")


if __name__ == "__main__":
    main()
