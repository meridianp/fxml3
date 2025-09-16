/**
 * 🔬 COMPREHENSIVE FXML4 PLATFORM FEATURE TESTING
 *
 * Systematic testing to identify:
 * - Real functionality vs mock data/placeholders
 * - API integration issues
 * - Frontend-backend endpoint mismatches
 * - Component functionality verification
 */

import { test, expect, Page } from '@playwright/test';

// Test configuration
const BASE_URL = process.env.PLAYWRIGHT_TEST_BASE_URL || 'http://localhost:3000';
const API_URL = process.env.PLAYWRIGHT_API_URL || 'http://localhost:8001';

interface TestResult {
  feature: string;
  status: 'PASS' | 'FAIL' | 'MOCK_DATA' | 'API_ERROR';
  details: string;
  consoleLogs: string[];
  apiErrors: string[];
}

let testResults: TestResult[] = [];

/**
 * Utility function to capture console messages and API errors
 */
async function setupPageMonitoring(page: Page): Promise<{ logs: string[], apiErrors: string[] }> {
  const logs: string[] = [];
  const apiErrors: string[] = [];

  // Capture console messages
  page.on('console', msg => {
    const text = msg.text();
    logs.push(`[${msg.type()}] ${text}`);

    // Detect API-related errors
    if (text.includes('CORS') || text.includes('Network Error') || text.includes('Failed to fetch')) {
      apiErrors.push(text);
    }
  });

  // Capture failed requests
  page.on('requestfailed', request => {
    const errorMsg = `Request failed: ${request.method()} ${request.url()} - ${request.failure()?.errorText}`;
    logs.push(errorMsg);
    if (request.url().includes(':8001')) {
      apiErrors.push(errorMsg);
    }
  });

  return { logs, apiErrors };
}

/**
 * Check if content appears to be real data vs mock/placeholder
 */
function isRealData(text: string): boolean {
  const mockIndicators = [
    'placeholder', 'mock', 'demo', 'test data', 'sample',
    'lorem ipsum', 'example', 'dummy', '123.45', '0.00',
    'fake', 'simulation', 'not available', 'coming soon'
  ];

  const lowerText = text.toLowerCase();
  return !mockIndicators.some(indicator => lowerText.includes(indicator));
}

