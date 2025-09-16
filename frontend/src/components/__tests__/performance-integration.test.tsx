/**
 * Performance Testing Integration Tests
 *
 * Comprehensive performance testing demonstration for the FXML4 trading platform
 * Tests high-frequency trading scenarios and validates performance framework
 */

import React from 'react';
import { render, screen } from '@testing-library/react';
import {
  runPerformanceTestSuite,
  HIGH_FREQUENCY_TRADING_TESTS,
  generatePerformanceReport
} from '@/test-utils/performanceTesting';

// Mock high-performance trading component for testing
const MockHighFrequencyTradingDashboard = () => (
  <div data-testid="hft-dashboard">
    <header role="banner">
      <h1>High-Frequency Trading Dashboard</h1>
    </header>

    <main role="main">
      {/* Market Data Panel */}
      <section aria-labelledby="market-data">
        <h2 id="market-data">Live Market Data</h2>
        <div className="market-data-grid" role="grid" aria-label="Real-time market prices">
          <div role="row" aria-label="Header row">
            <div role="columnheader">Symbol</div>
            <div role="columnheader">Bid</div>
            <div role="columnheader">Ask</div>
            <div role="columnheader">Change</div>
            <div role="columnheader">Volume</div>
          </div>

          {/* Simulate multiple currency pairs for performance testing */}
          {['EURUSD', 'GBPUSD', 'USDJPY', 'USDCHF', 'AUDUSD', 'USDCAD', 'NZDUSD', 'EURJPY'].map(symbol => (
            <div key={symbol} role="row" aria-label={`${symbol} market data`} data-testid={`market-${symbol}`}>
              <div role="gridcell">{symbol}</div>
              <div role="gridcell" aria-live="polite">{(1.0000 + Math.random() * 0.5).toFixed(5)}</div>
              <div role="gridcell" aria-live="polite">{(1.0003 + Math.random() * 0.5).toFixed(5)}</div>
              <div role="gridcell" aria-live="polite" className={Math.random() > 0.5 ? 'positive' : 'negative'}>
                {(Math.random() * 0.002 - 0.001).toFixed(5)}
              </div>
              <div role="gridcell">{Math.floor(Math.random() * 1000000)}</div>
            </div>
          ))}
        </div>
      </section>

      {/* Order Entry Panel */}
      <section aria-labelledby="order-entry">
        <h2 id="order-entry">Quick Order Entry</h2>
        <form aria-label="High-frequency order placement">
          <div className="order-grid">
            <label htmlFor="hf-symbol">Symbol</label>
            <select id="hf-symbol" aria-required="true">
              <option value="EURUSD">EUR/USD</option>
              <option value="GBPUSD">GBP/USD</option>
              <option value="USDJPY">USD/JPY</option>
            </select>

            <label htmlFor="hf-quantity">Quantity</label>
            <input
              id="hf-quantity"
              type="number"
              aria-required="true"
              min="1000"
              max="10000000"
              step="1000"
              defaultValue="100000"
            />

            <label htmlFor="hf-price">Price</label>
            <input
              id="hf-price"
              type="number"
              aria-required="true"
              step="0.00001"
              defaultValue="1.08245"
            />

            <div className="order-buttons">
              <button
                type="button"
                className="buy-button"
                aria-label="Place buy order"
                data-testid="buy-order-button"
              >
                BUY
              </button>
              <button
                type="button"
                className="sell-button"
                aria-label="Place sell order"
                data-testid="sell-order-button"
              >
                SELL
              </button>
            </div>
          </div>
        </form>
      </section>

      {/* Live Positions */}
      <section aria-labelledby="live-positions">
        <h2 id="live-positions">Live Positions</h2>
        <table role="table" aria-label="Current trading positions">
          <caption>Real-time position updates</caption>
          <thead>
            <tr>
              <th scope="col">Position ID</th>
              <th scope="col">Symbol</th>
              <th scope="col">Side</th>
              <th scope="col">Quantity</th>
              <th scope="col">Entry Price</th>
              <th scope="col">Current Price</th>
              <th scope="col">P&L</th>
              <th scope="col">Actions</th>
            </tr>
          </thead>
          <tbody>
            {/* Simulate multiple positions for performance testing */}
            {Array.from({ length: 20 }, (_, i) => {
              const symbols = ['EURUSD', 'GBPUSD', 'USDJPY'];
              const symbol = symbols[i % symbols.length];
              const side = i % 2 === 0 ? 'Long' : 'Short';
              const pnl = (Math.random() - 0.5) * 2000;

              return (
                <tr key={i} data-testid={`position-${i}`}>
                  <td>POS_{String(i).padStart(4, '0')}</td>
                  <td>{symbol}</td>
                  <td>{side}</td>
                  <td>{(100000 + Math.floor(Math.random() * 900000)).toLocaleString()}</td>
                  <td>{(1.0000 + Math.random() * 0.5).toFixed(5)}</td>
                  <td aria-live="polite">{(1.0000 + Math.random() * 0.5).toFixed(5)}</td>
                  <td
                    aria-live="polite"
                    className={pnl >= 0 ? 'positive' : 'negative'}
                    data-testid={`pnl-${i}`}
                  >
                    {pnl >= 0 ? '+' : ''}${pnl.toFixed(2)}
                  </td>
                  <td>
                    <button
                      aria-label={`Close ${symbol} position`}
                      data-testid={`close-position-${i}`}
                    >
                      Close
                    </button>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </section>

      {/* Trading Chart */}
      <section aria-labelledby="trading-chart">
        <h2 id="trading-chart">Real-Time Chart</h2>
        <div
          role="application"
          aria-label="High-frequency trading chart with real-time price data"
          aria-describedby="chart-description"
          tabIndex="0"
          className="hf-trading-chart"
          data-testid="hf-trading-chart"
          style={{ width: '100%', height: '400px', background: '#1a1a1a' }}
        >
          <div id="chart-description" className="sr-only">
            Interactive high-frequency trading chart showing price movements and volume.
            Use arrow keys to navigate, + and - to zoom, and mouse to pan.
          </div>

          {/* Simulate chart elements for performance testing */}
          <div className="chart-grid">
            {Array.from({ length: 1000 }, (_, i) => (
              <div
                key={i}
                className="chart-point"
                style={{
                  position: 'absolute',
                  left: `${(i / 1000) * 100}%`,
                  top: `${Math.random() * 100}%`,
                  width: '2px',
                  height: '2px',
                  background: '#00ff00'
                }}
                data-testid={`chart-point-${i}`}
              />
            ))}
          </div>
        </div>
      </section>
    </main>

    {/* Status and Notifications */}
    <div role="status" aria-live="polite" aria-label="Trading status updates">
      <div data-testid="connection-status">Connected to trading server</div>
    </div>

    <div role="alert" aria-live="assertive" className="alert-container">
      {/* Alert messages appear here */}
    </div>
  </div>
);

describe('Performance Testing Integration', () => {
  describe('High-Frequency Trading Performance', () => {
    it('should validate performance testing framework initialization', async () => {
      // Test that the performance testing framework can be initialized
      expect(HIGH_FREQUENCY_TRADING_TESTS.length).toBeGreaterThan(0);
      expect(HIGH_FREQUENCY_TRADING_TESTS[0]).toHaveProperty('id');
      expect(HIGH_FREQUENCY_TRADING_TESTS[0]).toHaveProperty('testFunction');
      expect(HIGH_FREQUENCY_TRADING_TESTS[0]).toHaveProperty('targets');
    });

    it('should test market data streaming performance', async () => {
      render(<MockHighFrequencyTradingDashboard />);

      const marketDataTest = HIGH_FREQUENCY_TRADING_TESTS.find(t => t.id === 'market_data_streaming');
      expect(marketDataTest).toBeDefined();

      if (marketDataTest) {
        const metrics = await marketDataTest.testFunction(<MockHighFrequencyTradingDashboard />);

        expect(metrics.renderTime).toBeGreaterThan(0);
        expect(metrics.interactionLatency).toBeGreaterThan(0);
        expect(metrics.memoryUsage.initial).toBeGreaterThanOrEqual(0);
        expect(metrics.memoryUsage.final).toBeGreaterThanOrEqual(metrics.memoryUsage.initial);
        expect(typeof metrics.memoryUsage.leakDetected).toBe('boolean');
      }
    }, 15000); // Allow 15 seconds for performance testing

    it('should test order execution performance', async () => {
      render(<MockHighFrequencyTradingDashboard />);

      const orderTest = HIGH_FREQUENCY_TRADING_TESTS.find(t => t.id === 'order_execution_speed');
      expect(orderTest).toBeDefined();

      if (orderTest) {
        const metrics = await orderTest.testFunction(<MockHighFrequencyTradingDashboard />);

        expect(metrics.renderTime).toBeGreaterThan(0);
        expect(metrics.interactionLatency).toBeGreaterThan(0);
        expect(metrics.orderExecutionTime).toBeGreaterThan(0);
        expect(metrics.memoryUsage).toBeDefined();
      }
    }, 10000);

    it('should test chart rendering performance', async () => {
      render(<MockHighFrequencyTradingDashboard />);

      const chartTest = HIGH_FREQUENCY_TRADING_TESTS.find(t => t.id === 'chart_performance');
      expect(chartTest).toBeDefined();

      if (chartTest) {
        const metrics = await chartTest.testFunction(<MockHighFrequencyTradingDashboard />);

        expect(metrics.renderTime).toBeGreaterThan(0);
        expect(metrics.interactionLatency).toBeGreaterThan(0);
        expect(metrics.chartUpdateLatency).toBeGreaterThan(0);
        expect(metrics.memoryUsage).toBeDefined();
      }
    }, 10000);

    it('should test position updates performance', async () => {
      render(<MockHighFrequencyTradingDashboard />);

      const positionTest = HIGH_FREQUENCY_TRADING_TESTS.find(t => t.id === 'position_updates');
      expect(positionTest).toBeDefined();

      if (positionTest) {
        const metrics = await positionTest.testFunction(<MockHighFrequencyTradingDashboard />);

        expect(metrics.renderTime).toBeGreaterThan(0);
        expect(metrics.interactionLatency).toBeGreaterThan(0);
        expect(metrics.memoryUsage).toBeDefined();
      }
    }, 10000);

    it('should test concurrent operations performance', async () => {
      render(<MockHighFrequencyTradingDashboard />);

      const concurrentTest = HIGH_FREQUENCY_TRADING_TESTS.find(t => t.id === 'concurrent_operations');
      expect(concurrentTest).toBeDefined();

      if (concurrentTest) {
        const metrics = await concurrentTest.testFunction(<MockHighFrequencyTradingDashboard />);

        expect(metrics.renderTime).toBeGreaterThan(0);
        expect(metrics.interactionLatency).toBeGreaterThan(0);
        expect(metrics.memoryUsage).toBeDefined();
      }
    }, 15000);

    it('should test mobile performance', async () => {
      render(<MockHighFrequencyTradingDashboard />);

      const mobileTest = HIGH_FREQUENCY_TRADING_TESTS.find(t => t.id === 'mobile_performance');
      expect(mobileTest).toBeDefined();

      if (mobileTest) {
        const metrics = await mobileTest.testFunction(<MockHighFrequencyTradingDashboard />);

        expect(metrics.renderTime).toBeGreaterThan(0);
        expect(metrics.interactionLatency).toBeGreaterThan(0);
        expect(metrics.memoryUsage).toBeDefined();
      }
    }, 10000);
  });

  describe('Performance Test Suite Integration', () => {
    it('should run comprehensive performance test suite', async () => {
      // Run a subset of tests for integration validation
      const testSubset = HIGH_FREQUENCY_TRADING_TESTS.slice(0, 3); // First 3 tests

      const results = await runPerformanceTestSuite(<MockHighFrequencyTradingDashboard />, testSubset);

      expect(results).toHaveLength(3);

      results.forEach(result => {
        expect(result).toHaveProperty('testId');
        expect(result).toHaveProperty('renderTime');
        expect(result).toHaveProperty('interactionLatency');
        expect(result).toHaveProperty('memoryUsage');
        expect(result).toHaveProperty('passed');
        expect(result).toHaveProperty('violations');
        expect(result).toHaveProperty('recommendations');
        expect(result).toHaveProperty('timestamp');

        expect(typeof result.passed).toBe('boolean');
        expect(Array.isArray(result.violations)).toBe(true);
        expect(Array.isArray(result.recommendations)).toBe(true);
      });
    }, 30000); // Allow 30 seconds for full suite

    it('should generate comprehensive performance report', async () => {
      const testSubset = HIGH_FREQUENCY_TRADING_TESTS.slice(0, 2);
      const results = await runPerformanceTestSuite(<MockHighFrequencyTradingDashboard />, testSubset);

      const report = generatePerformanceReport(results);

      expect(report).toContain('High-Frequency Trading Performance Report');
      expect(report).toContain('Summary');
      expect(report).toContain('Tests Run');
      expect(report).toContain('Performance Metrics Overview');
      expect(report).toContain('Critical Performance Thresholds');
      expect(report).toContain('Production Readiness');

      console.log('\n=== PERFORMANCE TEST REPORT ===\n' + report.substring(0, 2000) + '...\n');
    }, 20000);
  });

  describe('Performance Validation Scenarios', () => {
    it('should validate critical trading performance thresholds', () => {
      const criticalTest = HIGH_FREQUENCY_TRADING_TESTS.find(t => t.priority === 'critical');

      expect(criticalTest).toBeDefined();
      if (criticalTest) {
        // Validate that critical tests have appropriate thresholds for HFT
        expect(criticalTest.targets.maxRenderTime).toBeLessThanOrEqual(100); // 100ms max for critical rendering
        expect(criticalTest.targets.maxInteractionLatency).toBeLessThanOrEqual(200); // 200ms max for critical interactions
        expect(criticalTest.targets.maxMemoryIncrease).toBeLessThanOrEqual(20); // 20MB max for critical operations
      }
    });

    it('should validate market data performance requirements', () => {
      const marketDataTest = HIGH_FREQUENCY_TRADING_TESTS.find(t => t.scenario === 'market_data');

      expect(marketDataTest).toBeDefined();
      if (marketDataTest) {
        // Market data updates should be extremely fast
        expect(marketDataTest.targets.maxRenderTime).toBeLessThanOrEqual(50);
        expect(marketDataTest.targets.maxWebsocketLatency).toBeLessThanOrEqual(50);
      }
    });

    it('should validate order execution performance requirements', () => {
      const orderTest = HIGH_FREQUENCY_TRADING_TESTS.find(t => t.scenario === 'order_execution');

      expect(orderTest).toBeDefined();
      if (orderTest) {
        // Order execution should be fast and responsive
        expect(orderTest.targets.maxInteractionLatency).toBeLessThanOrEqual(100);
        expect(orderTest.targets.maxMemoryIncrease).toBeLessThanOrEqual(10);
      }
    });

    it('should validate chart rendering performance requirements', () => {
      const chartTest = HIGH_FREQUENCY_TRADING_TESTS.find(t => t.scenario === 'chart_rendering');

      expect(chartTest).toBeDefined();
      if (chartTest) {
        // Charts can have higher rendering time but should maintain good interaction
        expect(chartTest.targets.maxRenderTime).toBeLessThanOrEqual(300);
        expect(chartTest.targets.minFPS).toBeGreaterThanOrEqual(30);
      }
    });
  });

  describe('Component Performance Validation', () => {
    it('should have performant market data grid structure', () => {
      render(<MockHighFrequencyTradingDashboard />);

      // Verify that we have market data elements for performance testing
      const marketGrid = screen.getByRole('grid', { name: /real-time market prices/i });
      expect(marketGrid).toBeInTheDocument();

      // Check that we have multiple currency pairs for performance stress testing
      const eurUsdRow = screen.getByTestId('market-EURUSD');
      const gbpUsdRow = screen.getByTestId('market-GBPUSD');
      expect(eurUsdRow).toBeInTheDocument();
      expect(gbpUsdRow).toBeInTheDocument();
    });

    it('should have performant position table structure', () => {
      render(<MockHighFrequencyTradingDashboard />);

      // Verify positions table exists
      const positionsTable = screen.getByRole('table', { name: /current trading positions/i });
      expect(positionsTable).toBeInTheDocument();

      // Check that we have multiple positions for performance testing
      const position0 = screen.getByTestId('position-0');
      const position10 = screen.getByTestId('position-10');
      expect(position0).toBeInTheDocument();
      expect(position10).toBeInTheDocument();

      // Verify P&L elements exist for update performance testing
      const pnl0 = screen.getByTestId('pnl-0');
      expect(pnl0).toBeInTheDocument();
    });

    it('should have performant chart structure', () => {
      render(<MockHighFrequencyTradingDashboard />);

      // Verify chart exists
      const chart = screen.getByRole('application', { name: /high-frequency trading chart/i });
      expect(chart).toBeInTheDocument();
      expect(chart).toHaveAttribute('tabIndex', '0');

      // Check that we have chart points for performance testing
      const chartPoint0 = screen.getByTestId('chart-point-0');
      const chartPoint500 = screen.getByTestId('chart-point-500');
      expect(chartPoint0).toBeInTheDocument();
      expect(chartPoint500).toBeInTheDocument();
    });

    it('should have performant order entry structure', () => {
      render(<MockHighFrequencyTradingDashboard />);

      // Verify order entry form exists
      const orderForm = screen.getByRole('form', { name: /high-frequency order placement/i });
      expect(orderForm).toBeInTheDocument();

      // Check order buttons exist for performance testing
      const buyButton = screen.getByTestId('buy-order-button');
      const sellButton = screen.getByTestId('sell-order-button');
      expect(buyButton).toBeInTheDocument();
      expect(sellButton).toBeInTheDocument();
    });
  });
});
