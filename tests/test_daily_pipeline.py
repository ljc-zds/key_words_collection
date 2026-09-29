from datetime import date

from keyword_loop.core.data.models import KeywordObservation
from keyword_loop.core.screening.pipeline import SourceAllocator
from keyword_loop.core.screening.screening import volume_kd_gate
from keyword_loop.core.data.store import KeywordStore
from keyword_loop.workflows.validation_publish import ValidationTotals


def test_validation_totals_tracks_publication_separately() -> None:
    totals = ValidationTotals(queued=4, accepted=2, published=True)

    assert totals.to_dict() == {"queued": 4, "accepted": 2, "published": True}


def test_source_allocator_moves_exhausted_revenue_quota_to_roots() -> None:
    allocator = SourceAllocator({"stripe": 100, "toolify": 100, "root": 100})

    assert allocator.next_source({"stripe": 100, "toolify": 40, "root": 100}, set()) == "toolify"
    assert allocator.next_source({"stripe": 100, "toolify": 100, "root": 100}, {"stripe", "toolify"}) == "root"


def test_volume_kd_gate_uses_tighter_kd_for_lower_volume() -> None:
    assert volume_kd_gate(30_000, 60).decision == "保留"
    assert volume_kd_gate(10_000, 45).decision == "保留"
    assert volume_kd_gate(5_000, 30).decision == "保留"
    assert volume_kd_gate(9_999, 31).decision == "淘汰"
    assert volume_kd_gate(4_999, 1).decision == "淘汰"


def test_daily_run_counts_only_keywords_passing_semrush_and_intent(tmp_path) -> None:
    store = KeywordStore(tmp_path / "loop.sqlite3")
    run_date = date(2026, 9, 1)
    store.start_daily_run(run_date, target=3)
    store.queue_daily_keyword(run_date, "agent crm", "global", "stripe")
    store.queue_daily_keyword(run_date, "air fryer", "global", "toolify")

    store.record_daily_gate(run_date, "agent crm", "global", "semrush", "保留", "KD 35")
    store.record_daily_gate(run_date, "agent crm", "global", "intent", "保留", "工具意图")
    store.record_daily_gate(run_date, "air fryer", "global", "semrush", "保留", "KD 55")
    store.record_daily_gate(run_date, "air fryer", "global", "intent", "淘汰", "实体商品主词")

    status = store.daily_run_status(run_date)
    assert status.accepted == 1
    assert status.rejected == 1
    assert status.remaining == 2


def test_daily_keyword_queue_is_resumable_and_deduplicated(tmp_path) -> None:
    store = KeywordStore(tmp_path / "loop.sqlite3")
    run_date = date(2026, 9, 1)
    store.start_daily_run(run_date, target=300)

    assert store.queue_daily_keyword(run_date, "agent crm", "global", "stripe") is True
    assert store.queue_daily_keyword(run_date, "agent crm", "global", "root") is False
    assert store.daily_run_status(run_date).queued == 1


def test_daily_accepted_candidates_excludes_failed_hard_gates(tmp_path) -> None:
    store = KeywordStore(tmp_path / "loop.sqlite3")
    run_date = date(2026, 9, 1)
    store.start_daily_run(run_date)
    store.record(KeywordObservation("trade analyzer", 165_000, 34, "COMMERCIAL", "trade", "phrase_match", "global", "now"))
    store.record(KeywordObservation("animeflv", 246_000, 32, "INFORMATIONAL", "anime", "phrase_match", "global", "now"))
    for keyword in ("trade analyzer", "animeflv"):
        store.queue_daily_keyword(run_date, keyword, "global", "root")
        store.record_daily_gate(run_date, keyword, "global", "semrush", "保留", "KD 通过")
    store.record_daily_gate(run_date, "trade analyzer", "global", "intent", "保留", "工具意图")
    store.record_daily_gate(run_date, "animeflv", "global", "intent", "淘汰", "影视导航")
    store.record_validation("trade analyzer", "global", "serper", {"organic": []})
    store.record_validation("trade analyzer", "global", "ai_screen", {"decision": "保留"})
    store.record_enrichment("trade analyzer", "global", {"score": 20}, ("含义", "意图", "订阅"), "now")

    assert [item.keyword for item in store.daily_accepted_candidates(run_date)] == ["trade analyzer"]


def test_replenishment_starts_before_an_entire_batch_finishes() -> None:
    allocator = SourceAllocator({"stripe": 100, "toolify": 100, "root": 100})

    assert allocator.replenishment_needed(accepted_total=18, queued_pending=0, target=300)
    assert not allocator.replenishment_needed(accepted_total=300, queued_pending=0, target=300)
