from product_hunt.aitdk.product.search_resolver import build_search_query, select_official_domain


def test_select_official_domain_rejects_non_official_hosts() -> None:
    href = select_official_domain([
        "https://www.producthunt.com/posts/example",
        "https://www.linkedin.com/company/example",
        "https://www.crunchbase.com/organization/example",
        "https://example.com",
    ])
    assert href == "https://example.com"


def test_build_search_query_combines_product_name_and_tagline() -> None:
    assert build_search_query("Example", "A useful tool") == "Example A useful tool official website"
