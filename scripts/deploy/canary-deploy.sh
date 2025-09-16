#!/bin/bash

# FXML4 Canary Deployment Script
# Gradual rollout with traffic splitting and automated rollback
# Financial trading system optimized with risk management

set -euo pipefail

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
DEPLOYMENT_LOG="/tmp/fxml4-canary-$(date +%Y%m%d-%H%M%S).log"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Configuration variables
ENVIRONMENT="${ENVIRONMENT:-production}"
IMAGE_TAG="${IMAGE_TAG:-latest}"
NAMESPACE="${NAMESPACE:-fxml4-prod}"
SERVICE="${SERVICE:-api}"  # Service to deploy

# Canary configuration
CANARY_STEPS="${CANARY_STEPS:-5,10,25,50,100}"  # Traffic percentage steps
STEP_DURATION="${STEP_DURATION:-300}"  # 5 minutes per step
ROLLBACK_THRESHOLD="${ROLLBACK_THRESHOLD:-5}"  # Error rate threshold (%)
LATENCY_THRESHOLD="${LATENCY_THRESHOLD:-10}"  # Latency threshold (ms)

# Metrics configuration
PROMETHEUS_URL="${PROMETHEUS_URL:-http://prometheus:9090}"
GRAFANA_URL="${GRAFANA_URL:-http://grafana:3000}"

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

# Market hours check for canary deployment
check_market_hours() {
    log_info "🏛️  Checking market hours for canary deployment..."

    local current_hour=$(TZ='America/New_York' date +%H)
    local current_day=$(date +%u)

    # More restrictive during market hours
    if [[ $current_day -ge 1 && $current_day -le 5 ]] && [[ $current_hour -ge 9 && $current_hour -lt 16 ]]; then
        if [[ "${EMERGENCY_DEPLOYMENT:-false}" != "true" ]]; then
            log_error "❌ Canary deployment blocked during market hours"
            log_error "Use EMERGENCY_DEPLOYMENT=true for emergency deployments"
            exit 1
        else
            log_warn "🚨 Emergency canary deployment during market hours"
            # Reduce canary traffic during market hours
            CANARY_STEPS="1,2,5,10,20"
            STEP_DURATION=600  # 10 minutes per step
            log_info "📊 Adjusted canary steps for market hours: $CANARY_STEPS"
        fi
    else
        log_success "✅ Outside market hours - normal canary deployment"
    fi
}

# Deploy canary version
deploy_canary() {
    local service="$1"
    local image_tag="$2"

    log_info "🚀 Deploying canary version of $service with tag $image_tag"

    # Create canary deployment
    kubectl apply -f - <<EOF
apiVersion: apps/v1
kind: Deployment
metadata:
  name: ${service}-canary
  namespace: ${NAMESPACE}
  labels:
    app: ${service}
    version: canary
    deployment-type: canary
spec:
  replicas: 1
  selector:
    matchLabels:
      app: ${service}
      version: canary
  template:
    metadata:
      labels:
        app: ${service}
        version: canary
        deployment-type: canary
    spec:
      containers:
      - name: ${service}
        image: ghcr.io/meridianp/fxml4-${service}:${image_tag}
        ports:
        - containerPort: 8000
        env:
        - name: DEPLOYMENT_TYPE
          value: "canary"
        - name: VERSION
          value: "${image_tag}"
        livenessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /ready
            port: 8000
          initialDelaySeconds: 10
          periodSeconds: 5
EOF

    # Wait for canary deployment to be ready
    log_info "⏳ Waiting for canary deployment to be ready..."
    if ! kubectl rollout status deployment/"${service}-canary" -n "$NAMESPACE" --timeout=300s; then
        log_error "❌ Canary deployment failed"
        return 1
    fi

    log_success "✅ Canary deployment ready"
}

