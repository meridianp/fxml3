# FXML4 Testing Plan & Strategy

<!-- AUTODOC:START file="testing_plan.md" section="overview" generated_by="docs-tdd-bot" -->
## Testing Strategy Overview

**Approach**: Test-Driven Development (TDD) with comprehensive coverage
**Philosophy**: Red → Green → Refactor methodology for all features
**Coverage Target**: 80%+ for production code
**Test Pyramid**: Unit (70%) → Integration (20%) → E2E (10%)
**CI/CD Integration**: All tests must pass before deployment
<!-- AUTODOC:END -->

<!-- AUTODOC:START file="testing_plan.md" section="test_structure" generated_by="docs-tdd-bot" -->
## Test Structure & Organization

### Backend Testing (Python)
```
tests/
├── unit/                    # 85+ isolated unit tests
│   ├── api/                # API endpoint and middleware tests
│   ├── brokers/            # Broker adapter tests
│   ├── data_engineering/   # Database and data processing tests
│   ├── ml/                 # Machine learning model tests
│   ├── strategy/           # Trading strategy tests
│   └── wave_analysis/      # Elliott Wave analysis tests
├── integration/            # 12+ service integration tests
│   ├── test_broker_adapter_ecosystem.py
│   ├── test_ml_pipeline.py
│   ├── test_end_to_end.py
│   └── test_signal_to_execution_flow.py
├── functional/             # 7+ end-to-end workflow tests
├── performance/            # Load and stress testing
└── concurrency/           # 6+ race condition and deadlock tests
```

### Frontend Testing (JavaScript/TypeScript)
```
ftml4-ui/
├── src/components/**/__tests__/    # Component unit tests
├── src/hooks/__tests__/           # Custom hooks tests
├── src/services/__tests__/        # Service integration tests
├── e2e/                          # Playwright E2E tests
│   ├── auth.setup.ts
│   ├── global-setup.ts
│   └── global-teardown.ts
└── src/test/                     # Test utilities and suites
    ├── analytics.integration.test.ts
    └── analytics.test-suite.ts
```
<!-- AUTODOC:END -->

<!-- AUTODOC:START file="testing_plan.md" section="test_categories" generated_by="docs-tdd-bot" -->
## Test Categories & Markers (23 Available)

### Core Test Markers
- `@pytest.mark.unit` - Fast isolated unit tests
- `@pytest.mark.integration` - Service integration tests
- `@pytest.mark.functional` - End-to-end workflow tests
- `@pytest.mark.performance` - Performance benchmarks
- `@pytest.mark.concurrency` - Concurrency and race condition tests

### Dependency-Based Markers
- `@pytest.mark.requires_ib` - Interactive Brokers TWS dependency
- `@pytest.mark.requires_fxcm` - FXCM ForexConnect dependency
- `@pytest.mark.requires_db` - Database dependency
- `@pytest.mark.requires_redis` - Redis cache dependency
- `@pytest.mark.requires_rabbitmq` - RabbitMQ message queue

### Feature-Specific Markers
- `@pytest.mark.security` - Security validation tests
- `@pytest.mark.auth` - Authentication system tests
- `@pytest.mark.ml` - Machine learning tests
- `@pytest.mark.api` - API endpoint tests
- `@pytest.mark.compliance` - Regulatory compliance tests
- `@pytest.mark.stress` - Stress and load tests

### Execution Control Markers
- `@pytest.mark.slow` - Long-running tests (>30s)
- `@pytest.mark.fast` - Quick tests (<5s)
- `@pytest.mark.smoke` - Essential functionality smoke tests
- `@pytest.mark.regression` - Regression prevention tests
- `@pytest.mark.critical` - Business-critical functionality
- `@pytest.mark.experimental` - Experimental feature tests
- `@pytest.mark.skip_ci` - Skip in CI environment
<!-- AUTODOC:END -->

