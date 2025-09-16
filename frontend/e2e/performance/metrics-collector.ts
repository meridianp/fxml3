/**
 * Performance Metrics Collector
 *
 * Continuous performance monitoring and metrics collection system
 */

import fs from 'fs/promises';
import path from 'path';
import { PerformanceMonitor, PerformanceMetrics } from './performance-monitor';

export interface MetricsCollectionConfig {
  enabled: boolean;
  interval: number; // Collection interval in milliseconds
  retentionDays: number;
  thresholds: PerformanceThresholds;
  exportFormats: ('json' | 'csv' | 'prometheus' | 'datadog')[];
  alerting: AlertingConfig;
}

interface PerformanceThresholds {
  loadTime: {
    warning: number;
    critical: number;
  };
  memoryUsage: {
    warning: number; // MB
    critical: number;
  };
  errorRate: {
    warning: number; // Percentage
    critical: number;
  };
  throughput: {
    warning: number; // Requests per second
    critical: number;
  };
}

interface AlertingConfig {
  enabled: boolean;
  webhookUrl?: string;
  slackChannel?: string;
  emailRecipients?: string[];
  thresholdBreachCount: number; // Number of consecutive breaches before alert
}

interface MetricsSnapshot {
  timestamp: string;
  environment: string;
  commit: string;
  branch: string;
  metrics: PerformanceMetrics;
  thresholdBreaches: ThresholdBreach[];
  score: PerformanceScore;
}

interface ThresholdBreach {
  metric: string;
  value: number;
  threshold: number;
  severity: 'warning' | 'critical';
  description: string;
}

interface PerformanceScore {
  overall: number; // 0-100
  categories: {
    loadTime: number;
    memoryEfficiency: number;
    networkPerformance: number;
    interactivity: number;
  };
  grade: 'A' | 'B' | 'C' | 'D' | 'F';
}

interface TrendAnalysis {
  metric: string;
  direction: 'improving' | 'stable' | 'degrading';
  changePercentage: number;
  significance: 'low' | 'medium' | 'high';
  recommendation?: string;
}

export class MetricsCollector {
  private config: MetricsCollectionConfig;
  private snapshots: MetricsSnapshot[] = [];
  private performanceMonitor: PerformanceMonitor;
  private alertCounts: Map<string, number> = new Map();

  constructor(config: Partial<MetricsCollectionConfig> = {}) {
    this.config = {
      enabled: true,
      interval: 60000, // 1 minute
      retentionDays: 30,
      thresholds: {
        loadTime: { warning: 3000, critical: 5000 },
        memoryUsage: { warning: 100, critical: 200 },
        errorRate: { warning: 2, critical: 5 },
        throughput: { warning: 10, critical: 5 }
      },
      exportFormats: ['json', 'csv'],
      alerting: {
        enabled: false,
        thresholdBreachCount: 3
      },
      ...config
    };

    this.performanceMonitor = new PerformanceMonitor();
  }

  /**
   * Start continuous metrics collection
   */
  async startCollection(): Promise<void> {
    if (!this.config.enabled) {
      console.log('📊 Metrics collection is disabled');
      return;
    }

    console.log('🚀 Starting continuous performance metrics collection...');
    console.log(`📈 Collection interval: ${this.config.interval / 1000}s`);
    console.log(`📅 Retention: ${this.config.retentionDays} days`);

    // Load existing metrics
    await this.loadHistoricalMetrics();

    // Set up collection interval
    setInterval(async () => {
      try {
        await this.collectMetrics();
      } catch (error) {
        console.error('❌ Failed to collect metrics:', error);
      }
    }, this.config.interval);

    // Set up cleanup interval (daily)
    setInterval(async () => {
      await this.cleanupOldMetrics();
    }, 24 * 60 * 60 * 1000);

    console.log('✅ Metrics collection started');
  }

