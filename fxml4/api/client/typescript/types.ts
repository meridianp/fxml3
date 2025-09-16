/**
 * FXML4 API TypeScript Type Definitions
 * Version: 2.0.0
 *
 * These types can be used with any TypeScript/JavaScript HTTP client
 * to interact with the FXML4 API.
 */

// Enums
export enum Timeframe {
  ONE_MINUTE = "1m",
  THREE_MINUTES = "3m",
  FIVE_MINUTES = "5m",
  FIFTEEN_MINUTES = "15m",
  THIRTY_MINUTES = "30m",
  ONE_HOUR = "1h",
  TWO_HOURS = "2h",
  FOUR_HOURS = "4h",
  SIX_HOURS = "6h",
  TWELVE_HOURS = "12h",
  ONE_DAY = "1d",
  ONE_WEEK = "1w",
  ONE_MONTH = "1M"
}

export enum Strategy {
  INTEGRATED = "integrated_strategy",
  ML = "ml_strategy",
  WAVE = "wave_strategy",
  SENTIMENT = "sentiment_strategy",
  HYBRID = "hybrid_strategy",
  CUSTOM = "custom_strategy",
  ENSEMBLE = "ensemble_strategy"
}

export enum SignalType {
  ENTRY_LONG = "entry_long",
  ENTRY_SHORT = "entry_short",
  EXIT_LONG = "exit_long",
  EXIT_SHORT = "exit_short",
  SCALE_IN = "scale_in",
  SCALE_OUT = "scale_out",
  STOP_LOSS = "stop_loss",
  TAKE_PROFIT = "take_profit",
  TRAILING_STOP = "trailing_stop"
}

export enum DataSource {
  ALPHA_VANTAGE = "alpha_vantage",
  INTERACTIVE_BROKERS = "interactive_brokers",
  POLYGON = "polygon",
  YAHOO = "yahoo",
  BINANCE = "binance",
  CUSTOM = "custom"
}

export enum OrderSide {
  BUY = "buy",
  SELL = "sell"
}

// Request interfaces
export interface DataRequest {
  symbol: string;
  timeframe: Timeframe;
  start_date: string;  // ISO 8601 format
  end_date: string;    // ISO 8601 format
  limit?: number;
  source?: DataSource;
  include_indicators?: string[];
}

export interface SignalRequest {
  symbol: string;
  timeframe: Timeframe;
  strategy: Strategy;
  lookback_periods?: number;
  confidence_threshold?: number;
  parameters?: Record<string, any>;
  real_time?: boolean;
}

export interface BacktestRequest {
  symbol: string;
  timeframe: Timeframe;
  strategy: Strategy | Strategy[];
  start_date: string;
  end_date: string;
  initial_capital?: number;
  commission?: number;
  slippage?: number;
  position_size?: number;
  max_positions?: number;
  parameters?: Record<string, any>;
  monte_carlo?: boolean;
  walk_forward?: boolean;
  auto_report?: boolean;
}

// Response interfaces
export interface ApiResponse<T = any> {
  success: boolean;
  message: string;
  timestamp: string;
  request_id?: string;
  data?: T;
}

export interface ErrorResponse extends ApiResponse {
  success: false;
  error: string;
  details?: ErrorDetail[];
  help_url?: string;
}

export interface ErrorDetail {
  field?: string;
  message: string;
  code?: string;
}

export interface PaginationMeta {
  page: number;
  page_size: number;
  total_items: number;
  total_pages: number;
  has_next: boolean;
  has_previous: boolean;
}

export interface PaginatedResponse<T> {
  items: T[];
  meta: PaginationMeta;
}

// Data models
export interface MarketData {
  timestamp: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
  quality_score?: number;
  indicators?: Record<string, number>;
}

export interface Signal {
  id: string;
  symbol: string;
  timestamp: string;
  signal_type: SignalType;
  confidence: number;
  strength: number;
  price: number;
  target_price?: number;
  stop_loss?: number;
  timeframe: Timeframe;
  strategy: string;
  description: string;
  metadata?: Record<string, any>;
  indicators?: Record<string, number>;
}

