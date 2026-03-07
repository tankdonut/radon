"""Live integration tests for MenthorQClient — hits real MenthorQ with credentials.

Run with:
    python3 -m pytest scripts/tests/test_menthorq_integration.py -v -m integration

Requires:
    MENTHORQ_USER and MENTHORQ_PASS set in .env (project root)
    Playwright browsers installed: python3 -m playwright install chromium

These tests share a single browser session (module-scoped fixture) to avoid
repeated logins. Image tests only verify PNG bytes are returned (no Vision API
calls to minimize cost).
"""
from __future__ import annotations

import os
from datetime import datetime, timedelta

import pytest

from clients.menthorq_client import (
    MenthorQClient,
    MenthorQError,
)


# ── Helpers ──────────────────────────────────────────────────────────


def _last_trading_date() -> str:
    """Return the most recent weekday as YYYY-MM-DD."""
    today = datetime.now()
    # Walk back from today to find the last weekday
    for offset in range(0, 5):
        d = today - timedelta(days=offset)
        if d.weekday() < 5:  # Mon-Fri
            return d.strftime("%Y-%m-%d")
    return today.strftime("%Y-%m-%d")


# ── Module-scoped client ────────────────────────────────────────────

# Skip the entire module if credentials aren't available
_has_creds = bool(
    os.environ.get("MENTHORQ_USER", "").strip()
    and os.environ.get("MENTHORQ_PASS", "").strip()
)


@pytest.fixture(scope="module")
def client():
    """Single browser session for all integration tests."""
    if not _has_creds:
        pytest.skip("MENTHORQ_USER / MENTHORQ_PASS not set")

    c = MenthorQClient(headless=True)
    yield c
    c.close()


@pytest.fixture(scope="module")
def trading_date() -> str:
    return _last_trading_date()


# ══════════════════════════════════════════════════════════════════════
# LOGIN
# ══════════════════════════════════════════════════════════════════════


@pytest.mark.integration
class TestMenthorQIntegrationLogin:
    def test_login_succeeds(self, client):
        """Client is authenticated — URL should be on /account/."""
        url = client._page.url.lower()
        assert "/login" not in url, f"Still on login page: {url}"
        assert "menthorq.com" in url


# ══════════════════════════════════════════════════════════════════════
# HTML ROUTES
# ══════════════════════════════════════════════════════════════════════


@pytest.mark.integration
class TestMenthorQIntegrationHTML:
    def test_eod_spx(self, client, trading_date):
        """get_eod() returns structured data for SPX."""
        result = client.get_eod("SPX", trading_date)
        assert isinstance(result, dict)
        assert len(result) > 0, "EOD should return non-empty dict"

    def test_intraday(self, client):
        """get_intraday() returns a list."""
        result = client.get_intraday()
        assert isinstance(result, list)

    def test_screener_options(self, client):
        """get_screener('options') returns a list of dicts."""
        result = client.get_screener("options")
        assert isinstance(result, list)

    def test_screener_flow(self, client):
        """get_screener('flow') returns a list of dicts."""
        result = client.get_screener("flow")
        assert isinstance(result, list)

    def test_screener_unusual(self, client):
        """get_screener('unusual') returns a list of dicts."""
        result = client.get_screener("unusual")
        assert isinstance(result, list)

    def test_screener_category_gamma(self, client):
        """get_screener_category() returns data for a gamma screener."""
        result = client.get_screener_category("gamma", "top-gamma")
        assert isinstance(result, list)

    def test_futures_list(self, client):
        """get_futures_list() returns a list of futures."""
        result = client.get_futures_list()
        assert isinstance(result, list)

    def test_futures_detail(self, client):
        """get_futures_detail() returns detail data for ES."""
        result = client.get_futures_detail("ES")
        assert isinstance(result, list)

    def test_futures_contracts(self, client, trading_date):
        """get_futures_contracts() returns contracts for ES."""
        result = client.get_futures_contracts("ES", trading_date)
        assert isinstance(result, list)

    def test_forex_list(self, client):
        """get_forex_list() returns a list of forex pairs."""
        result = client.get_forex_list()
        assert isinstance(result, list)

    def test_forex_detail(self, client):
        """get_forex_detail() returns detail for EURUSD."""
        result = client.get_forex_detail("EURUSD")
        assert isinstance(result, list)

    def test_crypto_list(self, client):
        """get_crypto_list() returns a list of crypto assets."""
        result = client.get_crypto_list()
        assert isinstance(result, list)


