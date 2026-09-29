import pytest


def test_wait_is_shared_across_instances_and_starts_after_completion(tmp_path, monkeypatch):
    from trend_radar.google_trends import pacing
    clock = [1000.0]
    sleeps = []
    monkeypatch.setenv('GOOGLE_TRENDS_PACING_DIR', str(tmp_path))
    monkeypatch.setattr(pacing.time, 'time', lambda: clock[0])
    def sleep(seconds):
        sleeps.append(seconds)
        clock[0] += seconds
    monkeypatch.setattr(pacing.time, 'sleep', sleep)
    def sample(low, high):
        assert (low, high) == (5, 5)
        return 5
    monkeypatch.setattr(pacing.random, 'uniform', sample)
    with pacing.operation_slot('http://127.0.0.1:9229'):
        clock[0] += 20  # Includes request and page cleanup.
    assert float(next(tmp_path.glob('*.state')).read_text()) == 1025
    with pacing.operation_slot('http://127.0.0.1:9229'):
        assert clock[0] == 1025
    assert sleeps == [5]


def test_failed_attempt_also_schedules_wait(tmp_path, monkeypatch):
    from trend_radar.google_trends import pacing
    monkeypatch.setenv('GOOGLE_TRENDS_PACING_DIR', str(tmp_path))
    clock = [1000.0]
    monkeypatch.setattr(pacing.time, 'time', lambda: clock[0])
    monkeypatch.setattr(pacing.time, 'sleep', lambda n: clock.__setitem__(0, clock[0] + n))
    with pytest.raises(RuntimeError):
        with pacing.operation_slot('http://127.0.0.1:9229'):
            raise RuntimeError('new failed')
    with pacing.operation_slot('http://127.0.0.1:9229'):
        assert clock[0] == 1005


def test_same_chrome_operations_cannot_overlap(tmp_path, monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Event
    from trend_radar.google_trends import pacing
    monkeypatch.setenv('GOOGLE_TRENDS_PACING_DIR', str(tmp_path))
    monkeypatch.setenv('GOOGLE_TRENDS_OPERATION_MIN_WAIT', '0')
    monkeypatch.setenv('GOOGLE_TRENDS_OPERATION_MAX_WAIT', '0')
    first_entered, release, second_entered = Event(), Event(), Event()
    def first():
        with pacing.operation_slot('http://127.0.0.1:9229'):
            first_entered.set()
            assert release.wait(3)
    def second():
        with pacing.operation_slot('http://127.0.0.1:9229'):
            second_entered.set()
    with ThreadPoolExecutor(max_workers=2) as pool:
        a = pool.submit(first)
        assert first_entered.wait(2)
        b = pool.submit(second)
        try:
            assert not second_entered.wait(0.1)
        finally:
            release.set()
        a.result(timeout=3)
        b.result(timeout=3)
    assert second_entered.is_set()
