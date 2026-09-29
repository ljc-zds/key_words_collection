from backfill_existing_feishu import assess_with_heartbeat, compact_ai_item


class BatchClient:
    def assess_batch(self, items, *, stage):
        assert stage == "final"
        return [{"decision": "保留"} for _ in items]


def test_assess_with_heartbeat_returns_batch_results() -> None:
    assert assess_with_heartbeat(BatchClient(), [{"keyword": "calculator"}]) == [{"decision": "保留"}]


def test_compact_ai_item_excludes_large_raw_serp_and_gofei_fields() -> None:
    item = compact_ai_item(
        "calculator",
        {"volume": 30_000, "kd": 20, "ignored": "x"},
        {"organic": [{"position": 1, "title": "Result", "link": "https://example.com/path", "snippet": "ignored"}]},
        {"score": 22, "reasons": ["one", "two", "three", "four"], "details": [{"domain": "ignored"}]},
    )

    assert item["semrush"] == {"volume": 30_000, "kd": 20, "cpc": None, "intent": None, "competitive_density": None, "serp_features": None, "gate_decision": None}
    assert item["serp"]["top_results"] == [{"position": 1, "title": "Result", "domain": "example.com"}]
    assert item["gofei"]["reasons"] == ["one", "two", "three"]
