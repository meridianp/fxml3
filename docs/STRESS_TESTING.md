# FXML4 Stress Testing Framework

## Overview

The FXML4 stress testing framework provides comprehensive performance validation for high-frequency trading operations. It tests system behavior under extreme load conditions, validates performance thresholds, and identifies bottlenecks before they impact production trading.

## Quick Start

### Basic Usage

```bash
# Run light stress tests (CI-friendly)
python3 scripts/test_stress_framework.py

# Run comprehensive stress tests with pytest (requires pytest installation)
pytest tests/stress/ -m stress_light -v

# Run custom stress tests
python3 scripts/run_stress_tests.py --custom --orders 500 --ticks 5000
```

### Test Profiles

- **Light Profile**: Fast tests suitable for CI/CD pipelines
- **Full Profile**: Comprehensive tests for thorough validation
- **Custom Profile**: Configurable tests with specific parameters
- **Benchmark Profile**: Performance baseline measurements

## Test Categories

### 1. Order Submission Stress Tests

Tests the order processing pipeline under high concurrency:

- **Light**: 100 orders with 5 concurrent workers
- **Full**: 1000 orders with 10 concurrent workers
- **Performance Targets**:
  - Latency: <100ms average, <200ms P95
  - Throughput: >100 orders/second
  - Error rate: <1%

### 2. Market Data Processing Stress Tests

Validates market data ingestion at high frequencies:

- **Light**: 1000 ticks at 100/second
- **Full**: 10,000 ticks at 1000/second
- **Performance Targets**:
  - Latency: <10ms average, <20ms P95
  - Throughput: >1000 ticks/second
  - Error rate: <0.1%

### 3. Risk Calculation Stress Tests

Tests risk management under concurrent position calculations:

- **Light**: 100 calculations with 10 positions
- **Full**: 1000 calculations with 50 positions
- **Performance Targets**:
  - Latency: <200ms average, <500ms P95
  - Throughput: >10 calculations/second
  - Error rate: <0.1%

### 4. Signal Generation Stress Tests

Validates ML signal generation pipeline performance:

- **Light**: 10 signals with 2 generators
- **Full**: 100 signals with 5 generators
- **Performance Targets**:
  - Latency: <2000ms average, <5000ms P95
  - Throughput: >1 signal/second
  - Error rate: <1%

## Framework Components

### HighFrequencyStressTester

Main stress testing class that orchestrates all test scenarios:

```python
tester = HighFrequencyStressTester()

# Run order submission stress test
metrics = await tester.stress_test_order_submission(
    num_orders=1000,
    concurrent_workers=10
)
```

### ResourceMonitor

Monitors system resources during stress tests:

```python
monitor = ResourceMonitor()
monitor.start_monitoring(interval=0.1)
# ... run tests ...
resource_metrics = monitor.stop_monitoring()
```

### StressTestMetrics

Performance metrics collected during stress tests:

- `total_operations`: Number of operations executed
- `duration_seconds`: Total test duration
- `operations_per_second`: Throughput measurement
- `avg_latency_ms`: Average operation latency
- `p95_latency_ms`: 95th percentile latency
- `p99_latency_ms`: 99th percentile latency
- `error_rate`: Fraction of failed operations
- `peak_memory_mb`: Peak memory usage
- `peak_cpu_percent`: Peak CPU usage

## Running Stress Tests

### Prerequisites

The stress testing framework is designed to work without external dependencies:

- **Core Requirements**: Python 3.8+, asyncio, psutil
- **Optional Dependencies**: pytest (for full test suite integration)
- **Mock Implementation**: Framework provides mock implementations for missing modules

### Command Line Interface

#### Validation Script

```bash
# Quick validation (no dependencies required)
python3 scripts/test_stress_framework.py
```

#### Comprehensive Runner

```bash
# Light profile (CI-friendly)
python3 scripts/run_stress_tests.py --profile light

# Full profile (comprehensive testing)
python3 scripts/run_stress_tests.py --profile full

# Custom parameters
python3 scripts/run_stress_tests.py --custom \
    --orders 500 \
    --ticks 5000 \
    --concurrent-orders 10 \
    --concurrent-ticks 500

# Generate detailed reports
python3 scripts/run_stress_tests.py --profile full \
    --output stress_report.json \
    --format json

# HTML report generation
python3 scripts/run_stress_tests.py --profile full \
    --output stress_report.html \
    --format html
```

#### Pytest Integration

```bash
# Run with pytest (if available)
pytest tests/stress/ -v

# Specific test categories
pytest tests/stress/ -m stress_light -v
pytest tests/stress/ -m stress_full -v

# With custom configuration
pytest tests/stress/ -c tests/config/pytest_stress.ini -v
```

## Performance Thresholds

### Production Targets

The framework validates against enterprise-grade performance requirements:

| Component | Metric | Target | Critical |
|-----------|--------|---------|----------|
| Order Submission | Avg Latency | <100ms | <200ms |
| Order Submission | P95 Latency | <200ms | <500ms |
| Order Submission | Throughput | >100 ops/sec | >50 ops/sec |
| Market Data | Avg Latency | <10ms | <20ms |
| Market Data | Throughput | >1000 ticks/sec | >500 ticks/sec |
| Risk Calculations | Avg Latency | <200ms | <500ms |
| Signal Generation | Avg Latency | <2000ms | <5000ms |
| System Resources | Memory Usage | <2GB | <4GB |
| System Resources | CPU Usage | <70% | <85% |

