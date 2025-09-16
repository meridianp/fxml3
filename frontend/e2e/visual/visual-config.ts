/**
 * Visual Regression Testing Configuration
 *
 * Configuration for visual testing including screenshot comparison settings,
 * baseline management, and CI/CD integration
 */

export interface VisualTestConfig {
  threshold: number;
  updateSnapshots: boolean;
  outputDir: string;
  baselineDir: string;
  diffDir: string;
  browsers: string[];
  viewports: ViewportConfig[];
  animations: 'disabled' | 'allow';
  maskSelectors: string[];
  ignoreRegions: RegionConfig[];
}

export interface ViewportConfig {
  name: string;
  width: number;
  height: number;
  deviceScaleFactor?: number;
  isMobile?: boolean;
  hasTouch?: boolean;
}

export interface RegionConfig {
  selector: string;
  reason: string;
}

export const defaultVisualConfig: VisualTestConfig = {
  threshold: 0.2, // 20% difference threshold
  updateSnapshots: process.env.UPDATE_SNAPSHOTS === 'true',
  outputDir: 'e2e-results/visual',
  baselineDir: 'e2e/visual/baselines',
  diffDir: 'e2e-results/visual/diffs',
  browsers: ['chromium', 'firefox', 'webkit'],
  animations: 'disabled',

  // Elements to mask (hide) in screenshots
  maskSelectors: [
    '[data-testid="current-time"]',
    '[data-testid="last-updated"]',
    '[data-testid="live-price"]',
    '[data-testid="websocket-status"]',
    '[data-testid="session-timer"]',
    '.timestamp',
    '.live-data',
    '.real-time-price',
    '.connection-status'
  ],

  // Regions to ignore during comparison
  ignoreRegions: [
    { selector: '[data-testid="advertisement"]', reason: 'Dynamic ad content' },
    { selector: '[data-testid="live-chat"]', reason: 'Real-time chat messages' },
    { selector: '[data-testid="notification-banner"]', reason: 'Dynamic notifications' }
  ],

  viewports: [
    {
      name: 'Desktop 4K',
      width: 3840,
      height: 2160,
      deviceScaleFactor: 2
    },
    {
      name: 'Desktop Large',
      width: 1920,
      height: 1080,
      deviceScaleFactor: 1
    },
    {
      name: 'Desktop Standard',
      width: 1280,
      height: 720,
      deviceScaleFactor: 1
    },
    {
      name: 'Desktop Small',
      width: 1024,
      height: 768,
      deviceScaleFactor: 1
    },
    {
      name: 'Tablet Landscape',
      width: 1024,
      height: 768,
      deviceScaleFactor: 1,
      isMobile: false,
      hasTouch: true
    },
    {
      name: 'Tablet Portrait',
      width: 768,
      height: 1024,
      deviceScaleFactor: 2,
      isMobile: false,
      hasTouch: true
    },
    {
      name: 'Mobile Large',
      width: 414,
      height: 896,
      deviceScaleFactor: 3,
      isMobile: true,
      hasTouch: true
    },
    {
      name: 'Mobile Standard',
      width: 375,
      height: 667,
      deviceScaleFactor: 2,
      isMobile: true,
      hasTouch: true
    },
    {
      name: 'Mobile Small',
      width: 320,
      height: 568,
      deviceScaleFactor: 2,
      isMobile: true,
      hasTouch: true
    }
  ]
};

export const ciVisualConfig: Partial<VisualTestConfig> = {
  threshold: 0.1, // Stricter threshold for CI
  browsers: ['chromium', 'firefox'], // Fewer browsers for CI speed
  viewports: [
    {
      name: 'Desktop Standard',
      width: 1280,
      height: 720,
      deviceScaleFactor: 1
    },
    {
      name: 'Mobile Standard',
      width: 375,
      height: 667,
      deviceScaleFactor: 2,
      isMobile: true,
      hasTouch: true
    }
  ]
};

export const localVisualConfig: Partial<VisualTestConfig> = {
  threshold: 0.3, // More lenient for local development
  browsers: ['chromium'], // Single browser for speed
  updateSnapshots: true, // Allow updates locally
  viewports: [
    {
      name: 'Desktop Standard',
      width: 1280,
      height: 720,
      deviceScaleFactor: 1
    }
  ]
};

export const componentTestConfig: Partial<VisualTestConfig> = {
  threshold: 0.1, // Strict for components
  animations: 'disabled',
  maskSelectors: [
    '[data-testid="timestamp"]',
    '.dynamic-content',
    '.live-indicator'
  ]
};

export const getVisualConfig = (environment: 'ci' | 'local' | 'comprehensive' = 'comprehensive'): VisualTestConfig => {
  const baseConfig = { ...defaultVisualConfig };

  switch (environment) {
    case 'ci':
      return { ...baseConfig, ...ciVisualConfig };
    case 'local':
      return { ...baseConfig, ...localVisualConfig };
    case 'comprehensive':
    default:
      return baseConfig;
  }
};

export const screenshotOptions = {
  fullPage: {
    fullPage: true,
    animations: 'disabled' as const,
    mask: defaultVisualConfig.maskSelectors.map(selector => ({ selector }))
  },

  component: {
    fullPage: false,
    animations: 'disabled' as const,
    mask: componentTestConfig.maskSelectors?.map(selector => ({ selector })) || []
  },

  mobile: {
    fullPage: true,
    animations: 'disabled' as const,
    mask: defaultVisualConfig.maskSelectors.map(selector => ({ selector })),
    clip: { x: 0, y: 0, width: 375, height: 667 }
  }
};

