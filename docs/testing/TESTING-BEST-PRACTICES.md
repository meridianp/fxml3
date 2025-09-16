# FXML4 Testing Best Practices

## Table of Contents
- [Code Organization](#code-organization)
- [Naming Conventions](#naming-conventions)
- [Test Data Management](#test-data-management)
- [Mocking Strategies](#mocking-strategies)
- [Error Testing](#error-testing)
- [Performance Guidelines](#performance-guidelines)
- [CI/CD Integration](#cicd-integration)
- [Code Coverage](#code-coverage)
- [Common Pitfalls](#common-pitfalls)

## Code Organization

### Directory Structure
```
tests/
├── unit/                    # Unit tests (70% of tests)
│   ├── services/
│   │   ├── OrderService.test.ts
│   │   ├── WebSocketService.comprehensive.test.ts
│   │   └── AuthService.test.ts
│   ├── components/
│   │   ├── TradingDashboard.test.tsx
│   │   └── OrderPanel.test.tsx
│   └── utils/
│       ├── DateUtils.test.ts
│       └── PerformanceMonitor.test.ts
├── integration/             # Integration tests (20% of tests)
│   ├── trading-workflow.test.ts
│   ├── frontend-integration.test.tsx
│   └── api-integration.test.ts
├── performance/             # Performance tests (10% of tests)
│   ├── latency-validation.test.ts
│   ├── comprehensive-load-testing.test.ts
│   └── performance-dashboard.test.ts
├── mocks/                   # Shared mock data
│   ├── tradingMocks.ts
│   ├── apiMocks.ts
│   └── userMocks.ts
└── utils/                   # Test utilities
    ├── testHelpers.ts
    ├── renderWithProviders.tsx
    └── setupTests.ts
```

### File Naming Conventions

```bash
# Unit tests
ComponentName.test.tsx       # React components
ServiceName.test.ts          # Services and utilities
ServiceName.comprehensive.test.ts  # Comprehensive coverage tests

# Integration tests
feature-workflow.test.ts     # Feature workflows
component-integration.test.tsx  # Component integration

# Performance tests
performance-category.test.ts # Performance tests by category
```

### Test File Structure

```typescript
/**
 * Test file header with description
 *
 * Tests for [ComponentName/ServiceName]
 * Covers: [list main functionality being tested]
 */

import { dependencies } from './path';

// Mocks should be at the top
jest.mock('./external-dependency');

describe('ComponentName/ServiceName', () => {
  // Setup and teardown
  let service: ServiceName;
  let mockDependency: jest.Mocked<DependencyType>;

  beforeAll(() => {
    // One-time setup
  });

  beforeEach(() => {
    // Setup before each test
    service = new ServiceName();
    mockDependency = createMockDependency();
  });

  afterEach(() => {
    // Cleanup after each test
    jest.clearAllMocks();
  });

  afterAll(() => {
    // One-time cleanup
  });

  // Group related tests
  describe('Initialization', () => {
    test('should initialize with default values', () => {
      // Test implementation
    });
  });

  describe('Core Functionality', () => {
    test('should handle normal operations', () => {
      // Test implementation
    });

    test('should handle edge cases', () => {
      // Test implementation
    });
  });

  describe('Error Handling', () => {
    test('should handle invalid input gracefully', () => {
      // Test implementation
    });
  });
});
```

## Naming Conventions

### Test Names
Follow the pattern: `should [expected behavior] when [condition]`

```typescript
// ✅ Good - Clear and descriptive
describe('Order Validation', () => {
  test('should accept order when all fields are valid', () => {});
  test('should reject order when quantity exceeds balance', () => {});
  test('should throw error when symbol is not supported', () => {});
  test('should calculate margin correctly for leveraged trades', () => {});
});

// ❌ Bad - Vague or unclear
describe('Order Tests', () => {
  test('validation works', () => {});
  test('error case', () => {});
  test('test order', () => {});
});
```

### Variable Names

```typescript
// ✅ Good - Descriptive and purposeful
const mockOrderService = jest.mocked(OrderService);
const validEurUsdOrder = createTestOrder({ symbol: 'EUR/USD' });
const expectedApiResponse = { success: true, orderId: '12345' };
const userWithInsufficientBalance = createTestUser({ balance: 100 });

// ❌ Bad - Generic or unclear
const mock = jest.mocked(Service);
const order = createOrder();
const response = { data: 'test' };
const user = createUser();
```

## Test Data Management

### Centralized Test Data

```typescript
// tests/mocks/tradingMocks.ts
export const mockMarketData = {
  'EUR/USD': {
    symbol: 'EUR/USD',
    bid: 1.2048,
    ask: 1.2050,
    spread: 0.0002,
    timestamp: '2023-12-01T10:00:00Z'
  },
  'GBP/USD': {
    symbol: 'GBP/USD',
    bid: 1.3945,
    ask: 1.3948,
    spread: 0.0003,
    timestamp: '2023-12-01T10:00:00Z'
  }
};

export const mockOrders = {
  validMarketOrder: {
    symbol: 'EUR/USD',
    side: 'BUY' as const,
    quantity: 100000,
    type: 'MARKET' as const,
    timestamp: new Date('2023-12-01T10:00:00Z')
  },
  validLimitOrder: {
    symbol: 'EUR/USD',
    side: 'SELL' as const,
    quantity: 50000,
    type: 'LIMIT' as const,
    price: 1.2055,
    timestamp: new Date('2023-12-01T10:00:00Z')
  }
};

export const mockPositions = [
  {
    id: 'pos-001',
    symbol: 'EUR/USD',
    side: 'LONG',
    quantity: 100000,
    entryPrice: 1.2045,
    currentPrice: 1.2050,
    unrealizedPnL: 50.0,
    timestamp: new Date('2023-12-01T09:30:00Z')
  }
];
```

### Test Data Builders

```typescript
// tests/utils/testDataBuilders.ts
export class OrderBuilder {
  private order: Partial<Order> = {};

  static create(): OrderBuilder {
    return new OrderBuilder();
  }

  symbol(symbol: string): OrderBuilder {
    this.order.symbol = symbol;
    return this;
  }

  buy(): OrderBuilder {
    this.order.side = 'BUY';
    return this;
  }

  sell(): OrderBuilder {
    this.order.side = 'SELL';
    return this;
  }

  quantity(quantity: number): OrderBuilder {
    this.order.quantity = quantity;
    return this;
  }

  marketOrder(): OrderBuilder {
    this.order.type = 'MARKET';
    return this;
  }

  limitOrder(price: number): OrderBuilder {
    this.order.type = 'LIMIT';
    this.order.price = price;
    return this;
  }

  build(): Order {
    return {
      symbol: 'EUR/USD',
      side: 'BUY',
      quantity: 100000,
      type: 'MARKET',
      timestamp: new Date(),
      ...this.order
    } as Order;
  }
}

// Usage in tests
test('should process large orders', () => {
  const largeOrder = OrderBuilder.create()
    .symbol('EUR/USD')
    .buy()
    .quantity(1000000)
    .marketOrder()
    .build();

  const result = orderProcessor.process(largeOrder);
  expect(result.success).toBe(true);
});
```

## Mocking Strategies

### Service Mocking

```typescript
// Mock entire service
jest.mock('../../services/TradingAPIService');

describe('OrderService', () => {
  let mockApiService: jest.Mocked<TradingAPIService>;

  beforeEach(() => {
    mockApiService = {
      submitOrder: jest.fn(),
      getOrderStatus: jest.fn(),
      cancelOrder: jest.fn(),
      getPositions: jest.fn()
    } as any;

    (TradingAPIService as jest.MockedClass<typeof TradingAPIService>)
      .mockImplementation(() => mockApiService);
  });

  test('should handle successful order submission', async () => {
    mockApiService.submitOrder.mockResolvedValue({
      success: true,
      orderId: 'order-123',
      status: 'PENDING'
    });

    const service = new OrderService();
    const result = await service.submitOrder(testOrder);

    expect(result.orderId).toBe('order-123');
    expect(mockApiService.submitOrder).toHaveBeenCalledWith(testOrder);
  });
});
```

### Partial Mocking

```typescript
// Mock only specific methods
const mockMarketDataService = {
  getCurrentPrice: jest.fn(),
  subscribe: jest.fn(),
  unsubscribe: jest.fn()
} as jest.Mocked<Partial<MarketDataService>>;

test('should fetch current price', async () => {
  mockMarketDataService.getCurrentPrice!.mockResolvedValue({
    bid: 1.2048,
    ask: 1.2050
  });

  const result = await service.getPrice('EUR/USD');
  expect(result.bid).toBe(1.2048);
});
```

### WebSocket Mocking

```typescript
class MockWebSocket {
  public onopen: ((event: Event) => void) | null = null;
  public onmessage: ((event: MessageEvent) => void) | null = null;
  public onclose: ((event: CloseEvent) => void) | null = null;
  public onerror: ((event: Event) => void) | null = null;

  public sentMessages: string[] = [];

  constructor(public url: string) {}

  send(data: string): void {
    this.sentMessages.push(data);
  }

  close(code?: number, reason?: string): void {
    if (this.onclose) {
      this.onclose(new CloseEvent('close', { code, reason }));
    }
  }

  simulateOpen(): void {
    if (this.onopen) {
      this.onopen(new Event('open'));
    }
  }

  simulateMessage(data: any): void {
    if (this.onmessage) {
      this.onmessage(new MessageEvent('message', {
        data: JSON.stringify(data)
      }));
    }
  }

  simulateError(): void {
    if (this.onerror) {
      this.onerror(new Event('error'));
    }
  }
}

// Use in tests
beforeEach(() => {
  global.WebSocket = MockWebSocket as any;
});
```

## Error Testing

### Exception Testing

```typescript
describe('Error Handling', () => {
  test('should throw ValidationError for invalid order', () => {
    const invalidOrder = { symbol: '', quantity: -100 };

    expect(() => validator.validate(invalidOrder))
      .toThrow(ValidationError);
  });

  test('should throw specific error message', () => {
    expect(() => validator.validate(invalidOrder))
      .toThrow('Invalid quantity: must be positive');
  });

  test('should handle async errors', async () => {
    mockApiService.submitOrder.mockRejectedValue(
      new Error('Network timeout')
    );

    await expect(orderService.submitOrder(order))
      .rejects.toThrow('Network timeout');
  });
});
```

### Error Recovery Testing

```typescript
test('should retry on temporary failures', async () => {
  // First call fails, second succeeds
  mockApiService.submitOrder
    .mockRejectedValueOnce(new Error('Temporary failure'))
    .mockResolvedValueOnce({ success: true, orderId: '123' });

  const result = await orderService.submitOrderWithRetry(order);

  expect(result.orderId).toBe('123');
  expect(mockApiService.submitOrder).toHaveBeenCalledTimes(2);
});
```

### Boundary Testing

```typescript
describe('Boundary Conditions', () => {
  test('should handle minimum order quantity', () => {
    const minOrder = { ...testOrder, quantity: 1000 }; // Minimum
    expect(() => validator.validate(minOrder)).not.toThrow();
  });

  test('should handle maximum order quantity', () => {
    const maxOrder = { ...testOrder, quantity: 10000000 }; // Maximum
    expect(() => validator.validate(maxOrder)).not.toThrow();
  });

  test('should reject quantity below minimum', () => {
    const belowMinOrder = { ...testOrder, quantity: 999 };
    expect(() => validator.validate(belowMinOrder))
      .toThrow('Quantity below minimum');
  });

  test('should reject quantity above maximum', () => {
    const aboveMaxOrder = { ...testOrder, quantity: 10000001 };
    expect(() => validator.validate(aboveMaxOrder))
      .toThrow('Quantity exceeds maximum');
  });
});
```

## Performance Guidelines

### Test Performance

```typescript
// Set reasonable timeouts
describe('Performance-Critical Tests', () => {
  beforeAll(() => {
    jest.setTimeout(10000); // 10 seconds for performance tests
  });

  test('should complete order processing within 100ms', async () => {
    const startTime = performance.now();

    await orderProcessor.process(testOrder);

    const duration = performance.now() - startTime;
    expect(duration).toBeLessThan(100);
  });
});
```

### Memory Testing

```typescript
test('should not leak memory during batch processing', async () => {
  const initialMemory = process.memoryUsage().heapUsed;

  // Process many orders
  const promises = Array(1000).fill(null).map(() =>
    orderProcessor.process(createTestOrder())
  );
  await Promise.all(promises);

  // Force garbage collection
  if (global.gc) global.gc();

  const finalMemory = process.memoryUsage().heapUsed;
  const memoryIncrease = finalMemory - initialMemory;

  expect(memoryIncrease).toBeLessThan(50 * 1024 * 1024); // 50MB limit
});
```

### Load Testing Patterns

```typescript
test('should handle concurrent requests', async () => {
  const concurrentRequests = 100;
  const promises = Array(concurrentRequests).fill(null).map(() =>
    api.submitOrder(createUniqueOrder())
  );

  const results = await Promise.allSettled(promises);
  const successful = results.filter(r => r.status === 'fulfilled');

  expect(successful.length).toBeGreaterThan(95); // 95% success rate
});
```

## CI/CD Integration

### GitHub Actions Configuration

```yaml
# .github/workflows/tests.yml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest

    strategy:
      matrix:
        node-version: [18.x, 20.x]

    steps:
      - uses: actions/checkout@v3

      - name: Use Node.js ${{ matrix.node-version }}
        uses: actions/setup-node@v3
        with:
          node-version: ${{ matrix.node-version }}
          cache: 'npm'

      - name: Install dependencies
        run: npm ci

      - name: Run linting
        run: npm run lint

      - name: Run unit tests
        run: npm run test:unit

      - name: Run integration tests
        run: npm run test:integration

      - name: Run performance tests
        run: npm run test:performance

      - name: Generate coverage report
        run: npm run test:coverage

      - name: Upload coverage to Codecov
        uses: codecov/codecov-action@v3
```

### Pre-commit Hooks

```json
// package.json
{
  "husky": {
    "hooks": {
      "pre-commit": "lint-staged"
    }
  },
  "lint-staged": {
    "*.{ts,tsx}": [
      "eslint --fix",
      "prettier --write",
      "npm run test:staged"
    ]
  },
  "scripts": {
    "test:staged": "jest --findRelatedTests --passWithNoTests"
  }
}
```

## Code Coverage

### Coverage Configuration

```javascript
// jest.config.js
module.exports = {
  collectCoverageFrom: [
    'src/**/*.{ts,tsx}',
    '!src/**/*.d.ts',
    '!src/**/index.ts',
    '!src/**/*.stories.tsx'
  ],
  coverageThreshold: {
    global: {
      branches: 80,
      functions: 80,
      lines: 85,
      statements: 85
    },
    // Per-file thresholds for critical components
    './src/services/OrderService.ts': {
      branches: 90,
      functions: 90,
      lines: 95,
      statements: 95
    }
  },
  coverageReporters: ['text', 'lcov', 'html', 'cobertura']
};
```

### Coverage Analysis

```bash
# Generate detailed coverage report
npm run test:coverage

# View HTML coverage report
open coverage/lcov-report/index.html

# Check coverage for specific files
npm test -- --coverage --collectCoverageOnlyFrom="src/services/OrderService.ts"
```

### Coverage Best Practices

- **Aim for >85% line coverage** on critical business logic
- **Focus on branch coverage** to ensure all code paths are tested
- **Don't chase 100% coverage** at the expense of test quality
- **Use coverage reports** to identify untested edge cases
- **Exclude generated files** and configuration from coverage

## Common Pitfalls

### ❌ Pitfall: Testing Implementation Details

```typescript
// Bad - Testing internal implementation
test('should call private method', () => {
  const spy = jest.spyOn(service, 'privateMethod' as any);
  service.publicMethod();
  expect(spy).toHaveBeenCalled();
});

// Good - Testing behavior
test('should calculate correct result', () => {
  const result = service.publicMethod(input);
  expect(result).toBe(expectedOutput);
});
```

### ❌ Pitfall: Brittle Tests

```typescript
// Bad - Too specific, breaks easily
test('should render exact HTML structure', () => {
  render(<Component />);
  expect(screen.getByTestId('container').innerHTML)
    .toBe('<div class="specific-class"><span>Text</span></div>');
});

// Good - Test user-visible behavior
test('should display expected content', () => {
  render(<Component />);
  expect(screen.getByText('Text')).toBeInTheDocument();
});
```

### ❌ Pitfall: Flaky Tests

```typescript
// Bad - Timing-dependent
test('should update after delay', async () => {
  triggerUpdate();
  await new Promise(resolve => setTimeout(resolve, 100));
  expect(getState()).toBe('updated');
});

// Good - Wait for specific condition
test('should update when condition met', async () => {
  triggerUpdate();
  await waitFor(() => {
    expect(getState()).toBe('updated');
  });
});
```

### ❌ Pitfall: Shared Test State

```typescript
// Bad - Tests affect each other
let sharedService = new Service();

test('test A', () => {
  sharedService.setValue(1);
  expect(sharedService.getValue()).toBe(1);
});

test('test B', () => {
  // This test might fail if test A didn't run
  expect(sharedService.getValue()).toBe(0);
});

// Good - Isolated test state
describe('Service', () => {
  let service: Service;

  beforeEach(() => {
    service = new Service();
  });

  test('test A', () => {
    service.setValue(1);
    expect(service.getValue()).toBe(1);
  });

  test('test B', () => {
    expect(service.getValue()).toBe(0);
  });
});
```

## Test Maintenance

### Regular Test Review
- **Review test failures** regularly and fix flaky tests immediately
- **Update tests** when requirements change
- **Refactor tests** when they become hard to understand
- **Remove obsolete tests** for deprecated functionality

### Performance Monitoring
- **Monitor test suite execution time** and optimize slow tests
- **Use test sharding** for large test suites
- **Optimize setup/teardown** to reduce overhead

### Documentation
- **Document complex test scenarios** with comments
- **Keep test documentation** up to date with code changes
- **Share testing knowledge** through team code reviews

---

**Remember**: Good tests are investments in code quality. They should be treated with the same care and attention as production code.
