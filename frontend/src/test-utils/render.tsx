/**
 * Custom Render Utilities
 *
 * Custom render functions with providers for testing components
 */

import React, { ReactElement } from 'react';
import { render, RenderOptions } from '@testing-library/react';
import { useAppStore } from '@/stores/appStore';
import { useMarketDataStore } from '@/stores/marketDataStore';
import { useTradingStore } from '@/stores/tradingStore';

// Mock stores initial state
const mockAppState = {
  theme: 'dark' as const,
  sidebarCollapsed: false,
  sidebarOpen: false,
  isConnected: true,
  connectionStatus: 'connected' as const,
  lastConnectionTime: Date.now(),
  systemHealth: 'healthy' as const,
  systemMetrics: {},
  preferences: {
    theme: 'dark' as const,
    default_timeframe: '1h',
    favorite_symbols: ['EURUSD', 'GBPUSD', 'USDJPY'],
    dashboard_layout: [],
    notifications: {
      email: true,
      push: true,
      trading_signals: true,
      order_fills: true,
      system_alerts: true,
    },
    risk_settings: {
      max_position_size: 100000,
      max_daily_loss: 1000,
      max_drawdown: 0.05,
      enable_auto_stop_loss: true,
    },
  },
  globalLoading: 'idle' as const,
  errors: [],
  notifications: [],
};

const mockMarketDataState = {
  currentPrices: {},
  symbols: [],
  isConnected: true,
  lastUpdate: Date.now(),
  historicalData: {},
  isLoadingHistorical: {},
  subscribedSymbols: new Set<string>(),
};

const mockTradingState = {
  account: null,
  orders: [],
  positions: [],
  signals: [],
  isLoadingOrders: false,
  isLoadingPositions: false,
  isLoadingAccount: false,
  selectedOrder: null,
  selectedPosition: null,
  lastOrderUpdate: 0,
  lastPositionUpdate: 0,
  lastAccountUpdate: 0,
};

// Test wrapper component
interface AllTheProvidersProps {
  children: React.ReactNode;
}

const AllTheProviders = ({ children }: AllTheProvidersProps) => {
  // Initialize stores with mock data
  React.useEffect(() => {
    // Reset stores to initial state
    useAppStore.setState(mockAppState);
    useMarketDataStore.setState(mockMarketDataState);
    useTradingStore.setState(mockTradingState);
  }, []);

  return <>{children}</>;
};

// Custom render function
const customRender = (
  ui: ReactElement,
  options?: Omit<RenderOptions, 'wrapper'>
) => render(ui, { wrapper: AllTheProviders, ...options });

// Custom render with specific store state
interface RenderWithStoreOptions extends Omit<RenderOptions, 'wrapper'> {
  appState?: Partial<typeof mockAppState>;
  marketDataState?: Partial<typeof mockMarketDataState>;
  tradingState?: Partial<typeof mockTradingState>;
}

const renderWithStore = (
  ui: ReactElement,
  options?: RenderWithStoreOptions
) => {
  const { appState, marketDataState, tradingState, ...renderOptions } = options || {};

  const TestWrapper = ({ children }: AllTheProvidersProps) => {
    React.useEffect(() => {
      if (appState) {
        useAppStore.setState({ ...mockAppState, ...appState });
      }
      if (marketDataState) {
        useMarketDataStore.setState({ ...mockMarketDataState, ...marketDataState });
      }
      if (tradingState) {
        useTradingStore.setState({ ...mockTradingState, ...tradingState });
      }
    }, []);

    return <>{children}</>;
  };

  return render(ui, { wrapper: TestWrapper, ...renderOptions });
};

// Custom render for testing WebSocket components
const renderWithWebSocket = (ui: ReactElement, options?: RenderOptions) => {
  const WebSocketWrapper = ({ children }: AllTheProvidersProps) => {
    React.useEffect(() => {
      // Set up WebSocket connection state
      useAppStore.setState({
        ...mockAppState,
        isConnected: true,
        connectionStatus: 'connected',
      });

      useMarketDataStore.setState({
        ...mockMarketDataState,
        isConnected: true,
      });
    }, []);

    return <>{children}</>;
  };

  return render(ui, { wrapper: WebSocketWrapper, ...options });
};

// Export utilities
export * from '@testing-library/react';
export { customRender as render, renderWithStore, renderWithWebSocket };

// Mock data generators for testing
export const generateMockMarketData = (symbol: string, overrides = {}) => ({
  symbol,
  bid: 1.08245,
  ask: 1.08248,
  timestamp: new Date().toISOString(),
  volume: 1000000,
  ...overrides,
});

export const generateMockOrder = (overrides = {}) => ({
  id: `order-${Date.now()}`,
  symbol: 'EURUSD',
  side: 'buy' as const,
  type: 'market' as const,
  quantity: 10000,
  price: undefined,
  status: 'pending' as const,
  created_at: new Date().toISOString(),
  updated_at: new Date().toISOString(),
  filled_quantity: 0,
  avg_fill_price: undefined,
  time_in_force: 'GTC' as const,
  ...overrides,
});

export const generateMockPosition = (overrides = {}) => ({
  id: `position-${Date.now()}`,
  symbol: 'EURUSD',
  side: 'long' as const,
  quantity: 10000,
  entry_price: 1.08200,
  current_price: 1.08245,
  unrealized_pnl: 45,
  realized_pnl: 0,
  margin_used: 1082,
  created_at: new Date().toISOString(),
  updated_at: new Date().toISOString(),
  ...overrides,
});

// Async utilities for testing
export const waitForWebSocketConnection = () => {
  return new Promise<void>((resolve) => {
    const checkConnection = () => {
      if (useAppStore.getState().isConnected) {
        resolve();
      } else {
        setTimeout(checkConnection, 10);
      }
    };
    checkConnection();
  });
};

// Mock API responses
export const mockApiSuccess = (data: any) => ({
  data,
  status: 200,
  statusText: 'OK',
  headers: {},
  config: {},
});

export const mockApiError = (message: string, status = 400) => ({
  response: {
    data: { message },
    status,
    statusText: 'Bad Request',
    headers: {},
    config: {},
  },
});

// Test helpers for trading calculations
export const calculateExpectedPnL = (
  entryPrice: number,
  currentPrice: number,
  quantity: number,
  side: 'long' | 'short'
) => {
  const priceDiff = side === 'long'
    ? currentPrice - entryPrice
    : entryPrice - currentPrice;
  return priceDiff * quantity;
};

export const calculateExpectedMargin = (
  price: number,
  quantity: number,
  leverage: number
) => {
  return (price * quantity) / leverage;
};
