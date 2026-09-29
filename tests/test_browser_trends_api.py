import pytest
import json
import shutil
import subprocess
from pathlib import Path
from trend_radar.cli import build_client


def test_default_client_uses_new_ui_with_browser_api_fallback():
    assert type(build_client('http://127.0.0.1:9229')).__name__ == 'FallbackGoogleTrendsClient'


def client_with_payload(monkeypatch, payload):
    from trend_radar.google_trends.browser_api import BrowserApiGoogleTrendsClient
    client = BrowserApiGoogleTrendsClient()
    monkeypatch.setattr(client, '_fetch_widget', lambda *args: payload)
    return client


def test_rising_excludes_top_and_preserves_numeric_breakout(monkeypatch):
    client = client_with_payload(monkeypatch, {'default': {'rankedList': [
        {'rankedKeyword': [{'query': 'top only', 'value': 100}]},
        {'rankedKeyword': [
            {'query': 'new tool', 'value': 5000, 'formattedValue': 'Breakout'},
            {'query': 'fast tool', 'value': 700, 'formattedValue': '+700%'},
            {'query': 'slow tool', 'value': 50, 'formattedValue': '+50%'},
        ]},
    ]}})
    assert client.related_rising_all('tool') == [
        {'query': 'new tool', 'type': 'Breakout', 'growth_percent': None},
        {'query': 'fast tool', 'type': 'rising', 'growth_percent': 700},
        {'query': 'slow tool', 'type': 'rising', 'growth_percent': 50},
    ]
    assert [r['query'] for r in client.related_rising('tool')] == ['new tool', 'fast tool']


@pytest.mark.parametrize('payload', [{}, {'default': {}}, {'default': {'rankedList': []}}])
def test_missing_rising_is_retryable_error(monkeypatch, payload):
    with pytest.raises(RuntimeError):
        client_with_payload(monkeypatch, payload).related_rising_all('action')


def test_batch_aligns_baseline_and_preserves_zero(monkeypatch):
    client = client_with_payload(monkeypatch, {'default': {'timelineData': [
        {'time': '100', 'value': [5, 8, 0]}, {'time': '200', 'value': [9, 4, 2]},
    ]}})
    assert client.compare_batch(['a', 'b']) == {
        'a': (['100', '200'], [5, 9], [0, 2]),
        'b': (['100', '200'], [8, 4], [0, 2]),
    }


@pytest.mark.parametrize('rows', [[], [{'time': '100', 'value': [9]}, {'time': '200', 'value': [8]}]])
def test_missing_baseline_is_not_zero_filled(monkeypatch, rows):
    with pytest.raises(RuntimeError):
        client_with_payload(monkeypatch, {'default': {'timelineData': rows}}).compare('a')


def test_page_fetch_uses_widget_token_without_returning_it():
    node = shutil.which('node')
    if not node:
        pytest.skip('Node required for page JavaScript test')
    source = Path('trend_radar/google_trends/browser_api.js').read_text()
    test = r'''
const assert = require('node:assert/strict');
const calls = [];
global.fetch = async (url, options) => {
  assert.equal(options.credentials, 'same-origin');
  const u = new URL(url, 'https://trends.google.com'); calls.push(u.pathname);
  if (u.pathname === '/trends/api/explore') {
    assert.deepEqual(JSON.parse(u.searchParams.get('req')).comparisonItem.map(x => x.keyword), ['a', 'gpts']);
    return new Response(")]}'\n" + JSON.stringify({widgets:[{id:'TIMESERIES',request:{resolution:'DAY'},token:'private-widget-token'}]}));
  }
  assert.equal(u.pathname, '/trends/api/widgetdata/multiline');
  assert.equal(u.searchParams.get('token'), 'private-widget-token');
  return new Response(")]}'\n" + JSON.stringify({default:{timelineData:[{time:'1',value:[2,3]}]}}));
};
(async()=>{
 const result = await trendsWidget(['a','gpts'],'today 1-m','TIMESERIES','multiline',1000,0);
 assert.deepEqual(result,{data:{default:{timelineData:[{time:'1',value:[2,3]}]}}});
 assert.equal(calls.length,2);
 assert.ok(!JSON.stringify(result).includes('private-widget-token'));
 global.fetch = async () => new Response('private failure body',{status:429,headers:{'Retry-After':'600'}});
 const error = await trendsWidget(['a'],'today 1-m','RELATED_QUERIES','relatedsearches',1000,0);
 assert.equal(error.status,429);assert.equal(error.retryAfter,600);
 assert.ok(!JSON.stringify(error).includes('private failure body'));
})().catch(e=>{console.error(e);process.exitCode=1});
'''
    result = subprocess.run([node, '-e', source + '\n' + test], capture_output=True, text=True, timeout=10)
    assert result.returncode == 0, result.stderr


def test_rate_limit_closes_owned_target_and_blocks_further_network(monkeypatch):
    import io
    from trend_radar.google_trends import browser_api as api
    calls = []
    def get(url, **kwargs):
        calls.append(url)
        data = {'webSocketDebuggerUrl': 'ws://browser'} if url.endswith('/json/version') else [
            {'id': 'owned-target', 'webSocketDebuggerUrl': 'ws://page'}]
        return io.StringIO(json.dumps(data))
    class Socket:
        def __init__(self): self.messages = []; self.closed = False
        def send(self, text): self.messages.append(json.loads(text))
        def recv(self):
            m = self.messages[-1]
            if m['method'] == 'Target.createTarget': result = {'targetId': 'owned-target'}
            elif m['method'] == 'Target.closeTarget': result = {'success': True}
            else:
                value = True if not m['params'].get('awaitPromise') else {
                    'error': 'Trends HTTP 429: explore', 'status': 429, 'retryAfter': 600}
                result = {'result': {'value': value}}
            return json.dumps({'id': m['id'], 'result': result})
        def close(self): self.closed = True
        def settimeout(self, value): pass
    browser, page = Socket(), Socket()
    monkeypatch.setattr(api, 'urlopen', get)
    monkeypatch.setattr(api.websocket, 'create_connection', lambda url, **kw: browser if url == 'ws://browser' else page)
    client = api.BrowserApiGoogleTrendsClient()
    with pytest.raises(RuntimeError, match='429'):
        client.related_rising_all('action')
    count = len(calls)
    with pytest.raises(RuntimeError, match='paused'):
        client.related_rising_all('action')
    assert len(calls) == count
    assert client._blocked_until - api.time.monotonic() > 590
    assert browser.messages[0]['params']['background'] is True
    assert browser.messages[-1]['params'] == {'targetId': 'owned-target'}
    assert browser.closed and page.closed
