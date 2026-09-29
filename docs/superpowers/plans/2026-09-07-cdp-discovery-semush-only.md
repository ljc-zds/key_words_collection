# CDP Discovery and Semrush-Only Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a resumable CDP-only runner that collects Stripe, Toolify, and root candidates, applies Similarweb volume/KD gates, and cross-validates exact keywords with Semrush US without any AI, Serper, 哥飞 KD, or Feishu writes.

**Architecture:** Reuse `SimilarwebCollector` for CDP network JSON collection and `SemrushBrowserProvider` for Semrush network JSON. A focused runner owns source dispatch, SQLite persistence, quality/volume gates, Semrush payload normalization, and source checkpoints; all later enrichment and publication stages remain outside this command.

**Tech Stack:** Python 3.13, SQLite, Playwright CDP on `http://127.0.0.1:9222`, existing Similarweb and Semrush browser providers.

**Spec:** `docs/关键词挖掘完整流程.md`

## Global Constraints

- Use the existing isolated Chrome profile and CDP port `9222`; do not use OpenCLI, DOM scraping, screenshots, AI, Serper, 哥飞, or Feishu write APIs.
- Preserve existing SQLite rows and source checkpoints; never clear candidate or validation tables.
- Apply the existing Similarweb volume/KD tiers and the Semrush US cross-validation tiers.
- A per-root/product failure records a failure and continues to the next candidate.

---

### Task 1: Define the discovery-only gate runner

**Files:**
- Create: `run_discovery_semrush_only.py`
- Test: `tests/test_discovery_semrush_only.py`

**Interfaces:**
- Consumes: `SimilarwebCollector.collect(root) -> list[KeywordObservation]`, `KeywordStore.record`, `KeywordStore.collection_checkpoint`, `volume_kd_gate`, `keyword_quality_gate`.
- Produces: `collect_and_gate_source(store, collector, source, terms) -> tuple[int, int]`, where the tuple is `(stored_count, passed_count)`.

- [ ] **Step 1: Write the failing gate test**

```python
def test_collect_and_gate_source_records_only_similarweb_tier_passes(tmp_path):
    store = KeywordStore(tmp_path / "loop.sqlite3")
    collector = FakeCollector([
        KeywordObservation("good calculator", 30_000, 60, "Commercial", "calc", "Phrase", "global", "now"),
        KeywordObservation("weak calculator", 9_000, 31, "Commercial", "calc", "Phrase", "global", "now"),
    ])

    stored, passed = collect_and_gate_source(store, collector, "root", ["calc"])

    assert (stored, passed) == (2, 1)
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `PYTHONPATH=. .venv/bin/python -m pytest -q tests/test_discovery_semrush_only.py::test_collect_and_gate_source_records_only_similarweb_tier_passes`

Expected: FAIL because `collect_and_gate_source` is not defined.

- [ ] **Step 3: Implement source collection and Similarweb gating**

```python
def collect_and_gate_source(store, collector, source: str, terms: list[str]) -> tuple[int, int]:
    stored = passed = 0
    for term in terms:
        for observation in collector.collect(term):
            store.record(observation)
            stored += 1
            if keyword_quality_gate(observation.keyword).decision == "保留" and volume_kd_gate(observation.average_volume, observation.kd).decision == "保留":
                passed += 1
    return stored, passed
```

- [ ] **Step 4: Run the focused test to verify it passes**

Run: `PYTHONPATH=. .venv/bin/python -m pytest -q tests/test_discovery_semrush_only.py::test_collect_and_gate_source_records_only_similarweb_tier_passes`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add run_discovery_semrush_only.py tests/test_discovery_semrush_only.py
git commit -m "feat: add CDP discovery-only Similarweb gate"
```

### Task 2: Add Semrush US cross-validation without downstream enrichment

**Files:**
- Modify: `run_discovery_semrush_only.py`
- Test: `tests/test_discovery_semrush_only.py`

**Interfaces:**
- Consumes: `SemrushBrowserProvider.query(keyword) -> dict`, `normalize_keyword_row`, `volume_kd_gate`, `KeywordStore.record_validation`.
- Produces: `validate_semrush(store, provider, keyword, market) -> GateResult` and a `keyword_validation` row at stage `semrush`.

- [ ] **Step 1: Write the failing exact-keyword test**

