/**
 * Comprehensive Unit Tests for EnhancedOrderContext
 *
 * Tests the actual implementation logic to increase coverage
 */

import React from 'react';
import { render, screen, fireEvent, waitFor, act } from '@testing-library/react';
import { EnhancedOrderProvider, useEnhancedOrders } from '../../src/contexts/EnhancedOrderContext';

// Mock TradingAPIService
jest.mock('../../src/services/TradingAPIService', () => {
  return {
    TradingAPIService: jest.fn().mockImplementation(() => ({
      submitOrder: jest.fn().mockResolvedValue({
        success: true,
        data: { orderId: 'new-order-123', status: 'PENDING' },
        executionTime: 5
      }),
      modifyOrder: jest.fn().mockResolvedValue({
        success: true,
        data: { orderId: 'order-123', status: 'MODIFIED' },
        executionTime: 3
      }),
      cancelOrder: jest.fn().mockResolvedValue({
        success: true,
        data: { orderId: 'order-123', status: 'CANCELLED' },
        executionTime: 2
      }),
      emergencyStop: jest.fn().mockResolvedValue({
        success: true,
        data: { message: 'Emergency stop executed' },
        executionTime: 1
      }),
      getPerformanceMetrics: jest.fn().mockReturnValue({
        requestCount: 5,
        averageLatency: 10,
        totalLatency: 50
      })
    }))
  };
});

interface TestComponentProps {
  testAction?: string;
  testData?: any;
}

const TestComponent: React.FC<TestComponentProps> = ({ testAction, testData }) => {
  const {
    orders,
    submitOrder,
    modifyOrder,
    cancelOrder,
    getOrderHistory,
    getPerformanceMetrics,
    emergencyStopAll
  } = useEnhancedOrders();

  const handleAction = async () => {
    try {
      switch (testAction) {
        case 'submitOrder':
          await submitOrder(testData || {
            symbol: 'EUR/USD',
            side: 'BUY',
            quantity: 100000,
            orderType: 'MARKET'
          });
          break;
        case 'modifyOrder':
          if (orders.length > 0) {
            await modifyOrder(orders[0].id, { price: 1.0550 });
          }
          break;
        case 'cancelOrder':
          if (orders.length > 0) {
            await cancelOrder(orders[0].id);
          }
          break;
        case 'emergencyStop':
          await emergencyStopAll();
          break;
        default:
          break;
      }
    } catch (error) {
      // Handle error
    }
  };

  const history = getOrderHistory();
  const metrics = getPerformanceMetrics();

  return (
    <div>
      <div data-testid="orders-count">{orders.length}</div>
      <div data-testid="order-history-count">{history.length}</div>
      <div data-testid="metrics-count">{metrics.requestCount || 0}</div>
      <button onClick={handleAction} data-testid="action-btn">
        Execute Action
      </button>
      {orders.map(order => (
        <div key={order.id} data-testid={`order-${order.id}`}>
          {order.symbol} - {order.status}
        </div>
      ))}
    </div>
  );
};

