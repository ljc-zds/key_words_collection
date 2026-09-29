from product_hunt.aitdk.domain.traffic_panel import parse_panel_text


def test_parse_panel_text_extracts_traffic_and_keywords() -> None:
    text = """Traffic Overview
July 2026
318.3K
Monthly Visits
1999-3-9
Domain Creation
27.48 years
Domain Age
Traffic Sources
Search: 31.42%
Direct: 30.17%
Top Keywords
Keyword
Traffic
Volume
CPC
deno
26K
28K
$2.89
deno desktop
5K
8K
$0
Top Regions"""
    result = parse_panel_text(text)
    assert result["monthly_visits"] == 318_300
    assert result["search_share"] == 0.3142
    assert result["direct_share"] == 0.3017
    assert result["registered"] == "1999-3-9"
    assert [item["name"] for item in result["keywords"]] == ["deno", "deno desktop"]


def test_parse_panel_text_marks_empty_panel_as_missing() -> None:
    result = parse_panel_text("Traffic Overview\nMonthly Visits\nTraffic Sources\nTop Keywords")
    assert result["status"] == "missing"
