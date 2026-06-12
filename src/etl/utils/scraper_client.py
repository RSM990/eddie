# src/etl/utils/scraper_client.py
from __future__ import annotations

from typing import Optional, Tuple

import requests
from bs4 import BeautifulSoup


class ScraperClient:
    """
    Fetch Cloudflare-gated PFR pages through a scraping API (DEC-005).

    The vendor runs a real browser behind residential IPs and returns rendered
    HTML, so eddie itself needs no browser — the extractors just make HTTP calls.
    ``get_soup()`` mirrors ``SeleniumFetcher``'s signature so extractors are
    agnostic to which fetch strategy ``fetch_mode`` selects.

    Provider request shapes are kept in ``_build_request``; add a branch to
    support another vendor. The ``wait_for_id`` maps to the provider's
    "wait for this CSS selector before returning" param so the target table is
    rendered (and the challenge solved) before the HTML comes back.
    """

    def __init__(self, settings, session: Optional[requests.Session] = None):
        self.provider = (getattr(settings, "scraper_provider", "scraperapi") or "scraperapi").lower()
        self.api_key = getattr(settings, "scraper_api_key", None)
        self.render_js = bool(getattr(settings, "scraper_render_js", True))
        self.timeout = float(getattr(settings, "scraper_timeout", 90.0))
        if not self.api_key:
            raise ValueError(
                "scraper_api_key is required when fetch_mode='api'. Set SCRAPER_API_KEY, "
                "or use fetch_mode='browser' to scrape with a local/attached Chrome."
            )
        self.session = session or requests.Session()

    def _build_request(self, url: str, wait_for_id: Optional[str]) -> Tuple[str, dict]:
        sel = f"#{wait_for_id}" if wait_for_id else None

        if self.provider == "scraperapi":
            params = {"api_key": self.api_key, "url": url}
            if self.render_js:
                params["render"] = "true"
            # ultra_premium engages the hardest anti-bot path (Cloudflare managed challenge).
            params["ultra_premium"] = "true"
            if sel:
                params["wait_for_selector"] = sel
            return "https://api.scraperapi.com/", params

        if self.provider == "zenrows":
            params = {"apikey": self.api_key, "url": url, "antibot": "true", "premium_proxy": "true"}
            if self.render_js:
                params["js_render"] = "true"
            if sel:
                params["wait_for"] = sel
            return "https://api.zenrows.com/v1/", params

        if self.provider == "scrapingbee":
            params = {"api_key": self.api_key, "url": url, "stealth_proxy": "true"}
            if self.render_js:
                params["render_js"] = "true"
            if sel:
                params["wait_for"] = sel
            return "https://app.scrapingbee.com/api/v1/", params

        raise ValueError(f"Unknown scraper_provider: {self.provider!r}")

    def get_soup(self, url: str, wait_for_id: Optional[str] = None) -> BeautifulSoup:
        endpoint, params = self._build_request(url, wait_for_id)
        resp = self.session.get(endpoint, params=params, timeout=self.timeout)
        resp.raise_for_status()
        return BeautifulSoup(resp.text, "html.parser")

    def quit(self) -> None:
        # Parity with SeleniumFetcher so callers can close either fetcher uniformly.
        try:
            self.session.close()
        except Exception:
            pass

    def __del__(self):
        self.quit()
