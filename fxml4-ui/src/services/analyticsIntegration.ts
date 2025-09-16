/**
 * Analytics Integration Service
 *
 * Connects analytics engine with data management services for unified insights
 */

import { AnalyticsService, getAnalyticsService } from './analytics';
import { MetricsAggregationService, getMetricsAggregationService } from './metricsAggregation';
import { ReportsService, getReportsService } from './reports';
import { DataSourceService } from './dataSource';
import { StorageMetricsService } from './storageMetrics';
import { DataQualityService } from './dataQuality';
import { PipelineService } from './pipeline';
import {
  AnalyticsDataPoint,
  AnalyticsQuery,
  TimeRange,
  TimeInterval,
  AnalyticsCategory,
  KPI,
  KPIStatus,
  TrendDirection,
  SystemHealth,
  IntegratedMetrics,
  CrossServiceInsights,
} from '@/types/analytics';
import {
  DataSourceStatusEvent,
  StorageStatusEvent,
  QualityStatusEvent,
  PipelineStatusEvent,
} from '@/types/dataManagement';

export interface AnalyticsIntegrationConfig {
  updateInterval: number;
  historyRetention: number;
  alertThresholds: {
    systemHealth: number;
    dataQuality: number;
    storageUsage: number;
    pipelineFailure: number;
  };
}

export interface DataManagementAnalytics {
  systemHealth: SystemHealth;
  crossServiceTrends: AnalyticsDataPoint[];
  correlationInsights: CrossServiceInsights[];
  aggregatedKPIs: KPI[];
  performanceScore: number;
  recommendations: string[];
}

export class AnalyticsIntegrationService {
  private analyticsService: AnalyticsService;
  private metricsService: MetricsAggregationService;
  private reportsService: ReportsService;
  private config: AnalyticsIntegrationConfig;
  private cache: Map<string, any> = new Map();
  private updateCallbacks: Array<(data: DataManagementAnalytics) => void> = [];

  constructor(
    config: Partial<AnalyticsIntegrationConfig> = {},
    analyticsService?: AnalyticsService,
    metricsService?: MetricsAggregationService,
    reportsService?: ReportsService
  ) {
    this.analyticsService = analyticsService || getAnalyticsService();
    this.metricsService = metricsService || getMetricsAggregationService();
    this.reportsService = reportsService || getReportsService();

    this.config = {
      updateInterval: 30000, // 30 seconds
      historyRetention: 24 * 60 * 60 * 1000, // 24 hours
      alertThresholds: {
        systemHealth: 80,
        dataQuality: 90,
        storageUsage: 85,
        pipelineFailure: 10,
      },
      ...config,
    };
  }

  /**
   * Initialize analytics integration with data management services
   */
  async initialize(services: {
    dataSource?: DataSourceService;
    storage?: StorageMetricsService;
    dataQuality?: DataQualityService;
    pipeline?: PipelineService;
  }): Promise<void> {
    // Set up data collection from each service
    if (services.dataSource) {
      await this.setupDataSourceAnalytics(services.dataSource);
    }
    if (services.storage) {
      await this.setupStorageAnalytics(services.storage);
    }
    if (services.dataQuality) {
      await this.setupQualityAnalytics(services.dataQuality);
    }
    if (services.pipeline) {
      await this.setupPipelineAnalytics(services.pipeline);
    }

    // Start periodic analytics update
    this.startPeriodicUpdates();
  }

  /**
   * Set up analytics collection from data source service
   */
  private async setupDataSourceAnalytics(service: DataSourceService): Promise<void> {
    // Register for status updates
    const collectDataSourceMetrics = async (event: DataSourceStatusEvent) => {
      const dataPoint: AnalyticsDataPoint = {
        timestamp: new Date(),
        metrics: {
          data_source_active_connections: event.activeConnections,
          data_source_failed_connections: event.failedConnections,
          data_source_uptime: event.uptime,
          data_source_response_time: event.averageResponseTime,
          data_source_throughput: event.throughput,
        },
        dimensions: {
          service: 'data_source',
          category: AnalyticsCategory.DATA_QUALITY,
        },
      };

      await this.analyticsService.addDataPoint(dataPoint);
      this.invalidateCache('data_source');
    };

    // Mock event listener setup (in real implementation, would use actual event system)
    this.cache.set('data_source_collector', collectDataSourceMetrics);
  }

