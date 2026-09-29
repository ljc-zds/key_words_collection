from pathlib import Path


def test_workbook_previews_use_bounded_ranges():
    script = (Path(__file__).parents[1] / "scripts/build_keyword_site_workbook.mjs").read_text()
    assert "const previewRanges" in script
    assert "range: previewRanges[sheetName]" in script
    assert 'autoCrop: "all"' not in script


def test_workbook_includes_detailed_keyword_purpose_column():
    script = (Path(__file__).parents[1] / "scripts/build_keyword_site_workbook.mjs").read_text()
    assert '"关键词用途说明"' in script
    assert "item.keyword_purpose" in script


def test_workbook_builder_accepts_explicit_input_and_output_paths():
    script = (Path(__file__).parents[1] / "scripts/build_keyword_site_workbook.mjs").read_text()
    assert "process.argv[2]" in script
    assert "process.argv[3]" in script
