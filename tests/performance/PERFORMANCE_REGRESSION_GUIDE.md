# Performance Regression Testing Guide

## Overview

The FXML4 Performance Regression Testing Suite is a comprehensive framework that monitors system performance over time, detects performance regressions, and ensures that performance targets are consistently met.

## Architecture

### Key Components

```
Performance Regression Testing Framework
├── Baseline Management System
│   ├── Baseline Storage (JSON files)
│   ├── Historical Tracking
│   └── Environment-Specific Baselines
├── Regression Detection Engine
│   ├── Statistical Analysis
│   ├── Threshold-Based Alerts
│   └── Trend Analysis
├── Comprehensive Test Coverage
│   ├── API Endpoint Performance
│   ├── Database Query Performance
│   ├── ML Inference Performance
│   └── Concurrent Load Testing
└── CI/CD Integration
    ├── Automated Baseline Updates
    ├── Pipeline Integration
    └── Performance Reports
```

### Performance Targets (SLA)

| Component | Metric | Target (95th percentile) | Critical Threshold |
|-----------|--------|-------------------------|-------------------|
| Health Endpoint | Response Time | < 50ms | 100ms |
| Data Endpoints | Response Time | < 500ms | 1000ms |
| Signal Generation | Response Time | < 2s | 5s |
| Database Queries | Response Time | < 100ms | 500ms |
| ML Inference | Response Time | < 200ms | 1s |
| Concurrent Load | Throughput | > 50 RPS | 25 RPS |

## Getting Started

### Prerequisites

1. **Python 3.12+** with required packages
2. **FXML4 API** running and accessible
3. **Database** (TimescaleDB) available
4. **Virtual environment** activated

### Quick Start

```bash
# Initialize performance baselines (first time only)
make test-performance-baseline

# Run performance regression tests
make test-performance

# Generate performance reports
make test-performance-report

# Clean test artifacts
make test-performance-clean
```

### Advanced Usage

```bash
# Initialize baselines with specific configuration
./scripts/run_performance_regression_tests.sh baseline \
  --api-url http://localhost:8001 \
  --environment production \
  --force-baseline

# Run tests with custom thresholds
./scripts/run_performance_regression_tests.sh test \
  --threshold 15 \
  --samples 30 \
  --environment staging

# Generate reports only
./scripts/run_performance_regression_tests.sh report \
  --output-dir custom-reports
```

## Test Categories

### 1. API Endpoint Performance

Tests critical API endpoints for response time and reliability.

**Endpoints Tested:**
- `/health` - System health check
- `/api/data/symbols` - Market data retrieval
- `/api/signals/generate` - Trading signal generation

**Metrics Captured:**
- P95 response time
- Mean response time
- Maximum response time
- Success rate
- Memory usage
- CPU utilization

```python
@pytest.mark.asyncio
@pytest.mark.performance
async def test_api_endpoint_performance_regression(self):
    """Test API endpoint performance regression."""
    # Measures response times for critical endpoints
    # Compares against established baselines
    # Fails if performance degrades beyond threshold
```

### 2. Database Performance

Validates database query performance and connection efficiency.

**Tests Include:**
- Complex market data queries
- Time-series data retrieval
- Aggregation queries
- Connection pool efficiency

**Metrics Captured:**
- Query execution time
- Connection establishment time
- Result set processing time
- Resource utilization

```python
@pytest.mark.asyncio
@pytest.mark.performance
async def test_database_performance_regression(self):
    """Test database query performance regression."""
    # Simulates real database operations
    # Measures query performance
    # Validates SLA compliance
```

### 3. ML Inference Performance

Tests machine learning model inference performance.

**Coverage:**
- Signal generation models
- Feature engineering pipeline
- Model loading and caching
- Batch vs. single predictions

**Metrics:**
- Inference latency
- Throughput (predictions/second)
- Memory consumption
- Model loading time

```python
@pytest.mark.asyncio
@pytest.mark.performance
async def test_ml_inference_performance_regression(self):
    """Test ML model inference performance regression."""
    # Tests real ML inference via API
    # Measures end-to-end latency
    # Validates inference SLA
```

### 4. Concurrent Load Testing

Validates system performance under concurrent load.

**Test Scenarios:**
- Multiple concurrent users
- Concurrent API requests
- Resource contention testing
- Scalability validation

**Metrics:**
- Throughput (requests/second)
- Response time under load
- Error rate
- Resource utilization

