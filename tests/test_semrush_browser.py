from keyword_loop.core.clients.semrush_browser import normalize_keyword_row


def test_report_limit_stops_discovery_without_retries_or_checkpoint_advance(tmp_path, monkeypatch):
    import pytest
    from types import SimpleNamespace
    from keyword_loop.core.clients import semrush_browser as client
    from keyword_loop.core.data.store import KeywordStore
    from keyword_loop.core.data.models import KeywordObservation
    from keyword_loop.workflows.discovery import pipeline

    calls = []
    def failed_run(*args, **kwargs):
        calls.append(args)
        return SimpleNamespace(returncode=1, stderr="Error: SEMRUSH_REPORT_LIMIT: -2004 Report limit reached", stdout="")
    monkeypatch.setattr(client.subprocess, "run", failed_run)
    monkeypatch.setattr(client.time, "sleep", lambda _: None)
    monkeypatch.setattr(pipeline, "source_terms", lambda _: {"root": ["seed"]})
    store = KeywordStore(tmp_path / "test.sqlite3")
    collector = SimpleNamespace(collect=lambda _: [KeywordObservation("grade calculator", 50000, 30, "Commercial", "seed", "Broad", "global", "now")])
    args = SimpleNamespace(source_approved_limit=None, new_only=True, semrush_limit=50)
    with pytest.raises(client.BrowserProxyError, match="SEMRUSH_REPORT_LIMIT"):
        pipeline.run_discovery(args, store, collector, client.SemrushBrowserProvider(cdp_url="http://localhost:9222", discovery_filters=True))
    assert len(calls) == 1
    assert store.get_state("discovery_only:root:offset", "0") == "0"
    assert store.validation("grade calculator", "global", "semrush") is None
    assert "Report limit reached" in store.connection.execute("SELECT reason FROM collection_failures").fetchone()[0]


def test_normalize_keyword_magic_response_fields() -> None:
    result = normalize_keyword_row({
        "phrase": "rotate pdf", "difficulty": 47, "competition_level": 0.15,
        "intents": [0, 2], "serp_features": [7, 9, 21],
    })

    assert result["kd"] == 47
    assert result["competitive_density"] == 0.15
    assert result["intent"] == "Informational/Commercial"
    assert result["serp_features"] == 3
