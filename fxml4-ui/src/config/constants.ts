/**
 * Application constants and configuration values
 */

// Application metadata
export const APP_CONFIG = {
  name: 'FXML4 Trading Platform',
  version: '1.0.0',
  description: 'Professional Forex Trading Platform with ML and Real-time Analytics',
  author: 'FXML4 Team',
} as const;

// API configuration
export const API_CONFIG = {
  baseURL: process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8001',
  timeout: 30000, // 30 seconds
  retryAttempts: 3,
  retryDelay: 1000, // 1 second
} as const;

// WebSocket configuration
export const WS_CONFIG = {
  url: process.env.NEXT_PUBLIC_WS_URL || 'ws://localhost:8001/ws',
  reconnectAttempts: 5,
  reconnectInterval: 3000, // 3 seconds
  heartbeatInterval: 30000, // 30 seconds
} as const;

// Trading configuration
export const TRADING_CONFIG = {
  defaultTimeframe: '1h' as const,
  maxPositions: 10,
  maxOrderSize: 1000000, // 1M units
  minOrderSize: 1000, // 1K units
  defaultLeverage: 100,
  supportedSymbols: [
    'EURUSD', 'GBPUSD', 'USDJPY', 'USDCHF', 'AUDUSD',
    'USDCAD', 'NZDUSD', 'EURJPY', 'GBPJPY', 'EURGBP'
  ],
  timeframes: [
    { value: '1m', label: '1 Minute' },
    { value: '5m', label: '5 Minutes' },
    { value: '15m', label: '15 Minutes' },
    { value: '30m', label: '30 Minutes' },
    { value: '1h', label: '1 Hour' },
    { value: '4h', label: '4 Hours' },
    { value: '1d', label: '1 Day' },
    { value: '1w', label: '1 Week' },
  ],
  orderTypes: [
    { value: 'market', label: 'Market Order' },
    { value: 'limit', label: 'Limit Order' },
    { value: 'stop', label: 'Stop Order' },
    { value: 'stop_limit', label: 'Stop Limit Order' },
  ],
} as const;

// Chart configuration
export const CHART_CONFIG = {
  defaultTheme: 'dark',
  defaultChartType: 'candlestick',
  maxDataPoints: 5000,
  updateInterval: 1000, // 1 second
  indicators: {
    sma: { name: 'Simple Moving Average', periods: [20, 50, 200] },
    ema: { name: 'Exponential Moving Average', periods: [12, 26] },
    rsi: { name: 'Relative Strength Index', period: 14, overbought: 70, oversold: 30 },
    macd: { name: 'MACD', fast: 12, slow: 26, signal: 9 },
    bollinger: { name: 'Bollinger Bands', period: 20, stdDev: 2 },
  },
  colors: {
    up: '#10b981',
    down: '#ef4444',
    neutral: '#6b7280',
    volume: '#3b82f6',
    grid: '#374151',
    text: '#f9fafb',
  },
} as const;

// UI configuration
export const UI_CONFIG = {
  sidebar: {
    width: 280,
    collapsedWidth: 64,
  },
  header: {
    height: 64,
  },
  panel: {
    width: 320,
    minWidth: 250,
    maxWidth: 500,
  },
  breakpoints: {
    mobile: 640,
    tablet: 768,
    desktop: 1024,
    wide: 1280,
  },
  animations: {
    duration: {
      fast: 150,
      normal: 300,
      slow: 500,
    },
    easing: 'cubic-bezier(0.4, 0, 0.2, 1)',
  },
} as const;

// Data refresh intervals (in milliseconds)
export const REFRESH_INTERVALS = {
  marketData: 1000,        // 1 second
  positions: 5000,         // 5 seconds
  orders: 2000,           // 2 seconds
  account: 10000,         // 10 seconds
  signals: 5000,          // 5 seconds
  performance: 30000,     // 30 seconds
} as const;

// Storage keys for localStorage/sessionStorage
export const STORAGE_KEYS = {
  theme: 'fxml4_theme',
  userPreferences: 'fxml4_user_preferences',
  dashboardLayout: 'fxml4_dashboard_layout',
  chartSettings: 'fxml4_chart_settings',
  authToken: 'fxml4_auth_token',
  refreshToken: 'fxml4_refresh_token',
  lastSession: 'fxml4_last_session',
} as const;

// Error messages
export const ERROR_MESSAGES = {
  network: 'Network connection error. Please check your internet connection.',
  unauthorized: 'Session expired. Please log in again.',
  forbidden: 'You do not have permission to perform this action.',
  notFound: 'The requested resource was not found.',
  serverError: 'Server error. Please try again later.',
  invalidData: 'Invalid data provided. Please check your input.',
  connectionLost: 'Connection to server lost. Attempting to reconnect...',
  orderRejected: 'Order was rejected. Please check your account and try again.',
  insufficientMargin: 'Insufficient margin to place order.',
  marketClosed: 'Market is currently closed.',
  symbolNotSupported: 'Trading symbol is not supported.',
} as const;

// Success messages
export const SUCCESS_MESSAGES = {
  orderPlaced: 'Order placed successfully',
  orderCancelled: 'Order cancelled successfully',
  positionClosed: 'Position closed successfully',
  settingsUpdated: 'Settings updated successfully',
  dataExported: 'Data exported successfully',
  modelTrained: 'Model training completed successfully',
  backtestCompleted: 'Backtest completed successfully',
} as const;

// Navigation routes
export const ROUTES = {
  home: '/',
  dashboard: '/dashboard',
  data: {
    index: '/data',
    marketData: '/data/market',
    history: '/data/history',
    feeds: '/data/feeds',
    quality: '/data/quality',
  },
  training: {
    index: '/training',
    models: '/training/models',
    datasets: '/training/datasets',
    experiments: '/training/experiments',
    deployment: '/training/deployment',
  },
  backtesting: {
    index: '/backtesting',
    strategies: '/backtesting/strategies',
    results: '/backtesting/results',
    optimization: '/backtesting/optimization',
    reports: '/backtesting/reports',
  },
  trading: {
    index: '/trading',
    dashboard: '/trading/dashboard',
    orders: '/trading/orders',
    positions: '/trading/positions',
    signals: '/trading/signals',
    risk: '/trading/risk',
  },
  settings: '/settings',
  profile: '/profile',
  help: '/help',
  api: '/api-docs',
} as const;

// Feature flags
export const FEATURE_FLAGS = {
  enableAdvancedCharts: true,
  enableLiveTrading: true,
  enableMLTraining: true,
  enableBacktesting: true,
  enableDarkMode: true,
  enableNotifications: true,
  enableMultiAccount: false,
  enableOptionsTrading: false,
  enableNewsIntegration: false,
  enableSocialTrading: false,
} as const;

// Development configuration
export const DEV_CONFIG = {
  enableDebugLogs: process.env.NODE_ENV === 'development',
  enableReduxDevTools: process.env.NODE_ENV === 'development',
  enablePerformanceMonitoring: true,
  mockApi: false,
  mockWebSocket: false,
} as const;

// Third-party service configuration
export const EXTERNAL_SERVICES = {
  tradingView: {
    containerId: 'tradingview_chart',
    library_path: '/charting_library/',
    datafeed: '/api/v1/tradingview/',
  },
  analytics: {
    enabled: process.env.NODE_ENV === 'production',
    trackingId: process.env.NEXT_PUBLIC_GA_TRACKING_ID,
  },
  sentry: {
    enabled: process.env.NODE_ENV === 'production',
    dsn: process.env.NEXT_PUBLIC_SENTRY_DSN,
  },
} as const;
