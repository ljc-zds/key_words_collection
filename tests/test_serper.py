from keyword_loop.core.clients.serper import _text_list


def test_text_list_extracts_serper_paa_and_related_queries() -> None:
    assert _text_list([{"question": "What is a calculator?"}, {"query": "calculator free"}, "calculator tool", {}]) == [
        "What is a calculator?", "calculator free", "calculator tool"
    ]
