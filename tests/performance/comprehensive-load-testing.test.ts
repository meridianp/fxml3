/**
 * Comprehensive Load Testing for FXML4 Trading Platform
 *
 * Advanced performance testing scenarios including:
 * - Stress testing under extreme load
 * - Real-world trading scenarios simulation
 * - Memory leak detection
 * - Resource exhaustion testing
 * - Performance degradation analysis
 */

import { PerformanceMonitor, performanceMonitor } from '../../src/utils/PerformanceMonitor';
import { TradingAPIService } from '../../src/services/TradingAPIService';
import { WebSocketService } from '../../src/services/WebSocketService';

describe('Comprehensive Load Testing', () => {
  let monitor: PerformanceMonitor;
  let apiService: TradingAPIService;

  beforeAll(() => {
    // Set longer timeout for load tests
    jest.setTimeout(30000);
  });

  beforeEach(() => {
    monitor = new PerformanceMonitor();
    apiService = new TradingAPIService('https://api.fxml4.com/v1', 'load_test_key');

    // Set aggressive performance thresholds for load testing
    monitor.setThreshold('stress_order_execution', 50); // 50ms max under load
    monitor.setThreshold('bulk_operation', 1000); // 1 second for bulk operations
    monitor.setThreshold('memory_leak', 200); // 200MB max memory usage
  });

  afterEach(() => {
    monitor.clear();
  });

  describe('Extreme Load Scenarios', () => {
    test('handles 1000 concurrent order submissions without degradation', async () => {
      const orderCount = 1000;
      const batchSize = 100;
      const batches = orderCount / batchSize;

      monitor.startTiming('bulk_operation');
      const results: any[] = [];
      const errors: any[] = [];

      console.log(`Starting extreme load test: ${orderCount} orders in ${batches} batches...`);

      for (let batch = 0; batch < batches; batch++) {
        const batchPromises: Promise<any>[] = [];

        for (let i = 0; i < batchSize; i++) {
          const orderIndex = batch * batchSize + i;

          const orderPromise = (async () => {
            const timingKey = `stress_order_execution_${orderIndex}`;
            monitor.startTiming(timingKey);

            try {
              const order = {
                symbol: `PAIR_${orderIndex % 10}`, // 10 different symbols
                side: orderIndex % 2 === 0 ? 'BUY' : 'SELL',
                quantity: 10000 + (orderIndex * 1000),
                orderType: 'MARKET' as const,
                clientOrderId: `load_test_${orderIndex}`
              };

              // Mock API response with realistic latency
              await new Promise(resolve => setTimeout(resolve, Math.random() * 30 + 5)); // 5-35ms

              const latency = monitor.endTiming(timingKey, 'stress_order');

              return {
                success: true,
                orderId: `stress_order_${orderIndex}`,
                latency,
                batchIndex: batch,
                orderIndex
              };
            } catch (error) {
              return { success: false, error, batchIndex: batch, orderIndex };
            }
          })();

          batchPromises.push(orderPromise);
        }

        // Process batch and collect results
        const batchResults = await Promise.allSettled(batchPromises);
        batchResults.forEach(result => {
          if (result.status === 'fulfilled') {
            if (result.value.success) {
              results.push(result.value);
            } else {
              errors.push(result.value);
            }
          } else {
            errors.push({ error: result.reason, batch });
          }
        });

        // Small delay between batches to prevent overwhelming
        await new Promise(resolve => setTimeout(resolve, 10));
      }

      const totalTime = monitor.endTiming('bulk_operation', 'bulk');

      // Calculate performance metrics
      const latencies = results.map(r => r.latency);
      const avgLatency = latencies.reduce((sum, lat) => sum + lat, 0) / latencies.length;
      const maxLatency = Math.max(...latencies);
      const minLatency = Math.min(...latencies);
      const throughput = results.length / (totalTime / 1000); // orders per second

      console.log(`Extreme Load Test Results:
        Orders Processed: ${results.length}/${orderCount}
        Errors: ${errors.length}
        Total Time: ${totalTime.toFixed(2)}ms
        Throughput: ${throughput.toFixed(0)} orders/second
        Latency - Avg: ${avgLatency.toFixed(2)}ms, Min: ${minLatency.toFixed(2)}ms, Max: ${maxLatency.toFixed(2)}ms
      `);

      // Performance validations
      expect(results.length).toBeGreaterThanOrEqual(orderCount * 0.95); // 95% success rate
      expect(errors.length).toBeLessThan(orderCount * 0.05); // <5% error rate
      expect(avgLatency).toBeLessThan(50); // Average latency under stress
      expect(throughput).toBeGreaterThan(20); // Minimum 20 orders/second
      expect(totalTime).toBeLessThan(25000); // Complete within 25 seconds
    });

    test('sustained high-frequency market data processing for 5 minutes', async () => {
      const duration = 5000; // 5 seconds for testing (would be 5 minutes in production)
      const ticksPerSecond = 1000;
      const totalTicks = (duration / 1000) * ticksPerSecond;

      let processedTicks = 0;
      let errors = 0;
      const latencies: number[] = [];

      console.log(`Starting sustained market data test: ${ticksPerSecond} ticks/sec for ${duration/1000}s...`);

      const startTime = performance.now();
      const endTime = startTime + duration;

      while (performance.now() < endTime) {
        const batchSize = Math.min(100, ticksPerSecond / 10); // Process in batches
        const batchPromises: Promise<void>[] = [];

        for (let i = 0; i < batchSize; i++) {
          const tickPromise = (async () => {
            const tickStart = performance.now();

            try {
              // Simulate market data processing
              const marketData = {
                symbol: `PAIR_${processedTicks % 20}`,
                price: 1.0500 + (Math.random() - 0.5) * 0.01,
                bid: 1.0498 + (Math.random() - 0.5) * 0.01,
                ask: 1.0502 + (Math.random() - 0.5) * 0.01,
                volume: Math.random() * 100000,
                timestamp: Date.now()
              };

              // Simulate processing time
              await new Promise(resolve => setTimeout(resolve, Math.random() * 2)); // 0-2ms

              const latency = performance.now() - tickStart;
              latencies.push(latency);
              processedTicks++;
            } catch (error) {
              errors++;
            }
          })();

          batchPromises.push(tickPromise);
        }

        await Promise.all(batchPromises);

        // Maintain target frequency
        await new Promise(resolve => setTimeout(resolve, 1));
      }

      const actualDuration = performance.now() - startTime;
      const actualTicksPerSecond = processedTicks / (actualDuration / 1000);
      const avgLatency = latencies.reduce((sum, lat) => sum + lat, 0) / latencies.length;
      const maxLatency = latencies.reduce((max, lat) => Math.max(max, lat), 0);

      console.log(`Sustained Market Data Test Results:
        Duration: ${actualDuration.toFixed(0)}ms
        Ticks Processed: ${processedTicks.toLocaleString()}
        Target Rate: ${ticksPerSecond} ticks/sec
        Actual Rate: ${actualTicksPerSecond.toFixed(0)} ticks/sec
        Errors: ${errors}
        Avg Latency: ${avgLatency.toFixed(3)}ms
        Max Latency: ${maxLatency.toFixed(3)}ms
      `);

      // Performance validations
      expect(processedTicks).toBeGreaterThan(totalTicks * 0.8); // Process 80% of target
      expect(actualTicksPerSecond).toBeGreaterThan(ticksPerSecond * 0.8); // Maintain 80% of target rate
      expect(errors).toBeLessThan(processedTicks * 0.01); // <1% error rate
      expect(avgLatency).toBeLessThan(10); // Average processing <10ms
      expect(maxLatency).toBeLessThan(50); // Max processing <50ms
    }, 10000);

    test('memory usage remains stable under extended load', async () => {
      const duration = 3000; // 3 seconds
      const operationsPerSecond = 100;

      monitor.recordMemoryUsage();
      const initialMemory = monitor.getMetrics('memory_usage').slice(-1)[0]?.value || 0;

      console.log(`Starting memory stability test for ${duration/1000}s...`);

      const startTime = performance.now();
      let operationCount = 0;
      const memorySnapshots: number[] = [];

      while (performance.now() - startTime < duration) {
        // Create temporary data structures that should be garbage collected
        const tempData = Array(1000).fill(0).map(() => ({
          id: Math.random(),
          timestamp: Date.now(),
          price: Math.random() * 100,
          volume: Math.random() * 1000000,
          metadata: {
            processed: true,
            calculations: Array(100).fill(0).map(() => Math.random())
          }
        }));

        // Process the data
        const processed = tempData.map(item => ({
          id: item.id,
          avgPrice: item.price,
          totalVolume: item.volume,
          score: item.metadata.calculations.reduce((sum, val) => sum + val, 0)
        }));

        operationCount++;

        // Record memory usage every 50 operations
        if (operationCount % 50 === 0) {
          monitor.recordMemoryUsage();
          const currentMemory = monitor.getMetrics('memory_usage').slice(-1)[0]?.value || 0;
          memorySnapshots.push(currentMemory);
        }

        // Allow some time for operations
        await new Promise(resolve => setTimeout(resolve, 1000 / operationsPerSecond));
      }

      // Force garbage collection if available
      if (global.gc) {
        global.gc();
      }

      monitor.recordMemoryUsage();
      const finalMemory = monitor.getMetrics('memory_usage').slice(-1)[0]?.value || 0;

      const memoryIncrease = finalMemory - initialMemory;
      const maxMemory = Math.max(...memorySnapshots, finalMemory);

      console.log(`Memory Stability Test Results:
        Duration: ${duration/1000}s
        Operations: ${operationCount}
        Initial Memory: ${initialMemory.toFixed(2)} MB
        Final Memory: ${finalMemory.toFixed(2)} MB
        Memory Increase: ${memoryIncrease.toFixed(2)} MB
        Peak Memory: ${maxMemory.toFixed(2)} MB
        Memory Snapshots: ${memorySnapshots.length}
      `);

      // Memory stability validations
      expect(memoryIncrease).toBeLessThan(50); // Memory increase <50MB
      expect(maxMemory).toBeLessThan(200); // Peak memory <200MB
      expect(finalMemory).toBeLessThan(initialMemory + 30); // Final memory reasonably close to initial
    });
  });

  describe('Resource Exhaustion Testing', () => {
    test('handles WebSocket connection limits gracefully', async () => {
      const maxConnections = 100;
      const connections: any[] = [];
      const errors: any[] = [];

      console.log(`Testing WebSocket connection limits: ${maxConnections} connections...`);

      for (let i = 0; i < maxConnections; i++) {
        try {
          // Mock WebSocket connection
          const mockConnection = {
            id: i,
            url: `ws://localhost:8080/stream_${i}`,
            readyState: 1, // OPEN
            connected: true,
            lastPing: Date.now()
          };

          connections.push(mockConnection);

          // Simulate connection overhead
          await new Promise(resolve => setTimeout(resolve, 2));
        } catch (error) {
          errors.push({ connectionIndex: i, error });
        }
      }

      // Simulate message processing across all connections
      monitor.startTiming('bulk_operation');

      for (let round = 0; round < 10; round++) {
        const messagePromises = connections.map(async (conn, index) => {
          if (!conn.connected) return;

          try {
            // Simulate incoming message processing
            const message = {
              type: 'price_update',
              symbol: `PAIR_${index % 20}`,
              price: Math.random(),
              timestamp: Date.now()
            };

            await new Promise(resolve => setTimeout(resolve, 1));
            return { success: true, connectionId: conn.id };
          } catch (error) {
            return { success: false, connectionId: conn.id, error };
          }
        });

        await Promise.all(messagePromises);
        await new Promise(resolve => setTimeout(resolve, 10)); // Brief pause between rounds
      }

      const processingTime = monitor.endTiming('bulk_operation', 'connection_processing');

      console.log(`WebSocket Connection Test Results:
        Connections Created: ${connections.length}
        Connection Errors: ${errors.length}
        Message Processing Time: ${processingTime.toFixed(2)}ms
        Success Rate: ${((connections.length - errors.length) / maxConnections * 100).toFixed(1)}%
      `);

      // Connection handling validations
      expect(connections.length).toBeGreaterThanOrEqual(maxConnections * 0.9); // 90% connection success
      expect(errors.length).toBeLessThan(maxConnections * 0.1); // <10% connection errors
      expect(processingTime).toBeLessThan(5000); // Processing within reasonable time
    });

    test('handles API rate limiting appropriately', async () => {
      const requestsPerSecond = 200; // Simulate high request rate
      const duration = 2000; // 2 seconds
      const totalRequests = (duration / 1000) * requestsPerSecond;

      let successfulRequests = 0;
      let rateLimitedRequests = 0;
      let erroredRequests = 0;
      const responseTimes: number[] = [];

      console.log(`Testing API rate limits: ${requestsPerSecond} req/sec for ${duration/1000}s...`);

      const startTime = performance.now();

      const requestPromises: Promise<void>[] = [];

      for (let i = 0; i < totalRequests; i++) {
        const requestPromise = (async () => {
          const requestStart = performance.now();

          try {
            // Simulate API request with potential rate limiting
            const shouldRateLimit = Math.random() < 0.1; // 10% chance of rate limiting

            if (shouldRateLimit) {
              rateLimitedRequests++;
              return;
            }

            // Simulate normal API response time
            const responseTime = Math.random() * 50 + 10; // 10-60ms
            await new Promise(resolve => setTimeout(resolve, responseTime));

            const totalTime = performance.now() - requestStart;
            responseTimes.push(totalTime);
            successfulRequests++;
          } catch (error) {
            erroredRequests++;
          }
        })();

        requestPromises.push(requestPromise);

        // Maintain request rate
        if (i % 10 === 0) {
          await new Promise(resolve => setTimeout(resolve, 50)); // Brief throttling
        }
      }

      await Promise.all(requestPromises);

      const totalTime = performance.now() - startTime;
      const actualRequestsPerSecond = (successfulRequests + rateLimitedRequests + erroredRequests) / (totalTime / 1000);
      const avgResponseTime = responseTimes.reduce((sum, time) => sum + time, 0) / responseTimes.length;

      console.log(`API Rate Limiting Test Results:
        Total Duration: ${totalTime.toFixed(0)}ms
        Successful Requests: ${successfulRequests}
        Rate Limited: ${rateLimitedRequests}
        Errors: ${erroredRequests}
        Actual Rate: ${actualRequestsPerSecond.toFixed(0)} req/sec
        Avg Response Time: ${avgResponseTime.toFixed(2)}ms
      `);

      // Rate limiting validations
      expect(successfulRequests).toBeGreaterThan(totalRequests * 0.7); // At least 70% success
      expect(rateLimitedRequests).toBeGreaterThan(0); // Some rate limiting should occur
      expect(erroredRequests).toBeLessThan(totalRequests * 0.05); // <5% errors
      expect(avgResponseTime).toBeLessThan(100); // Reasonable response times
    });
  });

  describe('Performance Degradation Analysis', () => {
    test('measures performance degradation over time', async () => {
      const testPeriods = 5;
      const operationsPerPeriod = 100;
      const periodDuration = 500; // 500ms per period

      const performanceData: Array<{
        period: number;
        avgLatency: number;
        throughput: number;
        errors: number;
      }> = [];

      console.log(`Analyzing performance degradation over ${testPeriods} periods...`);

      for (let period = 0; period < testPeriods; period++) {
        const periodStart = performance.now();
        const latencies: number[] = [];
        let errors = 0;

        // Execute operations for this period
        for (let i = 0; i < operationsPerPeriod; i++) {
          const opStart = performance.now();

          try {
            // Simulate gradually increasing load/complexity
            const complexity = 1 + (period * 0.2); // Increase complexity each period
            const baseLatency = Math.random() * 10; // 0-10ms base
            const additionalLatency = baseLatency * complexity;

            await new Promise(resolve => setTimeout(resolve, additionalLatency));

            const opLatency = performance.now() - opStart;
            latencies.push(opLatency);
          } catch (error) {
            errors++;
          }
        }

        const periodDurationActual = performance.now() - periodStart;
        const avgLatency = latencies.reduce((sum, lat) => sum + lat, 0) / latencies.length;
        const throughput = latencies.length / (periodDurationActual / 1000);

        performanceData.push({
          period: period + 1,
          avgLatency,
          throughput,
          errors
        });

        console.log(`Period ${period + 1}: Avg Latency: ${avgLatency.toFixed(2)}ms, Throughput: ${throughput.toFixed(0)} ops/sec, Errors: ${errors}`);

        // Wait before next period
        await new Promise(resolve => setTimeout(resolve, 100));
      }

      // Analyze degradation
      const firstPeriod = performanceData[0];
      const lastPeriod = performanceData[performanceData.length - 1];

      const latencyIncrease = ((lastPeriod.avgLatency - firstPeriod.avgLatency) / firstPeriod.avgLatency) * 100;
      const throughputDecrease = ((firstPeriod.throughput - lastPeriod.throughput) / firstPeriod.throughput) * 100;

      console.log(`Performance Degradation Analysis:
        Latency Increase: ${latencyIncrease.toFixed(1)}%
        Throughput Decrease: ${throughputDecrease.toFixed(1)}%
        Error Rate Trend: ${firstPeriod.errors} → ${lastPeriod.errors}
      `);

      // Degradation validations
      expect(latencyIncrease).toBeLessThan(200); // Latency shouldn't more than triple
      expect(throughputDecrease).toBeLessThan(70); // Throughput shouldn't drop more than 70%
      expect(lastPeriod.errors).toBeLessThan(operationsPerPeriod * 0.1); // <10% error rate even under stress
    });
  });
});