```python
@pytest.mark.asyncio
@pytest.mark.performance
async def test_concurrent_load_performance_regression(self):
    """Test system performance under concurrent load."""
    # Simulates multiple concurrent users
    # Measures throughput and latency
    # Validates scalability requirements
```

## Baseline Management

### Baseline Structure

```json
{
  "test_name": "api_endpoint_performance",
  "timestamp": "2025-01-19T10:30:00",
  "git_commit": "abc123def",
  "environment": "production",
  "metrics": {
    "p95_response_time_ms": 45.2,
    "mean_response_time_ms": 23.8,
    "max_response_time_ms": 156.7,
    "success_rate": 100.0
  },
  "metadata": {
    "samples": 20,
    "api_url": "http://localhost:8001",
    "python_version": "3.12.1"
  }
}
```

### Baseline Operations

```bash
# List existing baselines
python scripts/initialize_performance_baselines.py --list

# Create new baselines
python scripts/initialize_performance_baselines.py --force

# Environment-specific baselines
python scripts/initialize_performance_baselines.py --environment production
```

### Baseline Storage

- **Location**: `tests/performance/baselines/`
- **Format**: JSON files named by test
- **Versioning**: Git-tracked for history
- **Environment**: Separate baselines per environment

## Regression Detection

### Statistical Analysis

The regression detection engine uses statistical methods to identify performance degradation:

1. **Threshold-Based Detection**: Alerts when metrics exceed defined thresholds
2. **Trend Analysis**: Identifies gradual performance degradation
3. **Confidence Scoring**: Provides confidence levels for regression alerts
4. **Recommendation Engine**: Suggests actions based on regression analysis

### Regression Thresholds

```python
REGRESSION_THRESHOLD = 1.20  # 20% performance degradation threshold
MIN_SAMPLES = 10            # Minimum samples for statistical analysis
```

### Analysis Output

```python
@dataclass
class RegressionAnalysis:
    test_name: str
    current_metric: float
    baseline_metric: float
    regression_percent: float
    is_regression: bool
    confidence_level: float
    recommendation: str
```

## CI/CD Integration

### GitHub Actions Workflow

The performance regression tests are integrated into the CI/CD pipeline:

```yaml
# Performance Regression Tests
performance-regression:
  runs-on: ubuntu-latest
  needs: [frontend-backend-integration]
  
  steps:
    - name: Run Performance Regression Tests
      env:
        FXML4_ENV: ci
        GIT_COMMIT: ${{ github.sha }}
      run: |
        ./scripts/run_performance_regression_tests.sh test \
          --api-url http://localhost:8001 \
          --environment ci
      timeout-minutes: 15

    - name: Upload performance regression results
      uses: actions/upload-artifact@v3
      with:
        name: performance-regression-results
        path: performance-regression-results/
```

### Make Targets

```makefile
test-performance:           # Run performance regression tests
test-performance-baseline:  # Initialize performance baselines
test-performance-report:    # Generate performance reports
test-performance-clean:     # Clean performance test artifacts
```

### Pipeline Integration

The performance tests are integrated into the complete CI pipeline:

```bash
ci-pipeline: ## Complete CI pipeline
	@$(MAKE) test-unit
	@$(MAKE) test-integration
	@$(MAKE) test-security
	@$(MAKE) test-e2e
	@$(MAKE) test-integration-frontend
	@$(MAKE) test-performance  # ← Performance regression testing
	@$(MAKE) coverage-check
```

## Reporting

### Report Types

1. **Regression Analysis Report**: Detailed regression findings
2. **Performance Summary**: High-level metrics and trends
3. **JUnit XML**: Test results for CI integration
4. **Historical Trends**: Performance over time

### Sample Report

```markdown
# FXML4 Performance Regression Test Report

**Generated:** 2025-01-19T10:30:00
**Git Commit:** abc123def
**Environment:** ci

## Executive Summary

- **Total Tests:** 4
- **Regressions Detected:** 0
- **Regression Threshold:** 20%
- **Overall Status:** ✅ PASSED

## Detailed Results

### API Endpoint Performance - ✅ PASS
- Current P95: 42.3ms
- Baseline P95: 45.2ms
- Change: -6.4%
- Recommendation: Performance within acceptable range

### Database Performance - ✅ PASS
- Current P95: 89.7ms
- Baseline P95: 94.2ms
- Change: -4.8%
- Recommendation: Performance maintained

## Performance Measurements

| Operation | Avg Response Time (ms) | Success Rate | Memory (MB) | CPU (%) |
|-----------|----------------------|--------------|-------------|----------|
| GET /health | 23.1 | 100.0% | 45.2 | 12.3 |
| GET /api/data/symbols | 156.7 | 100.0% | 67.8 | 23.4 |
| POST /api/signals/generate | 1456.2 | 95.0% | 89.1 | 45.6 |
```

