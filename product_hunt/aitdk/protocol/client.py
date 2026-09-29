"""Client and data adapter for the local AITDK Chrome CDP MCP server."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any
from urllib.error import HTTPError
from urllib.parse import urljoin
from urllib.request import HTTPRedirectHandler, HTTPSHandler, Request, build_opener, urlopen

from ..product.product_hunt import trusted_ssl_context


class AitdkMcpError(RuntimeError):
    pass


PROJECT_ROOT = Path(__file__).resolve().parents[4]
MCP_SERVER = Path(__file__).with_name("mcp_server.py")
DEFAULT_CDP_URL = os.environ.get("AITDK_CDP_URL", "http://127.0.0.1:9230")


def _number(value: object) -> int | float | None:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return value
    if isinstance(value, str):
        try:
            return int(value.replace(",", ""))
        except ValueError:
            try:
                return float(value.replace(",", ""))
            except ValueError:
                return None
    return None


def _registered_date(whois: object) -> str | None:
    if not isinstance(whois, dict):
        return None
    for key in ("creationDate", "creation_date", "created", "registered", "registrationDate"):
        value = whois.get(key)
        if isinstance(value, str) and len(value) >= 10:
            return value[:10]
    return None


def traffic_panel(record: dict[str, Any]) -> dict[str, Any]:
    """Normalize sanitized ``domain_enrich`` output for the demand filter."""
    overview = record.get("overview") if isinstance(record.get("overview"), dict) else {}
    sources = record.get("traffic_sources") if isinstance(record.get("traffic_sources"), dict) else {}
    visits = _number(overview.get("visits"))
    keywords: list[dict[str, Any]] = []
    for item in record.get("top_keywords", []):
        if not isinstance(item, dict):
            continue
        keyword = dict(item)
        if "volume" in keyword:
            volume = _number(keyword["volume"])
            if volume is not None:
                keyword["volume"] = volume
        keywords.append(keyword)
    return {
        "status": "ok" if visits is not None else "missing",
        "monthly_visits": visits,
        "monthly_visits_trend": [],
        "search_share": sources.get("searchOrganic", sources.get("search_organic", sources.get("search"))),
        "direct_share": sources.get("direct"),
        "registered": _registered_date(record.get("whois")),
        "keywords": keywords,
    }


def ensure_cdp_available(cdp_url: str = DEFAULT_CDP_URL) -> None:
    """Fail before a batch when the browser automation endpoint is unavailable."""
    try:
        with urlopen(f"{cdp_url.rstrip('/')}/json/version", timeout=5) as response:
            payload = json.loads(response.read())
        if not isinstance(payload, dict) or not payload.get("Browser"):
            raise ValueError("invalid Chrome DevTools response")
    except Exception as error:
        raise AitdkMcpError(f"无法连接 Chrome CDP: {cdp_url}") from error


def _call_tool(name: str, arguments: dict[str, Any], *, timeout: int) -> dict[str, Any]:
    """Call one local stdio MCP tool without exposing Chrome credentials."""
    command = [str(PROJECT_ROOT / ".venv" / "bin" / "python"), str(MCP_SERVER)]
    if not Path(command[0]).is_file():
        command[0] = sys.executable
    requests = [
        {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
        {"jsonrpc": "2.0", "method": "notifications/initialized"},
        {"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {
            "name": name, "arguments": arguments,
        }},
    ]
    try:
        completed = subprocess.run(
            command,
            input="".join(json.dumps(item, ensure_ascii=False) + "\n" for item in requests),
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired as error:
        raise AitdkMcpError("AITDK MCP query timed out") from error
    responses = [json.loads(line) for line in completed.stdout.splitlines() if line.strip()]
    response = next((item for item in responses if item.get("id") == 2), None)
    if response is None:
        raise AitdkMcpError(f"AITDK MCP returned no {name} response")
    if "error" in response:
        raise AitdkMcpError(str(response["error"].get("message", "AITDK MCP failed")))
    try:
        return json.loads(response["result"]["content"][0]["text"])
    except (KeyError, IndexError, TypeError, json.JSONDecodeError) as error:
        raise AitdkMcpError(f"AITDK MCP returned an invalid {name} payload") from error


def domain_enrich(domain: str, *, cdp_url: str = DEFAULT_CDP_URL, timeout: int = 60) -> dict[str, Any]:
    """Collect traffic data from the local AITDK extension."""
    return _call_tool("domain_enrich", {"domain": domain, "cdp_url": cdp_url}, timeout=timeout)


def whois_created_date(domain: str, *, cdp_url: str = DEFAULT_CDP_URL, timeout: int = 60) -> str | None:
    """Read the date from AITDK Whois only after free RDAP is unavailable."""
    payload = _call_tool("whois_created_date", {"domain": domain, "cdp_url": cdp_url}, timeout=timeout)
    created = payload.get("created_date")
    return created if isinstance(created, str) else None


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def resolve_url(url: str) -> str:
    """Resolve a Product Hunt redirect without calling a traffic data provider."""
    opener = build_opener(HTTPSHandler(context=trusted_ssl_context()), _NoRedirect())
    try:
        response = opener.open(Request(url, headers={"User-Agent": "ProductHunt-Demand-Radar/1.0"}), timeout=30)
    except HTTPError as error:
        if not 300 <= error.code < 400:
            raise
        response = error
    location = response.headers.get("Location")
    return urljoin(url, location) if location else response.geturl()
