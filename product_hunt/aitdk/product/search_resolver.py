"""Choose likely official websites from browser search results."""

import json
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from .product_hunt import trusted_ssl_context


_REJECTED_HOSTS = (
    "producthunt.com",
    "linkedin.com",
    "twitter.com",
    "x.com",
    "facebook.com",
    "instagram.com",
    "youtube.com",
    "crunchbase.com",
    "github.com",
    "apps.apple.com",
    "play.google.com",
)


def select_official_domain(hrefs: list[str]) -> str | None:
    for href in hrefs:
        hostname = (urlparse(href).hostname or "").lower()
        if hostname and not any(hostname == item or hostname.endswith(f".{item}") for item in _REJECTED_HOSTS):
            return href
    return None


def build_search_query(product_name: str, tagline: str) -> str:
    return f"{product_name} {tagline} official website"


def resolve_with_serper(product_name: str, tagline: str, api_key: str) -> str | None:
    request = Request(
        "https://google.serper.dev/search",
        data=json.dumps({"q": build_search_query(product_name, tagline), "num": 10}).encode(),
        headers={"X-API-KEY": api_key, "Content-Type": "application/json"},
        method="POST",
    )
    with urlopen(request, context=trusted_ssl_context(), timeout=30) as response:
        data = json.load(response)
    return select_official_domain([item.get("link", "") for item in data.get("organic", [])])
