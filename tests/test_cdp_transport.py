"""Local CDP must remain reachable when macOS installs a web proxy."""
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread
from urllib.error import URLError

import pytest
import cdp_transport
import websocket


@contextmanager
def server(handler):
    httpd = ThreadingHTTPServer(('127.0.0.1', 0), handler)
    thread = Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        yield f'http://127.0.0.1:{httpd.server_port}'
    finally:
        httpd.shutdown()
        httpd.server_close()
        thread.join()


def test_loopback_http_ignores_configured_proxy(monkeypatch):
    proxy_hits = []
    class Origin(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200); self.end_headers(); self.wfile.write(b'{"Browser":"test"}')
        def log_message(self, *_): pass
    class Proxy(BaseHTTPRequestHandler):
        def do_GET(self):
            proxy_hits.append(self.path)
            self.send_response(502); self.end_headers()
        def log_message(self, *_): pass
    with server(Origin) as origin, server(Proxy) as proxy:
        # getproxies is also where urllib exposes macOS system proxy settings.
        monkeypatch.setattr(cdp_transport.request, 'getproxies', lambda: {'http': proxy})
        monkeypatch.setattr(cdp_transport.request, 'proxy_bypass', lambda _: False)
        with cdp_transport.cdp_urlopen(origin + '/json/version', timeout=2) as response:
            assert response.read() == b'{"Browser":"test"}'
    assert proxy_hits == []


@pytest.mark.parametrize('url', ['http://127.0.0.2:9229/json/version', 'http://localhost:9229', 'ws://[::1]:9229/devtools/browser/x'])
def test_loopback_detection(url):
    assert cdp_transport.is_loopback_url(url)


@pytest.mark.parametrize('url', ['https://trends.google.com', 'http://localhost.example.com', 'ws://192.168.1.2:9229', 'http://127.0.0.1.example.com'])
def test_nonloopback_keeps_default_proxy_behavior(monkeypatch, url):
    calls = []
    monkeypatch.setattr(cdp_transport.request, 'urlopen', lambda *a, **kw: calls.append((a, kw)) or 'default')
    monkeypatch.setattr(cdp_transport.request, 'build_opener', lambda *_: pytest.fail('public URL bypassed proxy'))
    assert cdp_transport.cdp_urlopen(url, timeout=3) == 'default'
    assert calls == [((url,), {'timeout': 3})]


def test_websocket_bypass_is_limited_to_loopback(monkeypatch):
    calls = []
    monkeypatch.setattr(websocket, 'create_connection', lambda *a, **kw: calls.append((a, kw)))
    cdp_transport.cdp_websocket('ws://127.0.0.1:9229/x', timeout=2)
    cdp_transport.cdp_websocket('wss://remote.example/x', timeout=2)
    assert calls[0][1]['http_no_proxy'] == ['127.0.0.1']
    assert calls[1][1] == {'timeout': 2}


def test_local_redirect_cannot_disable_proxy_for_public_url():
    with pytest.raises(URLError, match='outside loopback'):
        cdp_transport._LoopbackRedirectsOnly().redirect_request(None, None, 302, '', {}, 'https://example.com/')
