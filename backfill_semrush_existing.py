"""Fill missing Semrush display fields for the keywords currently in Feishu."""
from __future__ import annotations

import time

from keyword_loop.core.publishing.feishu import load_env
from keyword_loop.core.clients.semrush_browser import SemrushBrowserProvider
from keyword_loop.core.data.store import KeywordStore
from backfill_existing_feishu import sheet_keywords

REQUIRED = ("volume", "kd", "cpc", "intent", "competitive_density", "serp_features")


def query_with_retry(provider, keyword: str, attempts: int = 2) -> dict:
    """Retry transient CDP navigation aborts without restarting the batch."""
    last_error = None
    for attempt in range(attempts):
        try:
            return provider.query(keyword)
        except Exception as error:
            last_error = error
            if attempt + 1 < attempts:
                time.sleep(2)
    raise last_error  # type: ignore[misc]


def main() -> None:
    store = KeywordStore("output/keyword-loop.sqlite3")
    pending = []
    for keyword, market in sheet_keywords():
        payload = store.validation(keyword, market, "semrush") or {}
        if any(payload.get(field) in (None, "") for field in REQUIRED):
            pending.append((keyword, market))
    provider = SemrushBrowserProvider(cdp_url="http://127.0.0.1:9222")
    completed = 0
    for keyword, market in pending:
        try:
            response = query_with_retry(provider, keyword)
        except Exception as error:
            store.record_failure("semrush:" + keyword, type(error).__name__)
            print(f"failed={keyword} reason={type(error).__name__}", flush=True)
            continue
        exact = next((row for row in response["keywords"] if str(row.get("keyword", "")).lower() == keyword), None)
        if exact is None:
            print(f"not_found={keyword}")
            continue
        previous = store.validation(keyword, market, "semrush") or {}
        merged = {**previous, **exact, "exact_keyword_found": True}
        merged.setdefault("gate_decision", "保留")
        merged.setdefault("gate_reason", "Semrush 精确关键词补采完成")
        store.record_validation(keyword, market, "semrush", merged)
        completed += 1
        print(f"completed={completed}/{len(pending)} keyword={keyword}", flush=True)
    print(f"semrush_backfilled={completed} pending_before={len(pending)}")


if __name__ == "__main__":
    main()
