# Trend Radar Raw Results and Fallback Windows Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Preserve every Rising record Google Trends returns per parent and retry short trend series with progressively shorter windows.

**Architecture:** New Explore returns at most 50 Rising records for a parent, verified live for `action`; retain those raw records and separately derive the `Breakout`/`>=500%` DFS candidates. Candidate comparisons try `today 1-m`, `now 7-d`, `now 3-d`, `now 2-d`, then `now 1-d`; each usable aligned series uses a 70/30 baseline/recent split.

**Tech Stack:** Python 3.13, Playwright/CDP, Google Trends Explore RPC, pytest.

**Spec:** User request in this Codex task, 2026-09-08.

## Global Constraints

- Google supplies no more than 50 Rising records for one parent request; retain all supplied records.
- Only `Breakout` or growth `>=500%` records enter DFS recursion.
- Use background CDP targets only.
- Write a checkpoint after each comparison batch.

### Task 1: Raw Rising Records

**Files:** `trend_radar/google_trends/client.py`, `trend_radar/pipeline.py`, `tests/test_trend_radar.py`

- [ ] Add a failing parser test proving a numeric growth value below 500 is preserved when raw mode is selected.
- [ ] Run `.venv/bin/python -m pytest -q tests/test_trend_radar.py -k raw` and confirm failure.
- [ ] Add `related_rising_all()` which returns every available Rising row, retain `related_rising()` as the qualified-filter API, and write both raw and qualified lists to parent checkpoint data.
- [ ] Run targeted client/pipeline tests and confirm they pass.

### Task 2: Fallback Comparison Windows

**Files:** `trend_radar/pipeline.py`, `trend_radar/google_trends/comparison.py`, `tests/test_trend_radar.py`

- [ ] Add a failing test asserting a short 30-day result retries `now 7-d`.
- [ ] Run `.venv/bin/python -m pytest -q tests/test_trend_radar.py -k fallback` and confirm failure.
- [ ] Add a comparison helper using windows `today 1-m`, `now 7-d`, `now 3-d`, `now 2-d`, `now 1-d`; accept an aligned non-empty series of at least two points and compute a 70/30 split dynamically.
- [ ] Persist selected timeframe, point count and explicit unavailable state only after every window fails.
- [ ] Run targeted tests and confirm they pass.

### Task 3: Checkpoint and Live Verification

**Files:** `trend_radar/cli.py`, `tests/test_trend_radar.py`

- [ ] Add failing test for fallback windows in checkpoint rules.
- [ ] Add those rules without breaking old checkpoints.
- [ ] Run `.venv/bin/python -m pytest -q tests/test_feishu.py tests/test_trend_radar.py tests/test_google_trends_mcp.py`.
- [ ] Run one background CDP query and verify 50 raw records are retained and all qualified rows are available to DFS.

## Self-Review

- Raw data, threshold qualification, all requested fallback windows, DFS, checkpoints, tests and live CDP verification are covered.
- No change attempts to exceed Google's verified 50-record per-parent limit.