  /**
   * Set up analytics collection from storage service
   */
  private async setupStorageAnalytics(service: StorageMetricsService): Promise<void> {
    const collectStorageMetrics = async (event: StorageStatusEvent) => {
      const dataPoint: AnalyticsDataPoint = {
        timestamp: new Date(),
        metrics: {
          storage_used: event.usedStorage,
          storage_total: event.totalStorage,
          storage_utilization: (event.usedStorage / event.totalStorage) * 100,
          storage_operations_per_second: event.operationsPerSecond,
          storage_average_latency: event.averageLatency,
        },
        dimensions: {
          service: 'storage',
          category: AnalyticsCategory.PERFORMANCE,
        },
      };

      await this.analyticsService.addDataPoint(dataPoint);
      this.invalidateCache('storage');
    };

    this.cache.set('storage_collector', collectStorageMetrics);
  }

  /**
   * Set up analytics collection from data quality service
   */
  private async setupQualityAnalytics(service: DataQualityService): Promise<void> {
    const collectQualityMetrics = async (event: QualityStatusEvent) => {
      const dataPoint: AnalyticsDataPoint = {
        timestamp: new Date(),
        metrics: {
          data_quality_score: event.qualityScore,
          data_quality_completeness: event.completeness || 0,
          data_quality_accuracy: event.accuracy || 0,
          data_quality_consistency: event.consistency || 0,
          data_quality_timeliness: event.timeliness || 0,
        },
        dimensions: {
          service: 'data_quality',
          category: AnalyticsCategory.DATA_QUALITY,
          level: event.level,
        },
      };

      await this.analyticsService.addDataPoint(dataPoint);
      this.invalidateCache('quality');
    };

    this.cache.set('quality_collector', collectQualityMetrics);
  }

  /**
   * Set up analytics collection from pipeline service
   */
  private async setupPipelineAnalytics(service: PipelineService): Promise<void> {
    const collectPipelineMetrics = async (event: PipelineStatusEvent) => {
      const successRate = event.totalJobs > 0 ?
        ((event.totalJobs - event.failedJobs) / event.totalJobs) * 100 : 100;

      const dataPoint: AnalyticsDataPoint = {
        timestamp: new Date(),
        metrics: {
          pipeline_total_jobs: event.totalJobs,
          pipeline_running_jobs: event.runningJobs,
          pipeline_failed_jobs: event.failedJobs,
          pipeline_success_rate: successRate,
          pipeline_average_duration: event.averageDuration,
          pipeline_queue_size: event.queueSize,
        },
        dimensions: {
          service: 'pipeline',
          category: AnalyticsCategory.PERFORMANCE,
        },
      };

      await this.analyticsService.addDataPoint(dataPoint);
      this.invalidateCache('pipeline');
    };

    this.cache.set('pipeline_collector', collectPipelineMetrics);
  }

  /**
   * Generate comprehensive analytics for data management
   */
  async generateDataManagementAnalytics(timeRange?: TimeRange): Promise<DataManagementAnalytics> {
    const cacheKey = `analytics_${timeRange?.start.getTime()}_${timeRange?.end.getTime()}`;
    const cached = this.cache.get(cacheKey);
    if (cached && Date.now() - cached.timestamp < 30000) {
      return cached.data;
    }

    const defaultTimeRange: TimeRange = timeRange || {
      start: new Date(Date.now() - 60 * 60 * 1000), // Last hour
      end: new Date(),
      interval: TimeInterval.MINUTE,
    };

    try {
      // Gather data from all services
      const [
        systemHealth,
        crossServiceTrends,
        correlationInsights,
        aggregatedKPIs,
      ] = await Promise.all([
        this.calculateSystemHealth(defaultTimeRange),
        this.analyzeCrossServiceTrends(defaultTimeRange),
        this.findCorrelationInsights(defaultTimeRange),
        this.aggregateServiceKPIs(defaultTimeRange),
      ]);

      const performanceScore = this.calculateOverallPerformanceScore(aggregatedKPIs);
      const recommendations = await this.generateRecommendations(systemHealth, aggregatedKPIs);

      const analytics: DataManagementAnalytics = {
        systemHealth,
        crossServiceTrends,
        correlationInsights,
        aggregatedKPIs,
        performanceScore,
        recommendations,
      };

      this.cache.set(cacheKey, { data: analytics, timestamp: Date.now() });

      // Notify subscribers
      this.updateCallbacks.forEach(callback => callback(analytics));

      return analytics;
    } catch (error) {
      console.error('Failed to generate data management analytics:', error);
      throw error;
    }
  }

