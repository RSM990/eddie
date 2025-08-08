# src/etl/extractors/pfr/games.py
from __future__ import annotations

from bs4 import BeautifulSoup, Comment
import cloudscraper

from etl.extractors.base import Extractor
from etl.utils.http import rate_limited


class PFRGamesExtractor(Extractor):
    """
    Fetch /years/{season}/games.htm and return soup with the real <table id="games">
    injected even when PFR hides it inside HTML comments.
    """
    def __init__(self, settings):
        self.scraper  = cloudscraper.create_scraper(
            browser={"custom": settings.user_agent}
        )
        self.base_url = f"{settings.pfr_base_url}/years"

    @rate_limited(max_calls=20, period=60.0)
    def fetch(self, season: int) -> BeautifulSoup:

        url  = f"{self.base_url}/{season}/games.htm"

        print (f"Fetching games from {url}...")
        resp = self.scraper.get(url)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        # If table is commented out, pull from comments and insert it.
        if not soup.find("table", id="games"):
            for c in soup.find_all(string=lambda t: isinstance(t, Comment)):
                if 'table id="games"' in c:
                    commented = BeautifulSoup(c, "html.parser")
                    table = commented.find("table", id="games")
                    if table:
                        placeholder = soup.find(id="div_games")
                        (placeholder or soup).insert(0, table)
                        break

        return soup
