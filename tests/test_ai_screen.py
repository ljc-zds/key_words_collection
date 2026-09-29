import pytest

from keyword_loop.core.clients.ai_screen import parse_response_api_payload, parse_screen_response


def test_parse_screen_response_rejects_missing_required_fields() -> None:
    with pytest.raises(ValueError, match="missing AI screen field"):
        parse_screen_response('{"score": 80}')


def test_parse_screen_response_reads_final_decision_fields() -> None:
    result = parse_screen_response(
        '{"decision":"保留","score":80,"tool_page_fit":"high","exact_match_domain_fit":"medium",'
        '"recommended_page_type":"calculator","monetization":"广告","reason":"clear utility intent"}'
    )

    assert result["decision"] == "保留"
    assert result["recommended_page_type"] == "calculator"


def test_parse_response_api_payload_reads_responses_wire_text() -> None:
    payload = {
        "output": [{"content": [{"type": "output_text", "text": '{"decision":"保留","score":76,"tool_page_fit":"high","exact_match_domain_fit":"low","recommended_page_type":"converter","monetization":"广告","reason":"specific conversion demand"}'}]}]
    }

    assert parse_response_api_payload(payload)["score"] == 76
