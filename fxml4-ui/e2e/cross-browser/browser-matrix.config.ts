/**
 * Browser Test Matrix Configuration
 *
 * Comprehensive browser testing matrix for cross-platform compatibility
 */

import { defineConfig, devices } from '@playwright/test';

export const browserMatrix = {
  // Desktop browsers
  desktop: {
    chrome: {
      name: 'Desktop Chrome',
      use: devices['Desktop Chrome'],
      project: 'chrome-desktop',
      priority: 'high'
    },
    firefox: {
      name: 'Desktop Firefox',
      use: devices['Desktop Firefox'],
      project: 'firefox-desktop',
      priority: 'high'
    },
    safari: {
      name: 'Desktop Safari',
      use: devices['Desktop Safari'],
      project: 'safari-desktop',
      priority: 'medium'
    },
    edge: {
      name: 'Desktop Edge',
      use: { ...devices['Desktop Edge'], channel: 'msedge' },
      project: 'edge-desktop',
      priority: 'medium'
    }
  },

  // Mobile browsers
  mobile: {
    chromeAndroid: {
      name: 'Chrome Android',
      use: devices['Galaxy S21'],
      project: 'chrome-mobile',
      priority: 'high'
    },
    safariIOS: {
      name: 'Safari iOS',
      use: devices['iPhone 12'],
      project: 'safari-mobile',
      priority: 'high'
    },
    firefoxAndroid: {
      name: 'Firefox Android',
      use: { ...devices['Galaxy S21'], browserName: 'firefox' },
      project: 'firefox-mobile',
      priority: 'low'
    }
  },

  // Tablet browsers
  tablet: {
    iPadSafari: {
      name: 'iPad Safari',
      use: devices['iPad Pro'],
      project: 'ipad-safari',
      priority: 'medium'
    },
    androidTablet: {
      name: 'Android Tablet',
      use: devices['Galaxy Tab S4'],
      project: 'android-tablet',
      priority: 'low'
    }
  },

  // Legacy browsers (for compatibility testing)
  legacy: {
    chromeOld: {
      name: 'Chrome 90',
      use: {
        ...devices['Desktop Chrome'],
        channel: 'chrome',
        launchOptions: {
          args: ['--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/90.0.4430.212 Safari/537.36']
        }
      },
      project: 'chrome-legacy',
      priority: 'low'
    }
  }
};

export const testScenarios = {
  // Core functionality tests
  core: {
    authentication: ['login', 'logout', 'session-management'],
    navigation: ['page-routing', 'deep-linking', 'browser-history'],
    forms: ['input-validation', 'form-submission', 'field-interactions'],
    ui: ['responsive-layout', 'component-rendering', 'theme-switching']
  },

  // Feature-specific tests
  features: {
    trading: ['order-placement', 'symbol-selection', 'chart-interaction'],
    dataManagement: ['data-visualization', 'real-time-updates', 'export-functionality'],
    analytics: ['dashboard-interaction', 'report-generation', 'kpi-monitoring'],
    mlTraining: ['model-configuration', 'training-workflow', 'experiment-tracking']
  },

  // Performance tests
  performance: {
    loading: ['initial-load', 'route-transitions', 'component-mounting'],
    interaction: ['click-response', 'scroll-performance', 'animation-smoothness'],
    memory: ['memory-leaks', 'gc-pressure', 'long-running-sessions']
  },

  // Compatibility tests
  compatibility: {
    apis: ['web-apis', 'es6-features', 'polyfill-effectiveness'],
    css: ['grid-layout', 'flexbox', 'custom-properties', 'animations'],
    media: ['responsive-design', 'high-dpi', 'dark-mode'],
    accessibility: ['screen-reader', 'keyboard-navigation', 'color-contrast']
  }
};

export const browserCapabilities = {
  chrome: {
    webgl: true,
    webrtc: true,
    serviceWorker: true,
    pushNotifications: true,
    webAssembly: true,
    sharedArrayBuffer: true,
    es2020: true,
    cssGrid: true,
    cssCustomProperties: true,
    intersectionObserver: true,
    performanceObserver: true
  },
  firefox: {
    webgl: true,
    webrtc: true,
    serviceWorker: true,
    pushNotifications: true,
    webAssembly: true,
    sharedArrayBuffer: false, // Security restrictions
    es2020: true,
    cssGrid: true,
    cssCustomProperties: true,
    intersectionObserver: true,
    performanceObserver: true
  },
  safari: {
    webgl: true,
    webrtc: true,
    serviceWorker: true,
    pushNotifications: false, // iOS restrictions
    webAssembly: true,
    sharedArrayBuffer: false,
    es2020: true,
    cssGrid: true,
    cssCustomProperties: true,
    intersectionObserver: true,
    performanceObserver: false // Limited support
  },
  edge: {
    webgl: true,
    webrtc: true,
    serviceWorker: true,
    pushNotifications: true,
    webAssembly: true,
    sharedArrayBuffer: true,
    es2020: true,
    cssGrid: true,
    cssCustomProperties: true,
    intersectionObserver: true,
    performanceObserver: true
  }
};

