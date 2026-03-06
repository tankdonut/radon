Run portfolio scenario analysis. Argument: $ARGUMENTS

## Steps

1. **Parse arguments** — Expect format like `price_shock -10` or `delta_decay 10`. First word is scenario type, second is the percentage.
   - `price_shock <pct>` — Underlying price shock (e.g., `price_shock -10` for -10% shock)
   - `delta_decay <pct>` — Delta decay with no price movement (e.g., `delta_decay 10` for 10% decay)
   - If no arguments provided, run both scenarios at -10% shock and 10% decay.

2. **Get current spot prices** — Run `python3 scripts/ib_sync.py` to get fresh portfolio, then extract current spots from the portfolio positions' market prices or use IB live prices. Build the spots JSON dict from available price data for each ticker in the portfolio.

3. **Run the scenario** — Execute:
   ```
   python3 scripts/scenario_analysis.py <scenario_type> --shock|-decay <pct> --spots '<JSON>'
   ```

4. **Present results** in a clear table format:

   **Current State:**
   | Metric | Value |
   |--------|-------|
   | Net Liq | $X |
   | Dollar Delta | $X |
   | Net Long | $X |

   **Stressed State (scenario description):**
   | Metric | Current | Stressed | Change |
   |--------|---------|----------|--------|
   | Net Liq | $X | $X | -$X (-Y%) |
   | Dollar Delta | $X | $X | -$X (-Y%) |
   | Net Long | $X | $X | -$X (-Y%) |

   **Per-Position Impact** (sorted by absolute impact, largest first):
   | Ticker | Delta | P&L Impact | New MV |
   |--------|-------|------------|--------|

5. **Summarize** — One-sentence takeaway on portfolio vulnerability.
