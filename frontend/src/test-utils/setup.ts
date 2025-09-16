/**
 * Test Setup Configuration
 *
 * Global test setup for Jest and React Testing Library
 */

import '@testing-library/jest-dom';
import { configure } from '@testing-library/react';
import { TextEncoder, TextDecoder } from 'util';
import { EventEmitter } from 'events';
import { toHaveNoViolations } from 'jest-axe';

// Configure React Testing Library
configure({
  testIdAttribute: 'data-testid',
});

// Configure Accessibility Testing
expect.extend(toHaveNoViolations);

// Global polyfills for Node.js environment
global.TextEncoder = TextEncoder;
global.TextDecoder = TextDecoder;

// Mock WebSocket for testing
class MockWebSocket {
  static CONNECTING = 0;
  static OPEN = 1;
  static CLOSING = 2;
  static CLOSED = 3;

  readyState = MockWebSocket.CONNECTING;
  url = '';

  constructor(url: string) {
    this.url = url;
    setTimeout(() => {
      this.readyState = MockWebSocket.OPEN;
      this.onopen?.(new Event('open'));
    }, 10);
  }

  send = jest.fn();
  close = jest.fn(() => {
    this.readyState = MockWebSocket.CLOSED;
  });

  onopen: ((event: Event) => void) | null = null;
  onclose: ((event: CloseEvent) => void) | null = null;
  onmessage: ((event: MessageEvent) => void) | null = null;
  onerror: ((event: Event) => void) | null = null;
}

global.WebSocket = MockWebSocket as any;

// Mock localStorage
const localStorageMock = {
  getItem: jest.fn(),
  setItem: jest.fn(),
  removeItem: jest.fn(),
  clear: jest.fn(),
  length: 0,
  key: jest.fn(),
};

global.localStorage = localStorageMock;

// Mock sessionStorage
global.sessionStorage = localStorageMock;

// Mock window.matchMedia
Object.defineProperty(window, 'matchMedia', {
  writable: true,
  value: jest.fn().mockImplementation(query => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: jest.fn(), // Deprecated
    removeListener: jest.fn(), // Deprecated
    addEventListener: jest.fn(),
    removeEventListener: jest.fn(),
    dispatchEvent: jest.fn(),
  })),
});

// Mock ResizeObserver
global.ResizeObserver = jest.fn().mockImplementation(() => ({
  observe: jest.fn(),
  unobserve: jest.fn(),
  disconnect: jest.fn(),
}));

// Mock IntersectionObserver
global.IntersectionObserver = jest.fn().mockImplementation(() => ({
  observe: jest.fn(),
  unobserve: jest.fn(),
  disconnect: jest.fn(),
}));

// Mock EventEmitter for NotificationService
const mockEventBus = new EventEmitter();

// Mock NotificationService configuration
jest.mock('@/services/notification', () => ({
  ...jest.requireActual('@/services/notification'),
  getNotificationService: jest.fn(() => ({
    create: jest.fn(),
    getAll: jest.fn(() => []),
    getUnread: jest.fn(() => []),
    markAsRead: jest.fn(),
    dismiss: jest.fn(),
    getStats: jest.fn(() => ({
      total: 0,
      unread: 0,
      byType: {},
      byPriority: {}
    })),
    destroy: jest.fn(),
  })),
  NotificationService: jest.fn().mockImplementation(() => ({
    create: jest.fn(),
    getAll: jest.fn(() => []),
    getUnread: jest.fn(() => []),
    markAsRead: jest.fn(),
    dismiss: jest.fn(),
    getStats: jest.fn(() => ({
      total: 0,
      unread: 0,
      byType: {},
      byPriority: {}
    })),
    destroy: jest.fn(),
  })),
}));

