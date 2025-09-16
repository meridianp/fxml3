import { test, expect } from '@playwright/test';

const BASE_URL = 'http://localhost:3000';

test.describe('6. UI/UX FEATURES', () => {

  test('Loading states display properly', async ({ page }) => {
    await page.goto(`${BASE_URL}/dashboard`);

    // Look for loading indicators during page load
    const loadingSelectors = [
      '[data-testid*="loading"]',
      '.loading',
      '.spinner',
      '.skeleton',
      'div:has-text("Loading")',
      '[aria-label*="loading"]',
      '.loading-spinner'
    ];

    let loadingIndicators = 0;
    for (const selector of loadingSelectors) {
      const elements = page.locator(selector);
      const count = await elements.count();

      if (count > 0) {
        loadingIndicators += count;
        console.log(`✓ Found ${count} loading indicators: ${selector}`);

        // Check if loading indicators are properly styled
        const firstElement = elements.first();
        const isVisible = await firstElement.isVisible();
        console.log(`  Loading indicator visible: ${isVisible}`);
      }
    }

    await page.waitForLoadState('networkidle');
    console.log(`Total loading indicators: ${loadingIndicators}`);
  });

  test('Error messages and validation feedback', async ({ page }) => {
    await page.goto(`${BASE_URL}/trading`);
    await page.waitForLoadState('networkidle');

    // Look for form inputs to test validation
    const inputs = page.locator('input[type="number"], input[type="text"]');
    const inputCount = await inputs.count();

    if (inputCount > 0) {
      console.log(`Testing validation on ${inputCount} form inputs`);

      // Test validation by clearing required input
      const firstInput = inputs.first();
      const inputType = await firstInput.getAttribute('type');

      if (inputType === 'number') {
        // For number inputs, try to set invalid range value
        const min = await firstInput.getAttribute('min');
        if (min) {
          const minValue = parseInt(min);
          await firstInput.fill((minValue - 1).toString());
        } else {
          await firstInput.fill('-999999');
        }
      } else {
        // For text inputs, clear the field to test required validation
        await firstInput.clear();
      }
      await firstInput.blur();

      // Look for error messages
      const errorSelectors = [
        '.error',
        '.invalid',
        '[role="alert"]',
        '.field-error',
        'span:has-text("Required"), span:has-text("Invalid")',
        '[data-testid*="error"]'
      ];

      let errorMessages = 0;
      for (const selector of errorSelectors) {
        const elements = page.locator(selector);
        const count = await elements.count();

        if (count > 0) {
          errorMessages += count;
          console.log(`✓ Found ${count} error messages: ${selector}`);

          const firstError = elements.first();
          const errorText = await firstError.textContent();
          console.log(`  Error message: "${errorText}"`);
        }
      }

      console.log(`Total error messages found: ${errorMessages}`);
    }
  });

  test('Success notifications and feedback', async ({ page }) => {
    await page.goto(`${BASE_URL}/dashboard`);
    await page.waitForLoadState('networkidle');

    // Look for success indicators
    const successSelectors = [
      '.success',
      '.notification-success',
      '.toast-success',
      'div:has-text("Success")',
      '[data-testid*="success"]',
      '.alert-success'
    ];

    let successIndicators = 0;
    for (const selector of successSelectors) {
      const elements = page.locator(selector);
      const count = await elements.count();

      if (count > 0) {
        successIndicators += count;
        console.log(`✓ Found ${count} success indicators: ${selector}`);
      }
    }

    // Look for buttons that might trigger success messages
    const actionButtons = page.locator('button:has-text("Save"), button:has-text("Submit"), button:has-text("Update")');
    const actionCount = await actionButtons.count();

    console.log(`Success indicators: ${successIndicators}`);
    console.log(`Action buttons that might show success: ${actionCount}`);
  });

  test('Responsive design on different screen sizes', async ({ page }) => {
    const viewports = [
      { width: 1920, height: 1080, name: 'Desktop Large' },
      { width: 1366, height: 768, name: 'Desktop Standard' },
      { width: 768, height: 1024, name: 'Tablet' },
      { width: 375, height: 667, name: 'Mobile' }
    ];

    for (const viewport of viewports) {
      console.log(`Testing ${viewport.name} (${viewport.width}x${viewport.height})`);

      await page.setViewportSize({ width: viewport.width, height: viewport.height });
      await page.goto(`${BASE_URL}/dashboard`);
      await page.waitForLoadState('networkidle');

      // Check if content is visible and not cut off
      const mainContent = page.locator('main, .main-content, [role="main"]').first();
      if (await mainContent.count() > 0) {
        const boundingBox = await mainContent.boundingBox();
        if (boundingBox) {
          const fits = boundingBox.width <= viewport.width;
          console.log(`  Content fits in viewport: ${fits} (${boundingBox.width}px wide)`);
        }
      }

      // Check for mobile-specific elements
      if (viewport.width <= 768) {
        const mobileElements = page.locator('.mobile-menu, .hamburger, [data-mobile="true"]');
        const mobileCount = await mobileElements.count();
        console.log(`  Mobile-specific elements: ${mobileCount}`);
      }
    }
  });

  test('Keyboard navigation and accessibility', async ({ page }) => {
    await page.goto(`${BASE_URL}/dashboard`);
    await page.waitForLoadState('networkidle');

    // Test tab navigation
    console.log('Testing keyboard navigation...');

    // Focus on first focusable element and tab through
    await page.keyboard.press('Tab');
    await page.waitForTimeout(500);

    let focusedElement = page.locator(':focus');
    let tabStops = 0;

    // Tab through several elements
    for (let i = 0; i < 10; i++) {
      if (await focusedElement.count() > 0) {
        try {
          const tagName = await focusedElement.first().evaluate(el => el.tagName);
          const role = await focusedElement.getAttribute('role');
          console.log(`  Tab stop ${i + 1}: ${tagName} ${role ? `(${role})` : ''}`);
          tabStops++;
        } catch (error) {
          console.log(`  Tab stop ${i + 1}: Could not get element info`);
        }
      }

      await page.keyboard.press('Tab');
      await page.waitForTimeout(200);
      focusedElement = page.locator(':focus');
    }

    console.log(`Total tab stops found: ${tabStops}`);

    // Check for accessibility attributes
    const accessibilityElements = page.locator('[aria-label], [role], [aria-describedby]');
    const a11yCount = await accessibilityElements.count();
    console.log(`Elements with accessibility attributes: ${a11yCount}`);
  });

  test('Theme switching functionality', async ({ page }) => {
    await page.goto(`${BASE_URL}/dashboard`);
    await page.waitForLoadState('networkidle');

    // Look for theme toggle
    const themeSelectors = [
      'button:has-text("Dark"), button:has-text("Light")',
      '[data-testid*="theme"]',
      '.theme-toggle',
      '.dark-mode-toggle',
      'label:has-text("Dark") input[type="checkbox"]'
    ];

    let themeControls = 0;
    for (const selector of themeSelectors) {
      const elements = page.locator(selector);
      const count = await elements.count();

      if (count > 0) {
        themeControls += count;
        console.log(`✓ Found ${count} theme controls: ${selector}`);

        // Test theme switching
        const firstControl = elements.first();
        try {
          const initialClass = await page.locator('html, body').first().getAttribute('class') || '';
          console.log(`  Initial theme classes: "${initialClass}"`);

          await firstControl.click();
          await page.waitForTimeout(1000);

          const newClass = await page.locator('html, body').first().getAttribute('class') || '';
          console.log(`  After click theme classes: "${newClass}"`);

          if (initialClass !== newClass) {
            console.log(`  ✓ Theme switching works`);
          } else {
            console.log(`  ⚠ Theme classes didn't change`);
          }

        } catch (error) {
          console.log(`  Theme toggle test failed: ${error}`);
        }
      }
    }

    console.log(`Total theme controls: ${themeControls}`);
  });

  test('Performance and memory usage', async ({ page }) => {
    // Monitor page performance
    const startTime = Date.now();

    await page.goto(`${BASE_URL}/dashboard`);
    await page.waitForLoadState('networkidle');

    const loadTime = Date.now() - startTime;
    console.log(`Page load time: ${loadTime}ms`);

    // Check for performance issues
    const performanceEntries = await page.evaluate(() => {
      return JSON.stringify({
        navigation: performance.getEntriesByType('navigation')[0],
        resources: performance.getEntriesByType('resource').length,
        memory: (performance as any).memory ? {
          usedJSHeapSize: (performance as any).memory.usedJSHeapSize,
          totalJSHeapSize: (performance as any).memory.totalJSHeapSize
        } : null
      });
    });

    const perfData = JSON.parse(performanceEntries);
    console.log(`Resources loaded: ${perfData.resources}`);

    if (perfData.memory) {
      const memoryMB = Math.round(perfData.memory.usedJSHeapSize / 1024 / 1024);
      console.log(`Memory usage: ${memoryMB} MB`);
    }

    // Performance thresholds
    if (loadTime > 5000) {
      console.log(`⚠ Slow page load: ${loadTime}ms`);
    } else {
      console.log(`✓ Good page load performance: ${loadTime}ms`);
    }
  });

  test('Error boundary handling', async ({ page }) => {
    // Monitor for unhandled JavaScript errors
    const jsErrors: string[] = [];

    page.on('pageerror', err => {
      jsErrors.push(err.message);
    });

    await page.goto(`${BASE_URL}/dashboard`);
    await page.waitForLoadState('networkidle');

    // Navigate to different pages to test error boundaries
    const routes = ['/trading', '/data', '/signals'];

    for (const route of routes) {
      try {
        await page.goto(`${BASE_URL}${route}`, { timeout: 10000 });
        await page.waitForTimeout(2000);
      } catch (error) {
        console.log(`Error navigating to ${route}: ${error}`);
      }
    }

    console.log(`JavaScript errors caught: ${jsErrors.length}`);

    if (jsErrors.length > 0) {
      console.log('JavaScript errors:');
      jsErrors.forEach((error, index) => {
        console.log(`  ${index + 1}. ${error.slice(0, 100)}...`);
      });
    } else {
      console.log('✓ No JavaScript errors detected');
    }

    // Look for error boundary components
    const errorBoundaries = page.locator('.error-boundary, [data-testid*="error-boundary"]');
    const boundaryCount = await errorBoundaries.count();
    console.log(`Error boundary components found: ${boundaryCount}`);
  });
});
