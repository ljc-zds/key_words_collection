from keyword_loop.core.data.checkpoint import CollectionCheckpoint
from keyword_loop.core.data.store import KeywordStore


def test_collection_checkpoint_survives_a_new_daily_run(tmp_path) -> None:
    store = KeywordStore(tmp_path / "loop.sqlite3")
    checkpoint = CollectionCheckpoint(
        source="toolify",
        period="2026-09",
        source_position=17,
        product="Higgsfield",
        root="ai video generator",
        similarweb_page=3,
    )

    store.save_collection_checkpoint(checkpoint)
    store.start_daily_run("2026-09-02", target=300)

    assert store.collection_checkpoint("toolify") == checkpoint


def test_collection_checkpoint_replaces_only_the_same_source(tmp_path) -> None:
    store = KeywordStore(tmp_path / "loop.sqlite3")
    store.save_collection_checkpoint(CollectionCheckpoint("stripe", "2026-09", 8, "ElevenLabs", "text to speech", 2))
    toolify = CollectionCheckpoint("toolify", "2026-09", 17, "Higgsfield", "ai video generator", 3)
    store.save_collection_checkpoint(toolify)

    assert store.collection_checkpoint("toolify") == toolify
    assert store.collection_checkpoint("stripe").root == "text to speech"


def test_unresolved_semrush_queue_survives_the_next_daily_run(tmp_path) -> None:
    store = KeywordStore(tmp_path / "loop.sqlite3")
    store.start_daily_run("2026-09-01", target=300)
    store.queue_daily_keyword("2026-09-01", "png converter", "global", "root")
    store.start_daily_run("2026-09-02", target=300)

    assert store.unresolved_semrush_keywords() == [("2026-09-01", "png converter", "global", "root")]
