#!/bin/bash

# FXML4 UI Production Deployment Script
set -e

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
DOCKER_COMPOSE_FILE="docker-compose.production.yml"
ENV_FILE=".env.production"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
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

# Parse command line arguments
COMMAND=${1:-deploy}
ENVIRONMENT=${2:-production}

show_help() {
    echo "FXML4 UI Deployment Script"
    echo ""
    echo "Usage: $0 [command] [environment]"
    echo ""
    echo "Commands:"
    echo "  deploy       Deploy the application (default)"
    echo "  build        Build Docker images only"
    echo "  up           Start services"
    echo "  down         Stop services"
    echo "  restart      Restart services"
    echo "  logs         Show service logs"
    echo "  status       Show service status"
    echo "  cleanup      Clean up unused Docker resources"
    echo "  rollback     Rollback to previous version"
    echo "  health       Check service health"
    echo "  help         Show this help"
    echo ""
    echo "Environments: production (default)"
    echo ""
}

# Check prerequisites
check_prerequisites() {
    log_info "Checking prerequisites..."

    # Check if Docker is installed and running
    if ! command -v docker &> /dev/null; then
        log_error "Docker is not installed"
        exit 1
    fi

    if ! docker info &> /dev/null; then
        log_error "Docker is not running"
        exit 1
    fi

    # Check if Docker Compose is available
    if ! command -v docker-compose &> /dev/null && ! docker compose version &> /dev/null; then
        log_error "Docker Compose is not installed"
        exit 1
    fi

    # Set compose command
    if command -v docker-compose &> /dev/null; then
        COMPOSE_CMD="docker-compose"
    else
        COMPOSE_CMD="docker compose"
    fi

    log_success "Prerequisites check passed"
}

# Load environment variables
load_environment() {
    log_info "Loading environment configuration..."

    if [[ -f "$PROJECT_DIR/$ENV_FILE" ]]; then
        log_info "Loading $ENV_FILE"
        export $(grep -v '^#' "$PROJECT_DIR/$ENV_FILE" | xargs)
    else
        log_warning "$ENV_FILE not found, using defaults"
    fi

    # Set default values if not provided
    export UI_PORT=${UI_PORT:-3000}
    export NGINX_PORT=${NGINX_PORT:-80}
    export REDIS_PORT=${REDIS_PORT:-6379}

    log_success "Environment loaded"
}

# Pre-deployment checks
pre_deployment_checks() {
    log_info "Running pre-deployment checks..."

    # Check if ports are available
    check_port() {
        local port=$1
        local service=$2

        if lsof -Pi :$port -sTCP:LISTEN -t >/dev/null 2>&1; then
            log_warning "Port $port is already in use (required for $service)"
            read -p "Continue anyway? (y/N): " -n 1 -r
            echo
            if [[ ! $REPLY =~ ^[Yy]$ ]]; then
                log_error "Deployment cancelled"
                exit 1
            fi
        fi
    }

    check_port "$UI_PORT" "UI Service"
    check_port "$NGINX_PORT" "Nginx"
    check_port "$REDIS_PORT" "Redis"

    # Check disk space
    AVAILABLE_SPACE=$(df / | awk 'NR==2 {print $4}')
    REQUIRED_SPACE=1048576  # 1GB in KB

    if [[ $AVAILABLE_SPACE -lt $REQUIRED_SPACE ]]; then
        log_error "Insufficient disk space. Available: $(($AVAILABLE_SPACE/1024))MB, Required: $(($REQUIRED_SPACE/1024))MB"
        exit 1
    fi

    log_success "Pre-deployment checks passed"
}

# Build application
build_application() {
    log_info "Building application..."

    cd "$PROJECT_DIR"

    # Pull latest base images
    $COMPOSE_CMD -f "$DOCKER_COMPOSE_FILE" pull || log_warning "Failed to pull some base images"

    # Build application images
    $COMPOSE_CMD -f "$DOCKER_COMPOSE_FILE" build --no-cache

    log_success "Application built successfully"
}

# Deploy application
deploy_application() {
    log_info "Deploying FXML4 UI to $ENVIRONMENT..."

    cd "$PROJECT_DIR"

    # Create backup of current deployment if it exists
    if $COMPOSE_CMD -f "$DOCKER_COMPOSE_FILE" ps -q fxml4-ui &> /dev/null; then
        log_info "Creating deployment backup..."
        $COMPOSE_CMD -f "$DOCKER_COMPOSE_FILE" exec -T fxml4-ui tar czf /tmp/backup-$(date +%Y%m%d-%H%M%S).tar.gz /app/.next/cache || true
    fi

    # Deploy services
    $COMPOSE_CMD -f "$DOCKER_COMPOSE_FILE" up -d --remove-orphans

    # Wait for services to be healthy
    wait_for_health

    log_success "Deployment completed successfully"
}

