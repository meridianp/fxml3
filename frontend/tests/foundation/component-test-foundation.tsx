"""
Frontend Component Test Suite Foundation
========================================

Comprehensive testing foundation for React/Next.js components including:
1. Component rendering and lifecycle
2. User interaction testing
3. State management validation
4. API integration mocking
5. WebSocket connection testing
6. Performance benchmarking
7. Accessibility testing
8. Visual regression testing

This foundation provides reusable utilities, fixtures, and patterns
for testing all frontend components consistently.
"""

import React, { ReactElement, ReactNode } from 'react';
import { render, RenderOptions, RenderResult, waitFor, within } from '@testing-library/react';
import { act, renderHook } from '@testing-library/react-hooks';
import userEvent from '@testing-library/user-event';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { Provider } from 'react-redux';
import { configureStore } from '@reduxjs/toolkit';
import { ThemeProvider } from '@mui/material/styles';
import { LocalizationProvider } from '@mui/x-date-pickers';
import { AdapterDateFns } from '@mui/x-date-pickers/AdapterDateFns';
import { SnackbarProvider } from 'notistack';
import { SessionProvider } from 'next-auth/react';
import { RouterContext } from 'next/dist/shared/lib/router-context';
import { NextRouter } from 'next/router';
import { rest } from 'msw';
import { setupServer } from 'msw/node';
import '@testing-library/jest-dom';
import 'jest-canvas-mock';
import WS from 'jest-websocket-mock';

// Import application providers and themes
import { theme } from '@/styles/theme';
import { rootReducer } from '@/store/rootReducer';
import { WebSocketProvider } from '@/providers/WebSocketProvider';
import { NotificationProvider } from '@/providers/NotificationProvider';

// =============================================================================
// Test Configuration
// =============================================================================

interface TestConfig {
  // Feature flags
  features?: {
    realtimeData?: boolean;
    mlTraining?: boolean;
    backtesting?: boolean;
    trading?: boolean;
    compliance?: boolean;
  };

  // User configuration
  user?: {
    id?: string;
    email?: string;
    role?: 'admin' | 'trader' | 'analyst' | 'compliance';
    permissions?: string[];
  };

  // API configuration
  api?: {
    baseUrl?: string;
    timeout?: number;
    retries?: number;
  };

  // WebSocket configuration
  websocket?: {
    url?: string;
    autoConnect?: boolean;
    reconnectInterval?: number;
  };
}

const defaultTestConfig: TestConfig = {
  features: {
    realtimeData: true,
    mlTraining: true,
    backtesting: true,
    trading: true,
    compliance: true,
  },
  user: {
    id: 'test-user-123',
    email: 'test@fxml4.com',
    role: 'trader',
    permissions: ['read', 'write', 'trade'],
  },
  api: {
    baseUrl: 'http://localhost:8001',
    timeout: 5000,
    retries: 3,
  },
  websocket: {
    url: 'ws://localhost:8001/ws',
    autoConnect: false,
    reconnectInterval: 1000,
  },
};

// =============================================================================
// Mock Server Setup
// =============================================================================

const mockServer = setupServer(
  // Default handlers
  rest.get('/api/health', (req, res, ctx) => {
    return res(ctx.json({ status: 'healthy' }));
  }),

  rest.get('/api/user/profile', (req, res, ctx) => {
    return res(ctx.json(defaultTestConfig.user));
  }),

  rest.get('/api/market-data/:symbol', (req, res, ctx) => {
    const { symbol } = req.params;
    return res(ctx.json({
      symbol,
      price: 1.0850,
      timestamp: new Date().toISOString(),
    }));
  }),

  rest.post('/api/orders', (req, res, ctx) => {
    return res(ctx.json({
      orderId: 'ORD123456',
      status: 'submitted',
    }));
  }),
);

// Enable API mocking
beforeAll(() => mockServer.listen());
afterEach(() => mockServer.resetHandlers());
afterAll(() => mockServer.close());

// =============================================================================
// WebSocket Mock Setup
// =============================================================================

let mockWebSocketServer: WS | null = null;

export const setupMockWebSocket = (url: string = 'ws://localhost:8001/ws'): WS => {
  if (mockWebSocketServer) {
    mockWebSocketServer.close();
  }
  mockWebSocketServer = new WS(url);
  return mockWebSocketServer;
};

export const cleanupMockWebSocket = () => {
  if (mockWebSocketServer) {
    mockWebSocketServer.close();
    mockWebSocketServer = null;
  }
};

afterEach(() => {
  cleanupMockWebSocket();
});

// =============================================================================
// Custom Render Function
// =============================================================================

interface CustomRenderOptions extends Omit<RenderOptions, 'wrapper'> {
  config?: TestConfig;
  initialState?: any;
  router?: Partial<NextRouter>;
  session?: any;
}

const createMockRouter = (router?: Partial<NextRouter>): NextRouter => ({
  basePath: '',
  pathname: '/',
  route: '/',
  asPath: '/',
  query: {},
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
  isFallback: false,
  isLocaleDomain: false,
  isReady: true,
  isPreview: false,
  ...router,
});

