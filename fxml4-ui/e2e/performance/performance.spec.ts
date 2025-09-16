/**
 * Performance E2E Tests
 *
 * Performance benchmarking and monitoring for critical user journeys
 */

import { test, expect } from '@playwright/test';

test.describe('Performance Benchmarks', () => {
  test.use({ storageState: 'e2e/.auth/user.json' });

  test('page load performance benchmarks', async ({ page }) => {
    const pages = [
      { url: '/dashboard', name: 'Dashboard' },
      { url: '/trading', name: 'Trading Console' },
      { url: '/data', name: 'Data Management' },
      { url: '/training', name: 'ML Training' },
    ];

    for (const pageInfo of pages) {
      console.log(`\n📊 Testing ${pageInfo.name} performance...`);

      // Start performance measurement
      const startTime = Date.now();

      // Navigate to page
      await page.goto(pageInfo.url);

      // Wait for page to be fully loaded
      await page.waitForLoadState('networkidle');

      const loadTime = Date.now() - startTime;

      // Performance assertions
      expect(loadTime).toBeLessThan(5000); // Page should load within 5 seconds

      // Measure First Contentful Paint
      const fcpMetric = await page.evaluate(() => {
        return new Promise((resolve) => {
          new PerformanceObserver((list) => {
            const entries = list.getEntries();
            const fcpEntry = entries.find(entry => entry.name === 'first-contentful-paint');
            if (fcpEntry) {
              resolve(fcpEntry.startTime);
            }
          }).observe({ entryTypes: ['paint'] });
        });
      });

      if (fcpMetric) {
        expect(fcpMetric).toBeLessThan(2000); // FCP should be under 2 seconds
        console.log(`✅ ${pageInfo.name} - Load Time: ${loadTime}ms, FCP: ${fcpMetric}ms`);
      }

      // Test core interaction responsiveness
      const interactionStart = Date.now();

      // Simulate user interaction based on page
      if (pageInfo.url === '/trading') {
        await page.click('[data-testid="symbol-selector"]');
      } else if (pageInfo.url === '/data') {
        await page.click('[data-testid="refresh-data-button"]');
      } else if (pageInfo.url === '/dashboard') {
        await page.click('[data-testid="analytics-panel"]');
      }

      const interactionTime = Date.now() - interactionStart;
      expect(interactionTime).toBeLessThan(1000); // Interactions should respond within 1 second

      console.log(`⚡ ${pageInfo.name} - Interaction Time: ${interactionTime}ms`);
    }
  });

  test('trading console performance under load', async ({ page }) => {
    await page.goto('/trading');
    await page.waitForLoadState('networkidle');

    console.log('\n📈 Testing trading console performance under simulated load...');

    // Measure rapid symbol switching performance
    const symbols = ['EURUSD', 'GBPUSD', 'USDJPY', 'USDCHF'];
    const switchTimes: number[] = [];

    for (const symbol of symbols) {
      const startTime = Date.now();

      if (await page.locator('[data-testid="symbol-selector"]').isVisible()) {
        await page.click('[data-testid="symbol-selector"]');
        await page.click(`[data-testid="symbol-option-${symbol}"]`);

        // Wait for price data to load
        await page.waitForSelector('[data-testid="current-price"]');
      }

      const switchTime = Date.now() - startTime;
      switchTimes.push(switchTime);

      // Each symbol switch should be fast
      expect(switchTime).toBeLessThan(2000);
    }

    const avgSwitchTime = switchTimes.reduce((a, b) => a + b, 0) / switchTimes.length;
    console.log(`⚡ Average symbol switch time: ${avgSwitchTime.toFixed(2)}ms`);

    // Test rapid order entry performance
    const orderTimes: number[] = [];

    for (let i = 0; i < 5; i++) {
      const startTime = Date.now();

      // Fill order form rapidly
      await page.fill('[data-testid="order-size-input"]', '1000');
      await page.click('[data-testid="buy-button"]');

      // Wait for order preview
      await page.waitForSelector('[data-testid="order-preview"]');

      const orderTime = Date.now() - startTime;
      orderTimes.push(orderTime);

      // Cancel order
      await page.keyboard.press('Escape');

      // Order form should respond quickly
      expect(orderTime).toBeLessThan(1500);
    }

    const avgOrderTime = orderTimes.reduce((a, b) => a + b, 0) / orderTimes.length;
    console.log(`💨 Average order entry time: ${avgOrderTime.toFixed(2)}ms`);
  });

  test('data management dashboard memory usage', async ({ page }) => {
    await page.goto('/data');
    await page.waitForLoadState('networkidle');

    console.log('\n🧠 Testing data management memory usage...');

    // Get initial memory usage
    const initialMemory = await page.evaluate(() => {
      return (performance as any).memory ? (performance as any).memory.usedJSHeapSize : 0;
    });

    // Simulate heavy data operations
    for (let i = 0; i < 10; i++) {
      // Refresh data multiple times
      if (await page.locator('[data-testid="refresh-data-button"]').isVisible()) {
        await page.click('[data-testid="refresh-data-button"]');
        await page.waitForLoadState('networkidle');
      }

      // Switch between dashboard sections
      if (await page.locator('[data-testid="data-quality-tab"]').isVisible()) {
        await page.click('[data-testid="data-quality-tab"]');
        await page.waitForTimeout(500);
      }

      if (await page.locator('[data-testid="storage-tab"]').isVisible()) {
        await page.click('[data-testid="storage-tab"]');
        await page.waitForTimeout(500);
      }
    }

    // Get final memory usage
    const finalMemory = await page.evaluate(() => {
      return (performance as any).memory ? (performance as any).memory.usedJSHeapSize : 0;
    });

    if (initialMemory && finalMemory) {
      const memoryIncrease = finalMemory - initialMemory;
      const memoryIncreasePercentage = (memoryIncrease / initialMemory) * 100;

      console.log(`💾 Memory usage: ${(initialMemory / 1024 / 1024).toFixed(2)}MB → ${(finalMemory / 1024 / 1024).toFixed(2)}MB`);
      console.log(`📈 Memory increase: ${memoryIncreasePercentage.toFixed(1)}%`);

      // Memory increase should be reasonable (less than 100% increase)
      expect(memoryIncreasePercentage).toBeLessThan(100);
    }
  });

  test('analytics dashboard rendering performance', async ({ page }) => {
    await page.goto('/dashboard');
    await page.waitForLoadState('networkidle');

    console.log('\n📊 Testing analytics dashboard rendering performance...');

    // Measure chart rendering time
    if (await page.locator('[data-testid="analytics-dashboard"]').isVisible()) {
      const chartRenderStart = Date.now();

      // Trigger chart updates
      if (await page.locator('[data-testid="time-range-selector"]').isVisible()) {
        await page.selectOption('[data-testid="time-range-selector"]', '7d');

        // Wait for charts to re-render
        await page.waitForSelector('[data-testid="chart-loading"]', { state: 'hidden' });
      }

      const chartRenderTime = Date.now() - chartRenderStart;
      console.log(`📈 Chart rendering time: ${chartRenderTime}ms`);

      // Chart rendering should be fast
      expect(chartRenderTime).toBeLessThan(3000);
    }

    // Test real-time update performance
    const updateTimes: number[] = [];

    for (let i = 0; i < 5; i++) {
      const updateStart = Date.now();

      // Trigger analytics refresh
      if (await page.locator('[data-testid="refresh-analytics"]').isVisible()) {
        await page.click('[data-testid="refresh-analytics"]');
        await page.waitForSelector('[data-testid="analytics-loading"]', { state: 'hidden' });
      }

      const updateTime = Date.now() - updateStart;
      updateTimes.push(updateTime);

      // Each update should be reasonably fast
      expect(updateTime).toBeLessThan(5000);
    }

    const avgUpdateTime = updateTimes.reduce((a, b) => a + b, 0) / updateTimes.length;
    console.log(`🔄 Average analytics update time: ${avgUpdateTime.toFixed(2)}ms`);
  });

  test('ml training interface responsiveness', async ({ page }) => {
    await page.goto('/training');
    await page.waitForLoadState('networkidle');

    console.log('\n🤖 Testing ML training interface responsiveness...');

    // Test dataset loading performance
    if (await page.locator('[data-testid="dataset-manager"]').isVisible()) {
      const datasetLoadStart = Date.now();

      // Load dataset list
      if (await page.locator('[data-testid="refresh-datasets"]').isVisible()) {
        await page.click('[data-testid="refresh-datasets"]');
        await page.waitForSelector('[data-testid="dataset-loading"]', { state: 'hidden' });
      }

      const datasetLoadTime = Date.now() - datasetLoadStart;
      console.log(`📂 Dataset loading time: ${datasetLoadTime}ms`);

      expect(datasetLoadTime).toBeLessThan(3000);
    }

    // Test model configuration responsiveness
    const configTimes: number[] = [];

    for (let i = 0; i < 3; i++) {
      const configStart = Date.now();

      // Change model parameters
      if (await page.locator('[data-testid="learning-rate-input"]').isVisible()) {
        await page.fill('[data-testid="learning-rate-input"]', `0.00${i + 1}`);
      }

      if (await page.locator('[data-testid="batch-size-input"]').isVisible()) {
        await page.fill('[data-testid="batch-size-input"]', `${32 * (i + 1)}`);
      }

      // Wait for configuration validation
      await page.waitForTimeout(500);

      const configTime = Date.now() - configStart;
      configTimes.push(configTime);
    }

    const avgConfigTime = configTimes.reduce((a, b) => a + b, 0) / configTimes.length;
    console.log(`⚙️ Average configuration time: ${avgConfigTime.toFixed(2)}ms`);
  });

  test('bundle size and resource optimization', async ({ page }) => {
    console.log('\n📦 Analyzing bundle size and resource optimization...');

    // Navigate to main application
    await page.goto('/');

    // Analyze network resources
    const resources = await page.evaluate(() => {
      const entries = performance.getEntriesByType('resource') as PerformanceResourceTiming[];

      const jsResources = entries.filter(entry => entry.name.endsWith('.js'));
      const cssResources = entries.filter(entry => entry.name.endsWith('.css'));
      const imageResources = entries.filter(entry =>
        entry.name.match(/\.(png|jpg|jpeg|gif|svg|webp)$/i)
      );

      const totalJSSize = jsResources.reduce((total, resource) =>
        total + (resource.transferSize || 0), 0
      );

      const totalCSSSize = cssResources.reduce((total, resource) =>
        total + (resource.transferSize || 0), 0
      );

      const totalImageSize = imageResources.reduce((total, resource) =>
        total + (resource.transferSize || 0), 0
      );

      return {
        jsCount: jsResources.length,
        cssCount: cssResources.length,
        imageCount: imageResources.length,
        totalJSSize,
        totalCSSSize,
        totalImageSize,
        totalSize: totalJSSize + totalCSSSize + totalImageSize
      };
    });

    console.log(`📊 Resource Analysis:`);
    console.log(`   JS Files: ${resources.jsCount} (${(resources.totalJSSize / 1024).toFixed(2)} KB)`);
    console.log(`   CSS Files: ${resources.cssCount} (${(resources.totalCSSSize / 1024).toFixed(2)} KB)`);
    console.log(`   Images: ${resources.imageCount} (${(resources.totalImageSize / 1024).toFixed(2)} KB)`);
    console.log(`   Total: ${(resources.totalSize / 1024).toFixed(2)} KB`);

    // Bundle size should be reasonable (under 2MB for initial load)
    expect(resources.totalSize).toBeLessThan(2 * 1024 * 1024);

    // JS bundle shouldn't be too large
    expect(resources.totalJSSize).toBeLessThan(1 * 1024 * 1024);
  });

  test('websocket connection performance', async ({ page }) => {
    await page.goto('/data');
    await page.waitForLoadState('networkidle');

    console.log('\n🔌 Testing WebSocket connection performance...');

    // Monitor WebSocket connection
    const wsMessages: any[] = [];

    page.on('websocket', ws => {
      ws.on('framereceived', event => {
        wsMessages.push({
          timestamp: Date.now(),
          payload: event.payload
        });
      });
    });

    // Wait for WebSocket messages
    await page.waitForTimeout(10000);

    if (wsMessages.length > 0) {
      console.log(`📡 Received ${wsMessages.length} WebSocket messages`);

      // Calculate message frequency
      const messageFrequency = wsMessages.length / 10; // messages per second
      console.log(`📊 Message frequency: ${messageFrequency.toFixed(2)} messages/second`);

      // WebSocket should not be too chatty (reasonable update frequency)
      expect(messageFrequency).toBeLessThan(10);
      expect(messageFrequency).toBeGreaterThan(0.1);
    }
  });
});
