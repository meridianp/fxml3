/**
 * Simplified Unit Tests for PerformanceMonitor
 *
 * Focus on core functionality without complex mocking
 */

import { PerformanceMonitor } from '../../src/utils/PerformanceMonitor';

describe('PerformanceMonitor - Simplified', () => {
  let monitor: PerformanceMonitor;

  beforeEach(() => {
    monitor = new PerformanceMonitor();
  });

  afterEach(() => {
    monitor.clear();
  });

  test('creates monitor instance', () => {
    expect(monitor).toBeDefined();
  });

  test('records custom metrics', () => {
    monitor.recordMetric('test_metric', 100, 'ms');

    const metrics = monitor.getMetrics('test_metric');
    expect(metrics).toHaveLength(1);
    expect(metrics[0].name).toBe('test_metric');
    expect(metrics[0].value).toBe(100);
    expect(metrics[0].unit).toBe('ms');
  });

  test('calculates metric status based on thresholds', () => {
    monitor.recordMetric('good_metric', 50, 'ms', 100);
    monitor.recordMetric('warning_metric', 125, 'ms', 100);
    monitor.recordMetric('critical_metric', 250, 'ms', 100);

    const goodMetrics = monitor.getMetrics('good_metric');
    const warningMetrics = monitor.getMetrics('warning_metric');
    const criticalMetrics = monitor.getMetrics('critical_metric');

    expect(goodMetrics[0].status).toBe('good');
    expect(warningMetrics[0].status).toBe('warning');
    expect(criticalMetrics[0].status).toBe('critical');
  });

  test('returns empty array for non-existent metrics', () => {
    const metrics = monitor.getMetrics('non_existent');
    expect(metrics).toHaveLength(0);
  });

  test('calculates average latency', () => {
    monitor.recordMetric('test_op', 10, 'ms');
    monitor.recordMetric('test_op', 20, 'ms');
    monitor.recordMetric('test_op', 30, 'ms');

    const average = monitor.getAverageLatency('test_op');
    expect(average).toBe(20);
  });

  test('returns 0 for average of non-existent operation', () => {
    const average = monitor.getAverageLatency('non_existent');
    expect(average).toBe(0);
  });

  test('calculates percentile latency', () => {
    const values = [10, 20, 30, 40, 50];
    values.forEach(value => {
      monitor.recordMetric('test_op', value, 'ms');
    });

    const p50 = monitor.getPercentileLatency('test_op', 50);
    expect(p50).toBe(30); // Median of [10, 20, 30, 40, 50]
  });

  test('returns 0 for percentile of non-existent operation', () => {
    const p95 = monitor.getPercentileLatency('non_existent', 95);
    expect(p95).toBe(0);
  });

  test('generates performance report', () => {
    monitor.recordMetric('order_execution', 8, 'ms');
    monitor.recordMetric('api_call', 95, 'ms');
    monitor.recordMetric('websocket_message', 3, 'ms');

    const report = monitor.generateReport();

    expect(report).toHaveProperty('summary');
    expect(report).toHaveProperty('metrics');
    expect(report).toHaveProperty('violations');
    expect(report).toHaveProperty('recommendations');

    expect(Array.isArray(report.metrics)).toBe(true);
    expect(Array.isArray(report.violations)).toBe(true);
    expect(Array.isArray(report.recommendations)).toBe(true);
  });

  test('checks performance targets', () => {
    monitor.recordMetric('order_execution', 8, 'ms');
    monitor.recordMetric('api_call', 80, 'ms');
    monitor.recordMetric('websocket_message', 3, 'ms');

    const targets = monitor.checkPerformanceTargets();

    expect(targets).toHaveProperty('orderLatency');
    expect(targets).toHaveProperty('apiLatency');
    expect(targets).toHaveProperty('webSocketLatency');
    expect(targets).toHaveProperty('overall');

    expect(typeof targets.orderLatency).toBe('boolean');
    expect(typeof targets.apiLatency).toBe('boolean');
    expect(typeof targets.webSocketLatency).toBe('boolean');
    expect(typeof targets.overall).toBe('boolean');
  });

  test('sets custom thresholds', () => {
    monitor.setThreshold('custom_metric', 75);

    monitor.recordMetric('custom_metric', 50, 'ms', 75);
    const metrics = monitor.getMetrics('custom_metric');

    expect(metrics[0].threshold).toBe(75);
    expect(metrics[0].status).toBe('good');
  });

  test('clears all metrics', () => {
    monitor.recordMetric('test_metric', 100, 'ms');
    expect(monitor.getMetrics()).toHaveLength(1);

    monitor.clear();
    expect(monitor.getMetrics()).toHaveLength(0);
  });

  test('handles memory usage recording safely', () => {
    expect(() => monitor.recordMemoryUsage()).not.toThrow();
  });

  test('filters metrics by operation name', () => {
    monitor.recordMetric('operation_a', 10, 'ms');
    monitor.recordMetric('operation_b', 20, 'ms');
    monitor.recordMetric('operation_a', 15, 'ms');

    const operationAMetrics = monitor.getMetrics('operation_a');
    expect(operationAMetrics).toHaveLength(2);
    expect(operationAMetrics.every(m => m.name === 'operation_a')).toBe(true);
  });

  test('returns all metrics when no filter provided', () => {
    monitor.recordMetric('operation_a', 10, 'ms');
    monitor.recordMetric('operation_b', 20, 'ms');

    const allMetrics = monitor.getMetrics();
    expect(allMetrics).toHaveLength(2);
  });
});
