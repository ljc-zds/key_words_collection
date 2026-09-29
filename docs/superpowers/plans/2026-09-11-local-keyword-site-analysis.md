# Local Keyword Site Analysis Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rank locally collected Similarweb and Semrush keywords for site-building potential and produce a filtered Excel workbook plus a self-contained HTML analysis page.

**Architecture:** A Python analysis module reads SQLite, keeps provider metrics separate, applies deterministic qualification/scoring, clusters accepted keywords, and writes one canonical JSON file. A JavaScript workbook builder and Python HTML builder consume only that canonical file so counts, ranks, and wording stay synchronized.

**Tech Stack:** Python 3, SQLite JSON1, pytest, JavaScript, `@oai/artifact-tool`, static HTML/CSS/JavaScript.

**Spec:** `docs/superpowers/specs/2026-09-11-local-keyword-site-analysis-design.md`

## Global Constraints

- Read only existing local SQLite data; make no Semrush, Similarweb, SERP, or other network requests.
- Do not create a scheduled or background task.
- Never add provider search volumes together.
- Exclude rejected keyword text from both final artifacts.
- Label all accepted rows `未进行实时 SERP 验证`.

---

### Task 1: Qualification and scoring engine

**Files:**
- Create: `keyword_site_analysis.py`
- Create: `tests/test_keyword_site_analysis.py`

**Interfaces:**
- Produces: `normalize_keyword(text)`, `merge_keyword_records(rows)`, `assess_keyword(record)`, `cluster_key(keyword, site_type)`, and `priority_for_score(score)`.

- [ ] Write tests for normalization, independent provider fields, metric gates, navigation/risk rejection, tool acceptance, classification, clustering, and priority thresholds.
- [ ] Run `pytest -q tests/test_keyword_site_analysis.py` and confirm failure because the module does not exist.
- [ ] Implement the smallest deterministic scoring engine that passes those tests.
- [ ] Run the focused tests and the repository test suite.

### Task 2: Local extraction and canonical result

**Files:**
- Modify: `keyword_site_analysis.py`
- Create: `run_keyword_site_analysis.py`
- Create: `outputs/keyword_site_analysis_20260911_local/keyword_site_analysis.json`

**Interfaces:**
- Produces JSON keys `metadata`, `summary`, `projects`, and `keywords`.

- [ ] Add tests using a temporary SQLite database for Similarweb rows, Semrush exact validation, and Semrush related rows.
- [ ] Confirm the extraction test fails before implementation.
- [ ] Implement read-only extraction, aggregation, assessment, project grouping, deterministic sorting, and JSON export.
- [ ] Run the full local dataset and inspect counts plus representative top, middle, and bottom accepted rows.
- [ ] Tighten rules only when sampled false positives reveal a reproducible category; add a failing regression test first.

### Task 3: Excel workbook

**Files:**
- Create: `scripts/build_keyword_site_workbook.mjs`
- Create: `outputs/keyword_site_analysis_20260911_local/关键词建站机会.xlsx`

**Interfaces:**
- Consumes: canonical JSON from Task 2.

- [ ] Mark one XLSX create operation with the required artifact-operation command.
- [ ] Build `建站项目排名`, `关键词明细`, and `评分口径` with typed values, filters, frozen headers, restrained conditional formatting, and source/freshness notes.
- [ ] Inspect key ranges and scan formula errors.
- [ ] Render and visually review every sheet before export completion.

### Task 4: Interactive HTML report

**Files:**
- Create: `scripts/build_keyword_site_html.py`
- Create: `outputs/keyword_site_analysis_20260911_local/关键词建站机会分析.html`

**Interfaces:**
- Consumes: canonical JSON from Task 2.

- [ ] Add a builder test that asserts escaped content, embedded counts, filters, ranking table, and no external assets.
- [ ] Confirm the test fails before implementation.
- [ ] Implement the self-contained report with project ranking, distributions, searchable keyword detail, and methodology.
- [ ] Verify desktop and mobile layouts with screenshots and check that filters update counts without overlap.

### Task 5: Final reconciliation

**Files:**
- Verify all outputs from Tasks 2-4.

- [ ] Re-run all focused tests.
- [ ] Confirm Excel keyword count and HTML embedded keyword count equal canonical JSON.
- [ ] Confirm no output contains rejected keyword records or claims of live SERP validation.
- [ ] Report final artifact paths and exact retained/project/P0/P1/P2 counts.
