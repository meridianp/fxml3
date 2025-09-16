/**
 * Performance Monitoring Framework
 *
 * Comprehensive performance testing, metrics collection, and monitoring system
 */

import { Page, Browser } from '@playwright/test';
import fs from 'fs/promises';
import path from 'path';

export interface PerformanceMetrics {
  pageLoad: {
    loadTime: number;
    domContentLoaded: number;
    networkIdle: number;
    firstContentfulPaint?: number;
    largestContentfulPaint?: number;
    cumulativeLayoutShift?: number;
    firstInputDelay?: number;
  };
  resources: {
    totalSize: number;
    totalRequests: number;
    jsSize: number;
    cssSize: number;
    imageSize: number;
    slowestResource: {
      url: string;
      duration: number;
      size: number;
    };
  };
  memory: {
    initial: number;
    peak: number;
    final: number;
    increase: number;
    leakSuspected: boolean;
  };
  runtime: {
    interactions: InteractionMetric[];
    frameRate: number;
    scriptExecutionTime: number;
    layoutThrashing: number;
  };
  network: {
    totalTransferSize: number;
    totalRequests: number;
    failedRequests: number;
    averageResponseTime: number;
    slowestEndpoint: {
      url: string;
      responseTime: number;
    };
  };
}

interface InteractionMetric {
  action: string;
  startTime: number;
  duration: number;
  element: string;
  success: boolean;
}

interface PerformanceBenchmark {
  scenario: string;
  metrics: PerformanceMetrics;
  timestamp: string;
  userAgent: string;
  viewport: { width: number; height: number };
  networkCondition?: string;
}

export class PerformanceMonitor {
  private metrics: PerformanceMetrics;
  private benchmarks: PerformanceBenchmark[] = [];
  private isMonitoring: boolean = false;
  private startTime: number = 0;

  constructor() {
    this.metrics = this.getEmptyMetrics();
  }

  /**
   * Start performance monitoring for a page
   */
  async startMonitoring(page: Page, scenario: string): Promise<void> {
    this.isMonitoring = true;
    this.startTime = Date.now();
    this.metrics = this.getEmptyMetrics();

    // Set up performance monitoring
    await this.setupPerformanceObservers(page);

    // Monitor network requests
    await this.setupNetworkMonitoring(page);

    // Monitor memory usage
    await this.setupMemoryMonitoring(page);

    // Monitor runtime performance
    await this.setupRuntimeMonitoring(page);

    console.log(`🔍 Performance monitoring started for: ${scenario}`);
  }

  /**
   * Stop monitoring and collect final metrics
   */
  async stopMonitoring(page: Page, scenario: string): Promise<PerformanceMetrics> {
    if (!this.isMonitoring) {
      throw new Error('Performance monitoring is not active');
    }

    // Collect final metrics
    await this.collectFinalMetrics(page);

    // Create benchmark record
    const benchmark: PerformanceBenchmark = {
      scenario,
      metrics: { ...this.metrics },
      timestamp: new Date().toISOString(),
      userAgent: await page.evaluate(() => navigator.userAgent),
      viewport: page.viewportSize() || { width: 1280, height: 720 },
    };

    this.benchmarks.push(benchmark);
    this.isMonitoring = false;

    console.log(`✅ Performance monitoring completed for: ${scenario}`);
    console.log(`📊 Load time: ${this.metrics.pageLoad.loadTime}ms`);
    console.log(`💾 Memory increase: ${(this.metrics.memory.increase / 1024 / 1024).toFixed(2)}MB`);
    console.log(`🌐 Network requests: ${this.metrics.network.totalRequests}`);

    return this.metrics;
  }

  /**
   * Measure interaction performance
   */
  async measureInteraction(
    page: Page,
    action: string,
    element: string,
    interaction: () => Promise<void>
  ): Promise<InteractionMetric> {
    const startTime = performance.now();
    let success = false;

    try {
      await interaction();
      success = true;
    } catch (error) {
      console.error(`Interaction failed: ${action}`, error);
    }

    const duration = performance.now() - startTime;

    const metric: InteractionMetric = {
      action,
      startTime,
      duration,
      element,
      success
    };

    this.metrics.runtime.interactions.push(metric);

    console.log(`⚡ ${action} took ${duration.toFixed(2)}ms`);

    return metric;
  }

