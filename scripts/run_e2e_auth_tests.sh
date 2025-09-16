#!/bin/bash

# Run E2E Authentication Tests in Docker Containers
# This script orchestrates the complete containerized test environment

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

echo "🔧 FXML4 E2E Authentication Test Runner"
echo "======================================="
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Parse command line arguments
ACTION=${1:-run}
COMPOSE_FILE="docker-compose.test.yml"
TEST_RESULTS_DIR="test-results"

# Change to project root
cd "$PROJECT_ROOT"

# Function to cleanup containers
cleanup() {
    echo -e "\n${YELLOW}Cleaning up test containers...${NC}"
    docker-compose -f $COMPOSE_FILE down -v --remove-orphans
    echo -e "${GREEN}✓ Cleanup complete${NC}"
}

# Function to check container health
check_health() {
    local service=$1
    local max_attempts=30
    local attempt=0

    echo -n "Checking $service health..."

    while [ $attempt -lt $max_attempts ]; do
        if docker-compose -f $COMPOSE_FILE ps | grep -q "${service}.*Up.*healthy"; then
            echo -e " ${GREEN}✓${NC}"
            return 0
        fi

        sleep 2
        attempt=$((attempt + 1))
        echo -n "."
    done

    echo -e " ${RED}✗${NC}"
    return 1
}

# Function to show logs
show_logs() {
    local service=$1
    echo -e "\n${YELLOW}Logs for $service:${NC}"
    docker-compose -f $COMPOSE_FILE logs --tail=50 $service
}

case "$ACTION" in
    run)
        echo -e "${GREEN}Starting E2E Authentication Test Suite${NC}\n"

        # Create test results directory
        mkdir -p $TEST_RESULTS_DIR

        # Stop any existing test containers
        echo "Stopping any existing test containers..."
        docker-compose -f $COMPOSE_FILE down -v --remove-orphans 2>/dev/null || true

        # Build the test images
        echo -e "\n${YELLOW}Building test images...${NC}"
        docker-compose -f $COMPOSE_FILE build

        # Start infrastructure services
        echo -e "\n${YELLOW}Starting infrastructure services...${NC}"
        docker-compose -f $COMPOSE_FILE up -d test-db test-redis test-rabbitmq

        # Wait for infrastructure to be healthy
        echo -e "\n${YELLOW}Waiting for infrastructure...${NC}"
        check_health "test-db" || { echo "Database failed to start"; cleanup; exit 1; }
        check_health "test-redis" || { echo "Redis failed to start"; cleanup; exit 1; }
        check_health "test-rabbitmq" || { echo "RabbitMQ failed to start"; cleanup; exit 1; }

        # Start API service
        echo -e "\n${YELLOW}Starting API service...${NC}"
        docker-compose -f $COMPOSE_FILE up -d test-api

        # Wait for API to be healthy
        check_health "test-api" || {
            echo "API failed to start"
            show_logs "test-api"
            cleanup
            exit 1
        }

        # Run the tests
        echo -e "\n${YELLOW}Running E2E Authentication Tests...${NC}\n"

        if docker-compose -f $COMPOSE_FILE run --rm test-runner; then
            echo -e "\n${GREEN}✅ All E2E Authentication Tests Passed!${NC}"
            TEST_EXIT_CODE=0
        else
            echo -e "\n${RED}❌ Some tests failed${NC}"
            TEST_EXIT_CODE=1
        fi

        # Copy test results if they exist
        if docker-compose -f $COMPOSE_FILE ps -q test-runner 2>/dev/null; then
            docker cp fxml4-test-runner:/app/test-results/. $TEST_RESULTS_DIR/ 2>/dev/null || true
        fi

        # Show summary
        echo -e "\n${YELLOW}Test Summary:${NC}"
        echo "Results saved to: $TEST_RESULTS_DIR/"

        # Cleanup
        cleanup

        exit $TEST_EXIT_CODE
        ;;

    debug)
        echo -e "${YELLOW}Starting services in debug mode (containers stay running)${NC}\n"

        # Start all services
        docker-compose -f $COMPOSE_FILE up -d

        echo -e "\n${GREEN}Services are running. You can now:${NC}"
        echo "  - Access API at: http://localhost:8002"
        echo "  - Access RabbitMQ Management at: http://localhost:15673"
        echo "  - Connect to PostgreSQL at: localhost:5433"
        echo "  - Connect to Redis at: localhost:6380"
        echo ""
        echo "Run tests manually with:"
        echo "  docker-compose -f $COMPOSE_FILE run --rm test-runner"
        echo ""
        echo "View logs with:"
        echo "  docker-compose -f $COMPOSE_FILE logs -f [service-name]"
        echo ""
        echo "Stop all services with:"
        echo "  $0 stop"
        ;;

    stop)
        cleanup
        ;;

    logs)
        SERVICE=${2:-}
        if [ -z "$SERVICE" ]; then
            docker-compose -f $COMPOSE_FILE logs -f
        else
            docker-compose -f $COMPOSE_FILE logs -f $SERVICE
        fi
        ;;

    status)
        echo -e "${YELLOW}Test Container Status:${NC}\n"
        docker-compose -f $COMPOSE_FILE ps
        ;;

    *)
        echo "Usage: $0 {run|debug|stop|logs [service]|status}"
        echo ""
        echo "  run    - Run the complete E2E test suite"
        echo "  debug  - Start services for manual testing"
        echo "  stop   - Stop and clean up all test containers"
        echo "  logs   - View container logs (optionally specify service)"
        echo "  status - Show status of test containers"
        exit 1
        ;;
esac
