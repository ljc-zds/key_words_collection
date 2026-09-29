"""Local stdio MCP for Semrush Keyword Magic Tool's JSON-RPC endpoint."""
import json, os, sys
from json import JSONDecodeError
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

from product_hunt.aitdk.product.product_hunt import trusted_ssl_context

BASE_URL = os.environ.get("SEMRUSH_BASE_URL", "https://sem.3ue.co").rstrip("/")


def build_rpc_request(phrase: str, *, database: str = "us", page_size: int = 100, page_number: int = 1) -> dict:
    return {"id": 1, "jsonrpc": "2.0", "method": "ideas.GetKeywords", "params": {"mode": 4, "currency": "USD", "database": database, "filter": {"phrase": [], "competition_level": [], "cpc": [], "difficulty": [], "results": [], "serp_features": [{"inverted": False, "value": []}], "volume": [], "words_count": [], "phrase_include_logic": 0}, "groups": [], "order": {"direction": 1, "field": "similarity_score"}, "groups_order": {"direction": 1, "field": "relevance"}, "phrase": phrase, "questions_only": False, "topics_enabled": True, "page": {"number": page_number, "size": page_size}}}


def filter_keywords(rows: list[dict], minimum_volume: int, maximum_kd: int) -> list[dict]:
    return [r for r in rows if (r.get("volume") or 0) >= minimum_volume and r.get("difficulty") is not None and r["difficulty"] <= maximum_kd]


def _headers():
    h = {"Accept": "application/json", "Content-Type": "application/json", "User-Agent": "semrush-local-mcp/1.0"}
    raw = os.environ.get("SEMRUSH_HEADERS_JSON")
    if raw: h.update(json.loads(raw) if raw.lstrip().startswith("{") else json.loads(open(raw, encoding="utf-8").read()))
    if os.environ.get("SEMRUSH_COOKIE"): h["Cookie"] = os.environ["SEMRUSH_COOKIE"]
    if os.environ.get("SEMRUSH_AUTHORIZATION"): h["Authorization"] = os.environ["SEMRUSH_AUTHORIZATION"]
    return h


def keyword_magic(phrase: str, *, database: str, minimum_volume: int, maximum_kd: int, page_size: int) -> dict:
    req = Request(f"{BASE_URL}/kmtgw/v2/webapi", data=json.dumps(build_rpc_request(phrase, database=database, page_size=page_size)).encode(), headers=_headers(), method="POST")
    try:
        with urlopen(req, timeout=45, context=trusted_ssl_context()) as response:
            try:
                payload = json.load(response)
            except JSONDecodeError as error:
                raise RuntimeError("AUTH_REQUIRED: Semrush returned a non-JSON login page; refresh the logged-in session and update MCP headers") from error
    except HTTPError as e:
        if e.code in (401, 403): raise RuntimeError("AUTH_REQUIRED: configure a valid Semrush API/session credential") from e
        raise RuntimeError(f"Semrush HTTP {e.code}") from e
    except (URLError, TimeoutError) as e: raise RuntimeError(f"Semrush network error: {type(e).__name__}") from e
    result = payload.get("result") or {}
    rows = result.get("keywords") or []
    return {"phrase": phrase, "database": database, "total": result.get("total", len(rows)), "keywords": filter_keywords(rows, minimum_volume, maximum_kd)}


TOOLS = [{"name": "keyword_suggest", "description": "Query Semrush Keyword Magic Tool and filter by volume and KD.", "inputSchema": {"type": "object", "required": ["keyword"], "properties": {"keyword": {"type": "string"}, "database": {"type": "string", "default": "us"}, "minimum_volume": {"type": "integer", "default": 30000}, "maximum_kd": {"type": "integer", "default": 60}, "page_size": {"type": "integer", "default": 100}}}}, {"name": "health", "description": "Check local Semrush MCP configuration.", "inputSchema": {"type": "object", "properties": {}}}]


def handle(m):
    method, p, ident = m.get("method"), m.get("params") or {}, m.get("id")
    if method == "initialize": result = {"protocolVersion": "2024-11-05", "capabilities": {"tools": {}}, "serverInfo": {"name": "semrush-local", "version": "0.1.0"}}
    elif method == "tools/list": result = {"tools": TOOLS}
    elif method == "notifications/initialized": return {}
    elif method == "tools/call":
        name, a = p.get("name"), p.get("arguments") or {}
        if name == "health": result = {"content": [{"type": "text", "text": json.dumps({"base_url": BASE_URL, "credential_configured": bool(os.environ.get("SEMRUSH_HEADERS_JSON") or os.environ.get("SEMRUSH_COOKIE") or os.environ.get("SEMRUSH_AUTHORIZATION"))})}]}
        elif name == "keyword_suggest": result = {"content": [{"type": "text", "text": json.dumps(keyword_magic(a["keyword"], database=a.get("database", "us"), minimum_volume=a.get("minimum_volume", 30000), maximum_kd=a.get("maximum_kd", 60), page_size=a.get("page_size", 100)), ensure_ascii=False)}]}
        else: raise RuntimeError(f"Unknown tool: {name}")
    else: result = {}
    return {"jsonrpc": "2.0", "id": ident, "result": result}


def main():
    for line in sys.stdin:
        try: print(json.dumps(handle(json.loads(line))), flush=True)
        except Exception as e: print(json.dumps({"jsonrpc": "2.0", "id": None, "error": {"code": -32000, "message": str(e)}}), flush=True)


if __name__ == "__main__": main()
