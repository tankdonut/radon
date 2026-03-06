# Convex Scavenger

An autonomous options trading assistant for a sub-$1M individual account. Detects institutional positioning via dark pool/OTC flow, constructs convex options structures, and sizes with fractional Kelly criterion.

**No narrative trades. No TA trades. Flow signal or nothing.**

## Three Gates

Every trade must pass three gates in order:

1. **Convexity** — Potential gain >= 2x potential loss. Defined-risk only (long options, vertical spreads).
2. **Edge** — A specific, data-backed dark pool/OTC flow signal that hasn't yet moved price.
3. **Risk Management** — Fractional Kelly sizing with a hard cap of 2.5% of bankroll per position.

If any gate fails, no trade is taken.

## Prerequisites

- Python 3.9+
- [Interactive Brokers](https://www.interactivebrokers.com/) TWS or IB Gateway running locally
- [Unusual Whales](https://unusualwhales.com) API key for dark pool / flow data
- Node.js 18+ (for the web dashboard)

## Getting Started

### 1. Clone and install

```bash
git clone https://github.com/joemccann/convex-scavenger.git
cd convex-scavenger
pip install -r requirements.txt
```

### 2. Set environment variables

Add these to your shell profile (`.zshrc`, `.bashrc`, etc.):

```bash
# Unusual Whales — dark pool and options flow data
export UW_TOKEN="your-unusual-whales-api-key"

# Optional: xAI Grok — X/Twitter sentiment analysis
export XAI_API_KEY="your-xai-api-key"
```

IB Gateway/TWS connects locally on port 4001 (Gateway) or 7497 (TWS). No API key needed — just have it running.

### 3. Verify IB connection

```bash
python scripts/ib_sync.py
```

### 4. Run your first scan

```bash
python scripts/scanner.py --top 15
```

## Project Structure

```
convex-scavenger/
├── CLAUDE.md                          # Agent identity, trading rules, commands
├── VERSION                            # Semantic version (0.5.0)
├── requirements.txt                   # Python deps (ib_insync, requests, pandas)
├── scripts/
│   ├── clients/                       # API client libraries
│   │   ├── ib_client.py               # IBClient — wraps ib_insync (orders, quotes, fills, flex)
│   │   └── uw_client.py               # UWClient — wraps UW REST API (50+ endpoints)
│   ├── utils/                         # Shared utilities
│   │   ├── ib_connection.py           # IB connection helper + client ID registry
│   │   ├── uw_api.py                  # Legacy UW API helper (use UWClient instead)
│   │   └── market_calendar.py         # Market hours + holiday helpers
│   ├── config/
│   │   └── market_holidays.json       # US market holiday calendar
│   ├── trade_blotter/                 # IB trade blotter subsystem
│   │   ├── blotter_service.py         # Core blotter (IB fetcher + Flex Query)
│   │   ├── flex_query.py              # Historical fills (365-day via IB Flex)
│   │   ├── cli.py                     # CLI interface
│   │   ├── models.py                  # Data models
│   │   └── formatting.py             # Output formatting
│   ├── monitor_daemon/                # Background monitoring daemon
│   │   ├── daemon.py                  # Orchestrator
│   │   └── handlers/                  # Plugin handlers (fill_monitor, exit_orders)
│   ├── tests/                         # pytest test suite (612 tests)
│   ├── fetch_ticker.py                # Ticker validation via UW
│   ├── fetch_flow.py                  # Dark pool + options flow from UW
│   ├── fetch_options.py               # Options chain (IB → UW → Yahoo fallback)
│   ├── fetch_analyst_ratings.py       # Analyst ratings (IB → Yahoo)
│   ├── fetch_x_watchlist.py           # X/Twitter scraping via browser automation
│   ├── fetch_x_xai.py                # X/Twitter sentiment via xAI Grok
│   ├── scanner.py                     # Watchlist batch dark pool scan
│   ├── discover.py                    # Market-wide options flow scanner
│   ├── kelly.py                       # Kelly criterion calculator
│   ├── ib_sync.py                     # Sync live IB portfolio → portfolio.json
│   ├── ib_orders.py                   # Open orders sync → orders.json
│   ├── ib_order.py                    # Order placement
│   ├── ib_execute.py                  # Unified place + monitor + auto-log
│   ├── ib_order_manage.py             # Cancel or modify open IB orders
│   ├── ib_fill_monitor.py             # Long-running fill monitoring service
│   ├── ib_reconcile.py                # Reconcile IB fills vs trade_log
│   ├── ib_realtime_server.py          # WebSocket server for real-time quotes
│   ├── exit_order_service.py          # Background daemon for pending exit orders
│   ├── blotter.py                     # Trade blotter CLI wrapper
│   ├── leap_iv_scanner.py             # LEAP IV scanner (via IB)
│   ├── leap_scanner_uw.py             # LEAP scanner (via UW + Yahoo)
│   ├── garch_convergence.py           # GARCH convergence vol divergence scanner
│   ├── evaluate.py                    # Unified 7-milestone evaluation (parallel)
│   ├── portfolio_report.py            # HTML portfolio report generator
│   ├── free_trade_analyzer.py         # Multi-leg "free trade" analysis
│   └── context_constructor.py         # Persistent memory pipeline (Constructor + Evaluator)
├── context/                           # Persistent memory (context engineering)
│   ├── memory/
│   │   ├── fact/                      # Atomic facts (trading lessons, API quirks)
│   │   ├── episodic/                  # Session summaries
│   │   ├── procedural/                # Tool definitions
│   │   ├── user/                      # User preferences
│   │   └── experiential/              # Action→outcome trajectories
│   ├── human/                         # Human annotations (highest priority)
│   ├── history/                       # Immutable transaction log
│   └── metadata.json                  # Governance policies + token budget
├── data/                              # Runtime JSON data (gitignored)
│   ├── portfolio.json                 # Open positions, bankroll, exposure
│   ├── trade_log.json                 # Append-only executed trade journal
│   ├── orders.json                    # Open IB orders
│   ├── watchlist.json                 # Tickers under surveillance
│   ├── reconciliation.json            # IB reconciliation results
│   └── daemon_state.json              # Monitor daemon state
├── docs/
│   ├── ib_tws_api.md                  # IB TWS API reference
│   ├── unusual_whales_api.md          # UW API quick reference
│   ├── unusual_whales_api_spec.yaml   # Full UW OpenAPI spec
│   ├── strategies.md                  # Options strategies reference
│   ├── implement.md                   # Implementation notes
│   ├── plans.md                       # Milestone workflow
│   └── status.md                      # Evaluation audit log
├── reports/                           # Generated HTML reports (gitignored)
├── config/                            # launchd plists for background services
├── web/                               # Next.js 15 dashboard + chat UI
│   ├── app/                           # App router (dashboard, scanner, portfolio, etc.)
│   ├── components/                    # React components
│   ├── lib/                           # Shared TypeScript utilities
│   └── tests/                         # TypeScript tests
└── .pi/                               # PI agent configuration (legacy)
```

## API Clients

All scripts use two centralized API client classes in `scripts/clients/`:

### IBClient (`scripts/clients/ib_client.py`)

Wraps `ib_insync.IB` with connection management, retries, and a clean method API.

```python
from clients.ib_client import IBClient

with IBClient() as client:
    client.connect(client_name="ib_sync", port=4001)
    positions = client.get_positions()
    orders = client.get_open_orders()
    quote = client.get_quote(contract)
```

Key methods: `connect`, `get_positions`, `get_portfolio`, `get_account_summary`, `place_order`, `place_bracket_order`, `cancel_order`, `modify_order`, `get_open_orders`, `get_quote`, `get_option_chain`, `qualify_contract`, `get_fills`, `wait_for_fill`, `run_flex_query`, `get_historical_data`.

Exceptions: `IBConnectionError`, `IBOrderError`, `IBTimeoutError`, `IBContractError`.

### UWClient (`scripts/clients/uw_client.py`)

Wraps the Unusual Whales REST API with session pooling, retry logic, and rate limit awareness.

```python
from clients.uw_client import UWClient

with UWClient() as client:
    flow = client.get_darkpool_flow("AAPL")
    alerts = client.get_flow_alerts(ticker="AAPL", min_premium=500000)
    info = client.get_stock_info("AAPL")
```

50+ endpoints covering: dark pool, options flow, stock info, options chains, GEX, volatility, analyst ratings, seasonality, short interest, institutional ownership, insider transactions, congress trades, ETF data, market indicators, earnings, screeners, news.

Exceptions: `UWAuthError`, `UWRateLimitError`, `UWNotFoundError`, `UWValidationError`, `UWServerError`.

## Commands

When used with Claude Code, the agent responds to these commands:

| Command | Action |
|---------|--------|
| `scan` | Watchlist dark pool flow scan |
| `discover` | Market-wide options flow for new candidates |
| `evaluate [TICKER]` | Full 7-milestone three-gate evaluation |
| `portfolio` | Positions, exposure, capacity |
| `journal` | Recent trade log |
| `sync` | Pull live portfolio from IB |
| `blotter` | Today's fills + P&L |
| `blotter-history` | Historical trades via Flex Query |
| `leap-scan [TICKERS]` | LEAP IV mispricing opportunities |
| `garch-convergence [PRESET]` | Cross-asset GARCH vol divergence scan |
| `seasonal [TICKERS]` | Monthly seasonality assessment |
| `free-trade` | Analyze positions for free trade opportunities |
| `x-scan [@ACCOUNT]` | Extract ticker sentiment from X posts |
| `analyst-ratings [TICKERS]` | Ratings, changes, price targets |

## Evaluation Pipeline

The `evaluate` command runs a full 7-milestone evaluation with parallel data fetching:

```bash
# Full evaluation (human-readable)
python scripts/evaluate.py AAPL

# JSON output
python scripts/evaluate.py AAPL --json

# Custom bankroll
python scripts/evaluate.py AAPL --bankroll 1200000
```

The script fetches ticker info, seasonality, analyst ratings, dark pool flow, options flow, and OI changes **in parallel**, then runs edge determination sequentially. It stops at the first failing gate — no wasted API calls.

If edge passes, you design the structure with live IB quotes (Milestone 5), run Kelly sizing (Milestone 6), and generate an HTML trade specification report for confirmation before execution.

## Portfolio Report

Self-contained HTML report with 8 sections — connects to IB, fetches live positions, fetches 5-day dark pool flow for all tickers (including today), and generates a styled report:

```bash
python scripts/portfolio_report.py           # Generate and open in browser
python scripts/portfolio_report.py --no-open # Generate without opening
```

**8 sections:** Header, Data Freshness Banner, Summary Metrics (6 cards), Quick-Stat Badges, Attention Callouts, Thesis Check (with today-highlighted sparklines), All Positions Table, Dark Pool Flow Heatmap.

**Today-highlighting:** Sparkline bars for today's data have a white outline ring, and "LIVE" tags mark real-time flow values. This makes it immediately visible whether today's flow confirms or breaks the pattern.

## GARCH Convergence Scanner

Identifies cross-asset volatility divergences using GARCH(1,1) models:

```bash
# Built-in presets
python scripts/garch_convergence.py --preset semis
python scripts/garch_convergence.py --preset mega-tech
python scripts/garch_convergence.py --preset all

# File presets (150 available in data/presets/)
python scripts/garch_convergence.py --preset sp500-semiconductors
python scripts/garch_convergence.py --preset ndx100-biotech

# Ad-hoc ticker pairs
python scripts/garch_convergence.py NVDA AMD GOOGL META
```

Parallel fetch with 8 workers (~3s for 23 tickers). Generates an HTML report at `reports/garch-convergence-{preset}-{date}.html`.

## Persistent Memory (Context Engineering)

File-system-based persistent memory across sessions, implementing the Constructor → Evaluator pipeline:

```bash
# View current persistent memory
python scripts/context_constructor.py

# Save a trading lesson
python scripts/context_constructor.py --save-fact "trading.lesson.name" "Lesson content" \
  --confidence 0.95 --source "evaluation-TICKER-DATE"

# Save a session summary
python scripts/context_constructor.py --save-episode "What happened this session" \
  --session-id "session-2026-03-06"
```

**At startup**, the Constructor automatically loads all facts, episodic summaries, and human annotations into the agent's context (token-budgeted to 8000 tokens). Facts persist across sessions — the agent remembers trading lessons, API quirks, and portfolio state.

**Memory types:**
- `context/memory/fact/` — Atomic facts (permanent, deduplicated by key)
- `context/memory/episodic/` — Session summaries (1-year retention)
- `context/human/` — Human annotations (permanent, highest priority)
- `context/history/` — Transaction log (append-only, all operations)

## CLI Tools

Scripts can be run standalone:

```bash
# Discover new candidates from market-wide options flow
python scripts/discover.py --min-premium 500000 --dp-days 3

# Fetch dark pool flow for a ticker
python scripts/fetch_flow.py AAPL --days 5

# Validate a ticker
python scripts/fetch_ticker.py AAPL

# Scan entire watchlist
python scripts/scanner.py --top 15

# Calculate Kelly sizing
python scripts/kelly.py --prob 0.35 --odds 3.5 --fraction 0.25 --bankroll 100000

# Sync IB portfolio
python scripts/ib_sync.py

# Place an order
python scripts/ib_order.py AAPL 250 2025-06-20 C --action BUY --qty 5

# Today's fills and P&L
python scripts/blotter.py

# LEAP scanner
python scripts/leap_scanner_uw.py AAPL MSFT GOOGL

# GARCH convergence scan
python scripts/garch_convergence.py --preset semis

# Full evaluation
python scripts/evaluate.py GOOG

# Generate portfolio report
python scripts/portfolio_report.py

# Free trade analysis
python scripts/free_trade_analyzer.py --table

# Save a persistent fact
python scripts/context_constructor.py --save-fact "key" "value"
```

## Web Dashboard

A Next.js 15 chat interface with real-time IB price streaming.

```bash
cd web
npm install
npm run dev        # Starts Next.js + IB WebSocket server
```

Visit `http://localhost:3000`. The dashboard includes pages for scanner, portfolio, orders, flow analysis, and a chat interface.

## Data Source Priority

| Priority | Source | Notes |
|----------|--------|-------|
| **1** | Interactive Brokers (TWS/Gateway) | Real-time quotes, options chains, fundamentals |
| **2** | Unusual Whales (`$UW_TOKEN`) | Dark pool flow, sweeps, flow alerts, analyst ratings |
| **3** | Exa (`$EXA_API_KEY`) | Web search, company research |
| **4** | agent-browser | Interactive pages, JS-rendered content |
| **5** | Yahoo Finance | **Absolute last resort** — delayed, rate-limited |

Scripts automatically fall through this priority chain. Yahoo Finance is never used if any higher-priority source is available.

## Data Files

| File | Purpose |
|------|---------|
| `data/portfolio.json` | Open positions, bankroll, exposure, Kelly-derived limits |
| `data/trade_log.json` | Append-only journal of every executed trade |
| `data/orders.json` | Current open IB orders |
| `data/watchlist.json` | Tickers under surveillance with sector tags |
| `data/reconciliation.json` | IB fill reconciliation results |
| `data/presets/` | 150 strategy-agnostic ticker presets (SP500, NDX100, R2K) |
| `context/memory/fact/` | Persistent facts (trading lessons, API quirks) |
| `context/memory/episodic/` | Session summaries |
| `context/metadata.json` | Governance policies + token budget allocation |

## Testing

```bash
# Run the full test suite (612 tests)
python -m pytest scripts/tests/ -v

# Run specific test files
python -m pytest scripts/tests/test_ib_client.py -v
python -m pytest scripts/tests/test_uw_client.py -v
```

All tests use mocked API calls — no live IB or UW connections required.

## Background Services

Background daemons configurable via launchd (macOS):

| Service | Purpose |
|---------|---------|
| `monitor_daemon/` | Pluggable daemon: fill monitoring, exit order placement, preset rebalancing |
| `exit_order_service.py` | Monitors `PENDING_MANUAL` positions, places exit orders when IB accepts |

launchd plists are in `config/`.

### Startup Protocol

When the agent starts, the startup extension automatically:
1. Checks market hours (9:30 AM – 4:00 PM ET)
2. Loads project docs + persistent memory from `context/`
3. Runs IB reconciliation (detects new trades, closed positions)
4. Runs free trade analysis (waits for IB sync to complete)
5. Checks monitor daemon status
6. Scans X accounts for ticker sentiment (parallel)

## Discovery Scoring (0-100)

Candidates from `discover.py` are scored on edge quality:

| Component | Weight | What It Measures |
|-----------|--------|------------------|
| DP Strength | 30% | Dark pool buy/sell imbalance intensity |
| DP Sustained | 20% | Consecutive days in same direction |
| Confluence | 20% | Options bias aligns with dark pool direction |
| Vol/OI Ratio | 15% | Unusual options volume vs open interest |
| Sweeps | 15% | Sweep trades present (urgency signal) |

**60-100** Strong | **40-59** Monitor | **20-39** Weak | **<20** No signal

## IB Ports

| Port | Connection |
|------|-----------|
| 7496 | TWS Live |
| 7497 | TWS Paper (default) |
| 4001 | IB Gateway Live |
| 4002 | IB Gateway Paper |

## Glossary

| Term | Definition |
|------|------------|
| **ATM** | At-The-Money — strike price near current stock price |
| **Convexity** | Asymmetric payoff where gain >> loss (we require >= 2:1) |
| **DP** | Dark Pool — private exchanges for institutional orders |
| **Edge** | Data-backed reason the market is mispricing an outcome |
| **GEX** | Gamma Exposure — aggregate market maker gamma positioning |
| **IV** | Implied Volatility — market's expectation of future price movement |
| **Kelly Criterion** | Optimal bet sizing: `f* = p - (q/b)` where p = win prob, q = 1-p, b = odds |
| **OI** | Open Interest — outstanding option contracts not yet closed |
| **OTC** | Over-The-Counter — trades between parties, not on public exchanges |
| **R:R** | Risk-to-Reward ratio (we require gain >= 2x loss) |
| **Sweep** | Large order split across exchanges for fast execution |
| **UW** | Unusual Whales — data provider for dark pool and options flow |
