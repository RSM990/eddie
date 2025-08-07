from bs4 import BeautifulSoup
import cloudscraper
from etl.extractors.base import Extractor
from etl.utils.http import rate_limited, get_session

class PFRPlayersExtractor(Extractor):
    def __init__(self, settings):
        self.scraper = cloudscraper.create_scraper(
            browser={"custom": settings.user_agent}
        )
        # we'll hit /players/A/ … /players/Z/
        self.base_url = f"{settings.pfr_base_url}/players"

    @rate_limited(max_calls=30, period=60.0)
    def fetch_letter_page(self, letter: str) -> BeautifulSoup:
        url  = f"{self.base_url}/{letter}/"
        resp = self.scraper.get(url)
        resp.raise_for_status()
        return BeautifulSoup(resp.text, "html.parser")
