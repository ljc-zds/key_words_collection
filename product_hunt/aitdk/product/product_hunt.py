"""Official Product Hunt GraphQL collection."""

import json
import ssl
import time as clock
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from typing import Callable
from urllib.parse import urlparse
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import certifi


@dataclass(frozen=True)
class ProductCandidate:
    product_id: str
    name: str
    tagline: str
    product_hunt_url: str
    website_url: str
    domain: str
    created_at: str
    votes_count: int


def load_developer_token(env_file: Path) -> str:
    """Read the local Product Hunt token without exporting it to process logs."""
    for line in env_file.read_text(encoding="utf-8").splitlines():
        if line.startswith("PRODUCT_HUNT_DEVELOPER_TOKEN="):
            token = line.partition("=")[2].strip()
            if token:
                return token
    raise RuntimeError("PRODUCT_HUNT_DEVELOPER_TOKEN is missing from .env")


def trusted_ssl_context() -> ssl.SSLContext:
    return ssl.create_default_context(cafile=certifi.where())


def normalize_posts(payload: dict) -> list[ProductCandidate]:
    edges = payload.get("data", {}).get("posts", {}).get("edges", [])
    candidates: list[ProductCandidate] = []
    for edge in edges:
        node = edge.get("node", {})
        website = next(
            (link.get("url", "") for link in node.get("productLinks", []) if link.get("type") == "Website"),
            node.get("website") or "",
        )
        domain = urlparse(website).hostname
        if not domain:
            continue
        candidates.append(
            ProductCandidate(
                product_id=node["id"], name=node.get("name", ""), tagline=node.get("tagline", ""),
                product_hunt_url=node.get("url", ""), website_url=website, domain=domain.lower(),
                created_at=node.get("createdAt", ""), votes_count=node.get("votesCount", 0),
            )
        )
    return candidates


def fetch_newest_posts(token: str, limit: int = 20) -> list[ProductCandidate]:
    query = (
        "query($first: Int!, $after: String) { "
        "posts(first: $first, after: $after, order: NEWEST) { "
        "pageInfo { hasNextPage endCursor } edges { node { "
        "id name tagline url website productLinks { type url } createdAt votesCount "
        "} } } }"
    )
    candidates: list[ProductCandidate] = []
    cursor: str | None = None
    while len(candidates) < limit:
        page_size = min(20, limit - len(candidates))
        request = Request(
            "https://api.producthunt.com/v2/api/graphql",
            data=json.dumps({"query": query, "variables": {"first": page_size, "after": cursor}}).encode(),
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            method="POST",
        )
        with urlopen(request, timeout=30, context=trusted_ssl_context()) as response:
            payload = json.load(response)
        if payload.get("errors"):
            raise RuntimeError("Product Hunt API rejected the GraphQL query")
        page = payload.get("data", {}).get("posts", {})
        candidates.extend(normalize_posts(payload))
        page_info = page.get("pageInfo", {})
        cursor = page_info.get("endCursor")
        if not page_info.get("hasNextPage") or not cursor:
            break
    return candidates[:limit]


def _rate_limit_wait_seconds(error: HTTPError) -> int:
    try:
        return max(1, int(error.headers.get("X-Rate-Limit-Reset", "60")))
    except ValueError:
        return 60


def _read_request_json(request: Request, *, opener=urlopen, sleeper=clock.sleep) -> dict:
    network_attempts = 0
    rate_limit_attempts = 0
    while True:
        try:
            with opener(request, timeout=30, context=trusted_ssl_context()) as response:
                return json.load(response)
        except HTTPError as error:
            if error.code != 429 or rate_limit_attempts == 3:
                raise
            rate_limit_attempts += 1
            sleeper(_rate_limit_wait_seconds(error))
        except (URLError, TimeoutError):
            network_attempts += 1
            if network_attempts == 3:
                raise


def fetch_posts_for_date(
    token: str,
    collection_date: date,
    *,
    request_page: Callable[[Request], dict] = _read_request_json,
) -> list[ProductCandidate]:
    """Fetch every Product Hunt post created on one UTC calendar date."""
    start = datetime.combine(collection_date, time.min, tzinfo=timezone.utc)
    end = start + timedelta(days=1)
    query = (
        "query($first: Int!, $after: String, $postedAfter: DateTime, $postedBefore: DateTime) { "
        "posts(first: $first, after: $after, order: NEWEST, "
        "postedAfter: $postedAfter, postedBefore: $postedBefore) { "
        "pageInfo { hasNextPage endCursor } edges { node { "
        "id name tagline url website productLinks { type url } createdAt votesCount "
        "} } } }"
    )
    candidates: list[ProductCandidate] = []
    cursor: str | None = None
    while True:
        variables = {
            "first": 50,
            "after": cursor,
            "postedAfter": start.isoformat().replace("+00:00", "Z"),
            "postedBefore": end.isoformat().replace("+00:00", "Z"),
        }
        request = Request(
            "https://api.producthunt.com/v2/api/graphql",
            data=json.dumps({"query": query, "variables": variables}).encode(),
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            method="POST",
        )
        payload = request_page(request)
        if payload.get("errors"):
            raise RuntimeError("Product Hunt API rejected the GraphQL query")
        candidates.extend(normalize_posts(payload))
        page_info = payload.get("data", {}).get("posts", {}).get("pageInfo", {})
        cursor = page_info.get("endCursor")
        if not page_info.get("hasNextPage") or not cursor:
            break
    return candidates
