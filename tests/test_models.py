from product_hunt.aitdk.data.models import CollectionRecord


def test_record_keeps_allowed_traffic_fields_only() -> None:
    record = CollectionRecord.from_plugin_data(
        "deno.com",
        {"overview": {"visits": "318295"}, "topKeywords": [{"name": "deno"}]},
    )
    assert record.domain == "deno.com"
    assert record.overview == {"visits": "318295"}
    assert record.top_keywords == [{"name": "deno"}]
