"""Official TabAPI client for domain registration and traffic signals."""

import json
import re
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin
from urllib.request import HTTPRedirectHandler, HTTPSHandler, Request, build_opener, urlopen

from ..product.product_hunt import trusted_ssl_context


BASE_URL = "https://tabapi.com/api/v1"
USER_AGENT = "ProductHunt-Demand-Radar/1.0"


class TabAPIError(RuntimeError):
    def __init__(self, status: int, message: str = "") -> None:
        super().__init__(message or f"TabAPI returned HTTP {status}")
        self.status = status


def load_tabapi_key(env_file: Path) -> str:
    for line in env_file.read_text(encoding="utf-8").splitlines():
        if line.startswith("TABAPI_KEY="):
            key = line.partition("=")[2].strip()
            if key:
                return key
    raise RuntimeError("TABAPI_KEY is missing from .env")


def _get_json(path: str, key: str, *, opener=urlopen, sleeper=time.sleep) -> dict:
    request = Request(
        f"{BASE_URL}/{path}",
        headers={
            "Authorization": f"Bearer {key}",
            "Accept": "application/json",
            "User-Agent": USER_AGENT,
        },
    )
    for attempt in range(3):
        try:
            with opener(request, timeout=60, context=trusted_ssl_context()) as response:
                return json.load(response)
        except HTTPError as error:
            if error.code not in (429, 500, 502, 503, 504) or attempt == 2:
                raise TabAPIError(error.code) from error
        except (URLError, TimeoutError):
            if attempt == 2:
                raise
        sleeper(2 ** attempt)
    raise RuntimeError("unreachable")


def fetch_rdap(domain: str, key: str) -> dict:
    return _get_json(f"domains/{domain}/rdap", key)


def fetch_whois(domain: str, key: str) -> dict:
    return _get_json(f"domains/{domain}/whois", key)


def fetch_traffic(domain: str, key: str, months: int = 3) -> dict:
    return _get_json(f"domains/{domain}/traffic?months={months}", key)


def registration_date(payload: dict) -> str | None:
    for event in payload.get("events", []):
        if event.get("eventAction") == "registration" and event.get("eventDate"):
            return str(event["eventDate"])[:10]
    return None


def whois_registration_date(raw: str) -> str | None:
    pattern = re.compile(
        r"(?im)^\s*(?:creation date|created on|created|registered on|registration date|domain registration date)\s*:\s*"
        r"(\d{4}-\d{2}-\d{2})"
    )
    match = pattern.search(raw)
    return match.group(1) if match else None


def fetch_public_rdap(domain: str) -> dict:
    request = Request(
        f"https://rdap.org/domain/{domain}",
        headers={"Accept": "application/rdap+json, application/json", "User-Agent": USER_AGENT},
    )
    with urlopen(request, timeout=10, context=trusted_ssl_context()) as response:
        return json.load(response)


def fetch_registration_date(domain: str, key: str) -> str | None:
    try:
        registered = registration_date(fetch_public_rdap(domain))
        if registered:
            return registered
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError):
        pass
    try:
        registered = registration_date(fetch_rdap(domain, key))
        if registered:
            return registered
    except (TabAPIError, URLError, TimeoutError):
        pass
    try:
        registered = whois_registration_date(fetch_whois(domain, key).get("raw", ""))
        if registered:
            return registered
    except (TabAPIError, URLError, TimeoutError):
        pass
    return None


def traffic_panel(payload: dict, registered: str | None) -> dict:
    overview = payload.get("overview") or {}
    sources = payload.get("traffic_sources") or {}
    return {
        "status": "ok" if overview.get("visits") is not None else "missing",
        "monthly_visits": overview.get("visits"),
        "monthly_visits_trend": payload.get("monthly_visits") or [],
        "search_share": sources.get("search_organic", sources.get("search")),
        "direct_share": sources.get("direct"),
        "registered": registered,
        "keywords": payload.get("top_keywords") or [],
    }


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _open_without_redirect(request: Request):
    opener = build_opener(HTTPSHandler(context=trusted_ssl_context()), _NoRedirect())
    try:
        return opener.open(request, timeout=30)
    except HTTPError as error:
        if 300 <= error.code < 400:
            return error
        raise


def resolve_url(url: str, *, opener=_open_without_redirect) -> str:
    request = Request(url, headers={"User-Agent": USER_AGENT})
    response = opener(request)
    location = response.headers.get("Location")
    if location:
        return urljoin(url, location)
    return response.geturl()
