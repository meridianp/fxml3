#!/bin/bash

# FXML4 Local Development Deployment Script
set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Set compose command
if command -v docker-compose >/dev/null 2>&1; then
    COMPOSE_CMD="docker-compose"
else
    COMPOSE_CMD="docker compose"
fi

# Check if .env exists, if not copy from template
if [ ! -f .env ]; then
    print_status "Creating .env file from template..."
    cp .env .env.backup 2>/dev/null || true
    cat > .env << 'EOF'
# FXML4 Local Development Environment
FXML4_ENV=development
FXML4_API_HOST=0.0.0.0
FXML4_API_PORT=8000
FXML4_API_DEBUG=true
FXML4_API_ENABLE_DOCS=true

FXML4_UI_HOST=0.0.0.0
FXML4_UI_PORT=8501

# Database configuration
FXML4_DATABASE_TYPE=postgresql
FXML4_DATABASE_HOST=db
FXML4_DATABASE_PORT=5432
FXML4_DATABASE_NAME=fxml4
FXML4_DATABASE_USER=postgres
FXML4_DATABASE_PASSWORD=postgres

# Redis configuration
FXML4_REDIS_HOST=redis
FXML4_REDIS_PORT=6379
FXML4_REDIS_PASSWORD=

# RabbitMQ configuration
RABBITMQ_HOST=rabbitmq
RABBITMQ_PORT=5672
RABBITMQ_USERNAME=admin
RABBITMQ_PASSWORD=admin

# Security configuration
FXML4_JWT_SECRET_KEY=dev-secret-key-32-characters-long
FXML4_JWT_TOKEN_EXPIRE_MINUTES=60

# Logging configuration
FXML4_LOG_LEVEL=DEBUG
FXML4_LOG_FILE=logs/fxml4.log

# Test API keys (replace with real ones for testing)
POLYGON_API_KEY=test-polygon-key
ALPHA_VANTAGE_API_KEY=test-alpha-vantage-key
OPENAI_API_KEY=test-openai-key
ANTHROPIC_API_KEY=test-anthropic-key

# Conservative trading parameters for development
FOREX_MIN_POSITION_SIZE=25000
FOREX_ACCOUNT_LEVERAGE=10
FOREX_MAX_RISK_PER_TRADE=0.01
FOREX_MAX_POSITIONS=3

# Docker compose database passwords
POSTGRES_DB=fxml4
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres

# Monitoring
GRAFANA_PASSWORD=admin
EOF
    print_success ".env file created with development defaults"
fi

# Create directories
print_status "Creating necessary directories..."
mkdir -p data/{cache,features,historical,processed}
mkdir -p models/{EURUSD,GBPUSD,USDCHF,USDJPY}
mkdir -p logs config
mkdir -p monitoring

# Create basic monitoring config
mkdir -p monitoring
cat > monitoring/prometheus.yml << 'EOF'
global:
  scrape_interval: 15s

scrape_configs:
  - job_name: 'fxml4-api'
    static_configs:
      - targets: ['api:8000']
    scrape_interval: 5s
    metrics_path: /metrics

  - job_name: 'prometheus'
    static_configs:
      - targets: ['localhost:9090']
EOF

# Handle command line arguments
case "${1:-start}" in
    start)
        print_status "Starting FXML4 local development environment..."
        $COMPOSE_CMD -f docker-compose.local.yml up -d --build

        print_status "Waiting for services to start..."
        sleep 10

        print_success "FXML4 development environment started!"
        print_status "Access URLs:"
        echo "  API: http://localhost:8000"
        echo "  API Docs: http://localhost:8000/docs"
        echo "  Dashboard: http://localhost:8501"
        echo "  Grafana: http://localhost:3000 (admin/admin)"
        echo "  Prometheus: http://localhost:9090"
        echo "  RabbitMQ: http://localhost:15672 (admin/admin)"
        ;;
    stop)
        print_status "Stopping services..."
        $COMPOSE_CMD -f docker-compose.local.yml down
        print_success "Services stopped"
        ;;
    restart)
        print_status "Restarting services..."
        $COMPOSE_CMD -f docker-compose.local.yml restart
        print_success "Services restarted"
        ;;
    logs)
        $COMPOSE_CMD -f docker-compose.local.yml logs -f
        ;;
    status)
        print_status "Service Status:"
        $COMPOSE_CMD -f docker-compose.local.yml ps
        ;;
    clean)
        print_status "Cleaning up containers and volumes..."
        $COMPOSE_CMD -f docker-compose.local.yml down -v --remove-orphans
        docker system prune -f
        print_success "Cleanup completed"
        ;;
    build)
        print_status "Building services..."
        $COMPOSE_CMD -f docker-compose.local.yml build --no-cache
        print_success "Build completed"
        ;;
    *)
        echo "Usage: $0 {start|stop|restart|logs|status|clean|build}"
        echo ""
        echo "Commands:"
        echo "  start   - Start the development environment"
        echo "  stop    - Stop all services"
        echo "  restart - Restart all services"
        echo "  logs    - View logs from all services"
        echo "  status  - Show service status"
        echo "  clean   - Clean up containers and volumes"
        echo "  build   - Rebuild all services"
        exit 1
        ;;
esac
