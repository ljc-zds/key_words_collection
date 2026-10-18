"""Fetch classic Trends widget data inside a persistent, logged-in Chrome profile."""
from __future__ import annotations

import json
import os
import random
import time
from contextlib import suppress
from pathlib import Path
from cdp_transport import cdp_urlopen as urlopen, cdp_websocket

import websocket

from .parsing import parse_timeline_values
from .errors import TrendsRateLimited


class BrowserApiGoogleTrendsClient:
    def __init__(self, cdp_url='http://127.0.0.1:9229', timeout_ms=30_000):
        self.cdp_url = cdp_url.rstrip('/')
        self.timeout_ms = timeout_ms
        self._last_finished = 0.0
        self._blocked_until = 0.0

    def _pause_seconds(self):
        return max(0, float(os.environ.get('GOOGLE_TRENDS_MIN_INTERVAL', '10'))) + random.uniform(
            0, max(0, float(os.environ.get('GOOGLE_TRENDS_JITTER', '5'))))

    def _fetch_widget(self, terms, timeframe, identifier, path):
        now = time.monotonic()
        if now < self._blocked_until:
            raise RuntimeError('Google Trends requests paused after rate limiting; retry later')
        time.sleep(max(0, self._last_finished + self._pause_seconds() - now))
        browser = page = None
        target_id = None
        try:
            with urlopen(self.cdp_url + '/json/version', timeout=5) as response:
                info = json.load(response)
            browser = cdp_websocket(info['webSocketDebuggerUrl'], timeout=5, suppress_origin=True)
            # A real same-origin page is required; never create about:blank or activate it.
            browser.send(json.dumps({'id': 1, 'method': 'Target.createTarget', 'params': {
                'url': 'https://trends.google.com/trends/', 'background': True}}))
            while True:
                message = json.loads(browser.recv())
                if message.get('id') == 1:
                    target_id = message.get('result', {}).get('targetId')
                    break
            if not target_id:
                raise RuntimeError('Could not create background Trends page')
            with urlopen(self.cdp_url + '/json/list', timeout=5) as response:
                target = next((t for t in json.load(response) if t['id'] == target_id), None)
            if not target or not target.get('webSocketDebuggerUrl'):
                raise RuntimeError('Trends page CDP endpoint missing')
            page = cdp_websocket(target['webSocketDebuggerUrl'], timeout=1, suppress_origin=True)
            seq = 0

            def command(method, params, deadline):
                nonlocal seq
                seq += 1
                page.send(json.dumps({'id': seq, 'method': method, 'params': params}))
                while time.monotonic() < deadline:
                    try:
                        msg = json.loads(page.recv())
                    except websocket.WebSocketTimeoutException:
                        continue
                    if msg.get('id') == seq:
                        if 'error' in msg or msg.get('result', {}).get('exceptionDetails'):
                            raise RuntimeError('Trends page evaluation failed')
                        return msg.get('result', {}).get('result', {}).get('value')
                raise RuntimeError('Trends page evaluation timed out')

            deadline = time.monotonic() + self.timeout_ms / 1000
            while time.monotonic() < deadline:
                ready = command('Runtime.evaluate', {'expression':
                    "location.origin==='https://trends.google.com' && document.readyState!=='loading'",
                    'returnByValue': True}, deadline)
                if ready:
                    break
                time.sleep(0.2)
            else:
                raise RuntimeError('Trends page did not load; existing login profile retained')
            pause_ms = int(self._pause_seconds() * 1000)
            args = json.dumps([terms, timeframe, identifier, path, self.timeout_ms, pause_ms])
            script = Path(__file__).with_suffix('.js').read_text(encoding='utf-8')
            result = command('Runtime.evaluate', {
                'expression': script + '\ntrendsWidget(...' + args + ')',
                'awaitPromise': True, 'returnByValue': True,
            }, time.monotonic() + (2 * self.timeout_ms + pause_ms) / 1000 + 5)
            if not isinstance(result, dict):
                raise RuntimeError('Trends browser request returned no result')
            if result.get('error'):
                if result.get('status') in (429, 403):
                    self._blocked_until = time.monotonic() + max(300, result.get('retryAfter', 0))
                    raise TrendsRateLimited(result['error'])
                raise RuntimeError(result['error'])
            if not isinstance(result.get('data'), dict):
                raise RuntimeError('Trends widget returned invalid data')
            return result['data']
        except (OSError, ValueError, websocket.WebSocketException) as error:
            raise RuntimeError('Trends Chrome connection failed; retry with the same profile') from error
        finally:
            self._last_finished = time.monotonic()
            if page:
                with suppress(Exception):
                    page.close()
            if browser:
                if target_id:
                    with suppress(Exception):
                        browser.send(json.dumps({'id': 2, 'method': 'Target.closeTarget', 'params': {'targetId': target_id}}))
                        browser.settimeout(3)
                        while json.loads(browser.recv()).get('id') != 2:
                            pass
                with suppress(Exception):
                    browser.close()

    def related_rising_all(self, term, timeframe='today 1-m'):
        payload = self._fetch_widget([term], timeframe, 'RELATED_QUERIES', 'relatedsearches')
        groups = payload.get('default', {}).get('rankedList')
        if not isinstance(groups, list) or len(groups) < 2 or not isinstance(groups[1].get('rankedKeyword'), list):
            raise RuntimeError('Trends Rising data missing; parent remains retryable')
        result = {}
        for item in groups[1]['rankedKeyword']:
            query = str(item.get('query', '')).strip()
            if not query:
                continue
            if str(item.get('formattedValue', item.get('value', ''))).lower() == 'breakout':
                row = {'query': query, 'type': 'Breakout', 'growth_percent': None}
            else:
                growth = item.get('value')
                if not isinstance(growth, (int, float)):
                    raise RuntimeError('Trends Rising growth value missing')
                row = {'query': query, 'type': 'rising', 'growth_percent': int(growth)}
            result[query.lower()] = row
        return list(result.values())

    def related_rising(self, term, timeframe='today 1-m'):
        return [row for row in self.related_rising_all(term, timeframe)
                if row['type'] == 'Breakout' or row['growth_percent'] >= 500]

    def compare_batch(self, candidates, baseline='gpts', timeframe='today 1-m'):
        if not 1 <= len(candidates) <= 4:
            raise ValueError('compare_batch accepts one to four candidates')
        terms = [*candidates, baseline]
        payload = self._fetch_widget(terms, timeframe, 'TIMESERIES', 'multiline')
        raw = payload.get('default', {}).get('timelineData')
        if not isinstance(raw, list) or len(raw) < 2 or any(
            not isinstance(point.get('value'), list) or len(point['value']) != len(terms)
            or not point.get('time') or any(not isinstance(v, (int, float)) for v in point['value'])
            for point in raw
        ):
            raise RuntimeError('Trends comparison missing aligned series; retry later')
        times, rows = parse_timeline_values(payload)
        return {candidate: (times, [row[index] for row in rows], [row[-1] for row in rows])
                for index, candidate in enumerate(candidates)}

    def compare(self, candidate, baseline='gpts', timeframe='today 1-m'):
        return self.compare_batch([candidate], baseline, timeframe)[candidate]
