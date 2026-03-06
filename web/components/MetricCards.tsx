import type { PortfolioData } from "@/lib/types";
import type { PriceData } from "@/lib/pricesProtocol";
import { legPriceKey } from "@/components/WorkspaceSections";

type MetricCardsProps = {
  portfolio: PortfolioData | null;
  prices?: Record<string, PriceData>;
  realizedPnl?: number;
};

const fmt = (n: number) =>
  n >= 1_000_000
    ? `$${(n / 1_000_000).toFixed(2)}M`
    : `$${n.toLocaleString("en-US", { maximumFractionDigits: 0 })}`;

const fmtSigned = (n: number) =>
  `${n >= 0 ? "+" : ""}${fmt(Math.abs(n))}`;

function resolveMarketValue(pos: PortfolioData["positions"][number]): number | null {
  if (pos.market_value != null) return pos.market_value;
  const known = pos.legs.filter((l) => l.market_value != null);
  return known.length > 0 ? known.reduce((s, l) => s + l.market_value!, 0) : null;
}

function computePnL(portfolio: PortfolioData) {
  let totalPnL = 0;
  for (const pos of portfolio.positions) {
    const mv = resolveMarketValue(pos);
    if (mv != null) {
      totalPnL += mv - pos.entry_cost;
    }
  }
  return totalPnL;
}

function computeTodayUnrealizedPnl(
  portfolio: PortfolioData,
  prices: Record<string, PriceData>,
): { pnl: number; positionsWithData: number; totalPositions: number } {
  let pnl = 0;
  let positionsWithData = 0;
  const totalPositions = portfolio.positions.length;

  for (const pos of portfolio.positions) {
    if (pos.structure_type === "Stock") {
      const p = prices[pos.ticker];
      if (p?.last != null && p.last > 0 && p?.close != null && p.close > 0) {
        pnl += (p.last - p.close) * pos.contracts;
        positionsWithData++;
      }
      continue;
    }

    // Options / spreads: sum across legs
    let legPnl = 0;
    let allLegsValid = true;
    for (const leg of pos.legs) {
      const key = legPriceKey(pos.ticker, pos.expiry, leg);
      const lp = key ? prices[key] : null;
      if (!lp || lp.last == null || lp.last <= 0 || lp.close == null || lp.close <= 0) {
        allLegsValid = false;
        break;
      }
      const sign = leg.direction === "LONG" ? 1 : -1;
      legPnl += sign * (lp.last - lp.close) * leg.contracts * 100;
    }
    if (allLegsValid) {
      pnl += legPnl;
      positionsWithData++;
    }
  }

  return { pnl, positionsWithData, totalPositions };
}

export default function MetricCards({ portfolio, prices, realizedPnl }: MetricCardsProps) {
  if (!portfolio) {
    const placeholders = ["Net Liquidation", "Positions", "Deployed", "Open P&L"];
    return (
      <>
        <div className="section-label-mono">NET LEVERAGE</div>
        <div className="metrics-grid">
          {placeholders.map((label, i) => (
            <div key={i} className="metric-card metric-card-loading">
              <div className="metric-label">{label}</div>
              <div className="metric-value">$0,000</div>
              <div className="metric-change neutral">AWAITING SYNC</div>
            </div>
          ))}
        </div>
      </>
    );
  }

  const pnl = computePnL(portfolio);
  const pnlPct = portfolio.total_deployed_dollars > 0
    ? (pnl / portfolio.total_deployed_dollars) * 100
    : 0;

  const cards = [
    {
      label: "Net Liquidation",
      value: fmt(portfolio.bankroll),
      change: "BANKROLL",
      tone: "neutral" as const,
    },
    {
      label: "Positions",
      value: String(portfolio.position_count),
      change: `${portfolio.defined_risk_count} DEFINED / ${portfolio.undefined_risk_count} UNDEFINED`,
      tone: "neutral" as const,
    },
    {
      label: "Deployed",
      value: fmt(portfolio.total_deployed_dollars),
      change: `${portfolio.total_deployed_pct.toFixed(1)}% OF BANKROLL`,
      tone: portfolio.total_deployed_pct > 100 ? ("negative" as const) : ("neutral" as const),
    },
    {
      label: "Open P&L",
      value: `${pnl >= 0 ? "+" : ""}${fmt(Math.abs(pnl))}`,
      change: `${pnlPct >= 0 ? "+" : ""}${pnlPct.toFixed(1)}%`,
      tone: pnl >= 0 ? ("positive" as const) : ("negative" as const),
    },
  ];

  // Today's P&L computation
  const hasPrices = prices && Object.keys(prices).length > 0;
  const todayUnrealized = hasPrices
    ? computeTodayUnrealizedPnl(portfolio, prices)
    : null;
  const hasDaily = todayUnrealized != null && todayUnrealized.positionsWithData > 0;
  const unrealized = todayUnrealized?.pnl ?? 0;
  const realized = realizedPnl ?? 0;
  const total = unrealized + realized;

  return (
    <>
      <div className="section-label-mono">NET LEVERAGE</div>
      <div className="metrics-grid">
        {cards.map((item) => (
          <div key={item.label} className="metric-card">
            <div className="metric-label">{item.label}</div>
            <div className="metric-value">{item.value}</div>
            <div
              className={`metric-change ${
                item.tone === "positive" ? "positive" : item.tone === "negative" ? "negative" : "neutral"
              }`}
            >
              {item.change}
            </div>
          </div>
        ))}
      </div>

      <div className="section-label-mono">TODAY&apos;S P&amp;L</div>
      {hasDaily ? (
        <div className="metrics-grid-3">
          <div className="metric-card">
            <div className="metric-label">Unrealized</div>
            <div className="metric-value">{fmtSigned(unrealized)}</div>
            <div className="metric-change neutral">
              {todayUnrealized!.positionsWithData} OF {todayUnrealized!.totalPositions} POSITIONS
            </div>
          </div>
          <div className="metric-card">
            <div className="metric-label">Realized</div>
            <div className="metric-value">{fmtSigned(realized)}</div>
            <div className="metric-change neutral">TODAY&apos;S FILLS</div>
          </div>
          <div className="metric-card">
            <div className="metric-label">Total</div>
            <div className={`metric-value ${total >= 0 ? "positive" : "negative"}`}>
              {fmtSigned(total)}
            </div>
            <div className={`metric-change ${total >= 0 ? "positive" : "negative"}`}>
              COMBINED
            </div>
          </div>
        </div>
      ) : (
        <div className="metrics-grid-3">
          <div className="metric-card metric-card-loading">
            <div className="metric-label">Unrealized</div>
            <div className="metric-value">---</div>
            <div className="metric-change neutral">MARKET CLOSED</div>
          </div>
          <div className="metric-card metric-card-loading">
            <div className="metric-label">Realized</div>
            <div className="metric-value">{realizedPnl != null ? fmtSigned(realized) : "---"}</div>
            <div className="metric-change neutral">{realizedPnl != null ? "TODAY'S FILLS" : "MARKET CLOSED"}</div>
          </div>
          <div className="metric-card metric-card-loading">
            <div className="metric-label">Total</div>
            <div className="metric-value">---</div>
            <div className="metric-change neutral">MARKET CLOSED</div>
          </div>
        </div>
      )}
    </>
  );
}
