#!/usr/bin/env python3
"""Generate the canonical local keyword site-opportunity dataset."""

import argparse
import json
from pathlib import Path

from keyword_site_analysis import analyze_database


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--database", type=Path, default=Path("output/keyword-loop.sqlite3"))
    parser.add_argument("--output", type=Path, default=Path("outputs/keyword_site_analysis_20260911_local/keyword_site_analysis.json"))
    args = parser.parse_args()
    result = analyze_database(args.database)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result["summary"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
