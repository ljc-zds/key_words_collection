"""End-to-end local Product Hunt demand radar."""

import argparse
import asyncio
import json
import os
from dataclasses import asdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Callable
from product_hunt import storage
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse

from product_hunt.aitdk.domain.demand_filter import FilterResult, evaluate_candidate
from product_hunt.aitdk.cdp.cdp import resolve_redirect_via_cdp
from product_hunt.aitdk.protocol.client import AitdkMcpError, domain_enrich, ensure_cdp_available, resolve_url, traffic_panel
from product_hunt.aitdk.product.product_hunt import ProductCandidate, fetch_posts_for_date, load_developer_token
from product_hunt.aitdk.legacy.tabapi import fetch_public_rdap, registration_date
from write_feishu_batch import SHEET_ID, SPREADSHEET_TOKEN, load_env, request_json, tenant_token


REJECTED = ('producthunt.com', 'apps.apple.com', 'play.google.com')
CHECKPOINT_DIRECTORY = Path('runtime/product-hunt-checkpoints')
RETRY_SKIP_DIRECTORY = Path('runtime/product-hunt-retry-skip')


def domain_age_days(registered: str | None) -> int | None:
    if not registered:
        return None
    try:
        created = datetime.strptime(registered, '%Y-%m-%d').replace(tzinfo=timezone.utc)
    except ValueError:
        return None
    return (datetime.now(timezone.utc) - created).days


def public_registration_date(domain: str) -> str | None:
    """Use free RDAP only when AITDK does not include a Whois creation date."""
    try:
        return registration_date(fetch_public_rdap(domain))
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError, ValueError):
        return None


def apply_registration_result(row: dict, registered: str | None) -> None:
    """Finish the age and traffic filter once a registration date is available."""
    panel = row['panel']
    panel['registered'] = registered
    age = domain_age_days(registered)
    row['age'] = age
    if age is None:
        row['reason'] = 'domain registration date unavailable'
        row['status'] = 'no_data'
    elif age > 365:
        row['status'] = 'excluded'
        row['reason'] = 'domain age exceeds 365 days'
    elif panel['status'] == 'missing':
        row['reason'] = 'AITDK has no traffic data'
        row['status'] = failure_status(row['reason'])
    else:
        traffic = {
            'overview': {'visits': panel['monthly_visits'] or 0},
            'trafficSources': {
                'searchOrganic': panel['search_share'] or 0,
                'direct': panel['direct_share'] or 0,
            },
        }
        result = evaluate_candidate(row['domain'], row['product'].name, traffic, age, panel['keywords'])
        row['filter'] = result
        row['status'] = 'passed' if result.passed else 'excluded'
        row['reason'] = '; '.join(result.reasons)


def failure_status(reason: str) -> str:
    if reason == 'AITDK has no traffic data':
        return 'no_data'
    if reason == 'no independent official website':
        return 'no_website'
    return 'error'


def retryable_aitdk_error(reason: object) -> bool:
    """Only retry the requested AITDK iframe, Whois, and traffic failures."""
    text = cell_key(reason)
    return text.startswith('AITDK MCP:') and any(
        marker in text for marker in (
            'Created Date',
            'locator("#aitdk-iframe")',
            '未在规定时间内返回流量数据',
            'query timed out',
        )
    )


def transient_aitdk_error(reason: object) -> bool:
    """Classify the three single-site AITDK failures that may recover on retry."""
    return retryable_aitdk_error(reason)


def default_collection_date(today_utc: date | None = None) -> date:
    return (today_utc or datetime.now(timezone.utc).date()) - timedelta(days=1)


def load_products(
    collection_date: date,
    token: str,
    *,
    cache_directory: Path = Path('runtime/product-hunt-cache'),
    fetcher=fetch_posts_for_date,
) -> list[ProductCandidate]:
    cache_file = cache_directory / f'{collection_date.isoformat()}.json'
    if cache_file.is_file():
        cached = json.loads(cache_file.read_text(encoding='utf-8'))
        # Empty caches can come from transient API/network failures; retry
        # instead of suppressing an entire day's launches permanently.
        if cached:
            return [ProductCandidate(**item) for item in cached]
    products = fetcher(token, collection_date)
    cache_directory.mkdir(parents=True, exist_ok=True)
    temporary = cache_file.with_suffix('.tmp')
    temporary.write_text(json.dumps([asdict(product) for product in products], ensure_ascii=False), encoding='utf-8')
    temporary.replace(cache_file)
    return products


