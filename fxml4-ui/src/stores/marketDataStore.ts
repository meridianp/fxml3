/**
 * Market Data Store
 *
 * Manages real-time market data state using Zustand
 */

import { create } from 'zustand';
import { subscribeWithSelector } from 'zustand/middleware';
import type { MarketData, Candle, Symbol } from '@/types';

interface MarketDataState {
  // Current market data
  currentPrices: Record<string, MarketData>;
  symbols: Symbol[];
  isConnected: boolean;
  lastUpdate: number;

  // Historical data
  historicalData: Record<string, Candle[]>;
  isLoadingHistorical: Record<string, boolean>;

  // Subscriptions
  subscribedSymbols: Set<string>;

  // Actions
  updatePrice: (data: MarketData) => void;
  updatePrices: (data: MarketData[]) => void;
  setSymbols: (symbols: Symbol[]) => void;
  setConnected: (connected: boolean) => void;
  setHistoricalData: (symbol: string, data: Candle[]) => void;
  setLoadingHistorical: (symbol: string, loading: boolean) => void;
  subscribeToSymbol: (symbol: string) => void;
  unsubscribeFromSymbol: (symbol: string) => void;
  clearData: () => void;

  // Computed values
  getPrice: (symbol: string) => MarketData | undefined;
  getSpread: (symbol: string) => number;
  getPriceChange: (symbol: string) => { value: number; percentage: number } | undefined;
  getSymbolInfo: (symbol: string) => Symbol | undefined;
}

export const useMarketDataStore = create<MarketDataState>()(
  subscribeWithSelector((set, get) => ({
    // Initial state
    currentPrices: {},
    symbols: [],
    isConnected: false,
    lastUpdate: 0,
    historicalData: {},
    isLoadingHistorical: {},
    subscribedSymbols: new Set(),

    // Actions
    updatePrice: (data: MarketData) => {
      const current = get().currentPrices[data.symbol];
      const priceChanged = !current || current.bid !== data.bid || current.ask !== data.ask;

      set(state => ({
        currentPrices: {
          ...state.currentPrices,
          [data.symbol]: {
            ...data,
            // Add price change indicators
            bidChange: current ? (data.bid > current.bid ? 'up' : data.bid < current.bid ? 'down' : 'unchanged') : 'unchanged',
            askChange: current ? (data.ask > current.ask ? 'up' : data.ask < current.ask ? 'down' : 'unchanged') : 'unchanged',
          } as MarketData & { bidChange?: string; askChange?: string }
        },
        lastUpdate: Date.now()
      }));

      // Trigger price change animations
      if (priceChanged && typeof window !== 'undefined') {
        const event = new CustomEvent('priceUpdate', {
          detail: { symbol: data.symbol, data }
        });
        window.dispatchEvent(event);
      }
    },

    updatePrices: (dataArray: MarketData[]) => {
      set(state => {
        const newPrices = { ...state.currentPrices };

        dataArray.forEach(data => {
          const current = newPrices[data.symbol];
          newPrices[data.symbol] = {
            ...data,
            bidChange: current ? (data.bid > current.bid ? 'up' : data.bid < current.bid ? 'down' : 'unchanged') : 'unchanged',
            askChange: current ? (data.ask > current.ask ? 'up' : data.ask < current.ask ? 'down' : 'unchanged') : 'unchanged',
          } as MarketData & { bidChange?: string; askChange?: string };
        });

        return {
          currentPrices: newPrices,
          lastUpdate: Date.now()
        };
      });
    },

    setSymbols: (symbols: Symbol[]) => set({ symbols }),

    setConnected: (connected: boolean) => set({ isConnected: connected }),

    setHistoricalData: (symbol: string, data: Candle[]) => {
      set(state => ({
        historicalData: {
          ...state.historicalData,
          [symbol]: data
        }
      }));
    },

    setLoadingHistorical: (symbol: string, loading: boolean) => {
      set(state => ({
        isLoadingHistorical: {
          ...state.isLoadingHistorical,
          [symbol]: loading
        }
      }));
    },

    subscribeToSymbol: (symbol: string) => {
      set(state => ({
        subscribedSymbols: new Set([...state.subscribedSymbols, symbol])
      }));
    },

    unsubscribeFromSymbol: (symbol: string) => {
      set(state => {
        const newSet = new Set(state.subscribedSymbols);
        newSet.delete(symbol);
        return { subscribedSymbols: newSet };
      });
    },

    clearData: () => set({
      currentPrices: {},
      historicalData: {},
      subscribedSymbols: new Set(),
      lastUpdate: 0
    }),

    // Computed values
    getPrice: (symbol: string) => {
      return get().currentPrices[symbol];
    },

    getSpread: (symbol: string) => {
      const price = get().currentPrices[symbol];
      return price ? price.ask - price.bid : 0;
    },

    getPriceChange: (symbol: string) => {
      const current = get().currentPrices[symbol];
      const historical = get().historicalData[symbol];

      if (!current || !historical || historical.length === 0) {
        return undefined;
      }

      const previousClose = historical[historical.length - 1].close;
      const currentPrice = (current.bid + current.ask) / 2;
      const change = currentPrice - previousClose;
      const percentage = (change / previousClose) * 100;

      return { value: change, percentage };
    },

    getSymbolInfo: (symbol: string) => {
      return get().symbols.find(s => s.symbol === symbol);
    }
  }))
);
