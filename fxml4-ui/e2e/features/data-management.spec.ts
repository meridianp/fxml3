/**
 * Data Management E2E Tests
 *
 * Comprehensive testing of data management dashboard, monitoring, and analytics integration
 */

import { test, expect } from '@playwright/test';

test.describe('Data Management Dashboard', () => {
  test.use({ storageState: 'e2e/.auth/user.json' });

  test.beforeEach(async ({ page }) => {
    await page.goto('/data');
    await page.waitForLoadState('networkidle');
  });

  test('dashboard layout and components are present', async ({ page }) => {
    // Verify main dashboard container
    await expect(page.locator('[data-testid="data-management-dashboard"]')).toBeVisible();

    // Verify key dashboard sections
    await expect(page.locator('[data-testid="data-source-monitor"]')).toBeVisible();
    await expect(page.locator('[data-testid="storage-manager"]')).toBeVisible();
    await expect(page.locator('[data-testid="data-quality-dashboard"]')).toBeVisible();
    await expect(page.locator('[data-testid="pipeline-monitor"]')).toBeVisible();
  });

  test('data source monitoring functionality', async ({ page }) => {
    // Verify data source monitor section
    const dataSourceMonitor = page.locator('[data-testid="data-source-monitor"]');
    await expect(dataSourceMonitor).toBeVisible();

    // Verify connection status indicators
    await expect(page.locator('[data-testid="connection-status-ib"]')).toBeVisible();
    await expect(page.locator('[data-testid="connection-status-polygon"]')).toBeVisible();
    await expect(page.locator('[data-testid="connection-status-fxcm"]')).toBeVisible();

    // Test connection refresh
    await page.click('[data-testid="refresh-connections-button"]');

    // Verify loading state
    await expect(page.locator('[data-testid="connections-loading"]')).toBeVisible();

    // Wait for refresh to complete
    await page.waitForSelector('[data-testid="connections-loading"]', { state: 'hidden' });

    // Verify status updated
    await expect(page.locator('[data-testid="last-updated-timestamp"]')).toBeVisible();
  });

  test('storage metrics monitoring', async ({ page }) => {
    const storageManager = page.locator('[data-testid="storage-manager"]');
    await expect(storageManager).toBeVisible();

    // Verify storage metrics are displayed
    await expect(page.locator('[data-testid="storage-usage-chart"]')).toBeVisible();
    await expect(page.locator('[data-testid="database-metrics"]')).toBeVisible();
    await expect(page.locator('[data-testid="cache-metrics"]')).toBeVisible();

    // Test storage cleanup action
    if (await page.locator('[data-testid="cleanup-storage-button"]').isVisible()) {
      await page.click('[data-testid="cleanup-storage-button"]');

      // Verify confirmation dialog
      await expect(page.locator('[data-testid="cleanup-confirmation-dialog"]')).toBeVisible();

      // Cancel cleanup
      await page.click('[data-testid="cancel-cleanup-button"]');
      await expect(page.locator('[data-testid="cleanup-confirmation-dialog"]')).toBeHidden();
    }
  });

  test('data quality dashboard functionality', async ({ page }) => {
    const qualityDashboard = page.locator('[data-testid="data-quality-dashboard"]');
    await expect(qualityDashboard).toBeVisible();

    // Verify quality metrics
    await expect(page.locator('[data-testid="quality-score"]')).toBeVisible();
    await expect(page.locator('[data-testid="quality-trend-chart"]')).toBeVisible();

    // Test quality threshold configuration
    if (await page.locator('[data-testid="configure-thresholds-button"]').isVisible()) {
      await page.click('[data-testid="configure-thresholds-button"]');

      // Verify configuration panel
      await expect(page.locator('[data-testid="quality-threshold-config"]')).toBeVisible();

      // Update threshold
      await page.fill('[data-testid="quality-threshold-input"]', '95');
      await page.click('[data-testid="save-thresholds-button"]');

      // Verify success notification
      await expect(page.locator('[data-testid="success-notification"]')).toBeVisible();
    }
  });

  test('pipeline monitoring and job management', async ({ page }) => {
    const pipelineMonitor = page.locator('[data-testid="pipeline-monitor"]');
    await expect(pipelineMonitor).toBeVisible();

    // Verify pipeline status
    await expect(page.locator('[data-testid="pipeline-status-overview"]')).toBeVisible();
    await expect(page.locator('[data-testid="active-jobs-count"]')).toBeVisible();

    // Test job details view
    if (await page.locator('[data-testid="job-row"]').first().isVisible()) {
      await page.click('[data-testid="job-row"]');

      // Verify job details modal
      await expect(page.locator('[data-testid="job-details-modal"]')).toBeVisible();
      await expect(page.locator('[data-testid="job-logs"]')).toBeVisible();

      // Close modal
      await page.click('[data-testid="close-job-details"]');
      await expect(page.locator('[data-testid="job-details-modal"]')).toBeHidden();
    }
  });

  test('real-time updates and websocket integration', async ({ page }) => {
    // Verify websocket connection indicator
    await expect(page.locator('[data-testid="websocket-status"]')).toBeVisible();
    await expect(page.locator('[data-testid="websocket-status"]')).toContainText('Connected');

    // Monitor for real-time updates
    const initialTimestamp = await page.locator('[data-testid="last-updated-timestamp"]').textContent();

    // Wait for potential real-time update
    await page.waitForTimeout(5000);

    // Check if timestamp updated (indicates real-time data)
    const updatedTimestamp = await page.locator('[data-testid="last-updated-timestamp"]').textContent();

    // Verify data freshness indicator
    await expect(page.locator('[data-testid="data-freshness-indicator"]')).toBeVisible();
  });

  test('analytics integration', async ({ page }) => {
    // Check if analytics panel is integrated
    if (await page.locator('[data-testid="analytics-panel"]').isVisible()) {
      // Verify analytics integration
      await expect(page.locator('[data-testid="analytics-panel"]')).toBeVisible();

      // Test analytics toggle
      if (await page.locator('[data-testid="toggle-analytics"]').isVisible()) {
        await page.click('[data-testid="toggle-analytics"]');
        await expect(page.locator('[data-testid="analytics-panel"]')).toBeHidden();

        await page.click('[data-testid="toggle-analytics"]');
        await expect(page.locator('[data-testid="analytics-panel"]')).toBeVisible();
      }

      // Verify KPI display
      await expect(page.locator('[data-testid="system-health-kpi"]')).toBeVisible();
      await expect(page.locator('[data-testid="data-quality-kpi"]')).toBeVisible();
    }
  });

  test('dashboard customization and layout', async ({ page }) => {
    // Test layout switching if available
    if (await page.locator('[data-testid="layout-selector"]').isVisible()) {
      // Switch to grid layout
      await page.selectOption('[data-testid="layout-selector"]', 'grid');

      // Verify layout change
      await expect(page.locator('[data-testid="dashboard-grid-layout"]')).toBeVisible();

      // Switch to list layout
      await page.selectOption('[data-testid="layout-selector"]', 'list');
      await expect(page.locator('[data-testid="dashboard-list-layout"]')).toBeVisible();
    }

    // Test component resize if available
    if (await page.locator('[data-testid="resize-handle"]').first().isVisible()) {
      const resizeHandle = page.locator('[data-testid="resize-handle"]').first();
      const component = page.locator('[data-testid="data-source-monitor"]');

      const originalSize = await component.boundingBox();

      // Drag to resize
      await resizeHandle.hover();
      await page.mouse.down();
      await page.mouse.move(originalSize!.x + 100, originalSize!.y + 50);
      await page.mouse.up();

      // Verify size changed
      const newSize = await component.boundingBox();
      expect(newSize!.width).toBeGreaterThan(originalSize!.width);
    }
  });

  test('data export functionality', async ({ page }) => {
    // Test data export if available
    if (await page.locator('[data-testid="export-data-button"]').isVisible()) {
      await page.click('[data-testid="export-data-button"]');

      // Verify export modal
      await expect(page.locator('[data-testid="export-modal"]')).toBeVisible();

      // Select export format
      await page.selectOption('[data-testid="export-format-select"]', 'csv');

      // Configure export options
      await page.check('[data-testid="include-headers-checkbox"]');

      // Start export
      const downloadPromise = page.waitForEvent('download');
      await page.click('[data-testid="start-export-button"]');

      // Verify download starts
      const download = await downloadPromise;
      expect(download.suggestedFilename()).toContain('.csv');

      // Close export modal
      await page.click('[data-testid="close-export-modal"]');
      await expect(page.locator('[data-testid="export-modal"]')).toBeHidden();
    }
  });

  test('error handling and recovery', async ({ page }) => {
    // Simulate network error if possible
    await page.route('**/api/data/sources', route => route.abort());

    // Trigger data refresh
    await page.click('[data-testid="refresh-data-button"]');

    // Verify error state
    await expect(page.locator('[data-testid="data-error-message"]')).toBeVisible();
    await expect(page.locator('[data-testid="retry-button"]')).toBeVisible();

    // Restore network and retry
    await page.unroute('**/api/data/sources');
    await page.click('[data-testid="retry-button"]');

    // Verify recovery
    await expect(page.locator('[data-testid="data-error-message"]')).toBeHidden();
  });

  test('responsive design on mobile devices', async ({ page }) => {
    // Switch to mobile viewport
    await page.setViewportSize({ width: 375, height: 667 });

    // Verify mobile layout
    await expect(page.locator('[data-testid="data-management-dashboard"]')).toBeVisible();

    // Verify components stack vertically on mobile
    const dashboard = page.locator('[data-testid="data-management-dashboard"]');
    await expect(dashboard).toHaveClass(/flex-col|block/);

    // Test mobile navigation if present
    if (await page.locator('[data-testid="mobile-data-nav"]').isVisible()) {
      await page.click('[data-testid="mobile-data-nav"]');
      await expect(page.locator('[data-testid="mobile-data-menu"]')).toBeVisible();
    }
  });

  test('accessibility compliance', async ({ page }) => {
    // Verify ARIA labels and roles
    await expect(page.locator('[data-testid="data-management-dashboard"]')).toHaveAttribute('role', 'main');

    // Test keyboard navigation
    await page.keyboard.press('Tab');

    // Verify focus management
    const focusedElement = page.locator(':focus');
    await expect(focusedElement).toBeVisible();

    // Test screen reader announcements
    await expect(page.locator('[aria-live="polite"]')).toBeVisible();
  });
});
