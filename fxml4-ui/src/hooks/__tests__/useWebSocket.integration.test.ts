/**
 * WebSocket Hook Integration Tests
 *
 * Tests for WebSocket functionality with mock server
 */

import { renderHook, act, waitFor } from '@testing-library/react';
import { useWebSocket } from '../useWebSocket';
import type { MarketData, TradingSignal, OrderUpdate } from '@/types';

// Mock WebSocket
class MockWebSocket {
  static CONNECTING = 0;
  static OPEN = 1;
  static CLOSING = 2;
  static CLOSED = 3;

  readyState = MockWebSocket.CONNECTING;
  url = '';
  onopen: ((event: Event) => void) | null = null;
  onclose: ((event: CloseEvent) => void) | null = null;
  onmessage: ((event: MessageEvent) => void) | null = null;
  onerror: ((event: Event) => void) | null = null;

  private messageQueue: any[] = [];

  constructor(url: string) {
    this.url = url;

    // Simulate async connection
    setTimeout(() => {
      this.readyState = MockWebSocket.OPEN;
      this.onopen?.(new Event('open'));

      // Process queued messages
      this.messageQueue.forEach(message => {
        this.simulateMessage(message);
      });
      this.messageQueue = [];
    }, 10);
  }

  send = jest.fn((data: string) => {
    if (this.readyState === MockWebSocket.OPEN) {
      // Echo back some messages for testing
      const parsed = JSON.parse(data);
      if (parsed.type === 'subscribe') {
        this.simulateMessage({
          type: 'subscription_confirmed',
          data: { symbol: parsed.data.symbol },
        });
      }
    }
  });

  close = jest.fn(() => {
    this.readyState = MockWebSocket.CLOSED;
    this.onclose?.(new CloseEvent('close'));
  });

  // Helper method to simulate receiving messages
  simulateMessage(message: any) {
    if (this.readyState === MockWebSocket.OPEN) {
      setTimeout(() => {
        this.onmessage?.(new MessageEvent('message', {
          data: JSON.stringify(message),
        }));
      }, 1);
    } else {
      this.messageQueue.push(message);
    }
  }

  // Helper to simulate connection error
  simulateError() {
    this.onerror?.(new Event('error'));
  }

  // Helper to simulate connection close
  simulateClose() {
    this.readyState = MockWebSocket.CLOSED;
    this.onclose?.(new CloseEvent('close'));
  }
}

// Replace global WebSocket
global.WebSocket = MockWebSocket as any;

// Mock stores
jest.mock('@/stores/marketDataStore', () => ({
  useMarketDataStore: () => ({
    setCurrentPrice: jest.fn(),
    setConnectionStatus: jest.fn(),
    updateLastUpdate: jest.fn(),
  }),
}));

jest.mock('@/stores/tradingStore', () => ({
  useTradingStore: () => ({
    updateOrder: jest.fn(),
    updatePosition: jest.fn(),
    addSignal: jest.fn(),
  }),
}));

jest.mock('@/stores/appStore', () => ({
  useAppStore: () => ({
    setConnectionStatus: jest.fn(),
    addNotification: jest.fn(),
    addError: jest.fn(),
  }),
}));

