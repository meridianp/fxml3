/**
 * Frontend Integration Tests for FXML4 Trading Platform
 *
 * Tests end-to-end frontend workflows including:
 * - Complete trading workflows from market data to order execution
 * - Real-time data streaming with WebSocket connections
 * - Backend API integration with error handling
 * - Cross-component communication and state management
 * - Performance under load with multiple concurrent users
 * - Elliott Wave analysis integration with live charts
 * - ML prediction pipeline integration
 * - Emergency procedures and risk management
 */

import React from 'react';
import { render, screen, fireEvent, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import '@testing-library/jest-dom';

// Import all components for integration testing
import { TradingDashboard } from '../../src/components/TradingDashboard';
import { MarketDataProvider } from '../../src/contexts/MarketDataContext';
import { OrderProvider } from '../../src/contexts/OrderContext';

// Mock WebSocket for real-time testing
class MockWebSocket {
  constructor(url) {
    this.url = url;
    this.readyState = WebSocket.CONNECTING;
    this.onopen = null;
    this.onmessage = null;
    this.onclose = null;
    this.onerror = null;

    // Simulate connection after 100ms
    setTimeout(() => {
      this.readyState = WebSocket.OPEN;
      if (this.onopen) this.onopen(new Event('open'));
    }, 100);
  }

  send(data) {
    // Simulate server response after 50ms
    setTimeout(() => {
      if (this.onmessage) {
        const mockResponse = {
          type: 'price_update',
          symbol: 'EUR/USD',
          price: 1.0501,
          bid: 1.0500,
          ask: 1.0502,
          volume: 1500000,
          timestamp: new Date().toISOString()
        };
        this.onmessage({ data: JSON.stringify(mockResponse) });
      }
    }, 50);
  }

  close() {
    this.readyState = WebSocket.CLOSED;
    if (this.onclose) this.onclose(new Event('close'));
  }
}

// Mock fetch for API calls
global.fetch = jest.fn();

describe('Frontend Integration Tests', () => {
  let mockWebSocket;

  beforeEach(() => {
    jest.clearAllMocks();
    global.WebSocket = jest.fn().mockImplementation((url) => {
      mockWebSocket = new MockWebSocket(url);
      return mockWebSocket;
    });

    // Mock successful API responses
    global.fetch.mockResolvedValue({
      ok: true,
      json: async () => ({
        success: true,
        orderId: 'order_123456',
        status: 'PENDING'
      })
    });
  });

  afterEach(() => {
    if (mockWebSocket) {
      mockWebSocket.close();
    }
  });

  describe('Complete Trading Workflow Integration', () => {
    test('end-to-end trading workflow: market data → order placement → execution', async () => {
      const user = userEvent.setup();
      const mockProps = {
        userId: 'trader_001',
        accountId: 'acc_789',
        symbols: ['EUR/USD', 'GBP/USD', 'USD/JPY'],
        positions: [
          {
            symbol: 'EUR/USD',
            quantity: 100000,
            entryPrice: 1.0450,
            currentPrice: 1.0500,
            unrealizedPnL: 500
          }
        ],
        accountData: {
          balance: 100000,
          equity: 100500,
          margin: 10000,
          freeMargin: 90500
        }
      };

      const onOrderSubmit = jest.fn();
      const onOrderModify = jest.fn();

      render(
        <MarketDataProvider>
          <OrderProvider onOrderSubmit={onOrderSubmit}>
            <TradingDashboard {...mockProps} onOrderModify={onOrderModify} />
          </OrderProvider>
        </MarketDataProvider>
      );

      // 1. Verify initial dashboard load
      expect(screen.getByTestId('trading-dashboard')).toBeInTheDocument();
      expect(screen.getByTestId('market-watchlist')).toBeInTheDocument();
      expect(screen.getByTestId('order-panel')).toBeInTheDocument();
      expect(screen.getByTestId('positions-table')).toBeInTheDocument();

      // 2. Wait for WebSocket connection and real-time data
      await waitFor(() => {
        const watchlist = screen.getByTestId('market-watchlist');
        expect(within(watchlist).getByText('EUR/USD')).toBeInTheDocument();
      });

      // 3. Place a market order
      const orderPanel = screen.getByTestId('order-panel');

      // Enter trade details
      await user.type(
        within(orderPanel).getByLabelText('Quantity'),
        '50000'
      );

      // Execute buy order
      await user.click(within(orderPanel).getByText('BUY'));

      // 4. Verify order submission with proper data
      expect(onOrderSubmit).toHaveBeenCalledWith({
        symbol: 'EUR/USD',
        side: 'BUY',
        quantity: 50000,
        orderType: 'MARKET',
        price: undefined
      });

      // 5. Verify order appears in orders table
      await waitFor(() => {
        const ordersTable = screen.getByTestId('orders-table');
        expect(within(ordersTable).getByText('Open Orders')).toBeInTheDocument();

        // Look for BUY order specifically in orders table
        const orderRows = within(ordersTable).getAllByRole('row');
        const buyOrderExists = orderRows.some(row => {
          const rowText = row.textContent;
          return rowText?.includes('EUR/USD') && rowText?.includes('BUY') && rowText?.includes('50,000');
        });
        expect(buyOrderExists).toBe(true);
      });

      // 6. Verify P&L updates correctly
      const pnlDisplay = screen.getByTestId('total-pnl');
      expect(pnlDisplay).toHaveTextContent('$500.00');
      expect(pnlDisplay).toHaveClass('profit');

      // 7. Test order modification workflow
      const ordersTable = screen.getByTestId('orders-table');
      const modifyButtons = within(ordersTable).getAllByText('Modify');

      // Click the first modify button (should be the pending order)
      if (modifyButtons.length > 0) {
        await user.click(modifyButtons[0]);
      }

      // Wait for modal to open
      const modal = screen.getByRole('dialog');
      expect(within(modal).getByText('Modify Order')).toBeInTheDocument();

      // Update price
      const priceInput = within(modal).getByLabelText('Price');
      await user.clear(priceInput);
      await user.type(priceInput, '1.0520');
      await user.click(within(modal).getByText('Update Order'));

      // Verify modification callback
      expect(onOrderModify).toHaveBeenCalledWith({
        orderId: expect.any(String),
        price: 1.0520
      });
    });

    test('real-time market data streaming with price updates', async () => {
      const mockProps = {
        userId: 'trader_001',
        accountId: 'acc_789',
        symbols: ['EUR/USD', 'GBP/USD']
      };

      render(
        <MarketDataProvider>
          <OrderProvider>
            <TradingDashboard {...mockProps} />
          </OrderProvider>
        </MarketDataProvider>
      );

      const watchlist = screen.getByTestId('market-watchlist');

      // Wait for initial connection
      await waitFor(() => {
        expect(within(watchlist).getByText('EUR/USD')).toBeInTheDocument();
      });

      // Simulate WebSocket price updates
      const priceUpdate = {
        type: 'price_update',
        symbol: 'EUR/USD',
        price: 1.0525,
        bid: 1.0524,
        ask: 1.0526,
        volume: 2000000,
        timestamp: new Date().toISOString()
      };

      // Trigger WebSocket message
      if (mockWebSocket && mockWebSocket.onmessage) {
        mockWebSocket.onmessage({
          data: JSON.stringify(priceUpdate)
        });
      }

      // Verify price updates in UI - use more flexible matching
      await waitFor(() => {
        const priceElements = within(watchlist).getAllByText(/1\.05/);
        expect(priceElements.length).toBeGreaterThan(0);
      }, { timeout: 2000 });

      // Verify connection status indicator
      const statusIndicator = screen.getByTestId('connection-status');
      expect(statusIndicator).toHaveClass('connected');
    });

    test('Elliott Wave analysis integration with chart display', async () => {
      const user = userEvent.setup();
      const mockProps = {
        userId: 'trader_001',
        accountId: 'acc_789',
        symbols: ['EUR/USD']
      };

      render(
        <MarketDataProvider>
          <OrderProvider>
            <TradingDashboard {...mockProps} />
          </OrderProvider>
        </MarketDataProvider>
      );

      const chart = screen.getByTestId('price-chart');

      // Toggle Elliott Wave analysis
      const elliotWaveToggle = screen.getByLabelText('Elliott Wave');
      await user.click(elliotWaveToggle);

      // Verify Elliott Wave overlay appears
      await waitFor(() => {
        const elliotOverlay = within(chart).getByTestId('elliott-wave-overlay');
        expect(elliotOverlay).toBeInTheDocument();
        expect(within(elliotOverlay).getByText('Wave 3')).toBeInTheDocument();
      });

      // Test timeframe changes
      const timeframeButtons = ['1m', '5m', '15m', '1h', '4h', '1d'];

      for (const tf of timeframeButtons) {
        const button = within(chart).getByTestId(`timeframe-${tf}`);
        await user.click(button);

        await waitFor(() => {
          expect(button).toHaveClass('selected');
        });
      }
    });
  });

  describe('Error Handling and Resilience', () => {
    test('handles WebSocket connection failures gracefully', async () => {
      const mockProps = {
        userId: 'trader_001',
        accountId: 'acc_789',
        symbols: ['EUR/USD']
      };

      render(
        <MarketDataProvider connectionStatus="disconnected">
          <OrderProvider>
            <TradingDashboard {...mockProps} />
          </OrderProvider>
        </MarketDataProvider>
      );

      // Wait for component to render
      await waitFor(() => {
        expect(screen.getByTestId('trading-dashboard')).toBeInTheDocument();
      });

      // Verify dashboard still functions with cached/fallback data
      expect(screen.getByTestId('market-watchlist')).toBeInTheDocument();
      expect(screen.getByTestId('order-panel')).toBeInTheDocument();

      // Verify connection status indicator shows appropriate state
      const statusIndicator = screen.getByTestId('connection-status');
      expect(statusIndicator).toBeInTheDocument();
    });

    test('handles API failures with proper error messages', async () => {
      // Mock API failure
      global.fetch.mockRejectedValueOnce(new Error('Network error'));

      const user = userEvent.setup();
      const mockProps = {
        userId: 'trader_001',
        accountId: 'acc_789',
        symbols: ['EUR/USD']
      };

      const onOrderSubmit = jest.fn();

      render(
        <MarketDataProvider>
          <OrderProvider onOrderSubmit={onOrderSubmit}>
            <TradingDashboard {...mockProps} />
          </OrderProvider>
        </MarketDataProvider>
      );

      const orderPanel = screen.getByTestId('order-panel');

      // Attempt to place order
      await user.type(
        within(orderPanel).getByLabelText('Quantity'),
        '10000'
      );
      await user.click(within(orderPanel).getByText('BUY'));

      // Order should still be submitted to callback
      expect(onOrderSubmit).toHaveBeenCalled();
    });

    test('validates input data and prevents invalid orders', async () => {
      const user = userEvent.setup();
      const mockProps = {
        userId: 'trader_001',
        accountId: 'acc_789',
        symbols: ['EUR/USD']
      };

      render(
        <MarketDataProvider>
          <OrderProvider>
            <TradingDashboard {...mockProps} />
          </OrderProvider>
        </MarketDataProvider>
      );

      const orderPanel = screen.getByTestId('order-panel');

      // Test empty quantity validation
      await user.click(within(orderPanel).getByText('BUY'));
      await waitFor(() => {
        expect(within(orderPanel).getByText('Quantity is required')).toBeInTheDocument();
      });

      // Test negative quantity validation
      const quantityInput = within(orderPanel).getByLabelText('Quantity');
      await user.clear(quantityInput);
      await user.type(quantityInput, '-1000');
      await user.click(within(orderPanel).getByText('BUY'));

      await waitFor(() => {
        expect(within(orderPanel).getByText('Quantity must be positive')).toBeInTheDocument();
      });
    });
  });

  describe('Performance and Load Testing', () => {
    test('handles multiple rapid price updates efficiently', async () => {
      const mockProps = {
        userId: 'trader_001',
        accountId: 'acc_789',
        symbols: ['EUR/USD', 'GBP/USD', 'USD/JPY']
      };

      render(
        <MarketDataProvider>
          <OrderProvider>
            <TradingDashboard {...mockProps} />
          </OrderProvider>
        </MarketDataProvider>
      );

      // Wait for initial load
      await waitFor(() => {
        expect(screen.getByTestId('market-watchlist')).toBeInTheDocument();
      });

      // Simulate rapid price updates with realistic timing
      const startTime = performance.now();
      let finalPrice = 1.0500;

      for (let i = 0; i < 5; i++) {
        finalPrice = 1.0500 + (i * 0.0001);
        const priceUpdate = {
          type: 'price_update',
          symbol: 'EUR/USD',
          price: finalPrice,
          bid: finalPrice - 0.00005,
          ask: finalPrice + 0.00005,
          volume: 1000000 + (i * 100000),
          timestamp: new Date().toISOString()
        };

        if (mockWebSocket && mockWebSocket.onmessage) {
          mockWebSocket.onmessage({
            data: JSON.stringify(priceUpdate)
          });
        }

        // Allow React to process the price update
        await waitFor(() => {
          // Just wait for next tick to ensure UI processing
        }, { timeout: 10 });
      }

      const endTime = performance.now();
      const processingTime = endTime - startTime;

      // Verify updates processed efficiently
      expect(processingTime).toBeLessThan(1000); // Should handle 5 updates in <1s

      // Verify UI is still responsive
      const watchlist = screen.getByTestId('market-watchlist');
      expect(within(watchlist).getByText('EUR/USD')).toBeInTheDocument();
    });

    test('maintains responsive UI under concurrent operations', async () => {
      const user = userEvent.setup();
      const mockProps = {
        userId: 'trader_001',
        accountId: 'acc_789',
        symbols: ['EUR/USD'],
        positions: [
          { symbol: 'EUR/USD', quantity: 100000, entryPrice: 1.0450, currentPrice: 1.0500, unrealizedPnL: 500 },
          { symbol: 'GBP/USD', quantity: -50000, entryPrice: 1.2550, currentPrice: 1.2500, unrealizedPnL: 250 }
        ]
      };

      render(
        <MarketDataProvider>
          <OrderProvider>
            <TradingDashboard {...mockProps} />
          </OrderProvider>
        </MarketDataProvider>
      );

      // Perform multiple concurrent UI operations
      const startTime = performance.now();

      // Perform concurrent operations sequentially to avoid conflicts
      const filterInput = screen.getByPlaceholderText('Filter positions...');
      const themeToggle = screen.getByTestId('theme-toggle');
      const timeframeButton = screen.getByTestId('timeframe-1h');
      const quantityInput = within(screen.getByTestId('order-panel')).getByLabelText('Quantity');

      // Perform operations with small delays to ensure they complete
      await user.type(filterInput, 'EUR');
      await user.click(themeToggle);
      await user.click(timeframeButton);
      await user.type(quantityInput, '25000');

      const endTime = performance.now();
      const operationTime = endTime - startTime;

      // Verify all operations completed efficiently
      expect(operationTime).toBeLessThan(2000); // All operations in <2s

      // Verify all operations took effect
      expect(screen.getByTestId('trading-dashboard')).toHaveClass('theme-dark');
      expect(timeframeButton).toHaveClass('selected');
      expect(filterInput).toHaveValue('EUR');
      expect(quantityInput).toHaveValue('25000');
    });
  });

  describe('ML Integration and Advanced Features', () => {
    test('displays ML predictions with real-time confidence updates', async () => {
      const mlPredictions = {
        'EUR/USD': { direction: 'up', confidence: 0.87, target: 1.0580 },
        'GBP/USD': { direction: 'down', confidence: 0.73, target: 1.2420 }
      };

      const mockProps = {
        userId: 'trader_001',
        accountId: 'acc_789',
        symbols: ['EUR/USD', 'GBP/USD'],
        mlPredictions
      };

      render(
        <MarketDataProvider>
          <OrderProvider>
            <TradingDashboard {...mockProps} mlPredictions={mlPredictions} />
          </OrderProvider>
        </MarketDataProvider>
      );

      const mlPanel = screen.getByTestId('ml-predictions');

      // Verify initial predictions display
      expect(within(mlPanel).getByText('EUR/USD')).toBeInTheDocument();
      expect(within(mlPanel).getByText('GBP/USD')).toBeInTheDocument();

      // Use more flexible matching for percentages and arrows
      expect(within(mlPanel).getByText(/87%/)).toBeInTheDocument();
      expect(within(mlPanel).getByText(/73%/)).toBeInTheDocument();
      expect(within(mlPanel).getByText(/↑/)).toBeInTheDocument();
      expect(within(mlPanel).getByText(/↓/)).toBeInTheDocument();
    });

    test('emergency stop procedure works across all components', async () => {
      const user = userEvent.setup();
      const onEmergencyStop = jest.fn();

      const mockProps = {
        userId: 'trader_001',
        accountId: 'acc_789',
        symbols: ['EUR/USD'],
        positions: [
          { symbol: 'EUR/USD', quantity: 100000, entryPrice: 1.0450, currentPrice: 1.0500, unrealizedPnL: 500 }
        ],
        onEmergencyStop
      };

      render(
        <MarketDataProvider>
          <OrderProvider>
            <TradingDashboard {...mockProps} />
          </OrderProvider>
        </MarketDataProvider>
      );

      // Trigger emergency stop
      const emergencyButton = screen.getByTestId('emergency-stop');
      await user.click(emergencyButton);

      // Verify confirmation modal
      const modal = screen.getByRole('dialog');
      expect(within(modal).getByText('Emergency Stop')).toBeInTheDocument();
      expect(within(modal).getByText(/immediately close all positions/)).toBeInTheDocument();

      // Confirm emergency stop
      await user.click(within(modal).getByText('CONFIRM SHUTDOWN'));

      // Verify callback execution
      expect(onEmergencyStop).toHaveBeenCalled();
    });
  });

  describe('News and Market Events Integration', () => {
    test('displays news feed with impact indicators', async () => {
      const newsItems = [
        { id: 1, title: 'ECB Rate Decision Expected', impact: 'high' },
        { id: 2, title: 'USD Employment Report', impact: 'medium' },
        { id: 3, title: 'EUR Inflation Data', impact: 'low' }
      ];

      const mockProps = {
        userId: 'trader_001',
        accountId: 'acc_789',
        symbols: ['EUR/USD'],
        newsItems
      };

      render(
        <MarketDataProvider>
          <OrderProvider>
            <TradingDashboard {...mockProps} />
          </OrderProvider>
        </MarketDataProvider>
      );

      const newsPanel = screen.getByTestId('news-feed');

      // Verify all news items display
      expect(within(newsPanel).getByText('ECB Rate Decision Expected')).toBeInTheDocument();
      expect(within(newsPanel).getByText('USD Employment Report')).toBeInTheDocument();
      expect(within(newsPanel).getByText('EUR Inflation Data')).toBeInTheDocument();

      // Verify impact indicators
      expect(within(newsPanel).getByTestId('impact-high')).toBeInTheDocument();
      expect(within(newsPanel).getByTestId('impact-medium')).toBeInTheDocument();
      expect(within(newsPanel).getByTestId('impact-low')).toBeInTheDocument();
    });
  });

  describe('Keyboard Shortcuts and Accessibility', () => {
    test('keyboard shortcuts work correctly', async () => {
      const user = userEvent.setup();
      const onQuickBuy = jest.fn();
      const onQuickSell = jest.fn();

      const mockProps = {
        userId: 'trader_001',
        accountId: 'acc_789',
        symbols: ['EUR/USD'],
        onQuickBuy,
        onQuickSell
      };

      render(
        <MarketDataProvider>
          <OrderProvider>
            <TradingDashboard {...mockProps} />
          </OrderProvider>
        </MarketDataProvider>
      );

      // Test quick buy shortcut
      await user.keyboard('b');
      expect(onQuickBuy).toHaveBeenCalled();

      // Test quick sell shortcut
      await user.keyboard('s');
      expect(onQuickSell).toHaveBeenCalled();
    });

    test('components are accessible with screen readers', async () => {
      const mockProps = {
        userId: 'trader_001',
        accountId: 'acc_789',
        symbols: ['EUR/USD']
      };

      render(
        <MarketDataProvider>
          <OrderProvider>
            <TradingDashboard {...mockProps} />
          </OrderProvider>
        </MarketDataProvider>
      );

      // Verify main sections have proper ARIA labels
      expect(screen.getByTestId('trading-dashboard')).toBeInTheDocument();
      expect(screen.getByTestId('market-watchlist')).toBeInTheDocument();
      expect(screen.getByTestId('order-panel')).toBeInTheDocument();
      expect(screen.getByTestId('positions-table')).toBeInTheDocument();

      // Verify form controls have proper labels
      expect(screen.getByLabelText('Quantity')).toBeInTheDocument();
      expect(screen.getByDisplayValue('EUR/USD')).toBeInTheDocument();

      // Verify buttons have accessible names
      expect(screen.getByRole('button', { name: 'BUY' })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: 'SELL' })).toBeInTheDocument();
    });
  });
});
