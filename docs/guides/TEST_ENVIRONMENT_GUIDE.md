# FXML4 Test Environment Guide

## Overview

This guide describes the comprehensive test environment setup for FXML4, including configuration, execution strategies, and best practices for maintaining reliable and efficient testing.

## Test Environment Architecture

### Components

1. **Test Runners**: Multiple execution modes for different scenarios
2. **Configuration Management**: Centralized, environment-aware configuration
3. **Fixtures & Data Management**: Reusable test components and data
4. **Isolation & Cleanup**: Automated resource management
5. **Performance Monitoring**: Built-in performance testing utilities

### Directory Structure

```
tests/
├── config/
│   ├── test_config.py          # Configuration management
│   └── test_config.yaml        # Default test configuration
├── fixtures/
│   ├── broker_fixtures.py      # Broker adapter test fixtures
│   ├── database_fixtures.py    # Database testing utilities
│   └── test_isolation.py       # Test isolation and cleanup
├── utils/
│   └── performance_utils.py    # Performance testing utilities
├── base/                       # Base test classes
├── unit/                       # Unit tests
├── integration/                # Integration tests
├── functional/                 # End-to-end tests
├── performance/                # Performance tests
├── security/                   # Security tests
└── conftest.py                 # Main pytest configuration
```

## Test Execution Modes

### 1. Basic Test Runner (`run_basic_tests.py`)

Quick development feedback with simple command interface:

```bash
# Fast tests only (no DB, no IB, no slow tests)
python run_basic_tests.py fast

# All unit tests
python run_basic_tests.py unit

# Security tests
python run_basic_tests.py security

# API tests
python run_basic_tests.py api

# Smoke tests (minimal validation)
python run_basic_tests.py smoke
```

### 2. Comprehensive Test Runner (`run_test_suite.py`)

Full-featured test execution with advanced options:

```bash
# Use predefined presets
python run_test_suite.py --preset fast
python run_test_suite.py --preset integration
python run_test_suite.py --preset comprehensive

# Custom marker combinations
python run_test_suite.py --markers "unit and not slow"

# Specific paths
python run_test_suite.py --path tests/unit/

# Performance options
python run_test_suite.py --preset comprehensive --parallel --coverage

# List available presets
python run_test_suite.py --list-presets
```

### 3. Pytest Direct

Standard pytest execution with full control:

```bash
# Basic execution
source venv/bin/activate
source setup_test_env.sh
python -m pytest tests/

# With markers
python -m pytest tests/ -m "not slow and not requires_ib"

# Specific categories
python -m pytest tests/ -m "security"
python -m pytest tests/ -m "unit"
python -m pytest tests/ -m "integration"
```

## Configuration Management

### Environment Variables

The test environment automatically configures these variables:

```bash
FXML4_JWT_SECRET_KEY="test-secret-key"
FXML4_JWT_TOKEN_EXPIRE_MINUTES="60"
FXML4_DB_HOST="localhost"
FXML4_DB_PORT="5433"
FXML4_DB_NAME="fxml4_test"
FXML4_DB_USER="test_user"
FXML4_DB_PASSWORD="test_password"
ALPHA_VANTAGE_API_KEY="test-key"
POLYGON_API_KEY="test-key"
OPENAI_API_KEY="test-key"
ANTHROPIC_API_KEY="test-key"
PYTHONPATH="/path/to/project"
TESTING="1"
```

### Configuration Presets

Available test configurations:

- **fast**: Fast unit tests only, no external dependencies
- **unit**: All unit tests with basic setup
- **integration**: Integration tests with external services
- **performance**: Performance benchmarking tests
- **security**: Security and vulnerability tests
- **comprehensive**: Full test suite excluding IB tests

## Test Markers

The test suite uses 23 different markers for test categorization:

### Core Markers
- `unit`: Unit tests (fast, isolated)
- `integration`: Integration tests (slower, require services)
- `fast`: Fast tests (complete in milliseconds)
- `slow`: Slow tests (may take several seconds)

### Dependency Markers
- `requires_ib`: Tests requiring Interactive Brokers connection
- `requires_db`: Tests requiring database connection
- `requires_api`: Tests requiring API server
- `requires_network`: Tests requiring network access

### Category Markers
- `security`: Security-related tests
- `performance`: Performance and benchmarking tests
- `auth`: Authentication and authorization tests
- `database`: Database-related tests
- `ml`: Machine learning tests
- `wave`: Elliott Wave analysis tests
- `backtesting`: Backtesting framework tests
- `api`: API endpoint tests
- `stress`: Stress tests (high resource usage)

## Fixtures and Data Management

### Database Fixtures

```python
# SQLite test database
def test_with_sqlite(sqlite_test_db):
    conn = sqlite_test_db['connection']
    # Use database

# Populated test database
def test_with_data(populate_test_database):
    # Database pre-loaded with sample data

# Mock async database
async def test_async_db(mock_timescaledb_client):
    await mock_timescaledb_client.store_tick(...)
```

### Broker Fixtures

```python
# Sample orders
def test_orders(sample_market_order, sample_limit_order):
    # Test with realistic order objects

# Execution reports
def test_execution(sample_execution_report, partial_fill_report):
    # Test execution handling

# Mock adapters
def test_ib_adapter(mock_ib_client):
    # Test with mocked Interactive Brokers client
```

### Performance Testing

```python
from tests.utils.performance_utils import benchmark, time_operation

@benchmark(iterations=100, warmup=5)
def test_fast_function():
    # Function will be benchmarked
    return some_operation()

def test_timing():
    with time_operation("my_operation") as timer:
        expensive_operation()

    assert timer.elapsed() < 1.0  # Should complete in < 1s
```

