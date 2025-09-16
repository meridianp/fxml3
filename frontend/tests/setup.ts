"""
Jest Test Setup Configuration
=============================

Global test setup and configuration for the FXML4 frontend test suite.
Configures testing environment, polyfills, and global utilities.
"""

import '@testing-library/jest-dom';
import 'jest-canvas-mock';

// Mock Next.js router
jest.mock('next/router', () => ({
  useRouter() {
    return {
      route: '/',
      pathname: '/',
      query: {},
      asPath: '/',
      push: jest.fn(),
      replace: jest.fn(),
      reload: jest.fn(),
      back: jest.fn(),
      prefetch: jest.fn(),
      beforePopState: jest.fn(),
      events: {
        on: jest.fn(),
        off: jest.fn(),
        emit: jest.fn(),
      },
    };
  },
}));

// Mock Next.js image component
jest.mock('next/image', () => {
  const MockedImage = ({ src, alt, ...props }: any) => {
    return <img src={src} alt={alt} {...props} />;
  };
  MockedImage.displayName = 'NextImage';
  return MockedImage;
});

// Mock Next.js dynamic imports
jest.mock('next/dynamic', () => {
  return (dynamicFunction: any, options: any = {}) => {
    const Component = dynamicFunction();

    if (options.loading) {
      Component.displayName = 'DynamicComponent';
      return Component;
    }

    return Component;
  };
});

// Mock next-auth
jest.mock('next-auth/react', () => ({
  useSession: jest.fn(() => ({
    data: {
      user: {
        id: 'test-user',
        email: 'test@example.com',
        name: 'Test User',
      },
    },
    status: 'authenticated',
  })),
  signIn: jest.fn(),
  signOut: jest.fn(),
  SessionProvider: ({ children }: { children: React.ReactNode }) => children,
}));

// Mock Chart.js
jest.mock('chart.js', () => ({
  Chart: {
    register: jest.fn(),
  },
  CategoryScale: jest.fn(),
  LinearScale: jest.fn(),
  PointElement: jest.fn(),
  LineElement: jest.fn(),
  Title: jest.fn(),
  Tooltip: jest.fn(),
  Legend: jest.fn(),
}));

// Mock recharts
jest.mock('recharts', () => ({
  LineChart: ({ children }: any) => <div data-testid="line-chart">{children}</div>,
  Line: () => <div className="recharts-line" />,
  XAxis: () => <div className="recharts-xaxis" />,
  YAxis: () => <div className="recharts-yaxis" />,
  Tooltip: () => <div className="recharts-tooltip" />,
  Legend: () => <div className="recharts-legend" />,
  ResponsiveContainer: ({ children }: any) => <div>{children}</div>,
  BarChart: ({ children }: any) => <div data-testid="bar-chart">{children}</div>,
  Bar: () => <div className="recharts-bar" />,
  PieChart: ({ children }: any) => <div data-testid="pie-chart">{children}</div>,
  Pie: () => <div className="recharts-pie" />,
  Cell: () => <div className="recharts-cell" />,
}));

// Mock Plotly
jest.mock('plotly.js-dist-min', () => ({
  newPlot: jest.fn(),
  redraw: jest.fn(),
  purge: jest.fn(),
}));

jest.mock('react-plotly.js', () => {
  const Plot = ({ data, layout, ...props }: any) => (
    <div data-testid="plotly-chart" data-plot-data={JSON.stringify(data)} {...props} />
  );
  return Plot;
});

