# Subscription Keyword Loop Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Collect Similarweb keyword-generator results from root keywords, select high-volume/low-KD opportunities, and publish an actionable daily review batch to Feishu.

**Architecture:** A `keyword_loop` package separates deterministic domain logic from the live Similarweb browser collector and Feishu publisher. SQLite persists keyword provenance and makes reruns idempotent; Feishu receives an upserted daily review view after filtering.

**Tech Stack:** Python 3.13, Playwright, SQLite (`sqlite3`), urllib OpenAPI client, pytest.

---

## File Structure

- Create `keyword_loop/models.py`: immutable raw-result and candidate data structures.
- Create `keyword_loop/parsing.py`: Similarweb metric and row parsing with no browser dependency.
- Create `keyword_loop/store.py`: SQLite schema and keyword/provenance upsert/query operations.
- Create `keyword_loop/roots.py`: root CSV input and conservative root proposals.
- Create `keyword_loop/explanation.py`: deterministic Chinese review explanation.
- Create `keyword_loop/similarweb.py`: Playwright page navigation, tab extraction, pagination, and sanitized failures.
- Create `keyword_loop/feishu.py`: credential loading, wiki-node resolution, Sheets/Bitable payloads and publication.
- Create `keyword_loop/cli.py` and `keyword_loop/__main__.py`: `run`, `import-roots`, `propose-roots`, and `publish` commands.
- Create `tests/test_keyword_parsing.py`, `tests/test_keyword_store.py`, `tests/test_roots.py`, `tests/test_explanation.py`, `tests/test_feishu.py`, `tests/test_similarweb_fixture.py`, and `tests/test_keyword_cli.py`.
- Modify `requirements.txt`: retain existing requirements; add no dependency unless the selected Feishu target cannot be accessed through `urllib`.
- Modify `.env.example`: document names only, never values.

### Task 1: Define and parse keyword records

**Files:**
- Create: `keyword_loop/models.py`
- Create: `keyword_loop/parsing.py`
- Create: `tests/test_keyword_parsing.py`

- [ ] **Step 1: Write failing parser tests**

```python
from keyword_loop.parsing import parse_keyword_row, parse_metric


def test_parse_metric_supports_similarweb_suffixes() -> None:
    assert parse_metric("30K") == 30_000
    assert parse_metric("1.25M") == 1_250_000
    assert parse_metric("-") is None


def test_parse_keyword_row_normalizes_a_complete_table_row() -> None:
    result = parse_keyword_row(
        ["Agent CRM", "31.4K", "57", "COMMERCIAL"],
        root="agent",
        result_type="phrase_match",
        market="global",
        retrieved_at="2026-08-24T08:00:00+00:00",
    )
    assert result.keyword == "agent crm"
    assert result.average_volume == 31_400
    assert result.kd == 57
    assert result.intent == "COMMERCIAL"
```

- [ ] **Step 2: Verify failure**

Run: `pytest tests/test_keyword_parsing.py -v`

Expected: FAIL because `keyword_loop` does not yet exist.

- [ ] **Step 3: Implement minimal records and parser**

```python
@dataclass(frozen=True)
class KeywordObservation:
    keyword: str
    average_volume: int | None
    kd: int | None
    intent: str | None
    root: str
    result_type: str
    market: str
    retrieved_at: str


def parse_metric(value: str) -> int | None:
    cleaned = value.strip().replace(",", "").upper()
    if cleaned in {"", "-", "N/A"}:
        return None
    multiplier = 1_000_000 if cleaned.endswith("M") else 1_000 if cleaned.endswith("K") else 1
    return int(float(cleaned.rstrip("KM")) * multiplier)
```

`parse_keyword_row` must require four columns, normalize whitespace/case, return `None` for blank keywords, and parse KD as an integer only from `0..100`.

- [ ] **Step 4: Verify green**

Run: `pytest tests/test_keyword_parsing.py -v`

Expected: PASS.

### Task 2: Persist and filter candidates with provenance

**Files:**
- Create: `keyword_loop/store.py`
- Create: `tests/test_keyword_store.py`

- [ ] **Step 1: Write a failing persistence/filter test**

