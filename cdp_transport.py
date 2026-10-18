"""Keep local Chrome control traffic out of the operating system's web proxy."""
from ipaddress import ip_address
from urllib import request
from urllib.error import URLError
from urllib.parse import urlsplit



def is_loopback_url(url):
    host = urlsplit(url).hostname
    if host == 'localhost':
        return True
    try:
        return ip_address(host).is_loopback
    except ValueError:
        return False


class _LoopbackRedirectsOnly(request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if not is_loopback_url(newurl):
            raise URLError('Local CDP redirect outside loopback refused')
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def cdp_urlopen(url, *args, **kwargs):
    raw_url = url.full_url if isinstance(url, request.Request) else url
    if not is_loopback_url(raw_url):
        return request.urlopen(url, *args, **kwargs)
    opener = request.build_opener(request.ProxyHandler({}), _LoopbackRedirectsOnly())
    return opener.open(url, *args, **kwargs)


def cdp_websocket(url, *args, **kwargs):
    import websocket

    if is_loopback_url(url):
        # websocket-client reads macOS system proxies independently of urllib.
        # Restrict the exception to the actual local CDP address.
        kwargs['http_no_proxy'] = [urlsplit(url).hostname]
    return websocket.create_connection(url, *args, **kwargs)