  /**
   * Calculate overall system health across all services
   */
  private async calculateSystemHealth(timeRange: TimeRange): Promise<SystemHealth> {
    const metrics = await this.analyticsService.getHistoricalData('*', timeRange);

    const latestMetrics = metrics.reduce((latest, point) => {
      const timestamp = point.timestamp.getTime();
      if (!latest.timestamp || timestamp > latest.timestamp.getTime()) {
        return point;
      }
      return latest;
    }, {} as AnalyticsDataPoint);

    const healthScores = {
      dataSource: this.calculateDataSourceHealth(latestMetrics),
      storage: this.calculateStorageHealth(latestMetrics),
      quality: this.calculateQualityHealth(latestMetrics),
      pipeline: this.calculatePipelineHealth(latestMetrics),
    };

    const overallScore = Object.values(healthScores).reduce((sum, score) => sum + score, 0) / 4;

    return {
      overall: overallScore,
      components: healthScores,
      status: overallScore >= 80 ? 'healthy' : overallScore >= 60 ? 'warning' : 'critical',
      lastUpdated: new Date(),
      trends: await this.calculateHealthTrends(timeRange),
    };
  }

  /**
   * Analyze trends across different services
   */
  private async analyzeCrossServiceTrends(timeRange: TimeRange): Promise<AnalyticsDataPoint[]> {
    const allMetrics = await this.analyticsService.getHistoricalData('*', timeRange);

    // Group by time intervals and calculate service correlations
    const timeGrouped = allMetrics.reduce((groups, point) => {
      const interval = Math.floor(point.timestamp.getTime() / (5 * 60 * 1000)) * (5 * 60 * 1000);
      if (!groups[interval]) {
        groups[interval] = [];
      }
      groups[interval].push(point);
      return groups;
    }, {} as Record<number, AnalyticsDataPoint[]>);

    return Object.entries(timeGrouped).map(([timestamp, points]) => {
      const aggregated = this.aggregateDataPoints(points);
      return {
        timestamp: new Date(parseInt(timestamp)),
        metrics: aggregated.metrics,
        dimensions: { aggregated: true },
      };
    });
  }

  /**
   * Find correlation insights between services
   */
  private async findCorrelationInsights(timeRange: TimeRange): Promise<CrossServiceInsights[]> {
    const insights: CrossServiceInsights[] = [];

    // Example correlations to analyze
    const correlations = [
      {
        primary: 'data_quality_score',
        secondary: 'storage_utilization',
        insight: 'Storage utilization impact on data quality',
      },
      {
        primary: 'pipeline_success_rate',
        secondary: 'data_source_response_time',
        insight: 'Data source performance impact on pipeline success',
      },
      {
        primary: 'storage_operations_per_second',
        secondary: 'pipeline_average_duration',
        insight: 'Storage performance impact on pipeline duration',
      },
    ];

    for (const correlation of correlations) {
      const primaryData = await this.analyticsService.getHistoricalData(correlation.primary, timeRange);
      const secondaryData = await this.analyticsService.getHistoricalData(correlation.secondary, timeRange);

      const correlationCoeff = this.calculateCorrelation(primaryData, secondaryData);

      if (Math.abs(correlationCoeff) > 0.5) {
        insights.push({
          type: 'correlation',
          description: correlation.insight,
          strength: Math.abs(correlationCoeff),
          direction: correlationCoeff > 0 ? 'positive' : 'negative',
          confidence: this.calculateConfidence(primaryData.length, correlationCoeff),
          recommendations: this.generateCorrelationRecommendations(correlation, correlationCoeff),
        });
      }
    }

    return insights;
  }

  /**
   * Aggregate KPIs from all services
   */
  private async aggregateServiceKPIs(timeRange: TimeRange): Promise<KPI[]> {
    const kpis: KPI[] = [];

    // System-wide KPIs
    const systemKPIs = [
      {
        id: 'overall_system_health',
        name: 'Overall System Health',
        description: 'Composite health score across all services',
        category: AnalyticsCategory.SYSTEM,
        metric: 'system_health_score',
        target: 95,
        unit: '%',
        thresholds: {
          critical: { min: 60 },
          warning: { min: 80 },
          target: { min: 95, max: 100 },
        },
      },
      {
        id: 'data_availability',
        name: 'Data Availability',
        description: 'Overall data source availability',
        category: AnalyticsCategory.DATA_QUALITY,
        metric: 'data_source_uptime',
        target: 99.9,
        unit: '%',
        thresholds: {
          critical: { min: 95 },
          warning: { min: 98 },
          target: { min: 99.5, max: 100 },
        },
      },
      {
        id: 'storage_efficiency',
        name: 'Storage Efficiency',
        description: 'Storage utilization and performance metrics',
        category: AnalyticsCategory.PERFORMANCE,
        metric: 'storage_utilization',
        target: 75,
        unit: '%',
        thresholds: {
          critical: { max: 95 },
          warning: { max: 85 },
          target: { min: 60, max: 80 },
        },
      },
      {
        id: 'pipeline_reliability',
        name: 'Pipeline Reliability',
        description: 'Data pipeline success rate',
        category: AnalyticsCategory.PERFORMANCE,
        metric: 'pipeline_success_rate',
        target: 98,
        unit: '%',
        thresholds: {
          critical: { min: 90 },
          warning: { min: 95 },
          target: { min: 98, max: 100 },
        },
      },
    ];

    // Calculate current values and status for each KPI
    for (const kpiConfig of systemKPIs) {
      const currentValue = await this.calculateKPIValue(kpiConfig.metric, timeRange);
      const status = this.determineKPIStatus(currentValue, kpiConfig.thresholds, kpiConfig.target);
      const trend = await this.calculateKPITrend(kpiConfig.metric, timeRange);

      kpis.push({
        ...kpiConfig,
        currentValue,
        status,
        trend,
        lastUpdated: new Date(),
      });
    }

    return kpis;
  }