## Test Isolation and Cleanup

### Automatic Isolation

```python
def test_with_isolation(test_isolation):
    # Create temporary resources
    temp_dir = test_isolation.create_temp_directory()
    temp_file = test_isolation.create_temp_file(content="test data")

    # Set environment variables
    test_isolation.set_environment_var("TEST_VAR", "value")

    # Register cleanup
    test_isolation.register_cleanup(lambda: cleanup_resource())

    # All resources automatically cleaned up after test
```

### Memory Monitoring

```python
def test_memory_usage(memory_usage_monitor):
    memory_usage_monitor.measure("start")

    # Perform operations
    large_operation()

    memory_usage_monitor.measure("after_operation")
    summary = memory_usage_monitor.get_summary()

    assert summary['delta_mb'] < 100  # Should use < 100MB
```

## Performance Testing

### Built-in Performance Utilities

```python
from tests.utils.performance_utils import (
    PerformanceAssertions,
    measure_function_performance,
    compare_implementations
)

class TestPerformance:

    def test_function_speed(self):
        """Test function meets performance requirements."""

        @PerformanceAssertions.assert_max_execution_time(1.0)
        def slow_function():
            time.sleep(0.5)
            return "result"

        result = slow_function()  # Asserts completion within 1s

    def test_throughput(self):
        """Test function throughput."""

        @PerformanceAssertions.assert_throughput(min_ops_per_second=100)
        def fast_function():
            return sum(range(1000))

        fast_function()  # Asserts >= 100 ops/second

    def test_memory_limits(self):
        """Test memory usage limits."""

        @PerformanceAssertions.assert_memory_usage(max_delta_mb=50.0)
        def memory_function():
            data = [0] * 1000000  # Allocate some memory
            return len(data)

        memory_function()  # Asserts < 50MB increase
```

### Benchmarking

```python
def test_algorithm_comparison():
    """Compare multiple algorithm implementations."""

    def algorithm_v1(data):
        return sorted(data)

    def algorithm_v2(data):
        return list(data.sort())

    test_data = list(range(10000, 0, -1))

    comparison = compare_implementations(
        algorithm_v1, algorithm_v2,
        iterations=100,
        args=(test_data.copy(),)
    )

    print(f"Fastest: {comparison['fastest']}")
    print(f"Speedup: {comparison['speedup']:.2f}x")
```

## Environment-Specific Configuration

### CI/CD Environment

```yaml
# tests/config/test_config.yaml
environments:
  ci:
    parallel_workers: 2
    test_timeout: 600
    coverage_threshold: 70.0
    disable_external_apis: true
    skip_integration: true
```

### Local Development

```yaml
environments:
  local:
    debug_mode: true
    log_level: "DEBUG"
    parallel_workers: 4
    test_timeout: 300
```

## Best Practices

### 1. Test Organization

- Use appropriate markers for test categorization
- Place tests in correct directories based on type
- Use descriptive test names that explain what is being tested

### 2. Test Data Management

- Use fixtures for reusable test data
- Keep test data small and focused
- Clean up test data automatically

### 3. Mock External Dependencies

- Mock external API calls by default
- Use `disable_external_apis: true` in test config
- Only enable real external calls in integration tests

### 4. Performance Considerations

- Mark slow tests with `@pytest.mark.slow`
- Use performance assertions for critical code paths
- Monitor memory usage in resource-intensive tests

### 5. Test Isolation

- Ensure tests don't depend on each other
- Use database transactions that roll back
- Clean up temporary files and directories

### 6. Error Handling

- Test both success and failure scenarios
- Use appropriate assertions for different error types
- Verify error messages and codes

## Troubleshooting

### Common Issues

1. **Import Errors**: Ensure virtual environment is activated and PYTHONPATH is set
2. **Database Connection**: Check that test database is running and accessible
3. **Permission Errors**: Ensure test has write access to temporary directories
4. **Timeout Issues**: Increase test timeout or optimize slow operations
5. **Memory Leaks**: Use memory monitoring to identify resource leaks

### Debug Mode

Enable debug mode for verbose output:

```bash
export FXML4_LOG_LEVEL="DEBUG"
python run_test_suite.py --preset unit
```

### Performance Issues

Monitor performance with built-in utilities:

```python
def test_with_monitoring(performance_timer, memory_monitor):
    performance_timer.start()
    memory_monitor.start()

    # Perform operations
    result = expensive_operation()

    # Check metrics
    elapsed = performance_timer.stop()
    memory_summary = memory_monitor.get_summary()

    print(f"Elapsed: {elapsed:.3f}s")
    print(f"Memory delta: {memory_summary['delta_mb']:.1f}MB")
```

## Integration with Development Workflow

### Pre-commit Testing

```bash
# Quick validation before commit
python run_basic_tests.py smoke
```

### Development Testing

```bash
# Test specific module during development
python run_test_suite.py --path tests/unit/brokers/
```

### CI/CD Pipeline

```bash
# Comprehensive testing for CI/CD
python run_test_suite.py --preset comprehensive --parallel --coverage
```

### Performance Monitoring

```bash
# Regular performance benchmarking
python run_test_suite.py --preset performance
```

## Configuration Reference

See `tests/config/test_config.yaml` for complete configuration options and `tests/config/test_config.py` for programmatic configuration management.

The test environment provides a robust, scalable foundation for maintaining high code quality and reliable test execution across different development scenarios.
