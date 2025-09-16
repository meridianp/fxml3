/**
 * OrdersTable Component Tests
 *
 * Tests for order management and monitoring functionality
 */

import React from 'react';
import { screen, fireEvent, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { render, renderWithStore, generateMockOrder, mockApiSuccess, mockApiError } from '@/test-utils/render';
import OrdersTable from '../OrdersTable';
import { api } from '@/services/api';

jest.mock('@/services/api');
const mockedApi = api as jest.Mocked<typeof api>;

jest.mock('@/stores/tradingStore');
jest.mock('@/stores/marketDataStore');
jest.mock('@/stores/appStore');

describe('OrdersTable', () => {
  const user = userEvent.setup();

  const mockOrders = [
    generateMockOrder({
      id: 'order-1',
      symbol: 'EURUSD',
      side: 'buy',
      type: 'market',
      quantity: 10000,
      status: 'pending',
      created_at: '2024-01-15T10:25:00.000Z',
    }),
    generateMockOrder({
      id: 'order-2',
      symbol: 'GBPUSD',
      side: 'sell',
      type: 'limit',
      quantity: 5000,
      price: 1.27100,
      status: 'filled',
      filled_quantity: 5000,
      avg_fill_price: 1.27105,
      created_at: '2024-01-15T10:20:00.000Z',
    }),
    generateMockOrder({
      id: 'order-3',
      symbol: 'USDJPY',
      side: 'buy',
      type: 'stop',
      quantity: 8000,
      price: 148.50,
      status: 'cancelled',
      created_at: '2024-01-15T10:15:00.000Z',
    }),
  ];

  const mockMarketData = {
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

  beforeEach(() => {
    jest.clearAllMocks();
  });

  describe('Component Rendering', () => {
    it('should render empty state when no orders', () => {
      renderWithStore(<OrdersTable />, {
        tradingState: { orders: [] },
      });

      expect(screen.getByText('No Orders')).toBeInTheDocument();
      expect(screen.getByText('Your orders will appear here')).toBeInTheDocument();
    });

    it('should render orders table with data', () => {
      renderWithStore(<OrdersTable />, {
        tradingState: { orders: mockOrders },
        marketDataState: { currentPrices: mockMarketData },
      });

      expect(screen.getByText('Orders (3)')).toBeInTheDocument();
      expect(screen.getByText('EURUSD')).toBeInTheDocument();
      expect(screen.getByText('GBPUSD')).toBeInTheDocument();
      expect(screen.getByText('USDJPY')).toBeInTheDocument();
    });

    it('should display order details correctly', () => {
      renderWithStore(<OrdersTable />, {
        tradingState: { orders: [mockOrders[0]] },
        marketDataState: { currentPrices: mockMarketData },
      });

      // Check order details
      expect(screen.getByText('BUY')).toBeInTheDocument();
      expect(screen.getByText('MARKET')).toBeInTheDocument();
      expect(screen.getByText('10,000')).toBeInTheDocument();
      expect(screen.getByText('PENDING')).toBeInTheDocument();
    });

    it('should show filled order information', () => {
      renderWithStore(<OrdersTable />, {
        tradingState: { orders: [mockOrders[1]] },
        marketDataState: { currentPrices: mockMarketData },
      });

      expect(screen.getByText('SELL')).toBeInTheDocument();
      expect(screen.getByText('LIMIT')).toBeInTheDocument();
      expect(screen.getByText('1.27100')).toBeInTheDocument(); // Order price
      expect(screen.getByText('1.27105')).toBeInTheDocument(); // Avg fill price
      expect(screen.getByText('FILLED')).toBeInTheDocument();
      expect(screen.getByText('5,000 / 5,000')).toBeInTheDocument(); // Fill status
    });
  });

  describe('Order Status Display', () => {
    it('should use correct colors for order status', () => {
      renderWithStore(<OrdersTable />, {
        tradingState: { orders: mockOrders },
      });

      const pendingStatus = screen.getByText('PENDING');
      const filledStatus = screen.getByText('FILLED');
      const cancelledStatus = screen.getByText('CANCELLED');

      expect(pendingStatus).toHaveClass('text-yellow-400');
      expect(filledStatus).toHaveClass('text-green-400');
      expect(cancelledStatus).toHaveClass('text-red-400');
    });

    it('should show correct colors for buy/sell orders', () => {
      renderWithStore(<OrdersTable />, {
        tradingState: { orders: [mockOrders[0], mockOrders[1]] },
      });

      const buyOrder = screen.getByText('BUY');
      const sellOrder = screen.getByText('SELL');

      expect(buyOrder).toHaveClass('text-green-400');
      expect(sellOrder).toHaveClass('text-red-400');
    });

    it('should display partially filled orders correctly', () => {
      const partialOrder = generateMockOrder({
        quantity: 10000,
        filled_quantity: 3000,
        status: 'partially_filled',
      });

      renderWithStore(<OrdersTable />, {
        tradingState: { orders: [partialOrder] },
      });

      expect(screen.getByText('PARTIALLY FILLED')).toBeInTheDocument();
      expect(screen.getByText('3,000 / 10,000')).toBeInTheDocument();
    });
  });

  describe('Order Management Actions', () => {
    it('should cancel pending order when cancel button is clicked', async () => {
      mockedApi.delete.mockResolvedValueOnce(mockApiSuccess({}));

      renderWithStore(<OrdersTable />, {
        tradingState: { orders: [mockOrders[0]] },
        marketDataState: { currentPrices: mockMarketData },
      });

      const cancelButton = screen.getByTitle('Cancel Order');
      await user.click(cancelButton);

      await waitFor(() => {
        expect(mockedApi.delete).toHaveBeenCalledWith('/trading/orders/order-1');
      });
    });

    it('should not show cancel button for filled orders', () => {
      renderWithStore(<OrdersTable />, {
        tradingState: { orders: [mockOrders[1]] }, // Filled order
      });

      expect(screen.queryByTitle('Cancel Order')).not.toBeInTheDocument();
    });

    it('should not show cancel button for cancelled orders', () => {
      renderWithStore(<OrdersTable />, {
        tradingState: { orders: [mockOrders[2]] }, // Cancelled order
      });

      expect(screen.queryByTitle('Cancel Order')).not.toBeInTheDocument();
    });

    it('should handle order cancellation errors', async () => {
      mockedApi.delete.mockRejectedValueOnce(mockApiError('Order cannot be cancelled', 400));

      renderWithStore(<OrdersTable />, {
        tradingState: { orders: [mockOrders[0]] },
        marketDataState: { currentPrices: mockMarketData },
      });

      const cancelButton = screen.getByTitle('Cancel Order');
      await user.click(cancelButton);

      await waitFor(() => {
        expect(screen.getByText('Order cannot be cancelled')).toBeInTheDocument();
      });
    });

    it('should show loading state while cancelling order', async () => {
      mockedApi.delete.mockImplementationOnce(() =>
        new Promise(resolve => setTimeout(() => resolve(mockApiSuccess({})), 1000))
      );

      renderWithStore(<OrdersTable />, {
        tradingState: { orders: [mockOrders[0]] },
        marketDataState: { currentPrices: mockMarketData },
      });

      const cancelButton = screen.getByTitle('Cancel Order');
      await user.click(cancelButton);

      // Should show loading spinner
      expect(screen.getByRole('button')).toHaveClass('animate-spin');
    });

    it('should modify order when modify button is clicked', async () => {
      renderWithStore(<OrdersTable />, {
        tradingState: { orders: [mockOrders[0]] },
        marketDataState: { currentPrices: mockMarketData },
      });

      const modifyButton = screen.getByTitle('Modify Order');
      await user.click(modifyButton);

      // Should select the order in the store for modification
      // This would be tested by checking if the selected order is set
    });
  });

  describe('Order Filtering and Sorting', () => {
    it('should filter orders by status', async () => {
      renderWithStore(<OrdersTable />, {
        tradingState: { orders: mockOrders },
      });

      // Filter by pending orders
      const statusFilter = screen.getByDisplayValue('all');
      await user.selectOptions(statusFilter, 'pending');

      // Should only show pending orders
      expect(screen.getByText('PENDING')).toBeInTheDocument();
      expect(screen.queryByText('FILLED')).not.toBeInTheDocument();
      expect(screen.queryByText('CANCELLED')).not.toBeInTheDocument();
    });

    it('should filter orders by symbol', async () => {
      renderWithStore(<OrdersTable />, {
        tradingState: { orders: mockOrders },
      });

      // Filter by EURUSD
      const symbolFilter = screen.getByPlaceholderText('Filter by symbol...');
      await user.type(symbolFilter, 'EURUSD');

      // Should only show EURUSD orders
      expect(screen.getByText('EURUSD')).toBeInTheDocument();
      expect(screen.queryByText('GBPUSD')).not.toBeInTheDocument();
      expect(screen.queryByText('USDJPY')).not.toBeInTheDocument();
    });

    it('should sort orders by time', async () => {
      renderWithStore(<OrdersTable />, {
        tradingState: { orders: mockOrders },
      });

      const sortButton = screen.getByTitle('Sort by Time');
      await user.click(sortButton);

      // Orders should be sorted by creation time
      const orderRows = screen.getAllByTestId('order-row');
      expect(orderRows).toHaveLength(3);

      // Most recent order should be first (order-1: 10:25)
      expect(orderRows[0]).toHaveTextContent('order-1');
    });
  });

  describe('Time Display', () => {
    it('should display order creation time', () => {
      const recentOrder = generateMockOrder({
        created_at: new Date(Date.now() - 5 * 60 * 1000).toISOString(), // 5 minutes ago
      });

      renderWithStore(<OrdersTable />, {
        tradingState: { orders: [recentOrder] },
      });

      expect(screen.getByText('5m ago')).toBeInTheDocument();
    });

    it('should display fill time for completed orders', () => {
      const filledOrder = generateMockOrder({
        status: 'filled',
        updated_at: new Date(Date.now() - 10 * 60 * 1000).toISOString(), // 10 minutes ago
      });

      renderWithStore(<OrdersTable />, {
        tradingState: { orders: [filledOrder] },
      });

      expect(screen.getByText('Filled 10m ago')).toBeInTheDocument();
    });
  });

  describe('Order Summary', () => {
    it('should calculate and display total order count by status', () => {
      renderWithStore(<OrdersTable />, {
        tradingState: { orders: mockOrders },
      });

      expect(screen.getByText('Total Orders')).toBeInTheDocument();
      expect(screen.getByText('3')).toBeInTheDocument();
    });

    it('should show pending orders count', () => {
      const pendingOrders = mockOrders.filter(order => order.status === 'pending');

      renderWithStore(<OrdersTable />, {
        tradingState: { orders: mockOrders },
      });

      expect(screen.getByText('Pending')).toBeInTheDocument();
      expect(screen.getByText(pendingOrders.length.toString())).toBeInTheDocument();
    });

    it('should calculate total order value', () => {
      renderWithStore(<OrdersTable />, {
        tradingState: { orders: mockOrders },
        marketDataState: { currentPrices: mockMarketData },
      });

      expect(screen.getByText('Total Value')).toBeInTheDocument();
      // Should calculate based on current prices for pending orders
    });
  });

  describe('Connection Status', () => {
    it('should show connection status indicator', () => {
      renderWithStore(<OrdersTable />, {
        tradingState: { orders: mockOrders },
        appState: { isConnected: false },
      });

      expect(screen.getByText('Disconnected')).toBeInTheDocument();
    });

    it('should disable actions when disconnected', () => {
      renderWithStore(<OrdersTable />, {
        tradingState: { orders: [mockOrders[0]] },
        appState: { isConnected: false },
      });

      const cancelButton = screen.getByTitle('Cancel Order');
      expect(cancelButton).toBeDisabled();
    });
  });

  describe('Order Details Expansion', () => {
    it('should expand order details when row is clicked', async () => {
      renderWithStore(<OrdersTable />, {
        tradingState: { orders: [mockOrders[1]] },
      });

      const orderRow = screen.getByTestId('order-row');
      await user.click(orderRow);

      // Should show expanded details
      expect(screen.getByText('Order Details')).toBeInTheDocument();
      expect(screen.getByText('Average Fill Price:')).toBeInTheDocument();
      expect(screen.getByText('1.27105')).toBeInTheDocument();
    });

    it('should show stop loss and take profit if set', async () => {
      const orderWithSLTP = generateMockOrder({
        stop_loss: 1.08100,
        take_profit: 1.08400,
      });

      renderWithStore(<OrdersTable />, {
        tradingState: { orders: [orderWithSLTP] },
      });

      const orderRow = screen.getByTestId('order-row');
      await user.click(orderRow);

      expect(screen.getByText('Stop Loss: 1.08100')).toBeInTheDocument();
      expect(screen.getByText('Take Profit: 1.08400')).toBeInTheDocument();
    });
  });

  describe('Error Handling', () => {
    it('should display error state when orders fail to load', () => {
      renderWithStore(<OrdersTable />, {
        tradingState: {
          orders: [],
          isLoadingOrders: false,
        },
        appState: {
          errors: [{ message: 'Failed to load orders', type: 'error' }],
        },
      });

      expect(screen.getByText('Error loading orders')).toBeInTheDocument();
    });

    it('should show retry button on error', async () => {
      renderWithStore(<OrdersTable />, {
        tradingState: {
          orders: [],
          isLoadingOrders: false,
        },
        appState: {
          errors: [{ message: 'Failed to load orders', type: 'error' }],
        },
      });

      const retryButton = screen.getByText('Retry');
      expect(retryButton).toBeInTheDocument();
    });
  });

  describe('Loading States', () => {
    it('should show loading spinner when orders are being fetched', () => {
      renderWithStore(<OrdersTable />, {
        tradingState: {
          orders: [],
          isLoadingOrders: true,
        },
      });

      expect(screen.getByText('Loading orders...')).toBeInTheDocument();
    });
  });
});
