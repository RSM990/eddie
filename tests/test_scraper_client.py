"""
Scraping-API client + fetcher-factory tests (Phase 4.75, Sprint 4b / DEC-005).

No network: a fake session records the outgoing request so we can assert each
provider's endpoint/params and that the HTML round-trips into soup.
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from etl.utils.scraper_client import ScraperClient
from etl.utils.fetcher import get_pfr_fetcher


class _FakeResp:
    def __init__(self, text):
        self.text = text

    def raise_for_status(self):
        pass


class _FakeSession:
    def __init__(self, text="<html><table id='drafts'></table></html>"):
        self.text = text
        self.calls = []

    def get(self, endpoint, params=None, timeout=None):
        self.calls.append((endpoint, params, timeout))
        return _FakeResp(self.text)

    def close(self):
        pass


def _settings(**over):
    base = dict(
        scraper_provider="scraperapi",
        scraper_api_key="KEY",
        scraper_render_js=True,
        scraper_timeout=42.0,
    )
    base.update(over)
    return SimpleNamespace(**base)


def test_api_key_required():
    with pytest.raises(ValueError):
        ScraperClient(_settings(scraper_api_key=None))


def test_scraperapi_request_shape():
    sess = _FakeSession()
    client = ScraperClient(_settings(), session=sess)
    soup = client.get_soup(
        "https://www.pro-football-reference.com/years/2026/draft.htm", wait_for_id="drafts"
    )
    endpoint, params, timeout = sess.calls[0]
    assert endpoint == "https://api.scraperapi.com/"
    assert params["api_key"] == "KEY"
    assert params["url"].endswith("/years/2026/draft.htm")
    assert params["render"] == "true"
    assert params["ultra_premium"] == "true"
    assert params["wait_for_selector"] == "#drafts"
    assert timeout == 42.0
    assert soup.find("table", id="drafts") is not None


def test_zenrows_request_shape():
    sess = _FakeSession()
    client = ScraperClient(_settings(scraper_provider="zenrows"), session=sess)
    client.get_soup("http://x/y", wait_for_id="roster")
    endpoint, params, _ = sess.calls[0]
    assert endpoint == "https://api.zenrows.com/v1/"
    assert params["apikey"] == "KEY"
    assert params["js_render"] == "true"
    assert params["wait_for"] == "#roster"


def test_render_off_omits_flag():
    sess = _FakeSession()
    client = ScraperClient(_settings(scraper_render_js=False), session=sess)
    client.get_soup("http://x")
    _, params, _ = sess.calls[0]
    assert "render" not in params
    assert "wait_for_selector" not in params  # no wait_for_id given


def test_unknown_provider_raises():
    client = ScraperClient(_settings(scraper_provider="nope"), session=_FakeSession())
    with pytest.raises(ValueError):
        client.get_soup("http://x")


def test_factory_returns_scraper_client_for_api_mode():
    s = _settings(fetch_mode="api")
    assert isinstance(get_pfr_fetcher(s), ScraperClient)


def test_factory_unknown_mode_raises():
    with pytest.raises(ValueError):
        get_pfr_fetcher(SimpleNamespace(fetch_mode="bogus"))
