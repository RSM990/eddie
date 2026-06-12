# src/etl/utils/fetcher.py
from __future__ import annotations


def get_pfr_fetcher(settings):
    """
    Return a PFR page fetcher matching ``settings.fetch_mode`` (DEC-005).

    Both fetchers expose the same interface — ``get_soup(url, wait_for_id=None)``
    and ``quit()`` — so extractors don't care which one they got:
      - ``"api"``     -> ScraperClient   (default; vendor browser + residential IPs)
      - ``"browser"`` -> SeleniumFetcher (real Chrome; local dev / attached session)

    Imports are deferred so that, e.g., API-mode containers never import Selenium.
    """
    mode = (getattr(settings, "fetch_mode", "api") or "api").lower()
    if mode == "browser":
        from etl.utils.selenium_client import SeleniumFetcher
        return SeleniumFetcher()
    if mode == "api":
        from etl.utils.scraper_client import ScraperClient
        return ScraperClient(settings)
    raise ValueError(f"Unknown fetch_mode: {mode!r} (expected 'api' or 'browser')")
