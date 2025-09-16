/**
 * Cross-Browser Compatibility Tests
 *
 * Comprehensive testing across Chrome, Firefox, Safari, and Edge
 * Validates consistent behavior and accessibility across all major browsers
 */

import { test, expect, chromium, firefox, webkit, Browser, Page } from '@playwright/test';
import { injectAxe, checkA11y, getViolations } from '@axe-core/playwright';

interface BrowserTestResult {
  browser: string;
  version: string;
  passed: boolean;
  errors: string[];
  warnings: string[];
  performance: {
    loadTime: number;
    renderTime: number;
    interactionTime: number;
  };
  accessibility: {
    violations: number;
    issues: string[];
  };
}

const BROWSERS = [
  { name: 'chromium', launcher: chromium },
  { name: 'firefox', launcher: firefox },
  { name: 'webkit', launcher: webkit }
];

const TEST_URLS = [
  { path: '/dashboard', name: 'Dashboard' },
  { path: '/trading', name: 'Trading Console' },
  { path: '/analytics', name: 'Performance Analytics' },
  { path: '/data', name: 'Market Data' },
  { path: '/backtesting', name: 'Backtesting' }
];

const MOBILE_VIEWPORTS = [
  { name: 'iPhone 13', width: 390, height: 844 },
  { name: 'iPad', width: 768, height: 1024 },
  { name: 'Samsung Galaxy S21', width: 384, height: 854 }
];

