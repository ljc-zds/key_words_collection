from keyword_loop.core.screening.screening import intent_gate, keyword_quality_gate


def test_intent_gate_rejects_brand_navigation_and_physical_product() -> None:
    assert intent_gate("animeflv", {"intent": "Navigational"}).decision == "淘汰"
    assert intent_gate("air fryer", {"intent": "Commercial"}).decision == "淘汰"


def test_intent_gate_keeps_tool_and_toolizable_information_queries() -> None:
    assert intent_gate("ai image generator", {"intent": "Commercial"}).decision == "保留"
    assert intent_gate("how much protein do i need", {"intent": "Informational"}).decision == "保留"


def test_keyword_quality_gate_rejects_bare_numbers_before_paid_enrichment() -> None:
    assert keyword_quality_gate("67").decision == "淘汰"
    assert keyword_quality_gate("123456").decision == "淘汰"
    assert keyword_quality_gate("grade calculator").decision == "保留"