<!-- AUTODOC:START file="testing_plan.md" section="strategy_updates" generated_by="docs-tdd-bot" -->
## TDD Strategy Updates & Lessons Learned

### Recent Strategy Enhancements

#### 1. Dependency-Free Testing Pattern
**Challenge**: Test execution blocked by external dependencies (IB Gateway, FXCM servers)
**Solution**: Implemented dual testing approach:
- **Full Integration Tests**: For complete validation with real services
- **Mock-Based Tests**: For reliable CI/CD execution without external dependencies

**Example Implementation**:
```python
# Full integration test
@pytest.mark.requires_fxcm
def test_fxcm_live_connectivity():
    # Real FXCM connection testing

# Mock-based alternative
@pytest.mark.unit
def test_fxcm_connectivity_simulation():
    # Comprehensive simulation without external dependency
```

#### 2. Progressive Test Complexity
**Approach**: Start simple, evolve to comprehensive
- **Red Phase**: Basic connectivity/functionality tests
- **Green Phase**: Core implementation with minimal viable functionality
- **Refactor Phase**: Enhanced features while maintaining green tests

#### 3. Environment Configuration Testing
**Discovery**: Complex .env configuration often breaks test execution
**Solution**: Implemented test environment isolation:
```python
# Test-specific environment setup
@pytest.fixture(autouse=True)
def test_environment():
    with patch.dict(os.environ, {
        'FXML4_JWT_SECRET_KEY': 'test-secret',
        'FXML4_DATABASE_URL': 'sqlite:///:memory:'
    }):
        yield
```

#### 4. Async Testing Patterns
**Best Practice**: Proper async/await testing for financial data processing
```python
@pytest.mark.asyncio
async def test_real_time_data_processing():
    async with AsyncClient() as client:
        response = await client.websocket_connect("/ws/market-data")
        # Test real-time data flow
```

#### 5. ✅ Infrastructure-First vs. Test-First Development Gap RESOLVED
**Discovery**: Recent monitoring infrastructure was implemented without TDD (infrastructure-first development)
**Impact**: 265,447+ records processed successfully but initially had 0% test coverage
**✅ Solution COMPLETED**: Comprehensive retrospective test coverage implemented:
- **tests/unit/test_infrastructure_health_monitor.py** - 23 test methods, 711 lines
- **tests/unit/test_data_quality_validator.py** - 29 test methods, 762 lines
- **tests/unit/test_automated_data_updates.py** - 28 test methods, 689 lines
- **tests/unit/test_monitoring_dashboard.py** - 37 test methods, 906 lines

**Retrospective test pattern for existing infrastructure:**
```python
# Retrospective test pattern for existing infrastructure
def test_infrastructure_health_monitor_redis_check():
    """Retrospectively test existing Redis health monitoring"""
    monitor = InfrastructureHealthMonitor()

    # Test existing implementation behavior
    with patch('redis.Redis') as mock_redis:
        mock_redis.return_value.ping.return_value = True
        health_status = asyncio.run(monitor.check_redis_health())

    assert health_status.status == "healthy"
    assert health_status.response_time_ms > 0
```

#### 6. Production Validation Pattern
**Challenge**: Infrastructure works in production but lacks test validation
**Solution**: Production behavior testing approach:
```python
@pytest.mark.integration
def test_data_quality_validator_with_real_data():
    """Test data quality validator against known good data"""
    validator = DataQualityValidator()

    # Use actual data structure from production
    quality_report = asyncio.run(validator.validate_symbol("EURUSD", days_back=7))

    # Validate production behavior
    assert quality_report.symbol == "EURUSD"
    assert 0.0 <= quality_report.overall_quality <= 1.0
    assert isinstance(quality_report.gaps, list)
```
<!-- AUTODOC:END -->

<!-- AUTODOC:START file="testing_plan.md" section="tdd_implementation" generated_by="docs-tdd-bot" -->
## TDD Implementation Examples

