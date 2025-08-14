# src/etl/extractors/pfr/boxscores.py
from __future__ import annotations

from bs4 import BeautifulSoup, Comment
import cloudscraper

from etl.extractors.base import Extractor
from etl.utils.http import rate_limited


class PFRBoxscoreExtractor(Extractor):
    """
    Fetch a PFR box score page and ensure the key tables are present even if
    PFR hides them inside HTML comments.
    """
    TABLE_IDS = {
        "player_offense",  # passing/rushing/receiving/fumbles
        "kicking",         # PAT made (FG bins still parsed from scoring table)
        "returns",         # KR/PR
        "scoring",         # parse field-goal distances
        "player_defense",  # tackles/sacks/ints
    }

    def __init__(self, settings):
        # cloudscraper helps with Cloudflare (some PFR pages are protected)
        self.scraper = cloudscraper.create_scraper(
            browser={"custom": settings.user_agent}
        )

    # Satisfy the abstract interface expected by etl.extractors.base.Extractor
    def fetch(self, full_url: str) -> BeautifulSoup:
        return self.fetch_boxscore(full_url)

    @rate_limited(max_calls=10, period=60.0)
    def fetch_boxscore(self, full_url: str) -> BeautifulSoup:
        """
        full_url should be an absolute URL (https://www.pro-football-reference.com/boxscores/....htm)
        """
        resp = self.scraper.get(full_url)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        # If any of the tables are commented out, pull them from comments and insert into DOM.
        need = {tid for tid in self.TABLE_IDS if not soup.find("table", id=tid)}
        if need:
            for c in soup.find_all(string=lambda t: isinstance(t, Comment)):
                if any(f'id="{tid}"' in c for tid in need):
                    commented = BeautifulSoup(c, "html.parser")
                    for tid in list(need):
                        t = commented.find("table", id=tid)
                        if t:
                            placeholder = soup.find(id=f"div_{tid}")
                            (placeholder or soup).insert(0, t)
                            need.discard(tid)
                if not need:
                    break

        return soup
