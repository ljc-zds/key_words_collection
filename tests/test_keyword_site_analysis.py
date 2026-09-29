import json
import sqlite3

from keyword_site_analysis import (
    assess_keyword,
    cluster_key,
    explain_keyword,
    load_local_records,
    merge_keyword_records,
    normalize_keyword,
    priority_for_score,
)


def test_loader_uses_filtered_independent_candidates_only(tmp_path):
    database = tmp_path / "keywords.sqlite3"
    connection = sqlite3.connect(database)
    connection.executescript("""
        CREATE TABLE keywords (
            keyword TEXT NOT NULL, market TEXT NOT NULL, volume INTEGER, kd INTEGER,
            intent TEXT, retrieved_at TEXT NOT NULL, PRIMARY KEY (keyword, market)
        );
        CREATE TABLE provenance (
            keyword TEXT NOT NULL, market TEXT NOT NULL, root TEXT NOT NULL,
            result_type TEXT NOT NULL, PRIMARY KEY (keyword, market, root, result_type)
        );
        CREATE TABLE keyword_validation (
            keyword TEXT NOT NULL, market TEXT NOT NULL, stage TEXT NOT NULL,
            payload_json TEXT NOT NULL, retrieved_at TEXT NOT NULL,
            PRIMARY KEY (keyword, market, stage)
        );
        CREATE TABLE semrush_related_candidates (
            keyword TEXT NOT NULL, database_name TEXT NOT NULL, parent_keyword TEXT NOT NULL,
            payload_json TEXT NOT NULL, retrieved_at TEXT NOT NULL,
            PRIMARY KEY (keyword, database_name, parent_keyword)
        );
        CREATE TABLE independent_candidates (
            keyword TEXT NOT NULL, provider TEXT NOT NULL, market TEXT NOT NULL,
            payload_json TEXT NOT NULL, accepted_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY(keyword, provider, market)
        );
        CREATE TABLE independent_provenance (
            keyword TEXT NOT NULL, provider TEXT NOT NULL, market TEXT NOT NULL,
            source TEXT NOT NULL, seed TEXT NOT NULL,
            PRIMARY KEY(keyword, provider, market, source, seed)
        );
    """)
    connection.execute(
        "INSERT INTO keywords VALUES (?,?,?,?,?,?)",
        ("raw should not load", "global", 100, 99, "INFO", "2026-09-01"),
    )
    similarweb = {
        "keyword": "filtered calculator", "volume": 12000, "kd": 20,
        "intent": "Informational", "root": "calculator", "result_type": "Broad",
        "retrieved_at": "2026-09-10T01:00:00+00:00",
    }
    semrush = {
        "keyword": "filtered calculator", "volume": 9000, "kd": 24, "cpc": 1.5,
        "intent": "Commercial", "retrieved_at": "2026-09-10T02:00:00+00:00",
    }
    connection.executemany(
        "INSERT INTO independent_candidates(keyword,provider,market,payload_json) VALUES (?,?,?,?)",
        [
            ("filtered calculator", "similarweb", "global", json.dumps(similarweb)),
            ("filtered calculator", "semrush", "us", json.dumps(semrush)),
        ],
    )
    connection.executemany(
        "INSERT INTO independent_provenance VALUES (?,?,?,?,?)",
        [
            ("filtered calculator", "similarweb", "global", "root", "calculator"),
            ("filtered calculator", "semrush", "us", "root", "seed phrase"),
        ],
    )
    connection.commit()
    connection.close()

    records = load_local_records(database)

    assert len(records) == 2
    assert {record["keyword"] for record in records} == {"filtered calculator"}
    similarweb_record = next(record for record in records if record["provider"] == "similarweb")
    semrush_record = next(record for record in records if record["provider"] == "semrush")
    assert similarweb_record["roots"] == ["calculator"]
    assert semrush_record["parents"] == ["seed phrase"]


def test_normalize_keyword_collapses_space_and_case():
    assert normalize_keyword("  Mortgage   Calculator ") == "mortgage calculator"


def test_merge_keeps_provider_metrics_separate():
    rows = [
        {"keyword": "svg converter", "provider": "similarweb", "volume": 42000, "kd": 19},
        {"keyword": "SVG Converter", "provider": "semrush", "volume": 18100, "kd": 24, "cpc": 1.8},
    ]
    merged = merge_keyword_records(rows)
    assert len(merged) == 1
    assert merged[0]["similarweb_volume"] == 42000
    assert merged[0]["semrush_volume"] == 18100
    assert merged[0]["semrush_cpc"] == 1.8


def test_low_volume_is_rejected():
    result = assess_keyword({"keyword": "tiny niche calculator", "similarweb_volume": 900, "similarweb_kd": 4})
    assert result["included"] is False
    assert "5,000" in result["decision_reason"]


