from keyword_loop.core.clients.similarweb import discover_cdp_url, extract_rows_from_text, is_grid_ready


def test_discover_cdp_url_returns_none_when_ports_are_closed() -> None:
    assert discover_cdp_url((1,)) is None


def test_extract_rows_from_text_reads_keyword_volume_kd_and_intent() -> None:
    text = """agent crm
31.4K
57
COMMERCIAL
agent jobs
30K
61
INFORMATIONAL"""
    assert extract_rows_from_text(text) == [
        ["agent crm", "31.4K", "57", "COMMERCIAL"],
        ["agent jobs", "30K", "61", "INFORMATIONAL"],
    ]


def test_is_grid_ready_uses_url_and_visible_keyword_column_not_search_input() -> None:
    assert is_grid_ready(
        "https://sim.3ue.co/#/generator?keyword=audio&tab=phraseMatch",
        8,
        "fish audio\nyoutube audio download",
        "audio",
    ) is True