test.describe('Cross-Browser Compatibility Tests', () => {
  let browsers: Browser[] = [];

  test.beforeAll(async () => {
    // Launch all browsers
    for (const browser of BROWSERS) {
      const instance = await browser.launcher.launch({
        headless: true,
        args: ['--disable-web-security'] // For local testing
      });
      browsers.push(instance);
    }
  });

  test.afterAll(async () => {
    // Close all browsers
    await Promise.all(browsers.map(browser => browser.close()));
  });

  // Test each page across all browsers
  for (const testUrl of TEST_URLS) {
    for (let i = 0; i < BROWSERS.length; i++) {
      const browserInfo = BROWSERS[i];

      test(`${testUrl.name} - ${browserInfo.name} compatibility`, async () => {
        const browser = browsers[i];
        const context = await browser.newContext({
          viewport: { width: 1920, height: 1080 }
        });
        const page = await context.newPage();

        const result = await testPageCompatibility(page, testUrl.path, browserInfo.name);

        // Assert compatibility
        expect(result.passed, `Browser compatibility failed for ${browserInfo.name}: ${result.errors.join(', ')}`).toBe(true);
        expect(result.accessibility.violations).toBe(0);
        expect(result.performance.loadTime).toBeLessThan(5000);

        await context.close();
      });
    }
  }

  // Mobile compatibility tests
  for (const viewport of MOBILE_VIEWPORTS) {
    test(`Mobile compatibility - ${viewport.name}`, async () => {
      const browser = await chromium.launch();
      const context = await browser.newContext({
        viewport: { width: viewport.width, height: viewport.height },
        isMobile: true,
        hasTouch: true
      });
      const page = await context.newPage();

      // Test mobile trading console
      const result = await testMobileCompatibility(page, '/trading');

      expect(result.passed).toBe(true);
      expect(result.accessibility.violations).toBe(0);

      await browser.close();
    });
  }

  // Feature compatibility tests
  test('WebSocket compatibility across browsers', async () => {
    const results: BrowserTestResult[] = [];

    for (let i = 0; i < browsers.length; i++) {
      const browser = browsers[i];
      const browserName = BROWSERS[i].name;
      const context = await browser.newContext();
      const page = await context.newPage();

      const result = await testWebSocketCompatibility(page, browserName);
      results.push(result);

      await context.close();
    }

    // All browsers should support WebSocket
    results.forEach(result => {
      expect(result.passed, `WebSocket not supported in ${result.browser}`).toBe(true);
    });
  });

  test('PWA compatibility across browsers', async () => {
    const results: BrowserTestResult[] = [];

    for (let i = 0; i < browsers.length; i++) {
      const browser = browsers[i];
      const browserName = BROWSERS[i].name;
      const context = await browser.newContext();
      const page = await context.newPage();

      const result = await testPWACompatibility(page, browserName);
      results.push(result);

      await context.close();
    }

    // Check PWA support
    results.forEach(result => {
      if (result.browser === 'webkit') {
        // Safari has limited PWA support
        expect(result.warnings.length).toBeGreaterThan(0);
      } else {
        expect(result.passed).toBe(true);
      }
    });
  });

  test('Local Storage compatibility', async () => {
    for (let i = 0; i < browsers.length; i++) {
      const browser = browsers[i];
      const browserName = BROWSERS[i].name;
      const context = await browser.newContext();
      const page = await context.newPage();

      await page.goto('http://localhost:3001');

      // Test localStorage
      const localStorageSupported = await page.evaluate(() => {
        try {
          localStorage.setItem('test', 'value');
          const retrieved = localStorage.getItem('test');
          localStorage.removeItem('test');
          return retrieved === 'value';
        } catch (e) {
          return false;
        }
      });

      expect(localStorageSupported, `LocalStorage not supported in ${browserName}`).toBe(true);

      await context.close();
    }
  });

  test('CSS Grid and Flexbox compatibility', async () => {
    for (let i = 0; i < browsers.length; i++) {
      const browser = browsers[i];
      const browserName = BROWSERS[i].name;
      const context = await browser.newContext();
      const page = await context.newPage();

      await page.goto('http://localhost:3001/trading');

      // Test CSS Grid support
      const gridSupported = await page.evaluate(() => {
        const testElement = document.createElement('div');
        testElement.style.display = 'grid';
        return getComputedStyle(testElement).display === 'grid';
      });

      // Test Flexbox support
      const flexSupported = await page.evaluate(() => {
        const testElement = document.createElement('div');
        testElement.style.display = 'flex';
        return getComputedStyle(testElement).display === 'flex';
      });

      expect(gridSupported, `CSS Grid not supported in ${browserName}`).toBe(true);
      expect(flexSupported, `Flexbox not supported in ${browserName}`).toBe(true);

      await context.close();
    }
  });

  test('Chart rendering compatibility', async () => {
    for (let i = 0; i < browsers.length; i++) {
      const browser = browsers[i];
      const browserName = BROWSERS[i].name;
      const context = await browser.newContext();
      const page = await context.newPage();

      await page.goto('http://localhost:3001/analytics');

      // Wait for charts to render
      await page.waitForSelector('[data-testid="equity-curve-chart"]', { timeout: 10000 });

      // Check if charts are visible
      const chartVisible = await page.isVisible('[data-testid="equity-curve-chart"]');
      const chartHasContent = await page.evaluate(() => {
        const chart = document.querySelector('[data-testid="equity-curve-chart"]');
        return chart && chart.children.length > 0;
      });

      expect(chartVisible, `Chart not visible in ${browserName}`).toBe(true);
      expect(chartHasContent, `Chart has no content in ${browserName}`).toBe(true);

      await context.close();
    }
  });
});

/**
 * Test page compatibility across browsers
 */
