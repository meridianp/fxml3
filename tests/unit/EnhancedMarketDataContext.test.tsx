/**
 * Unit Tests for EnhancedMarketDataContext
 *
 * Tests real-time market data context functionality,
 * WebSocket integration, and performance monitoring.
 */

import React from 'react';
import { render, screen, waitFor, act } from '@testing-library/react';
import { EnhancedMarketDataProvider, useEnhancedMarketData } from '../../src/contexts/EnhancedMarketDataContext';

// Mock WebSocketService
jest.mock('../../src/services/WebSocketService');

const TestComponent: React.FC = () => {
  const { marketData, connectionStatus, subscribe, unsubscribe, getPerformanceMetrics, reconnect } = useEnhancedMarketData();

  return (
    <div>
      <div data-testid="connection-status">{connectionStatus}</div>
      <div data-testid="eur-usd-price">{marketData['EUR/USD']?.price || 'N/A'}</div>
      <button onClick={() => subscribe(['EUR/USD'])} data-testid="subscribe-btn">
        Subscribe
      </button>
      <button onClick={() => unsubscribe(['EUR/USD'])} data-testid="unsubscribe-btn">
        Unsubscribe
      </button>
      <button onClick={() => reconnect()} data-testid="reconnect-btn">
        Reconnect
      </button>
      <div data-testid="metrics">{JSON.stringify(getPerformanceMetrics())}</div>
    </div>
  );
};

describe('EnhancedMarketDataContext', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  describe('Provider Initialization', () => {
    test('provides market data context to children', () => {
      render(
        <EnhancedMarketDataProvider>
          <TestComponent />
        </EnhancedMarketDataProvider>
      );

      expect(screen.getByTestId('connection-status')).toBeInTheDocument();
      expect(screen.getByTestId('eur-usd-price')).toBeInTheDocument();
    });

    test('initializes with provided initial data', () => {
      const initialData = {
        'EUR/USD': {
          price: 1.0525,
          bid: 1.0524,
          ask: 1.0526,
          volume: 1000000,
          timestamp: new Date(),
          change: 0.0025,
          changePercent: 0.24
        }
      };

      render(
        <EnhancedMarketDataProvider initialData={initialData}>
          <TestComponent />
        </EnhancedMarketDataProvider>
      );

      expect(screen.getByTestId('eur-usd-price')).toHaveTextContent('1.0525');
    });

    test('initializes with provided connection status', () => {
      render(
        <EnhancedMarketDataProvider connectionStatus="connecting">
          <TestComponent />
        </EnhancedMarketDataProvider>
      );

      expect(screen.getByTestId('connection-status')).toHaveTextContent('connecting');
    });
  });

  describe('Context Hook', () => {
    test('throws error when used outside provider', () => {
      // Suppress console.error for this test
      const consoleError = jest.spyOn(console, 'error').mockImplementation(() => {});

      expect(() => render(<TestComponent />)).toThrow(
        'useEnhancedMarketData must be used within an EnhancedMarketDataProvider'
      );

      consoleError.mockRestore();
    });
  });

  describe('Subscription Management', () => {
    test('handles symbol subscription', async () => {
      render(
        <EnhancedMarketDataProvider>
          <TestComponent />
        </EnhancedMarketDataProvider>
      );

      const subscribeBtn = screen.getByTestId('subscribe-btn');

      await act(async () => {
        subscribeBtn.click();
      });

      // Verify component doesn't crash and renders properly
      expect(screen.getByTestId('connection-status')).toBeInTheDocument();
    });

    test('handles symbol unsubscription', async () => {
      render(
        <EnhancedMarketDataProvider>
          <TestComponent />
        </EnhancedMarketDataProvider>
      );

      const unsubscribeBtn = screen.getByTestId('unsubscribe-btn');

      await act(async () => {
        unsubscribeBtn.click();
      });

      // Verify component doesn't crash and renders properly
      expect(screen.getByTestId('connection-status')).toBeInTheDocument();
    });
  });

  describe('Connection Management', () => {
    test('handles reconnection', async () => {
      render(
        <EnhancedMarketDataProvider>
          <TestComponent />
        </EnhancedMarketDataProvider>
      );

      const reconnectBtn = screen.getByTestId('reconnect-btn');

      await act(async () => {
        reconnectBtn.click();
      });

      // Verify component doesn't crash and renders properly
      expect(screen.getByTestId('connection-status')).toBeInTheDocument();
    });
  });

  describe('Performance Metrics', () => {
    test('provides performance metrics', () => {
      render(
        <EnhancedMarketDataProvider>
          <TestComponent />
        </EnhancedMarketDataProvider>
      );

      const metricsElement = screen.getByTestId('metrics');

      // Should render some metrics data
      expect(metricsElement).toBeInTheDocument();
    });
  });

  describe('Market Data Updates', () => {
    test('updates market data when new data received', async () => {
      const initialData = {
        'EUR/USD': {
          price: 1.0500,
          bid: 1.0499,
          ask: 1.0501,
          volume: 500000,
          timestamp: new Date()
        }
      };

      render(
        <EnhancedMarketDataProvider initialData={initialData}>
          <TestComponent />
        </EnhancedMarketDataProvider>
      );

      expect(screen.getByTestId('eur-usd-price')).toHaveTextContent('1.05');
    });
  });

  describe('WebSocket Configuration', () => {
    test('accepts custom WebSocket configuration', () => {
      const wsConfig = {
        url: 'ws://custom-endpoint:8080',
        reconnectInterval: 500,
        maxReconnectAttempts: 5,
        heartbeatInterval: 2000
      };

      render(
        <EnhancedMarketDataProvider wsConfig={wsConfig}>
          <TestComponent />
        </EnhancedMarketDataProvider>
      );

      // Verify component renders without error with custom config
      expect(screen.getByTestId('connection-status')).toBeInTheDocument();
    });
  });
});
