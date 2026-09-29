import json

from similarweb_mcp import filter_records, build_suggest_url
from keyword_loop.core.clients import similarweb


def test_build_suggest_url_uses_similarweb_query_contract() -> None:
    url = build_suggest_url("agent", result_type="Broad", rows_per_page=100)
    assert "/api/KeywordGenerator/google/suggest?" in url
    assert "keyword=agent" in url
    assert "type=Broad" in url
    assert "rowsPerPage=100" in url


def test_filter_records_applies_average_volume_and_kd() -> None:
    records = [
        {"keyword": "good", "averageVolume": 30_000, "difficulty": 60},
        {"keyword": "low", "averageVolume": 29_999, "difficulty": 10},
        {"keyword": "hard", "averageVolume": 50_000, "difficulty": 61},
    ]
    assert filter_records(records, 30_000, 60) == [records[0]]


def test_primary_keyword_response_excludes_auxiliary_similarweb_labels() -> None:
    primary = "https://sim.3ue.co/api/KeywordGenerator/google/suggest?keyword=dreamg&type=Broad&rowsPerPage=100"
    questions = primary + "&label=Questions"
    trending = primary + "&label=Trending"

    assert similarweb.is_primary_keyword_response(primary) is True
    assert similarweb.is_primary_keyword_response(questions) is False
    assert similarweb.is_primary_keyword_response(trending) is False
