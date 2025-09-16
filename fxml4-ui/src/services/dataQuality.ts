/**
 * DataQualityService
 *
 * Service for real-time data quality monitoring and validation
 */

import { EventEmitter } from 'events';
import { DataQualityMetrics, ValidationError, DataQualityLevel } from '@/types/dataManagement';

export interface DataQualityServiceConfig {
  eventBus: EventEmitter;
  websocket?: WebSocket;
  apiBaseUrl: string;
  qualityMonitoringInterval?: number;
  cacheTimeout?: number; // milliseconds
}

export interface QualityTrendsQuery {
  source?: string;
  symbol?: string;
  start: Date;
  end: Date;
  interval: string; // e.g., '5m', '1h', '1d'
}

export interface QualityTrendsData {
  timestamp: string;
  overallScore: number;
  completenessScore: number;
  accuracyScore: number;
  timelinessScore: number;
  consistencyScore: number;
}

export interface ValidationRule {
  id?: string;
  name: string;
  description: string;
  parameters: Record<string, any>;
  appliesTo: string[]; // asset types: 'forex', 'stocks', etc.
  enabled: boolean;
  createdAt?: string;
  updatedAt?: string;
}

export interface ValidationRuleUpdate {
  name?: string;
  description?: string;
  parameters?: Record<string, any>;
  appliesTo?: string[];
  enabled?: boolean;
}

export interface DataRecord {
  symbol: string;
  timestamp: string;
  [key: string]: any; // flexible structure for different data types
}

export interface ValidationResult {
  valid: boolean;
  errors: ValidationError[];
  warnings: ValidationError[];
  qualityScore: number;
  appliedRules: string[];
}

export interface BatchValidationResult {
  totalRecords: number;
  validRecords: number;
  invalidRecords: number;
  warnings: number;
  errors: number;
  overallQualityScore: number;
  results: Array<{
    recordIndex: number;
    valid: boolean;
    errors: ValidationError[];
    warnings: ValidationError[];
  }>;
}

export interface AnomalyFilter {
  timeframe?: string;
  minSeverity?: 'low' | 'medium' | 'high' | 'critical';
  symbols?: string[];
  sources?: string[];
  anomalyTypes?: string[];
}

export interface Anomaly {
  id: string;
  timestamp: Date;
  symbol: string;
  anomalyType: string;
  severity: 'low' | 'medium' | 'high' | 'critical';
  description: string;
  value: any;
  expectedRange: { min: number; max: number };
  confidence: number; // 0-1
  source: string;
  metadata?: Record<string, any>;
}

export interface AnomalyDetectionConfig {
  priceAnomalyThreshold: number;
  volumeAnomalyThreshold: number;
  enableRealTimeDetection: boolean;
  detectionWindow: string;
  confidenceThreshold: number;
  notificationSettings: {
    email: boolean;
    webhook: boolean;
    dashboard: boolean;
  };
}

export interface DataProfileOptions {
  timeframe?: string;
  period?: string; // e.g., '30d', '7d', '1h'
}

export interface DataProfile {
  symbol: string;
  timeframe: string;
  period: string;
  statistics: {
    recordCount: number;
    completeness: number; // percentage
    uniqueness: number; // percentage
    validity: number; // percentage
    averageLatency: number; // ms
    dataSize: number; // bytes
  };
  patterns: {
    peakHours: number[];
    quietHours: number[];
    weekendDataGaps: boolean;
    holidayDataGaps: boolean;
  };
  qualityIssues: Array<{
    type: string;
    count: number;
    description: string;
  }>;
  recommendations: string[];
}

export interface SourceComparison {
  symbol: string;
  sources: string[];
  comparisonMetrics: {
    [metric: string]: {
      [source: string]: number;
      difference?: number;
    };
  };
  discrepancies: Array<{
    type: string;
    timestamp: string;
    values: Record<string, any>;
    difference: number;
  }>;
  recommendation: string;
}

export interface QualityAlert {
  type: string;
  severity: 'info' | 'warning' | 'critical';
  symbol: string;
  metric: string;
  currentValue: number;
  threshold: number;
  message: string;
  timestamp: Date;
  metadata?: Record<string, any>;
}

