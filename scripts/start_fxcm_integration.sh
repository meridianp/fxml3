#!/bin/bash
"""
FXCM Demo Integration Startup Script

Starts the complete FXML4-ForexConnect-FXCM integration using Docker containers
with the provided demo account credentials.

Usage:
  ./scripts/start_fxcm_integration.sh [OPTIONS]

Options:
  --build      Force rebuild of containers
  --logs       Show logs after startup
  --test       Run integration tests after startup
  --stop       Stop all containers
  --clean      Stop and remove all containers and volumes
  --help       Show this help message
"""

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
COMPOSE_FILE="docker-compose.fxcm-demo.yml"
PROJECT_NAME="fxml4-fxcm"

# Functions
print_header() {
    echo -e "${BLUE}"
    echo "================================================================================================"
    echo "🚀 FXML4-ForexConnect-FXCM Integration Startup"
    echo "================================================================================================"
    echo -e "${NC}"
    echo "📧 FXCM Demo Account: 0x0c9@quatumchain.com"
    echo "🖥️  FXCM Server: FXCM-USDDemo1"
    echo "🐳 Environment: Docker Containers"
    echo "🔧 Architecture: Containerized ForexConnect Bridge"
    echo ""
}

print_help() {
    echo "FXCM Demo Integration Startup Script"
    echo ""
    echo "Usage:"
    echo "  $0 [OPTIONS]"
    echo ""
    echo "Options:"
    echo "  --build      Force rebuild of containers"
    echo "  --logs       Show logs after startup"
    echo "  --test       Run integration tests after startup"
    echo "  --stop       Stop all containers"
    echo "  --clean      Stop and remove all containers and volumes"
    echo "  --help       Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0                    # Start with existing containers"
    echo "  $0 --build --test    # Rebuild and test"
    echo "  $0 --stop            # Stop all containers"
}

check_requirements() {
    echo -e "${BLUE}🔍 Checking requirements...${NC}"

    # Check Docker
    if ! command -v docker &> /dev/null; then
        echo -e "${RED}❌ Docker is not installed${NC}"
        exit 1
    fi

    # Check Docker Compose
    if ! command -v docker-compose &> /dev/null; then
        echo -e "${RED}❌ Docker Compose is not installed${NC}"
        exit 1
    fi

    # Check if Docker is running
    if ! docker info &> /dev/null; then
        echo -e "${RED}❌ Docker is not running${NC}"
        exit 1
    fi

    # Check compose file exists
    if [ ! -f "$COMPOSE_FILE" ]; then
        echo -e "${RED}❌ Docker compose file not found: $COMPOSE_FILE${NC}"
        exit 1
    fi

    echo -e "${GREEN}✅ All requirements satisfied${NC}"
    echo ""
}

build_containers() {
    echo -e "${BLUE}🔨 Building containers...${NC}"

    # Create necessary directories
    mkdir -p docker/fxcm-demo-bridge/logs
    mkdir -p logs
    mkdir -p db/init

    # Build containers
    docker-compose -f "$COMPOSE_FILE" -p "$PROJECT_NAME" build --no-cache

    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✅ Containers built successfully${NC}"
    else
        echo -e "${RED}❌ Container build failed${NC}"
        exit 1
    fi
    echo ""
}

start_containers() {
    echo -e "${BLUE}🚀 Starting containers...${NC}"

    # Start containers in detached mode
    docker-compose -f "$COMPOSE_FILE" -p "$PROJECT_NAME" up -d

    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✅ Containers started successfully${NC}"
    else
        echo -e "${RED}❌ Failed to start containers${NC}"
        exit 1
    fi
    echo ""
}

wait_for_services() {
    echo -e "${BLUE}⏳ Waiting for services to be ready...${NC}"

    services=(
        "http://localhost:8080/health:FXCM Bridge"
        "http://localhost:15672:RabbitMQ Management"
    )

    for service in "${services[@]}"; do
        IFS=':' read -r url name <<< "$service"
        echo -n "  Waiting for $name... "

        for i in {1..30}; do
            if curl -s "$url" > /dev/null 2>&1; then
                echo -e "${GREEN}✅ Ready${NC}"
                break
            fi

            if [ $i -eq 30 ]; then
                echo -e "${YELLOW}⚠️  Timeout (may still be starting)${NC}"
            else
                sleep 2
            fi
        done
    done
    echo ""
}