  /**
   * Collect performance metrics snapshot
   */
  async collectMetrics(): Promise<MetricsSnapshot> {
    const timestamp = new Date().toISOString();

    // Get environment information
    const environment = process.env.NODE_ENV || 'development';
    const commit = process.env.GITHUB_SHA || 'unknown';
    const branch = process.env.GITHUB_REF?.replace('refs/heads/', '') || 'unknown';

    // For CI/CD integration, metrics would be collected from test runs
    // Here we create a placeholder that would be populated with actual metrics
    const metrics: PerformanceMetrics = {
      pageLoad: {
        loadTime: Math.random() * 5000, // Mock data - replace with actual
        domContentLoaded: Math.random() * 3000,
        networkIdle: Math.random() * 4000,
        firstContentfulPaint: Math.random() * 2000,
        largestContentfulPaint: Math.random() * 3000,
        cumulativeLayoutShift: Math.random() * 0.1
      },
      resources: {
        totalSize: Math.random() * 2 * 1024 * 1024,
        totalRequests: Math.floor(Math.random() * 50) + 10,
        jsSize: Math.random() * 1024 * 1024,
        cssSize: Math.random() * 200 * 1024,
        imageSize: Math.random() * 500 * 1024,
        slowestResource: {
          url: '/assets/app.js',
          duration: Math.random() * 1000,
          size: Math.random() * 500 * 1024
        }
      },
      memory: {
        initial: 20 * 1024 * 1024,
        peak: 50 * 1024 * 1024,
        final: 30 * 1024 * 1024,
        increase: 10 * 1024 * 1024,
        leakSuspected: false
      },
      runtime: {
        interactions: [],
        frameRate: 60,
        scriptExecutionTime: Math.random() * 100,
        layoutThrashing: Math.random() * 10
      },
      network: {
        totalTransferSize: Math.random() * 1024 * 1024,
        totalRequests: Math.floor(Math.random() * 30) + 5,
        failedRequests: Math.floor(Math.random() * 2),
        averageResponseTime: Math.random() * 500,
        slowestEndpoint: {
          url: '/api/data',
          responseTime: Math.random() * 1000
        }
      }
    };

    // Check for threshold breaches
    const thresholdBreaches = this.checkThresholds(metrics);

    // Calculate performance score
    const score = this.calculatePerformanceScore(metrics);

    const snapshot: MetricsSnapshot = {
      timestamp,
      environment,
      commit,
      branch,
      metrics,
      thresholdBreaches,
      score
    };

    this.snapshots.push(snapshot);

    // Handle alerting
    if (thresholdBreaches.length > 0) {
      await this.handleAlerts(snapshot);
    }

    // Export metrics
    await this.exportMetrics(snapshot);

    console.log(`📊 Metrics collected - Score: ${score.overall}/${score.grade}, Breaches: ${thresholdBreaches.length}`);

    return snapshot;
  }

  /**
   * Analyze performance trends
   */
  analyzeTrends(days: number = 7): TrendAnalysis[] {
    const cutoffDate = new Date();
    cutoffDate.setDate(cutoffDate.getDate() - days);

    const recentSnapshots = this.snapshots.filter(s =>
      new Date(s.timestamp) > cutoffDate
    );

    if (recentSnapshots.length < 2) {
      return [];
    }

    const trends: TrendAnalysis[] = [];

    // Analyze load time trend
    const loadTimes = recentSnapshots.map(s => s.metrics.pageLoad.loadTime);
    trends.push(this.calculateTrend('Load Time', loadTimes, 'ms'));

    // Analyze memory usage trend
    const memoryUsage = recentSnapshots.map(s => s.metrics.memory.increase);
    trends.push(this.calculateTrend('Memory Usage', memoryUsage, 'bytes'));

    // Analyze error rate trend
    const errorRates = recentSnapshots.map(s =>
      s.metrics.network.totalRequests > 0
        ? (s.metrics.network.failedRequests / s.metrics.network.totalRequests) * 100
        : 0
    );
    trends.push(this.calculateTrend('Error Rate', errorRates, '%'));

    // Analyze performance score trend
    const scores = recentSnapshots.map(s => s.score.overall);
    trends.push(this.calculateTrend('Performance Score', scores, 'points'));

    return trends;
  }

