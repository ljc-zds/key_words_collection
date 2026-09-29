from keyword_loop.core.data.store import KeywordStore


def test_store_records_collection_failure_with_reason(tmp_path) -> None:
    store = KeywordStore(tmp_path / "loop.sqlite3")
    store.record_failure("advisor", "grid columns=0")
    assert store.failures() == [("advisor", "grid columns=0")]