export const platformSpecificTests = {
  windows: {
    browsers: ['chrome', 'firefox', 'edge'],
    specificTests: [
      'windows-notifications',
      'file-system-access',
      'clipboard-api'
    ]
  },
  macos: {
    browsers: ['chrome', 'firefox', 'safari'],
    specificTests: [
      'safari-specific-features',
      'mac-keyboard-shortcuts',
      'trackpad-gestures'
    ]
  },
  linux: {
    browsers: ['chrome', 'firefox'],
    specificTests: [
      'linux-specific-fonts',
      'gtk-theming',
      'wayland-support'
    ]
  },
  ios: {
    browsers: ['safari'],
    specificTests: [
      'ios-safari-quirks',
      'touch-interactions',
      'pwa-capabilities',
      'viewport-meta'
    ]
  },
  android: {
    browsers: ['chrome', 'firefox'],
    specificTests: [
      'android-chrome-features',
      'touch-interactions',
      'viewport-handling',
      'keyboard-behavior'
    ]
  }
};

export const testPriorities = {
  critical: [
    'authentication',
    'navigation',
    'core-trading-functionality',
    'data-visualization',
    'responsive-layout'
  ],
  high: [
    'form-interactions',
    'real-time-updates',
    'performance-benchmarks',
    'error-handling'
  ],
  medium: [
    'advanced-features',
    'analytics-interaction',
    'export-functionality',
    'theme-switching'
  ],
  low: [
    'edge-cases',
    'legacy-browser-support',
    'experimental-features'
  ]
};

export const getTestConfiguration = (environment: 'ci' | 'local' | 'comprehensive') => {
  const baseConfig = {
    timeout: 30000,
    retries: 2,
    workers: 4
  };

  switch (environment) {
    case 'ci':
      return {
        ...baseConfig,
        browsers: ['chrome-desktop', 'firefox-desktop'],
        scenarios: ['core', 'features.trading'],
        priorities: ['critical', 'high'],
        workers: 2,
        timeout: 60000
      };

    case 'local':
      return {
        ...baseConfig,
        browsers: ['chrome-desktop'],
        scenarios: ['core'],
        priorities: ['critical'],
        workers: 1,
        timeout: 45000
      };

    case 'comprehensive':
      return {
        ...baseConfig,
        browsers: Object.keys(browserMatrix).flatMap(category =>
          Object.keys(browserMatrix[category as keyof typeof browserMatrix])
        ),
        scenarios: Object.keys(testScenarios),
        priorities: Object.keys(testPriorities),
        workers: 8,
        timeout: 120000
      };

    default:
      return baseConfig;
  }
};

export const browserSpecificWorkarounds = {
  safari: {
    // Safari-specific workarounds
    disableWebSecurity: false,
    ignoreHTTPSErrors: false,
    extraFlags: ['--disable-web-security=false'],
    timeouts: {
      navigation: 45000,
      action: 15000
    }
  },
  firefox: {
    // Firefox-specific workarounds
    preferences: {
      'dom.webnotifications.enabled': false,
      'media.navigator.permission.disabled': true
    },
    timeouts: {
      navigation: 30000,
      action: 10000
    }
  },
  edge: {
    // Edge-specific workarounds
    channel: 'msedge',
    timeouts: {
      navigation: 30000,
      action: 10000
    }
  }
};

export const generateBrowserTestMatrix = () => {
  const matrix: any[] = [];

  Object.entries(browserMatrix).forEach(([category, browsers]) => {
    Object.entries(browsers).forEach(([browserKey, config]) => {
      Object.entries(testScenarios).forEach(([scenarioCategory, scenarios]) => {
        Object.entries(scenarios).forEach(([scenarioKey, tests]) => {
          if (Array.isArray(tests)) {
            tests.forEach(test => {
              matrix.push({
                browser: browserKey,
                category: category,
                scenario: scenarioCategory,
                test: test,
                priority: config.priority,
                project: config.project,
                config: config.use
              });
            });
          }
        });
      });
    });
  });

  return matrix;
};

export const filterTestsByPriority = (matrix: any[], priorities: string[]) => {
  return matrix.filter(test => priorities.includes(test.priority));
};

export const groupTestsByBrowser = (matrix: any[]) => {
  return matrix.reduce((groups, test) => {
    if (!groups[test.browser]) {
      groups[test.browser] = [];
    }
    groups[test.browser].push(test);
    return groups;
  }, {} as Record<string, any[]>);
};
