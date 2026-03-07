"""Headless browser client for MenthorQ data extraction.

MenthorQ has no public API. All data sits behind WordPress auth, rendered as
HTML tables (scrapeable) or chart images (requires Claude Vision). This client
handles authentication, navigation, HTML scraping, and image-based extraction.

Usage::

    from clients.menthorq_client import MenthorQClient

    with MenthorQClient() as client:
        eod = client.get_eod("SPX", "2026-03-06")
        cta = client.get_cta("2026-03-06")

    # Or without context manager:
    client = MenthorQClient(headless=False)
    try:
        screener = client.get_screener("options")
    finally:
        client.close()

Credentials (project root .env, loaded via python-dotenv):
    MENTHORQ_USER  -- MenthorQ email/username
    MENTHORQ_PASS  -- MenthorQ password

Vision API key (from web/.env or shell):
    ANTHROPIC_API_KEY / CLAUDE_CODE_API_KEY / CLAUDE_API_KEY
"""
from __future__ import annotations

import base64
import json
import logging
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv as _load_dotenv
from playwright.sync_api import sync_playwright, Page

# Load .env from project root
_load_dotenv(Path(__file__).resolve().parent.parent.parent / ".env")

logger = logging.getLogger(__name__)

# ══════════════════════════════════════════════════════════════════════
# Constants
# ══════════════════════════════════════════════════════════════════════

BASE_URL = "https://menthorq.com/account/"
LOGIN_URL = "https://menthorq.com/login/"

# CTA card slugs (data-command-slug attributes)
CTA_SLUGS = {
    "main": "cta_table",
    "index": "cta_index",
    "commodity": "cta_commodity",
    "currency": "cta_currency",
}

# Anthropic API key env var names (tried in order)
_ANTHROPIC_ENV_KEYS = ["ANTHROPIC_API_KEY", "CLAUDE_CODE_API_KEY", "CLAUDE_API_KEY"]

# Vision extraction prompt for CTA tables
_CTA_EXTRACTION_PROMPT = """Extract CTA positioning data from this table image.
Return ONLY a JSON array of objects with these exact fields:
[{"underlying":"E-Mini S&P 500 Index","position_today":0.45,"position_yesterday":0.21,"position_1m_ago":1.06,"percentile_1m":38,"percentile_3m":13,"percentile_1y":38,"z_score_3m":-1.56},...]

Rules:
- "underlying" is the asset name exactly as shown in the table
- Position values are decimal numbers as shown (can be negative)
- Percentiles are integers (e.g. 38 means 38th percentile)
- Z-scores are decimal numbers as shown (e.g. -1.56)
- Include ALL rows from the table
- Return ONLY the JSON array, no markdown, no explanation"""


# ══════════════════════════════════════════════════════════════════════
# Exception Hierarchy
# ══════════════════════════════════════════════════════════════════════


class MenthorQError(Exception):
    """Base exception for all MenthorQ client errors."""


class MenthorQAuthError(MenthorQError):
    """Login or credential failure."""


class MenthorQNotFoundError(MenthorQError):
    """Page or ticker not found."""


class MenthorQExtractionError(MenthorQError):
    """Vision or HTML parse failure."""


# ══════════════════════════════════════════════════════════════════════
# Client
# ══════════════════════════════════════════════════════════════════════


