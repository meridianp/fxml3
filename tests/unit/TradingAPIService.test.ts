/**
 * Unit Tests for TradingAPIService
 *
 * Tests API call handling, error management, retry logic,
 * and performance monitoring for trading operations.
 */

import { TradingAPIService, Order } from '../../src/services/TradingAPIService';

// Mock fetch globally
global.fetch = jest.fn();

describe('TradingAPIService', () => {
  let apiService: TradingAPIService;
  const mockBaseURL = 'https://api.fxml4.com/v1';
  const mockAPIKey = 'test_api_key_12345'; // pragma: allowlist secret

  beforeEach(() => {
    apiService = new TradingAPIService(mockBaseURL, mockAPIKey);
    jest.clearAllMocks();
  });

  afterEach(() => {
    jest.resetAllMocks();
  });

  describe('Order Management', () => {
    test('submits market order successfully', async () => {
      const mockResponse = {
        orderId: 'order_123456',
        status: 'PENDING',
        requestId: 'req_789'
      };

      (global.fetch as jest.Mock).mockResolvedValueOnce({
        ok: true,
        json: async () => mockResponse
      });

      const order: Order = {
        symbol: 'EUR/USD',
        side: 'BUY',
        quantity: 100000,
        orderType: 'MARKET'
      };

      const result = await apiService.submitOrder(order);

      expect(result.success).toBe(true);
      expect(result.data?.orderId).toBe('order_123456');
      expect(result.data?.status).toBe('PENDING');
      expect(result.executionTime).toBeGreaterThan(0);

      // Verify API call was made correctly
      expect(global.fetch).toHaveBeenCalledWith(
        `${mockBaseURL}/orders`,
        expect.objectContaining({
          method: 'POST',
          body: JSON.stringify(order),
          headers: expect.objectContaining({
            'Authorization': `Bearer ${mockAPIKey}`,
            'Content-Type': 'application/json',
            'X-Client-Version': '4.0.0',
            'X-Request-ID': expect.any(String)
          })
        })
      );
    });

    test('submits limit order successfully', async () => {
      const mockResponse = {
        orderId: 'order_789123',
        status: 'PENDING',
        requestId: 'req_456'
      };

      (global.fetch as jest.Mock).mockResolvedValueOnce({
        ok: true,
        json: async () => mockResponse
      });

      const order: Order = {
        symbol: 'GBP/USD',
        side: 'SELL',
        quantity: 50000,
        orderType: 'LIMIT',
        price: 1.2500
      };

      const result = await apiService.submitOrder(order);

      expect(result.success).toBe(true);
      expect(result.data?.orderId).toBe('order_789123');
      expect(JSON.parse((global.fetch as jest.Mock).mock.calls[0][1].body)).toEqual(order);
    });

    test('handles order submission failure', async () => {
      (global.fetch as jest.Mock).mockRejectedValueOnce(new Error('Network error'));

      const order: Order = {
        symbol: 'USD/JPY',
        side: 'BUY',
        quantity: 75000,
        orderType: 'MARKET'
      };

      const result = await apiService.submitOrder(order);

      expect(result.success).toBe(false);
      expect(result.error?.code).toBe('ORDER_SUBMIT_ERROR');
      expect(result.error?.message).toBe('Network error');
    });

    test('modifies order successfully', async () => {
      const mockResponse = {
        orderId: 'order_123456',
        status: 'MODIFIED',
        updatedPrice: 1.0520
      };

      (global.fetch as jest.Mock).mockResolvedValueOnce({
        ok: true,
        json: async () => mockResponse
      });

      const result = await apiService.modifyOrder('order_123456', { price: 1.0520 });

      expect(result.success).toBe(true);
      expect(result.executionTime).toBeGreaterThan(0);

      expect(global.fetch).toHaveBeenCalledWith(
        `${mockBaseURL}/orders/order_123456`,
        expect.objectContaining({
          method: 'PATCH',
          body: JSON.stringify({ price: 1.0520 })
        })
      );
    });

    test('cancels order successfully', async () => {
      const mockResponse = {
        orderId: 'order_123456',
        status: 'CANCELLED'
      };

      (global.fetch as jest.Mock).mockResolvedValueOnce({
        ok: true,
        json: async () => mockResponse
      });

      const result = await apiService.cancelOrder('order_123456');

      expect(result.success).toBe(true);
      expect(global.fetch).toHaveBeenCalledWith(
        `${mockBaseURL}/orders/order_123456`,
        expect.objectContaining({ method: 'DELETE' })
      );
    });
  });

  describe('Position Management', () => {
    test('retrieves positions successfully', async () => {
      const mockPositions = [
        {
          symbol: 'EUR/USD',
          quantity: 100000,
          entryPrice: 1.0500,
          currentPrice: 1.0525,
          unrealizedPnL: 250
        },
        {
          symbol: 'GBP/USD',
          quantity: -50000,
          entryPrice: 1.2600,
          currentPrice: 1.2580,
          unrealizedPnL: 100
        }
      ];

      (global.fetch as jest.Mock).mockResolvedValueOnce({
        ok: true,
        json: async () => ({ positions: mockPositions })
      });

      const result = await apiService.getPositions();

      expect(result.success).toBe(true);
      expect(result.data).toEqual(mockPositions);
      expect(result.executionTime).toBeGreaterThan(0);

      expect(global.fetch).toHaveBeenCalledWith(
        `${mockBaseURL}/positions`,
        expect.objectContaining({ method: 'GET' })
      );
    });

    test('handles positions retrieval failure', async () => {
      (global.fetch as jest.Mock).mockRejectedValueOnce(new Error('Server error'));

      const result = await apiService.getPositions();

      expect(result.success).toBe(false);
      expect(result.error?.code).toBe('POSITIONS_ERROR');
      expect(result.error?.message).toBe('Server error');
    });
  });

  describe('Account Information', () => {
    test('retrieves account info successfully', async () => {
      const mockAccountData = {
        accountId: 'acc_123',
        balance: 100000,
        equity: 102500,
        margin: 25000,
        freeMargin: 77500,
        marginLevel: 410,
        currency: 'USD'
      };

      (global.fetch as jest.Mock).mockResolvedValueOnce({
        ok: true,
        json: async () => mockAccountData
      });

      const result = await apiService.getAccountInfo();

      expect(result.success).toBe(true);
      expect(result.data).toEqual(mockAccountData);

      expect(global.fetch).toHaveBeenCalledWith(
        `${mockBaseURL}/account`,
        expect.objectContaining({ method: 'GET' })
      );
    });
  });

  describe('Emergency Operations', () => {
    test('executes emergency stop successfully', async () => {
      const mockResponse = {
        message: 'Emergency stop executed',
        closedPositions: 5,
        cancelledOrders: 3,
        timestamp: new Date().toISOString()
      };

      (global.fetch as jest.Mock).mockResolvedValueOnce({
        ok: true,
        json: async () => mockResponse
      });

      const result = await apiService.emergencyStop();

      expect(result.success).toBe(true);
      expect(result.data).toEqual(mockResponse);
      expect(result.executionTime).toBeGreaterThan(0);

      expect(global.fetch).toHaveBeenCalledWith(
        `${mockBaseURL}/emergency-stop`,
        expect.objectContaining({ method: 'POST' })
      );
    });

    test('handles emergency stop failure', async () => {
      (global.fetch as jest.Mock).mockRejectedValueOnce(new Error('Emergency stop failed'));

      const result = await apiService.emergencyStop();

      expect(result.success).toBe(false);
      expect(result.error?.code).toBe('EMERGENCY_STOP_ERROR');
      expect(result.error?.message).toBe('Emergency stop failed');
    });
  });

  describe('ML Predictions', () => {
    test('retrieves ML predictions successfully', async () => {
      const mockPrediction = {
        direction: 'up' as const,
        confidence: 0.85,
        target: 1.0550,
        timeframe: '1H'
      };

      (global.fetch as jest.Mock).mockResolvedValueOnce({
        ok: true,
        json: async () => mockPrediction
      });

      const result = await apiService.getMLPredictions('EUR/USD');

      expect(result.success).toBe(true);
      expect(result.data).toEqual(mockPrediction);

      expect(global.fetch).toHaveBeenCalledWith(
        `${mockBaseURL}/ml/predictions/EUR/USD`,
        expect.objectContaining({ method: 'GET' })
      );
    });
  });

  describe('Data Export', () => {
    test('exports trading history successfully', async () => {
      const mockResponse = {
        downloadUrl: 'https://api.fxml4.com/exports/history_123.csv'
      };

      (global.fetch as jest.Mock).mockResolvedValueOnce({
        ok: true,
        json: async () => mockResponse
      });

      const exportParams = {
        startDate: '2024-01-01',
        endDate: '2024-01-31',
        symbols: ['EUR/USD', 'GBP/USD']
      };

      const result = await apiService.exportTradingHistory('CSV', exportParams);

      expect(result.success).toBe(true);
      expect(result.data?.downloadUrl).toBe(mockResponse.downloadUrl);

      expect(global.fetch).toHaveBeenCalledWith(
        `${mockBaseURL}/export/history`,
        expect.objectContaining({
          method: 'POST',
          body: JSON.stringify({ format: 'CSV', ...exportParams })
        })
      );
    });
  });

  describe('Error Handling', () => {
    test('handles HTTP error responses', async () => {
      (global.fetch as jest.Mock).mockResolvedValueOnce({
        ok: false,
        status: 400,
        statusText: 'Bad Request'
      });

      const order: Order = {
        symbol: 'EUR/USD',
        side: 'BUY',
        quantity: 100000,
        orderType: 'MARKET'
      };

      const result = await apiService.submitOrder(order);

      expect(result.success).toBe(false);
      expect(result.error?.message).toContain('400 Bad Request');
    });

    test('handles network timeouts', async () => {
      (global.fetch as jest.Mock).mockImplementationOnce(() => {
        return new Promise((resolve, reject) => {
          setTimeout(() => reject(new Error('Request timeout')), 100);
        });
      });

      const result = await apiService.getAccountInfo();

      expect(result.success).toBe(false);
      expect(result.error?.message).toBe('Request timeout');
    });

    test('handles malformed response data', async () => {
      (global.fetch as jest.Mock).mockResolvedValueOnce({
        ok: true,
        json: async () => {
          throw new Error('Invalid JSON');
        }
      });

      const result = await apiService.getPositions();

      expect(result.success).toBe(false);
      expect(result.error?.message).toBe('Invalid JSON');
    });
  });

  describe('Performance Monitoring', () => {
    test('tracks API call metrics', async () => {
      (global.fetch as jest.Mock).mockResolvedValue({
        ok: true,
        json: async () => ({ success: true })
      });

      // Make multiple API calls
      await apiService.getAccountInfo();
      await apiService.getPositions();
      await apiService.submitOrder({
        symbol: 'EUR/USD',
        side: 'BUY',
        quantity: 10000,
        orderType: 'MARKET'
      });

      const metrics = apiService.getPerformanceMetrics();

      expect(metrics.requestCount).toBe(3);
      expect(metrics.averageLatency).toBeGreaterThan(0);
      expect(metrics.totalLatency).toBeGreaterThan(0);
    });

    test('calculates average latency correctly', async () => {
      (global.fetch as jest.Mock)
        .mockResolvedValueOnce({
          ok: true,
          json: async () => {
            await new Promise(resolve => setTimeout(resolve, 50));
            return { success: true };
          }
        })
        .mockResolvedValueOnce({
          ok: true,
          json: async () => {
            await new Promise(resolve => setTimeout(resolve, 100));
            return { success: true };
          }
        });

      await apiService.getAccountInfo();
      await apiService.getPositions();

      const metrics = apiService.getPerformanceMetrics();

      expect(metrics.requestCount).toBe(2);
      expect(metrics.averageLatency).toBeGreaterThan(50);
      expect(metrics.averageLatency).toBeLessThan(200);
    });
  });

  describe('Request Headers', () => {
    test('includes correct authentication headers', async () => {
      (global.fetch as jest.Mock).mockResolvedValueOnce({
        ok: true,
        json: async () => ({ success: true })
      });

      await apiService.getAccountInfo();

      const [url, options] = (global.fetch as jest.Mock).mock.calls[0];

      expect(options.headers).toMatchObject({
        'Authorization': `Bearer ${mockAPIKey}`,
        'Content-Type': 'application/json',
        'X-Client-Version': '4.0.0',
        'X-Request-ID': expect.any(String)
      });
    });

    test('generates unique request IDs', async () => {
      (global.fetch as jest.Mock).mockResolvedValue({
        ok: true,
        json: async () => ({ success: true })
      });

      await apiService.getAccountInfo();
      await apiService.getPositions();

      const call1Headers = (global.fetch as jest.Mock).mock.calls[0][1].headers;
      const call2Headers = (global.fetch as jest.Mock).mock.calls[1][1].headers;

      expect(call1Headers['X-Request-ID']).toBeDefined();
      expect(call2Headers['X-Request-ID']).toBeDefined();
      expect(call1Headers['X-Request-ID']).not.toBe(call2Headers['X-Request-ID']);
    });
  });
});