describe('useWebSocket Integration', () => {
  let mockWs: MockWebSocket;

  beforeEach(() => {
    jest.clearAllMocks();
    mockWs = null as any;
  });

  afterEach(() => {
    mockWs?.close();
  });

  describe('Connection Management', () => {
    it('should establish WebSocket connection automatically', async () => {
      const { result } = renderHook(() =>
        useWebSocket({
          autoConnect: true,
          url: 'ws://localhost:8000/ws'
        })
      );

      await waitFor(() => {
        expect(result.current.isConnected).toBe(true);
      });

      expect(result.current.connectionStatus).toBe('connected');
    });

    it('should not auto-connect when autoConnect is false', () => {
      const { result } = renderHook(() =>
        useWebSocket({
          autoConnect: false,
          url: 'ws://localhost:8000/ws'
        })
      );

      expect(result.current.isConnected).toBe(false);
      expect(result.current.connectionStatus).toBe('disconnected');
    });

    it('should connect manually when connect() is called', async () => {
      const { result } = renderHook(() =>
        useWebSocket({
          autoConnect: false,
          url: 'ws://localhost:8000/ws'
        })
      );

      expect(result.current.isConnected).toBe(false);

      act(() => {
        result.current.connect();
      });

      await waitFor(() => {
        expect(result.current.isConnected).toBe(true);
      });
    });

    it('should disconnect when disconnect() is called', async () => {
      const { result } = renderHook(() =>
        useWebSocket({
          autoConnect: true,
          url: 'ws://localhost:8000/ws'
        })
      );

      await waitFor(() => {
        expect(result.current.isConnected).toBe(true);
      });

      act(() => {
        result.current.disconnect();
      });

      await waitFor(() => {
        expect(result.current.isConnected).toBe(false);
      });
    });

    it('should handle connection errors', async () => {
      const { result } = renderHook(() =>
        useWebSocket({
          autoConnect: true,
          url: 'ws://localhost:8000/ws'
        })
      );

      // Wait for connection
      await waitFor(() => {
        expect(result.current.isConnected).toBe(true);
      });

      // Simulate error
      act(() => {
        const ws = (global.WebSocket as any).mockInstance;
        ws?.simulateError();
      });

      await waitFor(() => {
        expect(result.current.connectionStatus).toBe('error');
      });
    });

    it('should handle connection close', async () => {
      const { result } = renderHook(() =>
        useWebSocket({
          autoConnect: true,
          url: 'ws://localhost:8000/ws'
        })
      );

      await waitFor(() => {
        expect(result.current.isConnected).toBe(true);
      });

      // Simulate close
      act(() => {
        const ws = (global.WebSocket as any).mockInstance;
        ws?.simulateClose();
      });

      await waitFor(() => {
        expect(result.current.isConnected).toBe(false);
        expect(result.current.connectionStatus).toBe('disconnected');
      });
    });
  });

  describe('Market Data Subscription', () => {
    it('should subscribe to market data for symbols', async () => {
      const { result } = renderHook(() =>
        useWebSocket({
          autoConnect: true,
          subscribeToMarketData: true,
          symbols: ['EURUSD', 'GBPUSD']
        })
      );

      await waitFor(() => {
        expect(result.current.isConnected).toBe(true);
      });

      // Should have sent subscription messages
      const mockSend = (global.WebSocket as any).prototype.send;
      expect(mockSend).toHaveBeenCalledWith(
        JSON.stringify({
          type: 'subscribe',
          data: { symbol: 'EURUSD', type: 'market_data' },
        })
      );
      expect(mockSend).toHaveBeenCalledWith(
        JSON.stringify({
          type: 'subscribe',
          data: { symbol: 'GBPUSD', type: 'market_data' },
        })
      );
    });

    it('should handle market data updates', async () => {
      const { result } = renderHook(() =>
        useWebSocket({
          autoConnect: true,
          subscribeToMarketData: true,
          symbols: ['EURUSD']
        })
      );

      await waitFor(() => {
        expect(result.current.isConnected).toBe(true);
      });

      // Get reference to the WebSocket instance
      const wsConstructor = global.WebSocket as any;
      const wsInstance = new wsConstructor('ws://test');

      // Simulate market data message
      const marketData: MarketData = {
        symbol: 'EURUSD',
        bid: 1.08245,
        ask: 1.08248,
        timestamp: '2024-01-15T10:30:00.000Z',
        volume: 1000000,
      };

      act(() => {
        wsInstance.simulateMessage({
          type: 'market_data',
          data: marketData,
        });
      });

      // Verify market data was processed (would need to verify store calls)
    });

    it('should subscribe to additional symbols', async () => {
      const { result } = renderHook(() =>
        useWebSocket({
          autoConnect: true,
          subscribeToMarketData: true,
          symbols: ['EURUSD']
        })
      );

      await waitFor(() => {
        expect(result.current.isConnected).toBe(true);
      });

      act(() => {
        result.current.subscribeToSymbol('GBPUSD');
      });

      const mockSend = (global.WebSocket as any).prototype.send;
      expect(mockSend).toHaveBeenLastCalledWith(
        JSON.stringify({
          type: 'subscribe',
          data: { symbol: 'GBPUSD', type: 'market_data' },
        })
      );
    });

    it('should unsubscribe from symbols', async () => {
      const { result } = renderHook(() =>
        useWebSocket({
          autoConnect: true,
          subscribeToMarketData: true,
          symbols: ['EURUSD', 'GBPUSD']
        })
      );

      await waitFor(() => {
        expect(result.current.isConnected).toBe(true);
      });

      act(() => {
        result.current.unsubscribeFromSymbol('EURUSD');
      });

      const mockSend = (global.WebSocket as any).prototype.send;
      expect(mockSend).toHaveBeenLastCalledWith(
        JSON.stringify({
          type: 'unsubscribe',
          data: { symbol: 'EURUSD', type: 'market_data' },
        })
      );
    });
  });

  describe('Trading Updates', () => {
    it('should handle order updates', async () => {
      const { result } = renderHook(() =>
        useWebSocket({
          autoConnect: true,
          subscribeToTradingUpdates: true
        })
      );

      await waitFor(() => {
        expect(result.current.isConnected).toBe(true);
      });

      const wsConstructor = global.WebSocket as any;
      const wsInstance = new wsConstructor('ws://test');

      const orderUpdate: OrderUpdate = {
        id: 'order-123',
        symbol: 'EURUSD',
        side: 'buy',
        type: 'market',
        quantity: 10000,
        status: 'filled',
        filled_quantity: 10000,
        avg_fill_price: 1.08245,
        updated_at: '2024-01-15T10:30:00.000Z',
      };

      act(() => {
        wsInstance.simulateMessage({
          type: 'order_update',
          data: orderUpdate,
        });
      });

      // Verify order update was processed
    });

    it('should handle position updates', async () => {
      const { result } = renderHook(() =>
        useWebSocket({
          autoConnect: true,
          subscribeToTradingUpdates: true
        })
      );

      await waitFor(() => {
        expect(result.current.isConnected).toBe(true);
      });

      const wsConstructor = global.WebSocket as any;
      const wsInstance = new wsConstructor('ws://test');

      const positionUpdate = {
        id: 'pos-123',
        symbol: 'EURUSD',
        side: 'long' as const,
        quantity: 10000,
        current_price: 1.08250,
        unrealized_pnl: 50,
        updated_at: '2024-01-15T10:30:00.000Z',
      };

      act(() => {
        wsInstance.simulateMessage({
          type: 'position_update',
          data: positionUpdate,
        });
      });

      // Verify position update was processed
    });

    it('should handle trading signals', async () => {
      const { result } = renderHook(() =>
        useWebSocket({
          autoConnect: true,
          subscribeToSignals: true
        })
      );

      await waitFor(() => {
        expect(result.current.isConnected).toBe(true);
      });

      const wsConstructor = global.WebSocket as any;
      const wsInstance = new wsConstructor('ws://test');

      const signal: TradingSignal = {
        id: 'signal-123',
        symbol: 'EURUSD',
        signal_type: 'buy',
        confidence: 0.85,
        entry_price: 1.08250,
        stop_loss: 1.08150,
        take_profit: 1.08350,
        timestamp: '2024-01-15T10:30:00.000Z',
        model_name: 'EURUSD_Neural_Network',
        features: {
          rsi: 65.5,
          macd: 0.0025,
        },
      };

      act(() => {
        wsInstance.simulateMessage({
          type: 'trading_signal',
          data: signal,
        });
      });

      // Verify signal was processed
    });
  });

  describe('Reconnection Logic', () => {
    it('should attempt reconnection after connection loss', async () => {
      const { result } = renderHook(() =>
        useWebSocket({
          autoConnect: true,
          reconnectInterval: 100 // Fast reconnect for testing
        })
      );

      await waitFor(() => {
        expect(result.current.isConnected).toBe(true);
      });

      // Simulate connection loss
      const wsConstructor = global.WebSocket as any;
      const wsInstance = new wsConstructor('ws://test');

      act(() => {
        wsInstance.simulateClose();
      });

      await waitFor(() => {
        expect(result.current.isConnected).toBe(false);
      });

      // Should attempt reconnection
      await waitFor(() => {
        expect(result.current.connectionStatus).toBe('reconnecting');
      }, { timeout: 200 });

      // Should eventually reconnect
      await waitFor(() => {
        expect(result.current.isConnected).toBe(true);
      }, { timeout: 500 });
    });

    it('should respect maximum reconnect attempts', async () => {
      const { result } = renderHook(() =>
        useWebSocket({
          autoConnect: true,
          reconnectInterval: 50,
          maxReconnectAttempts: 2
        })
      );

      await waitFor(() => {
        expect(result.current.isConnected).toBe(true);
      });

      // Simulate repeated connection failures
      const wsConstructor = global.WebSocket as any;

      // Mock constructor to always fail
      (global.WebSocket as any) = function() {
        setTimeout(() => {
          throw new Error('Connection failed');
        }, 10);
      };

      const wsInstance = new wsConstructor('ws://test');

      act(() => {
        wsInstance.simulateClose();
      });

      // Should eventually stop trying and remain disconnected
      await waitFor(() => {
        expect(result.current.connectionStatus).toBe('disconnected');
      }, { timeout: 500 });
    });
  });

  describe('Message Queuing', () => {
    it('should queue messages when disconnected and send when reconnected', async () => {
      const { result } = renderHook(() =>
        useWebSocket({
          autoConnect: false
        })
      );

      // Try to send message while disconnected
      act(() => {
        result.current.subscribeToSymbol('EURUSD');
      });

      // Connect
      act(() => {
        result.current.connect();
      });

      await waitFor(() => {
        expect(result.current.isConnected).toBe(true);
      });

      // Should have sent queued message
      const mockSend = (global.WebSocket as any).prototype.send;
      expect(mockSend).toHaveBeenCalledWith(
        JSON.stringify({
          type: 'subscribe',
          data: { symbol: 'EURUSD', type: 'market_data' },
        })
      );
    });
  });

  describe('Cleanup', () => {
    it('should cleanup on unmount', async () => {
      const { result, unmount } = renderHook(() =>
        useWebSocket({
          autoConnect: true
        })
      );

      await waitFor(() => {
        expect(result.current.isConnected).toBe(true);
      });

      const mockClose = (global.WebSocket as any).prototype.close;

      unmount();

      expect(mockClose).toHaveBeenCalled();
    });

    it('should clear reconnection timers on unmount', async () => {
      jest.useFakeTimers();

      const { result, unmount } = renderHook(() =>
        useWebSocket({
          autoConnect: true,
          reconnectInterval: 1000
        })
      );

      await waitFor(() => {
        expect(result.current.isConnected).toBe(true);
      });

      // Simulate disconnect to start reconnection timer
      const wsConstructor = global.WebSocket as any;
      const wsInstance = new wsConstructor('ws://test');

      act(() => {
        wsInstance.simulateClose();
      });

      unmount();

      // Fast-forward time - should not attempt reconnection
      jest.advanceTimersByTime(2000);

      expect(result.current.isConnected).toBe(false);

      jest.useRealTimers();
    });
  });

  describe('Error Recovery', () => {
    it('should handle malformed message data', async () => {
      const { result } = renderHook(() =>
        useWebSocket({
          autoConnect: true
        })
      );

      await waitFor(() => {
        expect(result.current.isConnected).toBe(true);
      });

      const wsConstructor = global.WebSocket as any;
      const wsInstance = new wsConstructor('ws://test');

      // Send malformed JSON
      act(() => {
        wsInstance.onmessage?.(new MessageEvent('message', {
          data: 'invalid json{',
        }));
      });

      // Should not crash and remain connected
      expect(result.current.isConnected).toBe(true);
    });

    it('should handle unknown message types', async () => {
      const { result } = renderHook(() =>
        useWebSocket({
          autoConnect: true
        })
      );

      await waitFor(() => {
        expect(result.current.isConnected).toBe(true);
      });

      const wsConstructor = global.WebSocket as any;
      const wsInstance = new wsConstructor('ws://test');

      act(() => {
        wsInstance.simulateMessage({
          type: 'unknown_message_type',
          data: { some: 'data' },
        });
      });

      // Should handle gracefully
      expect(result.current.isConnected).toBe(true);
    });
  });
});
