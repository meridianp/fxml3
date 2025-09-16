/**
 * Test Data Factories for FXML4 TDD Framework
 *
 * Provides reusable factory functions for creating consistent test data
 * across all test suites. Follows the Factory pattern for maintainable
 * and predictable test data generation.
 */

import { faker } from '@faker-js/faker';

// Trading Domain Types
export interface TestOrder {
  id?: string;
  symbol: string;
  side: 'BUY' | 'SELL';
  quantity: number;
  type: 'MARKET' | 'LIMIT' | 'STOP';
  price?: number;
  stopPrice?: number;
  status: 'PENDING' | 'EXECUTED' | 'CANCELLED' | 'REJECTED';
  timestamp: string;
  userId?: string;
  executionPrice?: number;
}

export interface TestMarketData {
  symbol: string;
  bid: number;
  ask: number;
  spread: number;
  timestamp: number;
  volume?: number;
  high?: number;
  low?: number;
  open?: number;
  close?: number;
}

export interface TestUser {
  id: string;
  email: string;
  username: string;
  firstName: string;
  lastName: string;
  accountBalance: number;
  isActive: boolean;
  createdAt: string;
  roles: string[];
}

export interface TestTrade {
  id: string;
  orderId: string;
  symbol: string;
  side: 'BUY' | 'SELL';
  quantity: number;
  executionPrice: number;
  commission: number;
  timestamp: string;
  userId: string;
}

// Order Factory
export const createTestOrder = (overrides: Partial<TestOrder> = {}): TestOrder => {
  const symbols = ['EUR/USD', 'GBP/USD', 'USD/JPY', 'AUD/USD', 'USD/CHF', 'NZD/USD'];
  const sides: ('BUY' | 'SELL')[] = ['BUY', 'SELL'];
  const types: ('MARKET' | 'LIMIT' | 'STOP')[] = ['MARKET', 'LIMIT', 'STOP'];
  const statuses: ('PENDING' | 'EXECUTED' | 'CANCELLED' | 'REJECTED')[] =
    ['PENDING', 'EXECUTED', 'CANCELLED', 'REJECTED'];

  const baseOrder: TestOrder = {
    id: faker.string.uuid(),
    symbol: faker.helpers.arrayElement(symbols),
    side: faker.helpers.arrayElement(sides),
    quantity: faker.number.int({ min: 1000, max: 1000000 }),
    type: faker.helpers.arrayElement(types),
    status: faker.helpers.arrayElement(statuses),
    timestamp: faker.date.recent().toISOString(),
    userId: faker.string.uuid(),
  };

  // Add type-specific fields
  if (baseOrder.type === 'LIMIT') {
    baseOrder.price = faker.number.float({ min: 1.0, max: 2.0, fractionDigits: 4 });
  }

  if (baseOrder.type === 'STOP') {
    baseOrder.stopPrice = faker.number.float({ min: 1.0, max: 2.0, fractionDigits: 4 });
  }

  if (baseOrder.status === 'EXECUTED') {
    baseOrder.executionPrice = faker.number.float({ min: 1.0, max: 2.0, fractionDigits: 4 });
  }

  return { ...baseOrder, ...overrides };
};

// Market Data Factory
export const createTestMarketData = (overrides: Partial<TestMarketData> = {}): TestMarketData => {
  const symbols = ['EUR/USD', 'GBP/USD', 'USD/JPY', 'AUD/USD', 'USD/CHF', 'NZD/USD'];

  const bid = faker.number.float({ min: 1.0, max: 2.0, fractionDigits: 4 });
  const spread = faker.number.float({ min: 0.0001, max: 0.001, fractionDigits: 4 });
  const ask = bid + spread;

  const baseMarketData: TestMarketData = {
    symbol: faker.helpers.arrayElement(symbols),
    bid,
    ask,
    spread,
    timestamp: Date.now(),
    volume: faker.number.int({ min: 10000, max: 1000000 }),
    high: faker.number.float({ min: ask, max: ask * 1.01, fractionDigits: 4 }),
    low: faker.number.float({ min: bid * 0.99, max: bid, fractionDigits: 4 }),
    open: faker.number.float({ min: bid, max: ask, fractionDigits: 4 }),
    close: faker.number.float({ min: bid, max: ask, fractionDigits: 4 }),
  };

  return { ...baseMarketData, ...overrides };
};