  /**
   * Simulate network conditions
   */
  async setNetworkCondition(page: Page, condition: 'slow3g' | 'fast3g' | 'offline'): Promise<void> {
    const conditions = {
      slow3g: { downloadThroughput: 500 * 1024, uploadThroughput: 500 * 1024, latency: 400 },
      fast3g: { downloadThroughput: 1.5 * 1024 * 1024, uploadThroughput: 750 * 1024, latency: 150 },
      offline: { downloadThroughput: 0, uploadThroughput: 0, latency: 0 }
    };

    const context = page.context();
    await context.route('**/*', async (route) => {
      const networkCondition = conditions[condition];

      // Simulate network delay
      await new Promise(resolve => setTimeout(resolve, networkCondition.latency));

      if (condition === 'offline') {
        await route.abort();
      } else {
        await route.continue();
      }
    });

    console.log(`🌐 Network condition set to: ${condition}`);
  }

  /**
   * Run comprehensive performance test
   */
  async runPerformanceTest(
    page: Page,
    url: string,
    scenario: string,
    options: {
      networkCondition?: 'slow3g' | 'fast3g';
      viewport?: { width: number; height: number };
      interactions?: Array<{ name: string; action: () => Promise<void> }>;
    } = {}
  ): Promise<PerformanceMetrics> {

    // Set viewport if specified
    if (options.viewport) {
      await page.setViewportSize(options.viewport);
    }

    // Set network condition if specified
    if (options.networkCondition) {
      await this.setNetworkCondition(page, options.networkCondition);
    }

    // Start monitoring
    await this.startMonitoring(page, scenario);

    // Navigate to page
    const navigationStart = Date.now();
    await page.goto(url);
    await page.waitForLoadState('networkidle');
    this.metrics.pageLoad.loadTime = Date.now() - navigationStart;

    // Perform interactions if specified
    if (options.interactions) {
      for (const interaction of options.interactions) {
        await this.measureInteraction(
          page,
          interaction.name,
          'interactive-element',
          interaction.action
        );

        // Wait between interactions
        await page.waitForTimeout(1000);
      }
    }

    // Stop monitoring and return metrics
    return await this.stopMonitoring(page, scenario);
  }

  /**
   * Generate performance report
   */
  async generateReport(outputPath: string): Promise<void> {
    const report = {
      summary: this.generateSummary(),
      benchmarks: this.benchmarks,
      recommendations: this.generateRecommendations(),
      timestamp: new Date().toISOString()
    };

    // Write JSON report
    await fs.writeFile(
      path.join(outputPath, 'performance-report.json'),
      JSON.stringify(report, null, 2)
    );

    // Write HTML report
    const htmlReport = this.generateHTMLReport(report);
    await fs.writeFile(
      path.join(outputPath, 'performance-report.html'),
      htmlReport
    );

    // Write CSV for trending
    const csvReport = this.generateCSVReport();
    await fs.writeFile(
      path.join(outputPath, 'performance-metrics.csv'),
      csvReport
    );

    console.log(`📄 Performance report generated at: ${outputPath}`);
  }

  /**
   * Compare performance against baseline
   */
  compareAgainstBaseline(baselinePath: string): PerformanceComparison {
    // Implementation for comparing current metrics against baseline
    // This would be useful for regression detection
    return {
      improved: [],
      degraded: [],
      unchanged: []
    };
  }

  private getEmptyMetrics(): PerformanceMetrics {
    return {
      pageLoad: {
        loadTime: 0,
        domContentLoaded: 0,
        networkIdle: 0
      },
      resources: {
        totalSize: 0,
        totalRequests: 0,
        jsSize: 0,
        cssSize: 0,
        imageSize: 0,
        slowestResource: { url: '', duration: 0, size: 0 }
      },
      memory: {
        initial: 0,
        peak: 0,
        final: 0,
        increase: 0,
        leakSuspected: false
      },
      runtime: {
        interactions: [],
        frameRate: 60,
        scriptExecutionTime: 0,
        layoutThrashing: 0
      },
      network: {
        totalTransferSize: 0,
        totalRequests: 0,
        failedRequests: 0,
        averageResponseTime: 0,
        slowestEndpoint: { url: '', responseTime: 0 }
      }
    };
  }

