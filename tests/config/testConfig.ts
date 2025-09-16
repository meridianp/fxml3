/**
 * Comprehensive Test Configuration for FXML4 TDD Framework
 *
 * Centralizes all test configuration, setup utilities, and environment
 * management for consistent testing across the entire project.
 */

// Test Environment Configuration
export interface TestConfig {
  timeout: {
    unit: number;
    integration: number;
    performance: number;
    e2e: number;
  };
  database: {
    type: 'memory' | 'sqlite' | 'postgres';
    location?: string;
    cleanup: boolean;
  };
  api: {
    baseUrl: string;
    timeout: number;
    retries: number;
  };
  websocket: {
    url: string;
    connectionTimeout: number;
    heartbeatInterval: number;
  };
  performance: {
    maxLatency: {
      order: number;
      api: number;
      websocket: number;
    };
    memoryThreshold: number; // MB
    concurrentRequests: number;
  };
  coverage: {
    threshold: {
      statements: number;
      branches: number;
      functions: number;
      lines: number;
    };
    exclude: string[];
  };
  logging: {
    level: 'debug' | 'info' | 'warn' | 'error' | 'silent';
    enableConsole: boolean;
    enableFile: boolean;
  };
}

// Environment-specific configurations
const environmentConfigs: Record<string, TestConfig> = {
  unit: {
    timeout: {
      unit: 5000,        // 5 seconds for unit tests
      integration: 15000,  // 15 seconds for integration tests
      performance: 60000,  // 1 minute for performance tests
      e2e: 120000,        // 2 minutes for E2E tests
    },
    database: {
      type: 'memory',
      cleanup: true,
    },
    api: {
      baseUrl: 'http://localhost:3001/api/v1',
      timeout: 5000,
      retries: 0, // No retries for unit tests
    },
    websocket: {
      url: 'ws://localhost:3001/ws',
      connectionTimeout: 5000,
      heartbeatInterval: 10000,
    },
    performance: {
      maxLatency: {
        order: 10,      // 10ms for order processing
        api: 100,       // 100ms for API calls
        websocket: 5,   // 5ms for WebSocket messages
      },
      memoryThreshold: 50, // 50MB
      concurrentRequests: 100,
    },
    coverage: {
      threshold: {
        statements: 80,
        branches: 75,
        functions: 80,
        lines: 80,
      },
      exclude: [
        'src/**/*.d.ts',
        'src/**/index.ts',
        'src/**/*.stories.tsx',
        'src/mocks/**/*',
      ],
    },
    logging: {
      level: 'silent',
      enableConsole: false,
      enableFile: false,
    },
  },

  integration: {
    timeout: {
      unit: 5000,
      integration: 30000,   // Extended for integration tests
      performance: 60000,
      e2e: 180000,
    },
    database: {
      type: 'sqlite',
      location: ':memory:',
      cleanup: true,
    },
    api: {
      baseUrl: 'https://test-api.fxml4.com/v1',
      timeout: 10000,
      retries: 2,
    },
    websocket: {
      url: 'wss://test-ws.fxml4.com',
      connectionTimeout: 10000,
      heartbeatInterval: 30000,
    },
    performance: {
      maxLatency: {
        order: 20,      // More lenient for integration
        api: 200,
        websocket: 10,
      },
      memoryThreshold: 100, // 100MB
      concurrentRequests: 50,
    },
    coverage: {
      threshold: {
        statements: 70,  // Slightly lower for integration
        branches: 65,
        functions: 70,
        lines: 70,
      },
      exclude: [
        'src/**/*.d.ts',
        'src/**/index.ts',
        'src/**/*.stories.tsx',
        'src/mocks/**/*',
        'tests/**/*',
      ],
    },
    logging: {
      level: 'warn',
      enableConsole: true,
      enableFile: true,
    },
  },

  performance: {
    timeout: {
      unit: 5000,
      integration: 30000,
      performance: 300000,  // 5 minutes for performance tests
      e2e: 600000,         // 10 minutes for comprehensive E2E
    },
    database: {
      type: 'sqlite',
      location: 'tests/performance/perf_test.db',
      cleanup: false, // Preserve for performance analysis
    },
    api: {
      baseUrl: 'https://staging-api.fxml4.com/v1',
      timeout: 30000,
      retries: 3,
    },
    websocket: {
      url: 'wss://staging-ws.fxml4.com',
      connectionTimeout: 15000,
      heartbeatInterval: 60000,
    },
    performance: {
      maxLatency: {
        order: 15,
        api: 150,
        websocket: 8,
      },
      memoryThreshold: 200, // 200MB for performance tests
      concurrentRequests: 1000,
    },
    coverage: {
      threshold: {
        statements: 60,  // Lower threshold for performance focus
        branches: 55,
        functions: 60,
        lines: 60,
      },
      exclude: [
        'src/**/*.d.ts',
        'src/**/index.ts',
        'src/**/*.stories.tsx',
        'src/mocks/**/*',
        'tests/unit/**/*',
        'tests/integration/**/*',
      ],
    },
    logging: {
      level: 'info',
      enableConsole: true,
      enableFile: true,
    },
  },

  ci: {
    timeout: {
      unit: 10000,      // More generous timeouts for CI
      integration: 45000,
      performance: 120000, // Reduced for CI pipeline efficiency
      e2e: 300000,
    },
    database: {
      type: 'postgres',
      location: 'postgresql://test:test@localhost:5432/fxml4_test', // pragma: allowlist secret
      cleanup: true,
    },
    api: {
      baseUrl: 'https://staging-api.fxml4.com/v1',
      timeout: 15000,
      retries: 3,
    },
    websocket: {
      url: 'wss://staging-ws.fxml4.com',
      connectionTimeout: 20000,
      heartbeatInterval: 45000,
    },
    performance: {
      maxLatency: {
        order: 25,      // More lenient for CI environment
        api: 300,
        websocket: 15,
      },
      memoryThreshold: 150, // 150MB
      concurrentRequests: 200,
    },
    coverage: {
      threshold: {
        statements: 85,  // Strict requirements for CI
        branches: 80,
        functions: 85,
        lines: 85,
      },
      exclude: [
        'src/**/*.d.ts',
        'src/**/index.ts',
        'src/**/*.stories.tsx',
        'src/mocks/**/*',
      ],
    },
    logging: {
      level: 'error',
      enableConsole: true,
      enableFile: true,
    },
  },
};