export interface ValidationEvent {
  symbol: string;
  recordCount: number;
  validRecords: number;
  warnings: number;
  errors: number;
  qualityScore: number;
  timestamp: Date;
}

export interface RealtimeQualityUpdate {
  type: string;
  symbol?: string;
  overallScore?: number;
  trend?: 'improving' | 'stable' | 'degrading';
  lastUpdate?: Date;
  [key: string]: any;
}

export class DataQualityService {
  private eventBus: EventEmitter;
  private websocket?: WebSocket;
  private config: DataQualityServiceConfig;
  private qualityTimer?: NodeJS.Timeout;
  private cachedMetrics?: DataQualityMetrics[];
  private cacheTimestamp?: number;

  constructor(config: DataQualityServiceConfig) {
    this.config = {
      qualityMonitoringInterval: 60000, // 1 minute default
      cacheTimeout: 300000, // 5 minutes default
      ...config,
    };

    this.eventBus = config.eventBus;
    this.websocket = config.websocket;
  }

  /**
   * Get current quality metrics for all sources
   */
  async getCurrentQualityMetrics(): Promise<DataQualityMetrics[]> {
    const response = await fetch(`${this.config.apiBaseUrl}/data-quality/metrics`);

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }

    const metrics = await response.json();

    // Update cache
    this.cachedMetrics = metrics;
    this.cacheTimestamp = Date.now();

