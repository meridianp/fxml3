#!/bin/bash
"""
Frontend-Backend Integration Test Runner
========================================

Orchestrates complete E2E integration testing between React frontend,
FXML4 API backend, and all supporting services in containerized environment.

This script:
1. Spins up complete infrastructure (Frontend + Backend + DB + Redis + RabbitMQ)
2. Waits for all services to be healthy
3. Runs Playwright-driven integration tests
4. Captures comprehensive test results and artifacts
5. Cleans up resources

Usage:
  ./run_frontend_backend_integration_tests.sh [command]

Commands:
  run       - Run the complete integration test suite
  up        - Start services only (no tests)
  down      - Stop and cleanup services
  logs      - Show service logs
  status    - Check service status
  clean     - Complete cleanup (including volumes)
"""

set -euo pipefail

# Configuration
COMPOSE_FILE="docker-compose.integration.yml"
PROJECT_NAME="fxml4-integration"
TEST_RESULTS_DIR="integration-test-results"
MAX_WAIT_TIME=300  # 5 minutes
RETRY_INTERVAL=5

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

# Create test results directory
setup_results_dir() {
    mkdir -p "$TEST_RESULTS_DIR"
    log_info "Created test results directory: $TEST_RESULTS_DIR"
}

# Check if Docker and Docker Compose are available
check_prerequisites() {
    log_step "Checking prerequisites..."

    if ! command -v docker &> /dev/null; then
        log_error "Docker is not installed or not in PATH"
        exit 1
    fi

    if ! command -v docker-compose &> /dev/null; then
        log_error "Docker Compose is not installed or not in PATH"
        exit 1
    fi

    # Check if Docker daemon is running
    if ! docker info &> /dev/null; then
        log_error "Docker daemon is not running"
        exit 1
    fi

    log_success "Prerequisites check passed"
}

# Build and start all services
start_services() {
    log_step "Building and starting integration test services..."

    # Build services first
    docker-compose -f "$COMPOSE_FILE" -p "$PROJECT_NAME" build

    # Start infrastructure services first
    log_info "Starting infrastructure services..."
    docker-compose -f "$COMPOSE_FILE" -p "$PROJECT_NAME" up -d \
        integration-test-db \
        integration-test-redis \
        integration-test-rabbitmq

    # Wait for infrastructure to be ready
    wait_for_service "integration-test-db"
    wait_for_service "integration-test-redis"
    wait_for_service "integration-test-rabbitmq"

    # Start API service
    log_info "Starting API service..."
    docker-compose -f "$COMPOSE_FILE" -p "$PROJECT_NAME" up -d integration-test-api
    wait_for_service "integration-test-api"

    # Start frontend service
    log_info "Starting frontend service..."
    docker-compose -f "$COMPOSE_FILE" -p "$PROJECT_NAME" up -d integration-test-frontend
    wait_for_service "integration-test-frontend"

    log_success "All services started successfully"
}

# Wait for a service to be healthy
wait_for_service() {
    local service_name="$1"
    local elapsed=0

    log_info "Waiting for $service_name to be healthy..."

    while [ $elapsed -lt $MAX_WAIT_TIME ]; do
        if docker-compose -f "$COMPOSE_FILE" -p "$PROJECT_NAME" ps "$service_name" | grep -q "healthy"; then
            log_success "$service_name is healthy"
            return 0
        fi

        if docker-compose -f "$COMPOSE_FILE" -p "$PROJECT_NAME" ps "$service_name" | grep -q "Exit"; then
            log_error "$service_name has exited"
            show_service_logs "$service_name"
            return 1
        fi

        sleep $RETRY_INTERVAL
        elapsed=$((elapsed + RETRY_INTERVAL))
        echo -n "."
    done

    echo
    log_error "$service_name failed to become healthy within ${MAX_WAIT_TIME}s"
    show_service_logs "$service_name"
    return 1
}

# Show logs for a specific service
show_service_logs() {
    local service_name="$1"
    log_info "Logs for $service_name:"
    docker-compose -f "$COMPOSE_FILE" -p "$PROJECT_NAME" logs --tail=50 "$service_name"
}

# Run the integration tests
run_integration_tests() {
    log_step "Running frontend-backend integration tests..."

    # Start test runner container
    docker-compose -f "$COMPOSE_FILE" -p "$PROJECT_NAME" up --no-deps integration-test-runner

    # Get exit code
    local exit_code
    exit_code=$(docker-compose -f "$COMPOSE_FILE" -p "$PROJECT_NAME" ps -q integration-test-runner | xargs docker inspect --format='{{.State.ExitCode}}')

    # Copy test results
    log_info "Copying test results..."
    docker cp "$(docker-compose -f "$COMPOSE_FILE" -p "$PROJECT_NAME" ps -q integration-test-runner):/app/integration-test-results/." "$TEST_RESULTS_DIR/" || true

    # Show test runner logs
    log_info "Test runner output:"
    docker-compose -f "$COMPOSE_FILE" -p "$PROJECT_NAME" logs integration-test-runner

    return $exit_code
}

