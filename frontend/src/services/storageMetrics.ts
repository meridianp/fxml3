/**
 * StorageMetricsService
 *
 * Service for monitoring database and cache storage metrics
 */

import { EventEmitter } from 'events';
import { StorageMetrics, SlowQuery, RetentionPolicy } from '@/types/dataManagement';

export interface StorageMetricsServiceConfig {
  eventBus: EventEmitter;
  websocket?: WebSocket;
  apiBaseUrl: string;
  metricsCollectionInterval?: number;
}

export interface HistoricalMetricsQuery {
  start: Date;
  end: Date;
  interval: string; // e.g., '5m', '1h', '1d'
}

export interface HistoricalMetricsData {
  timestamp: string;
  databaseSize?: number;
  cacheHitRate?: number;
  queryRate?: number;
  connectionCount?: number;
  [key: string]: any;
}

export interface SlowQueryFilter {
  limit?: number;
  minDuration?: number; // milliseconds
  database?: string;
  user?: string;
}

export interface TableSizeInfo {
  [tableName: string]: {
    size: number; // bytes
    rows: number;
    indexes?: number;
    toast?: number;
  };
}

export interface DatabaseConnection {
  pid: number;
  database: string;
  username: string;
  clientAddress: string;
  state: 'active' | 'idle' | 'idle in transaction' | 'waiting';
  query: string | null;
  duration: number; // milliseconds
  applicationName?: string;
}

export interface CacheStatsByPattern {
  pattern: string;
  keyCount: number;
  totalMemory: number; // bytes
  avgTtl: number; // seconds
  hitRate: number; // percentage
}

export interface CacheKeyInfo {
  key: string;
  type: 'string' | 'list' | 'set' | 'hash' | 'zset';
  size: number; // number of elements
  ttl: number; // seconds, -1 for no expiry
  memory: number; // bytes
}

export interface CacheKeyQuery {
  pattern?: string;
  limit?: number;
  type?: string;
}

export interface VacuumAnalysisResult {
  tablesAnalyzed: number;
  spaceClaimed: number; // bytes
  duration: number; // milliseconds
  recommendations: string[];
  details?: {
    [tableName: string]: {
      deadTuples: number;
      spaceClaimed: number;
      duration: number;
    };
  };
}

export interface CompressionRecommendation {
  tableName: string;
  currentSize: number; // bytes
  estimatedCompressedSize: number; // bytes
  compressionRatio: number; // 0-1
  recommendation: string;
  potentialSavings: number; // bytes
}

export interface CompressionOptions {
  olderThan: string; // e.g., '7 days', '1 month'
  algorithm?: 'lz4' | 'zstd' | 'gzip';
  force?: boolean;
}

export interface CompressionResult {
  tableName: string;
  chunksCompressed: number;
  spaceSaved: number; // bytes
  duration: number; // milliseconds
  errors?: string[];
}

export interface StorageAlertThresholds {
  databaseSizeWarning?: number; // percentage
  databaseSizeCritical?: number; // percentage
  cacheHitRateWarning?: number; // percentage
  cacheHitRateCritical?: number; // percentage
  slowQueryThreshold?: number; // milliseconds
  connectionCountWarning?: number;
  connectionCountCritical?: number;
  diskUsageWarning?: number; // percentage
  diskUsageCritical?: number; // percentage
}

export interface StorageHealthCheck {
  overall: 'healthy' | 'warning' | 'critical';
  checks: Array<{
    name: string;
    status: 'healthy' | 'warning' | 'critical';
    value: number;
    threshold: number;
    message: string;
    details?: any;
  }>;
  timestamp: string;
}

export interface StorageAlert {
  type: string;
  severity: 'info' | 'warning' | 'critical';
  message: string;
  value: number;
  threshold: number;
  timestamp: Date;
  metadata?: Record<string, any>;
}

export interface RealtimeStorageUpdate {
  type: string;
  data: Record<string, any>;
  timestamp?: Date;
}

export interface StorageTrends {
  [metricName: string]: {
    trend: 'increasing' | 'decreasing' | 'stable';
    rate: number; // change per hour
    projection: {
      nextHour: number;
      nextDay: number;
      nextWeek: number;
    };
  };
}

