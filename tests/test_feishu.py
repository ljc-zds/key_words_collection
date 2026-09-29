import keyword_loop.core.publishing.feishu as feishu
from keyword_loop.core.publishing.feishu import build_sheet_values, parse_ranked_products, parse_sheet_id, parse_wiki_url


def test_parse_sheet_id_reads_explicit_worksheet() -> None:
    assert parse_sheet_id("https://my.feishu.cn/wiki/abc?from=copy&sheet=e2e503") == "e2e503"


def test_load_roots_can_preserve_feishu_row_order(monkeypatch) -> None:
    monkeypatch.setattr(feishu, "tenant_access_token", lambda env: "token")
    monkeypatch.setattr(feishu, "resolve_wiki_node", lambda url, token: {"obj_type": "sheet", "obj_token": "spreadsheet"})
    monkeypatch.setattr(feishu, "request_json", lambda url, **kwargs: {"data": {"sheets": [{"sheet_id": "sheet"}]}} if url.endswith("/sheets/query") else {"data": {"valueRange": {"values": [["英文关键词"], ["zeta"], ["alpha"], ["zeta"]]}}})

    assert feishu.load_roots_from_wiki("https://my.feishu.cn/wiki/abc", preserve_order=True) == ["zeta", "alpha"]
from keyword_loop.core.data.models import KeywordCandidate


def candidate() -> KeywordCandidate:
    return KeywordCandidate("agent crm", 31_000, 57, "COMMERCIAL", "global", ("agent",), ("phrase_match",), "now")


def test_build_sheet_values_creates_header_and_candidate_row() -> None:
    validations = {"agent crm": {"semrush": {"volume": 13000, "kd": 39, "cpc": 1.2, "intent": "Commercial", "competitive_density": 0.09, "serp_features": 4, "results": "接口未提供", "gate_decision": "保留", "gate_reason": "KD通过"}, "intent_gate": {"decision": "保留", "reason": "工具意图"}, "ai_screen": {"decision": "仅注释", "score": 82}, "serper": {"strong_site_count": 2}}}
    values = build_sheet_values([candidate()], validations=validations)
    assert values[0][0] == "关键词"
    assert values[0][10:13] == ["关键词含义", "搜索意图解读", "订阅机会"]
    assert values[1][0] == "agent crm"
    assert values[0][23:25] == ["Semrush搜索量", "Semrush KD"]
    assert values[1][23:25] == ["13000", "39"]
    assert values[1][25:29] == ["1.2", "Commercial", "0.09", "4"]
    assert "AI二筛结论" not in values[0]
    assert "结果数" not in values[0]
    assert values[0][40:44] == ["Semrush筛选", "Semrush筛选原因", "意图筛选", "意图筛选说明"]
    assert values[1][40:44] == ["保留", "KD通过", "保留", "工具意图"]
    assert values[1][37] == "本次SERP未返回 PAA"


def test_build_sheet_values_marks_missing_generic_score_as_unavailable() -> None:
    values = build_sheet_values([candidate()], gofei_payloads={"agent crm": {"genericScore": None}})

    assert values[1][13] == "接口未返回"


def test_build_sheet_values_marks_missing_semrush_exact_keyword() -> None:
    values = build_sheet_values([candidate()], validations={
        "agent crm": {"semrush": {"exact_keyword_found": False}},
    })

    assert values[1][23:29] == ["Semrush未返回精确关键词"] * 6


def test_parse_wiki_url_extracts_token_without_network() -> None:
    assert parse_wiki_url("https://my.feishu.cn/wiki/VHnXwGzGQiGeUkkgj4tc4kpLnbh") == "VHnXwGzGQiGeUkkgj4tc4kpLnbh"


def test_parse_ranked_products_reads_product_name_and_detail_link() -> None:
    rows = [
        ["排名", "产品", "月访问量", "月增长", "增长率", "Toolify详情页"],
        ["1", "ChatGPT", "5.5B", "68.1M", "1.27%", [{"link": "https://www.toolify.ai/tool/chatgpt-4"}]],
    ]

    products = parse_ranked_products(rows, "https://www.toolify.ai/Best-trending-AI-Tools")

    assert len(products) == 1
    assert products[0].name == "ChatGPT"
    assert products[0].detail_url == "https://www.toolify.ai/tool/chatgpt-4"


def test_publish_sheet_syncs_the_full_header(monkeypatch) -> None:
    writes = []
    write_methods = []

    def fake_request(url, *, method, payload=None, token=None):
        if method == "GET":
            return {"data": {"valueRange": {"values": [["keyword"], ["agent crm"]]}}}
        write_methods.append(method)
        writes.extend(payload["valueRanges"])
        return {}

    monkeypatch.setattr(feishu, "request_json", fake_request)

    feishu.publish_sheet("spreadsheet", "e2e503", [candidate()], "token")

    header_write = next(item for item in writes if item["range"] == "e2e503!A1:AR1")
    assert len(header_write["values"][0]) == 44
    assert header_write["values"][0][0] == "关键词"
    assert header_write["values"][0][-1] == "意图筛选说明"
    assert write_methods == ["POST"]


def test_publish_sheet_appends_after_the_last_nonempty_keyword(monkeypatch) -> None:
    writes = []

    def fake_request(url, *, method, payload=None, token=None):
        if method == "GET":
            return {"data": {"valueRange": {"values": [["关键词"], [], [], []]}}}
        writes.extend(payload["valueRanges"])
        return {}

    monkeypatch.setattr(feishu, "request_json", fake_request)

    feishu.publish_sheet("spreadsheet", "e2e503", [candidate()], "token")

    assert any(item["range"] == "e2e503!A2:AR2" for item in writes)
