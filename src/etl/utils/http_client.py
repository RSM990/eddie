from __future__ import annotations

import time, random
from typing import Optional
import requests
from bs4 import BeautifulSoup

from etl.config import Settings
from etl.utils.rate_limiter import RateLimiter


DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Connection": "keep-alive",
}


class PFRHttpClient:
    """HTTP client for PFR with polite rate limiting and simple retry/backoff."""

    def __init__(
        self,
        settings: Settings,
        *,
        timeout_sec: Optional[int] = None,
        min_interval_sec: Optional[float] = None,
        max_retries: int = 3,
        backoff_base: float = 2.0,
        session: Optional[requests.Session] = None,
    ) -> None:
        self.session = session or requests.Session()
        self.session.headers.update(DEFAULT_HEADERS)
        # allow override via settings/.env
        ua = getattr(settings, "pfr_user_agent", None) or getattr(settings, "USER_AGENT", None)
        if ua:
            self.session.headers["User-Agent"] = ua

        self.timeout = timeout_sec or getattr(settings, "http_timeout_sec", 30)
        interval = (
            min_interval_sec
            if min_interval_sec is not None
            else float(getattr(settings, "pfr_min_interval_sec", 1.5))
        )
        self.limiter = RateLimiter(min_interval=interval, jitter=0.2)
        self.max_retries = max_retries
        self.backoff_base = backoff_base

    def get(self, url: str) -> requests.Response:
        """GET with rate limit + retry on 429/503/403."""
        last_exc: Optional[Exception] = None
        for attempt in range(1, self.max_retries + 1):
            with self.limiter():
                try:
                    resp = self.session.get(url, timeout=self.timeout)
                except Exception as exc:
                    last_exc = exc
                    # brief backoff on network error
                    time.sleep(self._backoff_seconds(attempt))
                    continue

            # success
            if resp.status_code == 200:
                return resp

            # retry-worthy codes
            if resp.status_code in (429, 503, 403):
                wait = self._retry_after_or_backoff(resp, attempt)
                time.sleep(wait)
                last_exc = RuntimeError(f"HTTP {resp.status_code} on {url}")
                continue

            # other errors: raise immediately
            resp.raise_for_status()

        if last_exc:
            raise last_exc
        raise RuntimeError(f"Failed to fetch {url} after {self.max_retries} attempts")

    def get_soup(self, url: str, parser: str = "lxml") -> BeautifulSoup:
        html = self.get(url).text
        return BeautifulSoup(html, parser)

    # ---- internals ----
    def _retry_after_or_backoff(self, resp: requests.Response, attempt: int) -> float:
        ra = resp.headers.get("Retry-After")
        if ra:
            try:
                return max(float(ra), self._backoff_seconds(attempt))
            except ValueError:
                pass
        return self._backoff_seconds(attempt)

    def _backoff_seconds(self, attempt: int) -> float:
        base = self.backoff_base ** (attempt - 1)
        return base + random.uniform(0, 0.5)

    def close(self) -> None:
        try:
            self.session.close()
        except Exception:
            pass
