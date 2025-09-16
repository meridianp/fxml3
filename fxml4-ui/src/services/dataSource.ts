/**
 * DataSourceService
 *
 * Service for managing data source connections and monitoring
 */

import { EventEmitter } from 'events';
import {
  DataSource,
  ConnectionStatus,
  DataSourceType,
  DataQualityLevel,
} from '@/types/dataManagement';

export interface DataSourceCreateData {
  name: string;
  type: DataSourceType;
  url?: string;
  description?: string;
  tags?: string[];
  timeout?: number;
  enabled?: boolean;
}

export interface DataSourceUpdateData {
  name?: string;
  url?: string;
  description?: string;
  tags?: string[];
  timeout?: number;
  enabled?: boolean;
}

export interface ConnectionTestResult {
  status: string;
  latency?: number;
  error?: string;
  timestamp: Date;
}

export interface ConnectionStatusUpdate {
  id: string;
  status: ConnectionStatus;
  latency?: number | null;
  lastUpdate: Date;
  errorMessage?: string;
}

export interface PerformanceMetrics {
  timestamp: string;
  sources: Array<{
    id: string;
    latency: number;
    throughput: number;
    errorRate: number;
    uptime: number;
  }>;
  summary: {
    totalSources: number;
    connectedSources: number;
    avgLatency: number;
    avgThroughput: number;
    avgUptime: number;
  };
}

export interface PerformanceHistoryQuery {
  start: Date;
  end: Date;
  interval: string; // e.g., '5m', '1h', '1d'
}

export interface PerformanceHistoryData {
  timestamp: string;
  latency: number;
  throughput: number;
  errorRate: number;
  uptime?: number;
}

export interface DiscoveredSource {
  type: DataSourceType;
  name: string;
  url: string;
  detected: boolean;
  configuration?: Record<string, any>;
}

export interface HealthCheckResult {
  sourceId: string;
  healthy: boolean;
  checks: Array<{
    name: string;
    status: 'pass' | 'fail' | 'warn';
    message: string;
    details?: Record<string, any>;
  }>;
  timestamp: Date;
}

export interface DataSourceServiceConfig {
  eventBus: EventEmitter;
  websocket?: WebSocket;
  apiBaseUrl: string;
  healthCheckInterval?: number;
}

export interface RealtimeUpdate {
  sourceId: string;
  status?: ConnectionStatus;
  metrics?: {
    latency?: number;
    throughput?: number;
    errorRate?: number;
    uptime?: number;
  };
  timestamp?: Date;
}

export class DataSourceService {
  private dataSources: Map<string, DataSource> = new Map();
  private eventBus: EventEmitter;
  private websocket?: WebSocket;
  private config: DataSourceServiceConfig;
  private healthCheckTimer?: NodeJS.Timeout;

  constructor(config: DataSourceServiceConfig) {
    this.config = {
      healthCheckInterval: 30000, // 30 seconds default
      ...config,
    };

    this.eventBus = config.eventBus;
    this.websocket = config.websocket;

    // Initialize data sources from API
    this.initializeDataSources();
  }

  /**
   * Initialize data sources from API
   */
  private async initializeDataSources(): Promise<void> {
    try {
      const sources = await this.getDataSources();
      sources.forEach(source => {
        this.dataSources.set(source.id, source);
      });
    } catch (error) {
      console.error('Failed to initialize data sources:', error);
    }
  }

