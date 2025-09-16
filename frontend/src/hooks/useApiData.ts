/**
 * API Data Hooks
 *
 * Custom hooks for fetching data from FXML4 backend API
 */

import { useState, useEffect, useCallback } from 'react';
import { apiClient } from '@/services/api';
import type { Account, Position, Order, MLModel, BacktestResult, TradingSignal } from '@/types';

interface ApiHookReturn<T> {
  data: T | null;
  loading: boolean;
  error: string | null;
  refresh: () => Promise<void>;
}

/**
 * Hook for fetching account data
 */
export function useAccount(): ApiHookReturn<Account> {
  const [data, setData] = useState<Account | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchData = useCallback(async () => {
    setLoading(true);
    setError(null);

    try {
      const accountData = await apiClient.getAccount();
      setData(accountData);
    } catch (err) {
      console.error('Failed to fetch account data:', err);
      setError(err instanceof Error ? err.message : 'Failed to fetch account data');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  return { data, loading, error, refresh: fetchData };
}

/**
 * Hook for fetching positions
 */
export function usePositions(): ApiHookReturn<Position[]> {
  const [data, setData] = useState<Position[] | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchData = useCallback(async () => {
    setLoading(true);
    setError(null);

    try {
      const positions = await apiClient.getPositions();
      setData(positions);
    } catch (err) {
      console.error('Failed to fetch positions:', err);
      setError(err instanceof Error ? err.message : 'Failed to fetch positions');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  return { data, loading, error, refresh: fetchData };
}

/**
 * Hook for fetching orders
 */
export function useOrders(): ApiHookReturn<Order[]> {
  const [data, setData] = useState<Order[] | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchData = useCallback(async () => {
    setLoading(true);
    setError(null);

    try {
      const orders = await apiClient.getOrders();
      setData(orders);
    } catch (err) {
      console.error('Failed to fetch orders:', err);
      setError(err instanceof Error ? err.message : 'Failed to fetch orders');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  return { data, loading, error, refresh: fetchData };
}

/**
 * Hook for fetching ML models
 */
export function useModels(): ApiHookReturn<MLModel[]> {
  const [data, setData] = useState<MLModel[] | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchData = useCallback(async () => {
    setLoading(true);
    setError(null);

    try {
      const models = await apiClient.getModels();
      setData(models);
    } catch (err) {
      console.error('Failed to fetch models:', err);
      setError(err instanceof Error ? err.message : 'Failed to fetch models');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  return { data, loading, error, refresh: fetchData };
}

/**
 * Hook for fetching backtest results
 */
export function useBacktests(): ApiHookReturn<BacktestResult[]> {
  const [data, setData] = useState<BacktestResult[] | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchData = useCallback(async () => {
    setLoading(true);
    setError(null);

    try {
      const backtests = await apiClient.getBacktestResults();
      setData(backtests);
    } catch (err) {
      console.error('Failed to fetch backtests:', err);
      setError(err instanceof Error ? err.message : 'Failed to fetch backtests');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  return { data, loading, error, refresh: fetchData };
}

/**
 * Hook for fetching trading signals
 */
export function useSignals(symbol?: string, limit: number = 50): ApiHookReturn<TradingSignal[]> {
  const [data, setData] = useState<TradingSignal[] | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchData = useCallback(async () => {
    setLoading(true);
    setError(null);

    try {
      const signals = await apiClient.getSignals(symbol, limit);
      setData(signals);
    } catch (err) {
      console.error('Failed to fetch signals:', err);
      setError(err instanceof Error ? err.message : 'Failed to fetch signals');
    } finally {
      setLoading(false);
    }
  }, [symbol, limit]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  return { data, loading, error, refresh: fetchData };
}

/**
 * Hook for aggregated dashboard statistics
 */
export function useDashboardStats() {
  const { data: account, loading: accountLoading, error: accountError } = useAccount();
  const { data: positions, loading: positionsLoading, error: positionsError } = usePositions();
  const { data: models, loading: modelsLoading, error: modelsError } = useModels();
  const { data: backtests, loading: backtestsLoading, error: backtestsError } = useBacktests();

  const stats = {
    activeModels: models?.filter(model => model.status === 'deployed').length || 0,
    totalModels: models?.length || 0,
    runningBacktests: backtests?.filter(backtest => backtest.status === 'running').length || 0,
    completedBacktests: backtests?.filter(backtest => backtest.status === 'completed').length || 0,
    openPositions: positions?.length || 0,
    totalPnL: account?.totalRealizedPnL || 0,
    unrealizedPnL: account?.totalUnrealizedPnL || 0,
    accountBalance: account?.balance || 0,
    accountEquity: account?.equity || 0,
    marginUsed: account?.marginUsed || 0,
    availableMargin: account?.availableMargin || 0
  };

  const loading = accountLoading || positionsLoading || modelsLoading || backtestsLoading;
  const error = accountError || positionsError || modelsError || backtestsError;

  return { stats, loading, error };
}

/**
 * Hook for system health status
 */
export function useSystemHealth(): ApiHookReturn<any> {
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchData = useCallback(async () => {
    setLoading(true);
    setError(null);

    try {
      const health = await apiClient.getSystemHealth();
      setData(health);
    } catch (err) {
      console.error('Failed to fetch system health:', err);
      setError(err instanceof Error ? err.message : 'Failed to fetch system health');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchData();

    // Poll system health every 30 seconds
    const interval = setInterval(fetchData, 30000);
    return () => clearInterval(interval);
  }, [fetchData]);

  return { data, loading, error, refresh: fetchData };
}

/**
 * Hook for periodic data refresh
 */
export function usePeriodicRefresh(callback: () => void, interval: number = 10000) {
  useEffect(() => {
    const intervalId = setInterval(callback, interval);
    return () => clearInterval(intervalId);
  }, [callback, interval]);
}
