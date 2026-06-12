# src/etl/extractors/pfr/roster.py

from bs4 import BeautifulSoup

from etl.extractors.base import Extractor
from etl.utils.http import rate_limited
from etl.utils.fetcher import get_pfr_fetcher


class PFRRosterExtractor(Extractor):
    """
    Fetch /teams/{team_code}/{season}_roster.htm.

    Like the draft pages, PFR fronts roster pages with a Cloudflare managed JS
    challenge, so we fetch via the configured strategy (scraping API by default,
    or a real browser in fetch_mode='browser'). The fetcher is created lazily so
    merely constructing this extractor doesn't spin one up.
    """

    def __init__(self, settings):
        self.base_url = str(settings.pfr_base_url).rstrip("/")
        self._settings = settings
        self._fetcher = None

    @property
    def fetcher(self):
        if self._fetcher is None:
            self._fetcher = get_pfr_fetcher(self._settings)
        return self._fetcher

    @rate_limited(max_calls=18, period=60.0)
    def fetch(self, season: int, team_code: str) -> BeautifulSoup:
        url = f"{self.base_url}/teams/{team_code}/{season}_roster.htm"
        print(f"Fetching PFR roster for {team_code} ({season}) from {url}")
        return self.fetcher.get_soup(url, wait_for_id="roster")

    def __del__(self):
        fetcher = getattr(self, "_fetcher", None)
        if fetcher is not None:
            fetcher.quit()
