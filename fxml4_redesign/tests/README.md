# FXML4 Microservices Testing Framework

Comprehensive testing infrastructure for the FXML4 redesigned microservices trading system.

## Structure

```
tests/
├── unit/                    # Unit tests for individual services
│   ├── test_base_service.py    # Base service class tests
│   ├── test_data_collector.py  # Data collector service tests
│   ├── test_signal_generator.py # Signal generator tests
│   └── test_llm_analyzer.py     # LLM analyzer tests
├── integration/             # Integration tests
│   ├── test_service_communication.py  # Inter-service messaging
│   └── test_database_operations.py    # Database integration
├── fixtures/                # Test fixtures and utilities
│   ├── database_fixtures.py     # Database test data generators
│   ├── rabbitmq_fixtures.py     # RabbitMQ mocks and helpers
│   └── market_data_fixtures.py  # Market data generators
├── conftest.py             # Pytest configuration and shared fixtures
├── pytest.ini              # Pytest settings
└── run_tests.py           # Test runner script
```

## Quick Start

### Run All Tests
```bash
./run_tests.py all
```

### Run Unit Tests Only
```bash
./run_tests.py unit
```

### Run Specific Service Tests
```bash
./run_tests.py unit --service data_collector
```

### Run Integration Tests
```bash
./run_tests.py integration
```

### Run Specific Test
```bash
./run_tests.py specific --test unit/test_base_service.py::TestBaseService::test_initialization
```

### Run with Coverage
```bash
./run_tests.py coverage
```

## Test Categories

### Unit Tests
- Test individual service components in isolation
- Mock all external dependencies (database, RabbitMQ, Redis, IB Gateway)
- Fast execution (< 1 second per test)
- High coverage of business logic

### Integration Tests
- Test service interactions and data flow
- May use real databases (in test mode)
- Test complete workflows across services
- Performance benchmarks included

### Performance Tests
Run benchmarks with:
```bash
./run_tests.py performance
```

## Key Testing Patterns

### 1. Async Testing
All tests use `pytest-asyncio` for async/await support:
```python
@pytest.mark.asyncio
async def test_async_operation():
    result = await some_async_function()
    assert result == expected
```

### 2. Service Mocking
Services are tested with injected mocks:
```python
@pytest.fixture
def data_collector(mock_db_pool, mock_rabbitmq_connection):
    service = DataCollectorService(config)
    service.db_pool = mock_db_pool
    service.rabbitmq_connection = mock_rabbitmq_connection
    return service
```

### 3. Message Flow Testing
Test inter-service communication:
```python
async def test_message_flow(rabbitmq_harness):
    await rabbitmq_harness.publish('exchange', 'routing.key', message)
    messages = rabbitmq_harness.get_published_messages('exchange')
    assert len(messages) == 1
```

### 4. Database Testing
Test with isolated test database:
```python
async def test_database_operation(test_db):
    async with test_db.acquire() as conn:
        await conn.execute("INSERT INTO ...")
        result = await conn.fetch("SELECT ...")
```

## Fixtures

### Core Fixtures (conftest.py)
- `test_config`: Service configuration for testing
- `mock_db_pool`: Mocked database connection pool
- `mock_rabbitmq_connection`: Mocked RabbitMQ connection
- `mock_redis_client`: Mocked Redis client
- `mock_ib_gateway_client`: Mocked IB Gateway client
- `sample_market_data`: Sample OHLC data
- `sample_tick_data`: Sample tick data
- `sample_indicators`: Sample technical indicators
- `sample_signal`: Sample trading signal
- `sample_trade`: Sample trade data

### Database Fixtures
- `DatabaseFixtures`: Generate test data
- `generate_complete_test_dataset`: Create full test dataset

### RabbitMQ Fixtures
- `RabbitMQTestHarness`: Test message routing
- `MockMessage`, `MockQueue`, `MockExchange`: RabbitMQ mocks
- `create_test_messages`: Generate test messages

### Market Data Fixtures
- `MarketDataGenerator`: Generate realistic market data
- `IndicatorDataGenerator`: Generate technical indicators
- `SignalDataGenerator`: Generate trading signals

## Environment Setup

### Prerequisites
```bash
pip install pytest pytest-asyncio pytest-cov pytest-benchmark
```

### Environment Variables
Set `TESTING=true` to use test configuration:
```bash
export TESTING=true
```

## Test Markers

- `@pytest.mark.unit`: Unit tests
- `@pytest.mark.integration`: Integration tests
- `@pytest.mark.slow`: Slow tests (> 1 second)
- `@pytest.mark.benchmark`: Performance benchmarks
- `@pytest.mark.requires_db`: Requires database
- `@pytest.mark.requires_ib`: Requires IB Gateway

Run tests with specific markers:
```bash
pytest -m "unit and not slow"
pytest -m "integration and requires_db"
```

## Coverage Requirements

- Minimum coverage: 80%
- Target coverage: 90%
- Critical paths: 100%

View coverage report:
```bash
open htmlcov/index.html
```

## Best Practices

1. **Test Isolation**: Each test should be independent
2. **Mock External Services**: Never call real APIs in unit tests
3. **Use Fixtures**: Reuse common test setup via fixtures
4. **Test Edge Cases**: Include error conditions and edge cases
5. **Performance Tests**: Include benchmarks for critical paths
6. **Async Patterns**: Use proper async/await patterns
7. **Clear Names**: Test names should describe what they test
8. **Documentation**: Document complex test scenarios

## Debugging Tests

### Run with verbose output
```bash
pytest -vv -s unit/test_base_service.py
```

### Run with debugger
```python
import pdb; pdb.set_trace()
```

### Check test output
```bash
./run_tests.py specific --test path/to/test.py --verbose
```

## CI/CD Integration

Tests are automatically run in CI/CD pipeline:
- Unit tests on every commit
- Integration tests on PR merge
- Performance tests weekly
- Coverage reports uploaded to coverage service
