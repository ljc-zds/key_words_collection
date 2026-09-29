"""Load parameterized new Explore pages and observe their natural responses."""
from __future__ import annotations

import json
import hashlib
import os
from pathlib import Path
import sys
import time
from collections import deque
from contextlib import suppress
from urllib.request import urlopen
from urllib.parse import urlencode

import websocket
from .errors import TrendsRateLimited

from .client import (NewCdpGoogleTrendsClient, is_new_trends_rpc_response,
                     parse_batchexecute_rpc, parse_new_rising_queries, parse_new_timeline_values)


class PageUrlGoogleTrendsClient(NewCdpGoogleTrendsClient):
    def __init__(self, cdp_url='http://127.0.0.1:9229', timeout_ms=60_000):
        super().__init__(cdp_url, timeout_ms, timeout_ms)
        self.partial_success = False

    @staticmethod
    def _usable(payload, rpc_id, terms, source):
        if rpc_id == 'fXqlme':
            return bool(parse_new_rising_queries(payload, minimum_growth=0, source_term=source))
        series = parse_new_timeline_values(payload)
        return all(term.lower() in series and len(series[term.lower()][0]) >= 2 for term in terms)

    def _capture_rpc(self, terms, rpc_id, timeframe, *, timeout_ms=None, activate_related_term=None):
        source = activate_related_term or terms[0]
        cache_root = Path(os.environ.get('GOOGLE_TRENDS_PAGE_CACHE',
                         str(Path(__file__).resolve().parents[2] / 'output' / 'trends-new-url-cache')))
        key = hashlib.sha256(json.dumps([self.cdp_url, terms, timeframe]).encode()).hexdigest()
        cache_path = cache_root / (key + '.json')
        cached = {}
        try:
            saved = json.loads(cache_path.read_text())
            for kind in ('fXqlme', 'g4kJzf'):
                if kind in saved and self._usable(saved[kind], kind, terms, source):
                    cached[kind] = saved[kind]
        except (OSError, ValueError, TypeError, KeyError):
            pass
        self.partial_success = bool(cached)
        if rpc_id in cached:
            return [cached[rpc_id]]
        url = 'https://trends.google.com/explore?' + urlencode({'q': ','.join(terms), 'date': timeframe})
        self._throttle()
        browser = page = None
        target_id = None
        wait_seconds = (timeout_ms or self.timeout_ms) / 1000
        deadline = time.monotonic() + wait_seconds
        events = deque()
        seq = 0
        def check_restriction(msg):
            if msg.get('method') == 'Network.responseReceived':
                response = msg.get('params', {}).get('response', {})
                if is_new_trends_rpc_response(response.get('url', '')) and response.get('status') in (429, 403):
                    raise TrendsRateLimited('New Explore HTTP ' + str(response['status']))
        try:
            with urlopen(self.cdp_url.rstrip('/') + '/json/version', timeout=5) as r:
                info = json.load(r)
            browser = websocket.create_connection(info['webSocketDebuggerUrl'], timeout=5, suppress_origin=True)
            browser.send(json.dumps({'id': 1, 'method': 'Target.createTarget', 'params': {
                'url': 'https://trends.google.com/trends/', 'background': True}}))
            while time.monotonic() < deadline:
                msg = json.loads(browser.recv())
                if msg.get('id') == 1:
                    target_id = msg.get('result', {}).get('targetId')
                    break
            if not target_id:
                raise RuntimeError('Could not create new Explore background page')
            with urlopen(self.cdp_url.rstrip('/') + '/json/list', timeout=5) as r:
                target = next(t for t in json.load(r) if t['id'] == target_id)
            page = websocket.create_connection(target['webSocketDebuggerUrl'], timeout=1, suppress_origin=True)

            def command(method, params=None):
                nonlocal seq
                seq += 1
                page.send(json.dumps({'id': seq, 'method': method, 'params': params or {}}))
                while time.monotonic() < deadline:
                    try:
                        msg = json.loads(page.recv())
                    except websocket.WebSocketTimeoutException:
                        continue
                    if msg.get('id') == seq:
                        if msg.get('error') or msg.get('result', {}).get('exceptionDetails'):
                            raise RuntimeError('New Explore browser operation failed: ' + method)
                        return msg.get('result', {})
                    if msg.get('method'):
                        check_restriction(msg)
                        events.append(msg)
                raise RuntimeError('New Explore timed out while waiting for ' + method)

            command('Network.enable')
            # Attach before navigation; refresh only if the requested RPC stays
            # unavailable for the full window. Never type or click controls.
            navigation = command('Page.navigate', {'url': url})
            if navigation.get('errorText'):
                raise RuntimeError('New Explore navigation failed: ' + navigation['errorText'])

            # Navigation can finish requests while CDP commands are in flight.
            # Keep those events and only accept payloads containing all requested series/source.
            response_ids = set()
            refreshed = False
            while True:
                if time.monotonic() >= deadline:
                    if refreshed:
                        break
                    refreshed = True
                    print(f'新版 {rpc_id} 等待 {wait_seconds:g} 秒无有效数据，刷新当前页一次。',
                          file=sys.stderr, flush=True)
                    events.clear()
                    response_ids.clear()
                    deadline = time.monotonic() + wait_seconds
                    command('Page.reload')
                if events:
                    msg = events.popleft()
                else:
                    try:
                        msg = json.loads(page.recv())
                    except websocket.WebSocketTimeoutException:
                        continue
                params = msg.get('params', {})
                check_restriction(msg)
                if msg.get('method') == 'Network.responseReceived':
                    response = params['response']
                    if is_new_trends_rpc_response(response.get('url', '')) and response.get('status') == 200:
                        response_ids.add(params['requestId'])
                if msg.get('method') != 'Network.loadingFinished' or params.get('requestId') not in response_ids:
                    continue
                response_ids.discard(params['requestId'])
                try:
                    body = command('Network.getResponseBody', {'requestId': params['requestId']}).get('body', '')
                except (ValueError, TypeError):
                    continue
                for kind in ('fXqlme', 'g4kJzf'):
                    try:
                        payload = parse_batchexecute_rpc(body, kind)
                        if not self._usable(payload, kind, terms, source):
                            continue
                    except (ValueError, TypeError, KeyError):
                        continue
                    self.partial_success = True
                    cached[kind] = payload
                    # Only validated trend payloads, never headers/cookies/tokens.
                    cache_root.mkdir(parents=True, exist_ok=True)
                    temporary = cache_path.with_suffix('.tmp')
                    temporary.write_text(json.dumps(cached, ensure_ascii=False))
                    os.replace(temporary, cache_path)
                if rpc_id in cached:
                    # Leave the successfully loaded page open before cleanup.
                    time.sleep(10)
                    return [cached[rpc_id]]
            raise RuntimeError('New Explore did not return usable ' + rpc_id + ' before the wait limit')
        except (OSError, websocket.WebSocketException, StopIteration) as error:
            raise RuntimeError('New Explore browser connection failed') from error
        finally:
            if page:
                with suppress(Exception): page.close()
            if browser:
                if target_id:
                    with suppress(Exception):
                        browser.send(json.dumps({'id': 2, 'method': 'Target.closeTarget', 'params': {'targetId': target_id}}))
                        browser.settimeout(3)
                        while json.loads(browser.recv()).get('id') != 2: pass
                with suppress(Exception): browser.close()


# Preserve imports used by older local diagnostics; behavior is URL-only now.
PageUiGoogleTrendsClient = PageUrlGoogleTrendsClient
