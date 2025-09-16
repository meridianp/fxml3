#!/bin/bash
"""
Performance Regression Test Runner
=================================

Comprehensive script to run performance regression tests for the FXML4 system.
This script handles baseline initialization, regression testing, and reporting.

Features:
- Automated baseline management
- Performance regression detection
- Comprehensive reporting
- CI/CD integration
- Environment-specific configuration
- Historical trend analysis

Usage:
  ./run_performance_regression_tests.sh [command] [options]

Commands:
  test       - Run performance regression tests (default)
  baseline   - Initialize/update performance baselines
  report     - Generate performance reports only
  clean      - Clean test artifacts
  help       - Show this help

Options:
  --api-url URL          - API endpoint URL (default: http://localhost:8001)
  --environment ENV      - Environment name (default: test)
  --samples N            - Number of test samples (default: 20)
  --threshold PERCENT    - Regression threshold percentage (default: 20)
  --force-baseline       - Force baseline recreation
  --no-baseline          - Skip baseline check/creation
  --output-dir DIR       - Output directory for reports
"""

set -euo pipefail

# Configuration
DEFAULT_API_URL="http://localhost:8001"
DEFAULT_ENVIRONMENT="test"
DEFAULT_SAMPLES=20
DEFAULT_THRESHOLD=20
DEFAULT_OUTPUT_DIR="performance-regression-results"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
BASELINES_DIR="$PROJECT_ROOT/tests/performance/baselines"
VENV_PATH="$PROJECT_ROOT/venv"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
MAGENTA='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Logging functions
log_info() {
    echo -e "${CYAN}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

log_step() {
    echo -e "${MAGENTA}[STEP]${NC} $1"
}

# Initialize default values
API_URL="$DEFAULT_API_URL"
ENVIRONMENT="$DEFAULT_ENVIRONMENT"
SAMPLES="$DEFAULT_SAMPLES"
THRESHOLD="$DEFAULT_THRESHOLD"
OUTPUT_DIR="$DEFAULT_OUTPUT_DIR"
FORCE_BASELINE=false
NO_BASELINE=false
COMMAND="test"

# Parse command line arguments
parse_args() {
    while [[ $# -gt 0 ]]; do
        case $1 in
            test|baseline|report|clean|help)
                COMMAND="$1"
                shift
                ;;
            --api-url)
                API_URL="$2"
                shift 2
                ;;
            --environment)
                ENVIRONMENT="$2"
                shift 2
                ;;
            --samples)
                SAMPLES="$2"
                shift 2
                ;;
            --threshold)
                THRESHOLD="$2"
                shift 2
                ;;
            --output-dir)
                OUTPUT_DIR="$2"
                shift 2
                ;;
            --force-baseline)
                FORCE_BASELINE=true
                shift
                ;;
            --no-baseline)
                NO_BASELINE=true
                shift
                ;;
            *)
                log_error "Unknown option: $1"
                show_help
                exit 1
                ;;
        esac
    done
}

# Show help message
show_help() {
    echo "$0"
    echo
    echo "Available commands:"
    echo "  test       - Run performance regression tests (default)"
    echo "  baseline   - Initialize/update performance baselines"
    echo "  report     - Generate performance reports only"
    echo "  clean      - Clean test artifacts"
    echo "  help       - Show this help"
    echo
    echo "Options:"
    echo "  --api-url URL          - API endpoint URL (default: $DEFAULT_API_URL)"
    echo "  --environment ENV      - Environment name (default: $DEFAULT_ENVIRONMENT)"
    echo "  --samples N            - Number of test samples (default: $DEFAULT_SAMPLES)"
    echo "  --threshold PERCENT    - Regression threshold percentage (default: $DEFAULT_THRESHOLD)"
    echo "  --force-baseline       - Force baseline recreation"
    echo "  --no-baseline          - Skip baseline check/creation"
    echo "  --output-dir DIR       - Output directory for reports"
}

