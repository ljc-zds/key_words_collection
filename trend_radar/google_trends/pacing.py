"""Serialize operations and retain their cooldown across client/process restarts."""
from contextlib import contextmanager
import fcntl
import hashlib
import math
import os
from pathlib import Path
import random
import time


@contextmanager
def operation_slot(cdp_url):
    minimum = float(os.environ.get('GOOGLE_TRENDS_OPERATION_MIN_WAIT', '5'))
    maximum = float(os.environ.get('GOOGLE_TRENDS_OPERATION_MAX_WAIT', '5'))
    if not (math.isfinite(minimum) and math.isfinite(maximum) and 0 <= minimum <= maximum):
        raise ValueError('Trends operation wait must satisfy 0 <= minimum <= maximum')
    root = Path(os.environ.get('GOOGLE_TRENDS_PACING_DIR',
                str(Path(__file__).resolve().parents[2] / 'runtime' / 'google-trends-pacing')))
    root.mkdir(parents=True, exist_ok=True)
    name = hashlib.sha256(cdp_url.rstrip('/').encode()).hexdigest()[:16] + '.state'
    # The lock covers loading, waiting, the entire browser operation, and cleanup.
    # Its timestamp contains no queries, cookies, or tokens.
    with (root / name).open('a+', encoding='utf-8') as state:
        fcntl.flock(state, fcntl.LOCK_EX)
        try:
            state.seek(0)
            text = state.read().strip()
            try:
                ready_at = float(text) if text else 0
                if not math.isfinite(ready_at):
                    raise ValueError('Invalid cooldown')
            except ValueError:
                ready_at = time.time() + maximum
            remaining = ready_at - time.time()
            while remaining > 0:
                time.sleep(min(remaining, 60))
                remaining = ready_at - time.time()
            try:
                yield
            finally:
                ready_at = time.time() + random.uniform(minimum, maximum)
                state.seek(0)
                state.truncate()
                state.write(str(ready_at))
                state.flush()
                os.fsync(state.fileno())
        finally:
            fcntl.flock(state, fcntl.LOCK_UN)
