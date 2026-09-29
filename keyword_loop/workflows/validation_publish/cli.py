"""CLI for AI, Serper, Web.Cafe KD, and Feishu publication."""

from __future__ import annotations

import argparse
from datetime import date
from pathlib import Path

from ...core.clients.ai_screen import AIScreenClient
from ...core.publishing.feishu import load_env
from ...core.clients.semrush_browser import SemrushBrowserProvider
from ...core.clients.serper import SerperClient
from ...core.data.store import KeywordStore
from ...core.clients.webcafe import WebCafeClient
from .pipeline import run_validation_publish


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Deep keyword validation and Feishu publication.")
    parser.add_argument("--run-date", type=date.fromisoformat, default=date.today())
    parser.add_argument("--database", type=Path, default=Path("output/keyword-loop.sqlite3"))
    parser.add_argument("--results-feishu-url", required=True)
    parser.add_argument("--cdp-url", default="http://127.0.0.1:9222")
    parser.add_argument("--limit", type=int, default=60)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    environment = load_env()
    totals = run_validation_publish(
        args.run_date,
        KeywordStore(args.database),
        SemrushBrowserProvider(cdp_url=args.cdp_url),
        AIScreenClient(environment["OPENAI_API_KEY"], model=environment.get("AI_SCREEN_MODEL", "gpt-5.5"), base_url=environment.get("AI_SCREEN_BASE_URL", "https://api.openai.com")),
        SerperClient(environment["SERPER_API_KEY"]),
        WebCafeClient(environment["SEO_WEBCAFE_TOKEN"], interval=7),
        args.results_feishu_url,
        args.limit,
    )
    print(totals.to_dict())


if __name__ == "__main__":
    main()
