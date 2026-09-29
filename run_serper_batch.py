"""Annotate hard-gate-approved keywords with Google SERP data and republish."""
import json
import argparse
from datetime import date
from pathlib import Path

from keyword_loop.core.publishing.feishu import load_env, publish_wiki
from keyword_loop.core.clients.serper import SerperClient, SerperError
from keyword_loop.core.data.store import KeywordStore


DB = Path(__file__).parent / "output/keyword-loop.sqlite3"
FEISHU_URL = "https://my.feishu.cn/wiki/VHnXwGzGQiGeUkkgj4tc4kpLnbh?sheet=e2e503"


def validations_for(store: KeywordStore, candidates) -> dict[str, dict[str, dict]]:
    stages = ("semrush", "intent_gate", "ai_screen", "serper")
    return {
        candidate.keyword: {
            stage: payload
            for stage in stages
            if (payload := store.validation(candidate.keyword, candidate.market, stage)) is not None
        }
        for candidate in candidates
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-date", type=date.fromisoformat, default=date.today())
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    store = KeywordStore(DB)
    candidates = store.daily_accepted_candidates(args.run_date)
    client = SerperClient(load_env()["SERPER_API_KEY"])
    done = 0
    for candidate in candidates:
        if store.validation(candidate.keyword, candidate.market, "serper") is not None:
            continue
        try:
            store.record_validation(candidate.keyword, candidate.market, "serper", client.analyze(candidate.keyword))
        except SerperError as error:
            print(f"paused_after={done} reason={error}")
            return
        done += 1
    enrichments, scores, payloads = {}, {}, {}
    for keyword, market, score, payload_json, explanation_json in store.connection.execute(
        "SELECT keyword, market, score, payload_json, explanation_json FROM kd_enrichment"
    ):
        enrichments[keyword] = tuple(json.loads(explanation_json))
        scores[keyword] = score
        payloads[keyword] = json.loads(payload_json)
    publish_wiki(
        FEISHU_URL,
        candidates,
        enrichments=enrichments,
        gofei_scores=scores,
        gofei_payloads=payloads,
        validations=validations_for(store, candidates),
    )
    print(f"serper_batch={done} published={len(candidates)}")


if __name__ == "__main__":
    main()
