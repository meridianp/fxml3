/**
 * Cross-Browser Compatibility Tests
 *
 * Comprehensive testing across different browsers to ensure consistent behavior
 */

import { test, expect, devices } from '@playwright/test';

test.describe('Cross-Browser Compatibility', () => {
  test.use({ storageState: 'e2e/.auth/user.json' });

  const browsers = ['chromium', 'firefox', 'webkit'];
  const criticalPages = [
    { url: '/dashboard', name: 'Dashboard' },
    { url: '/trading', name: 'Trading Console' },
    { url: '/data', name: 'Data Management' },
    { url: '/training', name: 'ML Training' },
  ];

  test.describe('Core Functionality Across Browsers', () => {
    browsers.forEach(browserName => {
      test.describe(`${browserName} Browser Tests`, () => {
        test.use({
          ...devices[browserName === 'webkit' ? 'Desktop Safari' :
                     browserName === 'firefox' ? 'Desktop Firefox' : 'Desktop Chrome']
        });

        criticalPages.forEach(pageInfo => {
          test(`${pageInfo.name} - Basic functionality on ${browserName}`, async ({ page, browserName: currentBrowser }) => {
            console.log(`🌐 Testing ${pageInfo.name} on ${currentBrowser}`);

            // Navigate to page
            await page.goto(pageInfo.url);
            await page.waitForLoadState('networkidle');

            // Verify page loads successfully
            await expect(page).toHaveTitle(/FXML4/);

            // Verify core layout elements
            await expect(page.locator('[data-testid="app-layout"]')).toBeVisible();
            await expect(page.locator('[data-testid="header"]')).toBeVisible();
            await expect(page.locator('[data-testid="main-content"]')).toBeVisible();

            // Page-specific functionality tests
            switch (pageInfo.url) {
              case '/dashboard':
                await this.testDashboardFunctionality(page);
                break;
              case '/trading':
                await this.testTradingFunctionality(page);
                break;
              case '/data':
                await this.testDataManagementFunctionality(page);
                break;
              case '/training':
                await this.testMLTrainingFunctionality(page);
                break;
            }

            console.log(`✅ ${pageInfo.name} functional on ${currentBrowser}`);
          });
        });

        test(`Navigation consistency on ${browserName}`, async ({ page }) => {
          await page.goto('/dashboard');
          await page.waitForLoadState('networkidle');

          // Test navigation between pages
          const navItems = [
            { selector: '[data-testid="nav-trading"]', expectedUrl: '/trading' },
            { selector: '[data-testid="nav-data"]', expectedUrl: '/data' },
            { selector: '[data-testid="nav-training"]', expectedUrl: '/training' },
            { selector: '[data-testid="nav-dashboard"]', expectedUrl: '/dashboard' },
          ];

          for (const navItem of navItems) {
            if (await page.locator(navItem.selector).isVisible()) {
              await page.click(navItem.selector);
              await page.waitForLoadState('networkidle');
              await expect(page).toHaveURL(new RegExp(`.*${navItem.expectedUrl}`));
            }
          }
        });

        test(`Form interactions on ${browserName}`, async ({ page }) => {
          // Test form functionality across browsers
          await page.goto('/trading');
          await page.waitForLoadState('networkidle');

          // Test order form if available
          if (await page.locator('[data-testid="order-panel"]').isVisible()) {
            // Fill order size
            await page.fill('[data-testid="order-size-input"]', '1000');
            const orderSize = await page.locator('[data-testid="order-size-input"]').inputValue();
            expect(orderSize).toBe('1000');

            // Test dropdown selection
            if (await page.locator('[data-testid="order-type-selector"]').isVisible()) {
              await page.selectOption('[data-testid="order-type-selector"]', 'limit');
              const selectedValue = await page.locator('[data-testid="order-type-selector"]').inputValue();
              expect(selectedValue).toBe('limit');
            }

            // Test checkbox interaction
            if (await page.locator('[data-testid="enable-stop-loss"]').isVisible()) {
              await page.check('[data-testid="enable-stop-loss"]');
              await expect(page.locator('[data-testid="enable-stop-loss"]')).toBeChecked();
            }
          }
        });
      });
    });
  });

  test.describe('CSS and Styling Compatibility', () => {
    criticalPages.forEach(pageInfo => {
      test(`${pageInfo.name} - Layout consistency across browsers`, async ({ page, browserName }) => {
        await page.goto(pageInfo.url);
        await page.waitForLoadState('networkidle');

        // Check responsive grid layouts
        const gridElements = page.locator('[class*="grid"], [class*="flex"]');
        const gridCount = await gridElements.count();

        if (gridCount > 0) {
          for (let i = 0; i < Math.min(gridCount, 5); i++) {
            const element = gridElements.nth(i);
            await expect(element).toBeVisible();

            // Verify element has proper dimensions
            const boundingBox = await element.boundingBox();
            expect(boundingBox?.width).toBeGreaterThan(0);
            expect(boundingBox?.height).toBeGreaterThan(0);
          }
        }

        // Check for CSS animation support
        const animatedElements = page.locator('[class*="animate"], [class*="transition"]');
        const animatedCount = await animatedElements.count();

        if (animatedCount > 0) {
          // Verify animations don't break layout
          const firstAnimated = animatedElements.first();
          await expect(firstAnimated).toBeVisible();
        }

        // Verify color scheme consistency
        const primaryElements = page.locator('[class*="bg-blue"], [class*="text-blue"]');
        const primaryCount = await primaryElements.count();

        if (primaryCount > 0) {
          // Check that themed elements are properly styled
          await expect(primaryElements.first()).toBeVisible();
        }

        console.log(`✅ ${pageInfo.name} styling consistent on ${browserName}`);
      });
    });

    test('Dark mode compatibility', async ({ page, browserName }) => {
      await page.goto('/settings');
      await page.waitForLoadState('networkidle');

      // Toggle dark mode if available
      if (await page.locator('[data-testid="dark-mode-toggle"]').isVisible()) {
        await page.click('[data-testid="dark-mode-toggle"]');

        // Verify dark mode is applied
        const bodyClass = await page.getAttribute('body', 'class');
        expect(bodyClass).toContain('dark');

        // Check that dark mode styles are applied correctly
        const darkElements = page.locator('[class*="dark:"]');
        const darkCount = await darkElements.count();

        if (darkCount > 0) {
          await expect(darkElements.first()).toBeVisible();
        }

        console.log(`🌙 Dark mode working on ${browserName}`);
      }
    });
  });

  test.describe('JavaScript API Compatibility', () => {
    test('Modern JavaScript features', async ({ page, browserName }) => {
      await page.goto('/dashboard');
      await page.waitForLoadState('networkidle');

      // Test modern JS features are supported
      const jsFeatures = await page.evaluate(() => {
        const features = {
          asyncAwait: typeof async function() {} === 'function',
          destructuring: (() => { try { const {a} = {a: 1}; return true; } catch { return false; } })(),
          arrowFunctions: (() => { try { const f = () => true; return f(); } catch { return false; } })(),
          templateLiterals: (() => { try { const x = `test`; return true; } catch { return false; } })(),
          promises: typeof Promise !== 'undefined',
          fetch: typeof fetch !== 'undefined',
          localStorage: typeof localStorage !== 'undefined',
          sessionStorage: typeof sessionStorage !== 'undefined',
          websocket: typeof WebSocket !== 'undefined',
          intersectionObserver: typeof IntersectionObserver !== 'undefined'
        };
        return features;
      });

      // Verify essential features are supported
      expect(jsFeatures.promises).toBe(true);
      expect(jsFeatures.fetch).toBe(true);
      expect(jsFeatures.localStorage).toBe(true);
      expect(jsFeatures.websocket).toBe(true);

      console.log(`🔧 JavaScript features supported on ${browserName}:`, jsFeatures);
    });

    test('WebSocket compatibility', async ({ page, browserName }) => {
      await page.goto('/data');
      await page.waitForLoadState('networkidle');

      // Test WebSocket connection
      const wsSupport = await page.evaluate(() => {
        return typeof WebSocket !== 'undefined';
      });

      expect(wsSupport).toBe(true);

      // If WebSocket status indicator exists, check it
      if (await page.locator('[data-testid="websocket-status"]').isVisible()) {
        await expect(page.locator('[data-testid="websocket-status"]')).toBeVisible();

        // Wait for connection to establish
        await page.waitForTimeout(2000);

        const wsStatus = await page.locator('[data-testid="websocket-status"]').textContent();
        console.log(`🔌 WebSocket status on ${browserName}: ${wsStatus}`);
      }
    });

    test('Local storage and session storage', async ({ page, browserName }) => {
      await page.goto('/dashboard');
      await page.waitForLoadState('networkidle');

      // Test storage APIs
      const storageTest = await page.evaluate(() => {
        try {
          // Test localStorage
          localStorage.setItem('test', 'value');
          const localStorageWorks = localStorage.getItem('test') === 'value';
          localStorage.removeItem('test');

          // Test sessionStorage
          sessionStorage.setItem('test', 'value');
          const sessionStorageWorks = sessionStorage.getItem('test') === 'value';
          sessionStorage.removeItem('test');

          return {
            localStorage: localStorageWorks,
            sessionStorage: sessionStorageWorks
          };
        } catch (error) {
          return {
            localStorage: false,
            sessionStorage: false,
            error: error.message
          };
        }
      });

      expect(storageTest.localStorage).toBe(true);
      expect(storageTest.sessionStorage).toBe(true);

      console.log(`💾 Storage APIs working on ${browserName}`);
    });
  });

  test.describe('Performance Across Browsers', () => {
    criticalPages.forEach(pageInfo => {
      test(`${pageInfo.name} - Load performance on different browsers`, async ({ page, browserName }) => {
        const startTime = Date.now();

        await page.goto(pageInfo.url);
        await page.waitForLoadState('networkidle');

        const loadTime = Date.now() - startTime;

        // Performance expectations may vary by browser
        const maxLoadTime = browserName === 'webkit' ? 8000 : 6000; // Safari can be slower
        expect(loadTime).toBeLessThan(maxLoadTime);

        // Check for JavaScript errors
        const jsErrors: string[] = [];
        page.on('pageerror', error => {
          jsErrors.push(error.message);
        });

        // Trigger some interactions to check for errors
        if (await page.locator('[data-testid="refresh-button"]').isVisible()) {
          await page.click('[data-testid="refresh-button"]');
          await page.waitForTimeout(1000);
        }

        // Verify no JavaScript errors occurred
        expect(jsErrors.length).toBe(0);

        console.log(`⚡ ${pageInfo.name} loaded in ${loadTime}ms on ${browserName}`);
      });
    });
  });

  test.describe('Mobile Browser Compatibility', () => {
    const mobileDevices = [
      'iPhone 12',
      'iPhone 12 Pro',
      'Pixel 5',
      'Galaxy S21'
    ];

    mobileDevices.forEach(deviceName => {
      test(`Mobile compatibility - ${deviceName}`, async ({ browser }) => {
        const device = devices[deviceName];
        const context = await browser.newContext({
          ...device,
          locale: 'en-US'
        });
        const page = await context.newPage();

        try {
          await page.goto('/dashboard');
          await page.waitForLoadState('networkidle');

          // Verify responsive layout
          await expect(page.locator('[data-testid="app-layout"]')).toBeVisible();

          // Check for mobile-specific elements
          if (await page.locator('[data-testid="mobile-menu-button"]').isVisible()) {
            await page.click('[data-testid="mobile-menu-button"]');
            await expect(page.locator('[data-testid="mobile-menu"]')).toBeVisible();
          }

          // Test touch interactions
          const interactiveElements = page.locator('button, [role="button"]');
          const elementCount = await interactiveElements.count();

          if (elementCount > 0) {
            // Test first few interactive elements
            for (let i = 0; i < Math.min(elementCount, 3); i++) {
              const element = interactiveElements.nth(i);
              if (await element.isVisible()) {
                await element.tap();
                await page.waitForTimeout(500);
              }
            }
          }

          console.log(`📱 ${deviceName} compatibility verified`);

        } finally {
          await context.close();
        }
      });
    });
  });

  // Helper methods for page-specific testing
  async testDashboardFunctionality(page: any) {
    // Verify analytics components load
    if (await page.locator('[data-testid="analytics-dashboard"]').isVisible()) {
      await expect(page.locator('[data-testid="analytics-dashboard"]')).toBeVisible();
    }

    // Test dashboard interactions
    if (await page.locator('[data-testid="refresh-analytics"]').isVisible()) {
      await page.click('[data-testid="refresh-analytics"]');
      await page.waitForTimeout(1000);
    }
  }

  async testTradingFunctionality(page: any) {
    // Verify trading console loads
    await expect(page.locator('[data-testid="trading-console"]')).toBeVisible();

    // Test symbol selection
    if (await page.locator('[data-testid="symbol-selector"]').isVisible()) {
      await page.click('[data-testid="symbol-selector"]');
      await page.waitForTimeout(500);
      await page.keyboard.press('Escape');
    }
  }

  async testDataManagementFunctionality(page: any) {
    // Verify data management dashboard
    await expect(page.locator('[data-testid="data-management-dashboard"]')).toBeVisible();

    // Test data refresh
    if (await page.locator('[data-testid="refresh-data-button"]').isVisible()) {
      await page.click('[data-testid="refresh-data-button"]');
      await page.waitForTimeout(1000);
    }
  }

  async testMLTrainingFunctionality(page: any) {
    // Verify ML training studio
    await expect(page.locator('[data-testid="training-studio"]')).toBeVisible();

    // Test model configuration
    if (await page.locator('[data-testid="model-type-selector"]').isVisible()) {
      await page.click('[data-testid="model-type-selector"]');
      await page.waitForTimeout(500);
      await page.keyboard.press('Escape');
    }
  }
});