def test_navigational_brand_is_rejected():
    result = assess_keyword({
        "keyword": "funimation",
        "semrush_volume": 33100,
        "semrush_kd": 51,
        "semrush_cpc": 1.41,
        "semrush_intent": "Navigational",
    })
    assert result["included"] is False
    assert result["exclusion_code"] == "navigational"


def test_piracy_query_is_rejected():
    result = assess_keyword({"keyword": "movie watch online free", "similarweb_volume": 90000, "similarweb_kd": 10})
    assert result["included"] is False
    assert result["exclusion_code"] == "policy_risk"


def test_clear_tool_query_is_included_and_classified():
    result = assess_keyword({
        "keyword": "mortgage payment calculator",
        "similarweb_volume": 110000,
        "similarweb_kd": 22,
        "similarweb_intent": "Informational",
        "semrush_volume": 90500,
        "semrush_kd": 25,
        "semrush_cpc": 3.2,
        "semrush_intent": "Commercial",
    })
    assert result["included"] is True
    assert result["site_type"] == "计算器"
    assert result["priority"] in {"P0", "P1"}
    assert result["serp_status"] == "未进行实时 SERP 验证"


def test_semrush_only_converter_can_qualify():
    result = assess_keyword({
        "keyword": "webp to png converter",
        "semrush_volume": 12100,
        "semrush_kd": 21,
        "semrush_cpc": 0.8,
        "semrush_intent": "Transactional",
    })
    assert result["included"] is True
    assert result["site_type"] == "转换工具"


def test_cluster_key_removes_product_modifier():
    assert cluster_key("mortgage payment calculator", "计算器") == "mortgage payment"


def test_priority_thresholds():
    assert priority_for_score(80) == "P0"
    assert priority_for_score(70) == "P1"
    assert priority_for_score(60) == "P2"
    assert priority_for_score(59.9) == "淘汰"


def test_signal_matching_does_not_use_partial_words():
    for keyword in ("checkers liquor", "checkered", "iconic football celebrations", "polovne motorne testere"):
        result = assess_keyword({"keyword": keyword, "similarweb_volume": 80000, "similarweb_kd": 10})
        assert result["included"] is False, keyword
        assert result["exclusion_code"] == "no_site_fit", keyword


def test_platform_media_conversion_is_rejected():
    result = assess_keyword({"keyword": "youtube mp4 converter", "similarweb_volume": 61000, "similarweb_kd": 34})
    assert result["included"] is False
    assert result["exclusion_code"] == "policy_risk"


def test_misspelled_platform_media_conversion_is_rejected():
    for keyword in (
        "yotube to mp3", "youtbe to mp3", "youtibe to mp3",
        "youtub to mp3", "yputube to mp3", "yourube to mp3", "link to mp3",
    ):
        result = assess_keyword({"keyword": keyword, "semrush_volume": 12100, "semrush_kd": 12})
        assert result["included"] is False, keyword
        assert result["exclusion_code"] == "policy_risk", keyword


def test_how_much_content_is_not_automatically_a_calculator():
    result = assess_keyword({"keyword": "how much does it cost to freeze eggs", "semrush_volume": 5400, "semrush_kd": 16})
    assert result["included"] is False
    assert result["exclusion_code"] == "question_page"


def test_jobs_and_physical_testers_are_not_online_tools():
    for keyword in ("game tester jobs", "battery tester", "diamond tester", "xrf analyzer"):
        result = assess_keyword({"keyword": keyword, "similarweb_volume": 30000, "similarweb_kd": 10})
        assert result["included"] is False, keyword


def test_watermark_removal_is_rejected_as_policy_risk():
    result = assess_keyword({"keyword": "sora 2 watermark remover", "similarweb_volume": 30000, "similarweb_kd": 20})
    assert result["included"] is False
    assert result["exclusion_code"] == "policy_risk"


def test_generic_how_to_and_meaning_queries_are_not_standalone_site_opportunities():
    for keyword in ("how to reset airpods", "what is a rheumatologist", "emergent meaning"):
        result = assess_keyword({"keyword": keyword, "similarweb_volume": 50000, "similarweb_kd": 10})
        assert result["included"] is False, keyword


def test_explicit_reference_resource_can_qualify():
    result = assess_keyword({"keyword": "fantasy football cheat sheet", "similarweb_volume": 28000, "similarweb_kd": 21})
    assert result["included"] is True
    assert result["site_type"] == "教程与资料站"


