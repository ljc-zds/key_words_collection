import asyncio
from datetime import date

from product_hunt.aitdk.domain.demand_filter import FilterResult
from product_hunt.aitdk.product.product_hunt import ProductCandidate
from product_hunt_daily import (
    default_collection_date,
    load_checkpoint_rows,
    filter_unseen_products,
    failure_status,
    load_products,
    merge_daily_rows,
    merge_retry_rows,
    pad_rows_for_overwrite,
    public_registration_date,
    sheet_rows,
    save_checkpoint_rows,
    collect_transient_aitdk_retries,
    transient_aitdk_error,
)
import product_hunt.pipeline as pipeline


def test_rdap_runs_while_next_aitdk_query_is_in_flight(monkeypatch):
    import threading
    ready = threading.Event()
    products = [ProductCandidate(str(i), str(i), '', f'https://ph/{i}', f'https://site{i}.test', '', '2026-09-09', 0) for i in range(2)]
    def enrich(host):
        if host == 'site1.test':
            assert ready.wait(2), 'RDAP blocked by synchronous AITDK'
        return {'status': 'ok', 'registered': None, 'monthly_visits': 50000, 'search_share': .5, 'direct_share': .3, 'keywords': []}
    def rdap(host):
        ready.set()
        return '2020-01-01'
    monkeypatch.setattr(pipeline, 'domain_enrich', enrich)
    monkeypatch.setattr(pipeline, 'traffic_panel', lambda value: value)
    monkeypatch.setattr(pipeline, 'public_registration_date', rdap)
    saved = []
    rows = asyncio.run(pipeline.collect(date(2026, 9, 9), products=products,
        on_record=lambda r: saved.append((r['domain'], r['reason'], r['panel']['monthly_visits']))))
    assert all(r['status'] == 'excluded' for r in rows)
    assert all(r['panel']['monthly_visits'] == 50000 for r in rows)
    assert any(reason == 'domain age exceeds 365 days' for _, reason, _ in saved)


def test_retry_checkpoint_survives_interruption_and_preserves_rounds(tmp_path):
    import json
    import pytest
    first = ProductCandidate('1', 'First', '', 'https://ph/1', 'https://first.test', 'first.test', '2026-09-08T00:00:00Z', 0)
    second = ProductCandidate('2', 'Second', '', 'https://ph/2', 'https://second.test', 'second.test', '2026-09-08T00:00:00Z', 0)
    calls = []
    interrupted = False

    async def collector(day, limit, products, on_record):
        nonlocal interrupted
        calls.append([p.product_id for p in products])
        result = []
        for p in products:
            row = {'product': p, 'panel': {}, 'status': 'excluded', 'reason': 'too old'}
            if not interrupted:
                row.update(status='error', reason='AITDK MCP: waiting for Created Date')
            else:
                row['filter'] = FilterResult(False, ['too old'], ['demand keyword'])
            on_record(row)
            result.append(row)
            if not interrupted:
                interrupted = True
                raise RuntimeError('simulated interruption')
        return result

    async def no_wait(seconds):
        pass

    def run():
        return asyncio.run(pipeline.collect_transient_aitdk_retries(
            date(2026, 9, 8), [first, second], collector=collector,
            sleeper=no_wait, checkpoint_directory=tmp_path))

    with pytest.raises(RuntimeError, match='simulated interruption'):
        run()
    assert len(json.loads((tmp_path / 'round-1.json').read_text())) == 1
    records = run()
    assert calls == [['1', '2'], ['2'], ['1']]
    assert all(row['status'] == 'excluded' for row in records)
    resumed = run()
    assert [row['filter'].non_brand_keywords for row in resumed] == [['demand keyword']] * 2
    assert all(not call for call in calls[3:])


def test_failure_status_distinguishes_expected_outcomes() -> None:
    assert failure_status("AITDK has no traffic data") == "no_data"
    assert failure_status("no independent official website") == "no_website"
    assert failure_status("TimeoutError") == "error"


def test_default_collection_date_is_previous_utc_day() -> None:
    assert default_collection_date(date(2026, 8, 31)) == date(2026, 8, 30)


