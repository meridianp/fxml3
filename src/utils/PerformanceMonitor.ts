/**
 * Performance Monitor for FXML4 Trading Platform
 *
 * Tracks and reports performance metrics for:
 * - Order execution latency
 * - WebSocket message latency
 * - API response times
 * - UI render times
 * - Memory usage
 */

export interface PerformanceMetric {
  name: string;
  value: number;
  unit: 'ms' | 'bytes' | 'count' | '%';
  timestamp: Date;
  threshold?: number;
  status: 'good' | 'warning' | 'critical';
}

export interface PerformanceReport {
  summary: {
    averageOrderLatency: number;
    averageAPILatency: number;
    averageWebSocketLatency: number;
    uiRenderTime: number;
    memoryUsage: number;
  };
  metrics: PerformanceMetric[];
  violations: PerformanceMetric[];
  recommendations: string[];
}

export class PerformanceMonitor {
  private metrics: PerformanceMetric[] = [];
  private startTimes: Map<string, number> = new Map();
  private thresholds: Map<string, number> = new Map([
    ['order_execution', 10], // 10ms threshold
    ['api_call', 100], // 100ms threshold
    ['websocket_message', 5], // 5ms threshold
    ['ui_render', 16], // 16ms for 60fps
    ['memory_usage_mb', 100] // 100MB threshold
  ]);

  // Start timing an operation
  startTiming(operationName: string): void {
    this.startTimes.set(operationName, performance.now());
  }

  // End timing an operation and record the metric
  endTiming(operationName: string, category: 'order' | 'api' | 'websocket' | 'ui' | 'memory' = 'api'): number {
    const startTime = this.startTimes.get(operationName);
    if (!startTime) {
      console.warn(`No start time found for operation: ${operationName}`);
      return 0;
    }

    const endTime = performance.now();
    const duration = endTime - startTime;
    this.startTimes.delete(operationName);

    const threshold = this.thresholds.get(`${category}_${operationName}`) || this.thresholds.get(category) || 100;

    const metric: PerformanceMetric = {
      name: operationName,
      value: duration,
      unit: 'ms',
      timestamp: new Date(),
      threshold,
      status: this.getStatus(duration, threshold)
    };

    this.metrics.push(metric);

    // Keep only last 1000 metrics to prevent memory leak
    if (this.metrics.length > 1000) {
      this.metrics = this.metrics.slice(-1000);
    }

    return duration;
  }

  // Record a custom metric
  recordMetric(name: string, value: number, unit: 'ms' | 'bytes' | 'count' | '%', threshold?: number): void {
    const metric: PerformanceMetric = {
      name,
      value,
      unit,
      timestamp: new Date(),
      threshold,
      status: threshold ? this.getStatus(value, threshold) : 'good'
    };

    this.metrics.push(metric);
  }

  // Record memory usage
  recordMemoryUsage(): void {
    if ('memory' in performance) {
      const memInfo = (performance as any).memory;
      const usedMB = memInfo.usedJSHeapSize / 1024 / 1024;

      this.recordMetric('memory_usage', usedMB, 'bytes', this.thresholds.get('memory_usage_mb'));
    }
  }

  // Get metrics for a specific operation
  getMetrics(operationName?: string): PerformanceMetric[] {
    if (operationName) {
      return this.metrics.filter(m => m.name === operationName);
    }
    return [...this.metrics];
  }

  // Get average latency for an operation
  getAverageLatency(operationName: string): number {
    const operationMetrics = this.metrics.filter(m => m.name === operationName && m.unit === 'ms');
    if (operationMetrics.length === 0) return 0;

    const sum = operationMetrics.reduce((acc, m) => acc + m.value, 0);
    return sum / operationMetrics.length;
  }

  // Get 95th percentile latency
  getPercentileLatency(operationName: string, percentile: number = 95): number {
    const operationMetrics = this.metrics
      .filter(m => m.name === operationName && m.unit === 'ms')
      .map(m => m.value)
      .sort((a, b) => a - b);

    if (operationMetrics.length === 0) return 0;

    const index = Math.ceil((percentile / 100) * operationMetrics.length) - 1;
    return operationMetrics[index];
  }

  // Check if performance targets are met
  checkPerformanceTargets(): {
    orderLatency: boolean;
    apiLatency: boolean;
    webSocketLatency: boolean;
    overall: boolean;
  } {
    const orderLatency = this.getAverageLatency('order_execution') <= 10; // <10ms
    const apiLatency = this.getAverageLatency('api_call') <= 100; // <100ms
    const webSocketLatency = this.getAverageLatency('websocket_message') <= 5; // <5ms

    return {
      orderLatency,
      apiLatency,
      webSocketLatency,
      overall: orderLatency && apiLatency && webSocketLatency
    };
  }

  // Generate performance report
  generateReport(): PerformanceReport {
    const violations = this.metrics.filter(m => m.status === 'critical' || m.status === 'warning');

    const recommendations = [];
    if (this.getAverageLatency('order_execution') > 10) {
      recommendations.push('Order execution latency exceeds 10ms target. Consider optimizing order processing logic.');
    }
    if (this.getAverageLatency('api_call') > 100) {
      recommendations.push('API response time exceeds 100ms target. Consider API caching or connection pooling.');
    }
    if (this.getAverageLatency('websocket_message') > 5) {
      recommendations.push('WebSocket message latency exceeds 5ms target. Check network conditions and message processing.');
    }

    const memoryMetrics = this.metrics.filter(m => m.name === 'memory_usage');
    const avgMemory = memoryMetrics.length > 0 ?
      memoryMetrics.reduce((sum, m) => sum + m.value, 0) / memoryMetrics.length : 0;

    if (avgMemory > 100) {
      recommendations.push('Memory usage exceeds 100MB target. Consider memory optimization and garbage collection tuning.');
    }

    return {
      summary: {
        averageOrderLatency: this.getAverageLatency('order_execution'),
        averageAPILatency: this.getAverageLatency('api_call'),
        averageWebSocketLatency: this.getAverageLatency('websocket_message'),
        uiRenderTime: this.getAverageLatency('ui_render'),
        memoryUsage: avgMemory
      },
      metrics: this.getMetrics(),
      violations,
      recommendations
    };
  }

  // Clear all metrics
  clear(): void {
    this.metrics = [];
    this.startTimes.clear();
  }

  // Set custom threshold for an operation
  setThreshold(operationName: string, threshold: number): void {
    this.thresholds.set(operationName, threshold);
  }

  private getStatus(value: number, threshold: number): 'good' | 'warning' | 'critical' {
    if (value <= threshold) return 'good';
    if (value <= threshold * 1.5) return 'warning';
    return 'critical';
  }
}

// Global performance monitor instance
export const performanceMonitor = new PerformanceMonitor();

// Performance monitoring HOC for React components
export function withPerformanceMonitoring<T extends {}>(
  WrappedComponent: React.ComponentType<T>,
  componentName: string
): React.ComponentType<T> {
  const MonitoredComponent = (props: T) => {
    React.useEffect(() => {
      performanceMonitor.startTiming(`${componentName}_mount`);
      return () => {
        performanceMonitor.endTiming(`${componentName}_mount`, 'ui');
      };
    }, []);

    React.useLayoutEffect(() => {
      performanceMonitor.startTiming(`${componentName}_render`);
      performanceMonitor.endTiming(`${componentName}_render`, 'ui');
    });

    return React.createElement(WrappedComponent, props);
  };

  MonitoredComponent.displayName = `withPerformanceMonitoring(${componentName})`;
  return MonitoredComponent;
}
