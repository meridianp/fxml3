/**
 * Playwright Configuration for Visual Regression Testing
 *
 * Specialized configuration for visual testing with optimized settings
 */

import { defineConfig, devices } from '@playwright/test';

export default defineConfig({
  testDir: './e2e/visual',

  // Visual testing specific settings
  expect: {
    // Global screenshot comparison threshold
    threshold: parseFloat(process.env.VISUAL_THRESHOLD || '0.2'),

    // Screenshot comparison mode
    mode: 'precise',

    // Animation handling
    animations: 'disabled',
  },

  // Test execution settings
  timeout: 120000, // Longer timeout for visual tests
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 1,
  workers: process.env.CI ? 2 : undefined,

  // Reporter configuration
  reporter: [
    ['html', {
      outputFolder: 'e2e-results/visual/playwright-report',
      open: process.env.CI ? 'never' : 'on-failure'
    }],
    ['json', {
      outputFile: 'e2e-results/visual/results.json'
    }],
    ['junit', {
      outputFile: 'e2e-results/visual/junit.xml'
    }]
  ],

  // Global test configuration
  use: {
    // Base URL
    baseURL: process.env.BASE_URL || 'http://localhost:3000',

    // Screenshot settings
    screenshot: {
      mode: 'only-on-failure',
      fullPage: true
    },

    // Video recording for failed tests
    video: 'retain-on-failure',

    // Trace collection
    trace: 'retain-on-failure',

    // Ignore HTTPS errors for local testing
    ignoreHTTPSErrors: true,

    // Action timeout
    actionTimeout: 15000,

    // Navigation timeout
    navigationTimeout: 30000,
  },

  // Test output directories
  outputDir: 'e2e-results/visual/test-results',

  // Projects for different browsers and configurations
  projects: [
    // Setup project for authentication
    {
      name: 'setup',
      testMatch: /.*\.setup\.ts/,
      use: {
        ...devices['Desktop Chrome'],
      },
    },

    // Desktop browsers
    {
      name: 'chrome-visual',
      testMatch: '**/*.spec.ts',
      dependencies: ['setup'],
      use: {
        ...devices['Desktop Chrome'],
        channel: 'chrome',
      },
    },

    {
      name: 'firefox-visual',
      testMatch: '**/*.spec.ts',
      dependencies: ['setup'],
      use: {
        ...devices['Desktop Firefox'],
      },
    },

    {
      name: 'safari-visual',
      testMatch: '**/*.spec.ts',
      dependencies: ['setup'],
      use: {
        ...devices['Desktop Safari'],
      },
    },

    // Mobile browsers
    {
      name: 'mobile-chrome-visual',
      testMatch: '**/*.spec.ts',
      dependencies: ['setup'],
      use: {
        ...devices['Pixel 5'],
      },
    },

    {
      name: 'mobile-safari-visual',
      testMatch: '**/*.spec.ts',
      dependencies: ['setup'],
      use: {
        ...devices['iPhone 12'],
      },
    },

    // Tablet browsers
    {
      name: 'tablet-visual',
      testMatch: '**/*.spec.ts',
      dependencies: ['setup'],
      use: {
        ...devices['iPad Pro'],
      },
    },

    // High DPI displays
    {
      name: 'high-dpi-visual',
      testMatch: '**/*.spec.ts',
      dependencies: ['setup'],
      use: {
        ...devices['Desktop Chrome'],
        deviceScaleFactor: 2,
        viewport: { width: 1920, height: 1080 },
      },
    },

    // Legacy browser simulation
    {
      name: 'legacy-visual',
      testMatch: '**/*.spec.ts',
      dependencies: ['setup'],
      use: {
        ...devices['Desktop Chrome'],
        channel: 'chrome',
        launchOptions: {
          args: [
            '--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/90.0.4430.212 Safari/537.36'
          ]
        }
      },
    },
  ],

  // Web server configuration
  webServer: process.env.CI ? undefined : {
    command: 'npm run dev',
    port: 3000,
    reuseExistingServer: !process.env.CI,
    timeout: 120000,
  },
});
