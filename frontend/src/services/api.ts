/**
 * API service layer for FXML4 trading platform
 *
 * Provides type-safe API client for all backend interactions
 */

import axios, { AxiosInstance, AxiosRequestConfig, AxiosResponse } from 'axios';
import { API_CONFIG, ERROR_MESSAGES } from '@/config/constants';
import { AuthService } from '@/services/auth';
import type {
  ApiResponse,
  PaginatedResponse,
  MarketData,
  Candle,
  Symbol,
  Order,
  Position,
  TradingSignal,
  Account,
  MLModel,
  TrainingConfig,
  TrainingProgress,
  BacktestConfig,
  BacktestResult,
  BrokerAdapter,
} from '@/types';

// Request/Response interceptor types
interface ApiError {
  message: string;
  code?: string;
  status?: number;
}

class ApiErrorClass extends Error {
  code?: string;
  status?: number;

  constructor(message: string, code?: string, status?: number) {
    super(message);
    this.name = 'ApiError';
    this.code = code;
    this.status = status;
  }
}

class ApiClient {
  private client: AxiosInstance;
  private authToken: string | null = null;

  constructor() {
    this.client = axios.create({
      baseURL: API_CONFIG.baseURL,
      timeout: API_CONFIG.timeout,
      headers: {
        'Content-Type': 'application/json',
      },
    });

    // Initialize with development token
    this.authToken = AuthService.getToken();
    this.setupInterceptors();
  }

  private setupInterceptors() {
    // Request interceptor for auth token
    this.client.interceptors.request.use(
      (config) => {
        // Always use the latest token from AuthService
        const currentToken = AuthService.getToken();
        if (currentToken) {
          config.headers.Authorization = `Bearer ${currentToken}`;
          this.authToken = currentToken;
        }
        return config;
      },
      (error) => Promise.reject(error)
    );

    // Response interceptor for error handling
    this.client.interceptors.response.use(
      (response) => response,
      async (error) => {
        const originalRequest = error.config;

        // Handle 401 unauthorized - attempt token refresh
        if (error.response?.status === 401 && !originalRequest._retry) {
          originalRequest._retry = true;

          try {
            await this.refreshToken();
            return this.client(originalRequest);
          } catch (refreshError) {
            this.logout();
            throw new ApiErrorClass('Session expired. Please log in again.');
          }
        }

        // Transform error to standard format
        const apiError: ApiError = {
          message: this.getErrorMessage(error),
          code: error.response?.data?.code,
          status: error.response?.status,
        };

        return Promise.reject(apiError);
      }
    );
  }

  private getErrorMessage(error: any): string {
    if (error.response?.data?.message) {
      return error.response.data.message;
    }

    switch (error.response?.status) {
      case 401:
        return ERROR_MESSAGES.unauthorized;
      case 403:
        return ERROR_MESSAGES.forbidden;
      case 404:
        return ERROR_MESSAGES.notFound;
      case 500:
        return ERROR_MESSAGES.serverError;
      default:
        return error.message || ERROR_MESSAGES.network;
    }
  }

  // Authentication methods
  async login(username: string, password: string): Promise<string> {
    const response = await this.client.post<ApiResponse<{ access_token: string }>>('/auth/login', {
      username,
      password,
    });

    if (response.data.success && response.data.data?.access_token) {
      this.authToken = response.data.data.access_token;
      localStorage.setItem('fxml4_auth_token', this.authToken);
      return this.authToken;
    }

    throw new Error('Login failed');
  }

  async refreshToken(): Promise<string> {
    const refreshToken = localStorage.getItem('fxml4_refresh_token');
    if (!refreshToken) {
      throw new Error('No refresh token available');
    }

    const response = await this.client.post<ApiResponse<{ access_token: string }>>('/auth/refresh', {
      refresh_token: refreshToken,
    });

    if (response.data.success && response.data.data?.access_token) {
      this.authToken = response.data.data.access_token;
      localStorage.setItem('fxml4_auth_token', this.authToken);
      return this.authToken;
    }

    throw new Error('Token refresh failed');
  }

  logout(): void {
    this.authToken = null;
    localStorage.removeItem('fxml4_auth_token');
    localStorage.removeItem('fxml4_refresh_token');
  }

  setAuthToken(token: string): void {
    this.authToken = token;
  }

  // Market data endpoints
  async getMarketData(symbol: string, timeframe: string = '1h', limit: number = 100): Promise<Candle[]> {
    const response = await this.client.get<ApiResponse<Candle[]>>('/data/candles', {
      params: { symbol, timeframe, limit },
    });
    return response.data.data || [];
  }

  async getSymbols(): Promise<Symbol[]> {
    const response = await this.client.get<ApiResponse<Symbol[]>>('/data/symbols');
    return response.data.data || [];
  }

  async getCurrentPrices(symbols?: string[]): Promise<MarketData[]> {
    const response = await this.client.get<ApiResponse<MarketData[]>>('/data/current', {
      params: symbols ? { symbols: symbols.join(',') } : {},
    });
    return response.data.data || [];
  }

  // Trading endpoints
  async getAccount(): Promise<Account> {
    const response = await this.client.get<ApiResponse<Account>>('/trading/account');
    if (!response.data.data) throw new Error('Account data not available');
    return response.data.data;
  }

  async getPositions(): Promise<Position[]> {
    const response = await this.client.get<ApiResponse<Position[]>>('/trading/positions');
    return response.data.data || [];
  }