    return metrics;
  }

  /**
   * Get quality metrics for specific source
   */
  async getQualityMetricsBySource(source: string): Promise<DataQualityMetrics> {
    const encodedSource = encodeURIComponent(source);
    const response = await fetch(`${this.config.apiBaseUrl}/data-quality/metrics/source/${encodedSource}`);

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }

    return await response.json();
  }

  /**
   * Get quality metrics for specific symbol
   */
  async getQualityMetricsBySymbol(symbol: string): Promise<DataQualityMetrics[]> {
    const response = await fetch(`${this.config.apiBaseUrl}/data-quality/metrics/symbol/${symbol}`);

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }

    return await response.json();
  }

  /**
   * Get historical quality trends
   */
  async getQualityTrends(query: QualityTrendsQuery): Promise<QualityTrendsData[]> {
    const params = new URLSearchParams({
      start: query.start.toISOString(),
      end: query.end.toISOString(),
      interval: query.interval,
    });

    if (query.source) params.append('source', query.source);
    if (query.symbol) params.append('symbol', query.symbol);

    const response = await fetch(`${this.config.apiBaseUrl}/data-quality/trends?${params}`);

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }

    return await response.json();
  }

  /**
   * Get all validation rules
   */
  async getValidationRules(): Promise<ValidationRule[]> {
    const response = await fetch(`${this.config.apiBaseUrl}/data-quality/validation-rules`);

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }

    return await response.json();
  }

  /**
   * Create new validation rule
   */
  async createValidationRule(rule: Omit<ValidationRule, 'id' | 'createdAt' | 'updatedAt'>): Promise<ValidationRule> {
    const response = await fetch(`${this.config.apiBaseUrl}/data-quality/validation-rules`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(rule),
    });

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }

    return await response.json();
  }

  /**
   * Update validation rule
   */
  async updateValidationRule(ruleId: string, updates: ValidationRuleUpdate): Promise<ValidationRule> {
    const response = await fetch(`${this.config.apiBaseUrl}/data-quality/validation-rules/${ruleId}`, {
      method: 'PUT',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(updates),
    });

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }

    return await response.json();
  }

  /**
   * Delete validation rule
   */
  async deleteValidationRule(ruleId: string): Promise<boolean> {
    const response = await fetch(`${this.config.apiBaseUrl}/data-quality/validation-rules/${ruleId}`, {
      method: 'DELETE',
    });

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }

    return true;
  }

  /**
   * Validate single data record
   */
  async validateDataRecord(record: DataRecord): Promise<ValidationResult> {
    const response = await fetch(`${this.config.apiBaseUrl}/data-quality/validate`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(record),
    });

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }

    return await response.json();
  }

  /**
   * Validate batch of data records
   */
  async validateDataBatch(records: DataRecord[]): Promise<BatchValidationResult> {
    const response = await fetch(`${this.config.apiBaseUrl}/data-quality/validate-batch`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ records }),
    });

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }

    return await response.json();
  }

  /**
   * Get anomalies based on filter criteria
   */
  async getAnomalies(filter: AnomalyFilter = {}): Promise<Anomaly[]> {
    const params = new URLSearchParams();

    if (filter.timeframe) params.append('timeframe', filter.timeframe);
    if (filter.minSeverity) params.append('minSeverity', filter.minSeverity);
    if (filter.symbols) params.append('symbols', filter.symbols.join(','));
    if (filter.sources) params.append('sources', filter.sources.join(','));
    if (filter.anomalyTypes) params.append('anomalyTypes', filter.anomalyTypes.join(','));

    const response = await fetch(`${this.config.apiBaseUrl}/data-quality/anomalies?${params}`);

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }

    return await response.json();
  }

  /**
   * Configure anomaly detection settings
   */
  async configureAnomalyDetection(config: AnomalyDetectionConfig): Promise<AnomalyDetectionConfig> {
    const response = await fetch(`${this.config.apiBaseUrl}/data-quality/anomaly-detection/config`, {
      method: 'PUT',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(config),
    });

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }

    return await response.json();
  }

  /**
   * Generate data profile for symbol
   */
  async generateDataProfile(symbol: string, options: DataProfileOptions = {}): Promise<DataProfile> {
    const params = new URLSearchParams();

    if (options.timeframe) params.append('timeframe', options.timeframe);
    if (options.period) params.append('period', options.period);

    const response = await fetch(`${this.config.apiBaseUrl}/data-quality/profile/${symbol}?${params}`);

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }

    return await response.json();
  }

  /**
   * Compare data quality between sources
   */
  async compareDataSources(symbol: string, sources: string[]): Promise<SourceComparison> {
    const response = await fetch(`${this.config.apiBaseUrl}/data-quality/compare`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ symbol, sources }),
    });

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }

    return await response.json();
  }

  /**
   * Emit quality alert
   */
  emitQualityAlert(alert: QualityAlert): void {
    this.eventBus.emit('dataQuality:alert', alert);
  }

  /**
   * Emit validation event
   */
  emitValidationEvent(event: ValidationEvent): void {
    this.eventBus.emit('dataQuality:validation', event);
  }

  /**
   * Send real-time quality update over WebSocket
   */
  sendRealtimeUpdate(update: RealtimeQualityUpdate): void {
    if (!this.websocket || this.websocket.readyState !== WebSocket.OPEN) {
      return;
    }

    try {
      this.websocket.send(JSON.stringify({
        type: 'dataQuality:update',
        data: {
          ...update,
          timestamp: update.lastUpdate || new Date(),
        },
      }));
    } catch (error) {
      console.warn('Failed to send real-time quality update over WebSocket:', error);
    }
  }

  /**
   * Start periodic quality monitoring
   */
  startPeriodicQualityMonitoring(interval?: number): void {
    const monitoringInterval = interval || this.config.qualityMonitoringInterval || 60000;

    this.qualityTimer = setInterval(async () => {
      try {
        const metrics = await this.getCurrentQualityMetrics();

        // Emit events for each metric set
        metrics.forEach(metric => {
          // Check for quality degradation and emit alerts
          if (metric.overallScore < 80) {
            this.emitQualityAlert({
              type: 'quality_degradation',
              severity: metric.overallScore < 60 ? 'critical' : 'warning',
              symbol: metric.symbol || 'ALL',
              metric: 'overall_score',
              currentValue: metric.overallScore,
              threshold: 80,
              message: `Overall quality score below threshold for ${metric.symbol || 'system'}`,
              timestamp: new Date(),
            });
          }

          // Send real-time updates
          this.sendRealtimeUpdate({
            type: 'quality_metrics',
            symbol: metric.symbol,
            overallScore: metric.overallScore,
            trend: metric.trend,
            lastUpdate: new Date(),
          });
        });
      } catch (error) {
        console.error('Failed to monitor data quality:', error);
      }
    }, monitoringInterval);
  }

  /**
   * Stop periodic quality monitoring
   */
  stopPeriodicQualityMonitoring(): void {
    if (this.qualityTimer) {
      clearInterval(this.qualityTimer);
      this.qualityTimer = undefined;
    }
  }

  /**
   * Get cached quality metrics
   */
  getCachedQualityMetrics(): DataQualityMetrics[] | null {
    if (!this.cachedMetrics || !this.cacheTimestamp) {
      return null;
    }

    const cacheAge = Date.now() - this.cacheTimestamp;
    const cacheTimeout = this.config.cacheTimeout || 300000;

    if (cacheAge > cacheTimeout) {
      // Cache expired
      this.cachedMetrics = undefined;
      this.cacheTimestamp = undefined;
      return null;
    }

    return this.cachedMetrics;
  }

  /**
   * Calculate quality score from components
   */
  calculateOverallQualityScore(
    completeness: number,
    accuracy: number,
    timeliness: number,
    consistency: number,
    weights: { completeness: number; accuracy: number; timeliness: number; consistency: number } = {
      completeness: 0.3,
      accuracy: 0.3,
      timeliness: 0.2,
      consistency: 0.2,
    }
  ): number {
    return (
      completeness * weights.completeness +
      accuracy * weights.accuracy +
      timeliness * weights.timeliness +
      consistency * weights.consistency
    );
  }

  /**
   * Determine quality level from score
   */
  getQualityLevel(score: number): DataQualityLevel {
    if (score >= 95) return DataQualityLevel.EXCELLENT;
    if (score >= 85) return DataQualityLevel.GOOD;
    if (score >= 70) return DataQualityLevel.FAIR;
    if (score >= 50) return DataQualityLevel.POOR;
    return DataQualityLevel.CRITICAL;
  }

  /**
   * Get quality summary statistics
   */
  getQualitySummary(): {
    averageScore: number;
    totalSources: number;
    excellentSources: number;
    goodSources: number;
    poorSources: number;
    criticalSources: number;
    trendDirection: 'improving' | 'stable' | 'degrading';
  } | null {
    const cached = this.getCachedQualityMetrics();
    if (!cached || cached.length === 0) return null;

    const scores = cached.map(m => m.overallScore);
    const averageScore = scores.reduce((sum, score) => sum + score, 0) / scores.length;

    const excellentSources = cached.filter(m => m.qualityLevel === DataQualityLevel.EXCELLENT).length;
    const goodSources = cached.filter(m => m.qualityLevel === DataQualityLevel.GOOD).length;
    const poorSources = cached.filter(m => m.qualityLevel === DataQualityLevel.POOR).length;
    const criticalSources = cached.filter(m => m.qualityLevel === DataQualityLevel.CRITICAL).length;

    // Calculate overall trend
    const improvingCount = cached.filter(m => m.trend === 'improving').length;
    const degradingCount = cached.filter(m => m.trend === 'degrading').length;

    let trendDirection: 'improving' | 'stable' | 'degrading';
    if (improvingCount > degradingCount) trendDirection = 'improving';
    else if (degradingCount > improvingCount) trendDirection = 'degrading';
    else trendDirection = 'stable';

    return {
      averageScore,
      totalSources: cached.length,
      excellentSources,
      goodSources,
      poorSources,
      criticalSources,
      trendDirection,
    };
  }

  /**
   * Clean up resources
   */
  destroy(): void {
    this.stopPeriodicQualityMonitoring();
    this.cachedMetrics = undefined;
    this.cacheTimestamp = undefined;
    this.eventBus.removeAllListeners();
  }
}

// Singleton instance for global use
let globalDataQualityService: DataQualityService | null = null;

/**
 * Get or create global data quality service instance
 */
export const getDataQualityService = (config?: DataQualityServiceConfig): DataQualityService => {
  if (!globalDataQualityService && config) {
    globalDataQualityService = new DataQualityService(config);
  }

  if (!globalDataQualityService) {
    throw new Error('DataQualityService not initialized. Call getDataQualityService with config first.');
  }

  return globalDataQualityService;
};