// Current test configuration based on environment
export const getTestConfig = (): TestConfig => {
  const env = process.env.NODE_ENV || 'unit';
  const testEnv = process.env.TEST_ENV || env;

  const config = environmentConfigs[testEnv] || environmentConfigs.unit;

  // Override with environment variables if present
  return {
    ...config,
    timeout: {
      ...config.timeout,
      unit: parseInt(process.env.TEST_TIMEOUT_UNIT || config.timeout.unit.toString()),
      integration: parseInt(process.env.TEST_TIMEOUT_INTEGRATION || config.timeout.integration.toString()),
      performance: parseInt(process.env.TEST_TIMEOUT_PERFORMANCE || config.timeout.performance.toString()),
      e2e: parseInt(process.env.TEST_TIMEOUT_E2E || config.timeout.e2e.toString()),
    },
    api: {
      ...config.api,
      baseUrl: process.env.TEST_API_URL || config.api.baseUrl,
    },
    websocket: {
      ...config.websocket,
      url: process.env.TEST_WS_URL || config.websocket.url,
    },
    logging: {
      ...config.logging,
      level: (process.env.TEST_LOG_LEVEL as any) || config.logging.level,
    },
  };
};

// Global test setup utilities
export class TestSetupManager {
  private static instance: TestSetupManager;
  private config: TestConfig;
  private setupComplete: boolean = false;

  private constructor() {
    this.config = getTestConfig();
  }

  public static getInstance(): TestSetupManager {
    if (!TestSetupManager.instance) {
      TestSetupManager.instance = new TestSetupManager();
    }
    return TestSetupManager.instance;
  }

  public async setupGlobalTestEnvironment(): Promise<void> {
    if (this.setupComplete) return;

    console.log(`Setting up test environment: ${process.env.TEST_ENV || 'unit'}`);

    // Configure Jest timeouts
    jest.setTimeout(this.config.timeout.unit);

    // Setup global mocks
    this.setupGlobalMocks();

    // Setup performance monitoring if needed
    if (process.env.TEST_ENV === 'performance') {
      this.setupPerformanceMonitoring();
    }

    // Setup database if needed
    if (this.config.database.type !== 'memory') {
      await this.setupDatabase();
    }

    // Configure logging
    this.setupLogging();

    this.setupComplete = true;
    console.log('Test environment setup complete');
  }

