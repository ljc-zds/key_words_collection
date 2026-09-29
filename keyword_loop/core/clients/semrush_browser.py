"""Semrush Keyword Magic browser-proxy provider (JSON network responses only)."""
from __future__ import annotations

from urllib.parse import urlencode, urlparse
import time
from pathlib import Path
import subprocess

from .browser_proxy import OpenCliBrowser, BrowserProxyError
from .cdp_proxy import CdpBrowser
from .discovery_filters import semrush_filter


class SemrushReportLimitError(BrowserProxyError):
    """The current account cannot run more reports; do not retry keywords."""


def _as_dict(value):
    """OpenCLI may expose response bodies as dicts or JSON strings."""
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        import json
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return {}
        return parsed if isinstance(parsed, dict) else {}
    return {}


_INTENT_CODES = {
    0: "Informational",
    1: "Navigational",
    2: "Commercial",
    3: "Transactional",
}


def normalize_keyword_row(row: dict) -> dict:
    """Map raw Keyword Magic response fields to the publication schema."""
    result = dict(row)
    result.setdefault("kd", result.get("difficulty"))
    result.setdefault("competitive_density", result.get("competition_level"))
    intents = result.get("intents")
    if not result.get("intent") and isinstance(intents, list):
        labels = [_INTENT_CODES[value] for value in intents if value in _INTENT_CODES]
        if labels:
            result["intent"] = "/".join(labels)
    if isinstance(result.get("serp_features"), list):
        result["serp_features"] = len(result["serp_features"])
    return result


class SemrushBrowserProvider:
    _last_query = 0.0
    _min_interval = 1.0
    def __init__(self, *, database: str = "us", executable: str = "opencli", cdp_url: str | None = None, discovery_filters: bool = False, per_root_cap: int = 100) -> None:
        self.per_root_cap = per_root_cap
        self.discovery_filters = discovery_filters
        self.database = database
        self.cdp_url = cdp_url
        self.browser = None if cdp_url else OpenCliBrowser(prefix="semrush-keyword", executable=executable)

    def query(self, keyword: str, *, page_size: int | None = None) -> dict:
        page_size = self.per_root_cap if page_size is None else page_size
        if page_size < 0:
            raise ValueError("page_size must be nonnegative")
        # Use a short baseline interval. The runner applies a long backoff
        # only when the page/API explicitly reports rate limiting.
        delay = self._min_interval - (time.monotonic() - type(self)._last_query)
        if delay > 0:
            time.sleep(delay)
        type(self)._last_query = time.monotonic()
        url = "https://sem.3ue.co/analytics/keywordmagic/?" + urlencode({"q": keyword, "db": self.database, "type": "all", "mode": "0", "_proxy": str(time.time_ns())})
        query_filter = semrush_filter() if self.discovery_filters else ""
        if query_filter:
            url += "&" + urlencode({"filter": query_filter})
        if self.cdp_url:
            script = Path(__file__).with_name("semrush_native_cdp.mjs")
            endpoint = self.cdp_url.rstrip("/")
            result = None
            last_error = ""
            for attempt in range(2):
                try:
                    result = subprocess.run(
                        ["node", str(script), endpoint, keyword, self.database, query_filter, str(page_size)],
                        check=False,
                        capture_output=True,
                        text=True,
                        timeout=60 + 30 * ((page_size - 1) // 100) if page_size else None,
                    )
                    if result.returncode == 0:
                        break
                    last_error = result.stderr.strip()
                    if "SEMRUSH_REPORT_LIMIT" in last_error:
                        raise SemrushReportLimitError("SEMRUSH_REPORT_LIMIT: -2004 Report limit reached")
                except subprocess.TimeoutExpired as error:
                    last_error = f"timeout after 60s (attempt {attempt + 1})"
                if attempt == 0:
                    time.sleep(2)
            if result is None or result.returncode:
                raise BrowserProxyError(last_error or "Semrush native CDP query failed")
            try:
                body = {"result": __import__("json").loads(result.stdout)}
            except Exception as error:
                raise BrowserProxyError("Semrush native CDP returned malformed JSON") from error
            parsed = self._rows(keyword, [{"body": body}], page_size)
            parsed["pages_fetched"] = body["result"].get("pages_fetched", 1)
            return parsed
        self.browser.run("open", url)
        entries = []
        for _ in range(3):
            self.browser.run("wait", "time", "15")
            payload = self.browser.run("network", "--raw", "--since", "10m")
            for entry in payload.get("entries", []):
                if "/kmtgw/v2/webapi" in entry.get("url", "") and entry.get("status") == 200:
                    body = _as_dict(entry.get("body", {}))
                    result = _as_dict(body.get("result", {}))
                    if isinstance(result.get("keywords"), list): entries.append(entry)
            if entries: break
            self.browser.run("open", url)
        parsed = self._rows(keyword, entries, page_size)
        return parsed

    def _rows(self, keyword: str, entries: list[dict], page_size: int) -> dict:
        rows = []
        for entry in entries:
            body = _as_dict(entry.get("body", {}))
            result = _as_dict(body.get("result", body))
            if isinstance(result.get("keywords"), list): rows.extend(result["keywords"])
        if rows:
            for row in rows:
                if not row.get("keyword"): row["keyword"] = row.get("phrase") or row.get("keyword_text") or row.get("term")
                if row.get("difficulty") is None: row["difficulty"] = row.get("kd") or row.get("pkd")
            return {"keyword": keyword, "database": self.database, "total": len(rows), "keywords": [normalize_keyword_row(row) for row in rows[:page_size or None]]}
        if any(isinstance(_as_dict(_as_dict(e.get("body", {})).get("result", {})).get("keywords"), list) for e in entries):
            return {"keyword": keyword, "database": self.database, "total": 0, "keywords": []}
        raise BrowserProxyError("Semrush returned no keyword JSON response")
        # The batch runner keeps this lease alive across keywords and closes it
        # once the queue is exhausted.
