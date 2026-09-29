import re

from scripts.build_keyword_site_html import build_html


def sample_result():
    return {
        "metadata": {
            "analysis_generated_at": "2026-09-11T11:34:48+00:00",
            "latest_source_retrieved_at": "2026-09-10T04:48:32+00:00",
            "market_scope": "Similarweb Global / Semrush US",
            "serp_validation": False,
            "method_version": "test-filtered-v2",
        },
        "summary": {
            "raw_unique_keywords": 25_851,
            "accepted_keywords": 1,
            "excluded_keywords": 25_850,
            "project_count": 1,
            "priorities": {"P0": 1, "P1": 0, "P2": 0},
            "site_types": {"计算器": 1},
            "source_statuses": {"双来源": 1},
            "exclusion_counts": {"low_volume": 25_850},
        },
        "projects": [{
            "rank": 1,
            "project_name": "Cpm Calculator",
            "main_keyword": "cpm calculator",
            "site_type": "计算器",
            "priority": "P0",
            "score": 87,
            "keyword_count": 1,
            "main_volume": 99_000,
            "main_kd": 28,
            "monetization": "广告、订阅、付费报告",
            "reason": "单页工具可直接满足需求",
            "risk_notes": "上线前人工复核",
            "keywords": ["cpm calculator"],
        }],
        "keywords": [{
            "rank": 1,
            "project_rank": 1,
            "project_name": "Cpm Calculator",
            "keyword": "cpm calculator",
            "site_type": "计算器",
            "priority": "P0",
            "score": 87,
            "source_status": "双来源",
            "demand_volume": 99_000,
            "conservative_kd": 28,
            "similarweb_volume": 99_000,
            "similarweb_kd": 28,
            "semrush_volume": 27_100,
            "semrush_kd": 27,
            "semrush_cpc": 5.91,
            "decision_reason": "单页工具可直接满足需求",
            "monetization": "广告、订阅、付费报告",
            "risk_notes": "上线前人工复核",
            "serp_status": "未进行实时 SERP 验证",
        }],
    }


def test_html_is_self_contained_and_reconciles_counts():
    page = build_html(sample_result())
    assert "25,851" in page
    assert "1 个合格关键词" in page
    assert "1 个建站项目" in page
    assert "未进行实时 SERP 验证" in page
    assert "cpm calculator" in page
    assert not re.search(r'<(?:script|link)[^>]+(?:src|href)=["\']https?://', page)


def test_html_has_project_and_keyword_exploration_controls():
    page = build_html(sample_result())
    for control_id in (
        "project-search", "project-priority", "project-type",
        "keyword-search", "keyword-priority", "keyword-source", "keyword-type",
    ):
        assert f'id="{control_id}"' in page
    assert 'id="project-table-body"' in page
    assert 'id="keyword-table-body"' in page
    assert 'id="detail-panel"' in page


def test_html_embeds_only_accepted_keyword_dataset():
    data = sample_result()
    data["excluded_keywords"] = [{"keyword": "should never appear"}]
    page = build_html(data)
    assert "should never appear" not in page
    assert '"keywords":[{"rank":1' in page


def test_distribution_fill_can_render_its_calculated_width():
    page = build_html(sample_result())
    assert ".fill{display:block;height:100%" in page


def test_html_displays_method_version_from_canonical_metadata():
    page = build_html(sample_result())
    assert "方法版本：test-filtered-v2" in page


def test_html_keyword_detail_includes_keyword_purpose():
    page = build_html(sample_result())
    assert "关键词用途说明" in page
    assert "item.keyword_purpose" in page
