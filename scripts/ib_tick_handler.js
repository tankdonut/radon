/**
 * IB tick handler — pure functions for processing tickPrice/tickSize events.
 * Extracted from ib_realtime_server.js so they can be unit-tested independently.
 */

import IB from "ib";

const { TICK_TYPE } = IB;

export function normalizeNumber(value) {
  if (typeof value !== "number" || !Number.isFinite(value) || value < 0) {
    return null;
  }
  return value;
}

export function createPriceData(symbol) {
  return {
    symbol,
    last: null,
    lastIsCalculated: false,
    bid: null,
    ask: null,
    bidSize: null,
    askSize: null,
    volume: null,
    high: null,
    low: null,
    open: null,
    close: null,
    delta: null,
    gamma: null,
    theta: null,
    vega: null,
    impliedVol: null,
    undPrice: null,
    timestamp: new Date().toISOString(),
  };
}

export function updateDerivedLast(data) {
  if (data.last == null && data.bid != null && data.ask != null) {
    const midpoint = (data.bid + data.ask) / 2;
    data.last = Number.isFinite(midpoint) ? Number(midpoint.toFixed(4)) : null;
    data.lastIsCalculated = true;
  }
  // Cash indexes (e.g. VIX, VVIX) report their value via CLOSE tick, not LAST.
  // If last is still null after bid/ask check, use close as the live value.
  if (data.last == null && data.close != null) {
    data.last = data.close;
    data.lastIsCalculated = true;
  }
}

export function updatePriceFromTickPrice(data, tickType, value) {
  switch (tickType) {
    // ── Live tick types ───────────────────────────────────────────────────
    case TICK_TYPE.BID:
      data.bid = normalizeNumber(value);
      data.lastIsCalculated = false;
      break;
    case TICK_TYPE.ASK:
      data.ask = normalizeNumber(value);
      data.lastIsCalculated = false;
      break;
    case TICK_TYPE.LAST:
      data.last = normalizeNumber(value);
      data.lastIsCalculated = false;
      break;
    case TICK_TYPE.HIGH:
      data.high = normalizeNumber(value);
      break;
    case TICK_TYPE.LOW:
      data.low = normalizeNumber(value);
      break;
    case TICK_TYPE.OPEN:
      data.open = normalizeNumber(value);
      break;
    case TICK_TYPE.CLOSE:
      data.close = normalizeNumber(value);
      break;
    case TICK_TYPE.VOLUME:
      data.volume = normalizeNumber(value);
      break;

    // ── Delayed tick types (reqMarketDataType(4) fallback for indexes) ────
    // IB sends these instead of live types when a real-time subscription is
    // absent. VIX/VVIX always receive delayed ticks because they require a
    // separate CBOE index subscription.
    case TICK_TYPE.DELAYED_BID:         // 66
      data.bid = normalizeNumber(value);
      data.lastIsCalculated = false;
      break;
    case TICK_TYPE.DELAYED_ASK:         // 67
      data.ask = normalizeNumber(value);
      data.lastIsCalculated = false;
      break;
    case TICK_TYPE.DELAYED_LAST:        // 68
      data.last = normalizeNumber(value);
      data.lastIsCalculated = false;
      break;
    case TICK_TYPE.DELAYED_HIGH:        // 72
      data.high = normalizeNumber(value);
      break;
    case TICK_TYPE.DELAYED_LOW:         // 73
      data.low = normalizeNumber(value);
      break;
    case TICK_TYPE.DELAYED_VOLUME:      // 74
      data.volume = normalizeNumber(value);
      break;
    case TICK_TYPE.DELAYED_CLOSE:       // 75
      data.close = normalizeNumber(value);
      break;
    case TICK_TYPE.DELAYED_OPEN:        // 76
      data.open = normalizeNumber(value);
      break;

    default:
      break;
  }

  if (data.last == null) {
    updateDerivedLast(data);
  }
  data.timestamp = new Date().toISOString();
}

export function updatePriceFromTickSize(data, sizeType, value) {
  switch (sizeType) {
    case TICK_TYPE.BID_SIZE:
      data.bidSize = normalizeNumber(value);
      break;
    case TICK_TYPE.ASK_SIZE:
      data.askSize = normalizeNumber(value);
      break;
    case TICK_TYPE.VOLUME:
      data.volume = normalizeNumber(value);
      break;
    case TICK_TYPE.DELAYED_BID_SIZE:    // 69
      data.bidSize = normalizeNumber(value);
      break;
    case TICK_TYPE.DELAYED_ASK_SIZE:    // 70
      data.askSize = normalizeNumber(value);
      break;
    case TICK_TYPE.DELAYED_VOLUME:      // 74
      data.volume = normalizeNumber(value);
      break;
    case TICK_TYPE.LAST_SIZE:
      break;
    default:
      break;
  }

  data.timestamp = new Date().toISOString();
}
