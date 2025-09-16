#!/bin/bash

# FXML4 UI Production Health Check Script
set -e

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

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

# Configuration
HEALTH_CHECK_URL=${HEALTH_CHECK_URL:-"http://localhost:3000/api/health"}
TIMEOUT=${TIMEOUT:-10}
MAX_RETRIES=${MAX_RETRIES:-3}
RETRY_DELAY=${RETRY_DELAY:-5}

# Health check results
HEALTH_STATUS="unknown"
RESPONSE_TIME=0
ERROR_MESSAGE=""

# Perform health check
perform_health_check() {
    local url=$1
    local timeout=${2:-10}

    log_info "Checking health endpoint: $url"

    local start_time=$(date +%s.%N)

    if response=$(curl -s -f -m "$timeout" "$url" 2>&1); then
        local end_time=$(date +%s.%N)
        RESPONSE_TIME=$(echo "$end_time - $start_time" | bc -l)

        # Parse response if JSON
        if echo "$response" | jq . >/dev/null 2>&1; then
            local status=$(echo "$response" | jq -r '.status // "unknown"')
            local message=$(echo "$response" | jq -r '.message // ""')

            if [[ "$status" == "healthy" || "$status" == "ok" ]]; then
                HEALTH_STATUS="healthy"
                log_success "Service is healthy (${RESPONSE_TIME}s)"
                if [[ -n "$message" ]]; then
                    log_info "Message: $message"
                fi
                return 0
            else
                HEALTH_STATUS="unhealthy"
                ERROR_MESSAGE="Service reported status: $status"
                log_error "$ERROR_MESSAGE"
                return 1
            fi
        else
            # Non-JSON response, check if it contains "healthy" or similar
            if echo "$response" | grep -iq "healthy\|ok\|running"; then
                HEALTH_STATUS="healthy"
                log_success "Service is healthy (${RESPONSE_TIME}s)"
                return 0
            else
                HEALTH_STATUS="unhealthy"
                ERROR_MESSAGE="Unexpected response: $response"
                log_error "$ERROR_MESSAGE"
                return 1
            fi
        fi
    else
        local end_time=$(date +%s.%N)
        RESPONSE_TIME=$(echo "$end_time - $start_time" | bc -l)
        HEALTH_STATUS="unreachable"
        ERROR_MESSAGE="Health check failed: $response"
        log_error "$ERROR_MESSAGE"
        return 1
    fi
}

# Check service dependencies
check_dependencies() {
    log_info "Checking service dependencies..."

    local all_healthy=true

    # Check Redis (if configured)
    if [[ -n "${REDIS_URL}" ]]; then
        log_info "Checking Redis connectivity..."
        if command -v redis-cli >/dev/null 2>&1; then
            if redis-cli -u "$REDIS_URL" ping >/dev/null 2>&1; then
                log_success "Redis is responsive"
            else
                log_error "Redis is not responding"
                all_healthy=false
            fi
        else
            log_warning "redis-cli not available, skipping Redis check"
        fi
    fi

    # Check external API endpoints
    if [[ -n "${NEXT_PUBLIC_API_URL}" ]]; then
        log_info "Checking API connectivity..."
        local api_health_url="${NEXT_PUBLIC_API_URL}/health"

        if curl -s -f -m 5 "$api_health_url" >/dev/null 2>&1; then
            log_success "API is responsive"
        else
            log_error "API is not responding"
            all_healthy=false
        fi
    fi

    if $all_healthy; then
        log_success "All dependencies are healthy"
        return 0
    else
        log_error "Some dependencies are unhealthy"
        return 1
    fi
}

