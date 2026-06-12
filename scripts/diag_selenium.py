#!/usr/bin/env python
"""
Diagnostic: what does headless Chrome actually render for the PFR draft page?

    PYTHONPATH=src python scripts/diag_selenium.py --season 2026

Paste the output back. It tells us whether we're getting a Cloudflare challenge
page vs. the real page with the table hidden in an HTML comment.
"""
from __future__ import annotations

import argparse
import time

from bs4 import BeautifulSoup, Comment

from etl.utils.selenium_client import SeleniumFetcher


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--season", type=int, default=2026)
    args = ap.parse_args()

    url = f"https://www.pro-football-reference.com/years/{args.season}/draft.htm"
    f = SeleniumFetcher()
    try:
        f.driver.get(url)
        time.sleep(6)  # give any Cloudflare challenge time to resolve
        src = f.driver.page_source
        low = src.lower()

        print("title:        ", f.driver.title)
        print("current_url:  ", f.driver.current_url)
        print("page_source len:", len(src))
        for marker in [
            "just a moment", "checking your browser", "cf-chl", "challenge-platform",
            "attention required", "cloudflare", "access denied", "enable javascript",
            'id="drafts"', "<table",
        ]:
            print(f"  contains {marker!r:28}: {marker in low}")

        soup = BeautifulSoup(src, "html.parser")
        print("tables (uncommented):", len(soup.find_all("table")))
        comment_tables = sum(
            1 for c in soup.find_all(string=lambda t: isinstance(t, Comment)) if "<table" in c
        )
        print("comments containing <table:", comment_tables)

        out = "/tmp/pfr_draft.html"
        with open(out, "w") as fh:
            fh.write(src)
        print(f"saved rendered HTML to {out}")
    finally:
        f.quit()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
