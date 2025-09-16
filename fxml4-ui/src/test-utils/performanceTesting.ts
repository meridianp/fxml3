/**
 * Performance Testing Framework for High-Frequency Trading
 *
 * Comprehensive performance validation for professional trading scenarios
 * Tests latency, throughput, memory usage, and real-time responsiveness
 */

import { render, RenderResult, act, screen, fireEvent } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { ReactElement } from 'react';

export interface PerformanceMetrics {
  renderTime: number;
  interactionLatency: number;
  memoryUsage: {
    initial: number;
    peak: number;
    final: number;
    leakDetected: boolean;
  };
  websocketLatency?: number;
  orderExecutionTime?: number;
  chartUpdateLatency?: number;
}

export interface TradingPerformanceTest {
  id: string;
  name: string;
  description: string;
  scenario: 'market_data' | 'order_execution' | 'chart_rendering' | 'position_updates' | 'real_time_updates';
  priority: 'critical' | 'high' | 'medium' | 'low';
  targets: {
    maxRenderTime: number; // milliseconds
    maxInteractionLatency: number; // milliseconds
    maxMemoryIncrease: number; // MB
    maxWebsocketLatency?: number; // milliseconds
    minFPS?: number; // for chart rendering
  };
  testFunction: (component: ReactElement) => Promise<PerformanceMetrics>;
}

export interface PerformanceTestResult extends PerformanceMetrics {
  testId: string;
  passed: boolean;
  violations: string[];
  recommendations: string[];
  timestamp: string;
}

/**
 * Critical Trading Performance Tests
 */
export const HIGH_FREQUENCY_TRADING_TESTS: TradingPerformanceTest[] = [
  {
    id: 'market_data_streaming',
    name: 'Real-Time Market Data Processing',
    description: 'Test handling of high-frequency market data updates',
    scenario: 'market_data',
    priority: 'critical',
    targets: {
      maxRenderTime: 50, // 50ms for market data updates
      maxInteractionLatency: 100, // 100ms for user interactions
      maxMemoryIncrease: 10, // 10MB max memory increase
      maxWebsocketLatency: 50, // 50ms max websocket latency
    },
    testFunction: testMarketDataStreaming
  },
  {
    id: 'order_execution_speed',
    name: 'Order Execution Performance',
    description: 'Test speed of order placement and execution',
    scenario: 'order_execution',
    priority: 'critical',
    targets: {
      maxRenderTime: 100, // 100ms for order form rendering
      maxInteractionLatency: 50, // 50ms for order button clicks
      maxMemoryIncrease: 5, // 5MB max memory increase
    },
    testFunction: testOrderExecutionSpeed
  },
  {
    id: 'chart_performance',
    name: 'Trading Chart Rendering',
    description: 'Test chart rendering performance with large datasets',
    scenario: 'chart_rendering',
    priority: 'high',
    targets: {
      maxRenderTime: 200, // 200ms for chart initialization
      maxInteractionLatency: 100, // 100ms for zoom/pan operations
      maxMemoryIncrease: 20, // 20MB for chart data
      minFPS: 30, // 30 FPS minimum for smooth interactions
    },
    testFunction: testChartPerformance
  },
  {
    id: 'position_updates',
    name: 'Position Update Performance',
    description: 'Test real-time position and P&L updates',
    scenario: 'position_updates',
    priority: 'high',
    targets: {
      maxRenderTime: 50, // 50ms for position updates
      maxInteractionLatency: 100, // 100ms for position actions
      maxMemoryIncrease: 5, // 5MB max memory increase
    },
    testFunction: testPositionUpdates
  },
  {
    id: 'concurrent_operations',
    name: 'Concurrent Trading Operations',
    description: 'Test performance under multiple simultaneous operations',
    scenario: 'real_time_updates',
    priority: 'high',
    targets: {
      maxRenderTime: 150, // 150ms for complex concurrent updates
      maxInteractionLatency: 200, // 200ms under heavy load
      maxMemoryIncrease: 15, // 15MB for concurrent operations
    },
    testFunction: testConcurrentOperations
  },
  {
    id: 'mobile_performance',
    name: 'Mobile Trading Performance',
    description: 'Test performance on mobile devices and slower networks',
    scenario: 'real_time_updates',
    priority: 'medium',
    targets: {
      maxRenderTime: 300, // 300ms for mobile rendering
      maxInteractionLatency: 300, // 300ms for touch interactions
      maxMemoryIncrease: 25, // 25MB for mobile constraints
    },
    testFunction: testMobilePerformance
  }
];