  /**
   * Generate performance report
   */
  async generateReport(outputPath: string): Promise<void> {
    const trends = this.analyzeTrends();
    const recentSnapshot = this.snapshots[this.snapshots.length - 1];

    const report = {
      summary: {
        currentScore: recentSnapshot?.score || null,
        totalSnapshots: this.snapshots.length,
        collectionPeriod: this.getCollectionPeriod(),
        environment: recentSnapshot?.environment || 'unknown'
      },
      trends,
      thresholds: this.config.thresholds,
      recentBreaches: this.getRecentBreaches(7),
      recommendations: this.generateRecommendations(trends),
      rawData: this.snapshots.slice(-100), // Last 100 snapshots
      timestamp: new Date().toISOString()
    };

    // Write JSON report
    await fs.writeFile(
      path.join(outputPath, 'metrics-report.json'),
      JSON.stringify(report, null, 2)
    );

    // Generate dashboard HTML
    const dashboardHtml = this.generateDashboard(report);
    await fs.writeFile(
      path.join(outputPath, 'metrics-dashboard.html'),
      dashboardHtml
    );

    console.log(`📊 Metrics report generated at: ${outputPath}`);
  }

  /**
   * Export metrics in various formats
   */
  async exportMetrics(snapshot: MetricsSnapshot): Promise<void> {
    const exportDir = 'e2e-results/metrics';
    await fs.mkdir(exportDir, { recursive: true });

    for (const format of this.config.exportFormats) {
      switch (format) {
        case 'json':
          await this.exportJSON(snapshot, exportDir);
          break;
        case 'csv':
          await this.exportCSV(snapshot, exportDir);
          break;
        case 'prometheus':
          await this.exportPrometheus(snapshot, exportDir);
          break;
        case 'datadog':
          await this.exportDatadog(snapshot);
          break;
      }
    }
  }

  /**
   * Check performance against baseline
   */
  compareToBaseline(baselinePath: string): Promise<{
    improvements: string[];
    regressions: string[];
    neutral: string[];
  }> {
    // Implementation for baseline comparison
    return Promise.resolve({
      improvements: [],
      regressions: [],
      neutral: []
    });
  }

  private checkThresholds(metrics: PerformanceMetrics): ThresholdBreach[] {
    const breaches: ThresholdBreach[] = [];

    // Check load time
    if (metrics.pageLoad.loadTime > this.config.thresholds.loadTime.critical) {
      breaches.push({
        metric: 'loadTime',
        value: metrics.pageLoad.loadTime,
        threshold: this.config.thresholds.loadTime.critical,
        severity: 'critical',
        description: `Page load time ${metrics.pageLoad.loadTime}ms exceeds critical threshold`
      });
    } else if (metrics.pageLoad.loadTime > this.config.thresholds.loadTime.warning) {
      breaches.push({
        metric: 'loadTime',
        value: metrics.pageLoad.loadTime,
        threshold: this.config.thresholds.loadTime.warning,
        severity: 'warning',
        description: `Page load time ${metrics.pageLoad.loadTime}ms exceeds warning threshold`
      });
    }

    // Check memory usage
    const memoryMB = metrics.memory.increase / (1024 * 1024);
    if (memoryMB > this.config.thresholds.memoryUsage.critical) {
      breaches.push({
        metric: 'memoryUsage',
        value: memoryMB,
        threshold: this.config.thresholds.memoryUsage.critical,
        severity: 'critical',
        description: `Memory usage ${memoryMB.toFixed(2)}MB exceeds critical threshold`
      });
    } else if (memoryMB > this.config.thresholds.memoryUsage.warning) {
      breaches.push({
        metric: 'memoryUsage',
        value: memoryMB,
        threshold: this.config.thresholds.memoryUsage.warning,
        severity: 'warning',
        description: `Memory usage ${memoryMB.toFixed(2)}MB exceeds warning threshold`
      });
    }

    // Check error rate
    const errorRate = metrics.network.totalRequests > 0
      ? (metrics.network.failedRequests / metrics.network.totalRequests) * 100
      : 0;

    if (errorRate > this.config.thresholds.errorRate.critical) {
      breaches.push({
        metric: 'errorRate',
        value: errorRate,
        threshold: this.config.thresholds.errorRate.critical,
        severity: 'critical',
        description: `Error rate ${errorRate.toFixed(2)}% exceeds critical threshold`
      });
    } else if (errorRate > this.config.thresholds.errorRate.warning) {
      breaches.push({
        metric: 'errorRate',
        value: errorRate,
        threshold: this.config.thresholds.errorRate.warning,
        severity: 'warning',
        description: `Error rate ${errorRate.toFixed(2)}% exceeds warning threshold`
      });
    }

    return breaches;
  }

