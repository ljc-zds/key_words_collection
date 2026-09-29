# Ranking Keyword Discovery Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Discover keyword opportunities from public Toolify and third-party Stripe ranking pages, then prioritize terms shared by multiple ranked products.

**Architecture:** Source adapters produce normalized ranking products. A resolver and the existing Similarweb collector create observations with ranked-product provenance; SQLite aggregates distinct product support into consensus counts before Feishu publication.

**Tech Stack:** Python, urllib, Playwright/CDP, SQLite, pytest.

---

### Task 1: Parse public ranking pages

**Files:**
- Create: `keyword_loop/rankings.py`
- Create: `tests/test_rankings.py`

- [ ] Write fixture tests for a Toolify card and a third-party Stripe card, asserting name, target URL, rank, revenue text, source URL, and estimate flag.
- [ ] Verify the tests fail because the parser is absent.
- [ ] Implement `parse_toolify_page()` and `parse_stripe_page()` using stable links and visible card text only; reject missing URLs.
- [ ] Run `pytest tests/test_rankings.py -v`.

### Task 2: Store ranking provenance and consensus

**Files:**
- Modify: `keyword_loop/store.py`
- Modify: `keyword_loop/models.py`
- Create: `tests/test_ranking_consensus.py`

- [ ] Write a failing test where one keyword is observed for two products and assert consensus count is two.
- [ ] Add ranking-product and keyword-product provenance tables with parameterized SQL.
- [ ] Extend candidate query with distinct product count and product names.
- [ ] Run `pytest tests/test_ranking_consensus.py -v`.

### Task 3: Resolve products and collect Similarweb keywords

**Files:**
- Modify: `keyword_loop/cli.py`
- Modify: `keyword_loop/similarweb.py`
- Create: `tests/test_ranking_cli.py`

- [ ] Write a dry-run test using fixture ranking products and a stub collector.
- [ ] Add `rankings` CLI subcommand accepting source URLs and the existing CDP URL.
- [ ] Resolve direct official URLs, record per-product failures, and reuse the CDP collector.
- [ ] Run focused tests and a manual Toolify one-page dry-run.

### Task 4: Publish ranking evidence

**Files:**
- Modify: `keyword_loop/feishu.py`
- Modify: `tests/test_feishu.py`

- [ ] Write a failing row-rendering test for consensus count, ranked products, and source URLs.
- [ ] Add these columns to the Feishu output without removing current root provenance.
- [ ] Run `pytest -q` and manually publish a small dry-run batch only after inspecting the destination range.
