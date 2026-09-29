"""Run annotation-only AI screening and republish accepted keywords."""
import json
import argparse
from datetime import date
from pathlib import Path

from keyword_loop.core.clients.ai_screen import AIScreenClient, AIScreenError
from keyword_loop.core.publishing.feishu import load_env, publish_wiki
from keyword_loop.core.data.store import KeywordStore
from run_serper_batch import validations_for


DB = Path(__file__).parent / "output/keyword-loop.sqlite3"
FEISHU_URL = "https://my.feishu.cn/wiki/VHnXwGzGQiGeUkkgj4tc4kpLnbh?sheet=e2e503"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-date", type=date.fromisoformat, default=date.today())
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    env = load_env()
    if not env.get("OPENAI_API_KEY"):
        raise RuntimeError("OPENAI_API_KEY is required for AI screening")
    store = KeywordStore(DB)
    candidates = store.daily_accepted_candidates(args.run_date)
    client = AIScreenClient(
        env["OPENAI_API_KEY"],
        model=env.get("AI_SCREEN_MODEL", "gpt-5.6-sol"),
        base_url=env.get("AI_SCREEN_BASE_URL", "https://api.openai.com"),
    )
    done = 0
    for candidate in candidates:
        if store.validation(candidate.keyword, candidate.market, "ai_screen") is not None:
            continue
        try:
            payload = client.assess(
                candidate.keyword,
                store.validation(candidate.keyword, candidate.market, "semrush") or {},
                store.validation(candidate.keyword, candidate.market, "serper") or {},
            )
        except AIScreenError as error:
            print(f"paused_after={done} reason={error}")
            return
        store.record_validation(candidate.keyword, candidate.market, "ai_screen", payload)
        done += 1
    enrichments, scores, payloads = {}, {}, {}
    for keyword, market, score, payload_json, explanation_json in store.connection.execute(
        "SELECT keyword, market, score, payload_json, explanation_json FROM kd_enrichment"
    ):
        enrichments[keyword] = tuple(json.loads(explanation_json))
        scores[keyword] = score
        payloads[keyword] = json.loads(payload_json)
    publish_wiki(FEISHU_URL, candidates, enrichments=enrichments, gofei_scores=scores, gofei_payloads=payloads, validations=validations_for(store, candidates))
    print(f"ai_screen_batch={done} published={len(candidates)}")


if __name__ == "__main__":
    main()
