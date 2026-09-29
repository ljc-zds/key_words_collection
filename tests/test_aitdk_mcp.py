import json

from aitdk_mcp import handle, normalize_domain


def test_tools_list_exposes_domain_enrichment_and_health() -> None:
    response = handle({"jsonrpc": "2.0", "id": 1, "method": "tools/list"})

    assert [tool["name"] for tool in response["result"]["tools"]] == ["domain_enrich", "health"]


def test_health_reports_the_configured_cdp_endpoint() -> None:
    response = handle({"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {"name": "health", "arguments": {}}})

    payload = json.loads(response["result"]["content"][0]["text"])
    assert payload["cdp_url"] == "http://127.0.0.1:9222"


def test_normalize_domain_removes_url_path_without_accepting_non_http_schemes() -> None:
    assert normalize_domain("https://deno.com/blog/post") == "deno.com"
    assert normalize_domain("deno.com") == "deno.com"
    try:
        normalize_domain("javascript:alert(1)")
    except ValueError as error:
        assert "domain" in str(error)
    else:
        raise AssertionError("non-http scheme must be rejected")
