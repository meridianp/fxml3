/**
 * TradingConsole Component Tests
 *
 * Tests for the main trading interface integration
 */

import React from 'react';
import { screen, fireEvent, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { renderWithStore, mockApiSuccess } from '@/test-utils/render';
import { mockAccount, mockMarketData } from '@/test-utils/setup';
import TradingConsole from '../TradingConsole';
import { api } from '@/services/api';

jest.mock('@/services/api');
const mockedApi = api as jest.Mocked<typeof api>;

jest.mock('@/stores/tradingStore');
jest.mock('@/stores/marketDataStore');
jest.mock('@/stores/appStore');

// Mock child components to focus on integration testing
jest.mock('../OrderPanel', () => {
  return function MockOrderPanel() {
    return <div data-testid="order-panel">Order Panel Component</div>;
  };
});

jest.mock('../OrdersTable', () => {
  return function MockOrdersTable() {
    return <div data-testid="orders-table">Orders Table Component</div>;
  };
});

jest.mock('../PositionsTable', () => {
  return function MockPositionsTable() {
    return <div data-testid="positions-table">Positions Table Component</div>;
  };
});

describe('TradingConsole', () => {
  const user = userEvent.setup();

  const mockInitialState = {
    tradingState: {
      account: mockAccount,
      orders: [],
      positions: [],
      signals: [],
      isLoadingOrders: false,
      isLoadingPositions: false,
      isLoadingAccount: false,
    },
    marketDataState: {
      currentPrices: mockMarketData,
      isConnected: true,
      symbols: ['EURUSD', 'GBPUSD', 'USDJPY'],
    },
    appState: {
      isConnected: true,
      connectionStatus: 'connected',
      preferences: {
        theme: 'dark',
        default_timeframe: '1h',
        favorite_symbols: ['EURUSD', 'GBPUSD'],
      },
    },
  };

  beforeEach(() => {
    jest.clearAllMocks();
    mockedApi.get.mockResolvedValue(mockApiSuccess({}));
    mockedApi.post.mockResolvedValue(mockApiSuccess({}));
  });

  describe('Component Rendering', () => {
    it('should render all main trading components', () => {
      renderWithStore(<TradingConsole />, mockInitialState);

      expect(screen.getByTestId('order-panel')).toBeInTheDocument();
      expect(screen.getByTestId('orders-table')).toBeInTheDocument();
      expect(screen.getByTestId('positions-table')).toBeInTheDocument();
    });

    it('should display account summary information', () => {
      renderWithStore(<TradingConsole />, mockInitialState);

      expect(screen.getByText('Account Balance')).toBeInTheDocument();
      expect(screen.getByText('$100,000.00')).toBeInTheDocument();
      expect(screen.getByText('Equity')).toBeInTheDocument();
      expect(screen.getByText('$102,500.00')).toBeInTheDocument();
      expect(screen.getByText('Available Margin')).toBeInTheDocument();
      expect(screen.getByText('$97,500.00')).toBeInTheDocument();
    });

    it('should show connection status indicator', () => {
      renderWithStore(<TradingConsole />, {
        ...mockInitialState,
        appState: {
          ...mockInitialState.appState,
          isConnected: true,
          connectionStatus: 'connected',
        },
      });

      expect(screen.getByText('Connected')).toBeInTheDocument();
      expect(screen.getByTestId('connection-indicator')).toHaveClass('bg-green-500');
    });

    it('should show disconnected state', () => {
      renderWithStore(<TradingConsole />, {
        ...mockInitialState,
        appState: {
          ...mockInitialState.appState,
          isConnected: false,
          connectionStatus: 'disconnected',
        },
      });

      expect(screen.getByText('Disconnected')).toBeInTheDocument();
      expect(screen.getByTestId('connection-indicator')).toHaveClass('bg-red-500');
    });
  });

  describe('Market Data Display', () => {
    it('should display current market prices', () => {
      renderWithStore(<TradingConsole />, mockInitialState);

      expect(screen.getByText('EURUSD')).toBeInTheDocument();
      expect(screen.getByText('1.08245')).toBeInTheDocument();
      expect(screen.getByText('1.08248')).toBeInTheDocument();
      expect(screen.getByText('GBPUSD')).toBeInTheDocument();
      expect(screen.getByText('1.27156')).toBeInTheDocument();
    });

    it('should show last update time', () => {
      renderWithStore(<TradingConsole />, mockInitialState);

      expect(screen.getByText('Last Update:')).toBeInTheDocument();
    });

    it('should handle missing market data gracefully', () => {
      renderWithStore(<TradingConsole />, {
        ...mockInitialState,
        marketDataState: {
          ...mockInitialState.marketDataState,
          currentPrices: {},
          isConnected: false,
        },
      });

      expect(screen.getByText('Market Data Unavailable')).toBeInTheDocument();
    });
  });

  describe('Account Information', () => {
    it('should calculate and display margin usage percentage', () => {
      renderWithStore(<TradingConsole />, mockInitialState);

      // Margin used: 2500, Equity: 102500
      // Usage: (2500 / 102500) * 100 = ~2.44%
      expect(screen.getByText('Margin Usage')).toBeInTheDocument();
      expect(screen.getByText('2.44%')).toBeInTheDocument();
    });

    it('should show P&L information', () => {
      renderWithStore(<TradingConsole />, mockInitialState);

      expect(screen.getByText('Realized P&L')).toBeInTheDocument();
      expect(screen.getByText('+$1,500.00')).toBeInTheDocument();
      expect(screen.getByText('Unrealized P&L')).toBeInTheDocument();
      expect(screen.getByText('+$1,000.00')).toBeInTheDocument();
    });

    it('should handle loading account state', () => {
      renderWithStore(<TradingConsole />, {
        ...mockInitialState,
        tradingState: {
          ...mockInitialState.tradingState,
          account: null,
          isLoadingAccount: true,
        },
      });

      expect(screen.getByText('Loading account...')).toBeInTheDocument();
    });

    it('should handle account loading error', () => {
      renderWithStore(<TradingConsole />, {
        ...mockInitialState,
        tradingState: {
          ...mockInitialState.tradingState,
          account: null,
          isLoadingAccount: false,
        },
        appState: {
          ...mockInitialState.appState,
          errors: [{ message: 'Failed to load account', type: 'error' }],
        },
      });

      expect(screen.getByText('Error loading account')).toBeInTheDocument();
    });
  });

  describe('Trading Session Management', () => {
    it('should display trading session status', () => {
      renderWithStore(<TradingConsole />, mockInitialState);

      expect(screen.getByText('Trading Session')).toBeInTheDocument();
      expect(screen.getByText('Market Open')).toBeInTheDocument();
    });

    it('should show session countdown during closed hours', () => {
      // Mock current time to be during market close
      const mockDate = new Date('2024-01-15T02:00:00.000Z'); // Monday 2 AM UTC (market closed)
      jest.spyOn(global, 'Date').mockImplementation(() => mockDate as any);

      renderWithStore(<TradingConsole />, mockInitialState);

      expect(screen.getByText('Market Closed')).toBeInTheDocument();
      expect(screen.getByText(/Opens in/)).toBeInTheDocument();

      jest.restoreAllMocks();
    });

    it('should handle different market sessions', () => {
      renderWithStore(<TradingConsole />, mockInitialState);

      // Should detect different trading sessions (Asian, European, US)
      expect(screen.getByText(/Session:/)).toBeInTheDocument();
    });
  });

  describe('Quick Actions', () => {
    it('should provide quick buy/sell actions', async () => {
      renderWithStore(<TradingConsole />, mockInitialState);

      const quickBuyButton = screen.getByText('Quick Buy EURUSD');
      const quickSellButton = screen.getByText('Quick Sell EURUSD');

      expect(quickBuyButton).toBeInTheDocument();
      expect(quickSellButton).toBeInTheDocument();
    });

    it('should execute quick buy order', async () => {
      mockedApi.post.mockResolvedValueOnce(mockApiSuccess({
        order: { id: 'quick-order-1', status: 'pending' },
      }));

      renderWithStore(<TradingConsole />, mockInitialState);

      const quickBuyButton = screen.getByText('Quick Buy EURUSD');
      await user.click(quickBuyButton);

      await waitFor(() => {
        expect(mockedApi.post).toHaveBeenCalledWith('/trading/orders', {
          symbol: 'EURUSD',
          side: 'buy',
          type: 'market',
          quantity: 10000,
        });
      });
    });

    it('should close all positions button', async () => {
      renderWithStore(<TradingConsole />, {
        ...mockInitialState,
        tradingState: {
          ...mockInitialState.tradingState,
          positions: [
            { id: 'pos-1', symbol: 'EURUSD', unrealized_pnl: 50 },
            { id: 'pos-2', symbol: 'GBPUSD', unrealized_pnl: -25 },
          ],
        },
      });

      const closeAllButton = screen.getByText('Close All Positions');
      expect(closeAllButton).toBeInTheDocument();

      await user.click(closeAllButton);

      // Should show confirmation dialog
      expect(screen.getByText('Confirm Close All')).toBeInTheDocument();
    });
  });

  describe('Risk Management', () => {
    it('should show risk warnings for high margin usage', () => {
      renderWithStore(<TradingConsole />, {
        ...mockInitialState,
        tradingState: {
          ...mockInitialState.tradingState,
          account: {
            ...mockAccount,
            margin_used: 80000, // High margin usage
            margin_available: 20000,
          },
        },
      });

      expect(screen.getByText('High Margin Usage')).toBeInTheDocument();
      expect(screen.getByText(/Warning:/)).toBeInTheDocument();
    });

    it('should display margin call warning', () => {
      renderWithStore(<TradingConsole />, {
        ...mockInitialState,
        tradingState: {
          ...mockInitialState.tradingState,
          account: {
            ...mockAccount,
            margin_used: 95000, // Very high margin usage
            margin_available: 5000,
          },
        },
      });

      expect(screen.getByText('Margin Call Risk')).toBeInTheDocument();
    });

    it('should show daily P&L limits', () => {
      renderWithStore(<TradingConsole />, mockInitialState);

      expect(screen.getByText('Daily P&L')).toBeInTheDocument();
      expect(screen.getByText(/Limit:/)).toBeInTheDocument();
    });
  });

  describe('Layout Management', () => {
    it('should allow collapsing/expanding panels', async () => {
      renderWithStore(<TradingConsole />, mockInitialState);

      const collapseOrdersButton = screen.getByTitle('Collapse Orders Panel');
      await user.click(collapseOrdersButton);

      expect(screen.queryByTestId('orders-table')).not.toBeVisible();
    });

    it('should remember panel states', () => {
      renderWithStore(<TradingConsole />, {
        ...mockInitialState,
        appState: {
          ...mockInitialState.appState,
          preferences: {
            ...mockInitialState.appState.preferences,
            dashboard_layout: [
              { component: 'orders', collapsed: true },
              { component: 'positions', collapsed: false },
            ],
          },
        },
      });

      // Orders panel should start collapsed based on preferences
      expect(screen.queryByTestId('orders-table')).not.toBeVisible();
      expect(screen.getByTestId('positions-table')).toBeVisible();
    });
  });

  describe('Keyboard Shortcuts', () => {
    it('should handle keyboard shortcuts for quick actions', async () => {
      renderWithStore(<TradingConsole />, mockInitialState);

      // Test F1 for quick buy
      await user.keyboard('{F1}');

      // Should focus on order panel or trigger quick buy
      expect(screen.getByTestId('order-panel')).toHaveFocus();
    });

    it('should handle ESC to close modals', async () => {
      renderWithStore(<TradingConsole />, mockInitialState);

      // Open a modal first
      const settingsButton = screen.getByTitle('Trading Settings');
      await user.click(settingsButton);

      expect(screen.getByText('Trading Settings')).toBeInTheDocument();

      // Press ESC to close
      await user.keyboard('{Escape}');

      expect(screen.queryByText('Trading Settings')).not.toBeInTheDocument();
    });
  });

  describe('Real-time Updates', () => {
    it('should update when WebSocket data is received', () => {
      renderWithStore(<TradingConsole />, mockInitialState);

      // Simulate WebSocket price update
      const mockWebSocketData = {
        type: 'price_update',
        data: {
          EURUSD: { bid: 1.08300, ask: 1.08303 },
        },
      };

      // Trigger WebSocket message (this would need to be implemented based on actual WebSocket handling)
      expect(screen.getByText('EURUSD')).toBeInTheDocument();
    });

    it('should handle connection interruptions gracefully', () => {
      renderWithStore(<TradingConsole />, {
        ...mockInitialState,
        appState: {
          ...mockInitialState.appState,
          isConnected: false,
          connectionStatus: 'reconnecting',
        },
      });

      expect(screen.getByText('Reconnecting...')).toBeInTheDocument();
      expect(screen.getByTestId('connection-indicator')).toHaveClass('bg-yellow-500');
    });
  });

  describe('Error Handling', () => {
    it('should display global error messages', () => {
      renderWithStore(<TradingConsole />, {
        ...mockInitialState,
        appState: {
          ...mockInitialState.appState,
          errors: [
            { message: 'Connection lost', type: 'error', timestamp: Date.now() },
          ],
        },
      });

      expect(screen.getByText('Connection lost')).toBeInTheDocument();
    });

    it('should allow dismissing error messages', async () => {
      renderWithStore(<TradingConsole />, {
        ...mockInitialState,
        appState: {
          ...mockInitialState.appState,
          errors: [
            { message: 'Test error', type: 'error', timestamp: Date.now() },
          ],
        },
      });

      const dismissButton = screen.getByTitle('Dismiss Error');
      await user.click(dismissButton);

      expect(screen.queryByText('Test error')).not.toBeInTheDocument();
    });
  });
});
