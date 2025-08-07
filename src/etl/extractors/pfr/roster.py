# src/etl/extractors/pfr/nfl_rosters.py

from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from etl.extractors.base import Extractor
from etl.utils.http    import rate_limited

class PFRRosterExtractor(Extractor):
    def __init__(self, settings, use_selenium: bool = True):
        self.base_url     = settings.pfr_base_url
        self.use_selenium = use_selenium

        if self.use_selenium:
            opts = Options()
            opts.add_argument("--headless")
            opts.add_argument("--disable-gpu")
            opts.add_argument("--no-sandbox")
            opts.add_argument("--window-size=1920,1080")
            # inject your user‑agent so you don’t get blocked
            opts.add_argument(f"user-agent={settings.user_agent}")
            self.driver = webdriver.Chrome(service=Service(), options=opts)
            # wait up to 15s for the table to appear
            self.wait   = WebDriverWait(self.driver, 15)

    @rate_limited(max_calls=30, period=60.0)
    def fetch(self, season: int, team_code: str) -> BeautifulSoup:
        url = f"{self.base_url}/teams/{team_code}/{season}_roster.htm"

        print(f"Fetching PFR roster for {team_code} ({season}) from {url}")

        if self.use_selenium:
            self.driver.get(url)
            # block until the roster table is actually in the DOM
            self.wait.until(EC.presence_of_element_located((By.ID, "roster")))
            html = self.driver.page_source
            return BeautifulSoup(html, "html.parser")

        # (optional) fallback to a plain‐requests version here
        raise RuntimeError("Need Selenium to fetch PFR rosters")

    def __del__(self):
        # clean up the browser when this object is garbage‑collected
        if getattr(self, "driver", None):
            self.driver.quit()
