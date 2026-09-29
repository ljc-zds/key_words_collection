from urllib.error import HTTPError

import pytest

from keyword_loop.core.sources.rankings import fetch_toolify_ranking, parse_toolify_page, select_official_url, select_toolify_open_site


def test_parse_toolify_page_extracts_ranked_product_cards() -> None:
    html = '''<table><tr><th>Ranking</th></tr><tr><td>4</td><td><a href="/tool/example">Example</a></td><td>1.2M</td><td>300K</td><td>20%</td><td>Example description</td></tr></table>'''
    products = parse_toolify_page(html, "https://www.toolify.ai/Best-trending-AI-Tools")
    assert len(products) == 1
    assert products[0].name == "Example"
    assert products[0].detail_url == "https://www.toolify.ai/tool/example"
    assert products[0].rank == 4
    assert products[0].monthly_visits == "1.2M"


def test_parse_toolify_page_assigns_ranks_to_unranked_top_rows() -> None:
    html = '''<table><tr><th>Ranking</th></tr>
      <tr><td></td><td><a href="/tool/first">First</a></td><td>5.5B</td><td>68.1M</td><td>1%</td><td>First desc</td></tr>
      <tr><td></td><td><a href="/tool/second">Second</a></td><td>380M</td><td>23M</td><td>6%</td><td>Second desc</td></tr></table>'''
    products = parse_toolify_page(html, "https://www.toolify.ai/Best-trending-AI-Tools")
    assert [(p.rank, p.name) for p in products] == [(1, "First"), (2, "Second")]


def test_select_official_url_rejects_toolify_and_social_links() -> None:
    assert select_official_url([
        "https://www.toolify.ai/tool/example",
        "https://twitter.com/example",
        "https://example.com",
    ]) == "https://example.com"


def test_select_toolify_open_site_uses_named_link_not_sponsored_link() -> None:
    links = [("https://www.checkdomain.ai/", "Sponsored"), ("https://chatgpt.com?utm_source=toolify", "Open site")]
    assert select_toolify_open_site(links) == "https://chatgpt.com?utm_source=toolify"


def test_fetch_toolify_ranking_uses_cdp_after_cloudflare_forbidden(monkeypatch) -> None:
    source_url = "https://www.toolify.ai/Best-trending-AI-Tools"
    html = '''<table><tr><th>Ranking</th></tr><tr><td>1</td><td><a href="/tool/example">Example</a></td><td>1M</td><td>2K</td><td>3%</td></tr></table>'''

    def blocked(*_args, **_kwargs):
        raise HTTPError(source_url, 403, "Forbidden", None, None)

    captured = {}
    monkeypatch.setattr("keyword_loop.core.sources.rankings._fetch_toolify_html", blocked)
    monkeypatch.setattr(
        "keyword_loop.core.sources.rankings._fetch_toolify_html_cdp",
        lambda url, cdp_url: captured.update(url=url, cdp_url=cdp_url) or html,
    )

    products = fetch_toolify_ranking(source_url, cdp_url="http://127.0.0.1:9222")

    assert [product.name for product in products] == ["Example"]
    assert captured == {"url": source_url, "cdp_url": "http://127.0.0.1:9222"}


def test_fetch_toolify_ranking_uses_cdp_when_challenge_page_returns_http_200(monkeypatch) -> None:
    source_url = "https://www.toolify.ai/Best-trending-AI-Tools"
    html = '''<table><tr><th>Ranking</th></tr><tr><td>1</td><td><a href="/tool/example">Example</a></td><td>1M</td><td>2K</td><td>3%</td></tr></table>'''

    monkeypatch.setattr("keyword_loop.core.sources.rankings._fetch_toolify_html", lambda _url: "<html>challenge</html>")
    monkeypatch.setattr("keyword_loop.core.sources.rankings._fetch_toolify_html_cdp", lambda _url, _cdp_url: html)

    products = fetch_toolify_ranking(source_url, cdp_url="http://127.0.0.1:9222")

    assert [product.name for product in products] == ["Example"]
