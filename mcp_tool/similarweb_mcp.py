"""Local stdio MCP for Similarweb's authenticated keyword suggest endpoint."""
import json
import os
import sys
from datetime import date, timedelta
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
from json import JSONDecodeError

from product_hunt.aitdk.product.product_hunt import trusted_ssl_context


BASE_URL = os.environ.get("SIMILARWEB_BASE_URL", "https://sim.3ue.co").rstrip("/")


def build_suggest_url(keyword: str, *, result_type: str = "Broad", rows_per_page: int = 100, country: int = 999) -> str:
    end = date.today() - timedelta(days=4)
    start = end - timedelta(days=27)
    query = {"keyword": keyword, "country": country, "from": start.strftime("%Y|%m|%d"), "to": end.strftime("%Y|%m|%d"), "isWindow": "true", "websource": "Total", "sort": "windowVolume", "asc": "false", "rowsPerPage": rows_per_page, "type": result_type, "latest": "28d"}
    return f"{BASE_URL}/api/KeywordGenerator/google/suggest?{urlencode(query)}"


def filter_records(records: list[dict], minimum_volume: int, maximum_kd: int) -> list[dict]:
    return [r for r in records if (r.get("averageVolume") or 0) >= minimum_volume and (r.get("difficulty") is not None and r["difficulty"] <= maximum_kd)]


def _headers() -> dict[str, str]:
    headers = {"Accept": "application/json", "Content-Type": "application/json", "X-Requested-With": "XMLHttpRequest", "User-Agent": "keyword-loop-local-mcp/1.0"}
    raw = os.environ.get("SIMILARWEB_HEADERS_JSON")
    if raw:
        headers.update(json.loads(raw) if raw.lstrip().startswith("{") else json.loads(open(raw, encoding="utf-8").read()))
    if os.environ.get("SIMILARWEB_COOKIE"):
        headers["Cookie"] = os.environ["SIMILARWEB_COOKIE"]
    if os.environ.get("SIMILARWEB_AUTHORIZATION"):
        headers["Authorization"] = os.environ["SIMILARWEB_AUTHORIZATION"]
    return headers


def suggest(keyword: str, *, result_type: str, minimum_volume: int, maximum_kd: int, rows_per_page: int, country: int) -> dict:
    request = Request(build_suggest_url(keyword, result_type=result_type, rows_per_page=rows_per_page, country=country), headers=_headers(), method="POST")
    try:
        with urlopen(request, timeout=45, context=trusted_ssl_context()) as response:
            try:
                payload = json.load(response)
            except JSONDecodeError as error:
                raise RuntimeError("AUTH_REQUIRED: Similarweb returned a non-JSON login page; refresh the logged-in session and update MCP headers") from error
    except HTTPError as error:
        if error.code in (401, 403):
            raise RuntimeError("AUTH_REQUIRED: configure a valid Similarweb API/session credential") from error
        raise RuntimeError(f"Similarweb HTTP {error.code}") from error
    except (URLError, TimeoutError) as error:
        raise RuntimeError(f"Similarweb network error: {type(error).__name__}") from error
    records = payload.get("records", [])
    return {"keyword": keyword, "result_type": result_type, "total_records": payload.get("totalRecords", 0), "total_volume": payload.get("totalVolume", 0), "total_clicks": payload.get("totalClicks", 0), "records": filter_records(records, minimum_volume, maximum_kd)}


TOOLS = [{"name": "keyword_suggest", "description": "Query Similarweb keyword suggestions and filter by average volume and KD.", "inputSchema": {"type": "object", "required": ["keyword"], "properties": {"keyword": {"type": "string"}, "result_type": {"type": "string", "enum": ["Broad", "Related"]}, "minimum_volume": {"type": "integer", "default": 30000}, "maximum_kd": {"type": "integer", "default": 60}, "rows_per_page": {"type": "integer", "default": 100}, "country": {"type": "integer", "default": 999}}} }, {"name": "health", "description": "Check MCP configuration without making a Similarweb request.", "inputSchema": {"type": "object", "properties": {}}}]


def handle(message: dict) -> dict:
    method, params, ident = message.get("method"), message.get("params") or {}, message.get("id")
    if method == "initialize":
        result = {"protocolVersion": "2024-11-05", "capabilities": {"tools": {}}, "serverInfo": {"name": "similarweb-local", "version": "0.1.0"}}
    elif method == "tools/list": result = {"tools": TOOLS}
    elif method == "tools/call":
        name, args = params.get("name"), params.get("arguments") or {}
        if name == "health": result = {"content": [{"type": "text", "text": json.dumps({"base_url": BASE_URL, "credential_configured": bool(os.environ.get("SIMILARWEB_HEADERS_JSON") or os.environ.get("SIMILARWEB_COOKIE") or os.environ.get("SIMILARWEB_AUTHORIZATION"))})}]}
        elif name == "keyword_suggest":
            result = {"content": [{"type": "text", "text": json.dumps(suggest(args["keyword"], result_type=args.get("result_type", "Broad"), minimum_volume=args.get("minimum_volume", 30000), maximum_kd=args.get("maximum_kd", 60), rows_per_page=args.get("rows_per_page", 100), country=args.get("country", 999)), ensure_ascii=False)}]}
        else: raise RuntimeError(f"Unknown tool: {name}")
    elif method == "notifications/initialized": return {}
    else: result = {}
    return {"jsonrpc": "2.0", "id": ident, "result": result}


def main() -> None:
    for line in sys.stdin:
        try: print(json.dumps(handle(json.loads(line))), flush=True)
        except Exception as error: print(json.dumps({"jsonrpc": "2.0", "id": None, "error": {"code": -32000, "message": str(error)}}), flush=True)


if __name__ == "__main__": main()
