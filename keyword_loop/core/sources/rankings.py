from dataclasses import dataclass
from html.parser import HTMLParser
from urllib.parse import urljoin
from urllib.parse import urlparse
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from product_hunt.aitdk.product.product_hunt import trusted_ssl_context
from .revenue_sources import _fetch_revenue_html_cdp


@dataclass(frozen=True)
class RankedProduct:
    name: str
    detail_url: str
    rank: int
    monthly_visits: str
    growth: str
    description: str
    source_url: str


class _ToolifyTableParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.rows: list[list[tuple[str, str | None]]] = []
        self.row: list[tuple[str, str | None]] | None = None
        self.cell: list[str] | None = None
        self.href: str | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "tr": self.row = []
        elif tag in {"td", "th"} and self.row is not None: self.cell, self.href = [], None
        elif tag == "a" and self.cell is not None: self.href = dict(attrs).get("href")

    def handle_data(self, data: str) -> None:
        if self.cell is not None: self.cell.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag in {"td", "th"} and self.cell is not None and self.row is not None:
            self.row.append((" ".join("".join(self.cell).split()), self.href)); self.cell = None
        elif tag == "tr" and self.row is not None:
            self.rows.append(self.row); self.row = None


def parse_toolify_page(html: str, source_url: str) -> list[RankedProduct]:
    parser = _ToolifyTableParser(); parser.feed(html)
    products = []
    fallback_rank = 0
    for row in parser.rows:
        # Toolify omits the rank cell for the first few sponsored/top rows.
        # Locate the first linked cell and derive the metric columns relative
        # to it instead of relying on a fixed table layout.
        if len(row) < 5:
            continue
        link_index = next((i for i, (_, href) in enumerate(row) if href), None)
        if link_index is None or not row[link_index][0]:
            continue
        rank_text = row[0][0] if row and row[0][0].isdigit() else ""
        if rank_text:
            rank = int(rank_text)
            fallback_rank = max(fallback_rank, rank)
        else:
            fallback_rank += 1
            rank = fallback_rank
        cells = [text for text, _ in row]
        metrics = cells[link_index + 1:]
        if len(metrics) < 2:
            continue
        monthly_visits, growth = metrics[0], metrics[1]
        description = metrics[3] if len(metrics) > 3 else (metrics[2] if len(metrics) > 2 else "")
        products.append(RankedProduct(row[link_index][0], urljoin(source_url, row[link_index][1] or ""), rank, monthly_visits, growth, description, source_url))
    return products


def select_official_url(urls: list[str]) -> str | None:
    rejected = ("toolify.ai", "twitter.com", "x.com", "linkedin.com", "facebook.com", "instagram.com", "youtube.com")
    for url in urls:
        host = (urlparse(url).hostname or "").lower()
        if host and not any(host == item or host.endswith(f".{item}") for item in rejected):
            return url
    return None


def select_toolify_open_site(links: list[tuple[str, str]]) -> str | None:
    for url, label in links:
        if label.strip().lower() == "open site":
            return url
    return None


def _fetch_toolify_html(source_url: str) -> str:
    request = Request(source_url, headers={"User-Agent": "Mozilla/5.0"})
    with urlopen(request, context=trusted_ssl_context(), timeout=30) as response:
        return response.read().decode("utf-8", errors="replace")


def _fetch_toolify_html_cdp(source_url: str, cdp_url: str) -> str:
    """Read Toolify's public ranking page through the user's existing Chrome session."""
    return _fetch_revenue_html_cdp(source_url, cdp_url)


def fetch_toolify_ranking(source_url: str, *, cdp_url: str | None = None) -> list[RankedProduct]:
    """Fetch Toolify rankings, falling back to Chrome only for Cloudflare blocks."""
    try:
        html = _fetch_toolify_html(source_url)
    except HTTPError as error:
        if error.code != 403 or not cdp_url:
            raise
        html = _fetch_toolify_html_cdp(source_url, cdp_url)
    products = parse_toolify_page(html, source_url)
    if products or not cdp_url:
        return products
    # Cloudflare can return a challenge page with HTTP 200. A ranking page
    # with no parsable products is therefore retried in the existing browser.
    return parse_toolify_page(_fetch_toolify_html_cdp(source_url, cdp_url), source_url)