def test_unclear_or_branded_software_tool_queries_are_rejected():
    for keyword in ("the analyzer twitter", "dell optimizer", "tivoli workload scheduler", "perfumes tester", "tester"):
        result = assess_keyword({"keyword": keyword, "similarweb_volume": 50000, "similarweb_kd": 10})
        assert result["included"] is False, keyword


def test_yt_media_conversion_is_rejected():
    result = assess_keyword({"keyword": "yt to mp3 converter", "similarweb_volume": 70000, "similarweb_kd": 20})
    assert result["included"] is False
    assert result["exclusion_code"] == "policy_risk"


def test_sports_match_vs_query_is_not_a_comparison_site():
    for keyword in ("arsenal vs chelsea", "ind vs sl"):
        result = assess_keyword({"keyword": keyword, "semrush_volume": 80000, "semrush_kd": 20, "semrush_cpc": 1})
        assert result["included"] is False, keyword


def test_physical_product_maker_is_not_a_generator_site():
    result = assess_keyword({"keyword": "best drip coffee maker", "semrush_volume": 90000, "semrush_kd": 25})
    assert result["included"] is False
    assert result["exclusion_code"] == "physical_product"


def test_interrogative_product_name_is_not_mistaken_for_tool():
    result = assess_keyword({"keyword": "what does performance planner automatically do", "similarweb_volume": 9000, "similarweb_kd": 1})
    assert result["included"] is False


def test_ambiguous_short_acronym_needs_cross_source_support():
    result = assess_keyword({"keyword": "fd calculator", "similarweb_volume": 365600, "similarweb_kd": 13})
    assert result["included"] is False
    assert result["exclusion_code"] == "ambiguous_acronym"


def test_known_acronym_calculator_can_qualify_from_one_source():
    result = assess_keyword({"keyword": "cpm calculator", "similarweb_volume": 99000, "similarweb_kd": 20})
    assert result["included"] is True


def test_generic_vs_and_media_reviews_are_not_site_opportunities():
    for keyword in ("psychopath vs sociopath", "portrait vs landscape", "one battle after another reviews", "weapons review"):
        result = assess_keyword({"keyword": keyword, "semrush_volume": 50000, "semrush_kd": 20, "semrush_cpc": 1})
        assert result["included"] is False, keyword


def test_saas_vs_query_remains_eligible():
    result = assess_keyword({"keyword": "zapier vs n8n", "semrush_volume": 12000, "semrush_kd": 25, "semrush_cpc": 3})
    assert result["included"] is True
    assert result["site_type"] == "比较与评测站"


def test_generic_trade_tool_without_domain_is_rejected():
    for keyword in ("trade analyzer", "trade calculator"):
        result = assess_keyword({"keyword": keyword, "similarweb_volume": 120000, "similarweb_kd": 20})
        assert result["included"] is False, keyword


def test_related_format_converters_share_projects():
    assert cluster_key("png to pdf", "转换工具") == "image to document"
    assert cluster_key("jpg to pdf", "转换工具") == "image to document"
    assert cluster_key("pdf to png", "转换工具") == "document to image"


def test_related_content_resources_share_projects():
    assert cluster_key("cute nail ideas", "教程与资料站") == "nail ideas"
    assert cluster_key("summer nail ideas", "教程与资料站") == "nail ideas"


def test_known_product_and_brand_asset_false_positives_are_rejected():
    for keyword in (
        "espresso maker", "pdf24 creator", "roblox creator dashboard", "creator dashboard",
        "google fitbit air fitness tracker", "pokemon wallpaper", "cornell scheduler",
    ):
        result = assess_keyword({"keyword": keyword, "similarweb_volume": 50000, "similarweb_kd": 20})
        assert result["included"] is False, keyword


def test_non_english_converter_phrase_is_rejected_for_english_scope():
    result = assess_keyword({"keyword": "converter pdf em jpg", "semrush_volume": 90000, "semrush_kd": 20})
    assert result["included"] is False
    assert result["exclusion_code"] == "non_english"


def test_physical_makers_and_generators_are_not_digital_products():
    for keyword in (
        "waffle maker", "bread maker", "ninja ice cream maker", "roti maker machine",
        "diesel generator", "solar generator", "function generator",
    ):
        result = assess_keyword({"keyword": keyword, "similarweb_volume": 100000, "similarweb_kd": 10})
        assert result["included"] is False, keyword
        assert result["exclusion_code"] == "physical_product", keyword


def test_generator_sales_and_service_queries_are_not_digital_generators():
    for keyword in (
        "gas generator", "generator repair", "generator installation",
        "generac generator cost", "whole house generator cost",
        "generator transfer switch", "propane generator", "rv generator",
    ):
        result = assess_keyword({"keyword": keyword, "similarweb_volume": 30000, "similarweb_kd": 20})
        assert result["included"] is False, keyword
        assert result["exclusion_code"] == "physical_product", keyword