```python
def test_daily_candidates_merge_provenance_and_enforce_thresholds(tmp_path) -> None:
    store = KeywordStore(tmp_path / "loop.sqlite3")
    store.record(observation("agent crm", 31_000, 57, "agent"))
    store.record(observation("agent crm", 31_000, 57, "crm"))
    store.record(observation("agent jobs", 30_000, 61, "agent"))

    candidates = store.daily_candidates(minimum_volume=30_000, maximum_kd=60, limit=300)

    assert [(item.keyword, item.source_roots) for item in candidates] == [("agent crm", ("agent", "crm"))]
```

- [ ] **Step 2: Verify failure**

Run: `pytest tests/test_keyword_store.py -v`

Expected: FAIL because `KeywordStore` is undefined.

- [ ] **Step 3: Implement schema and query**

Create `observations`, `keywords`, and `keyword_provenance` tables with parameterized SQL. `record()` must normalize keyword plus market, preserve the newest metric values, and insert provenance with `INSERT OR IGNORE`. `daily_candidates()` must query only observations having non-null volume/KD, apply inclusive thresholds, aggregate roots/result types, and sort by volume descending then KD ascending then root count descending.

- [ ] **Step 4: Verify green**

Run: `pytest tests/test_keyword_store.py -v`

Expected: PASS.

### Task 3: Import roots and generate conservative proposals

**Files:**
- Create: `keyword_loop/roots.py`
- Create: `tests/test_roots.py`

- [ ] **Step 1: Write failing root tests**

```python
def test_load_roots_uses_active_rows_and_deduplicates_case_insensitively(tmp_path) -> None:
    path = tmp_path / "roots.csv"
    path.write_text("root,active\nAgent,true\nagent,true\nCRM,false\n", encoding="utf-8")
    assert load_roots(path) == ["agent"]


def test_propose_roots_keeps_meaningful_keyword_tokens() -> None:
    assert propose_roots(["best ai invoice generator"]) == ["ai", "invoice", "generator"]
```

- [ ] **Step 2: Verify failure**

Run: `pytest tests/test_roots.py -v`

Expected: FAIL because root functions are undefined.

- [ ] **Step 3: Implement input/proposal functions**

`load_roots()` must require a `root` header, treat missing `active` as active, accept only `true/1/yes` as active values, and return sorted normalized roots. `propose_roots()` must lowercase, tokenize ASCII words, remove an explicit stop-word set (`best`, `for`, `with`, `the`, `and`), discard one-character tokens, and return sorted unique proposals. It must not update any source root file.

- [ ] **Step 4: Verify green**

Run: `pytest tests/test_roots.py -v`

Expected: PASS.

### Task 4: Produce a deterministic Chinese review explanation

**Files:**
- Create: `keyword_loop/explanation.py`
- Create: `tests/test_explanation.py`

- [ ] **Step 1: Write failing explanation test**

```python
def test_explanation_answers_definition_intent_and_subscription_value() -> None:
    text = explain_candidate(candidate(keyword="agent crm", intent="COMMERCIAL"))
    assert "是什么：" in text
    assert "搜索意图：" in text
    assert "商业价值：" in text
    assert "商业型" in text
```

- [ ] **Step 2: Verify failure**

Run: `pytest tests/test_explanation.py -v`

Expected: FAIL because `explain_candidate` is undefined.

- [ ] **Step 3: Implement explanation mapping**

Map `COMMERCIAL`, `TRANSACTIONAL`, `INFORMATIONAL`, `NAVIGATIONAL`, and unknown values to Chinese intent labels and a fixed subscription-value sentence. Build three labelled clauses from the candidate fields. Do not call an LLM or insert claims not present in the keyword.

- [ ] **Step 4: Verify green**

Run: `pytest tests/test_explanation.py -v`

Expected: PASS.

### Task 5: Extract Similarweb Keyword Generator rows

**Files:**
- Create: `keyword_loop/similarweb.py`
- Create: `tests/fixtures/similarweb-keyword-generator.html`
- Create: `tests/test_similarweb_fixture.py`

- [ ] **Step 1: Write a failing fixture extraction test**

```python
def test_extract_rows_reads_keyword_volume_kd_and_intent_from_generator_fixture() -> None:
    html = Path("tests/fixtures/similarweb-keyword-generator.html").read_text()
    rows = extract_rows_from_html(html)
    assert rows[0] == ["agent crm", "31.4K", "57", "COMMERCIAL"]
```

- [ ] **Step 2: Verify failure**

Run: `pytest tests/test_similarweb_fixture.py -v`

