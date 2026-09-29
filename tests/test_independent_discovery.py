from types import SimpleNamespace

from keyword_loop.core.data.models import KeywordObservation
from keyword_loop.core.data.store import KeywordStore
from keyword_loop.workflows.discovery.independent import run_independent


class Semrush:
    database = "us"
    def __init__(self):
        self.calls = []

    def query(self, seed):
        self.calls.append(seed)
        return {"keywords": [
            {"keyword": "related a", "volume": 5000, "kd": 30, "cpc": .01},
            {"keyword": "related b", "volume": 10000, "kd": 45, "cpc": 1},
            {"keyword": "too hard", "volume": 5000, "kd": 31, "cpc": 1},
        ]}


def args(providers="similarweb,semrush", limit=50, continue_on_error=False):
    return SimpleNamespace(providers=providers, provider_limit=limit, continue_on_error=continue_on_error)


def test_continue_on_error_advances_failed_seed(tmp_path):
    store = KeywordStore(tmp_path / "db")
    class Broken:
        database = "us"
        def query(self, seed):
            if seed == "bad":
                raise RuntimeError("rpc failure")
            return {"keywords": [{"keyword": "good", "volume": 5000, "kd": 20, "cpc": .1}]}
    result = run_independent(args("semrush", 0, True), store, None, Broken(), {"root": ["bad", "good"]})
    assert result["semrush"]["status"] == "exhausted"
    assert store.get_state("independent:semrush:root:offset") == "2"


def test_zero_limit_exhausts_all_sources(tmp_path):
    store = KeywordStore(tmp_path / "db")
    sem = Semrush()
    result = run_independent(args("semrush", 0), store, None, sem,
                             {"stripe": ["a"], "toolify": ["b"], "root": ["c"]})
    assert sem.calls == ["a", "b", "c"]
    assert result["semrush"]["status"] == "exhausted"
    assert result["semrush"]["checked"] == 9


def test_each_provider_uses_its_own_checkpoint_and_accepts_without_cross_validation(tmp_path):
    store = KeywordStore(tmp_path / "db")
    store.set_state("discovery_only:root:offset", "1")
    calls = []
    def collect(seed):
        calls.append(seed)
        return [KeywordObservation("sw only", 6000, 20, "Navigational", seed, "Broad", "global", "now", cpc=.2)]
    sem = Semrush()
    result = run_independent(args(), store, SimpleNamespace(collect=collect), sem, {"root": ["old", "next"]})
    assert calls == ["next"]
    assert sem.calls == ["old", "next"]
    assert result["similarweb"]["added"] == 1
    assert result["semrush"]["added"] == 2
    assert store.connection.execute("SELECT count(*) FROM keyword_validation").fetchone()[0] == 0
    assert store.get_state("independent:similarweb:root:offset") == "2"
    assert store.get_state("independent:semrush:root:offset") == "2"


def test_partial_batch_resumes_without_query_and_retains_all_sources(tmp_path):
    store = KeywordStore(tmp_path / "db")
    sem = Semrush()
    seeds = {"stripe": ["product"], "toolify": ["product"]}
    first = run_independent(args("semrush", 1), store, None, sem, seeds)
    assert first["semrush"]["added"] == 1
    assert store.get_state("independent:semrush:stripe:offset") == "0"
    second = run_independent(args("semrush", 1), store, None, sem, seeds)
    assert second["semrush"]["added"] == 1
    assert sem.calls == ["product"]
    run_independent(args("semrush"), store, None, sem, seeds)
    assert store.connection.execute("SELECT count(*) FROM independent_candidates").fetchone()[0] == 2
    assert store.connection.execute("SELECT count(*) FROM independent_provenance").fetchone()[0] == 4


def test_failure_does_not_advance_and_other_provider_continues(tmp_path):
    store = KeywordStore(tmp_path / "db")
    def broken(_):
        raise RuntimeError("network unavailable")
    result = run_independent(args(), store, SimpleNamespace(collect=broken), Semrush(), {"root": ["one", "two"]})
    assert result["similarweb"]["status"] == "blocked"
    assert store.get_state("independent:similarweb:root:offset") == "0"
    assert result["semrush"]["added"] == 2


def test_seed_order_is_pinned_across_restart(tmp_path):
    store = KeywordStore(tmp_path / "db")
    sem = Semrush()
    run_independent(args("semrush", 1), store, None, sem, {"root": ["first", "second"]})
    run_independent(args("semrush"), store, None, sem, {"root": ["second", "first", "third"]})
    assert sem.calls == ["first", "second", "third"]