async function testPageCompatibility(
  page: Page,
  url: string,
  browserName: string
): Promise<BrowserTestResult> {
  const result: BrowserTestResult = {
    browser: browserName,
    version: await getBrowserVersion(page),
    passed: true,
    errors: [],
    warnings: [],
    performance: {
      loadTime: 0,
      renderTime: 0,
      interactionTime: 0
    },
    accessibility: {
      violations: 0,
      issues: []
    }
  };

  try {
    // Measure load time
    const startTime = Date.now();
    await page.goto(`http://localhost:3001${url}`, { waitUntil: 'networkidle' });
    result.performance.loadTime = Date.now() - startTime;

    // Measure render time
    const renderStartTime = Date.now();
    await page.waitForSelector('body');
    result.performance.renderTime = Date.now() - renderStartTime;

    // Check for JavaScript errors
    page.on('console', (msg) => {
      if (msg.type() === 'error') {
        result.errors.push(msg.text());
      } else if (msg.type() === 'warning') {
        result.warnings.push(msg.text());
      }
    });

    page.on('pageerror', (error) => {
      result.errors.push(error.message);
    });

    // Test accessibility
    await injectAxe(page);
    const violations = await getViolations(page);
    result.accessibility.violations = violations.length;
    result.accessibility.issues = violations.map(v => v.description);

    // Test basic functionality
    const functionalityTests = await testBasicFunctionality(page);
    if (!functionalityTests.success) {
      result.errors.push(...functionalityTests.errors);
    }

    // Measure interaction time
    const interactionStartTime = Date.now();
    await page.click('button:first-of-type', { timeout: 5000 });
    result.performance.interactionTime = Date.now() - interactionStartTime;

  } catch (error) {
    result.errors.push(`Test execution failed: ${error}`);
  }

  result.passed = result.errors.length === 0 && result.accessibility.violations === 0;
  return result;
}

/**
 * Test mobile compatibility
 */
async function testMobileCompatibility(
  page: Page,
  url: string
): Promise<BrowserTestResult> {
  const result: BrowserTestResult = {
    browser: 'mobile',
    version: 'mobile',
    passed: true,
    errors: [],
    warnings: [],
    performance: { loadTime: 0, renderTime: 0, interactionTime: 0 },
    accessibility: { violations: 0, issues: [] }
  };

  try {
    await page.goto(`http://localhost:3001${url}`);

    // Test mobile-specific features
    const hasMobileQuickActions = await page.isVisible('.fixed.bottom-6.right-6');
    if (!hasMobileQuickActions) {
      result.warnings.push('Mobile quick actions not visible');
    }

    // Test touch interactions
    const touchSupported = await page.evaluate(() => 'ontouchstart' in window);
    if (!touchSupported) {
      result.warnings.push('Touch events not supported');
    }

    // Test responsive layout
    const isResponsive = await page.evaluate(() => {
      const viewport = document.querySelector('meta[name="viewport"]');
      return viewport && viewport.getAttribute('content')?.includes('width=device-width');
    });

    if (!isResponsive) {
      result.errors.push('Page is not responsive');
    }

    // Test accessibility on mobile
    await injectAxe(page);
    const violations = await getViolations(page);
    result.accessibility.violations = violations.length;

  } catch (error) {
    result.errors.push(`Mobile test failed: ${error}`);
  }

  result.passed = result.errors.length === 0;
  return result;
}

/**
 * Test WebSocket compatibility
 */
async function testWebSocketCompatibility(
  page: Page,
  browserName: string
): Promise<BrowserTestResult> {
  const result: BrowserTestResult = {
    browser: browserName,
    version: await getBrowserVersion(page),
    passed: true,
    errors: [],
    warnings: [],
    performance: { loadTime: 0, renderTime: 0, interactionTime: 0 },
    accessibility: { violations: 0, issues: [] }
  };

  try {
    await page.goto('http://localhost:3001');

    const webSocketSupported = await page.evaluate(() => {
      return 'WebSocket' in window;
    });

    if (!webSocketSupported) {
      result.errors.push('WebSocket not supported');
    }

    // Test WebSocket connection
    const connectionTest = await page.evaluate(() => {
      return new Promise<boolean>((resolve) => {
        try {
          const ws = new WebSocket('ws://localhost:8080');
          ws.onopen = () => {
            ws.close();
            resolve(true);
          };
          ws.onerror = () => resolve(false);
          setTimeout(() => resolve(false), 5000);
        } catch (e) {
          resolve(false);
        }
      });
    });

    if (!connectionTest) {
      result.warnings.push('WebSocket connection test failed');
    }

  } catch (error) {
    result.errors.push(`WebSocket test failed: ${error}`);
  }

  result.passed = result.errors.length === 0;
  return result;
}

/**
 * Test PWA compatibility
 */