Expected: FAIL because the fixture extractor is undefined.

- [ ] **Step 3: Implement fixture parser and Playwright collector**

Implement `extract_rows_from_html()` against stable `data-testid` selectors captured from a sanitized fixture. Implement `SimilarwebCollector.collect(root)` to open the generator URL with `keyword` query parameter, wait for the results grid, visit the four configured tabs, extract rows through the same DOM mapping, click only a visible enabled next-page control, and stop at the configured cap. Catch `TimeoutError` and selector errors into `CollectionFailure(root, reason)` with type-only messages. No page HTML, headers, cookies, or credentials may be logged.

- [ ] **Step 4: Verify green**

Run: `pytest tests/test_similarweb_fixture.py -v`

Expected: PASS.

### Task 6: Resolve and publish to Feishu

**Files:**
- Create: `keyword_loop/feishu.py`
- Create: `tests/test_feishu.py`
- Modify: `.env.example`

- [ ] **Step 1: Write failing payload-selection tests**

```python
def test_build_sheet_values_creates_header_and_candidate_row() -> None:
    values = build_sheet_values([candidate(keyword="agent crm", intent="COMMERCIAL")])
    assert values[0][0] == "关键词"
    assert values[1][0] == "agent crm"


def test_parse_wiki_url_extracts_token_without_network() -> None:
    assert parse_wiki_url("https://my.feishu.cn/wiki/VHnXwGzGQiGeUkkgj4tc4kpLnbh") == "VHnXwGzGQiGeUkkgj4tc4kpLnbh"
```

- [ ] **Step 2: Verify failure**

Run: `pytest tests/test_feishu.py -v`

Expected: FAIL because Feishu helpers are undefined.

- [ ] **Step 3: Implement Feishu client**

Implement `load_feishu_env()` using `os.environ` with optional `.env` parsing, `tenant_access_token()` using the internal tenant-token endpoint, and `resolve_wiki_node()` using `GET /open-apis/wiki/v2/spaces/get_node?token=<token>`. Dispatch `obj_type == "sheet"` to Sheets v2 values update and `obj_type == "bitable"` to Bitable v1 records batch create/update. Raise sanitized errors containing response code and endpoint category only. Add `.env.example` lines:

```dotenv
FEISHU_APP_ID=
FEISHU_APP_SECRET=
```

- [ ] **Step 4: Verify green**

Run: `pytest tests/test_feishu.py -v`

Expected: PASS.

### Task 7: Compose the CLI and verify the full suite

**Files:**
- Create: `keyword_loop/cli.py`
- Create: `keyword_loop/__main__.py`
- Modify: `keyword_loop/store.py`
- Test: all `tests/test_keyword_*.py`, `tests/test_roots.py`, `tests/test_explanation.py`, `tests/test_feishu.py`, `tests/test_similarweb_fixture.py`

- [ ] **Step 1: Write a failing dry-run integration test**

```python
def test_run_dry_run_stores_candidates_without_calling_feishu(tmp_path, monkeypatch) -> None:
    result = run(
        roots=["agent"], database=tmp_path / "loop.sqlite3", dry_run=True,
        collector=StubCollector([observation("agent crm", 31_000, 57, "agent")]),
    )
    assert result.candidate_count == 1
    assert result.published is False
```

- [ ] **Step 2: Verify failure**

Run: `pytest tests/test_keyword_cli.py::test_run_dry_run_stores_candidates_without_calling_feishu -v`

Expected: FAIL because `run` is undefined.

- [ ] **Step 3: Implement CLI composition**

Implement `run()` to collect per root, record successful observations, query daily candidates, add explanations, and only call the publisher when `dry_run` is false. Add argparse subcommands `run`, `import-roots`, `propose-roots`, and `publish`; use explicit `--roots-csv`, `--results-feishu-url`, and `--database` options. Exit nonzero only for invalid configuration or a failed publication, not for individual root failures.

- [ ] **Step 4: Verify green and run regression suite**

Run: `pytest -q`

Expected: all existing and new tests PASS.

- [ ] **Step 5: Manually validate live dependencies with one root**

Run: `python -m keyword_loop run --roots-csv /path/to/one-root.csv --results-feishu-url <configured-wiki-url> --database output/keyword-loop.sqlite3 --per-root-cap 10`

Expected: one published Feishu batch, or a sanitized error identifying login, selector, wiki permission, or destination-type setup.
