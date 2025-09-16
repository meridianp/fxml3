/**
 * Jest Global Setup for FXML4 TDD Framework
 *
 * This file is executed once before all tests run. It initializes the
 * test environment, sets up global mocks, and configures the testing
 * infrastructure for optimal performance and reliability.
 */

import '@testing-library/jest-dom';
import { testSetup } from '../config/testConfig';

// Initialize test environment before all tests
beforeAll(async () => {
  await testSetup.setupGlobalTestEnvironment();
});

// Cleanup after all tests complete
afterAll(async () => {
  await testSetup.teardownGlobalTestEnvironment();
});

// Configure React Testing Library
import { configure } from '@testing-library/react';

configure({
  testIdAttribute: 'data-testid',
  // Increase timeout for slow CI environments
  asyncUtilTimeout: 10000,
  // Enable better error messages
  getElementError: (message, container) => {
    const error = new Error(
      [
        message,
        'Here is the current DOM structure:',
        container ? container.innerHTML : 'No container provided',
      ].filter(Boolean).join('\n\n')
    );
    error.name = 'TestingLibraryElementError';
    return error;
  },
});

// Suppress specific console warnings/errors in tests
const originalError = console.error;
const originalWarn = console.warn;

console.error = (...args: any[]) => {
  // Suppress known warnings that are not actionable in tests
  const suppressedWarnings = [
    'Warning: ReactDOM.render is deprecated',
    'Warning: validateDOMNesting',
    'Warning: React.createFactory() is deprecated',
    'Warning: componentWillReceiveProps has been renamed',
    'Warning: componentWillMount has been renamed',
    'Warning: componentWillUpdate has been renamed',
    'Warning: findDOMNode is deprecated',
    'Download the React DevTools',
  ];

  const shouldSuppress = suppressedWarnings.some(warning =>
    args.some(arg => typeof arg === 'string' && arg.includes(warning))
  );

  if (!shouldSuppress) {
    originalError.apply(console, args);
  }
};

console.warn = (...args: any[]) => {
  // Suppress MUI warnings in test environment
  const suppressedMuiWarnings = [
    'Material-UI: The value provided to the TextField is invalid',
    'Material-UI: You have provided an out-of-range value',
    'MUI: The value provided to',
    'deprecated findDOMNode',
  ];

  const shouldSuppress = suppressedMuiWarnings.some(warning =>
    args.some(arg => typeof arg === 'string' && arg.includes(warning))
  );

  if (!shouldSuppress) {
    originalWarn.apply(console, args);
  }
};

// Enhanced error handling for unhandled rejections in tests
process.on('unhandledRejection', (reason, promise) => {
  console.error('Unhandled Rejection at:', promise, 'reason:', reason);
  // Don't exit the process in test environment
});

// Enhanced error handling for uncaught exceptions in tests
process.on('uncaughtException', (error) => {
  console.error('Uncaught Exception:', error);
  // Don't exit the process in test environment
});

// Mock modules that cause issues in test environment
jest.mock('react-virtualized-auto-sizer', () => ({
  __esModule: true,
  default: ({ children }: { children: (props: { width: number; height: number }) => React.ReactNode }) =>
    children({ width: 800, height: 600 }),
}));

jest.mock('recharts', () => ({
  ResponsiveContainer: ({ children }: { children: React.ReactNode }) => children,
  LineChart: ({ children }: { children: React.ReactNode }) => <div data-testid="line-chart">{children}</div>,
  Line: () => <div data-testid="line" />,
  XAxis: () => <div data-testid="x-axis" />,
  YAxis: () => <div data-testid="y-axis" />,
  CartesianGrid: () => <div data-testid="cartesian-grid" />,
  Tooltip: () => <div data-testid="tooltip" />,
  Legend: () => <div data-testid="legend" />,
  Area: () => <div data-testid="area" />,
  AreaChart: ({ children }: { children: React.ReactNode }) => <div data-testid="area-chart">{children}</div>,
  Bar: () => <div data-testid="bar" />,
  BarChart: ({ children }: { children: React.ReactNode }) => <div data-testid="bar-chart">{children}</div>,
}));

