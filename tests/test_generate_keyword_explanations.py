from generate_keyword_explanations import parse_explanations


def test_parse_explanations_accepts_fenced_json_and_preserves_keyword():
    text = '''```json
    {"items":[{"keyword":"atar calculator","explanation":"用于估算澳大利亚大学入学排名。"}]}
    ```'''
    assert parse_explanations(text) == {
        "atar calculator": "用于估算澳大利亚大学入学排名。"
    }


def test_parse_explanations_rejects_empty_or_unrequested_rows():
    text = '{"items":[{"keyword":"a","explanation":""},{"name":"b","text":"x"}]}'
    assert parse_explanations(text) == {}
