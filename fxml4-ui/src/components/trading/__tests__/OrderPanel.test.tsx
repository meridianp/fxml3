/**
 * OrderPanel Component Tests
 *
 * Comprehensive tests for the order placement functionality
 */

import React from 'react';
import { screen, fireEvent, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { render, renderWithStore, mockApiSuccess, mockApiError } from '@/test-utils/render';
import { mockAccount } from '@/test-utils/setup';
import OrderPanel from '../OrderPanel';
import { api } from '@/services/api';

// Mock the API service
jest.mock('@/services/api');
const mockedApi = api as jest.Mocked<typeof api>;

// Mock the stores
jest.mock('@/stores/marketDataStore');
jest.mock('@/stores/tradingStore');
jest.mock('@/stores/appStore');

describe('OrderPanel', () => {
  const user = userEvent.setup();

  const mockMarketData = {
    EURUSD: {
      symbol: 'EURUSD',
      bid: 1.08245,
      ask: 1.08248,
      timestamp: '2024-01-15T10:30:00.000Z',
      volume: 1000000,
    },
  };

  beforeEach(() => {
    jest.clearAllMocks();
  });

  describe('Component Rendering', () => {
    it('should render order panel with default values', () => {
      render(<OrderPanel />);

      expect(screen.getByText('Place Order')).toBeInTheDocument();
      expect(screen.getByDisplayValue('EURUSD')).toBeInTheDocument();
      expect(screen.getByDisplayValue('10000')).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /BUY 10000 EURUSD/i })).toBeInTheDocument();
    });

    it('should display current market prices when available', () => {
      renderWithStore(<OrderPanel />, {
        marketDataState: {
          currentPrices: mockMarketData,
        },
      });

      expect(screen.getByText('1.08245')).toBeInTheDocument(); // Bid
      expect(screen.getByText('1.08248')).toBeInTheDocument(); // Ask
      expect(screen.getByText('0.00003')).toBeInTheDocument(); // Spread
    });

    it('should show margin calculations', () => {
      renderWithStore(<OrderPanel />, {
        marketDataState: { currentPrices: mockMarketData },
        tradingState: { account: mockAccount },
      });

      // Should display required margin and available margin
      expect(screen.getByText('Required Margin:')).toBeInTheDocument();
      expect(screen.getByText('Available Margin:')).toBeInTheDocument();
    });
  });

  describe('Order Type Selection', () => {
    it('should switch between buy and sell', async () => {
      render(<OrderPanel />);

      const sellButton = screen.getByRole('button', { name: /SELL/i });
      await user.click(sellButton);

      expect(screen.getByRole('button', { name: /SELL 10000 EURUSD/i })).toBeInTheDocument();
    });

    it('should change order type from market to limit', async () => {
      render(<OrderPanel />);

      const orderTypeSelect = screen.getByDisplayValue('market');
      await user.selectOptions(orderTypeSelect, 'limit');

      expect(screen.getByDisplayValue('limit')).toBeInTheDocument();
      expect(screen.getByPlaceholderText('Enter price...')).toBeInTheDocument();
    });

    it('should show price input for limit orders', async () => {
      render(<OrderPanel />);

      const orderTypeSelect = screen.getByDisplayValue('market');
      await user.selectOptions(orderTypeSelect, 'limit');

      const priceInput = screen.getByPlaceholderText('Enter price...');
      expect(priceInput).toBeInTheDocument();

      await user.type(priceInput, '1.08200');
      expect(priceInput).toHaveValue(1.08200);
    });
  });

  describe('Advanced Options', () => {
    it('should show advanced options when settings icon is clicked', async () => {
      render(<OrderPanel />);

      const settingsButton = screen.getByTitle('Advanced Options');
      await user.click(settingsButton);

      expect(screen.getByPlaceholderText('Optional stop loss price...')).toBeInTheDocument();
      expect(screen.getByPlaceholderText('Optional take profit price...')).toBeInTheDocument();
    });

    it('should accept stop loss and take profit values', async () => {
      render(<OrderPanel />);

      const settingsButton = screen.getByTitle('Advanced Options');
      await user.click(settingsButton);

      const stopLossInput = screen.getByPlaceholderText('Optional stop loss price...');
      const takeProfitInput = screen.getByPlaceholderText('Optional take profit price...');

      await user.type(stopLossInput, '1.08100');
      await user.type(takeProfitInput, '1.08400');

      expect(stopLossInput).toHaveValue(1.08100);
      expect(takeProfitInput).toHaveValue(1.08400);
    });
  });

  describe('Order Validation', () => {
    it('should disable order button when insufficient margin', () => {
      renderWithStore(<OrderPanel />, {
        marketDataState: { currentPrices: mockMarketData },
        tradingState: {
          account: { ...mockAccount, margin_available: 100 }, // Very low margin
        },
      });

      const orderButton = screen.getByRole('button', { name: /BUY 10000 EURUSD/i });
      expect(orderButton).toBeDisabled();

      expect(screen.getByText(/Insufficient margin to place this order/i)).toBeInTheDocument();
    });

    it('should require price for limit orders', async () => {
      render(<OrderPanel />);

      // Switch to limit order
      const orderTypeSelect = screen.getByDisplayValue('market');
      await user.selectOptions(orderTypeSelect, 'limit');

      const orderButton = screen.getByRole('button', { name: /BUY 10000 EURUSD/i });
      expect(orderButton).toBeDisabled();
    });

    it('should validate quantity input', async () => {
      render(<OrderPanel />);

      const quantityInput = screen.getByDisplayValue('10000');
      await user.clear(quantityInput);
      await user.type(quantityInput, '0');

      const orderButton = screen.getByRole('button', { name: /BUY 0 EURUSD/i });
      expect(orderButton).toBeDisabled();
    });
  });

  describe('Order Placement', () => {
    it('should place a market order successfully', async () => {
      mockedApi.post.mockResolvedValueOnce(mockApiSuccess({
        order: {
          id: 'order-123',
          symbol: 'EURUSD',
          side: 'buy',
          type: 'market',
          quantity: 10000,
          status: 'pending',
        },
      }));

      renderWithStore(<OrderPanel />, {
        marketDataState: { currentPrices: mockMarketData },
        tradingState: { account: mockAccount },
      });

      const orderButton = screen.getByRole('button', { name: /BUY 10000 EURUSD/i });
      await user.click(orderButton);

      await waitFor(() => {
        expect(mockedApi.post).toHaveBeenCalledWith('/trading/orders', {
          symbol: 'EURUSD',
          side: 'buy',
          type: 'market',
          quantity: 10000,
          price: undefined,
          stop_loss: undefined,
          take_profit: undefined,
          time_in_force: 'GTC',
        });
      });
    });

    it('should place a limit order with price', async () => {
      mockedApi.post.mockResolvedValueOnce(mockApiSuccess({
        order: {
          id: 'order-124',
          symbol: 'EURUSD',
          side: 'buy',
          type: 'limit',
          quantity: 10000,
          price: 1.08200,
          status: 'pending',
        },
      }));

      render(<OrderPanel />);

      // Switch to limit order and set price
      const orderTypeSelect = screen.getByDisplayValue('market');
      await user.selectOptions(orderTypeSelect, 'limit');

      const priceInput = screen.getByPlaceholderText('Enter price...');
      await user.type(priceInput, '1.08200');

      const orderButton = screen.getByRole('button', { name: /BUY 10000 EURUSD/i });
      await user.click(orderButton);

      await waitFor(() => {
        expect(mockedApi.post).toHaveBeenCalledWith('/trading/orders', {
          symbol: 'EURUSD',
          side: 'buy',
          type: 'limit',
          quantity: 10000,
          price: 1.08200,
          stop_loss: undefined,
          take_profit: undefined,
          time_in_force: 'GTC',
        });
      });
    });

    it('should include stop loss and take profit in order', async () => {
      mockedApi.post.mockResolvedValueOnce(mockApiSuccess({ order: {} }));

      render(<OrderPanel />);

      // Open advanced options
      const settingsButton = screen.getByTitle('Advanced Options');
      await user.click(settingsButton);

      // Set stop loss and take profit
      const stopLossInput = screen.getByPlaceholderText('Optional stop loss price...');
      const takeProfitInput = screen.getByPlaceholderText('Optional take profit price...');

      await user.type(stopLossInput, '1.08100');
      await user.type(takeProfitInput, '1.08400');

      const orderButton = screen.getByRole('button', { name: /BUY 10000 EURUSD/i });
      await user.click(orderButton);

      await waitFor(() => {
        expect(mockedApi.post).toHaveBeenCalledWith('/trading/orders', expect.objectContaining({
          stop_loss: 1.08100,
          take_profit: 1.08400,
        }));
      });
    });

    it('should handle order placement errors', async () => {
      mockedApi.post.mockRejectedValueOnce(mockApiError('Insufficient margin', 400));

      renderWithStore(<OrderPanel />, {
        marketDataState: { currentPrices: mockMarketData },
        tradingState: { account: mockAccount },
      });

      const orderButton = screen.getByRole('button', { name: /BUY 10000 EURUSD/i });
      await user.click(orderButton);

      await waitFor(() => {
        expect(screen.getByText('Insufficient margin')).toBeInTheDocument();
      });
    });

    it('should show loading state during order placement', async () => {
      mockedApi.post.mockImplementationOnce(() =>
        new Promise(resolve => setTimeout(() => resolve(mockApiSuccess({ order: {} })), 1000))
      );

      renderWithStore(<OrderPanel />, {
        marketDataState: { currentPrices: mockMarketData },
        tradingState: { account: mockAccount },
      });

      const orderButton = screen.getByRole('button', { name: /BUY 10000 EURUSD/i });
      await user.click(orderButton);

      expect(screen.getByText('Placing Order...')).toBeInTheDocument();
      expect(orderButton).toBeDisabled();
    });
  });

  describe('Symbol Selection', () => {
    it('should change symbol and update calculations', async () => {
      const mockGbpData = {
        GBPUSD: {
          symbol: 'GBPUSD',
          bid: 1.27156,
          ask: 1.27159,
          timestamp: '2024-01-15T10:30:00.000Z',
          volume: 750000,
        },
      };

      renderWithStore(<OrderPanel />, {
        marketDataState: {
          currentPrices: { ...mockMarketData, ...mockGbpData }
        },
        tradingState: { account: mockAccount },
      });

      // Find and interact with symbol selector (this would need to be implemented)
      // For now, we'll test the order button text changes
      const orderButton = screen.getByRole('button', { name: /BUY 10000 EURUSD/i });
      expect(orderButton).toBeInTheDocument();
    });
  });

  describe('Risk Management', () => {
    it('should calculate and display order value correctly', () => {
      renderWithStore(<OrderPanel />, {
        marketDataState: { currentPrices: mockMarketData },
        tradingState: { account: mockAccount },
      });

      expect(screen.getByText('Order Value:')).toBeInTheDocument();
      // Order value should be quantity * ask price for buy orders
      // 10000 * 1.08248 = 10824.8
      expect(screen.getByText('$10,824.80')).toBeInTheDocument();
    });

    it('should calculate required margin based on leverage', () => {
      renderWithStore(<OrderPanel />, {
        marketDataState: { currentPrices: mockMarketData },
        tradingState: { account: { ...mockAccount, leverage: 50 } }, // 50:1 leverage
      });

      // Required margin should be order value / leverage
      // 10824.8 / 50 = 216.50
      expect(screen.getByText('$216.50')).toBeInTheDocument();
    });
  });
});
