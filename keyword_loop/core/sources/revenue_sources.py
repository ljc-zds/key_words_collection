"""Public revenue/trending ranking source helpers."""

from dataclasses import dataclass
from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen
from urllib.error import URLError
import json
import subprocess

from product_hunt.aitdk.product.product_hunt import trusted_ssl_context
from playwright.sync_api import sync_playwright

from ..clients.cdp_proxy import CdpBrowser


@dataclass(frozen=True)
class RevenueUrl:
    domain: str
    url: str
    source: str
    title: str = ""


class _LinkParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.links: list[tuple[str, str]] = []
        self._href: str | None = None
        self._text: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "a":
            self._href = dict(attrs).get("href")
            self._text = []

    def handle_data(self, data: str) -> None:
        if self._href is not None:
            self._text.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag == "a" and self._href:
            self.links.append((self._href, " ".join("".join(self._text).split())))
            self._href, self._text = None, []


class _RevenueRankingParser(HTMLParser):
    """Extract the domain identifiers emitted by web.cafe's rendered rank table."""

    def __init__(self) -> None:
        super().__init__()
        self.domains: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag != "a":
            return
        domain = dict(attrs).get("data-d")
        if domain:
            self.domains.append(domain)


def canonical_domain(url: str) -> str | None:
    host = (urlparse(url).hostname or "").lower().rstrip(".")
    if host.startswith("www."):
        host = host[4:]
    if not host or "." not in host:
        return None
    blocked = ("toolify.ai", "seo.web.cafe", "twitter.com", "x.com", "facebook.com", "linkedin.com")
    if any(host == item or host.endswith("." + item) for item in blocked):
        return None
    return host


def parse_revenue_links(html: str, source_url: str, source: str) -> list[RevenueUrl]:
    parser = _LinkParser()
    parser.feed(html)
    results: dict[str, RevenueUrl] = {}
    for href, title in parser.links:
        absolute = urljoin(source_url, href)
        domain = canonical_domain(absolute)
        if domain and domain not in results:
            results[domain] = RevenueUrl(domain, absolute, source, title)
    return list(results.values())


def parse_revenue_ranking_domains(html: str, source_url: str, source: str) -> list[RevenueUrl]:
    parser = _RevenueRankingParser()
    parser.feed(html)
    results: dict[str, RevenueUrl] = {}
    for raw_domain in parser.domains:
        domain = canonical_domain(f"https://{raw_domain}")
        if domain and domain not in results:
            results[domain] = RevenueUrl(domain, f"https://{domain}", source, domain)
    return list(results.values())


def _fetch_revenue_html_cdp(source_url: str, cdp_url: str) -> str:
    script = __import__("pathlib").Path(__file__).resolve().parents[1] / "clients" / "revenue_native_cdp.mjs"
    result = subprocess.run(["node", str(script), cdp_url, source_url], capture_output=True, text=True, timeout=45)
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or "native CDP ranking fetch failed")
    return result.stdout


def fetch_revenue_links(source_url: str, source: str, *, cdp_url: str | None = None) -> list[RevenueUrl]:
    request = Request(source_url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urlopen(request, context=trusted_ssl_context(), timeout=30) as response:
            html = response.read().decode("utf-8", errors="replace")
    except (URLError, OSError):
        if not cdp_url:
            raise
        html = _fetch_revenue_html_cdp(source_url, cdp_url)
    ranked = parse_revenue_ranking_domains(html, source_url, source)
    if ranked:
        return ranked
    if cdp_url:
        ranked = parse_revenue_ranking_domains(_fetch_revenue_html_cdp(source_url, cdp_url), source_url, source)
        if ranked:
            return ranked
    return parse_revenue_links(html, source_url, source)