async def collect(
    collection_date: date,
    limit: int | None = None,
    products: list[ProductCandidate] | None = None,
    on_record: Callable[[dict], None] | None = None,
) -> list[dict]:
    if products is None:
        products = load_products(collection_date, load_developer_token(Path('.env')))
    if limit is not None:
        products = products[:limit]
    output: list[dict] = []
    rdap_limit = asyncio.Semaphore(8)
    pending_rdap: list[asyncio.Task[dict]] = []

    async def complete_rdap(row: dict) -> dict:
        async with rdap_limit:
            registered = await asyncio.to_thread(public_registration_date, row['domain'])
        apply_registration_result(row, registered)
        if on_record is not None:
            on_record(row)
        return row

    for index, product in enumerate(products, 1):
        row = {'product': product, 'status': 'error', 'reason': '', 'panel': {}}
        try:
            website = product.website_url
            initial_host = (urlparse(website).hostname or '').lower()
            if initial_host == 'producthunt.com' or initial_host.endswith('.producthunt.com'):
                try:
                    website = resolve_url(website)
                except (HTTPError, URLError, TimeoutError):
                    website = await resolve_redirect_via_cdp(website)
            hostname = (urlparse(website).hostname or '').lower()
            row['website'], row['domain'] = website, hostname
            if not hostname or any(hostname == host or hostname.endswith('.' + host) for host in REJECTED):
                row['reason'] = 'no independent official website'
                row['status'] = failure_status(row['reason'])
            else:
                panel = traffic_panel(await asyncio.to_thread(domain_enrich, hostname))
                row['panel'] = panel
                # AITDK Whois is the first date source. RDAP is deliberately
                # deferred so an empty Whois panel never pauses browser work.
                registered = panel['registered']
                if registered is None:
                    row['status'] = 'no_data'
                    row['reason'] = 'domain registration date unavailable (RDAP pending)'
                    pending_rdap.append(asyncio.create_task(complete_rdap(row)))
                else:
                    apply_registration_result(row, registered)
        except AitdkMcpError as error:
            row['reason'] = f'AITDK MCP: {error}'
            row['status'] = failure_status(row['reason'])
        except Exception as error:
            row['reason'] = type(error).__name__
            row['status'] = failure_status(row['reason'])
        output.append(row)
        if on_record is not None:
            on_record(row)
        print(f"[{index}/{len(products)}] {product.name}: {row['status']} - {row['reason']}", flush=True)
    for future in asyncio.as_completed(pending_rdap):
        row = await future
        if on_record is not None:
            on_record(row)
    return output


async def collect_transient_aitdk_retries(
    collection_date: date,
    products: list[ProductCandidate],
    *,
    rounds: int = 3,
    collector: Callable = collect,
    sleeper: Callable = asyncio.sleep,
    checkpoint_directory: Path | None = None,
) -> list[dict]:
    """Retry only the requested transient AITDK failures with increasing pauses."""
    pending = list(products)
    latest: dict[str, dict] = {}
    for attempt in range(1, rounds + 1):
        if not pending:
            break
        print(f"AITDK transient retry round {attempt}/{rounds}: {len(pending)} products", flush=True)
        records = await collect_retry_round(
            collection_date, pending, collector=collector,
            checkpoint=(checkpoint_directory / f'round-{attempt}.json')
            if checkpoint_directory is not None else None,
        )
        for record in records:
            latest[record['product'].product_hunt_url] = record
        pending = [record['product'] for record in records if transient_aitdk_error(record['reason'])]
        if pending and attempt < rounds:
            await sleeper(attempt * 10)
    return [latest[product.product_hunt_url] for product in products if product.product_hunt_url in latest]