# Check prerequisites
check_prerequisites() {
    log_step "Checking prerequisites..."

    # Check Python
    if ! command -v python3 &> /dev/null; then
        log_error "Python 3 is not installed or not in PATH"
        exit 1
    fi

    # Check if in project directory
    if [[ ! -f "$PROJECT_ROOT/pyproject.toml" ]]; then
        log_error "Not in FXML4 project directory"
        exit 1
    fi

    # Activate virtual environment if available
    if [[ -d "$VENV_PATH" ]]; then
        source "$VENV_PATH/bin/activate"
        log_info "Activated virtual environment"
    else
        log_warning "No virtual environment found at $VENV_PATH"
    fi

    # Check required Python packages
    if ! python3 -c "import pytest, aiohttp, numpy" &> /dev/null; then
        log_error "Required Python packages not installed (pytest, aiohttp, numpy)"
        exit 1
    fi

    log_success "Prerequisites check passed"
}

# Setup environment
setup_environment() {
    log_step "Setting up test environment..."

    # Set environment variables
    export FXML4_ENV="$ENVIRONMENT"
    export PYTHONPATH="$PROJECT_ROOT:$PYTHONPATH"

    # Create output directory
    mkdir -p "$OUTPUT_DIR"
    mkdir -p "$BASELINES_DIR"

    # Create pytest configuration if it doesn't exist
    if [[ ! -f "$PROJECT_ROOT/pytest.ini" ]]; then
        cat > "$PROJECT_ROOT/pytest.ini" << EOF
[tool:pytest]
markers =
    performance: Performance and regression tests
    slow: Slow-running tests
    integration: Integration tests
    unit: Unit tests
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*
EOF
    fi

    log_success "Environment setup complete"
}

# Wait for API to be available
wait_for_api() {
    log_step "Checking API availability at $API_URL..."

    local max_attempts=30
    local attempt=0

    while [ $attempt -lt $max_attempts ]; do
        if curl -s -f "$API_URL/health" > /dev/null 2>&1; then
            log_success "API is available"
            return 0
        fi

        sleep 2
        attempt=$((attempt + 1))
        echo -n "."
    done

    echo
    log_error "API not available after $max_attempts attempts"
    return 1
}

# Initialize baselines
initialize_baselines() {
    log_step "Initializing performance baselines..."

    local force_flag=""
    if [[ "$FORCE_BASELINE" == "true" ]]; then
        force_flag="--force"
    fi

    python3 "$SCRIPT_DIR/initialize_performance_baselines.py" \
        --api-url "$API_URL" \
        --environment "$ENVIRONMENT" \
        $force_flag

    if [[ $? -eq 0 ]]; then
        log_success "Baselines initialized successfully"
    else
        log_error "Failed to initialize baselines"
        return 1
    fi
}

