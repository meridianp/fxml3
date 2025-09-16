/**
 * Visual Testing Utilities
 *
 * Helper functions for visual regression testing including screenshot comparison,
 * baseline management, and reporting
 */

import { Page, expect } from '@playwright/test';
import { VisualTestConfig, ViewportConfig, criticalPageSelectors } from './visual-config';
import fs from 'fs/promises';
import path from 'path';

export class VisualTestHelper {
  private page: Page;
  private config: VisualTestConfig;

  constructor(page: Page, config: VisualTestConfig) {
    this.page = page;
    this.config = config;
  }

  /**
   * Setup page for consistent visual testing
   */
  async setupForVisualTesting(): Promise<void> {
    // Disable animations and transitions
    await this.page.addStyleTag({
      content: `
        *, *::before, *::after {
          animation-duration: 0s !important;
          animation-delay: 0s !important;
          transition-duration: 0s !important;
          transition-delay: 0s !important;
          scroll-behavior: auto !important;
        }

        /* Hide dynamic content */
        ${this.config.maskSelectors.join(', ')} {
          visibility: hidden !important;
          opacity: 0 !important;
        }

        /* Ensure consistent font rendering */
        * {
          -webkit-font-smoothing: antialiased !important;
          -moz-osx-font-smoothing: grayscale !important;
          text-rendering: optimizeLegibility !important;
        }

        /* Hide scrollbars for consistent screenshots */
        ::-webkit-scrollbar {
          display: none;
        }

        * {
          scrollbar-width: none;
          -ms-overflow-style: none;
        }
      `
    });

    // Wait for any initial rendering to complete
    await this.page.waitForTimeout(1000);
  }

  /**
   * Navigate to page and wait for stability
   */
  async navigateAndWait(url: string): Promise<void> {
    await this.page.goto(url);
    await this.page.waitForLoadState('networkidle');
    await this.waitForPageStability();
  }

  /**
   * Wait for page to be visually stable
   */
  async waitForPageStability(): Promise<void> {
    // Wait for fonts to load
    await this.page.waitForFunction(() => document.fonts.ready);

    // Wait for images to load
    await this.page.waitForFunction(() => {
      const images = Array.from(document.images);
      return images.every(img => img.complete);
    });

    // Wait for any lazy loading to complete
    await this.page.waitForTimeout(2000);

    // Scroll to trigger any lazy loading
    await this.page.evaluate(() => {
      window.scrollTo(0, document.body.scrollHeight);
    });
    await this.page.waitForTimeout(500);

    // Scroll back to top
    await this.page.evaluate(() => {
      window.scrollTo(0, 0);
    });
    await this.page.waitForTimeout(500);
  }

  /**
   * Set viewport with proper device characteristics
   */
  async setViewport(viewport: ViewportConfig): Promise<void> {
    await this.page.setViewportSize({
      width: viewport.width,
      height: viewport.height
    });

    // Set device scale factor if specified
    if (viewport.deviceScaleFactor) {
      await this.page.evaluate((scaleFactor) => {
        Object.defineProperty(window, 'devicePixelRatio', {
          value: scaleFactor,
          writable: false
        });
      }, viewport.deviceScaleFactor);
    }

    // Simulate touch if mobile device
    if (viewport.hasTouch) {
      await this.page.evaluate(() => {
        Object.defineProperty(navigator, 'maxTouchPoints', {
          value: 5,
          writable: false
        });
      });
    }
  }

  /**
   * Take a full page screenshot with masking
   */
  async takeFullPageScreenshot(name: string, options: any = {}): Promise<void> {
    await this.setupForVisualTesting();

    const screenshotOptions = {
      fullPage: true,
      animations: 'disabled' as const,
      threshold: this.config.threshold,
      ...options
    };

    await expect(this.page).toHaveScreenshot(name, screenshotOptions);
  }

  /**
   * Take a component screenshot
   */
  async takeComponentScreenshot(
    selector: string,
    name: string,
    options: any = {}
  ): Promise<void> {
    await this.setupForVisualTesting();

    const element = this.page.locator(selector);

    if (!(await element.isVisible())) {
      throw new Error(`Component ${selector} is not visible`);
    }

    const screenshotOptions = {
      animations: 'disabled' as const,
      threshold: this.config.threshold,
      ...options
    };

    await expect(element).toHaveScreenshot(name, screenshotOptions);
  }

  /**
   * Compare multiple theme states
   */
  async compareThemeStates(
    url: string,
    name: string,
    themes: string[] = ['light', 'dark']
  ): Promise<void> {
    for (const theme of themes) {
      await this.navigateAndWait(url);
      await this.setTheme(theme);
      await this.takeFullPageScreenshot(`${name}-${theme}-theme.png`);
    }
  }

  /**
   * Set application theme
   */
  async setTheme(theme: 'light' | 'dark'): Promise<void> {
    await this.page.evaluate((themeValue) => {
      if (themeValue === 'dark') {
        document.documentElement.classList.add('dark');
        document.body.classList.add('dark');
      } else {
        document.documentElement.classList.remove('dark');
        document.body.classList.remove('dark');
      }
    }, theme);

    // Wait for theme transition
    await this.page.waitForTimeout(1000);
  }

