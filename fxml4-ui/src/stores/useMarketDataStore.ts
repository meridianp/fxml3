import { create } from 'zustand';
import { devtools } from 'zustand/middleware';

export interface MarketDataPoint {
  symbol: string;
  bid: number;
  ask: number;
  last: number;
  change: number;
  changePercent: number;
  volume: number;
  timestamp: Date;
  session: 'london' | 'new_york' | 'tokyo' | 'sydney' | 'closed';
}

export interface PriceData {
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
  timestamp: Date;
}

export interface MarketDataState {
  // Real-time data
  marketData: Record<string, MarketDataPoint>;
  selectedSymbol: string;
  subscribedSymbols: string[];

  // Historical data
  historicalData: Record<string, PriceData[]>;
  selectedTimeframe: '1m' | '5m' | '15m' | '1h' | '4h' | '1d' | '1w';

  // Data quality
  staleSymbols: Set<string>;
  lastUpdateTime: Date | null;

  // Connection
  isConnected: boolean;
  reconnectAttempts: number;
}

interface MarketDataActions {
  // Symbol management
  setSelectedSymbol: (symbol: string) => void;
  subscribeToSymbol: (symbol: string) => void;
  unsubscribeFromSymbol: (symbol: string) => void;

  // Market data updates
  updateMarketData: (data: MarketDataPoint) => void;
  updateMultipleMarketData: (data: MarketDataPoint[]) => void;

  // Historical data
  setHistoricalData: (symbol: string, data: PriceData[]) => void;
  setTimeframe: (timeframe: MarketDataState['selectedTimeframe']) => void;

  // Data quality
  markSymbolStale: (symbol: string) => void;
  markSymbolFresh: (symbol: string) => void;
  setLastUpdateTime: (time: Date) => void;

  // Connection
  setConnectionStatus: (connected: boolean) => void;
  incrementReconnectAttempts: () => void;
  resetReconnectAttempts: () => void;

  // Utilities
  getSymbolData: (symbol: string) => MarketDataPoint | undefined;
  getHistoricalData: (symbol: string, timeframe?: string) => PriceData[];
  isSymbolStale: (symbol: string) => boolean;

  // Reset
  reset: () => void;
}

const initialState: MarketDataState = {
  marketData: {},
  selectedSymbol: 'EURUSD',
  subscribedSymbols: ['EURUSD', 'GBPUSD', 'USDJPY', 'USDCHF'],
  historicalData: {},
  selectedTimeframe: '1h',
  staleSymbols: new Set(),
  lastUpdateTime: null,
  isConnected: false,
  reconnectAttempts: 0,
};

export const useMarketDataStore = create<MarketDataState & MarketDataActions>()(
  devtools(
    (set, get) => ({
      ...initialState,

      // Symbol management
      setSelectedSymbol: (symbol) => {
        set({ selectedSymbol: symbol }, false, 'setSelectedSymbol');
      },

      subscribeToSymbol: (symbol) => {
        set(
          (state) => ({
            subscribedSymbols: state.subscribedSymbols.includes(symbol)
              ? state.subscribedSymbols
              : [...state.subscribedSymbols, symbol],
          }),
          false,
          'subscribeToSymbol'
        );
      },

      unsubscribeFromSymbol: (symbol) => {
        set(
          (state) => ({
            subscribedSymbols: state.subscribedSymbols.filter((s) => s !== symbol),
            marketData: Object.fromEntries(
              Object.entries(state.marketData).filter(([key]) => key !== symbol)
            ),
          }),
          false,
          'unsubscribeFromSymbol'
        );
      },

      // Market data updates
      updateMarketData: (data) => {
        set(
          (state) => {
            const newStaleSymbols = new Set(state.staleSymbols);
            newStaleSymbols.delete(data.symbol);

            return {
              marketData: {
                ...state.marketData,
                [data.symbol]: data,
              },
              staleSymbols: newStaleSymbols,
              lastUpdateTime: new Date(),
            };
          },
          false,
          'updateMarketData'
        );
      },

      updateMultipleMarketData: (dataArray) => {
        set(
          (state) => {
            const newMarketData = { ...state.marketData };
            const newStaleSymbols = new Set(state.staleSymbols);

            dataArray.forEach((data) => {
              newMarketData[data.symbol] = data;
              newStaleSymbols.delete(data.symbol);
            });

            return {
              marketData: newMarketData,
              staleSymbols: newStaleSymbols,
              lastUpdateTime: new Date(),
            };
          },
          false,
          'updateMultipleMarketData'
        );
      },

      // Historical data
      setHistoricalData: (symbol, data) => {
        set(
          (state) => ({
            historicalData: {
              ...state.historicalData,
              [`${symbol}-${state.selectedTimeframe}`]: data,
            },
          }),
          false,
          'setHistoricalData'
        );
      },

      setTimeframe: (timeframe) => {
        set({ selectedTimeframe: timeframe }, false, 'setTimeframe');
      },

      // Data quality
      markSymbolStale: (symbol) => {
        set(
          (state) => ({
            staleSymbols: new Set([...state.staleSymbols, symbol]),
          }),
          false,
          'markSymbolStale'
        );
      },

      markSymbolFresh: (symbol) => {
        set(
          (state) => {
            const newStaleSymbols = new Set(state.staleSymbols);
            newStaleSymbols.delete(symbol);
            return { staleSymbols: newStaleSymbols };
          },
          false,
          'markSymbolFresh'
        );
      },

      setLastUpdateTime: (time) => {
        set({ lastUpdateTime: time }, false, 'setLastUpdateTime');
      },

      // Connection
      setConnectionStatus: (connected) => {
        set(
          (state) => ({
            isConnected: connected,
            reconnectAttempts: connected ? 0 : state.reconnectAttempts,
            staleSymbols: connected ? new Set() : new Set(state.subscribedSymbols),
          }),
          false,
          'setConnectionStatus'
        );
      },

      incrementReconnectAttempts: () => {
        set(
          (state) => ({ reconnectAttempts: state.reconnectAttempts + 1 }),
          false,
          'incrementReconnectAttempts'
        );
      },

      resetReconnectAttempts: () => {
        set({ reconnectAttempts: 0 }, false, 'resetReconnectAttempts');
      },

      // Utilities
      getSymbolData: (symbol) => {
        return get().marketData[symbol];
      },

      getHistoricalData: (symbol, timeframe) => {
        const tf = timeframe || get().selectedTimeframe;
        return get().historicalData[`${symbol}-${tf}`] || [];
      },

      isSymbolStale: (symbol) => {
        return get().staleSymbols.has(symbol);
      },

      // Reset
      reset: () => {
        set(initialState, false, 'reset');
      },
    }),
    {
      name: 'market-data-store',
    }
  )
);
