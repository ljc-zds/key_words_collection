"""New URL-loaded page first; classic API second; stop if neither supplies data."""
import sys

from .browser_api import BrowserApiGoogleTrendsClient
from .page_ui import PageUrlGoogleTrendsClient
from .errors import TrendsRateLimited, MissingTrendsData
from .pacing import operation_slot


class CollectionStopped(Exception):
    """Terminal for this run; deliberately not a retryable RuntimeError."""


class FallbackGoogleTrendsClient:
    def __init__(self, cdp_url='http://127.0.0.1:9229', *, primary=None, fallback=None):
        self.cdp_url = cdp_url
        self.primary = primary if primary is not None else PageUrlGoogleTrendsClient(cdp_url)
        self.fallback = fallback if fallback is not None else BrowserApiGoogleTrendsClient(cdp_url)
        self.last_backend = None
        self._stop_reason = None

    def _request(self, method, args, valid):
        if self._stop_reason:
            raise CollectionStopped(self._stop_reason)
        failures = []
        partial = False
        for name, source in [('new_url', self.primary), ('classic', self.fallback)]:
            with operation_slot(self.cdp_url):
                if self._stop_reason:
                    raise CollectionStopped(self._stop_reason)
                try:
                    data = getattr(source, method)(*args)
                    if not valid(data):
                        raise RuntimeError('No usable data returned')
                    self.last_backend = name
                    return data
                except TrendsRateLimited as error:
                    self._stop_reason = f'采集已停止：{name} {method} {args[0]!r} 遇到明确限制：{error}'
                    raise CollectionStopped(self._stop_reason) from error
                except (RuntimeError, ValueError, KeyError, TypeError) as error:
                    failures.append(f'{name}: {error}')
                    if name == 'new_url':
                        partial = bool(getattr(self.primary, 'partial_success', False))
                        message = ('新版部分成功，已保存返回数据，等待操作间隔后用旧版补齐：'
                                   if partial else '新版取数失败，等待操作间隔后回退旧版：')
                        print(message + str(error), file=sys.stderr, flush=True)
                    else:
                        if partial:
                            message = f'{method} {args[0]!r} 部分成功；缺失数据旧版未补齐，记录待重试并继续。' + '; '.join(failures)
                            print(message, file=sys.stderr, flush=True)
                            raise MissingTrendsData(message) from error
                        self._stop_reason = f'采集已停止：{method} {args[0]!r} 新版和旧版均未取得有效数据。' + '; '.join(failures)
                        raise CollectionStopped(self._stop_reason) from error

    def related_rising_all(self, term, timeframe='today 1-m'):
        return self._request('related_rising_all', (term, timeframe), lambda rows: isinstance(rows, list) and bool(rows))

    def related_rising(self, term, timeframe='today 1-m'):
        return [r for r in self.related_rising_all(term, timeframe)
                if r['type'] == 'Breakout' or r.get('growth_percent', 0) >= 500]

    def compare_batch(self, candidates, baseline='gpts', timeframe='today 1-m'):
        if not 1 <= len(candidates) <= 4:
            raise ValueError('compare_batch accepts one to four candidates')
        def valid(result):
            return isinstance(result, dict) and all(
                c in result and len(result[c]) == 3 and len(result[c][0]) >= 2
                and len(result[c][0]) == len(result[c][1]) == len(result[c][2]) for c in candidates)
        return self._request('compare_batch', (candidates, baseline, timeframe), valid)

    def compare(self, candidate, baseline='gpts', timeframe='today 1-m'):
        return self.compare_batch([candidate], baseline, timeframe)[candidate]
