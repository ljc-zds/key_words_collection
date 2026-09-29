"""Validate queued keywords with Semrush through the OpenCLI browser proxy."""
import argparse
from datetime import date
from pathlib import Path

from keyword_loop.core.clients.semrush_browser import SemrushBrowserProvider
from keyword_loop.core.data.store import KeywordStore


DB = Path(__file__).parent / "output/keyword-loop.sqlite3"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-date", type=date.fromisoformat, default=date.today())
    parser.add_argument("--limit", type=int, default=60)
    parser.add_argument("--cdp-url", default=None, help="连接已登录 Chrome，例如 http://127.0.0.1:9222")
    args = parser.parse_args()
    store = KeywordStore(DB)
    provider = SemrushBrowserProvider(cdp_url=args.cdp_url)
    done = 0
    for run_date, keyword, market, source in store.unresolved_semrush_keywords():
        if run_date != args.run_date.isoformat():
            continue
        try:
            payload = provider.query(keyword)
            exact = next((row for row in payload.get("keywords", []) if str(row.get("keyword", "")).strip().lower() == keyword.lower()), None)
            if exact is None:
                store.record_daily_gate(args.run_date, keyword, market, "semrush", "保留", "Semrush未返回精确关键词")
                store.record_validation(keyword, market, "semrush", {"exact_keyword_found": False, "source": "browser_proxy", **payload})
            else:
                store.record_daily_gate(args.run_date, keyword, market, "semrush", "保留", "浏览器代理返回精确关键词")
                store.record_validation(keyword, market, "semrush", {"exact_keyword_found": True, "source": "browser_proxy", **exact})
            done += 1
        except Exception as error:
            store.record_daily_gate(args.run_date, keyword, market, "semrush", "保留", f"Semrush待重试: {type(error).__name__}")
        if done >= args.limit:
            break
    if provider.browser:
        provider.browser.close()
    print(f"semrush_browser_batch={done}")


if __name__ == "__main__":
    main()