# Check if baselines exist
check_baselines() {
    log_step "Checking existing baselines..."

    if [[ "$NO_BASELINE" == "true" ]]; then
        log_info "Skipping baseline check (--no-baseline)"
        return 0
    fi

    local baseline_count=$(ls -1 "$BASELINES_DIR"/*.json 2>/dev/null | wc -l)

    if [[ $baseline_count -eq 0 ]]; then
        log_warning "No baselines found, initializing..."
        initialize_baselines
        return $?
    else
        log_info "Found $baseline_count existing baselines"

        # Show existing baselines
        python3 "$SCRIPT_DIR/initialize_performance_baselines.py" --list
    fi
}

# Run performance regression tests
run_regression_tests() {
    log_step "Running performance regression tests..."

    local pytest_args=(
        "tests/performance/test_performance_regression_suite.py"
        "-v"
        "--tb=short"
        "-m" "performance"
        "--junit-xml=$OUTPUT_DIR/performance-regression-junit.xml"
    )

    # Set test configuration environment variables
    export PERFORMANCE_API_URL="$API_URL"
    export PERFORMANCE_SAMPLES="$SAMPLES"
    export REGRESSION_THRESHOLD="$THRESHOLD"

    log_info "Test configuration:"
    log_info "  API URL: $API_URL"
    log_info "  Environment: $ENVIRONMENT"
    log_info "  Samples: $SAMPLES"
    log_info "  Regression Threshold: $THRESHOLD%"
    log_info "  Output Directory: $OUTPUT_DIR"

    # Run the tests
    python3 -m pytest "${pytest_args[@]}"
    local exit_code=$?

    if [[ $exit_code -eq 0 ]]; then
        log_success "Performance regression tests passed"
    else
        log_error "Performance regression tests failed"
    fi

    return $exit_code
}

# Generate performance report
generate_report() {
    log_step "Generating performance regression report..."

    local report_file="$OUTPUT_DIR/performance-regression-summary.md"
    local timestamp=$(date +"%Y-%m-%d %H:%M:%S")

    cat > "$report_file" << EOF
# FXML4 Performance Regression Test Report

**Generated:** $timestamp
**Environment:** $ENVIRONMENT
**API URL:** $API_URL
**Git Commit:** ${GIT_COMMIT:-$(git rev-parse --short HEAD 2>/dev/null || echo "unknown")}

## Test Configuration

- **Samples per test:** $SAMPLES
- **Regression threshold:** $THRESHOLD%
- **Output directory:** $OUTPUT_DIR

## Results Summary

$(if [[ -f "$OUTPUT_DIR/performance-regression-junit.xml" ]]; then
    echo "JUnit XML results available: performance-regression-junit.xml"
else
    echo "No JUnit XML results found"
fi)

## Baseline Information

$(python3 "$SCRIPT_DIR/initialize_performance_baselines.py" --list 2>/dev/null || echo "No baselines available")

## Files Generated

- \`performance-regression-junit.xml\` - JUnit test results
- \`performance-regression-summary.md\` - This summary report

## Next Steps

1. Review test results for any performance regressions
2. If regressions are found, investigate recent changes
3. Update baselines if performance improvements are verified
4. Monitor trends over time for performance degradation

---
*Generated by FXML4 Performance Regression Test Suite*
EOF

    log_success "Performance report generated: $report_file"
}

# Clean test artifacts
clean_artifacts() {
    log_step "Cleaning performance test artifacts..."

    # Remove output directory
    if [[ -d "$OUTPUT_DIR" ]]; then
        rm -rf "$OUTPUT_DIR"
        log_info "Removed output directory: $OUTPUT_DIR"
    fi

    # Remove pytest cache
    if [[ -d "$PROJECT_ROOT/.pytest_cache" ]]; then
        rm -rf "$PROJECT_ROOT/.pytest_cache"
        log_info "Removed pytest cache"
    fi

    # Remove Python cache
    find "$PROJECT_ROOT" -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true
    find "$PROJECT_ROOT" -name "*.pyc" -delete 2>/dev/null || true

    log_success "Cleanup complete"
}

# Main execution function
main() {
    local start_time=$(date)

    echo
    echo -e "${BLUE}FXML4 Performance Regression Test Runner${NC}"
    echo -e "${BLUE}=========================================${NC}"
    echo

    case "$COMMAND" in
        "test")
            check_prerequisites
            setup_environment

            # Wait for API unless running baseline-only
            if ! wait_for_api; then
                log_error "Cannot run performance tests - API not available"
                exit 1
            fi

            # Check/initialize baselines
            if ! check_baselines; then
                log_error "Baseline check/initialization failed"
                exit 1
            fi

            # Run regression tests
            if run_regression_tests; then
                generate_report

                echo
                log_success "🎉 Performance Regression Tests PASSED"
                echo -e "${CYAN}Started:${NC} $start_time"
                echo -e "${CYAN}Ended:${NC} $(date)"
                echo -e "${CYAN}Results:${NC} $OUTPUT_DIR/"
                echo
                exit 0
            else
                generate_report

                echo
                log_error "💥 Performance Regression Tests FAILED"
                echo -e "${CYAN}Started:${NC} $start_time"
                echo -e "${CYAN}Ended:${NC} $(date)"
                echo -e "${CYAN}Results:${NC} $OUTPUT_DIR/"
                echo
                exit 1
            fi
            ;;

        "baseline")
            check_prerequisites
            setup_environment

            if ! wait_for_api; then
                log_error "Cannot initialize baselines - API not available"
                exit 1
            fi

            if initialize_baselines; then
                log_success "Baselines initialized successfully"
                exit 0
            else
                log_error "Baseline initialization failed"
                exit 1
            fi
            ;;

        "report")
            check_prerequisites
            setup_environment
            generate_report
            log_success "Report generated successfully"
            ;;

        "clean")
            clean_artifacts
            ;;

        "help")
            show_help
            ;;

        *)
            log_error "Unknown command: $COMMAND"
            show_help
            exit 1
            ;;
    esac
}

# Parse arguments and run main function
parse_args "$@"
main
