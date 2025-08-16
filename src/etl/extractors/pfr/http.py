# src/etl/extractors/pfr/http.py
from __future__ import annotations
import time
from typing import Optional
import random
import requests
from bs4 import BeautifulSoup

class PFRHttpClient:
    def __init__(self, min_delay: float = 1.0, max_delay: float = 2.0, timeout: float = 20.0):
        self.session = requests.Session()
        self.min_delay = float(min_delay)
        self.max_delay = float(max_delay)
        self.timeout   = float(timeout)
        self.last_ts   = 0.0
        # a reasonable desktop UA helps avoid being blocked
        self.session.headers.update({
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            "Accept-Language": "en-US,en;q=0.9",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Connection": "keep-alive",
        })

    def _throttle(self) -> None:
        now = time.time()
        elapsed = now - self.last_ts
        delay = random.uniform(self.min_delay, self.max_delay)
        if elapsed < delay:
            time.sleep(delay - elapsed)
        self.last_ts = time.time()

    def get_soup(self, url: str) -> BeautifulSoup:
        self._throttle()
        resp = self.session.get(url, timeout=self.timeout)
        resp.raise_for_status()
        # Use lxml if installed; otherwise fall back to html.parser
        try:
            return BeautifulSoup(resp.text, "lxml")
        except Exception:
            return BeautifulSoup(resp.text, "html.parser")