export const criticalPageSelectors = {
  dashboard: {
    main: '[data-testid="dashboard-main"]',
    analytics: '[data-testid="analytics-dashboard"]',
    performance: '[data-testid="performance-scorecard"]',
    charts: '[data-testid="chart-container"]'
  },

  trading: {
    console: '[data-testid="trading-console"]',
    orderPanel: '[data-testid="order-panel"]',
    symbolSelector: '[data-testid="symbol-selector"]',
    priceChart: '[data-testid="price-chart"]',
    orderBook: '[data-testid="order-book"]'
  },

  data: {
    dashboard: '[data-testid="data-management-dashboard"]',
    qualityMetrics: '[data-testid="data-quality-dashboard"]',
    sourceMonitor: '[data-testid="data-source-monitor"]',
    storageManager: '[data-testid="storage-manager"]'
  },

  training: {
    studio: '[data-testid="training-studio"]',
    experimentList: '[data-testid="experiment-list"]',
    modelConfig: '[data-testid="model-configuration"]',
    parameterOptimization: '[data-testid="parameter-optimization"]'
  },

  analytics: {
    dashboard: '[data-testid="analytics-dashboard"]',
    reportsManager: '[data-testid="reports-manager"]',
    exportManager: '[data-testid="export-manager"]',
    metricsView: '[data-testid="metrics-view"]'
  }
};

export const visualTestCategories = {
  smoke: {
    pages: ['dashboard', 'trading'],
    viewports: ['Desktop Standard', 'Mobile Standard'],
    browsers: ['chromium']
  },

  regression: {
    pages: ['dashboard', 'trading', 'data', 'training'],
    viewports: ['Desktop Standard', 'Desktop Small', 'Mobile Standard'],
    browsers: ['chromium', 'firefox']
  },

  comprehensive: {
    pages: ['dashboard', 'trading', 'data', 'training', 'analytics'],
    viewports: defaultVisualConfig.viewports.map(v => v.name),
    browsers: defaultVisualConfig.browsers
  }
};

export class VisualTestManager {
  private config: VisualTestConfig;

  constructor(environment: 'ci' | 'local' | 'comprehensive' = 'comprehensive') {
    this.config = getVisualConfig(environment);
  }

  getConfig(): VisualTestConfig {
    return this.config;
  }

  shouldUpdateSnapshots(): boolean {
    return this.config.updateSnapshots;
  }

  getThreshold(): number {
    return this.config.threshold;
  }

  getMaskSelectors(): string[] {
    return this.config.maskSelectors;
  }

  getViewportsForCategory(category: keyof typeof visualTestCategories): ViewportConfig[] {
    const categoryConfig = visualTestCategories[category];
    return this.config.viewports.filter(vp =>
      categoryConfig.viewports.includes(vp.name)
    );
  }

  getBrowsersForCategory(category: keyof typeof visualTestCategories): string[] {
    const categoryConfig = visualTestCategories[category];
    return this.config.browsers.filter(browser =>
      categoryConfig.browsers.includes(browser)
    );
  }

  getScreenshotPath(
    page: string,
    viewport: string,
    browser: string,
    suffix: string = ''
  ): string {
    const sanitizedViewport = viewport.toLowerCase().replace(/\s+/g, '-');
    const sanitizedSuffix = suffix ? `-${suffix}` : '';
    return `${page}-${sanitizedViewport}-${browser}${sanitizedSuffix}.png`;
  }

  async setupPage(page: any): Promise<void> {
    // Add global styles to hide dynamic content
    await page.addStyleTag({
      content: `
        /* Hide dynamic content for consistent screenshots */
        ${this.config.maskSelectors.join(', ')} {
          visibility: hidden !important;
          opacity: 0 !important;
        }

        /* Disable animations */
        *, *::before, *::after {
          animation-duration: 0s !important;
          animation-delay: 0s !important;
          transition-duration: 0s !important;
          transition-delay: 0s !important;
          scroll-behavior: auto !important;
        }

        /* Ensure consistent font rendering */
        * {
          -webkit-font-smoothing: antialiased !important;
          -moz-osx-font-smoothing: grayscale !important;
        }
      `
    });

    // Wait for any initial animations to complete
    await page.waitForTimeout(1000);
  }

  generateReport(results: any[]): string {
    const passed = results.filter(r => r.status === 'passed').length;
    const failed = results.filter(r => r.status === 'failed').length;
    const total = results.length;

    return `
# Visual Regression Test Report

## Summary
- **Total Tests**: ${total}
- **Passed**: ${passed}
- **Failed**: ${failed}
- **Success Rate**: ${((passed / total) * 100).toFixed(1)}%

## Configuration
- **Threshold**: ${this.config.threshold}
- **Browsers**: ${this.config.browsers.join(', ')}
- **Viewports**: ${this.config.viewports.length}
- **Update Mode**: ${this.config.updateSnapshots ? 'Enabled' : 'Disabled'}

## Results
${results.map(result => `
### ${result.name}
- **Status**: ${result.status}
- **Browser**: ${result.browser}
- **Viewport**: ${result.viewport}
${result.status === 'failed' ? `- **Diff**: [View Diff](${result.diffPath})` : ''}
`).join('\n')}
    `;
  }
}
