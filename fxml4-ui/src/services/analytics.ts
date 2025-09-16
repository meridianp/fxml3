/**
 * AnalyticsService
 *
 * Core analytics service for data aggregation, trend analysis, and statistical processing
 */

import {
  IAnalyticsService,
  AnalyticsQuery,
  AnalyticsResult,
  AnalyticsMetric,
  AnalyticsDataPoint,
  AnalyticsCategory,
  TimeRange,
  TimeInterval,
  TrendAnalysis,
  TrendDirection,
  AnomalyData,
  AnomalyType,
  AnomalySeverity,
  ForecastData,
  SeasonalityData,
  StatisticalSummary,
  CorrelationAnalysis,
  PerformanceBaseline,
  FilterOperator,
  AggregationType,
} from '@/types/analytics';

export class AnalyticsService implements IAnalyticsService {
  private baseUrl: string;
  private cache: Map<string, { data: any; expiry: number }> = new Map();
  private cacheTimeout = 5 * 60 * 1000; // 5 minutes

  constructor(baseUrl: string = '/api/analytics') {
    this.baseUrl = baseUrl;
  }

  // Data aggregation methods
  async aggregate(query: AnalyticsQuery): Promise<AnalyticsResult> {
    const cacheKey = this.generateCacheKey('aggregate', query);
    const cached = this.getFromCache(cacheKey);
    if (cached) return cached;

    try {
      const response = await fetch(`${this.baseUrl}/aggregate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(query),
      });

      if (!response.ok) {
        throw new Error(`Analytics aggregation failed: ${response.statusText}`);
      }

      const result = await response.json();
      this.setCache(cacheKey, result);
      return result;
    } catch (error) {
      // Fallback to simulated data for development
      return this.simulateAggregateData(query);
    }
  }

  async getMetrics(category?: AnalyticsCategory): Promise<AnalyticsMetric[]> {
    const cacheKey = this.generateCacheKey('metrics', { category });
    const cached = this.getFromCache(cacheKey);
    if (cached) return cached;

    try {
      const url = category
        ? `${this.baseUrl}/metrics?category=${category}`
        : `${this.baseUrl}/metrics`;

      const response = await fetch(url);

      if (!response.ok) {
        throw new Error(`Failed to fetch metrics: ${response.statusText}`);
      }

      const metrics = await response.json();
      this.setCache(cacheKey, metrics);
      return metrics;
    } catch (error) {
      // Fallback to simulated data
      return this.simulateMetricsData(category);
    }
  }

  async getHistoricalData(metric: string, timeRange: TimeRange): Promise<AnalyticsDataPoint[]> {
    const cacheKey = this.generateCacheKey('historical', { metric, timeRange });
    const cached = this.getFromCache(cacheKey);
    if (cached) return cached;

    try {
      const response = await fetch(`${this.baseUrl}/historical/${metric}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(timeRange),
      });

      if (!response.ok) {
        throw new Error(`Failed to fetch historical data: ${response.statusText}`);
      }

      const data = await response.json();
      this.setCache(cacheKey, data);
      return data;
    } catch (error) {
      // Fallback to simulated data
      return this.simulateHistoricalData(metric, timeRange);
    }
  }

  // Trend analysis methods
  async analyzeTrend(metric: string, timeRange: TimeRange): Promise<TrendAnalysis> {
    const historicalData = await this.getHistoricalData(metric, timeRange);

    if (historicalData.length < 2) {
      return {
        metric,
        timeRange,
        trend: TrendDirection.UNKNOWN,
        confidence: 0,
        slope: 0,
        correlation: 0,
      };
    }

    // Calculate trend using linear regression
    const values = historicalData.map((point, index) => ({
      x: index,
      y: point.metrics[metric] || 0,
    }));

    const { slope, correlation, rSquared } = this.calculateLinearRegression(values);

    // Determine trend direction
    let trend: TrendDirection;
    if (Math.abs(slope) < 0.01) {
      trend = TrendDirection.STABLE;
    } else if (slope > 0) {
      trend = TrendDirection.INCREASING;
    } else {
      trend = TrendDirection.DECREASING;
    }

    // Calculate volatility
    const meanValue = values.reduce((sum, v) => sum + v.y, 0) / values.length;
    const variance = values.reduce((sum, v) => sum + Math.pow(v.y - meanValue, 2), 0) / values.length;
    const volatility = Math.sqrt(variance) / meanValue;

    if (volatility > 0.2) {
      trend = TrendDirection.VOLATILE;
    }

    // Generate forecast
    const forecast = await this.generateForecast(metric, timeRange, TimeInterval.DAY);

    // Detect anomalies
    const anomalies = await this.detectAnomalies(metric, timeRange);

    // Analyze seasonality
    const seasonality = this.analyzeSeasonality(historicalData, metric);

    return {
      metric,
      timeRange,
      trend,
      confidence: Math.min(rSquared, 1),
      slope,
      correlation,
      forecast,
      anomalies,
      seasonality,
    };
  }

  async detectAnomalies(metric: string, timeRange: TimeRange): Promise<AnomalyData[]> {
    const historicalData = await this.getHistoricalData(metric, timeRange);

    if (historicalData.length < 10) {
      return [];
    }

    const values = historicalData.map(point => point.metrics[metric] || 0);
    const mean = values.reduce((sum, val) => sum + val, 0) / values.length;
    const stdDev = Math.sqrt(
      values.reduce((sum, val) => sum + Math.pow(val - mean, 2), 0) / values.length
    );

    const anomalies: AnomalyData[] = [];
    const threshold = 2; // 2 standard deviations

    historicalData.forEach((point, index) => {
      const value = point.metrics[metric] || 0;
      const deviationScore = Math.abs(value - mean) / stdDev;

      if (deviationScore > threshold) {
        const anomalyType = value > mean ? AnomalyType.SPIKE : AnomalyType.DIP;
        const severity = deviationScore > 3 ? AnomalySeverity.CRITICAL :
                        deviationScore > 2.5 ? AnomalySeverity.HIGH :
                        deviationScore > 2 ? AnomalySeverity.MEDIUM : AnomalySeverity.LOW;

        anomalies.push({
          timestamp: point.timestamp,
          value,
          expectedValue: mean,
          deviationScore,
          anomalyType,
          severity,
        });
      }
    });

    return anomalies;
  }

  async generateForecast(metric: string, timeRange: TimeRange, horizon: TimeInterval): Promise<ForecastData[]> {
    const historicalData = await this.getHistoricalData(metric, timeRange);

    if (historicalData.length < 5) {
      return [];
    }

    // Simple moving average forecast (in production, use more sophisticated models)
    const values = historicalData.map(point => point.metrics[metric] || 0);
    const windowSize = Math.min(5, values.length);
    const recentValues = values.slice(-windowSize);
    const avgValue = recentValues.reduce((sum, val) => sum + val, 0) / recentValues.length;

    // Calculate standard deviation for confidence bands
    const stdDev = Math.sqrt(
      recentValues.reduce((sum, val) => sum + Math.pow(val - avgValue, 2), 0) / recentValues.length
    );

    // Generate forecast points
    const forecast: ForecastData[] = [];
    const intervalMs = this.getIntervalMs(horizon);
    const startTime = new Date(timeRange.end.getTime() + intervalMs);

    for (let i = 0; i < 10; i++) {
      const timestamp = new Date(startTime.getTime() + (i * intervalMs));
      const confidence = Math.max(0.1, 0.9 - (i * 0.08)); // Decreasing confidence

      forecast.push({
        timestamp,
        value: avgValue,
        confidence,
        upperBound: avgValue + (stdDev * 2 * (1 - confidence + 0.1)),
        lowerBound: avgValue - (stdDev * 2 * (1 - confidence + 0.1)),
      });
    }

    return forecast;
  }

  // Statistical analysis methods
  async getStatisticalSummary(metric: string, timeRange: TimeRange): Promise<StatisticalSummary> {
    const historicalData = await this.getHistoricalData(metric, timeRange);
    const values = historicalData.map(point => point.metrics[metric] || 0).filter(v => !isNaN(v));

    if (values.length === 0) {
      throw new Error(`No valid data found for metric: ${metric}`);
    }

    // Sort values for percentile calculations
    const sortedValues = [...values].sort((a, b) => a - b);

    // Basic statistics
    const count = values.length;
    const sum = values.reduce((acc, val) => acc + val, 0);
    const mean = sum / count;
    const min = Math.min(...values);
    const max = Math.max(...values);
    const range = max - min;

    // Median
    const median = count % 2 === 0
      ? (sortedValues[count / 2 - 1] + sortedValues[count / 2]) / 2
      : sortedValues[Math.floor(count / 2)];

    // Mode (most frequent value)
    const frequencyMap = new Map<number, number>();
    values.forEach(val => {
      frequencyMap.set(val, (frequencyMap.get(val) || 0) + 1);
    });
    const mode = [...frequencyMap.entries()].reduce((a, b) => a[1] > b[1] ? a : b)[0];

    // Variance and standard deviation
    const variance = values.reduce((acc, val) => acc + Math.pow(val - mean, 2), 0) / count;
    const standardDeviation = Math.sqrt(variance);

    // Skewness and kurtosis
    const skewness = values.reduce((acc, val) => acc + Math.pow((val - mean) / standardDeviation, 3), 0) / count;
    const kurtosis = values.reduce((acc, val) => acc + Math.pow((val - mean) / standardDeviation, 4), 0) / count - 3;

    // Percentiles
    const getPercentile = (p: number) => {
      const index = (p / 100) * (count - 1);
      const lower = Math.floor(index);
      const upper = Math.ceil(index);
      return lower === upper
        ? sortedValues[lower]
        : sortedValues[lower] + (sortedValues[upper] - sortedValues[lower]) * (index - lower);
    };

    return {
      metric,
      timeRange,
      count,
      sum,
      mean,
      median,
      mode,
      min,
      max,
      range,
      variance,
      standardDeviation,
      skewness,
      kurtosis,
      percentiles: {
        '25th': getPercentile(25),
        '50th': getPercentile(50),
        '75th': getPercentile(75),
        '90th': getPercentile(90),
        '95th': getPercentile(95),
        '99th': getPercentile(99),
      },
    };
  }

  async calculateCorrelation(metric1: string, metric2: string, timeRange: TimeRange): Promise<CorrelationAnalysis> {
    const [data1, data2] = await Promise.all([
      this.getHistoricalData(metric1, timeRange),
      this.getHistoricalData(metric2, timeRange),
    ]);

    // Align data points by timestamp
    const alignedData = this.alignDataByTimestamp(data1, data2, metric1, metric2);

    if (alignedData.length < 3) {
      throw new Error('Insufficient data for correlation analysis');
    }

    const values1 = alignedData.map(d => d.value1);
    const values2 = alignedData.map(d => d.value2);

    // Calculate Pearson correlation coefficient
    const { correlation, pValue } = this.calculatePearsonCorrelation(values1, values2);

    return {
      metric1,
      metric2,
      timeRange,
      coefficient: correlation,
      pValue,
      significance: pValue < 0.05 ? 0.95 : pValue < 0.01 ? 0.99 : 1 - pValue,
      type: 'pearson',
    };
  }

  // Baseline and benchmark methods
  async createBaseline(metric: string, timeRange: TimeRange): Promise<PerformanceBaseline> {
    const historicalData = await this.getHistoricalData(metric, timeRange);
    const values = historicalData.map(point => point.metrics[metric] || 0);

    if (values.length === 0) {
      throw new Error(`No data available for baseline creation: ${metric}`);
    }

    const mean = values.reduce((sum, val) => sum + val, 0) / values.length;
    const stdDev = Math.sqrt(
      values.reduce((sum, val) => sum + Math.pow(val - mean, 2), 0) / values.length
    );

    // Confidence based on sample size and stability
    const confidence = Math.min(0.95, values.length / 100);

    // Check for seasonality
    const seasonality = this.detectSeasonality(values);

    const baseline: PerformanceBaseline = {
      metric,
      category: this.inferCategory(metric),
      baseline: mean,
      unit: this.inferUnit(metric),
      confidence,
      createdAt: new Date(),
      validUntil: new Date(Date.now() + 30 * 24 * 60 * 60 * 1000), // 30 days
      metadata: {
        sampleSize: values.length,
        method: 'moving_average',
        seasonality,
      },
    };

    // Save baseline to backend
    try {
      const response = await fetch(`${this.baseUrl}/baselines`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(baseline),
      });

      if (response.ok) {
        return await response.json();
      }
    } catch (error) {
      console.warn('Failed to save baseline to backend:', error);
    }

    return baseline;
  }

  async getBaselines(category?: AnalyticsCategory): Promise<PerformanceBaseline[]> {
    try {
      const url = category
        ? `${this.baseUrl}/baselines?category=${category}`
        : `${this.baseUrl}/baselines`;

      const response = await fetch(url);

      if (response.ok) {
        return await response.json();
      }
    } catch (error) {
      console.warn('Failed to fetch baselines from backend:', error);
    }

    // Return simulated baselines
    return this.simulateBaselines(category);
  }

  async compareToBaseline(metric: string, value: number): Promise<{ deviation: number; significance: number }> {
    const baselines = await this.getBaselines();
    const baseline = baselines.find(b => b.metric === metric);

    if (!baseline) {
      throw new Error(`No baseline found for metric: ${metric}`);
    }

    const deviation = ((value - baseline.baseline) / baseline.baseline) * 100;
    const significance = Math.abs(deviation) / 10; // Simplified significance calculation

    return { deviation, significance: Math.min(significance, 1) };
  }

  // Private helper methods
  private generateCacheKey(operation: string, params: any): string {
    return `${operation}:${JSON.stringify(params)}`;
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

  private calculateLinearRegression(points: Array<{ x: number; y: number }>): {
    slope: number;
    intercept: number;
    correlation: number;
    rSquared: number;
  } {
    const n = points.length;
    const sumX = points.reduce((sum, p) => sum + p.x, 0);
    const sumY = points.reduce((sum, p) => sum + p.y, 0);
    const sumXY = points.reduce((sum, p) => sum + p.x * p.y, 0);
    const sumXX = points.reduce((sum, p) => sum + p.x * p.x, 0);
    const sumYY = points.reduce((sum, p) => sum + p.y * p.y, 0);

    const slope = (n * sumXY - sumX * sumY) / (n * sumXX - sumX * sumX);
    const intercept = (sumY - slope * sumX) / n;

    const correlation = (n * sumXY - sumX * sumY) /
      Math.sqrt((n * sumXX - sumX * sumX) * (n * sumYY - sumY * sumY));

    const rSquared = correlation * correlation;

    return { slope, intercept, correlation, rSquared };
  }

  private calculatePearsonCorrelation(x: number[], y: number[]): { correlation: number; pValue: number } {
    const n = x.length;
    const sumX = x.reduce((a, b) => a + b, 0);
    const sumY = y.reduce((a, b) => a + b, 0);
    const sumXY = x.reduce((sum, xi, i) => sum + xi * y[i], 0);
    const sumXX = x.reduce((sum, xi) => sum + xi * xi, 0);
    const sumYY = y.reduce((sum, yi) => sum + yi * yi, 0);

    const numerator = n * sumXY - sumX * sumY;
    const denominator = Math.sqrt((n * sumXX - sumX * sumX) * (n * sumYY - sumY * sumY));

    const correlation = denominator === 0 ? 0 : numerator / denominator;

    // Simplified p-value calculation (t-test)
    const t = correlation * Math.sqrt((n - 2) / (1 - correlation * correlation));
    const pValue = 2 * (1 - this.cumulativeStandardNormal(Math.abs(t)));

    return { correlation, pValue };
  }

  private cumulativeStandardNormal(x: number): number {
    // Simplified approximation of cumulative standard normal distribution
    return 0.5 * (1 + Math.sign(x) * Math.sqrt(1 - Math.exp(-2 * x * x / Math.PI)));
  }

  private analyzeSeasonality(data: AnalyticsDataPoint[], metric: string): SeasonalityData | undefined {
    const values = data.map(point => point.metrics[metric] || 0);

    if (values.length < 24) { // Need at least 24 points for daily seasonality
      return undefined;
    }

    // Simplified seasonality detection
    const hourlyPattern = this.detectSeasonalPattern(values, 24);
    const dailyPattern = this.detectSeasonalPattern(values, 7 * 24);

    if (hourlyPattern.strength > 0.1 || dailyPattern.strength > 0.1) {
      return {
        period: hourlyPattern.strength > dailyPattern.strength ? TimeInterval.DAY : TimeInterval.WEEK,
        strength: Math.max(hourlyPattern.strength, dailyPattern.strength),
        patterns: [
          {
            period: 'daily',
            amplitude: hourlyPattern.amplitude,
            phase: hourlyPattern.phase,
          },
          {
            period: 'weekly',
            amplitude: dailyPattern.amplitude,
            phase: dailyPattern.phase,
          },
        ],
      };
    }

    return undefined;
  }

  private detectSeasonalPattern(values: number[], period: number): { strength: number; amplitude: number; phase: number } {
    if (values.length < period * 2) {
      return { strength: 0, amplitude: 0, phase: 0 };
    }

    // Calculate autocorrelation at the seasonal lag
    const lag = period;
    let correlation = 0;
    let count = 0;

    for (let i = lag; i < values.length; i++) {
      correlation += values[i] * values[i - lag];
      count++;
    }

    const strength = count > 0 ? Math.abs(correlation / count) : 0;

    // Simplified amplitude and phase calculation
    const amplitude = Math.sqrt(values.reduce((sum, val) => sum + val * val, 0) / values.length);
    const phase = 0; // Simplified

    return { strength: Math.min(strength / 1000, 1), amplitude, phase };
  }

  private detectSeasonality(values: number[]): boolean {
    if (values.length < 12) return false;

    // Simple seasonality check using autocorrelation
    const periods = [7, 24, 168]; // Weekly, daily, hourly patterns

    for (const period of periods) {
      if (values.length >= period * 2) {
        const correlation = this.calculateAutocorrelation(values, period);
        if (Math.abs(correlation) > 0.3) {
          return true;
        }
      }
    }

    return false;
  }

  private calculateAutocorrelation(values: number[], lag: number): number {
    if (values.length <= lag) return 0;

    const mean = values.reduce((sum, val) => sum + val, 0) / values.length;
    let numerator = 0;
    let denominator = 0;

    for (let i = lag; i < values.length; i++) {
      numerator += (values[i] - mean) * (values[i - lag] - mean);
    }

    for (let i = 0; i < values.length; i++) {
      denominator += Math.pow(values[i] - mean, 2);
    }

    return denominator === 0 ? 0 : numerator / denominator;
  }

  private alignDataByTimestamp(
    data1: AnalyticsDataPoint[],
    data2: AnalyticsDataPoint[],
    metric1: string,
    metric2: string
  ): Array<{ timestamp: Date; value1: number; value2: number }> {
    const aligned: Array<{ timestamp: Date; value1: number; value2: number }> = [];

    // Create maps for efficient lookup
    const map1 = new Map(data1.map(d => [d.timestamp.getTime(), d.metrics[metric1] || 0]));
    const map2 = new Map(data2.map(d => [d.timestamp.getTime(), d.metrics[metric2] || 0]));

    // Find common timestamps
    for (const [timestamp, value1] of map1.entries()) {
      const value2 = map2.get(timestamp);
      if (value2 !== undefined) {
        aligned.push({
          timestamp: new Date(timestamp),
          value1,
          value2,
        });
      }
    }

    return aligned.sort((a, b) => a.timestamp.getTime() - b.timestamp.getTime());
  }

  private getIntervalMs(interval: TimeInterval): number {
    const intervals: Record<TimeInterval, number> = {
      [TimeInterval.MINUTE]: 60 * 1000,
      [TimeInterval.FIVE_MINUTES]: 5 * 60 * 1000,
      [TimeInterval.FIFTEEN_MINUTES]: 15 * 60 * 1000,
      [TimeInterval.HOUR]: 60 * 60 * 1000,
      [TimeInterval.DAY]: 24 * 60 * 60 * 1000,
      [TimeInterval.WEEK]: 7 * 24 * 60 * 60 * 1000,
      [TimeInterval.MONTH]: 30 * 24 * 60 * 60 * 1000,
      [TimeInterval.QUARTER]: 90 * 24 * 60 * 60 * 1000,
      [TimeInterval.YEAR]: 365 * 24 * 60 * 60 * 1000,
    };

    return intervals[interval] || intervals[TimeInterval.HOUR];
  }

  private inferCategory(metric: string): AnalyticsCategory {
    const lowerMetric = metric.toLowerCase();

    if (lowerMetric.includes('source') || lowerMetric.includes('connection')) {
      return AnalyticsCategory.DATA_SOURCE;
    }
    if (lowerMetric.includes('storage') || lowerMetric.includes('disk') || lowerMetric.includes('memory')) {
      return AnalyticsCategory.STORAGE;
    }
    if (lowerMetric.includes('quality') || lowerMetric.includes('validation')) {
      return AnalyticsCategory.DATA_QUALITY;
    }
    if (lowerMetric.includes('pipeline') || lowerMetric.includes('job')) {
      return AnalyticsCategory.PIPELINE;
    }
    if (lowerMetric.includes('latency') || lowerMetric.includes('throughput') || lowerMetric.includes('performance')) {
      return AnalyticsCategory.PERFORMANCE;
    }

    return AnalyticsCategory.SYSTEM;
  }

  private inferUnit(metric: string): string {
    const lowerMetric = metric.toLowerCase();

    if (lowerMetric.includes('latency') || lowerMetric.includes('time') || lowerMetric.includes('duration')) {
      return 'ms';
    }
    if (lowerMetric.includes('rate') || lowerMetric.includes('percentage') || lowerMetric.includes('ratio')) {
      return '%';
    }
    if (lowerMetric.includes('count') || lowerMetric.includes('number')) {
      return 'count';
    }
    if (lowerMetric.includes('size') || lowerMetric.includes('bytes')) {
      return 'bytes';
    }
    if (lowerMetric.includes('throughput') || lowerMetric.includes('rps')) {
      return 'ops/sec';
    }

    return 'units';
  }

  // Simulation methods for development (replace with real data in production)
  private simulateAggregateData(query: AnalyticsQuery): AnalyticsResult {
    const dataPoints: AnalyticsDataPoint[] = [];
    const startTime = query.timeRange.start.getTime();
    const endTime = query.timeRange.end.getTime();
    const interval = this.getIntervalMs(query.timeRange.interval || TimeInterval.HOUR);

    for (let time = startTime; time <= endTime; time += interval) {
      const point: AnalyticsDataPoint = {
        timestamp: new Date(time),
        metrics: {},
        dimensions: {},
      };

      query.metrics.forEach(metric => {
        point.metrics[metric] = Math.random() * 100 + 50; // Random value between 50-150
      });

      dataPoints.push(point);
    }

    return {
      query,
      data: dataPoints,
      metadata: {
        totalRecords: dataPoints.length,
        executionTime: Math.random() * 100 + 50,
        dataQuality: 0.95,
        lastUpdated: new Date(),
      },
    };
  }

  private simulateMetricsData(category?: AnalyticsCategory): AnalyticsMetric[] {
    const baseMetrics = [
      { name: 'connection_count', category: AnalyticsCategory.DATA_SOURCE, unit: 'count' },
      { name: 'avg_latency', category: AnalyticsCategory.PERFORMANCE, unit: 'ms' },
      { name: 'error_rate', category: AnalyticsCategory.PERFORMANCE, unit: '%' },
      { name: 'storage_usage', category: AnalyticsCategory.STORAGE, unit: 'GB' },
      { name: 'quality_score', category: AnalyticsCategory.DATA_QUALITY, unit: '%' },
      { name: 'pipeline_success_rate', category: AnalyticsCategory.PIPELINE, unit: '%' },
    ];

    return baseMetrics
      .filter(metric => !category || metric.category === category)
      .map((metric, index) => ({
        id: `metric-${index}`,
        name: metric.name,
        description: `Simulated ${metric.name} metric`,
        category: metric.category,
        value: Math.random() * 100,
        unit: metric.unit,
        timestamp: new Date(),
        tags: ['simulated'],
      }));
  }

  private simulateHistoricalData(metric: string, timeRange: TimeRange): AnalyticsDataPoint[] {
    const dataPoints: AnalyticsDataPoint[] = [];
    const startTime = timeRange.start.getTime();
    const endTime = timeRange.end.getTime();
    const interval = this.getIntervalMs(timeRange.interval || TimeInterval.HOUR);

    let baseValue = 75;
    const trend = (Math.random() - 0.5) * 0.1; // Small trend

    for (let time = startTime; time <= endTime; time += interval) {
      baseValue += trend + (Math.random() - 0.5) * 10;
      baseValue = Math.max(0, baseValue);

      dataPoints.push({
        timestamp: new Date(time),
        metrics: { [metric]: baseValue },
        dimensions: { source: 'simulation' },
      });
    }

    return dataPoints;
  }

  private simulateBaselines(category?: AnalyticsCategory): PerformanceBaseline[] {
    const baselines = [
      { metric: 'avg_latency', category: AnalyticsCategory.PERFORMANCE, baseline: 150, unit: 'ms' },
      { metric: 'error_rate', category: AnalyticsCategory.PERFORMANCE, baseline: 1.5, unit: '%' },
      { metric: 'storage_usage', category: AnalyticsCategory.STORAGE, baseline: 65, unit: '%' },
      { metric: 'quality_score', category: AnalyticsCategory.DATA_QUALITY, baseline: 92, unit: '%' },
    ];

    return baselines
      .filter(baseline => !category || baseline.category === category)
      .map(baseline => ({
        ...baseline,
        confidence: 0.85,
        createdAt: new Date(Date.now() - 7 * 24 * 60 * 60 * 1000),
        validUntil: new Date(Date.now() + 23 * 24 * 60 * 60 * 1000),
        metadata: {
          sampleSize: 1000,
          method: 'moving_average',
          seasonality: false,
        },
      }));
  }
}

// Singleton instance
let globalAnalyticsService: AnalyticsService | null = null;

export const getAnalyticsService = (baseUrl?: string): AnalyticsService => {
  if (!globalAnalyticsService) {
    globalAnalyticsService = new AnalyticsService(baseUrl);
  }
  return globalAnalyticsService;
};