### Feature Development Cycle

#### Example 1: FXCM Broker Connectivity
**Red**: Initial test creation
```python
def test_fxcm_broker_connection():
    """Test FXCM broker connection establishment"""
    broker = FXCMAdapter()

    # This will fail initially - RED phase
    assert broker.connect() == True
    assert broker.get_connection_status() == "connected"
```

**Green**: Minimal implementation
```python
class FXCMAdapter:
    def connect(self):
        # Minimal implementation to make test pass
        return True

    def get_connection_status(self):
        return "connected"
```

**Refactor**: Enhanced implementation
```python
class FXCMAdapter:
    def __init__(self):
        self.connection = None
        self.status = "disconnected"

    def connect(self):
        # Robust connection logic with error handling
        try:
            self.connection = ForexConnect.create_session()
            self.status = "connected"
            return True
        except Exception as e:
            self.status = f"error: {e}"
            return False

    def get_connection_status(self):
        return self.status
```

#### Example 2: WebSocket Market Data Streaming
**Red**: Comprehensive test requirements
```python
@pytest.mark.asyncio
async def test_websocket_market_data_streaming():
    """Test real-time market data streaming"""
    ws_manager = WebSocketMarketDataManager()

    # Initially failing tests - RED phase
    await ws_manager.start_streaming("EURUSD")

    # Collect some data
    await asyncio.sleep(1)
    data = ws_manager.get_latest_data("EURUSD")

    assert data is not None
    assert "bid" in data
    assert "ask" in data
    assert "timestamp" in data
```

**Green**: Basic streaming implementation
```python
class WebSocketMarketDataManager:
    def __init__(self):
        self.data_cache = {}
        self.connections = {}

    async def start_streaming(self, symbol):
        # Basic WebSocket connection
        self.connections[symbol] = await websockets.connect("ws://api.example.com")
        asyncio.create_task(self._stream_data(symbol))

    async def _stream_data(self, symbol):
        # Simple data collection
        while True:
            data = await self.connections[symbol].recv()
            self.data_cache[symbol] = json.loads(data)
```

**Refactor**: Production-ready implementation with error handling, reconnection logic, and performance optimization
<!-- AUTODOC:END -->

<!-- AUTODOC:START file="testing_plan.md" section="frontend_testing" generated_by="docs-tdd-bot" -->
## Frontend Testing Implementation

### React Component Testing Pattern

#### Component Test Structure
```typescript
// TradingConsole.test.tsx
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { TradingConsole } from '../TradingConsole'

describe('TradingConsole', () => {
  // Given-When-Then pattern
  it('should place order when form is submitted with valid data', async () => {
    // Given: Component is rendered with mock data
    const mockPlaceOrder = jest.fn()
    render(<TradingConsole onPlaceOrder={mockPlaceOrder} />)

    // When: User fills form and submits
    fireEvent.change(screen.getByLabelText(/symbol/i), {
      target: { value: 'EURUSD' }
    })
    fireEvent.change(screen.getByLabelText(/quantity/i), {
      target: { value: '10000' }
    })
    fireEvent.click(screen.getByRole('button', { name: /place order/i }))

    // Then: Order placement function is called with correct parameters
    await waitFor(() => {
      expect(mockPlaceOrder).toHaveBeenCalledWith({
        symbol: 'EURUSD',
        quantity: 10000,
        side: 'buy'
      })
    })
  })
})
```