// User Factory
export const createTestUser = (overrides: Partial<TestUser> = {}): TestUser => {
  const firstName = faker.person.firstName();
  const lastName = faker.person.lastName();

  const baseUser: TestUser = {
    id: faker.string.uuid(),
    email: faker.internet.email({ firstName, lastName }).toLowerCase(),
    username: faker.internet.username({ firstName, lastName }).toLowerCase(),
    firstName,
    lastName,
    accountBalance: faker.number.float({ min: 1000, max: 100000, fractionDigits: 2 }),
    isActive: true,
    createdAt: faker.date.past().toISOString(),
    roles: ['trader'],
  };

  return { ...baseUser, ...overrides };
};

// Trade Factory
export const createTestTrade = (overrides: Partial<TestTrade> = {}): TestTrade => {
  const symbols = ['EUR/USD', 'GBP/USD', 'USD/JPY', 'AUD/USD', 'USD/CHF', 'NZD/USD'];
  const sides: ('BUY' | 'SELL')[] = ['BUY', 'SELL'];

  const quantity = faker.number.int({ min: 1000, max: 1000000 });
  const executionPrice = faker.number.float({ min: 1.0, max: 2.0, fractionDigits: 4 });
  const commission = quantity * executionPrice * 0.0001; // 0.01% commission

  const baseTrade: TestTrade = {
    id: faker.string.uuid(),
    orderId: faker.string.uuid(),
    symbol: faker.helpers.arrayElement(symbols),
    side: faker.helpers.arrayElement(sides),
    quantity,
    executionPrice,
    commission,
    timestamp: faker.date.recent().toISOString(),
    userId: faker.string.uuid(),
  };

  return { ...baseTrade, ...overrides };
};

// API Response Factories
export const createTestApiResponse = <T>(data: T, overrides: any = {}) => ({
  success: true,
  data,
  timestamp: new Date().toISOString(),
  requestId: faker.string.uuid(),
  ...overrides,
});

export const createTestApiError = (message: string = 'Test error', code: string = 'TEST_ERROR') => ({
  success: false,
  error: {
    message,
    code,
    details: null,
  },
  timestamp: new Date().toISOString(),
  requestId: faker.string.uuid(),
});

// WebSocket Message Factories
export const createTestWebSocketMessage = {
  priceUpdate: (overrides: Partial<TestMarketData> = {}) => ({
    type: 'price',
    ...createTestMarketData(overrides),
  }),

  orderUpdate: (overrides: Partial<TestOrder> = {}) => ({
    type: 'orderUpdate',
    ...createTestOrder(overrides),
  }),

  tradeUpdate: (overrides: Partial<TestTrade> = {}) => ({
    type: 'trade',
    ...createTestTrade(overrides),
  }),

  error: (message: string = 'WebSocket error', code: string = 'WS_ERROR') => ({
    type: 'error',
    error: {
      message,
      code,
      timestamp: Date.now(),
    },
  }),

  heartbeat: () => ({
    type: 'heartbeat',
    timestamp: Date.now(),
    status: 'alive',
  }),
};

// Batch Factories for Load Testing
export const createTestOrderBatch = (count: number, overrides: Partial<TestOrder> = {}): TestOrder[] => {
  return Array.from({ length: count }, () => createTestOrder(overrides));
};

export const createTestMarketDataBatch = (count: number, overrides: Partial<TestMarketData> = {}): TestMarketData[] => {
  return Array.from({ length: count }, () => createTestMarketData(overrides));
};

export const createTestUserBatch = (count: number, overrides: Partial<TestUser> = {}): TestUser[] => {
  return Array.from({ length: count }, () => createTestUser(overrides));
};

// Realistic Data Scenarios
export const createRealisticTradingScenario = () => {
  const user = createTestUser({
    accountBalance: 50000,
    roles: ['trader', 'premium'],
  });

  const marketData = createTestMarketData({
    symbol: 'EUR/USD',
    bid: 1.2048,
    ask: 1.2050,
    spread: 0.0002,
  });

  const pendingOrder = createTestOrder({
    userId: user.id,
    symbol: marketData.symbol,
    side: 'BUY',
    quantity: 100000,
    type: 'MARKET',
    status: 'PENDING',
  });

  const executedTrade = createTestTrade({
    orderId: pendingOrder.id!,
    userId: user.id,
    symbol: marketData.symbol,
    side: 'BUY',
    quantity: pendingOrder.quantity,
    executionPrice: marketData.ask,
  });

  return {
    user,
    marketData,
    pendingOrder,
    executedTrade,
  };
};

