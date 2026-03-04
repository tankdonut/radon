import type { LayoutDashboard } from "lucide-react";

export type MessageRole = "assistant" | "user";

export type Message = {
  id: string;
  role: MessageRole;
  content: string;
  timestamp: string;
};

export type FlowRow = {
  ticker: string;
  position: string;
  flowLabel: string;
  flowClass: string;
  strength: string;
  note: string;
};

export type ApiMessage = {
  role: MessageRole;
  content: string;
};

export type AssistantResponse = {
  content?: string;
  model?: string;
  error?: string;
};

export type PiResponse = {
  command: string;
  status: "ok" | "error";
  output: string;
  stderr?: string;
  error?: string;
};

export type WorkspaceSection = "dashboard" | "flow-analysis" | "portfolio" | "orders" | "scanner" | "discover" | "journal";

export type JsonValue = string | number | boolean | null | JsonValue[] | { [key: string]: JsonValue };

export type WorkspaceNavItem = {
  label: string;
  route: WorkspaceSection;
  href: string;
  icon: typeof LayoutDashboard;
};

export type PortfolioLeg = {
  direction: "LONG" | "SHORT";
  contracts: number;
  type: "Call" | "Put" | "Stock";
  strike: number | null;
  entry_cost: number;
  avg_cost: number;
  market_price: number | null;
  market_value: number | null;
  market_price_is_calculated?: boolean;
};

export type PortfolioPosition = {
  id: number;
  ticker: string;
  structure: string;
  structure_type: string;
  risk_profile: string;
  expiry: string;
  contracts: number;
  direction: string;
  entry_cost: number;
  max_risk: number | null;
  market_value: number | null;
  legs: PortfolioLeg[];
  market_price_is_calculated?: boolean;
  kelly_optimal: number | null;
  target: number | null;
  stop: number | null;
  entry_date: string;
};

export type OrderContract = {
  conId: number | null;
  symbol: string;
  secType: string;
  strike: number | null;
  right: string | null;
  expiry: string | null;
};

export type OpenOrder = {
  orderId: number;
  permId: number;
  symbol: string;
  contract: OrderContract;
  action: string;
  orderType: string;
  totalQuantity: number;
  limitPrice: number | null;
  auxPrice: number | null;
  status: string;
  filled: number;
  remaining: number;
  avgFillPrice: number | null;
  tif: string;
};

export type ExecutedOrder = {
  execId: string;
  symbol: string;
  contract: OrderContract;
  side: string;
  quantity: number;
  avgPrice: number | null;
  commission: number | null;
  realizedPNL: number | null;
  time: string;
  exchange: string;
};

export type OrdersData = {
  last_sync: string;
  open_orders: OpenOrder[];
  executed_orders: ExecutedOrder[];
  open_count: number;
  executed_count: number;
};

export type PortfolioData = {
  bankroll: number;
  peak_value: number;
  last_sync: string;
  positions: PortfolioPosition[];
  total_deployed_pct: number;
  total_deployed_dollars: number;
  remaining_capacity_pct: number;
  position_count: number;
  defined_risk_count: number;
  undefined_risk_count: number;
  avg_kelly_optimal: number | null;
};

// Real-time pricing types
export type PriceData = {
  symbol: string;
  last: number | null;
  lastIsCalculated: boolean;
  bid: number | null;
  ask: number | null;
  bidSize: number | null;
  askSize: number | null;
  volume: number | null;
  high: number | null;
  low: number | null;
  open: number | null;
  close: number | null;
  timestamp: string;
};

export type PriceUpdate = {
  symbol: string;
  data: PriceData;
  receivedAt: Date;
};