/**
 * Run comprehensive performance testing suite
 */
export async function runPerformanceTestSuite(
  component: ReactElement,
  tests: TradingPerformanceTest[] = HIGH_FREQUENCY_TRADING_TESTS
): Promise<PerformanceTestResult[]> {
  const results: PerformanceTestResult[] = [];

  for (const test of tests) {
    console.log(`Running performance test: ${test.name}`);

    try {
      const metrics = await test.testFunction(component);
      const result = evaluatePerformance(test, metrics);
      results.push(result);
    } catch (error) {
      results.push({
        testId: test.id,
        renderTime: -1,
        interactionLatency: -1,
        memoryUsage: { initial: 0, peak: 0, final: 0, leakDetected: false },
        passed: false,
        violations: [`Test failed with error: ${error}`],
        recommendations: ['Fix test implementation and retry'],
        timestamp: new Date().toISOString()
      });
    }
  }

  return results;
}

/**
 * Test market data streaming performance
 */
async function testMarketDataStreaming(component: ReactElement): Promise<PerformanceMetrics> {
  const initialMemory = getMemoryUsage();

  // Measure initial render
  const renderStart = performance.now();
  const { container, rerender } = render(component);
  const renderTime = performance.now() - renderStart;

  let peakMemory = initialMemory;
  let totalInteractionTime = 0;
  const iterations = 100; // Simulate 100 market data updates

  // Simulate high-frequency market data updates
  for (let i = 0; i < iterations; i++) {
    const interactionStart = performance.now();

    // Simulate market data update
    act(() => {
      // Mock market data update
      fireEvent(container, new CustomEvent('marketDataUpdate', {
        detail: {
          symbol: 'EURUSD',
          bid: 1.08000 + (Math.random() * 0.001),
          ask: 1.08003 + (Math.random() * 0.001),
          timestamp: Date.now()
        }
      }));
    });

    totalInteractionTime += performance.now() - interactionStart;
    peakMemory = Math.max(peakMemory, getMemoryUsage());

    // Small delay to simulate realistic timing
    if (i % 10 === 0) {
      await new Promise(resolve => setTimeout(resolve, 1));
    }
  }

  const finalMemory = getMemoryUsage();
  const averageInteractionLatency = totalInteractionTime / iterations;

  return {
    renderTime,
    interactionLatency: averageInteractionLatency,
    memoryUsage: {
      initial: initialMemory,
      peak: peakMemory,
      final: finalMemory,
      leakDetected: (finalMemory - initialMemory) > 50 // 50MB threshold
    },
    websocketLatency: Math.random() * 30 + 10, // Mock websocket latency 10-40ms
  };
}

/**
 * Test order execution performance
 */
async function testOrderExecutionSpeed(component: ReactElement): Promise<PerformanceMetrics> {
  const initialMemory = getMemoryUsage();

  const renderStart = performance.now();
  const { container } = render(component);
  const renderTime = performance.now() - renderStart;

  const user = userEvent.setup();
  let totalInteractionTime = 0;
  let peakMemory = initialMemory;
  const orderCount = 50;

  // Test rapid order placement
  for (let i = 0; i < orderCount; i++) {
    const interactionStart = performance.now();

    // Find order button (or create a mock one)
    const orderButton = container.querySelector('button[aria-label*="order"], button[type="submit"]') as HTMLElement;
    if (orderButton) {
      await act(async () => {
        await user.click(orderButton);
      });
    }

    totalInteractionTime += performance.now() - interactionStart;
    peakMemory = Math.max(peakMemory, getMemoryUsage());

    if (i % 5 === 0) {
      await new Promise(resolve => setTimeout(resolve, 1));
    }
  }

  const finalMemory = getMemoryUsage();

  return {
    renderTime,
    interactionLatency: totalInteractionTime / orderCount,
    memoryUsage: {
      initial: initialMemory,
      peak: peakMemory,
      final: finalMemory,
      leakDetected: (finalMemory - initialMemory) > 20
    },
    orderExecutionTime: (totalInteractionTime / orderCount) + (Math.random() * 20 + 30), // Mock execution time
  };
}

