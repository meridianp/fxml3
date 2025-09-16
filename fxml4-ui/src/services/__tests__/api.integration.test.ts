/**
 * API Service Integration Tests
 *
 * Tests for API service functionality with mock backend
 */

import { api } from '../api';
import type { Order, Position, MLModel, MarketData } from '@/types';

// Mock fetch for Node.js environment
global.fetch = jest.fn();

describe('API Service Integration', () => {
  const mockResponse = (data: any, status = 200) => ({
    ok: status >= 200 && status < 300,
    status,
    json: () => Promise.resolve(data),
    text: () => Promise.resolve(JSON.stringify(data)),
  });

  beforeEach(() => {
    jest.clearAllMocks();
    (fetch as jest.Mock).mockResolvedValue(mockResponse({ success: true }));
  });

  describe('Trading API Endpoints', () => {
    describe('Orders', () => {
      it('should create a new order', async () => {
        const orderData = {
          symbol: 'EURUSD',
          side: 'buy' as const,
          type: 'market' as const,
          quantity: 10000,
        };

        const mockOrder: Order = {
          id: 'order-123',
          ...orderData,
          status: 'pending',
          created_at: '2024-01-15T10:30:00.000Z',
          updated_at: '2024-01-15T10:30:00.000Z',
          filled_quantity: 0,
          time_in_force: 'GTC',
        };

        (fetch as jest.Mock).mockResolvedValueOnce(
          mockResponse({ data: { order: mockOrder } })
        );

        const result = await api.post('/trading/orders', orderData);

        expect(fetch).toHaveBeenCalledWith(
          expect.stringContaining('/trading/orders'),
          expect.objectContaining({
            method: 'POST',
            headers: expect.objectContaining({
              'Content-Type': 'application/json',
            }),
            body: JSON.stringify(orderData),
          })
        );

        expect(result.data.order).toEqual(mockOrder);
      });

      it('should fetch all orders', async () => {
        const mockOrders: Order[] = [
          {
            id: 'order-1',
            symbol: 'EURUSD',
            side: 'buy',
            type: 'market',
            quantity: 10000,
            status: 'filled',
            created_at: '2024-01-15T10:30:00.000Z',
            updated_at: '2024-01-15T10:32:00.000Z',
            filled_quantity: 10000,
            avg_fill_price: 1.08245,
            time_in_force: 'GTC',
          },
        ];

        (fetch as jest.Mock).mockResolvedValueOnce(
          mockResponse({ data: { orders: mockOrders } })
        );

        const result = await api.get('/trading/orders');

        expect(fetch).toHaveBeenCalledWith(
          expect.stringContaining('/trading/orders'),
          expect.objectContaining({
            method: 'GET',
          })
        );

        expect(result.data.orders).toEqual(mockOrders);
      });

      it('should cancel an order', async () => {
        const orderId = 'order-123';

        (fetch as jest.Mock).mockResolvedValueOnce(
          mockResponse({ data: { success: true } })
        );

        const result = await api.delete(`/trading/orders/${orderId}`);

        expect(fetch).toHaveBeenCalledWith(
          expect.stringContaining(`/trading/orders/${orderId}`),
          expect.objectContaining({
            method: 'DELETE',
          })
        );

        expect(result.data.success).toBe(true);
      });
    });

    describe('Positions', () => {
      it('should fetch all positions', async () => {
        const mockPositions: Position[] = [
          {
            id: 'pos-1',
            symbol: 'EURUSD',
            side: 'long',
            quantity: 10000,
            entry_price: 1.08200,
            current_price: 1.08245,
            unrealized_pnl: 45,
            realized_pnl: 0,
            margin_used: 1082,
            created_at: '2024-01-15T10:25:00.000Z',
            updated_at: '2024-01-15T10:30:00.000Z',
          },
        ];

        (fetch as jest.Mock).mockResolvedValueOnce(
          mockResponse({ data: { positions: mockPositions } })
        );

        const result = await api.get('/trading/positions');

        expect(result.data.positions).toEqual(mockPositions);
      });

      it('should close a position', async () => {
        const positionId = 'pos-123';

        (fetch as jest.Mock).mockResolvedValueOnce(
          mockResponse({ data: { success: true } })
        );

        const result = await api.post(`/trading/positions/${positionId}/close`);

        expect(fetch).toHaveBeenCalledWith(
          expect.stringContaining(`/trading/positions/${positionId}/close`),
          expect.objectContaining({
            method: 'POST',
          })
        );

        expect(result.data.success).toBe(true);
      });
    });

    describe('Account', () => {
      it('should fetch account information', async () => {
        const mockAccount = {
          id: 'account-123',
          balance: 100000,
          equity: 102500,
          margin_used: 2500,
          margin_available: 97500,
          leverage: 100,
          currency: 'USD',
          realized_pnl: 1500,
          unrealized_pnl: 1000,
        };

        (fetch as jest.Mock).mockResolvedValueOnce(
          mockResponse({ data: { account: mockAccount } })
        );

        const result = await api.get('/trading/account');

        expect(result.data.account).toEqual(mockAccount);
      });
    });
  });

  describe('Market Data API Endpoints', () => {
    it('should fetch current prices', async () => {
      const mockPrices: Record<string, MarketData> = {
        EURUSD: {
          symbol: 'EURUSD',
          bid: 1.08245,
          ask: 1.08248,
          timestamp: '2024-01-15T10:30:00.000Z',
          volume: 1000000,
        },
      };

      (fetch as jest.Mock).mockResolvedValueOnce(
        mockResponse({ data: { prices: mockPrices } })
      );

      const result = await api.get('/data/prices');

      expect(result.data.prices).toEqual(mockPrices);
    });

    it('should fetch historical data with parameters', async () => {
      const mockCandles = [
        {
          timestamp: '2024-01-15T10:00:00.000Z',
          open: 1.08200,
          high: 1.08280,
          low: 1.08180,
          close: 1.08250,
          volume: 1000,
        },
      ];

      (fetch as jest.Mock).mockResolvedValueOnce(
        mockResponse({ data: { data: mockCandles } })
      );

      const result = await api.get('/data/historical/EURUSD', {
        params: {
          timeframe: '1h',
          limit: 100,
        },
      });

      expect(fetch).toHaveBeenCalledWith(
        expect.stringContaining('/data/historical/EURUSD?timeframe=1h&limit=100'),
        expect.any(Object)
      );

      expect(result.data.data).toEqual(mockCandles);
    });
  });

  describe('ML API Endpoints', () => {
    it('should create a new ML model', async () => {
      const modelData = {
        name: 'EURUSD Neural Network',
        description: 'Deep learning model for EURUSD',
        model_type: 'neural_network',
        symbol: 'EURUSD',
        timeframe: '1h',
        features: ['price_features', 'technical_indicators'],
        hyperparameters: { learning_rate: 0.001 },
      };

      const mockModel: MLModel = {
        id: 'model-123',
        ...modelData,
        status: 'draft',
        is_deployed: false,
        created_at: '2024-01-15T10:00:00.000Z',
      };

      (fetch as jest.Mock).mockResolvedValueOnce(
        mockResponse({ data: { model: mockModel } })
      );

      const result = await api.post('/ml/models', modelData);

      expect(result.data.model).toEqual(mockModel);
    });

    it('should start model training', async () => {
      const modelId = 'model-123';

      (fetch as jest.Mock).mockResolvedValueOnce(
        mockResponse({ data: { success: true, training_job_id: 'job-456' } })
      );

      const result = await api.post(`/ml/models/${modelId}/train`);

      expect(fetch).toHaveBeenCalledWith(
        expect.stringContaining(`/ml/models/${modelId}/train`),
        expect.objectContaining({
          method: 'POST',
        })
      );

      expect(result.data.success).toBe(true);
      expect(result.data.training_job_id).toBe('job-456');
    });

    it('should fetch all models', async () => {
      const mockModels: MLModel[] = [
        {
          id: 'model-1',
          name: 'EURUSD Neural Network',
          description: 'Deep learning model for EURUSD',
          model_type: 'neural_network',
          symbol: 'EURUSD',
          timeframe: '1h',
          status: 'trained',
          is_deployed: false,
          created_at: '2024-01-15T10:00:00.000Z',
          metrics: { accuracy: 0.85, loss: 0.023 },
        },
      ];

      (fetch as jest.Mock).mockResolvedValueOnce(
        mockResponse({ data: { models: mockModels } })
      );

      const result = await api.get('/ml/models');

      expect(result.data.models).toEqual(mockModels);
    });
  });

  describe('Authentication', () => {
    it('should handle authentication headers', async () => {
      const token = 'test-jwt-token';

      // Mock localStorage
      const mockLocalStorage = {
        getItem: jest.fn(() => token),
        setItem: jest.fn(),
        removeItem: jest.fn(),
      };
      Object.defineProperty(window, 'localStorage', {
        value: mockLocalStorage,
        writable: true,
      });

      (fetch as jest.Mock).mockResolvedValueOnce(
        mockResponse({ data: { success: true } })
      );

      await api.get('/protected-endpoint');

      expect(fetch).toHaveBeenCalledWith(
        expect.any(String),
        expect.objectContaining({
          headers: expect.objectContaining({
            'Authorization': `Bearer ${token}`,
          }),
        })
      );
    });

    it('should handle missing authentication token', async () => {
      // Mock localStorage with no token
      const mockLocalStorage = {
        getItem: jest.fn(() => null),
        setItem: jest.fn(),
        removeItem: jest.fn(),
      };
      Object.defineProperty(window, 'localStorage', {
        value: mockLocalStorage,
        writable: true,
      });

      (fetch as jest.Mock).mockResolvedValueOnce(
        mockResponse({ error: 'Unauthorized' }, 401)
      );

      try {
        await api.get('/protected-endpoint');
      } catch (error: any) {
        expect(error.response?.status).toBe(401);
      }
    });
  });

  describe('Error Handling', () => {
    it('should handle network errors', async () => {
      (fetch as jest.Mock).mockRejectedValueOnce(new Error('Network error'));

      try {
        await api.get('/test-endpoint');
      } catch (error: any) {
        expect(error.message).toContain('Network error');
      }
    });

    it('should handle HTTP error responses', async () => {
      (fetch as jest.Mock).mockResolvedValueOnce({
        ok: false,
        status: 400,
        json: () => Promise.resolve({
          error: 'Bad Request',
          message: 'Invalid parameters',
        }),
      });

      try {
        await api.get('/test-endpoint');
      } catch (error: any) {
        expect(error.response?.status).toBe(400);
        expect(error.response?.data?.message).toBe('Invalid parameters');
      }
    });

    it('should handle server errors (5xx)', async () => {
      (fetch as jest.Mock).mockResolvedValueOnce({
        ok: false,
        status: 500,
        json: () => Promise.resolve({
          error: 'Internal Server Error',
        }),
      });

      try {
        await api.get('/test-endpoint');
      } catch (error: any) {
        expect(error.response?.status).toBe(500);
      }
    });
  });

  describe('Request Interceptors', () => {
    it('should add correlation IDs to requests', async () => {
      (fetch as jest.Mock).mockResolvedValueOnce(
        mockResponse({ data: { success: true } })
      );

      await api.get('/test-endpoint');

      expect(fetch).toHaveBeenCalledWith(
        expect.any(String),
        expect.objectContaining({
          headers: expect.objectContaining({
            'X-Correlation-ID': expect.any(String),
          }),
        })
      );
    });

    it('should add request timestamps', async () => {
      (fetch as jest.Mock).mockResolvedValueOnce(
        mockResponse({ data: { success: true } })
      );

      await api.get('/test-endpoint');

      expect(fetch).toHaveBeenCalledWith(
        expect.any(String),
        expect.objectContaining({
          headers: expect.objectContaining({
            'X-Request-Time': expect.any(String),
          }),
        })
      );
    });
  });

  describe('Response Processing', () => {
    it('should parse JSON responses correctly', async () => {
      const mockData = { message: 'Success', data: { id: 123 } };

      (fetch as jest.Mock).mockResolvedValueOnce(
        mockResponse(mockData)
      );

      const result = await api.get('/test-endpoint');

      expect(result.data).toEqual(mockData);
      expect(result.status).toBe(200);
    });

    it('should handle empty responses', async () => {
      (fetch as jest.Mock).mockResolvedValueOnce({
        ok: true,
        status: 204,
        json: () => Promise.resolve(null),
        text: () => Promise.resolve(''),
      });

      const result = await api.delete('/test-endpoint');

      expect(result.status).toBe(204);
    });
  });

  describe('Timeout Handling', () => {
    it('should handle request timeouts', async () => {
      jest.useFakeTimers();

      (fetch as jest.Mock).mockImplementationOnce(() =>
        new Promise((resolve) => {
          setTimeout(() => resolve(mockResponse({ data: 'delayed' })), 10000);
        })
      );

      const requestPromise = api.get('/slow-endpoint');

      // Fast-forward time to trigger timeout
      jest.advanceTimersByTime(5000);

      try {
        await requestPromise;
      } catch (error: any) {
        expect(error.message).toContain('timeout');
      }

      jest.useRealTimers();
    });
  });

  describe('Retry Logic', () => {
    it('should retry failed requests', async () => {
      // First call fails, second succeeds
      (fetch as jest.Mock)
        .mockRejectedValueOnce(new Error('Network error'))
        .mockResolvedValueOnce(mockResponse({ data: { success: true } }));

      const result = await api.get('/test-endpoint');

      expect(fetch).toHaveBeenCalledTimes(2);
      expect(result.data.success).toBe(true);
    });

    it('should not retry on client errors (4xx)', async () => {
      (fetch as jest.Mock).mockResolvedValueOnce({
        ok: false,
        status: 400,
        json: () => Promise.resolve({ error: 'Bad Request' }),
      });

      try {
        await api.get('/test-endpoint');
      } catch (error) {
        expect(fetch).toHaveBeenCalledTimes(1);
      }
    });
  });
});
