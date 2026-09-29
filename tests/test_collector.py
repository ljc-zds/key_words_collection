from product_hunt.aitdk.cdp.collector import parse_event_stream, parse_traffic_event


def test_parse_traffic_event_returns_sanitized_record() -> None:
    event = {"domain": "deno.com", "data": {"overview": {"visits": "318295"}, "topKeywords": []}}
    assert parse_traffic_event(event).overview["visits"] == "318295"


def test_parse_event_stream_returns_traffic_event_after_other_events() -> None:
    stream = "event: whois\ndata: {\"domain\": \"deno.com\", \"data\": {}}\n\nevent: traffic\ndata: {\"domain\": \"deno.com\", \"data\": {\"overview\": {\"visits\": \"318295\"}}}\n"
    record = parse_event_stream(stream)
    assert record is not None
    assert record.domain == "deno.com"
    assert record.overview["visits"] == "318295"


def test_parse_event_stream_keeps_whois_before_traffic() -> None:
    stream = (
        'event: whois\n'
        'data: {"domain": "deno.com", "data": {"creationDate": "2018-05-08T00:00:00Z"}}\n\n'
        'event: traffic\n'
        'data: {"domain": "deno.com", "data": {"overview": {"visits": "100"}}}\n'
    )

    record = parse_event_stream(stream)

    assert record is not None
    assert record.whois == {"creationDate": "2018-05-08T00:00:00Z"}


def test_parse_event_stream_skips_incomplete_traffic_events() -> None:
    stream = (
        "event: traffic\ndata: {\"status\": \"loading\"}\n\n"
        "event: traffic\ndata: {\"domain\": \"deno.com\", \"data\": "
        "{\"overview\": {\"visits\": \"318295\"}}}\n"
    )
    record = parse_event_stream(stream)
    assert record is not None
    assert record.domain == "deno.com"