show_status() {
    echo -e "${BLUE}📊 Container Status:${NC}"
    docker-compose -f "$COMPOSE_FILE" -p "$PROJECT_NAME" ps
    echo ""

    echo -e "${BLUE}🌐 Service URLs:${NC}"
    echo "  FXCM Bridge API:      http://localhost:8080"
    echo "  FXCM Bridge Status:   http://localhost:8080/status"
    echo "  FXCM WebSocket:       ws://localhost:8081"
    echo "  RabbitMQ Management:  http://localhost:15672 (guest/guest)"
    echo "  Redis:                localhost:6379"
    echo ""

    echo -e "${BLUE}🔗 Integration Endpoints:${NC}"
    echo "  Account Info:         curl http://localhost:8080/account"
    echo "  Market Data:          curl http://localhost:8080/prices"
    echo "  Positions:            curl http://localhost:8080/positions"
    echo "  Health Check:         curl http://localhost:8080/health"
    echo ""
}

show_logs() {
    echo -e "${BLUE}📋 Container Logs:${NC}"
    echo "Press Ctrl+C to stop viewing logs"
    echo ""

    docker-compose -f "$COMPOSE_FILE" -p "$PROJECT_NAME" logs -f
}

run_tests() {
    echo -e "${BLUE}🧪 Running integration tests...${NC}"

    # Install test dependencies if needed
    if [ -f "requirements-test.txt" ]; then
        pip install -r requirements-test.txt > /dev/null 2>&1
    fi

    # Run the test script
    if [ -f "scripts/test_fxcm_docker_integration.py" ]; then
        python3 scripts/test_fxcm_docker_integration.py
    else
        echo -e "${RED}❌ Test script not found${NC}"
        exit 1
    fi
}

stop_containers() {
    echo -e "${BLUE}⏹️  Stopping containers...${NC}"

    docker-compose -f "$COMPOSE_FILE" -p "$PROJECT_NAME" stop

    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✅ Containers stopped successfully${NC}"
    else
        echo -e "${YELLOW}⚠️  Some containers may not have stopped cleanly${NC}"
    fi
    echo ""
}

clean_containers() {
    echo -e "${BLUE}🧹 Cleaning up containers and volumes...${NC}"

    # Stop and remove containers, networks, and volumes
    docker-compose -f "$COMPOSE_FILE" -p "$PROJECT_NAME" down -v --remove-orphans

    # Remove any dangling images
    docker image prune -f > /dev/null 2>&1

    echo -e "${GREEN}✅ Cleanup completed${NC}"
    echo ""
}

# Main execution
main() {
    print_header

    # Parse command line arguments
    BUILD=false
    LOGS=false
    TEST=false
    STOP=false
    CLEAN=false

    while [[ $# -gt 0 ]]; do
        case $1 in
            --build)
                BUILD=true
                shift
                ;;
            --logs)
                LOGS=true
                shift
                ;;
            --test)
                TEST=true
                shift
                ;;
            --stop)
                STOP=true
                shift
                ;;
            --clean)
                CLEAN=true
                shift
                ;;
            --help)
                print_help
                exit 0
                ;;
            *)
                echo -e "${RED}❌ Unknown option: $1${NC}"
                print_help
                exit 1
                ;;
        esac
    done

    # Handle stop/clean first
    if [ "$CLEAN" = true ]; then
        check_requirements
        clean_containers
        exit 0
    fi

    if [ "$STOP" = true ]; then
        check_requirements
        stop_containers
        exit 0
    fi

    # Normal startup flow
    check_requirements

    if [ "$BUILD" = true ]; then
        build_containers
    fi

    start_containers
    wait_for_services
    show_status

    if [ "$TEST" = true ]; then
        run_tests

        if [ $? -eq 0 ]; then
            echo -e "${GREEN}✅ All integration tests passed!${NC}"
        else
            echo -e "${RED}❌ Some integration tests failed${NC}"
        fi
        echo ""
    fi

    if [ "$LOGS" = true ]; then
        show_logs
    else
        echo -e "${GREEN}🎉 FXML4-FXCM Integration Started Successfully!${NC}"
        echo ""
        echo -e "${BLUE}Next Steps:${NC}"
        echo "  1. Check service status: curl http://localhost:8080/health"
        echo "  2. View account info: curl http://localhost:8080/account"
        echo "  3. Monitor logs: docker-compose -f $COMPOSE_FILE logs -f"
        echo "  4. Run tests: $0 --test"
        echo "  5. Stop services: $0 --stop"
        echo ""
        echo -e "${YELLOW}💡 Tip: Use --logs to view real-time container logs${NC}"
    fi
}

# Run main function
main "$@"
