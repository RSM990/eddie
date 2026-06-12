# src/etl/utils/selenium_client.py
from __future__ import annotations

import os
import time
from typing import Optional

from bs4 import BeautifulSoup
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException

# Title/markers Cloudflare shows while its managed challenge is running.
_CHALLENGE_MARKERS = ("just a moment", "attention required", "checking your browser")


class SeleniumFetcher:
    """
    Browser-based fetcher for Cloudflare-gated PFR pages.

    PFR fronts pages like the draft index with a Cloudflare *managed JS challenge*
    ("Just a moment…"). requests/cloudscraper get a 403; headless Selenium and
    undetected-chromedriver get detected or break on Chrome-version mismatches.

    Most reliable path: **attach to a real Chrome you launched yourself**, which
    has a genuine browser fingerprint and passes the challenge. Launch it once:

        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" \\
            --remote-debugging-port=9222 --user-data-dir="$HOME/.eddie-chrome"

    then set ``CHROME_DEBUGGER_ADDRESS=127.0.0.1:9222`` (or pass
    ``debugger_address=``). In attach mode ``quit()`` is a no-op so your browser
    stays open for the whole run.

    Without a debugger address it tries undetected-chromedriver, then falls back
    to stock Selenium with anti-automation flags (both less reliable against the
    challenge / sensitive to Chrome version).
    """

    def __init__(
        self,
        headless: bool = False,
        wait_seconds: float = 20.0,
        debugger_address: Optional[str] = None,
    ):
        self.debugger_address = debugger_address or os.getenv("CHROME_DEBUGGER_ADDRESS") or None
        self.attached = bool(self.debugger_address)
        self.driver = self._build_driver(headless)
        self.wait = WebDriverWait(self.driver, wait_seconds)

    def _build_driver(self, headless: bool):
        # 1) Attach to a user-launched Chrome (most reliable against Cloudflare).
        if self.attached:
            from selenium import webdriver
            from selenium.webdriver.chrome.options import Options

            opts = Options()
            opts.add_experimental_option("debuggerAddress", self.debugger_address)
            return webdriver.Chrome(options=opts)

        # 2) undetected-chromedriver, if installed and version-compatible.
        try:
            import undetected_chromedriver as uc

            opts = uc.ChromeOptions()
            opts.add_argument("--no-sandbox")
            opts.add_argument("--disable-gpu")
            opts.add_argument("--window-size=1920,1080")
            if headless:
                opts.add_argument("--headless=new")
            return uc.Chrome(options=opts)
        except Exception:
            pass

        # 3) Stock Selenium with best-effort anti-detection.
        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options

        opts = Options()
        if headless:
            opts.add_argument("--headless=new")
        opts.add_argument("--no-sandbox")
        opts.add_argument("--disable-gpu")
        opts.add_argument("--window-size=1920,1080")
        opts.add_argument("--disable-blink-features=AutomationControlled")
        opts.add_experimental_option("excludeSwitches", ["enable-automation"])
        opts.add_experimental_option("useAutomationExtension", False)
        driver = webdriver.Chrome(options=opts)
        driver.execute_cdp_cmd(
            "Page.addScriptToEvaluateOnNewDocument",
            {"source": "Object.defineProperty(navigator,'webdriver',{get:()=>undefined})"},
        )
        return driver

    def _ride_out_challenge(self, timeout: float) -> None:
        """Block until the Cloudflare challenge title clears (or timeout)."""
        deadline = time.time() + timeout
        while time.time() < deadline:
            title = (self.driver.title or "").lower()
            if not any(m in title for m in _CHALLENGE_MARKERS):
                return
            time.sleep(1.0)

    def get_soup(
        self,
        url: str,
        wait_for_id: Optional[str] = None,
        challenge_timeout: float = 30.0,
    ) -> BeautifulSoup:
        """
        Load ``url``, ride out any Cloudflare challenge, and return parsed soup.
        If ``wait_for_id`` is given, also wait for that element id (falling back
        to whatever rendered if it never appears).
        """
        self.driver.get(url)
        self._ride_out_challenge(challenge_timeout)
        if wait_for_id:
            try:
                self.wait.until(EC.presence_of_element_located((By.ID, wait_for_id)))
            except TimeoutException:
                pass
        return BeautifulSoup(self.driver.page_source, "html.parser")

    def quit(self) -> None:
        # In attach mode the browser belongs to the user — never close it.
        if getattr(self, "attached", False):
            return
        driver = getattr(self, "driver", None)
        if driver is not None:
            try:
                driver.quit()
            except Exception:
                pass
            self.driver = None

    def __del__(self):
        self.quit()