// Performance Test Data
export const createPerformanceTestData = {
  highFrequency: () => ({
    orders: createTestOrderBatch(1000, { type: 'MARKET', status: 'PENDING' }),
    marketTicks: createTestMarketDataBatch(5000),
    users: createTestUserBatch(100, { isActive: true }),
  }),

  stressTest: () => ({
    orders: createTestOrderBatch(10000, { type: 'MARKET', status: 'PENDING' }),
    marketTicks: createTestMarketDataBatch(50000),
    users: createTestUserBatch(1000, { isActive: true }),
  }),

  memoryIntensive: () => ({
    orders: createTestOrderBatch(100000, { type: 'LIMIT' }),
    marketData: createTestMarketDataBatch(500000),
  }),
};

// Error Scenario Factories
export const createErrorScenarios = {
  invalidOrder: () => createTestOrder({
    quantity: -1000, // Invalid quantity
    symbol: 'INVALID/PAIR', // Invalid symbol
  }),

  insufficientFunds: (user: TestUser) => createTestOrder({
    userId: user.id,
    quantity: user.accountBalance * 100, // Quantity exceeding balance
    type: 'MARKET',
  }),

  marketClosed: () => createTestOrder({
    timestamp: '2023-12-25T00:00:00Z', // Christmas Day
    type: 'MARKET',
  }),

  connectionError: () => ({
    type: 'error',
    error: {
      message: 'Connection lost',
      code: 'CONNECTION_LOST',
      timestamp: Date.now(),
    },
  }),
};

// Test Environment Configuration
export const createTestEnvironment = {
  development: () => ({
    apiUrl: 'https://dev-api.fxml4.com/v1',
    websocketUrl: 'wss://dev-ws.fxml4.com',
    database: ':memory:',
    debug: true,
  }),

  testing: () => ({
    apiUrl: 'https://test-api.fxml4.com/v1',
    websocketUrl: 'wss://test-ws.fxml4.com',
    database: 'test.db',
    debug: false,
  }),

  staging: () => ({
    apiUrl: 'https://staging-api.fxml4.com/v1',
    websocketUrl: 'wss://staging-ws.fxml4.com',
    database: 'staging_test.db',
    debug: false,
  }),
};

// Utility Functions for Test Data
export const testDataUtils = {
  // Generate deterministic data for consistent tests
  generateDeterministic: <T>(factory: () => T, seed: string): T => {
    faker.seed(seed.split('').reduce((acc, char) => acc + char.charCodeAt(0), 0));
    const result = factory();
    faker.seed(); // Reset seed
    return result;
  },

  // Validate test data structure
  validateTestOrder: (order: TestOrder): boolean => {
    return !!(
      order.id &&
      order.symbol &&
      ['BUY', 'SELL'].includes(order.side) &&
      order.quantity > 0 &&
      ['MARKET', 'LIMIT', 'STOP'].includes(order.type) &&
      ['PENDING', 'EXECUTED', 'CANCELLED', 'REJECTED'].includes(order.status)
    );
  },

  validateTestMarketData: (data: TestMarketData): boolean => {
    return !!(
      data.symbol &&
      data.bid > 0 &&
      data.ask > data.bid &&
      data.spread > 0 &&
      data.timestamp
    );
  },

  // Deep clone test data for mutation testing
  cloneTestData: <T>(data: T): T => {
    return JSON.parse(JSON.stringify(data));
  },

  // Generate time series data for testing charts
  generateTimeSeries: (
    basePrice: number,
    periods: number,
    volatility: number = 0.01
  ): Array<{ timestamp: number; price: number }> => {
    const timeSeries = [];
    let currentPrice = basePrice;
    const startTime = Date.now() - (periods * 60000); // 1 minute intervals

    for (let i = 0; i < periods; i++) {
      const randomChange = (Math.random() - 0.5) * 2 * volatility;
      currentPrice *= (1 + randomChange);

      timeSeries.push({
        timestamp: startTime + (i * 60000),
        price: parseFloat(currentPrice.toFixed(4)),
      });
    }

    return timeSeries;
  },
};
