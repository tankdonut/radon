# Progress

## Session: 2026-03-04 — Cancel & Modify Order Actions on /orders Page

### Problem
The orders page displayed open orders from IB but had no ability to act on them. Users needed Cancel and Modify buttons directly in the open orders table.

### Solution
Full-stack implementation: Python CLI for IB order management, Next.js API routes, reusable modal component, and cancel/modify dialogs with real-time bid/ask data.

### Files Created
1. **`scripts/ib_order_manage.py`** — Python CLI: cancel/modify orders via IB API (client ID 12). Finds trades by `permId` (preferred) or `orderId`. All output is JSON to stdout.
2. **`scripts/tests/test_ib_order_manage.py`** — 16 unit tests covering find_trade, cancel, modify, edge cases (filled, MKT, zero price, STP LMT)
3. **`web/app/api/orders/cancel/route.ts`** — POST endpoint: spawns `ib_order_manage.py cancel`, then refreshes `orders.json` via sync
4. **`web/app/api/orders/modify/route.ts`** — POST endpoint: spawns `ib_order_manage.py modify`, then refreshes `orders.json` via sync
5. **`web/components/Modal.tsx`** — Reusable modal: portal to body, esc key, click-outside, scroll lock, slide-up animation
6. **`web/components/CancelOrderDialog.tsx`** — Cancel confirmation showing order details, partial-fill warning
7. **`web/components/ModifyOrderModal.tsx`** — Modify modal with bid/ask market data, price input, BID/MID/ASK quick-set buttons, change indicator

### Files Modified
1. **`scripts/utils/ib_connection.py`** — Added `"ib_order_manage": 12` to CLIENT_IDS
2. **`scripts/ib_orders.py`** — Added `permId` to order data, `conId` to contract serialization
3. **`web/lib/types.ts`** — Added `permId` to `OpenOrder`, `conId` to `OrderContract`
4. **`web/lib/useOrders.ts`** — Added `updateData()` method for optimistic updates from action responses
5. **`web/components/WorkspaceSections.tsx`** — Added Actions column (MODIFY + CANCEL buttons), cancel/modify state + handlers, modal rendering, bid/ask resolution for STK/OPT/BAG
6. **`web/components/WorkspaceShell.tsx`** — Threads `addToast`, `syncNow`, `onOrdersUpdate` to WorkspaceSections
7. **`web/app/globals.css`** — Modal styles, order action buttons, cancel/modify dialog styles, shared button styles
8. **`CLAUDE.md`** — Added `ib_order_manage.py` to Key Scripts table

### Key Behaviors
- **Cancel**: Works for all order types. Warns on partial fills. Uses `permId` for lookup (globally unique across IB sessions)
- **Modify**: Only enabled for LMT/STP LMT orders. Shows real-time bid/ask with quick-set buttons. BAG orders show "market data unavailable" warning
- **After action**: API refreshes `orders.json` via sync, returns fresh data in response for instant UI update

### Verification
- TypeScript: Compiles clean (no new errors)
- Python: 16/16 tests pass
- Backward compatible: Existing order display unchanged, new fields (`permId`, `conId`) are additive

---

## Session: 2026-03-03 — Real-Time Option Contract Price Subscriptions

### Changes Made

**Problem**: IB realtime WS server only subscribed to stock contracts, leaving options positions with stale sync data.

**Solution**: Extended the WS protocol with composite keys (`SYMBOL_YYYYMMDD_STRIKE_RIGHT`) so both stock and option prices coexist in the same price map.

#### Files Modified

1. **`web/lib/pricesProtocol.ts`** — Added `OptionContract` type, `optionKey()`, `contractsKey()`, `portfolioLegToContract()` helpers
2. **`scripts/ib_realtime_server.js`** — Added `normalizeContracts()` validator, refactored `startLiveSubscription(key, ibContract)` to accept pre-built contracts, option subscribe handler via `ib.contract.option()`, updated `restoreSubscriptions()` to use stored contracts
3. **`web/lib/usePrices.ts`** — Added `contracts` option to `UsePricesOptions`, `contractHash` memoization, contracts in WS subscribe message
4. **`web/components/WorkspaceShell.tsx`** — Added `portfolioContracts` useMemo that extracts option legs from portfolio, passed to `usePrices()`
5. **`web/components/WorkspaceSections.tsx`** — Added `legPriceKey()` helper, real-time MV computation for options (sum of `sign * last * contracts * 100`), daily change as % of entry cost, `LegRow` displays WS leg prices

### Verification
- TypeScript: All modified files compile clean (`npx tsc --noEmit`)
- Server: Syntax check passes (`node --check`)
- Backward compatible: Stock subscriptions unchanged

### Architecture Notes
- Composite key format: `{SYMBOL}_{YYYYMMDD}_{STRIKE}_{RIGHT}` (e.g., `EWY_20260417_42_P`)
- Server `startLiveSubscription(key, ibContract)` now takes a pre-built IB contract object
- Client subscribe message: `{ action: "subscribe", symbols: [...], contracts: [{ symbol, expiry, strike, right }] }`
- Options daily change = `sum(sign * (last - close) * contracts * 100) / |entryCost| * 100`