  private async setupPerformanceObservers(page: Page): Promise<void> {
    await page.addInitScript(() => {
      // Core Web Vitals monitoring
      (window as any).performanceMetrics = {
        fcp: null,
        lcp: null,
        cls: null,
        fid: null
      };

      // First Contentful Paint
      new PerformanceObserver((list) => {
        const entries = list.getEntries();
        const fcpEntry = entries.find(entry => entry.name === 'first-contentful-paint');
        if (fcpEntry) {
          (window as any).performanceMetrics.fcp = fcpEntry.startTime;
        }
      }).observe({ entryTypes: ['paint'] });

      // Largest Contentful Paint
      new PerformanceObserver((list) => {
        const entries = list.getEntries();
        const lastEntry = entries[entries.length - 1];
        (window as any).performanceMetrics.lcp = lastEntry.startTime;
      }).observe({ entryTypes: ['largest-contentful-paint'] });

      // Cumulative Layout Shift
      new PerformanceObserver((list) => {
        let clsValue = 0;
        for (const entry of list.getEntries()) {
          if (!(entry as any).hadRecentInput) {
            clsValue += (entry as any).value;
          }
        }
        (window as any).performanceMetrics.cls = clsValue;
      }).observe({ entryTypes: ['layout-shift'] });
    });
  }

  private async setupNetworkMonitoring(page: Page): Promise<void> {
    const requests: any[] = [];

    page.on('request', request => {
      requests.push({
        url: request.url(),
        method: request.method(),
        startTime: Date.now()
      });
    });

    page.on('response', response => {
      const request = requests.find(req => req.url === response.url());
      if (request) {
        request.endTime = Date.now();
        request.status = response.status();
        request.size = parseInt(response.headers()['content-length'] || '0', 10);
      }
    });

    // Store requests for analysis
    (this.metrics as any)._requests = requests;
  }

  private async setupMemoryMonitoring(page: Page): Promise<void> {
    // Get initial memory
    this.metrics.memory.initial = await page.evaluate(() => {
      return (performance as any).memory ? (performance as any).memory.usedJSHeapSize : 0;
    });
  }

  private async setupRuntimeMonitoring(page: Page): Promise<void> {
    // Monitor frame rate and script execution
    await page.addInitScript(() => {
      let frameCount = 0;
      let lastTime = performance.now();

      function measureFrameRate() {
        frameCount++;
        const currentTime = performance.now();

        if (currentTime - lastTime >= 1000) {
          (window as any).frameRate = frameCount;
          frameCount = 0;
          lastTime = currentTime;
        }

        requestAnimationFrame(measureFrameRate);
      }

      requestAnimationFrame(measureFrameRate);
    });
  }

  private async collectFinalMetrics(page: Page): Promise<void> {
    // Collect Core Web Vitals
    const vitals = await page.evaluate(() => (window as any).performanceMetrics);
    if (vitals) {
      this.metrics.pageLoad.firstContentfulPaint = vitals.fcp;
      this.metrics.pageLoad.largestContentfulPaint = vitals.lcp;
      this.metrics.pageLoad.cumulativeLayoutShift = vitals.cls;
      this.metrics.pageLoad.firstInputDelay = vitals.fid;
    }

    // Collect final memory
    this.metrics.memory.final = await page.evaluate(() => {
      return (performance as any).memory ? (performance as any).memory.usedJSHeapSize : 0;
    });

    this.metrics.memory.increase = this.metrics.memory.final - this.metrics.memory.initial;
    this.metrics.memory.leakSuspected = this.metrics.memory.increase > 50 * 1024 * 1024; // 50MB

    // Collect frame rate
    this.metrics.runtime.frameRate = await page.evaluate(() => (window as any).frameRate || 60);

    // Analyze network requests
    this.analyzeNetworkRequests();
  }

  private analyzeNetworkRequests(): void {
    const requests = (this.metrics as any)._requests || [];

    this.metrics.network.totalRequests = requests.length;
    this.metrics.network.failedRequests = requests.filter((req: any) => req.status >= 400).length;

    const responseTimes = requests
      .filter((req: any) => req.endTime)
      .map((req: any) => req.endTime - req.startTime);

    if (responseTimes.length > 0) {
      this.metrics.network.averageResponseTime =
        responseTimes.reduce((sum, time) => sum + time, 0) / responseTimes.length;

      const slowestIndex = responseTimes.indexOf(Math.max(...responseTimes));
      this.metrics.network.slowestEndpoint = {
        url: requests[slowestIndex].url,
        responseTime: responseTimes[slowestIndex]
      };
    }

    // Resource analysis
    const jsRequests = requests.filter((req: any) => req.url.endsWith('.js'));
    const cssRequests = requests.filter((req: any) => req.url.endsWith('.css'));
    const imageRequests = requests.filter((req: any) =>
      /\.(png|jpg|jpeg|gif|svg|webp)$/i.test(req.url)
    );

    this.metrics.resources.jsSize = jsRequests.reduce((sum: number, req: any) => sum + (req.size || 0), 0);
    this.metrics.resources.cssSize = cssRequests.reduce((sum: number, req: any) => sum + (req.size || 0), 0);
    this.metrics.resources.imageSize = imageRequests.reduce((sum: number, req: any) => sum + (req.size || 0), 0);
    this.metrics.resources.totalSize = this.metrics.resources.jsSize + this.metrics.resources.cssSize + this.metrics.resources.imageSize;
    this.metrics.resources.totalRequests = requests.length;
  }