  private calculatePerformanceScore(metrics: PerformanceMetrics): PerformanceScore {
    // Load time score (0-100, 100 = under 1s, 0 = over 5s)
    const loadTimeScore = Math.max(0, Math.min(100,
      100 - ((metrics.pageLoad.loadTime - 1000) / 4000) * 100
    ));

    // Memory efficiency score (0-100, 100 = under 10MB, 0 = over 100MB)
    const memoryMB = metrics.memory.increase / (1024 * 1024);
    const memoryScore = Math.max(0, Math.min(100,
      100 - ((memoryMB - 10) / 90) * 100
    ));

    // Network performance score (0-100, based on requests and response times)
    const avgResponseTime = metrics.network.averageResponseTime;
    const networkScore = Math.max(0, Math.min(100,
      100 - (avgResponseTime / 1000) * 100
    ));

    // Interactivity score (based on frame rate and interaction times)
    const interactivityScore = Math.min(100, (metrics.runtime.frameRate / 60) * 100);

    const categories = {
      loadTime: Math.round(loadTimeScore),
      memoryEfficiency: Math.round(memoryScore),
      networkPerformance: Math.round(networkScore),
      interactivity: Math.round(interactivityScore)
    };

    const overall = Math.round(
      (categories.loadTime + categories.memoryEfficiency +
       categories.networkPerformance + categories.interactivity) / 4
    );

    const grade = overall >= 90 ? 'A' :
                  overall >= 80 ? 'B' :
                  overall >= 70 ? 'C' :
                  overall >= 60 ? 'D' : 'F';

    return { overall, categories, grade };
  }

  private calculateTrend(name: string, values: number[], unit: string): TrendAnalysis {
    if (values.length < 2) {
      return {
        metric: name,
        direction: 'stable',
        changePercentage: 0,
        significance: 'low'
      };
    }

    const first = values[0];
    const last = values[values.length - 1];
    const changePercentage = ((last - first) / first) * 100;

    let direction: 'improving' | 'stable' | 'degrading';
    if (Math.abs(changePercentage) < 5) {
      direction = 'stable';
    } else if (name === 'Performance Score' ? changePercentage > 0 : changePercentage < 0) {
      direction = 'improving';
    } else {
      direction = 'degrading';
    }

    const significance = Math.abs(changePercentage) > 20 ? 'high' :
                        Math.abs(changePercentage) > 10 ? 'medium' : 'low';

    return {
      metric: name,
      direction,
      changePercentage,
      significance,
      recommendation: this.getTrendRecommendation(name, direction, significance)
    };
  }

  private getTrendRecommendation(metric: string, direction: string, significance: string): string | undefined {
    if (direction === 'degrading' && significance === 'high') {
      switch (metric) {
        case 'Load Time':
          return 'Consider optimizing bundle size, implementing code splitting, or improving server response times';
        case 'Memory Usage':
          return 'Investigate potential memory leaks and optimize component lifecycle management';
        case 'Error Rate':
          return 'Review recent changes and improve error handling and monitoring';
        case 'Performance Score':
          return 'Overall performance is declining - prioritize optimization efforts';
      }
    }
    return undefined;
  }

  private async handleAlerts(snapshot: MetricsSnapshot): Promise<void> {
    if (!this.config.alerting.enabled) return;

    for (const breach of snapshot.thresholdBreaches) {
      const alertKey = `${breach.metric}_${breach.severity}`;
      const currentCount = this.alertCounts.get(alertKey) || 0;
      this.alertCounts.set(alertKey, currentCount + 1);

      if (currentCount + 1 >= this.config.alerting.thresholdBreachCount) {
        await this.sendAlert(breach, snapshot);
        this.alertCounts.set(alertKey, 0); // Reset counter after alert
      }
    }
  }

  private async sendAlert(breach: ThresholdBreach, snapshot: MetricsSnapshot): Promise<void> {
    const alertMessage = {
      title: `Performance Alert: ${breach.severity.toUpperCase()}`,
      description: breach.description,
      environment: snapshot.environment,
      commit: snapshot.commit,
      timestamp: snapshot.timestamp,
      score: snapshot.score.overall
    };

    console.log(`🚨 ALERT: ${JSON.stringify(alertMessage)}`);

    // In a real implementation, you would send to Slack, email, webhooks, etc.
    if (this.config.alerting.webhookUrl) {
      // await fetch(this.config.alerting.webhookUrl, { ... });
    }
  }

