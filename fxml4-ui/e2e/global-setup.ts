/**
 * Global Setup for E2E Tests
 *
 * Handles authentication, test data preparation, and environment setup
 */

import { chromium, FullConfig } from '@playwright/test';
import fs from 'fs/promises';
import path from 'path';

async function globalSetup(config: FullConfig) {
  console.log('🚀 Starting global E2E test setup...');

  const { baseURL, storageState } = config.projects[0].use;

  // Create browser instance for setup
  const browser = await chromium.launch();
  const context = await browser.newContext();
  const page = await context.newPage();

  try {
    // Navigate to login page
    await page.goto(`${baseURL}/auth/login`);

    // Perform authentication (using test credentials)
    const testUser = {
      email: process.env.E2E_TEST_EMAIL || 'test@fxml4.com',
      password: process.env.E2E_TEST_PASSWORD || 'test123',
    };

    // Wait for login form and fill credentials
    await page.waitForSelector('[data-testid="login-form"]', { timeout: 10000 });
    await page.fill('[data-testid="email-input"]', testUser.email);
    await page.fill('[data-testid="password-input"]', testUser.password);
    await page.click('[data-testid="login-button"]');

    // Wait for successful login (check for dashboard or authenticated state)
    await page.waitForURL('**/dashboard', { timeout: 30000 });

    // Verify authentication was successful
    const isAuthenticated = await page.locator('[data-testid="user-menu"]').isVisible();
    if (!isAuthenticated) {
      throw new Error('Authentication failed during global setup');
    }

    console.log('✅ Authentication successful');

    // Save storage state for authenticated tests
    if (storageState) {
      await context.storageState({ path: storageState as string });
      console.log('✅ Storage state saved');
    }

    // Setup test data
    await setupTestData(page);

    // Verify critical services are available
    await verifyServices(page);

    console.log('✅ Global setup completed successfully');

  } catch (error) {
    console.error('❌ Global setup failed:', error);
    throw error;
  } finally {
    await browser.close();
  }
}

/**
 * Setup test data required for E2E tests
 */
async function setupTestData(page: any) {
  console.log('📝 Setting up test data...');

  try {
    // Navigate to data management to ensure services are initialized
    await page.goto('/data');
    await page.waitForLoadState('networkidle');

    // Ensure we have test market data
    const hasData = await page.locator('[data-testid="market-data-grid"]').count() > 0;
    if (!hasData) {
      // Trigger data load if needed
      await page.click('[data-testid="refresh-data-button"]');
      await page.waitForSelector('[data-testid="market-data-grid"]', { timeout: 30000 });
    }

    // Setup test strategies if needed
    await page.goto('/training');
    await page.waitForLoadState('networkidle');

    // Verify training components are available
    await page.waitForSelector('[data-testid="training-studio"]', { timeout: 10000 });

    console.log('✅ Test data setup completed');
  } catch (error) {
    console.warn('⚠️ Test data setup encountered issues:', error);
    // Don't fail setup for data issues, just log warning
  }
}

/**
 * Verify critical services are available
 */
async function verifyServices(page: any) {
  console.log('🔍 Verifying services...');

  const services = [
    { name: 'Analytics', path: '/dashboard', selector: '[data-testid="analytics-panel"]' },
    { name: 'Data Management', path: '/data', selector: '[data-testid="data-management-dashboard"]' },
    { name: 'Trading Console', path: '/trading', selector: '[data-testid="trading-console"]' },
  ];

  for (const service of services) {
    try {
      await page.goto(service.path);
      await page.waitForSelector(service.selector, { timeout: 15000 });
      console.log(`✅ ${service.name} service verified`);
    } catch (error) {
      console.warn(`⚠️ ${service.name} service verification failed:`, error);
    }
  }
}

/**
 * Create test reports directory
 */
async function createReportsDirectory() {
  const reportsDir = path.join(process.cwd(), 'e2e-results');
  try {
    await fs.access(reportsDir);
  } catch {
    await fs.mkdir(reportsDir, { recursive: true });
    console.log('📁 Created e2e-results directory');
  }
}

// Initialize reports directory
createReportsDirectory();

export default globalSetup;
