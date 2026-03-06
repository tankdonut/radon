#!/usr/bin/env python3
"""Portfolio scenario analysis — stress testing via price shock and delta decay."""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


# ── Portfolio loader ────────────────────────────────────

def load_portfolio() -> dict:
    """Load data/portfolio.json."""
    with open(DATA_DIR / "portfolio.json") as f:
        return json.load(f)


# ── Delta approximation (ported from exposureBreakdown.ts) ──

def approx_delta(spot: float, strike: float, dte: float, opt_type: str) -> float:
    """
    Approximate option delta using tanh model.
    opt_type: "Call" or "Put"
    Returns: delta in [-1, 1]
    """
    if spot <= 0 or strike <= 0 or dte <= 0:
        return 0.5 if opt_type == "Call" else -0.5
    # Always compute call moneyness, then apply put-call parity.
    # (The TS source uses a separate put moneyness formula that inverts ITM/OTM —
    #  we fix that here by always using call moneyness.)
    moneyness = (spot - strike) / strike
    time_factor = max(0.1, math.sqrt(dte / 365))
    adjusted = moneyness / (0.2 * time_factor)
    call_delta = 0.5 + 0.5 * math.tanh(adjusted * 2)
    return call_delta if opt_type == "Call" else call_delta - 1


def days_to_expiry(expiry: str) -> float:
    """Days until option expiry. Returns 0 for N/A or past dates."""
    if not expiry or expiry == "N/A":
        return 0
    try:
        exp = datetime.strptime(expiry, "%Y-%m-%d").replace(
            hour=16, tzinfo=timezone.utc  # 4pm ET approximation
        )
        now = datetime.now(timezone.utc)
        diff = (exp - now).total_seconds() / 86400
        return max(0, math.ceil(diff))
    except ValueError:
        return 0


# ── Per-position delta ──────────────────────────────────

def compute_position_delta(pos: dict, spot: float | None) -> float:
    """
    Net delta-equivalent shares for a position.
    Matches sign conventions from exposureBreakdown.ts:positionDeltaDetailed.
    """
    if spot is None or spot <= 0:
        return 0

    total = 0.0
    dte = days_to_expiry(pos.get("expiry", "N/A"))

    for leg in pos.get("legs", []):
        sign = 1 if leg["direction"] == "LONG" else -1

        if leg["type"] == "Stock":
            total += sign * leg["contracts"]
            continue

        strike = leg.get("strike")
        if not strike or strike <= 0:
            continue

        raw_delta = approx_delta(spot, strike, dte, leg["type"])
        total += sign * raw_delta * leg["contracts"] * 100

    return total


# ── Portfolio-level exposure ────────────────────────────

def compute_exposure(portfolio: dict, spots: dict[str, float]) -> dict:
    """Current portfolio exposure metrics."""
    dollar_delta = 0.0
    net_long = 0.0
    net_short = 0.0
    net_liq = portfolio.get("bankroll", 0)

    for pos in portfolio.get("positions", []):
        ticker = pos.get("ticker", "")
        spot = spots.get(ticker)
        delta = compute_position_delta(pos, spot)

        if spot and spot > 0:
            dd = delta * spot
        else:
            dd = 0
        dollar_delta += dd

        mv = abs(pos.get("market_value", 0) or 0)
        if delta > 0:
            net_long += mv
        elif delta < 0:
            net_short += mv

    return {
        "net_liq": net_liq,
        "dollar_delta": dollar_delta,
        "net_long": net_long,
        "net_short": net_short,
    }


# ── Scenario A: Underlying Price Shock ──────────────────

def scenario_price_shock(portfolio: dict, spots: dict[str, float], shock_pct: float) -> dict:
    """
    All underlyings shift by shock_pct (e.g., -0.10 for -10%).
    First-order delta approximation for P&L.
    """
    current = compute_exposure(portfolio, spots)

    total_pnl = 0.0
    pos_details = []
    new_spots = {t: s * (1 + shock_pct) for t, s in spots.items()}

    for pos in portfolio.get("positions", []):
        ticker = pos.get("ticker", "")
        old_spot = spots.get(ticker)
        if not old_spot or old_spot <= 0:
            pos_details.append({
                "ticker": ticker,
                "pnl_impact": 0,
                "new_mv": pos.get("market_value", 0) or 0,
            })
            continue

        delta = compute_position_delta(pos, old_spot)
        new_spot = old_spot * (1 + shock_pct)
        price_change = new_spot - old_spot
        pnl = delta * price_change

        old_mv = pos.get("market_value", 0) or 0
        new_mv = old_mv + pnl

        total_pnl += pnl
        pos_details.append({
            "ticker": ticker,
            "delta": round(delta, 2),
            "pnl_impact": round(pnl, 2),
            "old_mv": round(old_mv, 2),
            "new_mv": round(new_mv, 2),
        })

    stressed = compute_exposure(portfolio, new_spots)
    stressed["net_liq"] = current["net_liq"] + total_pnl

    return {
        "scenario": "price_shock",
        "parameters": {"shock_pct": shock_pct},
        "current": {k: round(v, 2) for k, v in current.items()},
        "stressed": {k: round(v, 2) for k, v in stressed.items()},
        "impact": {
            "net_liq_change": round(total_pnl, 2),
            "dollar_delta_change": round(stressed["dollar_delta"] - current["dollar_delta"], 2),
            "net_long_change": round(stressed["net_long"] - current["net_long"], 2),
        },
        "positions": pos_details,
    }