# Stop and remove services
stop_services() {
    log_step "Stopping integration test services..."
    docker-compose -f "$COMPOSE_FILE" -p "$PROJECT_NAME" down
    log_success "Services stopped"
}

# Complete cleanup including volumes
clean_all() {
    log_step "Performing complete cleanup..."
    docker-compose -f "$COMPOSE_FILE" -p "$PROJECT_NAME" down -v --remove-orphans

    # Remove any dangling containers
    docker container prune -f

    # Remove test results if they exist
    if [ -d "$TEST_RESULTS_DIR" ]; then
        rm -rf "$TEST_RESULTS_DIR"
        log_info "Removed test results directory"
    fi

    log_success "Complete cleanup finished"
}

# Show service status
show_status() {
    log_step "Service status:"
    docker-compose -f "$COMPOSE_FILE" -p "$PROJECT_NAME" ps
}

# Show service logs
show_logs() {
    log_step "Service logs:"
    docker-compose -f "$COMPOSE_FILE" -p "$PROJECT_NAME" logs
}

# Generate test report
generate_report() {
    local exit_code=$1
    local end_time=$(date)
    local test_file="$TEST_RESULTS_DIR/integration-junit.xml"

    log_step "Generating integration test report..."

    cat > "$TEST_RESULTS_DIR/integration-test-report.md" << EOF
# Frontend-Backend Integration Test Report

**Generated:** $end_time
**Status:** $([ $exit_code -eq 0 ] && echo "✅ PASSED" || echo "❌ FAILED")
**Exit Code:** $exit_code

## Test Environment
- Docker Compose File: $COMPOSE_FILE
- Project Name: $PROJECT_NAME
- Services: Frontend (React/Next.js), Backend (FastAPI), Database (TimescaleDB), Cache (Redis), Message Queue (RabbitMQ)

## Test Scope
- Complete user authentication flow (Registration → Login → Session Management → Logout)
- Frontend-to-Backend API communication
- Database state verification
- Redis session management
- Security audit trail validation
- Real-time WebSocket communication
- Error handling and recovery

## Test Results
$([ -f "$test_file" ] && echo "JUnit XML results available: $test_file" || echo "JUnit XML results not generated")

## Service Health
$(docker-compose -f "$COMPOSE_FILE" -p "$PROJECT_NAME" ps 2>/dev/null || echo "Services not running")

## Next Steps
$([ $exit_code -eq 0 ] && echo "✅ All integration tests passed. Ready for production deployment." || echo "❌ Integration tests failed. Review logs and fix issues before proceeding.")

---
Generated by FXML4 Integration Test Runner
EOF

    log_info "Integration test report saved to: $TEST_RESULTS_DIR/integration-test-report.md"
}

# Main execution function
main() {
    local command=${1:-"run"}
    local start_time=$(date)

    echo
    echo -e "${BLUE}FXML4 Frontend-Backend Integration Test Runner${NC}"
    echo -e "${BLUE}=============================================${NC}"
    echo

    case "$command" in
        "run")
            check_prerequisites
            setup_results_dir

            # Cleanup any existing resources
            clean_all &>/dev/null || true

            # Start services
            if ! start_services; then
                log_error "Failed to start services"
                stop_services
                exit 1
            fi

            # Run tests
            local test_exit_code=0
            if ! run_integration_tests; then
                test_exit_code=1
                log_error "Integration tests failed"
            else
                log_success "Integration tests passed"
            fi

            # Generate report
            generate_report $test_exit_code

            # Cleanup
            stop_services

            echo
            if [ $test_exit_code -eq 0 ]; then
                log_success "🎉 Frontend-Backend Integration Tests PASSED"
            else
                log_error "💥 Frontend-Backend Integration Tests FAILED"
            fi

            echo -e "${CYAN}Started:${NC} $start_time"
            echo -e "${CYAN}Ended:${NC} $(date)"
            echo -e "${CYAN}Results:${NC} $TEST_RESULTS_DIR/"
            echo

            exit $test_exit_code
            ;;

        "up")
            check_prerequisites
            start_services
            log_success "Services are running. Use 'down' to stop them."
            ;;

        "down")
            stop_services
            ;;

        "logs")
            show_logs
            ;;

        "status")
            show_status
            ;;

        "clean")
            clean_all
            ;;

        "help"|"-h"|"--help")
            echo "$0"
            echo
            echo "Available commands:"
            echo "  run     - Run complete integration test suite (default)"
            echo "  up      - Start services only"
            echo "  down    - Stop services"
            echo "  logs    - Show service logs"
            echo "  status  - Show service status"
            echo "  clean   - Complete cleanup"
            echo "  help    - Show this help"
            ;;

        *)
            log_error "Unknown command: $command"
            echo "Use 'help' to see available commands"
            exit 1
            ;;
    esac
}

# Execute main function with all arguments
main "$@"