# Update traffic split using Istio or NGINX Ingress
update_traffic_split() {
    local service="$1"
    local canary_weight="$2"
    local stable_weight=$((100 - canary_weight))

    log_info "🔄 Updating traffic split: ${stable_weight}% stable, ${canary_weight}% canary"

    # Update VirtualService for Istio (if using Istio)
    if kubectl get virtualservice "${service}" -n "$NAMESPACE" &>/dev/null; then
        kubectl apply -f - <<EOF
apiVersion: networking.istio.io/v1beta1
kind: VirtualService
metadata:
  name: ${service}
  namespace: ${NAMESPACE}
spec:
  hosts:
  - ${service}
  http:
  - match:
    - headers:
        canary:
          exact: "true"
    route:
    - destination:
        host: ${service}
        subset: canary
  - route:
    - destination:
        host: ${service}
        subset: stable
      weight: ${stable_weight}
    - destination:
        host: ${service}
        subset: canary
      weight: ${canary_weight}
EOF
    fi

    # Update NGINX Ingress annotations (if using NGINX)
    if kubectl get ingress "${service}" -n "$NAMESPACE" &>/dev/null; then
        kubectl annotate ingress "${service}" -n "$NAMESPACE" \
            nginx.ingress.kubernetes.io/canary-weight="${canary_weight}" --overwrite
    fi

    # Give time for traffic split to take effect
    sleep 30
}

# Get metrics from Prometheus
get_metrics() {
    local service="$1"
    local version="$2"
    local metric_name="$3"
    local duration="5m"

    # Query Prometheus for metrics
    local query="rate(${metric_name}{service=\"${service}\",version=\"${version}\"}[${duration}])"
    local encoded_query=$(python3 -c "import urllib.parse; print(urllib.parse.quote('$query'))")

    curl -s "${PROMETHEUS_URL}/api/v1/query?query=${encoded_query}" | \
        jq -r '.data.result[0].value[1] // "0"' 2>/dev/null || echo "0"
}

# Calculate error rate
get_error_rate() {
    local service="$1"
    local version="$2"

    local total_requests=$(get_metrics "$service" "$version" "http_requests_total")
    local error_requests=$(get_metrics "$service" "$version" "http_requests_total{status=~\"5.*\"}")

    if [[ "$total_requests" == "0" ]]; then
        echo "0"
    else
        echo "scale=2; $error_requests * 100 / $total_requests" | bc -l || echo "0"
    fi
}

# Calculate average latency
get_latency() {
    local service="$1"
    local version="$2"

    local latency=$(get_metrics "$service" "$version" "http_request_duration_seconds_sum")
    local count=$(get_metrics "$service" "$version" "http_request_duration_seconds_count")

    if [[ "$count" == "0" ]]; then
        echo "0"
    else
        echo "scale=2; $latency * 1000 / $count" | bc -l || echo "0"
    fi
}

# Monitor canary deployment
monitor_canary() {
    local service="$1"
    local duration="$2"

    log_info "📊 Monitoring canary deployment for ${duration} seconds..."

    local end_time=$(($(date +%s) + duration))

    while [[ $(date +%s) -lt $end_time ]]; do
        local stable_error_rate=$(get_error_rate "$service" "stable")
        local canary_error_rate=$(get_error_rate "$service" "canary")
        local stable_latency=$(get_latency "$service" "stable")
        local canary_latency=$(get_latency "$service" "canary")

        log_info "📈 Stable - Error Rate: ${stable_error_rate}%, Latency: ${stable_latency}ms"
        log_info "📈 Canary - Error Rate: ${canary_error_rate}%, Latency: ${canary_latency}ms"

        # Check error rate threshold
        if (( $(echo "$canary_error_rate > $ROLLBACK_THRESHOLD" | bc -l) )); then
            log_error "❌ Canary error rate (${canary_error_rate}%) exceeds threshold (${ROLLBACK_THRESHOLD}%)"
            return 1
        fi

        # Check latency threshold
        if (( $(echo "$canary_latency > $LATENCY_THRESHOLD" | bc -l) )); then
            log_error "❌ Canary latency (${canary_latency}ms) exceeds threshold (${LATENCY_THRESHOLD}ms)"
            return 1
        fi

        # Check for significant regression
        local error_diff=$(echo "$canary_error_rate - $stable_error_rate" | bc -l)
        local latency_diff=$(echo "$canary_latency - $stable_latency" | bc -l)

        if (( $(echo "$error_diff > 2" | bc -l) )); then
            log_warn "⚠️  Canary error rate significantly higher than stable"
        fi

        if (( $(echo "$latency_diff > 5" | bc -l) )); then
            log_warn "⚠️  Canary latency significantly higher than stable"
        fi

        sleep 30
    done

    log_success "✅ Monitoring period completed successfully"
    return 0
}

