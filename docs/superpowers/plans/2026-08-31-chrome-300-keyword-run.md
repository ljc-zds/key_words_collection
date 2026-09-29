# Chrome 300-Keyword Run Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Run the three keyword sources through the logged-in Chrome Similarweb session in short, resumable batches and publish at most 300 qualified keywords per day.

**Architecture:** The browser worker performs one source query at a time and writes raw observations immediately to SQLite. A separate filter/enrichment worker selects new rows, calls Web.Cafe at 6-second intervals, and publishes only completed rows to the keyword sheet. URL metadata is imported independently so a failed Similarweb page does not lose source provenance.

**Tech Stack:** Python 3.11+, Playwright/CDP, SQLite, Feishu Sheets API, Web.Cafe API.

## Global Constraints

- Use the user's authorized Chrome session; never copy cookies or credentials.
- Each browser operation must finish within 30 seconds or persist a checkpoint before retrying.
- Daily output limit is 300 newly enriched keywords.
- Filter is average volume >= 30,000 and Similarweb KD <= 60.
- Web.Cafe requests are serialized with at least 6 seconds between calls.

### Task 1: Source Queue

**Files:** `keyword_loop/revenue_sources.py`, `keyword_loop/store.py`, `tests/test_revenue_sources.py`

- [ ] Parse Stripe/Web.Cafe and Toolify pages into canonical domains and source labels.
- [ ] Upsert each domain with `source`, `month`, `rank`, and source URL.
- [ ] Test duplicate domains and blocked social/marketplace domains.

### Task 2: Chrome Batch Worker

**Files:** `keyword_loop/similarweb.py`, `keyword_loop/similarweb_pages.py`, `tests/test_similarweb_pages.py`

- [ ] Add `collect_batch(source_type, source_id, cursor, limit=100)`.
- [ ] Navigate one root/domain per call, read visible columns by header, and return rows plus next cursor.
- [ ] Persist cursor after every completed page; retry a failed page once.
- [ ] Test K/M parsing, missing cells, and cursor resume with fixture DOM.

### Task 3: Three-Source Scheduler

**Files:** `keyword_loop/pipeline.py`, `tests/test_pipeline.py`

- [ ] Interleave sources in fixed order: Stripe URLs, Toolify URLs, Feishu roots.
- [ ] Deduplicate keywords by normalized text and retain all provenance.
- [ ] Stop collection when 300 new qualified candidates are available or queues are exhausted.
- [ ] Test restart from a saved cursor without duplicate processing.

### Task 4: KD Enrichment

**Files:** `keyword_loop/webcafe.py`, `keyword_loop/store.py`, `tests/test_webcafe.py`

- [ ] Select only candidates not present in `kd_enrichment`.
- [ ] Enrich serially, storing response and generated Chinese explanation after each keyword.
- [ ] Stop exactly at the daily limit and record the next keyword position.
- [ ] Test rate-limit handling and restart behavior.

### Task 5: Feishu Publication

**Files:** `keyword_loop/feishu.py`, `tests/test_feishu.py`

- [ ] Parse `sheet=e2e503` and publish keyword rows there.
- [ ] Parse `sheet=HJ7cif` and publish URL rows there.
- [ ] Use append/upsert ranges; never clear existing rows.
- [ ] Validate target headers before the first write.

### Task 6: Operational Run

- [ ] Run a one-root batch of 100 rows in Chrome and verify SQLite counts.
- [ ] Run three additional short batches until 300 qualified rows or source exhaustion.
- [ ] Run Web.Cafe enrichment and publish completed rows.
- [ ] Print `collected`, `qualified`, `enriched`, `published`, `failed`, and next checkpoint.

