/**
 * Core TypeScript type definitions for FXML4 Trading Platform
 *
 * This file contains all the shared type definitions used throughout
 * the trading interface application.
 */

// Base types
export type Status = 'online' | 'offline' | 'warning' | 'error';
export type Theme = 'light' | 'dark' | 'system';

// Trading related types
export type Side = 'buy' | 'sell';
export type OrderType = 'market' | 'limit' | 'stop' | 'stop_limit';
export type OrderStatus = 'pending' | 'filled' | 'cancelled' | 'rejected' | 'partially_filled';
export type TimeFrame = '1m' | '5m' | '15m' | '30m' | '1h' | '4h' | '1d' | '1w';

// Symbol and currency pairs
export interface Symbol {
  symbol: string;
  base_currency: string;
  quote_currency: string;
  pip_value: number;
  min_lot_size: number;
  max_lot_size: number;
  lot_step: number;
  spread: number;
}

// Market data types
export interface MarketData {
  symbol: string;
  timestamp: string;
  bid: number;
  ask: number;
  spread: number;
  volume: number;
  high: number;
  low: number;
  open: number;
  close: number;
}

export interface Candle {
  timestamp: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

// Order management types
export interface Order {
  id: string;
  client_order_id: string;
  symbol: string;
  side: Side;
  type: OrderType;
  quantity: number;
  price?: number;
  stop_price?: number;
  status: OrderStatus;
  filled_quantity: number;
  remaining_quantity: number;
  average_fill_price?: number;
  created_at: string;
  updated_at: string;
  expires_at?: string;
  // Optimistic locking for race condition prevention
  sequence_number: number;
  source: 'api' | 'websocket' | 'manual';
}

export interface Position {
  id: string;
  symbol: string;
  side: Side;
  quantity: number;
  entry_price: number;
  current_price: number;
  unrealized_pnl: number;
  realized_pnl: number;
  margin_used: number;
  created_at: string;
  updated_at: string;
}

// Trading signal types
export interface TradingSignal {
  id: string;
  symbol: string;
  signal_type: 'buy' | 'sell' | 'hold';
  confidence: number;
  price: number;
  target_price?: number;
  stop_loss?: number;
  model_name: string;
  features: Record<string, number>;
  timestamp: string;
  expires_at?: string;
}

// ML Model types
export interface MLModel {
  id: string;
  name: string;
  type: 'classification' | 'regression';
  status: 'training' | 'ready' | 'deployed' | 'error';
  accuracy?: number;
  sharpe_ratio?: number;
  max_drawdown?: number;
  created_at: string;
  updated_at: string;
  version: number;
}

export interface TrainingConfig {
  model_name: string;
  model_type: 'xgboost' | 'lstm' | 'transformer';
  symbols: string[];
  timeframe: TimeFrame;
  lookback_days: number;
  features: string[];
  target: string;
  train_start_date: string;
  train_end_date: string;
  validation_split: number;
  hyperparameters: Record<string, any>;
}

export interface TrainingProgress {
  epoch: number;
  total_epochs: number;
  loss: number;
  validation_loss: number;
  accuracy?: number;
  validation_accuracy?: number;
  elapsed_time: number;
  eta: number;
  status: 'running' | 'completed' | 'failed' | 'stopped';
}

// Backtesting types
export interface BacktestConfig {
  strategy_name: string;
  symbols: string[];
  timeframe: TimeFrame;
  start_date: string;
  end_date: string;
  initial_capital: number;
  position_size: number;
  max_positions: number;
  commission: number;
  slippage: number;
  parameters: Record<string, any>;
}

export interface BacktestResult {
  id: string;
  config: BacktestConfig;
  status: 'running' | 'completed' | 'failed';
  total_return: number;
  annualized_return: number;
  sharpe_ratio: number;
  max_drawdown: number;
  win_rate: number;
  total_trades: number;
  winning_trades: number;
  losing_trades: number;
  average_win: number;
  average_loss: number;
  profit_factor: number;
  equity_curve: Array<{ timestamp: string; value: number }>;
  trades: Trade[];
  created_at: string;
  completed_at?: string;
}

export interface Trade {
  id: string;
  symbol: string;
  side: Side;
  entry_price: number;
  exit_price: number;
  quantity: number;
  pnl: number;
  commission: number;
  entry_time: string;
  exit_time: string;
  duration: number;
  signal_confidence?: number;
}

// Account and portfolio types
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

export interface Portfolio {
  account: Account;
  positions: Position[];
  orders: Order[];
  daily_pnl: number;
  weekly_pnl: number;
  monthly_pnl: number;
  ytd_pnl: number;
}

// Broker adapter types
export interface BrokerAdapter {
  id: string;
  name: string;
  status: Status;
  connection_status: 'connected' | 'disconnected' | 'connecting' | 'error';
  last_heartbeat: string;
  latency: number;
  supported_symbols: Symbol[];
  supported_order_types: OrderType[];
}

// WebSocket message types
export interface WSMessage {
  type: string;
  data: any;
  timestamp: string;
}

export interface MarketDataUpdate extends WSMessage {
  type: 'market_data';
  data: MarketData;
}

export interface OrderUpdate extends WSMessage {
  type: 'order_update';
  data: Order;
}

export interface PositionUpdate extends WSMessage {
  type: 'position_update';
  data: Position;
}

export interface SignalUpdate extends WSMessage {
  type: 'signal_update';
  data: TradingSignal;
}

// API response types
export interface ApiResponse<T> {
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

// Chart and visualization types
export interface ChartConfig {
  symbol: string;
  timeframe: TimeFrame;
  indicators: string[];
  chart_type: 'candlestick' | 'line' | 'area';
  theme: Theme;
}

export interface TechnicalIndicator {
  name: string;
  parameters: Record<string, number>;
  color: string;
  visible: boolean;
}

// User interface state types
export interface NavigationItem {
  id: string;
  label: string;
  icon: string;
  path: string;
  badge?: number;
  children?: NavigationItem[];
}

export interface DashboardWidget {
  id: string;
  title: string;
  type: 'chart' | 'table' | 'metric' | 'alert';
  position: { x: number; y: number; width: number; height: number };
  config: Record<string, any>;
  data?: any;
}

// Settings and preferences
export interface UserPreferences {
  theme: Theme;
  default_timeframe: TimeFrame;
  favorite_symbols: string[];
  dashboard_layout: DashboardWidget[];
  notifications: {
    email: boolean;
    push: boolean;
    trading_signals: boolean;
    order_fills: boolean;
    system_alerts: boolean;
  };
  risk_settings: {
    max_position_size: number;
    max_daily_loss: number;
    max_drawdown: number;
    enable_auto_stop_loss: boolean;
  };
}

// Error types
export interface AppError {
  code: string;
  message: string;
  details?: string;
  timestamp: string;
  context?: Record<string, any>;
}

// Utility types
export type LoadingState = 'idle' | 'loading' | 'success' | 'error';
export type SortOrder = 'asc' | 'desc';
export type FilterOperator = 'eq' | 'ne' | 'gt' | 'gte' | 'lt' | 'lte' | 'contains' | 'in';

export interface TableColumn<T> {
  key: keyof T;
  label: string;
  sortable?: boolean;
  width?: string;
  align?: 'left' | 'center' | 'right';
  render?: (value: any, row: T) => React.ReactNode;
}

export interface Filter {
  field: string;
  operator: FilterOperator;
  value: any;
}

export interface Sort {
  field: string;
  order: SortOrder;
}

// Event types for analytics
export interface AnalyticsEvent {
  event: string;
  properties: Record<string, any>;
  timestamp: string;
  user_id?: string;
  session_id: string;
}

// Auto-generated API types
export * from "./api-generated";
