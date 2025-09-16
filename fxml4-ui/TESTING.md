# FXML4 Frontend Testing Guide

Comprehensive testing infrastructure for the FXML4 trading platform frontend.

## Overview

This testing setup follows Test-After Development (TAD) methodology with comprehensive coverage of:

- **Unit Tests**: Individual functions and components
- **Integration Tests**: API services and WebSocket connections
- **Component Tests**: React components with user interactions
- **Coverage Analysis**: Code coverage reporting and thresholds

## Test Structure

```
src/
├── components/
│   ├── trading/__tests__/
│   │   ├── OrderPanel.test.tsx
│   │   ├── OrdersTable.test.tsx
│   │   ├── PositionsTable.test.tsx
│   │   └── TradingConsole.test.tsx
│   ├── ml/__tests__/
│   │   ├── ModelCard.test.tsx
│   │   └── TrainingStudio.test.tsx
│   └── data/__tests__/
│       ├── SymbolSelector.test.tsx
│       ├── MarketDataGrid.test.tsx
│       └── PriceChart.test.tsx
├── services/__tests__/
│   └── api.integration.test.ts
├── hooks/__tests__/
│   └── useWebSocket.integration.test.ts
└── test-utils/
    ├── setup.ts
    └── render.tsx
```

## Quick Start

### Install Dependencies

```bash
npm install
```

### Run All Tests

```bash
npm run test:all
```

### Run Specific Test Types

```bash
# Unit tests only
npm run test:unit

# Component tests only
npm run test:component

# Integration tests only
npm run test:integration

# Watch mode for development
npm run test:watch

# Coverage analysis
npm run test:coverage
```

## Test Categories

### 1. Component Tests

Tests React components with full user interaction simulation.

**Example: OrderPanel Component**

```typescript
describe('OrderPanel', () => {
  it('should place a market order successfully', async () => {
    mockedApi.post.mockResolvedValueOnce(mockApiSuccess({
      order: { id: 'order-123', status: 'pending' }
    }));

    renderWithStore(<OrderPanel />, {
      marketDataState: { currentPrices: mockMarketData },
      tradingState: { account: mockAccount },
    });

    const orderButton = screen.getByRole('button', { name: /BUY 10000 EURUSD/i });
    await user.click(orderButton);

    await waitFor(() => {
      expect(mockedApi.post).toHaveBeenCalledWith('/trading/orders', {
        symbol: 'EURUSD',
        side: 'buy',
        type: 'market',
        quantity: 10000,
      });
    });
  });
});
```

### 2. Integration Tests

Tests API services and WebSocket connections with mock backends.

**Example: API Service Integration**

```typescript
describe('API Service Integration', () => {
  it('should create a new order', async () => {
    const orderData = {
      symbol: 'EURUSD',
      side: 'buy' as const,
      type: 'market' as const,
      quantity: 10000,
    };

    (fetch as jest.Mock).mockResolvedValueOnce(
      mockResponse({ data: { order: mockOrder } })
    );

    const result = await api.post('/trading/orders', orderData);

    expect(fetch).toHaveBeenCalledWith(
      expect.stringContaining('/trading/orders'),
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify(orderData),
      })
    );
  });
});
```

### 3. WebSocket Integration Tests

Tests real-time data connections and message handling.

**Example: WebSocket Hook Testing**

```typescript
describe('useWebSocket Integration', () => {
  it('should handle market data updates', async () => {
    const { result } = renderHook(() =>
      useWebSocket({
        autoConnect: true,
        subscribeToMarketData: true,
        symbols: ['EURUSD']
      })
    );

    await waitFor(() => {
      expect(result.current.isConnected).toBe(true);
    });

    const marketData = {
      symbol: 'EURUSD',
      bid: 1.08245,
      ask: 1.08248,
      timestamp: '2024-01-15T10:30:00.000Z',
    };

    // Simulate WebSocket message
    act(() => {
      mockWs.simulateMessage({
        type: 'market_data',
        data: marketData,
      });
    });
  });
});
```

## Test Utilities

### Custom Render Functions

Located in `src/test-utils/render.tsx`:

- `renderWithStore()`: Renders components with Zustand store providers
- `renderWithWebSocket()`: Renders with WebSocket connection mocking
- `generateMockOrder()`, `generateMockPosition()`: Mock data generators

### Mock Setup

Located in `src/test-utils/setup.ts`:

- WebSocket mocking
- localStorage/sessionStorage mocking
- Global polyfills for Node.js environment
- Mock data for trading entities

## Coverage Thresholds

Different components have different coverage requirements based on criticality:

```javascript
coverageThreshold: {
  global: {
    branches: 80, functions: 80, lines: 80, statements: 80
  },
  // Critical trading components require higher coverage
  './src/components/trading/': {
    branches: 90, functions: 90, lines: 90, statements: 90
  },
  './src/services/': {
    branches: 85, functions: 85, lines: 85, statements: 85
  }
}
```

## Coverage Reports

Coverage reports are generated in multiple formats:

- **Console**: Summary displayed after test runs
- **HTML**: Interactive report in `coverage/lcov-report/index.html`
- **LCOV**: Machine-readable format for CI/CD integration
- **JSON**: Detailed coverage data for analysis

### Viewing Coverage Reports

```bash
# Generate and view HTML coverage report
npm run test:coverage

# Open HTML report (macOS)
open coverage/lcov-report/index.html

# Open HTML report (Linux)
xdg-open coverage/lcov-report/index.html
```

## CI/CD Integration

### GitHub Actions

```yaml
- name: Run tests with coverage
  run: npm run test:all -- --coverage

- name: Upload coverage reports
  uses: codecov/codecov-action@v3
  with:
    file: ./coverage/lcov.info
```

