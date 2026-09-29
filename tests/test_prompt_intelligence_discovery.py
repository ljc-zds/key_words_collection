from collect_prompt_intelligence_keywords import cluster_keyword, read_sqlite, write_sqlite


def test_clusters_reverse_prompt_tools_before_model_specific_terms():
    assert cluster_keyword("gemini image to prompt generator") == "图片反推 Prompt"
    assert cluster_keyword("AI video to prompt generator") == "视频反推 Prompt"


def test_clusters_product_features_and_risk_terms():
    assert cluster_keyword("prompt optimizer") == "Prompt 优化增强"
    assert cluster_keyword("team prompt manager") == "Prompt 管理与协作"
    assert cluster_keyword("Claude prompt generator") == "模型专属 Prompt"
    assert cluster_keyword("NSFW prompt generator") == "风险/成人/越狱"


def test_sqlite_merges_provider_runs_for_resumable_collection(tmp_path):
    database = tmp_path / "keywords.sqlite3"
    base = {
        "keyword": "prompt optimizer", "cluster": "Prompt 优化增强", "market": "global",
        "seed": "prompt optimizer", "volume": 10, "kd": 20, "cpc": 1, "intent": None,
        "leading_site": None, "raw_json": "{}",
    }
    write_sqlite(database, [dict(base, provider="similarweb")], [{
        "provider": "similarweb", "seed": "prompt optimizer", "row_count": 1,
        "error": None, "collected_at": "2026-09-24T00:00:00+08:00",
    }])
    write_sqlite(database, [dict(base, provider="semrush", market="us")], [{
        "provider": "semrush", "seed": "prompt optimizer", "row_count": 1,
        "error": None, "collected_at": "2026-09-24T01:00:00+08:00",
    }])
    rows, runs = read_sqlite(database)
    assert {row["provider"] for row in rows} == {"similarweb", "semrush"}
    assert {run["provider"] for run in runs} == {"similarweb", "semrush"}