  private setupGlobalMocks(): void {
    // Mock global objects commonly needed in tests

    // Mock performance API
    Object.defineProperty(performance, 'now', {
      value: jest.fn(() => Date.now()),
      writable: true,
    });

    // Mock matchMedia for CSS media queries
    Object.defineProperty(window, 'matchMedia', {
      writable: true,
      value: jest.fn().mockImplementation(query => ({
        matches: false,
        media: query,
        onchange: null,
        addListener: jest.fn(),
        removeListener: jest.fn(),
        addEventListener: jest.fn(),
        removeEventListener: jest.fn(),
        dispatchEvent: jest.fn(),
      })),
    });

    // Mock localStorage
    const localStorageMock = {
      getItem: jest.fn(),
      setItem: jest.fn(),
      removeItem: jest.fn(),
      clear: jest.fn(),
      length: 0,
      key: jest.fn(),
    };

    Object.defineProperty(window, 'localStorage', {
      value: localStorageMock,
      writable: true,
    });

    // Mock sessionStorage
    Object.defineProperty(window, 'sessionStorage', {
      value: localStorageMock,
      writable: true,
    });

    // Mock WebSocket
    global.WebSocket = jest.fn().mockImplementation(() => ({
      send: jest.fn(),
      close: jest.fn(),
      addEventListener: jest.fn(),
      removeEventListener: jest.fn(),
      readyState: WebSocket.CONNECTING,
    }));

    // Mock fetch
    global.fetch = jest.fn();

    // Mock ResizeObserver
    global.ResizeObserver = jest.fn().mockImplementation(() => ({
      observe: jest.fn(),
      unobserve: jest.fn(),
      disconnect: jest.fn(),
    }));

    // Mock IntersectionObserver
    global.IntersectionObserver = jest.fn().mockImplementation(() => ({
      observe: jest.fn(),
      unobserve: jest.fn(),
      disconnect: jest.fn(),
    }));
  }

  private setupPerformanceMonitoring(): void {
    // Enable performance monitoring for performance tests
    if (typeof global.gc === 'function') {
      console.log('Garbage collection available for memory tests');
    } else {
      console.warn('Garbage collection not available - run with --expose-gc for memory tests');
    }
  }

  private async setupDatabase(): Promise<void> {
    console.log(`Setting up ${this.config.database.type} database for testing`);

    // Database setup would go here based on the type
    switch (this.config.database.type) {
      case 'sqlite':
        // SQLite setup
        break;
      case 'postgres':
        // PostgreSQL setup
        break;
    }
  }

  private setupLogging(): void {
    const { level, enableConsole, enableFile } = this.config.logging;

    // Configure console logging
    if (!enableConsole && level === 'silent') {
      const consoleMethods = ['log', 'info', 'warn', 'error', 'debug'];
      consoleMethods.forEach(method => {
        jest.spyOn(console, method as any).mockImplementation(() => {});
      });
    }

    // File logging would be configured here if needed
    if (enableFile) {
      console.log('File logging enabled for tests');
    }
  }

  public async teardownGlobalTestEnvironment(): Promise<void> {
    console.log('Tearing down test environment');

    if (this.config.database.cleanup) {
      await this.cleanupDatabase();
    }

    // Reset all mocks
    jest.restoreAllMocks();
    jest.clearAllMocks();

    this.setupComplete = false;
    console.log('Test environment teardown complete');
  }

  private async cleanupDatabase(): Promise<void> {
    console.log('Cleaning up test database');
    // Database cleanup logic would go here
  }

  public getConfig(): TestConfig {
    return this.config;
  }
}

// Test utilities for common operations
export const testUtils = {
  // Wait for condition with timeout
  waitFor: async (
    condition: () => boolean | Promise<boolean>,
    timeout: number = 5000,
    interval: number = 100
  ): Promise<void> => {
    const startTime = Date.now();

    while (Date.now() - startTime < timeout) {
      const result = await condition();
      if (result) return;

      await new Promise(resolve => setTimeout(resolve, interval));
    }

    throw new Error(`Condition not met within ${timeout}ms`);
  },

  // Create test timeout for async operations
  withTimeout: <T>(promise: Promise<T>, timeout: number): Promise<T> => {
    return Promise.race([
      promise,
      new Promise<T>((_, reject) => {
        setTimeout(() => reject(new Error(`Operation timed out after ${timeout}ms`)), timeout);
      }),
    ]);
  },

  // Measure execution time
  measureTime: async <T>(operation: () => Promise<T>): Promise<{ result: T; duration: number }> => {
    const startTime = performance.now();
    const result = await operation();
    const duration = performance.now() - startTime;

    return { result, duration };
  },

  // Memory usage measurement
  measureMemory: (): { heapUsed: number; heapTotal: number; external: number } => {
    const memUsage = process.memoryUsage();
    return {
      heapUsed: Math.round(memUsage.heapUsed / 1024 / 1024 * 100) / 100, // MB
      heapTotal: Math.round(memUsage.heapTotal / 1024 / 1024 * 100) / 100, // MB
      external: Math.round(memUsage.external / 1024 / 1024 * 100) / 100, // MB
    };
  },

  // Force garbage collection if available
  forceGC: (): void => {
    if (global.gc) {
      global.gc();
    }
  },

  // Generate unique test IDs
  generateTestId: (): string => {
    return `test-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
  },

  // Create test isolation (clean up between tests)
  isolateTest: () => {
    beforeEach(() => {
      jest.clearAllMocks();
      // Clear any global state
    });

    afterEach(() => {
      jest.restoreAllMocks();
      // Additional cleanup
    });
  },
};

// Export the singleton instance for use in tests
export const testSetup = TestSetupManager.getInstance();
