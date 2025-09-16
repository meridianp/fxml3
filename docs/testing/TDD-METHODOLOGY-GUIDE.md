# FXML4 Test-Driven Development (TDD) Methodology Guide

## Table of Contents
- [TDD Principles](#tdd-principles)
- [Red-Green-Refactor Cycle](#red-green-refactor-cycle)
- [Testing Pyramid](#testing-pyramid)
- [Test Categories](#test-categories)
- [Best Practices](#best-practices)
- [Common Patterns](#common-patterns)
- [Performance Testing](#performance-testing)
- [Tools and Setup](#tools-and-setup)

## TDD Principles

### Core Philosophy
Test-Driven Development is a software development methodology where tests are written **before** the implementation code. This approach ensures:

- **Design by Contract**: Tests define the expected behavior before implementation
- **Code Quality**: Only necessary code is written to pass tests
- **Regression Prevention**: Comprehensive test suite catches breaking changes
- **Documentation**: Tests serve as living documentation of system behavior

### The Three Laws of TDD
1. **Write no production code** until you have written a failing unit test
2. **Write only enough of a unit test** sufficient to fail, and not compiling is failing
3. **Write only enough production code** to pass the currently failing test

## Red-Green-Refactor Cycle

### 🔴 RED Phase
Write a **failing test** that defines the desired functionality.

```typescript
// Example: Testing order submission
describe('Order Submission', () => {
  test('should submit market order successfully', async () => {
    const orderService = new OrderService();
    const order = {
      symbol: 'EUR/USD',
      side: 'BUY',
      quantity: 100000,
      type: 'MARKET'
    };

    const result = await orderService.submitOrder(order);

    expect(result.success).toBe(true);
    expect(result.orderId).toBeDefined();
    expect(result.status).toBe('PENDING');
  });
});
```

**Key Points:**
- Test should fail initially (implementation doesn't exist)
- Test should be specific and focused
- Use descriptive test names that explain the behavior
- Include all necessary assertions

### 🟢 GREEN Phase
Write the **minimum code** necessary to make the test pass.

```typescript
// Minimal implementation to pass the test
export class OrderService {
  async submitOrder(order: any): Promise<any> {
    // Minimal implementation
    return {
      success: true,
      orderId: 'test-order-123',
      status: 'PENDING'
    };
  }
}
```

**Key Points:**
- Don't worry about perfect code quality yet
- Write only enough code to pass the test
- Hardcoded values are acceptable at this stage
- Focus on making the test green

### 🔵 REFACTOR Phase
**Improve the code** while keeping tests green.

```typescript
// Refactored implementation
export class OrderService {
  private idGenerator: IdGenerator;
  private validator: OrderValidator;

  constructor(idGenerator: IdGenerator, validator: OrderValidator) {
    this.idGenerator = idGenerator;
    this.validator = validator;
  }

  async submitOrder(order: OrderRequest): Promise<OrderResult> {
    // Validate order
    this.validator.validate(order);

    // Generate unique ID
    const orderId = this.idGenerator.generate();

    // Submit to trading system
    const result: OrderResult = {
      success: true,
      orderId,
      status: OrderStatus.PENDING,
      timestamp: new Date(),
      executionPrice: null
    };

    return result;
  }
}
```

**Key Points:**
- Improve code structure and design
- Add proper types and interfaces
- Extract common functionality
- Maintain passing tests throughout refactoring

## Testing Pyramid

### Unit Tests (70%)
**Fast, isolated tests** for individual components.

```typescript
describe('PriceCalculator', () => {
  test('calculates correct spread', () => {
    const calculator = new PriceCalculator();

    const result = calculator.calculateSpread(1.2050, 1.2048);

    expect(result).toBe(0.0002);
  });
});
```

**Characteristics:**
- Test single functions or methods
- Mock all external dependencies
- Run in milliseconds
- High code coverage (>90%)

### Integration Tests (20%)
**Test interactions** between components.

```typescript
describe('Trading Workflow Integration', () => {
  test('complete order flow from submission to execution', async () => {
    const tradingSystem = new TradingSystem({
      orderService: new OrderService(),
      marketDataService: new MarketDataService(),
      riskService: new RiskService()
    });

    const order = createTestOrder();
    const result = await tradingSystem.processOrder(order);

    expect(result.status).toBe('EXECUTED');
    expect(result.executionPrice).toBeGreaterThan(0);
  });
});
```

**Characteristics:**
- Test component interactions
- Use real implementations where possible
- Test realistic scenarios
- Medium execution time

### End-to-End Tests (10%)
**Full system tests** simulating user workflows.

```typescript
describe('Trading Dashboard E2E', () => {
  test('user can place and monitor order', async () => {
    const { render, user } = setupE2ETest();

    render(<TradingDashboard />);

    // Place order
    await user.selectOption(screen.getByLabelText('Symbol'), 'EUR/USD');
    await user.type(screen.getByLabelText('Quantity'), '100000');
    await user.click(screen.getByText('BUY'));

    // Verify order appears
    await waitFor(() => {
      expect(screen.getByText('Order Submitted')).toBeInTheDocument();
    });
  });
});
```

**Characteristics:**
- Test complete user journeys
- Use real UI components
- Slower execution
- Focus on critical paths

## Test Categories

### 1. Unit Tests
Located in: `tests/unit/`

**Example Structure:**
```
tests/unit/
├── services/
│   ├── OrderService.test.ts
│   ├── PriceService.test.ts
│   └── RiskService.test.ts
├── utils/
│   ├── DateUtils.test.ts
│   └── MathUtils.test.ts
└── components/
    ├── OrderPanel.test.tsx
    └── PriceChart.test.tsx
```

### 2. Integration Tests
Located in: `tests/integration/`

**Example Structure:**
```
tests/integration/
├── trading-workflow.test.ts
├── market-data-flow.test.ts
├── authentication-flow.test.ts
└── frontend-integration.test.tsx
```

### 3. Performance Tests
Located in: `tests/performance/`

**Example Structure:**
```
tests/performance/
├── latency-validation.test.ts
├── comprehensive-load-testing.test.ts
├── performance-dashboard.test.ts
└── memory-usage.test.ts
```

## Best Practices

### Test Structure (AAA Pattern)

```typescript
describe('Component/Function Name', () => {
  test('should do something when condition', () => {
    // 🅰️ ARRANGE - Set up test data and conditions
    const service = new OrderService();
    const order = createTestOrder({ symbol: 'EUR/USD' });

    // 🅰️ ACT - Execute the behavior being tested
    const result = service.validateOrder(order);

    // 🅰️ ASSERT - Verify the expected outcome
    expect(result.isValid).toBe(true);
    expect(result.errors).toHaveLength(0);
  });
});
```

### Descriptive Test Names

```typescript
// ❌ Bad - Vague and unclear
test('order test', () => {});
test('should work', () => {});

// ✅ Good - Clear and descriptive
test('should reject order when quantity exceeds account balance', () => {});
test('should calculate correct commission for EUR/USD trades', () => {});
test('should display error message when API request fails', () => {});
```

### One Assertion Per Concept

```typescript
// ❌ Bad - Multiple unrelated assertions
test('order processing', () => {
  const result = processOrder(order);
  expect(result.success).toBe(true);
  expect(result.timestamp).toBeDefined();
  expect(calculateFee(100)).toBe(2.50); // Unrelated!
});

// ✅ Good - Focused assertions
test('should successfully process valid order', () => {
  const result = processOrder(order);
  expect(result.success).toBe(true);
  expect(result.timestamp).toBeDefined();
});

test('should calculate correct fee for trade amount', () => {
  const fee = calculateFee(100);
  expect(fee).toBe(2.50);
});
```

### Effective Mocking

```typescript
// Mock external dependencies
jest.mock('../../services/TradingAPIService');

describe('OrderService', () => {
  let mockApiService: jest.Mocked<TradingAPIService>;

  beforeEach(() => {
    mockApiService = {
      submitOrder: jest.fn(),
      getOrderStatus: jest.fn(),
      cancelOrder: jest.fn()
    } as any;
  });

  test('should handle API errors gracefully', async () => {
    // Setup mock to simulate error
    mockApiService.submitOrder.mockRejectedValue(
      new Error('API Unavailable')
    );

    const service = new OrderService(mockApiService);
    const result = await service.submitOrder(testOrder);

    expect(result.success).toBe(false);
    expect(result.error).toBe('API Unavailable');
  });
});
```

### Async Testing Patterns

```typescript
// ✅ Use async/await for cleaner tests
test('should handle async operations', async () => {
  const result = await service.fetchData();
  expect(result).toBeDefined();
});

// ✅ Use waitFor for UI updates
test('should display loading state', async () => {
  render(<DataComponent />);

  await waitFor(() => {
    expect(screen.getByText('Loading...')).toBeInTheDocument();
  });
});

// ✅ Wrap state updates in act()
test('should update component state', async () => {
  const { rerender } = render(<Component />);

  await act(async () => {
    fireEvent.click(screen.getByText('Update'));
  });

  expect(screen.getByText('Updated')).toBeInTheDocument();
});
```

## Common Patterns

### Testing React Components

```typescript
describe('TradingPanel', () => {
  test('should display current price', () => {
    const mockData = { symbol: 'EUR/USD', price: 1.2050 };

    render(<TradingPanel marketData={mockData} />);

    expect(screen.getByText('EUR/USD')).toBeInTheDocument();
    expect(screen.getByText('1.2050')).toBeInTheDocument();
  });

  test('should handle user interactions', async () => {
    const onOrderSubmit = jest.fn();
    const user = userEvent.setup();

    render(<TradingPanel onOrderSubmit={onOrderSubmit} />);

    await user.type(screen.getByLabelText('Quantity'), '100000');
    await user.click(screen.getByText('BUY'));

    expect(onOrderSubmit).toHaveBeenCalledWith({
      quantity: 100000,
      side: 'BUY'
    });
  });
});
```

### Testing API Services

```typescript
describe('MarketDataService', () => {
  let service: MarketDataService;

  beforeEach(() => {
    service = new MarketDataService('http://test-api.com');
  });

  test('should fetch current prices', async () => {
    // Mock fetch response
    global.fetch = jest.fn(() =>
      Promise.resolve({
        ok: true,
        json: () => Promise.resolve({
          symbol: 'EUR/USD',
          bid: 1.2048,
          ask: 1.2050
        })
      })
    ) as jest.Mock;

    const result = await service.getCurrentPrice('EUR/USD');

    expect(result.bid).toBe(1.2048);
    expect(result.ask).toBe(1.2050);
  });

  test('should handle API errors', async () => {
    global.fetch = jest.fn(() =>
      Promise.resolve({
        ok: false,
        status: 500,
        statusText: 'Internal Server Error'
      })
    ) as jest.Mock;

    await expect(service.getCurrentPrice('EUR/USD'))
      .rejects.toThrow('API Error: 500');
  });
});
```

### Testing WebSocket Services

```typescript
describe('WebSocketService', () => {
  let mockWebSocket: any;

  beforeEach(() => {
    mockWebSocket = {
      send: jest.fn(),
      close: jest.fn(),
      addEventListener: jest.fn(),
      removeEventListener: jest.fn()
    };

    global.WebSocket = jest.fn(() => mockWebSocket);
  });

  test('should connect and handle messages', () => {
    const onMessage = jest.fn();
    const service = new WebSocketService('ws://test', onMessage);

    service.connect();

    // Simulate message received
    const messageEvent = {
      data: JSON.stringify({ type: 'price', symbol: 'EUR/USD', price: 1.2050 })
    };

    mockWebSocket.onmessage(messageEvent);

    expect(onMessage).toHaveBeenCalledWith({
      type: 'price',
      symbol: 'EUR/USD',
      price: 1.2050
    });
  });
});
```

## Performance Testing

### Latency Testing

```typescript
test('order submission should complete within 10ms', async () => {
  const startTime = performance.now();

  await orderService.submitOrder(testOrder);

  const endTime = performance.now();
  const latency = endTime - startTime;

  expect(latency).toBeLessThan(10);
});
```

### Load Testing

```typescript
test('should handle 1000 concurrent requests', async () => {
  const promises = Array(1000).fill(null).map(() =>
    orderService.submitOrder(createTestOrder())
  );

  const results = await Promise.allSettled(promises);
  const successful = results.filter(r => r.status === 'fulfilled');

  expect(successful.length).toBeGreaterThan(950); // 95% success rate
});
```

### Memory Testing

```typescript
test('should not leak memory during intensive operations', async () => {
  const initialMemory = process.memoryUsage().heapUsed;

  // Perform intensive operations
  for (let i = 0; i < 10000; i++) {
    await processOrder(createTestOrder());
  }

  // Force garbage collection
  if (global.gc) global.gc();

  const finalMemory = process.memoryUsage().heapUsed;
  const memoryIncrease = finalMemory - initialMemory;

  expect(memoryIncrease).toBeLessThan(50 * 1024 * 1024); // Less than 50MB
});
```

## Tools and Setup

### Required Dependencies

```json
{
  "devDependencies": {
    "@testing-library/react": "^13.4.0",
    "@testing-library/jest-dom": "^5.16.5",
    "@testing-library/user-event": "^14.4.3",
    "jest": "^29.3.1",
    "ts-jest": "^29.0.5",
    "@types/jest": "^29.2.5"
  }
}
```

### Jest Configuration

```javascript
module.exports = {
  preset: 'ts-jest',
  testEnvironment: 'jsdom',
  setupFilesAfterEnv: ['<rootDir>/tests/setup.ts'],
  collectCoverageFrom: [
    'src/**/*.{ts,tsx}',
    '!src/**/*.d.ts',
    '!src/**/index.ts'
  ],
  coverageThreshold: {
    global: {
      branches: 80,
      functions: 80,
      lines: 85,
      statements: 85
    }
  }
};
```

### Test Setup File

```typescript
// tests/setup.ts
import '@testing-library/jest-dom';

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

// Performance mock
Object.defineProperty(performance, 'now', {
  value: jest.fn(() => Date.now())
});
```

## Running Tests

```bash
# Run all tests
npm test

# Run with coverage
npm test -- --coverage

# Run specific test files
npm test -- OrderService

# Run in watch mode
npm test -- --watch

# Run performance tests
npm test tests/performance/

# Generate coverage report
npm run test:coverage
```

---

**Remember**: TDD is not just about testing—it's a design methodology that leads to better, more maintainable code. The tests drive the design, not the other way around.
