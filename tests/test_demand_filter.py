from product_hunt.aitdk.domain.demand_filter import evaluate_candidate


def test_evaluate_candidate_extracts_non_brand_keywords() -> None:
    result = evaluate_candidate(
        domain="example.com",
        product_name="Example",
        traffic={"overview": {"visits": "15000"}, "trafficSources": {"searchOrganic": 0.3, "direct": 0.25}},
        domain_age_days=180,
        keywords=[{"name": "example"}, {"name": "invoice template"}],
    )
    assert result.passed is True
    assert result.non_brand_keywords == ["invoice template"]


def test_non_brand_keywords_do_not_add_a_fourth_filter_condition() -> None:
    result = evaluate_candidate(
        domain="example.com",
        product_name="Example",
        traffic={"overview": {"visits": 15000}, "trafficSources": {"searchOrganic": 0.3, "direct": 0.25}},
        domain_age_days=180,
        keywords=[{"name": "example"}],
    )

    assert result.passed is True
    assert result.non_brand_keywords == []


def test_monthly_search_visits_must_exceed_3000() -> None:
    result = evaluate_candidate(
        domain="tool.com",
        product_name="Tool",
        traffic={"overview": {"visits": 5000}, "trafficSources": {"searchOrganic": 0.3, "direct": 0.25}},
        domain_age_days=100,
        keywords=[{"name": "invoice generator"}],
    )

    assert result.passed is False
    assert "monthly search visits are below 3000" in result.reasons


def test_screenshot_filter_boundaries_are_inclusive() -> None:
    result = evaluate_candidate(
        domain="tool.com",
        product_name="Tool",
        traffic={"overview": {"visits": 15_000}, "trafficSources": {"searchOrganic": 0.2, "direct": 0.2}},
        domain_age_days=365,
        keywords=[],
    )

    assert result.passed is True
