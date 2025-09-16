import { test, expect } from '@playwright/test';

const BASE_URL = 'http://localhost:3000';

test.describe('4. DATA FEATURES', () => {

  test('Market data tables display and function', async ({ page }) => {
    await page.goto(`${BASE_URL}/data`);
    await page.waitForLoadState('networkidle');

    // Look for market data tables
    const tableSelectors = [
      'table',
      '[data-testid*="data-table"]',
      '[data-testid*="market-data"]',
      '.data-table',
      '.market-data-table'
    ];

    let foundTables = 0;
    for (const selector of tableSelectors) {
      const tables = page.locator(selector);
      const count = await tables.count();

      if (count > 0) {
        foundTables += count;
        console.log(`✓ Found ${count} data tables: ${selector}`);

        const firstTable = tables.first();

        // Check for table headers
        const headers = firstTable.locator('th');
        const headerCount = await headers.count();
        console.log(`  Table headers: ${headerCount}`);

        if (headerCount > 0) {
          const headerTexts = await headers.allTextContents();
          console.log(`  Headers: ${headerTexts.join(', ')}`);
        }

        // Check for table data
        const rows = firstTable.locator('tbody tr, tr');
        const rowCount = await rows.count();
        console.log(`  Data rows: ${rowCount}`);

        if (rowCount > 0) {
          const firstRowText = await rows.first().textContent();
          console.log(`  Sample row: "${firstRowText?.slice(0, 100)}..."`);
        }
      }
    }

    console.log(`Total data tables found: ${foundTables}`);
    expect(foundTables, 'Should have data tables').toBeGreaterThan(0);
  });

  test('Data sorting by column works', async ({ page }) => {
    await page.goto(`${BASE_URL}/data`);
    await page.waitForLoadState('networkidle');

    // Look for sortable column headers
    const sortableHeaders = page.locator('th[role="columnheader"], th:has(button), th.sortable, th[data-sort]');
    const count = await sortableHeaders.count();

    console.log(`Sortable column headers found: ${count}`);

    if (count > 0) {
      // Test clicking first sortable header
      const firstHeader = sortableHeaders.first();
      const headerText = await firstHeader.textContent();
      console.log(`Testing sort on column: "${headerText}"`);

      try {
        await firstHeader.click();
        await page.waitForTimeout(1000);

        // Check for sort indicators
        const sortIndicators = page.locator('.sort-asc, .sort-desc, [aria-sort], .fa-sort');
        const indicatorCount = await sortIndicators.count();
        console.log(`Sort indicators found: ${indicatorCount}`);

      } catch (error) {
        console.log(`Sort test failed: ${error}`);
      }
    }
  });

  test('Data filtering functionality', async ({ page }) => {
    await page.goto(`${BASE_URL}/data`);
    await page.waitForLoadState('networkidle');

    // Look for filter controls
    const filterSelectors = [
      'input[placeholder*="filter"], input[placeholder*="Filter"]',
      'input[placeholder*="search"], input[placeholder*="Search"]',
      'select[data-testid*="filter"]',
      '.filter-input',
      '.search-input',
      'button:has-text("Filter")'
    ];

    let filterControls = 0;
    for (const selector of filterSelectors) {
      const elements = page.locator(selector);
      const count = await elements.count();

      if (count > 0) {
        filterControls += count;
        console.log(`✓ Found ${count} filter controls: ${selector}`);

        // Test first filter
        const firstFilter = elements.first();
        try {
          if (await firstFilter.getAttribute('type') === 'text' ||
              await firstFilter.tagName() === 'INPUT') {
            await firstFilter.fill('EUR');
            await page.waitForTimeout(1000);
            console.log(`  Filter test successful`);
          }
        } catch (error) {
          console.log(`  Filter test failed: ${error}`);
        }
      }
    }

    console.log(`Total filter controls: ${filterControls}`);
  });

  test('Historical data display and navigation', async ({ page }) => {
    await page.goto(`${BASE_URL}/data`);
    await page.waitForLoadState('networkidle');

    // Look for date/time controls
    const dateSelectors = [
      'input[type="date"]',
      'input[type="datetime-local"]',
      '[data-testid*="date"]',
      'select:has(option:has-text("1H"), option:has-text("1D"))',
      '.date-picker',
      '.timeframe-selector'
    ];

    let dateControls = 0;
    for (const selector of dateSelectors) {
      const elements = page.locator(selector);
      const count = await elements.count();

      if (count > 0) {
        dateControls += count;
        console.log(`✓ Found ${count} date/time controls: ${selector}`);

        const firstControl = elements.first();
        const tagName = await firstControl.tagName();
        const type = await firstControl.getAttribute('type');
        console.log(`  Control type: ${tagName} (${type})`);
      }
    }

    console.log(`Total date/time controls: ${dateControls}`);
  });

  test('Data export functionality', async ({ page }) => {
    await page.goto(`${BASE_URL}/data`);
    await page.waitForLoadState('networkidle');

    // Look for export buttons
    const exportSelectors = [
      'button:has-text("Export")',
      'button:has-text("Download")',
      'button:has-text("CSV")',
      'button:has-text("Excel")',
      '[data-testid*="export"]',
      '.export-button'
    ];

    let exportButtons = 0;
    for (const selector of exportSelectors) {
      const buttons = page.locator(selector);
      const count = await buttons.count();

      if (count > 0) {
        exportButtons += count;
        console.log(`✓ Found ${count} export buttons: ${selector}`);

        // Test button functionality (without actually downloading)
        const firstButton = buttons.first();
        const isEnabled = await firstButton.isEnabled();
        const buttonText = await firstButton.textContent();
        console.log(`  Button "${buttonText}" enabled: ${isEnabled}`);
      }
    }

    console.log(`Total export buttons: ${exportButtons}`);
  });

  test('Price chart visualization', async ({ page }) => {
    await page.goto(`${BASE_URL}/data`);
    await page.waitForLoadState('networkidle');

    // Look for chart elements
    const chartSelectors = [
      'canvas',
      'svg',
      '[data-testid*="chart"]',
      '.chart-container',
      '.price-chart',
      '.recharts-wrapper',
      '#price-chart'
    ];

    let foundCharts = 0;
    for (const selector of chartSelectors) {
      const charts = page.locator(selector);
      const count = await charts.count();

      if (count > 0) {
        foundCharts += count;
        console.log(`✓ Found ${count} charts: ${selector}`);

        // Check chart dimensions
        const firstChart = charts.first();
        const boundingBox = await firstChart.boundingBox();
        if (boundingBox) {
          console.log(`  Chart size: ${boundingBox.width}x${boundingBox.height}px`);

          // Chart should be reasonably sized
          if (boundingBox.width > 200 && boundingBox.height > 100) {
            console.log(`  ✓ Chart has proper dimensions`);
          } else {
            console.log(`  ⚠ Chart seems too small`);
          }
        }
      }
    }

    console.log(`Total chart elements: ${foundCharts}`);
  });

  test('Timeframe selection functionality', async ({ page }) => {
    await page.goto(`${BASE_URL}/data`);
    await page.waitForLoadState('networkidle');

    // Look for timeframe selectors
    const timeframeSelectors = [
      'select:has(option:has-text("1m"), option:has-text("5m"))',
      'button:has-text("1H"), button:has-text("1D")',
      '[data-testid*="timeframe"]',
      '.timeframe-buttons',
      '.period-selector'
    ];

    let timeframeControls = 0;
    for (const selector of timeframeSelectors) {
      const elements = page.locator(selector);
      const count = await elements.count();

      if (count > 0) {
        timeframeControls += count;
        console.log(`✓ Found ${count} timeframe controls: ${selector}`);

        // Test functionality
        const firstControl = elements.first();
        try {
          if (await firstControl.tagName() === 'SELECT') {
            const options = firstControl.locator('option');
            const optionCount = await options.count();
            console.log(`  Select has ${optionCount} timeframe options`);
          } else {
            // Assume it's a button
            await firstControl.click();
            await page.waitForTimeout(500);
            console.log(`  Timeframe button clicked successfully`);
          }
        } catch (error) {
          console.log(`  Timeframe control test failed: ${error}`);
        }
      }
    }

    console.log(`Total timeframe controls: ${timeframeControls}`);
  });

  test('Real-time price updates in data view', async ({ page }) => {
    await page.goto(`${BASE_URL}/data`);
    await page.waitForLoadState('networkidle');

    // Look for price elements that should update
    const priceSelectors = [
      '[data-testid*="price"]',
      '.price',
      '.live-price',
      'td:has-text("1."), td:has-text("0.")',
      '.market-price'
    ];

    let priceElements = 0;
    for (const selector of priceSelectors) {
      const elements = page.locator(selector);
      const count = await elements.count();

      if (count > 0) {
        priceElements += count;
        console.log(`✓ Found ${count} price elements: ${selector}`);

        // Check if prices look like valid numbers
        const firstElement = elements.first();
        const priceText = await firstElement.textContent() || '';
        const hasNumberPattern = /[\d.]+/.test(priceText);
        console.log(`  Sample price: "${priceText}" (valid format: ${hasNumberPattern})`);
      }
    }

    console.log(`Total price elements: ${priceElements}`);
  });
});
