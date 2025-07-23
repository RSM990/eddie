# src/etl/extractors/pfr_draft.py

from bs4 import BeautifulSoup
import cloudscraper
from etl.extractors.base import Extractor

class PFRDraftExtractor(Extractor):
    def __init__(self, settings):
        # cloudscraper handles Cloudflare JS challenges
        self.scraper  = cloudscraper.create_scraper(
            browser={"custom": settings.user_agent}
        )
        self.base_url = f"{settings.pfr_base_url}years"

    def fetch(self, year: int) -> BeautifulSoup:
        """
        Returns a BeautifulSoup tree of the /years/{year}/draft.htm page.
        """
        url  = f"{self.base_url}/{year}/draft.htm"
        resp = self.scraper.get(url)
        resp.raise_for_status()
        return BeautifulSoup(resp.text, "html.parser")
