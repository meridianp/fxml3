import { test, expect } from '@playwright/test';

const BASE_URL = 'http://localhost:3000';

test.describe('7. FUNCTIONAL REALITY CHECK', () => {

  test('Dashboard shows REAL data vs mock placeholders', async ({ page }) => {
    await page.goto(`${BASE_URL}/dashboard`);
    await page.waitForLoadState('networkidle');

    console.log('=== DASHBOARD REALITY CHECK ===');

    // Test 1: Check for obviously fake/placeholder data
    const suspiciousPatterns = [
      'Lorem ipsum',
      'placeholder',
      'mock',
      'fake',
      'test data',
      'sample',
      '123.45', // Common placeholder number
      'John Doe',
      'example.com'
    ];

    const bodyText = await page.textContent('body');
    let placeholderCount = 0;
    let foundPlaceholders: string[] = [];

    for (const pattern of suspiciousPatterns) {
      if (bodyText?.toLowerCase().includes(pattern.toLowerCase())) {
        placeholderCount++;
        foundPlaceholders.push(pattern);
        console.log(`⚠ Found placeholder: "${pattern}"`);
      }
    }

    // Test 2: Check metrics for realistic values
    const metricCards = page.locator('.metric-card, .dashboard-card');
    const metricCount = await metricCards.count();
    console.log(`Found ${metricCount} metric cards`);

    for (let i = 0; i < metricCount; i++) {
      const card = metricCards.nth(i);
      const text = await card.textContent();

      // Look for obviously fake data patterns
      if (text?.includes('$2,847') || text?.includes('+$127') || text?.includes('12') || text?.includes('3') || text?.includes('5')) {
        console.log(`⚠ Suspicious static data in metric ${i + 1}: "${text?.slice(0, 50)}..."`);
      }
    }

    // Test 3: Check for real-time updates by waiting and checking again
    console.log('Testing for real-time updates...');
    const initialState = await page.textContent('body');

    await page.waitForTimeout(5000); // Wait 5 seconds

    const updatedState = await page.textContent('body');
    const hasRealTimeUpdates = initialState !== updatedState;

    console.log(`Real-time updates detected: ${hasRealTimeUpdates}`);
    console.log(`Placeholder patterns found: ${placeholderCount}`);
    console.log(`Specific placeholders: ${foundPlaceholders.join(', ')}`);
  });

  test('Market data shows LIVE prices vs static mockups', async ({ page }) => {
    await page.goto(`${BASE_URL}/data`);
    await page.waitForLoadState('networkidle');

    console.log('=== MARKET DATA REALITY CHECK ===');

    // Test 1: Look for market data tables
    const tables = page.locator('table, .data-table, .market-data');
    const tableCount = await tables.count();
    console.log(`Found ${tableCount} data tables`);

    if (tableCount === 0) {
      console.log('⚠ NO MARKET DATA TABLES FOUND');
      return;
    }

    // Test 2: Check for forex price patterns
    const bodyText = await page.textContent('body');
    const forexPatterns = [
      /EUR\/USD.*1\.\d{4}/,  // EURUSD price pattern
      /GBP\/USD.*1\.\d{4}/,  // GBPUSD price pattern
      /USD\/JPY.*\d{3}\.\d{3}/, // USDJPY price pattern
    ];

    let realForexPrices = 0;
    for (const pattern of forexPatterns) {
      if (pattern.test(bodyText || '')) {
        realForexPrices++;
        console.log(`✓ Found realistic forex price pattern: ${pattern}`);
      }
    }

    // Test 3: Check for bid/ask spreads
    const bidAskElements = page.locator('*:has-text("BID"), *:has-text("ASK"), *:has-text("Bid"), *:has-text("Ask")');
    const bidAskCount = await bidAskElements.count();
    console.log(`Bid/Ask elements found: ${bidAskCount}`);

    // Test 4: Look for obviously static/repeated values
    const priceElements = page.locator('*:has-text("1."), *:has-text("0."), [data-testid*="price"]');
    const priceCount = await priceElements.count();

    const prices: string[] = [];
    for (let i = 0; i < Math.min(priceCount, 10); i++) {
      const priceText = await priceElements.nth(i).textContent();
      if (priceText && priceText.match(/\d+\.\d+/)) {
        prices.push(priceText);
      }
    }

    // Check for duplicate prices (sign of mock data)
    const uniquePrices = [...new Set(prices)];
    const duplicateRatio = uniquePrices.length / prices.length;

    console.log(`Total prices found: ${prices.length}`);
    console.log(`Unique prices: ${uniquePrices.length}`);
    console.log(`Uniqueness ratio: ${duplicateRatio.toFixed(2)} (should be close to 1.0 for real data)`);
    console.log(`Realistic forex prices found: ${realForexPrices}`);

    if (duplicateRatio < 0.8) {
      console.log('⚠ High duplicate price ratio - likely mock data');
    }
  });

  test('Trading console shows REAL account data vs placeholder values', async ({ page }) => {
    await page.goto(`${BASE_URL}/trading`);
    await page.waitForLoadState('networkidle');

    console.log('=== TRADING CONSOLE REALITY CHECK ===');

    // Test 1: Check account balance display
    const balanceElements = page.locator('[data-testid="account-balance"], *:has-text("Balance"), *:has-text("$")');
    const balanceCount = await balanceElements.count();
    console.log(`Balance elements found: ${balanceCount}`);

    // Test 2: Look for common placeholder account values
    const suspiciousAccountValues = [
      '$10,000',
      '$100,000',
      '$50,000',
      '$5,000',
      '10000',
      '50000',
      '100000'
    ];

    let suspiciousValues = 0;
    const bodyText = await page.textContent('body');

    for (const value of suspiciousAccountValues) {
      if (bodyText?.includes(value)) {
        suspiciousValues++;
        console.log(`⚠ Found suspicious account value: ${value}`);
      }
    }

    // Test 3: Check for trading form functionality
    const tradingForm = page.locator('form[data-testid="trading-form"], .trading-form, .order-form');
    const formExists = await tradingForm.count() > 0;
    console.log(`Trading form exists: ${formExists}`);

    if (formExists) {
      // Test form inputs for real functionality
      const symbolInput = tradingForm.locator('select, input').first();
      const quantityInput = tradingForm.locator('input[type="number"]').first();

      if (await symbolInput.count() > 0) {
        console.log('✓ Trading form has symbol selection');
      }

      if (await quantityInput.count() > 0) {
        const placeholder = await quantityInput.getAttribute('placeholder');
        const value = await quantityInput.inputValue();
        console.log(`Quantity input - placeholder: "${placeholder}", value: "${value}"`);
      }
    }

    // Test 4: Check for position and order tables
    const positionTables = page.locator('table:has(th:has-text("Position")), .positions-table');
    const orderTables = page.locator('table:has(th:has-text("Order")), .orders-table');

    const positionCount = await positionTables.count();
    const orderCount = await orderTables.count();

    console.log(`Position tables found: ${positionCount}`);
    console.log(`Order tables found: ${orderCount}`);
    console.log(`Suspicious account values: ${suspiciousValues}`);
  });

  test('API connectivity and backend integration', async ({ page }) => {
    console.log('=== BACKEND CONNECTIVITY CHECK ===');

    // Test 1: Check network requests during page load
    const requests: string[] = [];
    const responses: number[] = [];

    page.on('request', request => {
      requests.push(request.url());
    });

    page.on('response', response => {
      responses.push(response.status());
    });

    await page.goto(`${BASE_URL}/dashboard`);
    await page.waitForLoadState('networkidle');

    // Analyze API calls
    const apiCalls = requests.filter(url =>
      url.includes('/api/') ||
      url.includes(':8000') ||
      url.includes(':8001') ||
      url.includes('fxml4')
    );

    const successfulResponses = responses.filter(status => status >= 200 && status < 300).length;
    const errorResponses = responses.filter(status => status >= 400).length;

    console.log(`Total requests: ${requests.length}`);
    console.log(`API calls: ${apiCalls.length}`);
    console.log(`Successful responses: ${successfulResponses}`);
    console.log(`Error responses: ${errorResponses}`);

    // Test 2: Check for WebSocket connections
    await page.evaluate(() => {
      // Check if WebSocket is being used
      const wsConnections = (window as any).wsConnections || [];
      console.log(`WebSocket connections: ${wsConnections.length}`);
    });

    // Test 3: Check local storage for real session data
    const localStorage = await page.evaluate(() => {
      const items: any = {};
      for (let i = 0; i < localStorage.length; i++) {
        const key = localStorage.key(i);
        if (key) {
          items[key] = localStorage.getItem(key);
        }
      }
      return items;
    });

    console.log('LocalStorage contents:', Object.keys(localStorage));

    // Look for authentication tokens or real session data
    const hasAuthData = Object.keys(localStorage).some(key =>
      key.includes('token') ||
      key.includes('auth') ||
      key.includes('session') ||
      key.includes('fxml4')
    );

    console.log(`Has authentication data: ${hasAuthData}`);

    if (apiCalls.length === 0) {
      console.log('⚠ NO API CALLS DETECTED - Platform may be purely static');
    }
  });

  test('ML and advanced features functionality check', async ({ page }) => {
    console.log('=== ML FEATURES REALITY CHECK ===');

    // Test 1: Check ML Training page
    await page.goto(`${BASE_URL}/training`);
    await page.waitForLoadState('networkidle');

    const trainingElements = page.locator('*:has-text("model"), *:has-text("training"), *:has-text("ML"), *:has-text("neural")');
    const trainingCount = await trainingElements.count();
    console.log(`ML/Training elements found: ${trainingCount}`);

    // Test 2: Check Backtesting page
    await page.goto(`${BASE_URL}/backtesting`);
    await page.waitForLoadState('networkidle');

    const backtestElements = page.locator('*:has-text("backtest"), *:has-text("strategy"), *:has-text("performance")');
    const backtestCount = await backtestElements.count();
    console.log(`Backtesting elements found: ${backtestCount}`);

    // Test 3: Look for charts and visualization
    const charts = page.locator('canvas, svg, .chart, [data-testid*="chart"]');
    const chartCount = await charts.count();
    console.log(`Charts/visualizations found: ${chartCount}`);

    // Test 4: Check for signal generation
    await page.goto(`${BASE_URL}/dashboard`);
    await page.waitForLoadState('networkidle');

    const signalElements = page.locator('*:has-text("signal"), *:has-text("buy"), *:has-text("sell"), *:has-text("recommendation")');
    const signalCount = await signalElements.count();
    console.log(`Signal-related elements found: ${signalCount}`);

    if (trainingCount === 0 && backtestCount === 0 && signalCount === 0) {
      console.log('⚠ NO ML FEATURES DETECTED - Advanced functionality missing');
    }
  });
});
