# FXML4 Comprehensive Testing Guide

## Table of Contents
1. [Overview](#overview)
2. [Test Categories](#test-categories)
3. [Running Tests](#running-tests)
4. [Writing Tests](#writing-tests)
5. [Test Frameworks](#test-frameworks)
6. [CI/CD Integration](#cicd-integration)
7. [Performance Testing](#performance-testing)
8. [Troubleshooting](#troubleshooting)

## Overview

FXML4 employs a comprehensive Test-Driven Development (TDD) approach with multiple testing layers ensuring robust, production-ready forex trading capabilities. Our testing philosophy follows the "Test Pyramid" pattern with extensive unit tests, integration tests, and end-to-end tests.

### Testing Philosophy
- **Red-Green-Refactor**: Write failing tests first, implement code to pass, then refactor
- **Coverage Target**: Minimum 85% for core modules, 60% overall
- **Performance Standards**: Sub-second response times for real-time operations
- **Security-First**: All authentication and financial operations have dedicated security tests

## Test Categories

FXML4 uses 23 different test markers to organize and run specific test suites:

### Core Test Categories

#### Unit Tests (`@pytest.mark.unit`)
Fast, isolated tests for individual functions and classes.
```bash
pytest -m unit
```

#### Integration Tests (`@pytest.mark.integration`)
Tests verifying component interactions and data flow.
```bash
pytest -m integration
```

#### API Tests (`@pytest.mark.api`)
Comprehensive API endpoint testing with contract validation.
```bash
pytest -m api
```

#### End-to-End Tests (`@pytest.mark.e2e`)
Complete workflow testing from user action to database update.
```bash
pytest -m e2e
```

### Specialized Test Categories

#### Security Tests (`@pytest.mark.security`)
- JWT authentication validation
- Authorization checks
- Input sanitization
- SQL injection prevention
- XSS protection

```bash
pytest -m security
```

#### Performance Tests (`@pytest.mark.performance`)
- Load testing with concurrent users
- Stress testing for market volatility
- Latency benchmarking
- Memory leak detection

```bash
pytest -m performance
```

#### Machine Learning Tests (`@pytest.mark.ml`)
- Model training validation
- Prediction accuracy tests
- Feature engineering verification
- Hyperparameter optimization tests

```bash
pytest -m ml
```

#### Trading Strategy Tests (`@pytest.mark.strategy`)
- Signal generation accuracy
- Risk management validation
- Position sizing tests
- Stop-loss/take-profit logic

```bash
pytest -m strategy
```

#### Compliance Tests (`@pytest.mark.compliance`)
- Regulatory reporting accuracy
- Audit trail completeness
- Risk limit enforcement
- Trade surveillance checks

```bash
pytest -m compliance
```

### External Dependency Markers

#### Interactive Brokers (`@pytest.mark.requires_ib`)
Tests requiring IB Gateway connection.
```bash
pytest -m "not requires_ib"  # Skip IB tests
```

#### FXCM (`@pytest.mark.requires_fxcm`)
Tests requiring FXCM API access.
```bash
pytest -m "not requires_fxcm"  # Skip FXCM tests
```

#### Database (`@pytest.mark.requires_db`)
Tests requiring TimescaleDB connection.
```bash
pytest -m "not requires_db"  # Skip database tests
```

## Running Tests

### Quick Start

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=fxml4 --cov-report=html

# Run fast tests only (no external dependencies)
pytest -m "not slow and not requires_ib and not requires_fxcm"

# Run with parallel execution (optimized)
pytest -n auto --dist loadscope

# Run specific test file
pytest tests/unit/test_risk_management.py

# Run with verbose output
pytest -xvs
```

### Advanced Test Runners

#### Comprehensive Test Suite
```bash
python scripts/run_enhanced_test_suite.py

Options:
  --category [unit|integration|api|ml|security|performance]
  --coverage-threshold 85
  --parallel
  --report-format [html|json|xml]
```

#### API Testing Suite
```bash
python tests/run_api_tests.py all

Commands:
  discovery     - Discover all API endpoints
  contracts     - Validate endpoint contracts
  security      - Security vulnerability testing
  comprehensive - Full multi-phase testing
```

#### Performance Benchmarking
```bash
python scripts/run_performance_benchmarks.py run

Commands:
  run           - Run benchmarks once
  continuous    - Run continuously at interval
  targeted      - Run specific category
  trends        - Analyze historical trends
  update-baselines - Update performance baselines
```

#### Mutation Testing
```bash
python scripts/run_mutation_tests.py --quick

Options:
  --quick       - Run quick validation
  --source      - Source directories to test
  --file        - Specific file to test
  --output      - Report output file
```

#### Visual Regression Testing
```bash
python scripts/run_visual_tests.py capture

Commands:
  capture       - Capture baseline screenshots
  compare       - Compare against baselines
  update        - Update baselines
  report        - Generate HTML report
```

### Test Configuration

#### pytest.ini
```ini
[tool:pytest]
minversion = 6.0
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*
addopts =
    -ra
    --strict-markers
    --ignore=tests/fixtures
    --ignore=tests/data
markers =
    unit: Unit tests
    integration: Integration tests
    api: API tests
    slow: Slow running tests
    requires_ib: Requires Interactive Brokers
    requires_fxcm: Requires FXCM
    requires_db: Requires database
```

#### Coverage Configuration
```ini
[coverage:run]
source = fxml4
omit =
    */tests/*
    */test_*.py
    */__pycache__/*
    */migrations/*

[coverage:report]
precision = 2
show_missing = True
skip_covered = False
fail_under = 60
```

## Writing Tests

### TDD Best Practices

#### 1. Red Phase - Write Failing Test
```python
def test_calculate_position_size():
    """Test position size calculation with 2% risk."""
    # Given
    account_balance = 10000
    risk_percent = 2
    stop_loss_pips = 50

    # When
    position_size = calculate_position_size(
        account_balance, risk_percent, stop_loss_pips
    )

    # Then
    assert position_size == 4000  # Will fail initially
```

#### 2. Green Phase - Implement Minimal Code
```python
def calculate_position_size(balance, risk_pct, sl_pips):
    """Calculate position size based on risk parameters."""
    risk_amount = balance * (risk_pct / 100)
    position_size = (risk_amount / sl_pips) * 10000
    return position_size
```

#### 3. Refactor Phase - Improve Implementation
```python
def calculate_position_size(
    balance: float,
    risk_pct: float,
    sl_pips: int,
    leverage: float = 1.0,
    pip_value: float = 10.0
) -> float:
    """
    Calculate position size based on risk management rules.

    Args:
        balance: Account balance in base currency
        risk_pct: Risk percentage per trade (e.g., 2 for 2%)
        sl_pips: Stop loss distance in pips
        leverage: Account leverage (default 1.0)
        pip_value: Value per pip (default 10.0 for standard lot)

    Returns:
        Position size in units
    """
    if balance <= 0 or risk_pct <= 0 or sl_pips <= 0:
        return 0.0

    risk_amount = balance * (risk_pct / 100)
    position_size = (risk_amount / (sl_pips * pip_value)) * 100000

    # Apply leverage
    position_size *= leverage

    # Ensure position doesn't exceed balance
    max_position = balance * leverage
    return min(position_size, max_position)
```

### Test Structure Patterns

#### Given-When-Then Pattern
```python
def test_signal_generation_with_confluence():
    """Test signal generation with multiple confirmations."""
    # Given - Setup test data and conditions
    market_data = create_test_market_data(
        symbol="EURUSD",
        trend="bullish",
        volatility="low"
    )
    indicators = {
        "rsi": 45,
        "macd": {"signal": "buy", "strength": 0.8},
        "ema_cross": True
    }

    # When - Execute the action being tested
    signal = generate_trading_signal(market_data, indicators)

    # Then - Assert expected outcomes
    assert signal.direction == SignalDirection.BUY
    assert signal.confidence >= 0.7
    assert signal.risk_reward_ratio >= 2.0
```

#### Arrange-Act-Assert (AAA) Pattern
```python
def test_order_execution_with_slippage():
    """Test order execution handling slippage."""
    # Arrange
    order = create_market_order(
        symbol="GBPUSD",
        volume=100000,
        side="BUY"
    )
    market_conditions = {"spread": 2, "volatility": "high"}

    # Act
    execution = execute_order(order, market_conditions)

    # Assert
    assert execution.status == "FILLED"
    assert execution.slippage_pips <= 3
    assert execution.fill_price != order.expected_price
```

### Fixtures and Test Data

#### Pytest Fixtures
```python
@pytest.fixture
def market_data_feed():
    """Provide mock market data feed."""
    return MockMarketDataFeed(
        symbols=["EURUSD", "GBPUSD", "USDJPY"],
        update_frequency=1.0
    )

@pytest.fixture
def authenticated_client():
    """Provide authenticated API client."""
    client = TestClient(app)
    token = generate_test_jwt_token(user_id=1, role="trader")
    client.headers["Authorization"] = f"Bearer {token}"
    return client

@pytest.fixture(scope="session")
def test_database():
    """Provide test database connection."""
    db = create_test_database()
    yield db
    db.cleanup()
```

#### Test Data Factories
```python
class OrderFactory:
    """Factory for creating test orders."""

    @staticmethod
    def create_market_order(**kwargs):
        defaults = {
            "symbol": "EURUSD",
            "volume": 100000,
            "side": "BUY",
            "order_type": "MARKET",
            "timestamp": datetime.now()
        }
        defaults.update(kwargs)
        return Order(**defaults)

    @staticmethod
    def create_limit_order(**kwargs):
        defaults = {
            "symbol": "GBPUSD",
            "volume": 50000,
            "side": "SELL",
            "order_type": "LIMIT",
            "limit_price": 1.2500,
            "timestamp": datetime.now()
        }
        defaults.update(kwargs)
        return Order(**defaults)
```

### Mocking External Dependencies

#### Mock Broker Connections
```python
@pytest.fixture
def mock_ib_client():
    """Mock Interactive Brokers client."""
    with patch('fxml4.brokers.ib_adapter.IBClient') as mock:
        client = mock.return_value
        client.connect.return_value = True
        client.get_positions.return_value = []
        client.place_order.return_value = {"order_id": "123"}
        yield client

def test_order_placement_with_ib(mock_ib_client):
    """Test order placement through IB."""
    order = create_test_order()
    result = place_order_with_broker(order, broker="IB")

    assert result["status"] == "submitted"
    mock_ib_client.place_order.assert_called_once()
```

#### Mock External APIs
```python
@responses.activate
def test_market_data_fetch():
    """Test fetching market data from external API."""
    responses.add(
        responses.GET,
        "https://api.polygon.io/v2/aggs/ticker/X:EURUSD",
        json={"results": [{"c": 1.1850, "h": 1.1875, "l": 1.1825}]},
        status=200
    )

    data = fetch_market_data("EURUSD")
    assert data["close"] == 1.1850
```

## Test Frameworks

### Property-Based Testing (Hypothesis)

```python
from hypothesis import given, strategies as st

@given(
    balance=st.floats(min_value=1000, max_value=1000000),
    risk_pct=st.floats(min_value=0.1, max_value=5.0),
    sl_pips=st.integers(min_value=10, max_value=200)
)
def test_position_size_properties(balance, risk_pct, sl_pips):
    """Test position size calculation properties."""
    position_size = calculate_position_size(balance, risk_pct, sl_pips)

    # Properties that should always hold
    assert position_size >= 0
    assert position_size <= balance * 100  # Max leverage

    # Risk should not exceed specified percentage
    potential_loss = (position_size / 100000) * sl_pips * 10
    assert potential_loss <= balance * (risk_pct / 100) * 1.01  # 1% tolerance
```

### Stress Testing

```python
async def test_high_frequency_order_submission():
    """Test system under high-frequency trading load."""
    stress_tester = StressTester()

    metrics = await stress_tester.stress_test_order_submission(
        num_orders=10000,
        concurrent_workers=50,
        duration_seconds=60
    )

    assert metrics.success_rate >= 0.99
    assert metrics.p95_latency_ms <= 100
    assert metrics.orders_per_second >= 100
    assert metrics.cpu_usage_percent <= 80
    assert metrics.memory_usage_mb <= 4000
```

### API Contract Testing

```python
def test_api_contract_validation():
    """Test API endpoint contract compliance."""
    tester = APIContractTester()

    # Test all endpoints
    results = tester.validate_all_endpoints()

    assert results.total_endpoints >= 145
    assert results.validation_errors == 0
    assert results.schema_violations == 0
    assert results.deprecated_endpoints == 0
```

### Mutation Testing

```python
def test_mutation_testing_quality():
    """Validate test suite quality with mutation testing."""
    mutator = MutationTester(["fxml4/core"])

    score = mutator.run_mutation_testing()

    assert score.mutation_score >= 70  # 70% of mutations killed
    assert score.survived_mutants < 100

    # Check specific mutation types
    assert score.arithmetic_killed_rate >= 0.8
    assert score.conditional_killed_rate >= 0.7
```

### Visual Regression Testing

```python
def test_dashboard_visual_regression():
    """Test dashboard UI for visual regressions."""
    tester = VisualRegressionTester()

    result = tester.compare_screenshot(
        "dashboard_main",
        threshold=0.99,  # 99% similarity required
        ignore_regions=[(0, 0, 200, 50)]  # Ignore timestamp area
    )

    assert result.similarity >= 0.99
    assert result.different_pixels < 1000
```

## CI/CD Integration

### GitHub Actions Workflow

```yaml
name: Comprehensive Testing

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest

    steps:
    - uses: actions/checkout@v3

    - name: Setup Python
      uses: actions/setup-python@v4
      with:
        python-version: '3.11'

    - name: Install dependencies
      run: |
        pip install -r requirements-dev.txt
        pip install -e .

    - name: Run unit tests
      run: pytest -m unit --cov=fxml4

    - name: Run integration tests
      run: pytest -m integration

    - name: Run security tests
      run: pytest -m security

    - name: Check coverage
      run: pytest --cov=fxml4 --cov-fail-under=60

    - name: Run mutation testing
      run: python scripts/run_mutation_tests.py --quick

    - name: Performance benchmarks
      run: python scripts/run_performance_benchmarks.py run

    - name: Upload coverage
      uses: codecov/codecov-action@v3
```

### Pre-commit Hooks

```yaml
# .pre-commit-config.yaml
repos:
  - repo: https://github.com/psf/black
    rev: 23.3.0
    hooks:
      - id: black
        language_version: python3.11

  - repo: https://github.com/pycqa/isort
    rev: 5.12.0
    hooks:
      - id: isort

  - repo: https://github.com/pycqa/flake8
    rev: 6.0.0
    hooks:
      - id: flake8

  - repo: local
    hooks:
      - id: pytest-unit
        name: pytest unit tests
        entry: pytest -m unit
        language: system
        pass_filenames: false
        always_run: true
```

## Performance Testing

### Load Testing Configuration

```python
# tests/performance/load_config.py
LOAD_TEST_CONFIG = {
    "scenarios": {
        "normal_trading": {
            "users": 100,
            "spawn_rate": 10,
            "duration": 300,
            "endpoints": [
                {"path": "/api/v1/market/data", "weight": 40},
                {"path": "/api/v1/signals", "weight": 30},
                {"path": "/api/v1/orders", "weight": 20},
                {"path": "/api/v1/positions", "weight": 10}
            ]
        },
        "market_volatility": {
            "users": 500,
            "spawn_rate": 50,
            "duration": 600,
            "endpoints": [
                {"path": "/api/v1/market/data", "weight": 60},
                {"path": "/api/v1/risk/calculate", "weight": 40}
            ]
        }
    }
}
```

### Performance Benchmarks

```python
def run_performance_benchmarks():
    """Run comprehensive performance benchmarks."""
    benchmarker = PerformanceBenchmarker()

    # API Latency Benchmarks
    api_results = benchmarker.benchmark_api_endpoints()
    assert_performance_thresholds(api_results, {
        "p50": 50,   # 50ms median
        "p95": 500,  # 500ms 95th percentile
        "p99": 2000  # 2s 99th percentile
    })

    # Database Query Benchmarks
    db_results = benchmarker.benchmark_database_queries()
    assert_performance_thresholds(db_results, {
        "select_simple": 10,
        "select_complex": 100,
        "insert_batch": 500
    })

    # ML Inference Benchmarks
    ml_results = benchmarker.benchmark_ml_inference()
    assert_performance_thresholds(ml_results, {
        "single_prediction": 100,
        "batch_prediction": 1000
    })
```

## Troubleshooting

### Common Issues and Solutions

#### 1. Import Errors
```bash
# Issue: ModuleNotFoundError: No module named 'fxml4'
# Solution:
pip install -e .
export PYTHONPATH="${PYTHONPATH}:$(pwd)"
```

#### 2. Database Connection Failures
```bash
# Issue: could not connect to server: Connection refused
# Solution:
docker-compose up -d timescaledb
# Wait for database to be ready
python scripts/wait_for_db.py
```

#### 3. Slow Test Execution
```bash
# Issue: Tests taking too long
# Solution: Use parallel execution
pytest -n auto --dist loadscope

# Skip slow tests
pytest -m "not slow"

# Run only specific test categories
pytest -m unit
```

#### 4. Flaky Tests
```python
# Use retry decorator for flaky tests
@pytest.mark.flaky(reruns=3, reruns_delay=2)
def test_external_api_call():
    """Test that may fail due to network issues."""
    response = call_external_api()
    assert response.status_code == 200
```

#### 5. Memory Issues
```bash
# Issue: Tests consuming too much memory
# Solution: Run tests in smaller batches
pytest tests/unit --maxfail=1
pytest tests/integration --maxfail=1

# Use memory profiling
pytest --memprof tests/performance
```

### Debugging Tests

#### Using pytest debugger
```bash
# Drop into debugger on failure
pytest --pdb

# Drop into debugger at specific point
def test_complex_logic():
    import pdb; pdb.set_trace()
    result = complex_calculation()
    assert result == expected
```

#### Verbose Output
```bash
# Show all test output
pytest -vvs

# Show local variables on failure
pytest -l

# Show test execution times
pytest --durations=10
```

#### Test Isolation
```python
# Ensure test isolation
@pytest.fixture(autouse=True)
def reset_database():
    """Reset database before each test."""
    yield
    cleanup_test_data()

@pytest.fixture(autouse=True)
def clear_cache():
    """Clear caches before each test."""
    cache.clear()
    yield
```

## Test Metrics and Reporting

### Coverage Reports
```bash
# Generate HTML coverage report
pytest --cov=fxml4 --cov-report=html
# Open htmlcov/index.html in browser

# Generate XML for CI integration
pytest --cov=fxml4 --cov-report=xml

# Console report with missing lines
pytest --cov=fxml4 --cov-report=term-missing
```

### Test Result Formats
```bash
# JUnit XML for CI systems
pytest --junit-xml=test-results.xml

# JSON report
pytest --json-report --json-report-file=report.json

# HTML report with charts
pytest --html=report.html --self-contained-html
```

### Performance Metrics
```python
# Track test execution times
pytest --benchmark-only
pytest --benchmark-histogram

# Memory usage tracking
pytest --memprof --memprof-top=10

# Profile test execution
pytest --profile --profile-svg
```

## Best Practices Summary

1. **Write Tests First**: Always follow TDD - Red, Green, Refactor
2. **Keep Tests Fast**: Unit tests should run in milliseconds
3. **Test One Thing**: Each test should verify a single behavior
4. **Use Descriptive Names**: Test names should explain what they test
5. **Avoid Test Interdependence**: Tests should run independently
6. **Mock External Dependencies**: Don't rely on external services
7. **Use Fixtures**: Share setup code via pytest fixtures
8. **Test Edge Cases**: Include boundary conditions and error cases
9. **Maintain Test Data**: Use factories for consistent test data
10. **Regular Cleanup**: Remove obsolete tests and update as code changes

## Additional Resources

- [Pytest Documentation](https://docs.pytest.org/)
- [Hypothesis Documentation](https://hypothesis.readthedocs.io/)
- [Coverage.py Documentation](https://coverage.readthedocs.io/)
- [FXML4 TDD Specification](./TDD_SPECIFICATION.md)
- [API Testing Guide](./API_TESTING.md)
- [Performance Testing Guide](./PERFORMANCE_TESTING.md)
