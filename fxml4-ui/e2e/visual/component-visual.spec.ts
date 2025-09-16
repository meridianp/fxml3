/**
 * Component-Level Visual Regression Tests
 *
 * Focused testing of individual components for visual consistency
 */

import { test, expect } from '@playwright/test';
import { VisualTestHelper, getPageSelectors } from './visual-utils';
import { getVisualConfig } from './visual-config';

test.describe('Component Visual Regression', () => {
  test.use({ storageState: 'e2e/.auth/user.json' });

  let visualHelper: VisualTestHelper;
  const config = getVisualConfig(process.env.CI ? 'ci' : 'comprehensive');

  test.beforeEach(async ({ page }) => {
    visualHelper = new VisualTestHelper(page, config);
  });

  test.describe('Header and Navigation Components', () => {
    test('App header consistency', async ({ page, browserName }) => {
      await visualHelper.navigateAndWait('/dashboard');

      const headerSelector = '[data-testid="app-header"]';
      if (await page.locator(headerSelector).isVisible()) {
        await visualHelper.takeComponentScreenshot(
          headerSelector,
          `header-${browserName}.png`
        );
      }
    });

    test('Navigation sidebar states', async ({ page, browserName }) => {
      await visualHelper.navigateAndWait('/dashboard');

      const navSelector = '[data-testid="navigation-sidebar"]';
      if (await page.locator(navSelector).isVisible()) {
        // Test collapsed state
        await visualHelper.takeComponentScreenshot(
          navSelector,
          `nav-sidebar-default-${browserName}.png`
        );

        // Test expanded state (if applicable)
        const expandButton = page.locator('[data-testid="nav-expand-button"]');
        if (await expandButton.isVisible()) {
          await expandButton.click();
          await page.waitForTimeout(500);

          await visualHelper.takeComponentScreenshot(
            navSelector,
            `nav-sidebar-expanded-${browserName}.png`
          );
        }
      }
    });

    test('Mobile navigation menu', async ({ page, browserName }) => {
      // Test on mobile viewport
      await page.setViewportSize({ width: 375, height: 667 });
      await visualHelper.navigateAndWait('/dashboard');

      const mobileMenuButton = page.locator('[data-testid="mobile-menu-button"]');
      if (await mobileMenuButton.isVisible()) {
        // Test closed state
        await visualHelper.takeComponentScreenshot(
          '[data-testid="app-header"]',
          `mobile-header-closed-${browserName}.png`
        );

        // Test open state
        await mobileMenuButton.click();
        await page.waitForTimeout(500);

        const mobileMenu = page.locator('[data-testid="mobile-menu"]');
        if (await mobileMenu.isVisible()) {
          await visualHelper.takeComponentScreenshot(
            mobileMenu,
            `mobile-menu-open-${browserName}.png`
          );
        }
      }
    });
  });

  test.describe('Dashboard Components', () => {
    test('Analytics dashboard widget', async ({ page, browserName }) => {
      await visualHelper.navigateAndWait('/dashboard');
      await visualHelper.waitForChartsToRender();

      const analyticsSelector = '[data-testid="analytics-dashboard"]';
      if (await page.locator(analyticsSelector).isVisible()) {
        await visualHelper.takeComponentScreenshot(
          analyticsSelector,
          `analytics-widget-${browserName}.png`
        );
      }
    });

    test('Performance scorecard', async ({ page, browserName }) => {
      await visualHelper.navigateAndWait('/dashboard');

      const scorecardSelector = '[data-testid="performance-scorecard"]';
      if (await page.locator(scorecardSelector).isVisible()) {
        await visualHelper.takeComponentScreenshot(
          scorecardSelector,
          `performance-scorecard-${browserName}.png`
        );
      }
    });

    test('Data quality metrics', async ({ page, browserName }) => {
      await visualHelper.navigateAndWait('/dashboard');

      const qualitySelector = '[data-testid="data-quality-dashboard"]';
      if (await page.locator(qualitySelector).isVisible()) {
        await visualHelper.takeComponentScreenshot(
          qualitySelector,
          `data-quality-metrics-${browserName}.png`
        );
      }
    });

    test('Chart containers', async ({ page, browserName }) => {
      await visualHelper.navigateAndWait('/dashboard');
      await visualHelper.waitForChartsToRender();

      const chartSelector = '[data-testid="chart-container"]';
      const charts = page.locator(chartSelector);
      const chartCount = await charts.count();

      for (let i = 0; i < Math.min(chartCount, 3); i++) {
        const chart = charts.nth(i);
        if (await chart.isVisible()) {
          await visualHelper.takeComponentScreenshot(
            chart,
            `chart-${i}-${browserName}.png`
          );
        }
      }
    });
  });

  test.describe('Trading Console Components', () => {
    test('Order panel', async ({ page, browserName }) => {
      await visualHelper.navigateAndWait('/trading');

      const orderPanelSelector = '[data-testid="order-panel"]';
      if (await page.locator(orderPanelSelector).isVisible()) {
        await visualHelper.takeComponentScreenshot(
          orderPanelSelector,
          `order-panel-${browserName}.png`
        );
      }
    });

    test('Symbol selector', async ({ page, browserName }) => {
      await visualHelper.navigateAndWait('/trading');

      const symbolSelector = '[data-testid="symbol-selector"]';
      if (await page.locator(symbolSelector).isVisible()) {
        // Test closed state
        await visualHelper.takeComponentScreenshot(
          symbolSelector,
          `symbol-selector-closed-${browserName}.png`
        );

        // Test open state
        await page.click(symbolSelector);
        await page.waitForTimeout(500);

        const dropdown = page.locator('[data-testid="symbol-dropdown"]');
        if (await dropdown.isVisible()) {
          await visualHelper.takeComponentScreenshot(
            dropdown,
            `symbol-selector-open-${browserName}.png`
          );
        }

        // Close dropdown
        await page.keyboard.press('Escape');
      }
    });

    test('Price chart', async ({ page, browserName }) => {
      await visualHelper.navigateAndWait('/trading');
      await visualHelper.waitForChartsToRender();

      const chartSelector = '[data-testid="price-chart"]';
      if (await page.locator(chartSelector).isVisible()) {
        await visualHelper.takeComponentScreenshot(
          chartSelector,
          `price-chart-${browserName}.png`
        );
      }
    });

    test('Order book', async ({ page, browserName }) => {
      await visualHelper.navigateAndWait('/trading');

      const orderBookSelector = '[data-testid="order-book"]';
      if (await page.locator(orderBookSelector).isVisible()) {
        await visualHelper.takeComponentScreenshot(
          orderBookSelector,
          `order-book-${browserName}.png`
        );
      }
    });
  });

  test.describe('Data Management Components', () => {
    test('Data source monitor', async ({ page, browserName }) => {
      await visualHelper.navigateAndWait('/data');

      const monitorSelector = '[data-testid="data-source-monitor"]';
      if (await page.locator(monitorSelector).isVisible()) {
        await visualHelper.takeComponentScreenshot(
          monitorSelector,
          `data-source-monitor-${browserName}.png`
        );
      }
    });

    test('Storage manager', async ({ page, browserName }) => {
      await visualHelper.navigateAndWait('/data');

      const storageSelector = '[data-testid="storage-manager"]';
      if (await page.locator(storageSelector).isVisible()) {
        await visualHelper.takeComponentScreenshot(
          storageSelector,
          `storage-manager-${browserName}.png`
        );
      }
    });

    test('Data table', async ({ page, browserName }) => {
      await visualHelper.navigateAndWait('/data');

      const tableSelector = '[data-testid="data-table"]';
      if (await page.locator(tableSelector).isVisible()) {
        await visualHelper.takeComponentScreenshot(
          tableSelector,
          `data-table-${browserName}.png`
        );
      }
    });
  });

  test.describe('Form Components', () => {
    test('Form input states', async ({ page, browserName }) => {
      await visualHelper.navigateAndWait('/trading');

      // Test various input states
      const inputSelector = '[data-testid="order-size-input"]';
      if (await page.locator(inputSelector).isVisible()) {
        // Default state
        await visualHelper.takeComponentScreenshot(
          inputSelector,
          `input-default-${browserName}.png`
        );

        // Focused state
        await page.focus(inputSelector);
        await page.waitForTimeout(200);
        await visualHelper.takeComponentScreenshot(
          inputSelector,
          `input-focused-${browserName}.png`
        );

        // Filled state
        await page.fill(inputSelector, '1000');
        await visualHelper.takeComponentScreenshot(
          inputSelector,
          `input-filled-${browserName}.png`
        );

        // Error state (invalid value)
        await page.fill(inputSelector, '-100');
        await page.click('[data-testid="place-order-button"]');
        await page.waitForTimeout(500);
        await visualHelper.takeComponentScreenshot(
          inputSelector,
          `input-error-${browserName}.png`
        );
      }
    });

    test('Button states', async ({ page, browserName }) => {
      await visualHelper.navigateAndWait('/trading');

      const buttonSelector = '[data-testid="place-order-button"]';
      if (await page.locator(buttonSelector).isVisible()) {
        // Default state
        await visualHelper.takeComponentScreenshot(
          buttonSelector,
          `button-default-${browserName}.png`
        );

        // Hover state
        await page.hover(buttonSelector);
        await page.waitForTimeout(200);
        await visualHelper.takeComponentScreenshot(
          buttonSelector,
          `button-hover-${browserName}.png`
        );

        // Focus state
        await page.focus(buttonSelector);
        await page.waitForTimeout(200);
        await visualHelper.takeComponentScreenshot(
          buttonSelector,
          `button-focused-${browserName}.png`
        );
      }
    });

    test('Dropdown states', async ({ page, browserName }) => {
      await visualHelper.navigateAndWait('/trading');

      const dropdownSelector = '[data-testid="order-type-selector"]';
      if (await page.locator(dropdownSelector).isVisible()) {
        // Closed state
        await visualHelper.takeComponentScreenshot(
          dropdownSelector,
          `dropdown-closed-${browserName}.png`
        );

        // Open state
        await page.click(dropdownSelector);
        await page.waitForTimeout(300);

        const dropdownMenu = page.locator('[data-testid="order-type-menu"]');
        if (await dropdownMenu.isVisible()) {
          await visualHelper.takeComponentScreenshot(
            dropdownMenu,
            `dropdown-open-${browserName}.png`
          );
        }
      }
    });
  });

  test.describe('Modal and Dialog Components', () => {
    test('Modal dialog', async ({ page, browserName }) => {
      await visualHelper.navigateAndWait('/settings');

      const modalTrigger = '[data-testid="settings-modal-trigger"]';
      if (await page.locator(modalTrigger).isVisible()) {
        await page.click(modalTrigger);
        await page.waitForTimeout(500);

        const modal = page.locator('[data-testid="settings-modal"]');
        if (await modal.isVisible()) {
          await visualHelper.takeComponentScreenshot(
            modal,
            `settings-modal-${browserName}.png`
          );
        }
      }
    });

    test('Confirmation dialog', async ({ page, browserName }) => {
      await visualHelper.navigateAndWait('/trading');

      // Trigger confirmation dialog
      const deleteButton = '[data-testid="delete-order-button"]';
      if (await page.locator(deleteButton).isVisible()) {
        await page.click(deleteButton);
        await page.waitForTimeout(300);

        const confirmDialog = page.locator('[data-testid="confirm-dialog"]');
        if (await confirmDialog.isVisible()) {
          await visualHelper.takeComponentScreenshot(
            confirmDialog,
            `confirm-dialog-${browserName}.png`
          );
        }
      }
    });
  });

  test.describe('Loading and Empty States', () => {
    test('Loading spinner', async ({ page, browserName }) => {
      // Intercept API calls to create loading state
      await page.route('**/api/data/**', route => {
        setTimeout(() => route.continue(), 2000);
      });

      await visualHelper.navigateAndWait('/data');

      // Trigger loading state
      if (await page.locator('[data-testid="refresh-data-button"]').isVisible()) {
        await page.click('[data-testid="refresh-data-button"]');
        await page.waitForTimeout(500);

        const loader = page.locator('[data-testid="loading-spinner"]');
        if (await loader.isVisible()) {
          await visualHelper.takeComponentScreenshot(
            loader,
            `loading-spinner-${browserName}.png`
          );
        }
      }
    });

    test('Empty state message', async ({ page, browserName }) => {
      // Mock empty data response
      await page.route('**/api/data/**', route => {
        route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({ data: [], total: 0 })
        });
      });

      await visualHelper.navigateAndWait('/data');
      await page.waitForTimeout(1000);

      const emptyState = page.locator('[data-testid="empty-state"]');
      if (await emptyState.isVisible()) {
        await visualHelper.takeComponentScreenshot(
          emptyState,
          `empty-state-${browserName}.png`
        );
      }
    });
  });

  test.describe('Responsive Component Behavior', () => {
    const viewports = [
      { width: 1920, height: 1080, name: 'desktop' },
      { width: 768, height: 1024, name: 'tablet' },
      { width: 375, height: 667, name: 'mobile' }
    ];

    test('Responsive navigation', async ({ page, browserName }) => {
      for (const viewport of viewports) {
        await page.setViewportSize(viewport);
        await visualHelper.navigateAndWait('/dashboard');

        const navSelector = viewport.width >= 768 ?
          '[data-testid="navigation-sidebar"]' :
          '[data-testid="mobile-navigation"]';

        if (await page.locator(navSelector).isVisible()) {
          await visualHelper.takeComponentScreenshot(
            navSelector,
            `nav-${viewport.name}-${browserName}.png`
          );
        }
      }
    });

    test('Responsive order panel', async ({ page, browserName }) => {
      for (const viewport of viewports) {
        await page.setViewportSize(viewport);
        await visualHelper.navigateAndWait('/trading');

        const orderPanel = '[data-testid="order-panel"]';
        if (await page.locator(orderPanel).isVisible()) {
          await visualHelper.takeComponentScreenshot(
            orderPanel,
            `order-panel-${viewport.name}-${browserName}.png`
          );
        }
      }
    });
  });
});