def test_sheet_rows_include_three_month_trend_and_keyword_volumes() -> None:
    product = ProductCandidate("1", "Tool", "Useful", "https://ph/tool", "https://ph/r/tool", "ph", "2026-08-30T01:00:00Z", 10)
    records = [{
        "product": product, "website": "https://tool.com", "domain": "tool.com", "age": 100,
        "status": "passed", "reason": "", "filter": FilterResult(True, [], ["invoice generator"]),
        "panel": {
            "registered": "2026-05-23", "monthly_visits": 20_000,
            "monthly_visits_trend": [{"month": "2026-06", "visits": 10_000}, {"month": "2026-07", "visits": 15_000}, {"month": "2026-08", "visits": 20_000}],
            "search_share": 0.3, "direct_share": 0.25,
            "keywords": [{"name": "invoice generator", "volume": 4500}],
        },
    }]

    rows = sheet_rows(records)

    assert "3个月访问趋势" in rows[0]
    assert "2026-06: 10,000 → 2026-07: 15,000 → 2026-08: 20,000" in rows[1]
    assert "invoice generator (4,500)" in rows[1]


def test_product_list_is_cached_by_collection_date(tmp_path) -> None:
    product = ProductCandidate("1", "Tool", "Useful", "https://ph/tool", "https://tool.com", "tool.com", "2026-08-30T01:00:00Z", 10)
    calls = 0

    def fetcher(_token, _date):
        nonlocal calls
        calls += 1
        return [product]

    first = load_products(date(2026, 8, 30), "token", cache_directory=tmp_path, fetcher=fetcher)
    second = load_products(date(2026, 8, 30), "token", cache_directory=tmp_path, fetcher=fetcher)

    assert first == second == [product]
    assert calls == 1


def test_retry_rows_replace_only_matching_error_records() -> None:
    header = ["product"] + [""] * 19
    old_error = ["Broken"] + [""] * 14 + ["error", "URLError", "https://ph/broken", "", ""]
    unchanged = ["Good"] + [""] * 14 + ["Success", "", "https://ph/good", "", ""]
    replacement = ["Broken"] + [""] * 14 + ["excluded", "too old", "https://ph/broken", "", "https://broken.com"]

    merged = merge_retry_rows([header, old_error, unchanged], [replacement])

    assert merged == [header, replacement, unchanged]


def test_daily_rows_append_new_products_and_skip_existing_date_link_pairs() -> None:
    header = ["product"] + [""] * 19
    existing = ["Old"] + [""] * 5 + ["2026-08-30"] + [""] * 10 + ["https://ph/old", "", ""]
    duplicate = ["Old rerun"] + [""] * 5 + ["2026-08-30"] + [""] * 10 + ["https://ph/old", "", ""]
    new_row = ["New"] + [""] * 5 + ["2026-08-31"] + [""] * 10 + ["https://ph/new", "", ""]

    merged = merge_daily_rows([header, existing], [header, duplicate, new_row])

    assert merged == [header, existing, new_row]


def test_daily_rows_can_replace_duplicate_during_error_retry() -> None:
    header = ["product"] + [""] * 19
    old_error = ["Tool"] + [""] * 5 + ["2026-08-30"] + [""] * 8 + ["error", "failed", "https://ph/tool", "", ""]
    repaired = ["Tool"] + [""] * 5 + ["2026-08-30"] + [""] * 8 + ["excluded", "too old", "https://ph/tool", "", ""]

    merged = merge_daily_rows([header, old_error], [header, repaired], replace_duplicates=True)

    assert merged == [header, repaired]


def test_daily_rows_deduplicate_feishu_rich_link_against_plain_url() -> None:
    header = ["product"] + [""] * 19
    rich_link = [{"type": "url", "text": "Product", "link": "https://ph/tool"}]
    existing = ["Tool"] + [""] * 5 + ["2026-08-30"] + [""] * 10 + [rich_link, "", ""]
    duplicate = ["Tool"] + [""] * 5 + ["2026-08-30"] + [""] * 10 + ["https://ph/tool", "", ""]

    merged = merge_daily_rows([header, existing], [header, duplicate])

    assert merged == [header, existing]


