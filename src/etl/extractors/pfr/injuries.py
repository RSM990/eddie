# src/etl/extractors/pfr/injuries.py
from __future__ import annotations

from bs4 import BeautifulSoup, Comment
import cloudscraper

from etl.extractors.base import Extractor
from etl.utils.http import rate_limited


class PFRInjuryExtractor(Extractor):
    """
    Fetch /players/injuries.htm and return soup with the real <table id="injuries">
    injected even when PFR hides it inside HTML comments.
    """
    def __init__(self, settings):
        # Match the games extractor pattern: build a cloudscraper with your UA
        self.scraper  = cloudscraper.create_scraper(
            browser={"custom": settings.user_agent}
        )
        self.base_url = f"{settings.pfr_base_url}"

    @rate_limited(max_calls=20, period=60.0)
    def fetch(self) -> BeautifulSoup:
        url = f"{self.base_url}/players/injuries.htm"
        print(f"Fetching injuries from {url}...")

        resp = self.scraper.get(url)
        resp.raise_for_status()

        soup = BeautifulSoup(resp.text, "html.parser")

        # If the injuries table is commented out (common on PFR), extract and insert it.
        if not soup.find("table", id="injuries"):
            for c in soup.find_all(string=lambda t: isinstance(t, Comment)):
                if 'table id="injuries"' in c:
                    commented = BeautifulSoup(c, "html.parser")
                    table = commented.find("table", id="injuries")
                    if table:
                        placeholder = soup.find(id="div_injuries")
                        (placeholder or soup).insert(0, table)
                        break

        return soup
