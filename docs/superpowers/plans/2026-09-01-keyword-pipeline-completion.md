# Keyword Pipeline Completion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Complete the keyword pipeline so every published accepted keyword carries Semrush, AI-screening, Web.Cafe, and Serper annotations, with explicit unavailable states rather than blank cells.

**Architecture:** Normalize each Semrush Keyword Manager row into a single validation payload before gate decisions. Run AI screening and Serper after hard gates as annotation-only stages, then publish a single Feishu upsert using all stored validations. Similarweb collection replenishes the queue whenever accepted plus pending candidates is below the daily target.

**Tech Stack:** Python 3.13, SQLite, Semrush Chrome UI, Similarweb Chrome UI, OpenAI-compatible Responses API, Web.Cafe API, Serper API, Feishu Sheets API, pytest.

**Spec:** `docs/keyword-pipeline-runbook.md`

## Global Constraints

- Only Similarweb volume >= 30,000 and Similarweb KD <= 60 candidates enter Semrush.
- Only Semrush volume >= 30,000 and Semrush KD <= 60 candidates may enter the intent gate.
- Only tool-page-intent candidates may be published to Feishu.
- AI, Web.Cafe, and Serper annotate accepted candidates and do not reject them.
- Web.Cafe calls use an interval of at least seven seconds.
- The Feishu keyword sheet is upsert-only and is never cleared.

---

### Task 1: Normalize Semrush Manager Data

**Files:**
- Create: `keyword_loop/semrush.py`
- Modify: `tests/test_semrush.py`

**Interfaces:**
- Produces: `parse_manager_cells(cells: list[str]) -> dict[str, object] | None`
- Consumes: one Semrush Keyword Manager row with keyword, intent, volume, KD, CPC, competition density, and SERP-feature count.

- [ ] **Step 1: Write the failing test**

```python
def test_parse_manager_cells_maps_all_publishable_semrush_fields():
    payload = parse_manager_cells(["", "png converter添加标签", "C", "-", "33.1千", "", "75", "60", "0.99", "0.09", "4"])
    assert payload == {
        "keyword": "png converter", "intent": "Commercial", "volume": 33100,
        "kd": 60, "cpc": 0.99, "competitive_density": 0.09,
        "serp_features": 4, "results": "接口未提供",
    }
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_semrush.py -q`
Expected: FAIL because `keyword_loop.semrush` does not exist.

- [ ] **Step 3: Write minimal implementation**

```python
def parse_manager_cells(cells: list[str]) -> dict[str, object] | None:
    if len(cells) < 11:
        return None
    return {"keyword": cells[1].removesuffix("添加标签"), ...}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_semrush.py -q`
Expected: PASS.

### Task 2: Add AI Screening Client and Batch Entry Point

**Files:**
- Create: `keyword_loop/ai_screen.py`
- Create: `run_ai_screen_batch.py`
- Modify: `tests/test_ai_screen.py`

**Interfaces:**
- Produces: `parse_screen_response(text: str) -> dict[str, object]`
- Consumes: model JSON with `score`, `tool_page_fit`, `exact_match_domain_fit`, `recommended_page_type`, and `reason`.

- [ ] **Step 1: Write the failing test**

```python
def test_parse_screen_response_rejects_missing_required_fields():
    with pytest.raises(ValueError):
        parse_screen_response('{"score": 80}')
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_ai_screen.py -q`
Expected: FAIL because `keyword_loop.ai_screen` does not exist.

- [ ] **Step 3: Write minimal implementation**

```python
def parse_screen_response(text: str) -> dict[str, object]:
    payload = json.loads(text)
    required = ("score", "tool_page_fit", "exact_match_domain_fit", "recommended_page_type", "reason")
    if any(key not in payload for key in required):
        raise ValueError("missing AI screen field")
    return {"decision": "仅注释", **payload}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_ai_screen.py -q`
Expected: PASS.

### Task 3: Publish Complete Annotation State

**Files:**
- Modify: `run_keyword_enrichment_batch.py`
- Modify: `run_serper_batch.py`
- Modify: `tests/test_feishu.py`

**Interfaces:**
- Consumes: validations returned by `validations_for(store, candidates)`.
- Produces: Feishu rows whose Semrush and annotation columns use stored values or explicit unavailable states.

- [ ] **Step 1: Write the failing test**

```python
assert values[1][28:31] == ["0.09", "4", "接口未提供"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_feishu.py -q`
Expected: FAIL because the fixture lacks full Semrush fields.

- [ ] **Step 3: Extend fixture and publish path**

```python
validations = {"agent crm": {"semrush": {"competitive_density": 0.09, "serp_features": 4, "results": "接口未提供"}}}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_feishu.py -q`
Expected: PASS.

### Task 4: Operational Runbook

**Files:**
- Create: `docs/keyword-pipeline-runbook.md`

**Interfaces:**
- Consumes: local commands, API environment variables, and Feishu sheet contract.
- Produces: the authoritative daily operating procedure.

- [ ] **Step 1: Document the source priority and streaming replenishment trigger**
- [ ] **Step 2: Document the exact hard gates, annotation stages, and field ownership**
- [ ] **Step 3: Document rate limits, failure recovery, and no-overwrite rules**
- [ ] **Step 4: Document commands, required environment variables, and verification checks**

### Task 5: Final Verification

**Files:**
- Test: `tests/test_semrush.py`
- Test: `tests/test_ai_screen.py`
- Test: `tests/test_feishu.py`

- [ ] **Step 1: Run focused tests**

Run: `python3 -m pytest tests/test_semrush.py tests/test_ai_screen.py tests/test_feishu.py -q`
Expected: PASS.

- [ ] **Step 2: Run full suite**

Run: `python3 -m pytest -q`
Expected: PASS.