def test_daily_rows_remove_duplicates_already_in_feishu() -> None:
    header = ["product"] + [""] * 19
    first = ["Tool"] + [""] * 5 + ["2026-08-30"] + [""] * 10 + ["https://ph/tool", "", ""]
    duplicate = ["Tool duplicate"] + [""] * 5 + ["2026-08-30"] + [""] * 10 + ["https://ph/tool", "", ""]

    merged = merge_daily_rows([header, first, duplicate], [header])

    assert merged == [header, first]


def test_pad_rows_for_overwrite_clears_old_trailing_rows() -> None:
    rows = [["header", ""], ["new", "value"]]

    assert pad_rows_for_overwrite(rows, previous_row_count=4) == [
        ["header", ""],
        ["new", "value"],
        ["", ""],
        ["", ""],
    ]


def test_filter_unseen_products_skips_existing_date_and_product_hunt_link() -> None:
    existing_keys = {("2026-08-31", "https://ph/existing")}
    existing = ProductCandidate("1", "Existing", "", "https://ph/existing", "", "", "2026-08-31T01:00:00Z", 0)
    new = ProductCandidate("2", "New", "", "https://ph/new", "", "", "2026-08-31T02:00:00Z", 0)

    assert filter_unseen_products([existing, new], existing_keys) == [new]


def test_filter_unseen_products_skips_duplicates_within_product_hunt_batch() -> None:
    duplicate = ProductCandidate("1", "Duplicate", "", "https://ph/same", "", "", "2026-09-01T01:00:00Z", 0)
    same_product = ProductCandidate("2", "Duplicate again", "", "https://ph/same", "", "", "2026-09-01T02:00:00Z", 0)

    assert filter_unseen_products([duplicate, same_product], set()) == [duplicate]


def test_checkpoint_rows_persist_completed_records_for_resume(tmp_path) -> None:
    checkpoint = tmp_path / "2026-09-01.json"
    rows = [["Tool"] + [""] * 5 + ["2026-09-01"] + [""] * 10 + ["https://ph/tool", "", ""]]

    save_checkpoint_rows(checkpoint, rows)

    assert load_checkpoint_rows(checkpoint) == rows


def test_public_registration_date_uses_rdap_without_a_tabapi_key(monkeypatch) -> None:
    monkeypatch.setattr(
        pipeline,
        "fetch_public_rdap",
        lambda _domain: {"events": [{"eventAction": "registration", "eventDate": "2026-06-01T00:00:00Z"}]},
    )

    assert public_registration_date("example.com") == "2026-06-01"


def test_transient_aitdk_error_only_accepts_the_three_retry_categories() -> None:
    assert transient_aitdk_error('AITDK MCP: Locator.wait_for: waiting for locator("#aitdk-iframe") to be visible')
    assert transient_aitdk_error('AITDK MCP: waiting for Created Date')
    assert transient_aitdk_error('AITDK MCP: AITDK 未在规定时间内返回流量数据')
    assert not transient_aitdk_error('AITDK MCP: Page.goto: net::ERR_CONNECTION_CLOSED')
    assert not transient_aitdk_error('domain registration date unavailable')


def test_transient_aitdk_retries_only_requeues_matching_errors() -> None:
    first = ProductCandidate('1', 'First', '', 'https://ph/1', 'https://first.test', 'first.test', '2026-09-07T00:00:00Z', 0)
    second = ProductCandidate('2', 'Second', '', 'https://ph/2', 'https://second.test', 'second.test', '2026-09-07T00:00:00Z', 0)
    calls = []

    async def collector(_day, _limit, products):
        calls.append([product.product_id for product in products])
        if len(calls) == 1:
            return [
                {'product': first, 'status': 'error', 'reason': 'AITDK MCP: waiting for Created Date', 'panel': {}},
                {'product': second, 'status': 'error', 'reason': 'AITDK MCP: Page.goto: net::ERR_CONNECTION_CLOSED', 'panel': {}},
            ]
        return [{'product': first, 'status': 'excluded', 'reason': 'too old', 'panel': {}}]

    async def no_wait(_seconds):
        return None

    records = asyncio.run(collect_transient_aitdk_retries(
        date(2026, 9, 7), [first, second], rounds=3, collector=collector, sleeper=no_wait,
    ))

    assert calls == [['1', '2'], ['1']]
    assert [(record['product'].product_id, record['status']) for record in records] == [('1', 'excluded'), ('2', 'error')]
