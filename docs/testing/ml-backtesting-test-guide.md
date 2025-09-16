# ML Model Building and Backtesting Test Guide

This guide provides comprehensive instructions for testing FXML4's ML model building and backtesting capabilities.

## Table of Contents

1. [Overview](#overview)
2. [Test Environment Setup](#test-environment-setup)
3. [Unit Testing](#unit-testing)
4. [Integration Testing](#integration-testing)
5. [API Testing](#api-testing)
6. [Performance Testing](#performance-testing)
7. [Manual Testing Scenarios](#manual-testing-scenarios)
8. [Automated Test Suite](#automated-test-suite)
9. [Troubleshooting](#troubleshooting)

## Overview

The FXML4 ML model building and backtesting system includes:

- **Feature Engineering**: Technical indicator calculation
- **Model Training**: Multiple ML algorithms (Random Forest, XGBoost, Logistic Regression)
- **Signal Generation**: ML-based trading signals
- **Backtesting Engine**: Event-driven backtesting with realistic execution
- **Performance Analysis**: Comprehensive metrics and reporting
- **API Integration**: RESTful API for all functionality

## Test Environment Setup

### Prerequisites

```bash
# 1. Ensure FXML4 is installed
pip install -e .

# 2. Install test dependencies
pip install pytest requests pandas numpy scikit-learn

# 3. Set up environment variables
export PYTHONPATH=/path/to/fxml4:$PYTHONPATH

# 4. Verify installation
python -c "import fxml4; print('FXML4 installed successfully')"
```

### Database Setup (Optional)

```bash
# If using TimescaleDB for testing
docker run -d --name test-timescaledb \
  -p 5433:5432 \
  -e POSTGRES_PASSWORD=test_password \
  timescale/timescaledb:latest-pg13

# Initialize test database
python scripts/init_test_db.py
```

## Unit Testing

### Running Individual Tests

```bash
# Run ML pipeline integration tests
pytest tests/integration/test_ml_pipeline.py -v -s

# Run specific test class
pytest tests/integration/test_ml_pipeline.py::TestMLPipeline -v -s

# Run specific test method
pytest tests/integration/test_ml_pipeline.py::TestMLPipeline::test_03_ml_model_training -v -s
```

### Test Coverage

```bash
# Run tests with coverage
pytest tests/integration/test_ml_pipeline.py --cov=fxml4 --cov-report=html

# View coverage report
open htmlcov/index.html
```

### Understanding Test Results

The unit tests validate:

1. **Data Validation**: Market data quality and structure
2. **Feature Engineering**: Technical indicator calculation
3. **Model Training**: ML model creation and training
4. **Signal Generation**: Trading signal creation from models
5. **Backtest Execution**: Complete backtest workflow
6. **Performance Analysis**: Metrics calculation and validation
7. **Model Persistence**: Save/load model functionality

Expected output:
```
tests/integration/test_ml_pipeline.py::TestMLPipeline::test_01_data_validation PASSED
tests/integration/test_ml_pipeline.py::TestMLPipeline::test_02_feature_engineering PASSED
tests/integration/test_ml_pipeline.py::TestMLPipeline::test_03_ml_model_training PASSED
...
```

## Integration Testing

### ML Demo Script

The ML demo script provides a complete end-to-end test:

```bash
# Run the ML backtesting demo
python scripts/test_ml_backtest_demo.py
```

This script demonstrates:

1. **Sample Data Generation**: Creates realistic market data
2. **Feature Engineering**: Builds technical indicators
3. **Model Training**: Trains multiple ML models
4. **Signal Generation**: Creates trading signals
5. **Backtesting**: Runs complete backtest
6. **Results Analysis**: Analyzes performance metrics
7. **Model Persistence**: Saves trained models

Expected output:
```
🚀 Starting FXML4 ML Backtest Demo
==================================================
🔄 Step 1: Generating sample market data...
✅ Generated 2190 data points from 2023-01-01 to 2023-12-01
🔄 Step 2: Creating technical features...
✅ Created 45 features
...
📊 BACKTEST RESULTS SUMMARY
==================================================
Strategy: ML-based (random_forest)
Initial Capital: $10,000.00
Final Capital: $10,234.56
Total Return: $234.56 (2.35%)
```

## API Testing

### Starting the API

```bash
# Option 1: Docker Compose
docker-compose up -d api

# Option 2: Direct Python
uvicorn fxml4.api.main:app --host 0.0.0.0 --port 8000

# Verify API is running
curl http://localhost:8000/health
```

### Running API Tests

```bash
# Run comprehensive API tests
python scripts/test_api_backtest.py --url http://localhost:8000

# Test specific functionality
python scripts/test_api_backtest.py --url http://localhost:8000 --username admin --password admin
```

### Manual API Testing

#### 1. Authentication

```bash
# Get access token
curl -X POST http://localhost:8000/token \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=admin&password=admin"

# Extract token from response
TOKEN="your_jwt_token_here"
```

#### 2. Market Data Retrieval

```bash
# Get market data
curl -X POST http://localhost:8000/data \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "symbol": "EURUSD",
    "timeframe": "4h",
    "start_date": "2023-01-01",
    "end_date": "2023-06-30",
    "limit": 1000
  }'
```

#### 3. Signal Generation

```bash
# Generate trading signals
curl -X POST http://localhost:8000/signals \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "symbol": "EURUSD",
    "timeframe": "4h",
    "strategy": "ml_strategy",
    "parameters": {
      "model": "random_forest",
      "threshold": 0.7
    }
  }'
```

#### 4. Backtesting

```bash
# Run backtest
curl -X POST http://localhost:8000/backtest \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "symbol": "EURUSD",
    "timeframe": "4h",
    "strategy": "ml_strategy",
    "start_date": "2023-01-01",
    "end_date": "2023-03-31",
    "initial_capital": 10000,
    "parameters": {
      "model": "random_forest",
      "threshold": 0.6
    }
  }'
```

#### 5. Performance Analysis

```bash
# Get backtest ID from previous response
BACKTEST_ID="BT-20231201-143022"

# Get performance metrics
curl -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8000/performance/metrics/$BACKTEST_ID?include_trades=true&include_equity_curve=true"

# Get performance report
curl -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8000/performance/report/$BACKTEST_ID?format=html" \
  -o backtest_report.html
```

## Performance Testing

### Load Testing

```bash
# Install load testing tools
pip install locust

# Run load test
locust -f tests/load/locustfile.py --host=http://localhost:8000
```

### Memory and CPU Testing

```python
# Test script for performance monitoring
import psutil
import time
from fxml4.ml.features import create_technical_features
import pandas as pd
import numpy as np

# Monitor resource usage during ML operations
process = psutil.Process()

print(f"Initial memory: {process.memory_info().rss / 1024 / 1024:.2f} MB")

# Create large dataset
dates = pd.date_range('2020-01-01', '2023-12-31', freq='1H')
data = pd.DataFrame({
    'timestamp': dates,
    'open': np.random.uniform(1.05, 1.15, len(dates)),
    'high': np.random.uniform(1.05, 1.15, len(dates)),
    'low': np.random.uniform(1.05, 1.15, len(dates)),
    'close': np.random.uniform(1.05, 1.15, len(dates)),
    'volume': np.random.randint(1000, 10000, len(dates))
})
data.set_index('timestamp', inplace=True)

print(f"After data creation: {process.memory_info().rss / 1024 / 1024:.2f} MB")

# Create features
start_time = time.time()
features_data = create_technical_features(data, indicators=['sma', 'ema', 'rsi'])
end_time = time.time()

print(f"After feature engineering: {process.memory_info().rss / 1024 / 1024:.2f} MB")
print(f"Feature engineering time: {end_time - start_time:.2f} seconds")
```

## Manual Testing Scenarios

### Scenario 1: Complete ML Workflow

1. **Generate Sample Data**
   - Create 1 year of hourly EUR/USD data
   - Validate data quality (no gaps, proper OHLC relationships)

2. **Feature Engineering**
   - Calculate 20+ technical indicators
   - Verify indicator values are reasonable
   - Check for NaN handling

3. **Model Training**
   - Train Random Forest, XGBoost, and Logistic Regression
   - Compare accuracy scores
   - Validate feature importance

4. **Signal Generation**
   - Generate signals with 60% confidence threshold
   - Verify signal timing and logic
   - Test different confidence levels

5. **Backtesting**
   - Run 3-month backtest with 2% risk per trade
   - Validate trade execution logic
   - Check performance metrics

### Scenario 2: Strategy Comparison

```python
# Test multiple strategies
strategies = [
    ("ML Random Forest", "ml_strategy", {"model": "random_forest"}),
    ("ML XGBoost", "ml_strategy", {"model": "xgboost"}),
    ("Technical MA", "integrated_strategy", {}),
    ("Elliott Wave", "wave_strategy", {"strictness": 0.5})
]

results = {}
for name, strategy, params in strategies:
    # Run backtest for each strategy
    result = run_backtest_via_api(strategy, params)
    results[name] = result

# Compare results
print("Strategy Comparison:")
for name, result in results.items():
    print(f"{name}: {result['total_return_pct']:.2f}% return")
```

### Scenario 3: Risk Management Testing

```python
# Test different risk levels
risk_levels = [0.01, 0.02, 0.05, 0.10]  # 1%, 2%, 5%, 10%

for risk_pct in risk_levels:
    result = run_backtest_with_risk(risk_pct)
    print(f"Risk {risk_pct:.0%}: Return {result['total_return_pct']:.2f}%, "
          f"Max DD {result['max_drawdown_pct']:.2f}%")
```

### Scenario 4: Data Quality Testing

```python
# Test with problematic data
def test_data_quality():
    # Test with gaps
    data_with_gaps = create_data_with_missing_periods()
    test_ml_pipeline(data_with_gaps)

    # Test with extreme values
    data_with_outliers = create_data_with_outliers()
    test_ml_pipeline(data_with_outliers)

    # Test with insufficient data
    minimal_data = create_minimal_dataset(50)  # Only 50 records
    test_ml_pipeline(minimal_data)
```

## Automated Test Suite

### Running All Tests

```bash
# Run the complete test suite
./scripts/run_ml_backtest_tests.sh
```

This script will:

1. **Check Environment**: Verify Python packages and dependencies
2. **Start API**: Launch API server if not running
3. **Run Unit Tests**: Execute pytest suite
4. **Run ML Demo**: Complete end-to-end ML workflow
5. **Run API Tests**: Test all API endpoints
6. **Performance Tests**: Validate system performance
7. **Generate Report**: Create comprehensive test report

### Test Suite Options

```bash
# Run only unit tests
./scripts/run_ml_backtest_tests.sh --unit-only

# Skip API startup (if already running)
./scripts/run_ml_backtest_tests.sh --skip-api-start

# Get help
./scripts/run_ml_backtest_tests.sh --help
```

### Expected Output

```
🚀 FXML4 ML Model and Backtesting Test Suite
==============================================
[INFO] Starting ML model and backtesting test suite...
[STEP] Checking Python environment...
[INFO] Python environment OK
[STEP] Checking API status...
[INFO] API is running
[STEP] Running unit tests for ML pipeline...
[INFO] Unit tests passed ✅
[STEP] Running ML model building and backtesting demo...
[INFO] ML demo completed successfully ✅
[STEP] Running API backtesting tests...
[INFO] API tests completed successfully ✅
[STEP] Running performance tests...
[INFO] Performance tests passed ✅
[STEP] Generating test report...
[INFO] Test report generated: output/test_results/test_report.md
==============================================
[INFO] Test Suite Completed
[INFO] Results: 4/4 tests passed
[INFO] 🎉 All tests passed! System is ready for production.
```

## Troubleshooting

### Common Issues

#### 1. Import Errors

```bash
# Error: ModuleNotFoundError: No module named 'fxml4'
# Solution: Install in development mode
pip install -e .

# Error: No module named 'sklearn'
# Solution: Install scikit-learn
pip install scikit-learn
```

#### 2. API Connection Issues

```bash
# Error: Connection refused
# Check if API is running
curl http://localhost:8000/health

# Start API manually
uvicorn fxml4.api.main:app --host 0.0.0.0 --port 8000

# Check logs
docker-compose logs api
```

#### 3. Memory Issues

```bash
# Error: Memory allocation failed
# Solution: Reduce data size or increase memory limits

# For Docker
docker-compose up -d --memory=4g api

# For Kubernetes
kubectl patch deployment fxml4-api -p '{"spec":{"template":{"spec":{"containers":[{"name":"api","resources":{"limits":{"memory":"4Gi"}}}]}}}}'
```

#### 4. Model Training Failures

```python
# Error: Insufficient data for training
# Solution: Check data availability
print(f"Data shape: {data.shape}")
print(f"Non-null values: {data.count()}")

# Error: Feature engineering fails
# Solution: Check for infinite values
data = data.replace([np.inf, -np.inf], np.nan)
data = data.dropna()
```

#### 5. Backtest Execution Issues

```python
# Error: No trades generated
# Solution: Check signal generation
signals = generate_signals(data)
print(f"Signals generated: {len(signals)}")

# Error: Unrealistic returns
# Solution: Check commission and slippage settings
config = {
    'commission': 0.0002,  # 2 pips
    'slippage': 0.0001,    # 1 pip
}
```

### Debug Mode

```bash
# Enable debug logging
export LOG_LEVEL=DEBUG

# Run tests with verbose output
pytest tests/integration/test_ml_pipeline.py -v -s --log-cli-level=DEBUG

# API debug mode
uvicorn fxml4.api.main:app --host 0.0.0.0 --port 8000 --log-level debug
```

### Test Data Generation

```python
# Generate test data for debugging
from fxml4.tests.utils import create_test_data

# Create sample data
data = create_test_data(
    symbol="EURUSD",
    start_date="2023-01-01",
    end_date="2023-06-30",
    timeframe="4h",
    with_trend=True,
    volatility=0.01
)

# Save for manual inspection
data.to_csv("test_data.csv")
```

### Performance Profiling

```python
# Profile ML operations
import cProfile
import pstats

def profile_ml_pipeline():
    profiler = cProfile.Profile()
    profiler.enable()

    # Run ML pipeline
    run_complete_ml_workflow()

    profiler.disable()
    stats = pstats.Stats(profiler)
    stats.sort_stats('cumulative')
    stats.print_stats(20)

profile_ml_pipeline()
```

## Test Results Interpretation

### Unit Test Results

- **PASSED**: All tests completed successfully
- **FAILED**: One or more assertions failed
- **ERROR**: Exception occurred during test execution
- **SKIPPED**: Test was skipped (usually due to missing dependencies)

### ML Demo Results

Key metrics to evaluate:
- **Model Accuracy**: Should be > 0.5 (better than random)
- **Signal Generation**: Should produce reasonable number of signals
- **Backtest Return**: Should be realistic (-50% to +50% for short periods)
- **Risk Metrics**: Max drawdown should be < 30%

### API Test Results

- **Authentication**: Should return valid JWT tokens
- **Data Retrieval**: Should return properly formatted market data
- **Signal Generation**: Should return signal objects with required fields
- **Backtesting**: Should complete and return performance metrics
- **Error Handling**: Should return appropriate HTTP status codes

### Performance Benchmarks

- **Feature Engineering**: < 1 second per 1000 data points
- **Model Training**: < 30 seconds for typical datasets
- **Signal Generation**: < 100ms per signal
- **Backtesting**: < 5 minutes for 1 year of 4-hour data
- **API Response**: < 500ms for 95th percentile

---

For additional support, see the [Troubleshooting Guide](../troubleshooting/troubleshooting-guide.md) or contact the development team.