async def collect_retry_round(collection_date, products, *, collector=collect, checkpoint=None):
    """Persist each result atomically; resume only unfinished work in this round."""
    if checkpoint is None:
        return await collector(collection_date, None, products)
    saved = json.loads(checkpoint.read_text(encoding='utf-8')) if checkpoint.is_file() else []
    records = {}
    for item in saved:
        item['product'] = ProductCandidate(**item['product'])
        if item.get('filter'):
            item['filter'] = FilterResult(**item['filter'])
        records[product_key(item['product'])] = item

    def persist(record):
        records[product_key(record['product'])] = record
        storage.upsert(sheet_rows([record])[1:])
        checkpoint.parent.mkdir(parents=True, exist_ok=True)
        temporary = checkpoint.with_name(f'.{checkpoint.name}.{os.getpid()}.tmp')
        temporary.write_text(json.dumps(list(records.values()), default=asdict,
                                        ensure_ascii=False, indent=2), encoding='utf-8')
        temporary.replace(checkpoint)

    pending = [product for product in products if product_key(product) not in records
               or records[product_key(product)]['reason'].endswith('(RDAP pending)')]
    print(f'retry checkpoint: {len(products) - len(pending)} saved, {len(pending)} remaining', flush=True)
    await collector(collection_date, None, pending, on_record=persist)
    return [records[product_key(product)] for product in products]


def sheet_rows(records: list[dict]) -> list[list[object]]:
    rows: list[list[object]] = [[
        '产品', '描述', '关注度', '域名', '来源', 'MRR', '发布日期', '注册日期',
        '域名年龄（天）', '搜索访问量', '总访问量', '3个月访问趋势', '搜索占比',
        '直接占比', '非品牌关键词（搜索量）', '状态', '错误/排除原因',
        '来源链接', '原始链接', '真实官网',
    ]]
    for record in records:
        product, panel = record['product'], record.get('panel') or {}
        visits = panel.get('monthly_visits')
        search_share = panel.get('search_share')
        search_visits = round(visits * search_share) if visits is not None and search_share is not None else ''
        result = record.get('filter')
        keywords = result.non_brand_keywords if result else []
        keyword_volumes = {
            item.get('name'): item.get('volume')
            for item in panel.get('keywords', [])
            if isinstance(item.get('name'), str)
        }
        keyword_text = ', '.join(
            f"{keyword} ({keyword_volumes[keyword]:,})"
            if isinstance(keyword_volumes.get(keyword), (int, float))
            else keyword
            for keyword in keywords
        )
        trend = ' → '.join(
            f"{item.get('month')}: {item.get('visits', 0):,}"
            for item in panel.get('monthly_visits_trend', [])
        )
        rows.append([
            product.name, product.tagline, '', record.get('domain', ''), 'Product Hunt', '',
            product.created_at[:10], panel.get('registered') or '', record.get('age', ''),
            search_visits, visits if visits is not None else '', trend,
            f"{search_share:.2%}" if search_share is not None else '',
            f"{panel['direct_share']:.2%}" if panel.get('direct_share') is not None else '',
            keyword_text, 'Success' if record['status'] == 'passed' else record['status'],
            record['reason'], product.product_hunt_url, product.website_url, record.get('website', ''),
        ])
    return rows


def sheet_column(number: int) -> str:
    label = ''
    while number:
        number, remainder = divmod(number - 1, 26)
        label = chr(65 + remainder) + label
    return label


def merge_retry_rows(existing: list[list[object]], replacements: list[list[object]]) -> list[list[object]]:
    replacement_by_source = {cell_key(row[17]): row for row in replacements if len(row) > 17}
    return [existing[0]] + [replacement_by_source.get(cell_key(row[17]), row) for row in existing[1:]]


def cell_key(value: object) -> str:
    if isinstance(value, list):
        for item in value:
            if isinstance(item, dict):
                link = item.get('link')
                if isinstance(link, str) and link:
                    return link
                text = item.get('text')
                if isinstance(text, str) and text:
                    return text
        return ''
    return str(value) if value is not None else ''


def product_key(product: ProductCandidate) -> tuple[str, str]:
    return product.created_at[:10], product.product_hunt_url


def row_key(row: list[object]) -> tuple[str, str] | None:
    if len(row) <= 17:
        return None
    published, source = cell_key(row[6]), cell_key(row[17])
    return (published, source) if published and source else None


def filter_unseen_products(
    products: list[ProductCandidate],
    existing_keys: set[tuple[str, str]],
) -> list[ProductCandidate]:
    seen_keys = set(existing_keys)
    unseen: list[ProductCandidate] = []
    for product in products:
        key = product_key(product)
        if key in seen_keys:
            continue
        seen_keys.add(key)
        unseen.append(product)
    return unseen


def checkpoint_file(collection_date: date, directory: Path = CHECKPOINT_DIRECTORY) -> Path:
    return directory / f'{collection_date.isoformat()}.json'


def retry_skip_file(collection_date: date) -> Path:
    return RETRY_SKIP_DIRECTORY / f'{collection_date.isoformat()}.json'