// Mock WebSocket services
jest.mock('@/services/dataManagementWebSocket', () => ({
  getDataManagementWebSocket: jest.fn(() => ({
    isConnected: jest.fn(() => false),
    getConnectionStatus: jest.fn(() => ({
      state: 'DISCONNECTED',
      reconnectAttempts: 0,
      latency: undefined,
      lastHeartbeat: undefined,
      connectedAt: undefined,
      error: undefined,
    })),
    connect: jest.fn(() => Promise.resolve()),
    disconnect: jest.fn(),
    reconnect: jest.fn(() => Promise.resolve()),
    addEventListener: jest.fn(),
    removeEventListener: jest.fn(),
    subscribe: jest.fn(() => 'mock-subscription-id'),
    unsubscribe: jest.fn(),
    send: jest.fn(),
  })),
  DataManagementWebSocketService: jest.fn().mockImplementation(() => ({
    isConnected: jest.fn(() => false),
    getConnectionStatus: jest.fn(() => ({
      state: 'DISCONNECTED',
      reconnectAttempts: 0,
    })),
    connect: jest.fn(() => Promise.resolve()),
    disconnect: jest.fn(),
    addEventListener: jest.fn(),
    removeEventListener: jest.fn(),
  })),
}));

// Mock WebSocket types
jest.mock('@/types/websocket', () => ({
  WebSocketState: {
    DISCONNECTED: 'DISCONNECTED',
    CONNECTING: 'CONNECTING',
    CONNECTED: 'CONNECTED',
    RECONNECTING: 'RECONNECTING',
    ERROR: 'ERROR',
    CLOSED: 'CLOSED',
  },
}));

// Mock service factories with proper EventBus configuration
beforeEach(() => {
  // Reset mocks before each test
  jest.clearAllMocks();

  // Provide default eventBus config for any services that need it
  (global as any).mockEventBus = mockEventBus;
  (global as any).mockServiceConfig = {
    eventBus: mockEventBus,
    websocket: new MockWebSocket('ws://localhost:8080') as any,
  };
});

// Suppress console warnings in tests
const originalConsoleWarn = console.warn;
const originalConsoleError = console.error;

beforeEach(() => {
  console.warn = jest.fn();
  console.error = jest.fn();
});

afterEach(() => {
  console.warn = originalConsoleWarn;
  console.error = originalConsoleError;
});

// Global test utilities
export const mockMarketData = {
  EURUSD: {
    symbol: 'EURUSD',
    bid: 1.08245,
    ask: 1.08248,
    timestamp: '2024-01-15T10:30:00.000Z',
    volume: 1000000,
  },
  GBPUSD: {
    symbol: 'GBPUSD',
    bid: 1.27156,
    ask: 1.27159,
    timestamp: '2024-01-15T10:30:00.000Z',
    volume: 750000,
  },
};

export const mockAccount = {
  id: 'test-account-123',
  balance: 100000,
  equity: 102500,
  margin_used: 2500,
  margin_available: 97500,
  leverage: 100,
  currency: 'USD',
  realized_pnl: 1500,
  unrealized_pnl: 1000,
};

export const mockOrder = {
  id: 'order-123',
  symbol: 'EURUSD',
  side: 'buy' as const,
  type: 'market' as const,
  quantity: 10000,
  price: undefined,
  status: 'pending' as const,
  created_at: '2024-01-15T10:30:00.000Z',
  updated_at: '2024-01-15T10:30:00.000Z',
  filled_quantity: 0,
  avg_fill_price: undefined,
  time_in_force: 'GTC' as const,
};

export const mockPosition = {
  id: 'position-123',
  symbol: 'EURUSD',
  side: 'long' as const,
  quantity: 10000,
  entry_price: 1.08200,
  current_price: 1.08245,
  unrealized_pnl: 45,
  realized_pnl: 0,
  margin_used: 1082,
  created_at: '2024-01-15T10:25:00.000Z',
  updated_at: '2024-01-15T10:30:00.000Z',
};

// Mock trading signals
export const mockTradingSignal = {
  id: 'signal-123',
  symbol: 'EURUSD',
  signal_type: 'buy' as const,
  confidence: 0.85,
  entry_price: 1.08250,
  stop_loss: 1.08150,
  take_profit: 1.08350,
  timestamp: '2024-01-15T10:30:00.000Z',
  model_name: 'EURUSD_Neural_Network',
  features: {
    rsi: 65.5,
    macd: 0.0025,
    bb_position: 0.7,
  },
};
