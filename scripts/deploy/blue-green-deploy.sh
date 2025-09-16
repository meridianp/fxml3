#!/bin/bash

# FXML4 Blue-Green Deployment Script
# Provides zero-downtime deployment for financial trading system
# Supports market hours awareness and emergency rollback

set -euo pipefail

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
DEPLOYMENT_LOG="/tmp/fxml4-deployment-$(date +%Y%m%d-%H%M%S).log"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration variables
ENVIRONMENT="${ENVIRONMENT:-production}"
IMAGE_TAG="${IMAGE_TAG:-latest}"
NAMESPACE="${NAMESPACE:-fxml4-prod}"
HEALTH_CHECK_TIMEOUT="${HEALTH_CHECK_TIMEOUT:-300}"
ROLLBACK_TIMEOUT="${ROLLBACK_TIMEOUT:-120}"

# Service configurations
declare -A SERVICES=(
    ["api"]="8000"
    ["dashboard"]="8501"
    ["frontend"]="3000"
    ["worker"]="N/A"
)

# Logging function
log() {
    local level="$1"
    shift
    local message="$*"
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    echo -e "${timestamp} [${level}] ${message}" | tee -a "$DEPLOYMENT_LOG"
}

log_info() { log "INFO" "$@"; }
log_warn() { log "WARN" "$@"; }
log_error() { log "ERROR" "$@"; }
log_success() { log "SUCCESS" "$@"; }

# Market hours check
check_market_hours() {
    log_info "🏛️  Checking market hours..."

    local current_hour=$(TZ='America/New_York' date +%H)
    local current_day=$(date +%u)  # 1=Monday, 7=Sunday
    local current_time=$(TZ='America/New_York' date +%H:%M)

    # Market is open Monday-Friday, 9:30 AM - 4:00 PM ET
    if [[ $current_day -ge 1 && $current_day -le 5 ]] && [[ $current_hour -ge 9 && $current_hour -lt 16 ]]; then
        if [[ "${EMERGENCY_DEPLOYMENT:-false}" != "true" ]]; then
            log_error "❌ Deployment blocked: Market hours detected (${current_time} ET)"
            log_error "Use EMERGENCY_DEPLOYMENT=true for emergency deployments"
            exit 1
        else
            log_warn "🚨 Emergency deployment during market hours authorized"
        fi
    else
        log_success "✅ Outside market hours - deployment allowed"
    fi
}

# Pre-deployment validation
pre_deployment_checks() {
    log_info "🔍 Running pre-deployment checks..."

    # Check if kubectl is available
    if ! command -v kubectl &> /dev/null; then
        log_error "❌ kubectl not found"
        exit 1
    fi

    # Check cluster connectivity
    if ! kubectl cluster-info &> /dev/null; then
        log_error "❌ Cannot connect to Kubernetes cluster"
        exit 1
    fi

    # Check namespace exists
    if ! kubectl get namespace "$NAMESPACE" &> /dev/null; then
        log_error "❌ Namespace $NAMESPACE does not exist"
        exit 1
    fi

    # Check if images exist
    for service in "${!SERVICES[@]}"; do
        local image="ghcr.io/meridianp/fxml4-${service}:${IMAGE_TAG}"
        log_info "Checking image: $image"
        if ! docker manifest inspect "$image" &> /dev/null; then
            log_error "❌ Image not found: $image"
            exit 1
        fi
    done

    log_success "✅ Pre-deployment checks passed"
}

# Get current deployment color
get_current_color() {
    local service="$1"
    local current_deployment=$(kubectl get deployment -n "$NAMESPACE" -l app="$service",active=true -o jsonpath='{.items[0].metadata.labels.color}' 2>/dev/null || echo "")

    if [[ -z "$current_deployment" ]]; then
        echo "blue"  # Default to blue if no active deployment
    else
        echo "$current_deployment"
    fi
}

# Get next deployment color
get_next_color() {
    local current_color="$1"
    if [[ "$current_color" == "blue" ]]; then
        echo "green"
    else
        echo "blue"
    fi
}