  /**
   * Calculate overall performance score
   */
  private calculateOverallPerformanceScore(kpis: KPI[]): number {
    if (kpis.length === 0) return 0;

    const weights = {
      [KPIStatus.EXCELLENT]: 100,
      [KPIStatus.GOOD]: 80,
      [KPIStatus.WARNING]: 60,
      [KPIStatus.CRITICAL]: 30,
      [KPIStatus.UNKNOWN]: 50,
    };

    const totalScore = kpis.reduce((sum, kpi) => sum + weights[kpi.status], 0);
    return Math.round(totalScore / kpis.length);
  }

  /**
   * Generate actionable recommendations
   */
  private async generateRecommendations(
    systemHealth: SystemHealth,
    kpis: KPI[]
  ): Promise<string[]> {
    const recommendations: string[] = [];

    // System health recommendations
    if (systemHealth.overall < 80) {
      recommendations.push('System health is below optimal. Review component health scores and address critical issues.');
    }

    // KPI-specific recommendations
    kpis.forEach(kpi => {
      if (kpi.status === KPIStatus.CRITICAL) {
        recommendations.push(`Critical: ${kpi.name} requires immediate attention (${kpi.currentValue}${kpi.unit})`);
      } else if (kpi.status === KPIStatus.WARNING) {
        recommendations.push(`Warning: Monitor ${kpi.name} closely (${kpi.currentValue}${kpi.unit})`);
      }
    });

    // Trend-based recommendations
    const decliningKPIs = kpis.filter(kpi => kpi.trend === TrendDirection.DECREASING);
    if (decliningKPIs.length > 0) {
      recommendations.push(`Declining trends detected in: ${decliningKPIs.map(kpi => kpi.name).join(', ')}`);
    }

    return recommendations;
  }

  /**
   * Subscribe to analytics updates
   */
  onAnalyticsUpdate(callback: (data: DataManagementAnalytics) => void): () => void {
    this.updateCallbacks.push(callback);

    return () => {
      const index = this.updateCallbacks.indexOf(callback);
      if (index > -1) {
        this.updateCallbacks.splice(index, 1);
      }
    };
  }

  /**
   * Helper methods for calculations
   */
  private calculateDataSourceHealth(metrics: AnalyticsDataPoint): number {
    const activeConnections = metrics.metrics?.data_source_active_connections || 0;
    const failedConnections = metrics.metrics?.data_source_failed_connections || 0;
    const totalConnections = activeConnections + failedConnections;
    return totalConnections > 0 ? (activeConnections / totalConnections) * 100 : 100;
  }

  private calculateStorageHealth(metrics: AnalyticsDataPoint): number {
    const utilization = metrics.metrics?.storage_utilization || 0;
    // Optimal storage utilization is around 70-80%
    const optimal = 75;
    const deviation = Math.abs(utilization - optimal);
    return Math.max(0, 100 - (deviation * 2));
  }

  private calculateQualityHealth(metrics: AnalyticsDataPoint): number {
    return metrics.metrics?.data_quality_score || 0;
  }

  private calculatePipelineHealth(metrics: AnalyticsDataPoint): number {
    return metrics.metrics?.pipeline_success_rate || 0;
  }

  private async calculateHealthTrends(timeRange: TimeRange): Promise<Record<string, TrendDirection>> {
    // Simplified trend calculation
    return {
      overall: TrendDirection.STABLE,
      dataSource: TrendDirection.STABLE,
      storage: TrendDirection.STABLE,
      quality: TrendDirection.STABLE,
      pipeline: TrendDirection.STABLE,
    };
  }

