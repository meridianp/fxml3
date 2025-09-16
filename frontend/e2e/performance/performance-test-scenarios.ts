/**
 * Performance Test Scenarios
 *
 * Comprehensive performance testing scenarios for FXML4 application
 */

import { test, expect } from '@playwright/test';
import { PerformanceMonitor } from './performance-monitor';
import { LoadTester, LoadTestConfig, LoadTestScenario } from './load-testing';
import fs from 'fs/promises';
import path from 'path';

test.describe('FXML4 Performance Test Scenarios', () => {
  test.use({ storageState: 'e2e/.auth/user.json' });

  let performanceMonitor: PerformanceMonitor;
  let loadTester: LoadTester;

  test.beforeAll(async () => {
    performanceMonitor = new PerformanceMonitor();
    loadTester = new LoadTester();

    // Ensure results directory exists
    await fs.mkdir('e2e-results/performance', { recursive: true });
  });

  test('critical user journey performance', async ({ page }) => {
    console.log('🎯 Testing critical user journey performance...');

    // Define critical user journey
    const journeyActions = [
      { name: 'Dashboard Load', action: async () => {
        await page.goto('/dashboard');
        await page.waitForLoadState('networkidle');
      }},
      { name: 'Navigate to Trading', action: async () => {
        await page.click('[data-testid="nav-trading"]');
        await page.waitForLoadState('networkidle');
      }},
      { name: 'Select Symbol', action: async () => {
        if (await page.locator('[data-testid="symbol-selector"]').isVisible()) {
          await page.click('[data-testid="symbol-selector"]');
          await page.click('[data-testid="symbol-option-EURUSD"]');
        }
      }},
      { name: 'View Analytics', action: async () => {
        await page.goto('/dashboard');
        if (await page.locator('[data-testid="analytics-panel"]').isVisible()) {
          await page.click('[data-testid="analytics-panel"]');
        }
      }},
      { name: 'Check Data Quality', action: async () => {
        await page.goto('/data');
        await page.waitForLoadState('networkidle');
      }}
    ];

    // Run performance test
    const metrics = await performanceMonitor.runPerformanceTest(
      page,
      '/dashboard',
      'Critical User Journey',
      {
        interactions: journeyActions,
        viewport: { width: 1920, height: 1080 }
      }
    );

    // Performance assertions
    expect(metrics.pageLoad.loadTime).toBeLessThan(5000); // 5 seconds max
    expect(metrics.memory.increase).toBeLessThan(100 * 1024 * 1024); // 100MB max increase
    expect(metrics.network.failedRequests).toBe(0); // No failed requests

    // Log key metrics
    console.log(`📊 Load time: ${metrics.pageLoad.loadTime}ms`);
    console.log(`🧠 Memory increase: ${(metrics.memory.increase / 1024 / 1024).toFixed(2)}MB`);
    console.log(`🌐 Network requests: ${metrics.network.totalRequests}`);
  });

  test('trading console load performance', async ({ page }) => {
    console.log('📈 Testing trading console load performance...');

    await performanceMonitor.startMonitoring(page, 'Trading Console Load');

    // Navigate to trading console
    await page.goto('/trading');
    await page.waitForLoadState('networkidle');

    // Simulate rapid trading actions
    const tradingActions = [
      async () => {
        if (await page.locator('[data-testid="symbol-selector"]').isVisible()) {
          await page.click('[data-testid="symbol-selector"]');
          await page.click('[data-testid="symbol-option-GBPUSD"]');
        }
      },
      async () => {
        await page.fill('[data-testid="order-size-input"]', '10000');
      },
      async () => {
        await page.click('[data-testid="order-type-market"]');
      },
      async () => {
        await page.click('[data-testid="buy-button"]');
        await page.keyboard.press('Escape'); // Cancel order preview
      }
    ];

    // Measure each trading action
    for (let i = 0; i < tradingActions.length; i++) {
      await performanceMonitor.measureInteraction(
        page,
        `Trading Action ${i + 1}`,
        'trading-element',
        tradingActions[i]
      );
    }

    const metrics = await performanceMonitor.stopMonitoring(page, 'Trading Console Load');

    // Trading-specific performance requirements
    expect(metrics.pageLoad.loadTime).toBeLessThan(3000); // Trading console must load fast
    expect(metrics.runtime.interactions.every(i => i.duration < 500)).toBe(true); // All interactions under 500ms

    console.log(`⚡ Fastest interaction: ${Math.min(...metrics.runtime.interactions.map(i => i.duration)).toFixed(2)}ms`);
    console.log(`🐌 Slowest interaction: ${Math.max(...metrics.runtime.interactions.map(i => i.duration)).toFixed(2)}ms`);
  });

  test('data management dashboard memory usage', async ({ page }) => {
    console.log('🧠 Testing data management memory usage...');

    await performanceMonitor.startMonitoring(page, 'Data Management Memory');

    // Load data management dashboard
    await page.goto('/data');
    await page.waitForLoadState('networkidle');

    // Simulate data-intensive operations
    const dataOperations = [
      async () => {
        // Refresh data multiple times
        for (let i = 0; i < 5; i++) {
          if (await page.locator('[data-testid="refresh-data-button"]').isVisible()) {
            await page.click('[data-testid="refresh-data-button"]');
            await page.waitForLoadState('networkidle');
          }
          await page.waitForTimeout(1000);
        }
      },
      async () => {
        // Switch between different data views
        const tabs = ['[data-testid="data-source-tab"]', '[data-testid="storage-tab"]', '[data-testid="quality-tab"]'];
        for (const tab of tabs) {
          if (await page.locator(tab).isVisible()) {
            await page.click(tab);
            await page.waitForTimeout(1000);
          }
        }
      }
    ];

    for (const operation of dataOperations) {
      await operation();
    }

    const metrics = await performanceMonitor.stopMonitoring(page, 'Data Management Memory');

    // Memory usage should be reasonable
    expect(metrics.memory.leakSuspected).toBe(false);
    expect(metrics.memory.increase).toBeLessThan(50 * 1024 * 1024); // 50MB max for data operations

    console.log(`📊 Initial memory: ${(metrics.memory.initial / 1024 / 1024).toFixed(2)}MB`);
    console.log(`📈 Final memory: ${(metrics.memory.final / 1024 / 1024).toFixed(2)}MB`);
    console.log(`${metrics.memory.leakSuspected ? '⚠️' : '✅'} Memory leak: ${metrics.memory.leakSuspected ? 'Suspected' : 'None detected'}`);
  });

  test('analytics dashboard rendering performance', async ({ page }) => {
    console.log('📊 Testing analytics dashboard rendering performance...');

    await performanceMonitor.startMonitoring(page, 'Analytics Rendering');

    // Load analytics dashboard
    await page.goto('/dashboard');
    await page.waitForLoadState('networkidle');

    // Test chart rendering performance
    const chartOperations = [
      async () => {
        // Switch time ranges
        const timeRanges = ['1d', '7d', '30d'];
        for (const range of timeRanges) {
          const selector = `[data-testid="time-range-${range}"]`;
          if (await page.locator(selector).isVisible()) {
            await page.click(selector);
            await page.waitForSelector('[data-testid="chart-loading"]', { state: 'hidden' });
          }
        }
      },
      async () => {
        // Toggle different analytics panels
        if (await page.locator('[data-testid="analytics-panel"]').isVisible()) {
          await page.click('[data-testid="toggle-panel"]');
          await page.waitForTimeout(500);
          await page.click('[data-testid="toggle-panel"]');
        }
      }
    ];

    for (const operation of chartOperations) {
      await performanceMonitor.measureInteraction(
        page,
        'Chart Operation',
        'chart-element',
        operation
      );
    }

    const metrics = await performanceMonitor.stopMonitoring(page, 'Analytics Rendering');

    // Chart rendering should be smooth
    expect(metrics.runtime.frameRate).toBeGreaterThan(30); // Minimum 30 FPS
    expect(metrics.pageLoad.firstContentfulPaint || 0).toBeLessThan(2000); // FCP under 2s

    console.log(`🎞️  Frame rate: ${metrics.runtime.frameRate} FPS`);
    console.log(`🎨 First Contentful Paint: ${metrics.pageLoad.firstContentfulPaint || 'N/A'}ms`);
  });

  test('ml training interface responsiveness', async ({ page }) => {
    console.log('🤖 Testing ML training interface responsiveness...');

    await performanceMonitor.startMonitoring(page, 'ML Training Interface');

    // Navigate to training interface
    await page.goto('/training');
    await page.waitForLoadState('networkidle');

    // Test model configuration performance
    const mlOperations = [
      async () => {
        // Model type selection
        if (await page.locator('[data-testid="model-type-selector"]').isVisible()) {
          await page.click('[data-testid="model-type-selector"]');
          await page.click('[data-testid="model-type-lstm"]');
        }
      },
      async () => {
        // Parameter adjustments
        const parameters = [
          { selector: '[data-testid="learning-rate-input"]', value: '0.001' },
          { selector: '[data-testid="batch-size-input"]', value: '32' },
          { selector: '[data-testid="epochs-input"]', value: '10' }
        ];

        for (const param of parameters) {
          if (await page.locator(param.selector).isVisible()) {
            await page.fill(param.selector, param.value);
          }
        }
      },
      async () => {
        // Dataset operations
        if (await page.locator('[data-testid="dataset-manager"]').isVisible()) {
          await page.click('[data-testid="dataset-manager"]');
          await page.waitForTimeout(500);
        }
      }
    ];

    for (const operation of mlOperations) {
      await performanceMonitor.measureInteraction(
        page,
        'ML Configuration',
        'ml-element',
        operation
      );
    }

    const metrics = await performanceMonitor.stopMonitoring(page, 'ML Training Interface');

    // ML interface should be responsive
    expect(metrics.runtime.interactions.every(i => i.duration < 1000)).toBe(true); // All interactions under 1s
    expect(metrics.pageLoad.loadTime).toBeLessThan(4000); // Initial load under 4s

    console.log(`⚡ Average interaction time: ${(metrics.runtime.interactions.reduce((sum, i) => sum + i.duration, 0) / metrics.runtime.interactions.length).toFixed(2)}ms`);
  });

  test('cross-browser performance comparison', async ({ page, browserName }) => {
    console.log(`🌐 Testing performance on ${browserName}...`);

    const scenarios = [
      { url: '/dashboard', name: 'Dashboard' },
      { url: '/trading', name: 'Trading' },
      { url: '/data', name: 'Data Management' }
    ];

    const browserResults: any[] = [];

    for (const scenario of scenarios) {
      const metrics = await performanceMonitor.runPerformanceTest(
        page,
        scenario.url,
        `${scenario.name} - ${browserName}`
      );

      browserResults.push({
        browser: browserName,
        scenario: scenario.name,
        loadTime: metrics.pageLoad.loadTime,
        memoryIncrease: metrics.memory.increase,
        networkRequests: metrics.network.totalRequests
      });

      // Browser-agnostic performance requirements
      expect(metrics.pageLoad.loadTime).toBeLessThan(6000); // 6s max (more lenient for cross-browser)
      expect(metrics.network.failedRequests).toBe(0);
    }

    // Save browser-specific results
    const resultsPath = path.join('e2e-results/performance', `${browserName}-results.json`);
    await fs.writeFile(resultsPath, JSON.stringify(browserResults, null, 2));

    console.log(`💾 ${browserName} results saved to: ${resultsPath}`);
  });

  test('mobile performance optimization', async ({ page }) => {
    console.log('📱 Testing mobile performance...');

    // Set mobile viewport
    await page.setViewportSize({ width: 375, height: 667 });

    // Test mobile-specific performance
    const mobileMetrics = await performanceMonitor.runPerformanceTest(
      page,
      '/dashboard',
      'Mobile Dashboard',
      {
        viewport: { width: 375, height: 667 },
        networkCondition: 'fast3g',
        interactions: [
          { name: 'Mobile Navigation', action: async () => {
            if (await page.locator('[data-testid="mobile-menu-button"]').isVisible()) {
              await page.click('[data-testid="mobile-menu-button"]');
              await page.click('[data-testid="mobile-menu-button"]'); // Close
            }
          }}
        ]
      }
    );

    // Mobile performance should account for slower networks
    expect(mobileMetrics.pageLoad.loadTime).toBeLessThan(8000); // 8s on 3G
    expect(mobileMetrics.resources.totalSize).toBeLessThan(2 * 1024 * 1024); // 2MB max

    console.log(`📱 Mobile load time: ${mobileMetrics.pageLoad.loadTime}ms`);
    console.log(`📦 Total bundle size: ${(mobileMetrics.resources.totalSize / 1024).toFixed(2)}KB`);
  });

  test('performance regression detection', async ({ page }) => {
    console.log('🔍 Running performance regression detection...');

    // Define baseline performance expectations
    const baselineMetrics = {
      dashboardLoadTime: 3000,
      tradingLoadTime: 2500,
      dataLoadTime: 3500,
      maxMemoryIncrease: 30 * 1024 * 1024 // 30MB
    };

    const regressionResults: any[] = [];

    // Test key pages against baseline
    const pages = [
      { url: '/dashboard', name: 'Dashboard', baseline: baselineMetrics.dashboardLoadTime },
      { url: '/trading', name: 'Trading', baseline: baselineMetrics.tradingLoadTime },
      { url: '/data', name: 'Data', baseline: baselineMetrics.dataLoadTime }
    ];

    for (const testPage of pages) {
      const metrics = await performanceMonitor.runPerformanceTest(
        page,
        testPage.url,
        `Regression Test - ${testPage.name}`
      );

      const regression = {
        page: testPage.name,
        currentLoadTime: metrics.pageLoad.loadTime,
        baselineLoadTime: testPage.baseline,
        regressionPercentage: ((metrics.pageLoad.loadTime - testPage.baseline) / testPage.baseline) * 100,
        memoryIncrease: metrics.memory.increase,
        hasRegression: metrics.pageLoad.loadTime > testPage.baseline * 1.2 // 20% tolerance
      };

      regressionResults.push(regression);

      // Log regression status
      if (regression.hasRegression) {
        console.log(`⚠️ Performance regression detected in ${testPage.name}: ${regression.regressionPercentage.toFixed(1)}%`);
      } else {
        console.log(`✅ ${testPage.name} performance within baseline`);
      }
    }

    // Save regression analysis
    const regressionReport = {
      timestamp: new Date().toISOString(),
      baseline: baselineMetrics,
      results: regressionResults,
      hasAnyRegression: regressionResults.some(r => r.hasRegression)
    };

    await fs.writeFile(
      'e2e-results/performance/regression-report.json',
      JSON.stringify(regressionReport, null, 2)
    );

    // Fail test if significant regression detected
    expect(regressionResults.filter(r => r.hasRegression).length).toBeLessThanOrEqual(1);
  });

  test.afterAll(async () => {
    // Generate comprehensive performance report
    console.log('📄 Generating comprehensive performance report...');

    try {
      await performanceMonitor.generateReport('e2e-results/performance');
      console.log('✅ Performance report generated successfully');
    } catch (error) {
      console.error('❌ Failed to generate performance report:', error);
    }
  });
});
