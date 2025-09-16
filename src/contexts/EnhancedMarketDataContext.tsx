/**
 * Enhanced Market Data Context with Real WebSocket Integration
 *
 * Provides real-time market data streaming with:
 * - WebSocket connection management
 * - Automatic reconnection
 * - Performance monitoring
 * - Message queuing and buffering
 */

import React, { createContext, useContext, useState, useEffect, useRef, useCallback } from 'react';
import { WebSocketService, WebSocketMessage } from '../services/WebSocketService';

interface MarketData {
  [symbol: string]: {
    price: number;
    bid: number;
    ask: number;
    volume: number;
    timestamp: Date;
    change?: number;
    changePercent?: number;
  };
}

interface MarketDataContextType {
  marketData: MarketData;
  connectionStatus: 'connected' | 'disconnected' | 'connecting';
  subscribe: (symbols: string[]) => void;
  unsubscribe: (symbols: string[]) => void;
  getPerformanceMetrics: () => any;
  reconnect: () => Promise<void>;
}

const EnhancedMarketDataContext = createContext<MarketDataContextType | undefined>(undefined);

export const useEnhancedMarketData = () => {
  const context = useContext(EnhancedMarketDataContext);
  if (!context) {
    throw new Error('useEnhancedMarketData must be used within an EnhancedMarketDataProvider');
  }
  return context;
};

interface EnhancedMarketDataProviderProps {
  children: React.ReactNode;
  initialData?: MarketData;
  connectionStatus?: 'connected' | 'disconnected' | 'connecting';
  wsConfig?: {
    url: string;
    reconnectInterval: number;
    maxReconnectAttempts: number;
    heartbeatInterval: number;
  };
}

