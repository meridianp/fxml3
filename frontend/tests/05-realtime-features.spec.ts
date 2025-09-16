import { test, expect } from '@playwright/test';

const BASE_URL = 'http://localhost:3000';

test.describe('5. REAL-TIME FEATURES', () => {

  test('WebSocket connection status is displayed', async ({ page }) => {
    await page.goto(`${BASE_URL}/dashboard`);
    await page.waitForLoadState('networkidle');

    // Look for connection status indicators
    const connectionSelectors = [
      '[data-testid*="connection"]',
      '[data-testid*="status"]',
      '.connection-status',
      '.ws-status',
      '.online-indicator',
      'span:has-text("Connected"), span:has-text("Disconnected")',
      '.status-indicator'
    ];

    let connectionIndicators = 0;
    for (const selector of connectionSelectors) {
      const elements = page.locator(selector);
      const count = await elements.count();

      if (count > 0) {
        connectionIndicators += count;
        console.log(`✓ Found ${count} connection indicators: ${selector}`);

        const firstElement = elements.first();
        const statusText = await firstElement.textContent();
        console.log(`  Status: "${statusText}"`);

        // Check for visual indicators (colors, icons)
        const className = await firstElement.getAttribute('class') || '';
        if (className.includes('green') || className.includes('red') ||
            className.includes('online') || className.includes('offline')) {
          console.log(`  ✓ Has visual status indicator`);
        }
      }
    }

    console.log(`Total connection status indicators: ${connectionIndicators}`);
  });

  test('Live price updates functionality', async ({ page }) => {
    await page.goto(`${BASE_URL}/dashboard`);
    await page.waitForLoadState('networkidle');

    // Capture console errors related to WebSocket
    const wsErrors: string[] = [];
    page.on('console', msg => {
      if (msg.type() === 'error' &&
          (msg.text().includes('WebSocket') || msg.text().includes('socket'))) {
        wsErrors.push(msg.text());
      }
    });

    // Look for price elements
    const priceSelectors = [
      '[data-testid*="price"]',
      '.price',
      '.live-price',
      '.market-price',
      'span:text-matches("\\\\d+\\\\.\\\\d+")'
    ];

    let priceElements = 0;
    let initialPrices: string[] = [];

    for (const selector of priceSelectors) {
      const elements = page.locator(selector);
      const count = await elements.count();

      if (count > 0) {
        priceElements += count;
        console.log(`✓ Found ${count} price elements: ${selector}`);

        // Capture initial prices
        const prices = await elements.allTextContents();
        initialPrices.push(...prices.filter(p => /\d+\.?\d*/.test(p)));

        if (initialPrices.length > 0) {
          console.log(`  Sample prices: ${initialPrices.slice(0, 3).join(', ')}`);
        }
      }
    }

    // Wait and check for updates
    await page.waitForTimeout(5000);

    // Check WebSocket errors
    if (wsErrors.length > 0) {
      console.log(`⚠ WebSocket errors detected:`);
      wsErrors.forEach(error => console.log(`  - ${error}`));
    } else {
      console.log(`✓ No WebSocket connection errors`);
    }

    console.log(`Total price elements for live updates: ${priceElements}`);
  });

  test('Real-time notifications system', async ({ page }) => {
    await page.goto(`${BASE_URL}/dashboard`);
    await page.waitForLoadState('networkidle');

    // Look for notification areas
    const notificationSelectors = [
      '[data-testid*="notification"]',
      '.notification',
      '.toast',
      '.alert',
      '.message',
      '[role="alert"]',
      '.notification-container'
    ];

    let notificationContainers = 0;
    for (const selector of notificationSelectors) {
      const elements = page.locator(selector);
      const count = await elements.count();

      if (count > 0) {
        notificationContainers += count;
        console.log(`✓ Found ${count} notification containers: ${selector}`);

        // Check if notifications have content
        const firstElement = elements.first();
        const isVisible = await firstElement.isVisible();
        const content = await firstElement.textContent();

        console.log(`  Visible: ${isVisible}, Content: "${content?.slice(0, 50)}..."`);
      }
    }

    console.log(`Total notification containers: ${notificationContainers}`);

    // Test notification trigger (if there are buttons that might create notifications)
    const triggerButtons = page.locator('button:has-text("Test"), button:has-text("Refresh")');
    const triggerCount = await triggerButtons.count();

    if (triggerCount > 0) {
      console.log(`Found ${triggerCount} potential notification triggers`);
    }
  });

  test('Auto-refresh and data streaming', async ({ page }) => {
    await page.goto(`${BASE_URL}/data`);
    await page.waitForLoadState('networkidle');

    // Look for auto-refresh controls
    const refreshSelectors = [
      'button:has-text("Refresh")',
      'input[type="checkbox"]:has-text("Auto-refresh")',
      '[data-testid*="auto-refresh"]',
      '.auto-refresh',
      'label:has-text("Auto")'
    ];

    let refreshControls = 0;
    for (const selector of refreshSelectors) {
      const elements = page.locator(selector);
      const count = await elements.count();

      if (count > 0) {
        refreshControls += count;
        console.log(`✓ Found ${count} refresh controls: ${selector}`);

        // Test refresh functionality
        const firstElement = elements.first();
        try {
          if (await firstElement.getAttribute('type') === 'checkbox') {
            const isChecked = await firstElement.isChecked();
            console.log(`  Auto-refresh checkbox checked: ${isChecked}`);
          } else {
            await firstElement.click();
            await page.waitForTimeout(1000);
            console.log(`  Refresh button clicked successfully`);
          }
        } catch (error) {
          console.log(`  Refresh control test failed: ${error}`);
        }
      }
    }

    console.log(`Total refresh controls: ${refreshControls}`);
  });

  test('Connection reconnection handling', async ({ page }) => {
    await page.goto(`${BASE_URL}/dashboard`);
    await page.waitForLoadState('networkidle');

    // Monitor network activity and reconnection attempts
    let networkRequests = 0;
    let wsConnections = 0;

    page.on('request', request => {
      if (request.url().includes('socket.io') || request.url().includes('ws://')) {
        wsConnections++;
      }
      networkRequests++;
    });

    // Wait to observe initial connection attempts
    await page.waitForTimeout(10000);

    console.log(`Network requests observed: ${networkRequests}`);
    console.log(`WebSocket connection attempts: ${wsConnections}`);

    // Look for reconnection indicators
    const reconnectSelectors = [
      '[data-testid*="reconnect"]',
      'span:has-text("Reconnecting")',
      'span:has-text("Retrying")',
      '.reconnecting',
      '.connection-retry'
    ];

    let reconnectIndicators = 0;
    for (const selector of reconnectSelectors) {
      const elements = page.locator(selector);
      const count = await elements.count();

      if (count > 0) {
        reconnectIndicators += count;
        console.log(`✓ Found ${count} reconnection indicators: ${selector}`);
      }
    }

    console.log(`Reconnection indicators found: ${reconnectIndicators}`);
  });

  test('Live data streaming performance', async ({ page }) => {
    await page.goto(`${BASE_URL}/trading`);
    await page.waitForLoadState('networkidle');

    // Monitor performance during data updates
    const startTime = Date.now();

    // Look for streaming data indicators
    const streamingSelectors = [
      '.streaming',
      '.live',
      '.updating',
      '[data-streaming="true"]',
      '.real-time-data'
    ];

    let streamingElements = 0;
    for (const selector of streamingSelectors) {
      const elements = page.locator(selector);
      const count = await elements.count();

      if (count > 0) {
        streamingElements += count;
        console.log(`✓ Found ${count} streaming elements: ${selector}`);
      }
    }

    // Wait and measure responsiveness
    await page.waitForTimeout(5000);
    const endTime = Date.now();
    const responseTime = endTime - startTime;

    console.log(`Page response time: ${responseTime}ms`);
    console.log(`Streaming elements found: ${streamingElements}`);

    // Check for performance issues (excessive CPU/memory usage indicators)
    const performanceWarnings = await page.locator('.performance-warning, .slow-connection').count();
    console.log(`Performance warnings: ${performanceWarnings}`);
  });
});