// Mock worker threads for tests
jest.mock('worker_threads', () => ({
  Worker: jest.fn().mockImplementation(() => ({
    postMessage: jest.fn(),
    terminate: jest.fn(),
    on: jest.fn(),
    off: jest.fn(),
  })),
  parentPort: {
    postMessage: jest.fn(),
    on: jest.fn(),
    off: jest.fn(),
  },
}));

// Mock crypto module for Node.js compatibility
Object.defineProperty(global, 'crypto', {
  value: {
    randomUUID: () => 'test-uuid-' + Math.random().toString(36).substr(2, 9),
    getRandomValues: (arr: any[]) => {
      for (let i = 0; i < arr.length; i++) {
        arr[i] = Math.floor(Math.random() * 256);
      }
      return arr;
    },
  },
});

// Mock TextEncoder/TextDecoder for older Node.js versions
if (typeof global.TextEncoder === 'undefined') {
  const { TextEncoder, TextDecoder } = require('util');
  global.TextEncoder = TextEncoder;
  global.TextDecoder = TextDecoder;
}

// Mock URL constructor for Node.js compatibility
if (typeof global.URL === 'undefined') {
  global.URL = require('url').URL;
}

// Mock Blob for file operations in tests
if (typeof global.Blob === 'undefined') {
  global.Blob = jest.fn().mockImplementation((parts: any[], options: any = {}) => ({
    size: parts.reduce((size, part) => size + (part.length || 0), 0),
    type: options.type || '',
    text: jest.fn().mockResolvedValue(parts.join('')),
    arrayBuffer: jest.fn().mockResolvedValue(new ArrayBuffer(0)),
    slice: jest.fn().mockReturnThis(),
  }));
}

// Mock File constructor
if (typeof global.File === 'undefined') {
  global.File = jest.fn().mockImplementation((bits: any[], filename: string, options: any = {}) => ({
    name: filename,
    size: bits.reduce((size, bit) => size + (bit.length || 0), 0),
    type: options.type || '',
    lastModified: Date.now(),
    text: jest.fn().mockResolvedValue(bits.join('')),
    arrayBuffer: jest.fn().mockResolvedValue(new ArrayBuffer(0)),
    slice: jest.fn().mockReturnThis(),
  }));
}

// Mock FileReader for file upload tests
global.FileReader = jest.fn().mockImplementation(() => ({
  readAsText: jest.fn(),
  readAsDataURL: jest.fn(),
  readAsArrayBuffer: jest.fn(),
  addEventListener: jest.fn(),
  removeEventListener: jest.fn(),
  result: null,
  error: null,
  readyState: 0,
  onload: null,
  onerror: null,
}));

// Mock canvas operations for chart testing
HTMLCanvasElement.prototype.getContext = jest.fn().mockImplementation(() => ({
  fillRect: jest.fn(),
  clearRect: jest.fn(),
  getImageData: jest.fn(() => ({ data: new Array(4) })),
  putImageData: jest.fn(),
  createImageData: jest.fn(() => ({ data: new Array(4) })),
  setTransform: jest.fn(),
  drawImage: jest.fn(),
  save: jest.fn(),
  fillText: jest.fn(),
  restore: jest.fn(),
  beginPath: jest.fn(),
  moveTo: jest.fn(),
  lineTo: jest.fn(),
  closePath: jest.fn(),
  stroke: jest.fn(),
  translate: jest.fn(),
  scale: jest.fn(),
  rotate: jest.fn(),
  arc: jest.fn(),
  fill: jest.fn(),
  measureText: jest.fn(() => ({ width: 0 })),
  transform: jest.fn(),
  rect: jest.fn(),
  clip: jest.fn(),
}));