# Deploy service to specific color
deploy_service() {
    local service="$1"
    local color="$2"
    local port="${SERVICES[$service]}"

    log_info "🚀 Deploying $service to $color environment..."

    # Update deployment with new image and color
    kubectl patch deployment "$service-$color" -n "$NAMESPACE" -p '{
        "spec": {
            "template": {
                "spec": {
                    "containers": [{
                        "name": "'$service'",
                        "image": "ghcr.io/meridianp/fxml4-'$service':'$IMAGE_TAG'"
                    }]
                },
                "metadata": {
                    "labels": {
                        "version": "'$IMAGE_TAG'",
                        "deployment-time": "'$(date +%s)'"
                    }
                }
            }
        }
    }'

    # Wait for deployment to be ready
    log_info "⏳ Waiting for $service-$color deployment to be ready..."
    if ! kubectl rollout status deployment/"$service-$color" -n "$NAMESPACE" --timeout="${HEALTH_CHECK_TIMEOUT}s"; then
        log_error "❌ Deployment $service-$color failed to become ready"
        return 1
    fi

    log_success "✅ $service-$color deployment ready"
}

# Health check for service
health_check_service() {
    local service="$1"
    local color="$2"
    local port="${SERVICES[$service]}"

    if [[ "$port" == "N/A" ]]; then
        log_info "ℹ️  Skipping health check for $service (no HTTP endpoint)"
        return 0
    fi

    log_info "🔍 Health checking $service-$color..."

    # Get pod name
    local pod=$(kubectl get pods -n "$NAMESPACE" -l app="$service",color="$color" -o jsonpath='{.items[0].metadata.name}' 2>/dev/null || echo "")

    if [[ -z "$pod" ]]; then
        log_error "❌ No pods found for $service-$color"
        return 1
    fi

    # Port forward for health check
    local local_port=$((port + 1000))
    kubectl port-forward -n "$NAMESPACE" pod/"$pod" "$local_port:$port" &
    local port_forward_pid=$!

    # Wait for port forward to establish
    sleep 5

    # Health check with retries
    local retries=30
    local success=false

    for ((i=1; i<=retries; i++)); do
        if curl -f -s "http://localhost:$local_port/health" &> /dev/null; then
            log_success "✅ $service-$color health check passed"
            success=true
            break
        else
            log_info "⏳ Health check attempt $i/$retries for $service-$color..."
            sleep 10
        fi
    done

    # Cleanup port forward
    kill $port_forward_pid 2>/dev/null || true

    if [[ "$success" != "true" ]]; then
        log_error "❌ Health check failed for $service-$color"
        return 1
    fi

    return 0
}

# Switch traffic to new color
switch_traffic() {
    local service="$1"
    local new_color="$2"
    local old_color="$3"

    log_info "🔄 Switching traffic for $service from $old_color to $new_color..."

    # Update service selector to point to new color
    kubectl patch service "$service" -n "$NAMESPACE" -p '{
        "spec": {
            "selector": {
                "color": "'$new_color'"
            }
        }
    }'

    # Update active labels
    kubectl label deployment "$service-$new_color" -n "$NAMESPACE" active=true --overwrite
    kubectl label deployment "$service-$old_color" -n "$NAMESPACE" active=false --overwrite

    log_success "✅ Traffic switched for $service"
}

# Validate deployment after traffic switch
validate_deployment() {
    local service="$1"
    local color="$2"

    log_info "🔍 Validating $service deployment..."

    # Check if service is responding
    if ! health_check_service "$service" "$color"; then
        log_error "❌ Post-deployment validation failed for $service"
        return 1
    fi

    # Check for any error logs
    local pod=$(kubectl get pods -n "$NAMESPACE" -l app="$service",color="$color" -o jsonpath='{.items[0].metadata.name}')
    local error_count=$(kubectl logs -n "$NAMESPACE" "$pod" --since=2m | grep -i error | wc -l || echo "0")

    if [[ $error_count -gt 5 ]]; then
        log_warn "⚠️  High error count ($error_count) detected in $service logs"
    fi

    log_success "✅ $service deployment validated"
}

# Rollback deployment
rollback_deployment() {
    local service="$1"
    local rollback_color="$2"
    local failed_color="$3"

    log_warn "🔙 Rolling back $service from $failed_color to $rollback_color..."

    # Switch traffic back
    switch_traffic "$service" "$rollback_color" "$failed_color"

    # Scale down failed deployment
    kubectl scale deployment "$service-$failed_color" -n "$NAMESPACE" --replicas=0

    log_success "✅ Rollback completed for $service"
}