# Rollback canary deployment
rollback_canary() {
    local service="$1"

    log_warn "🔙 Rolling back canary deployment..."

    # Set traffic split to 100% stable
    update_traffic_split "$service" 0

    # Delete canary deployment
    kubectl delete deployment "${service}-canary" -n "$NAMESPACE" --ignore-not-found

    # Remove canary-related resources
    kubectl delete virtualservice "${service}" -n "$NAMESPACE" --ignore-not-found
    kubectl annotate ingress "${service}" -n "$NAMESPACE" \
        nginx.ingress.kubernetes.io/canary- --all

    log_success "✅ Canary rollback completed"
}

# Promote canary to stable
promote_canary() {
    local service="$1"
    local image_tag="$2"

    log_info "🎯 Promoting canary to stable..."

    # Update stable deployment with canary image
    kubectl set image deployment/"${service}" -n "$NAMESPACE" \
        "${service}=ghcr.io/meridianp/fxml4-${service}:${image_tag}"

    # Wait for stable deployment rollout
    if ! kubectl rollout status deployment/"${service}" -n "$NAMESPACE" --timeout=300s; then
        log_error "❌ Stable deployment update failed"
        return 1
    fi

    # Set traffic to 100% stable
    update_traffic_split "$service" 0

    # Clean up canary deployment
    kubectl delete deployment "${service}-canary" -n "$NAMESPACE"

    log_success "✅ Canary promoted to stable"
}

# Financial compliance check
financial_compliance_check() {
    local service="$1"

    log_info "🏦 Running financial compliance checks..."

    # Check for audit trail
    local audit_logs=$(kubectl logs -n "$NAMESPACE" -l app="$service",version="canary" --since=5m | grep -c "AUDIT" || echo "0")
    if [[ $audit_logs -lt 1 ]]; then
        log_warn "⚠️  No audit logs detected in canary deployment"
    fi

    # Check for regulatory compliance endpoints
    local compliance_endpoints=("/health" "/compliance" "/audit")
    for endpoint in "${compliance_endpoints[@]}"; do
        local pod=$(kubectl get pods -n "$NAMESPACE" -l app="$service",version="canary" -o jsonpath='{.items[0].metadata.name}')
        kubectl port-forward -n "$NAMESPACE" pod/"$pod" 8080:8000 &
        local pf_pid=$!
        sleep 2

        if curl -f -s "http://localhost:8080${endpoint}" &>/dev/null; then
            log_success "✅ Compliance endpoint ${endpoint} accessible"
        else
            log_warn "⚠️  Compliance endpoint ${endpoint} not accessible"
        fi

        kill $pf_pid 2>/dev/null || true
    done

    log_success "✅ Financial compliance checks completed"
}

# Main canary deployment function
main() {
    local service="${1:-$SERVICE}"
    local image_tag="${2:-$IMAGE_TAG}"

    log_info "🚀 Starting FXML4 Canary Deployment"
    log_info "Service: $service"
    log_info "Image Tag: $image_tag"
    log_info "Canary Steps: $CANARY_STEPS"

    # Check market hours
    check_market_hours

    # Deploy canary
    if ! deploy_canary "$service" "$image_tag"; then
        log_error "❌ Canary deployment failed"
        exit 1
    fi

    # Financial compliance check
    financial_compliance_check "$service"

    # Progressive traffic split
    IFS=',' read -ra STEPS <<< "$CANARY_STEPS"
    for step in "${STEPS[@]}"; do
        log_info "📊 Canary step: ${step}% traffic"

        # Update traffic split
        update_traffic_split "$service" "$step"

        # Monitor for step duration
        if ! monitor_canary "$service" "$STEP_DURATION"; then
            log_error "❌ Canary deployment failed at ${step}% traffic"
            rollback_canary "$service"
            exit 1
        fi

        log_success "✅ Step ${step}% completed successfully"
    done

    # Final validation before promotion
    log_info "🔍 Final validation before promotion..."
    if ! monitor_canary "$service" 300; then  # 5 minute final check
        log_error "❌ Final validation failed"
        rollback_canary "$service"
        exit 1
    fi

    # Promote canary to stable
    if ! promote_canary "$service" "$image_tag"; then
        log_error "❌ Canary promotion failed"
        rollback_canary "$service"
        exit 1
    fi

    log_success "🎉 Canary deployment completed successfully!"
    log_info "📋 Deployment log: $DEPLOYMENT_LOG"
}

# Signal handlers
trap 'log_error "❌ Canary deployment interrupted"; rollback_canary "$SERVICE"; exit 1' INT TERM

# Run main function
main "$@"