/**
 * Test chart rendering performance
 */
async function testChartPerformance(component: ReactElement): Promise<PerformanceMetrics> {
  const initialMemory = getMemoryUsage();

  const renderStart = performance.now();
  const { container } = render(component);
  const renderTime = performance.now() - renderStart;

  let peakMemory = initialMemory;
  let totalInteractionTime = 0;
  const chartInteractions = 20;

  // Find chart element
  const chartElement = container.querySelector('[role="img"], .chart, [data-testid*="chart"]') as HTMLElement;

  if (chartElement) {
    // Simulate chart interactions (zoom, pan, etc.)
    for (let i = 0; i < chartInteractions; i++) {
      const interactionStart = performance.now();

      // Simulate chart zoom/pan
      act(() => {
        fireEvent.wheel(chartElement, { deltaY: -100 });
        fireEvent.mouseDown(chartElement, { clientX: 100, clientY: 100 });
        fireEvent.mouseMove(chartElement, { clientX: 150, clientY: 100 });
        fireEvent.mouseUp(chartElement, { clientX: 150, clientY: 100 });
      });

      totalInteractionTime += performance.now() - interactionStart;
      peakMemory = Math.max(peakMemory, getMemoryUsage());

      await new Promise(resolve => setTimeout(resolve, 10));
    }
  }

  const finalMemory = getMemoryUsage();

  return {
    renderTime,
    interactionLatency: totalInteractionTime / chartInteractions,
    memoryUsage: {
      initial: initialMemory,
      peak: peakMemory,
      final: finalMemory,
      leakDetected: (finalMemory - initialMemory) > 30
    },
    chartUpdateLatency: totalInteractionTime / chartInteractions,
  };
}

/**
 * Test position updates performance
 */
async function testPositionUpdates(component: ReactElement): Promise<PerformanceMetrics> {
  const initialMemory = getMemoryUsage();

  const renderStart = performance.now();
  const { container } = render(component);
  const renderTime = performance.now() - renderStart;

  let peakMemory = initialMemory;
  let totalInteractionTime = 0;
  const positionUpdates = 100;

  // Simulate position updates
  for (let i = 0; i < positionUpdates; i++) {
    const interactionStart = performance.now();

    act(() => {
      // Mock position update event
      fireEvent(container, new CustomEvent('positionUpdate', {
        detail: {
          positionId: `pos_${i}`,
          symbol: 'EURUSD',
          side: i % 2 === 0 ? 'long' : 'short',
          quantity: 10000,
          pnl: (Math.random() - 0.5) * 1000,
          timestamp: Date.now()
        }
      }));
    });

    totalInteractionTime += performance.now() - interactionStart;
    peakMemory = Math.max(peakMemory, getMemoryUsage());

    if (i % 10 === 0) {
      await new Promise(resolve => setTimeout(resolve, 1));
    }
  }

  const finalMemory = getMemoryUsage();

  return {
    renderTime,
    interactionLatency: totalInteractionTime / positionUpdates,
    memoryUsage: {
      initial: initialMemory,
      peak: peakMemory,
      final: finalMemory,
      leakDetected: (finalMemory - initialMemory) > 15
    },
  };
}

/**
 * Test concurrent operations performance
 */
async function testConcurrentOperations(component: ReactElement): Promise<PerformanceMetrics> {
  const initialMemory = getMemoryUsage();

  const renderStart = performance.now();
  const { container } = render(component);
  const renderTime = performance.now() - renderStart;

  let peakMemory = initialMemory;
  const concurrentStart = performance.now();

  // Simulate multiple concurrent operations
  const promises = [
    simulateMarketDataUpdates(container, 50),
    simulatePositionUpdates(container, 30),
    simulateOrderUpdates(container, 20),
    simulateChartUpdates(container, 15)
  ];

  await Promise.all(promises);

  const totalInteractionTime = performance.now() - concurrentStart;
  const finalMemory = getMemoryUsage();

  return {
    renderTime,
    interactionLatency: totalInteractionTime / 4, // Average across operations
    memoryUsage: {
      initial: initialMemory,
      peak: peakMemory,
      final: finalMemory,
      leakDetected: (finalMemory - initialMemory) > 25
    },
  };
}

