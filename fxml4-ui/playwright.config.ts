/**
 * Playwright Configuration for FXML4 UI E2E Testing
 *
 * Comprehensive E2E testing setup with cross-browser support, visual regression,
 * and performance monitoring
 */

import { defineConfig, devices } from '@playwright/test';

const baseURL = process.env.NEXT_PUBLIC_BASE_URL || 'http://localhost:3000';

export default defineConfig({
  // Test directory
  testDir: './tests',

  // Test timeout (increased for complex trading operations)
  timeout: 60 * 1000,

  // Expect timeout for assertions
  expect: {
    timeout: 10 * 1000,
  },

  // Simplified for comprehensive testing
  // globalSetup: require.resolve('./tests/global-setup.ts'),
  // globalTeardown: require.resolve('./tests/global-teardown.ts'),

  // Fail the build on CI if you accidentally left test.only in the source code
  forbidOnly: !!process.env.CI,

  // Retry on CI only
  retries: process.env.CI ? 2 : 0,

  // Opt out of parallel tests on CI
  workers: process.env.CI ? 1 : undefined,

  // Reporter configuration
  reporter: [
    ['html', { outputFolder: 'e2e-results' }],
    ['json', { outputFile: 'e2e-results/results.json' }],
    ['junit', { outputFile: 'e2e-results/results.xml' }],
    ['list']
  ],

  // Global configuration
  use: {
    // Base URL for tests
    baseURL,

    // Browser context options
    viewport: { width: 1280, height: 720 },

    // Collect trace when retrying the failed test
    trace: 'on-first-retry',

    // Record video on failure
    video: 'retain-on-failure',

    // Screenshot on failure
    screenshot: 'only-on-failure',

    // Navigation timeout
    navigationTimeout: 30 * 1000,

    // Action timeout
    actionTimeout: 15 * 1000,

    // Ignore certificate errors (for development)
    ignoreHTTPSErrors: true,

    // Authentication storage
    storageState: process.env.STORAGE_STATE,
  },

  // Simplified projects for comprehensive testing
  projects: [
    // Primary testing with Chromium
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
  ],

  // Development server configuration (disabled - using existing server)
  // webServer: {
  //   command: 'npm run dev',
  //   url: baseURL,
  //   timeout: 120 * 1000,
  //   reuseExistingServer: true,
  // },
});
