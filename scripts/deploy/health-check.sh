#!/bin/bash

# FXML4 Production Health Check Script
# Usage: ./health-check.sh [environment] [timeout]
# Example: ./health-check.sh production 300

set -euo pipefail

# Configuration
ENVIRONMENT="${1:-production}"
TIMEOUT="${2:-180}"
RETRY_INTERVAL=5
MAX_RETRIES=$((TIMEOUT / RETRY_INTERVAL))

# Color codes for output
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

# Environment-specific URLs
case $ENVIRONMENT in
    "production")
        API_URL="https://api.fxml4.trading"
        UI_URL="https://app.fxml4.trading"
        WS_URL="https://ws.fxml4.trading"
        NAMESPACE="fxml4-production"
        ;;
    "staging")
        API_URL="https://staging-api.fxml4.trading"
        UI_URL="https://staging.fxml4.trading"
        WS_URL="https://staging-ws.fxml4.trading"
        NAMESPACE="fxml4-staging"
        ;;
    *)
        log_error "Unknown environment: $ENVIRONMENT"
        exit 1
        ;;
esac

log_info "Starting health checks for FXML4 $ENVIRONMENT environment"
log_info "Timeout: ${TIMEOUT}s, Max retries: ${MAX_RETRIES}"

# Function to check HTTP endpoint
check_http_endpoint() {
    local url=$1
    local expected_status=${2:-200}
    local description=$3

    log_info "Checking $description: $url"

    local retry_count=0
    while [ $retry_count -lt $MAX_RETRIES ]; do
        if response=$(curl -s -o /dev/null -w "%{http_code}" --max-time 10 "$url" 2>/dev/null); then
            if [ "$response" -eq "$expected_status" ]; then
                log_success "$description is healthy (HTTP $response)"
                return 0
            else
                log_warning "$description returned HTTP $response (expected $expected_status)"
            fi
        else
            log_warning "$description is unreachable (attempt $((retry_count + 1))/$MAX_RETRIES)"
        fi

        retry_count=$((retry_count + 1))
        if [ $retry_count -lt $MAX_RETRIES ]; then
            sleep $RETRY_INTERVAL
        fi
    done

    log_error "$description health check failed after $MAX_RETRIES attempts"
    return 1
}

# Function to check detailed API health
check_api_detailed() {
    local url="$API_URL/health"

    log_info "Performing detailed API health check"

    local retry_count=0
    while [ $retry_count -lt $MAX_RETRIES ]; do
        if health_response=$(curl -s --max-time 15 "$url" 2>/dev/null); then
            # Parse JSON response
            if echo "$health_response" | jq -e '.status == "healthy"' > /dev/null 2>&1; then
                log_success "API detailed health check passed"

                # Extract key metrics
                if database_status=$(echo "$health_response" | jq -r '.checks.database.status' 2>/dev/null); then
                    log_info "Database status: $database_status"
                fi

                if redis_status=$(echo "$health_response" | jq -r '.checks.redis.status' 2>/dev/null); then
                    log_info "Redis status: $redis_status"
                fi

                if rabbitmq_status=$(echo "$health_response" | jq -r '.checks.rabbitmq.status' 2>/dev/null); then
                    log_info "RabbitMQ status: $rabbitmq_status"
                fi

                return 0
            else
                log_warning "API health check returned unhealthy status"
            fi
        else
            log_warning "Failed to get API health response (attempt $((retry_count + 1))/$MAX_RETRIES)"
        fi

        retry_count=$((retry_count + 1))
        if [ $retry_count -lt $MAX_RETRIES ]; then
            sleep $RETRY_INTERVAL
        fi
    done

    log_error "API detailed health check failed"
    return 1
}

# Function to check Kubernetes deployment status
check_k8s_deployments() {
    if ! command -v kubectl &> /dev/null; then
        log_warning "kubectl not found, skipping Kubernetes health checks"
        return 0
    fi

    log_info "Checking Kubernetes deployment status"

    local deployments=("fxml4-api" "fxml4-ui" "fxml4-websocket")
    local all_healthy=true

    for deployment in "${deployments[@]}"; do
        log_info "Checking deployment: $deployment"

        if kubectl get deployment "$deployment" -n "$NAMESPACE" &>/dev/null; then
            # Check if deployment is ready
            if kubectl wait --for=condition=available deployment/"$deployment" -n "$NAMESPACE" --timeout=60s &>/dev/null; then
                # Get replica info
                local replicas_info
                replicas_info=$(kubectl get deployment "$deployment" -n "$NAMESPACE" -o jsonpath='{.status.readyReplicas}/{.spec.replicas}')
                log_success "$deployment is ready ($replicas_info replicas)"
            else
                log_error "$deployment is not ready"
                all_healthy=false
            fi
        else
            log_error "$deployment not found in namespace $NAMESPACE"
            all_healthy=false
        fi
    done

    if [ "$all_healthy" = true ]; then
        log_success "All Kubernetes deployments are healthy"
        return 0
    else
        log_error "Some Kubernetes deployments are unhealthy"
        return 1
    fi
}

