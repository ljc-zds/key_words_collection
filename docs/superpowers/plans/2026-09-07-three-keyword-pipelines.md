# Three Keyword Pipelines Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Expose Product Hunt/AITDK, Similarweb/Semrush discovery, and downstream validation/publication as three readable, independently runnable scripts.

**Architecture:** Move orchestration from the existing Similarweb/Semrush and daily-gates command modules into two focused pipeline modules. Keep command modules limited to CLI parsing and dependency construction, and retain legacy filenames as delegates so installed automation continues to work.

**Tech Stack:** Python 3.13, pytest, SQLite, Chrome CDP, AITDK MCP, Similarweb, Semrush, Feishu.

**Spec:** `docs/superpowers/specs/2026-09-07-three-keyword-pipelines-design.md`

## Global Constraints

- Keep `product_hunt_daily.py` as the Product Hunt/AITDK entry point.
- Discovery must not call AI, Serper, Web.Cafe KD, or Feishu publishing.
- Validation/publication must not collect new Similarweb observations.
- Preserve the existing SQLite schema, thresholds, and Feishu write behavior.
- Keep `docs/关键词挖掘完整流程.md` unchanged.

---

### Task 1: Extract Similarweb/Semrush Discovery Pipeline

**Files:**
- Create: `keyword_loop/workflows/discovery.py`
- Modify: `run_discovery_semrush_only.py`
- Create: `run_keyword_discovery.py`
- Modify: `tests/test_discovery_semrush_only.py`

**Interfaces:**
- Consumes: `KeywordStore`, `SimilarwebCollector`, `SemrushBrowserProvider`, source loaders, and screening gates.
- Produces: `DiscoveryTotals`, `collect_and_gate_source`, `validate_semrush`, `run_discovery`.

- [x] **Step 1: Write the failing test**

```python
from keyword_loop.workflows.discovery import DiscoveryTotals

def test_discovery_totals_reports_only_discovery_stages():
    totals = DiscoveryTotals(stored=2, similarweb_passed=1, semrush_checked=1, semrush_passed=1, semrush_rejected=0)
    assert totals.to_dict() == {
        "stored": 2, "similarweb_passed": 1, "semrush_checked": 1,
        "semrush_passed": 1, "semrush_rejected": 0,
    }
```

- [x] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=. .venv/bin/python -m pytest -q tests/test_discovery_semrush_only.py`

Expected: FAIL because `keyword_loop.workflows.discovery` does not exist.

- [x] **Step 3: Write minimal implementation**

```python
@dataclass
class DiscoveryTotals:
    stored: int = 0
    similarweb_passed: int = 0
    semrush_checked: int = 0
    semrush_passed: int = 0
    semrush_rejected: int = 0

    def to_dict(self) -> dict[str, int]:
        return asdict(self)
```

Move the current discovery functions into this module. Make both command files
delegate to `run_discovery` after parsing compatible arguments.

- [x] **Step 4: Run tests to verify it passes**

Run: `PYTHONPATH=. .venv/bin/python -m pytest -q tests/test_discovery_semrush_only.py`

Expected: PASS.

### Task 2: Extract Validation and Publication Pipeline

**Files:**
- Create: `keyword_loop/workflows/validation_publish.py`
- Create: `run_keyword_validation_publish.py`
- Modify: `run_daily_gates.py`
- Test: `tests/test_daily_pipeline.py`

**Interfaces:**
- Consumes: `KeywordStore`, Semrush, AI screen, Serper, Web.Cafe, and `publish_wiki`.
- Produces: `ValidationTotals` and `run_validation_publish`.

- [x] **Step 1: Write the failing test**

```python
from keyword_loop.workflows.validation_publish import ValidationTotals

def test_validation_totals_tracks_publication_separately():
    totals = ValidationTotals(queued=4, accepted=2, published=True)
    assert totals.to_dict() == {"queued": 4, "accepted": 2, "published": True}
```

- [x] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=. .venv/bin/python -m pytest -q tests/test_daily_pipeline.py`

Expected: FAIL because `keyword_loop.workflows.validation_publish` does not exist.

- [x] **Step 3: Write minimal implementation**

```python
@dataclass(frozen=True)
class ValidationTotals:
    queued: int
    accepted: int
    published: bool
```

Move the current `run_daily_gates.py` workflow into `run_validation_publish`.
Have the new command construct its clients and have `run_daily_gates.py` call
the new command `main()` for compatibility.

- [x] **Step 4: Run tests to verify it passes**

Run: `PYTHONPATH=. .venv/bin/python -m pytest -q tests/test_daily_pipeline.py`

Expected: PASS.

### Task 3: Add Three-Pipeline Operating Guide

**Files:**
- Create: `docs/三条找词流水线运行说明.md`
- Modify: `AITDK_CDP_MCP.md`

**Interfaces:**
- Consumes: command-line interfaces from Tasks 1 and 2 plus `product_hunt_daily.py`.
- Produces: a Chinese guide with command examples, data boundaries, CDP requirements, daily order, and retry behavior.

- [x] **Step 1: Write the documentation acceptance checklist**

```text
The guide names exactly three scripts, states whether each writes Feishu,
and includes one retry command for Product Hunt and one for validation.
```

- [x] **Step 2: Verify the checklist fails**

Run: `test -f docs/三条找词流水线运行说明.md`

Expected: exit status 1 because the guide does not exist.

- [x] **Step 3: Write the guide**

Document the Product Hunt/AITDK pipeline, discovery-only pipeline, and
validation/publication pipeline. Add the AITDK CDP startup command as the
prerequisite for the Product Hunt pipeline. Do not edit the existing complete
keyword-process document.

- [x] **Step 4: Verify the checklist passes**

Run: `rg -n "product_hunt_daily.py|run_keyword_discovery.py|run_keyword_validation_publish.py" docs/三条找词流水线运行说明.md`

Expected: each command name appears in the guide.

### Task 4: Full Regression Check

**Files:**
- Verify: `tests/test_product_hunt_daily.py`
- Verify: `tests/test_discovery_semrush_only.py`
- Verify: `tests/test_daily_pipeline.py`

**Interfaces:**
- Consumes: the three complete command paths.
- Produces: evidence that each pipeline boundary remains covered.

- [x] **Step 1: Run focused tests**

Run: `PYTHONPATH=. .venv/bin/python -m pytest -q tests/test_product_hunt_daily.py tests/test_discovery_semrush_only.py tests/test_daily_pipeline.py`

Expected: PASS.

- [x] **Step 2: Run the full suite**

Run: `PYTHONPATH=. .venv/bin/python -m pytest -q`

Expected: PASS, or report an unrelated pre-existing collection failure with its exact file.