# ── Scenario B: Delta Decay ────────────────────────────

def _leg_extrinsic(leg: dict, spot: float) -> float:
    """Extrinsic value per contract for an option leg."""
    if leg["type"] == "Stock":
        return 0
    strike = leg.get("strike", 0) or 0
    mp = leg.get("market_price", 0) or 0
    if leg["type"] == "Call":
        intrinsic = max(0, spot - strike)
    else:
        intrinsic = max(0, strike - spot)
    return max(0, mp - intrinsic)


def scenario_delta_decay(portfolio: dict, spots: dict[str, float], decay_pct: float) -> dict:
    """
    All option deltas shrink by decay_pct (e.g., 0.10 for 10%).
    Stocks unaffected. Net liq impact via extrinsic value loss.
    """
    current = compute_exposure(portfolio, spots)

    total_ext_loss = 0.0
    option_dd_current = 0.0
    pos_details = []

    for pos in portfolio.get("positions", []):
        ticker = pos.get("ticker", "")
        spot = spots.get(ticker)
        is_stock = all(leg["type"] == "Stock" for leg in pos.get("legs", []))

        if is_stock or not spot or spot <= 0:
            pos_details.append({
                "ticker": ticker,
                "extrinsic_loss": 0,
                "delta_change": 0,
            })
            if is_stock and spot and spot > 0:
                # Stock dollar delta unchanged
                pass
            continue

        # Compute current option dollar delta for this position
        delta = compute_position_delta(pos, spot)
        pos_dd = delta * spot
        option_dd_current += pos_dd

        # Extrinsic loss per leg
        pos_ext_loss = 0.0
        for leg in pos.get("legs", []):
            if leg["type"] == "Stock":
                continue
            sign = 1 if leg["direction"] == "LONG" else -1
            ext = _leg_extrinsic(leg, spot)
            leg_loss = sign * decay_pct * ext * leg["contracts"] * 100
            pos_ext_loss += leg_loss

        total_ext_loss += pos_ext_loss
        pos_details.append({
            "ticker": ticker,
            "extrinsic_loss": round(pos_ext_loss, 2),
            "delta_change": round(-decay_pct * pos_dd, 2),
        })

    # Stressed dollar delta: option portion scales, stock portion unchanged
    stock_dd = current["dollar_delta"] - option_dd_current
    stressed_dd = stock_dd + option_dd_current * (1 - decay_pct)

    stressed = {
        "net_liq": round(current["net_liq"] - total_ext_loss, 2),
        "dollar_delta": round(stressed_dd, 2),
        "net_long": current["net_long"],  # classification unchanged
        "net_short": current["net_short"],
    }

    return {
        "scenario": "delta_decay",
        "parameters": {"decay_pct": decay_pct},
        "current": {k: round(v, 2) for k, v in current.items()},
        "stressed": stressed,
        "impact": {
            "net_liq_change": round(-total_ext_loss, 2),
            "dollar_delta_change": round(stressed_dd - current["dollar_delta"], 2),
            "net_long_change": 0,
        },
        "positions": pos_details,
    }


# ── CLI ─────────────────────────────────────────────────

if __name__ == "__main__":
    p = argparse.ArgumentParser(description="Portfolio scenario analysis")
    sub = p.add_subparsers(dest="scenario", required=True)

    # price_shock
    ps = sub.add_parser("price_shock", help="Underlying price shock scenario")
    ps.add_argument("--shock", type=float, required=True,
                    help="Shock percentage (e.g., -10 for -10%%)")
    ps.add_argument("--spots", type=str, required=True,
                    help='JSON dict of ticker→spot prices, e.g. \'{"AAPL":250}\'')

    # delta_decay
    dd = sub.add_parser("delta_decay", help="Delta decay scenario (no price movement)")
    dd.add_argument("--decay", type=float, required=True,
                    help="Decay percentage (e.g., 10 for 10%%)")
    dd.add_argument("--spots", type=str, required=True,
                    help='JSON dict of ticker→spot prices')

    args = p.parse_args()
    portfolio = load_portfolio()
    spots = json.loads(args.spots)

    if args.scenario == "price_shock":
        result = scenario_price_shock(portfolio, spots, shock_pct=args.shock / 100)
    elif args.scenario == "delta_decay":
        result = scenario_delta_decay(portfolio, spots, decay_pct=args.decay / 100)

    print(json.dumps(result, indent=2))