# Performance test after deployment
performance_test() {
    local service="$1"
    local port="${SERVICES[$service]}"

    if [[ "$port" == "N/A" ]]; then
        return 0
    fi

    log_info "⚡ Running performance test for $service..."

    # Get service endpoint
    local service_ip=$(kubectl get service "$service" -n "$NAMESPACE" -o jsonpath='{.status.loadBalancer.ingress[0].ip}' 2>/dev/null || echo "localhost")

    # Simple latency test
    local latency=$(curl -w "%{time_total}" -s -o /dev/null "http://$service_ip:$port/health" || echo "999")
    local latency_ms=$(echo "$latency * 1000" | bc -l 2>/dev/null || echo "999")

    log_info "📊 $service latency: ${latency_ms}ms"

    # Check against SLA (5ms for production)
    if (( $(echo "$latency_ms > 5" | bc -l) )); then
        log_warn "⚠️  $service latency (${latency_ms}ms) exceeds SLA (5ms)"
    else
        log_success "✅ $service performance within SLA"
    fi
}

# Main deployment function
main() {
    log_info "🚀 Starting FXML4 Blue-Green Deployment"
    log_info "Environment: $ENVIRONMENT"
    log_info "Image Tag: $IMAGE_TAG"
    log_info "Namespace: $NAMESPACE"

    # Check market hours
    check_market_hours

    # Pre-deployment checks
    pre_deployment_checks

    # Store original deployment state for rollback
    declare -A original_colors
    declare -A new_colors

    for service in "${!SERVICES[@]}"; do
        original_colors[$service]=$(get_current_color "$service")
        new_colors[$service]=$(get_next_color "${original_colors[$service]}")
        log_info "📋 $service: ${original_colors[$service]} -> ${new_colors[$service]}"
    done

    # Deploy all services to new color
    local deployment_failed=false
    for service in "${!SERVICES[@]}"; do
        if ! deploy_service "$service" "${new_colors[$service]}"; then
            deployment_failed=true
            break
        fi
    done

    if [[ "$deployment_failed" == "true" ]]; then
        log_error "❌ Deployment failed, stopping..."
        exit 1
    fi

    # Health check all services
    local health_check_failed=false
    for service in "${!SERVICES[@]}"; do
        if ! health_check_service "$service" "${new_colors[$service]}"; then
            health_check_failed=true
            break
        fi
    done

    if [[ "$health_check_failed" == "true" ]]; then
        log_error "❌ Health checks failed, rolling back..."
        for service in "${!SERVICES[@]}"; do
            rollback_deployment "$service" "${original_colors[$service]}" "${new_colors[$service]}"
        done
        exit 1
    fi

    # Switch traffic for all services
    for service in "${!SERVICES[@]}"; do
        switch_traffic "$service" "${new_colors[$service]}" "${original_colors[$service]}"
    done

    # Monitor for 2 minutes
    log_info "📊 Monitoring deployment for 2 minutes..."
    sleep 120

    # Final validation
    local validation_failed=false
    for service in "${!SERVICES[@]}"; do
        if ! validate_deployment "$service" "${new_colors[$service]}"; then
            validation_failed=true
            break
        fi
    done

    if [[ "$validation_failed" == "true" ]]; then
        log_error "❌ Validation failed, rolling back..."
        for service in "${!SERVICES[@]}"; do
            rollback_deployment "$service" "${original_colors[$service]}" "${new_colors[$service]}"
        done
        exit 1
    fi

    # Performance testing
    for service in "${!SERVICES[@]}"; do
        performance_test "$service"
    done

    # Scale down old deployments
    for service in "${!SERVICES[@]}"; do
        log_info "🔽 Scaling down old deployment $service-${original_colors[$service]}"
        kubectl scale deployment "$service-${original_colors[$service]}" -n "$NAMESPACE" --replicas=0
    done

    log_success "🎉 Blue-Green deployment completed successfully!"
    log_info "📋 Deployment log: $DEPLOYMENT_LOG"
}

# Signal handlers for graceful shutdown
trap 'log_error "❌ Deployment interrupted"; exit 1' INT TERM

# Run main function
main "$@"
