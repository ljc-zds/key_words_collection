import asyncio
import json

from product_hunt.aitdk.cdp.cdp import (
    extract_traffic_record,
    is_aitdk_bulk_url,
    resolve_redirect_via_cdp,
    whois_created_date_from_text,
)
from product_hunt.aitdk.legacy.cli import build_parser


STREAM = (
    "event: traffic\n"
    "data: {\"domain\": \"deno.com\", \"data\": {\"overview\": {\"visits\": \"318295\"}}}\n"
)


def test_extract_traffic_record_accepts_only_aitdk_bulk_streams() -> None:
    record = extract_traffic_record("https://api.aitdk.com/api/v1/bulk?nonce=secret", STREAM)

    assert record is not None
    assert record.domain == "deno.com"
    assert record.overview["visits"] == "318295"


def test_extract_traffic_record_ignores_same_shaped_unrelated_response() -> None:
    assert extract_traffic_record("https://example.com/api/v1/bulk", STREAM) is None


def test_aitdk_bulk_url_allows_query_but_requires_exact_path() -> None:
    assert is_aitdk_bulk_url("https://api.aitdk.com/api/v1/bulk?request_id=1")
    assert not is_aitdk_bulk_url("https://api.aitdk.com/api/v1/bulk/other")


def test_whois_created_date_parser_returns_none_for_an_empty_panel() -> None:
    assert whois_created_date_from_text("Whois / RDAP\nNo data available") is None
    assert whois_created_date_from_text("Created Date\n2026-06-01 10:00:00 UTC") == "2026-06-01"


def test_cli_accepts_cdp_mode_without_isolated_browser_files() -> None:
    args = build_parser().parse_args(["deno.com", "--cdp-url", "http://127.0.0.1:9222"])

    assert args.domain == "deno.com"
    assert args.cdp_url == "http://127.0.0.1:9222"
    assert args.archive is None
    assert args.edge is None


def test_resolve_redirect_via_cdp_returns_the_final_background_page_url(monkeypatch) -> None:
    calls = []

    class Response:
        def __init__(self, payload):
            self.payload = payload

        def read(self):
            return json.dumps(self.payload).encode()

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

    def open_cdp(request, **_kwargs):
        calls.append((request.full_url, request.get_method()))
        if "/json/new?" in request.full_url:
            return Response({"id": "target-1"})
        if request.full_url.endswith("/json/list"):
            return Response([{"id": "target-1", "url": "https://mcpx.digital/?ref=producthunt"}])
        return Response({})

    monkeypatch.setattr("product_hunt.aitdk.cdp.cdp.urlopen", open_cdp, raising=False)

    resolved = asyncio.run(resolve_redirect_via_cdp("https://www.producthunt.com/r/WA3KFL67WKU55X"))

    assert resolved == "https://mcpx.digital/?ref=producthunt"
    assert calls[0][1] == "PUT"
    assert calls[1] == ("http://127.0.0.1:9230/json/list", "GET")
    assert calls[-1] == ("http://127.0.0.1:9230/json/close/target-1", "GET")