```python
def test_validate_semrush_records_normalized_us_metrics(tmp_path):
    store = KeywordStore(tmp_path / "loop.sqlite3")
    provider = FakeSemrush({"keywords": [{"keyword": "grade calculator", "volume": 165000, "difficulty": 49, "cpc": 1.2, "intents": [2], "competition_level": 0.1, "serp_features": [1, 2]}]})

    result = validate_semrush(store, provider, "grade calculator", "global")

    assert result.decision == "保留"
    assert store.validation("grade calculator", "global", "semrush")["intent"] == "Commercial"
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `PYTHONPATH=. .venv/bin/python -m pytest -q tests/test_discovery_semrush_only.py::test_validate_semrush_records_normalized_us_metrics`

Expected: FAIL because `validate_semrush` is not defined.

- [ ] **Step 3: Implement exact-match Semrush validation**

```python
def validate_semrush(store, provider, keyword: str, market: str) -> GateResult:
    response = provider.query(keyword)
    exact = next((row for row in response["keywords"] if row["keyword"].lower() == keyword.lower()), None)
    payload = {"exact_keyword_found": exact is not None, **(exact or {})}
    gate = volume_kd_gate(payload.get("volume"), payload.get("kd")) if exact else semrush_missing_gate()
    payload.update(gate_decision=gate.decision, gate_reason=gate.reason)
    store.record_validation(keyword, market, "semrush", payload)
    return gate
```

- [ ] **Step 4: Run the focused test to verify it passes**

Run: `PYTHONPATH=. .venv/bin/python -m pytest -q tests/test_discovery_semrush_only.py::test_validate_semrush_records_normalized_us_metrics`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add run_discovery_semrush_only.py tests/test_discovery_semrush_only.py
git commit -m "feat: add Semrush-only cross validation"
```

### Task 3: Wire Stripe, Toolify, and root source inputs with resumable checkpoints

**Files:**
- Modify: `run_discovery_semrush_only.py`
- Modify: `docs/关键词挖掘完整流程.md`
- Test: `tests/test_discovery_semrush_only.py`

**Interfaces:**
- Consumes: root list from `load_roots_from_wiki`, product names from `fetch_toolify_ranking`, saved `CollectionCheckpoint` values.
- Produces: CLI arguments `--stripe-url`, `--toolify-url`, `--roots-feishu-url`, `--source-limit`, `--cdp-url`; console counts per source.

- [ ] **Step 1: Write the failing checkpoint test**

```python
def test_completed_source_checkpoint_skips_completed_terms(tmp_path):
    store = KeywordStore(tmp_path / "loop.sqlite3")
    store.set_state("discovery_only:root:offset", "1")

    assert remaining_terms(store, "root", ["first", "second"]) == ["second"]
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `PYTHONPATH=. .venv/bin/python -m pytest -q tests/test_discovery_semrush_only.py::test_completed_source_checkpoint_skips_completed_terms`

Expected: FAIL because `remaining_terms` is not defined.

- [ ] **Step 3: Implement source selection and per-source offsets**

```python
def remaining_terms(store, source: str, terms: list[str]) -> list[str]:
    offset = int(store.get_state(f"discovery_only:{source}:offset", "0"))
    return terms[offset:]
```

Advance `discovery_only:<source>:offset` only after Similarweb collection and Semrush validation for that term finish; record exceptions with `store.record_failure` and leave the offset unchanged for retry.

- [ ] **Step 4: Update the runbook command and explicit exclusions**

Document that this runner performs only `Stripe/Toolify/词根 -> Similarweb -> Semrush US`, consumes website subscription/query quotas but no model tokens, and does not publish to Feishu.

- [ ] **Step 5: Run focused and regression tests**

Run: `PYTHONPATH=. .venv/bin/python -m pytest -q tests/test_discovery_semrush_only.py tests/test_semrush_browser.py tests/test_screening.py`

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add run_discovery_semrush_only.py tests/test_discovery_semrush_only.py docs/关键词挖掘完整流程.md
git commit -m "feat: add resumable three-source CDP discovery runner"
```

## Self-Review

- Spec coverage: Task 1 covers Similarweb CDP and volume/KD initial filtering; Task 2 covers Semrush US cross-validation; Task 3 covers all three source inputs, checkpoints, and explicit exclusion of downstream model/API stages.
- Placeholder scan: no implementation step uses undefined behavior; each function, command, and expected outcome is specified.
- Type consistency: Task 1 persists `KeywordObservation`; Task 2 consumes the persisted keyword/market pair; Task 3 dispatches source term lists into Task 1 and Task 2.

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-09-07-cdp-discovery-semush-only.md`. Two execution options:

1. Subagent-Driven (recommended) - dispatch a fresh subagent per task and review between tasks.
2. Inline Execution - execute tasks in this session with checkpoints.