  private async loadHistoricalMetrics(): Promise<void> {
    try {
      const metricsFile = 'e2e-results/metrics/historical-metrics.json';
      const data = await fs.readFile(metricsFile, 'utf-8');
      this.snapshots = JSON.parse(data);
      console.log(`📂 Loaded ${this.snapshots.length} historical metrics`);
    } catch {
      console.log('📂 No historical metrics found, starting fresh');
    }
  }

  private async cleanupOldMetrics(): Promise<void> {
    const cutoffDate = new Date();
    cutoffDate.setDate(cutoffDate.getDate() - this.config.retentionDays);

    const initialCount = this.snapshots.length;
    this.snapshots = this.snapshots.filter(s => new Date(s.timestamp) > cutoffDate);

    const removedCount = initialCount - this.snapshots.length;
    if (removedCount > 0) {
      console.log(`🧹 Cleaned up ${removedCount} old metrics`);
      await this.saveHistoricalMetrics();
    }
  }

  private async saveHistoricalMetrics(): Promise<void> {
    const metricsDir = 'e2e-results/metrics';
    await fs.mkdir(metricsDir, { recursive: true });

    await fs.writeFile(
      path.join(metricsDir, 'historical-metrics.json'),
      JSON.stringify(this.snapshots, null, 2)
    );
  }

  private getCollectionPeriod(): { start: string; end: string } {
    const snapshots = this.snapshots;
    return {
      start: snapshots.length > 0 ? snapshots[0].timestamp : new Date().toISOString(),
      end: snapshots.length > 0 ? snapshots[snapshots.length - 1].timestamp : new Date().toISOString()
    };
  }

  private getRecentBreaches(days: number): ThresholdBreach[] {
    const cutoffDate = new Date();
    cutoffDate.setDate(cutoffDate.getDate() - days);

    return this.snapshots
      .filter(s => new Date(s.timestamp) > cutoffDate)
      .flatMap(s => s.thresholdBreaches);
  }

  private generateRecommendations(trends: TrendAnalysis[]): string[] {
    const recommendations: string[] = [];

    const degradingTrends = trends.filter(t => t.direction === 'degrading' && t.significance !== 'low');

    if (degradingTrends.length > 0) {
      recommendations.push('Performance degradation detected in multiple areas - consider a comprehensive performance review');
    }

    trends.forEach(trend => {
      if (trend.recommendation) {
        recommendations.push(trend.recommendation);
      }
    });

    if (recommendations.length === 0) {
      recommendations.push('Performance is stable - continue monitoring');
    }

    return recommendations;
  }

  private generateDashboard(report: any): string {
    return `
<!DOCTYPE html>
<html>
<head>
    <title>FXML4 Performance Metrics Dashboard</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 0; padding: 20px; background: #f5f5f5; }
        .dashboard { display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 20px; }
        .card { background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
        .score { font-size: 3em; font-weight: bold; text-align: center; }
        .grade-A { color: #4caf50; }
        .grade-B { color: #8bc34a; }
        .grade-C { color: #ff9800; }
        .grade-D { color: #f44336; }
        .grade-F { color: #d32f2f; }
        .trend-improving { color: #4caf50; }
        .trend-degrading { color: #f44336; }
        .trend-stable { color: #666; }
        table { width: 100%; border-collapse: collapse; }
        th, td { padding: 8px; text-align: left; border-bottom: 1px solid #ddd; }
        .metric-value { font-weight: bold; }
    </style>
</head>
<body>
    <h1>FXML4 Performance Metrics Dashboard</h1>

    <div class="dashboard">
        <div class="card">
            <h3>Current Performance Score</h3>
            <div class="score grade-${report.summary.currentScore?.grade || 'F'}">
                ${report.summary.currentScore?.overall || 0}
            </div>
            <div style="text-align: center; margin-top: 10px;">
                Grade: ${report.summary.currentScore?.grade || 'F'}
            </div>
        </div>

        <div class="card">
            <h3>Collection Summary</h3>
            <p><strong>Total Snapshots:</strong> ${report.summary.totalSnapshots}</p>
            <p><strong>Environment:</strong> ${report.summary.environment}</p>
            <p><strong>Period:</strong> ${report.summary.collectionPeriod.start.split('T')[0]} to ${report.summary.collectionPeriod.end.split('T')[0]}</p>
        </div>

        <div class="card">
            <h3>Performance Trends</h3>
            <table>
                <tr><th>Metric</th><th>Direction</th><th>Change</th></tr>
                ${report.trends.map((trend: TrendAnalysis) => `
                    <tr>
                        <td>${trend.metric}</td>
                        <td class="trend-${trend.direction}">${trend.direction}</td>
                        <td class="metric-value">${trend.changePercentage.toFixed(1)}%</td>
                    </tr>
                `).join('')}
            </table>
        </div>

        <div class="card">
            <h3>Recent Threshold Breaches</h3>
            ${report.recentBreaches.length > 0 ? `
                <ul>
                    ${report.recentBreaches.slice(-5).map((breach: ThresholdBreach) => `
                        <li class="trend-${breach.severity === 'critical' ? 'degrading' : 'stable'}">
                            ${breach.description}
                        </li>
                    `).join('')}
                </ul>
            ` : '<p>No recent breaches</p>'}
        </div>

        <div class="card">
            <h3>Recommendations</h3>
            <ul>
                ${report.recommendations.map((rec: string) => `<li>${rec}</li>`).join('')}
            </ul>
        </div>
    </div>

    <p style="text-align: center; margin-top: 40px; color: #666;">
        Generated on ${report.timestamp}
    </p>
</body>
</html>`;
  }

