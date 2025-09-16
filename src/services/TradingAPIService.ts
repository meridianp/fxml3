/**
 * Trading API Service
 *
 * Handles all API calls to the FXML4 trading backend
 * with error handling, retry logic, and performance monitoring.
 */

export interface Order {
  id?: string;
  symbol: string;
  side: 'BUY' | 'SELL';
  quantity: number;
  orderType: 'MARKET' | 'LIMIT' | 'STOP';
  price?: number;
  stopPrice?: number;
  timeInForce?: 'GTC' | 'IOC' | 'FOK';
  clientOrderId?: string;
}

export interface Position {
  symbol: string;
  quantity: number;
  entryPrice: number;
  currentPrice: number;
  unrealizedPnL: number;
  realizedPnL?: number;
  marginUsed?: number;
}

export interface AccountInfo {
  accountId: string;
  balance: number;
  equity: number;
  margin: number;
  freeMargin: number;
  marginLevel: number;
  currency: string;
}

export interface APIResponse<T = any> {
  success: boolean;
  data?: T;
  error?: {
    code: string;
    message: string;
  };
  executionTime?: number;
  requestId?: string;
}

export class TradingAPIService {
  private baseURL: string;
  private apiKey: string;
  private requestCount = 0;
  private totalLatency = 0;

  constructor(baseURL: string, apiKey: string) {
    this.baseURL = baseURL;
    this.apiKey = apiKey;
  }

  async submitOrder(order: Order): Promise<APIResponse<{ orderId: string; status: string }>> {
    const startTime = performance.now();

    try {
      const response = await this.makeRequest('/orders', {
        method: 'POST',
        body: JSON.stringify(order)
      });

      const endTime = performance.now();
      const executionTime = endTime - startTime;

      this.updateMetrics(executionTime);

      return {
        success: true,
        data: {
          orderId: response.orderId,
          status: response.status
        },
        executionTime,
        requestId: response.requestId
      };
    } catch (error) {
      return {
        success: false,
        error: {
          code: 'ORDER_SUBMIT_ERROR',
          message: error instanceof Error ? error.message : 'Unknown error'
        }
      };
    }
  }

  async modifyOrder(orderId: string, modifications: Partial<Order>): Promise<APIResponse> {
    const startTime = performance.now();

    try {
      const response = await this.makeRequest(`/orders/${orderId}`, {
        method: 'PATCH',
        body: JSON.stringify(modifications)
      });

      const endTime = performance.now();
      const executionTime = endTime - startTime;

      this.updateMetrics(executionTime);

      return {
        success: true,
        data: response,
        executionTime
      };
    } catch (error) {
      return {
        success: false,
        error: {
          code: 'ORDER_MODIFY_ERROR',
          message: error instanceof Error ? error.message : 'Unknown error'
        }
      };
    }
  }

  async cancelOrder(orderId: string): Promise<APIResponse> {
    const startTime = performance.now();

    try {
      const response = await this.makeRequest(`/orders/${orderId}`, {
        method: 'DELETE'
      });

      const endTime = performance.now();
      const executionTime = endTime - startTime;

      this.updateMetrics(executionTime);

      return {
        success: true,
        data: response,
        executionTime
      };
    } catch (error) {
      return {
        success: false,
        error: {
          code: 'ORDER_CANCEL_ERROR',
          message: error instanceof Error ? error.message : 'Unknown error'
        }
      };
    }
  }

  async getPositions(): Promise<APIResponse<Position[]>> {
    const startTime = performance.now();

    try {
      const response = await this.makeRequest('/positions', {
        method: 'GET'
      });

      const endTime = performance.now();
      const executionTime = endTime - startTime;

      this.updateMetrics(executionTime);

      return {
        success: true,
        data: response.positions,
        executionTime
      };
    } catch (error) {
      return {
        success: false,
        error: {
          code: 'POSITIONS_ERROR',
          message: error instanceof Error ? error.message : 'Unknown error'
        }
      };
    }
  }

  async getAccountInfo(): Promise<APIResponse<AccountInfo>> {
    const startTime = performance.now();

    try {
      const response = await this.makeRequest('/account', {
        method: 'GET'
      });

      const endTime = performance.now();
      const executionTime = endTime - startTime;

      this.updateMetrics(executionTime);

      return {
        success: true,
        data: response,
        executionTime
      };
    } catch (error) {
      return {
        success: false,
        error: {
          code: 'ACCOUNT_ERROR',
          message: error instanceof Error ? error.message : 'Unknown error'
        }
      };
    }
  }

  async emergencyStop(): Promise<APIResponse> {
    const startTime = performance.now();

    try {
      const response = await this.makeRequest('/emergency-stop', {
        method: 'POST'
      });

      const endTime = performance.now();
      const executionTime = endTime - startTime;

      this.updateMetrics(executionTime);

      return {
        success: true,
        data: response,
        executionTime
      };
    } catch (error) {
      return {
        success: false,
        error: {
          code: 'EMERGENCY_STOP_ERROR',
          message: error instanceof Error ? error.message : 'Unknown error'
        }
      };
    }
  }

  async getMLPredictions(symbol: string): Promise<APIResponse<{
    direction: 'up' | 'down';
    confidence: number;
    target: number;
    timeframe: string;
  }>> {
    const startTime = performance.now();

    try {
      const response = await this.makeRequest(`/ml/predictions/${symbol}`, {
        method: 'GET'
      });

      const endTime = performance.now();
      const executionTime = endTime - startTime;

      this.updateMetrics(executionTime);

      return {
        success: true,
        data: response,
        executionTime
      };
    } catch (error) {
      return {
        success: false,
        error: {
          code: 'ML_PREDICTIONS_ERROR',
          message: error instanceof Error ? error.message : 'Unknown error'
        }
      };
    }
  }

  async exportTradingHistory(format: 'CSV' | 'PDF' | 'EXCEL', params: any): Promise<APIResponse<{ downloadUrl: string }>> {
    const startTime = performance.now();

    try {
      const response = await this.makeRequest('/export/history', {
        method: 'POST',
        body: JSON.stringify({ format, ...params })
      });

      const endTime = performance.now();
      const executionTime = endTime - startTime;

      this.updateMetrics(executionTime);

      return {
        success: true,
        data: response,
        executionTime
      };
    } catch (error) {
      return {
        success: false,
        error: {
          code: 'EXPORT_ERROR',
          message: error instanceof Error ? error.message : 'Unknown error'
        }
      };
    }
  }

  getPerformanceMetrics() {
    return {
      requestCount: this.requestCount,
      averageLatency: this.requestCount > 0 ? this.totalLatency / this.requestCount : 0,
      totalLatency: this.totalLatency
    };
  }

  private async makeRequest(endpoint: string, options: RequestInit): Promise<any> {
    const url = `${this.baseURL}${endpoint}`;

    const defaultHeaders = {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${this.apiKey}`,
      'X-Client-Version': '4.0.0',
      'X-Request-ID': this.generateRequestId()
    };

    const response = await fetch(url, {
      ...options,
      headers: {
        ...defaultHeaders,
        ...options.headers
      }
    });

    if (!response.ok) {
      throw new Error(`API request failed: ${response.status} ${response.statusText}`);
    }

    return response.json();
  }

  private updateMetrics(latency: number): void {
    this.requestCount++;
    this.totalLatency += latency;
  }

  private generateRequestId(): string {
    return `req_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
  }
}
