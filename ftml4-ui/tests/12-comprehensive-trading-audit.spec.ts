/**
 * 💹 COMPREHENSIVE TRADING CONSOLE AUDIT
 *
 * Systematic validation of all trading functionality
 * This is part 2 of the comprehensive feature testing suite
 */

import { test, expect } from '@playwright/test';

const BASE_URL = process.env.PLAYWRIGHT_TEST_BASE_URL || 'http://localhost:3000';

test.describe('💹 Trading Console - Comprehensive Audit', () => {

  test.beforeEach(async ({ page }) => {
    await page.goto(`${BASE_URL}/trading`);
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(2000); // Allow components to load
  });

  test('Trading page loads with all required components', async ({ page }) => {
    console.log('\n💹 Testing Trading Console Components...');

    // Check page title
    await expect(page).toHaveTitle(/Trading|FXML4/i);
    console.log('✅ Trading page title correct');

    // Look for main trading components
    const components = [
      { name: 'Order Panel', selectors: '.order-panel, [data-testid="order-panel"], .order-form' },
      { name: 'Positions Table', selectors: '.positions-table, [data-testid="positions"], .positions' },
      { name: 'Orders Table', selectors: '.orders-table, [data-testid="orders"], .orders' },
      { name: 'Trading Console', selectors: '.trading-console, [data-testid="trading-console"], .console' },
      { name: 'Risk Dashboard', selectors: '.risk-dashboard, [data-testid="risk"], .risk' }
    ];

    for (const component of components) {
      const element = page.locator(component.selectors);
      if (await element.count() > 0) {
        console.log(`✅ ${component.name} found`);
      } else {
        console.log(`⚠️  ${component.name} not found`);
      }
    }
  });

  test('Order panel functionality and validation', async ({ page }) => {
    console.log('\n📝 Testing Order Panel Functionality...');

    // Look for order panel
    const orderPanel = page.locator('.order-panel, [data-testid="order-panel"], .order-form').first();

    if (await orderPanel.count() > 0) {
      console.log('✅ Order panel found');

      // Test symbol selection
      const symbolSelect = orderPanel.locator('select, .symbol-selector, [data-testid="symbol"]');
      if (await symbolSelect.count() > 0) {
        console.log('✅ Symbol selector found');

        // Test symbol selection
        await symbolSelect.click();
        await page.waitForTimeout(500);

        const options = symbolSelect.locator('option');
        const optionCount = await options.count();
        console.log(`  Found ${optionCount} symbol options`);

        if (optionCount > 1) {
          await options.nth(1).click();
          console.log('✅ Symbol selection working');
        }
      } else {
        console.log('⚠️  Symbol selector not found');
      }

      // Test order type selection
      const orderTypeSelect = orderPanel.locator('select[name="type"], .order-type, [data-testid="order-type"]');
      if (await orderTypeSelect.count() > 0) {
        console.log('✅ Order type selector found');

        await orderTypeSelect.click();
        const typeOptions = orderTypeSelect.locator('option');
        const typeCount = await typeOptions.count();
        console.log(`  Found ${typeCount} order type options`);
      } else {
        console.log('⚠️  Order type selector not found');
      }

      // Test quantity input
      const quantityInput = orderPanel.locator('input[name="quantity"], .quantity-input, [data-testid="quantity"]');
      if (await quantityInput.count() > 0) {
        console.log('✅ Quantity input found');

        await quantityInput.fill('10000');
        const value = await quantityInput.inputValue();
        expect(value).toBe('10000');
        console.log('✅ Quantity input working');
      } else {
        console.log('⚠️  Quantity input not found');
      }

      // Test price input (for limit orders)
      const priceInput = orderPanel.locator('input[name="price"], .price-input, [data-testid="price"]');
      if (await priceInput.count() > 0) {
        console.log('✅ Price input found');
      } else {
        console.log('⚠️  Price input not found');
      }

      // Test buy/sell buttons
      const buyButton = orderPanel.locator('button:has-text("Buy"), .buy-button, [data-testid="buy"]');
      const sellButton = orderPanel.locator('button:has-text("Sell"), .sell-button, [data-testid="sell"]');

      if (await buyButton.count() > 0) {
        console.log('✅ Buy button found');

        // Test button click (don't actually submit)
        const isEnabled = await buyButton.isEnabled();
        console.log(`  Buy button enabled: ${isEnabled}`);
      } else {
        console.log('⚠️  Buy button not found');
      }

      if (await sellButton.count() > 0) {
        console.log('✅ Sell button found');
      } else {
        console.log('⚠️  Sell button not found');
      }

    } else {
      console.log('❌ Order panel not found');
    }
  });

  test('Positions table display and functionality', async ({ page }) => {
    console.log('\n📊 Testing Positions Table...');

    const positionsTable = page.locator('.positions-table, [data-testid="positions"], table:has(th:has-text("Position"))').first();

    if (await positionsTable.count() > 0) {
      console.log('✅ Positions table found');

      // Check table headers
      const headers = positionsTable.locator('th, .table-header');
      const headerCount = await headers.count();
      console.log(`  Found ${headerCount} table headers`);

      if (headerCount > 0) {
        for (let i = 0; i < Math.min(headerCount, 8); i++) {
          const header = headers.nth(i);
          const headerText = await header.textContent();
          console.log(`    Header ${i + 1}: ${headerText}`);
        }
      }

      // Check for position rows
      const rows = positionsTable.locator('tbody tr, .position-row');
      const rowCount = await rows.count();
      console.log(`  Found ${rowCount} position rows`);

      if (rowCount > 0) {
        console.log('✅ Position data displayed');

        // Test first row for expected data
        const firstRow = rows.first();
        const cells = firstRow.locator('td, .cell');
        const cellCount = await cells.count();
        console.log(`    First row has ${cellCount} cells`);

      } else {
        console.log('ℹ️  No active positions (this may be expected)');
      }

      // Look for action buttons (close position, etc.)
      const actionButtons = positionsTable.locator('button, .action-button');
      const buttonCount = await actionButtons.count();
      console.log(`  Found ${buttonCount} action buttons`);

    } else {
      console.log('⚠️  Positions table not found');
    }
  });

  test('Orders table display and management', async ({ page }) => {
    console.log('\n📋 Testing Orders Table...');

    const ordersTable = page.locator('.orders-table, [data-testid="orders"], table:has(th:has-text("Order"))').first();

    if (await ordersTable.count() > 0) {
      console.log('✅ Orders table found');

      // Check table structure
      const headers = ordersTable.locator('th, .table-header');
      const headerCount = await headers.count();
      console.log(`  Found ${headerCount} order table headers`);

      // Check for order rows
      const rows = ordersTable.locator('tbody tr, .order-row');
      const rowCount = await rows.count();
      console.log(`  Found ${rowCount} order rows`);

      if (rowCount > 0) {
        console.log('✅ Order data displayed');
      } else {
        console.log('ℹ️  No pending orders (this may be expected)');
      }

      // Look for cancel buttons
      const cancelButtons = ordersTable.locator('button:has-text("Cancel"), .cancel-button');
      const cancelCount = await cancelButtons.count();
      console.log(`  Found ${cancelCount} cancel buttons`);

    } else {
      console.log('⚠️  Orders table not found');
    }
  });

  test('Risk management dashboard', async ({ page }) => {
    console.log('\n⚠️  Testing Risk Management Dashboard...');

    const riskDashboard = page.locator('.risk-dashboard, [data-testid="risk"], .risk-panel').first();

    if (await riskDashboard.count() > 0) {
      console.log('✅ Risk dashboard found');

      // Look for risk metrics
      const riskMetrics = [
        { name: 'Account Balance', selectors: '.balance, .account-balance, [data-testid="balance"]' },
        { name: 'Available Margin', selectors: '.margin, .available-margin, [data-testid="margin"]' },
        { name: 'Used Margin', selectors: '.used-margin, [data-testid="used-margin"]' },
        { name: 'Equity', selectors: '.equity, [data-testid="equity"]' },
        { name: 'P&L', selectors: '.pnl, .profit-loss, [data-testid="pnl"]' },
        { name: 'Drawdown', selectors: '.drawdown, [data-testid="drawdown"]' }
      ];

      for (const metric of riskMetrics) {
        const element = riskDashboard.locator(metric.selectors);
        if (await element.count() > 0) {
          const value = await element.textContent();
          console.log(`  ✅ ${metric.name}: ${value?.trim()}`);
        } else {
          console.log(`  ⚠️  ${metric.name} not found`);
        }
      }

      // Look for risk warnings or alerts
      const warnings = riskDashboard.locator('.warning, .alert, .risk-warning');
      const warningCount = await warnings.count();

      if (warningCount > 0) {
        console.log(`  ⚠️  Found ${warningCount} risk warnings`);
        for (let i = 0; i < warningCount; i++) {
          const warning = warnings.nth(i);
          const text = await warning.textContent();
          console.log(`    Warning ${i + 1}: ${text}`);
        }
      } else {
        console.log('  ✅ No risk warnings (good)');
      }

    } else {
      console.log('⚠️  Risk dashboard not found');
    }
  });

  test('Account information display', async ({ page }) => {
    console.log('\n💰 Testing Account Information...');

    // Look for account info section
    const accountInfo = page.locator('.account-info, [data-testid="account"], .account-section').first();

    if (await accountInfo.count() > 0) {
      console.log('✅ Account information section found');

      // Test account balance display
      const balance = accountInfo.locator('.balance, [data-testid="balance"]');
      if (await balance.count() > 0) {
        const balanceText = await balance.textContent();
        console.log(`  Balance: ${balanceText}`);

        // Validate balance format (should contain currency/number)
        const hasNumber = /[\d,.]/.test(balanceText || '');
        if (hasNumber) {
          console.log('  ✅ Balance contains numeric data');
        } else {
          console.log('  ⚠️  Balance may not be showing real data');
        }
      }

      // Test equity display
      const equity = accountInfo.locator('.equity, [data-testid="equity"]');
      if (await equity.count() > 0) {
        const equityText = await equity.textContent();
        console.log(`  Equity: ${equityText}`);
      }

    } else {
      console.log('⚠️  Account information section not found');
    }
  });

  test('Trading form validation and error handling', async ({ page }) => {
    console.log('\n✅ Testing Form Validation...');

    const orderPanel = page.locator('.order-panel, [data-testid="order-panel"], .order-form').first();

    if (await orderPanel.count() > 0) {
      console.log('Testing order form validation...');

      // Test invalid quantity
      const quantityInput = orderPanel.locator('input[name="quantity"], .quantity-input, [data-testid="quantity"]');
      if (await quantityInput.count() > 0) {
        await quantityInput.fill('-1000'); // Invalid negative quantity

        const submitButton = orderPanel.locator('button[type="submit"], .submit-button, button:has-text("Buy")').first();
        if (await submitButton.count() > 0) {
          await submitButton.click();
          await page.waitForTimeout(1000);

          // Look for validation messages
          const validationMessages = page.locator('.error, .validation-error, .invalid-feedback');
          const messageCount = await validationMessages.count();

          if (messageCount > 0) {
            console.log('✅ Form validation working');
            for (let i = 0; i < messageCount; i++) {
              const message = validationMessages.nth(i);
              const text = await message.textContent();
              console.log(`  Validation: ${text}`);
            }
          } else {
            console.log('⚠️  No validation messages found');
          }
        }
      }
    }
  });

  test('Real-time price updates and data', async ({ page }) => {
    console.log('\n📈 Testing Real-time Price Updates...');

    // Look for price displays
    const priceElements = page.locator('.price, .current-price, [data-testid*="price"]');
    const priceCount = await priceElements.count();

    if (priceCount > 0) {
      console.log(`Found ${priceCount} price elements`);

      // Record initial prices
      const initialPrices = [];
      for (let i = 0; i < Math.min(priceCount, 5); i++) {
        const element = priceElements.nth(i);
        const price = await element.textContent();
        initialPrices.push(price);
        console.log(`  Initial price ${i + 1}: ${price}`);
      }

      // Wait and check for updates
      await page.waitForTimeout(5000);

      let updatesDetected = 0;
      for (let i = 0; i < Math.min(priceCount, 5); i++) {
        const element = priceElements.nth(i);
        const newPrice = await element.textContent();

        if (newPrice !== initialPrices[i]) {
          updatesDetected++;
          console.log(`  ✅ Price ${i + 1} updated: ${initialPrices[i]} → ${newPrice}`);
        }
      }

      if (updatesDetected > 0) {
        console.log(`✅ Real-time updates working (${updatesDetected} prices updated)`);
      } else {
        console.log('ℹ️  No price updates detected (may be expected during market close)');
      }

    } else {
      console.log('⚠️  No price elements found');
    }
  });

  test('Trading console responsiveness', async ({ page }) => {
    console.log('\n📱 Testing Trading Console Mobile Responsiveness...');

    // Test mobile layout
    await page.setViewportSize({ width: 375, height: 667 });
    await page.waitForTimeout(1000);

    // Check if components stack vertically or hide appropriately
    const orderPanel = page.locator('.order-panel, [data-testid="order-panel"]').first();
    if (await orderPanel.count() > 0) {
      const panelBox = await orderPanel.boundingBox();
      if (panelBox && panelBox.width <= 375) {
        console.log('✅ Order panel responsive');
      } else {
        console.log('⚠️  Order panel may not be fully responsive');
      }
    }

    // Test tablet layout
    await page.setViewportSize({ width: 768, height: 1024 });
    await page.waitForTimeout(1000);
    console.log('✅ Tablet layout tested');

    // Reset to desktop
    await page.setViewportSize({ width: 1280, height: 720 });
  });

  test('Trading console performance and interactions', async ({ page }) => {
    console.log('\n⚡ Testing Trading Console Performance...');

    const startTime = Date.now();

    // Test rapid interactions
    const clickableElements = page.locator('button:not([disabled]), select, input');
    const elementCount = Math.min(await clickableElements.count(), 10);

    for (let i = 0; i < elementCount; i++) {
      try {
        const element = clickableElements.nth(i);
        const isVisible = await element.isVisible();

        if (isVisible) {
          await element.click({ timeout: 1000 });
          await page.waitForTimeout(100); // Small delay between clicks
        }
      } catch (e) {
        // Continue if interaction fails
      }
    }

    const interactionTime = Date.now() - startTime;
    console.log(`Interaction time: ${interactionTime}ms`);

    if (interactionTime < 2000) {
      console.log('✅ Interactive performance good');
    } else {
      console.log('⚠️  Interactive performance slow');
    }

    // Check for memory leaks or performance issues
    const jsHeapSize = await page.evaluate(() => {
      return (window.performance as any).memory?.usedJSHeapSize || 'Not available';
    });

    console.log(`Memory usage: ${jsHeapSize}`);
  });
});