#### WebSocket Integration Testing
```typescript
// useWebSocket.integration.test.ts
import { renderHook } from '@testing-library/react'
import { useWebSocket } from '../useWebSocket'
import { setupServer } from 'msw/node'
import { ws } from 'msw'

const server = setupServer(
  ws.link('ws://localhost:8000/ws/market-data', ({ client }) => {
    client.addEventListener('message', (event) => {
      client.send(JSON.stringify({
        symbol: 'EURUSD',
        bid: 1.0850,
        ask: 1.0852,
        timestamp: Date.now()
      }))
    })
  })
)

describe('WebSocket Integration', () => {
  beforeAll(() => server.listen())
  afterAll(() => server.close())

  it('should receive real-time market data', async () => {
    const { result } = renderHook(() => useWebSocket('ws://localhost:8000/ws/market-data'))

    // Test WebSocket connection and data reception
    await waitFor(() => {
      expect(result.current.data).toEqual(
        expect.objectContaining({
          symbol: 'EURUSD',
          bid: expect.any(Number),
          ask: expect.any(Number)
        })
      )
    })
  })
})
```

### E2E Testing with Playwright
```typescript
// trading-workflow.spec.ts
import { test, expect } from '@playwright/test'

test('complete trading workflow', async ({ page }) => {
  // Given: User is logged in
  await page.goto('/login')
  await page.fill('[data-testid="email"]', 'trader@example.com')
  await page.fill('[data-testid="password"]', 'password123')
  await page.click('[data-testid="login-button"]')

  // When: User navigates to trading console
  await page.goto('/trading')

  // Then: Trading console is loaded with market data
  await expect(page.locator('[data-testid="market-data-grid"]')).toBeVisible()

  // When: User places an order
  await page.fill('[data-testid="order-symbol"]', 'EURUSD')
  await page.fill('[data-testid="order-quantity"]', '10000')
  await page.click('[data-testid="place-order-button"]')

  // Then: Order appears in orders table
  await expect(page.locator('[data-testid="orders-table"]')).toContainText('EURUSD')
})
```
<!-- AUTODOC:END -->

<!-- AUTODOC:START file="testing_plan.md" section="performance_testing" generated_by="docs-tdd-bot" -->
## Performance Testing Strategy

### Backend Performance Tests
```python
@pytest.mark.performance
def test_market_data_processing_performance():
    """Test market data processing under load"""
    processor = MarketDataProcessor()

    # Generate test data
    test_data = generate_market_data_batch(10000)  # 10k price updates

    start_time = time.time()
    processed_count = 0

    for data_point in test_data:
        processor.process_tick(data_point)
        processed_count += 1

    execution_time = time.time() - start_time

    # Performance assertions
    assert processed_count == 10000
    assert execution_time < 5.0  # Must process 10k ticks in under 5 seconds
    assert processor.get_processing_rate() > 2000  # >2000 ticks/second

@pytest.mark.stress
def test_concurrent_order_processing():
    """Test order processing under concurrent load"""
    order_manager = OrderManager()

    # Simulate 100 concurrent orders
    with ThreadPoolExecutor(max_workers=20) as executor:
        futures = []

        for i in range(100):
            order = create_test_order(f"ORDER_{i}")
            futures.append(executor.submit(order_manager.place_order, order))

        # Wait for all orders to complete
        results = [future.result(timeout=30) for future in futures]

    # All orders should be processed successfully
    assert len([r for r in results if r.status == "filled"]) == 100
```

### Frontend Performance Benchmarks
```typescript
// performance-benchmarks.js
import { measurePerformance } from './test-utils/performance'

describe('Frontend Performance', () => {
  it('should render trading console within performance budget', async () => {
    const metrics = await measurePerformance(async () => {
      render(<TradingConsole />)
    })

    expect(metrics.renderTime).toBeLessThan(16) // 60fps = 16ms budget
    expect(metrics.memoryUsage).toBeLessThan(50 * 1024 * 1024) // 50MB limit
  })

  it('should handle 1000 market data updates without performance degradation', async () => {
    const { rerender } = render(<MarketDataGrid />)

    const updateTimes = []

    for (let i = 0; i < 1000; i++) {
      const startTime = performance.now()
      rerender(<MarketDataGrid data={generateMarketData(i)} />)
      updateTimes.push(performance.now() - startTime)
    }

    // Performance should not degrade over time
    const firstBatch = updateTimes.slice(0, 100)
    const lastBatch = updateTimes.slice(-100)

    const firstBatchAvg = firstBatch.reduce((a, b) => a + b) / firstBatch.length
    const lastBatchAvg = lastBatch.reduce((a, b) => a + b) / lastBatch.length

    expect(lastBatchAvg).toBeLessThan(firstBatchAvg * 1.5) // Max 50% degradation
  })
})
```
<!-- AUTODOC:END -->

