# src/etl/extractors/pfr_draft.py

from bs4 import BeautifulSoup
from etl.extractors.base import Extractor
from etl.utils.fetcher import get_pfr_fetcher

class PFRDraftExtractor(Extractor):
    def __init__(self, settings):
        # The draft index is Cloudflare-gated; fetch via the configured strategy
        # (scraping API by default, or a real browser in fetch_mode='browser').
        self.fetcher  = get_pfr_fetcher(settings)
        self.base_url = f"{settings.pfr_base_url}years"

    def fetch(self, year: int) -> BeautifulSoup:
        """
        Returns a BeautifulSoup tree of the /years/{year}/draft.htm page.
        """
        url = f"{self.base_url}/{year}/draft.htm"
        return self.fetcher.get_soup(url, wait_for_id="drafts")

    def __del__(self):
        fetcher = getattr(self, "fetcher", None)
        if fetcher is not None:
            fetcher.quit()