### Pre-commit Hooks

```json
{
  "husky": {
    "hooks": {
      "pre-commit": "npm run test:unit && npm run lint",
      "pre-push": "npm run test:all"
    }
  }
}
```

## Writing New Tests

### 1. Component Tests

```typescript
import React from 'react';
import { screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { renderWithStore } from '@/test-utils/render';
import YourComponent from '../YourComponent';

describe('YourComponent', () => {
  const user = userEvent.setup();

  beforeEach(() => {
    jest.clearAllMocks();
  });

  it('should render correctly', () => {
    renderWithStore(<YourComponent />);
    expect(screen.getByText('Expected Text')).toBeInTheDocument();
  });

  it('should handle user interactions', async () => {
    renderWithStore(<YourComponent />);
    const button = screen.getByRole('button');
    await user.click(button);
    // Assert expected behavior
  });
});
```

### 2. Integration Tests

```typescript
import { api } from '../yourService';

jest.mock('global.fetch');

describe('Service Integration', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    (fetch as jest.Mock).mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ data: 'test' })
    });
  });

  it('should make API calls correctly', async () => {
    await api.get('/endpoint');
    expect(fetch).toHaveBeenCalledWith(
      expect.stringContaining('/endpoint'),
      expect.any(Object)
    );
  });
});
```

## Best Practices

### 1. Test Organization

- Group related tests using `describe` blocks
- Use descriptive test names that explain expected behavior
- Follow AAA pattern: Arrange, Act, Assert

### 2. Mocking Strategy

- Mock external dependencies (API, WebSocket, localStorage)
- Use real implementations for internal code when possible
- Keep mocks simple and focused on test requirements

### 3. Async Testing

```typescript
// ✅ Good: Use waitFor for async assertions
await waitFor(() => {
  expect(screen.getByText('Loaded Data')).toBeInTheDocument();
});

// ❌ Bad: Don't use arbitrary timeouts
await new Promise(resolve => setTimeout(resolve, 100));
```

### 4. User Interactions

```typescript
// ✅ Good: Use userEvent for realistic interactions
const user = userEvent.setup();
await user.click(button);
await user.type(input, 'text');

// ❌ Bad: Don't use fireEvent for user interactions
fireEvent.click(button);
```

### 5. Component State Testing

```typescript
// ✅ Good: Test behavior, not implementation
expect(screen.getByText('Order placed successfully')).toBeInTheDocument();

// ❌ Bad: Don't test internal state directly
expect(component.state.orderPlaced).toBe(true);
```

## Debugging Tests

### 1. Debug Failing Tests

```bash
# Run single test with verbose output
npm test -- --testNamePattern="specific test name" --verbose

# Run tests in watch mode with coverage
npm run test:watch -- --coverage
```

### 2. Debug Component Rendering

```typescript
import { screen } from '@testing-library/react';

// Print current DOM structure
screen.debug();

// Print specific element
const element = screen.getByTestId('my-element');
console.log(element.outerHTML);
```

### 3. Debug Store State

```typescript
// In tests using renderWithStore
renderWithStore(<Component />, {
  tradingState: { /* mock state */ }
});

// Add logging to see what's happening
console.log('Current store state:', useStore.getState());
```

## Common Issues

### 1. Import Path Issues

```typescript
// ✅ Use absolute imports consistently
import { api } from '@/services/api';
import { OrderPanel } from '@/components/trading';

// ❌ Avoid relative imports in tests
import { api } from '../../../services/api';
```

### 2. Timer and Animation Issues

```typescript
// ✅ Mock timers when testing animations
jest.useFakeTimers();
// ... test code
jest.advanceTimersByTime(1000);
jest.useRealTimers();
```

### 3. WebSocket Testing

```typescript
// ✅ Use proper WebSocket mocking
class MockWebSocket {
  // Complete implementation in test-utils/setup.ts
}
global.WebSocket = MockWebSocket;
```

## Performance Testing

### 1. Large Dataset Testing

```typescript
it('should handle large datasets efficiently', () => {
  const largeDataset = Array.from({ length: 1000 }, (_, i) =>
    generateMockOrder({ id: `order-${i}` })
  );

  renderWithStore(<OrdersTable />, {
    tradingState: { orders: largeDataset }
  });

  // Test should complete within reasonable time
  expect(screen.getByText('Orders (1000)')).toBeInTheDocument();
});
```

### 2. Memory Leak Testing

```typescript
it('should cleanup properly on unmount', () => {
  const { unmount } = renderWithStore(<Component />);

  // Simulate component unmount
  unmount();

  // Verify cleanup (timers, subscriptions, etc.)
  expect(mockCleanupFunction).toHaveBeenCalled();
});
```

## Continuous Integration

The testing setup is designed for CI/CD integration:

- **Fast feedback**: Unit tests run first
- **Parallel execution**: Different test types can run in parallel
- **Failure isolation**: Each test type reports independently
- **Coverage reporting**: Automated coverage analysis and reporting

## Getting Help

### Common Commands Reference

```bash
# Quick test run
npm test

# Full test suite with coverage
npm run test:all -- --coverage

# Component-specific testing
npm run test:coverage -- --component trading

# Pattern-based testing
npm run test:all -- --pattern "should render"

# Skip linting/type-checking in CI
npm run test:all -- --skip-lint --skip-type-check
```

### Debugging Commands

```bash
# Run tests with detailed output
DEBUG=true npm test

# Run tests and keep Jest open for debugging
npm run test:watch -- --no-watchman

# Run tests with coverage and open HTML report
npm run test:coverage && open coverage/lcov-report/index.html
```

This testing infrastructure ensures reliable, maintainable code for the FXML4 trading platform while providing comprehensive coverage and excellent developer experience.
