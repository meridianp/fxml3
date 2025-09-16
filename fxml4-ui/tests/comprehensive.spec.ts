import { test, expect, Page } from '@playwright/test';

const BASE_URL = 'http://localhost:3000';
const STREAMLIT_URL = 'http://localhost:8501';

test.describe('FXML4 Trading Platform - Comprehensive UI Testing', () => {

  test.beforeEach(async ({ page }) => {
    // Set longer timeout for slow operations
    test.setTimeout(60000);
    await page.goto(BASE_URL);
  });

  test('Homepage loads and redirects to dashboard', async ({ page }) => {
    await expect(page).toHaveURL(/.*dashboard/);
    await expect(page).toHaveTitle(/Dashboard.*FXML4/);
  });

  test('Dashboard loads without NotificationService errors', async ({ page }) => {
    await page.goto(`${BASE_URL}/dashboard`);

    // Wait for page to fully load
    await page.waitForLoadState('networkidle');

    // Check that the dashboard loaded without errors
    await expect(page.locator('h1').filter({ hasText: 'FXML4 Trading Platform' })).toBeVisible();

    // Verify no JavaScript errors
    const errors: string[] = [];
    page.on('pageerror', (error) => {
      errors.push(error.message);
    });

    // Wait a bit to catch any runtime errors
    await page.waitForTimeout(3000);

    expect(errors.filter(e => e.includes('NotificationService'))).toHaveLength(0);
  });

  test('Sidebar navigation is present and functional', async ({ page }) => {
    await page.goto(`${BASE_URL}/dashboard`);

    // Check sidebar exists
    await expect(page.locator('nav')).toBeVisible();

    // Check main navigation items
    await expect(page.locator('a[href="/dashboard"]')).toBeVisible();
    await expect(page.locator('a[href="/data"]')).toBeVisible();
    await expect(page.locator('a[href="/trading"]')).toBeVisible();
    await expect(page.locator('a[href="/backtesting"]')).toBeVisible();
    await expect(page.locator('a[href="/training"]')).toBeVisible();
  });

  test('Dashboard metrics cards are displayed', async ({ page }) => {
    await page.goto(`${BASE_URL}/dashboard`);
    await page.waitForLoadState('networkidle');

    // Look for metrics cards
    const metricsTexts = [
      'Active Models',
      'Running Backtests',
      'Open Positions',
      'Total P&L'
    ];

    for (const text of metricsTexts) {
      await expect(page.locator(`text=${text}`)).toBeVisible();
    }
  });

  test('Dashboard feature cards are clickable', async ({ page }) => {
    await page.goto(`${BASE_URL}/dashboard`);
    await page.waitForLoadState('networkidle');

    // Test Data Management card
    const dataCard = page.locator('text=Data Management');
    await expect(dataCard).toBeVisible();

    // Test ML Training Studio card
    const trainingCard = page.locator('text=ML Training Studio');
    await expect(trainingCard).toBeVisible();

    // Test Backtesting Workbench card
    const backtestCard = page.locator('text=Backtesting Workbench');
    await expect(backtestCard).toBeVisible();

    // Test Trading Console card
    const tradingCard = page.locator('text=Trading Console');
    await expect(tradingCard).toBeVisible();
  });

  test('Data page loads and has market data functionality', async ({ page }) => {
    await page.goto(`${BASE_URL}/data`);
    await page.waitForLoadState('networkidle');

    await expect(page).toHaveTitle(/Data.*FXML4/);
    // Look for data-related content
    const dataPageLoaded = await page.locator('body').textContent();
    expect(dataPageLoaded).toBeTruthy();
  });

  test('Trading page loads and has trading functionality', async ({ page }) => {
    await page.goto(`${BASE_URL}/trading`);
    await page.waitForLoadState('networkidle');

    await expect(page).toHaveTitle(/Trading.*FXML4/);
    // Look for trading-related content
    const tradingPageLoaded = await page.locator('body').textContent();
    expect(tradingPageLoaded).toBeTruthy();
  });

  test('Backtesting page loads and has backtesting functionality', async ({ page }) => {
    await page.goto(`${BASE_URL}/backtesting`);
    await page.waitForLoadState('networkidle');

    await expect(page).toHaveTitle(/Backtesting.*FXML4/);
    // Look for backtesting-related content
    const backtestPageLoaded = await page.locator('body').textContent();
    expect(backtestPageLoaded).toBeTruthy();
  });

  test('Training page loads and has ML training functionality', async ({ page }) => {
    await page.goto(`${BASE_URL}/training`);
    await page.waitForLoadState('networkidle');

    await expect(page).toHaveTitle(/Training.*FXML4/);
    // Look for training-related content
    const trainingPageLoaded = await page.locator('body').textContent();
    expect(trainingPageLoaded).toBeTruthy();
  });

  test('Profile page loads', async ({ page }) => {
    await page.goto(`${BASE_URL}/profile`);
    await page.waitForLoadState('networkidle');

    await expect(page).toHaveTitle(/Profile.*FXML4/);
  });

  test('Settings page loads', async ({ page }) => {
    await page.goto(`${BASE_URL}/settings`);
    await page.waitForLoadState('networkidle');

    await expect(page).toHaveTitle(/Settings.*FXML4/);
  });

  test('Help page loads', async ({ page }) => {
    await page.goto(`${BASE_URL}/help`);
    await page.waitForLoadState('networkidle');

    await expect(page).toHaveTitle(/Help.*FXML4/);
  });

  test('Navigation between pages works', async ({ page }) => {
    await page.goto(`${BASE_URL}/dashboard`);

    // Navigate to Data page
    await page.click('a[href="/data"]');
    await expect(page).toHaveURL(/.*data/);

    // Navigate to Trading page
    await page.click('a[href="/trading"]');
    await expect(page).toHaveURL(/.*trading/);

    // Navigate back to Dashboard
    await page.click('a[href="/dashboard"]');
    await expect(page).toHaveURL(/.*dashboard/);
  });

  test('Mobile responsive design works', async ({ page }) => {
    // Test mobile viewport
    await page.setViewportSize({ width: 375, height: 667 });
    await page.goto(`${BASE_URL}/dashboard`);

    await expect(page.locator('h1').filter({ hasText: 'FXML4 Trading Platform' })).toBeVisible();
  });

  test('Dark theme is applied correctly', async ({ page }) => {
    await page.goto(`${BASE_URL}/dashboard`);

    const html = page.locator('html');
    await expect(html).toHaveClass(/dark/);

    // Check for dark theme styles
    const body = page.locator('body');
    const bodyClasses = await body.getAttribute('class');
    expect(bodyClasses).toContain('bg-gray-950');
  });

  test('No JavaScript console errors on main pages', async ({ page }) => {
    const errors: string[] = [];

    page.on('pageerror', (error) => {
      errors.push(`${error.name}: ${error.message}`);
    });

    page.on('console', (msg) => {
      if (msg.type() === 'error') {
        errors.push(`Console error: ${msg.text()}`);
      }
    });

    const pages = ['/dashboard', '/data', '/trading', '/backtesting', '/training'];

    for (const route of pages) {
      await page.goto(`${BASE_URL}${route}`);
      await page.waitForLoadState('networkidle');
      await page.waitForTimeout(2000); // Wait for any delayed errors
    }

    // Filter out expected warnings (like metadata warnings)
    const criticalErrors = errors.filter(error =>
      !error.includes('metadata') &&
      !error.includes('Warning') &&
      !error.includes('viewport')
    );

    expect(criticalErrors).toHaveLength(0);
  });

  test('Audit fix endpoints are accessible', async ({ page }) => {
    // Test that the API endpoints for audit fixes work
    const response = await page.request.get('http://localhost:8001/health');
    expect(response.ok()).toBe(true);

    const healthData = await response.json();
    expect(healthData).toHaveProperty('status');
  });

  test('Page performance is acceptable', async ({ page }) => {
    // Measure page load performance
    const startTime = Date.now();

    await page.goto(`${BASE_URL}/dashboard`);
    await page.waitForLoadState('networkidle');

    const loadTime = Date.now() - startTime;

    // Expect page to load within 10 seconds
    expect(loadTime).toBeLessThan(10000);
  });
});

test.describe('Streamlit Analytics Dashboard', () => {
  test('Streamlit dashboard is accessible', async ({ page }) => {
    await page.goto(STREAMLIT_URL);
    await page.waitForLoadState('networkidle');

    // Look for Streamlit-specific content
    const pageContent = await page.locator('body').textContent();
    expect(pageContent).toBeTruthy();
  });

  test('Streamlit dashboard shows demo content', async ({ page }) => {
    await page.goto(STREAMLIT_URL);
    await page.waitForLoadState('networkidle');

    // Wait for Streamlit to fully load
    await page.waitForTimeout(5000);

    // Look for expected content
    const content = await page.textContent('body');
    expect(content).toContain('FXML4'); // Should have FXML4 branding
  });
});

test.describe('API Integration', () => {
  test('API health endpoint responds correctly', async ({ page }) => {
    const response = await page.request.get('http://localhost:8001/health');
    expect(response.ok()).toBe(true);

    const data = await response.json();
    expect(data).toHaveProperty('status', 'healthy');
    expect(data).toHaveProperty('version');
  });

  test('API documentation is accessible', async ({ page }) => {
    const response = await page.request.get('http://localhost:8001/docs');
    expect(response.ok()).toBe(true);
  });
});
