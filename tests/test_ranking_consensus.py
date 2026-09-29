from keyword_loop.core.data.store import KeywordStore


def test_ranking_consensus_counts_distinct_ranked_products(tmp_path) -> None:
    store = KeywordStore(tmp_path / "rankings.sqlite3")
    store.record_ranking_keyword("ai video generator", "tripo.ai")
    store.record_ranking_keyword("ai video generator", "higgsfield.ai")
    store.record_ranking_keyword("ai video generator", "tripo.ai")
    assert store.ranking_consensus("ai video generator") == 2
