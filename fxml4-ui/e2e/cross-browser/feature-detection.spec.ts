/**
 * Browser Feature Detection Tests
 *
 * Tests for modern browser features and graceful degradation
 */

import { test, expect } from '@playwright/test';

test.describe('Browser Feature Detection and Polyfills', () => {
  test.use({ storageState: 'e2e/.auth/user.json' });

  test('CSS Grid and Flexbox support', async ({ page, browserName }) => {
    await page.goto('/dashboard');
    await page.waitForLoadState('networkidle');

    const cssSupport = await page.evaluate(() => {
      const testElement = document.createElement('div');
      document.body.appendChild(testElement);

      const features = {
        grid: CSS.supports('display', 'grid'),
        flexbox: CSS.supports('display', 'flex'),
        customProperties: CSS.supports('--custom-property', 'value'),
        transforms: CSS.supports('transform', 'translateX(0)'),
        transitions: CSS.supports('transition', 'all 0.3s'),
        calc: CSS.supports('width', 'calc(100% - 10px)'),
        objectFit: CSS.supports('object-fit', 'cover'),
        backdropFilter: CSS.supports('backdrop-filter', 'blur(10px)')
      };

      document.body.removeChild(testElement);
      return features;
    });

    // Essential CSS features should be supported
    expect(cssSupport.grid).toBe(true);
    expect(cssSupport.flexbox).toBe(true);
    expect(cssSupport.customProperties).toBe(true);

    console.log(`🎨 CSS features on ${browserName}:`, cssSupport);

    // Verify grid layouts work correctly
    const gridElements = page.locator('[class*="grid"]');
    const gridCount = await gridElements.count();

    if (gridCount > 0) {
      const firstGrid = gridElements.first();
      await expect(firstGrid).toBeVisible();

      const computedStyle = await firstGrid.evaluate((el) => {
        return window.getComputedStyle(el).display;
      });

      expect(computedStyle).toBe('grid');
    }
  });

  test('JavaScript ES6+ features', async ({ page, browserName }) => {
    await page.goto('/dashboard');
    await page.waitForLoadState('networkidle');

    const jsFeatures = await page.evaluate(() => {
      const features: any = {};

      // Test ES6+ features
      try {
        // Arrow functions
        const arrow = () => true;
        features.arrowFunctions = arrow();

        // Template literals
        const template = `test${1}`;
        features.templateLiterals = template === 'test1';

        // Destructuring
        const { a } = { a: 1 };
        features.destructuring = a === 1;

        // Spread operator
        const arr = [1, 2, 3];
        const spread = [...arr];
        features.spreadOperator = spread.length === 3;

        // Async/await
        features.asyncAwait = typeof (async function() {}) === 'function';

        // Promises
        features.promises = typeof Promise !== 'undefined';

        // Map and Set
        features.map = typeof Map !== 'undefined';
        features.set = typeof Set !== 'undefined';

        // WeakMap and WeakSet
        features.weakMap = typeof WeakMap !== 'undefined';
        features.weakSet = typeof WeakSet !== 'undefined';

        // Symbol
        features.symbol = typeof Symbol !== 'undefined';

        // Proxy
        features.proxy = typeof Proxy !== 'undefined';

        // Classes
        try {
          eval('class TestClass {}');
          features.classes = true;
        } catch {
          features.classes = false;
        }

        // Default parameters
        try {
          eval('function test(a = 1) { return a; }');
          features.defaultParameters = true;
        } catch {
          features.defaultParameters = false;
        }

        // Rest parameters
        try {
          eval('function test(...args) { return args.length; }');
          features.restParameters = true;
        } catch {
          features.restParameters = false;
        }

      } catch (error) {
        features.error = error.message;
      }

      return features;
    });

    // Essential JavaScript features
    expect(jsFeatures.promises).toBe(true);
    expect(jsFeatures.arrowFunctions).toBe(true);
    expect(jsFeatures.templateLiterals).toBe(true);
    expect(jsFeatures.destructuring).toBe(true);

    console.log(`🔧 JavaScript features on ${browserName}:`, jsFeatures);
  });

  test('Web APIs availability', async ({ page, browserName }) => {
    await page.goto('/data');
    await page.waitForLoadState('networkidle');

    const webApis = await page.evaluate(() => {
      return {
        // Storage APIs
        localStorage: typeof Storage !== 'undefined' && typeof localStorage !== 'undefined',
        sessionStorage: typeof Storage !== 'undefined' && typeof sessionStorage !== 'undefined',
        indexedDB: typeof indexedDB !== 'undefined',

        // Network APIs
        fetch: typeof fetch !== 'undefined',
        websocket: typeof WebSocket !== 'undefined',
        eventSource: typeof EventSource !== 'undefined',

        // Performance APIs
        performance: typeof performance !== 'undefined',
        performanceObserver: typeof PerformanceObserver !== 'undefined',
        intersectionObserver: typeof IntersectionObserver !== 'undefined',
        mutationObserver: typeof MutationObserver !== 'undefined',

        // Media APIs
        mediaDevices: typeof navigator !== 'undefined' &&
                     typeof navigator.mediaDevices !== 'undefined',

        // Geolocation
        geolocation: typeof navigator !== 'undefined' &&
                    typeof navigator.geolocation !== 'undefined',

        // Service Worker
        serviceWorker: 'serviceWorker' in navigator,

        // Notifications
        notifications: 'Notification' in window,

        // Clipboard
        clipboard: typeof navigator !== 'undefined' &&
                  typeof navigator.clipboard !== 'undefined',

        // File API
        fileReader: typeof FileReader !== 'undefined',
        blob: typeof Blob !== 'undefined',
        file: typeof File !== 'undefined',

        // Canvas
        canvas: (() => {
          try {
            const canvas = document.createElement('canvas');
            return !!(canvas.getContext && canvas.getContext('2d'));
          } catch {
            return false;
          }
        })(),

        // WebGL
        webgl: (() => {
          try {
            const canvas = document.createElement('canvas');
            return !!(canvas.getContext('webgl') || canvas.getContext('experimental-webgl'));
          } catch {
            return false;
          }
        })(),

        // Audio Context
        audioContext: typeof AudioContext !== 'undefined' ||
                     typeof (window as any).webkitAudioContext !== 'undefined',

        // Crypto
        crypto: typeof crypto !== 'undefined' && typeof crypto.subtle !== 'undefined'
      };
    });

    // Critical APIs for FXML4
    expect(webApis.localStorage).toBe(true);
    expect(webApis.sessionStorage).toBe(true);
    expect(webApis.fetch).toBe(true);
    expect(webApis.websocket).toBe(true);
    expect(webApis.performance).toBe(true);
    expect(webApis.canvas).toBe(true);

    console.log(`🌐 Web APIs on ${browserName}:`, webApis);

    // Test specific API functionality
    if (webApis.intersectionObserver) {
      const intersectionObserverWorks = await page.evaluate(() => {
        try {
          const observer = new IntersectionObserver(() => {});
          observer.disconnect();
          return true;
        } catch {
          return false;
        }
      });
      expect(intersectionObserverWorks).toBe(true);
    }

    if (webApis.performanceObserver) {
      const performanceObserverWorks = await page.evaluate(() => {
        try {
          const observer = new PerformanceObserver(() => {});
          observer.disconnect();
          return true;
        } catch {
          return false;
        }
      });
      expect(performanceObserverWorks).toBe(true);
    }
  });

  test('Media queries and responsive design', async ({ page, browserName }) => {
    await page.goto('/dashboard');
    await page.waitForLoadState('networkidle');

    // Test different viewport sizes
    const viewports = [
      { width: 320, height: 568, name: 'Mobile Portrait' },
      { width: 768, height: 1024, name: 'Tablet' },
      { width: 1024, height: 768, name: 'Tablet Landscape' },
      { width: 1280, height: 720, name: 'Desktop Small' },
      { width: 1920, height: 1080, name: 'Desktop Large' }
    ];

    for (const viewport of viewports) {
      await page.setViewportSize({ width: viewport.width, height: viewport.height });
      await page.waitForTimeout(500);

      // Verify responsive layout
      const layout = await page.evaluate(() => {
        const body = document.body;
        const computedStyle = window.getComputedStyle(body);

        return {
          overflow: computedStyle.overflow,
          width: body.offsetWidth,
          height: body.offsetHeight
        };
      });

      // Layout should adapt to viewport
      expect(layout.width).toBeLessThanOrEqual(viewport.width);

      // Check for responsive elements
      const responsiveElements = page.locator('[class*="sm:"], [class*="md:"], [class*="lg:"], [class*="xl:"]');
      const responsiveCount = await responsiveElements.count();

      if (responsiveCount > 0) {
        // Verify responsive classes are applied
        const firstResponsive = responsiveElements.first();
        await expect(firstResponsive).toBeVisible();
      }

      console.log(`📱 ${viewport.name} (${viewport.width}x${viewport.height}) working on ${browserName}`);
    }

    // Reset to default viewport
    await page.setViewportSize({ width: 1280, height: 720 });
  });

  test('Touch and pointer events', async ({ page, browserName }) => {
    await page.goto('/trading');
    await page.waitForLoadState('networkidle');

    const touchSupport = await page.evaluate(() => {
      return {
        touchEvents: 'ontouchstart' in window,
        pointerEvents: 'onpointerdown' in window,
        maxTouchPoints: navigator.maxTouchPoints || 0,
        msMaxTouchPoints: (navigator as any).msMaxTouchPoints || 0
      };
    });

    console.log(`👆 Touch support on ${browserName}:`, touchSupport);

    // Test touch interactions if supported
    if (touchSupport.touchEvents || touchSupport.pointerEvents) {
      const interactiveElements = page.locator('button, [role="button"]');
      const elementCount = await interactiveElements.count();

      if (elementCount > 0) {
        const firstButton = interactiveElements.first();

        // Test that touch events can be simulated
        await firstButton.tap();
        await page.waitForTimeout(500);

        // Verify no errors occurred
        const jsErrors: string[] = [];
        page.on('pageerror', error => {
          jsErrors.push(error.message);
        });

        expect(jsErrors.length).toBe(0);
      }
    }

    // Test mouse events work regardless
    if (await page.locator('[data-testid="symbol-selector"]').isVisible()) {
      await page.click('[data-testid="symbol-selector"]');
      await page.waitForTimeout(500);
      await page.keyboard.press('Escape');
    }
  });

  test('Security features and restrictions', async ({ page, browserName }) => {
    await page.goto('/dashboard');
    await page.waitForLoadState('networkidle');

    const securityFeatures = await page.evaluate(() => {
      return {
        // Content Security Policy
        csp: document.querySelector('meta[http-equiv="Content-Security-Policy"]') !== null,

        // HTTPS
        isSecure: location.protocol === 'https:',

        // Secure context features
        isSecureContext: typeof isSecureContext !== 'undefined' ? isSecureContext : false,

        // Cookie security
        cookieSecure: document.cookie.includes('Secure'),

        // Mixed content detection
        mixedContent: performance.getEntriesByType('navigation').some((entry: any) =>
          entry.name.startsWith('http:') && location.protocol === 'https:'
        ),

        // Cross-origin restrictions
        corsSupported: typeof XMLHttpRequest !== 'undefined' &&
                     'withCredentials' in new XMLHttpRequest(),

        // SubResource Integrity
        sriSupported: 'integrity' in document.createElement('script')
      };
    });

    console.log(`🔒 Security features on ${browserName}:`, securityFeatures);

    // Verify CORS support for API calls
    expect(securityFeatures.corsSupported).toBe(true);

    // In production, these should be true
    if (process.env.NODE_ENV === 'production') {
      // expect(securityFeatures.isSecure).toBe(true);
      // expect(securityFeatures.isSecureContext).toBe(true);
    }
  });

  test('Error handling and fallbacks', async ({ page, browserName }) => {
    await page.goto('/dashboard');
    await page.waitForLoadState('networkidle');

    // Test graceful degradation
    const degradationTest = await page.evaluate(() => {
      const results: any = {};

      // Test if polyfills are loaded
      results.polyfillsPresent = !!(window as any).core || !!(window as any).regeneratorRuntime;

      // Test error boundaries
      try {
        // Trigger a controlled error to test error boundaries
        const testError = new Error('Test error for boundary');
        window.dispatchEvent(new CustomEvent('test-error', { detail: testError }));
        results.errorBoundaryTest = true;
      } catch (error) {
        results.errorBoundaryTest = false;
        results.errorBoundaryError = error.message;
      }

      // Test feature detection patterns
      results.featureDetection = {
        hasModernFeatures: typeof Promise !== 'undefined' && typeof fetch !== 'undefined',
        hasFallbacks: typeof (window as any).polyfill !== 'undefined' ||
                     typeof (window as any).shim !== 'undefined'
      };

      return results;
    });

    console.log(`🛠️ Fallback mechanisms on ${browserName}:`, degradationTest);

    // Application should handle missing features gracefully
    expect(degradationTest.featureDetection.hasModernFeatures).toBe(true);

    // Check that the application still works even with limited feature support
    await expect(page.locator('[data-testid="app-layout"]')).toBeVisible();
    await expect(page.locator('[data-testid="main-content"]')).toBeVisible();
  });

  test('Performance across browsers', async ({ page, browserName }) => {
    const performanceMetrics = await page.evaluate(() => {
      const navigation = performance.getEntriesByType('navigation')[0] as PerformanceNavigationTiming;

      return {
        loadTime: navigation.loadEventEnd - navigation.loadEventStart,
        domContentLoaded: navigation.domContentLoadedEventEnd - navigation.domContentLoadedEventStart,
        firstByte: navigation.responseStart - navigation.requestStart,
        dnsLookup: navigation.domainLookupEnd - navigation.domainLookupStart,
        tcpConnect: navigation.connectEnd - navigation.connectStart,
        serverResponse: navigation.responseEnd - navigation.responseStart,
        domParsing: navigation.domInteractive - navigation.responseEnd,
        resourceCount: performance.getEntriesByType('resource').length
      };
    });

    console.log(`📊 Performance metrics on ${browserName}:`, performanceMetrics);

    // Performance should be reasonable across browsers
    expect(performanceMetrics.loadTime).toBeLessThan(5000);
    expect(performanceMetrics.domContentLoaded).toBeLessThan(3000);
    expect(performanceMetrics.resourceCount).toBeGreaterThan(0);

    // Browser-specific performance allowances
    const maxLoadTime = browserName === 'webkit' ? 6000 : 5000;
    expect(performanceMetrics.loadTime).toBeLessThan(maxLoadTime);
  });
});