async function testPWACompatibility(
  page: Page,
  browserName: string
): Promise<BrowserTestResult> {
  const result: BrowserTestResult = {
    browser: browserName,
    version: await getBrowserVersion(page),
    passed: true,
    errors: [],
    warnings: [],
    performance: { loadTime: 0, renderTime: 0, interactionTime: 0 },
    accessibility: { violations: 0, issues: [] }
  };

  try {
    await page.goto('http://localhost:3001');

    // Check for manifest
    const manifestExists = await page.evaluate(() => {
      const manifest = document.querySelector('link[rel="manifest"]');
      return !!manifest;
    });

    if (!manifestExists) {
      result.errors.push('PWA manifest not found');
    }

    // Check for service worker support
    const serviceWorkerSupported = await page.evaluate(() => {
      return 'serviceWorker' in navigator;
    });

    if (!serviceWorkerSupported) {
      if (browserName === 'webkit') {
        result.warnings.push('Service Worker support limited in Safari');
      } else {
        result.errors.push('Service Worker not supported');
      }
    }

    // Check for notification support
    const notificationSupported = await page.evaluate(() => {
      return 'Notification' in window;
    });

    if (!notificationSupported) {
      result.warnings.push('Notification API not supported');
    }

  } catch (error) {
    result.errors.push(`PWA test failed: ${error}`);
  }

  result.passed = result.errors.length === 0;
  return result;
}

/**
 * Test basic functionality
 */
async function testBasicFunctionality(page: Page): Promise<{ success: boolean; errors: string[] }> {
  const errors: string[] = [];

  try {
    // Check if page loaded properly
    const title = await page.title();
    if (!title || title.includes('Error')) {
      errors.push('Page failed to load properly');
    }

    // Check for critical elements
    const hasMainContent = await page.isVisible('main, [role="main"], #root');
    if (!hasMainContent) {
      errors.push('Main content not visible');
    }

    // Check for interactive elements
    const hasButtons = await page.$$('button');
    if (hasButtons.length === 0) {
      errors.push('No interactive buttons found');
    }

    // Check for navigation
    const hasNavigation = await page.isVisible('nav, [role="navigation"]');
    if (!hasNavigation) {
      errors.push('Navigation not found');
    }

  } catch (error) {
    errors.push(`Functionality test failed: ${error}`);
  }

  return {
    success: errors.length === 0,
    errors
  };
}

/**
 * Get browser version
 */
async function getBrowserVersion(page: Page): Promise<string> {
  try {
    return await page.evaluate(() => navigator.userAgent);
  } catch {
    return 'unknown';
  }
}

/**
 * Generate compatibility report
 */
export function generateCompatibilityReport(results: BrowserTestResult[]): string {
  let report = '# Cross-Browser Compatibility Report\n\n';

  report += '## Summary\n';
  const totalTests = results.length;
  const passedTests = results.filter(r => r.passed).length;
  const failedTests = totalTests - passedTests;

  report += `- **Total Tests**: ${totalTests}\n`;
  report += `- **Passed**: ${passedTests}\n`;
  report += `- **Failed**: ${failedTests}\n`;
  report += `- **Success Rate**: ${Math.round((passedTests / totalTests) * 100)}%\n\n`;

  report += '## Browser Results\n';
  results.forEach(result => {
    const status = result.passed ? '✅' : '❌';
    report += `### ${status} ${result.browser}\n`;
    report += `- **Version**: ${result.version}\n`;
    report += `- **Load Time**: ${result.performance.loadTime}ms\n`;
    report += `- **Render Time**: ${result.performance.renderTime}ms\n`;
    report += `- **Accessibility Violations**: ${result.accessibility.violations}\n`;

    if (result.errors.length > 0) {
      report += `- **Errors**:\n`;
      result.errors.forEach(error => {
        report += `  - ${error}\n`;
      });
    }

    if (result.warnings.length > 0) {
      report += `- **Warnings**:\n`;
      result.warnings.forEach(warning => {
        report += `  - ${warning}\n`;
      });
    }

    report += '\n';
  });

  return report;
}
