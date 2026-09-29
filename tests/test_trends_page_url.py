import io
import json
from collections import deque
from urllib.parse import parse_qs, urlparse

import pytest


@pytest.fixture(autouse=True)
def isolated_cache(monkeypatch, tmp_path):
    monkeypatch.setenv('GOOGLE_TRENDS_PAGE_CACHE', str(tmp_path / 'page-cache'))


def transport(monkeypatch, status=200, empty_first=False, empty_always=False, timeline_after_refresh=False):
    from trend_radar.google_trends import page_ui as module
    calls = []
    payload = [[["action", [["new action", 800, 8]]]]]
    body = json.dumps([["wrb.fr", "fXqlme", json.dumps(payload)]])
    clock = [0.0]
    monkeypatch.setattr(module.time, 'monotonic', lambda: clock[0])

    class Socket:
        def __init__(self, browser=False):
            self.browser = browser
            self.messages = deque()
        def send(self, text):
            msg = json.loads(text)
            method = msg['method']
            calls.append((method, msg.get('params', {})))
            result = {}
            if method == 'Target.createTarget': result = {'targetId': 'owned'}
            if method in ('Page.navigate', 'Page.reload'):
                calls.append(('load_at', clock[0]))
                # Events may arrive before navigation's command acknowledgment.
                self.messages.extend([
                    {'method': 'Network.responseReceived', 'params': {'requestId': 'rpc', 'response': {
                        'status': status, 'url': 'https://trends.google.com/_/TrendsUi/data/batchexecute'}}},
                    {'method': 'Network.loadingFinished', 'params': {'requestId': 'rpc'}}])
            if method == 'Network.getResponseBody':
                refreshed = any(m == 'Page.reload' for m, _ in calls)
                result = {'body': json.dumps([["wrb.fr", "fXqlme", "[]"]])
                          if empty_always or (empty_first and not refreshed) else body}
                if timeline_after_refresh and refreshed:
                    timeline = [[[
                        ['action', None, None, 1, [[0, 3, [[100], [200]]], [0, 6, [[200], [300]]]]],
                        ['gpts', None, None, 1, [[0, 4, [[100], [200]]], [0, 5, [[200], [300]]]]],
                    ]]]
                    result = {'body': json.dumps([['wrb.fr', 'g4kJzf', json.dumps(timeline)]])}
            if method.startswith('Input.') or method == 'Runtime.evaluate':
                raise AssertionError('URL loading must not depend on DOM controls or clicks')
            self.messages.append({'id': msg['id'], 'result': result})
        def recv(self):
            if not self.messages:
                clock[0] += 1
                raise module.websocket.WebSocketTimeoutException()
            return json.dumps(self.messages.popleft())
        def close(self): pass
        def settimeout(self, timeout): pass

    browser, page = Socket(True), Socket()
    monkeypatch.setattr(module.websocket, 'create_connection', lambda url, **kw: browser if url == 'ws://browser' else page)
    monkeypatch.setattr(module, 'urlopen', lambda url, **kw: io.StringIO(json.dumps(
        {'webSocketDebuggerUrl': 'ws://browser'} if url.endswith('/version') else
        [{'id': 'owned', 'webSocketDebuggerUrl': 'ws://page'}])))
    monkeypatch.setattr(module.time, 'sleep', lambda seconds: calls.append(('sleep', seconds)))
    monkeypatch.setattr(module.PageUiGoogleTrendsClient, '_throttle', lambda self: None)
    return module.PageUiGoogleTrendsClient(), calls


def test_url_query_captures_data_without_clicks_and_dwells_before_close(monkeypatch):
    client, calls = transport(monkeypatch)
    rows = client.related_rising_all('action')
    assert rows[0]['query'] == 'new action'
    methods = [method for method, _ in calls]
    assert not any(method.startswith('Input.') or method in ('Runtime.evaluate', 'Page.reload') for method in methods)
    assert methods.index('Network.enable') < methods.index('Page.navigate')
    url = next(params['url'] for method, params in calls if method == 'Page.navigate')
    assert urlparse(url).path == '/explore'
    assert parse_qs(urlparse(url).query) == {'q': ['action,gpts'], 'date': ['today 1-m']}
    sleeps = [(i, seconds) for i, (method, seconds) in enumerate(calls) if method == 'sleep']
    assert any(seconds == 10 and i < methods.index('Target.closeTarget') for i, seconds in sleeps)
    assert next(params for method, params in calls if method == 'Target.createTarget')['background'] is True


@pytest.mark.parametrize('status', [429, 403])
def test_url_restriction_closes_owned_page_without_retry(monkeypatch, status):
    from trend_radar.google_trends.errors import TrendsRateLimited
    client, calls = transport(monkeypatch, status)
    with pytest.raises(TrendsRateLimited): client.related_rising_all('action')
    methods = [method for method, _ in calls]
    assert methods.count('Page.navigate') == 1
    assert methods.count('Target.closeTarget') == 1
    assert 'Page.reload' not in methods


def test_empty_response_waits_60_seconds_then_refreshes_same_page(monkeypatch):
    client, calls = transport(monkeypatch, empty_first=True)
    assert client.related_rising_all('action')[0]['query'] == 'new action'
    methods = [m for m, _ in calls]
    assert [t for m, t in calls if m == 'load_at'] == [0, 60]
    assert methods.count('Target.createTarget') == 1
    assert methods.count('Page.reload') == 1


def test_double_timeout_stops_after_one_refresh(monkeypatch):
    client, calls = transport(monkeypatch, empty_always=True)
    with pytest.raises(RuntimeError, match='wait limit'):
        client.related_rising_all('action')
    methods = [m for m, _ in calls]
    assert [t for m, t in calls if m == 'load_at'] == [0, 60]
    assert methods.count('Page.reload') == 1
    assert methods.count('Target.closeTarget') == 1
    from trend_radar.google_trends import page_ui
    assert page_ui.time.monotonic() == 120


def test_rising_response_does_not_complete_timeline_wait(monkeypatch):
    client, calls = transport(monkeypatch, timeline_after_refresh=True)
    assert client.compare('action') == (['100', '200'], [3, 6], [4, 5])
    assert [t for m, t in calls if m == 'load_at'] == [0, 60]


def test_partial_rising_survives_missing_timeline_and_client_restart(monkeypatch):
    client, calls = transport(monkeypatch)
    with pytest.raises(RuntimeError):
        client.compare('action')
    assert client.partial_success is True
    calls.clear()
    from trend_radar.google_trends.page_ui import PageUrlGoogleTrendsClient
    restored = PageUrlGoogleTrendsClient()
    assert restored.related_rising_all('action')[0]['query'] == 'new action'
    assert not calls  # Valid saved Rising must not issue another browser request.
