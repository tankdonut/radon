"use client";

import { useCallback, useEffect, useState } from "react";
import { fmtPrice } from "@/components/WorkspaceSections";

type RatingChange = {
  firm: string;
  action: string;
  from_rating?: string;
  to_rating?: string;
  target_price?: number;
  date?: string;
};

type RatingsData = {
  ticker: string;
  recommendation?: string;
  analyst_count?: number;
  buy_count?: number;
  hold_count?: number;
  sell_count?: number;
  strong_buy_count?: number;
  strong_sell_count?: number;
  price_target_low?: number;
  price_target_high?: number;
  price_target_mean?: number;
  price_target_median?: number;
  recent_changes?: RatingChange[];
  [key: string]: unknown;
};

type RatingsTabProps = {
  ticker: string;
  active: boolean;
  currentPrice?: number | null;
};

function recPillClass(rec: string): string {
  const r = rec.toLowerCase();
  if (r.includes("buy") || r.includes("outperform") || r.includes("overweight")) return "bullish";
  if (r.includes("sell") || r.includes("underperform") || r.includes("underweight")) return "bearish";
  return "neutral";
}

export default function RatingsTab({ ticker, active, currentPrice }: RatingsTabProps) {
  const [data, setData] = useState<RatingsData | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [fetched, setFetched] = useState(false);

  const fetchRatings = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`/api/ticker/ratings?ticker=${encodeURIComponent(ticker)}`);
      if (!res.ok) {
        const json = await res.json().catch(() => ({}));
        throw new Error(json.error || `Failed to fetch ratings (${res.status})`);
      }
      const json = await res.json();
      // API may return array — unwrap first element
      const item = Array.isArray(json) ? json[0] : json;
      if (item?.error) {
        throw new Error(item.error);
      }
      setData(item ?? null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to fetch ratings");
    } finally {
      setLoading(false);
      setFetched(true);
    }
  }, [ticker]);

  useEffect(() => {
    if (active && !fetched) {
      fetchRatings();
    }
  }, [active, fetched, fetchRatings]);

  if (loading) {
    return (
      <div className="tab-loading">
        <div className="tab-loading-text">Loading ratings...</div>
      </div>
    );
  }

  if (error) {
    return <div className="tab-error">{error}</div>;
  }

  if (!data) {
    return <div className="tab-empty">No analyst data for {ticker}</div>;
  }

  const total = (data.strong_buy_count ?? 0) + (data.buy_count ?? 0) + (data.hold_count ?? 0) + (data.sell_count ?? 0) + (data.strong_sell_count ?? 0);

  return (
    <div className="ratings-tab">
      {/* Recommendation pill */}
      {data.recommendation && (
        <div className="ratings-rec">
          <span className={`ratings-rec-pill ${recPillClass(data.recommendation)}`}>
            {data.recommendation}
          </span>
          {data.analyst_count != null && (
            <span className="ratings-count">{data.analyst_count} analysts</span>
          )}
        </div>
      )}

      {/* Ratings bar */}
      {total > 0 && (
        <div className="ratings-bar-wrap">
          <div className="ratings-bar">
            {(data.strong_buy_count ?? 0) > 0 && (
              <div className="ratings-bar-seg ratings-strong-buy" style={{ flex: data.strong_buy_count }}>
                {data.strong_buy_count}
              </div>
            )}
            {(data.buy_count ?? 0) > 0 && (
              <div className="ratings-bar-seg ratings-buy" style={{ flex: data.buy_count }}>
                {data.buy_count}
              </div>
            )}
            {(data.hold_count ?? 0) > 0 && (
              <div className="ratings-bar-seg ratings-hold" style={{ flex: data.hold_count }}>
                {data.hold_count}
              </div>
            )}
            {(data.sell_count ?? 0) > 0 && (
              <div className="ratings-bar-seg ratings-sell" style={{ flex: data.sell_count }}>
                {data.sell_count}
              </div>
            )}
            {(data.strong_sell_count ?? 0) > 0 && (
              <div className="ratings-bar-seg ratings-strong-sell" style={{ flex: data.strong_sell_count }}>
                {data.strong_sell_count}
              </div>
            )}
          </div>
          <div className="ratings-bar-labels">
            <span>Strong Buy</span>
            <span>Buy</span>
            <span>Hold</span>
            <span>Sell</span>
            <span>Strong Sell</span>
          </div>
        </div>
      )}

      {/* Price targets */}
      {(data.price_target_low != null || data.price_target_high != null) && (
        <div className="ratings-targets">
          <div className="ratings-targets-title">Price Targets</div>
          <div className="ratings-targets-grid">
            {data.price_target_low != null && (
              <div className="pos-stat">
                <span className="pos-stat-label">Low</span>
                <span className="pos-stat-value">{fmtPrice(data.price_target_low)}</span>
              </div>
            )}
            {data.price_target_median != null && (
              <div className="pos-stat">
                <span className="pos-stat-label">Median</span>
                <span className="pos-stat-value">{fmtPrice(data.price_target_median)}</span>
              </div>
            )}
            {data.price_target_mean != null && (
              <div className="pos-stat">
                <span className="pos-stat-label">Mean</span>
                <span className="pos-stat-value">{fmtPrice(data.price_target_mean)}</span>
              </div>
            )}
            {data.price_target_high != null && (
              <div className="pos-stat">
                <span className="pos-stat-label">High</span>
                <span className="pos-stat-value">{fmtPrice(data.price_target_high)}</span>
              </div>
            )}
            {currentPrice != null && (
              <div className="pos-stat">
                <span className="pos-stat-label">Current</span>
                <span className="pos-stat-value">{fmtPrice(currentPrice)}</span>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Recent changes */}
      {data.recent_changes && data.recent_changes.length > 0 && (
        <div className="ratings-changes">
          <div className="ratings-targets-title">Recent Changes</div>
          <table className="pos-legs-table">
            <thead>
              <tr>
                <th>Date</th>
                <th>Firm</th>
                <th>Action</th>
                <th>Rating</th>
                <th className="right">Target</th>
              </tr>
            </thead>
            <tbody>
              {data.recent_changes.slice(0, 10).map((c, i) => (
                <tr key={i}>
                  <td>{c.date || "---"}</td>
                  <td>{c.firm}</td>
                  <td>{c.action}</td>
                  <td>
                    {c.from_rating && c.to_rating
                      ? `${c.from_rating} → ${c.to_rating}`
                      : c.to_rating || c.from_rating || "---"}
                  </td>
                  <td className="right">{c.target_price != null ? fmtPrice(c.target_price) : "---"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
