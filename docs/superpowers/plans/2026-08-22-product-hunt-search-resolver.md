# Product Hunt Search Resolver Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox syntax for tracking.

**Goal:** Resolve Product Hunt products to official domains and create a filtered Obsidian candidate table.

**Architecture:** A resolver accepts browser search-result links and chooses only likely official domains. The orchestrator combines Product Hunt metadata, website resolution, AITDK records, and filter results into a Markdown table.

**Tech Stack:** Python, Playwright, Product Hunt GraphQL, AITDK extension, pytest.

---

### Task 1: Search Result Selection

**Files:**
- Create: `aitdk_enrichment/search_resolver.py`
- Create: `tests/test_search_resolver.py`

- [ ] Write a failing test asserting that `select_official_domain()` rejects `producthunt.com`, social networks, app stores, and directories, while accepting `example.com`.
- [ ] Run `.venv/bin/python -m pytest tests/test_search_resolver.py -v` and confirm missing-module failure.
- [ ] Implement a pure hostname allow/reject classifier and run the test to green.

### Task 2: Candidate Table Mapping

**Files:**
- Create: `aitdk_enrichment/candidate_table.py`
- Create: `tests/test_candidate_table.py`

- [ ] Write a failing test mapping a Product Hunt candidate and AITDK traffic record to fields: domain, source date, total visits, search share, direct share, keywords, status, and source links.
- [ ] Run its test, implement the mapper, then rerun the test.

### Task 3: Obsidian Table Report

**Files:**
- Modify: `aitdk_enrichment/obsidian_report.py`
- Modify: `tests/test_obsidian_report.py`

- [ ] Write a failing test asserting the Markdown contains screenshot-equivalent columns and no credential fields.
- [ ] Implement Markdown table rendering with success/error status and links.
- [ ] Run all unit tests.

### Task 4: Five-Product Live Batch

**Files:**
- Create: `aitdk_enrichment/product_hunt_batch.py`

- [ ] Fetch five newest public Product Hunt posts.
- [ ] Use browser search to resolve one official domain per product, recording a sanitized failure when no confident result exists.
- [ ] Query resolved domains through AITDK sequentially, apply filters, and write the dated table to the Obsidian vault.
- [ ] Run the complete test suite and inspect the generated note for credentials and malformed rows.

## Review

- The browser resolver never accepts Product Hunt redirect links or directory/social hosts.
- Reports retain Product Hunt source and resolved website links but no API token, AITDK signature, cookie, or request URL.
- Current directory is not a Git repository, so commits are deferred.
