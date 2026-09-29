import argparse
from dataclasses import dataclass
from pathlib import Path

from ..publishing.feishu import load_roots_from_wiki, publish_wiki, load_env
from ..data.store import KeywordStore
from ..clients.similarweb import SimilarwebCollector
from ..clients.webcafe import WebCafeClient, explain_payload, retrieved_at


@dataclass(frozen=True)
class RunResult:
    candidate_count: int
    published: bool
    failed_roots: tuple[str, ...] = ()


def run(*, roots: list[str], database: Path, dry_run: bool, collector, results_wiki_url: str | None = None, review_limit: int = 60, kd_client=None) -> RunResult:
    store = KeywordStore(database)
    failed_roots: list[str] = []
    completed_roots = 0
    for root in roots:
        try:
            for item in collector.collect(root):
                store.record(item)
        except Exception as error:
            failed_roots.append(root)
            store.record_failure(root, type(error).__name__)
        else:
            completed_roots += 1
    # The generic collector only builds the candidate pool. Never publish pool
    # rows directly; publication is reserved for the daily gate pipeline.
    candidates = []
    if kd_client:
        for candidate in candidates:
            if store.connection.execute("SELECT 1 FROM kd_enrichment WHERE keyword=? AND market=?", (candidate.keyword, candidate.market)).fetchone():
                continue
            try:
                payload = kd_client.estimate(candidate.keyword)
                store.record_enrichment(candidate.keyword, candidate.market, payload, explain_payload(candidate.keyword, payload), retrieved_at())
            except Exception as error:
                store.record_failure("kd:" + candidate.keyword, type(error).__name__)
    if not dry_run:
        if not results_wiki_url:
            raise ValueError("results_wiki_url is required unless --dry-run is used")
        if candidates:
            publish_wiki(results_wiki_url, candidates)
    return RunResult(len(candidates), not dry_run, tuple(failed_roots))


def main() -> None:
    parser = argparse.ArgumentParser(description="Collect subscription keyword candidates from Similarweb.")
    parser.add_argument("--roots-feishu-url", required=True)
    parser.add_argument("--results-feishu-url", required=True)
    parser.add_argument("--database", type=Path, default=Path("output/keyword-loop.sqlite3"))
    parser.add_argument("--browser", type=Path, default=Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"))
    parser.add_argument("--profile", type=Path, default=Path("runtime/keyword-loop-profile"))
    parser.add_argument("--cdp-url", help="Connect to an already-open Chrome, for example http://127.0.0.1:9222")
    parser.add_argument("--per-root-cap", type=int, default=500)
    parser.add_argument("--review-limit", "--daily-limit", type=int, default=60)
    parser.add_argument("--root-limit", type=int)
    parser.add_argument("--root-offset", type=int, default=0)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--webcafe-token", default=None)
    parser.add_argument("--skip-kd", action="store_true", help="先发布硬筛结果，跳过限流的哥飞 KD 注释")
    arguments = parser.parse_args()
    roots = load_roots_from_wiki(arguments.roots_feishu_url)
    state_store = KeywordStore(arguments.database)
    saved_offset = int(state_store.get_state("root_offset", "0") or "0")
    offset = max(arguments.root_offset, saved_offset)
    roots = roots[offset:]
    if arguments.root_limit:
        roots = roots[:arguments.root_limit]
    collector = SimilarwebCollector(browser=arguments.browser, profile=arguments.profile, per_root_cap=arguments.per_root_cap, cdp_url=arguments.cdp_url)
    env = load_env()
    kd_token = arguments.webcafe_token or env.get("SEO_WEBCAFE_TOKEN")
    kd_client = None if arguments.skip_kd else (WebCafeClient(kd_token) if kd_token else None)
    result = run(roots=roots, database=arguments.database, dry_run=arguments.dry_run, collector=collector, results_wiki_url=arguments.results_feishu_url, review_limit=arguments.review_limit, kd_client=kd_client)
    # Advance only past roots that completed successfully; failed roots remain
    # at the checkpoint and are retried on the next run.
    state_store.set_state("root_offset", str(offset + completed_roots))
    print(f"candidates={result.candidate_count} published={result.published} failed_roots={len(result.failed_roots)}")


if __name__ == "__main__":
    main()
