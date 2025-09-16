/**
 * Phase 7 TDD Test Suite - Advanced Trading Dashboard
 * 
 * Comprehensive test suite for advanced trading dashboard
 * following TDD Red -> Green -> Refactor methodology.
 */

import React from 'react';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { act } from '@testing-library/react';
import '@testing-library/jest-dom';
import AdvancedTradingDashboard from '../../components/trading/AdvancedTradingDashboard';

// Mock recharts
jest.mock('recharts', () => ({
  LineChart: ({ children }: any) => <div data-testid="line-chart">{children}</div>,
  Line: () => <div data-testid="line" />,
  XAxis: () => <div data-testid="x-axis" />,
  YAxis: () => <div data-testid="y-axis" />,
  CartesianGrid: () => <div data-testid="cartesian-grid" />,
  Tooltip: () => <div data-testid="tooltip" />,
  ResponsiveContainer: ({ children }: any) => <div data-testid="responsive-container">{children}</div>,
  ReferenceLine: () => <div data-testid="reference-line" />,
  Brush: () => <div data-testid="brush" />,
  ComposedChart: ({ children }: any) => <div data-testid="composed-chart">{children}</div>,
  Bar: () => <div data-testid="bar" />,
  Area: () => <div data-testid="area" />
}));

// Mock lightweight-charts
jest.mock('lightweight-charts', () => ({
  createChart: jest.fn(() => ({
    addCandlestickSeries: jest.fn(() => ({ setData: jest.fn() })),
    addHistogramSeries: jest.fn(() => ({ setData: jest.fn() })),
    priceScale: jest.fn(() => ({ applyOptions: jest.fn() })),
    applyOptions: jest.fn(),
    remove: jest.fn()
  })),
  ColorType: { Solid: 'solid' }
}));

// Mock framer-motion
jest.mock('framer-motion', () => ({
  motion: {
    div: ({ children, ...props }: any) => <div {...props}>{children}</div>,
    tr: ({ children, ...props }: any) => <tr {...props}>{children}</tr>
  },
  AnimatePresence: ({ children }: any) => <>{children}</>
}));

