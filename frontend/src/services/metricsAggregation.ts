/**
 * MetricsAggregationService
 *
 * Service for KPI calculations, performance monitoring, and real-time metrics aggregation
 */

import {
  IMetricsAggregationService,
  KPI,
  KPIStatus,
  KPIThresholds,
  AnalyticsCategory,
  AnalyticsMetric,
  AnalyticsDataPoint,
  TimeRange,
  TimeInterval,
} from '@/types/analytics';
import { AnalyticsService, getAnalyticsService } from './analytics';

export class MetricsAggregationService implements IMetricsAggregationService {
  private baseUrl: string;
  private analyticsService: AnalyticsService;
  private kpis: Map<string, KPI> = new Map();
  private cache: Map<string, { data: any; expiry: number }> = new Map();
  private cacheTimeout = 2 * 60 * 1000; // 2 minutes

  constructor(baseUrl: string = '/api/metrics', analyticsService?: AnalyticsService) {
    this.baseUrl = baseUrl;
    this.analyticsService = analyticsService || getAnalyticsService();
    this.initializeDefaultKPIs();
  }

  // KPI management methods
  async getKPIs(category?: AnalyticsCategory): Promise<KPI[]> {
    const cacheKey = `kpis:${category || 'all'}`;
    const cached = this.getFromCache(cacheKey);
    if (cached) return cached;

    try {
      const url = category
        ? `${this.baseUrl}/kpis?category=${category}`
        : `${this.baseUrl}/kpis`;

      const response = await fetch(url);

      if (!response.ok) {
        throw new Error(`Failed to fetch KPIs: ${response.statusText}`);
      }

      const kpis = await response.json();

      // Update local cache
      kpis.forEach((kpi: KPI) => this.kpis.set(kpi.id, kpi));

      this.setCache(cacheKey, kpis);
      return kpis;
    } catch (error) {
      console.warn('Failed to fetch KPIs from backend, using local data:', error);

      // Filter local KPIs by category
      const localKPIs = Array.from(this.kpis.values());
      return category ? localKPIs.filter(kpi => kpi.category === category) : localKPIs;
    }
  }

  async createKPI(kpiData: Omit<KPI, 'id' | 'currentValue' | 'status' | 'lastUpdated'>): Promise<KPI> {
    const kpi: KPI = {
      ...kpiData,
      id: this.generateKPIId(kpiData.name),
      currentValue: 0,
      status: KPIStatus.UNKNOWN,
      lastUpdated: new Date(),
    };

    try {
      const response = await fetch(`${this.baseUrl}/kpis`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(kpi),
      });

      if (response.ok) {
        const savedKPI = await response.json();
        this.kpis.set(savedKPI.id, savedKPI);
        this.clearCacheByPattern('kpis:');
        return savedKPI;
      }
    } catch (error) {
      console.warn('Failed to save KPI to backend:', error);
    }

