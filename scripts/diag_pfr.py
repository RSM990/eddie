#!/usr/bin/env python
"""
Diagnostic: which HTTP method can actually fetch a Cloudflare-gated PFR page?

Tries several approaches against the draft index and the homepage and prints the
status code for each (no exceptions). Run on a machine that should reach PFR:

    PYTHONPATH=src python scripts/diag_pfr.py --season 2026

Paste the output back so we wire the draft path to whatever returns 200.
"""
from __future__ import annotations

import argparse

import requests

BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
}


def _status(fn):
    try:
        return str(fn())
    except Exception as e:  # noqa: BLE001 - diagnostic, report everything
        return f"ERR {type(e).__name__}: {str(e)[:80]}"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--season", type=int, default=2026)
    args = ap.parse_args()

    urls = {
        "draft": f"https://www.pro-football-reference.com/years/{args.season}/draft.htm",
        "home": "https://www.pro-football-reference.com/",
    }

    methods = {}

    # 1) plain requests + realistic browser headers (the PFRHttpClient approach)
    def m_requests(url):
        return requests.get(url, headers=BROWSER_HEADERS, timeout=30).status_code
    methods["requests+browser-headers"] = m_requests

    # 2) cloudscraper, default browser emulation
    try:
        import cloudscraper
        sc_default = cloudscraper.create_scraper(
            browser={"browser": "chrome", "platform": "darwin", "mobile": False}
        )
        methods["cloudscraper-default"] = lambda url: sc_default.get(url, timeout=30).status_code

        # 3) cloudscraper with the old custom bot UA
        sc_bot = cloudscraper.create_scraper(browser={"custom": "eddie-etl-bot/1.0"})
        methods["cloudscraper-bot-ua"] = lambda url: sc_bot.get(url, timeout=30).status_code

        # 4) cloudscraper but override headers with full browser header set
        sc_hdr = cloudscraper.create_scraper(
            browser={"browser": "chrome", "platform": "darwin", "mobile": False}
        )
        sc_hdr.headers.update(BROWSER_HEADERS)
        methods["cloudscraper+browser-headers"] = lambda url: sc_hdr.get(url, timeout=30).status_code
    except Exception as e:  # noqa: BLE001
        print(f"cloudscraper unavailable: {e}")

    print(f"cloudscraper version: ", end="")
    try:
        import cloudscraper
        print(getattr(cloudscraper, "__version__", "?"))
    except Exception:
        print("n/a")

    for label, url in urls.items():
        print(f"\n# {label}: {url}")
        for name, fn in methods.items():
            print(f"  {name:<32} -> {_status(lambda: fn(url))}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