def load_checkpoint_rows(path: Path) -> list[list[object]]:
    if not path.is_file():
        return []
    rows = json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(rows, list) or not all(isinstance(row, list) for row in rows):
        raise RuntimeError(f'invalid checkpoint: {path}')
    return rows


def save_checkpoint_rows(path: Path, rows: list[list[object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    # Include the process id so overlapping/manual runs cannot clobber each other's temp file.
    temporary = path.with_name(f'.{path.name}.{os.getpid()}.tmp')
    temporary.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding='utf-8')
    temporary.replace(path)


def read_feishu_rows(token: str, end_column: str) -> list[list[object]]:
    current = request_json(
        f'https://open.feishu.cn/open-apis/sheets/v2/spreadsheets/{SPREADSHEET_TOKEN}/values/{SHEET_ID}!A1:{end_column}',
        method='GET', token=token,
    )
    if current.get('code') != 0:
        raise RuntimeError('Feishu read failed')
    return current.get('data', {}).get('valueRange', {}).get('values', [])


def read_feishu_keys() -> set[tuple[str, str]]:
    token = tenant_token(load_env())
    return {key for row in read_feishu_rows(token, 'T')[1:] if (key := row_key(row)) is not None}


def merge_daily_rows(
    existing: list[list[object]],
    incoming: list[list[object]],
    *,
    replace_duplicates: bool = False,
) -> list[list[object]]:
    if not existing:
        return incoming
    merged = [list(existing[0])]
    index_by_key = {}
    for row in existing[1:]:
        key = row_key(row)
        if key is not None and key in index_by_key:
            continue
        if key is not None:
            index_by_key[key] = len(merged)
        merged.append(list(row))
    for row in incoming[1:]:
        key = row_key(row)
        if key in index_by_key:
            if replace_duplicates:
                merged[index_by_key[key]] = row
            continue
        if key is not None:
            index_by_key[key] = len(merged)
        merged.append(row)
    return merged


def pad_rows_for_overwrite(rows: list[list[object]], previous_row_count: int) -> list[list[object]]:
    if len(rows) >= previous_row_count:
        return rows
    column_count = len(rows[0])
    return rows + [[''] * column_count for _ in range(previous_row_count - len(rows))]


def write_feishu(rows: list[list[object]], *, replace_duplicates: bool = False) -> None:
    token = tenant_token(load_env())
    end_column = sheet_column(len(rows[0]))
    existing = read_feishu_rows(token, end_column)
    merged = merge_daily_rows(existing, rows, replace_duplicates=replace_duplicates)
    values = pad_rows_for_overwrite(merged, len(existing))
    end_row = len(values)
    base = f'https://open.feishu.cn/open-apis/sheets/v2/spreadsheets/{SPREADSHEET_TOKEN}'
    metadata = request_json(
        f'https://open.feishu.cn/open-apis/sheets/v3/spreadsheets/{SPREADSHEET_TOKEN}/sheets/query',
        method='GET', token=token)
    if metadata.get('code') != 0:
        raise RuntimeError(f'Feishu metadata failed: {metadata.get("code")} {metadata.get("msg")}')
    sheet = next(s for s in metadata['data']['sheets'] if s['sheet_id'] == SHEET_ID)
    capacity = sheet['grid_properties']['row_count']
    if end_row > capacity:
        result = request_json(base + '/dimension_range', method='POST', token=token,
            payload={'dimension': {'sheetId': SHEET_ID, 'majorDimension': 'ROWS',
                                   'startIndex': capacity, 'endIndex': end_row},
                     'inheritStyle': 'BEFORE'})
        if result.get('code') != 0:
            raise RuntimeError(f'Feishu resize failed: {result.get("code")} {result.get("msg")}')
    for offset in range(0, end_row, 500):
        batch = values[offset:offset + 500]
        result = request_json(base + '/values', method='PUT', token=token,
            payload={'valueRange': {'range': f'{SHEET_ID}!A{offset + 1}:{end_column}{offset + len(batch)}',
                                    'values': batch}})
        if result.get('code') != 0:
            raise RuntimeError(f'Feishu write failed at row {offset + 1}: {result.get("code")} {result.get("msg")}')


async def run(collection_date: date, limit: int | None, skip_feishu: bool, retry_errors: bool = False, retry_aitdk_errors: bool = False) -> None:
    # Do not turn a browser outage into hundreds of misleading per-product failures.
    ensure_cdp_available()
    report_file = Path('runtime/product_hunt_daily.json')
    if retry_errors or retry_aitdk_errors:
        existing = [sheet_rows([])[0]] + storage.rows_for_date(collection_date)
        error_sources = {
            cell_key(row[17]) for row in existing[1:]
            if row[15] == 'error' and cell_key(row[17])
            and (not retry_aitdk_errors or retryable_aitdk_error(row[16]))
        }
        skip_path = retry_skip_file(collection_date)
        completed_sources = set() if retry_aitdk_errors else (
            set(json.loads(skip_path.read_text(encoding='utf-8'))) if skip_path.is_file() else set()
        )
        products = load_products(collection_date, load_developer_token(Path('.env')))
        retry_products = [product for product in products if product.product_hunt_url in error_sources - completed_sources]
        retry_directory = Path('runtime/product-hunt-retry-checkpoints') / collection_date.isoformat() / ('aitdk' if retry_aitdk_errors else 'all')
        if limit is not None:
            retry_products = retry_products[:limit]
        records = (
            await collect_transient_aitdk_retries(collection_date, retry_products, checkpoint_directory=retry_directory)
            if retry_aitdk_errors else await collect_retry_round(collection_date, retry_products, checkpoint=retry_directory / 'round-1.json')
        )
        rows = merge_retry_rows(existing, sheet_rows(records)[1:])
    else:
        header = sheet_rows([])[0]
        checkpoint = checkpoint_file(collection_date)
        checkpoint_rows = load_checkpoint_rows(checkpoint)
        checkpoint_keys = {key for row in checkpoint_rows if (key := row_key(row)) is not None}
        products = load_products(collection_date, load_developer_token(Path('.env')))
        existing_keys = storage.keys()
        before_filter = len(products)
        products = filter_unseen_products(products, existing_keys | checkpoint_keys)
        print(f"skipped {before_filter - len(products)} existing products before AITDK (SQLite)", flush=True)

        def persist_record(record: dict) -> None:
            row = sheet_rows([record])[1]
            storage.upsert([row])
            checkpoint_rows[:] = merge_daily_rows(
                [header] + checkpoint_rows,
                [header, row],
                replace_duplicates=True,
            )[1:]
            save_checkpoint_rows(checkpoint, checkpoint_rows)

        records = await collect(collection_date, limit, products, persist_record)
        # Finish the fast pass first; retry only this day's saved AITDK errors.
        if limit is None:
            error_keys = {row_key(row) for row in checkpoint_rows
                          if row[15] == 'error' and retryable_aitdk_error(row[16])}
            retry_products = [p for p in load_products(collection_date, load_developer_token(Path('.env')))
                              if product_key(p) in error_keys]
            for attempt in range(1, 3):
                if not retry_products:
                    break
                print(f'post-pass AITDK retry {attempt}/2: {len(retry_products)} products', flush=True)
                retried = await collect(collection_date, None, retry_products, persist_record)
                records.extend(retried)
                retry_products = [r['product'] for r in retried if retryable_aitdk_error(r['reason'])]
        rows = [header] + checkpoint_rows
    if not records and not rows[1:] and retry_errors is False and retry_aitdk_errors is False:
        print(f"no products found for {collection_date.isoformat()}; preserving existing local report", flush=True)
        return
    Path('runtime').mkdir(exist_ok=True)
    report_file.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding='utf-8')
    if rows[1:]:
        storage.upsert(rows[1:])
        if retry_errors or retry_aitdk_errors:
            if retry_directory.exists():
                archived = retry_directory.with_name(retry_directory.name + '-completed-' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%f'))
                retry_directory.rename(archived)
        else:
            checkpoint.unlink(missing_ok=True)
    print(f"completed: {len(records)} products, {sum(row[15] == 'Success' for row in rows[1:])} passed", flush=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--date', type=date.fromisoformat, default=default_collection_date())
    parser.add_argument('--limit', type=int)
    parser.add_argument('--skip-feishu', action='store_true', help='Compatibility flag; all runs now use local SQLite only')
    parser.add_argument('--retry-errors', action='store_true')
    parser.add_argument('--retry-aitdk-errors', action='store_true')
    args = parser.parse_args()
    asyncio.run(run(args.date, args.limit, args.skip_feishu, args.retry_errors, args.retry_aitdk_errors))


if __name__ == '__main__':
    main()
