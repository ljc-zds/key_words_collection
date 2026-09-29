from datetime import datetime, timezone
from urllib.error import HTTPError

from product_hunt.aitdk import tabapi
from product_hunt.aitdk.legacy.tabapi import _get_json, registration_date, resolve_url, traffic_panel, whois_registration_date


def test_registration_date_reads_rdap_registration_event() -> None:
    payload = {"events": [
        {"eventAction": "last changed", "eventDate": "2026-08-20T10:00:00Z"},
        {"eventAction": "registration", "eventDate": "2026-01-15T05:00:00Z"},
    ]}

    assert registration_date(payload) == "2026-01-15"


def test_registration_date_uses_free_public_rdap_before_tabapi(monkeypatch) -> None:
    monkeypatch.setattr(
        tabapi,
        "fetch_public_rdap",
        lambda _domain: {"events": [{"eventAction": "registration", "eventDate": "2026-02-03T00:00:00Z"}]},
    )

    def unexpected_tabapi_call(*_args):
        raise AssertionError("TabAPI should not be called when public RDAP has a registration date")

    monkeypatch.setattr(tabapi, "fetch_rdap", unexpected_tabapi_call)
    monkeypatch.setattr(tabapi, "fetch_whois", unexpected_tabapi_call)

    assert tabapi.fetch_registration_date("example.com", "key") == "2026-02-03"


def test_registration_date_falls_back_to_tabapi_when_public_rdap_fails(monkeypatch) -> None:
    calls = []

    def unavailable_public_rdap(_domain):
        calls.append("public")
        raise TimeoutError

    def tabapi_rdap(_domain, _key):
        calls.append("tabapi")
        return {"events": [{"eventAction": "registration", "eventDate": "2025-11-09T00:00:00Z"}]}

    monkeypatch.setattr(tabapi, "fetch_public_rdap", unavailable_public_rdap)
    monkeypatch.setattr(tabapi, "fetch_rdap", tabapi_rdap)

    assert tabapi.fetch_registration_date("example.com", "key") == "2025-11-09"
    assert calls == ["public", "tabapi"]


def test_traffic_panel_normalizes_tabapi_fields() -> None:
    payload = {
        "overview": {"visits": 12_345},
        "traffic_sources": {"search_organic": 0.31, "direct": 0.42},
        "monthly_visits": [
            {"month": "2026-06", "visits": 10_000},
            {"month": "2026-07", "visits": 11_000},
            {"month": "2026-08", "visits": 12_345},
        ],
        "top_keywords": [{"name": "invoice generator", "estimated_value": 900, "volume": 1200}],
    }

    panel = traffic_panel(payload, "2026-01-15")

    assert panel["monthly_visits"] == 12_345
    assert panel["search_share"] == 0.31
    assert panel["direct_share"] == 0.42
    assert panel["registered"] == "2026-01-15"
    assert panel["keywords"][0]["name"] == "invoice generator"
    assert panel["monthly_visits_trend"][-1] == {"month": "2026-08", "visits": 12_345}


def test_tabapi_retries_temporary_upstream_errors() -> None:
    attempts = 0

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def read(self):
            return b'{"ok": true}'

    def opener(*_args, **_kwargs):
        nonlocal attempts
        attempts += 1
        if attempts < 3:
            raise HTTPError("https://tabapi.com", 502, "upstream", None, None)
        return Response()

    assert _get_json("test", "key", opener=opener, sleeper=lambda _seconds: None) == {"ok": True}
    assert attempts == 3


def test_whois_registration_date_parses_common_creation_fields() -> None:
    assert whois_registration_date("Creation Date: 2025-09-25T12:30:00Z") == "2025-09-25"
    assert whois_registration_date("Registered On: 2026-01-02") == "2026-01-02"


def test_resolve_url_uses_redirect_location_without_opening_destination() -> None:
    class Redirect:
        status = 302
        headers = {"Location": "https://example.com/product"}

    assert resolve_url("https://producthunt.com/r/example", opener=lambda _request: Redirect()) == "https://example.com/product"
