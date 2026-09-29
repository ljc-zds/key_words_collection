from keyword_loop.core.sources.roots import load_roots, propose_roots


def test_load_roots_uses_active_rows_and_deduplicates_case_insensitively(tmp_path) -> None:
    path = tmp_path / "roots.csv"
    path.write_text("root,active\nAgent,true\nagent,true\nCRM,false\n", encoding="utf-8")
    assert load_roots(path) == ["agent"]


def test_propose_roots_keeps_meaningful_keyword_tokens() -> None:
    assert propose_roots(["best ai invoice generator"]) == ["ai", "generator", "invoice"]
