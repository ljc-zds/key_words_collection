"""Run the Google Trends new-word radar from a Feishu root library."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from keyword_loop.core.publishing.feishu import load_roots_from_wiki
from .google_trends.client import GoogleTrendsClient
from .google_trends.fallback import FallbackGoogleTrendsClient, CollectionStopped
from .pipeline import scan_roots


def load_resume_state(output: Path) -> tuple[list[dict], set[str], dict[str, dict], dict[str, dict]]:
    """Return prior records plus completed and failed parents for safe resumption."""
    if not output.exists():
        return [], set(), {}, {}
    payload = json.loads(output.read_text(encoding="utf-8"))
    records = payload.get("evaluated_candidates", [])
    parents = payload.get("completed_parents", [])
    pending = payload.get("pending_parents", [])
    parent_rising = payload.get("parent_rising", [])
    if not isinstance(records, list) or not isinstance(parents, list) or not isinstance(pending, list) or not isinstance(parent_rising, list):
        raise ValueError(f"Invalid trend radar checkpoint: {output}")
    failed_parents = {
        str(parent["parent_keyword"]).lower(): parent
        for parent in pending
        if isinstance(parent, dict) and parent.get("parent_keyword") and parent.get("root")
    }
    rising = {str(parent["parent_keyword"]).lower(): parent for parent in parent_rising if isinstance(parent, dict) and parent.get("parent_keyword")}
    return records, {str(parent).lower() for parent in parents}, failed_parents, rising


def save_results(output: Path, records: list[dict], completed_parents: set[str], failed_parents: dict[str, dict], parent_rising: dict[str, dict], max_depth: int | None) -> None:
    """Atomically persist progress so interrupted scans can resume safely."""
    results = {
        "rules": {"rising": "Breakout or growth_percent >= 500", "baseline": "past 30 days: first 21 days", "recent": "last 9 days", "max_depth": max_depth},
        "completed_parents": sorted(completed_parents),
        "pending_parents": sorted(failed_parents.values(), key=lambda parent: parent["parent_keyword"].lower()),
        "parent_rising": sorted(parent_rising.values(), key=lambda parent: parent["parent_keyword"].lower()),
        "evaluated_candidates": records,
        "new_words": [record for record in records if record["comparison"]["is_new_word"]],
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(f"{output.suffix}.tmp")
    temporary.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(temporary, output)


def build_client(cdp_url: str | None):
    """Use new URL-loaded pages, classic fallback, then stop on dual failure."""
    return FallbackGoogleTrendsClient(cdp_url) if cdp_url else GoogleTrendsClient()


def main() -> None:
    parser = argparse.ArgumentParser(description="Find Google Trends Rising words that cross above gpts.")
    parser.add_argument("--roots-feishu-url", required=True)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--max-depth", type=int, help="Optional Rising-query expansion depth limit")
    parser.add_argument("--cdp-url", default="http://127.0.0.1:9229", help="Dedicated Google Trends Chrome CDP session")
    parser.add_argument("--output", type=Path, default=Path("output/trend-radar.json"))
    args = parser.parse_args()
    roots = load_roots_from_wiki(args.roots_feishu_url, preserve_order=True)
    if args.limit:
        roots = roots[:args.limit]
    client = build_client(args.cdp_url)
    existing_records, completed_parents, failed_parents, parent_rising = load_resume_state(args.output)
    records = scan_roots(
        roots,
        client,
        max_depth=args.max_depth,
        existing_records=existing_records,
        completed_parents=completed_parents,
        failed_parents=failed_parents,
        parent_rising=parent_rising,
        on_checkpoint=lambda current, completed, failed: save_results(args.output, current, completed, failed, parent_rising, args.max_depth),
    )
    save_results(args.output, records, completed_parents, failed_parents, parent_rising, args.max_depth)
    print({"roots": len(roots), "evaluated_candidates": len(records), "new_words": sum(record["comparison"]["is_new_word"] for record in records), "output": str(args.output)})


if __name__ == "__main__":
    try:
        main()
    except CollectionStopped as error:
        print(str(error) + ' 检查点已保存；不会继续请求后续词。', file=sys.stderr, flush=True)
        raise SystemExit(2)
