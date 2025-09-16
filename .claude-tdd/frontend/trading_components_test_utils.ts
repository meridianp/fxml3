/**
 * FXML4 Trading Components Test Utilities
 * Specialized testing utilities for financial trading UI components
 */

import { render, RenderOptions, RenderResult } from '@testing-library/react'
import { ReactElement, ReactNode } from 'react'
import { Provider } from 'react-redux'
import { ThemeProvider } from 'styled-components'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'

// Types for trading-specific test data
export interface MockMarketData {
  symbol: string
  bid: number
  ask: number
  timestamp: string
  change: number
  changePercent: number
}

export interface MockTradingAccount {
  accountId: string
  balance: number
  equity: number
  marginUsed: number
  marginAvailable: number
  positions: MockPosition[]
}

export interface MockPosition {
  id: string
  symbol: string
  side: 'long' | 'short'
  size: number
  entryPrice: number
  currentPrice: number
  unrealizedPnl: number
  timestamp: string
}

export interface MockSignal {
  id: string
  symbol: string
  action: 'buy' | 'sell' | 'hold'
  confidence: number
  entryPrice: number
  stopLoss?: number
  takeProfit?: number
  timestamp: string
  reasoning: string
}

// Mock data generators
export const createMockMarketData = (overrides: Partial<MockMarketData> = {}): MockMarketData => ({
  symbol: 'GBPUSD',
  bid: 1.2500,
  ask: 1.2502,
  timestamp: new Date().toISOString(),
  change: 0.0015,
  changePercent: 0.12,
  ...overrides,
})

export const createMockTradingAccount = (overrides: Partial<MockTradingAccount> = {}): MockTradingAccount => ({
  accountId: 'ACC001',
  balance: 10000.00,
  equity: 10150.00,
  marginUsed: 500.00,
  marginAvailable: 9650.00,
  positions: [],
  ...overrides,
})

export const createMockPosition = (overrides: Partial<MockPosition> = {}): MockPosition => ({
  id: 'POS001',
  symbol: 'GBPUSD',
  side: 'long',
  size: 10000,
  entryPrice: 1.2480,
  currentPrice: 1.2500,
  unrealizedPnl: 20.00,
  timestamp: new Date().toISOString(),
  ...overrides,
})

export const createMockSignal = (overrides: Partial<MockSignal> = {}): MockSignal => ({
  id: 'SIG001',
  symbol: 'GBPUSD',
  action: 'buy',
  confidence: 0.85,
  entryPrice: 1.2500,
  stopLoss: 1.2450,
  takeProfit: 1.2600,
  timestamp: new Date().toISOString(),
  reasoning: 'Elliott Wave pattern suggests upward movement',
  ...overrides,
})

// WebSocket mock for real-time data
export class MockWebSocket {
  private listeners: { [key: string]: Function[] } = {}
  public readyState: number = 1

  constructor(public url: string) {}

  addEventListener(event: string, listener: Function) {
    if (!this.listeners[event]) {
      this.listeners[event] = []
    }
    this.listeners[event].push(listener)
  }

  removeEventListener(event: string, listener: Function) {
    if (this.listeners[event]) {
      this.listeners[event] = this.listeners[event].filter(l => l !== listener)
    }
  }

  send(data: string) {
    // Mock sending data
    console.log('Mock WebSocket send:', data)
  }

  close() {
    this.readyState = 3
    this.dispatchEvent('close', {})
  }

  // Utility to simulate receiving data
  simulateMessage(data: any) {
    this.dispatchEvent('message', { data: JSON.stringify(data) })
  }

  private dispatchEvent(event: string, data: any) {
    if (this.listeners[event]) {
      this.listeners[event].forEach(listener => listener(data))
    }
  }
}

// Redux store mock for testing
export const createMockStore = (initialState: any = {}) => {
  const defaultState = {
    trading: {
      account: createMockTradingAccount(),
      positions: [],
      orders: [],
      signals: [],
    },
    market: {
      symbols: ['GBPUSD', 'EURUSD', 'USDJPY'],
      prices: {},
      isConnected: true,
    },
    ui: {
      selectedSymbol: 'GBPUSD',
      theme: 'dark',
      isLoading: false,
    },
    ...initialState,
  }

  return {
    getState: () => defaultState,
    dispatch: jest.fn(),
    subscribe: jest.fn(),
    replaceReducer: jest.fn(),
  }
}

// Custom render function with trading-specific providers
interface CustomRenderOptions extends Omit<RenderOptions, 'wrapper'> {
  initialState?: any
  theme?: any
}

export const renderWithProviders = (
  ui: ReactElement,
  options: CustomRenderOptions = {}
): RenderResult => {
  const { initialState, theme, ...renderOptions } = options

  const mockStore = createMockStore(initialState)
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  })

  const defaultTheme = {
    colors: {
      primary: '#1f2937',
      secondary: '#374151',
      success: '#10b981',
      danger: '#ef4444',
      warning: '#f59e0b',
      text: '#f9fafb',
      background: '#111827',
    },
    fonts: {
      mono: 'JetBrains Mono, monospace',
      sans: 'Inter, sans-serif',
    },
  }

  function Wrapper({ children }: { children: ReactNode }) {
    return (
      <Provider store={mockStore}>
        <QueryClientProvider client={queryClient}>
          <ThemeProvider theme={theme || defaultTheme}>
            {children}
          </ThemeProvider>
        </QueryClientProvider>
      </Provider>
    )
  }

  return render(ui, { wrapper: Wrapper, ...renderOptions })
}