  /**
   * Test responsive behavior across viewports
   */
  async testResponsiveComponent(
    selector: string,
    name: string,
    viewports: ViewportConfig[]
  ): Promise<void> {
    for (const viewport of viewports) {
      await this.setViewport(viewport);
      await this.page.waitForTimeout(500);

      const componentName = `${name}-${viewport.name.toLowerCase().replace(/\s+/g, '-')}.png`;
      await this.takeComponentScreenshot(selector, componentName);
    }
  }

  /**
   * Test interactive states
   */
  async testInteractiveStates(
    selector: string,
    name: string,
    states: { action: string; stateName: string }[]
  ): Promise<void> {
    const element = this.page.locator(selector);

    for (const state of states) {
      // Reset to default state
      await this.page.reload();
      await this.waitForPageStability();

      // Perform action to reach state
      switch (state.action) {
        case 'hover':
          await element.hover();
          break;
        case 'focus':
          await element.focus();
          break;
        case 'click':
          await element.click();
          break;
        case 'disabled':
          await this.page.evaluate((sel) => {
            const el = document.querySelector(sel);
            if (el) el.setAttribute('disabled', 'true');
          }, selector);
          break;
      }

      await this.page.waitForTimeout(300);

      const stateName = `${name}-${state.stateName}.png`;
      await this.takeComponentScreenshot(selector, stateName);
    }
  }

  /**
   * Hide dynamic content elements
   */
  async hideDynamicContent(): Promise<void> {
    await this.page.addStyleTag({
      content: `
        ${this.config.maskSelectors.join(', ')} {
          visibility: hidden !important;
          opacity: 0 !important;
        }
      `
    });
  }

  /**
   * Wait for charts and visualizations to render
   */
  async waitForChartsToRender(): Promise<void> {
    // Wait for common chart libraries
    await this.page.waitForFunction(() => {
      // Check for Recharts
      const recharts = document.querySelector('.recharts-wrapper');
      if (recharts) return true;

      // Check for Lightweight Charts
      const lightweightCharts = document.querySelector('tr-widget');
      if (lightweightCharts) return true;

      // Check for Canvas-based charts
      const canvases = document.querySelectorAll('canvas');
      if (canvases.length > 0) {
        return Array.from(canvases).some(canvas =>
          canvas.width > 0 && canvas.height > 0
        );
      }

      return false;
    }, { timeout: 10000 }).catch(() => {
      // If no charts found, continue
    });

    // Additional wait for chart animations
    await this.page.waitForTimeout(2000);
  }

  /**
   * Generate visual diff report
   */
  static async generateDiffReport(
    baselinePath: string,
    currentPath: string,
    diffPath: string
  ): Promise<{ diffPercentage: number; hasDifferences: boolean }> {
    try {
      // This would integrate with image comparison library
      // For now, return mock data
      return {
        diffPercentage: 0,
        hasDifferences: false
      };
    } catch (error) {
      console.error('Error generating diff report:', error);
      return {
        diffPercentage: 100,
        hasDifferences: true
      };
    }
  }

  /**
   * Cleanup old screenshots
   */
  static async cleanupOldScreenshots(
    directory: string,
    maxAge: number = 7 * 24 * 60 * 60 * 1000 // 7 days
  ): Promise<void> {
    try {
      const files = await fs.readdir(directory);
      const now = Date.now();

      for (const file of files) {
        const filePath = path.join(directory, file);
        const stats = await fs.stat(filePath);

        if (now - stats.mtime.getTime() > maxAge) {
          await fs.unlink(filePath);
        }
      }
    } catch (error) {
      console.error('Error cleaning up screenshots:', error);
    }
  }
}

/**
 * Get page-specific selectors for testing
 */
export function getPageSelectors(page: string): Record<string, string> {
  return criticalPageSelectors[page as keyof typeof criticalPageSelectors] || {};
}

/**
 * Create viewport configuration for testing
 */
export function createViewport(
  name: string,
  width: number,
  height: number,
  options: Partial<ViewportConfig> = {}
): ViewportConfig {
  return {
    name,
    width,
    height,
    deviceScaleFactor: 1,
    isMobile: width < 768,
    hasTouch: width < 1024,
    ...options
  };
}

/**
 * Wait for network to be idle with retries
 */
export async function waitForNetworkIdle(
  page: Page,
  timeout: number = 30000,
  retries: number = 3
): Promise<void> {
  for (let i = 0; i < retries; i++) {
    try {
      await page.waitForLoadState('networkidle', { timeout });
      return;
    } catch (error) {
      if (i === retries - 1) throw error;
      await page.waitForTimeout(1000);
    }
  }
}

/**
 * Ensure directory exists for screenshots
 */
export async function ensureScreenshotDirectory(dirPath: string): Promise<void> {
  try {
    await fs.access(dirPath);
  } catch {
    await fs.mkdir(dirPath, { recursive: true });
  }
}

/**
 * Generate screenshot metadata
 */
export function generateScreenshotMetadata(
  testName: string,
  viewport: ViewportConfig,
  browser: string,
  timestamp: Date = new Date()
): any {
  return {
    testName,
    viewport: {
      name: viewport.name,
      width: viewport.width,
      height: viewport.height,
      deviceScaleFactor: viewport.deviceScaleFactor
    },
    browser,
    timestamp: timestamp.toISOString(),
    environment: process.env.NODE_ENV || 'test',
    commit: process.env.GITHUB_SHA || 'unknown'
  };
}