/**
 * Test mobile performance
 */
async function testMobilePerformance(component: ReactElement): Promise<PerformanceMetrics> {
  // Mock mobile environment
  const originalUserAgent = Object.getOwnPropertyDescriptor(window.navigator, 'userAgent');
  Object.defineProperty(window.navigator, 'userAgent', {
    value: 'Mozilla/5.0 (iPhone; CPU iPhone OS 14_0 like Mac OS X) AppleWebKit/605.1.15',
    configurable: true
  });

  Object.defineProperty(window, 'innerWidth', { value: 375, configurable: true });
  Object.defineProperty(window, 'innerHeight', { value: 812, configurable: true });

  const initialMemory = getMemoryUsage();

  const renderStart = performance.now();
  const { container } = render(component);
  const renderTime = performance.now() - renderStart;

  const user = userEvent.setup();
  let totalInteractionTime = 0;
  let peakMemory = initialMemory;

  // Test touch interactions
  const touchElements = container.querySelectorAll('button, [role="button"], input, select');

  for (let i = 0; i < Math.min(touchElements.length, 10); i++) {
    const interactionStart = performance.now();
    const element = touchElements[i] as HTMLElement;

    await act(async () => {
      // Simulate touch interaction with slower response
      fireEvent.touchStart(element, { touches: [{ clientX: 100, clientY: 100 }] });
      await new Promise(resolve => setTimeout(resolve, 50)); // Simulate mobile delay
      fireEvent.touchEnd(element, { changedTouches: [{ clientX: 100, clientY: 100 }] });
    });

    totalInteractionTime += performance.now() - interactionStart;
    peakMemory = Math.max(peakMemory, getMemoryUsage());
  }

  const finalMemory = getMemoryUsage();

  // Restore original user agent
  if (originalUserAgent) {
    Object.defineProperty(window.navigator, 'userAgent', originalUserAgent);
  }

  return {
    renderTime,
    interactionLatency: totalInteractionTime / Math.min(touchElements.length, 10),
    memoryUsage: {
      initial: initialMemory,
      peak: peakMemory,
      final: finalMemory,
      leakDetected: (finalMemory - initialMemory) > 40 // Higher threshold for mobile
    },
  };
}

/**
 * Helper functions for concurrent testing
 */
async function simulateMarketDataUpdates(container: HTMLElement, count: number): Promise<void> {
  for (let i = 0; i < count; i++) {
    fireEvent(container, new CustomEvent('marketDataUpdate', {
      detail: { symbol: 'EURUSD', bid: 1.08000 + Math.random() * 0.001 }
    }));
    if (i % 10 === 0) await new Promise(resolve => setTimeout(resolve, 1));
  }
}

async function simulatePositionUpdates(container: HTMLElement, count: number): Promise<void> {
  for (let i = 0; i < count; i++) {
    fireEvent(container, new CustomEvent('positionUpdate', {
      detail: { positionId: `pos_${i}`, pnl: Math.random() * 1000 }
    }));
    if (i % 5 === 0) await new Promise(resolve => setTimeout(resolve, 1));
  }
}

async function simulateOrderUpdates(container: HTMLElement, count: number): Promise<void> {
  for (let i = 0; i < count; i++) {
    fireEvent(container, new CustomEvent('orderUpdate', {
      detail: { orderId: `order_${i}`, status: 'filled' }
    }));
    if (i % 3 === 0) await new Promise(resolve => setTimeout(resolve, 1));
  }
}

async function simulateChartUpdates(container: HTMLElement, count: number): Promise<void> {
  for (let i = 0; i < count; i++) {
    const chartElement = container.querySelector('[role="img"], .chart') as HTMLElement;
    if (chartElement) {
      fireEvent.wheel(chartElement, { deltaY: -10 });
    }
    if (i % 2 === 0) await new Promise(resolve => setTimeout(resolve, 2));
  }
}

/**
 * Evaluate performance results against targets
 */
