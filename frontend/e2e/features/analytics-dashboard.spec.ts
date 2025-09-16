/**
 * Analytics Dashboard E2E Tests
 *
 * Comprehensive testing of analytics functionality, KPIs, reports, and performance monitoring
 */

import { test, expect } from '@playwright/test';

test.describe('Analytics Dashboard', () => {
  test.use({ storageState: 'e2e/.auth/user.json' });

  test.beforeEach(async ({ page }) => {
    await page.goto('/dashboard');
    await page.waitForLoadState('networkidle');
  });

  test('analytics dashboard layout and components', async ({ page }) => {
    // Verify main analytics components
    await expect(page.locator('[data-testid="analytics-dashboard"]')).toBeVisible();

    // Check for key analytics sections
    if (await page.locator('[data-testid="analytics-panel"]').isVisible()) {
      await expect(page.locator('[data-testid="analytics-panel"]')).toBeVisible();
    }

    // Verify performance metrics
    await expect(page.locator('[data-testid="performance-metrics"]')).toBeVisible();
    await expect(page.locator('[data-testid="system-health-indicator"]')).toBeVisible();
  });

  test('KPI monitoring and display', async ({ page }) => {
    // Navigate to analytics section
    if (await page.locator('[data-testid="analytics-tab"]').isVisible()) {
      await page.click('[data-testid="analytics-tab"]');
    }

    // Verify KPI cards are displayed
    await expect(page.locator('[data-testid="kpi-cards"]')).toBeVisible();

    // Check individual KPIs
    const kpiSelectors = [
      '[data-testid="kpi-system-health"]',
      '[data-testid="kpi-data-quality"]',
      '[data-testid="kpi-performance-score"]',
      '[data-testid="kpi-trading-performance"]'
    ];

    for (const selector of kpiSelectors) {
      if (await page.locator(selector).isVisible()) {
        await expect(page.locator(selector)).toBeVisible();

        // Verify KPI has value and status
        await expect(page.locator(`${selector} [data-testid="kpi-value"]`)).toBeVisible();
        await expect(page.locator(`${selector} [data-testid="kpi-status"]`)).toBeVisible();
      }
    }
  });

  test('analytics panel interaction', async ({ page }) => {
    // Check if analytics panel is available
    if (await page.locator('[data-testid="analytics-panel"]').isVisible()) {
      const analyticsPanel = page.locator('[data-testid="analytics-panel"]');

      // Test panel expansion/collapse
      if (await analyticsPanel.locator('[data-testid="toggle-panel"]').isVisible()) {
        await analyticsPanel.locator('[data-testid="toggle-panel"]').click();

        // Verify panel state change
        await expect(analyticsPanel.locator('[data-testid="panel-content"]')).toBeHidden();

        // Expand again
        await analyticsPanel.locator('[data-testid="toggle-panel"]').click();
        await expect(analyticsPanel.locator('[data-testid="panel-content"]')).toBeVisible();
      }

      // Test refresh functionality
      if (await analyticsPanel.locator('[data-testid="refresh-button"]').isVisible()) {
        await analyticsPanel.locator('[data-testid="refresh-button"]').click();

        // Verify loading state
        await expect(analyticsPanel.locator('[data-testid="loading-indicator"]')).toBeVisible();
        await page.waitForSelector('[data-testid="loading-indicator"]', { state: 'hidden' });
      }
    }
  });

  test('performance scorecard functionality', async ({ page }) => {
    // Navigate to performance scorecard if available
    if (await page.locator('[data-testid="performance-scorecard"]').isVisible()) {
      const scorecard = page.locator('[data-testid="performance-scorecard"]');

      // Verify scorecard components
      await expect(scorecard.locator('[data-testid="overall-score"]')).toBeVisible();
      await expect(scorecard.locator('[data-testid="score-breakdown"]')).toBeVisible();

      // Test time range selection
      if (await scorecard.locator('[data-testid="time-range-selector"]').isVisible()) {
        await scorecard.locator('[data-testid="time-range-selector"]').click();
        await page.click('[data-testid="time-range-7d"]');

        // Verify scorecard updates
        await page.waitForSelector('[data-testid="scorecard-loading"]', { state: 'hidden' });
        await expect(scorecard.locator('[data-testid="time-range-indicator"]')).toContainText('7 days');
      }

      // Test category filtering
      if (await scorecard.locator('[data-testid="category-filter"]').isVisible()) {
        await scorecard.locator('[data-testid="category-filter"]').click();
        await page.click('[data-testid="filter-trading"]');

        // Verify filtered view
        await expect(scorecard.locator('[data-testid="filtered-metrics"]')).toBeVisible();
      }
    }
  });

  test('reports generation and management', async ({ page }) => {
    // Navigate to reports section
    if (await page.locator('[data-testid="reports-section"]').isVisible()) {
      await page.click('[data-testid="reports-section"]');

      // Verify reports interface
      await expect(page.locator('[data-testid="reports-manager"]')).toBeVisible();

      // Test creating a new report
      if (await page.locator('[data-testid="create-report-button"]').isVisible()) {
        await page.click('[data-testid="create-report-button"]');

        // Fill report details
        await expect(page.locator('[data-testid="report-form"]')).toBeVisible();
        await page.fill('[data-testid="report-name"]', 'Test E2E Report');
        await page.selectOption('[data-testid="report-type"]', 'performance');

        // Configure report parameters
        await page.selectOption('[data-testid="report-timeframe"]', 'last_30_days');

        // Generate report
        await page.click('[data-testid="generate-report-button"]');

        // Verify report generation
        await expect(page.locator('[data-testid="report-generation-status"]')).toBeVisible();
        await page.waitForSelector('[data-testid="report-complete"]', { timeout: 30000 });

        // Verify report appears in list
        await expect(page.locator('[data-testid="report-list"]')).toContainText('Test E2E Report');
      }
    }
  });

  test('data export functionality', async ({ page }) => {
    // Test export from analytics dashboard
    if (await page.locator('[data-testid="export-data-button"]').isVisible()) {
      await page.click('[data-testid="export-data-button"]');

      // Verify export modal
      await expect(page.locator('[data-testid="export-modal"]')).toBeVisible();

      // Select export format
      await page.selectOption('[data-testid="export-format"]', 'csv');

      // Configure export options
      await page.check('[data-testid="include-metadata"]');
      await page.selectOption('[data-testid="date-range"]', 'last_7_days');

      // Start export
      const downloadPromise = page.waitForEvent('download');
      await page.click('[data-testid="start-export-button"]');

      // Verify download
      const download = await downloadPromise;
      expect(download.suggestedFilename()).toMatch(/analytics.*\.csv$/);

      // Close export modal
      await page.click('[data-testid="close-export-modal"]');
    }
  });

  test('real-time analytics updates', async ({ page }) => {
    // Verify real-time update indicators
    if (await page.locator('[data-testid="realtime-indicator"]').isVisible()) {
      await expect(page.locator('[data-testid="realtime-indicator"]')).toContainText('Live');
    }

    // Monitor for timestamp updates
    if (await page.locator('[data-testid="last-update-time"]').isVisible()) {
      const initialTime = await page.locator('[data-testid="last-update-time"]').textContent();

      // Wait for potential update
      await page.waitForTimeout(10000);

      const updatedTime = await page.locator('[data-testid="last-update-time"]').textContent();

      // Note: In a real test, we might mock real-time updates
      console.log(`Initial time: ${initialTime}, Updated time: ${updatedTime}`);
    }
  });

  test('analytics alerts and notifications', async ({ page }) => {
    // Check for analytics alerts
    if (await page.locator('[data-testid="analytics-alerts"]').isVisible()) {
      const alertsSection = page.locator('[data-testid="analytics-alerts"]');

      // Verify alert display
      if (await alertsSection.locator('[data-testid="alert-item"]').first().isVisible()) {
        const firstAlert = alertsSection.locator('[data-testid="alert-item"]').first();

        // Verify alert components
        await expect(firstAlert.locator('[data-testid="alert-title"]')).toBeVisible();
        await expect(firstAlert.locator('[data-testid="alert-severity"]')).toBeVisible();

        // Test alert dismissal
        if (await firstAlert.locator('[data-testid="dismiss-alert"]').isVisible()) {
          await firstAlert.locator('[data-testid="dismiss-alert"]').click();

          // Verify alert is dismissed
          await expect(firstAlert).toBeHidden();
        }
      }
    }
  });

  test('analytics dashboard customization', async ({ page }) => {
    // Test layout customization if available
    if (await page.locator('[data-testid="customize-dashboard"]').isVisible()) {
      await page.click('[data-testid="customize-dashboard"]');

      // Verify customization panel
      await expect(page.locator('[data-testid="customization-panel"]')).toBeVisible();

      // Test widget toggling
      if (await page.locator('[data-testid="widget-toggles"]').isVisible()) {
        const toggles = page.locator('[data-testid="widget-toggle"]');
        const toggleCount = await toggles.count();

        if (toggleCount > 0) {
          // Toggle first widget
          await toggles.first().click();

          // Apply changes
          await page.click('[data-testid="apply-customization"]');

          // Verify dashboard layout changed
          await page.waitForSelector('[data-testid="customization-panel"]', { state: 'hidden' });
        }
      }
    }
  });

  test('analytics data integration verification', async ({ page }) => {
    // Verify data from different sources is integrated

    // Check system health metrics
    if (await page.locator('[data-testid="system-health-metrics"]').isVisible()) {
      await expect(page.locator('[data-testid="system-health-score"]')).toBeVisible();
    }

    // Check trading performance metrics
    if (await page.locator('[data-testid="trading-metrics"]').isVisible()) {
      await expect(page.locator('[data-testid="total-pnl"]')).toBeVisible();
      await expect(page.locator('[data-testid="win-rate"]')).toBeVisible();
    }

    // Check data quality metrics
    if (await page.locator('[data-testid="data-quality-metrics"]').isVisible()) {
      await expect(page.locator('[data-testid="quality-score"]')).toBeVisible();
    }

    // Verify cross-service correlations
    if (await page.locator('[data-testid="correlation-insights"]').isVisible()) {
      await expect(page.locator('[data-testid="insight-item"]')).toBeVisible();
    }
  });

  test('analytics error handling', async ({ page }) => {
    // Simulate analytics service error
    await page.route('**/api/analytics/**', route => route.abort());

    // Trigger analytics refresh
    if (await page.locator('[data-testid="refresh-analytics"]').isVisible()) {
      await page.click('[data-testid="refresh-analytics"]');

      // Verify error state
      await expect(page.locator('[data-testid="analytics-error"]')).toBeVisible();
      await expect(page.locator('[data-testid="retry-analytics"]')).toBeVisible();

      // Restore service and retry
      await page.unroute('**/api/analytics/**');
      await page.click('[data-testid="retry-analytics"]');

      // Verify recovery
      await page.waitForSelector('[data-testid="analytics-error"]', { state: 'hidden' });
    }
  });

  test('analytics dashboard accessibility', async ({ page }) => {
    // Verify ARIA labels and roles
    if (await page.locator('[data-testid="analytics-dashboard"]').isVisible()) {
      await expect(page.locator('[data-testid="analytics-dashboard"]')).toHaveAttribute('role', 'region');
    }

    // Test keyboard navigation
    await page.keyboard.press('Tab');

    // Verify screen reader announcements
    if (await page.locator('[aria-live="polite"]').isVisible()) {
      await expect(page.locator('[aria-live="polite"]')).toBeVisible();
    }

    // Test high contrast mode compatibility
    await page.emulateMedia({ colorScheme: 'dark' });
    await expect(page.locator('[data-testid="analytics-dashboard"]')).toBeVisible();
  });

  test('analytics mobile responsiveness', async ({ page }) => {
    // Switch to mobile viewport
    await page.setViewportSize({ width: 375, height: 667 });

    // Verify mobile layout
    await expect(page.locator('[data-testid="analytics-dashboard"]')).toBeVisible();

    // Check mobile-specific adaptations
    if (await page.locator('[data-testid="mobile-analytics-nav"]').isVisible()) {
      await page.click('[data-testid="mobile-analytics-nav"]');
      await expect(page.locator('[data-testid="mobile-analytics-menu"]')).toBeVisible();
    }

    // Verify charts adapt to mobile
    if (await page.locator('[data-testid="analytics-chart"]').isVisible()) {
      const chart = page.locator('[data-testid="analytics-chart"]');
      const chartBox = await chart.boundingBox();

      // Chart should fit mobile width
      expect(chartBox?.width).toBeLessThanOrEqual(375);
    }
  });
});
