"""CLI for Similarweb and Semrush discovery without downstream publication."""

from __future__ import annotations

import argparse
from pathlib import Path

from ...core.clients.semrush_browser import SemrushBrowserProvider
from ...core.clients.similarweb import SimilarwebCollector
from ...core.data.store import KeywordStore
from .pipeline import run_discovery, source_terms
from .independent import run_independent


DEFAULT_STRIPE_URL = "https://seo.web.cafe/referring/"
DEFAULT_TOOLIFY_URL = "https://www.toolify.ai/Best-trending-AI-Tools"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Similarweb and Semrush keyword discovery only.")
    parser.add_argument("--database", type=Path, default=Path("output/keyword-loop.sqlite3"))
    parser.add_argument("--cdp-url", default="http://127.0.0.1:9222")
    parser.add_argument("--sources", default="stripe,toolify,root")
    parser.add_argument("--mode", choices=["independent", "cross-validation"], default="independent",
                        help="Default: each provider discovers and filters its own keywords")
    parser.add_argument("--providers", default="similarweb,semrush")
    parser.add_argument("--provider-limit", type=int, default=50,
                        help="New unique keywords per selected provider; 0 means unlimited (independent mode)")
    parser.add_argument("--stripe-url", default=DEFAULT_STRIPE_URL)
    parser.add_argument("--toolify-url", default=DEFAULT_TOOLIFY_URL)
    parser.add_argument("--roots-feishu-url")
    parser.add_argument("--source-limit", type=int, default=200, help="Sources per list; 0 means all available")
    parser.add_argument("--per-term-cap", type=int, default=500, help="Keywords per seed; 0 means all available pages")
    parser.add_argument("--semrush-limit", type=int, help="Legacy cross-validation target; independent mode uses --provider-limit")
    parser.add_argument("--source-approved-limit", type=int)
    parser.add_argument("--new-only", action="store_true", help="Count only newly approved Similarweb+Semrush keywords toward --semrush-limit.")
    parser.add_argument("--continue-on-error", action="store_true", help="Record a failed source seed and continue to the next seed")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if min(args.provider_limit, args.source_limit, args.per_term_cap) < 0:
        raise SystemExit("Limits must be nonnegative; 0 means unlimited")
    if args.mode == "independent" and args.semrush_limit is not None:
        raise SystemExit("Use --provider-limit for independent discovery, or --mode cross-validation for the legacy --semrush-limit")
    if args.mode == "cross-validation" and args.semrush_limit is None:
        args.semrush_limit = 60
    if args.mode == "independent" and args.source_approved_limit is not None:
        raise SystemExit("Independent mode uses --provider-limit; --source-approved-limit is for legacy cross-validation only")
    store = KeywordStore(args.database)
    similarweb = SimilarwebCollector(cdp_url=args.cdp_url, per_root_cap=args.per_term_cap, discovery_filters=True)
    semrush = SemrushBrowserProvider(cdp_url=args.cdp_url, discovery_filters=True, per_root_cap=args.per_term_cap if args.mode == "independent" else 100)
    if args.mode == "independent":
        totals = run_independent(args, store, similarweb, semrush, source_terms(args))
        print(totals, flush=True)
        if any(item["status"] == "blocked" for item in totals.values()):
            raise SystemExit(2)
        return
    totals = run_discovery(args, store, similarweb, semrush)
    source_counts = {source.strip(): store.source_accepted_count(source.strip()) for source in args.sources.split(",")}
    print({**totals.to_dict(), "source_accepted": source_counts})


if __name__ == "__main__":
    main()