  private generateSummary(): any {
    if (this.benchmarks.length === 0) return {};

    const avgLoadTime = this.benchmarks.reduce((sum, b) => sum + b.metrics.pageLoad.loadTime, 0) / this.benchmarks.length;
    const avgMemoryIncrease = this.benchmarks.reduce((sum, b) => sum + b.metrics.memory.increase, 0) / this.benchmarks.length;

    return {
      totalBenchmarks: this.benchmarks.length,
      averageLoadTime: avgLoadTime,
      averageMemoryIncrease: avgMemoryIncrease,
      memoryLeaksDetected: this.benchmarks.filter(b => b.metrics.memory.leakSuspected).length
    };
  }

  private generateRecommendations(): string[] {
    const recommendations: string[] = [];

    if (this.benchmarks.length === 0) return recommendations;

    const avgLoadTime = this.benchmarks.reduce((sum, b) => sum + b.metrics.pageLoad.loadTime, 0) / this.benchmarks.length;
    const avgMemoryIncrease = this.benchmarks.reduce((sum, b) => sum + b.metrics.memory.increase, 0) / this.benchmarks.length;

    if (avgLoadTime > 3000) {
      recommendations.push('Consider optimizing page load time - currently averaging over 3 seconds');
    }

    if (avgMemoryIncrease > 20 * 1024 * 1024) {
      recommendations.push('High memory usage detected - investigate potential memory leaks');
    }

    if (this.benchmarks.some(b => b.metrics.runtime.frameRate < 30)) {
      recommendations.push('Low frame rate detected - optimize animations and heavy computations');
    }

    return recommendations;
  }

  private generateHTMLReport(report: any): string {
    return `
<!DOCTYPE html>
<html>
<head>
    <title>FXML4 Performance Report</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; }
        .metric { margin: 10px 0; padding: 10px; border-left: 4px solid #007acc; }
        .warning { border-left-color: #ff9800; }
        .error { border-left-color: #f44336; }
        .good { border-left-color: #4caf50; }
        table { width: 100%; border-collapse: collapse; }
        th, td { padding: 8px; text-align: left; border-bottom: 1px solid #ddd; }
    </style>
</head>
<body>
    <h1>FXML4 Performance Report</h1>
    <div class="metric">
        <h3>Summary</h3>
        <p>Total Benchmarks: ${report.summary.totalBenchmarks}</p>
        <p>Average Load Time: ${report.summary.averageLoadTime?.toFixed(2)}ms</p>
        <p>Memory Leaks Detected: ${report.summary.memoryLeaksDetected}</p>
    </div>

    <div class="metric">
        <h3>Recommendations</h3>
        <ul>
            ${report.recommendations.map((rec: string) => `<li>${rec}</li>`).join('')}
        </ul>
    </div>

    <h3>Detailed Benchmarks</h3>
    <table>
        <tr>
            <th>Scenario</th>
            <th>Load Time (ms)</th>
            <th>Memory Increase (MB)</th>
            <th>Requests</th>
            <th>Failed Requests</th>
        </tr>
        ${report.benchmarks.map((benchmark: PerformanceBenchmark) => `
            <tr>
                <td>${benchmark.scenario}</td>
                <td>${benchmark.metrics.pageLoad.loadTime}</td>
                <td>${(benchmark.metrics.memory.increase / 1024 / 1024).toFixed(2)}</td>
                <td>${benchmark.metrics.network.totalRequests}</td>
                <td>${benchmark.metrics.network.failedRequests}</td>
            </tr>
        `).join('')}
    </table>
</body>
</html>`;
  }

  private generateCSVReport(): string {
    const headers = 'Scenario,LoadTime,MemoryIncrease,TotalRequests,FailedRequests,Timestamp\n';
    const rows = this.benchmarks.map(b =>
      `${b.scenario},${b.metrics.pageLoad.loadTime},${b.metrics.memory.increase},${b.metrics.network.totalRequests},${b.metrics.network.failedRequests},${b.timestamp}`
    ).join('\n');

    return headers + rows;
  }
}

interface PerformanceComparison {
  improved: string[];
  degraded: string[];
  unchanged: string[];
}

export { PerformanceMonitor };