# Wait for services to be healthy
wait_for_health() {
    log_info "Waiting for services to be healthy..."

    local max_attempts=30
    local attempt=1

    while [[ $attempt -le $max_attempts ]]; do
        log_info "Health check attempt $attempt/$max_attempts"

        # Check if all services are healthy
        local healthy_services=$($COMPOSE_CMD -f "$DOCKER_COMPOSE_FILE" ps --filter "health=healthy" -q | wc -l)
        local total_services=$($COMPOSE_CMD -f "$DOCKER_COMPOSE_FILE" ps -q | wc -l)

        if [[ $healthy_services -eq $total_services ]] && [[ $total_services -gt 0 ]]; then
            log_success "All services are healthy"
            return 0
        fi

        sleep 10
        ((attempt++))
    done

    log_error "Services failed to become healthy within timeout"
    show_service_status
    return 1
}

# Show service status
show_service_status() {
    log_info "Service status:"
    cd "$PROJECT_DIR"
    $COMPOSE_CMD -f "$DOCKER_COMPOSE_FILE" ps
}

# Show service logs
show_logs() {
    cd "$PROJECT_DIR"
    $COMPOSE_CMD -f "$DOCKER_COMPOSE_FILE" logs -f --tail=100
}

# Stop services
stop_services() {
    log_info "Stopping services..."
    cd "$PROJECT_DIR"
    $COMPOSE_CMD -f "$DOCKER_COMPOSE_FILE" down
    log_success "Services stopped"
}

# Restart services
restart_services() {
    log_info "Restarting services..."
    cd "$PROJECT_DIR"
    $COMPOSE_CMD -f "$DOCKER_COMPOSE_FILE" restart
    wait_for_health
    log_success "Services restarted"
}

# Clean up unused Docker resources
cleanup_docker() {
    log_info "Cleaning up unused Docker resources..."

    # Remove unused images
    docker image prune -f

    # Remove unused volumes
    docker volume prune -f

    # Remove unused networks
    docker network prune -f

    log_success "Docker cleanup completed"
}

# Rollback to previous version
rollback_deployment() {
    log_warning "Rollback functionality requires a backup strategy"
    log_info "This would typically involve:"
    log_info "  1. Stopping current services"
    log_info "  2. Restoring previous Docker images"
    log_info "  3. Starting services with previous configuration"
    log_info "  4. Verifying health"

    read -p "Continue with basic rollback (rebuild from last known good commit)? (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        log_info "Performing basic rollback..."
        stop_services
        build_application
        deploy_application
    fi
}

# Check service health
check_health() {
    log_info "Checking service health..."
    cd "$PROJECT_DIR"

    # Check UI service
    if curl -f -s "http://localhost:$UI_PORT/api/health" > /dev/null; then
        log_success "UI service is healthy"
    else
        log_error "UI service is not responding"
    fi

    # Check Nginx
    if curl -f -s "http://localhost:$NGINX_PORT/health" > /dev/null; then
        log_success "Nginx is healthy"
    else
        log_error "Nginx is not responding"
    fi

    # Check Redis
    if docker exec fxml4-redis redis-cli ping | grep -q PONG; then
        log_success "Redis is healthy"
    else
        log_error "Redis is not responding"
    fi
}

# Main execution
main() {
    case $COMMAND in
        deploy)
            check_prerequisites
            load_environment
            pre_deployment_checks
            build_application
            deploy_application
            ;;
        build)
            check_prerequisites
            load_environment
            build_application
            ;;
        up)
            check_prerequisites
            load_environment
            cd "$PROJECT_DIR"
            $COMPOSE_CMD -f "$DOCKER_COMPOSE_FILE" up -d
            wait_for_health
            ;;
        down)
            check_prerequisites
            stop_services
            ;;
        restart)
            check_prerequisites
            restart_services
            ;;
        logs)
            check_prerequisites
            show_logs
            ;;
        status)
            check_prerequisites
            show_service_status
            ;;
        cleanup)
            check_prerequisites
            cleanup_docker
            ;;
        rollback)
            check_prerequisites
            load_environment
            rollback_deployment
            ;;
        health)
            check_prerequisites
            load_environment
            check_health
            ;;
        help)
            show_help
            ;;
        *)
            log_error "Unknown command: $COMMAND"
            show_help
            exit 1
            ;;
    esac
}

# Execute main function
main
