export interface Config {
  symbols: string[];
  candle_interval: string;
  short_window: number;
  long_window: number;
  lookback_days: number;
  max_investment: number;
  max_slots: number;
  rotation_weakness_pct: number;
  rotation_enabled: boolean;
}

export interface WatchlistRow {
  symbol: string;
  close?: number;
  short_ma?: number;
  long_ma?: number;
  distance_pct?: number;
  signal?: "bullish" | "bearish" | null;
  evaluated_at?: string | null;
  error?: string;
}

export interface Position {
  symbol: string;
  qty: string;
  side: string;
  market_value: string;
  avg_entry_price: string;
  current_price: string;
  unrealized_pl: string;
  unrealized_plpc: string;
}

export interface Trade {
  id: number;
  order_id: string;
  symbol: string;
  side: string;
  qty: number | null;
  notional: number | null;
  filled_qty: number | null;
  filled_avg_price: number | null;
  status: string;
  reason: string | null;
  submitted_at: string | null;
  recorded_at: string;
  synced_at: string | null;
}

export interface RealizedPnlRow {
  symbol: string;
  realized_pnl: number;
  matched_qty: number;
  open_qty_unmatched: number;
}

export interface PnlSummary {
  realized: RealizedPnlRow[];
  total_realized_pnl: number;
}

export interface Run {
  id: number;
  started_at: string;
  finished_at: string;
  status: "success" | "partial" | "error";
  error_message: string | null;
  log: string;
}

export interface Schedule {
  time1: string;
  time2: string;
  timezone: string;
  enabled: boolean;
  saved?: boolean;
  next_run?: string | null;
}
