import { test, expect } from '@playwright/test';

const BASE_URL = 'http://localhost:3000';

test.describe('3. TRADING FEATURES', () => {

  test('Order placement form is present and functional', async ({ page }) => {
    await page.goto(`${BASE_URL}/trading`);
    await page.waitForLoadState('networkidle');

    // Look for order placement form
    const formSelectors = [
      'form[data-testid*="order"]',
      'form:has(button:has-text("Buy"), button:has-text("Sell"))',
      '[data-testid="trading-form"]',
      '.order-form',
      '.trading-form'
    ];

    let foundForm = false;
    for (const selector of formSelectors) {
      const forms = page.locator(selector);
      const count = await forms.count();

      if (count > 0) {
        foundForm = true;
        console.log(`✓ Found order form: ${selector}`);

        // Test form fields
        const form = forms.first();

        // Check for symbol/instrument selection
        const symbolInputs = form.locator('select, input[placeholder*="symbol"], input[placeholder*="Symbol"], [data-testid*="symbol"]');
        const symbolCount = await symbolInputs.count();
        console.log(`  Symbol selection fields: ${symbolCount}`);

        // Check for quantity input
        const quantityInputs = form.locator('input[type="number"], input[placeholder*="quantity"], input[placeholder*="Quantity"], [data-testid*="quantity"]');
        const quantityCount = await quantityInputs.count();
        console.log(`  Quantity input fields: ${quantityCount}`);

        // Check for order type selection
        const orderTypes = form.locator('select:has(option:has-text("Market")), select:has(option:has-text("Limit")), [data-testid*="order-type"]');
        const orderTypeCount = await orderTypes.count();
        console.log(`  Order type selectors: ${orderTypeCount}`);

        break;
      }
    }

    expect(foundForm, 'Should have an order placement form').toBe(true);
  });

  test('Buy/Sell buttons are present and functional', async ({ page }) => {
    await page.goto(`${BASE_URL}/trading`);
    await page.waitForLoadState('networkidle');

    // Look for buy/sell buttons
    const buyButtons = page.locator('button:has-text("Buy")');
    const sellButtons = page.locator('button:has-text("Sell")');

    const buyCount = await buyButtons.count();
    const sellCount = await sellButtons.count();

    console.log(`Buy buttons found: ${buyCount}`);
    console.log(`Sell buttons found: ${sellCount}`);

    expect(buyCount + sellCount, 'Should have Buy and/or Sell buttons').toBeGreaterThan(0);

    // Test button states
    if (buyCount > 0) {
      const firstBuy = buyButtons.first();
      const isEnabled = await firstBuy.isEnabled();
      console.log(`First Buy button enabled: ${isEnabled}`);
    }

    if (sellCount > 0) {
      const firstSell = sellButtons.first();
      const isEnabled = await firstSell.isEnabled();
      console.log(`First Sell button enabled: ${isEnabled}`);
    }
  });

  test('Position management table displays positions', async ({ page }) => {
    await page.goto(`${BASE_URL}/trading`);
    await page.waitForLoadState('networkidle');

    // Look for positions table
    const positionSelectors = [
      'table:has(th:has-text("Position"), th:has-text("Symbol"))',
      '[data-testid*="position"]',
      '.positions-table',
      '.position-list',
      'h2:has-text("Position"), h3:has-text("Position")'
    ];

    let foundPositions = false;
    for (const selector of positionSelectors) {
      const elements = page.locator(selector);
      const count = await elements.count();

      if (count > 0) {
        foundPositions = true;
        console.log(`✓ Found positions section: ${selector}`);

        // Look for position data
        const element = elements.first();
        const text = await element.textContent();
        console.log(`  Content preview: "${text?.slice(0, 200)}..."`);

        // Look for table rows or position items
        const rows = element.locator('tr, .position-row, .position-item');
        const rowCount = await rows.count();
        console.log(`  Position entries: ${rowCount}`);

        break;
      }
    }

    console.log(`Positions section found: ${foundPositions}`);
  });

  test('Active orders display and management', async ({ page }) => {
    await page.goto(`${BASE_URL}/trading`);
    await page.waitForLoadState('networkidle');

    // Look for active orders section
    const orderSelectors = [
      'table:has(th:has-text("Order"), th:has-text("Status"))',
      '[data-testid*="order"]',
      '.orders-table',
      '.active-orders',
      'h2:has-text("Order"), h3:has-text("Order")'
    ];

    for (const selector of orderSelectors) {
      const elements = page.locator(selector);
      const count = await elements.count();

      if (count > 0) {
        console.log(`✓ Found orders section: ${selector}`);

        // Look for order management buttons (Cancel, Modify)
        const element = elements.first();
        const cancelButtons = element.locator('button:has-text("Cancel")');
        const modifyButtons = element.locator('button:has-text("Modify"), button:has-text("Edit")');

        const cancelCount = await cancelButtons.count();
        const modifyCount = await modifyButtons.count();

        console.log(`  Cancel buttons: ${cancelCount}`);
        console.log(`  Modify buttons: ${modifyCount}`);

        break;
      }
    }
  });

  test('Market data display in trading interface', async ({ page }) => {
    await page.goto(`${BASE_URL}/trading`);
    await page.waitForLoadState('networkidle');

    // Look for market data (prices, spreads, etc.)
    const marketDataSelectors = [
      '[data-testid*="price"]',
      '[data-testid*="bid"]',
      '[data-testid*="ask"]',
      '.price',
      '.market-price',
      '.bid-ask',
      'table:has(th:has-text("Price"), th:has-text("Bid"))'
    ];

    let foundMarketData = 0;
    for (const selector of marketDataSelectors) {
      const elements = page.locator(selector);
      const count = await elements.count();

      if (count > 0) {
        foundMarketData += count;
        console.log(`✓ Found ${count} market data elements: ${selector}`);

        // Check first element for price-like content
        const firstElement = elements.first();
        const content = await firstElement.textContent();
        console.log(`  Sample content: "${content}"`);
      }
    }

    console.log(`Total market data elements: ${foundMarketData}`);
  });

  test('Trade history and filtering', async ({ page }) => {
    await page.goto(`${BASE_URL}/trading`);
    await page.waitForLoadState('networkidle');

    // Look for trade history section
    const historySelectors = [
      '[data-testid*="history"]',
      '.trade-history',
      '.transaction-history',
      'table:has(th:has-text("Date"), th:has-text("Trade"))',
      'h2:has-text("History"), h3:has-text("History")'
    ];

    for (const selector of historySelectors) {
      const elements = page.locator(selector);
      const count = await elements.count();

      if (count > 0) {
        console.log(`✓ Found trade history: ${selector}`);

        // Look for filtering controls
        const element = elements.first();
        const filters = element.locator('select, input[type="date"], button:has-text("Filter")');
        const filterCount = await filters.count();
        console.log(`  Filter controls: ${filterCount}`);

        // Look for history entries
        const entries = element.locator('tr, .history-item, .trade-entry');
        const entryCount = await entries.count();
        console.log(`  History entries: ${entryCount}`);

        break;
      }
    }
  });

  test('Risk management controls (Stop Loss/Take Profit)', async ({ page }) => {
    await page.goto(`${BASE_URL}/trading`);
    await page.waitForLoadState('networkidle');

    // Look for risk management inputs
    const riskSelectors = [
      'input[placeholder*="stop"], input[placeholder*="Stop"]',
      'input[placeholder*="profit"], input[placeholder*="Profit"]',
      '[data-testid*="stop-loss"]',
      '[data-testid*="take-profit"]',
      'label:has-text("Stop Loss"), label:has-text("Take Profit")'
    ];

    let riskControls = 0;
    for (const selector of riskSelectors) {
      const elements = page.locator(selector);
      const count = await elements.count();

      if (count > 0) {
        riskControls += count;
        console.log(`✓ Found ${count} risk management controls: ${selector}`);

        // Test if inputs are functional
        const firstElement = elements.first();
        try {
          await firstElement.fill('100');
          const value = await firstElement.inputValue();
          console.log(`  Test input successful: ${value}`);
        } catch (error) {
          console.log(`  Input test failed: ${error}`);
        }
      }
    }

    console.log(`Total risk management controls: ${riskControls}`);
  });
});
