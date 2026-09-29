# Revenue Keyword Pipeline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a daily, resumable pipeline that imports revenue-ranking URLs and Feishu roots, collects Similarweb keyword data, filters volume >= 30,000 and KD <= 60, enriches candidates with Web.Cafe KD explanations, and writes keyword and URL records to the supplied Feishu sheets.

**Architecture:** Keep SQLite as the durable queue and provenance store. Use a browser-backed Similarweb provider for authorized pages, a small HTTP Web.Cafe provider for KD enrichment, and isolated Feishu sheet adapters for reading and upserting rows. A checkpoint table records completed source/keyword positions so a run resumes after 300 enriched keywords or a failure.

**Tech Stack:** Python 3.11+, Playwright, stdlib urllib/sqlite3, Feishu Open API, Web.Cafe KD HTTP API.

**Spec:** `docs/superpowers/specs/2026-08-24-subscription-keyword-loop-design.md` plus the current user requirements.

## Global Constraints

- Use only the user's authorized Chrome/Similarweb session; never log or persist cookies, tokens, or page credentials.
- Similarweb data collection is capped and rate-limited; failed sources are recorded and do not abort the batch.
- Web.Cafe/API tokens come from environment variables and are never printed.
- Feishu writes are append/upsert operations; never clear destination sheets.
- Daily enrichment limit defaults to 300 and must be resumable from SQLite.

### Task 1: Normalize Source and Destination Configuration

**Files:**
- Modify: `keyword_loop/feishu.py`
- Create: `keyword_loop/config.py`
- Test: `tests/test_config.py`

- [ ] Add explicit configuration for roots wiki URL, keyword output sheet URL, URL output sheet URL, market, daily limit, and checkpoint database.
- [ ] Parse Feishu sheet URLs with `sheet=` while preserving the wiki token.
- [ ] Add tests for URL parsing and defaults.

### Task 2: Extend SQLite for URLs, Enrichment, and Checkpoints

**Files:**
- Modify: `keyword_loop/store.py`, `keyword_loop/models.py`
- Test: `tests/test_store_pipeline.py`

- [ ] Add tables for `source_urls`, `url_keywords`, `kd_enrichment`, and `run_checkpoints`.
- [ ] Add methods to upsert URL records, record URL keyword provenance, record KD/explanation payloads, and atomically advance checkpoints.
- [ ] Add tests proving restart does not reprocess completed positions.

### Task 3: Import Revenue Ranking URLs

**Files:**
- Create: `keyword_loop/revenue_sources.py`
- Modify: `keyword_loop/feishu.py`
- Test: `tests/test_revenue_sources.py`

- [ ] Fetch the public Web.Cafe referring/revenue page and parse product/detail URLs from structured links.
- [ ] Support Toolify ranking URLs supplied as an optional source URL and deduplicate canonical domains.
- [ ] Record source month, ranking source, title, and URL in SQLite; expose a bounded `--url-limit` option.

### Task 4: Replace Similarweb Collector with Page and Root Providers

**Files:**
- Modify: `keyword_loop/similarweb.py`
- Create: `keyword_loop/similarweb_pages.py`
- Test: `tests/test_similarweb_pages.py`

- [ ] Build parameterized URLs for the root keyword generator and the domain/page keyword analysis route.
- [ ] Extract table columns by header names, not fixed indexes; parse `K/M` metrics and KD safely.
- [ ] Implement pagination/virtual-scroll collection up to a configured per-source cap and expose totals.
- [ ] Record URL keyword provenance and preserve result type.

### Task 5: Web.Cafe KD Enrichment and Explanations

**Files:**
- Create: `keyword_loop/webcafe.py`
- Modify: `keyword_loop/explanation.py`
- Test: `tests/test_webcafe.py`

- [ ] Add a token-authenticated HTTP client with 6-second pacing, 429 handling, and sanitized errors.
- [ ] Parse `score`, `keywordVolume`, `keywordType`, `keywordTrend`, `linkBudget`, `reasons`, and `details`.
- [ ] Generate deterministic Chinese fields answering what the keyword is, search intent, and subscription value.

### Task 6: Daily Orchestration and Feishu Publication

**Files:**
- Modify: `keyword_loop/cli.py`, `keyword_loop/feishu.py`
- Create: `keyword_loop/pipeline.py`
- Test: `tests/test_pipeline.py`

- [ ] Orchestrate roots and revenue URLs, filter volume/KD, enrich at most 300 new keywords per run, and resume from checkpoint.
- [ ] Publish keyword records to the `e2e503` sheet and URL records to `HJ7cif` using explicit sheet IDs.
- [ ] Keep dry-run local and report counts, failures, and next checkpoint.

### Task 7: Verification and Operations

**Files:**
- Modify: `README.md` or create `docs/keyword-pipeline.md`
- Test: full `tests/` suite

- [ ] Document environment variables, Chrome/CDP requirements, daily scheduling, and safe token handling.
- [ ] Add fixture-based tests for current Similarweb DOM and Web.Cafe responses.
- [ ] Run unit tests and a one-root/one-URL dry-run without publishing.

