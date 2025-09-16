import { test, expect } from '@playwright/test';

test('FINAL VALIDATION: Critical runtime errors are fixed', async ({ page }) => {
  const criticalErrors: string[] = [];

  // Capture critical runtime errors
  page.on('pageerror', err => {
    const errorMsg = err.message;
    if (errorMsg.includes('updatePrice is not defined')) {
      criticalErrors.push('❌ CRITICAL: updatePrice is not defined');
    }
    if (errorMsg.includes('addError is not a function')) {
      criticalErrors.push('❌ CRITICAL: addError is not a function');
    }
    if (errorMsg.includes('setMarketDataConnected is not a function')) {
      criticalErrors.push('❌ CRITICAL: setMarketDataConnected is not a function');
    }
  });

  // Test main pages that were previously broken
  const pagesToTest = ['/dashboard', '/data', '/trading'];

  for (const path of pagesToTest) {
    console.log(`✅ Testing ${path}...`);

    await page.goto(`http://localhost:3000${path}`, {
      waitUntil: 'domcontentloaded',
      timeout: 15000
    });

    // Wait for any immediate runtime errors
    await page.waitForTimeout(3000);

    // Verify page loaded with correct title (not 404)
    const pageTitle = await page.title();
    const is404 = pageTitle.includes('404') || pageTitle.includes('This page could not be found');

    if (!is404) {
      console.log(`✅ ${path} loads successfully: "${pageTitle}"`);
    } else {
      criticalErrors.push(`❌ ${path}: Still showing 404 page`);
    }
  }

  // Results summary
  console.log('\\n=== VALIDATION RESULTS ===');

  if (criticalErrors.length === 0) {
    console.log('🎉 SUCCESS: All critical runtime errors have been FIXED!');
    console.log('✅ updatePrice errors: RESOLVED');
    console.log('✅ addError errors: RESOLVED');
    console.log('✅ setMarketDataConnected errors: RESOLVED');
    console.log('✅ Pages loading correctly: CONFIRMED');
  } else {
    console.log('❌ REMAINING ISSUES:');
    criticalErrors.forEach(error => console.log(`   ${error}`));
  }

  console.log('========================\\n');

  // Test should pass if we fixed the core runtime errors
  expect(criticalErrors.length, 'All critical runtime errors should be resolved').toBe(0);
});