# Check system resources
check_system_resources() {
    log_info "Checking system resources..."

    # Memory usage
    if command -v free >/dev/null 2>&1; then
        local memory_usage=$(free | awk 'NR==2{printf "%.1f", $3*100/$2}')
        log_info "Memory usage: ${memory_usage}%"

        if (( $(echo "$memory_usage > 90" | bc -l) )); then
            log_warning "High memory usage detected"
        fi
    fi

    # Disk usage
    if command -v df >/dev/null 2>&1; then
        local disk_usage=$(df / | awk 'NR==2{print $5}' | sed 's/%//')
        log_info "Disk usage: ${disk_usage}%"

        if (( disk_usage > 85 )); then
            log_warning "High disk usage detected"
        fi
    fi

    # CPU load (if available)
    if command -v uptime >/dev/null 2>&1; then
        local load_avg=$(uptime | awk -F'load average:' '{print $2}' | awk '{print $1}' | sed 's/,//')
        log_info "Load average: $load_avg"
    fi
}

# Check Docker containers (if running in Docker)
check_docker_containers() {
    if command -v docker >/dev/null 2>&1 && docker info >/dev/null 2>&1; then
        log_info "Checking Docker containers..."

        # Check if fxml4-ui container is running
        if docker ps --filter "name=fxml4-ui" --format "table {{.Names}}\t{{.Status}}" | grep -q "fxml4-ui"; then
            local container_status=$(docker ps --filter "name=fxml4-ui" --format "{{.Status}}")
            log_success "FXML4 UI container is running: $container_status"

            # Check container resource usage
            local container_stats=$(docker stats --no-stream --format "table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}" fxml4-ui-prod 2>/dev/null || echo "N/A")
            if [[ "$container_stats" != "N/A" ]]; then
                log_info "Container stats: $container_stats"
            fi
        else
            log_error "FXML4 UI container is not running"
            return 1
        fi

        # Check other related containers
        for container in "fxml4-nginx" "fxml4-redis"; do
            if docker ps --filter "name=$container" --format "{{.Names}}" | grep -q "$container"; then
                log_success "$container container is running"
            else
                log_warning "$container container is not running"
            fi
        done
    else
        log_info "Docker not available or not running, skipping container checks"
    fi
}

# Check Kubernetes pods (if running in K8s)
check_kubernetes_pods() {
    if command -v kubectl >/dev/null 2>&1; then
        log_info "Checking Kubernetes pods..."

        # Check if we can connect to cluster
        if kubectl cluster-info >/dev/null 2>&1; then
            # Check FXML4 UI pods
            local pod_status=$(kubectl get pods -n fxml4-ui -l app.kubernetes.io/name=fxml4-ui --no-headers 2>/dev/null || echo "")

            if [[ -n "$pod_status" ]]; then
                log_info "FXML4 UI pods status:"
                echo "$pod_status" | while read -r line; do
                    local pod_name=$(echo "$line" | awk '{print $1}')
                    local ready=$(echo "$line" | awk '{print $2}')
                    local status=$(echo "$line" | awk '{print $3}')

                    if [[ "$status" == "Running" ]]; then
                        log_success "Pod $pod_name: $status ($ready)"
                    else
                        log_error "Pod $pod_name: $status ($ready)"
                    fi
                done
            else
                log_warning "No FXML4 UI pods found in cluster"
            fi
        else
            log_info "Cannot connect to Kubernetes cluster, skipping pod checks"
        fi
    else
        log_info "kubectl not available, skipping Kubernetes checks"
    fi
}

