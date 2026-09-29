#!/usr/bin/env python3
"""Fetch fresh Web.Cafe KD and Serper data for the selected prompt keywords."""

from __future__ import annotations

import json
import time
from pathlib import Path

from keyword_loop.core.clients.serper import SerperClient
from keyword_loop.core.clients.webcafe import WebCafeClient
from keyword_loop.core.publishing.feishu import load_env


KEYWORDS = (
    "video to prompt generator",
    "chatgpt prompt generator",
    "claude prompt generator",
    "image to prompt generator",
)
OUTPUT = Path("outputs/keyword_site_analysis_20260923_full/prompt_keywords_gofei_serp.json")


def main() -> None:
    environment = load_env()
    gofei = WebCafeClient(environment["SEO_WEBCAFE_TOKEN"], gl="us", hl="en", interval=7)
    serper = SerperClient(environment["SERPER_API_KEY"], gl="us", hl="en")
    rows = []
    for index, keyword in enumerate(KEYWORDS, 1):
        row = {"keyword": keyword}
        try:
            row["gofei"] = gofei.estimate(keyword)
        except Exception as error:
            row["gofei_error"] = f"{type(error).__name__}: {error}"
        try:
            row["serp"] = serper.analyze(keyword)
        except Exception as error:
            row["serp_error"] = f"{type(error).__name__}: {error}"
        rows.append(row)
        print(f"completed={index}/{len(KEYWORDS)} keyword={keyword!r}", flush=True)
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(
        json.dumps(
            {
                "market": "US",
                "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "rows": rows,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"wrote={OUTPUT}")


if __name__ == "__main__":
    main()
