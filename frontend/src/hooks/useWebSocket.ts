/**
 * WebSocket Hook
 *
 * Custom hook for managing WebSocket connections and integrating with stores
 */

import { useEffect, useRef, useCallback } from 'react';
import { wsService } from '@/services/websocket';
import { useMarketDataStore } from '@/stores/useMarketDataStore';
import { useTradingStore } from '@/stores/useTradingStore';
import { useAppStore } from '@/stores/useAppStore';
import type { MarketData, Order, Position, TradingSignal } from '@/types';

interface UseWebSocketOptions {
  autoConnect?: boolean;
  subscribeToMarketData?: boolean;
  subscribeToTradingUpdates?: boolean;
  subscribeToSignals?: boolean;
  subscribeToSystemUpdates?: boolean;
  symbols?: string[];
}

interface UseWebSocketReturn {
  isConnected: boolean;
  connectionStatus: string;
  connect: () => Promise<void>;
  disconnect: () => void;
  subscribeToSymbol: (symbol: string) => void;
  unsubscribeFromSymbol: (symbol: string) => void;
  requestMarketData: (symbol: string, timeframe: string) => void;
  requestSignal: (symbol: string, modelName?: string) => void;
}

export function useWebSocket(options: UseWebSocketOptions = {}): UseWebSocketReturn {
  const {
    autoConnect = false, // Temporarily disabled to prevent errors
    subscribeToMarketData = false,
    subscribeToTradingUpdates = false,
    subscribeToSignals = false,
    subscribeToSystemUpdates = false,
    symbols = []
  } = options;

  // Store actions
  const updateMarketData = useMarketDataStore(state => state.updateMarketData);
  const updateMultipleMarketData = useMarketDataStore(state => state.updateMultipleMarketData);
  const setMarketDataConnected = useMarketDataStore(state => state.setConnectionStatus);

  const addOrder = useTradingStore(state => state.addOrder);
  const updateOrder = useTradingStore(state => state.updateOrder);
  const addPosition = useTradingStore(state => state.addPosition);
  const updatePosition = useTradingStore(state => state.updatePosition);
  const updateAccount = useTradingStore(state => state.updateAccount);
  const addSignal = useTradingStore(state => state.addSignal);

  const setConnectionStatus = useAppStore(state => state.setConnectionStatus);
  const setSystemMetrics = useAppStore(state => state.setSystemMetrics);
  const addNotification = useAppStore(state => state.addNotification);

  // Connection state
  const isConnected = useAppStore(state => state.isConnected);
  const connectionStatus = useAppStore(state => state.connectionStatus);

  // Refs for cleanup
  const unsubscribeRefs = useRef<Array<() => void>>([]);

  // Connection management
  const connect = useCallback(async () => {
    try {
      setConnectionStatus('connecting');

      // Temporarily disable WebSocket connection to prevent errors
      console.log('WebSocket connection temporarily disabled');
      setConnectionStatus('disconnected');
      setMarketDataConnected(false);

      // const authToken = localStorage.getItem('fxml4_auth_token');
      // await wsService.connect(authToken || undefined);
      // setConnectionStatus('connected');
      // setMarketDataConnected(true);

    } catch (error) {
      console.error('WebSocket connection failed:', error);
      setConnectionStatus('error');
      setMarketDataConnected(false);

      addNotification({
        type: 'error',
        title: 'Connection Failed',
        message: 'Failed to connect to real-time data service'
      });
    }
  }, [setConnectionStatus, setMarketDataConnected, addNotification]);

  const disconnect = useCallback(() => {
    // wsService.disconnect(); // Temporarily disabled
    setConnectionStatus('disconnected');
    setMarketDataConnected(false);

    // Clean up all subscriptions
    unsubscribeRefs.current.forEach(unsubscribe => unsubscribe());
    unsubscribeRefs.current = [];
  }, [setConnectionStatus, setMarketDataConnected]);

  // Subscription management
  const subscribeToSymbol = useCallback((symbol: string) => {
    if (isConnected) {
      wsService.subscribeToMarketData([symbol]);
    }
  }, [isConnected]);

  const unsubscribeFromSymbol = useCallback((symbol: string) => {
    if (isConnected) {
      wsService.unsubscribe(`market_data:${symbol}`);
    }
  }, [isConnected]);

  // Direct requests
  const requestMarketData = useCallback((symbol: string, timeframe: string) => {
    if (isConnected) {
      wsService.requestMarketData(symbol, timeframe);
    }
  }, [isConnected]);

  const requestSignal = useCallback((symbol: string, modelName?: string) => {
    if (isConnected) {
      wsService.requestSignalGeneration(symbol, modelName);
    }
  }, [isConnected]);

  // Set up WebSocket event listeners
  useEffect(() => {
    const unsubscribes: Array<() => void> = [];

    // Connection event handlers
    unsubscribes.push(
      wsService.on('connected', () => {
        setConnectionStatus('connected');
        setMarketDataConnected(true);
        addNotification({
          type: 'success',
          title: 'Connected',
          message: 'Real-time data connection established'
        });
      })
    );

    unsubscribes.push(
      wsService.on('disconnected', (reason: string) => {
        setConnectionStatus('disconnected');
        setMarketDataConnected(false);
        addNotification({
          type: 'warning',
          title: 'Disconnected',
          message: `Connection lost: ${reason}`
        });
      })
    );

    unsubscribes.push(
      wsService.on('reconnecting', (attempt: number) => {
        setConnectionStatus('connecting');
        addNotification({
          type: 'info',
          title: 'Reconnecting',
          message: `Attempting to reconnect (${attempt})`
        });
      })
    );

    unsubscribes.push(
      wsService.on('reconnected', () => {
        setConnectionStatus('connected');
        setMarketDataConnected(true);
        addNotification({
          type: 'success',
          title: 'Reconnected',
          message: 'Connection restored successfully'
        });
      })
    );

    unsubscribes.push(
      wsService.on('error', (error: Error) => {
        setConnectionStatus('error');
        setMarketDataConnected(false);
        addNotification({
          type: 'error',
          title: 'WebSocket Error',
          message: error.message
        });
      })
    );

    // Data event handlers
    unsubscribes.push(
      wsService.on('market_data', (data: MarketData) => {
        updateMarketData(data.symbol, data);
      })
    );

    unsubscribes.push(
      wsService.on('market_data_batch', (data: MarketData[]) => {
        updateMultipleMarketData(data);
      })
    );

    unsubscribes.push(
      wsService.on('order_update', (order: Order) => {
        // Ensure WebSocket updates have proper sequence numbers and source
        const orderWithMeta = {
          ...order,
          sequence_number: order.sequence_number || Date.now(), // Fallback if not provided
          source: 'websocket' as const,
          updatedAt: new Date()
        };

        // Check if this is a new order or update
        const existingOrders = useTradingStore.getState().orders;
        const existing = existingOrders.find(o => o.id === order.id);

        if (existing) {
          // Update existing order (sequence number will be checked in updateOrder)
          updateOrder(order.id, orderWithMeta);
        } else {
          // Add new order
          addOrder(orderWithMeta);
        }
      })
    );

    unsubscribes.push(
      wsService.on('position_update', (position: Position) => {
        // Check if this is a new position or update
        const existingPositions = useTradingStore.getState().positions;
        const existing = existingPositions.find(p => p.id === position.id);

        if (existing) {
          updatePosition(position);
        } else {
          addPosition(position);
        }
      })
    );

    unsubscribes.push(
      wsService.on('account_update', (accountData: any) => {
        updateAccount(accountData);
      })
    );

    unsubscribes.push(
      wsService.on('signal_update', (signal: TradingSignal) => {
        addSignal(signal);
        addNotification({
          type: 'info',
          title: 'New Trading Signal',
          message: `${signal.signal_type.toUpperCase()} signal for ${signal.symbol} (${signal.confidence.toFixed(1)}% confidence)`
        });
      })
    );

    unsubscribes.push(
      wsService.on('system_alert', (alert: any) => {
        addNotification({
          type: alert.level || 'info',
          title: alert.title || 'System Alert',
          message: alert.message || 'System notification'
        });
      })
    );

    unsubscribes.push(
      wsService.on('broker_status', (status: any) => {
        // Handle broker status updates
        setSystemMetrics(prevMetrics => ({
          ...prevMetrics,
          brokerStatus: status
        }));
      })
    );

    // Store unsubscribe functions
    unsubscribeRefs.current = unsubscribes;

    return () => {
      unsubscribes.forEach(unsubscribe => unsubscribe());
    };
  }, [
    updateMarketData, updateMultipleMarketData, addOrder, updateOrder, addPosition, updatePosition,
    updateAccount, addSignal, setConnectionStatus, setMarketDataConnected,
    addNotification, setSystemMetrics
  ]);

  // Auto-connect on mount
  useEffect(() => {
    if (autoConnect && !isConnected && connectionStatus === 'disconnected') {
      connect();
    }
  }, [autoConnect, isConnected, connectionStatus, connect]);

  // Set up subscriptions when connected
  useEffect(() => {
    if (isConnected) {
      if (subscribeToMarketData && symbols.length > 0) {
        wsService.subscribeToMarketData(symbols);
      }

      if (subscribeToTradingUpdates) {
        wsService.subscribeToTradingUpdates();
      }

      if (subscribeToSignals) {
        wsService.subscribeToSignals();
      }

      if (subscribeToSystemUpdates) {
        wsService.subscribeToSystemUpdates();
      }
    }
  }, [isConnected, subscribeToMarketData, subscribeToTradingUpdates, subscribeToSignals, subscribeToSystemUpdates, symbols]);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (!autoConnect) {
        disconnect();
      }
    };
  }, [autoConnect, disconnect]);

  return {
    isConnected,
    connectionStatus,
    connect,
    disconnect,
    subscribeToSymbol,
    unsubscribeFromSymbol,
    requestMarketData,
    requestSignal
  };
}
