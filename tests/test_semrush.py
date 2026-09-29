from keyword_loop.core.screening.screening import semrush_missing_gate
from keyword_loop.core.clients.semrush import parse_manager_cells


def test_parse_manager_cells_maps_all_publishable_semrush_fields() -> None:
    payload = parse_manager_cells([
        "", "png converter添加标签", "C", "-", "33.1千", "", "75", "60", "0.99", "0.09", "4",
    ])

    assert payload == {
        "keyword": "png converter",
        "intent": "Commercial",
        "volume": 33_100,
        "kd": 60,
        "cpc": 0.99,
        "competitive_density": 0.09,
        "serp_features": 4,
    }


def test_missing_semrush_exact_keyword_keeps_similarweb_approved_candidate() -> None:
    result = semrush_missing_gate()

    assert result.decision == "保留"
    assert "未返回精确关键词" in result.reason