### Report Artifacts

- `performance-regression-junit.xml` - JUnit test results
- `performance-regression-summary.md` - Comprehensive report
- `regression_report_TIMESTAMP.md` - Detailed analysis

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `PERFORMANCE_API_URL` | `http://localhost:8001` | API endpoint URL |
| `PERFORMANCE_SAMPLES` | `20` | Number of test samples |
| `REGRESSION_THRESHOLD` | `20` | Regression threshold (%) |
| `FXML4_ENV` | `test` | Environment name |
| `GIT_COMMIT` | auto-detected | Git commit hash |

### Test Configuration

```python
# Configuration constants
BASELINES_DIR = Path("tests/performance/baselines")
REPORTS_DIR = Path("performance-regression-results")
REGRESSION_THRESHOLD = 1.20  # 20% threshold
MIN_SAMPLES = 10
```

## Troubleshooting

### Common Issues

1. **No Baselines Found**
   ```bash
   # Initialize baselines first
   make test-performance-baseline
   ```

2. **API Not Available**
   ```bash
   # Check API status
   curl http://localhost:8001/health
   
   # Start API if needed
   python scripts/start_fxml4_api.py
   ```

3. **Performance Test Failures**
   ```bash
   # Check test logs
   cat performance-regression-results/regression_report_*.md
   
   # Run with verbose output
   pytest tests/performance/ -v -s
   ```

4. **Baseline Update Needed**
   ```bash
   # Force baseline recreation
   ./scripts/run_performance_regression_tests.sh baseline --force-baseline
   ```

### Debugging

```bash
# Run individual test with detailed output
python -m pytest tests/performance/test_performance_regression_suite.py::test_api_endpoint_performance_regression -v -s

# Check baseline files
ls -la tests/performance/baselines/
cat tests/performance/baselines/api_endpoint_performance.json

# Review performance measurements
python -c "
import sys
sys.path.append('.')
from tests.performance.test_performance_regression_suite import PerformanceRegressionSuite
# ... debugging code
"
```

### Log Analysis

Performance regression tests generate detailed logs:

```
[INFO] 📊 Measuring baseline performance for api_endpoint_performance
[INFO]   Iteration 1/3
[INFO] Testing GET /health
[INFO] Testing GET /api/data/symbols
[INFO] Testing POST /api/signals/generate
[INFO] ✅ api_endpoint_performance completed
[INFO] 📊 Performance regression report generated: performance-regression-results/regression_report_20250119_103045.md
```

## Best Practices

### 1. Baseline Management

- **Regular Updates**: Update baselines after verified performance improvements
- **Environment Separation**: Maintain separate baselines for different environments
- **Version Control**: Track baselines in Git for historical analysis
- **Documentation**: Document significant baseline changes

### 2. Test Design

- **Realistic Workloads**: Use realistic data and scenarios
- **Statistical Significance**: Use adequate sample sizes
- **Error Handling**: Gracefully handle test failures
- **Resource Cleanup**: Clean up test data and resources

### 3. CI/CD Integration

- **Threshold Configuration**: Set appropriate regression thresholds
- **Failure Handling**: Handle test failures gracefully in CI
- **Artifact Storage**: Store test results and reports
- **Notification**: Alert teams on performance regressions

### 4. Performance Monitoring

- **Continuous Monitoring**: Run tests regularly
- **Trend Analysis**: Monitor performance trends over time
- **Alert Fatigue**: Avoid false positives with proper thresholds
- **Root Cause Analysis**: Investigate performance regressions promptly

## Future Enhancements

1. **Advanced Analytics**
   - Machine learning-based anomaly detection
   - Predictive performance modeling
   - Seasonal trend analysis

2. **Extended Coverage**
   - Frontend performance testing
   - Network latency testing
   - Resource utilization monitoring

3. **Enhanced Reporting**
   - Interactive dashboards
   - Real-time performance monitoring
   - Historical trend visualization

4. **Integration Improvements**
   - Slack/Teams notifications
   - JIRA integration for regression tickets
   - Performance budgets and gates

---

This performance regression testing framework ensures that FXML4 maintains high performance standards while detecting and preventing performance degradation over time.
