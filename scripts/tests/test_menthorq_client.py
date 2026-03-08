"""Tests for MenthorQClient — headless browser client for MenthorQ data extraction.

RED/GREEN TDD: All tests written first (RED), then client implemented (GREEN).
Uses unittest.mock to avoid any real browser or API calls.
"""
import inspect
import json
import os

import pytest
from unittest.mock import MagicMock, patch, PropertyMock, call

from clients.menthorq_client import (
    MenthorQClient,
    MenthorQError,
    MenthorQAuthError,
    MenthorQNotFoundError,
    MenthorQExtractionError,
    BASE_URL,
)


# ── Fixtures ──────────────────────────────────────────────────────────


@pytest.fixture
def mock_env_creds():
    """Provide mock MenthorQ credentials and Anthropic key in environment."""
    with patch.dict(os.environ, {
        "MENTHORQ_USER": "test@example.com",
        "MENTHORQ_PASS": "testpass123",
        "ANTHROPIC_API_KEY": "sk-ant-test-key",
    }):
        yield


@pytest.fixture
def mock_playwright():
    """Mock Playwright so no real browser is launched."""
    with patch("clients.menthorq_client.sync_playwright") as mock_sp, \
         patch("clients.menthorq_client.time.sleep"):
        # Build the mock browser chain
        mock_pw = MagicMock()
        mock_sp.return_value.__enter__ = MagicMock(return_value=mock_pw)
        mock_sp.return_value.__exit__ = MagicMock(return_value=False)

        mock_browser = MagicMock()
        mock_pw.chromium.launch.return_value = mock_browser

        mock_context = MagicMock()
        mock_browser.new_context.return_value = mock_context

        mock_page = MagicMock()
        mock_context.new_page.return_value = mock_page

        # Default: login succeeds (URL doesn't contain /login after submit)
        mock_page.url = "https://menthorq.com/account/"

        yield {
            "sync_playwright": mock_sp,
            "playwright": mock_pw,
            "browser": mock_browser,
            "context": mock_context,
            "page": mock_page,
        }


@pytest.fixture
def client(mock_env_creds, mock_playwright):
    """Create a MenthorQClient with mocked browser and credentials."""
    c = MenthorQClient(headless=True)
    yield c


# ══════════════════════════════════════════════════════════════════════
# 1. INITIALIZATION
# ══════════════════════════════════════════════════════════════════════


