from keyword_loop.core.data.parsing import parse_keyword_row, parse_metric


def test_parse_metric_supports_similarweb_suffixes() -> None:
    assert parse_metric("30K") == 30_000
    assert parse_metric("1.25M") == 1_250_000
    assert parse_metric("-") is None


def test_parse_keyword_row_normalizes_a_complete_table_row() -> None:
    result = parse_keyword_row(
        ["Agent CRM", "31.4K", "57", "COMMERCIAL"],
        root="agent",
        result_type="phrase_match",
        market="global",
        retrieved_at="2026-08-24T08:00:00+00:00",
    )
    assert result is not None
    assert result.keyword == "agent crm"
    assert result.average_volume == 31_400
    assert result.kd == 57
    assert result.intent == "COMMERCIAL"