### Error Rate Thresholds

- **Critical Operations** (Orders, Risk): <0.1% error rate
- **Data Processing**: <0.1% error rate
- **ML Operations** (Signals): <1% error rate

## Report Generation

### JSON Report Format

```json
{
  "timestamp": "2025-01-19T10:30:00",
  "test_summary": {
    "total_tests": 4,
    "test_names": ["order_submission", "market_data", "risk_calculations", "signal_generation"]
  },
  "results": {
    "order_submission": {
      "total_operations": 1000,
      "duration_seconds": 8.45,
      "operations_per_second": 118.3,
      "avg_latency_ms": 84.2,
      "p95_latency_ms": 156.7,
      "error_rate": 0.002,
      "peak_memory_mb": 245.6,
      "peak_cpu_percent": 68.4
    }
  },
  "performance_analysis": {
    "order_submission": {
      "latency_grade": "A",
      "throughput_grade": "B",
      "error_grade": "A",
      "resource_grade": "A"
    }
  },
  "recommendations": [
    "GOOD: All stress tests passed with acceptable performance!"
  ]
}
```

### HTML Report Features

- **Visual Performance Dashboard**: Grades and color-coded results
- **Detailed Metrics Tables**: Complete performance breakdown
- **Resource Usage Graphs**: Memory and CPU utilization
- **Actionable Recommendations**: Performance improvement suggestions

## Integration with CI/CD

### GitHub Actions Integration

```yaml
- name: Run Stress Tests
  run: |
    python3 scripts/test_stress_framework.py
    pytest tests/stress/ -m stress_light --tb=short
```

### Performance Regression Detection

The framework can detect performance regressions by comparing results against historical baselines:

1. **Automated Baseline Storage**: Store performance metrics in version control
2. **Regression Analysis**: Compare current results against previous runs
3. **Threshold Alerts**: Fail builds if performance degrades beyond acceptable limits

## Best Practices

### Test Environment

- **Dedicated Resources**: Run stress tests on dedicated hardware when possible
- **Consistent Environment**: Use containerized environments for reproducible results
- **Resource Isolation**: Avoid running other intensive processes during stress tests

### Performance Optimization

- **Baseline Measurement**: Establish performance baselines before optimization
- **Incremental Testing**: Test small changes to isolate performance impacts
- **Profiling Integration**: Use profiling tools to identify specific bottlenecks

### Monitoring and Alerting

- **Continuous Monitoring**: Run light stress tests regularly in CI/CD
- **Performance Dashboards**: Track performance trends over time
- **Alert Thresholds**: Set up alerts for performance degradation

## Troubleshooting

### Common Issues

1. **High Memory Usage**
   - **Symptom**: Peak memory >2GB during light tests
   - **Solution**: Check for memory leaks, optimize data structures

2. **High Latency**
   - **Symptom**: Avg latency exceeds thresholds
   - **Solution**: Profile code paths, optimize database queries

3. **Low Throughput**
   - **Symptom**: Operations/second below targets
   - **Solution**: Increase concurrency, optimize bottlenecks

4. **High Error Rates**
   - **Symptom**: Error rate >1% for any component
   - **Solution**: Improve error handling, validate input data

### Debug Mode

Enable detailed logging and debug output:

```bash
# Enable debug logging
export FXML4_LOG_LEVEL=DEBUG
python3 scripts/test_stress_framework.py

# Run with verbose output
pytest tests/stress/ -v -s --tb=long
```

## Architecture

### Mock Implementation Strategy

The framework uses intelligent mocking to simulate production components:

- **Trading Engine**: Simulates order processing with realistic latencies
- **Broker Adapters**: Mock market data feeds and execution latencies
- **Risk Calculator**: Simulates VaR calculations and risk metrics
- **Signal Generator**: Mock ML inference with configurable response times

### Scalability Design

- **Async Architecture**: Full async/await support for concurrent operations
- **Resource Monitoring**: Real-time system resource tracking
- **Configurable Load**: Adjustable parameters for different test scenarios
- **Graceful Degradation**: Handles failures without crashing entire test suite

## Future Enhancements

### Planned Features

1. **Historical Performance Tracking**: Database storage of performance metrics
2. **Performance Regression Analysis**: Automated comparison with baselines
3. **Load Testing UI**: Web interface for configuring and monitoring tests
4. **Production Integration**: Safe performance testing against live systems
5. **ML Performance Testing**: Specialized tests for model inference performance

### Integration Points

- **Kubernetes**: Deploy stress tests in production-like environments
- **Monitoring Stack**: Integration with Prometheus/Grafana for metrics
- **Alert Manager**: Automated performance degradation alerts
- **CI/CD Pipelines**: Advanced integration with deployment workflows

## Conclusion

The FXML4 stress testing framework provides enterprise-grade performance validation for high-frequency trading systems. It ensures system reliability under extreme load conditions and helps maintain performance standards as the system evolves.

For questions or contributions, see the main project documentation and contribution guidelines.