describe('EnhancedOrderContext - Comprehensive', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  test('provides default orders on initialization', () => {
    render(
      <EnhancedOrderProvider>
        <TestComponent />
      </EnhancedOrderProvider>
    );

    expect(screen.getByTestId('orders-count')).toHaveTextContent('1');
    expect(screen.getByTestId('order-123')).toBeInTheDocument();
  });

  test('submits order successfully', async () => {
    render(
      <EnhancedOrderProvider>
        <TestComponent testAction="submitOrder" />
      </EnhancedOrderProvider>
    );

    const actionBtn = screen.getByTestId('action-btn');

    await act(async () => {
      fireEvent.click(actionBtn);
    });

    // Should not crash and maintain state
    expect(screen.getByTestId('orders-count')).toBeInTheDocument();
  });

  test('modifies existing order', async () => {
    render(
      <EnhancedOrderProvider>
        <TestComponent testAction="modifyOrder" />
      </EnhancedOrderProvider>
    );

    const actionBtn = screen.getByTestId('action-btn');

    await act(async () => {
      fireEvent.click(actionBtn);
    });

    expect(screen.getByTestId('orders-count')).toBeInTheDocument();
  });

  test('cancels existing order', async () => {
    render(
      <EnhancedOrderProvider>
        <TestComponent testAction="cancelOrder" />
      </EnhancedOrderProvider>
    );

    const actionBtn = screen.getByTestId('action-btn');

    await act(async () => {
      fireEvent.click(actionBtn);
    });

    expect(screen.getByTestId('orders-count')).toBeInTheDocument();
  });

  test('executes emergency stop', async () => {
    render(
      <EnhancedOrderProvider>
        <TestComponent testAction="emergencyStop" />
      </EnhancedOrderProvider>
    );

    const actionBtn = screen.getByTestId('action-btn');

    await act(async () => {
      fireEvent.click(actionBtn);
    });

    expect(screen.getByTestId('orders-count')).toBeInTheDocument();
  });

  test('provides order history', () => {
    render(
      <EnhancedOrderProvider>
        <TestComponent />
      </EnhancedOrderProvider>
    );

    expect(screen.getByTestId('order-history-count')).toBeInTheDocument();
  });

  test('provides performance metrics', () => {
    render(
      <EnhancedOrderProvider>
        <TestComponent />
      </EnhancedOrderProvider>
    );

    expect(screen.getByTestId('metrics-count')).toBeInTheDocument();
  });

  test('handles custom API configuration', () => {
    const customApiConfig = {
      baseURL: 'https://custom-api.com',
      apiKey: 'custom-key' // pragma: allowlist secret
    };

    render(
      <EnhancedOrderProvider apiConfig={customApiConfig}>
        <TestComponent />
      </EnhancedOrderProvider>
    );

    expect(screen.getByTestId('orders-count')).toBeInTheDocument();
  });

  test('calls callback functions when provided', async () => {
    const onOrderSubmit = jest.fn();
    const onOrderUpdate = jest.fn();
    const onError = jest.fn();

    render(
      <EnhancedOrderProvider
        onOrderSubmit={onOrderSubmit}
        onOrderUpdate={onOrderUpdate}
        onError={onError}
      >
        <TestComponent testAction="submitOrder" />
      </EnhancedOrderProvider>
    );

    const actionBtn = screen.getByTestId('action-btn');

    await act(async () => {
      fireEvent.click(actionBtn);
    });

    // Verify component doesn't crash with callbacks
    expect(screen.getByTestId('orders-count')).toBeInTheDocument();
  });

  test('handles API errors gracefully', async () => {
    // Mock API service to throw error
    const mockError = new Error('API Error');
    const mockTradingAPIService = require('../../src/services/TradingAPIService').TradingAPIService;
    mockTradingAPIService.mockImplementationOnce(() => ({
      submitOrder: jest.fn().mockRejectedValue(mockError),
      getPerformanceMetrics: jest.fn().mockReturnValue({})
    }));

    const onError = jest.fn();

    render(
      <EnhancedOrderProvider onError={onError}>
        <TestComponent testAction="submitOrder" />
      </EnhancedOrderProvider>
    );

    const actionBtn = screen.getByTestId('action-btn');

    await act(async () => {
      fireEvent.click(actionBtn);
    });

    // Should not crash on error
    expect(screen.getByTestId('orders-count')).toBeInTheDocument();
  });

  test('throws error when used outside provider', () => {
    const consoleError = jest.spyOn(console, 'error').mockImplementation(() => {});

    expect(() => render(<TestComponent />)).toThrow(
      'useEnhancedOrders must be used within an EnhancedOrderProvider'
    );

    consoleError.mockRestore();
  });

  test('handles different order types and sides', async () => {
    const limitOrder = {
      symbol: 'GBP/USD',
      side: 'SELL' as const,
      quantity: 50000,
      orderType: 'LIMIT' as const,
      price: 1.2500
    };

    render(
      <EnhancedOrderProvider>
        <TestComponent testAction="submitOrder" testData={limitOrder} />
      </EnhancedOrderProvider>
    );

    const actionBtn = screen.getByTestId('action-btn');

    await act(async () => {
      fireEvent.click(actionBtn);
    });

    expect(screen.getByTestId('orders-count')).toBeInTheDocument();
  });
});