  private aggregateDataPoints(points: AnalyticsDataPoint[]): AnalyticsDataPoint {
    const metrics: Record<string, number> = {};

    points.forEach(point => {
      Object.entries(point.metrics).forEach(([key, value]) => {
        if (typeof value === 'number') {
          metrics[key] = (metrics[key] || 0) + value;
        }
      });
    });

    // Average the metrics
    Object.keys(metrics).forEach(key => {
      metrics[key] = metrics[key] / points.length;
    });

    return {
      timestamp: new Date(),
      metrics,
      dimensions: { aggregated: true },
    };
  }

  private calculateCorrelation(data1: AnalyticsDataPoint[], data2: AnalyticsDataPoint[]): number {
    // Simplified correlation calculation
    if (data1.length !== data2.length || data1.length === 0) return 0;

    // This would be a proper Pearson correlation in a real implementation
    return Math.random() * 2 - 1; // Mock correlation between -1 and 1
  }

  private calculateConfidence(sampleSize: number, correlation: number): number {
    // Simplified confidence calculation
    const baseConfidence = Math.min(sampleSize / 100, 1) * 0.8;
    const strengthBonus = Math.abs(correlation) * 0.2;
    return Math.min(baseConfidence + strengthBonus, 1);
  }

  private generateCorrelationRecommendations(
    correlation: { primary: string; secondary: string; insight: string },
    coefficient: number
  ): string[] {
    const strength = Math.abs(coefficient);
    const direction = coefficient > 0 ? 'increases' : 'decreases';

    return [
      `When ${correlation.primary} ${direction}, ${correlation.secondary} tends to follow (${(strength * 100).toFixed(1)}% correlation)`,
      `Monitor both metrics together for optimal system performance`,
    ];
  }

  private async calculateKPIValue(metric: string, timeRange: TimeRange): Promise<number> {
    const data = await this.analyticsService.getHistoricalData(metric, timeRange);
    if (data.length === 0) return 0;

    // Return the most recent value
    const latest = data.reduce((latest, point) =>
      point.timestamp > latest.timestamp ? point : latest
    );

    return latest.metrics[metric] || 0;
  }

  private determineKPIStatus(value: number, thresholds: any, target: number): KPIStatus {
    if (thresholds.critical) {
      if (thresholds.critical.min !== undefined && value < thresholds.critical.min) return KPIStatus.CRITICAL;
      if (thresholds.critical.max !== undefined && value > thresholds.critical.max) return KPIStatus.CRITICAL;
    }

    if (thresholds.warning) {
      if (thresholds.warning.min !== undefined && value < thresholds.warning.min) return KPIStatus.WARNING;
      if (thresholds.warning.max !== undefined && value > thresholds.warning.max) return KPIStatus.WARNING;
    }

    if (thresholds.target) {
      if (thresholds.target.min !== undefined && thresholds.target.max !== undefined) {
        if (value >= thresholds.target.min && value <= thresholds.target.max) return KPIStatus.EXCELLENT;
      }
    }

    return KPIStatus.GOOD;
  }

  private async calculateKPITrend(metric: string, timeRange: TimeRange): Promise<TrendDirection> {
    const data = await this.analyticsService.getHistoricalData(metric, timeRange);
    if (data.length < 2) return TrendDirection.UNKNOWN;

    // Simple trend calculation based on first and last values
    const first = data[0].metrics[metric] || 0;
    const last = data[data.length - 1].metrics[metric] || 0;
    const change = ((last - first) / first) * 100;

    if (Math.abs(change) < 5) return TrendDirection.STABLE;
    return change > 0 ? TrendDirection.INCREASING : TrendDirection.DECREASING;
  }

  private invalidateCache(prefix: string): void {
    const keysToDelete = Array.from(this.cache.keys()).filter(key => key.startsWith(prefix));
    keysToDelete.forEach(key => this.cache.delete(key));
  }

  private startPeriodicUpdates(): void {
    setInterval(async () => {
      try {
        await this.generateDataManagementAnalytics();
      } catch (error) {
        console.error('Periodic analytics update failed:', error);
      }
    }, this.config.updateInterval);
  }

  /**
   * Clean up resources
   */
  dispose(): void {
    this.cache.clear();
    this.updateCallbacks.length = 0;
  }
}

// Singleton instance
let analyticsIntegrationInstance: AnalyticsIntegrationService | null = null;

export const getAnalyticsIntegrationService = (
  config?: Partial<AnalyticsIntegrationConfig>
): AnalyticsIntegrationService => {
  if (!analyticsIntegrationInstance) {
    analyticsIntegrationInstance = new AnalyticsIntegrationService(config);
  }
  return analyticsIntegrationInstance;
};
