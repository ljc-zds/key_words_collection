from product_hunt.aitdk.product.resolver import select_website_url


def test_select_website_url_uses_visit_website_anchor() -> None:
    href = select_website_url([
        {"text": "Cloudflare", "href": "https://cloudflare.com"},
        {"text": "Visit website", "href": "https://example.com"},
    ])
    assert href == "https://example.com"