# Comprehensive health check
comprehensive_health_check() {
    log_info "Starting comprehensive health check..."
    echo "========================================"

    local overall_status=0

    # Primary health check with retries
    local retry_count=0
    while [[ $retry_count -lt $MAX_RETRIES ]]; do
        if perform_health_check "$HEALTH_CHECK_URL" "$TIMEOUT"; then
            break
        else
            retry_count=$((retry_count + 1))
            if [[ $retry_count -lt $MAX_RETRIES ]]; then
                log_warning "Health check failed, retrying in ${RETRY_DELAY}s (attempt $retry_count/$MAX_RETRIES)"
                sleep "$RETRY_DELAY"
            else
                log_error "Health check failed after $MAX_RETRIES attempts"
                overall_status=1
            fi
        fi
    done

    # Dependency checks
    if ! check_dependencies; then
        overall_status=1
    fi

    # System resource checks
    check_system_resources

    # Container/Pod checks
    check_docker_containers || check_kubernetes_pods

    echo "========================================"

    # Final status
    if [[ $overall_status -eq 0 ]]; then
        log_success "Overall health check: PASSED"

        # Output summary
        echo ""
        echo "Health Check Summary:"
        echo "- Status: $HEALTH_STATUS"
        echo "- Response Time: ${RESPONSE_TIME}s"
        echo "- URL: $HEALTH_CHECK_URL"
        echo "- Timestamp: $(date -Iseconds)"

    else
        log_error "Overall health check: FAILED"

        # Output error details
        echo ""
        echo "Health Check Summary:"
        echo "- Status: $HEALTH_STATUS"
        echo "- Error: $ERROR_MESSAGE"
        echo "- URL: $HEALTH_CHECK_URL"
        echo "- Timestamp: $(date -Iseconds)"
    fi

    return $overall_status
}

# Generate health report
generate_health_report() {
    local report_file="${1:-health-report.json}"

    log_info "Generating health report: $report_file"

    cat > "$report_file" << EOF
{
  "timestamp": "$(date -Iseconds)",
  "health_check": {
    "url": "$HEALTH_CHECK_URL",
    "status": "$HEALTH_STATUS",
    "response_time": $RESPONSE_TIME,
    "error_message": "$ERROR_MESSAGE"
  },
  "system": {
    "hostname": "$(hostname)",
    "uptime": "$(uptime -p 2>/dev/null || echo 'unknown')",
    "load_average": "$(uptime | awk -F'load average:' '{print $2}' | xargs)"
  },
  "environment": {
    "node_env": "${NODE_ENV:-unknown}",
    "port": "${PORT:-3000}",
    "api_url": "${NEXT_PUBLIC_API_URL:-unknown}"
  }
}
EOF

    log_success "Health report generated: $report_file"
}

# Main execution
main() {
    case "${1:-check}" in
        check)
            comprehensive_health_check
            ;;
        report)
            comprehensive_health_check
            generate_health_report "${2:-health-report.json}"
            ;;
        quick)
            perform_health_check "$HEALTH_CHECK_URL" "$TIMEOUT"
            ;;
        deps|dependencies)
            check_dependencies
            ;;
        resources)
            check_system_resources
            ;;
        containers)
            check_docker_containers
            ;;
        pods)
            check_kubernetes_pods
            ;;
        help)
            echo "FXML4 UI Production Health Check Script"
            echo ""
            echo "Usage: $0 [command]"
            echo ""
            echo "Commands:"
            echo "  check        Full health check (default)"
            echo "  report       Full health check + generate JSON report"
            echo "  quick        Quick health endpoint check only"
            echo "  deps         Check dependencies only"
            echo "  resources    Check system resources only"
            echo "  containers   Check Docker containers only"
            echo "  pods         Check Kubernetes pods only"
            echo "  help         Show this help"
            echo ""
            echo "Environment Variables:"
            echo "  HEALTH_CHECK_URL    Health endpoint URL (default: http://localhost:3000/api/health)"
            echo "  TIMEOUT             Request timeout in seconds (default: 10)"
            echo "  MAX_RETRIES         Maximum retry attempts (default: 3)"
            echo "  RETRY_DELAY         Delay between retries in seconds (default: 5)"
            ;;
        *)
            log_error "Unknown command: $1"
            echo "Use '$0 help' for usage information"
            exit 1
            ;;
    esac
}

# Load environment if available
if [[ -f "$PROJECT_DIR/.env.production" ]]; then
    source "$PROJECT_DIR/.env.production"
fi

# Execute main function
main "$@"