export interface TradeInfo {
  id: string;
  position_id: string;
  symbol: string;
  side: OrderSide;
  entry_price: number;
  entry_time: string;
  quantity: number;
  exit_price?: number;
  exit_time?: string;
  pnl?: number;
  pnl_pct?: number;
  commission?: number;
  slippage?: number;
  status: string;
  strategy: string;
  entry_reason: string;
  exit_reason?: string;
  max_drawdown?: number;
  hold_time?: number;
  metadata?: Record<string, any>;
}

export interface BacktestResult {
  backtest_id: string;
  symbol: string;
  timeframe: string;
  strategy: string | string[];
  period: {
    start: string;
    end: string;
  };
  performance: {
    initial_capital: number;
    final_capital: number;
    total_return: number;
    total_return_pct: number;
    annualized_return: number;
    max_drawdown: number;
    max_drawdown_pct: number;
    sharpe_ratio: number;
    sortino_ratio: number;
    calmar_ratio: number;
    win_rate: number;
    profit_factor: number;
    expectancy: number;
    var_95: number;
    cvar_95: number;
  };
  trade_statistics: {
    total_trades: number;
    winning_trades: number;
    losing_trades: number;
    avg_win: number;
    avg_loss: number;
    best_trade: number;
    worst_trade: number;
    avg_hold_time: number;
    max_consecutive_wins: number;
    max_consecutive_losses: number;
  };
  monte_carlo?: {
    simulations: number;
    confidence_intervals: {
      return_95: [number, number];
      drawdown_95: [number, number];
    };
    probability_of_profit: number;
    probability_of_drawdown_10pct: number;
  };
  walk_forward?: {
    in_sample_periods: number;
    out_sample_periods: number;
    efficiency_ratio: number;
    robustness_score: number;
  };
  report_url?: string;
}

// WebSocket messages
export interface WebSocketMessage<T = any> {
  type: string;
  channel: string;
  data: T;
  timestamp: string;
  sequence?: number;
}

// Filter interfaces
export interface DateRangeFilter {
  start_date?: string;
  end_date?: string;
}

export interface DataFilter {
  symbols?: string[];
  timeframes?: string[];
  sources?: string[];
  date_range?: DateRangeFilter;
  quality_score_min?: number;
}

export interface SignalFilter {
  symbols?: string[];
  signal_types?: string[];
  strategies?: string[];
  confidence_min?: number;
  strength_min?: number;
  date_range?: DateRangeFilter;
  active_only?: boolean;
}

export interface BacktestFilter {
  symbols?: string[];
  strategies?: string[];
  date_range?: DateRangeFilter;
  min_return?: number;
  max_drawdown?: number;
  min_sharpe?: number;
  status?: string[];
  tags?: string[];
}

// Batch operation types
export interface BatchOperation {
  id?: string;
  type: "data" | "signals" | "backtest";
  params: DataRequest | SignalRequest | BacktestRequest;
}

export interface BatchResult {
  id: string;
  type: string;
  status: "success" | "failed";
  data?: any;
  error?: string;
}

// Version information
export interface VersionInfo {
  current_version: string;
  supported_versions: string[];
  versions: Record<string, {
    status: "active" | "deprecated" | "sunset" | "retired";
    release_date?: string;
    deprecated_date?: string;
    sunset_date?: string;
    retirement_date?: string;
    successor?: string;
    changes: string[];
  }>;
}

// Authentication types
export interface TokenResponse {
  access_token: string;
  token_type: string;
  expires_in?: number;
}

export interface User {
  username: string;
  email?: string;
  full_name?: string;
  disabled?: boolean;
  scopes?: string[];
}

// Rate limit information
export interface RateLimitInfo {
  limit: number;
  remaining: number;
  reset: string;
  retry_after?: number;
}
