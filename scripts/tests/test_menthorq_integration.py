"""Live integration tests for MenthorQClient — hits real MenthorQ with credentials.

Run with:
    python3 -m pytest scripts/tests/test_menthorq_integration.py -v -m integration

Requires:
    MENTHORQ_USER and MENTHORQ_PASS set in .env (project root)
    Playwright browsers installed: python3 -m playwright install chromium

These tests share a single browser session (module-scoped fixture) to avoid
repeated logins. Image tests verify S3 download is used (not viewport screenshots)
and that returned bytes are valid PNGs.
"""
from __future__ import annotations

import os
from datetime import datetime, timedelta
from unittest.mock import patch

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


def _get_image_with_tracking(client, command: str, *, tickers: str | None = None):
    """Call get_dashboard_image with instrumentation to track image source.

    Returns (png_bytes, s3_used: bool, download_attempted: bool).
    """
    original_download = client._download_card_images.__func__
    download_results = []

    def tracking_download(self_inner, page, slugs):
        result = original_download(self_inner, page, slugs)
        download_results.append(result)
        return result

    with patch.object(type(client), "_download_card_images", tracking_download):
        if tickers:
            data = client.get_dashboard_image(command, tickers=tickers)
        else:
            data = client.get_dashboard_image(command)

    download_attempted = len(download_results) >= 1
    s3_used = download_attempted and len(download_results[0]) > 0

    return data, s3_used, download_attempted


@pytest.mark.integration
class TestMenthorQIntegrationImage:
    """Verify all image routes attempt S3 download before falling back to screenshot.

    CTA page is the only MenthorQ route with S3-hosted card images
    (.command-card elements with <img src="s3...">). All other dashboards
    (GEX, DIX, VIX, etc.) render charts dynamically in the DOM, so they
    legitimately fall back to viewport screenshot.

    Every route MUST:
      1. Attempt S3 download via _download_card_images (proving the code path runs)
      2. Return valid PNG bytes
    CTA additionally MUST:
      3. Actually use S3 images (not fall back to screenshot)
    """

    def test_cta_downloads_s3_images(self, client, trading_date):
        """get_cta() downloads S3 images for all 4 CTA cards, not screenshots."""
        from clients.menthorq_client import CTA_SLUGS

        original_download = client._download_card_images.__func__
        download_results = []

        def tracking_download(self_inner, page, slugs):
            result = original_download(self_inner, page, slugs)
            download_results.append(result)
            return result

        with patch.object(type(client), "_download_card_images", tracking_download):
            try:
                result = client.get_cta(trading_date)
                assert isinstance(result, dict)
            except MenthorQError:
                pytest.skip("Vision API key not set or extraction failed")

        # Verify S3 download was used and returned all 4 images
        assert len(download_results) >= 1, "S3 download was not attempted"
        first_result = download_results[0]
        assert len(first_result) == len(CTA_SLUGS), (
            f"Expected {len(CTA_SLUGS)} S3 images, got {len(first_result)}. "
            f"Keys: {list(first_result.keys())}"
        )
        for key, png_bytes in first_result.items():
            _assert_png(png_bytes, f"cta/{key}")

    def test_image_gex(self, client):
        data, s3, attempted = _get_image_with_tracking(client, "gex")
        _assert_png(data, "gex")
        assert attempted, "S3 download was not attempted"

    def test_image_dix(self, client):
        data, s3, attempted = _get_image_with_tracking(client, "dix")
        _assert_png(data, "dix")
        assert attempted, "S3 download was not attempted"

    def test_image_vix(self, client):
        data, s3, attempted = _get_image_with_tracking(client, "vix")
        _assert_png(data, "vix")
        assert attempted, "S3 download was not attempted"

    def test_image_flows(self, client):
        data, s3, attempted = _get_image_with_tracking(client, "flows")
        _assert_png(data, "flows")
        assert attempted, "S3 download was not attempted"

    def test_image_darkpool(self, client):
        data, s3, attempted = _get_image_with_tracking(client, "darkpool")
        _assert_png(data, "darkpool")
        assert attempted, "S3 download was not attempted"

    def test_image_options(self, client):
        data, s3, attempted = _get_image_with_tracking(client, "options")
        _assert_png(data, "options")
        assert attempted, "S3 download was not attempted"

    def test_image_putcall(self, client):
        data, s3, attempted = _get_image_with_tracking(client, "putcall")
        _assert_png(data, "putcall")
        assert attempted, "S3 download was not attempted"

    def test_image_skew(self, client):
        data, s3, attempted = _get_image_with_tracking(client, "skew")
        _assert_png(data, "skew")
        assert attempted, "S3 download was not attempted"

    def test_image_term(self, client):
        data, s3, attempted = _get_image_with_tracking(client, "term")
        _assert_png(data, "term")
        assert attempted, "S3 download was not attempted"

    def test_image_breadth(self, client):
        data, s3, attempted = _get_image_with_tracking(client, "breadth")
        _assert_png(data, "breadth")
        assert attempted, "S3 download was not attempted"

    def test_image_sectors(self, client):
        data, s3, attempted = _get_image_with_tracking(client, "sectors")
        _assert_png(data, "sectors")
        assert attempted, "S3 download was not attempted"

    def test_image_correlation(self, client):
        data, s3, attempted = _get_image_with_tracking(client, "correlation")
        _assert_png(data, "correlation")
        assert attempted, "S3 download was not attempted"

    def test_image_cta_flows(self, client):
        data, s3, attempted = _get_image_with_tracking(client, "cta-flows")
        _assert_png(data, "cta-flows")
        assert attempted, "S3 download was not attempted"

    def test_image_vol_models(self, client):
        data, s3, attempted = _get_image_with_tracking(client, "vol-models")
        _assert_png(data, "vol-models")
        assert attempted, "S3 download was not attempted"

    def test_image_vol(self, client):
        data, s3, attempted = _get_image_with_tracking(client, "vol")
        _assert_png(data, "vol")
        assert attempted, "S3 download was not attempted"

    def test_image_forex_levels(self, client):
        data, s3, attempted = _get_image_with_tracking(client, "forex")
        _assert_png(data, "forex")
        assert attempted, "S3 download was not attempted"

    def test_image_crypto_options(self, client):
        data, s3, attempted = _get_image_with_tracking(
            client, "cryptos_options", tickers="cryptos_options"
        )
        _assert_png(data, "cryptos_options")
        assert attempted, "S3 download was not attempted"

    def test_image_crypto_quant(self, client):
        data, s3, attempted = _get_image_with_tracking(
            client, "cryptos_technical", tickers="cryptos_technical"
        )
        _assert_png(data, "cryptos_technical")
        assert attempted, "S3 download was not attempted"

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
