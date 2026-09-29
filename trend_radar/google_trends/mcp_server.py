"""Local stdio MCP for Google Trends same-origin browser API requests."""

from __future__ import annotations

import json
import os
import sys
from functools import lru_cache

from .fallback import FallbackGoogleTrendsClient
from .comparison import is_new_word


# Dedicated Trends profile; never fall back to another workflow's IPv6 listener.
DEFAULT_CDP_URL = os.environ.get("GOOGLE_TRENDS_CDP_URL", "http://127.0.0.1:9229")
DEFAULT_TIMEFRAME = "today 1-m"

TOOLS = [
    {
        "name": "trend_analyze",
        "description": "Read Google Trends widget data through logged-in Chrome and compare a keyword with a baseline term.",
        "inputSchema": {
            "type": "object",
            "required": ["keyword"],
            "properties": {
                "keyword": {"type": "string"},
                "timeframe": {"type": "string", "default": DEFAULT_TIMEFRAME},
                "baseline": {"type": "string", "default": "gpts"},
                "cdp_url": {"type": "string"},
            },
        },
    },
    {
        "name": "rising_queries",
        "description": "Return Google Trends Rising or Breakout related queries for one keyword.",
        "inputSchema": {
            "type": "object",
            "required": ["keyword"],
            "properties": {
                "keyword": {"type": "string"},
                "timeframe": {"type": "string", "default": DEFAULT_TIMEFRAME},
                "minimum_growth": {"type": "integer", "default": 500},
                "include_all": {"type": "boolean", "default": False},
                "cdp_url": {"type": "string"},
            },
        },
    },
    {
        "name": "health",
        "description": "Show the configured Chrome CDP endpoint without querying Google Trends.",
        "inputSchema": {"type": "object", "properties": {}},
    },
]


@lru_cache(maxsize=8)
def _client(cdp_url: str):
    # Preserve spacing and rate-limit cooldown across calls in this MCP process.
    return FallbackGoogleTrendsClient(cdp_url)


def _keyword(value: object) -> str:
    keyword = " ".join(str(value).split())
    if not keyword:
        raise ValueError("keyword is required")
    return keyword


def trend_analyze(keyword: str, *, timeframe: str = DEFAULT_TIMEFRAME, baseline: str = "gpts", cdp_url: str = DEFAULT_CDP_URL) -> dict:
    keyword, baseline = _keyword(keyword), _keyword(baseline)
    times, values, baseline_values = _client(cdp_url).compare(keyword, baseline, timeframe)
    baseline_points = max(1, int(len(times) * 0.7))
    comparison = is_new_word(values, baseline_values, baseline_points=baseline_points)
    return {
        "keyword": keyword,
        "baseline": baseline,
        "timeframe": timeframe,
        "baseline_points": baseline_points,
        "timeline": [
            {"time": time, "interest": value, "baseline_interest": base}
            for time, value, base in zip(times, values, baseline_values)
        ],
        "comparison": comparison,
    }


def rising_queries(keyword: str, *, timeframe: str = DEFAULT_TIMEFRAME, minimum_growth: int = 500, include_all: bool = False, cdp_url: str = DEFAULT_CDP_URL) -> dict:
    keyword = _keyword(keyword)
    if minimum_growth < 0:
        raise ValueError("minimum_growth must be zero or greater")
    client = _client(cdp_url)
    queries = client.related_rising_all(keyword, timeframe)
    retained = [
        item for item in queries
        if item.get("type") == "Breakout" or (isinstance(item.get("growth_percent"), (int, float)) and item["growth_percent"] >= minimum_growth)
    ]
    return {"keyword": keyword, "timeframe": timeframe, "minimum_growth": minimum_growth,
            "backend": getattr(client, 'last_backend', None),
            "raw_result_limit": (50 if client.last_backend == 'new_url' else 25) if include_all else None,
            "queries": queries if include_all else retained}


def handle(message: dict) -> dict:
    method, params, ident = message.get("method"), message.get("params") or {}, message.get("id")
    if method == "initialize":
        result = {"protocolVersion": "2024-11-05", "capabilities": {"tools": {}}, "serverInfo": {"name": "google-trends-cdp-local", "version": "0.1.0"}}
    elif method == "tools/list":
        result = {"tools": TOOLS}
    elif method == "notifications/initialized":
        return {}
    elif method == "tools/call":
        name, args = params.get("name"), params.get("arguments") or {}
        if name == "health":
            payload = {"cdp_url": DEFAULT_CDP_URL, "mode": "New page URL -> classic API -> stop on dual failure"}
        elif name == "trend_analyze":
            payload = trend_analyze(args["keyword"], timeframe=args.get("timeframe", DEFAULT_TIMEFRAME), baseline=args.get("baseline", "gpts"), cdp_url=args.get("cdp_url", DEFAULT_CDP_URL))
        elif name == "rising_queries":
            payload = rising_queries(args["keyword"], timeframe=args.get("timeframe", DEFAULT_TIMEFRAME), minimum_growth=args.get("minimum_growth", 500), include_all=args.get("include_all", False), cdp_url=args.get("cdp_url", DEFAULT_CDP_URL))
        else:
            raise RuntimeError(f"Unknown tool: {name}")
        result = {"content": [{"type": "text", "text": json.dumps(payload, ensure_ascii=False)}]}
    else:
        result = {}
    return {"jsonrpc": "2.0", "id": ident, "result": result}


def main() -> None:
    for line in sys.stdin:
        ident = None
        try:
            message = json.loads(line)
            ident = message.get("id")
            print(json.dumps(handle(message), ensure_ascii=False), flush=True)
        except Exception as error:
            print(json.dumps({"jsonrpc": "2.0", "id": ident, "error": {"code": -32000, "message": str(error)}}, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