# Function to check WebSocket connectivity
check_websocket() {
    local ws_url="$WS_URL/socket.io/?transport=polling"

    log_info "Checking WebSocket endpoint"

    if response=$(curl -s --max-time 10 "$ws_url" 2>/dev/null); then
        if echo "$response" | grep -q "socket.io"; then
            log_success "WebSocket endpoint is responding"
            return 0
        fi
    fi

    log_warning "WebSocket endpoint check failed"
    return 1
}

# Function to run performance checks
check_performance() {
    log_info "Running basic performance checks"

    local api_response_time
    api_response_time=$(curl -s -o /dev/null -w "%{time_total}" --max-time 5 "$API_URL/health" 2>/dev/null || echo "timeout")

    if [ "$api_response_time" != "timeout" ]; then
        if (( $(echo "$api_response_time < 2.0" | bc -l) )); then
            log_success "API response time: ${api_response_time}s (good)"
        else
            log_warning "API response time: ${api_response_time}s (slow)"
        fi
    else
        log_warning "API performance check timed out"
    fi

    local ui_response_time
    ui_response_time=$(curl -s -o /dev/null -w "%{time_total}" --max-time 10 "$UI_URL" 2>/dev/null || echo "timeout")

    if [ "$ui_response_time" != "timeout" ]; then
        if (( $(echo "$ui_response_time < 3.0" | bc -l) )); then
            log_success "UI response time: ${ui_response_time}s (good)"
        else
            log_warning "UI response time: ${ui_response_time}s (slow)"
        fi
    else
        log_warning "UI performance check timed out"
    fi
}

# Function to run trading system specific checks
check_trading_system() {
    log_info "Running trading system health checks"

    local trading_health_url="$API_URL/health/trading"

    if trading_response=$(curl -s --max-time 15 "$trading_health_url" 2>/dev/null); then
        if echo "$trading_response" | jq -e '.trading_enabled == true' > /dev/null 2>&1; then
            log_success "Trading system is enabled and healthy"

            # Check broker connections if available
            if broker_status=$(echo "$trading_response" | jq -r '.brokers // empty' 2>/dev/null); then
                log_info "Broker connections: $broker_status"
            fi
        else
            log_warning "Trading system is disabled or unhealthy"
        fi
    else
        log_warning "Unable to check trading system health"
    fi
}

# Main health check execution
main() {
    local overall_status=0

    echo "=================================================="
    echo "FXML4 Health Check - $ENVIRONMENT Environment"
    echo "Timestamp: $(date)"
    echo "=================================================="

    # Basic HTTP health checks
    check_http_endpoint "$API_URL/health" 200 "API Health Endpoint" || overall_status=1
    check_http_endpoint "$UI_URL/api/health" 200 "UI Health Endpoint" || overall_status=1
    check_http_endpoint "$WS_URL/health" 200 "WebSocket Health Endpoint" || overall_status=1

    # Detailed API health check
    check_api_detailed || overall_status=1

    # Kubernetes deployment checks
    check_k8s_deployments || overall_status=1

    # WebSocket connectivity
    check_websocket || overall_status=1

    # Performance checks
    check_performance

    # Trading system specific checks
    check_trading_system

    echo "=================================================="

    if [ $overall_status -eq 0 ]; then
        log_success "All health checks passed successfully!"
        echo "FXML4 $ENVIRONMENT environment is healthy and ready for trading."
    else
        log_error "Some health checks failed!"
        echo "FXML4 $ENVIRONMENT environment has issues that need attention."
    fi

    echo "=================================================="

    exit $overall_status
}

# Check for required dependencies
if ! command -v curl &> /dev/null; then
    log_error "curl is required but not installed"
    exit 1
fi

if ! command -v jq &> /dev/null; then
    log_warning "jq not found, JSON parsing will be limited"
fi

if ! command -v bc &> /dev/null; then
    log_warning "bc not found, performance calculations will be limited"
fi

# Run main function
main "$@"
