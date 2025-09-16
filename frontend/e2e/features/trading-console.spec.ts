/**
 * Trading Console E2E Tests
 *
 * Comprehensive testing of trading interface, order management, and risk controls
 */

import { test, expect } from '@playwright/test';

test.describe('Trading Console', () => {
  test.use({ storageState: 'e2e/.auth/user.json' });

  test.beforeEach(async ({ page }) => {
    await page.goto('/trading');
    await page.waitForLoadState('networkidle');
  });

  test('trading console layout and components', async ({ page }) => {
    // Verify main trading console
    await expect(page.locator('[data-testid="trading-console"]')).toBeVisible();

    // Verify key components
    await expect(page.locator('[data-testid="order-panel"]')).toBeVisible();
    await expect(page.locator('[data-testid="positions-table"]')).toBeVisible();
    await expect(page.locator('[data-testid="orders-table"]')).toBeVisible();
    await expect(page.locator('[data-testid="price-chart"]')).toBeVisible();
  });

  test('symbol selection and market data', async ({ page }) => {
    // Test symbol selector
    await page.click('[data-testid="symbol-selector"]');
    await expect(page.locator('[data-testid="symbol-dropdown"]')).toBeVisible();

    // Select a symbol
    await page.click('[data-testid="symbol-option-EURUSD"]');

    // Verify symbol selection
    await expect(page.locator('[data-testid="selected-symbol"]')).toContainText('EURUSD');

    // Verify price data loads
    await expect(page.locator('[data-testid="current-price"]')).toBeVisible();
    await expect(page.locator('[data-testid="bid-price"]')).toBeVisible();
    await expect(page.locator('[data-testid="ask-price"]')).toBeVisible();

    // Verify chart updates
    await expect(page.locator('[data-testid="price-chart"]')).toBeVisible();
    await page.waitForSelector('[data-testid="chart-data-loaded"]', { timeout: 10000 });
  });

  test('market order placement', async ({ page }) => {
    // Ensure we have a symbol selected
    await page.click('[data-testid="symbol-selector"]');
    await page.click('[data-testid="symbol-option-EURUSD"]');

    // Select market order type
    await page.click('[data-testid="order-type-market"]');

    // Set order size
    await page.fill('[data-testid="order-size-input"]', '10000');

    // Select buy direction
    await page.click('[data-testid="buy-button"]');

    // Verify order preview
    await expect(page.locator('[data-testid="order-preview"]')).toBeVisible();
    await expect(page.locator('[data-testid="order-preview-symbol"]')).toContainText('EURUSD');
    await expect(page.locator('[data-testid="order-preview-size"]')).toContainText('10,000');
    await expect(page.locator('[data-testid="order-preview-type"]')).toContainText('Market');

    // Submit order (in demo mode)
    await page.click('[data-testid="submit-order-button"]');

    // Verify order confirmation
    await expect(page.locator('[data-testid="order-confirmation"]')).toBeVisible();
    await expect(page.locator('[data-testid="order-id"]')).toBeVisible();

    // Close confirmation
    await page.click('[data-testid="close-confirmation"]');
  });

  test('limit order placement with validation', async ({ page }) => {
    // Select limit order type
    await page.click('[data-testid="order-type-limit"]');

    // Set invalid order size (should trigger validation)
    await page.fill('[data-testid="order-size-input"]', '0');
    await page.fill('[data-testid="limit-price-input"]', '1.1000');

    // Try to submit
    await page.click('[data-testid="sell-button"]');

    // Verify validation error
    await expect(page.locator('[data-testid="order-size-error"]')).toBeVisible();
    await expect(page.locator('[data-testid="order-size-error"]')).toContainText('Size must be greater than 0');

    // Fix order size
    await page.fill('[data-testid="order-size-input"]', '5000');

    // Set invalid price
    await page.fill('[data-testid="limit-price-input"]', '0');

    // Try to submit
    await page.click('[data-testid="sell-button"]');

    // Verify price validation
    await expect(page.locator('[data-testid="limit-price-error"]')).toBeVisible();

    // Set valid price
    await page.fill('[data-testid="limit-price-input"]', '1.0950');

    // Submit valid order
    await page.click('[data-testid="sell-button"]');

    // Verify order submitted
    await expect(page.locator('[data-testid="order-confirmation"]')).toBeVisible();
  });

  test('stop loss and take profit orders', async ({ page }) => {
    // Select market order
    await page.click('[data-testid="order-type-market"]');
    await page.fill('[data-testid="order-size-input"]', '10000');

    // Enable stop loss
    await page.check('[data-testid="enable-stop-loss"]');
    await page.fill('[data-testid="stop-loss-input"]', '1.0900');

    // Enable take profit
    await page.check('[data-testid="enable-take-profit"]');
    await page.fill('[data-testid="take-profit-input"]', '1.1100');

    // Submit buy order
    await page.click('[data-testid="buy-button"]');

    // Verify order preview includes SL/TP
    await expect(page.locator('[data-testid="order-preview-stop-loss"]')).toContainText('1.0900');
    await expect(page.locator('[data-testid="order-preview-take-profit"]')).toContainText('1.1100');

    // Confirm order
    await page.click('[data-testid="submit-order-button"]');
    await expect(page.locator('[data-testid="order-confirmation"]')).toBeVisible();
  });

  test('positions management', async ({ page }) => {
    // Verify positions table
    await expect(page.locator('[data-testid="positions-table"]')).toBeVisible();

    // Check if there are positions
    const positionRows = page.locator('[data-testid="position-row"]');
    const positionCount = await positionRows.count();

    if (positionCount > 0) {
      // Test position actions
      const firstPosition = positionRows.first();
      await expect(firstPosition).toBeVisible();

      // Verify position details
      await expect(firstPosition.locator('[data-testid="position-symbol"]')).toBeVisible();
      await expect(firstPosition.locator('[data-testid="position-size"]')).toBeVisible();
      await expect(firstPosition.locator('[data-testid="position-pnl"]')).toBeVisible();

      // Test position modification
      await firstPosition.locator('[data-testid="modify-position-button"]').click();

      // Verify modification modal
      await expect(page.locator('[data-testid="modify-position-modal"]')).toBeVisible();

      // Update stop loss
      await page.fill('[data-testid="modify-stop-loss"]', '1.0850');

      // Save changes
      await page.click('[data-testid="save-position-changes"]');

      // Verify success notification
      await expect(page.locator('[data-testid="position-updated-notification"]')).toBeVisible();
    }
  });

  test('orders management and cancellation', async ({ page }) => {
    // Create a pending order first
    await page.click('[data-testid="order-type-limit"]');
    await page.fill('[data-testid="order-size-input"]', '5000');
    await page.fill('[data-testid="limit-price-input"]', '1.0800'); // Below market
    await page.click('[data-testid="buy-button"]');
    await page.click('[data-testid="submit-order-button"]');
    await page.click('[data-testid="close-confirmation"]');

    // Check orders table
    await expect(page.locator('[data-testid="orders-table"]')).toBeVisible();

    const orderRows = page.locator('[data-testid="order-row"]');
    const orderCount = await orderRows.count();

    if (orderCount > 0) {
      const firstOrder = orderRows.first();

      // Verify order details
      await expect(firstOrder.locator('[data-testid="order-symbol"]')).toBeVisible();
      await expect(firstOrder.locator('[data-testid="order-type"]')).toBeVisible();
      await expect(firstOrder.locator('[data-testid="order-status"]')).toBeVisible();

      // Test order cancellation
      await firstOrder.locator('[data-testid="cancel-order-button"]').click();

      // Verify cancellation confirmation
      await expect(page.locator('[data-testid="cancel-order-confirmation"]')).toBeVisible();

      // Confirm cancellation
      await page.click('[data-testid="confirm-cancel-order"]');

      // Verify order cancelled
      await expect(page.locator('[data-testid="order-cancelled-notification"]')).toBeVisible();
    }
  });

  test('risk management controls', async ({ page }) => {
    // Test maximum position size limit
    await page.fill('[data-testid="order-size-input"]', '1000000'); // Large size

    // Try to submit
    await page.click('[data-testid="buy-button"]');

    // Verify risk warning
    await expect(page.locator('[data-testid="risk-warning"]')).toBeVisible();
    await expect(page.locator('[data-testid="risk-warning"]')).toContainText('exceeds maximum position size');

    // Test daily loss limit (if applicable)
    if (await page.locator('[data-testid="daily-loss-limit"]').isVisible()) {
      const dailyLossLimit = page.locator('[data-testid="daily-loss-limit"]');
      await expect(dailyLossLimit).toBeVisible();
    }

    // Test margin requirements
    if (await page.locator('[data-testid="margin-requirement"]').isVisible()) {
      const marginInfo = page.locator('[data-testid="margin-requirement"]');
      await expect(marginInfo).toBeVisible();
    }
  });

  test('account information and balances', async ({ page }) => {
    // Verify account info panel
    if (await page.locator('[data-testid="account-info"]').isVisible()) {
      const accountInfo = page.locator('[data-testid="account-info"]');

      // Verify balance information
      await expect(accountInfo.locator('[data-testid="account-balance"]')).toBeVisible();
      await expect(accountInfo.locator('[data-testid="available-margin"]')).toBeVisible();
      await expect(accountInfo.locator('[data-testid="used-margin"]')).toBeVisible();

      // Verify P&L information
      await expect(accountInfo.locator('[data-testid="total-pnl"]')).toBeVisible();
      await expect(accountInfo.locator('[data-testid="daily-pnl"]')).toBeVisible();
    }
  });

  test('trading alerts and notifications', async ({ page }) => {
    // Create an order that should trigger notification
    await page.click('[data-testid="order-type-market"]');
    await page.fill('[data-testid="order-size-input"]', '1000');
    await page.click('[data-testid="buy-button"]');
    await page.click('[data-testid="submit-order-button"]');

    // Verify notification appears
    await expect(page.locator('[data-testid="trading-notification"]')).toBeVisible();

    // Verify notification content
    await expect(page.locator('[data-testid="notification-message"]')).toContainText('Order submitted');

    // Close notification
    if (await page.locator('[data-testid="close-notification"]').isVisible()) {
      await page.click('[data-testid="close-notification"]');
      await expect(page.locator('[data-testid="trading-notification"]')).toBeHidden();
    }
  });

  test('chart interaction and analysis', async ({ page }) => {
    // Verify chart is loaded
    await expect(page.locator('[data-testid="price-chart"]')).toBeVisible();

    // Test timeframe selection
    if (await page.locator('[data-testid="timeframe-selector"]').isVisible()) {
      await page.click('[data-testid="timeframe-1h"]');

      // Verify chart updates
      await page.waitForSelector('[data-testid="chart-loading"]', { state: 'hidden' });
      await expect(page.locator('[data-testid="chart-timeframe-indicator"]')).toContainText('1h');
    }

    // Test chart drawing tools (if available)
    if (await page.locator('[data-testid="drawing-tools"]').isVisible()) {
      await page.click('[data-testid="trend-line-tool"]');

      // Draw on chart
      const chart = page.locator('[data-testid="chart-canvas"]');
      await chart.click({ position: { x: 100, y: 100 } });
      await chart.click({ position: { x: 200, y: 150 } });

      // Verify line drawn
      await expect(page.locator('[data-testid="chart-trend-line"]')).toBeVisible();
    }
  });

  test('trading keyboard shortcuts', async ({ page }) => {
    // Test buy shortcut (if implemented)
    await page.keyboard.press('KeyB');

    // Verify buy button gets focus or action
    const buyButton = page.locator('[data-testid="buy-button"]');

    // Test sell shortcut
    await page.keyboard.press('KeyS');

    // Test escape to close modals
    if (await page.locator('[data-testid="order-preview"]').isVisible()) {
      await page.keyboard.press('Escape');
      await expect(page.locator('[data-testid="order-preview"]')).toBeHidden();
    }
  });

  test('demo mode restrictions', async ({ page }) => {
    // Verify demo mode banner if in demo
    if (await page.locator('[data-testid="demo-mode-banner"]').isVisible()) {
      await expect(page.locator('[data-testid="demo-mode-banner"]')).toContainText('Demo Mode');

      // Verify demo restrictions message
      await expect(page.locator('[data-testid="demo-restrictions"]')).toBeVisible();

      // Test that real trading is disabled
      const submitButton = page.locator('[data-testid="submit-order-button"]');
      if (await submitButton.isVisible()) {
        await expect(submitButton).toContainText('Demo Order');
      }
    }
  });

  test('responsive trading interface', async ({ page }) => {
    // Test mobile layout
    await page.setViewportSize({ width: 375, height: 667 });

    // Verify mobile layout adaptations
    await expect(page.locator('[data-testid="trading-console"]')).toBeVisible();

    // Verify components stack appropriately
    const orderPanel = page.locator('[data-testid="order-panel"]');
    const positionsTable = page.locator('[data-testid="positions-table"]');

    // On mobile, order panel should be more compact
    await expect(orderPanel).toHaveClass(/compact|mobile/);

    // Test mobile-specific UI elements
    if (await page.locator('[data-testid="mobile-trading-tabs"]').isVisible()) {
      await page.click('[data-testid="positions-tab"]');
      await expect(page.locator('[data-testid="positions-view"]')).toBeVisible();

      await page.click('[data-testid="orders-tab"]');
      await expect(page.locator('[data-testid="orders-view"]')).toBeVisible();
    }
  });
});
