import json

from trend_radar.google_trends.mcp_server import handle, rising_queries, trend_analyze


def test_tools_list_exposes_new_trends_analysis_tools() -> None:
    response = handle({"jsonrpc": "2.0", "id": 1, "method": "tools/list"})

    assert [tool["name"] for tool in response["result"]["tools"]] == ["trend_analyze", "rising_queries", "health"]


def test_trend_analyze_returns_aligned_timeline_and_comparison(monkeypatch) -> None:
    class Client:
        def __init__(self, cdp_url: str) -> None:
            assert cdp_url == "http://cdp.test"

        def compare(self, keyword: str, baseline: str, timeframe: str):
            assert (keyword, baseline, timeframe) == ("action", "gpts", "today 1-m")
            return ["t1", "t2"], [1, 9], [4, 5]

    monkeypatch.setattr("trend_radar.google_trends.mcp_server._client", Client)

    result = trend_analyze("action", cdp_url="http://cdp.test")

    assert result["timeline"] == [
        {"time": "t1", "interest": 1, "baseline_interest": 4},
        {"time": "t2", "interest": 9, "baseline_interest": 5},
    ]
    assert result["comparison"]["is_new_word"] is True


def test_rising_queries_filters_below_the_requested_growth(monkeypatch) -> None:
    class Client:
        def __init__(self, cdp_url: str) -> None:
            pass

        def related_rising_all(self, keyword: str, timeframe: str):
            return [
                {"query": "breakout", "type": "Breakout", "growth_percent": None},
                {"query": "fast", "type": "rising", "growth_percent": 700},
                {"query": "slow", "type": "rising", "growth_percent": 300},
            ]

    monkeypatch.setattr("trend_radar.google_trends.mcp_server._client", Client)

    assert rising_queries("action", minimum_growth=500, cdp_url="http://cdp.test")["queries"] == [
        {"query": "breakout", "type": "Breakout", "growth_percent": None},
        {"query": "fast", "type": "rising", "growth_percent": 700},
    ]


def test_health_returns_configured_cdp_url() -> None:
    response = handle({"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "health", "arguments": {}}})

    assert json.loads(response["result"]["content"][0]["text"])["cdp_url"] == "http://127.0.0.1:9229"