test.describe('🔬 FXML4 Platform Comprehensive Testing', () => {

  test.beforeEach(async ({ page }) => {
    // Set up request interception to monitor API calls
    await page.route('**/*', async (route) => {
      const url = route.request().url();

      // Log all API requests
      if (url.includes(':8001')) {
        console.log(`API Request: ${route.request().method()} ${url}`);
      }

      await route.continue();
    });
  });

  test('🏠 Dashboard - Real Data vs Mock Detection', async ({ page }) => {
    const monitoring = await setupPageMonitoring(page);

    await page.goto(`${BASE_URL}/dashboard`);
    await page.waitForLoadState('networkidle');

    // Wait for potential data loading
    await page.waitForTimeout(3000);

    // Test account balance display
    const balanceElements = await page.locator('[data-testid*="balance"], [class*="balance"]').all();
    const priceElements = await page.locator('text=/\\$[0-9,]+\\.?[0-9]*/').all();
    let balanceStatus = 'PASS';
    let balanceDetails = '';

    const allElements = [...balanceElements, ...priceElements];

    if (allElements.length === 0) {
      balanceStatus = 'FAIL';
      balanceDetails = 'No balance information found';
    } else {
      for (const element of allElements) {
        const text = await element.textContent() || '';
        if (!isRealData(text) || text.includes('$0.00') || text.includes('$123,456')) {
          balanceStatus = 'MOCK_DATA';
          balanceDetails = `Suspicious balance data: ${text}`;
          break;
        }
      }
    }

    // Check for connection status
    const connectionStatus = await page.locator('[data-testid*="connection"], [class*="connection"]').first();
    const isConnected = connectionStatus ? await connectionStatus.textContent() : null;

    // Check for loading states vs real data
    const loadingElements = await page.locator('[data-testid*="loading"], [class*="loading"], [class*="spinner"]').count();
    const hasRealContent = await page.locator('text=/[0-9]+\\.?[0-9]*%|\\$[0-9,]+|[A-Z]{6}/').count() > 0;

    testResults.push({
      feature: 'Dashboard Balance Display',
      status: balanceStatus as any,
      details: balanceDetails || `Found ${balanceElements.length} balance elements, connected: ${isConnected}`,
      consoleLogs: monitoring.logs.slice(),
      apiErrors: monitoring.apiErrors.slice()
    });

    expect(balanceElements.length).toBeGreaterThan(0);
    expect(hasRealContent).toBe(true);
  });

  test('💹 Trading Console - API Integration', async ({ page }) => {
    const monitoring = await setupPageMonitoring(page);

    await page.goto(`${BASE_URL}/trading`);
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(3000);

    // Check for order placement forms
    const orderForms = await page.locator('form, [data-testid*=\"order\"], [class*=\"order-form\"]').count();

    // Check for position displays
    const positions = await page.locator('[data-testid*="position"], [class*="position"]').count();
    const symbolElements = await page.locator('text=/EURUSD|GBPUSD|USDJPY/').count();

    // Check for real-time price displays
    const priceElements = await page.locator('text=/[0-9]+\\.[0-9]{4,5}|1\\.[0-9]+/').count();

    // Look for API error indicators in the UI
    const errorMessages = await page.locator('text=/error|failed|unable to connect/i').count();

    let status: TestResult['status'] = 'PASS';
    const totalPositions = positions + symbolElements;
    let details = `Forms: ${orderForms}, Positions: ${totalPositions}, Prices: ${priceElements}`;

    if (monitoring.apiErrors.length > 0) {
      status = 'API_ERROR';
      details += `, API Errors: ${monitoring.apiErrors.length}`;
    } else if (errorMessages > 0) {
      status = 'FAIL';
      details += `, UI Errors: ${errorMessages}`;
    } else if (positions === 0 && priceElements === 0) {
      status = 'MOCK_DATA';
      details += ', No real trading data visible';
    }

    testResults.push({
      feature: 'Trading Console',
      status,
      details,
      consoleLogs: monitoring.logs.slice(),
      apiErrors: monitoring.apiErrors.slice()
    });

    expect(orderForms).toBeGreaterThan(0);
  });

  test('🤖 ML Models - Backend Integration', async ({ page }) => {
    const monitoring = await setupPageMonitoring(page);

    await page.goto(`${BASE_URL}/training`);
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(3000);

    // Check for model listings
    const modelElements = await page.locator('[data-testid*="model"], [class*="model"]').count();
    const mlTextElements = await page.locator('text=/model|training|accuracy/i').count();

    // Check for training controls
    const trainingControls = await page.locator('button:has-text(\"train\"), button:has-text(\"start\"), [data-testid*=\"train\"]').count();

    // Check for performance metrics
    const metrics = await page.locator('text=/accuracy|precision|recall|[0-9]+\\.[0-9]+%/').count();

    let status: TestResult['status'] = 'PASS';
    const totalModels = modelElements + mlTextElements;
    let details = `Models: ${totalModels}, Controls: ${trainingControls}, Metrics: ${metrics}`;

    if (monitoring.apiErrors.some(err => err.includes('ml/models'))) {
      status = 'API_ERROR';
      details += ', ML API endpoints failing';
    } else if (modelElements === 0) {
      status = 'MOCK_DATA';
      details += ', No models visible';
    }

    testResults.push({
      feature: 'ML Models',
      status,
      details,
      consoleLogs: monitoring.logs.slice(),
      apiErrors: monitoring.apiErrors.slice()
    });
  });

  test('📊 Backtesting - Workflow Integration', async ({ page }) => {
    const monitoring = await setupPageMonitoring(page);

    await page.goto(`${BASE_URL}/backtesting`);
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(3000);

    // Check for strategy configuration
    const strategyElements = await page.locator('[data-testid*=\"strategy\"], [class*=\"strategy\"], button:has-text(\"backtest\")').count();

    // Check for results display
    const resultsElements = await page.locator('[data-testid*="result"], [class*="result"]').count();
    const profitLossElements = await page.locator('text=/profit|loss|return/i').count();

    // Check for chart/visualization elements
    const chartElements = await page.locator('canvas, svg, [data-testid*=\"chart\"], [class*=\"chart\"]').count();

    let status: TestResult['status'] = 'PASS';
    const totalResults = resultsElements + profitLossElements;
    let details = `Strategies: ${strategyElements}, Results: ${totalResults}, Charts: ${chartElements}`;

    if (monitoring.apiErrors.some(err => err.includes('backtest'))) {
      status = 'API_ERROR';
      details += ', Backtest API failing';
    } else if (strategyElements === 0) {
      status = 'MOCK_DATA';
      details += ', No backtesting functionality visible';
    }

    testResults.push({
      feature: 'Backtesting',
      status,
      details,
      consoleLogs: monitoring.logs.slice(),
      apiErrors: monitoring.apiErrors.slice()
    });
  });

  test('🌊 Elliott Wave Analysis - Feature Completeness', async ({ page }) => {
    const monitoring = await setupPageMonitoring(page);

    await page.goto(`${BASE_URL}/elliott-waves`);
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(3000);

    // Check for wave analysis elements
    const waveElements = await page.locator('text=/wave|elliott|pattern|impulse|corrective/i').count();

    // Check for chart analysis tools
    const chartTools = await page.locator('canvas, svg, [data-testid*=\"chart\"], button:has-text(\"analyze\")').count();

    // Check for LLM integration indicators
    const llmElements = await page.locator('text=/ai|llm|analysis|generate/i').count();

    let status: TestResult['status'] = 'PASS';
    let details = `Wave Elements: ${waveElements}, Charts: ${chartTools}, LLM: ${llmElements}`;

    if (waveElements === 0 && chartTools === 0) {
      status = 'MOCK_DATA';
      details += ', Elliott Wave functionality missing';
    }

    testResults.push({
      feature: 'Elliott Wave Analysis',
      status,
      details,
      consoleLogs: monitoring.logs.slice(),
      apiErrors: monitoring.apiErrors.slice()
    });
  });

  test('📈 Data Management - Feed Integration', async ({ page }) => {
    const monitoring = await setupPageMonitoring(page);

    await page.goto(`${BASE_URL}/data`);
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(3000);

    // Check for data source indicators
    const dataElements = await page.locator('[data-testid*="data"]').count();
    const feedElements = await page.locator('text=/feed|source|symbol|EURUSD|GBPUSD/').count();

    // Check for connection status indicators
    const statusElements = await page.locator('text=/connected|active|live|status/i').count();

    // Check for data quality indicators
    const qualityElements = await page.locator('text=/quality|health|latency|[0-9]+ms/').count();

    let status: TestResult['status'] = 'PASS';
    const totalElements = dataElements + feedElements;
    let details = `Data: ${totalElements}, Status: ${statusElements}, Quality: ${qualityElements}`;

    if (monitoring.apiErrors.length > 0) {
      status = 'API_ERROR';
      details += `, API issues: ${monitoring.apiErrors.length}`;
    } else if (totalElements === 0) {
      status = 'MOCK_DATA';
      details += ', No data management features visible';
    }

    testResults.push({
      feature: 'Data Management',
      status,
      details,
      consoleLogs: monitoring.logs.slice(),
      apiErrors: monitoring.apiErrors.slice()
    });
  });

  test('🔌 WebSocket - Real-time Features', async ({ page }) => {
    const monitoring = await setupPageMonitoring(page);

    await page.goto(`${BASE_URL}/dashboard`);
    await page.waitForLoadState('networkidle');

    // Wait longer to allow WebSocket connection attempts
    await page.waitForTimeout(5000);

    // Check for WebSocket connection indicators in console
    const hasWebSocketLogs = monitoring.logs.some(log =>
      log.includes('WebSocket') || log.includes('ws://') || log.includes('socket')
    );

    // Check for real-time update indicators in UI
    const realtimeElements = await page.locator('[data-testid*="live"], [class*="live"]').count();
    const updateElements = await page.locator('text=/live|real-time|updating/i').count();

    // Check for connection status displays
    const connectionElements = await page.locator('[data-testid*="connection"]').count();
    const statusTextElements = await page.locator('text=/connected|disconnected/i').count();

    let status: TestResult['status'] = 'PASS';
    const totalElements = realtimeElements + updateElements + connectionElements + statusTextElements;
    let details = `WebSocket logs: ${hasWebSocketLogs}, RT elements: ${totalElements}, Update elements: ${updateElements}`;

    if (!hasWebSocketLogs && totalElements === 0) {
      status = 'MOCK_DATA';
      details += ', No real-time features detected';
    }

    testResults.push({
      feature: 'WebSocket Real-time',
      status,
      details,
      consoleLogs: monitoring.logs.slice(),
      apiErrors: monitoring.apiErrors.slice()
    });
  });

  test.afterAll(async () => {
    // Generate comprehensive test report
    console.log('\\n🔬 COMPREHENSIVE FXML4 TEST RESULTS');
    console.log('=====================================');

    let passCount = 0;
    let failCount = 0;
    let mockCount = 0;
    let apiErrorCount = 0;

    for (const result of testResults) {
      console.log(`\\n${result.feature}: ${result.status}`);
      console.log(`Details: ${result.details}`);

      if (result.apiErrors.length > 0) {
        console.log(`API Errors (${result.apiErrors.length}):`);
        result.apiErrors.forEach(error => console.log(`  - ${error}`));
      }

      switch (result.status) {
        case 'PASS': passCount++; break;
        case 'FAIL': failCount++; break;
        case 'MOCK_DATA': mockCount++; break;
        case 'API_ERROR': apiErrorCount++; break;
      }
    }

    console.log('\\n📊 SUMMARY');
    console.log('===========');
    console.log(`✅ PASS: ${passCount}`);
    console.log(`❌ FAIL: ${failCount}`);
    console.log(`🎭 MOCK_DATA: ${mockCount}`);
    console.log(`🔌 API_ERROR: ${apiErrorCount}`);
    console.log(`📝 TOTAL TESTS: ${testResults.length}`);

    // Success rate calculation
    const successRate = ((passCount / testResults.length) * 100).toFixed(1);
    console.log(`🎯 SUCCESS RATE: ${successRate}%`);

    if (apiErrorCount > 0 || mockCount > 0 || failCount > 0) {
      console.log('\\n🚨 ACTION ITEMS NEEDED:');
      if (apiErrorCount > 0) console.log('- Fix API endpoint integration issues');
      if (mockCount > 0) console.log('- Replace mock data with real backend integration');
      if (failCount > 0) console.log('- Address component functionality failures');
    }
  });
});
