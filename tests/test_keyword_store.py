from keyword_loop.core.data.models import KeywordObservation
from keyword_loop.core.data.store import KeywordStore


def observation(keyword: str, volume: int, kd: int, root: str) -> KeywordObservation:
    return KeywordObservation(keyword, volume, kd, "COMMERCIAL", root, "phrase_match", "global", "2026-08-24T08:00:00+00:00")


def test_daily_candidates_merge_provenance_and_enforce_thresholds(tmp_path) -> None:
    store = KeywordStore(tmp_path / "loop.sqlite3")
    store.record(observation("agent crm", 31_000, 57, "agent"))
    store.record(observation("agent crm", 31_000, 57, "crm"))
    store.record(observation("agent jobs", 30_000, 61, "agent"))

    candidates = store.daily_candidates(minimum_volume=30_000, maximum_kd=60, limit=300)

    assert [(item.keyword, item.source_roots) for item in candidates] == [("agent crm", ("agent", "crm"))]


def test_record_validation_results_upserts_each_stage(tmp_path) -> None:
    store = KeywordStore(tmp_path / "loop.sqlite3")
    store.record_validation("agent crm", "global", "semrush", {"volume": 12000, "kd": 41})
    store.record_validation("agent crm", "global", "semrush", {"volume": 13000, "kd": 39})
    store.record_validation("agent crm", "global", "ai_screen", {"decision": "保留", "score": 82})

    assert store.validation("agent crm", "global", "semrush") == {"volume": 13000, "kd": 39}
    assert store.validation("agent crm", "global", "ai_screen")["decision"] == "保留"