// Financial calculation test utilities
export const formatCurrency = (amount: number, currency: string = 'USD'): string => {
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency,
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(amount)
}

export const formatPrice = (price: number, decimals: number = 5): string => {
  return price.toFixed(decimals)
}

export const calculatePnL = (
  side: 'long' | 'short',
  entryPrice: number,
  currentPrice: number,
  size: number
): number => {
  const priceDiff = side === 'long'
    ? currentPrice - entryPrice
    : entryPrice - currentPrice
  return priceDiff * size
}

export const calculateMarginUsed = (
  price: number,
  size: number,
  leverage: number = 100
): number => {
  return (price * size) / leverage
}

// Chart testing utilities
export const mockChartData = (periods: number = 100): any[] => {
  const data = []
  let currentPrice = 1.2500
  const baseTime = Date.now() - (periods * 60000) // 1 minute per candle

  for (let i = 0; i < periods; i++) {
    const variation = (Math.random() - 0.5) * 0.01 // ±0.5% variation
    const open = currentPrice
    const change = variation * open
    const close = open + change
    const high = Math.max(open, close) + Math.random() * 0.0005
    const low = Math.min(open, close) - Math.random() * 0.0005

    data.push({
      timestamp: baseTime + (i * 60000),
      open,
      high,
      low,
      close,
      volume: Math.floor(Math.random() * 1000000),
    })

    currentPrice = close
  }

  return data
}

// API response mocks
export const mockApiResponses = {
  marketData: (symbol: string) => ({
    symbol,
    bid: 1.2500 + Math.random() * 0.01,
    ask: 1.2502 + Math.random() * 0.01,
    timestamp: new Date().toISOString(),
  }),

  accountStatus: () => createMockTradingAccount(),

  tradingSignals: (count: number = 5) =>
    Array.from({ length: count }, (_, i) => createMockSignal({
      id: `SIG${String(i + 1).padStart(3, '0')}`,
    })),

  waveAnalysis: (symbol: string) => ({
    symbol,
    waveCount: {
      currentWave: Math.floor(Math.random() * 5) + 1,
      waveType: Math.random() > 0.5 ? 'impulse' : 'corrective',
      confidence: 0.7 + Math.random() * 0.3,
    },
    fibonacciLevels: [
      { level: 0.236, price: 1.2450, type: 'support' },
      { level: 0.382, price: 1.2480, type: 'support' },
      { level: 0.618, price: 1.2520, type: 'resistance' },
    ],
    signals: [createMockSignal({ symbol })],
  }),
}

// Performance testing utilities
export const measureRenderTime = (renderFn: () => any): number => {
  const start = performance.now()
  renderFn()
  const end = performance.now()
  return end - start
}

export const simulateTyping = async (
  element: HTMLElement,
  text: string,
  delay: number = 50
) => {
  const { userEvent } = await import('@testing-library/user-event')
  const user = userEvent.setup({ delay })

  await user.clear(element)
  await user.type(element, text)
}

// Accessibility testing utilities
export const checkAccessibility = async (container: HTMLElement) => {
  const { axe } = await import('jest-axe')
  const results = await axe(container)
  return results
}

// Trading-specific test scenarios
export const tradingScenarios = {
  // Profitable long position
  profitableLong: createMockPosition({
    side: 'long',
    entryPrice: 1.2450,
    currentPrice: 1.2500,
    unrealizedPnl: 50.00,
  }),

  // Loss-making short position
  losingShort: createMockPosition({
    side: 'short',
    entryPrice: 1.2500,
    currentPrice: 1.2520,
    unrealizedPnl: -20.00,
  }),

  // High-confidence buy signal
  strongBuySignal: createMockSignal({
    action: 'buy',
    confidence: 0.95,
    reasoning: 'Multiple bullish confirmations: Elliott Wave, RSI oversold, support level hold',
  }),

  // Market volatility scenario
  volatileMarket: createMockMarketData({
    changePercent: 2.5, // 2.5% change
    change: 0.03125,
  }),

  // Account at risk
  highRiskAccount: createMockTradingAccount({
    balance: 1000.00,
    equity: 800.00,
    marginUsed: 750.00,
    marginAvailable: 50.00,
  }),
}

// Test data validation
export const validateTradingData = {
  isValidPrice: (price: number): boolean =>
    typeof price === 'number' && price > 0 && !isNaN(price),

  isValidSymbol: (symbol: string): boolean =>
    typeof symbol === 'string' && /^[A-Z]{6}$/.test(symbol),

  isValidPnL: (pnl: number): boolean =>
    typeof pnl === 'number' && !isNaN(pnl),

  isValidConfidence: (confidence: number): boolean =>
    typeof confidence === 'number' && confidence >= 0 && confidence <= 1,
}

export default {
  renderWithProviders,
  createMockStore,
  MockWebSocket,
  mockApiResponses,
  tradingScenarios,
  validateTradingData,
  measureRenderTime,
  checkAccessibility,
}