class MenthorQClient:
    """Headless browser client for MenthorQ data extraction.

    Features:
      - Playwright-managed Chromium with WordPress auth
      - HTML table scraping for structured data (EOD, screeners)
      - Screenshot + Claude Vision for image-rendered data (CTA)
      - Context manager support for clean browser lifecycle
    """

    # ── init / lifecycle ───────────────────────────────────────────

    def __init__(self, headless: bool = True):
        self._username = os.environ.get("MENTHORQ_USER", "").strip() or None
        self._password = os.environ.get("MENTHORQ_PASS", "").strip() or None

        if not self._username:
            raise MenthorQAuthError(
                "MENTHORQ_USER environment variable is not set. "
                "Add it to the project root .env file."
            )
        if not self._password:
            raise MenthorQAuthError(
                "MENTHORQ_PASS environment variable is not set. "
                "Add it to the project root .env file."
            )

        self._api_key = self._resolve_api_key()
        self._headless = headless

        # Launch browser and login
        self._pw_context = sync_playwright()
        self._pw = self._pw_context.__enter__()
        self._browser = self._pw.chromium.launch(headless=headless)
        self._browser_context = self._browser.new_context(
            viewport={"width": 1920, "height": 1080},
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
        )
        self._page = self._browser_context.new_page()
        self._login()

    def close(self) -> None:
        """Close browser and Playwright context."""
        if self._browser is not None:
            try:
                self._browser.close()
            except Exception:
                pass
            self._browser = None
        if hasattr(self, "_pw_context") and self._pw_context is not None:
            try:
                self._pw_context.__exit__(None, None, None)
            except Exception:
                pass
            self._pw_context = None

    def __enter__(self) -> "MenthorQClient":
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    # ── credentials ────────────────────────────────────────────────

    @staticmethod
    def _resolve_api_key() -> Optional[str]:
        """Resolve Anthropic API key from environment."""
        for key in _ANTHROPIC_ENV_KEYS:
            value = os.environ.get(key, "").strip()
            if value:
                return value
        return None

    # ── login ──────────────────────────────────────────────────────

    def _login(self) -> None:
        """Authenticate to MenthorQ via WordPress login form."""
        logger.info("Navigating to MenthorQ login...")
        self._page.goto(LOGIN_URL, wait_until="networkidle", timeout=30000)
        time.sleep(2)

        # WordPress login form — try multiple selector patterns
        username_selectors = [
            'input[name="log"]',
            'input#user_login',
            'input[name="username"]',
            'input[type="text"]',
            'input[type="email"]',
        ]
        password_selectors = [
            'input[name="pwd"]',
            'input#user_pass',
            'input[name="password"]',
            'input[type="password"]',
        ]

        for sel in username_selectors:
            el = self._page.query_selector(sel)
            if el:
                el.fill(self._username)
                break

        for sel in password_selectors:
            el = self._page.query_selector(sel)
            if el:
                el.fill(self._password)
                break

        # Submit
        submit_selectors = [
            'input[name="wp-submit"]',
            'input[type="submit"]',
            'button[type="submit"]',
            '#wp-submit',
        ]
        for sel in submit_selectors:
            el = self._page.query_selector(sel)
            if el:
                el.click()
                break

        self._page.wait_for_load_state("networkidle", timeout=30000)
        time.sleep(3)

        # Verify login succeeded
        current_url = self._page.url.lower()
        if "/login" in current_url or "/wp-login" in current_url:
            raise MenthorQAuthError(
                "Login failed — still on login page after submit. "
                "Check MENTHORQ_USER and MENTHORQ_PASS credentials."
            )

        logger.info("MenthorQ login successful.")

    # ── navigation ─────────────────────────────────────────────────

    def _navigate(self, params: Dict[str, str]) -> Page:
        """Build MenthorQ URL from params, navigate, wait for load.

        Uses ``domcontentloaded`` instead of ``networkidle`` because
        chart-heavy pages (EOD, dashboards) have persistent network
        activity that prevents networkidle from resolving.
        """
        query = "&".join(f"{k}={v}" for k, v in params.items())
        url = f"{BASE_URL}?{query}"
        logger.info(f"Navigating to: {url}")
        self._page.goto(url, wait_until="domcontentloaded", timeout=60000)
        # Allow dynamic content (charts, cards) to render after DOM ready
        time.sleep(5)
        return self._page

    # ══════════════════════════════════════════════════════════════
    # Phase 1: Core Methods
    # ══════════════════════════════════════════════════════════════

    # ── EOD ─────────────────────────────────────────────────────

    def get_eod(self, ticker: str, date: str) -> dict:
        """Fetch end-of-day data for a ticker via HTML scraping.

        Args:
            ticker: Stock/index ticker (e.g. "SPX", "AAPL")
            date: Date string YYYY-MM-DD

        Returns:
            Dict with fields like last_price, change_pct, iv_30d, qscore, etc.

        Raises:
            MenthorQExtractionError: If scraping returns empty data.
        """
        self._navigate({
            "action": "data",
            "type": "dashboard",
            "commands": "eod",
            "tickers": "commons",
            "date": date,
            "ticker": ticker,
        })

        result = self._scrape_eod_fields(self._page)
        if not result:
            raise MenthorQExtractionError(
                f"EOD scrape returned empty data for {ticker} on {date}. "
                "Page may not have loaded or ticker may be invalid."
            )
        return result

    # ── CTA ─────────────────────────────────────────────────────

    def get_cta(self, date: str) -> Dict[str, List[Dict[str, Any]]]:
        """Fetch CTA positioning data via screenshot + Vision extraction.

        Args:
            date: Date string YYYY-MM-DD

        Returns:
            Dict mapping table keys ("main", "index", "commodity", "currency")
            to lists of asset positioning dicts.

        Raises:
            MenthorQExtractionError: If no data could be extracted.
        """
        if not self._api_key:
            raise MenthorQExtractionError(
                "No Anthropic API key found. Set ANTHROPIC_API_KEY in environment."
            )

        self._navigate({
            "action": "data",
            "type": "dashboard",
            "commands": "cta",
            "date": date,
        })

        screenshots = self._screenshot_cards(self._page, CTA_SLUGS)
        if not screenshots:
            raise MenthorQExtractionError(
                f"No CTA card screenshots captured for {date}."
            )

        tables: Dict[str, List[Dict]] = {}
        for table_key, png_bytes in screenshots.items():
            extracted = self._extract_via_vision(png_bytes, _CTA_EXTRACTION_PROMPT)
            if extracted:
                tables[table_key] = extracted

        if not tables:
            raise MenthorQExtractionError(
                f"Vision extraction returned no data for CTA tables on {date}."
            )

        return tables

    # ── Screeners ──────────────────────────────────────────────

    def get_screener(self, commands: str) -> List[Dict[str, Any]]:
        """Fetch screener results via HTML table scraping.

        Args:
            commands: Screener type — "options", "flow", "unusual"

        Returns:
            List of dicts, one per screener row.
        """
        self._navigate({
            "action": "data",
            "type": "screener",
            "commands": commands,
        })
        return self._scrape_tables(self._page)

    def get_screener_category(
        self, category: str, slug: str
    ) -> List[Dict[str, Any]]:
        """Fetch category screener results via HTML table scraping.

        Args:
            category: Screener category (e.g. "gamma", "volatility")
            slug: Specific screener slug (e.g. "top-gamma")

        Returns:
            List of dicts, one per screener row.
        """
        self._navigate({
            "action": "data",
            "type": "screeners",
            "category": category,
            "slug": slug,
        })
        return self._scrape_tables(self._page)

    # ══════════════════════════════════════════════════════════════
    # Phase 2: Dashboard Images + Asset Lists
    # ══════════════════════════════════════════════════════════════

    # ── Dashboard Images ─────────────────────────────────────────

    def get_dashboard_image(
        self, command: str, *, tickers: str | None = None
    ) -> bytes:
        """Screenshot a dashboard page and return PNG bytes.

        Covers GEX, DIX, VIX, flows, dark pool, options, put/call, skew,
        term structure, breadth, sectors, correlation, CTA flows, vol models,
        volatility, forex levels, crypto options, crypto quant dashboards.

        Args:
            command: Dashboard command slug (e.g. "gex", "dix", "vix").
            tickers: Optional tickers param (needed for crypto routes).

        Returns:
            PNG screenshot bytes of the dashboard viewport.

        Raises:
            MenthorQExtractionError: If screenshot capture fails.
        """
        params: Dict[str, str] = {
            "action": "data",
            "type": "dashboard",
            "commands": command,
        }
        if tickers:
            params["tickers"] = tickers

        self._navigate(params)

        try:
            png = self._page.screenshot(type="png", full_page=False)
        except Exception as exc:
            raise MenthorQExtractionError(
                f"Dashboard screenshot failed for command={command}: {exc}"
            ) from exc

        if not png:
            raise MenthorQExtractionError(
                f"Dashboard screenshot returned empty bytes for command={command}."
            )

        logger.info(f"Dashboard image: {command} ({len(png):,} bytes)")
        return png

    # ── Intraday ─────────────────────────────────────────────────

    def get_intraday(self) -> List[Dict[str, Any]]:
        """Fetch intraday data via HTML table scraping.

        Returns:
            List of dicts with intraday data rows.
        """
        self._navigate({
            "action": "data",
            "type": "dashboard",
            "commands": "intraday",
        })
        return self._scrape_tables(self._page)

    # ── Futures ──────────────────────────────────────────────────

    def get_futures_list(self) -> List[Dict[str, Any]]:
        """Fetch list of futures instruments via HTML table scraping.

        Returns:
            List of dicts with futures instrument data.
        """
        self._navigate({
            "action": "data",
            "type": "futures",
            "commands": "list",
        })
        return self._scrape_tables(self._page)

    def get_futures_detail(self, ticker: str) -> List[Dict[str, Any]]:
        """Fetch detail data for a specific futures instrument.

        Args:
            ticker: Futures ticker (e.g. "ES", "NQ", "CL").

        Returns:
            List of dicts with futures detail data.
        """
        self._navigate({
            "action": "data",
            "type": "futures",
            "commands": "detail",
            "ticker": ticker,
        })
        return self._scrape_tables(self._page)

    def get_futures_contracts(
        self, ticker: str, date: str
    ) -> List[Dict[str, Any]]:
        """Fetch contracts for a futures instrument on a given date.

        Args:
            ticker: Futures ticker (e.g. "ES").
            date: Date string YYYY-MM-DD.

        Returns:
            List of dicts with contract data.
        """
        self._navigate({
            "action": "data",
            "type": "futures",
            "commands": "contracts",
            "ticker": ticker,
            "date": date,
        })
        return self._scrape_tables(self._page)

    # ── Forex ────────────────────────────────────────────────────

    def get_forex_list(self) -> List[Dict[str, Any]]:
        """Fetch list of forex instruments via HTML table scraping.

        Returns:
            List of dicts with forex instrument data.
        """
        self._navigate({
            "action": "data",
            "type": "forex",
            "commands": "list",
        })
        return self._scrape_tables(self._page)

    def get_forex_detail(self, ticker: str) -> List[Dict[str, Any]]:
        """Fetch detail data for a specific forex pair.

        Args:
            ticker: Forex pair (e.g. "EURUSD", "GBPUSD").

        Returns:
            List of dicts with forex detail data.
        """
        self._navigate({
            "action": "data",
            "type": "forex",
            "commands": "detail",
            "ticker": ticker,
        })
        return self._scrape_tables(self._page)

    # ── Crypto ───────────────────────────────────────────────────

    def get_crypto_list(self) -> List[Dict[str, Any]]:
        """Fetch list of crypto instruments via HTML table scraping.

        Returns:
            List of dicts with crypto instrument data.
        """
        self._navigate({
            "action": "data",
            "type": "crypto",
            "commands": "list",
        })
        return self._scrape_tables(self._page)

    def get_crypto_detail(self, ticker: str) -> List[Dict[str, Any]]:
        """Fetch detail data for a specific crypto asset.

        Args:
            ticker: Crypto ticker (e.g. "BTC", "ETH").

        Returns:
            List of dicts with crypto detail data.
        """
        self._navigate({
            "action": "data",
            "type": "crypto",
            "commands": "detail",
            "ticker": ticker,
        })
        return self._scrape_tables(self._page)

    # ══════════════════════════════════════════════════════════════
    # Low-Level Extraction Methods
    # ══════════════════════════════════════════════════════════════

    def _scrape_tables(self, page: Page) -> List[Dict[str, Any]]:
        """Extract all HTML tables from page into list of dicts.

        Each table row becomes a dict with column headers as keys.
        Returns combined rows from all tables found on the page.
        """
        result = page.evaluate("""() => {
            const tables = document.querySelectorAll('table');
            const allRows = [];
            for (const table of tables) {
                const headers = [];
                const headerRow = table.querySelector('thead tr, tr:first-child');
                if (!headerRow) continue;
                for (const th of headerRow.querySelectorAll('th, td')) {
                    headers.push(th.textContent.trim().toLowerCase().replace(/[\\s\\/]+/g, '_'));
                }
                if (headers.length === 0) continue;
                const bodyRows = table.querySelectorAll('tbody tr, tr:not(:first-child)');
                for (const row of bodyRows) {
                    const cells = row.querySelectorAll('td');
                    if (cells.length === 0) continue;
                    const obj = {};
                    for (let i = 0; i < Math.min(headers.length, cells.length); i++) {
                        let val = cells[i].textContent.trim();
                        // Try to parse numbers
                        const num = parseFloat(val.replace(/[,%$]/g, ''));
                        obj[headers[i]] = isNaN(num) ? val : num;
                    }
                    allRows.push(obj);
                }
            }
            return allRows;
        }""")
        return result if isinstance(result, list) else []

    def _scrape_eod_fields(self, page: Page) -> Dict[str, Any]:
        """Extract EOD-specific fields from the dashboard page.

        The EOD page renders data in two DOM sections:
          1. ``.ticker-container`` → ``.ticker-info`` divs (price, change, IV, etc.)
          2. ``.ticker-qscore-wrapper`` → ``.ticker-qscore-item`` divs (scores)
        """
        result = page.evaluate("""() => {
            const data = {};

            const num = (s) => {
                if (!s) return null;
                const n = parseFloat(s.replace(/[,%$±]/g, ''));
                return isNaN(n) ? null : n;
            };

            // 1. Ticker name from .ticker-container
            const container = document.querySelector('.ticker-container');
            if (!container) return data;

            const nameEl = container.querySelector('.ticker-name');
            if (nameEl) data.name = nameEl.textContent.trim();

            // 2. Info fields from .ticker-info divs
            const infos = container.querySelectorAll('.ticker-info');
            for (const info of infos) {
                const titleEl = info.querySelector('.ticker-info-title');
                const contentEl = info.querySelector('.ticker-info-content');
                if (!titleEl || !contentEl) continue;

                const key = titleEl.textContent.trim().toLowerCase()
                    .replace(/[\\s\\/]+/g, '_').replace(/[^a-z0-9_]/g, '');
                const val = contentEl.textContent.trim();
                const n = num(val);
                data[key] = n !== null ? n : val;
            }

            // 3. QScore items from .ticker-qscore-item divs
            const qscoreItems = container.querySelectorAll('.ticker-qscore-item');
            for (const item of qscoreItems) {
                const valueEl = item.querySelector('.item-value');
                const labelEl = item.querySelector('.item-label');
                const titleEl = item.querySelector('.item-title');
                const descEl = item.querySelector('.item-description');
                if (!titleEl || !valueEl) continue;

                const key = 'qscore_' + titleEl.textContent.trim().toLowerCase()
                    .replace(/[\\s]+/g, '_');
                data[key] = {
                    score: parseInt(valueEl.textContent.trim()) || 0,
                    label: labelEl ? labelEl.textContent.trim() : '',
                    description: descEl ? descEl.textContent.trim() : '',
                };
            }

            return data;
        }""")
        return result if isinstance(result, dict) else {}

    def _screenshot_cards(
        self, page: Page, slugs: Dict[str, str]
    ) -> Dict[str, bytes]:
        """Screenshot card elements identified by data-command-slug.

        Args:
            page: Current Playwright page.
            slugs: Mapping of key names to data-command-slug values.

        Returns:
            Dict mapping key names to PNG bytes for each captured card.
        """
        screenshots: Dict[str, bytes] = {}
        for key, slug in slugs.items():
            try:
                card = page.query_selector(f'[data-command-slug="{slug}"]')
                if not card:
                    card = page.query_selector(
                        f'.command-card:has([data-command-slug="{slug}"])'
                    )
                if not card:
                    logger.warning(f"Card not found for slug: {slug}")
                    continue

                container = card.query_selector(".main-container") or card
                png = container.screenshot(type="png")
                screenshots[key] = png
                logger.info(f"Screenshot: {key} ({len(png):,} bytes)")
            except Exception as exc:
                logger.warning(f"Screenshot failed for {slug}: {exc}")
        return screenshots

    def _extract_via_vision(
        self, png_bytes: bytes, prompt: str
    ) -> Optional[List[Dict[str, Any]]]:
        """Send a screenshot to Claude Haiku Vision for structured extraction.

        Args:
            png_bytes: PNG image bytes.
            prompt: Extraction prompt describing the desired output format.

        Returns:
            List of dicts parsed from Vision response, or None on failure.
        """
        if not self._api_key:
            logger.warning("No Anthropic API key — skipping Vision extraction.")
            return None

        import httpx

        b64 = base64.b64encode(png_bytes).decode("utf-8")

        try:
            resp = httpx.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": self._api_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json={
                    "model": "claude-haiku-4-5-20251001",
                    "max_tokens": 4096,
                    "messages": [
                        {
                            "role": "user",
                            "content": [
                                {
                                    "type": "image",
                                    "source": {
                                        "type": "base64",
                                        "media_type": "image/png",
                                        "data": b64,
                                    },
                                },
                                {"type": "text", "text": prompt},
                            ],
                        }
                    ],
                },
                timeout=60.0,
            )

            if resp.status_code != 200:
                logger.warning(
                    f"Vision API error: {resp.status_code} {resp.text[:200]}"
                )
                return None

            data = resp.json()
            text = None
            for block in data.get("content", []):
                if block.get("type") == "text":
                    text = block.get("text", "")
                    break

            if not text:
                return None

            # Strip markdown fences if present
            cleaned = text.strip()
            if cleaned.startswith("```"):
                cleaned = (
                    cleaned.split("\n", 1)[-1] if "\n" in cleaned else cleaned[3:]
                )
            if cleaned.endswith("```"):
                cleaned = cleaned[:-3]
            cleaned = cleaned.strip()

            parsed = json.loads(cleaned)
            if not isinstance(parsed, list):
                return None

            logger.info(f"Vision extracted {len(parsed)} rows")
            return parsed

        except Exception as exc:
            logger.warning(f"Vision extraction failed: {exc}")
            return None
