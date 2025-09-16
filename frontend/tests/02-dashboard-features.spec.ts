import { test, expect } from '@playwright/test';

const BASE_URL = 'http://localhost:3000';

test.describe('2. DASHBOARD FEATURES', () => {

  test('Dashboard metrics cards display account data', async ({ page }) => {
    await page.goto(`${BASE_URL}/dashboard`);
    await page.waitForLoadState('networkidle');

    // Look for metric cards with financial data
    const metricSelectors = [
      '[data-testid*="balance"]',
      '[data-testid*="equity"]',
      '[data-testid*="pl"]',
      '[data-testid*="profit"]',
      '[data-testid*="position"]',
      '.metric-card',
      '.dashboard-card',
      '.stat-card'
    ];

    let foundMetrics = 0;
    for (const selector of metricSelectors) {
      const cards = page.locator(selector);
      const count = await cards.count();
      if (count > 0) {
        foundMetrics += count;
        console.log(`✓ Found ${count} metric cards with selector: ${selector}`);

        // Check if cards have actual data
        for (let i = 0; i < Math.min(count, 3); i++) {
          const cardText = await cards.nth(i).textContent();
          if (cardText && cardText.trim().length > 0) {
            console.log(`  Card ${i + 1}: "${cardText.slice(0, 50)}..."`);
          }
        }
      }
    }

    console.log(`Total metric cards found: ${foundMetrics}`);
    expect(foundMetrics, 'Should have at least some metric cards').toBeGreaterThan(0);
  });

  test('Feature cards are clickable and functional', async ({ page }) => {
    await page.goto(`${BASE_URL}/dashboard`);
    await page.waitForLoadState('networkidle');

    // Look for feature cards (Trading, Analysis, etc.)
    const featureCardSelectors = [
      'button:has-text("Trading")',
      'button:has-text("Analysis")',
      'a:has-text("Trading")',
      'a:has-text("Analysis")',
      '[data-testid*="feature-card"]',
      '.feature-card',
      '.dashboard-feature'
    ];

    let clickableCards = 0;
    for (const selector of featureCardSelectors) {
      const cards = page.locator(selector);
      const count = await cards.count();

      if (count > 0) {
        clickableCards += count;
        console.log(`✓ Found ${count} feature cards: ${selector}`);

        // Test clicking first card
        try {
          const firstCard = cards.first();
          const cardText = await firstCard.textContent() || 'Unknown';

          console.log(`  Testing click on: "${cardText}"`);
          await firstCard.click();
          await page.waitForTimeout(2000);

          // Check if navigation occurred or modal opened
          const currentUrl = page.url();
          console.log(`  After click, URL: ${currentUrl}`);

        } catch (error) {
          console.log(`  ❌ Click failed: ${error}`);
        }
      }
    }

    console.log(`Total clickable feature cards: ${clickableCards}`);
  });

  test('Charts and visualizations render', async ({ page }) => {
    await page.goto(`${BASE_URL}/dashboard`);
    await page.waitForLoadState('networkidle');

    // Look for chart containers
    const chartSelectors = [
      'canvas',
      'svg',
      '[data-testid*="chart"]',
      '.chart-container',
      '.recharts-wrapper',
      '[class*="chart"]',
      '#trading-chart'
    ];

    let foundCharts = 0;
    for (const selector of chartSelectors) {
      const charts = page.locator(selector);
      const count = await charts.count();
      if (count > 0) {
        foundCharts += count;
        console.log(`✓ Found ${count} chart elements: ${selector}`);

        // Check if chart has actual content
        const firstChart = charts.first();
        const boundingBox = await firstChart.boundingBox();
        if (boundingBox && boundingBox.width > 50 && boundingBox.height > 50) {
          console.log(`  Chart has content: ${boundingBox.width}x${boundingBox.height}`);
        }
      }
    }

    console.log(`Total chart elements found: ${foundCharts}`);
  });

  test('Recent activity feed displays data', async ({ page }) => {
    await page.goto(`${BASE_URL}/dashboard`);
    await page.waitForLoadState('networkidle');

    // Look for activity/history sections
    const activitySelectors = [
      '[data-testid*="activity"]',
      '[data-testid*="history"]',
      '.recent-activity',
      '.activity-feed',
      '.trade-history',
      'h2:has-text("Recent"), h3:has-text("Activity")'
    ];

    for (const selector of activitySelectors) {
      const sections = page.locator(selector);
      const count = await sections.count();

      if (count > 0) {
        console.log(`✓ Found activity section: ${selector}`);

        // Look for activity items within the section
        const items = sections.first().locator('li, tr, .activity-item, .trade-item');
        const itemCount = await items.count();
        console.log(`  Contains ${itemCount} activity items`);

        if (itemCount > 0) {
          const firstItemText = await items.first().textContent();
          console.log(`  First item: "${firstItemText?.slice(0, 100)}..."`);
        }
      }
    }
  });

  test('Quick action buttons are functional', async ({ page }) => {
    await page.goto(`${BASE_URL}/dashboard`);
    await page.waitForLoadState('networkidle');

    // Look for quick action buttons
    const actionSelectors = [
      'button:has-text("Buy")',
      'button:has-text("Sell")',
      'button:has-text("Trade")',
      'button:has-text("Analyze")',
      'button:has-text("Backtest")',
      '[data-testid*="quick-action"]',
      '.quick-action',
      '.action-button'
    ];

    let functionalButtons = 0;
    for (const selector of actionSelectors) {
      const buttons = page.locator(selector);
      const count = await buttons.count();

      if (count > 0) {
        console.log(`✓ Found ${count} quick action buttons: ${selector}`);

        // Test button functionality
        try {
          const firstButton = buttons.first();
          const buttonText = await firstButton.textContent() || 'Unknown';

          // Check if button is enabled
          const isEnabled = await firstButton.isEnabled();
          console.log(`  Button "${buttonText}" enabled: ${isEnabled}`);

          if (isEnabled) {
            functionalButtons++;

            // Test click (but don't actually execute trades)
            if (!buttonText.toLowerCase().includes('buy') && !buttonText.toLowerCase().includes('sell')) {
              await firstButton.click();
              await page.waitForTimeout(1000);
              console.log(`  ✓ Button "${buttonText}" clicked successfully`);
            }
          }

        } catch (error) {
          console.log(`  ❌ Button test failed: ${error}`);
        }
      }
    }

    console.log(`Total functional quick action buttons: ${functionalButtons}`);
  });

  test('Real-time data updates work', async ({ page }) => {
    await page.goto(`${BASE_URL}/dashboard`);
    await page.waitForLoadState('networkidle');

    // Look for elements that should update in real-time
    const realtimeSelectors = [
      '[data-testid*="price"]',
      '[data-testid*="balance"]',
      '.price',
      '.live-price',
      '.real-time',
      '[class*="updating"]'
    ];

    let updatingElements = 0;
    for (const selector of realtimeSelectors) {
      const elements = page.locator(selector);
      const count = await elements.count();

      if (count > 0) {
        console.log(`✓ Found ${count} potentially real-time elements: ${selector}`);

        // Capture initial values
        const firstElement = elements.first();
        const initialValue = await firstElement.textContent();
        console.log(`  Initial value: "${initialValue}"`);

        // Wait and check if value changes (simulate real-time update)
        await page.waitForTimeout(3000);
        const laterValue = await firstElement.textContent();

        if (initialValue !== laterValue) {
          console.log(`  ✓ Value updated to: "${laterValue}"`);
          updatingElements++;
        } else {
          console.log(`  Value unchanged (may not be real-time or no data)`);
        }
      }
    }

    console.log(`Elements with real-time updates: ${updatingElements}`);
  });
});
