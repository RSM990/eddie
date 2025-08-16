from __future__ import annotations
import threading, time, random
from contextlib import contextmanager

class RateLimiter:
    """Simple per-request minimum-interval limiter with optional jitter."""
    def __init__(self, min_interval: float = 1.5, jitter: float = 0.2) -> None:
        self.min_interval = float(min_interval)
        self.jitter = float(jitter)
        self._lock = threading.Lock()
        self._last = 0.0

    @contextmanager
    def __call__(self):
        with self._lock:
            now = time.time()
            wait = self.min_interval - (now - self._last)
            if wait > 0:
                wait += random.uniform(0, self.jitter)
                time.sleep(wait)
            self._last = time.time()
        yield