const AllTheProviders: React.FC<{
  children: ReactNode;
  config: TestConfig;
  initialState?: any;
  router?: Partial<NextRouter>;
  session?: any;
}> = ({ children, config, initialState, router, session }) => {
  // Create Redux store
  const store = configureStore({
    reducer: rootReducer,
    preloadedState: initialState,
  });

  // Create React Query client
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
        cacheTime: 0,
      },
    },
  });

  // Create mock router
  const mockRouter = createMockRouter(router);

  return (
    <SessionProvider session={session}>
      <Provider store={store}>
        <QueryClientProvider client={queryClient}>
          <RouterContext.Provider value={mockRouter}>
            <ThemeProvider theme={theme}>
              <LocalizationProvider dateAdapter={AdapterDateFns}>
                <SnackbarProvider maxSnack={3}>
                  <WebSocketProvider config={config.websocket}>
                    <NotificationProvider>
                      {children}
                    </NotificationProvider>
                  </WebSocketProvider>
                </SnackbarProvider>
              </LocalizationProvider>
            </ThemeProvider>
          </RouterContext.Provider>
        </QueryClientProvider>
      </Provider>
    </SessionProvider>
  );
};

export const customRender = (
  ui: ReactElement,
  options?: CustomRenderOptions
): RenderResult => {
  const {
    config = defaultTestConfig,
    initialState,
    router,
    session,
    ...renderOptions
  } = options || {};

  return render(ui, {
    wrapper: ({ children }) => (
      <AllTheProviders
        config={config}
        initialState={initialState}
        router={router}
        session={session}
      >
        {children}
      </AllTheProviders>
    ),
    ...renderOptions,
  });
};

// =============================================================================
// Test Utilities
// =============================================================================

export const testUtils = {
  // User interactions
  user: userEvent.setup(),

  // Wait utilities
  waitFor,
  waitForElementToBeRemoved: waitFor,

  // Query utilities
  within,

  // Mock utilities
  mockApi: (handler: any) => mockServer.use(handler),

  // WebSocket utilities
  mockWebSocket: setupMockWebSocket,
  sendWebSocketMessage: (message: any) => {
    if (mockWebSocketServer) {
      mockWebSocketServer.send(JSON.stringify(message));
    }
  },

  // Time utilities
  advanceTimersByTime: (ms: number) => act(() => jest.advanceTimersByTime(ms)),
  runAllTimers: () => act(() => jest.runAllTimers()),

  // Snapshot utilities
  toMatchSnapshot: expect.any,
};

// =============================================================================
// Component Test Patterns
// =============================================================================

export class ComponentTestBuilder<P = {}> {
  private component: React.ComponentType<P>;
  private props: Partial<P> = {};
  private config: TestConfig = defaultTestConfig;
  private mockHandlers: any[] = [];
  private renderResult: RenderResult | null = null;

  constructor(component: React.ComponentType<P>) {
    this.component = component;
  }

  withProps(props: Partial<P>): this {
    this.props = { ...this.props, ...props };
    return this;
  }

  withConfig(config: Partial<TestConfig>): this {
    this.config = { ...this.config, ...config };
    return this;
  }

  withApiMock(handler: any): this {
    this.mockHandlers.push(handler);
    return this;
  }

  async render(): Promise<RenderResult> {
    // Apply mock handlers
    this.mockHandlers.forEach(handler => mockServer.use(handler));

    // Render component
    const Component = this.component;
    this.renderResult = customRender(
      <Component {...(this.props as P)} />,
      { config: this.config }
    );

    return this.renderResult;
  }

  async renderAndWait(selector: string): Promise<RenderResult> {
    const result = await this.render();
    await waitFor(() => {
      expect(result.getByTestId(selector)).toBeInTheDocument();
    });
    return result;
  }

  getResult(): RenderResult {
    if (!this.renderResult) {
      throw new Error('Component not rendered yet. Call render() first.');
    }
    return this.renderResult;
  }

  async clickButton(text: string): Promise<void> {
    const result = this.getResult();
    const button = result.getByRole('button', { name: text });
    await testUtils.user.click(button);
  }

  async typeInInput(label: string, text: string): Promise<void> {
    const result = this.getResult();
    const input = result.getByLabelText(label);
    await testUtils.user.type(input, text);
  }

  async selectOption(label: string, value: string): Promise<void> {
    const result = this.getResult();
    const select = result.getByLabelText(label);
    await testUtils.user.selectOptions(select, value);
  }

  expectText(text: string): void {
    const result = this.getResult();
    expect(result.getByText(text)).toBeInTheDocument();
  }

  expectNotText(text: string): void {
    const result = this.getResult();
    expect(result.queryByText(text)).not.toBeInTheDocument();
  }

  async waitForText(text: string): Promise<void> {
    const result = this.getResult();
    await waitFor(() => {
      expect(result.getByText(text)).toBeInTheDocument();
    });
  }

