# FXML4 Testing Templates and Examples

## Table of Contents
- [Unit Test Templates](#unit-test-templates)
- [Integration Test Templates](#integration-test-templates)
- [Performance Test Templates](#performance-test-templates)
- [React Component Test Templates](#react-component-test-templates)
- [Service Test Templates](#service-test-templates)
- [Mock Templates](#mock-templates)
- [Setup and Teardown Templates](#setup-and-teardown-templates)

---

## Unit Test Templates

### Basic Function Test Template

```typescript
// tests/unit/[ServiceName].test.ts
import { [ServiceName] } from '../../src/services/[ServiceName]';
import { [DependencyType] } from '../../src/types/[Types]';

describe('[ServiceName]', () => {
  let service: [ServiceName];
  let mockDependency: jest.Mocked<[DependencyType]>;

  beforeEach(() => {
    mockDependency = {
      method1: jest.fn(),
      method2: jest.fn(),
    } as jest.Mocked<[DependencyType]>;

    service = new [ServiceName](mockDependency);
  });

  afterEach(() => {
    jest.clearAllMocks();
  });

  describe('[methodName]', () => {
    test('should [expected behavior] when [condition]', () => {
      // Arrange
      const input = [testData];
      const expectedOutput = [expectedResult];
      mockDependency.method1.mockReturnValue(expectedOutput);

      // Act
      const result = service.[methodName](input);

      // Assert
      expect(result).toBe(expectedOutput);
      expect(mockDependency.method1).toHaveBeenCalledWith(input);
      expect(mockDependency.method1).toHaveBeenCalledTimes(1);
    });

    test('should throw error when [error condition]', () => {
      // Arrange
      const invalidInput = [invalidData];
      mockDependency.method1.mockImplementation(() => {
        throw new Error('Test error');
      });

      // Act & Assert
      expect(() => service.[methodName](invalidInput))
        .toThrow('Test error');
    });
  });
});
```

### Async Function Test Template

```typescript
describe('[AsyncServiceName]', () => {
  let service: [AsyncServiceName];
  let mockApiService: jest.Mocked<[ApiServiceType]>;

  beforeEach(() => {
    mockApiService = {
      fetchData: jest.fn(),
      submitRequest: jest.fn(),
    } as jest.Mocked<[ApiServiceType]>;

    service = new [AsyncServiceName](mockApiService);
  });

  describe('[asyncMethodName]', () => {
    test('should successfully [expected behavior] when [condition]', async () => {
      // Arrange
      const inputData = [testData];
      const mockResponse = [mockResponseData];
      mockApiService.fetchData.mockResolvedValue(mockResponse);

      // Act
      const result = await service.[asyncMethodName](inputData);

      // Assert
      expect(result).toEqual(mockResponse);
      expect(mockApiService.fetchData).toHaveBeenCalledWith(inputData);
    });

    test('should handle API errors gracefully', async () => {
      // Arrange
      const inputData = [testData];
      const errorMessage = 'API Error';
      mockApiService.fetchData.mockRejectedValue(new Error(errorMessage));

      // Act & Assert
      await expect(service.[asyncMethodName](inputData))
        .rejects.toThrow(errorMessage);
    });

    test('should retry on transient failures', async () => {
      // Arrange
      const inputData = [testData];
      const finalResponse = [successResponse];

      mockApiService.fetchData
        .mockRejectedValueOnce(new Error('Transient Error'))
        .mockRejectedValueOnce(new Error('Transient Error'))
        .mockResolvedValue(finalResponse);

      // Act
      const result = await service.[asyncMethodName](inputData);

      // Assert
      expect(result).toEqual(finalResponse);
      expect(mockApiService.fetchData).toHaveBeenCalledTimes(3);
    });
  });
});
```

---

## Integration Test Templates

### API Integration Test Template

```typescript
// tests/integration/[feature]-integration.test.ts
import { TradingAPIService } from '../../src/services/TradingAPIService';
import { OrderService } from '../../src/services/OrderService';
import { MarketDataService } from '../../src/services/MarketDataService';

describe('[Feature] Integration Tests', () => {
  let apiService: TradingAPIService;
  let orderService: OrderService;
  let marketDataService: MarketDataService;

  beforeAll(() => {
    // Use test API endpoint
    apiService = new TradingAPIService(
      'https://test-api.fxml4.com/v1',
      'test_api_key'
    );
    orderService = new OrderService(apiService);
    marketDataService = new MarketDataService(apiService);
  });

  beforeEach(() => {
    // Reset test environment
    jest.clearAllMocks();
  });

  describe('[workflow description]', () => {
    test('should complete full [workflow name] successfully', async () => {
      // Arrange
      const testData = {
        symbol: 'EUR/USD',
        quantity: 100000,
        side: 'BUY'
      };

      // Act - Step 1: Get market data
      const marketData = await marketDataService.getCurrentPrice(testData.symbol);
      expect(marketData).toBeDefined();

      // Act - Step 2: Submit order
      const orderResult = await orderService.submitOrder({
        ...testData,
        price: marketData.ask
      });

      // Act - Step 3: Verify order status
      const orderStatus = await orderService.getOrderStatus(orderResult.orderId);

      // Assert
      expect(orderResult.success).toBe(true);
      expect(orderResult.orderId).toBeDefined();
      expect(orderStatus.status).toMatch(/PENDING|EXECUTED/);
    });

    test('should handle [error scenario] in integration', async () => {
      // Arrange
      const invalidData = [invalidTestData];

      // Act & Assert
      await expect(orderService.submitOrder(invalidData))
        .rejects.toThrow(/validation error/i);
    });
  });
});
```

### Database Integration Test Template

```typescript
describe('[Entity] Database Integration', () => {
  let connection: DatabaseConnection;
  let repository: [EntityRepository];

  beforeAll(async () => {
    connection = await createTestDatabase();
    repository = new [EntityRepository](connection);
  });

  afterAll(async () => {
    await connection.close();
  });

  beforeEach(async () => {
    await repository.clearAll(); // Clean slate for each test
  });

  describe('[operation] operations', () => {
    test('should successfully [operation description]', async () => {
      // Arrange
      const testEntity = createTest[EntityName]({
        property1: 'value1',
        property2: 'value2'
      });

      // Act
      const result = await repository.save(testEntity);
      const retrieved = await repository.findById(result.id);

      // Assert
      expect(result.id).toBeDefined();
      expect(retrieved).toEqual(expect.objectContaining(testEntity));
    });

    test('should handle database constraints', async () => {
      // Arrange
      const duplicateEntity = createTest[EntityName]({ uniqueField: 'duplicate' });
      await repository.save(duplicateEntity);

      // Act & Assert
      await expect(repository.save(duplicateEntity))
        .rejects.toThrow(/constraint violation/i);
    });
  });
});
```

---

## Performance Test Templates

### Latency Test Template

```typescript
// tests/performance/[feature]-performance.test.ts
import { PerformanceMonitor } from '../../src/utils/PerformanceMonitor';
import { [ServiceName] } from '../../src/services/[ServiceName]';

describe('[Feature] Performance Tests', () => {
  let service: [ServiceName];
  let monitor: PerformanceMonitor;

  beforeAll(() => {
    jest.setTimeout(30000); // Extended timeout for performance tests
  });

  beforeEach(() => {
    service = new [ServiceName]();
    monitor = new PerformanceMonitor();
  });

  describe('Latency Requirements', () => {
    test('should complete [operation] within [X]ms', async () => {
      // Arrange
      const testData = [performanceTestData];
      const maxLatencyMs = [maxLatency];
      const iterations = 100;
      const latencies: number[] = [];

      // Act
      for (let i = 0; i < iterations; i++) {
        const startTime = performance.now();
        await service.[operation](testData);
        const latency = performance.now() - startTime;
        latencies.push(latency);
      }

      // Assert
      const avgLatency = latencies.reduce((sum, lat) => sum + lat, 0) / latencies.length;
      const maxLatency = Math.max(...latencies);
      const p95Latency = latencies.sort((a, b) => a - b)[Math.floor(iterations * 0.95)];

      console.log(`Performance Metrics:
        Average Latency: ${avgLatency.toFixed(2)}ms
        Max Latency: ${maxLatency.toFixed(2)}ms
        P95 Latency: ${p95Latency.toFixed(2)}ms`);

      expect(avgLatency).toBeLessThan(maxLatencyMs);
      expect(p95Latency).toBeLessThan(maxLatencyMs * 1.5); // 50% tolerance for P95
    });

    test('should maintain performance under concurrent load', async () => {
      // Arrange
      const concurrentRequests = 50;
      const maxLatencyMs = [maxLatency * 2]; // Allow higher latency under load

      // Act
      const promises = Array(concurrentRequests).fill(null).map(async () => {
        const startTime = performance.now();
        await service.[operation]([testData]);
        return performance.now() - startTime;
      });

      const latencies = await Promise.all(promises);

      // Assert
      const avgLatency = latencies.reduce((sum, lat) => sum + lat, 0) / latencies.length;
      const successfulRequests = latencies.filter(lat => lat < maxLatencyMs).length;
      const successRate = successfulRequests / concurrentRequests;

      console.log(`Concurrent Load Results:
        Successful Requests: ${successfulRequests}/${concurrentRequests}
        Success Rate: ${(successRate * 100).toFixed(1)}%
        Average Latency: ${avgLatency.toFixed(2)}ms`);

      expect(successRate).toBeGreaterThan(0.95); // 95% success rate
      expect(avgLatency).toBeLessThan(maxLatencyMs);
    });
  });
});
```

### Memory Test Template

```typescript
describe('Memory Performance', () => {
  test('should not leak memory during intensive operations', async () => {
    // Arrange
    const initialMemory = process.memoryUsage().heapUsed;
    const iterations = 10000;
    const service = new [ServiceName]();

    // Act
    for (let i = 0; i < iterations; i++) {
      await service.[operation]([testData]);

      // Periodic garbage collection hint
      if (i % 1000 === 0 && global.gc) {
        global.gc();
      }
    }

    // Force garbage collection before measurement
    if (global.gc) {
      global.gc();
      await new Promise(resolve => setTimeout(resolve, 100)); // Allow GC to complete
    }

    const finalMemory = process.memoryUsage().heapUsed;
    const memoryIncrease = finalMemory - initialMemory;
    const memoryIncreaseInMB = memoryIncrease / (1024 * 1024);

    console.log(`Memory Usage:
      Initial: ${(initialMemory / 1024 / 1024).toFixed(2)} MB
      Final: ${(finalMemory / 1024 / 1024).toFixed(2)} MB
      Increase: ${memoryIncreaseInMB.toFixed(2)} MB`);

    // Assert
    expect(memoryIncreaseInMB).toBeLessThan(50); // Less than 50MB increase
  });
});
```

---

## React Component Test Templates

### Basic Component Test Template

```typescript
// tests/unit/components/[ComponentName].test.tsx
import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { [ComponentName] } from '../../../src/components/[ComponentName]';

// Mock dependencies
jest.mock('../../../src/hooks/[hookName]', () => ({
  [hookName]: jest.fn()
}));

describe('[ComponentName]', () => {
  const defaultProps = {
    prop1: 'value1',
    prop2: 'value2',
    onAction: jest.fn()
  };

  beforeEach(() => {
    jest.clearAllMocks();
  });

  describe('Rendering', () => {
    test('should render with required props', () => {
      render(<[ComponentName] {...defaultProps} />);

      expect(screen.getByText([expectedText])).toBeInTheDocument();
      expect(screen.getByRole([expectedRole])).toBeInTheDocument();
    });

    test('should render with optional props', () => {
      const propsWithOptional = {
        ...defaultProps,
        optionalProp: 'optional value'
      };

      render(<[ComponentName] {...propsWithOptional} />);

      expect(screen.getByText('optional value')).toBeInTheDocument();
    });

    test('should apply custom className', () => {
      const customClass = 'custom-test-class';

      render(<[ComponentName] {...defaultProps} className={customClass} />);

      expect(screen.getByTestId('[component-test-id]')).toHaveClass(customClass);
    });
  });

  describe('User Interactions', () => {
    test('should handle click events', async () => {
      const user = userEvent.setup();
      render(<[ComponentName] {...defaultProps} />);

      const button = screen.getByRole('button', { name: /[button text]/i });
      await user.click(button);

      expect(defaultProps.onAction).toHaveBeenCalledTimes(1);
      expect(defaultProps.onAction).toHaveBeenCalledWith([expectedCallData]);
    });

    test('should handle form input', async () => {
      const user = userEvent.setup();
      render(<[ComponentName] {...defaultProps} />);

      const input = screen.getByLabelText(/[input label]/i);
      await user.type(input, 'test input');

      expect(input).toHaveValue('test input');
    });

    test('should validate form submission', async () => {
      const user = userEvent.setup();
      render(<[ComponentName] {...defaultProps} />);

      const submitButton = screen.getByRole('button', { name: /submit/i });
      await user.click(submitButton);

      await waitFor(() => {
        expect(screen.getByText(/validation error/i)).toBeInTheDocument();
      });
    });
  });

  describe('State Management', () => {
    test('should update state on user action', async () => {
      const user = userEvent.setup();
      render(<[ComponentName] {...defaultProps} />);

      const toggleButton = screen.getByRole('button', { name: /toggle/i });

      // Initial state
      expect(screen.getByText(/initial state/i)).toBeInTheDocument();

      // After toggle
      await user.click(toggleButton);

      await waitFor(() => {
        expect(screen.getByText(/updated state/i)).toBeInTheDocument();
      });
    });
  });

  describe('Error Handling', () => {
    test('should display error message when error prop provided', () => {
      const errorProps = {
        ...defaultProps,
        error: 'Test error message'
      };

      render(<[ComponentName] {...errorProps} />);

      expect(screen.getByText('Test error message')).toBeInTheDocument();
      expect(screen.getByRole('alert')).toBeInTheDocument();
    });

    test('should handle loading state', () => {
      const loadingProps = {
        ...defaultProps,
        loading: true
      };

      render(<[ComponentName] {...loadingProps} />);

      expect(screen.getByTestId('loading-spinner')).toBeInTheDocument();
    });
  });
});
```

### Context Provider Test Template

```typescript
describe('[ContextProvider]', () => {
  const TestComponent = () => {
    const context = useContext([ContextName]);

    return (
      <div>
        <span data-testid="context-value">{context.value}</span>
        <button onClick={context.updateValue}>Update</button>
      </div>
    );
  };

  test('should provide context values to children', () => {
    render(
      <[ContextProvider] initialValue="test">
        <TestComponent />
      </[ContextProvider]>
    );

    expect(screen.getByTestId('context-value')).toHaveTextContent('test');
  });

  test('should update context state', async () => {
    const user = userEvent.setup();

    render(
      <[ContextProvider]>
        <TestComponent />
      </[ContextProvider]>
    );

    const updateButton = screen.getByRole('button', { name: /update/i });
    await user.click(updateButton);

    await waitFor(() => {
      expect(screen.getByTestId('context-value')).toHaveTextContent('updated');
    });
  });
});
```

---

## Service Test Templates

### API Service Test Template

```typescript
describe('[APIServiceName]', () => {
  let service: [APIServiceName];
  let mockFetch: jest.Mock;

  beforeEach(() => {
    mockFetch = jest.fn();
    global.fetch = mockFetch;
    service = new [APIServiceName]('https://api.test.com', 'test-key');
  });

  afterEach(() => {
    jest.restoreAllMocks();
  });

  describe('[methodName]', () => {
    test('should make correct API call', async () => {
      // Arrange
      const testData = [requestData];
      const mockResponse = [responseData];

      mockFetch.mockResolvedValue({
        ok: true,
        json: () => Promise.resolve(mockResponse)
      });

      // Act
      const result = await service.[methodName](testData);

      // Assert
      expect(mockFetch).toHaveBeenCalledWith(
        'https://api.test.com/[endpoint]',
        {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'Authorization': 'Bearer test-key'
          },
          body: JSON.stringify(testData)
        }
      );
      expect(result).toEqual(mockResponse);
    });

    test('should handle API errors', async () => {
      // Arrange
      mockFetch.mockResolvedValue({
        ok: false,
        status: 400,
        statusText: 'Bad Request',
        json: () => Promise.resolve({ error: 'Invalid request' })
      });

      // Act & Assert
      await expect(service.[methodName]([testData]))
        .rejects.toThrow('API Error: 400 - Invalid request');
    });

    test('should handle network errors', async () => {
      // Arrange
      mockFetch.mockRejectedValue(new Error('Network error'));

      // Act & Assert
      await expect(service.[methodName]([testData]))
        .rejects.toThrow('Network error');
    });

    test('should retry on transient failures', async () => {
      // Arrange
      const finalResponse = [successResponse];

      mockFetch
        .mockRejectedValueOnce(new Error('Network timeout'))
        .mockRejectedValueOnce(new Error('Connection reset'))
        .mockResolvedValue({
          ok: true,
          json: () => Promise.resolve(finalResponse)
        });

      // Act
      const result = await service.[methodName]([testData]);

      // Assert
      expect(result).toEqual(finalResponse);
      expect(mockFetch).toHaveBeenCalledTimes(3);
    });
  });
});
```

### WebSocket Service Test Template

```typescript
describe('[WebSocketServiceName]', () => {
  let service: [WebSocketServiceName];
  let mockWebSocket: any;
  let onMessage: jest.Mock;
  let onError: jest.Mock;

  beforeEach(() => {
    onMessage = jest.fn();
    onError = jest.fn();

    mockWebSocket = {
      send: jest.fn(),
      close: jest.fn(),
      addEventListener: jest.fn(),
      removeEventListener: jest.fn(),
      readyState: WebSocket.CONNECTING
    };

    global.WebSocket = jest.fn(() => mockWebSocket);
    service = new [WebSocketServiceName]('ws://test.com', { onMessage, onError });
  });

  afterEach(() => {
    jest.restoreAllMocks();
  });

  describe('Connection Management', () => {
    test('should establish WebSocket connection', () => {
      service.connect();

      expect(global.WebSocket).toHaveBeenCalledWith('ws://test.com');
      expect(mockWebSocket.addEventListener).toHaveBeenCalledWith('open', expect.any(Function));
      expect(mockWebSocket.addEventListener).toHaveBeenCalledWith('message', expect.any(Function));
      expect(mockWebSocket.addEventListener).toHaveBeenCalledWith('error', expect.any(Function));
      expect(mockWebSocket.addEventListener).toHaveBeenCalledWith('close', expect.any(Function));
    });

    test('should handle connection open', () => {
      service.connect();

      // Simulate connection open
      const openHandler = mockWebSocket.addEventListener.mock.calls
        .find(call => call[0] === 'open')[1];

      mockWebSocket.readyState = WebSocket.OPEN;
      openHandler();

      expect(service.isConnected()).toBe(true);
    });

    test('should handle incoming messages', () => {
      const testMessage = { type: 'price', symbol: 'EUR/USD', price: 1.2050 };

      service.connect();

      // Simulate message received
      const messageHandler = mockWebSocket.addEventListener.mock.calls
        .find(call => call[0] === 'message')[1];

      messageHandler({
        data: JSON.stringify(testMessage)
      });

      expect(onMessage).toHaveBeenCalledWith(testMessage);
    });

    test('should handle connection errors', () => {
      service.connect();

      // Simulate error
      const errorHandler = mockWebSocket.addEventListener.mock.calls
        .find(call => call[0] === 'error')[1];

      const error = new Error('Connection failed');
      errorHandler(error);

      expect(onError).toHaveBeenCalledWith(error);
    });
  });

  describe('Message Sending', () => {
    test('should send message when connected', () => {
      const message = { type: 'subscribe', symbol: 'EUR/USD' };

      mockWebSocket.readyState = WebSocket.OPEN;
      service.send(message);

      expect(mockWebSocket.send).toHaveBeenCalledWith(JSON.stringify(message));
    });

    test('should queue message when not connected', () => {
      const message = { type: 'subscribe', symbol: 'EUR/USD' };

      mockWebSocket.readyState = WebSocket.CONNECTING;
      service.send(message);

      expect(mockWebSocket.send).not.toHaveBeenCalled();

      // Simulate connection open
      mockWebSocket.readyState = WebSocket.OPEN;
      service.onConnectionOpen();

      expect(mockWebSocket.send).toHaveBeenCalledWith(JSON.stringify(message));
    });
  });
});
```

---

## Mock Templates

### Service Mock Template

```typescript
// tests/mocks/[ServiceName].mock.ts
export const create[ServiceName]Mock = (): jest.Mocked<[ServiceName]> => {
  return {
    [method1]: jest.fn(),
    [method2]: jest.fn(),
    [asyncMethod]: jest.fn(),
    // Add all methods from the service interface
  } as jest.Mocked<[ServiceName]>;
};

export const [serviceName]MockImplementation = {
  [method1]: jest.fn().mockReturnValue([defaultReturnValue]),
  [method2]: jest.fn().mockImplementation((param) => [defaultImplementation]),
  [asyncMethod]: jest.fn().mockResolvedValue([defaultAsyncReturnValue]),
};
```

### API Response Mock Template

```typescript
// tests/mocks/apiResponses.mock.ts
export const mockApiResponses = {
  [endpoint]: {
    success: {
      data: [successResponseData],
      status: 'success',
      timestamp: '2023-01-01T00:00:00Z'
    },
    error: {
      error: 'Test error message',
      status: 'error',
      code: 'TEST_ERROR',
      timestamp: '2023-01-01T00:00:00Z'
    },
    validationError: {
      error: 'Validation failed',
      status: 'error',
      code: 'VALIDATION_ERROR',
      details: [
        { field: 'testField', message: 'Field is required' }
      ],
      timestamp: '2023-01-01T00:00:00Z'
    }
  }
};
```

### WebSocket Message Mock Template

```typescript
// tests/mocks/webSocketMessages.mock.ts
export const mockWebSocketMessages = {
  priceUpdate: {
    type: 'price',
    symbol: 'EUR/USD',
    bid: 1.2048,
    ask: 1.2050,
    timestamp: Date.now()
  },
  orderUpdate: {
    type: 'orderUpdate',
    orderId: 'test-order-123',
    status: 'EXECUTED',
    executionPrice: 1.2049,
    timestamp: Date.now()
  },
  error: {
    type: 'error',
    message: 'Test WebSocket error',
    code: 'WS_ERROR',
    timestamp: Date.now()
  }
};
```

---

## Setup and Teardown Templates

### Database Setup Template

```typescript
// tests/setup/database.setup.ts
import { DatabaseConnection } from '../../src/database/connection';

export class TestDatabaseSetup {
  private static connection: DatabaseConnection;

  static async setupDatabase(): Promise<DatabaseConnection> {
    if (!this.connection) {
      this.connection = await DatabaseConnection.create({
        type: 'sqlite',
        database: ':memory:',
        synchronize: true,
        logging: false,
        entities: ['src/**/*.entity.ts']
      });
    }
    return this.connection;
  }

  static async teardownDatabase(): Promise<void> {
    if (this.connection) {
      await this.connection.close();
      this.connection = null;
    }
  }

  static async clearAllTables(): Promise<void> {
    if (this.connection) {
      const entities = this.connection.entityMetadatas;

      await this.connection.transaction(async manager => {
        for (const entity of entities) {
          await manager.query(`DELETE FROM ${entity.tableName}`);
        }
      });
    }
  }
}
```

### Test Environment Setup Template

```typescript
// tests/setup/testEnvironment.setup.ts
export const setupTestEnvironment = () => {
  // Mock global objects
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

  // Mock performance API
  Object.defineProperty(performance, 'now', {
    value: jest.fn(() => Date.now())
  });

  // Mock localStorage
  const localStorageMock = {
    getItem: jest.fn(),
    setItem: jest.fn(),
    removeItem: jest.fn(),
    clear: jest.fn(),
  };
  Object.defineProperty(window, 'localStorage', {
    value: localStorageMock
  });

  // Mock WebSocket
  global.WebSocket = jest.fn().mockImplementation(() => ({
    send: jest.fn(),
    close: jest.fn(),
    addEventListener: jest.fn(),
    removeEventListener: jest.fn(),
  }));

  // Mock fetch
  global.fetch = jest.fn();

  // Console override for cleaner test output
  const originalError = console.error;
  beforeAll(() => {
    console.error = (...args: any[]) => {
      if (typeof args[0] === 'string' && args[0].includes('Warning:')) {
        return; // Suppress React warnings in tests
      }
      originalError.call(console, ...args);
    };
  });

  afterAll(() => {
    console.error = originalError;
  });
};
```

### Custom Test Utilities Template

```typescript
// tests/utils/testUtils.tsx
import React from 'react';
import { render, RenderOptions } from '@testing-library/react';
import { [ContextProvider] } from '../../src/contexts/[ContextName]';
import { ThemeProvider } from '@mui/material/styles';
import { theme } from '../../src/theme/theme';

// Custom render function with providers
const AllTheProviders: React.FC<{ children: React.ReactNode }> = ({
  children,
}) => {
  return (
    <ThemeProvider theme={theme}>
      <[ContextProvider]>
        {children}
      </[ContextProvider]>
    </ThemeProvider>
  );
};

const customRender = (
  ui: React.ReactElement,
  options?: Omit<RenderOptions, 'wrapper'>
) => render(ui, { wrapper: AllTheProviders, ...options });

// Test data factories
export const createTestOrder = (overrides = {}) => ({
  id: 'test-order-123',
  symbol: 'EUR/USD',
  side: 'BUY',
  quantity: 100000,
  type: 'MARKET',
  status: 'PENDING',
  timestamp: new Date().toISOString(),
  ...overrides,
});

export const createTestMarketData = (overrides = {}) => ({
  symbol: 'EUR/USD',
  bid: 1.2048,
  ask: 1.2050,
  timestamp: Date.now(),
  ...overrides,
});

// Async test helpers
export const waitForCondition = async (
  condition: () => boolean,
  timeout: number = 5000
): Promise<void> => {
  const startTime = Date.now();

  while (!condition() && Date.now() - startTime < timeout) {
    await new Promise(resolve => setTimeout(resolve, 10));
  }

  if (!condition()) {
    throw new Error(`Condition not met within ${timeout}ms`);
  }
};

// Re-export everything
export * from '@testing-library/react';
export { customRender as render };
```

---

## Usage Guidelines

### How to Use These Templates

1. **Copy the appropriate template** for your test scenario
2. **Replace placeholder values** (marked with `[brackets]`) with actual values
3. **Customize the test cases** to match your specific requirements
4. **Add additional test scenarios** as needed for your use case
5. **Follow the naming conventions** established in the templates

### Template Selection Guide

| Test Type | Use When | Template to Use |
|-----------|----------|----------------|
| Unit Test | Testing individual functions/methods | Basic Function Test Template |
| Async Unit Test | Testing async operations | Async Function Test Template |
| Component Test | Testing React components | Basic Component Test Template |
| Integration Test | Testing component interactions | API Integration Test Template |
| Performance Test | Testing speed/memory usage | Latency/Memory Test Templates |
| Service Test | Testing API/WebSocket services | Service Test Templates |

### Best Practices

1. **Start with the template** closest to your use case
2. **Customize gradually** - don't try to modify everything at once
3. **Keep tests focused** - one concept per test
4. **Use descriptive names** - follow the "should [behavior] when [condition]" pattern
5. **Mock external dependencies** - keep tests isolated and fast
6. **Include edge cases** - test error conditions and boundary values
7. **Maintain test data** - use factories for consistent test data creation

These templates provide a solid foundation for implementing comprehensive TDD practices in the FXML4 project. They follow the established patterns and best practices documented in our methodology guide.
