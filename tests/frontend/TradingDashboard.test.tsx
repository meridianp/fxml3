/**
 * Unit tests for Trading Dashboard Component.
 *
 * Tests comprehensive trading dashboard functionality including:
 * - Real-time market data display
 * - Order placement and management
 * - Position monitoring
 * - P&L tracking
 * - Chart visualization
 * - Risk metrics display
 */

import React from 'react';
import { render, screen, fireEvent, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import '@testing-library/jest-dom';
import { TradingDashboard } from '../../src/components/TradingDashboard';
import { MarketDataProvider } from '../../src/contexts/MarketDataContext';
import { OrderProvider } from '../../src/contexts/OrderContext';
import { mockMarketData, mockPositions } from '../mocks/tradingMocks';

describe('TradingDashboard', () => {
  const mockProps = {
    userId: 'user123',
    accountId: 'acc456',
    symbols: ['EUR/USD', 'GBP/USD', 'USD/JPY'],
  };

  beforeEach(() => {
    jest.clearAllMocks();
  });

  test('renders trading dashboard with all major components', () => {
    render(
      <MarketDataProvider>
        <OrderProvider>
          <TradingDashboard {...mockProps} />
        </OrderProvider>
      </MarketDataProvider>
    );

    expect(screen.getByTestId('trading-dashboard')).toBeInTheDocument();
    expect(screen.getByTestId('market-watchlist')).toBeInTheDocument();
    expect(screen.getByTestId('order-panel')).toBeInTheDocument();
    expect(screen.getByTestId('positions-table')).toBeInTheDocument();
    expect(screen.getByTestId('chart-container')).toBeInTheDocument();
  });

  test('displays real-time market data updates', async () => {
    render(
      <MarketDataProvider initialData={mockMarketData}>
        <OrderProvider>
          <TradingDashboard {...mockProps} />
        </OrderProvider>
      </MarketDataProvider>
    );

    const watchlist = screen.getByTestId('market-watchlist');

    expect(within(watchlist).getByText('EUR/USD')).toBeInTheDocument();

    // Should show initial data price
    await waitFor(() => {
      expect(within(watchlist).getByText('1.05')).toBeInTheDocument();
    });

    // Wait for real-time update (price gets incremented by 0.0001)
    await waitFor(() => {
      expect(within(watchlist).getByText('1.0501')).toBeInTheDocument();
    }, { timeout: 2000 });
  });

  test('allows placing market orders', async () => {
    const user = userEvent.setup();
    const onOrderSubmit = jest.fn();

    render(
      <MarketDataProvider>
        <OrderProvider onOrderSubmit={onOrderSubmit}>
          <TradingDashboard {...mockProps} />
        </OrderProvider>
      </MarketDataProvider>
    );

    const orderPanel = screen.getByTestId('order-panel');

    // EUR/USD should already be selected by default (first symbol)
    // Just verify it's there and proceed to quantity
    expect(within(orderPanel).getByDisplayValue('EUR/USD')).toBeInTheDocument();

    // Enter quantity
    await user.type(
      within(orderPanel).getByLabelText('Quantity'),
      '100000'
    );

    // Click buy button
    await user.click(within(orderPanel).getByText('BUY'));

    expect(onOrderSubmit).toHaveBeenCalledWith({
      symbol: 'EUR/USD',
      side: 'BUY',
      quantity: 100000,
      orderType: 'MARKET',
    });
  });

  test('displays and updates positions table', async () => {
    render(
      <MarketDataProvider>
        <OrderProvider>
          <TradingDashboard {...mockProps} positions={mockPositions} />
        </OrderProvider>
      </MarketDataProvider>
    );

    const positionsTable = screen.getByTestId('positions-table');

    expect(within(positionsTable).getByText('EUR/USD')).toBeInTheDocument();
    expect(within(positionsTable).getByText('100,000')).toBeInTheDocument();
    expect(within(positionsTable).getByText('+$500.00')).toBeInTheDocument();
  });

  test('calculates and displays P&L correctly', () => {
    const positions = [
      {
        symbol: 'EUR/USD',
        quantity: 100000,
        entryPrice: 1.0500,
        currentPrice: 1.0550,
        unrealizedPnL: 500,
      },
      {
        symbol: 'GBP/USD',
        quantity: -50000,
        entryPrice: 1.2500,
        currentPrice: 1.2480,
        unrealizedPnL: 100,
      },
    ];

    render(
      <MarketDataProvider>
        <OrderProvider>
          <TradingDashboard {...mockProps} positions={positions} />
        </OrderProvider>
      </MarketDataProvider>
    );

    const pnlDisplay = screen.getByTestId('total-pnl');
    expect(pnlDisplay).toHaveTextContent('$600.00');
    expect(pnlDisplay).toHaveClass('profit');
  });

  test('handles order modification', async () => {
    const user = userEvent.setup();
    const onOrderModify = jest.fn();

    render(
      <MarketDataProvider>
        <OrderProvider>
          <TradingDashboard {...mockProps} onOrderModify={onOrderModify} />
        </OrderProvider>
      </MarketDataProvider>
    );

    // Find pending order
    const orderRow = screen.getByTestId('order-row-123');

    // Click modify button
    await user.click(within(orderRow).getByText('Modify'));

    // Update price in modal
    const modal = screen.getByRole('dialog');
    await user.clear(within(modal).getByLabelText('Price'));
    await user.type(within(modal).getByLabelText('Price'), '1.0510');

    // Confirm modification
    await user.click(within(modal).getByText('Update Order'));

    expect(onOrderModify).toHaveBeenCalledWith({
      orderId: '123',
      price: 1.0510,
    });
  });

  test('displays risk metrics panel', () => {
    render(
      <MarketDataProvider>
        <OrderProvider>
          <TradingDashboard {...mockProps} />
        </OrderProvider>
      </MarketDataProvider>
    );

    const riskPanel = screen.getByTestId('risk-metrics');

    expect(within(riskPanel).getByText('Margin Used')).toBeInTheDocument();
    expect(within(riskPanel).getByText('Free Margin')).toBeInTheDocument();
    expect(within(riskPanel).getByText('Margin Level')).toBeInTheDocument();
    expect(within(riskPanel).getByText('Daily P&L')).toBeInTheDocument();
  });

  test('renders interactive price chart', async () => {
    const user = userEvent.setup();

    render(
      <MarketDataProvider>
        <OrderProvider>
          <TradingDashboard {...mockProps} />
        </OrderProvider>
      </MarketDataProvider>
    );

    const chart = screen.getByTestId('price-chart');

    // Check for chart elements
    expect(within(chart).getByTestId('candlestick-chart')).toBeInTheDocument();
    expect(within(chart).getByTestId('volume-bars')).toBeInTheDocument();

    // Change timeframe
    await user.click(within(chart).getByText('1H'));

    await waitFor(() => {
      expect(within(chart).getByTestId('timeframe-1h')).toHaveClass('selected');
    });
  });

  test('shows Elliott Wave indicators on chart', async () => {
    const user = userEvent.setup();

    render(
      <MarketDataProvider>
        <OrderProvider>
          <TradingDashboard {...mockProps} />
        </OrderProvider>
      </MarketDataProvider>
    );

    const chart = screen.getByTestId('price-chart');

    // Toggle Elliott Wave
    await user.click(screen.getByLabelText('Elliott Wave'));

    await waitFor(() => {
      expect(within(chart).getByTestId('elliott-wave-overlay')).toBeInTheDocument();
      expect(within(chart).getByText('Wave 3')).toBeInTheDocument();
    });
  });

  test('handles emergency stop functionality', async () => {
    const user = userEvent.setup();
    const onEmergencyStop = jest.fn();

    render(
      <MarketDataProvider>
        <OrderProvider>
          <TradingDashboard {...mockProps} onEmergencyStop={onEmergencyStop} />
        </OrderProvider>
      </MarketDataProvider>
    );

    // Click emergency stop button
    const emergencyButton = screen.getByTestId('emergency-stop');
    await user.click(emergencyButton);

    // Confirm in modal
    const modal = screen.getByRole('dialog');
    expect(within(modal).getByText('Emergency Stop')).toBeInTheDocument();
    await user.click(within(modal).getByText('CONFIRM SHUTDOWN'));

    expect(onEmergencyStop).toHaveBeenCalled();
  });

  test('displays account summary information', () => {
    const accountData = {
      balance: 100000,
      equity: 102500,
      margin: 10000,
      freeMargin: 92500,
      marginLevel: 1025,
    };

    render(
      <MarketDataProvider>
        <OrderProvider>
          <TradingDashboard {...mockProps} accountData={accountData} />
        </OrderProvider>
      </MarketDataProvider>
    );

    const accountSummary = screen.getByTestId('account-summary');

    expect(within(accountSummary).getByText('Balance:')).toBeInTheDocument();
    expect(within(accountSummary).getByText('$100,000.00')).toBeInTheDocument();
    expect(within(accountSummary).getByText('Equity:')).toBeInTheDocument();
    expect(within(accountSummary).getByText('$102,500.00')).toBeInTheDocument();
  });

  test('filters positions by symbol', async () => {
    const user = userEvent.setup();

    render(
      <MarketDataProvider>
        <OrderProvider>
          <TradingDashboard {...mockProps} positions={mockPositions} />
        </OrderProvider>
      </MarketDataProvider>
    );

    const filterInput = screen.getByPlaceholderText('Filter positions...');
    await user.type(filterInput, 'EUR');

    const positionsTable = screen.getByTestId('positions-table');
    const rows = within(positionsTable).getAllByRole('row');

    // Header + 1 EUR position
    expect(rows).toHaveLength(2);
    expect(within(positionsTable).getByText('EUR/USD')).toBeInTheDocument();
    expect(within(positionsTable).queryByText('GBP/USD')).not.toBeInTheDocument();
  });

  test('exports trading history', async () => {
    const user = userEvent.setup();
    const onExport = jest.fn();

    render(
      <MarketDataProvider>
        <OrderProvider>
          <TradingDashboard {...mockProps} onExportHistory={onExport} />
        </OrderProvider>
      </MarketDataProvider>
    );

    await user.click(screen.getByText('Export History'));

    const modal = screen.getByRole('dialog');

    // CSV should be the default value, just click Export
    await user.click(within(modal).getByText('Export'));

    expect(onExport).toHaveBeenCalledWith({
      format: 'CSV',
      dateRange: expect.any(Object),
    });
  });

  test('displays connection status indicator', () => {
    render(
      <MarketDataProvider connectionStatus="connected">
        <OrderProvider>
          <TradingDashboard {...mockProps} />
        </OrderProvider>
      </MarketDataProvider>
    );

    const statusIndicator = screen.getByTestId('connection-status');
    expect(statusIndicator).toHaveClass('connected');
    expect(statusIndicator).toHaveAttribute('title', 'Connected to market data');
  });

  test('handles keyboard shortcuts', async () => {
    const user = userEvent.setup();
    const onQuickBuy = jest.fn();
    const onQuickSell = jest.fn();

    render(
      <MarketDataProvider>
        <OrderProvider>
          <TradingDashboard
            {...mockProps}
            onQuickBuy={onQuickBuy}
            onQuickSell={onQuickSell}
          />
        </OrderProvider>
      </MarketDataProvider>
    );

    // Press B for quick buy
    await user.keyboard('{b}');
    expect(onQuickBuy).toHaveBeenCalled();

    // Press S for quick sell
    await user.keyboard('{s}');
    expect(onQuickSell).toHaveBeenCalled();
  });

  test('shows ML predictions panel', async () => {
    const predictions = {
      'EUR/USD': { direction: 'up', confidence: 0.85, target: 1.0550 },
      'GBP/USD': { direction: 'down', confidence: 0.72, target: 1.2450 },
    };

    render(
      <MarketDataProvider>
        <OrderProvider>
          <TradingDashboard {...mockProps} mlPredictions={predictions} />
        </OrderProvider>
      </MarketDataProvider>
    );

    const mlPanel = screen.getByTestId('ml-predictions');

    expect(within(mlPanel).getByText('EUR/USD')).toBeInTheDocument();

    // Check for confidence percentage and direction
    await waitFor(() => {
      expect(within(mlPanel).getByText(/85%/)).toBeInTheDocument();
      expect(within(mlPanel).getByText(/↑/)).toBeInTheDocument();
    });
  });

  test('validates order input fields', async () => {
    const user = userEvent.setup();

    render(
      <MarketDataProvider>
        <OrderProvider>
          <TradingDashboard {...mockProps} />
        </OrderProvider>
      </MarketDataProvider>
    );

    const orderPanel = screen.getByTestId('order-panel');
    const submitButton = within(orderPanel).getByText('Submit Order');

    // Try to submit with BUY button (no validation message yet)
    await user.click(within(orderPanel).getByText('BUY'));

    await waitFor(() => {
      expect(within(orderPanel).getByText('Quantity is required')).toBeInTheDocument();
    });

    // Enter invalid quantity
    const quantityInput = within(orderPanel).getByLabelText('Quantity');
    await user.clear(quantityInput);
    await user.type(quantityInput, '-100');

    await user.click(within(orderPanel).getByText('BUY'));

    await waitFor(() => {
      expect(within(orderPanel).getByText('Quantity must be positive')).toBeInTheDocument();
    });
  });

  test('displays news feed panel', async () => {
    const newsItems = [
      { id: 1, title: 'ECB Rate Decision', impact: 'high' },
      { id: 2, title: 'USD Employment Data', impact: 'medium' },
    ];

    render(
      <MarketDataProvider>
        <OrderProvider>
          <TradingDashboard {...mockProps} newsItems={newsItems} />
        </OrderProvider>
      </MarketDataProvider>
    );

    const newsPanel = screen.getByTestId('news-feed');

    expect(within(newsPanel).getByText('ECB Rate Decision')).toBeInTheDocument();
    expect(within(newsPanel).getByTestId('impact-high')).toBeInTheDocument();
  });

  test('handles theme switching', async () => {
    const user = userEvent.setup();

    render(
      <MarketDataProvider>
        <OrderProvider>
          <TradingDashboard {...mockProps} />
        </OrderProvider>
      </MarketDataProvider>
    );

    const themeToggle = screen.getByTestId('theme-toggle');
    const dashboard = screen.getByTestId('trading-dashboard');

    expect(dashboard).toHaveClass('theme-light');

    await user.click(themeToggle);

    expect(dashboard).toHaveClass('theme-dark');
  });
});
