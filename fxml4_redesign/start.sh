#!/bin/bash

# FXML4 Redesigned Startup Script

set -e

echo "=========================================="
echo "FXML4 Redesigned - Microservices Startup"
echo "=========================================="

# Check if .env exists
if [ ! -f .env ]; then
    echo "Creating .env from template..."
    cp .env.example .env
    echo "Please edit .env with your configuration before running again."
    exit 1
fi

# Load environment variables
set -a
source .env
set +a

# Function to check if service is healthy
check_health() {
    local service=$1
    local max_attempts=30
    local attempt=1

    echo "Waiting for $service to be healthy..."

    while [ $attempt -le $max_attempts ]; do
        if docker-compose ps $service | grep -q "healthy"; then
            echo "$service is healthy ✓"
            return 0
        fi

        echo "Attempt $attempt/$max_attempts - $service not ready yet..."
        sleep 2
        attempt=$((attempt + 1))
    done

    echo "ERROR: $service failed to become healthy"
    return 1
}

# Function to start infrastructure services
start_infrastructure() {
    echo ""
    echo "Starting infrastructure services..."
    echo "===================================="

    # Start infrastructure
    docker-compose up -d timescaledb rabbitmq redis

    # Wait for services to be healthy
    check_health timescaledb
    check_health rabbitmq
    check_health redis

    echo ""
    echo "Infrastructure services ready ✓"
}

# Function to start trading services
start_trading_services() {
    echo ""
    echo "Starting trading services..."
    echo "============================="

    # Start core trading services
    echo "Starting data collector..."
    docker-compose up -d data_collector
    check_health data_collector

    echo "Starting signal generator..."
    docker-compose up -d signal_generator
    # Note: signal_generator may not have health check initially

    echo "Starting LLM analyzer..."
    docker-compose up -d llm_analyzer

    echo "Starting entry manager..."
    docker-compose up -d entry_manager

    echo "Starting trade manager..."
    docker-compose up -d trade_manager

    echo "Starting monitor service..."
    docker-compose up -d monitor

    echo ""
    echo "Trading services started ✓"
}

# Function to display status
show_status() {
    echo ""
    echo "System Status"
    echo "============="
    docker-compose ps

    echo ""
    echo "Service Endpoints:"
    echo "=================="
    echo "Monitoring Dashboard: http://localhost:8080"
    echo "RabbitMQ Management:  http://localhost:15672 (admin/admin123)"
    echo "TimescaleDB:          postgresql://postgres:postgres@localhost:5434/fxml4_trading"
    echo "Redis:                redis://localhost:6379"

    echo ""
    echo "Useful Commands:"
    echo "================"
    echo "View logs:           docker-compose logs -f [service_name]"
    echo "Stop all services:   docker-compose down"
    echo "Restart service:     docker-compose restart [service_name]"
    echo "Check health:        docker-compose ps"
}

# Function to cleanup
cleanup() {
    echo ""
    echo "Cleaning up..."
    docker-compose down
    echo "Cleanup complete"
}

# Main execution
case "${1:-start}" in
    "start")
        start_infrastructure
        start_trading_services
        show_status
        ;;
    "stop")
        echo "Stopping all services..."
        docker-compose down
        echo "All services stopped"
        ;;
    "restart")
        echo "Restarting system..."
        docker-compose down
        start_infrastructure
        start_trading_services
        show_status
        ;;
    "status")
        show_status
        ;;
    "logs")
        if [ -n "$2" ]; then
            docker-compose logs -f "$2"
        else
            docker-compose logs -f
        fi
        ;;
    "clean")
        echo "WARNING: This will remove all containers, networks, and volumes!"
        read -p "Are you sure? (y/N): " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            docker-compose down -v --remove-orphans
            docker system prune -f
            echo "System cleaned"
        fi
        ;;
    "test")
        echo "Running system tests..."
        # Add test commands here
        python -c "
import asyncio
import sys
sys.path.append('.')
from shared.utils.base_service import ServiceConfig
config = ServiceConfig.from_env()
print('Configuration loaded successfully ✓')
print(f'Database: {config[\"db_host\"]}:{config[\"db_port\"]}')
print(f'RabbitMQ: {config[\"rabbitmq_host\"]}')
print(f'Redis: {config[\"redis_host\"]}:{config[\"redis_port\"]}')
"
        ;;
    *)
        echo "Usage: $0 {start|stop|restart|status|logs [service]|clean|test}"
        echo ""
        echo "Commands:"
        echo "  start    - Start all services"
        echo "  stop     - Stop all services"
        echo "  restart  - Restart all services"
        echo "  status   - Show service status"
        echo "  logs     - Show logs (optionally for specific service)"
        echo "  clean    - Remove all containers and volumes"
        echo "  test     - Test configuration"
        exit 1
        ;;
esac

echo ""
echo "Done!"
