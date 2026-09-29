from keyword_loop.core.screening.explanation import explain_candidate
from keyword_loop.core.data.models import KeywordCandidate
import pytest


def test_explanation_answers_definition_intent_and_subscription_value() -> None:
    candidate = KeywordCandidate("agent crm", 31_000, 57, "COMMERCIAL", "global", ("agent",), ("phrase_match",), "now")
    text = explain_candidate(candidate)
    assert "是什么：" in text and "搜索意图：" in text and "商业价值：" in text and "商业型" in text


def test_explanation_maps_similarweb_info_to_informational_intent() -> None:
    candidate = KeywordCandidate("action movies", 50_000, 29, "INFO", "global", ("movie",), ("phrase_match",), "now")
    text = explain_candidate(candidate)
    assert "搜索意图：信息型" in text
    assert "用户正在寻找相关内容、答案或资源" in text


@pytest.mark.parametrize(
    ("raw_intent", "expected_label"),
    [("COMM", "商业型"), ("TRANS", "交易型"), ("NAV", "导航型"), ("LOCAL", "本地型")],
)
def test_explanation_maps_all_remaining_similarweb_intent_values(raw_intent: str, expected_label: str) -> None:
    candidate = KeywordCandidate("example keyword", 50_000, 29, raw_intent, "global", ("example",), ("phrase_match",), "now")
    assert f"搜索意图：{expected_label}" in explain_candidate(candidate)
