import { test, expect } from '@playwright/test';

test('Debug: Check what is actually loading on failed pages', async ({ page }) => {
  // Enable console logging
  page.on('console', msg => console.log('PAGE LOG:', msg.text()));
  page.on('pageerror', err => console.log('PAGE ERROR:', err.message));

  console.log('Testing /data page...');
  await page.goto('http://localhost:3000/data');
  await page.waitForLoadState('networkidle');

  const title = await page.title();
  console.log('Page title:', title);

  const content = await page.content();
  console.log('Page has __next_error__:', content.includes('__next_error__'));
  console.log('Page has 404 content:', content.includes('404'));

  await page.screenshot({ path: 'debug-data-page.png' });
});
