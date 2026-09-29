"""Local stdio MCP exposing AITDK extension enrichment through Chrome CDP."""

from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path
from urllib.parse import urlparse

# This module is also launched as a script by the stdio client.  In that mode
# Python only adds this directory to sys.path, not the repository root.
PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from product_hunt.aitdk.cdp.cdp import collect_via_cdp, whois_created_date_via_cdp


DEFAULT_CDP_URL = os.environ.get("AITDK_CDP_URL", "http://127.0.0.1:9230")

TOOLS = [
    {
        "name": "domain_enrich",
        "description": "Use the installed, logged-in AITDK Chrome extension to collect sanitized traffic and keyword data for one domain.",
        "inputSchema": {
            "type": "object",
            "required": ["domain"],
            "properties": {
                "domain": {"type": "string", "description": "Domain or http(s) URL to enrich."},
                "cdp_url": {"type": "string", "description": "Chrome remote-debugging endpoint."},
            },
        },
    },
    {
        "name": "health",
        "description": "Show the configured local Chrome CDP endpoint without querying AITDK.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "whois_created_date",
        "description": "Read the Created Date from the installed AITDK extension's Whois module.",
        "inputSchema": {"type": "object", "required": ["domain"], "properties": {"domain": {"type": "string"}, "cdp_url": {"type": "string"}}},
    },
]


def normalize_domain(value: str) -> str:
    """Allow a normal website URL while rejecting unsupported schemes and paths as inputs."""
    raw = str(value).strip()
    if ":" in raw and not raw.lower().startswith(("http://", "https://")):
        raise ValueError("domain must be a domain or http(s) URL")
    parsed = urlparse(raw if "://" in raw else "//" + raw)
    if parsed.scheme and parsed.scheme not in {"http", "https"}:
        raise ValueError("domain must be a domain or http(s) URL")
    if not parsed.hostname:
        raise ValueError("domain must contain a hostname")
    return parsed.hostname.lower().rstrip(".")


def domain_enrich(domain: str, cdp_url: str = DEFAULT_CDP_URL) -> dict:
    record = asyncio.run(collect_via_cdp(normalize_domain(domain), cdp_url))
    return record.to_dict()


def handle(message: dict) -> dict:
    method, params, ident = message.get("method"), message.get("params") or {}, message.get("id")
    if method == "initialize":
        result = {
            "protocolVersion": "2024-11-05",
            "capabilities": {"tools": {}},
            "serverInfo": {"name": "aitdk-cdp-local", "version": "0.1.0"},
        }
    elif method == "tools/list":
        result = {"tools": TOOLS}
    elif method == "notifications/initialized":
        return {}
    elif method == "tools/call":
        name, args = params.get("name"), params.get("arguments") or {}
        if name == "health":
            payload = {"cdp_url": DEFAULT_CDP_URL, "mode": "Chrome CDP + installed AITDK extension"}
        elif name == "domain_enrich":
            payload = domain_enrich(args["domain"], args.get("cdp_url", DEFAULT_CDP_URL))
        elif name == "whois_created_date":
            payload = {"created_date": asyncio.run(whois_created_date_via_cdp(normalize_domain(args["domain"]), args.get("cdp_url", DEFAULT_CDP_URL)))}
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