<!-- AUTODOC:START file="testing_plan.md" section="ci_cd_integration" generated_by="docs-tdd-bot" -->
## CI/CD Integration & Test Execution

### Test Execution Commands

#### Backend Testing
```bash
# Complete test suite
pytest tests/ -v --tb=short

# Fast tests only (CI pipeline)
pytest tests/ -m "not slow and not requires_ib" -v

# Coverage report generation
pytest --cov=fxml4 --cov-report=xml --cov-report=html

# Specific test categories
pytest -m "unit" -v                    # Unit tests only
pytest -m "integration" -v             # Integration tests
pytest -m "performance" -v             # Performance tests
pytest -m "security" -v                # Security tests
```

#### Frontend Testing
```bash
# Run all tests
npm test

# Coverage report
npm test -- --coverage

# E2E tests
npx playwright test

# Performance benchmarks
npm run test:performance

# Visual regression testing
npm run test:visual
```

### CI Pipeline Configuration
```yaml
# .github/workflows/test.yml
name: Test Suite
on: [push, pull_request]

jobs:
  backend-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.12'

      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install -e .

      - name: Run fast tests
        run: pytest -m "not slow and not requires_ib" --cov=fxml4 --cov-report=xml

      - name: Upload coverage
        uses: codecov/codecov-action@v3
        with:
          file: ./coverage.xml

  frontend-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Setup Node.js
        uses: actions/setup-node@v3
        with:
          node-version: '18'
          cache: 'npm'
          cache-dependency-path: ftml4-ui/package-lock.json

      - name: Install dependencies
        working-directory: ftml4-ui
        run: npm ci

      - name: Run tests
        working-directory: ftml4-ui
        run: npm test -- --coverage --watchAll=false

      - name: E2E tests
        working-directory: ftml4-ui
        run: npx playwright test
```
<!-- AUTODOC:END -->

<!-- AUTODOC:START file="testing_plan.md" section="quality_gates" generated_by="docs-tdd-bot" -->
## Quality Gates & Coverage Requirements

### Coverage Thresholds
- **Overall Coverage**: Minimum 80%
- **New Code Coverage**: Minimum 90%
- **Critical Modules**: Minimum 95%
  - `fxml4.risk_management.*`
  - `fxml4.brokers.adapters.*`
  - `fxml4.api.auth.*`

### Pre-Deployment Checklist
- [ ] All unit tests passing
- [ ] Integration tests passing (where dependencies available)
- [ ] Security tests passing
- [ ] Performance benchmarks within acceptable range
- [ ] Code coverage above thresholds
- [ ] No high-severity security vulnerabilities
- [ ] Frontend E2E tests passing
- [ ] Visual regression tests passing

### Test Failure Response Protocol
1. **Critical Test Failures**: Block deployment immediately
2. **Performance Regressions**: Require investigation before deployment
3. **Coverage Drops**: Require additional tests before merge
4. **Security Test Failures**: Immediate security review required

### Known Testing Challenges
1. **External Dependencies**: Tests requiring IB Gateway/FXCM may be flaky
2. **Async Operations**: Proper timing and cleanup required
3. **Financial Data**: Realistic test data generation complexity
4. **WebSocket Testing**: Connection management and cleanup
<!-- AUTODOC:END -->

---

*Testing plan implemented with comprehensive TDD methodology*
*Continuous refinement based on production requirements and discovered patterns*
