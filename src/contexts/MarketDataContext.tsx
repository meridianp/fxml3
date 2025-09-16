import React, { createContext, useContext, useState, useEffect } from 'react';

interface MarketData {
  [symbol: string]: {
    price: number;
    bid: number;
    ask: number;
    volume: number;
    timestamp: Date;
  };
}

interface MarketDataContextType {
  marketData: MarketData;
  connectionStatus: 'connected' | 'disconnected' | 'connecting';
  subscribe: (symbols: string[]) => void;
  unsubscribe: (symbols: string[]) => void;
}

const MarketDataContext = createContext<MarketDataContextType | undefined>(undefined);

export const useMarketData = () => {
  const context = useContext(MarketDataContext);
  if (!context) {
    throw new Error('useMarketData must be used within a MarketDataProvider');
  }
  return context;
};

interface MarketDataProviderProps {
  children: React.ReactNode;
  initialData?: MarketData;
  connectionStatus?: 'connected' | 'disconnected' | 'connecting';
}

export const MarketDataProvider: React.FC<MarketDataProviderProps> = ({
  children,
  initialData = {},
  connectionStatus: initialStatus = 'connected'
}) => {
  const [marketData, setMarketData] = useState<MarketData>(initialData);
  const [connectionStatus, setConnectionStatus] = useState<'connected' | 'disconnected' | 'connecting'>(initialStatus);

  useEffect(() => {
    // Simulate real-time updates
    const interval = setInterval(() => {
      setMarketData(prev => {
        const updated = { ...prev };
        Object.keys(updated).forEach(symbol => {
          if (updated[symbol]) {
            updated[symbol] = {
              ...updated[symbol],
              price: updated[symbol].price + 0.0001,
              bid: updated[symbol].bid + 0.0001,
              ask: updated[symbol].ask + 0.0001,
              timestamp: new Date()
            };
          }
        });
        return updated;
      });
    }, 1000);

    return () => clearInterval(interval);
  }, []);

  const subscribe = (symbols: string[]) => {
    // Implementation for subscribing to symbols
  };

  const unsubscribe = (symbols: string[]) => {
    // Implementation for unsubscribing from symbols
  };

  return (
    <MarketDataContext.Provider value={{ marketData, connectionStatus, subscribe, unsubscribe }}>
      {children}
    </MarketDataContext.Provider>
  );
};
