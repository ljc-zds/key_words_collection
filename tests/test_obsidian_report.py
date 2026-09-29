from product_hunt.aitdk.data.obsidian_report import render_report


def test_render_report_contains_front_matter_and_product_link() -> None:
    report = render_report(
        "2026-08-21",
        [{"name": "Example", "product_hunt_url": "https://producthunt.com/posts/example", "domain": "example.com", "keywords": ["invoice template"]}],
        [],
    )
    assert "source: product-hunt" in report
    assert "[Example](https://producthunt.com/posts/example)" in report
    assert "invoice template" in report
