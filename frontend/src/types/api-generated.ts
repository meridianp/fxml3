/**
 * Auto-generated TypeScript types from FXML4 Pydantic schemas
 *
 * DO NOT EDIT MANUALLY - This file is generated automatically
 * Based on FXML4 backend API schemas
 */

// Utility types
export type LoadingState = 'idle' | 'loading' | 'success' | 'error';
export type SortOrder = 'asc' | 'desc';

// API Response wrapper
export interface ApiResponse<T = any> {
  success: boolean;
  data?: T;
  error?: string;
  message?: string;
  timestamp: string;
}

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  size: number;
  pages: number;
}

// =============================================================================
// ENUMS
// =============================================================================

/** Supported timeframes */
export enum TimeframeEnum {
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

/** Supported strategy types */
export enum StrategyEnum {
  INTEGRATED = "integrated_strategy",
  ML = "ml_strategy",
  WAVE = "wave_strategy",
  SENTIMENT = "sentiment_strategy",
  HYBRID = "hybrid_strategy",
  CUSTOM = "custom_strategy",
  ENSEMBLE = "ensemble_strategy"
}

/** Signal types */
export enum SignalTypeEnum {
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

/** Order side types */
export enum OrderSideEnum {
  BUY = "buy",
  SELL = "sell"
}

/** Order types */
export enum OrderTypeEnum {
  MARKET = "market",
  LIMIT = "limit",
  STOP = "stop",
  STOP_LIMIT = "stop_limit"
}

/** Order status */
export enum OrderStatusEnum {
  PENDING = "pending",
  SUBMITTED = "submitted",
  WORKING = "working",
  FILLED = "filled",
  CANCELLED = "cancelled",
  REJECTED = "rejected",
  PARTIALLY_FILLED = "partially_filled"
}

/** Data source options */
export enum DataSourceEnum {
  ALPHA_VANTAGE = "alpha_vantage",
  INTERACTIVE_BROKERS = "interactive_brokers",
  POLYGON = "polygon",
  YAHOO = "yahoo",
  BINANCE = "binance",
  CUSTOM = "custom"
}

/** Trading engine states */
export enum TradingEngineState {
  INACTIVE = "inactive",
  STARTING = "starting",
  ACTIVE = "active",
  PAUSED = "paused",
  STOPPING = "stopping",
  ERROR = "error",
  MAINTENANCE = "maintenance"
}

/** Trading modes */
export enum TradingMode {
  MANUAL = "manual",
  SEMI_AUTO = "semi_auto",
  FULLY_AUTO = "fully_auto"
}

// =============================================================================
// AUTHENTICATION MODELS
// =============================================================================

/** JWT token response */
export interface Token {
  access_token: string;
  token_type: string;
}

/** User model */
export interface User {
  username: string;
  email?: string | null;
  full_name?: string | null;
  is_active: boolean;
  scopes: string[];
}

// =============================================================================
// MARKET DATA MODELS
// =============================================================================

/** Market data tick */
export interface MarketDataTick {
  symbol: string;
  timestamp: string;
  bid: number;
  ask: number;
  price?: number;
  volume?: number;
}

/** OHLCV candle */
export interface Candle {
  time: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

/** Symbol information */
export interface SymbolInfo {
  symbol: string;
  base_currency: string;
  quote_currency: string;
  pip_value: number;
  min_lot_size: number;
  max_lot_size: number;
  lot_step: number;
}

// =============================================================================
// TRADING MODELS
// =============================================================================

/** Trading signal */
export interface TradingSignal {
  id?: string;
  symbol: string;
  timeframe: string;
  direction: string;
  confidence: number;
  signal_type: string;
  source: string;
  timestamp: string;
  metadata?: Record<string, any>;
}

/** Order request */
export interface OrderRequest {
  symbol: string;
  side: OrderSideEnum;
  order_type: OrderTypeEnum;
  quantity: number;
  price?: number;
  stop_price?: number;
  time_in_force?: string;
}

/** Order response */
export interface OrderResponse {
  id: string;
  symbol: string;
  side: string;
  order_type: string;
  quantity: number;
  price?: number;
  status: string;
  filled_quantity: number;
  remaining_quantity: number;
  avg_fill_price?: number;
  created_at: string;
  submitted_at?: string;
  filled_at?: string;
  signal_id?: string;
  strategy_name?: string;
  risk_approved: boolean;
  compliance_checked: boolean;
}

/** Position data */
export interface Position {
  id: string;
  symbol: string;
  side: string;
  quantity: number;
  entry_price: number;
  current_price: number;
  unrealized_pnl: number;
  realized_pnl: number;
  margin_used: number;
  created_at: string;
  updated_at: string;
}

/** Account information */
export interface Account {
  id: string;
  account_number: string;
  currency: string;
  balance: number;
  equity: number;
  margin_used: number;
  margin_available: number;
  margin_level: number;
  unrealized_pnl: number;
  realized_pnl: number;
  total_positions: number;
  total_orders: number;
}

// =============================================================================
// TRADING ENGINE MODELS
// =============================================================================

/** Trading engine configuration */
export interface TradingEngineConfig {
  trading_mode: TradingMode;
  enabled_symbols: string[];
  min_signal_confidence: number;
  signal_timeout_minutes: number;
  auto_execute_confidence: number;
  position_size_multiplier: number;
  max_position_size: number;
  max_daily_volume: number;
  max_orders_per_hour: number;
  max_concurrent_orders: number;
  order_timeout_minutes: number;
  max_errors_per_minute: number;
  circuit_breaker_pause_minutes: number;
}

/** Trading engine metrics */
export interface TradingEngineMetrics {
  signals_processed: number;
  orders_created: number;
  orders_executed: number;
  orders_cancelled: number;
  successful_trades: number;
  failed_trades: number;
  total_pnl: number;
  active_positions: number;
  uptime_seconds: number;
  last_signal_time?: string;
  last_trade_time?: string;
  errors: number;
  recent_errors: string[];
  circuit_breaker_triggered: boolean;
  circuit_breaker_until?: string;
}

/** Trading engine status */
export interface TradingEngineStatus {
  state: TradingEngineState;
  config: TradingEngineConfig;
  metrics: TradingEngineMetrics;
  error_message?: string;
  start_time?: string;
  uptime_seconds: number;
}

// =============================================================================
// BACKTESTING MODELS
// =============================================================================

/** Backtest configuration */
export interface BacktestConfig {
  strategy: StrategyEnum;
  symbol: string;
  timeframe: TimeframeEnum;
  start_date: string;
  end_date: string;
  initial_capital: number;
  position_size_multiplier?: number;
  commission_rate?: number;
  slippage?: number;
  strategy_params?: Record<string, any>;
}

/** Backtest result */
export interface BacktestResult {
  id: string;
  config: BacktestConfig;
  status: string;
  initial_capital: number;
  final_capital: number;
  total_return: number;
  sharpe_ratio: number;
  max_drawdown: number;
  num_trades: number;
  win_rate: number;
  avg_trade_return: number;
  created_at: string;
  duration?: string;
}

// =============================================================================
// REQUEST/RESPONSE MODELS
// =============================================================================

/** Signal generation request */
export interface SignalRequest {
  symbol: string;
  timeframe: TimeframeEnum;
  strategy?: StrategyEnum;
  lookback_periods?: number;
}

/** Signal generation response */
export interface SignalResponse {
  symbol: string;
  timeframe: string;
  timestamp: string;
  direction: string;
  confidence: number;
  signal_type: string;
  source: string;
  metadata?: Record<string, any>;
}

/** Market data request */
export interface MarketDataRequest {
  symbol: string;
  timeframe: TimeframeEnum;
  start_time?: string;
  end_time?: string;
  limit?: number;
}

/** Health check response */
export interface HealthCheck {
  status: string;
  version: string;
  timestamp: string;
  services: Record<string, string>;
}

// =============================================================================
// WEBSOCKET MESSAGE TYPES
// =============================================================================

/** WebSocket message base */
export interface WSMessage {
  type: string;
  data: any;
  timestamp: string;
}

/** Market data update */
export interface MarketDataUpdate extends WSMessage {
  type: 'market_data';
  data: MarketDataTick;
}

/** Order update */
export interface OrderUpdate extends WSMessage {
  type: 'order_update';
  data: OrderResponse;
}

/** Position update */
export interface PositionUpdate extends WSMessage {
  type: 'position_update';
  data: Position;
}

/** Signal update */
export interface SignalUpdate extends WSMessage {
  type: 'signal_update';
  data: TradingSignal;
}

/** Trading engine update */
export interface TradingEngineUpdate extends WSMessage {
  type: 'trading_engine_update';
  data: TradingEngineStatus;
}