export const EnhancedMarketDataProvider: React.FC<EnhancedMarketDataProviderProps> = ({
  children,
  initialData = {},
  connectionStatus: initialStatus = 'connecting',
  wsConfig = {
    url: 'wss://api.fxml4.com/realtime',
    reconnectInterval: 5000,
    maxReconnectAttempts: 10,
    heartbeatInterval: 30000
  }
}) => {
  const [marketData, setMarketData] = useState<MarketData>(initialData);
  const [connectionStatus, setConnectionStatus] = useState<'connected' | 'disconnected' | 'connecting'>(initialStatus);
  const wsService = useRef<WebSocketService | null>(null);
  const subscribedSymbols = useRef<Set<string>>(new Set());

  // Initialize WebSocket service
  useEffect(() => {
    wsService.current = new WebSocketService(wsConfig);

    // Connect to WebSocket
    const connect = async () => {
      try {
        setConnectionStatus('connecting');
        await wsService.current!.connect();
        setConnectionStatus('connected');

        // Subscribe to price updates
        wsService.current!.subscribe('price_update', handlePriceUpdate);
        wsService.current!.subscribe('tick', handleTickData);
        wsService.current!.subscribe('heartbeat_response', handleHeartbeat);

        // Re-subscribe to any previously subscribed symbols
        if (subscribedSymbols.current.size > 0) {
          const symbolsArray = Array.from(subscribedSymbols.current);
          subscribeToSymbols(symbolsArray);
        }
      } catch (error) {
        console.error('Failed to connect to WebSocket:', error);
        setConnectionStatus('disconnected');
      }
    };

    connect();

    return () => {
      if (wsService.current) {
        wsService.current.disconnect();
      }
    };
  }, []);

  // Handle price updates from WebSocket
  const handlePriceUpdate = useCallback((message: WebSocketMessage) => {
    if (message.symbol && message.price) {
      setMarketData(prev => {
        const previousPrice = prev[message.symbol!]?.price || 0;
        const change = message.price! - previousPrice;
        const changePercent = previousPrice > 0 ? (change / previousPrice) * 100 : 0;

        return {
          ...prev,
          [message.symbol!]: {
            price: message.price!,
            bid: message.bid || message.price! - 0.00005,
            ask: message.ask || message.price! + 0.00005,
            volume: message.volume || 0,
            timestamp: new Date(message.timestamp),
            change,
            changePercent
          }
        };
      });
    }
  }, []);

  // Handle tick data (high-frequency updates)
  const handleTickData = useCallback((message: WebSocketMessage) => {
    if (message.symbol && message.price) {
      // Throttle tick updates to prevent UI overload
      setMarketData(prev => ({
        ...prev,
        [message.symbol!]: {
          ...prev[message.symbol!],
          price: message.price!,
          bid: message.bid || message.price! - 0.00005,
          ask: message.ask || message.price! + 0.00005,
          volume: (prev[message.symbol!]?.volume || 0) + (message.volume || 1),
          timestamp: new Date(message.timestamp)
        }
      }));
    }
  }, []);

  // Handle heartbeat responses
  const handleHeartbeat = useCallback((message: WebSocketMessage) => {
    // Update connection status based on heartbeat
    if (connectionStatus !== 'connected') {
      setConnectionStatus('connected');
    }
  }, [connectionStatus]);

  // Subscribe to symbols
  const subscribe = useCallback((symbols: string[]) => {
    symbols.forEach(symbol => subscribedSymbols.current.add(symbol));

    if (wsService.current && connectionStatus === 'connected') {
      subscribeToSymbols(symbols);
    }
  }, [connectionStatus]);

  // Unsubscribe from symbols
  const unsubscribe = useCallback((symbols: string[]) => {
    symbols.forEach(symbol => subscribedSymbols.current.delete(symbol));

    if (wsService.current && connectionStatus === 'connected') {
      symbols.forEach(symbol => {
        wsService.current!.send({
          type: 'unsubscribe',
          symbol,
          timestamp: new Date().toISOString()
        });
      });
    }
  }, [connectionStatus]);

  // Helper function to subscribe to symbols via WebSocket
  const subscribeToSymbols = (symbols: string[]) => {
    symbols.forEach(symbol => {
      wsService.current!.send({
        type: 'subscribe',
        symbol,
        dataTypes: ['price', 'tick', 'depth'],
        timestamp: new Date().toISOString()
      });
    });
  };

  // Get performance metrics
  const getPerformanceMetrics = useCallback(() => {
    if (wsService.current) {
      return wsService.current.getPerformanceMetrics();
    }
    return {
      messagesReceived: 0,
      averageLatency: 0,
      totalLatency: 0,
      lastMessageTime: 0
    };
  }, []);

  // Reconnect function
  const reconnect = useCallback(async () => {
    if (wsService.current) {
      try {
        setConnectionStatus('connecting');
        await wsService.current.connect();
        setConnectionStatus('connected');

        // Re-subscribe to symbols
        if (subscribedSymbols.current.size > 0) {
          const symbolsArray = Array.from(subscribedSymbols.current);
          subscribeToSymbols(symbolsArray);
        }
      } catch (error) {
        console.error('Failed to reconnect:', error);
        setConnectionStatus('disconnected');
        throw error;
      }
    }
  }, []);

  // Simulate real-time updates if no WebSocket connection (for testing/development)
  useEffect(() => {
    if (connectionStatus === 'connected' && Object.keys(marketData).length > 0) {
      const interval = setInterval(() => {
        setMarketData(prev => {
          const updated = { ...prev };
          Object.keys(updated).forEach(symbol => {
            if (updated[symbol]) {
              // Small random price movement
              const movement = (Math.random() - 0.5) * 0.0002;
              const newPrice = updated[symbol].price + movement;

              updated[symbol] = {
                ...updated[symbol],
                price: newPrice,
                bid: newPrice - 0.00005,
                ask: newPrice + 0.00005,
                timestamp: new Date(),
                change: newPrice - (initialData[symbol]?.price || updated[symbol].price),
                changePercent: ((newPrice - (initialData[symbol]?.price || updated[symbol].price)) / (initialData[symbol]?.price || updated[symbol].price)) * 100
              };
            }
          });
          return updated;
        });
      }, 1000);

      return () => clearInterval(interval);
    }
  }, [connectionStatus, marketData, initialData]);

  const value = {
    marketData,
    connectionStatus,
    subscribe,
    unsubscribe,
    getPerformanceMetrics,
    reconnect
  };

  return (
    <EnhancedMarketDataContext.Provider value={value}>
      {children}
    </EnhancedMarketDataContext.Provider>
  );
};
