/**
 * Navigation E2E Tests
 *
 * Comprehensive testing of application navigation, routing, and layout components
 */

import { test, expect } from '@playwright/test';

test.describe('Application Navigation', () => {
  // Use authenticated state for navigation tests
  test.use({ storageState: 'e2e/.auth/user.json' });

  test.beforeEach(async ({ page }) => {
    await page.goto('/dashboard');
    await page.waitForLoadState('networkidle');
  });

  test('main navigation structure is present', async ({ page }) => {
    // Verify main layout components
    await expect(page.locator('[data-testid="app-layout"]')).toBeVisible();
    await expect(page.locator('[data-testid="header"]')).toBeVisible();
    await expect(page.locator('[data-testid="sidebar"]')).toBeVisible();
    await expect(page.locator('[data-testid="main-content"]')).toBeVisible();
  });

  test('sidebar navigation items are accessible', async ({ page }) => {
    const navigationItems = [
      { testId: 'nav-dashboard', url: '/dashboard', title: 'Dashboard' },
      { testId: 'nav-trading', url: '/trading', title: 'Trading' },
      { testId: 'nav-data', url: '/data', title: 'Data' },
      { testId: 'nav-training', url: '/training', title: 'Training' },
      { testId: 'nav-backtesting', url: '/backtesting', title: 'Backtesting' },
    ];

    for (const item of navigationItems) {
      // Verify navigation item exists
      await expect(page.locator(`[data-testid="${item.testId}"]`)).toBeVisible();

      // Click navigation item
      await page.click(`[data-testid="${item.testId}"]`);

      // Verify URL change
      await expect(page).toHaveURL(new RegExp(`.*${item.url}`));

      // Verify page title or main content loaded
      await expect(page.locator('[data-testid="page-title"]')).toContainText(item.title);

      // Wait for page to fully load
      await page.waitForLoadState('networkidle');
    }
  });

  test('header user menu functionality', async ({ page }) => {
    // Click user menu
    await page.click('[data-testid="user-menu"]');

    // Verify dropdown is visible
    await expect(page.locator('[data-testid="user-dropdown"]')).toBeVisible();

    // Verify menu items
    await expect(page.locator('[data-testid="profile-link"]')).toBeVisible();
    await expect(page.locator('[data-testid="settings-link"]')).toBeVisible();
    await expect(page.locator('[data-testid="help-link"]')).toBeVisible();
    await expect(page.locator('[data-testid="logout-button"]')).toBeVisible();
  });

  test('profile page navigation', async ({ page }) => {
    // Navigate to profile
    await page.click('[data-testid="user-menu"]');
    await page.click('[data-testid="profile-link"]');

    // Verify profile page
    await expect(page).toHaveURL(/.*\/profile/);
    await expect(page.locator('[data-testid="profile-form"]')).toBeVisible();
  });

  test('settings page navigation', async ({ page }) => {
    // Navigate to settings
    await page.click('[data-testid="user-menu"]');
    await page.click('[data-testid="settings-link"]');

    // Verify settings page
    await expect(page).toHaveURL(/.*\/settings/);
    await expect(page.locator('[data-testid="settings-panel"]')).toBeVisible();
  });

  test('help page navigation', async ({ page }) => {
    // Navigate to help
    await page.click('[data-testid="user-menu"]');
    await page.click('[data-testid="help-link"]');

    // Verify help page
    await expect(page).toHaveURL(/.*\/help/);
    await expect(page.locator('[data-testid="help-content"]')).toBeVisible();
  });

  test('breadcrumb navigation', async ({ page }) => {
    // Navigate to a nested page
    await page.goto('/data/quality');

    // Verify breadcrumb is present
    await expect(page.locator('[data-testid="breadcrumb"]')).toBeVisible();

    // Verify breadcrumb items
    await expect(page.locator('[data-testid="breadcrumb-home"]')).toBeVisible();
    await expect(page.locator('[data-testid="breadcrumb-data"]')).toBeVisible();
    await expect(page.locator('[data-testid="breadcrumb-quality"]')).toBeVisible();

    // Click breadcrumb to navigate back
    await page.click('[data-testid="breadcrumb-data"]');
    await expect(page).toHaveURL(/.*\/data/);
  });

  test('mobile navigation toggle', async ({ page }) => {
    // Set mobile viewport
    await page.setViewportSize({ width: 375, height: 667 });

    // Verify mobile menu button is visible
    await expect(page.locator('[data-testid="mobile-menu-button"]')).toBeVisible();

    // Verify sidebar is hidden on mobile
    await expect(page.locator('[data-testid="sidebar"]')).toBeHidden();

    // Click mobile menu button
    await page.click('[data-testid="mobile-menu-button"]');

    // Verify sidebar becomes visible
    await expect(page.locator('[data-testid="sidebar"]')).toBeVisible();

    // Click outside to close menu
    await page.click('[data-testid="main-content"]');
    await expect(page.locator('[data-testid="sidebar"]')).toBeHidden();
  });

  test('page transitions and loading states', async ({ page }) => {
    // Navigate to data page
    await page.click('[data-testid="nav-data"]');

    // Verify loading state appears
    await expect(page.locator('[data-testid="loading-spinner"]')).toBeVisible();

    // Wait for page to load
    await page.waitForLoadState('networkidle');

    // Verify loading state disappears
    await expect(page.locator('[data-testid="loading-spinner"]')).toBeHidden();

    // Verify content is loaded
    await expect(page.locator('[data-testid="data-management-dashboard"]')).toBeVisible();
  });

  test('keyboard navigation support', async ({ page }) => {
    // Focus on first navigation item
    await page.keyboard.press('Tab');
    await page.keyboard.press('Tab'); // Skip logo/brand

    // Verify focus on navigation
    await expect(page.locator('[data-testid="nav-dashboard"]')).toBeFocused();

    // Navigate with keyboard
    await page.keyboard.press('ArrowDown');
    await expect(page.locator('[data-testid="nav-trading"]')).toBeFocused();

    // Press Enter to navigate
    await page.keyboard.press('Enter');
    await expect(page).toHaveURL(/.*\/trading/);
  });

  test('deep linking and URL parameters', async ({ page }) => {
    // Test direct navigation to deep URL with parameters
    await page.goto('/trading?symbol=EURUSD&timeframe=1h');

    // Verify page loads correctly
    await expect(page.locator('[data-testid="trading-console"]')).toBeVisible();

    // Verify URL parameters are preserved
    await expect(page).toHaveURL(/.*symbol=EURUSD/);
    await expect(page).toHaveURL(/.*timeframe=1h/);

    // Verify components use URL parameters
    await expect(page.locator('[data-testid="symbol-selector"]')).toContainText('EURUSD');
  });

  test('back/forward browser navigation', async ({ page }) => {
    // Navigate through pages
    await page.goto('/dashboard');
    await page.goto('/trading');
    await page.goto('/data');

    // Use browser back
    await page.goBack();
    await expect(page).toHaveURL(/.*\/trading/);

    // Use browser forward
    await page.goForward();
    await expect(page).toHaveURL(/.*\/data/);

    // Use browser back again
    await page.goBack();
    await page.goBack();
    await expect(page).toHaveURL(/.*\/dashboard/);
  });

  test('404 error page handling', async ({ page }) => {
    // Navigate to non-existent page
    await page.goto('/non-existent-page');

    // Verify 404 page
    await expect(page.locator('[data-testid="404-page"]')).toBeVisible();
    await expect(page.locator('[data-testid="404-message"]')).toContainText('Page not found');

    // Verify navigation back to home
    await page.click('[data-testid="back-to-home"]');
    await expect(page).toHaveURL(/.*\/dashboard/);
  });

  test('active navigation state indicators', async ({ page }) => {
    // Navigate to dashboard
    await page.goto('/dashboard');

    // Verify active state
    await expect(page.locator('[data-testid="nav-dashboard"]')).toHaveClass(/active/);

    // Navigate to trading
    await page.click('[data-testid="nav-trading"]');

    // Verify active state changed
    await expect(page.locator('[data-testid="nav-trading"]')).toHaveClass(/active/);
    await expect(page.locator('[data-testid="nav-dashboard"]')).not.toHaveClass(/active/);
  });

  test('external link handling', async ({ page }) => {
    // Navigate to help page that might have external links
    await page.goto('/help');

    // Listen for new page opening
    const [newPage] = await Promise.all([
      page.context().waitForEvent('page'),
      page.click('[data-testid="external-docs-link"]')
    ]);

    // Verify external link opens in new tab
    await expect(newPage).toHaveURL(/https?:\/\/docs\.fxml4\.com/);

    // Close new page
    await newPage.close();
  });
});
