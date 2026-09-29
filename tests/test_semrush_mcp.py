from semrush_mcp import build_rpc_request, filter_keywords


def test_build_rpc_request_uses_keyword_magic_method() -> None:
    request = build_rpc_request("agent", database="us", page_size=100, page_number=2)
    assert request["method"] == "ideas.GetKeywords"
    assert request["params"]["phrase"] == "agent"
    assert request["params"]["database"] == "us"
    assert request["params"]["page"]["size"] == 100
    assert request["params"]["page"]["number"] == 2


def test_filter_keywords_applies_volume_and_kd() -> None:
    rows = [{"phrase": "good", "volume": 30000, "difficulty": 60}, {"phrase": "low", "volume": 29999, "difficulty": 1}]
    assert filter_keywords(rows, 30000, 60) == [rows[0]]