  async getOrders(): Promise<Order[]> {
    const response = await this.client.get<ApiResponse<Order[]>>('/trading/orders');
    return response.data.data || [];
  }

  async placeOrder(order: Partial<Order>): Promise<Order> {
    const response = await this.client.post<ApiResponse<Order>>('/trading/orders', order);
    if (!response.data.data) throw new Error('Order placement failed');
    return response.data.data;
  }

  async cancelOrder(orderId: string): Promise<void> {
    await this.client.delete(`/trading/orders/${orderId}`);
  }

  async closePosition(positionId: string): Promise<void> {
    await this.client.post(`/trading/positions/${positionId}/close`);
  }

  // Signal endpoints
  async getSignals(symbol?: string, limit: number = 50): Promise<TradingSignal[]> {
    const response = await this.client.get<ApiResponse<TradingSignal[]>>('/signals', {
      params: { symbol, limit },
    });
    return response.data.data || [];
  }

  async generateSignal(symbol: string, modelName?: string): Promise<TradingSignal> {
    const response = await this.client.post<ApiResponse<TradingSignal>>('/signals/generate', {
      symbol,
      model_name: modelName,
    });
    if (!response.data.data) throw new Error('Signal generation failed');
    return response.data.data;
  }

  // ML Model endpoints
  async getModels(): Promise<MLModel[]> {
    try {
      // Note: Backend doesn't have /ml/models endpoint yet
      // Return empty array with clear development status
      console.warn('ML Models endpoint not implemented - returning empty array');
      return [];
    } catch (error) {
      console.error('Failed to fetch ML models:', error);
      return [];
    }
  }

  async createModel(config: TrainingConfig): Promise<MLModel> {
    const response = await this.client.post<ApiResponse<MLModel>>('/ml/models', config);
    if (!response.data.data) throw new Error('Model creation failed');
    return response.data.data;
  }

  async trainModel(modelId: string): Promise<void> {
    await this.client.post(`/ml/models/${modelId}/train`);
  }

  async getTrainingProgress(modelId: string): Promise<TrainingProgress> {
    const response = await this.client.get<ApiResponse<TrainingProgress>>(`/ml/models/${modelId}/progress`);
    if (!response.data.data) throw new Error('Training progress not available');
    return response.data.data;
  }

  async deployModel(modelId: string): Promise<void> {
    await this.client.post(`/ml/models/${modelId}/deploy`);
  }

  // Backtesting endpoints
  async runBacktest(config: BacktestConfig): Promise<BacktestResult> {
    const response = await this.client.post<ApiResponse<BacktestResult>>('/backtest', config);
    if (!response.data.data) throw new Error('Backtest failed to start');
    return response.data.data;
  }

  async getBacktestResults(backtestId?: string): Promise<BacktestResult[]> {
    try {
      // Note: Backend /backtest is POST-only for running backtests, not for retrieving results
      // Return empty array until backend implements results storage/retrieval
      console.warn('Backtest results endpoint not implemented - returning empty array');
      return [];
    } catch (error) {
      console.error('Failed to fetch backtest results:', error);
      return [];
    }
  }

  async getBacktestResult(backtestId: string): Promise<BacktestResult> {
    const response = await this.client.get<ApiResponse<BacktestResult>>(`/backtest/${backtestId}`);
    if (!response.data.data) throw new Error('Backtest result not found');
    return response.data.data;
  }

  // Broker adapter endpoints
  async getBrokerAdapters(): Promise<BrokerAdapter[]> {
    const response = await this.client.get<ApiResponse<BrokerAdapter[]>>('/brokers');
    return response.data.data || [];
  }

  async getBrokerStatus(adapterId: string): Promise<BrokerAdapter> {
    const response = await this.client.get<ApiResponse<BrokerAdapter>>(`/brokers/${adapterId}/status`);
    if (!response.data.data) throw new Error('Broker status not available');
    return response.data.data;
  }

  // Monitoring endpoints
  async getSystemHealth(): Promise<{ status: string; services: Record<string, any> }> {
    const response = await this.client.get<ApiResponse<any>>('/health');
    return response.data.data || { status: 'unknown', services: {} };
  }

  async getMetrics(): Promise<any> {
    const response = await this.client.get<ApiResponse<any>>('/monitoring/metrics/summary');
    return response.data.data || {};
  }

  // Generic request methods
  async get<T>(url: string, config?: AxiosRequestConfig): Promise<T> {
    const response = await this.client.get<ApiResponse<T>>(url, config);
    if (!response.data.data) throw new Error('No data received');
    return response.data.data;
  }

  async post<T>(url: string, data?: any, config?: AxiosRequestConfig): Promise<T> {
    const response = await this.client.post<ApiResponse<T>>(url, data, config);
    if (!response.data.data) throw new Error('No data received');
    return response.data.data;
  }

  async put<T>(url: string, data?: any, config?: AxiosRequestConfig): Promise<T> {
    const response = await this.client.put<ApiResponse<T>>(url, data, config);
    if (!response.data.data) throw new Error('No data received');
    return response.data.data;
  }

  async delete<T>(url: string, config?: AxiosRequestConfig): Promise<T> {
    const response = await this.client.delete<ApiResponse<T>>(url, config);
    return response.data.data!;
  }
}

// Export singleton instance
export const apiClient = new ApiClient();
export const api = apiClient; // Compatibility export for tests
export default apiClient;