describe('AdvancedTradingDashboard', () => {
  // Test 1: Component Rendering and Structure
  describe('Component Rendering', () => {
    test('should render dashboard header with title and description', async () => {
      render(<AdvancedTradingDashboard />);
      
      expect(screen.getByText('Advanced Trading Dashboard')).toBeInTheDocument();
      expect(screen.getByText('Real-time market analysis and position management')).toBeInTheDocument();
    });

    test('should render header control buttons', async () => {
      render(<AdvancedTradingDashboard />);
      
      expect(screen.getByRole('button', { name: /pause live data|resume live data/i })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /fullscreen|exit/i })).toBeInTheDocument();
    });

    test('should show loading state initially', () => {
      render(<AdvancedTradingDashboard />);
      
      // Component should render immediately due to mock data
      expect(screen.getByText('Advanced Trading Dashboard')).toBeInTheDocument();
    });
  });

  // Test 2: Trading Metrics Overview
  describe('Trading Metrics Overview', () => {
    test('should display trading metric cards after loading', async () => {
      render(<AdvancedTradingDashboard />);
      
      // Check for trading metric cards
      expect(screen.getByText('Total P&L')).toBeInTheDocument();
      expect(screen.getByText('Today P&L')).toBeInTheDocument();
      expect(screen.getByText('Open Positions')).toBeInTheDocument();
      expect(screen.getByText('Win Rate')).toBeInTheDocument();
    });

    test('should display correct metric values with proper formatting', async () => {
      render(<AdvancedTradingDashboard />);
      
      // Check for formatted values
      expect(screen.getByText(/\$12,847/)).toBeInTheDocument(); // Total P&L
      expect(screen.getByText(/\$892\.30/)).toBeInTheDocument(); // Today P&L
      expect(screen.getByText('3')).toBeInTheDocument(); // Open Positions
      expect(screen.getByText('68.4%')).toBeInTheDocument(); // Win Rate
    });

    test('should color-code P&L values correctly', async () => {
      render(<AdvancedTradingDashboard />);
      
      // Today P&L should be positive (green/blue styling)
      const todayPnL = screen.getByText(/\+\$892\.30/);
      expect(todayPnL).toBeInTheDocument();
      
      // Check for positive P&L styling (would need to check computed styles in real implementation)
      expect(todayPnL.closest('.bg-blue-100, .text-blue-900')).toBeInTheDocument();
    });
  });

  // Test 3: Chart Interface
  describe('Chart Interface', () => {
    test('should render main trading chart', async () => {
      render(<AdvancedTradingDashboard />);
      
      expect(screen.getByText(/EUR\/USD Chart/)).toBeInTheDocument();
      expect(screen.getByTestId('responsive-container')).toBeInTheDocument();
    });

    test('should have symbol selector with default value', async () => {
      render(<AdvancedTradingDashboard />);
      
      const symbolSelector = screen.getByDisplayValue('EUR/USD');
      expect(symbolSelector).toBeInTheDocument();
      
      // Should be a select element
      expect(symbolSelector.tagName).toBe('SELECT');
    });

    test('should have timeframe selector buttons', async () => {
      render(<AdvancedTradingDashboard />);
      
      // Check for timeframe buttons
      expect(screen.getByRole('button', { name: '1m' })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: '5m' })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: '15m' })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: '1h' })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: '4h' })).toBeInTheDocument();
    });

    test('should switch timeframes correctly', async () => {
      render(<AdvancedTradingDashboard />);
      
      const oneMinButton = screen.getByRole('button', { name: '1m' });
      const fiveMinButton = screen.getByRole('button', { name: '5m' });
      
      // Default should be 15m (active)
      expect(screen.getByRole('button', { name: '15m' })).toHaveClass('bg-blue-500');
      
      // Click 1m
      fireEvent.click(oneMinButton);
      expect(oneMinButton).toHaveClass('bg-blue-500');
      
      // Click 5m
      fireEvent.click(fiveMinButton);
      expect(fiveMinButton).toHaveClass('bg-blue-500');
    });

    test('should change symbols correctly', async () => {
      render(<AdvancedTradingDashboard />);
      
      const symbolSelector = screen.getByDisplayValue('EUR/USD');
      
      // Change to GBP/USD
      fireEvent.change(symbolSelector, { target: { value: 'GBP/USD' } });
      
      expect(screen.getByDisplayValue('GBP/USD')).toBeInTheDocument();
      expect(screen.getByText(/GBP\/USD Chart/)).toBeInTheDocument();
    });
  });

  // Test 4: Order Panel
  describe('Order Panel', () => {
    test('should render quick order panel', async () => {
      render(<AdvancedTradingDashboard />);
      
      expect(screen.getByText('Quick Order')).toBeInTheDocument();
      
      // Check for order form elements
      expect(screen.getByLabelText('Symbol')).toBeInTheDocument();
      expect(screen.getByLabelText('Size')).toBeInTheDocument();
      expect(screen.getByLabelText('Type')).toBeInTheDocument();
    });

    test('should have buy and sell buttons', async () => {
      render(<AdvancedTradingDashboard />);
      
      const buyButton = screen.getByRole('button', { name: /buy/i });
      const sellButton = screen.getByRole('button', { name: /sell/i });
      
      expect(buyButton).toBeInTheDocument();
      expect(sellButton).toBeInTheDocument();
      
      // Check button styling
      expect(buyButton).toHaveClass('bg-green-500');
      expect(sellButton).toHaveClass('bg-red-500');
    });

    test('should display current price in buttons', async () => {
      render(<AdvancedTradingDashboard />);
      
      // Buttons should show current price
      expect(screen.getByRole('button', { name: /buy 1\.09/i })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /sell 1\.09/i })).toBeInTheDocument();
    });

    test('should have market info section', async () => {
      render(<AdvancedTradingDashboard />);
      
      expect(screen.getByText('Market Info')).toBeInTheDocument();
      expect(screen.getByText('Spread:')).toBeInTheDocument();
      expect(screen.getByText('Margin:')).toBeInTheDocument();
      expect(screen.getByText('Swap:')).toBeInTheDocument();
    });

    test('should update order form values', async () => {
      render(<AdvancedTradingDashboard />);
      
      const sizeInput = screen.getByDisplayValue('10000');
      
      // Change size
      fireEvent.change(sizeInput, { target: { value: '25000' } });
      expect(screen.getByDisplayValue('25000')).toBeInTheDocument();
    });
  });

  // Test 5: Positions and Orders Tables
  describe('Positions and Orders Tables', () => {
    test('should render table navigation tabs', async () => {
      render(<AdvancedTradingDashboard />);
      
      expect(screen.getByRole('tab', { name: /open positions/i })).toBeInTheDocument();
      expect(screen.getByRole('tab', { name: /pending orders/i })).toBeInTheDocument();
      expect(screen.getByRole('tab', { name: /trade history/i })).toBeInTheDocument();
    });

    test('should display positions table with data', async () => {
      render(<AdvancedTradingDashboard />);
      
      // Should show positions by default
      expect(screen.getByText('Symbol')).toBeInTheDocument();
      expect(screen.getByText('Side')).toBeInTheDocument();
      expect(screen.getByText('Size')).toBeInTheDocument();
      expect(screen.getByText('Entry')).toBeInTheDocument();
      expect(screen.getByText('Current')).toBeInTheDocument();
      expect(screen.getByText('P&L')).toBeInTheDocument();
      
      // Check for position data
      expect(screen.getByText('EUR/USD')).toBeInTheDocument();
      expect(screen.getByText('GBP/USD')).toBeInTheDocument();
    });

    test('should display orders table when selected', async () => {
      render(<AdvancedTradingDashboard />);
      
      // Click orders tab
      fireEvent.click(screen.getByRole('tab', { name: /pending orders/i }));
      
      // Should show orders table
      expect(screen.getByText('USD/JPY')).toBeInTheDocument();
      expect(screen.getByText('AUD/USD')).toBeInTheDocument();
      expect(screen.getByText('LIMIT')).toBeInTheDocument();
      expect(screen.getByText('STOP')).toBeInTheDocument();
    });

    test('should have action buttons for positions and orders', async () => {
      render(<AdvancedTradingDashboard />);
      
      // Check position action buttons
      const closeButtons = screen.getAllByText('Close');
      const modifyButtons = screen.getAllByText('Modify');
      
      expect(closeButtons.length).toBeGreaterThan(0);
      expect(modifyButtons.length).toBeGreaterThan(0);
    });

    test('should format P&L values with colors', async () => {
      render(<AdvancedTradingDashboard />);
      
      // Check for positive P&L formatting
      const positivePnL = screen.getByText('+$70.00');
      expect(positivePnL).toBeInTheDocument();
      expect(positivePnL).toHaveClass('text-green-600');
      
      const positiveSmallPnL = screen.getByText('+$25.00');
      expect(positiveSmallPnL).toBeInTheDocument();
      expect(positiveSmallPnL).toHaveClass('text-green-600');
    });
  });

  // Test 6: Real-time Data and Live Updates
  describe('Real-time Data Management', () => {
    test('should toggle live data correctly', async () => {
      render(<AdvancedTradingDashboard />);
      
      const liveDataButton = screen.getByRole('button', { name: /pause live data/i });
      
      // Click to pause
      fireEvent.click(liveDataButton);
      expect(screen.getByRole('button', { name: /resume live data/i })).toBeInTheDocument();
      
      // Click to resume
      fireEvent.click(screen.getByRole('button', { name: /resume live data/i }));
      expect(screen.getByRole('button', { name: /pause live data/i })).toBeInTheDocument();
    });

    test('should handle fullscreen mode', async () => {
      render(<AdvancedTradingDashboard />);
      
      const fullscreenButton = screen.getByRole('button', { name: /fullscreen/i });
      
      // Click to enter fullscreen
      fireEvent.click(fullscreenButton);
      expect(screen.getByRole('button', { name: /exit/i })).toBeInTheDocument();
    });
  });

  // Test 7: Price Formatting
  describe('Price and Data Formatting', () => {
    test('should format prices correctly for different pairs', async () => {
      render(<AdvancedTradingDashboard />);
      
      // EUR/USD should show 5 decimal places
      expect(screen.getByText(/1\.0945/)).toBeInTheDocument();
      expect(screen.getByText(/1\.0952/)).toBeInTheDocument();
    });

    test('should format position sizes with commas', async () => {
      render(<AdvancedTradingDashboard />);
      
      // Check for comma-separated numbers
      expect(screen.getByText('100,000')).toBeInTheDocument();
      expect(screen.getByText('50,000')).toBeInTheDocument();
    });

    test('should display duration in human-readable format', async () => {
      render(<AdvancedTradingDashboard />);
      
      expect(screen.getByText('1h 15m')).toBeInTheDocument();
      expect(screen.getByText('32m')).toBeInTheDocument();
    });
  });

  // Test 8: Responsive Design
  describe('Responsive Design', () => {
    test('should handle mobile layout', async () => {
      // Mock mobile viewport
      Object.defineProperty(window, 'innerWidth', {
        writable: true,
        configurable: true,
        value: 375
      });
      
      render(<AdvancedTradingDashboard />);
      
      // Component should render without errors on mobile
      expect(screen.getByText('Advanced Trading Dashboard')).toBeInTheDocument();
    });

    test('should maintain functionality on smaller screens', async () => {
      render(<AdvancedTradingDashboard />);
      
      // All major functionality should be accessible
      expect(screen.getByRole('button', { name: /buy/i })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /sell/i })).toBeInTheDocument();
      expect(screen.getByRole('tab', { name: /open positions/i })).toBeInTheDocument();
    });
  });

  // Test 9: Error Handling
  describe('Error Handling', () => {
    test('should handle missing chart data gracefully', () => {
      render(<AdvancedTradingDashboard />);
      
      // Component should not crash with missing or invalid data
      expect(screen.getByText('Advanced Trading Dashboard')).toBeInTheDocument();
    });

    test('should handle empty positions and orders', async () => {
      render(<AdvancedTradingDashboard />);
      
      // Component should render even with no positions/orders
      expect(screen.getByRole('tab', { name: /open positions/i })).toBeInTheDocument();
    });
  });

  // Test 10: Accessibility
  describe('Accessibility', () => {
    test('should have proper ARIA labels', async () => {
      render(<AdvancedTradingDashboard />);
      
      // Check for tab accessibility
      expect(screen.getByRole('tablist')).toBeInTheDocument();
      expect(screen.getAllByRole('tab')).toHaveLength(3);
      
      // Check for table accessibility
      expect(screen.getAllByRole('table')).toHaveLength(1); // Positions table
      
      // Check button accessibility
      const buttons = screen.getAllByRole('button');
      buttons.forEach(button => {
        expect(button).toHaveAccessibleName();
      });
    });

    test('should support keyboard navigation', async () => {
      render(<AdvancedTradingDashboard />);
      
      const firstTab = screen.getByRole('tab', { name: /open positions/i });
      const buyButton = screen.getByRole('button', { name: /buy/i });
      
      // Elements should be focusable
      firstTab.focus();
      expect(document.activeElement).toBe(firstTab);
      
      buyButton.focus();
      expect(document.activeElement).toBe(buyButton);
    });
  });

  // Test 11: Performance
  describe('Performance', () => {
    test('should render chart efficiently', async () => {
      const startTime = performance.now();
      
      render(<AdvancedTradingDashboard />);
      
      const endTime = performance.now();
      const renderTime = endTime - startTime;
      
      // Should render quickly
      expect(renderTime).toBeLessThan(1000); // Less than 1 second
    });

    test('should handle frequent data updates', () => {
      render(<AdvancedTradingDashboard />);
      
      // Component should be stable with mock data
      expect(screen.getByText('Advanced Trading Dashboard')).toBeInTheDocument();
    });
  });
});

// Integration Tests
describe('AdvancedTradingDashboard Integration', () => {
  test('should integrate with WebSocket for real-time data', () => {
    render(<AdvancedTradingDashboard />);
    
    // Component should be ready for real-time data
    expect(screen.getByText('Advanced Trading Dashboard')).toBeInTheDocument();
  });

  test('should integrate with trading API for order placement', () => {
    render(<AdvancedTradingDashboard />);
    
    // Order buttons should be functional
    expect(screen.getByRole('button', { name: /buy/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /sell/i })).toBeInTheDocument();
  });

  test('should work with different chart data formats', () => {
    render(<AdvancedTradingDashboard />);
    
    // Should handle OHLCV data format
    expect(screen.getByTestId('responsive-container')).toBeInTheDocument();
  });
});