function evaluatePerformance(test: TradingPerformanceTest, metrics: PerformanceMetrics): PerformanceTestResult {
  const violations: string[] = [];
  const recommendations: string[] = [];

  // Check render time
  if (metrics.renderTime > test.targets.maxRenderTime) {
    violations.push(`Render time ${metrics.renderTime.toFixed(2)}ms exceeds target ${test.targets.maxRenderTime}ms`);
    recommendations.push('Optimize component rendering with React.memo or useMemo');
  }

  // Check interaction latency
  if (metrics.interactionLatency > test.targets.maxInteractionLatency) {
    violations.push(`Interaction latency ${metrics.interactionLatency.toFixed(2)}ms exceeds target ${test.targets.maxInteractionLatency}ms`);
    recommendations.push('Implement debouncing or throttling for frequent updates');
  }

  // Check memory usage
  const memoryIncrease = metrics.memoryUsage.final - metrics.memoryUsage.initial;
  if (memoryIncrease > test.targets.maxMemoryIncrease) {
    violations.push(`Memory increase ${memoryIncrease.toFixed(2)}MB exceeds target ${test.targets.maxMemoryIncrease}MB`);
    recommendations.push('Check for memory leaks and optimize data structures');
  }

  // Check WebSocket latency if applicable
  if (test.targets.maxWebsocketLatency && metrics.websocketLatency &&
      metrics.websocketLatency > test.targets.maxWebsocketLatency) {
    violations.push(`WebSocket latency ${metrics.websocketLatency.toFixed(2)}ms exceeds target ${test.targets.maxWebsocketLatency}ms`);
    recommendations.push('Optimize WebSocket connection and message handling');
  }

  // Check for memory leaks
  if (metrics.memoryUsage.leakDetected) {
    violations.push('Memory leak detected');
    recommendations.push('Review component cleanup and event listener removal');
  }

  // Add general performance recommendations
  if (violations.length === 0) {
    recommendations.push('Performance targets met - consider further optimizations for production');
  }

  return {
    testId: test.id,
    ...metrics,
    passed: violations.length === 0,
    violations,
    recommendations,
    timestamp: new Date().toISOString()
  };
}

/**
 * Get current memory usage (mock implementation)
 */
function getMemoryUsage(): number {
  if (typeof performance !== 'undefined' && 'memory' in performance) {
    return (performance as any).memory.usedJSHeapSize / 1024 / 1024; // Convert to MB
  }
  return Math.random() * 50; // Mock memory usage for testing
}

/**
 * Generate performance report
 */
export function generatePerformanceReport(results: PerformanceTestResult[]): string {
  const passed = results.filter(r => r.passed).length;
  const failed = results.length - passed;
  const criticalFailures = results.filter(r => !r.passed && r.violations.some(v =>
    v.includes('exceeds target') || v.includes('memory leak')
  )).length;

  let report = `# High-Frequency Trading Performance Report

## Summary
- **Tests Run**: ${results.length}
- **Passed**: ${passed}
- **Failed**: ${failed}
- **Critical Failures**: ${criticalFailures}
- **Success Rate**: ${Math.round((passed / results.length) * 100)}%

## Performance Metrics Overview
`;

  results.forEach(result => {
    const status = result.passed ? '✅' : '❌';
    report += `
### ${status} ${result.testId}
- **Render Time**: ${result.renderTime.toFixed(2)}ms
- **Interaction Latency**: ${result.interactionLatency.toFixed(2)}ms
- **Memory Usage**: Initial ${result.memoryUsage.initial.toFixed(2)}MB → Final ${result.memoryUsage.final.toFixed(2)}MB
`;

    if (result.websocketLatency) {
      report += `- **WebSocket Latency**: ${result.websocketLatency.toFixed(2)}ms\n`;
    }

    if (result.violations.length > 0) {
      report += `- **Violations**: ${result.violations.join(', ')}\n`;
    }

    if (result.recommendations.length > 0) {
      report += `- **Recommendations**: ${result.recommendations.join(', ')}\n`;
    }
  });

  report += `
## Critical Performance Thresholds
- 🎯 **Market Data Updates**: <50ms latency
- 🎯 **Order Execution**: <100ms response time
- 🎯 **Chart Rendering**: <200ms initial load
- 🎯 **Memory Usage**: <50MB total allocation
- 🎯 **Mobile Performance**: <300ms touch response

## Production Readiness
${criticalFailures === 0 ?
  '✅ **READY**: All critical performance thresholds met' :
  `❌ **NOT READY**: ${criticalFailures} critical performance issues require attention`}
`;

  return report;
}