  private async exportJSON(snapshot: MetricsSnapshot, dir: string): Promise<void> {
    const filename = `metrics-${snapshot.timestamp.replace(/[:.]/g, '-')}.json`;
    await fs.writeFile(path.join(dir, filename), JSON.stringify(snapshot, null, 2));
  }

  private async exportCSV(snapshot: MetricsSnapshot, dir: string): Promise<void> {
    const csvRow = [
      snapshot.timestamp,
      snapshot.environment,
      snapshot.commit,
      snapshot.metrics.pageLoad.loadTime,
      snapshot.metrics.memory.increase,
      snapshot.metrics.network.totalRequests,
      snapshot.metrics.network.failedRequests,
      snapshot.score.overall,
      snapshot.thresholdBreaches.length
    ].join(',');

    const filename = 'metrics.csv';
    const filepath = path.join(dir, filename);

    // Check if file exists to add header
    try {
      await fs.access(filepath);
    } catch {
      const header = 'Timestamp,Environment,Commit,LoadTime,MemoryIncrease,TotalRequests,FailedRequests,Score,Breaches\n';
      await fs.writeFile(filepath, header);
    }

    await fs.appendFile(filepath, csvRow + '\n');
  }

  private async exportPrometheus(snapshot: MetricsSnapshot, dir: string): Promise<void> {
    const metrics = [
      `fxml4_load_time_ms ${snapshot.metrics.pageLoad.loadTime}`,
      `fxml4_memory_usage_bytes ${snapshot.metrics.memory.increase}`,
      `fxml4_network_requests_total ${snapshot.metrics.network.totalRequests}`,
      `fxml4_network_requests_failed ${snapshot.metrics.network.failedRequests}`,
      `fxml4_performance_score ${snapshot.score.overall}`,
      `fxml4_threshold_breaches ${snapshot.thresholdBreaches.length}`
    ].join('\n');

    await fs.writeFile(path.join(dir, 'metrics.prom'), metrics);
  }

  private async exportDatadog(snapshot: MetricsSnapshot): Promise<void> {
    // In a real implementation, this would send metrics to Datadog API
    const datadogMetrics = {
      series: [
        {
          metric: 'fxml4.performance.load_time',
          points: [[Math.floor(Date.now() / 1000), snapshot.metrics.pageLoad.loadTime]],
          tags: [`environment:${snapshot.environment}`, `commit:${snapshot.commit}`]
        },
        {
          metric: 'fxml4.performance.score',
          points: [[Math.floor(Date.now() / 1000), snapshot.score.overall]],
          tags: [`environment:${snapshot.environment}`, `commit:${snapshot.commit}`]
        }
      ]
    };

    console.log('📊 Datadog metrics:', JSON.stringify(datadogMetrics, null, 2));
  }
}

export { MetricsCollector, MetricsCollectionConfig, MetricsSnapshot, TrendAnalysis };