  async waitForLoading(): Promise<void> {
    const result = this.getResult();
    await waitFor(() => {
      expect(result.queryByTestId('loading')).not.toBeInTheDocument();
    });
  }

  takeSnapshot(name?: string): void {
    const result = this.getResult();
    expect(result.container).toMatchSnapshot(name);
  }
}

// =============================================================================
// Accessibility Testing
// =============================================================================

import { axe, toHaveNoViolations } from 'jest-axe';

expect.extend(toHaveNoViolations);

export const testAccessibility = async (
  container: HTMLElement,
  options?: any
): Promise<void> => {
  const results = await axe(container, options);
  expect(results).toHaveNoViolations();
};

// =============================================================================
// Performance Testing
// =============================================================================

export const measureRenderTime = async (
  component: ReactElement
): Promise<number> => {
  const start = performance.now();
  const { unmount } = customRender(component);
  const end = performance.now();
  unmount();
  return end - start;
};

export const measureReRenderTime = async (
  component: ReactElement,
  newProps: any
): Promise<number> => {
  const { rerender, unmount } = customRender(component);

  const start = performance.now();
  rerender(React.cloneElement(component, newProps));
  const end = performance.now();

  unmount();
  return end - start;
};

// =============================================================================
// WebSocket Testing Utilities
// =============================================================================

export const createWebSocketTest = () => {
  let ws: WS;

  return {
    setup: (url?: string) => {
      ws = setupMockWebSocket(url);
      return ws;
    },

    sendMessage: (type: string, data: any) => {
      ws.send(JSON.stringify({ type, data }));
    },

    expectConnection: async () => {
      await ws.connected;
    },

    expectMessage: async (type: string) => {
      await expect(ws).toReceiveMessage(
        expect.objectContaining({ type })
      );
    },

    simulateError: () => {
      ws.error();
    },

    simulateClose: () => {
      ws.close();
    },

    cleanup: () => {
      cleanupMockWebSocket();
    },
  };
};

// =============================================================================
// Form Testing Utilities
// =============================================================================

export const fillForm = async (
  result: RenderResult,
  values: Record<string, string>
): Promise<void> => {
  for (const [name, value] of Object.entries(values)) {
    const input = result.getByLabelText(name);
    await testUtils.user.clear(input);
    await testUtils.user.type(input, value);
  }
};

export const submitForm = async (result: RenderResult): Promise<void> => {
  const submitButton = result.getByRole('button', { name: /submit/i });
  await testUtils.user.click(submitButton);
};

// =============================================================================
// Redux Testing Utilities
// =============================================================================

export const createMockStore = (initialState?: any) => {
  return configureStore({
    reducer: rootReducer,
    preloadedState: initialState,
  });
};

export const dispatchAndWait = async (
  store: any,
  action: any
): Promise<void> => {
  await act(async () => {
    store.dispatch(action);
  });
};

// =============================================================================
// React Query Testing Utilities
// =============================================================================

export const createQueryWrapper = () => {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  });

  const wrapper: React.FC<{ children: ReactNode }> = ({ children }) => (
    <QueryClientProvider client={queryClient}>
      {children}
    </QueryClientProvider>
  );

  return { queryClient, wrapper };
};

// =============================================================================
// Data Generators
// =============================================================================

export const generateMockData = {
  user: (overrides?: Partial<any>) => ({
    id: 'user-123',
    email: 'test@example.com',
    name: 'Test User',
    role: 'trader',
    ...overrides,
  }),

  marketData: (symbol: string = 'EUR/USD') => ({
    symbol,
    bid: 1.0849,
    ask: 1.0851,
    last: 1.0850,
    volume: 1000000,
    timestamp: new Date().toISOString(),
  }),

  order: (overrides?: Partial<any>) => ({
    orderId: 'ORD123456',
    symbol: 'EUR/USD',
    side: 'buy',
    quantity: 100000,
    orderType: 'market',
    status: 'pending',
    ...overrides,
  }),

  position: (overrides?: Partial<any>) => ({
    symbol: 'EUR/USD',
    quantity: 100000,
    avgPrice: 1.0850,
    pnl: 125.50,
    ...overrides,
  }),

  backtest: (overrides?: Partial<any>) => ({
    id: 'backtest-123',
    strategy: 'momentum',
    startDate: '2024-01-01',
    endDate: '2024-01-31',
    returns: 0.0523,
    sharpeRatio: 1.85,
    ...overrides,
  }),
};

// =============================================================================
// Export Everything
// =============================================================================

export {
  customRender as render,
  mockServer,
  setupMockWebSocket,
  cleanupMockWebSocket,
};

export default {
  ComponentTestBuilder,
  testUtils,
  testAccessibility,
  measureRenderTime,
  measureReRenderTime,
  createWebSocketTest,
  fillForm,
  submitForm,
  createMockStore,
  dispatchAndWait,
  createQueryWrapper,
  generateMockData,
};
