import pytest


@pytest.fixture(autouse=True)
def no_delays(monkeypatch, tmp_path):
    monkeypatch.setenv('GOOGLE_TRENDS_MIN_INTERVAL', '0')
    monkeypatch.setenv('GOOGLE_TRENDS_OPERATION_MIN_WAIT', '0')
    monkeypatch.setenv('GOOGLE_TRENDS_OPERATION_MAX_WAIT', '0')
    monkeypatch.setenv('GOOGLE_TRENDS_PACING_DIR', str(tmp_path))


def test_new_failure_falls_back_once_and_latches_stop():
    from trend_radar.google_trends.fallback import FallbackGoogleTrendsClient, CollectionStopped
    calls = []
    class Source:
        def __init__(self, name): self.name = name
        def related_rising_all(self, *args):
            calls.append(self.name)
            return []
    client = FallbackGoogleTrendsClient(primary=Source('new'), fallback=Source('old'))
    with pytest.raises(CollectionStopped): client.related_rising('action')
    with pytest.raises(CollectionStopped): client.related_rising('next')
    assert calls == ['new', 'old']


def test_old_success_is_returned_after_new_failure():
    from trend_radar.google_trends.fallback import FallbackGoogleTrendsClient
    class New:
        def compare_batch(self, *args): raise RuntimeError('timeout')
    class Old:
        def compare_batch(self, *args): return {'a': (['1', '2'], [0, 3], [2, 2])}
    client = FallbackGoogleTrendsClient(primary=New(), fallback=Old())
    assert client.compare('a') == (['1', '2'], [0, 3], [2, 2])
    assert client.last_backend == 'classic'


def test_new_success_does_not_call_old():
    from trend_radar.google_trends.fallback import FallbackGoogleTrendsClient
    class Source:
        def related_rising_all(self, *args):
            return [{'query': 'slow', 'type': 'rising', 'growth_percent': 100}]
    class Old:
        def related_rising_all(self, *args): raise AssertionError('must not call old')
    client = FallbackGoogleTrendsClient(primary=Source(), fallback=Old())
    assert client.related_rising('action') == []  # Valid data, none passes the threshold.


@pytest.mark.parametrize('stage', ['rising', 'comparison'])
def test_both_failed_stops_scan_and_saves_pending_parent(stage):
    from trend_radar.google_trends.fallback import CollectionStopped
    from trend_radar.pipeline import scan_roots
    calls = []; snapshots = []; failed = {}
    previous = {'candidate': 'done', 'root': 'root', 'parent_keyword': 'root', 'depth': 1,
                'comparison': {'is_new_word': False}}
    class Client:
        def related_rising(self, term):
            calls.append(term)
            if stage == 'rising': raise CollectionStopped('new and old unavailable')
            return [{'query': 'new term', 'type': 'Breakout', 'growth_percent': None}]
        def compare_batch(self, *args): raise CollectionStopped('new and old unavailable')
    with pytest.raises(CollectionStopped):
        scan_roots(['root', 'never-run'], Client(), existing_records=[previous], failed_parents=failed,
                   on_checkpoint=lambda records, completed, pending: snapshots.append(list(records)))
    assert calls == ['root']
    assert snapshots[-1] == [previous]
    assert failed['root']['parent_keyword'] == 'root'


def test_stop_keeps_previous_unavailable_record():
    from trend_radar.google_trends.fallback import CollectionStopped
    from trend_radar.pipeline import scan_roots
    old = {'candidate': 'retry me', 'root': 'root', 'parent_keyword': 'root', 'depth': 1,
           'comparison': {'is_new_word': False, 'status': 'unavailable'}}
    saved = []
    class Client:
        def related_rising(self, term): return [{'query': 'retry me', 'type': 'Breakout', 'growth_percent': None}]
        def compare_batch(self, *args): raise CollectionStopped('both failed')
    with pytest.raises(CollectionStopped):
        scan_roots(['root'], Client(), existing_records=[old],
                   on_checkpoint=lambda r, c, f: saved.append(list(r)))
    assert saved[-1] == [old]


def test_explicit_rate_limit_stops_without_trying_old():
    from trend_radar.google_trends.fallback import FallbackGoogleTrendsClient, CollectionStopped
    from trend_radar.google_trends.errors import TrendsRateLimited
    class New:
        def related_rising_all(self, *args): raise TrendsRateLimited('HTTP 429')
    class Old:
        def related_rising_all(self, *args): raise AssertionError('must stop immediately')
    client = FallbackGoogleTrendsClient(primary=New(), fallback=Old())
    with pytest.raises(CollectionStopped, match='429'):
        client.related_rising('action')


def test_partial_success_missing_component_is_retryable_not_terminal():
    from trend_radar.google_trends.fallback import FallbackGoogleTrendsClient
    from trend_radar.google_trends.errors import MissingTrendsData
    class New:
        partial_success = True
        def related_rising_all(self, *args): raise RuntimeError('only timeline available')
    class Old:
        def related_rising_all(self, *args): return []
    client = FallbackGoogleTrendsClient(primary=New(), fallback=Old())
    for term in ['first', 'next']:
        with pytest.raises(MissingTrendsData): client.related_rising(term)
    assert client._stop_reason is None


def test_partial_missing_comparison_checkpoints_and_continues_without_immediate_retry():
    from trend_radar.google_trends.errors import MissingTrendsData
    from trend_radar.pipeline import scan_roots
    calls = []
    rising = {}; failed = {}; snapshots = []
    class Client:
        def related_rising(self, term):
            calls.append(('rising', term))
            if term == 'missing': raise MissingTrendsData('only timeline')
            return [{'query': 'child', 'type': 'Breakout'}] if term == 'root' else []
        def compare_batch(self, terms, baseline):
            calls.append(('compare', terms))
            raise MissingTrendsData('only rising')
        def compare(self, *args): raise AssertionError('must defer, not retry immediately')
    records = scan_roots(['missing', 'root', 'next'], Client(), parent_rising=rising,
                         failed_parents=failed, on_checkpoint=lambda r,c,f: snapshots.append(list(r)))
    assert records[0]['comparison']['status'] == 'unavailable'
    assert ('rising', 'next') in calls
    assert 'missing' in failed and 'root' in failed
    assert rising['root']['qualified_rising_queries'][0]['query'] == 'child'
    assert snapshots[-1] == records


def test_saved_rising_is_reused_when_retrying_missing_comparison():
    from trend_radar.pipeline import scan_roots
    rising = {'root': {'qualified_rising_queries': [{'query': 'child', 'type': 'Breakout'}]}}
    class Client:
        def related_rising(self, *args): raise AssertionError('already saved')
        def compare_batch(self, terms, baseline):
            return {'child': ([str(i) for i in range(30)], [1] * 30, [2] * 30)}
    records = scan_roots(['root'], Client(), parent_rising=rising, max_depth=1)
    assert records[0]['candidate'] == 'child'
    assert 'status' not in records[0]['comparison']


def test_partial_success_does_not_override_old_rate_limit():
    from trend_radar.google_trends.fallback import FallbackGoogleTrendsClient, CollectionStopped
    from trend_radar.google_trends.errors import TrendsRateLimited
    class New:
        partial_success = True
        def related_rising_all(self, *args): raise RuntimeError('only timeline available')
    class Old:
        def related_rising_all(self, *args): raise TrendsRateLimited('HTTP 429')
    client = FallbackGoogleTrendsClient(primary=New(), fallback=Old())
    with pytest.raises(CollectionStopped, match='429'): client.related_rising('action')