def test_import_preserves_old_data_and_does_not_count_it_as_new(tmp_path):
    store = KeywordStore(tmp_path / "db")
    store.record_semrush_related("related a", "us", "historic seed",
                                 {"volume": 5000, "kd": 30, "cpc": .01, "validation_status": "待Similarweb验证"})
    result = run_independent(args("semrush"), store, None, Semrush(), {"root": ["seed"]})
    assert result["semrush"]["added"] == 1
    assert store.connection.execute("SELECT count(*) FROM semrush_related_candidates").fetchone()[0] == 1
    assert store.connection.execute("SELECT count(*) FROM independent_candidates").fetchone()[0] == 2


def test_cli_defaults_to_independent_and_keeps_legacy_opt_in(monkeypatch):
    from keyword_loop.workflows.discovery.cli import parse_args
    monkeypatch.setattr("sys.argv", ["discovery"])
    parsed = parse_args()
    assert parsed.mode == "independent"
    assert parsed.providers == "similarweb,semrush"
    monkeypatch.setattr("sys.argv", ["discovery", "--mode", "cross-validation"])
    assert parse_args().mode == "cross-validation"


def test_migration_preserves_duplicate_seed_positions(tmp_path):
    store = KeywordStore(tmp_path / "db")
    store.set_state("discovery_only:root:offset", "2")
    calls = []
    collector = SimpleNamespace(collect=lambda seed: calls.append(seed) or [])
    run_independent(args("similarweb"), store, collector, None, {"root": ["same", "same", "next"]})
    assert calls == ["next"]


def test_filters_preserve_boundary_and_reject_missing_metrics(tmp_path):
    store = KeywordStore(tmp_path / "db")
    data = [
        {"keyword": "large", "volume": 30000, "kd": 60, "cpc": .01},
        {"keyword": "small", "volume": 4999, "kd": 1, "cpc": 1},
        {"keyword": "no cpc", "volume": 50000, "kd": 1},
        {"keyword": "medium hard", "volume": 29999, "kd": 46, "cpc": 1},
    ]
    provider = SimpleNamespace(database="us", query=lambda _: {"keywords": data})
    result = run_independent(args("semrush"), store, None, provider, {"root": ["test"]})
    assert result["semrush"]["added"] == 1
    assert store.connection.execute("SELECT keyword FROM independent_candidates").fetchall() == [("large",)]


def test_similarweb_timeout_retries_once_then_retains_success(tmp_path):
    from keyword_loop.core.clients.similarweb import BrowserProxyError
    store = KeywordStore(tmp_path / "db")
    calls = []
    def collect(seed):
        calls.append(seed)
        if len(calls) == 1:
            raise BrowserProxyError("Similarweb primary JSON was not captured")
        return [KeywordObservation("recovered", 6000, 20, None, seed, "Broad", "global", "now", cpc=.1)]
    result = run_independent(args("similarweb"), store, SimpleNamespace(collect=collect), None, {"root": ["seed"]})
    assert calls == ["seed", "seed"]
    assert result["similarweb"]["added"] == 1
    assert store.get_state("independent:similarweb:root:offset") == "1"


def test_two_timeouts_skip_seed_keep_failure_and_continue(tmp_path):
    import subprocess
    store = KeywordStore(tmp_path / "db")
    calls = []
    def collect(seed):
        calls.append(seed)
        if seed == "bad":
            raise subprocess.TimeoutExpired("node", 60)
        return [KeywordObservation("next word", 6000, 20, None, seed, "Broad", "global", "now", cpc=.1)]
    result = run_independent(args("similarweb"), store, SimpleNamespace(collect=collect), None, {"root": ["bad", "good"]})
    assert calls == ["bad", "bad", "good"]
    assert result["similarweb"]["added"] == 1
    assert store.get_state("independent:similarweb:root:offset") == "2"
    assert "2" in store.connection.execute("SELECT reason FROM collection_failures").fetchone()[0]
    assert store.validation("bad", "global", "semrush") is None


def test_valid_empty_result_is_not_retried(tmp_path):
    store = KeywordStore(tmp_path / "db")
    calls = []
    result = run_independent(args("similarweb"), store, SimpleNamespace(collect=lambda seed: calls.append(seed) or []), None, {"root": ["empty", "next"]})
    assert calls == ["empty", "next"]
    assert result["similarweb"]["status"] == "exhausted"
