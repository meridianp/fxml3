"""
Trading Dashboard Component Test Suite
======================================

Example test suite demonstrating how to use the component test foundation
for testing complex trading dashboard components.
"""

import React from 'react';
import { rest } from 'msw';
import { ComponentTestBuilder, testUtils, generateMockData } from '../foundation/component-test-foundation';
import TradingDashboard from '@/components/TradingDashboard';

describe('TradingDashboard Component', () => {
  let testBuilder: ComponentTestBuilder<any>;

  beforeEach(() => {
    testBuilder = new ComponentTestBuilder(TradingDashboard);
  });

  describe('Rendering', () => {
    it('should render dashboard with all sections', async () => {
      const { getByTestId, getByText } = await testBuilder
        .withProps({ symbol: 'EUR/USD' })
        .render();

      expect(getByTestId('trading-dashboard')).toBeInTheDocument();
      expect(getByText('Market Overview')).toBeInTheDocument();
      expect(getByText('Order Entry')).toBeInTheDocument();
      expect(getByText('Positions')).toBeInTheDocument();
      expect(getByText('Order History')).toBeInTheDocument();
    });

    it('should display loading state initially', async () => {
      const { getByTestId } = await testBuilder.render();

      expect(getByTestId('loading-spinner')).toBeInTheDocument();

      await testBuilder.waitForLoading();
    });

    it('should handle error states gracefully', async () => {
      const { getByText } = await testBuilder
        .withApiMock(
          rest.get('/api/market-data/:symbol', (req, res, ctx) => {
            return res(ctx.status(500), ctx.json({ error: 'Server error' }));
          })
        )
        .render();

      await testBuilder.waitForText('Failed to load market data');
    });
  });

  describe('Market Data Updates', () => {
    it('should update prices via WebSocket', async () => {
      const ws = testUtils.mockWebSocket();

      const { getByTestId } = await testBuilder
        .withProps({ symbol: 'EUR/USD' })
        .render();

      await testBuilder.waitForLoading();

      // Send price update via WebSocket
      testUtils.sendWebSocketMessage({
        type: 'price_update',
        data: {
          symbol: 'EUR/USD',
          bid: 1.0855,
          ask: 1.0857,
        },
      });

      await testUtils.waitFor(() => {
        expect(getByTestId('bid-price')).toHaveTextContent('1.0855');
        expect(getByTestId('ask-price')).toHaveTextContent('1.0857');
      });
    });

    it('should handle WebSocket reconnection', async () => {
      const wsTest = testUtils.createWebSocketTest();
      const ws = wsTest.setup();

      await testBuilder.render();

      // Simulate disconnection
      wsTest.simulateClose();

      await testBuilder.waitForText('Reconnecting...');

      // Simulate reconnection
      await wsTest.expectConnection();

      await testBuilder.waitForText('Connected');

      wsTest.cleanup();
    });
  });

  describe('Order Placement', () => {
    it('should place market order successfully', async () => {
      await testBuilder
        .withApiMock(
          rest.post('/api/orders', (req, res, ctx) => {
            return res(ctx.json({
              orderId: 'ORD789',
              status: 'filled',
              fillPrice: 1.0851,
            }));
          })
        )
        .render();

      await testBuilder.waitForLoading();

      // Fill order form
      await testBuilder.typeInInput('Quantity', '100000');
      await testBuilder.selectOption('Order Type', 'market');
      await testBuilder.clickButton('Buy');

      // Verify success message
      await testBuilder.waitForText('Order filled at 1.0851');
    });

    it('should validate order parameters', async () => {
      await testBuilder.render();
      await testBuilder.waitForLoading();

      // Try to submit empty form
      await testBuilder.clickButton('Buy');

      // Check validation errors
      testBuilder.expectText('Quantity is required');
    });

    it('should disable trading for unauthorized users', async () => {
      const { getByRole } = await testBuilder
        .withConfig({
          user: {
            role: 'analyst',
            permissions: ['read'],
          },
        })
        .render();

      await testBuilder.waitForLoading();

      const buyButton = getByRole('button', { name: 'Buy' });
      expect(buyButton).toBeDisabled();
    });
  });

  describe('Position Management', () => {
    it('should display open positions', async () => {
      const mockPositions = [
        generateMockData.position({ symbol: 'EUR/USD', quantity: 100000 }),
        generateMockData.position({ symbol: 'GBP/USD', quantity: -50000 }),
      ];

      await testBuilder
        .withApiMock(
          rest.get('/api/positions', (req, res, ctx) => {
            return res(ctx.json(mockPositions));
          })
        )
        .render();

      await testBuilder.waitForLoading();

      testBuilder.expectText('EUR/USD');
      testBuilder.expectText('100,000');
      testBuilder.expectText('GBP/USD');
      testBuilder.expectText('-50,000');
    });

    it('should close position on button click', async () => {
      const mockPosition = generateMockData.position();

      const { getByTestId } = await testBuilder
        .withApiMock(
          rest.get('/api/positions', (req, res, ctx) => {
            return res(ctx.json([mockPosition]));
          })
        )
        .withApiMock(
          rest.delete('/api/positions/:symbol', (req, res, ctx) => {
            return res(ctx.json({ success: true }));
          })
        )
        .render();

      await testBuilder.waitForLoading();

      const closeButton = getByTestId('close-position-EUR/USD');
      await testUtils.user.click(closeButton);

      // Confirm dialog
      await testBuilder.clickButton('Confirm');

      await testBuilder.waitForText('Position closed successfully');
    });
  });

  describe('Performance', () => {
    it('should render within performance budget', async () => {
      const renderTime = await testUtils.measureRenderTime(
        <TradingDashboard symbol="EUR/USD" />
      );

      expect(renderTime).toBeLessThan(100); // 100ms budget
    });

    it('should handle rapid updates efficiently', async () => {
      const ws = testUtils.mockWebSocket();
      await testBuilder.render();

      // Send 100 rapid updates
      for (let i = 0; i < 100; i++) {
        testUtils.sendWebSocketMessage({
          type: 'price_update',
          data: {
            symbol: 'EUR/USD',
            bid: 1.0850 + i * 0.0001,
            ask: 1.0852 + i * 0.0001,
          },
        });
      }

      // Should batch updates and not crash
      await testUtils.advanceTimersByTime(100);

      const { getByTestId } = testBuilder.getResult();
      expect(getByTestId('update-count')).toHaveTextContent('100');
    });
  });

  describe('Accessibility', () => {
    it('should meet WCAG accessibility standards', async () => {
      const { container } = await testBuilder.render();

      await testUtils.testAccessibility(container);
    });

    it('should support keyboard navigation', async () => {
      await testBuilder.render();
      await testBuilder.waitForLoading();

      // Tab through interactive elements
      await testUtils.user.tab();
      expect(document.activeElement).toHaveAttribute('data-testid', 'symbol-selector');

      await testUtils.user.tab();
      expect(document.activeElement).toHaveAttribute('data-testid', 'quantity-input');

      await testUtils.user.tab();
      expect(document.activeElement).toHaveAttribute('data-testid', 'buy-button');
    });
  });

  describe('Integration', () => {
    it('should integrate with Redux state management', async () => {
      const store = testUtils.createMockStore({
        trading: {
          selectedSymbol: 'GBP/USD',
          positions: [],
        },
      });

      const { getByTestId } = await testBuilder
        .withProps({ store })
        .render();

      // Verify Redux state is used
      expect(getByTestId('selected-symbol')).toHaveTextContent('GBP/USD');

      // Dispatch action
      await testUtils.dispatchAndWait(store, {
        type: 'trading/selectSymbol',
        payload: 'USD/JPY',
      });

      expect(getByTestId('selected-symbol')).toHaveTextContent('USD/JPY');
    });

    it('should work with React Query for data fetching', async () => {
      const { queryClient, wrapper } = testUtils.createQueryWrapper();

      // Prime the cache
      queryClient.setQueryData(['market-data', 'EUR/USD'], {
        symbol: 'EUR/USD',
        bid: 1.0850,
        ask: 1.0852,
      });

      const { getByTestId } = await testBuilder
        .withProps({ wrapper })
        .render();

      // Data should be available immediately from cache
      expect(getByTestId('bid-price')).toHaveTextContent('1.0850');
    });
  });

  describe('Snapshot Testing', () => {
    it('should match visual snapshot', async () => {
      await testBuilder
        .withProps({ symbol: 'EUR/USD' })
        .render();

      await testBuilder.waitForLoading();

      testBuilder.takeSnapshot('trading-dashboard-loaded');
    });
  });
});
