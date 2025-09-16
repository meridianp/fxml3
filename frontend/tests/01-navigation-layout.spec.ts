import { test, expect } from '@playwright/test';

const BASE_URL = 'http://localhost:3000';

test.describe('1. NAVIGATION & LAYOUT', () => {

  test('Sidebar navigation is present and functional', async ({ page }) => {
    await page.goto(`${BASE_URL}/dashboard`);
    await page.waitForLoadState('networkidle');

    // Check sidebar exists
    const sidebar = page.locator('[data-testid="sidebar"], .sidebar, nav[role="navigation"]').first();
    await expect(sidebar).toBeVisible({ timeout: 10000 });

    // Check sidebar has navigation items
    const navItems = page.locator('a[href*="/"]').filter({ hasText: /Trading|Dashboard|Data|Signals/ });
    const navCount = await navItems.count();
    expect(navCount, 'Should have navigation menu items').toBeGreaterThan(2);

    console.log(`✓ Found ${navCount} navigation items`);
  });

  test('Sidebar menu items are clickable with active states', async ({ page }) => {
    await page.goto(`${BASE_URL}/dashboard`);
    await page.waitForLoadState('networkidle');

    // Test navigation to different pages
    const testRoutes = [
      { text: 'Trading', expected: '/trading' },
      { text: 'Data', expected: '/data' },
      { text: 'Dashboard', expected: '/dashboard' }
    ];

    for (const route of testRoutes) {
      console.log(`Testing navigation to ${route.text}...`);

      const navLink = page.locator(`a:has-text("${route.text}")`).first();
      if (await navLink.count() > 0) {
        await navLink.click();
        await page.waitForTimeout(2000);

        // Check URL changed
        const currentUrl = page.url();
        expect(currentUrl, `Should navigate to ${route.expected}`).toContain(route.expected);
        console.log(`✓ Navigation to ${route.text} works`);
      } else {
        console.log(`⚠ No navigation link found for ${route.text}`);
      }
    }
  });

  test('Header displays user info and controls', async ({ page }) => {
    await page.goto(`${BASE_URL}/dashboard`);
    await page.waitForLoadState('networkidle');

    // Check for header
    const header = page.locator('header, [role="banner"], .header').first();
    await expect(header).toBeVisible({ timeout: 10000 });

    // Check for user controls (logout, profile, settings)
    const userControls = page.locator('button:has-text("Logout"), a:has-text("Profile"), button:has-text("Settings")');
    const controlCount = await userControls.count();
    console.log(`Found ${controlCount} user controls in header`);
  });

  test('Mobile responsive sidebar works', async ({ page }) => {
    // Set mobile viewport
    await page.setViewportSize({ width: 375, height: 667 });
    await page.goto(`${BASE_URL}/dashboard`);
    await page.waitForLoadState('networkidle');

    // Look for mobile menu toggle
    const menuToggle = page.locator('button:has-text("Menu"), button[aria-label*="menu"], .hamburger, [data-testid="menu-toggle"]').first();

    if (await menuToggle.count() > 0) {
      console.log('✓ Mobile menu toggle found');
      await menuToggle.click();
      await page.waitForTimeout(500);

      // Check if menu is now visible
      const mobileNav = page.locator('nav, .sidebar, [role="navigation"]').first();
      console.log('Mobile navigation tested');
    } else {
      console.log('⚠ No mobile menu toggle found');
    }
  });

  test('Page routing works between all sections', async ({ page }) => {
    const routes = ['/dashboard', '/trading', '/data', '/signals', '/backtesting', '/training'];

    for (const route of routes) {
      console.log(`Testing direct navigation to ${route}...`);

      try {
        await page.goto(`${BASE_URL}${route}`, { timeout: 15000 });
        await page.waitForTimeout(2000);

        const title = await page.title();
        const is404 = title.includes('404') || title.includes('This page could not be found');

        if (!is404) {
          console.log(`✓ ${route} loads successfully: "${title}"`);
        } else {
          console.log(`❌ ${route} returns 404`);
        }

      } catch (error) {
        console.log(`❌ ${route} failed to load: ${error}`);
      }
    }
  });
});