export class StorageMetricsService {
  private eventBus: EventEmitter;
  private websocket?: WebSocket;
  private config: StorageMetricsServiceConfig;
  private metricsTimer?: NodeJS.Timeout;
  private lastMetrics?: StorageMetrics;

  constructor(config: StorageMetricsServiceConfig) {
    this.config = {
      metricsCollectionInterval: 30000, // 30 seconds default
      ...config,
    };

    this.eventBus = config.eventBus;
    this.websocket = config.websocket;
  }

  /**
   * Get current storage metrics
   */
  async getCurrentMetrics(): Promise<StorageMetrics> {
    const response = await fetch(`${this.config.apiBaseUrl}/storage/metrics`);

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }

    const metrics = await response.json();
    this.lastMetrics = metrics;
    return metrics;
  }

  /**
   * Get database-specific metrics
   */
  async getDatabaseMetrics(): Promise<{ timestamp: string; database: StorageMetrics['database'] }> {
    const response = await fetch(`${this.config.apiBaseUrl}/storage/database/metrics`);

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }

    return await response.json();
  }

  /**
   * Get cache-specific metrics
   */
  async getCacheMetrics(): Promise<{ timestamp: string; cache: StorageMetrics['cache'] }> {
    const response = await fetch(`${this.config.apiBaseUrl}/storage/cache/metrics`);

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }

    return await response.json();
  }

  /**
   * Get historical storage metrics
   */
  async getHistoricalMetrics(query: HistoricalMetricsQuery): Promise<HistoricalMetricsData[]> {
    const params = new URLSearchParams({
      start: query.start.toISOString(),
      end: query.end.toISOString(),
      interval: query.interval,
    });

    const response = await fetch(`${this.config.apiBaseUrl}/storage/metrics/history?${params}`);

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }

    return await response.json();
  }

  /**
   * Get slow queries
   */
  async getSlowQueries(filter: SlowQueryFilter = {}): Promise<SlowQuery[]> {
    const params = new URLSearchParams();

    if (filter.limit) params.append('limit', filter.limit.toString());
    if (filter.minDuration) params.append('minDuration', filter.minDuration.toString());
    if (filter.database) params.append('database', filter.database);
    if (filter.user) params.append('user', filter.user);

    const response = await fetch(`${this.config.apiBaseUrl}/storage/database/slow-queries?${params}`);

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }

    return await response.json();
  }

  /**
   * Get table sizes
   */
  async getTableSizes(): Promise<TableSizeInfo> {
    const response = await fetch(`${this.config.apiBaseUrl}/storage/database/table-sizes`);

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }

    return await response.json();
  }

  /**
   * Get active database connections
   */
  async getActiveConnections(): Promise<DatabaseConnection[]> {
    const response = await fetch(`${this.config.apiBaseUrl}/storage/database/connections`);

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }

    return await response.json();
  }

  /**
   * Get retention policies
   */
  async getRetentionPolicies(): Promise<RetentionPolicy[]> {
    const response = await fetch(`${this.config.apiBaseUrl}/storage/database/retention-policies`);

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }

    return await response.json();
  }

  /**
   * Get cache statistics by pattern
   */
  async getCacheStatsByPattern(pattern: string): Promise<CacheStatsByPattern> {
    const params = new URLSearchParams({ pattern });
    const response = await fetch(`${this.config.apiBaseUrl}/storage/cache/stats?${params}`);

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }

    return await response.json();
  }

  /**
   * Get cache keys
   */
  async getCacheKeys(query: CacheKeyQuery = {}): Promise<CacheKeyInfo[]> {
    const params = new URLSearchParams();

    if (query.pattern) params.append('pattern', query.pattern);
    if (query.limit) params.append('limit', query.limit.toString());
    if (query.type) params.append('type', query.type);

    const response = await fetch(`${this.config.apiBaseUrl}/storage/cache/keys?${params}`);

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }

    return await response.json();
  }

  /**
   * Flush cache by pattern
   */
  async flushCachePattern(pattern: string): Promise<{ removedKeys: number }> {
    const response = await fetch(`${this.config.apiBaseUrl}/storage/cache/flush`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ pattern }),
    });

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }

    return await response.json();
  }

  /**
   * Run database vacuum analysis
   */
  async runVacuumAnalysis(): Promise<VacuumAnalysisResult> {
    const response = await fetch(`${this.config.apiBaseUrl}/storage/database/vacuum-analyze`, {
      method: 'POST',
    });

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }

    return await response.json();
  }

  /**
   * Get compression recommendations
   */
  async getCompressionRecommendations(): Promise<CompressionRecommendation[]> {
    const response = await fetch(`${this.config.apiBaseUrl}/storage/database/compression-recommendations`);

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }

    return await response.json();
  }

  /**
   * Apply compression to table chunks
   */
  async applyCompression(tableName: string, options: CompressionOptions): Promise<CompressionResult> {
    const response = await fetch(`${this.config.apiBaseUrl}/storage/database/compress`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        tableName,
        ...options,
      }),
    });

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }

    return await response.json();
  }

  /**
   * Set storage alert thresholds
   */
  async setAlertThresholds(thresholds: StorageAlertThresholds): Promise<StorageAlertThresholds> {
    const response = await fetch(`${this.config.apiBaseUrl}/storage/alert-thresholds`, {
      method: 'PUT',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(thresholds),
    });

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }

    return await response.json();
  }

  /**
   * Check storage health
   */
  async checkStorageHealth(): Promise<StorageHealthCheck> {
    const response = await fetch(`${this.config.apiBaseUrl}/storage/health-check`);

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }

    return await response.json();
  }

  /**
   * Update metrics and emit events
   */
  updateMetrics(metrics: StorageMetrics): void {
    this.lastMetrics = metrics;
    this.eventBus.emit('storage:metricsUpdated', metrics);
  }

  /**
   * Emit storage alert
   */
  emitAlert(alert: StorageAlert): void {
    this.eventBus.emit('storage:alert', alert);
  }

  /**
   * Send real-time update over WebSocket
   */
  sendRealtimeUpdate(update: RealtimeStorageUpdate): void {
    if (!this.websocket || this.websocket.readyState !== WebSocket.OPEN) {
      return;
    }

    try {
      this.websocket.send(JSON.stringify({
        type: 'storage:update',
        data: {
          ...update,
          timestamp: update.timestamp || new Date(),
        },
      }));
    } catch (error) {
      console.warn('Failed to send real-time storage update over WebSocket:', error);
    }
  }

  /**
   * Start periodic metrics collection
   */
  startPeriodicMetricsCollection(interval?: number): void {
    const collectionInterval = interval || this.config.metricsCollectionInterval || 30000;

    this.metricsTimer = setInterval(async () => {
      try {
        const metrics = await this.getCurrentMetrics();
        this.updateMetrics(metrics);

        // Send real-time update
        this.sendRealtimeUpdate({
          type: 'storage_metrics',
          data: {
            databaseSize: metrics.database.totalSize,
            cacheHitRate: metrics.cache.hitRate,
            activeConnections: metrics.database.activeConnections,
            queryRate: metrics.database.queryRate,
          },
        });
      } catch (error) {
        console.error('Failed to collect storage metrics:', error);
      }
    }, collectionInterval);
  }

  /**
   * Stop periodic metrics collection
   */
  stopPeriodicMetricsCollection(): void {
    if (this.metricsTimer) {
      clearInterval(this.metricsTimer);
      this.metricsTimer = undefined;
    }
  }

  /**
   * Calculate storage trends from historical data
   */
  calculateStorageTrends(historicalData: HistoricalMetricsData[]): StorageTrends {
    const trends: StorageTrends = {};

    if (historicalData.length < 2) {
      return trends;
    }

    // Calculate trends for each metric
    const metrics = Object.keys(historicalData[0]).filter(key =>
      key !== 'timestamp' && typeof historicalData[0][key] === 'number'
    );

    metrics.forEach(metric => {
      const values = historicalData.map(item => item[metric] as number).filter(v => v !== undefined);

      if (values.length < 2) return;

      // Simple linear regression to calculate trend
      const n = values.length;
      const timePoints = Array.from({ length: n }, (_, i) => i);

      const sumX = timePoints.reduce((a, b) => a + b, 0);
      const sumY = values.reduce((a, b) => a + b, 0);
      const sumXY = timePoints.reduce((sum, x, i) => sum + x * values[i], 0);
      const sumX2 = timePoints.reduce((sum, x) => sum + x * x, 0);

      const slope = (n * sumXY - sumX * sumY) / (n * sumX2 - sumX * sumX);
      const intercept = (sumY - slope * sumX) / n;

      // Calculate rate per hour (assuming data points are evenly distributed)
      const timeSpanHours = (new Date(historicalData[n - 1].timestamp).getTime() -
                            new Date(historicalData[0].timestamp).getTime()) / (1000 * 60 * 60);
      const ratePerHour = (slope * n / timeSpanHours) || 0;

      const currentValue = values[values.length - 1];

      trends[metric] = {
        trend: Math.abs(ratePerHour) < 0.01 ? 'stable' : ratePerHour > 0 ? 'increasing' : 'decreasing',
        rate: ratePerHour,
        projection: {
          nextHour: currentValue + ratePerHour,
          nextDay: currentValue + ratePerHour * 24,
          nextWeek: currentValue + ratePerHour * 24 * 7,
        },
      };
    });

    return trends;
  }

  /**
   * Get cached metrics
   */
  getLastMetrics(): StorageMetrics | undefined {
    return this.lastMetrics;
  }

  /**
   * Get storage summary statistics
   */
  getStorageSummary(): {
    databaseUtilization: number; // percentage
    cacheEfficiency: number; // percentage
    queryPerformance: 'excellent' | 'good' | 'fair' | 'poor';
    overallHealth: 'healthy' | 'warning' | 'critical';
  } | null {
    if (!this.lastMetrics) return null;

    const { database, cache, filesystem } = this.lastMetrics;

    // Calculate database utilization (if filesystem info available)
    const databaseUtilization = filesystem
      ? (filesystem.usedSpace / filesystem.totalSpace) * 100
      : (database.totalSize / (database.totalSize + 1073741824)) * 100; // Assume some headroom

    // Cache efficiency based on hit rate
    const cacheEfficiency = cache.hitRate;

    // Query performance based on average query time
    let queryPerformance: 'excellent' | 'good' | 'fair' | 'poor';
    if (database.avgQueryTime < 100) queryPerformance = 'excellent';
    else if (database.avgQueryTime < 500) queryPerformance = 'good';
    else if (database.avgQueryTime < 2000) queryPerformance = 'fair';
    else queryPerformance = 'poor';

    // Overall health assessment
    let overallHealth: 'healthy' | 'warning' | 'critical';
    if (databaseUtilization > 90 || cacheEfficiency < 75 || database.avgQueryTime > 2000) {
      overallHealth = 'critical';
    } else if (databaseUtilization > 80 || cacheEfficiency < 85 || database.avgQueryTime > 500) {
      overallHealth = 'warning';
    } else {
      overallHealth = 'healthy';
    }

    return {
      databaseUtilization,
      cacheEfficiency,
      queryPerformance,
      overallHealth,
    };
  }

  /**
   * Clean up resources
   */
  destroy(): void {
    this.stopPeriodicMetricsCollection();
    this.eventBus.removeAllListeners();
  }
}

// Singleton instance for global use
let globalStorageMetricsService: StorageMetricsService | null = null;

/**
 * Get or create global storage metrics service instance
 */
export const getStorageMetricsService = (config?: StorageMetricsServiceConfig): StorageMetricsService => {
  if (!globalStorageMetricsService && config) {
    globalStorageMetricsService = new StorageMetricsService(config);
  }

  if (!globalStorageMetricsService) {
    throw new Error('StorageMetricsService not initialized. Call getStorageMetricsService with config first.');
  }

  return globalStorageMetricsService;
};