// Mock HTMLMediaElement for audio/video testing
Object.defineProperty(HTMLMediaElement.prototype, 'muted', {
  writable: true,
  value: false,
});

Object.defineProperty(HTMLMediaElement.prototype, 'currentTime', {
  writable: true,
  value: 0,
});

Object.defineProperty(HTMLMediaElement.prototype, 'duration', {
  writable: true,
  value: NaN,
});

// Enhanced Date mocking for consistent test timing
const OriginalDate = global.Date;

// Allow specific date mocking in tests
global.mockDate = (dateString: string) => {
  const mockedDate = new OriginalDate(dateString);
  global.Date = jest.fn(() => mockedDate) as any;
  global.Date.now = jest.fn(() => mockedDate.getTime());
  global.Date.UTC = OriginalDate.UTC;
  global.Date.parse = OriginalDate.parse;
};

global.restoreDate = () => {
  global.Date = OriginalDate;
};

// Test performance utilities
global.testPerformance = {
  startTime: 0,
  markStart: () => {
    global.testPerformance.startTime = performance.now();
  },
  markEnd: (label: string, maxDuration: number) => {
    const duration = performance.now() - global.testPerformance.startTime;
    if (duration > maxDuration) {
      console.warn(`Performance warning: ${label} took ${duration.toFixed(2)}ms (expected < ${maxDuration}ms)`);
    }
    return duration;
  },
};

// Custom matchers for common test scenarios
expect.extend({
  toBeWithinRange(received: number, floor: number, ceiling: number) {
    const pass = received >= floor && received <= ceiling;
    if (pass) {
      return {
        message: () => `expected ${received} not to be within range ${floor} - ${ceiling}`,
        pass: true,
      };
    } else {
      return {
        message: () => `expected ${received} to be within range ${floor} - ${ceiling}`,
        pass: false,
      };
    }
  },

  toHaveLatencyLessThan(received: number, expected: number) {
    const pass = received < expected;
    if (pass) {
      return {
        message: () => `expected latency ${received}ms not to be less than ${expected}ms`,
        pass: true,
      };
    } else {
      return {
        message: () => `expected latency ${received}ms to be less than ${expected}ms`,
        pass: false,
      };
    }
  },

  toBeValidOrder(received: any) {
    const requiredFields = ['id', 'symbol', 'side', 'quantity', 'type', 'status'];
    const hasAllFields = requiredFields.every(field => received.hasOwnProperty(field));
    const validSide = ['BUY', 'SELL'].includes(received.side);
    const validType = ['MARKET', 'LIMIT', 'STOP'].includes(received.type);
    const validStatus = ['PENDING', 'EXECUTED', 'CANCELLED', 'REJECTED'].includes(received.status);
    const validQuantity = typeof received.quantity === 'number' && received.quantity > 0;

    const pass = hasAllFields && validSide && validType && validStatus && validQuantity;

    if (pass) {
      return {
        message: () => `expected ${JSON.stringify(received)} not to be a valid order`,
        pass: true,
      };
    } else {
      return {
        message: () => `expected ${JSON.stringify(received)} to be a valid order with required fields and valid values`,
        pass: false,
      };
    }
  },
});

// Global test environment indicators
console.log(`
🧪 FXML4 TDD Framework Initialized
📊 Environment: ${process.env.TEST_ENV || 'unit'}
⚡ Node.js: ${process.version}
🔧 Jest: ${require('jest/package.json').version}
🎯 Test Setup Complete
`);

export {};

// Type declarations for global test utilities
declare global {
  interface Global {
    mockDate: (dateString: string) => void;
    restoreDate: () => void;
    testPerformance: {
      startTime: number;
      markStart: () => void;
      markEnd: (label: string, maxDuration: number) => number;
    };
  }

  namespace jest {
    interface Matchers<R> {
      toBeWithinRange(floor: number, ceiling: number): R;
      toHaveLatencyLessThan(expected: number): R;
      toBeValidOrder(): R;
    }
  }
}