    // Save to local cache
    this.kpis.set(kpi.id, kpi);
    this.clearCacheByPattern('kpis:');
    return kpi;
  }

  async updateKPI(id: string, updates: Partial<KPI>): Promise<KPI> {
    const existingKPI = this.kpis.get(id);
    if (!existingKPI) {
      throw new Error(`KPI not found: ${id}`);
    }

    const updatedKPI: KPI = {
      ...existingKPI,
      ...updates,
      lastUpdated: new Date(),
    };

    // Recalculate status if thresholds or current value changed
    if (updates.thresholds || updates.currentValue !== undefined) {
      updatedKPI.status = this.calculateKPIStatus(updatedKPI);
    }

    try {
      const response = await fetch(`${this.baseUrl}/kpis/${id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(updatedKPI),
      });

      if (response.ok) {
        const savedKPI = await response.json();
        this.kpis.set(id, savedKPI);
        this.clearCacheByPattern('kpis:');
        return savedKPI;
      }
    } catch (error) {
      console.warn('Failed to update KPI in backend:', error);
    }

    // Update local cache
    this.kpis.set(id, updatedKPI);
    this.clearCacheByPattern('kpis:');
    return updatedKPI;
  }

  async deleteKPI(id: string): Promise<boolean> {
    try {
      const response = await fetch(`${this.baseUrl}/kpis/${id}`, {
        method: 'DELETE',
      });

      if (response.ok) {
        this.kpis.delete(id);
        this.clearCacheByPattern('kpis:');
        return true;
      }
    } catch (error) {
      console.warn('Failed to delete KPI from backend:', error);
    }

    // Remove from local cache
    const existed = this.kpis.delete(id);
    this.clearCacheByPattern('kpis:');
    return existed;
  }

  calculateKPIStatus(kpi: KPI): KPIStatus {
    const value = kpi.currentValue;
    const thresholds = kpi.thresholds;

    // Check critical thresholds
    if (thresholds.critical.min !== undefined && value < thresholds.critical.min) {
      return KPIStatus.CRITICAL;
    }
    if (thresholds.critical.max !== undefined && value > thresholds.critical.max) {
      return KPIStatus.CRITICAL;
    }

    // Check warning thresholds
    if (thresholds.warning.min !== undefined && value < thresholds.warning.min) {
      return KPIStatus.WARNING;
    }
    if (thresholds.warning.max !== undefined && value > thresholds.warning.max) {
      return KPIStatus.WARNING;
    }

    // Check if within target range
    if (value >= thresholds.target.min && value <= thresholds.target.max) {
      return KPIStatus.EXCELLENT;
    }

    // Within acceptable range but not in target
    return KPIStatus.GOOD;
  }

  // Performance monitoring methods
  async getPerformanceSummary(category?: AnalyticsCategory): Promise<{
    kpis: KPI[];
    summary: {
      total: number;
      excellent: number;
      good: number;
      warning: number;
      critical: number;
    };
  }> {
    const kpis = await this.getKPIs(category);

    // Update KPI values with latest metrics
    await this.refreshKPIValues(kpis);

    const summary = {
      total: kpis.length,
      excellent: kpis.filter(kpi => kpi.status === KPIStatus.EXCELLENT).length,
      good: kpis.filter(kpi => kpi.status === KPIStatus.GOOD).length,
      warning: kpis.filter(kpi => kpi.status === KPIStatus.WARNING).length,
      critical: kpis.filter(kpi => kpi.status === KPIStatus.CRITICAL).length,
    };

    return { kpis, summary };
  }

  // Real-time aggregation methods
  async aggregateRealTimeMetrics(): Promise<AnalyticsMetric[]> {
    const cacheKey = 'realtime-metrics';
    const cached = this.getFromCache(cacheKey);
    if (cached) return cached;

    try {
      // Get metrics from all categories
      const categories = Object.values(AnalyticsCategory);
      const metricsPromises = categories.map(category =>
        this.analyticsService.getMetrics(category)
      );

      const allMetrics = (await Promise.all(metricsPromises)).flat();

      // Aggregate real-time metrics
      const aggregatedMetrics = await this.performRealTimeAggregation(allMetrics);

      this.setCache(cacheKey, aggregatedMetrics);
      return aggregatedMetrics;
    } catch (error) {
      console.error('Failed to aggregate real-time metrics:', error);
      return this.simulateRealTimeMetrics();
    }
  }

  async calculateRollingAverages(metric: string, windowSize: number): Promise<AnalyticsDataPoint[]> {
    // Get historical data for the metric
    const timeRange: TimeRange = {
      start: new Date(Date.now() - windowSize * 60 * 60 * 1000), // windowSize hours ago
      end: new Date(),
      interval: TimeInterval.HOUR,
    };

    const historicalData = await this.analyticsService.getHistoricalData(metric, timeRange);

    if (historicalData.length < windowSize) {
      return historicalData; // Not enough data for rolling average
    }

    const rollingAverages: AnalyticsDataPoint[] = [];

    for (let i = windowSize - 1; i < historicalData.length; i++) {
      const window = historicalData.slice(i - windowSize + 1, i + 1);
      const average = window.reduce((sum, point) => sum + (point.metrics[metric] || 0), 0) / windowSize;

      rollingAverages.push({
        timestamp: historicalData[i].timestamp,
        metrics: { [metric]: average },
        dimensions: { aggregationType: 'rolling_average', windowSize: windowSize.toString() },
      });
    }

    return rollingAverages;
  }

  // Advanced analytics methods
  async calculateServiceLevelAgreement(
    metric: string,
    threshold: number,
    timeRange: TimeRange
  ): Promise<{
    slaCompliance: number;
    totalMeasurements: number;
    breaches: number;
    availabilityPercentage: number;
  }> {
    const historicalData = await this.analyticsService.getHistoricalData(metric, timeRange);

    if (historicalData.length === 0) {
      return {
        slaCompliance: 0,
        totalMeasurements: 0,
        breaches: 0,
        availabilityPercentage: 0,
      };
    }

    const totalMeasurements = historicalData.length;
    const breaches = historicalData.filter(point =>
      (point.metrics[metric] || 0) > threshold
    ).length;

    const slaCompliance = ((totalMeasurements - breaches) / totalMeasurements) * 100;
    const availabilityPercentage = slaCompliance;

    return {
      slaCompliance,
      totalMeasurements,
      breaches,
      availabilityPercentage,
    };
  }

  async calculateMTTR(incidents: Array<{ startTime: Date; endTime: Date }>): Promise<number> {
    if (incidents.length === 0) return 0;

    const totalRecoveryTime = incidents.reduce((total, incident) => {
      return total + (incident.endTime.getTime() - incident.startTime.getTime());
    }, 0);

    return totalRecoveryTime / incidents.length; // Average in milliseconds
  }

  async calculateMTBF(
    failures: Date[],
    observationPeriod: { start: Date; end: Date }
  ): Promise<number> {
    if (failures.length <= 1) return 0;

    const observationTime = observationPeriod.end.getTime() - observationPeriod.start.getTime();
    const operationalTime = observationTime; // Simplified - should subtract downtime

    return operationalTime / (failures.length - 1); // Average time between failures
  }

  // Alerting and notifications
  async evaluateKPIThresholds(): Promise<Array<{
    kpi: KPI;
    breachType: 'critical' | 'warning';
    message: string;
  }>> {
    const kpis = await this.getKPIs();
    const alerts: Array<{
      kpi: KPI;
      breachType: 'critical' | 'warning';
      message: string;
    }> = [];

    for (const kpi of kpis) {
      await this.refreshKPIValue(kpi);

      if (kpi.status === KPIStatus.CRITICAL) {
        alerts.push({
          kpi,
          breachType: 'critical',
          message: `KPI "${kpi.name}" has breached critical thresholds (${kpi.currentValue} ${kpi.unit})`,
        });
      } else if (kpi.status === KPIStatus.WARNING) {
        alerts.push({
          kpi,
          breachType: 'warning',
          message: `KPI "${kpi.name}" has breached warning thresholds (${kpi.currentValue} ${kpi.unit})`,
        });
      }
    }

    return alerts;
  }

  // Data quality metrics
  async calculateDataQualityScore(category: AnalyticsCategory): Promise<{
    overallScore: number;
    completeness: number;
    accuracy: number;
    consistency: number;
    timeliness: number;
  }> {
    // This would integrate with the DataQualityService in a real implementation
    const metrics = await this.analyticsService.getMetrics(category);

    // Simulate quality metrics calculation
    const completeness = Math.random() * 20 + 80; // 80-100%
    const accuracy = Math.random() * 15 + 85; // 85-100%
    const consistency = Math.random() * 25 + 75; // 75-100%
    const timeliness = Math.random() * 10 + 90; // 90-100%

    const overallScore = (completeness + accuracy + consistency + timeliness) / 4;

    return {
      overallScore,
      completeness,
      accuracy,
      consistency,
      timeliness,
    };
  }

  // Cost analysis
  async calculateCostMetrics(timeRange: TimeRange): Promise<{
    totalCost: number;
    costByCategory: Record<AnalyticsCategory, number>;
    costPerTransaction: number;
    costTrend: number;
  }> {
    // This would integrate with cost tracking systems in a real implementation
    const categories = Object.values(AnalyticsCategory);
    const costByCategory: Record<AnalyticsCategory, number> = {} as any;

    let totalCost = 0;
    categories.forEach(category => {
      const cost = Math.random() * 1000 + 500; // $500-1500 per category
      costByCategory[category] = cost;
      totalCost += cost;
    });

    const costPerTransaction = totalCost / 10000; // Assuming 10k transactions
    const costTrend = (Math.random() - 0.5) * 0.2; // -10% to +10% trend

    return {
      totalCost,
      costByCategory,
      costPerTransaction,
      costTrend,
    };
  }

  // Private helper methods
  private async refreshKPIValues(kpis: KPI[]): Promise<void> {
    const updatePromises = kpis.map(kpi => this.refreshKPIValue(kpi));
    await Promise.all(updatePromises);
  }

  private async refreshKPIValue(kpi: KPI): Promise<void> {
    try {
      // Get latest metric value
      const timeRange: TimeRange = {
        start: new Date(Date.now() - 60 * 60 * 1000), // Last hour
        end: new Date(),
        interval: TimeInterval.MINUTE,
      };

      const historicalData = await this.analyticsService.getHistoricalData(kpi.metric, timeRange);

      if (historicalData.length > 0) {
        const latestPoint = historicalData[historicalData.length - 1];
        const newValue = latestPoint.metrics[kpi.metric] || 0;

        kpi.previousValue = kpi.currentValue;
        kpi.currentValue = newValue;
        kpi.status = this.calculateKPIStatus(kpi);
        kpi.lastUpdated = new Date();

        // Calculate trend
        if (kpi.previousValue !== undefined) {
          const change = newValue - kpi.previousValue;
          if (Math.abs(change) > 0.01) {
            kpi.trend = change > 0 ? 'increasing' : 'decreasing';
          } else {
            kpi.trend = 'stable';
          }
        }

        // Update in local cache
        this.kpis.set(kpi.id, kpi);
      }
    } catch (error) {
      console.warn(`Failed to refresh KPI value for ${kpi.name}:`, error);
    }
  }

  private async performRealTimeAggregation(metrics: AnalyticsMetric[]): Promise<AnalyticsMetric[]> {
    // Group metrics by category and calculate aggregates
    const categoryGroups = new Map<AnalyticsCategory, AnalyticsMetric[]>();

    metrics.forEach(metric => {
      if (!categoryGroups.has(metric.category)) {
        categoryGroups.set(metric.category, []);
      }
      categoryGroups.get(metric.category)!.push(metric);
    });

    const aggregatedMetrics: AnalyticsMetric[] = [];

    categoryGroups.forEach((categoryMetrics, category) => {
      // Calculate average for the category
      const avgValue = categoryMetrics.reduce((sum, metric) => sum + metric.value, 0) / categoryMetrics.length;

      aggregatedMetrics.push({
        id: `${category}_avg`,
        name: `${category}_average`,
        description: `Average value for ${category} category`,
        category,
        value: avgValue,
        unit: 'avg',
        timestamp: new Date(),
        metadata: {
          aggregationType: 'average',
          sourceCount: categoryMetrics.length,
        },
        tags: ['aggregated', 'real-time'],
      });

      // Calculate total for count-based metrics
      const countMetrics = categoryMetrics.filter(m => m.unit === 'count');
      if (countMetrics.length > 0) {
        const totalValue = countMetrics.reduce((sum, metric) => sum + metric.value, 0);

        aggregatedMetrics.push({
          id: `${category}_total`,
          name: `${category}_total`,
          description: `Total count for ${category} category`,
          category,
          value: totalValue,
          unit: 'count',
          timestamp: new Date(),
          metadata: {
            aggregationType: 'sum',
            sourceCount: countMetrics.length,
          },
          tags: ['aggregated', 'real-time'],
        });
      }
    });

    return aggregatedMetrics;
  }

  private initializeDefaultKPIs(): void {
    const defaultKPIs: Array<Omit<KPI, 'id' | 'currentValue' | 'status' | 'lastUpdated'>> = [
      {
        name: 'System Availability',
        description: 'Overall system uptime percentage',
        category: AnalyticsCategory.SYSTEM,
        metric: 'uptime_percentage',
        target: 99.9,
        unit: '%',
        thresholds: {
          critical: { min: 95 },
          warning: { min: 98 },
          target: { min: 99.5, max: 100 },
        },
        trend: 'stable',
      },
      {
        name: 'Average Response Time',
        description: 'Average API response time',
        category: AnalyticsCategory.PERFORMANCE,
        metric: 'avg_response_time',
        target: 200,
        unit: 'ms',
        thresholds: {
          critical: { max: 1000 },
          warning: { max: 500 },
          target: { min: 0, max: 200 },
        },
        trend: 'stable',
      },
      {
        name: 'Error Rate',
        description: 'System error rate percentage',
        category: AnalyticsCategory.PERFORMANCE,
        metric: 'error_rate',
        target: 0.1,
        unit: '%',
        thresholds: {
          critical: { max: 5 },
          warning: { max: 1 },
          target: { min: 0, max: 0.5 },
        },
        trend: 'stable',
      },
      {
        name: 'Data Quality Score',
        description: 'Overall data quality percentage',
        category: AnalyticsCategory.DATA_QUALITY,
        metric: 'quality_score',
        target: 95,
        unit: '%',
        thresholds: {
          critical: { min: 80 },
          warning: { min: 90 },
          target: { min: 95, max: 100 },
        },
        trend: 'stable',
      },
      {
        name: 'Storage Utilization',
        description: 'Storage usage percentage',
        category: AnalyticsCategory.STORAGE,
        metric: 'storage_usage',
        target: 70,
        unit: '%',
        thresholds: {
          critical: { max: 95 },
          warning: { max: 85 },
          target: { min: 50, max: 80 },
        },
        trend: 'stable',
      },
      {
        name: 'Pipeline Success Rate',
        description: 'ML/ETL pipeline success percentage',
        category: AnalyticsCategory.PIPELINE,
        metric: 'pipeline_success_rate',
        target: 98,
        unit: '%',
        thresholds: {
          critical: { min: 90 },
          warning: { min: 95 },
          target: { min: 98, max: 100 },
        },
        trend: 'stable',
      },
    ];

    defaultKPIs.forEach(kpiData => {
      const kpi: KPI = {
        ...kpiData,
        id: this.generateKPIId(kpiData.name),
        currentValue: 0,
        status: KPIStatus.UNKNOWN,
        lastUpdated: new Date(),
      };
      this.kpis.set(kpi.id, kpi);
    });
  }

  private generateKPIId(name: string): string {
    return `kpi_${name.toLowerCase().replace(/\s+/g, '_')}_${Date.now()}`;
  }

  private getFromCache(key: string): any {
    const cached = this.cache.get(key);
    if (cached && cached.expiry > Date.now()) {
      return cached.data;
    }
    this.cache.delete(key);
    return null;
  }

  private setCache(key: string, data: any): void {
    this.cache.set(key, {
      data,
      expiry: Date.now() + this.cacheTimeout,
    });
  }

  private clearCacheByPattern(pattern: string): void {
    for (const key of this.cache.keys()) {
      if (key.includes(pattern)) {
        this.cache.delete(key);
      }
    }
  }

  private simulateRealTimeMetrics(): AnalyticsMetric[] {
    const categories = Object.values(AnalyticsCategory);
    const metrics: AnalyticsMetric[] = [];

    categories.forEach(category => {
      metrics.push({
        id: `${category}_realtime`,
        name: `${category}_current`,
        description: `Real-time ${category} metric`,
        category,
        value: Math.random() * 100,
        unit: 'units',
        timestamp: new Date(),
        tags: ['real-time', 'simulated'],
      });
    });

    return metrics;
  }
}

// Singleton instance
let globalMetricsAggregationService: MetricsAggregationService | null = null;

export const getMetricsAggregationService = (
  baseUrl?: string,
  analyticsService?: AnalyticsService
): MetricsAggregationService => {
  if (!globalMetricsAggregationService) {
    globalMetricsAggregationService = new MetricsAggregationService(baseUrl, analyticsService);
  }
  return globalMetricsAggregationService;
};
