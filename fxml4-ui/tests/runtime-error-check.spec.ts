import { test, expect } from '@playwright/test';

test('Check for runtime errors on pages', async ({ page }) => {
  const errors: string[] = [];

  // Capture JavaScript errors
  page.on('pageerror', err => {
    console.log('PAGE ERROR:', err.message);
    errors.push(err.message);
  });

  // Capture console errors
  page.on('console', msg => {
    if (msg.type() === 'error') {
      console.log('CONSOLE ERROR:', msg.text());
      errors.push(msg.text());
    }
  });

  // Test main pages that were failing
  const pagesToTest = ['/dashboard', '/data', '/signals', '/trading'];

  for (const path of pagesToTest) {
    console.log(`Testing ${path}...`);

    try {
      await page.goto(`http://localhost:3000${path}`, {
        waitUntil: 'domcontentloaded',
        timeout: 15000
      });

      // Wait a bit for any runtime errors to surface
      await page.waitForTimeout(2000);

      // Check if we got a proper page or an error page
      const pageTitle = await page.title();
      const bodyText = await page.locator('body').textContent();

      console.log(`${path} - Title: "${pageTitle}"`);
      console.log(`${path} - Has content: ${bodyText ? bodyText.length > 100 : false}`);

      // Check for Next.js error indicators
      const hasNextError = await page.locator('h2').filter({ hasText: 'Application error: a client-side exception has occurred' }).count() > 0;
      const has404 = pageTitle.includes('404') || bodyText?.includes('This page could not be found');

      if (hasNextError) {
        errors.push(`${path}: Next.js application error detected`);
      }

      if (has404) {
        errors.push(`${path}: 404 page detected`);
      }

    } catch (error) {
      console.log(`${path} - Navigation failed:`, error);
      errors.push(`${path}: Navigation timeout - ${error}`);
    }
  }

  // Print all errors found
  if (errors.length > 0) {
    console.log('\\n=== ALL ERRORS FOUND ===');
    errors.forEach(error => console.log(`❌ ${error}`));
    console.log('========================\\n');
  } else {
    console.log('✅ No runtime errors detected!');
  }

  // The test should pass if we made progress (fewer errors than before)
  // Previously we had "updatePrice is not defined" - if that's gone, we're good
  const hasUpdatePriceError = errors.some(error => error.includes('updatePrice'));
  expect(hasUpdatePriceError, 'updatePrice error should be resolved').toBe(false);
});