class TestMenthorQClientInit:
    def test_loads_creds_from_env(self, mock_env_creds, mock_playwright):
        """Client loads MENTHORQ_USER and MENTHORQ_PASS from environment."""
        c = MenthorQClient()
        assert c._username == "test@example.com"
        assert c._password == "testpass123"

    def test_missing_user_raises_auth_error(self, mock_playwright):
        """Missing MENTHORQ_USER raises MenthorQAuthError."""
        with patch.dict(os.environ, {"MENTHORQ_PASS": "pass"}, clear=True):
            os.environ.pop("MENTHORQ_USER", None)
            with pytest.raises(MenthorQAuthError, match="MENTHORQ_USER"):
                MenthorQClient()

    def test_missing_pass_raises_auth_error(self, mock_playwright):
        """Missing MENTHORQ_PASS raises MenthorQAuthError."""
        with patch.dict(os.environ, {"MENTHORQ_USER": "user"}, clear=True):
            os.environ.pop("MENTHORQ_PASS", None)
            with pytest.raises(MenthorQAuthError, match="MENTHORQ_PASS"):
                MenthorQClient()

    def test_no_hardcoded_credentials_in_source(self):
        """Verify no credentials are hardcoded in the source file."""
        import re
        source = inspect.getsource(MenthorQClient)
        assert "joseph" not in source.lower()
        assert "gmail" not in source.lower()
        assert "RX$" not in source
        # Check for email addresses (but allow @ in decorators/string formatting)
        email_pattern = re.findall(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', source)
        assert len(email_pattern) == 0, f"Found email-like strings: {email_pattern}"

    def test_accepts_headless_param(self, mock_env_creds, mock_playwright):
        """Client passes headless parameter to browser launch."""
        c = MenthorQClient(headless=False)
        mock_playwright["playwright"].chromium.launch.assert_called_with(headless=False)


# ══════════════════════════════════════════════════════════════════════
# 2. LOGIN
# ══════════════════════════════════════════════════════════════════════


class TestMenthorQClientLogin:
    def test_login_navigates_to_login_url(self, client, mock_playwright):
        """Login navigates to the MenthorQ login page."""
        page = mock_playwright["page"]
        # The constructor calls _login(), which should have navigated to login URL
        calls = page.goto.call_args_list
        login_calls = [c for c in calls if "login" in str(c).lower()]
        assert len(login_calls) >= 1, "Should navigate to login URL"

    def test_login_fills_form_and_submits(self, client, mock_playwright):
        """Login fills username and password fields, then submits."""
        page = mock_playwright["page"]
        # Should have queried for form fields
        assert page.query_selector.call_count > 0, "Should query for form elements"

    def test_login_failure_raises_auth_error(self, mock_env_creds, mock_playwright):
        """Login failure (still on /login page after submit) raises MenthorQAuthError."""
        page = mock_playwright["page"]
        # Simulate login failure — URL still contains /login
        page.url = "https://menthorq.com/login/"
        with pytest.raises(MenthorQAuthError, match="[Ll]ogin"):
            MenthorQClient()


# ══════════════════════════════════════════════════════════════════════
# 3. EOD DATA
# ══════════════════════════════════════════════════════════════════════


SAMPLE_EOD_HTML = """
<div class="command-card" data-command-slug="eod">
  <div class="main-container">
    <table>
      <tr><th>Field</th><th>Value</th></tr>
      <tr><td>Last Price</td><td>5740.00</td></tr>
      <tr><td>Change %</td><td>-1.33</td></tr>
    </table>
    <div class="ticker-name">S&P 500 INDEX</div>
    <div class="score-block" data-score-type="qscore">
      <span class="score-value">1</span>
      <span class="score-label">Low</span>
    </div>
  </div>
</div>
"""


class TestMenthorQClientEOD:
    def test_get_eod_builds_correct_url(self, client, mock_playwright):
        """get_eod() navigates to the correct URL with ticker and date params."""
        page = mock_playwright["page"]
        page.content.return_value = SAMPLE_EOD_HTML

        # Mock _scrape_eod_fields to return valid data
        with patch.object(client, "_scrape_eod_fields", return_value={"last_price": 5740.0}):
            client.get_eod("SPX", "2026-03-06")

        # Check navigation URL contains expected params
        nav_calls = page.goto.call_args_list
        eod_calls = [c for c in nav_calls if "eod" in str(c)]
        assert len(eod_calls) >= 1, "Should navigate to EOD URL"
        url_str = str(eod_calls[-1])
        assert "commands=eod" in url_str
        assert "ticker=SPX" in url_str

    def test_get_eod_returns_structured_data(self, client, mock_playwright):
        """get_eod() returns a dict with expected keys."""
        expected = {
            "ticker": "SPX",
            "date": "2026-03-06",
            "last_price": 5740.0,
            "change_pct": -1.33,
        }
        with patch.object(client, "_scrape_eod_fields", return_value=expected):
            result = client.get_eod("SPX", "2026-03-06")
        assert isinstance(result, dict)
        assert result["ticker"] == "SPX"

    def test_get_eod_extracts_price_fields(self, client, mock_playwright):
        """get_eod() result contains numeric price fields."""
        expected = {
            "ticker": "SPX",
            "date": "2026-03-06",
            "last_price": 5740.0,
            "change_pct": -1.33,
            "iv_30d": 20.59,
            "hv_30": 12.19,
        }
        with patch.object(client, "_scrape_eod_fields", return_value=expected):
            result = client.get_eod("SPX", "2026-03-06")
        assert isinstance(result["last_price"], (int, float))
        assert isinstance(result["change_pct"], (int, float))

    def test_get_eod_extracts_qscore_fields(self, client, mock_playwright):
        """get_eod() result contains qscore sub-dict."""
        expected = {
            "ticker": "SPX",
            "date": "2026-03-06",
            "last_price": 5740.0,
            "qscore": {"score": 1, "label": "Low"},
        }
        with patch.object(client, "_scrape_eod_fields", return_value=expected):
            result = client.get_eod("SPX", "2026-03-06")
        assert "qscore" in result
        assert result["qscore"]["score"] == 1

    def test_get_eod_handles_missing_data(self, client, mock_playwright):
        """get_eod() raises MenthorQExtractionError when scrape returns empty."""
        with patch.object(client, "_scrape_eod_fields", return_value={}):
            with pytest.raises(MenthorQExtractionError):
                client.get_eod("INVALID", "2026-03-06")

    def test_get_eod_requires_ticker_and_date(self, client):
        """get_eod() requires both ticker and date parameters."""
        with pytest.raises(TypeError):
            client.get_eod()  # type: ignore
        with pytest.raises(TypeError):
            client.get_eod("SPX")  # type: ignore


# ══════════════════════════════════════════════════════════════════════
# 4. CTA DATA
# ══════════════════════════════════════════════════════════════════════


class TestMenthorQClientCTA:
    def test_get_cta_builds_correct_url(self, client, mock_playwright):
        """get_cta() navigates to CTA dashboard URL with date param."""
        page = mock_playwright["page"]
        page.evaluate.return_value = 4  # Card count polling
        with patch.object(client, "_download_card_images", return_value={}):
            with patch.object(client, "_screenshot_cards", return_value={}):
                with patch.object(client, "_extract_via_vision", return_value=[]):
                    try:
                        client.get_cta("2026-03-06")
                    except MenthorQExtractionError:
                        pass  # Expected when no images

        nav_calls = page.goto.call_args_list
        cta_calls = [c for c in nav_calls if "commands=cta" in str(c)]
        assert len(cta_calls) >= 1, "Should navigate to CTA URL"

    def test_get_cta_downloads_four_card_images(self, client, mock_playwright):
        """get_cta() attempts to download S3 images for all 4 CTA cards."""
        page = mock_playwright["page"]
        page.evaluate.return_value = 4
        with patch.object(client, "_download_card_images") as mock_dl:
            mock_dl.return_value = {
                "main": b"png1",
                "index": b"png2",
                "commodity": b"png3",
                "currency": b"png4",
            }
            with patch.object(client, "_extract_via_vision", return_value=[{"underlying": "test"}]):
                client.get_cta("2026-03-06")

            mock_dl.assert_called_once()
            args = mock_dl.call_args
            slugs = args[0][1] if len(args[0]) > 1 else args[1].get("slugs", {})
            assert len(slugs) == 4 or isinstance(slugs, dict) and len(slugs) == 4

    def test_get_cta_calls_vision_extraction(self, client, mock_playwright):
        """get_cta() sends each image to Vision for extraction."""
        page = mock_playwright["page"]
        page.evaluate.return_value = 4
        with patch.object(client, "_download_card_images", return_value={
            "main": b"png_bytes_main",
            "index": b"png_bytes_index",
        }):
            with patch.object(client, "_extract_via_vision", return_value=[{"underlying": "test"}]) as mock_vision:
                client.get_cta("2026-03-06")
                assert mock_vision.call_count == 2

    def test_get_cta_returns_tables_dict(self, client, mock_playwright):
        """get_cta() returns dict mapping table keys to lists of dicts."""
        page = mock_playwright["page"]
        page.evaluate.return_value = 4
        with patch.object(client, "_download_card_images", return_value={
            "main": b"png1",
            "index": b"png2",
        }):
            with patch.object(client, "_extract_via_vision", return_value=[
                {"underlying": "E-Mini S&P 500", "position_today": 0.45}
            ]):
                result = client.get_cta("2026-03-06")

        assert isinstance(result, dict)
        assert "main" in result
        assert isinstance(result["main"], list)
        assert result["main"][0]["underlying"] == "E-Mini S&P 500"

    def test_get_cta_falls_back_to_screenshots(self, client, mock_playwright):
        """get_cta() falls back to screenshots when S3 download fails."""
        page = mock_playwright["page"]
        page.evaluate.return_value = 4
        with patch.object(client, "_download_card_images", return_value={}):
            with patch.object(client, "_screenshot_cards", return_value={
                "main": b"png1",
            }) as mock_ss:
                with patch.object(client, "_extract_via_vision", return_value=[{"underlying": "test"}]):
                    client.get_cta("2026-03-06")
                mock_ss.assert_called_once()


# ══════════════════════════════════════════════════════════════════════
# 5. SCREENER
# ══════════════════════════════════════════════════════════════════════


class TestMenthorQClientScreener:
    def test_get_screener_builds_correct_url(self, client, mock_playwright):
        """get_screener() navigates to screener URL with commands param."""
        page = mock_playwright["page"]
        with patch.object(client, "_scrape_tables", return_value=[{"ticker": "AAPL"}]):
            client.get_screener("options")

        nav_calls = page.goto.call_args_list
        screener_calls = [c for c in nav_calls if "screener" in str(c) and "options" in str(c)]
        assert len(screener_calls) >= 1

    def test_get_screener_category_builds_correct_url(self, client, mock_playwright):
        """get_screener_category() navigates to category screener URL."""
        page = mock_playwright["page"]
        with patch.object(client, "_scrape_tables", return_value=[{"ticker": "AAPL"}]):
            client.get_screener_category("gamma", "top-gamma")

        nav_calls = page.goto.call_args_list
        cat_calls = [c for c in nav_calls if "category=gamma" in str(c)]
        assert len(cat_calls) >= 1

    def test_get_screener_returns_list_of_dicts(self, client, mock_playwright):
        """get_screener() returns a list of dicts."""
        with patch.object(client, "_scrape_tables", return_value=[
            {"ticker": "AAPL", "score": 5},
            {"ticker": "MSFT", "score": 4},
        ]):
            result = client.get_screener("options")

        assert isinstance(result, list)
        assert len(result) == 2
        assert result[0]["ticker"] == "AAPL"


# ══════════════════════════════════════════════════════════════════════
# 6. LIFECYCLE
# ══════════════════════════════════════════════════════════════════════


class TestMenthorQClientLifecycle:
    def test_context_manager_closes_browser(self, mock_env_creds, mock_playwright):
        """Context manager closes browser on exit."""
        with MenthorQClient() as c:
            browser = mock_playwright["browser"]
        browser.close.assert_called()

    def test_close_is_idempotent(self, client, mock_playwright):
        """Calling close() multiple times doesn't raise."""
        client.close()
        client.close()  # Should not raise

    def test_close_handles_already_closed(self, client, mock_playwright):
        """close() handles case where browser is already None."""
        client._browser = None
        client.close()  # Should not raise


# ══════════════════════════════════════════════════════════════════════
# 7. DASHBOARD IMAGE
# ══════════════════════════════════════════════════════════════════════


class TestMenthorQClientDashboardImage:
    def test_get_dashboard_image_builds_correct_url(self, client, mock_playwright):
        """get_dashboard_image() navigates to dashboard URL with command param."""
        page = mock_playwright["page"]
        page.evaluate.return_value = 1  # card count polling
        with patch.object(client, "_download_card_images", return_value={"gex": b"\x89PNG_s3"}):
            client.get_dashboard_image("gex")

        nav_calls = page.goto.call_args_list
        gex_calls = [c for c in nav_calls if "commands=gex" in str(c)]
        assert len(gex_calls) >= 1

    def test_get_dashboard_image_tries_s3_first(self, client, mock_playwright):
        """get_dashboard_image() tries S3 download before viewport screenshot."""
        page = mock_playwright["page"]
        page.evaluate.return_value = 1
        with patch.object(client, "_download_card_images", return_value={"gex": b"\x89PNG_s3"}) as mock_dl:
            result = client.get_dashboard_image("gex")
            mock_dl.assert_called_once()
            assert result == b"\x89PNG_s3"
            # Should NOT fall back to page.screenshot
            page.screenshot.assert_not_called()

    def test_get_dashboard_image_falls_back_to_screenshot(self, client, mock_playwright):
        """get_dashboard_image() falls back to viewport screenshot when S3 fails."""
        page = mock_playwright["page"]
        page.evaluate.return_value = 0  # no cards found
        page.screenshot.return_value = b"\x89PNG_viewport"
        with patch.object(client, "_download_card_images", return_value={}):
            result = client.get_dashboard_image("gex")
            assert result == b"\x89PNG_viewport"
            page.screenshot.assert_called_once()

    def test_get_dashboard_image_returns_png_bytes(self, client, mock_playwright):
        """get_dashboard_image() returns PNG bytes."""
        page = mock_playwright["page"]
        page.evaluate.return_value = 1
        with patch.object(client, "_download_card_images", return_value={"dix": b"\x89PNG_fake_data"}):
            result = client.get_dashboard_image("dix")
        assert isinstance(result, bytes)
        assert len(result) > 0

    def test_get_dashboard_image_with_tickers(self, client, mock_playwright):
        """get_dashboard_image() passes optional tickers param."""
        page = mock_playwright["page"]
        page.evaluate.return_value = 1
        with patch.object(client, "_download_card_images", return_value={"cryptos_options": b"\x89PNG"}):
            client.get_dashboard_image("cryptos_options", tickers="cryptos_options")

        nav_calls = page.goto.call_args_list
        crypto_calls = [c for c in nav_calls if "tickers=cryptos_options" in str(c)]
        assert len(crypto_calls) >= 1

    def test_get_dashboard_image_raises_on_empty(self, client, mock_playwright):
        """get_dashboard_image() raises MenthorQExtractionError when both S3 and screenshot fail."""
        page = mock_playwright["page"]
        page.evaluate.return_value = 0
        page.screenshot.return_value = b""
        with patch.object(client, "_download_card_images", return_value={}):
            with pytest.raises(MenthorQExtractionError):
                client.get_dashboard_image("vix")

    def test_get_dashboard_image_raises_on_exception(self, client, mock_playwright):
        """get_dashboard_image() raises MenthorQExtractionError on screenshot failure."""
        page = mock_playwright["page"]
        page.evaluate.return_value = 0
        page.screenshot.side_effect = Exception("screenshot failed")
        with patch.object(client, "_download_card_images", return_value={}):
            with pytest.raises(MenthorQExtractionError, match="screenshot"):
                client.get_dashboard_image("flows")

    def test_get_dashboard_image_uses_command_slug(self, client, mock_playwright):
        """get_dashboard_image() passes the command as the card slug to _download_card_images."""
        page = mock_playwright["page"]
        page.evaluate.return_value = 1
        with patch.object(client, "_download_card_images", return_value={"vol-models": b"\x89PNG"}) as mock_dl:
            client.get_dashboard_image("vol-models")
            # Verify the slugs dict uses command as both key and value
            args = mock_dl.call_args
            slugs = args[0][1]
            assert "vol-models" in slugs
            assert slugs["vol-models"] == "vol-models"


# ══════════════════════════════════════════════════════════════════════
# 8. INTRADAY
# ══════════════════════════════════════════════════════════════════════


class TestMenthorQClientIntraday:
    def test_get_intraday_builds_correct_url(self, client, mock_playwright):
        """get_intraday() navigates to intraday dashboard URL."""
        page = mock_playwright["page"]
        with patch.object(client, "_scrape_tables", return_value=[]):
            client.get_intraday()

        nav_calls = page.goto.call_args_list
        intraday_calls = [c for c in nav_calls if "commands=intraday" in str(c)]
        assert len(intraday_calls) >= 1

    def test_get_intraday_returns_list(self, client, mock_playwright):
        """get_intraday() returns a list of dicts."""
        with patch.object(client, "_scrape_tables", return_value=[
            {"ticker": "SPX", "price": 5740.0}
        ]):
            result = client.get_intraday()
        assert isinstance(result, list)
        assert result[0]["ticker"] == "SPX"


# ══════════════════════════════════════════════════════════════════════
# 9. FUTURES
# ══════════════════════════════════════════════════════════════════════


class TestMenthorQClientFutures:
    def test_get_futures_list_builds_correct_url(self, client, mock_playwright):
        """get_futures_list() navigates to futures list URL."""
        page = mock_playwright["page"]
        with patch.object(client, "_scrape_tables", return_value=[]):
            client.get_futures_list()

        nav_calls = page.goto.call_args_list
        futures_calls = [c for c in nav_calls if "type=futures" in str(c) and "commands=list" in str(c)]
        assert len(futures_calls) >= 1

    def test_get_futures_detail_includes_ticker(self, client, mock_playwright):
        """get_futures_detail() includes ticker in URL params."""
        page = mock_playwright["page"]
        with patch.object(client, "_scrape_tables", return_value=[]):
            client.get_futures_detail("ES")

        nav_calls = page.goto.call_args_list
        detail_calls = [c for c in nav_calls if "ticker=ES" in str(c)]
        assert len(detail_calls) >= 1

    def test_get_futures_contracts_includes_date(self, client, mock_playwright):
        """get_futures_contracts() includes ticker and date in URL params."""
        page = mock_playwright["page"]
        with patch.object(client, "_scrape_tables", return_value=[]):
            client.get_futures_contracts("ES", "2026-03-06")

        nav_calls = page.goto.call_args_list
        contract_calls = [c for c in nav_calls if "ticker=ES" in str(c) and "date=2026-03-06" in str(c)]
        assert len(contract_calls) >= 1

    def test_get_futures_list_returns_list(self, client, mock_playwright):
        """get_futures_list() returns a list of dicts."""
        with patch.object(client, "_scrape_tables", return_value=[
            {"ticker": "ES", "price": 5740.0}
        ]):
            result = client.get_futures_list()
        assert isinstance(result, list)

    def test_get_futures_detail_requires_ticker(self, client):
        """get_futures_detail() requires ticker param."""
        with pytest.raises(TypeError):
            client.get_futures_detail()  # type: ignore

    def test_get_futures_contracts_requires_params(self, client):
        """get_futures_contracts() requires ticker and date params."""
        with pytest.raises(TypeError):
            client.get_futures_contracts()  # type: ignore


# ══════════════════════════════════════════════════════════════════════
# 10. FOREX
# ══════════════════════════════════════════════════════════════════════


class TestMenthorQClientForex:
    def test_get_forex_list_builds_correct_url(self, client, mock_playwright):
        """get_forex_list() navigates to forex list URL."""
        page = mock_playwright["page"]
        with patch.object(client, "_scrape_tables", return_value=[]):
            client.get_forex_list()

        nav_calls = page.goto.call_args_list
        forex_calls = [c for c in nav_calls if "type=forex" in str(c) and "commands=list" in str(c)]
        assert len(forex_calls) >= 1

    def test_get_forex_detail_includes_ticker(self, client, mock_playwright):
        """get_forex_detail() includes ticker in URL params."""
        page = mock_playwright["page"]
        with patch.object(client, "_scrape_tables", return_value=[]):
            client.get_forex_detail("EURUSD")

        nav_calls = page.goto.call_args_list
        detail_calls = [c for c in nav_calls if "ticker=EURUSD" in str(c)]
        assert len(detail_calls) >= 1

    def test_get_forex_list_returns_list(self, client, mock_playwright):
        """get_forex_list() returns a list of dicts."""
        with patch.object(client, "_scrape_tables", return_value=[{"pair": "EURUSD"}]):
            result = client.get_forex_list()
        assert isinstance(result, list)

    def test_get_forex_detail_requires_ticker(self, client):
        """get_forex_detail() requires ticker param."""
        with pytest.raises(TypeError):
            client.get_forex_detail()  # type: ignore


# ══════════════════════════════════════════════════════════════════════
# 11. CRYPTO
# ══════════════════════════════════════════════════════════════════════


class TestMenthorQClientCrypto:
    def test_get_crypto_list_builds_correct_url(self, client, mock_playwright):
        """get_crypto_list() navigates to crypto list URL."""
        page = mock_playwright["page"]
        with patch.object(client, "_scrape_tables", return_value=[]):
            client.get_crypto_list()

        nav_calls = page.goto.call_args_list
        crypto_calls = [c for c in nav_calls if "type=crypto" in str(c) and "commands=list" in str(c)]
        assert len(crypto_calls) >= 1

    def test_get_crypto_detail_includes_ticker(self, client, mock_playwright):
        """get_crypto_detail() includes ticker in URL params."""
        page = mock_playwright["page"]
        with patch.object(client, "_scrape_tables", return_value=[]):
            client.get_crypto_detail("BTC")

        nav_calls = page.goto.call_args_list
        detail_calls = [c for c in nav_calls if "ticker=BTC" in str(c)]
        assert len(detail_calls) >= 1

    def test_get_crypto_list_returns_list(self, client, mock_playwright):
        """get_crypto_list() returns a list of dicts."""
        with patch.object(client, "_scrape_tables", return_value=[{"ticker": "BTC"}]):
            result = client.get_crypto_list()
        assert isinstance(result, list)

    def test_get_crypto_detail_requires_ticker(self, client):
        """get_crypto_detail() requires ticker param."""
        with pytest.raises(TypeError):
            client.get_crypto_detail()  # type: ignore
