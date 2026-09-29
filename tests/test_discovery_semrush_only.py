from keyword_loop.core.data.models import KeywordObservation
from keyword_loop.core.data.store import KeywordStore
from keyword_loop.workflows.discovery import (
    DiscoveryTotals,
    collect_and_gate_source,
    initial_discovery_totals,
    remaining_terms,
    semrush_target_reached,
    validate_semrush_intent,
    validate_semrush,
)


def test_discovery_totals_reports_only_discovery_stages() -> None:
    totals = DiscoveryTotals(stored=2, similarweb_passed=1, semrush_checked=1, semrush_passed=1, semrush_rejected=0)

    assert totals.to_dict() == {
        "stored": 2,
        "similarweb_passed": 1,
        "semrush_checked": 1,
        "semrush_passed": 1,
        "semrush_rejected": 0,
    }


class FakeCollector:
    def __init__(self, observations):
        self.observations = observations

    def collect(self, term):
        return self.observations


def test_collect_and_gate_source_records_only_similarweb_tier_passes(tmp_path) -> None:
    store = KeywordStore(tmp_path / "loop.sqlite3")
    collector = FakeCollector([
        KeywordObservation("good calculator", 30_000, 60, "Commercial", "calc", "Phrase", "global", "now"),
        KeywordObservation("weak calculator", 9_000, 31, "Commercial", "calc", "Phrase", "global", "now"),
    ])

    stored, passed = collect_and_gate_source(store, collector, "root", ["calc"])

    assert (stored, passed) == (2, 1)


class FakeSemrush:
    def query(self, keyword):
        return {"keywords": [{
            "keyword": keyword, "volume": 165_000, "difficulty": 49,
            "cpc": 1.2, "intents": [2], "competition_level": 0.1,
            "serp_features": [1, 2],
        }]}


def test_related_candidates_survive_missing_exact_without_polluting_similarweb(tmp_path):
    class Provider:
        calls = 0
        database = "us"

        def query(self, keyword):
            self.calls += 1
            return {"keywords": [
                {"keyword": "good related", "volume": 5000, "kd": 30, "cpc": .01},
                {"keyword": "hard related", "volume": 5000, "kd": 31, "cpc": 1},
                {"keyword": "small related", "volume": 4999, "kd": 10, "cpc": 1},
                {"keyword": "free related", "volume": 50000, "kd": 10, "cpc": 0},
            ]}

    store = KeywordStore(tmp_path / "loop.sqlite3")
    provider = Provider()
    for parent in ["first", "first", "second"]:
        assert validate_semrush(store, provider, parent, "global").decision == "淘汰"
    rows = store.connection.execute(
        "SELECT keyword,database_name,parent_keyword FROM semrush_related_candidates ORDER BY parent_keyword"
    ).fetchall()
    assert rows == [("good related", "us", "first"), ("good related", "us", "second")]
    assert provider.calls == 3
    assert store.connection.execute("SELECT count(*) FROM keywords").fetchone()[0] == 0
    assert store.approved_discovery_keywords() == set()
    assert store.validation("first", "global", "semrush")["related_candidates_retained"] == 1


def test_validate_semrush_records_normalized_us_metrics(tmp_path) -> None:
    store = KeywordStore(tmp_path / "loop.sqlite3")

    result = validate_semrush(store, FakeSemrush(), "grade calculator", "global")

    payload = store.validation("grade calculator", "global", "semrush")
    assert result.decision == "保留"
    assert payload["intent"] == "Commercial"
    assert payload["kd"] == 49
    assert payload["serp_features"] == 2


def test_validate_semrush_intent_rejects_navigation_keywords(tmp_path) -> None:
    store = KeywordStore(tmp_path / "loop.sqlite3")

    decision = validate_semrush_intent(store, "kling ai", "global", {"intent": "Navigational"})

    assert decision.decision == "淘汰"
    assert store.validation("kling ai", "global", "intent_gate")["decision"] == "淘汰"


def test_remaining_terms_uses_the_next_unprocessed_source_offset(tmp_path) -> None:
    store = KeywordStore(tmp_path / "loop.sqlite3")
    store.set_state("discovery_only:root:offset", "1")

    assert remaining_terms(store, "root", ["first", "second"]) == ["second"]


def test_semrush_target_counts_only_approved_keywords() -> None:
    totals = {"semrush_passed": 499, "semrush_rejected": 300, "semrush_checked": 799}

    assert semrush_target_reached(totals, 500) is False

    totals["semrush_passed"] += 1
    assert semrush_target_reached(totals, 500) is True


def test_new_only_discovery_starts_its_target_from_zero_existing_approvals() -> None:
    assert initial_discovery_totals(239, new_only=False).semrush_passed == 239
    assert initial_discovery_totals(239, new_only=True).semrush_passed == 0


def test_store_returns_only_existing_keywords_that_passed_both_gates(tmp_path) -> None:
    store = KeywordStore(tmp_path / "loop.sqlite3")
    store.record(KeywordObservation("good calculator", 30_000, 60, "Commercial", "calc", "Phrase", "global", "now"))
    store.record(KeywordObservation("weak calculator", 9_000, 31, "Commercial", "calc", "Phrase", "global", "now"))
    store.record_validation("good calculator", "global", "semrush", {"gate_decision": "保留"})
    store.record_validation("weak calculator", "global", "semrush", {"gate_decision": "保留"})

    assert store.approved_discovery_keywords() == {("good calculator", "global")}


def test_source_acceptance_assigns_each_keyword_to_one_quota_source(tmp_path) -> None:
    store = KeywordStore(tmp_path / "loop.sqlite3")

    assert store.record_source_acceptance("stripe", "good calculator", "global") is True
    assert store.record_source_acceptance("toolify", "good calculator", "global") is False
    assert store.source_accepted_count("stripe") == 1
    assert store.source_accepted_count("toolify") == 0
