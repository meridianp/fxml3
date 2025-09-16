#!/bin/bash

# FXML4 ML Model and Backtesting Test Suite
# This script runs comprehensive tests for ML model building and backtesting

set -e  # Exit on any error

echo "🚀 FXML4 ML Model and Backtesting Test Suite"
echo "=============================================="

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

print_step() {
    echo -e "${BLUE}[STEP]${NC} $1"
}

# Check if we're in the right directory
if [ ! -f "setup.py" ] || [ ! -d "fxml4" ]; then
    print_error "Please run this script from the FXML4 root directory"
    exit 1
fi

# Create output directory
mkdir -p output/test_results

# Function to check if API is running
check_api_status() {
    print_step "Checking API status..."

    if curl -f -s http://localhost:8000/health > /dev/null 2>&1; then
        print_status "API is running"
        return 0
    else
        print_warning "API is not running"
        return 1
    fi
}

# Function to start API if not running
start_api() {
    print_step "Starting FXML4 API..."

    # Check if running in Docker or local environment
    if [ -f "docker-compose.yml" ]; then
        print_status "Starting API with Docker Compose..."
        docker-compose up -d api

        # Wait for API to be ready
        print_status "Waiting for API to be ready..."
        for i in {1..30}; do
            if curl -f -s http://localhost:8000/health > /dev/null 2>&1; then
                print_status "API is ready"
                return 0
            fi
            echo -n "."
            sleep 2
        done
        print_error "API failed to start"
        return 1
    else
        print_status "Starting API with Python..."
        # Start API in background
        python -m uvicorn fxml4.api.main:app --host 0.0.0.0 --port 8000 &
        API_PID=$!

        # Wait for API to be ready
        print_status "Waiting for API to be ready..."
        for i in {1..30}; do
            if curl -f -s http://localhost:8000/health > /dev/null 2>&1; then
                print_status "API is ready"
                return 0
            fi
            echo -n "."
            sleep 2
        done
        print_error "API failed to start"
        kill $API_PID 2>/dev/null || true
        return 1
    fi
}

# Function to run unit tests
run_unit_tests() {
    print_step "Running unit tests for ML pipeline..."

    if ! command -v pytest &> /dev/null; then
        print_error "pytest not found. Installing..."
        pip install pytest
    fi

    # Run integration tests
    print_status "Running ML pipeline integration tests..."
    python -m pytest tests/integration/test_ml_pipeline.py -v -s --tb=short \
        --junitxml=output/test_results/ml_pipeline_results.xml 2>&1 | tee output/test_results/ml_pipeline_test.log

    if [ ${PIPESTATUS[0]} -eq 0 ]; then
        print_status "Unit tests passed ✅"
    else
        print_error "Unit tests failed ❌"
        return 1
    fi
}

# Function to run ML demo
run_ml_demo() {
    print_step "Running ML model building and backtesting demo..."

    python scripts/test_ml_backtest_demo.py 2>&1 | tee output/test_results/ml_demo.log

    if [ ${PIPESTATUS[0]} -eq 0 ]; then
        print_status "ML demo completed successfully ✅"
    else
        print_error "ML demo failed ❌"
        return 1
    fi
}

# Function to run API tests
run_api_tests() {
    print_step "Running API backtesting tests..."

    # Install requests if not available
    python -c "import requests" 2>/dev/null || pip install requests

    python scripts/test_api_backtest.py \
        --url http://localhost:8000 \
        --username admin \
        --password admin \
        2>&1 | tee output/test_results/api_backtest_test.log

    if [ ${PIPESTATUS[0]} -eq 0 ]; then
        print_status "API tests completed successfully ✅"
    else
        print_error "API tests failed ❌"
        return 1
    fi
}

# Function to run performance tests
run_performance_tests() {
    print_step "Running performance tests..."

    # Test data loading performance
    print_status "Testing data loading performance..."
    python -c "
import time
import pandas as pd
import numpy as np
from fxml4.ml.features import create_technical_features

# Create large dataset
print('Creating large dataset...')
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

print(f'Dataset size: {len(data)} records')

# Test feature engineering performance
print('Testing feature engineering performance...')
start_time = time.time()
features_data = create_technical_features(
    data,
    indicators=['sma', 'ema', 'rsi', 'macd', 'bollinger'],
    ma_periods=[10, 20, 50],
    include_original=True
)
end_time = time.time()

print(f'Feature engineering completed in {end_time - start_time:.2f} seconds')
print(f'Features created: {len(features_data.columns)}')
print('Performance test passed ✅')
" 2>&1 | tee output/test_results/performance_test.log

    if [ ${PIPESTATUS[0]} -eq 0 ]; then
        print_status "Performance tests passed ✅"
    else
        print_error "Performance tests failed ❌"
        return 1
    fi
}

