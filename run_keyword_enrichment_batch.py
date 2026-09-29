import json
import argparse
import time
from datetime import date
from pathlib import Path

from keyword_loop.core.publishing.feishu import load_env, publish_wiki
from keyword_loop.core.data.store import KeywordStore
from keyword_loop.core.clients.webcafe import WebCafeClient, WebCafeError, explain_payload, retrieved_at
from run_serper_batch import validations_for


DB = Path(__file__).parent / "output/keyword-loop.sqlite3"
FEISHU_URL = "https://my.feishu.cn/wiki/VHnXwGzGQiGeUkkgj4tc4kpLnbh?sheet=e2e503"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-date", type=date.fromisoformat, default=date.today())
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    store = KeywordStore(DB)
    # The account permits 10 calls per minute. Seven seconds leaves room for
    # request duration and prevents adjacent batches from crossing the limit.
    client = WebCafeClient(load_env()["SEO_WEBCAFE_TOKEN"], interval=7)
    candidates = store.daily_accepted_candidates(args.run_date)
    done = 0
    failed = 0
    for candidate in candidates:
        if store.connection.execute("SELECT 1 FROM kd_enrichment WHERE keyword=? AND market=?", (candidate.keyword, candidate.market)).fetchone():
            continue
        try:
            payload = client.estimate(candidate.keyword)
        except WebCafeError as error:
            failed += 1
            reason = str(error).lower()
            # A rate-limit response is recoverable. Wait a full minute and
            # continue the queue; transient failures get a short retry window.
            wait = 60 if "429" in reason or "rate" in reason or "limit" in reason else 15
            print(f"retry keyword={candidate.keyword!r} wait={wait}s reason={error}", flush=True)
            time.sleep(wait)
            try:
                payload = client.estimate(candidate.keyword)
            except WebCafeError as retry_error:
                store.record_failure("kd:" + candidate.keyword, type(retry_error).__name__)
                print(f"skipped keyword={candidate.keyword!r} reason={retry_error}", flush=True)
                continue
        store.record_enrichment(candidate.keyword, candidate.market, payload, explain_payload(candidate.keyword, payload), retrieved_at())
        done += 1
        if done >= 60:
            break
    enrichments, scores, payloads = {}, {}, {}
    for keyword, market, score, payload_json, explanation_json in store.connection.execute("SELECT keyword, market, score, payload_json, explanation_json FROM kd_enrichment"):
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
    print(f"batch={done} failed={failed} cached={len(enrichments)}")


if __name__ == "__main__":
    main()
