/**
 * PositionsTable Component Tests
 *
 * Tests for real-time position monitoring and management
 */

import React from 'react';
import { screen, fireEvent, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { render, renderWithStore, generateMockPosition, mockApiSuccess } from '@/test-utils/render';
import PositionsTable from '../PositionsTable';
import { api } from '@/services/api';
import { calculateExpectedPnL } from '@/test-utils/render';

jest.mock('@/services/api');
const mockedApi = api as jest.Mocked<typeof api>;

jest.mock('@/stores/tradingStore');
jest.mock('@/stores/marketDataStore');
jest.mock('@/stores/appStore');

describe('PositionsTable', () => {
  const user = userEvent.setup();

  const mockPositions = [
    generateMockPosition({
      id: 'pos-1',
      symbol: 'EURUSD',
      side: 'long',
      quantity: 10000,
      entry_price: 1.08200,
      current_price: 1.08245,
      unrealized_pnl: 45,
    }),
    generateMockPosition({
      id: 'pos-2',
      symbol: 'GBPUSD',
      side: 'short',
      quantity: 5000,
      entry_price: 1.27200,
      current_price: 1.27156,
      unrealized_pnl: 22,
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
    it('should render empty state when no positions', () => {
      renderWithStore(<PositionsTable />, {
        tradingState: { positions: [] },
      });

      expect(screen.getByText('No Open Positions')).toBeInTheDocument();
      expect(screen.getByText('Your active positions will appear here')).toBeInTheDocument();
    });

    it('should render positions table with data', () => {
      renderWithStore(<PositionsTable />, {
        tradingState: { positions: mockPositions },
        marketDataState: { currentPrices: mockMarketData },
      });

      expect(screen.getByText('Open Positions (2)')).toBeInTheDocument();
      expect(screen.getByText('EURUSD')).toBeInTheDocument();
      expect(screen.getByText('GBPUSD')).toBeInTheDocument();
      expect(screen.getByText('LONG')).toBeInTheDocument();
      expect(screen.getByText('SHORT')).toBeInTheDocument();
    });

    it('should display position details correctly', () => {
      renderWithStore(<PositionsTable />, {
        tradingState: { positions: [mockPositions[0]] },
        marketDataState: { currentPrices: mockMarketData },
      });

      // Check position details
      expect(screen.getByText('10,000')).toBeInTheDocument(); // Quantity
      expect(screen.getByText('1.08200')).toBeInTheDocument(); // Entry price
      expect(screen.getByText('1.08245')).toBeInTheDocument(); // Current price
      expect(screen.getByText('+$45.00')).toBeInTheDocument(); // P&L
    });
  });

  describe('Real-time P&L Calculations', () => {
    it('should calculate P&L correctly for long position', () => {
      const position = generateMockPosition({
        side: 'long',
        entry_price: 1.08200,
        quantity: 10000,
      });

      renderWithStore(<PositionsTable />, {
        tradingState: { positions: [position] },
        marketDataState: {
          currentPrices: {
            EURUSD: {
              ...mockMarketData.EURUSD,
              bid: 1.08250, // Current price for long position
            },
          },
        },
      });

      // Expected P&L: (1.08250 - 1.08200) * 10000 = 50
      const expectedPnL = calculateExpectedPnL(1.08200, 1.08250, 10000, 'long');
      expect(screen.getByText(`+$${expectedPnL.toFixed(2)}`)).toBeInTheDocument();
    });

    it('should calculate P&L correctly for short position', () => {
      const position = generateMockPosition({
        side: 'short',
        entry_price: 1.27200,
        quantity: 5000,
      });

      renderWithStore(<PositionsTable />, {
        tradingState: { positions: [position] },
        marketDataState: {
          currentPrices: {
            EURUSD: {
              ...mockMarketData.EURUSD,
              ask: 1.27150, // Current price for short position
            },
          },
        },
      });

      // Expected P&L: (1.27200 - 1.27150) * 5000 = 250
      const expectedPnL = calculateExpectedPnL(1.27200, 1.27150, 5000, 'short');
      expect(screen.getByText(`+$${expectedPnL.toFixed(2)}`)).toBeInTheDocument();
    });

    it('should show negative P&L with correct formatting', () => {
      const position = generateMockPosition({
        side: 'long',
        entry_price: 1.08300,
        quantity: 10000,
      });

      renderWithStore(<PositionsTable />, {
        tradingState: { positions: [position] },
        marketDataState: {
          currentPrices: {
            EURUSD: {
              ...mockMarketData.EURUSD,
              bid: 1.08250, // Loss position
            },
          },
        },
      });

      // Expected P&L: (1.08250 - 1.08300) * 10000 = -50
      expect(screen.getByText('-$50.00')).toBeInTheDocument();
    });

    it('should calculate P&L percentage correctly', () => {
      const position = generateMockPosition({
        entry_price: 1.08200,
        quantity: 10000,
      });

      renderWithStore(<PositionsTable />, {
        tradingState: { positions: [position] },
        marketDataState: {
          currentPrices: {
            EURUSD: {
              ...mockMarketData.EURUSD,
              bid: 1.08308, // 1% gain
            },
          },
        },
      });

      // Should show approximately 1% gain
      expect(screen.getByText('+1.00%')).toBeInTheDocument();
    });
  });

  describe('Position Management Actions', () => {
    it('should close position when close button is clicked', async () => {
      mockedApi.post.mockResolvedValueOnce(mockApiSuccess({}));

      renderWithStore(<PositionsTable />, {
        tradingState: { positions: [mockPositions[0]] },
        marketDataState: { currentPrices: mockMarketData },
      });

      const closeButton = screen.getByTitle('Close Position');
      await user.click(closeButton);

      await waitFor(() => {
        expect(mockedApi.post).toHaveBeenCalledWith('/trading/positions/pos-1/close');
      });
    });

    it('should show loading state while closing position', async () => {
      mockedApi.post.mockImplementationOnce(() =>
        new Promise(resolve => setTimeout(() => resolve(mockApiSuccess({})), 1000))
      );

      renderWithStore(<PositionsTable />, {
        tradingState: { positions: [mockPositions[0]] },
        marketDataState: { currentPrices: mockMarketData },
      });

      const closeButton = screen.getByTitle('Close Position');
      await user.click(closeButton);

      // Should show loading spinner
      expect(screen.getByRole('button')).toHaveClass('animate-spin');
    });

    it('should modify position when modify button is clicked', async () => {
      renderWithStore(<PositionsTable />, {
        tradingState: { positions: [mockPositions[0]] },
        marketDataState: { currentPrices: mockMarketData },
      });

      const modifyButton = screen.getByTitle('Modify Position');
      await user.click(modifyButton);

      // Should select the position in the store
      // This would be tested by checking if the selected position is set
    });
  });

  describe('Connection Status', () => {
    it('should show disconnected indicator when market data unavailable', () => {
      renderWithStore(<PositionsTable />, {
        tradingState: { positions: [mockPositions[0]] },
        marketDataState: { currentPrices: {} }, // No market data
      });

      // Should show a disconnection indicator
      const symbol = screen.getByText('EURUSD');
      const row = symbol.closest('tr');
      expect(row).toContainHTML('bg-gray-500'); // Disconnected indicator
    });
  });

  describe('Position Summary', () => {
    it('should calculate and display total P&L', () => {
      renderWithStore(<PositionsTable />, {
        tradingState: { positions: mockPositions },
        marketDataState: { currentPrices: mockMarketData },
      });

      // Total P&L should be sum of all position P&L
      const totalPnL = mockPositions.reduce((sum, pos) => sum + pos.unrealized_pnl, 0);
      expect(screen.getByText(`+$${totalPnL.toFixed(2)}`)).toBeInTheDocument();
    });

    it('should display total number of positions', () => {
      renderWithStore(<PositionsTable />, {
        tradingState: { positions: mockPositions },
      });

      expect(screen.getByText('Total Positions')).toBeInTheDocument();
      expect(screen.getByText(mockPositions.length.toString())).toBeInTheDocument();
    });

    it('should calculate total position value', () => {
      renderWithStore(<PositionsTable />, {
        tradingState: { positions: mockPositions },
      });

      const totalValue = mockPositions.reduce(
        (sum, pos) => sum + (pos.entry_price * pos.quantity), 0
      );

      expect(screen.getByText('Total Value')).toBeInTheDocument();
      expect(screen.getByText(`$${totalValue.toLocaleString()}.00`)).toBeInTheDocument();
    });
  });

  describe('Time Display', () => {
    it('should display position duration', () => {
      const recentPosition = generateMockPosition({
        created_at: new Date(Date.now() - 2 * 60 * 60 * 1000).toISOString(), // 2 hours ago
      });

      renderWithStore(<PositionsTable />, {
        tradingState: { positions: [recentPosition] },
      });

      expect(screen.getByText('2h ago')).toBeInTheDocument();
    });
  });

  describe('Color Coding', () => {
    it('should use green color for positive P&L', () => {
      const profitPosition = generateMockPosition({
        unrealized_pnl: 150,
      });

      renderWithStore(<PositionsTable />, {
        tradingState: { positions: [profitPosition] },
      });

      const pnlElement = screen.getByText('+$150.00');
      expect(pnlElement).toHaveClass('text-green-400');
    });

    it('should use red color for negative P&L', () => {
      const lossPosition = generateMockPosition({
        unrealized_pnl: -75,
      });

      renderWithStore(<PositionsTable />, {
        tradingState: { positions: [lossPosition] },
      });

      const pnlElement = screen.getByText('-$75.00');
      expect(pnlElement).toHaveClass('text-red-400');
    });

    it('should use appropriate colors for long and short positions', () => {
      renderWithStore(<PositionsTable />, {
        tradingState: { positions: mockPositions },
      });

      const longElement = screen.getByText('LONG');
      const shortElement = screen.getByText('SHORT');

      expect(longElement).toHaveClass('text-green-400');
      expect(shortElement).toHaveClass('text-red-400');
    });
  });
});