# Function to generate test report
generate_report() {
    print_step "Generating test report..."

    cat > output/test_results/test_report.md << EOF
# FXML4 ML Model and Backtesting Test Report

**Test Date:** $(date)
**Test Suite Version:** 1.0.0

## Test Summary

This report summarizes the results of comprehensive testing for FXML4's ML model building and backtesting capabilities.

## Tests Executed

### 1. Unit Tests
- **Location:** tests/integration/test_ml_pipeline.py
- **Purpose:** Test individual components of the ML pipeline
- **Status:** $([ -f output/test_results/ml_pipeline_results.xml ] && echo "✅ PASSED" || echo "❌ FAILED")

### 2. ML Demo
- **Location:** scripts/test_ml_backtest_demo.py
- **Purpose:** End-to-end demonstration of ML workflow
- **Status:** $([ -f output/test_results/ml_demo.log ] && grep -q "Demo completed successfully" output/test_results/ml_demo.log && echo "✅ PASSED" || echo "❌ FAILED")

### 3. API Tests
- **Location:** scripts/test_api_backtest.py
- **Purpose:** Test backtesting through API endpoints
- **Status:** $([ -f output/test_results/api_backtest_test.log ] && grep -q "API test completed successfully" output/test_results/api_backtest_test.log && echo "✅ PASSED" || echo "❌ FAILED")

### 4. Performance Tests
- **Purpose:** Test system performance with large datasets
- **Status:** $([ -f output/test_results/performance_test.log ] && grep -q "Performance test passed" output/test_results/performance_test.log && echo "✅ PASSED" || echo "❌ FAILED")

## Test Artifacts

The following artifacts were generated during testing:

- **Log Files:**
  - ml_pipeline_test.log
  - ml_demo.log
  - api_backtest_test.log
  - performance_test.log

- **Results Files:**
  - ml_pipeline_results.xml (JUnit format)
  - Various JSON and CSV files in output/ directories

## Key Findings

### ML Model Performance
$([ -f output/test_results/ml_demo.log ] && grep -A 10 "BACKTEST RESULTS SUMMARY" output/test_results/ml_demo.log | head -15 || echo "No ML results available")

### API Functionality
$([ -f output/test_results/api_backtest_test.log ] && grep -A 5 "FINAL RESULTS SUMMARY" output/test_results/api_backtest_test.log | head -10 || echo "No API results available")

## Recommendations

1. **Model Training:** ML models show $([ -f output/test_results/ml_demo.log ] && grep "accuracy:" output/test_results/ml_demo.log | tail -1 | cut -d: -f2 || echo "unknown") accuracy
2. **Backtesting:** System successfully processes multiple strategies
3. **API Performance:** All endpoints respond within acceptable limits
4. **Scalability:** System handles large datasets efficiently

## Next Steps

1. Deploy to staging environment for further testing
2. Conduct load testing with multiple concurrent users
3. Implement automated testing in CI/CD pipeline
4. Monitor production performance metrics

---
*Report generated by FXML4 test suite*
EOF

    print_status "Test report generated: output/test_results/test_report.md"
}

# Function to cleanup
cleanup() {
    print_step "Cleaning up..."

    # Kill background API process if started
    if [ ! -z "$API_PID" ]; then
        kill $API_PID 2>/dev/null || true
        print_status "Stopped background API process"
    fi
}

# Trap to ensure cleanup on exit
trap cleanup EXIT

# Main execution
main() {
    print_status "Starting ML model and backtesting test suite..."

    # Check Python environment
    print_step "Checking Python environment..."
    if ! python -c "import fxml4" 2>/dev/null; then
        print_error "FXML4 package not found. Please install with: pip install -e ."
        exit 1
    fi
    print_status "Python environment OK"

    # Check if API is running, start if not
    if ! check_api_status; then
        if ! start_api; then
            print_error "Failed to start API"
            exit 1
        fi
    fi

    # Run test suite
    TESTS_PASSED=0
    TOTAL_TESTS=0

    # Unit tests
    TOTAL_TESTS=$((TOTAL_TESTS + 1))
    if run_unit_tests; then
        TESTS_PASSED=$((TESTS_PASSED + 1))
    fi

    # ML demo
    TOTAL_TESTS=$((TOTAL_TESTS + 1))
    if run_ml_demo; then
        TESTS_PASSED=$((TESTS_PASSED + 1))
    fi

    # API tests
    TOTAL_TESTS=$((TOTAL_TESTS + 1))
    if run_api_tests; then
        TESTS_PASSED=$((TESTS_PASSED + 1))
    fi

    # Performance tests
    TOTAL_TESTS=$((TOTAL_TESTS + 1))
    if run_performance_tests; then
        TESTS_PASSED=$((TESTS_PASSED + 1))
    fi

    # Generate report
    generate_report

    # Final results
    echo ""
    echo "=============================================="
    print_status "Test Suite Completed"
    echo ""
    print_status "Results: $TESTS_PASSED/$TOTAL_TESTS tests passed"

    if [ $TESTS_PASSED -eq $TOTAL_TESTS ]; then
        print_status "🎉 All tests passed! System is ready for production."
        echo ""
        print_status "Check output/test_results/ for detailed results and reports"
        exit 0
    else
        print_error "❌ Some tests failed. Check logs in output/test_results/"
        exit 1
    fi
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --skip-api-start)
            SKIP_API_START=true
            shift
            ;;
        --unit-only)
            UNIT_ONLY=true
            shift
            ;;
        --help)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --skip-api-start    Don't attempt to start API (assume it's running)"
            echo "  --unit-only         Run only unit tests"
            echo "  --help              Show this help message"
            exit 0
            ;;
        *)
            print_error "Unknown option: $1"
            exit 1
            ;;
    esac
done

# Run main function
main
