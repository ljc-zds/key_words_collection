import json

import pytest

from product_hunt.aitdk.protocol import client
from product_hunt.aitdk.protocol.client import AitdkMcpError, traffic_panel


def test_traffic_panel_maps_aitdk_mcp_domain_enrich_data() -> None:
    panel = traffic_panel({
        "overview": {"visits": "12,345"},
        "traffic_sources": {"searchOrganic": 0.31, "direct": 0.42},
        "top_keywords": [{"name": "invoice generator", "volume": "4500"}],
        "whois": {"creationDate": "2026-01-15T12:00:00Z"},
    })

    assert panel == {
        "status": "ok",
        "monthly_visits": 12_345,
        "monthly_visits_trend": [],
        "search_share": 0.31,
        "direct_share": 0.42,
        "registered": "2026-01-15",
        "keywords": [{"name": "invoice generator", "volume": 4500}],
    }


def test_traffic_panel_requires_aitdk_visit_data() -> None:
    panel = traffic_panel({"overview": {}, "traffic_sources": {}, "top_keywords": []})

    assert panel["status"] == "missing"
    assert panel["registered"] is None


def test_cdp_preflight_requires_a_chrome_devtools_response(monkeypatch) -> None:
    class Response:
        def read(self):
            return json.dumps({"Browser": "Chrome/140"}).encode()

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

    monkeypatch.setattr(client, "urlopen", lambda *_args, **_kwargs: Response())
    client.ensure_cdp_available("http://127.0.0.1:9222")

    monkeypatch.setattr(client, "urlopen", lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError("down")))
    with pytest.raises(AitdkMcpError, match="Chrome CDP"):
        client.ensure_cdp_available("http://127.0.0.1:9222")


def test_whois_client_reads_optional_created_date(monkeypatch) -> None:
    monkeypatch.setattr(client, "_call_tool", lambda *_args, **_kwargs: {"created_date": "2026-06-01"})
    assert client.whois_created_date("example.com") == "2026-06-01"

    monkeypatch.setattr(client, "_call_tool", lambda *_args, **_kwargs: {"created_date": None})
    assert client.whois_created_date("example.com") is None