def test_physical_and_entertainment_trackers_are_not_online_product_opportunities():
    for keyword in (
        "mini gps tracker", "bike gps tracker", "casio step tracker",
        "tracker season 4", "tracker episodes", "chevy tracker",
    ):
        result = assess_keyword({"keyword": keyword, "similarweb_volume": 30000, "similarweb_kd": 20})
        assert result["included"] is False, keyword
        assert result["exclusion_code"] in {"physical_product", "branded_product"}, keyword


def test_india_specific_queries_are_excluded_from_target_market():
    for keyword in (
        "step up sip calculator", "ppf calculator", "bike emi calculator",
        "sukanya samriddhi yojana calculator", "gst calculator",
        "cbse sample paper", "best bike under 1 lakh",
    ):
        result = assess_keyword({"keyword": keyword, "similarweb_volume": 50000, "similarweb_kd": 20})
        assert result["included"] is False, keyword
        assert result["exclusion_code"] == "india_market", keyword


def test_high_risk_brand_and_copyright_queries_are_rejected():
    for keyword in (
        "ramsey investment calculator", "canva pdf editor", "freepik ai image generator",
        "hello kitty coloring page", "ti 84 calculator online", "rapidgator premium link generator",
        "nsfw prompt generator", "credit card generator",
    ):
        result = assess_keyword({"keyword": keyword, "similarweb_volume": 30000, "similarweb_kd": 20})
        assert result["included"] is False, keyword
        assert result["exclusion_code"] in {"branded_product", "policy_risk"}, keyword


def test_digital_makers_and_generators_remain_eligible():
    for keyword in ("logo maker", "meme maker", "username generator", "citation generator"):
        result = assess_keyword({"keyword": keyword, "similarweb_volume": 30000, "similarweb_kd": 20})
        assert result["included"] is True, keyword


def test_physical_converter_products_are_not_conversion_tools():
    for keyword in (
        "catalytic converter", "rust converter", "buck converter",
        "torque converter", "standing desk converter", "type c to usb converter",
    ):
        result = assess_keyword({"keyword": keyword, "similarweb_volume": 50000, "similarweb_kd": 20})
        assert result["included"] is False, keyword
        assert result["exclusion_code"] == "physical_product", keyword


def test_file_and_unit_converters_remain_eligible():
    for keyword in ("convert heic to png", "convert mm to inches", "roman numeral converter"):
        result = assess_keyword({"keyword": keyword, "similarweb_volume": 30000, "similarweb_kd": 20})
        assert result["included"] is True, keyword


def test_names_containing_creator_are_not_automatically_generators():
    for keyword in ("tyler the creator tour", "osmo pocket 3 creator combo", "lego creator"):
        result = assess_keyword({"keyword": keyword, "similarweb_volume": 30000, "similarweb_kd": 20})
        assert result["included"] is False, keyword


def test_non_ascii_phrase_is_rejected_for_english_scope():
    result = assess_keyword({"keyword": "font chữ đẹp", "similarweb_volume": 100000, "similarweb_kd": 10})
    assert result["included"] is False
    assert result["exclusion_code"] == "non_english"


def test_music_platform_conversion_is_rejected():
    for keyword in ("soundcloud to wav", "spotify to mp3 converter", "apple music to mp3"):
        result = assess_keyword({"keyword": keyword, "similarweb_volume": 30000, "similarweb_kd": 20})
        assert result["included"] is False, keyword
        assert result["exclusion_code"] == "policy_risk", keyword


def test_branded_or_purchase_calculator_is_not_an_online_calculator():
    for keyword in ("casio scientific calculator", "calculator price"):
        result = assess_keyword({"keyword": keyword, "similarweb_volume": 30000, "similarweb_kd": 20})
        assert result["included"] is False, keyword
        assert result["exclusion_code"] == "physical_product", keyword


def test_betting_calculator_is_rejected_as_policy_risk():
    result = assess_keyword({"keyword": "lucky 63 betmentor calculator", "similarweb_volume": 30000, "similarweb_kd": 20})
    assert result["included"] is False
    assert result["exclusion_code"] == "policy_risk"


def test_atar_calculator_gets_domain_specific_use_explanation():
    explanation = explain_keyword("atar calculator", "计算器", "未发现明显硬风险")
    assert "澳大利亚" in explanation
    assert "大学入学排名" in explanation
    assert "输入" in explanation and "输出" in explanation


def test_converter_explanation_describes_file_conversion_workflow():
    explanation = explain_keyword("convert heic to png", "转换工具", "未发现明显硬风险")
    assert "HEIC" in explanation and "PNG" in explanation
    assert "上传" in explanation and "下载" in explanation
