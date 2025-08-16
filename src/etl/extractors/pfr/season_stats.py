# src/etl/extractors/pfr/season.py

from __future__ import annotations

from typing import Dict
from bs4 import BeautifulSoup
from etl.extractors.pfr.http import PFRHttpClient


class PFRSeasonExtractor:
    """
    Tiny, concrete extractor (like the boxscore extractor) that fetches the
    season-level pages per category. Keeps all HTTP going through the
    rate-limited PFRHttpClient.
    """

    CATEGORY_URLS: Dict[str, str] = {
        "passing":   "https://www.pro-football-reference.com/years/{year}/passing.htm",
        "rushing":   "https://www.pro-football-reference.com/years/{year}/rushing.htm",
        "receiving": "https://www.pro-football-reference.com/years/{year}/receiving.htm",
        "returns":   "https://www.pro-football-reference.com/years/{year}/returns.htm",
        "scoring":   "https://www.pro-football-reference.com/years/{year}/scoring.htm",
        "kicking":   "https://www.pro-football-reference.com/years/{year}/kicking.htm",
        "defense":   "https://www.pro-football-reference.com/years/{year}/defense.htm",  # IDP
    }

    def __init__(self, client: PFRHttpClient | None = None) -> None:
        # If caller passed the wrong thing (e.g., Settings), fall back to a real client.
        if client is None or not hasattr(client, "get_soup"):
            self.client = PFRHttpClient()
        else:
            self.client = client


    def fetch(self, year: int, category: str) -> BeautifulSoup:
        cat = category.lower().strip()
        if cat not in self.CATEGORY_URLS:
            raise ValueError(f"Unknown season category: {category}")
        url = self.CATEGORY_URLS[cat].format(year=int(year))
        return self.client.get_soup(url)
