/**
 * Visual Regression Testing
 *
 * Tests for UI consistency across browsers, viewports, and theme changes
 */

import { test, expect, devices } from '@playwright/test';

test.describe('Visual Regression Testing', () => {
  test.use({ storageState: 'e2e/.auth/user.json' });

  const criticalPages = [
    { url: '/dashboard', name: 'Dashboard', key: 'dashboard' },
    { url: '/trading', name: 'Trading Console', key: 'trading' },
    { url: '/data', name: 'Data Management', key: 'data' },
    { url: '/training', name: 'ML Training', key: 'training' },
    { url: '/analytics', name: 'Analytics', key: 'analytics' },
  ];

  const viewports = [
    { width: 1920, height: 1080, name: 'Desktop Large', key: 'desktop-xl' },
    { width: 1280, height: 720, name: 'Desktop Standard', key: 'desktop-lg' },
    { width: 1024, height: 768, name: 'Desktop Small', key: 'desktop-md' },
    { width: 768, height: 1024, name: 'Tablet Portrait', key: 'tablet-portrait' },
    { width: 1024, height: 768, name: 'Tablet Landscape', key: 'tablet-landscape' },
    { width: 375, height: 667, name: 'Mobile Large', key: 'mobile-lg' },
    { width: 320, height: 568, name: 'Mobile Small', key: 'mobile-sm' },
  ];

  test.describe('Full Page Screenshots', () => {
    criticalPages.forEach(pageInfo => {
      viewports.forEach(viewport => {
        test(`${pageInfo.name} - ${viewport.name} (${viewport.width}x${viewport.height})`, async ({ page, browserName }) => {
          // Set viewport
          await page.setViewportSize({ width: viewport.width, height: viewport.height });

          // Navigate to page
          await page.goto(pageInfo.url);
          await page.waitForLoadState('networkidle');

          // Wait for animations to complete
          await page.waitForTimeout(1000);

          // Hide dynamic content that changes frequently
          await page.addStyleTag({
            content: `
              [data-testid="current-time"],
              [data-testid="last-updated"],
              [data-testid="live-price"],
              [data-testid="websocket-status"] {
                visibility: hidden !important;
              }

              /* Disable animations for consistent screenshots */
              *, *::before, *::after {
                animation-duration: 0s !important;
                animation-delay: 0s !important;
                transition-duration: 0s !important;
                transition-delay: 0s !important;
              }
            `
          });

          // Take full page screenshot
          await expect(page).toHaveScreenshot(
            `${pageInfo.key}-${viewport.key}-${browserName}.png`,
            {
              fullPage: true,
              threshold: 0.2,
              animations: 'disabled'
            }
          );
        });
      });
    });
  });

  test.describe('Component-Level Screenshots', () => {
    const criticalComponents = [
      { selector: '[data-testid="app-header"]', name: 'Header' },
      { selector: '[data-testid="navigation-sidebar"]', name: 'Navigation' },
      { selector: '[data-testid="trading-console"]', name: 'Trading Console' },
      { selector: '[data-testid="analytics-dashboard"]', name: 'Analytics Dashboard' },
      { selector: '[data-testid="data-quality-dashboard"]', name: 'Data Quality Dashboard' },
      { selector: '[data-testid="performance-scorecard"]', name: 'Performance Scorecard' },
      { selector: '[data-testid="chart-container"]', name: 'Chart Container' },
      { selector: '[data-testid="order-panel"]', name: 'Order Panel' },
    ];

    criticalComponents.forEach(component => {
      test(`${component.name} component consistency`, async ({ page, browserName }) => {
        await page.goto('/dashboard');
        await page.waitForLoadState('networkidle');

        // Wait for component to be visible
        const componentLocator = page.locator(component.selector);

        if (await componentLocator.isVisible()) {
          // Disable animations
          await page.addStyleTag({
            content: `
              * {
                animation-duration: 0s !important;
                transition-duration: 0s !important;
              }
            `
          });

          await page.waitForTimeout(500);

          // Take component screenshot
          await expect(componentLocator).toHaveScreenshot(
            `component-${component.name.toLowerCase().replace(/\s+/g, '-')}-${browserName}.png`,
            {
              threshold: 0.1,
              animations: 'disabled'
            }
          );
        }
      });
    });
  });

  test.describe('Theme Consistency', () => {
    ['light', 'dark'].forEach(theme => {
      criticalPages.slice(0, 3).forEach(pageInfo => { // Test fewer pages for themes
        test(`${pageInfo.name} - ${theme} theme`, async ({ page, browserName }) => {
          await page.goto(pageInfo.url);
          await page.waitForLoadState('networkidle');

          // Set theme
          if (theme === 'dark') {
            await page.evaluate(() => {
              document.documentElement.classList.add('dark');
              document.body.classList.add('dark');
            });
          } else {
            await page.evaluate(() => {
              document.documentElement.classList.remove('dark');
              document.body.classList.remove('dark');
            });
          }

          // Wait for theme transition
          await page.waitForTimeout(1000);

          // Disable animations
          await page.addStyleTag({
            content: `
              * {
                animation-duration: 0s !important;
                transition-duration: 0s !important;
              }
            `
          });

          // Take screenshot
          await expect(page).toHaveScreenshot(
            `${pageInfo.key}-${theme}-theme-${browserName}.png`,
            {
              fullPage: true,
              threshold: 0.2,
              animations: 'disabled'
            }
          );
        });
      });
    });
  });

  test.describe('Interactive State Screenshots', () => {
    test('Modal and overlay states', async ({ page, browserName }) => {
      await page.goto('/trading');
      await page.waitForLoadState('networkidle');

      // Test modal states
      const modalTriggers = [
        '[data-testid="symbol-selector"]',
        '[data-testid="order-settings-button"]',
        '[data-testid="help-button"]',
      ];

      for (const trigger of modalTriggers) {
        if (await page.locator(trigger).isVisible()) {
          await page.click(trigger);
          await page.waitForTimeout(500);

          // Take screenshot of modal state
          await expect(page).toHaveScreenshot(
            `modal-${trigger.replace(/[\[\]"=-]/g, '').replace(/data-testid/g, '')}-${browserName}.png`,
            {
              fullPage: true,
              threshold: 0.1,
              animations: 'disabled'
            }
          );

          // Close modal
          await page.keyboard.press('Escape');
          await page.waitForTimeout(300);
        }
      }
    });

    test('Form validation states', async ({ page, browserName }) => {
      await page.goto('/trading');
      await page.waitForLoadState('networkidle');

      // Test form validation states
      if (await page.locator('[data-testid="order-panel"]').isVisible()) {
        // Enter invalid data to trigger validation
        await page.fill('[data-testid="order-size-input"]', '-100');
        await page.fill('[data-testid="price-input"]', 'invalid');

        // Trigger validation by attempting to submit
        if (await page.locator('[data-testid="place-order-button"]').isVisible()) {
          await page.click('[data-testid="place-order-button"]');
          await page.waitForTimeout(500);

          // Take screenshot of validation errors
          await expect(page.locator('[data-testid="order-panel"]')).toHaveScreenshot(
            `form-validation-errors-${browserName}.png`,
            {
              threshold: 0.1,
              animations: 'disabled'
            }
          );
        }
      }
    });

    test('Loading and empty states', async ({ page, browserName }) => {
      await page.goto('/data');
      await page.waitForLoadState('networkidle');

      // Test loading states by intercepting network requests
      await page.route('**/api/data/**', route => {
        // Delay the response to capture loading state
        setTimeout(() => route.continue(), 2000);
      });

      // Trigger data refresh to show loading state
      if (await page.locator('[data-testid="refresh-data-button"]').isVisible()) {
        await page.click('[data-testid="refresh-data-button"]');
        await page.waitForTimeout(500);

        // Take screenshot of loading state
        await expect(page).toHaveScreenshot(
          `loading-state-${browserName}.png`,
          {
            fullPage: true,
            threshold: 0.1,
            animations: 'disabled'
          }
        );
      }
    });
  });

  test.describe('Responsive Design Consistency', () => {
    test('Navigation responsiveness', async ({ page, browserName }) => {
      const mobileViewports = [
        { width: 768, height: 1024 },
        { width: 375, height: 667 },
        { width: 320, height: 568 },
      ];

      for (const viewport of mobileViewports) {
        await page.setViewportSize(viewport);
        await page.goto('/dashboard');
        await page.waitForLoadState('networkidle');

        // Check for mobile navigation
        if (await page.locator('[data-testid="mobile-menu-button"]').isVisible()) {
          // Test closed mobile menu
          await expect(page).toHaveScreenshot(
            `mobile-nav-closed-${viewport.width}x${viewport.height}-${browserName}.png`,
            {
              fullPage: true,
              threshold: 0.1,
              animations: 'disabled'
            }
          );

          // Test open mobile menu
          await page.click('[data-testid="mobile-menu-button"]');
          await page.waitForTimeout(500);

          await expect(page).toHaveScreenshot(
            `mobile-nav-open-${viewport.width}x${viewport.height}-${browserName}.png`,
            {
              fullPage: true,
              threshold: 0.1,
              animations: 'disabled'
            }
          );
        }
      }
    });

    test('Data table responsiveness', async ({ page, browserName }) => {
      await page.goto('/data');
      await page.waitForLoadState('networkidle');

      const testViewports = [
        { width: 1920, height: 1080, name: 'desktop' },
        { width: 768, height: 1024, name: 'tablet' },
        { width: 375, height: 667, name: 'mobile' },
      ];

      for (const viewport of testViewports) {
        await page.setViewportSize(viewport);
        await page.waitForTimeout(500);

        if (await page.locator('[data-testid="data-table"]').isVisible()) {
          await expect(page.locator('[data-testid="data-table"]')).toHaveScreenshot(
            `data-table-${viewport.name}-${browserName}.png`,
            {
              threshold: 0.1,
              animations: 'disabled'
            }
          );
        }
      }
    });
  });

  test.describe('Browser-Specific Rendering', () => {
    test('CSS Grid and Flexbox layouts', async ({ page, browserName }) => {
      await page.goto('/dashboard');
      await page.waitForLoadState('networkidle');

      // Test grid layouts
      const gridElements = page.locator('[class*="grid"]');
      const gridCount = await gridElements.count();

      if (gridCount > 0) {
        await expect(gridElements.first()).toHaveScreenshot(
          `grid-layout-${browserName}.png`,
          {
            threshold: 0.1,
            animations: 'disabled'
          }
        );
      }

      // Test flexbox layouts
      const flexElements = page.locator('[class*="flex"]');
      const flexCount = await flexElements.count();

      if (flexCount > 0) {
        await expect(flexElements.first()).toHaveScreenshot(
          `flex-layout-${browserName}.png`,
          {
            threshold: 0.1,
            animations: 'disabled'
          }
        );
      }
    });

    test('Chart rendering consistency', async ({ page, browserName }) => {
      await page.goto('/analytics');
      await page.waitForLoadState('networkidle');

      // Wait for charts to render
      await page.waitForTimeout(2000);

      const chartSelectors = [
        '[data-testid="performance-chart"]',
        '[data-testid="metrics-chart"]',
        '[data-testid="trend-chart"]',
      ];

      for (const selector of chartSelectors) {
        if (await page.locator(selector).isVisible()) {
          await expect(page.locator(selector)).toHaveScreenshot(
            `chart-${selector.replace(/[\[\]"=-]/g, '').replace(/data-testid/g, '')}-${browserName}.png`,
            {
              threshold: 0.2, // Charts may have slight rendering differences
              animations: 'disabled'
            }
          );
        }
      }
    });

    test('Font and text rendering', async ({ page, browserName }) => {
      await page.goto('/dashboard');
      await page.waitForLoadState('networkidle');

      // Test different text elements
      const textElements = [
        { selector: 'h1', name: 'heading-1' },
        { selector: 'h2', name: 'heading-2' },
        { selector: 'p', name: 'paragraph' },
        { selector: '[data-testid="metric-value"]', name: 'metric-value' },
        { selector: 'button', name: 'button-text' },
      ];

      for (const element of textElements) {
        const locator = page.locator(element.selector).first();
        if (await locator.isVisible()) {
          await expect(locator).toHaveScreenshot(
            `text-${element.name}-${browserName}.png`,
            {
              threshold: 0.1,
              animations: 'disabled'
            }
          );
        }
      }
    });
  });

  test.describe('Error State Screenshots', () => {
    test('Network error states', async ({ page, browserName }) => {
      // Simulate network errors
      await page.route('**/api/**', route => {
        route.fulfill({
          status: 500,
          contentType: 'application/json',
          body: JSON.stringify({ error: 'Internal Server Error' })
        });
      });

      await page.goto('/dashboard');
      await page.waitForLoadState('networkidle');
      await page.waitForTimeout(2000);

      // Take screenshot of error state
      await expect(page).toHaveScreenshot(
        `network-error-state-${browserName}.png`,
        {
          fullPage: true,
          threshold: 0.1,
          animations: 'disabled'
        }
      );
    });

    test('404 error page', async ({ page, browserName }) => {
      await page.goto('/nonexistent-page');
      await page.waitForLoadState('networkidle');

      await expect(page).toHaveScreenshot(
        `404-error-page-${browserName}.png`,
        {
          fullPage: true,
          threshold: 0.1,
          animations: 'disabled'
        }
      );
    });
  });
});
