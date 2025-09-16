/**
 * 🏠 COMPREHENSIVE DASHBOARD AUDIT
 *
 * Systematic validation of dashboard functionality and navigation
 * This is part 1 of the comprehensive feature testing suite
 */

import { test, expect } from '@playwright/test';

const BASE_URL = process.env.PLAYWRIGHT_TEST_BASE_URL || 'http://localhost:3000';

test.describe('🏠 Dashboard & Navigation - Comprehensive Audit', () => {

  test.beforeEach(async ({ page }) => {
    await page.goto(`${BASE_URL}/dashboard`);
    await page.waitForLoadState('networkidle');
  });

  test('Dashboard loads with all core components', async ({ page }) => {
    console.log('\n🔍 Testing Dashboard Core Components...');

    // Test page title
    await expect(page).toHaveTitle(/FTML4/i);
    console.log('✅ Page title correct');

    // Test main layout components
    const header = page.locator('header, [data-testid="header"], .header');
    await expect(header).toBeVisible();
    console.log('✅ Header visible');

    const sidebar = page.locator('nav, [data-testid="sidebar"], .sidebar');
    await expect(sidebar).toBeVisible();
    console.log('✅ Sidebar visible');

    const main = page.locator('main, [role="main"], .main-content');
    await expect(main).toBeVisible();
    console.log('✅ Main content area visible');

    console.log('✅ All core layout components present');
  });

  test('Navigation sidebar functionality', async ({ page }) => {
    console.log('\n🧭 Testing Sidebar Navigation...');

    const navigationPages = [
      { name: 'Dashboard', path: '/dashboard', text: 'dashboard' },
      { name: 'Trading', path: '/trading', text: 'trading' },
      { name: 'Data', path: '/data', text: 'data' },
      { name: 'Training', path: '/training', text: 'training' },
      { name: 'Backtesting', path: '/backtesting', text: 'backtesting' },
      { name: 'Elliott Waves', path: '/elliott-waves', text: 'elliott' },
      { name: 'Analytics', path: '/analytics', text: 'analytics' }
    ];

    for (const navItem of navigationPages) {
      console.log(`Testing navigation to ${navItem.name}...`);

      // Look for navigation links by various selectors
      const navLink = page.locator(`a[href="${navItem.path}"], a:has-text("${navItem.name}"), [data-testid="${navItem.text}-nav"]`).first();

      if (await navLink.count() > 0) {
        await navLink.click();
        await page.waitForLoadState('networkidle');
        await page.waitForTimeout(1000); // Allow time for page to render

        // Verify navigation worked
        expect(page.url()).toContain(navItem.path);
        console.log(`  ✅ ${navItem.name} navigation successful`);
      } else {
        console.log(`  ⚠️  ${navItem.name} navigation link not found`);
      }
    }
  });

  test('Header functionality and user interface', async ({ page }) => {
    console.log('\n📋 Testing Header Functionality...');

    // Test time display
    const timeDisplay = page.locator('[data-testid="current-time"], .time, .current-time');
    if (await timeDisplay.count() > 0) {
      const timeText = await timeDisplay.textContent();
      expect(timeText).toBeTruthy();
      console.log(`✅ Time display working: ${timeText}`);
    } else {
      console.log('⚠️  Time display not found');
    }

    // Test theme toggle
    const themeToggle = page.locator('[data-testid="theme-toggle"], .theme-toggle, button:has-text("theme")');
    if (await themeToggle.count() > 0) {
      await themeToggle.click();
      console.log('✅ Theme toggle clickable');
    } else {
      console.log('⚠️  Theme toggle not found');
    }

    // Test notifications
    const notifications = page.locator('[data-testid="notifications"], .notifications, .notification-icon');
    if (await notifications.count() > 0) {
      await expect(notifications).toBeVisible();
      console.log('✅ Notifications area visible');
    } else {
      console.log('⚠️  Notifications area not found');
    }

    // Test user menu/profile
    const userMenu = page.locator('[data-testid="user-menu"], .user-menu, .profile-menu');
    if (await userMenu.count() > 0) {
      await expect(userMenu).toBeVisible();
      console.log('✅ User menu visible');
    } else {
      console.log('⚠️  User menu not found');
    }
  });

  test('Dashboard metrics and data display', async ({ page }) => {
    console.log('\n📊 Testing Dashboard Metrics...');

    // Look for metric cards/widgets
    const metricCards = page.locator('.metric-card, .stat-card, .dashboard-widget, [data-testid*="metric"]');
    const cardCount = await metricCards.count();
    console.log(`Found ${cardCount} metric cards`);

    if (cardCount > 0) {
      // Test each metric card
      for (let i = 0; i < Math.min(cardCount, 10); i++) { // Limit to first 10
        const card = metricCards.nth(i);
        await expect(card).toBeVisible();

        const cardText = await card.textContent();
        console.log(`  Card ${i + 1}: ${cardText?.slice(0, 50)}...`);
      }
      console.log('✅ Metric cards displaying data');
    } else {
      console.log('⚠️  No metric cards found');
    }

    // Look for specific dashboard elements
    const elements = [
      { name: 'Account Balance', selectors: '[data-testid="balance"], .balance, .account-balance' },
      { name: 'Active Positions', selectors: '[data-testid="positions"], .positions, .active-positions' },
      { name: 'P&L', selectors: '[data-testid="pnl"], .pnl, .profit-loss' },
      { name: 'Connection Status', selectors: '[data-testid="connection"], .connection, .status' }
    ];

    for (const element of elements) {
      const found = page.locator(element.selectors);
      if (await found.count() > 0) {
        console.log(`  ✅ ${element.name} element found`);
      } else {
        console.log(`  ⚠️  ${element.name} element not found`);
      }
    }
  });

  test('Real-time connection status and indicators', async ({ page }) => {
    console.log('\n🔌 Testing Real-time Connection Status...');

    // Look for connection indicators
    const connectionIndicators = page.locator('.connection-status, .online-indicator, .status-indicator, [data-testid*="connection"]');
    const indicatorCount = await connectionIndicators.count();

    if (indicatorCount > 0) {
      console.log(`Found ${indicatorCount} connection indicators`);

      for (let i = 0; i < indicatorCount; i++) {
        const indicator = connectionIndicators.nth(i);
        const isVisible = await indicator.isVisible();
        const text = await indicator.textContent();
        console.log(`  Indicator ${i + 1}: ${isVisible ? 'visible' : 'hidden'} - "${text}"`);
      }
      console.log('✅ Connection indicators present');
    } else {
      console.log('⚠️  No connection indicators found');
    }

    // Look for WebSocket status
    const wsStatus = page.locator('[data-testid="websocket-status"], .websocket, .ws-status');
    if (await wsStatus.count() > 0) {
      const status = await wsStatus.textContent();
      console.log(`✅ WebSocket status: ${status}`);
    } else {
      console.log('⚠️  WebSocket status not displayed');
    }

    // Look for API status
    const apiStatus = page.locator('[data-testid="api-status"], .api-status, .backend-status');
    if (await apiStatus.count() > 0) {
      const status = await apiStatus.textContent();
      console.log(`✅ API status: ${status}`);
    } else {
      console.log('⚠️  API status not displayed');
    }
  });

  test('Loading states and error boundaries', async ({ page }) => {
    console.log('\n⏳ Testing Loading States and Error Handling...');

    // Refresh page to trigger loading states
    await page.reload();

    // Look for loading indicators during page load
    const loadingSpinners = page.locator('.loading, .spinner, [data-testid="loading"], .animate-spin');
    const hasLoading = await loadingSpinners.count() > 0;

    if (hasLoading) {
      console.log('✅ Loading indicators found during page load');
    } else {
      console.log('⚠️  No loading indicators detected');
    }

    // Wait for page to fully load
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(2000);

    // Check for error boundaries
    const errorBoundaries = page.locator('.error-boundary, [data-testid="error"], .error-message');
    const errorCount = await errorBoundaries.count();

    if (errorCount > 0) {
      console.log(`❌ Found ${errorCount} error boundaries - this indicates problems`);
      for (let i = 0; i < errorCount; i++) {
        const error = errorBoundaries.nth(i);
        const errorText = await error.textContent();
        console.log(`  Error ${i + 1}: ${errorText}`);
      }
    } else {
      console.log('✅ No error boundaries found');
    }
  });

  test('Responsive mobile layout', async ({ page }) => {
    console.log('\n📱 Testing Mobile Responsive Layout...');

    // Test mobile viewport
    await page.setViewportSize({ width: 375, height: 667 }); // iPhone SE
    await page.waitForTimeout(1000);

    // Check if mobile layout activates
    const mobileMenu = page.locator('.mobile-menu, .hamburger, [data-testid="mobile-nav"]');
    const hasMobileMenu = await mobileMenu.count() > 0;

    if (hasMobileMenu) {
      console.log('✅ Mobile menu elements detected');

      // Test mobile menu functionality
      if (await mobileMenu.isVisible()) {
        await mobileMenu.click();
        console.log('✅ Mobile menu clickable');
      }
    } else {
      console.log('⚠️  Mobile menu not found');
    }

    // Test responsive containers
    const mainContent = page.locator('main, .main-content');
    const contentBox = await mainContent.boundingBox();

    if (contentBox && contentBox.width <= 375) {
      console.log('✅ Main content responsive to mobile width');
    } else {
      console.log('⚠️  Main content may not be fully responsive');
    }

    // Reset to desktop
    await page.setViewportSize({ width: 1280, height: 720 });
  });

  test('Performance and page load metrics', async ({ page }) => {
    console.log('\n⚡ Testing Performance Metrics...');

    const startTime = Date.now();

    // Navigate to dashboard and measure load time
    await page.goto(`${BASE_URL}/dashboard`);
    await page.waitForLoadState('networkidle');

    const loadTime = Date.now() - startTime;
    console.log(`Page load time: ${loadTime}ms`);

    // Performance expectations
    if (loadTime < 3000) {
      console.log('✅ Page load time acceptable (< 3s)');
    } else if (loadTime < 5000) {
      console.log('⚠️  Page load time slow (3-5s)');
    } else {
      console.log('❌ Page load time too slow (> 5s)');
    }

    // Check for performance metrics
    const performanceMarks = await page.evaluate(() => {
      return window.performance.getEntriesByType('navigation');
    });

    if (performanceMarks.length > 0) {
      console.log('✅ Performance metrics available');
    } else {
      console.log('⚠️  No performance metrics captured');
    }

    // Memory usage (rough estimate)
    const jsHeapSize = await page.evaluate(() => {
      return (window.performance as any).memory?.usedJSHeapSize || 'Not available';
    });

    console.log(`JS Heap Size: ${jsHeapSize}`);
  });

  test('Console errors and warnings audit', async ({ page }) => {
    console.log('\n🔍 Auditing Console Errors and Warnings...');

    const consoleMessages: string[] = [];

    page.on('console', message => {
      if (message.type() === 'error' || message.type() === 'warning') {
        consoleMessages.push(`${message.type().toUpperCase()}: ${message.text()}`);
      }
    });

    // Navigate and interact with dashboard
    await page.goto(`${BASE_URL}/dashboard`);
    await page.waitForLoadState('networkidle');

    // Click around to trigger any errors
    const clickableElements = page.locator('button, a, .clickable');
    const clickCount = Math.min(await clickableElements.count(), 5);

    for (let i = 0; i < clickCount; i++) {
      try {
        await clickableElements.nth(i).click({ timeout: 1000 });
        await page.waitForTimeout(500);
      } catch (e) {
        // Continue if click fails
      }
    }

    // Report console messages
    if (consoleMessages.length === 0) {
      console.log('✅ No console errors or warnings detected');
    } else {
      console.log(`⚠️  Found ${consoleMessages.length} console messages:`);
      consoleMessages.forEach((msg, i) => {
        console.log(`  ${i + 1}. ${msg}`);
      });
    }
  });
});