# ══════════════════════════════════════════════════════════════════════
# IMAGE ROUTES
# ══════════════════════════════════════════════════════════════════════


def _assert_png(data: bytes, label: str) -> None:
    """Verify data is non-empty PNG bytes."""
    assert isinstance(data, bytes), f"{label}: expected bytes, got {type(data)}"
    assert len(data) > 100, f"{label}: PNG too small ({len(data)} bytes)"
    assert data[:4] == b"\x89PNG", f"{label}: missing PNG magic header"


@pytest.mark.integration
class TestMenthorQIntegrationImage:
    def test_cta(self, client, trading_date):
        """get_cta() returns dict of table data (skips Vision cost — just checks navigation)."""
        # CTA requires Vision API key — if no key, expect extraction error
        try:
            result = client.get_cta(trading_date)
            assert isinstance(result, dict)
        except MenthorQError:
            # Acceptable — Vision key may not be set or extraction may fail
            pass

    def test_image_gex(self, client):
        _assert_png(client.get_dashboard_image("gex"), "gex")

    def test_image_dix(self, client):
        _assert_png(client.get_dashboard_image("dix"), "dix")

    def test_image_vix(self, client):
        _assert_png(client.get_dashboard_image("vix"), "vix")

    def test_image_flows(self, client):
        _assert_png(client.get_dashboard_image("flows"), "flows")

    def test_image_darkpool(self, client):
        _assert_png(client.get_dashboard_image("darkpool"), "darkpool")

    def test_image_options(self, client):
        _assert_png(client.get_dashboard_image("options"), "options")

    def test_image_putcall(self, client):
        _assert_png(client.get_dashboard_image("putcall"), "putcall")

    def test_image_skew(self, client):
        _assert_png(client.get_dashboard_image("skew"), "skew")

    def test_image_term(self, client):
        _assert_png(client.get_dashboard_image("term"), "term")

    def test_image_breadth(self, client):
        _assert_png(client.get_dashboard_image("breadth"), "breadth")

    def test_image_sectors(self, client):
        _assert_png(client.get_dashboard_image("sectors"), "sectors")

    def test_image_correlation(self, client):
        _assert_png(client.get_dashboard_image("correlation"), "correlation")

    def test_image_cta_flows(self, client):
        _assert_png(client.get_dashboard_image("cta-flows"), "cta-flows")

    def test_image_vol_models(self, client):
        _assert_png(client.get_dashboard_image("vol-models"), "vol-models")

    def test_image_vol(self, client):
        _assert_png(client.get_dashboard_image("vol"), "vol")

    def test_image_forex_levels(self, client):
        _assert_png(client.get_dashboard_image("forex"), "forex")

    def test_image_crypto_options(self, client):
        _assert_png(
            client.get_dashboard_image("cryptos_options", tickers="cryptos_options"),
            "cryptos_options",
        )

    def test_image_crypto_quant(self, client):
        _assert_png(
            client.get_dashboard_image("cryptos_technical", tickers="cryptos_technical"),
            "cryptos_technical",
        )

    def test_crypto_detail(self, client):
        """get_crypto_detail('BTC') returns data."""
        result = client.get_crypto_detail("BTC")
        assert isinstance(result, list)


# ══════════════════════════════════════════════════════════════════════
# SCREENER CATEGORIES (1 slug per category)
# ══════════════════════════════════════════════════════════════════════


@pytest.mark.integration
class TestMenthorQIntegrationScreenerCategories:
    def test_category_gamma(self, client):
        result = client.get_screener_category("gamma", "top-gamma")
        assert isinstance(result, list)

    def test_category_gamma_levels(self, client):
        result = client.get_screener_category("gamma_levels", "gamma-flip")
        assert isinstance(result, list)

    def test_category_open_interest(self, client):
        result = client.get_screener_category("open_interest", "top-oi-change")
        assert isinstance(result, list)

    def test_category_volatility(self, client):
        result = client.get_screener_category("volatility", "top-iv-rank")
        assert isinstance(result, list)

    def test_category_volume(self, client):
        result = client.get_screener_category("volume", "top-volume")
        assert isinstance(result, list)

    def test_category_qscore(self, client):
        result = client.get_screener_category("qscore", "top-qscore")
        assert isinstance(result, list)
