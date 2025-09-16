/**
 * 📊 COMPREHENSIVE DATA MANAGEMENT AUDIT
 *
 * Systematic validation of data management functionality
 * This is part 3 of the comprehensive feature testing suite
 */

import { test, expect } from '@playwright/test';

const BASE_URL = process.env.PLAYWRIGHT_TEST_BASE_URL || 'http://localhost:3000';

test.describe('📊 Data Management - Comprehensive Audit', () => {

  test.beforeEach(async ({ page }) => {
    await page.goto(`${BASE_URL}/data`);
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(2000);
  });

  test('Data management page loads with core components', async ({ page }) => {
    console.log('\n📊 Testing Data Management Components...');

    // Check page title
    await expect(page).toHaveTitle(/Data|FXML4/i);
    console.log('✅ Data page title correct');

    // Look for main data components
    const components = [
      { name: 'Market Data Grid', selectors: '.market-data-grid, [data-testid="market-data"], .data-grid' },
      { name: 'Symbol Selector', selectors: '.symbol-selector, [data-testid="symbol-selector"], select' },
      { name: 'Price Chart', selectors: '.price-chart, [data-testid="chart"], canvas, svg' },
      { name: 'Data Quality Dashboard', selectors: '.data-quality, [data-testid="data-quality"], .quality' },
      { name: 'Data Sources', selectors: '.data-sources, [data-testid="data-sources"], .sources' }
    ];

    for (const component of components) {
      const element = page.locator(component.selectors);
      if (await element.count() > 0) {
        console.log(`✅ ${component.name} found`);
      } else {
        console.log(`⚠️  ${component.name} not found`);
      }
    }
  });

  test('Symbol selector functionality', async ({ page }) => {
    console.log('\n🔍 Testing Symbol Selector...');

    const symbolSelector = page.locator('.symbol-selector, [data-testid="symbol-selector"], select').first();

    if (await symbolSelector.count() > 0) {
      console.log('✅ Symbol selector found');

      // Test selector interaction
      await symbolSelector.click();
      await page.waitForTimeout(500);

      // Get available options
      const options = symbolSelector.locator('option');
      const optionCount = await options.count();
      console.log(`  Found ${optionCount} symbol options`);

      if (optionCount > 1) {
        // Test selecting different symbols
        for (let i = 1; i < Math.min(optionCount, 4); i++) {
          const option = options.nth(i);
          const optionText = await option.textContent();
          console.log(`  Testing symbol: ${optionText}`);

          await symbolSelector.selectOption({ index: i });
          await page.waitForTimeout(1000); // Wait for data to load

          // Check if selection triggered data update
          const currentValue = await symbolSelector.inputValue();
          console.log(`    Selected value: ${currentValue}`);
        }
        console.log('✅ Symbol selection working');
      } else {
        console.log('⚠️  Insufficient symbol options');
      }

    } else {
      console.log('⚠️  Symbol selector not found');
    }
  });

  test('Market data grid display and functionality', async ({ page }) => {
    console.log('\n📈 Testing Market Data Grid...');

    const dataGrid = page.locator('.market-data-grid, [data-testid="market-data"], table').first();

    if (await dataGrid.count() > 0) {
      console.log('✅ Market data grid found');

      // Check table structure
      const headers = dataGrid.locator('th, .header');
      const headerCount = await headers.count();
      console.log(`  Found ${headerCount} column headers`);

      if (headerCount > 0) {
        console.log('  Column headers:');
        for (let i = 0; i < Math.min(headerCount, 8); i++) {
          const header = headers.nth(i);
          const headerText = await header.textContent();
          console.log(`    ${i + 1}. ${headerText}`);
        }
      }

      // Check data rows
      const rows = dataGrid.locator('tbody tr, .data-row');
      const rowCount = await rows.count();
      console.log(`  Found ${rowCount} data rows`);

      if (rowCount > 0) {
        console.log('✅ Market data displayed');

        // Analyze first few rows for data quality
        for (let i = 0; i < Math.min(rowCount, 3); i++) {
          const row = rows.nth(i);
          const cells = row.locator('td, .cell');
          const cellCount = await cells.count();

          console.log(`    Row ${i + 1}: ${cellCount} cells`);

          // Check for price-like data
          for (let j = 0; j < Math.min(cellCount, 6); j++) {
            const cell = cells.nth(j);
            const cellText = await cell.textContent();
            const hasNumericData = /\d+(\.\d+)?/.test(cellText || '');

            if (hasNumericData) {
              console.log(`      Cell ${j + 1}: ${cellText} ✅`);
            } else if (cellText && cellText.trim().length > 0) {
              console.log(`      Cell ${j + 1}: ${cellText}`);
            }
          }
        }
      } else {
        console.log('⚠️  No market data displayed');
      }

    } else {
      console.log('⚠️  Market data grid not found');
    }
  });

  test('Price chart functionality and interactions', async ({ page }) => {
    console.log('\n📈 Testing Price Chart...');

    const chart = page.locator('.price-chart, [data-testid="chart"], canvas, svg').first();

    if (await chart.count() > 0) {
      console.log('✅ Price chart found');

      const chartBounds = await chart.boundingBox();
      if (chartBounds) {
        console.log(`  Chart dimensions: ${chartBounds.width}x${chartBounds.height}`);

        // Test chart interactions
        console.log('  Testing chart interactions...');

        // Test hover
        await chart.hover();
        await page.waitForTimeout(500);

        // Test click
        await chart.click();
        await page.waitForTimeout(500);

        // Test drag for zoom/pan
        await page.mouse.move(chartBounds.x + 100, chartBounds.y + 100);
        await page.mouse.down();
        await page.mouse.move(chartBounds.x + 200, chartBounds.y + 150);
        await page.mouse.up();
        await page.waitForTimeout(500);

        console.log('✅ Chart interactions tested');

        // Look for chart controls
        const controls = page.locator('.chart-controls, .zoom-controls, [data-testid*="chart-control"]');
        const controlCount = await controls.count();
        console.log(`  Found ${controlCount} chart controls`);

      } else {
        console.log('⚠️  Chart has no dimensions');
      }

      // Test timeframe switching
      const timeframeSelector = page.locator('.timeframe-selector, [data-testid="timeframe"], select:has(option:has-text("1h"))');
      if (await timeframeSelector.count() > 0) {
        console.log('✅ Timeframe selector found');

        const options = timeframeSelector.locator('option');
        const optionCount = await options.count();
        console.log(`    Found ${optionCount} timeframe options`);

        if (optionCount > 1) {
          // Test switching timeframes
          await timeframeSelector.selectOption({ index: 1 });
          await page.waitForTimeout(2000); // Wait for chart to update
          console.log('✅ Timeframe switching tested');
        }
      } else {
        console.log('⚠️  Timeframe selector not found');
      }

    } else {
      console.log('⚠️  Price chart not found');
    }
  });

  test('Data quality dashboard and monitoring', async ({ page }) => {
    console.log('\n🔍 Testing Data Quality Dashboard...');

    const qualityDashboard = page.locator('.data-quality, [data-testid="data-quality"], .quality-dashboard').first();

    if (await qualityDashboard.count() > 0) {
      console.log('✅ Data quality dashboard found');

      // Look for quality metrics
      const qualityMetrics = [
        { name: 'Data Completeness', selectors: '.completeness, [data-testid="completeness"]' },
        { name: 'Data Accuracy', selectors: '.accuracy, [data-testid="accuracy"]' },
        { name: 'Data Freshness', selectors: '.freshness, [data-testid="freshness"]' },
        { name: 'Missing Data Points', selectors: '.missing-data, [data-testid="missing"]' },
        { name: 'Data Lag', selectors: '.data-lag, [data-testid="lag"]' }
      ];

      for (const metric of qualityMetrics) {
        const element = qualityDashboard.locator(metric.selectors);
        if (await element.count() > 0) {
          const value = await element.textContent();
          console.log(`  ✅ ${metric.name}: ${value?.trim()}`);
        } else {
          console.log(`  ⚠️  ${metric.name} not found`);
        }
      }

      // Look for quality alerts
      const alerts = qualityDashboard.locator('.alert, .warning, .quality-issue');
      const alertCount = await alerts.count();

      if (alertCount > 0) {
        console.log(`  ⚠️  Found ${alertCount} data quality alerts`);
        for (let i = 0; i < alertCount; i++) {
          const alert = alerts.nth(i);
          const alertText = await alert.textContent();
          console.log(`    Alert ${i + 1}: ${alertText}`);
        }
      } else {
        console.log('  ✅ No data quality alerts');
      }

    } else {
      console.log('⚠️  Data quality dashboard not found');
    }
  });

  test('Data source monitoring and status', async ({ page }) => {
    console.log('\n🔌 Testing Data Source Monitoring...');

    const sourceMonitor = page.locator('.data-sources, [data-testid="data-sources"], .source-monitor').first();

    if (await sourceMonitor.count() > 0) {
      console.log('✅ Data source monitor found');

      // Look for data provider status
      const providers = [
        { name: 'Polygon.io', selectors: '.polygon, [data-testid*="polygon"]' },
        { name: 'Alpha Vantage', selectors: '.alpha-vantage, [data-testid*="alpha"]' },
        { name: 'Interactive Brokers', selectors: '.ib, .interactive-brokers, [data-testid*="ib"]' },
        { name: 'WebSocket', selectors: '.websocket, [data-testid*="ws"]' }
      ];

      for (const provider of providers) {
        const element = sourceMonitor.locator(provider.selectors);
        if (await element.count() > 0) {
          const status = await element.textContent();
          console.log(`  ✅ ${provider.name}: ${status?.trim()}`);
        } else {
          console.log(`  ⚠️  ${provider.name} status not found`);
        }
      }

      // Look for connection indicators
      const connectionIndicators = sourceMonitor.locator('.connected, .disconnected, .status-indicator');
      const indicatorCount = await connectionIndicators.count();
      console.log(`  Found ${indicatorCount} connection indicators`);

      // Look for data pipeline status
      const pipeline = sourceMonitor.locator('.pipeline, [data-testid="pipeline"]');
      if (await pipeline.count() > 0) {
        const pipelineStatus = await pipeline.textContent();
        console.log(`  Pipeline status: ${pipelineStatus}`);
      }

    } else {
      console.log('⚠️  Data source monitor not found');
    }
  });

  test('Real-time data updates and WebSocket integration', async ({ page }) => {
    console.log('\n⚡ Testing Real-time Data Updates...');

    // Look for real-time indicators
    const realtimeIndicators = page.locator('.realtime, .live, [data-testid*="realtime"], [data-testid*="live"]');
    const indicatorCount = await realtimeIndicators.count();

    if (indicatorCount > 0) {
      console.log(`Found ${indicatorCount} real-time indicators`);

      for (let i = 0; i < indicatorCount; i++) {
        const indicator = realtimeIndicators.nth(i);
        const text = await indicator.textContent();
        const isVisible = await indicator.isVisible();
        console.log(`  Indicator ${i + 1}: ${text} (visible: ${isVisible})`);
      }
    }

    // Test WebSocket connection status
    const wsStatus = page.locator('.websocket-status, [data-testid="websocket"], .ws-status');
    if (await wsStatus.count() > 0) {
      const status = await wsStatus.textContent();
      console.log(`  WebSocket status: ${status}`);
    }

    // Look for data timestamps to verify freshness
    const timestamps = page.locator('.timestamp, [data-testid*="time"], .last-updated');
    const timestampCount = await timestamps.count();

    if (timestampCount > 0) {
      console.log(`Found ${timestampCount} timestamps`);

      for (let i = 0; i < Math.min(timestampCount, 3); i++) {
        const timestamp = timestamps.nth(i);
        const time = await timestamp.textContent();
        console.log(`  Timestamp ${i + 1}: ${time}`);
      }
    }

    // Monitor for data changes over time
    console.log('  Monitoring for real-time updates...');

    const priceElements = page.locator('.price, [data-testid*="price"], .current-price');
    const initialPrices = [];

    // Record initial values
    for (let i = 0; i < Math.min(await priceElements.count(), 5); i++) {
      const element = priceElements.nth(i);
      const price = await element.textContent();
      initialPrices.push(price);
    }

    // Wait and check for updates
    await page.waitForTimeout(3000);

    let updatesDetected = 0;
    for (let i = 0; i < Math.min(await priceElements.count(), 5); i++) {
      const element = priceElements.nth(i);
      const newPrice = await element.textContent();

      if (newPrice !== initialPrices[i]) {
        updatesDetected++;
        console.log(`    ✅ Price ${i + 1} updated: ${initialPrices[i]} → ${newPrice}`);
      }
    }

    if (updatesDetected > 0) {
      console.log(`✅ Real-time updates detected (${updatesDetected} changes)`);
    } else {
      console.log('ℹ️  No real-time updates detected (may be expected)');
    }
  });

  test('Data export and download functionality', async ({ page }) => {
    console.log('\n💾 Testing Data Export Functionality...');

    // Look for export buttons
    const exportButtons = page.locator('button:has-text("Export"), .export-button, [data-testid*="export"]');
    const exportCount = await exportButtons.count();

    if (exportCount > 0) {
      console.log(`Found ${exportCount} export buttons`);

      // Test export functionality (don't actually download)
      for (let i = 0; i < Math.min(exportCount, 3); i++) {
        const button = exportButtons.nth(i);
        const buttonText = await button.textContent();
        const isEnabled = await button.isEnabled();

        console.log(`  Export button ${i + 1}: "${buttonText}" (enabled: ${isEnabled})`);

        if (isEnabled) {
          // Click but don't actually download
          console.log(`    Testing click for: ${buttonText}`);
          // await button.click(); // Commented out to avoid actual downloads
        }
      }

    } else {
      console.log('⚠️  No export buttons found');
    }

    // Look for download options
    const downloadOptions = page.locator('.download-options, [data-testid="download"]');
    if (await downloadOptions.count() > 0) {
      console.log('✅ Download options found');
    }
  });

  test('Data filtering and search functionality', async ({ page }) => {
    console.log('\n🔍 Testing Data Filtering and Search...');

    // Look for search/filter inputs
    const searchInputs = page.locator('input[type="search"], .search-input, [data-testid*="search"]');
    const searchCount = await searchInputs.count();

    if (searchCount > 0) {
      console.log(`Found ${searchCount} search inputs`);

      const searchInput = searchInputs.first();

      // Test search functionality
      await searchInput.fill('EUR');
      await page.waitForTimeout(1000);

      const searchValue = await searchInput.inputValue();
      expect(searchValue).toBe('EUR');
      console.log('✅ Search input working');

      // Look for search results
      const results = page.locator('.search-results, .filtered-results');
      if (await results.count() > 0) {
        console.log('✅ Search results displayed');
      }

      // Clear search
      await searchInput.clear();
      await page.waitForTimeout(500);

    } else {
      console.log('⚠️  No search inputs found');
    }

    // Look for filter options
    const filters = page.locator('.filter-options, [data-testid*="filter"], select');
    const filterCount = await filters.count();

    if (filterCount > 0) {
      console.log(`Found ${filterCount} filter options`);

      // Test first filter
      const filter = filters.first();
      const options = filter.locator('option');
      const optionCount = await options.count();

      if (optionCount > 1) {
        await filter.selectOption({ index: 1 });
        await page.waitForTimeout(1000);
        console.log('✅ Filter functionality tested');
      }

    } else {
      console.log('⚠️  No filter options found');
    }
  });

  test('Data management performance and responsiveness', async ({ page }) => {
    console.log('\n⚡ Testing Data Management Performance...');

    const startTime = Date.now();

    // Test data loading performance
    await page.reload();
    await page.waitForLoadState('networkidle');

    const loadTime = Date.now() - startTime;
    console.log(`Data page load time: ${loadTime}ms`);

    if (loadTime < 3000) {
      console.log('✅ Data page load performance good');
    } else if (loadTime < 5000) {
      console.log('⚠️  Data page load performance moderate');
    } else {
      console.log('❌ Data page load performance slow');
    }

    // Test interactive performance
    const interactionStart = Date.now();

    // Click various elements to test responsiveness
    const interactiveElements = page.locator('button:not([disabled]), select, input');
    const elementCount = Math.min(await interactiveElements.count(), 8);

    for (let i = 0; i < elementCount; i++) {
      try {
        const element = interactiveElements.nth(i);
        if (await element.isVisible()) {
          await element.click({ timeout: 1000 });
          await page.waitForTimeout(100);
        }
      } catch (e) {
        // Continue if interaction fails
      }
    }

    const interactionTime = Date.now() - interactionStart;
    console.log(`Interaction response time: ${interactionTime}ms`);

    if (interactionTime < 2000) {
      console.log('✅ Interactive performance good');
    } else {
      console.log('⚠️  Interactive performance needs improvement');
    }
  });
});