  /**
   * Add a new data source
   */
  async addDataSource(data: DataSourceCreateData): Promise<DataSource> {
    const response = await fetch(`${this.config.apiBaseUrl}/data-sources`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        ...data,
        enabled: data.enabled ?? true,
        timeout: data.timeout ?? 5000,
        tags: data.tags ?? [],
      }),
    });

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }

    const dataSource = await response.json();
    this.dataSources.set(dataSource.id, dataSource);

    this.eventBus.emit('dataSource:added', dataSource);
    return dataSource;
  }

  /**
   * Get all data sources
   */
  async getDataSources(): Promise<DataSource[]> {
    const response = await fetch(`${this.config.apiBaseUrl}/data-sources`);

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }

    return await response.json();
  }

  /**
   * Get data source by ID
   */
  async getDataSource(id: string): Promise<DataSource | null> {
    const response = await fetch(`${this.config.apiBaseUrl}/data-sources/${id}`);

    if (!response.ok) {
      if (response.status === 404) {
        return null;
      }
      throw new Error(`HTTP error! status: ${response.status}`);
    }

    return await response.json();
  }

  /**
   * Update data source configuration
   */
  async updateDataSource(id: string, data: DataSourceUpdateData): Promise<DataSource> {
    const response = await fetch(`${this.config.apiBaseUrl}/data-sources/${id}`, {
      method: 'PUT',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(data),
    });

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }

    const dataSource = await response.json();
    this.dataSources.set(id, dataSource);

    this.eventBus.emit('dataSource:updated', dataSource);
    return dataSource;
  }

  /**
   * Delete data source
   */
  async deleteDataSource(id: string): Promise<boolean> {
    const response = await fetch(`${this.config.apiBaseUrl}/data-sources/${id}`, {
      method: 'DELETE',
    });

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }

    this.dataSources.delete(id);
    this.eventBus.emit('dataSource:deleted', id);
    return true;
  }

  /**
   * Test connection to a data source
   */
  async testConnection(id: string): Promise<ConnectionTestResult> {
    const response = await fetch(`${this.config.apiBaseUrl}/data-sources/${id}/test-connection`, {
      method: 'POST',
    });

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }

    const result = await response.json();
    return {
      ...result,
      timestamp: new Date(),
    };
  }

  /**
   * Get real-time connection statuses for all sources
   */
  async getConnectionStatuses(): Promise<ConnectionStatusUpdate[]> {
    const response = await fetch(`${this.config.apiBaseUrl}/data-sources/status`);

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }

    return await response.json();
  }

  /**
   * Get sources by connection status
   */
  getSourcesByStatus(status: ConnectionStatus): DataSource[] {
    return Array.from(this.dataSources.values()).filter(source => source.status === status);
  }

  /**
   * Get sources by type
   */
  getSourcesByType(type: DataSourceType): DataSource[] {
    return Array.from(this.dataSources.values()).filter(source => source.type === type);
  }

  /**
   * Get performance metrics for all sources
   */
  async getPerformanceMetrics(): Promise<PerformanceMetrics> {
    const response = await fetch(`${this.config.apiBaseUrl}/data-sources/metrics`);

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }

    return await response.json();
  }

  /**
   * Get historical performance data for a source
   */
  async getPerformanceHistory(
    sourceId: string,
    query: PerformanceHistoryQuery
  ): Promise<PerformanceHistoryData[]> {
    const params = new URLSearchParams({
      start: query.start.toISOString(),
      end: query.end.toISOString(),
      interval: query.interval,
    });

    const response = await fetch(
      `${this.config.apiBaseUrl}/data-sources/${sourceId}/metrics/history?${params}`
    );

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }

    return await response.json();
  }

  /**
   * Update data source status
   */
  updateSourceStatus(sourceId: string, update: Partial<ConnectionStatusUpdate>): void {
    const source = this.dataSources.get(sourceId);
    if (source) {
      const updatedSource = {
        ...source,
        ...update,
        updatedAt: new Date(),
      };

      this.dataSources.set(sourceId, updatedSource);

      this.eventBus.emit('dataSource:statusChanged', {
        sourceId,
        ...update,
      });
    }
  }

  /**
   * Update data source performance metrics
   */
  updateSourceMetrics(sourceId: string, metrics: RealtimeUpdate['metrics']): void {
    const source = this.dataSources.get(sourceId);
    if (source && metrics) {
      const updatedSource = {
        ...source,
        latency: metrics.latency ?? source.latency,
        throughput: metrics.throughput ?? source.throughput,
        errorRate: metrics.errorRate ?? source.errorRate,
        uptime: metrics.uptime ?? source.uptime,
        lastUpdate: new Date(),
        updatedAt: new Date(),
      };

      this.dataSources.set(sourceId, updatedSource);

      this.eventBus.emit('dataSource:metricsUpdated', {
        sourceId,
        metrics,
      });
    }
  }

  /**
   * Send real-time update over WebSocket
   */
  sendRealtimeUpdate(update: RealtimeUpdate): void {
    if (!this.websocket || this.websocket.readyState !== WebSocket.OPEN) {
      return;
    }

    try {
      this.websocket.send(JSON.stringify({
        type: 'dataSource:update',
        data: {
          ...update,
          timestamp: update.timestamp || new Date(),
        },
      }));
    } catch (error) {
      console.warn('Failed to send real-time update over WebSocket:', error);
    }
  }

  /**
   * Discover available data sources
   */
  async discoverDataSources(): Promise<DiscoveredSource[]> {
    const response = await fetch(`${this.config.apiBaseUrl}/data-sources/discover`);

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }

    return await response.json();
  }

  /**
   * Run health checks on all data sources
   */
  async runHealthChecks(): Promise<HealthCheckResult[]> {
    const response = await fetch(`${this.config.apiBaseUrl}/data-sources/health-check`, {
      method: 'POST',
    });

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }

    const results = await response.json();

    // Emit health check events
    results.forEach((result: HealthCheckResult) => {
      this.eventBus.emit('dataSource:healthCheck', result);
    });

    return results;
  }

  /**
   * Start periodic health checks
   */
  startPeriodicHealthChecks(interval?: number): void {
    const checkInterval = interval || this.config.healthCheckInterval || 30000;

    this.healthCheckTimer = setInterval(async () => {
      try {
        await this.runHealthChecks();
      } catch (error) {
        console.error('Health check failed:', error);
      }
    }, checkInterval);
  }

  /**
   * Stop periodic health checks
   */
  stopPeriodicHealthChecks(): void {
    if (this.healthCheckTimer) {
      clearInterval(this.healthCheckTimer);
      this.healthCheckTimer = undefined;
    }
  }

  /**
   * Get cached data sources
   */
  getCachedDataSources(): DataSource[] {
    return Array.from(this.dataSources.values());
  }

  /**
   * Get cached data source by ID
   */
  getCachedDataSource(id: string): DataSource | undefined {
    return this.dataSources.get(id);
  }

  /**
   * Get sources with poor performance
   */
  getPoorPerformanceSources(): DataSource[] {
    return Array.from(this.dataSources.values()).filter(source => {
      return (
        source.qualityScore < 70 ||
        source.errorRate > 0.05 ||
        source.uptime < 95 ||
        source.latency > 1000
      );
    });
  }

  /**
   * Get summary statistics
   */
  getSummaryStats(): {
    total: number;
    connected: number;
    disconnected: number;
    errors: number;
    avgLatency: number;
    avgThroughput: number;
    avgUptime: number;
  } {
    const sources = Array.from(this.dataSources.values());
    const connected = sources.filter(s => s.status === ConnectionStatus.CONNECTED);
    const disconnected = sources.filter(s => s.status === ConnectionStatus.DISCONNECTED);
    const errors = sources.filter(s => s.status === ConnectionStatus.ERROR);

    return {
      total: sources.length,
      connected: connected.length,
      disconnected: disconnected.length,
      errors: errors.length,
      avgLatency: sources.reduce((sum, s) => sum + s.latency, 0) / sources.length || 0,
      avgThroughput: sources.reduce((sum, s) => sum + s.throughput, 0) / sources.length || 0,
      avgUptime: sources.reduce((sum, s) => sum + s.uptime, 0) / sources.length || 0,
    };
  }

  /**
   * Clean up resources
   */
  destroy(): void {
    this.stopPeriodicHealthChecks();
    this.dataSources.clear();
    this.eventBus.removeAllListeners();
  }
}

// Singleton instance for global use
let globalDataSourceService: DataSourceService | null = null;

/**
 * Get or create global data source service instance
 */
export const getDataSourceService = (config?: DataSourceServiceConfig): DataSourceService => {
  if (!globalDataSourceService && config) {
    globalDataSourceService = new DataSourceService(config);
  }

  if (!globalDataSourceService) {
    throw new Error('DataSourceService not initialized. Call getDataSourceService with config first.');
  }

  return globalDataSourceService;
};