// Mock Material-UI components that require DOM
jest.mock('@mui/x-data-grid', () => ({
  DataGrid: ({ rows, columns, ...props }: any) => (
    <div data-testid="data-grid" data-rows={rows.length} {...props}>
      <table>
        <thead>
          <tr>
            {columns.map((col: any) => (
              <th key={col.field}>{col.headerName}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row: any, index: number) => (
            <tr key={index}>
              {columns.map((col: any) => (
                <td key={col.field}>{row[col.field]}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  ),
  GridActionsCellItem: ({ label, onClick }: any) => (
    <button onClick={onClick}>{label}</button>
  ),
}));

// Mock date picker components
jest.mock('@mui/x-date-pickers', () => ({
  DatePicker: ({ value, onChange, label }: any) => (
    <input
      type="date"
      value={value?.toISOString().split('T')[0] || ''}
      onChange={(e) => onChange && onChange(new Date(e.target.value))}
      aria-label={label}
    />
  ),
  DateTimePicker: ({ value, onChange, label }: any) => (
    <input
      type="datetime-local"
      value={value?.toISOString().slice(0, 16) || ''}
      onChange={(e) => onChange && onChange(new Date(e.target.value))}
      aria-label={label}
    />
  ),
  LocalizationProvider: ({ children }: any) => children,
}));

// Mock WebSocket
global.WebSocket = jest.fn(() => ({
  close: jest.fn(),
  send: jest.fn(),
  addEventListener: jest.fn(),
  removeEventListener: jest.fn(),
  readyState: WebSocket.OPEN,
})) as any;

// Mock IntersectionObserver
global.IntersectionObserver = class IntersectionObserver {
  constructor() {}
  observe() {}
  unobserve() {}
  disconnect() {}
};

// Mock ResizeObserver
global.ResizeObserver = class ResizeObserver {
  constructor() {}
  observe() {}
  unobserve() {}
  disconnect() {}
};

// Mock matchMedia
Object.defineProperty(window, 'matchMedia', {
  writable: true,
  value: jest.fn().mockImplementation((query) => ({
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

// Mock requestAnimationFrame
global.requestAnimationFrame = (callback: FrameRequestCallback): number => {
  return setTimeout(callback, 0);
};

global.cancelAnimationFrame = (id: number): void => {
  clearTimeout(id);
};

// Mock performance API
Object.defineProperty(window, 'performance', {
  writable: true,
  value: {
    now: jest.fn(() => Date.now()),
    getEntriesByName: jest.fn(),
    getEntriesByType: jest.fn(),
    mark: jest.fn(),
    measure: jest.fn(),
    navigation: {
      type: 0,
    },
    timing: {
      navigationStart: Date.now(),
      loadEventEnd: Date.now(),
    },
  },
});

// Mock clipboard API
Object.defineProperty(navigator, 'clipboard', {
  writable: true,
  value: {
    writeText: jest.fn().mockResolvedValue(undefined),
    readText: jest.fn().mockResolvedValue(''),
  },
});

// Mock geolocation
Object.defineProperty(navigator, 'geolocation', {
  writable: true,
  value: {
    getCurrentPosition: jest.fn(),
    watchPosition: jest.fn(),
    clearWatch: jest.fn(),
  },
});

// Mock crypto API for UUID generation
Object.defineProperty(window, 'crypto', {
  writable: true,
  value: {
    randomUUID: () => 'test-uuid-123',
    getRandomValues: (array: any) => {
      for (let i = 0; i < array.length; i++) {
        array[i] = Math.floor(Math.random() * 256);
      }
      return array;
    },
  },
});

// Mock localStorage
const localStorageMock = (() => {
  let store: Record<string, string> = {};

  return {
    getItem: (key: string) => store[key] || null,
    setItem: (key: string, value: string) => {
      store[key] = value.toString();
    },
    removeItem: (key: string) => {
      delete store[key];
    },
    clear: () => {
      store = {};
    },
    length: Object.keys(store).length,
    key: (index: number) => Object.keys(store)[index] || null,
  };
})();

Object.defineProperty(window, 'localStorage', {
  value: localStorageMock,
});

// Mock sessionStorage
Object.defineProperty(window, 'sessionStorage', {
  value: localStorageMock,
});

// Setup console overrides for cleaner test output
const originalConsoleError = console.error;
const originalConsoleWarn = console.warn;

console.error = (...args: any[]) => {
  // Suppress known React warnings during tests
  const message = args[0];

  if (
    typeof message === 'string' &&
    (message.includes('Warning: ReactDOM.render is no longer supported') ||
     message.includes('Warning: An invalid form control') ||
     message.includes('Warning: componentWillReceiveProps'))
  ) {
    return;
  }

  originalConsoleError.apply(console, args);
};

console.warn = (...args: any[]) => {
  const message = args[0];

  if (
    typeof message === 'string' &&
    (message.includes('Warning: React.createFactory()') ||
     message.includes('Warning: componentWillMount'))
  ) {
    return;
  }

  originalConsoleWarn.apply(console, args);
};

// Global test configuration
beforeAll(() => {
  // Set test environment timezone
  process.env.TZ = 'UTC';

  // Configure fetch timeout for tests
  global.fetch = jest.fn();
});

beforeEach(() => {
  // Reset all mocks before each test
  jest.clearAllMocks();

  // Reset timers
  jest.clearAllTimers();

  // Clear localStorage/sessionStorage
  localStorage.clear();
  sessionStorage.clear();
});

afterEach(() => {
  // Cleanup after each test
  jest.useRealTimers();

  // Reset fetch mock
  if (global.fetch) {
    (global.fetch as jest.Mock).mockClear();
  }
});

// Custom matchers
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

  toHaveBeenCalledWithObjectContaining(received: jest.Mock, expected: object) {
    const calls = received.mock.calls;
    const pass = calls.some((call: any[]) => {
      return call.some((arg: any) => {
        if (typeof arg === 'object' && arg !== null) {
          return Object.keys(expected).every(key => {
            return (expected as any)[key] === arg[key];
          });
        }
        return false;
      });
    });

    return {
      pass,
      message: () =>
        pass
          ? `expected mock not to have been called with object containing ${JSON.stringify(expected)}`
          : `expected mock to have been called with object containing ${JSON.stringify(expected)}`,
    };
  },
});

// Type declarations for custom matchers
declare global {
  namespace jest {
    interface Matchers<R> {
      toBeWithinRange(floor: number, ceiling: number): R;
      toHaveBeenCalledWithObjectContaining(expected: object): R;
    }
  }
}

export {};
