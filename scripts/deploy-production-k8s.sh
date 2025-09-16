#!/bin/bash
# FTML4 Production Kubernetes Deployment Script
# This script orchestrates the complete deployment of FXML4 to production Kubernetes

set -e

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
NAMESPACE="fxml4"
DEPLOYMENT_TIMEOUT="900s"
EXTERNAL_DB_HOST="postgres01.tailb381ec.ts.net"
EXTERNAL_DB_PORT="5432"
IMAGE_TAG="${IMAGE_TAG:-latest}"
KUBE_CONTEXT="${KUBE_CONTEXT:-}"
DRY_RUN="${DRY_RUN:-false}"

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

# Function to check prerequisites
check_prerequisites() {
    log_info "Checking prerequisites..."

    # Check kubectl
    if ! command -v kubectl &> /dev/null; then
        log_error "kubectl is not installed"
        exit 1
    fi

    # Check jq
    if ! command -v jq &> /dev/null; then
        log_error "jq is not installed"
        exit 1
    fi

    # Check curl
    if ! command -v curl &> /dev/null; then
        log_error "curl is not installed"
        exit 1
    fi

    # Check kubectl context
    if [ -n "$KUBE_CONTEXT" ]; then
        kubectl config use-context "$KUBE_CONTEXT"
        log_info "Using Kubernetes context: $KUBE_CONTEXT"
    fi

    # Verify cluster access
    if ! kubectl cluster-info &> /dev/null; then
        log_error "Unable to connect to Kubernetes cluster"
        exit 1
    fi

    # Check external database connectivity
    log_info "Checking external database connectivity..."
    if ! kubectl run db-check-temp --rm -i --restart=Never --image=postgres:16-alpine -- \
        pg_isready -h "$EXTERNAL_DB_HOST" -p "$EXTERNAL_DB_PORT" -U postgres; then
        log_error "Cannot connect to external database at $EXTERNAL_DB_HOST:$EXTERNAL_DB_PORT"
        exit 1
    fi

    log_success "Prerequisites check passed"
}

# Function to validate manifests
validate_manifests() {
    log_info "Validating Kubernetes manifests..."

    local manifest_files=(
        "k8s/namespace/namespace.yaml"
        "k8s/configmaps/app-config.yaml"
        "k8s/secrets/app-secrets.yaml"
        "k8s/production/production-api.yaml"
        "k8s/services/api-service.yaml"
        "k8s/ingress/ingress.yaml"
        "k8s/security/network-policies.yaml"
        "k8s/monitoring/servicemonitor.yaml"
    )

    for manifest in "${manifest_files[@]}"; do
        if [ ! -f "$manifest" ]; then
            log_error "Manifest file not found: $manifest"
            exit 1
        fi

        # Validate YAML syntax
        if ! kubectl apply --dry-run=client -f "$manifest" > /dev/null 2>&1; then
            log_error "Invalid manifest: $manifest"
            exit 1
        fi
    done

    log_success "All manifests are valid"
}

# Function to deploy namespace and base configuration
deploy_base_infrastructure() {
    log_info "Deploying base infrastructure..."

    # Create namespace
    kubectl apply -f k8s/namespace/namespace.yaml

    # Wait for namespace to be ready
    kubectl wait --for=condition=Active namespace/"$NAMESPACE" --timeout=60s

    # Create secrets (if they don't exist)
    if ! kubectl get secret fxml4-secrets -n "$NAMESPACE" &> /dev/null; then
        log_warning "Secrets not found. Please ensure secrets are created manually or via CI/CD"
        log_info "You can use: kubectl apply -f k8s/secrets/app-secrets.yaml"
    fi

    # Apply ConfigMaps
    kubectl apply -f k8s/configmaps/app-config.yaml

    # Apply network policies for security
    kubectl apply -f k8s/security/network-policies.yaml

    log_success "Base infrastructure deployed"
}

# Function to run database migrations
run_database_migrations() {
    log_info "Running database migrations..."

    # Apply migration job
    kubectl apply -f k8s/jobs/db-migration.yaml

    # Wait for migration to complete
    if ! kubectl wait --for=condition=complete job/fxml4-db-migration -n "$NAMESPACE" --timeout=600s; then
        log_error "Database migration failed"
        kubectl logs job/fxml4-db-migration -n "$NAMESPACE"
        exit 1
    fi

    log_success "Database migrations completed"
}

# Function to deploy supporting services
deploy_supporting_services() {
    log_info "Deploying supporting services..."

    # Deploy Redis
    if [ -f "k8s/deployments/redis.yaml" ]; then
        kubectl apply -f k8s/deployments/redis.yaml
        kubectl apply -f k8s/services/redis-service.yaml
        kubectl rollout status deployment/redis -n "$NAMESPACE" --timeout="$DEPLOYMENT_TIMEOUT"
    fi

    # Deploy RabbitMQ
    if [ -f "k8s/deployments/rabbitmq.yaml" ]; then
        kubectl apply -f k8s/deployments/rabbitmq.yaml
        kubectl apply -f k8s/services/rabbitmq-service.yaml
        kubectl rollout status deployment/rabbitmq -n "$NAMESPACE" --timeout="$DEPLOYMENT_TIMEOUT"
    fi

    log_success "Supporting services deployed"
}

# Function to deploy main application
deploy_application() {
    log_info "Deploying FXML4 application..."

    # Update image tag in production manifests
    if [ "$IMAGE_TAG" != "latest" ]; then
        log_info "Updating image tag to: $IMAGE_TAG"
        sed -i.bak "s|ghcr.io/meridianp/fxml4-api:.*|ghcr.io/meridianp/fxml4-api:$IMAGE_TAG|g" k8s/production/production-api.yaml
    fi

    # Deploy API
    kubectl apply -f k8s/production/production-api.yaml

    # Deploy services
    kubectl apply -f k8s/services/api-service.yaml

    # Deploy workers if they exist
    if [ -f "k8s/deployments/worker.yaml" ]; then
        kubectl apply -f k8s/deployments/worker.yaml
    fi

    # Deploy dashboard if it exists
    if [ -f "k8s/deployments/dashboard.yaml" ]; then
        kubectl apply -f k8s/deployments/dashboard.yaml
        kubectl apply -f k8s/services/dashboard-service.yaml
    fi

    log_success "Application deployments applied"
}

# Function to wait for deployments to be ready
wait_for_deployments() {
    log_info "Waiting for deployments to be ready..."

    # Wait for API deployment
    if ! kubectl rollout status deployment/fxml4-api -n "$NAMESPACE" --timeout="$DEPLOYMENT_TIMEOUT"; then
        log_error "API deployment failed to become ready"
        kubectl describe deployment/fxml4-api -n "$NAMESPACE"
        kubectl logs deployment/fxml4-api -n "$NAMESPACE" --tail=100
        exit 1
    fi

    # Wait for worker deployment if it exists
    if kubectl get deployment fxml4-worker -n "$NAMESPACE" &> /dev/null; then
        kubectl rollout status deployment/fxml4-worker -n "$NAMESPACE" --timeout="$DEPLOYMENT_TIMEOUT"
    fi

    # Wait for dashboard deployment if it exists
    if kubectl get deployment fxml4-dashboard -n "$NAMESPACE" &> /dev/null; then
        kubectl rollout status deployment/fxml4-dashboard -n "$NAMESPACE" --timeout="$DEPLOYMENT_TIMEOUT"
    fi

    # Wait for all pods to be ready
    kubectl wait --for=condition=ready pod -l app=fxml4-api -n "$NAMESPACE" --timeout=300s

    log_success "All deployments are ready"
}

# Function to deploy ingress and monitoring
deploy_ingress_monitoring() {
    log_info "Deploying ingress and monitoring..."

    # Deploy ingress
    kubectl apply -f k8s/ingress/ingress.yaml

    # Deploy monitoring if Prometheus is available
    if kubectl get crd servicemonitors.monitoring.coreos.com &> /dev/null; then
        kubectl apply -f k8s/monitoring/servicemonitor.yaml
        log_success "Monitoring deployed"
    else
        log_warning "Prometheus Operator not found, skipping ServiceMonitor deployment"
    fi

    log_success "Ingress deployed"
}

# Function to deploy operational tools
deploy_operations() {
    log_info "Deploying operational tools..."

    # Deploy database operations (backup, monitoring)
    kubectl apply -f k8s/operations/database-operations.yaml

    # Deploy system health monitoring
    kubectl apply -f k8s/operations/system-health-monitoring.yaml

    log_success "Operational tools deployed"
}

# Function to run health checks
run_health_checks() {
    log_info "Running comprehensive health checks..."

    # Wait a bit for services to stabilize
    sleep 30

    # Get API pod for testing
    local api_pod
    api_pod=$(kubectl get pods -l app=fxml4-api -n "$NAMESPACE" -o jsonpath='{.items[0].metadata.name}')

    if [ -z "$api_pod" ]; then
        log_error "No API pods found"
        exit 1
    fi

    # Test health endpoints
    log_info "Testing health endpoints..."

    # Health endpoint
    if kubectl exec "$api_pod" -n "$NAMESPACE" -- curl -sf http://localhost:8000/health > /dev/null; then
        log_success "Health endpoint OK"
    else
        log_error "Health endpoint failed"
        exit 1
    fi

    # Ready endpoint
    if kubectl exec "$api_pod" -n "$NAMESPACE" -- curl -sf http://localhost:8000/ready > /dev/null; then
        log_success "Ready endpoint OK"
    else
        log_error "Ready endpoint failed"
        exit 1
    fi

    # Test database connectivity from pod
    log_info "Testing database connectivity from application..."
    if kubectl exec "$api_pod" -n "$NAMESPACE" -- python -c "
    import asyncio
    import os
    from fxml4.database.timescaledb import TimescaleDBManager

    async def test_db():
        try:
            db = TimescaleDBManager()
            await db.initialize()
            await db.cleanup()
            print('Database connection successful')
            return True
        except Exception as e:
            print(f'Database connection failed: {e}')
            return False

    result = asyncio.run(test_db())
    exit(0 if result else 1)
    "; then
        log_success "Database connectivity OK"
    else
        log_error "Database connectivity failed"
        exit 1
    fi

    # Test external API endpoints if ingress is configured
    local ingress_host
    ingress_host=$(kubectl get ingress fxml4-ingress -n "$NAMESPACE" -o jsonpath='{.spec.rules[0].host}' 2>/dev/null || echo "")

    if [ -n "$ingress_host" ] && [ "$ingress_host" != "null" ]; then
        log_info "Testing external endpoints via ingress: $ingress_host"

        # Test with retry
        local retry_count=0
        local max_retries=5

        while [ $retry_count -lt $max_retries ]; do
            if curl -sf "https://$ingress_host/health" > /dev/null 2>&1; then
                log_success "External health endpoint OK"
                break
            else
                retry_count=$((retry_count + 1))
                log_warning "External endpoint not ready, attempt $retry_count/$max_retries"
                sleep 10
            fi
        done

        if [ $retry_count -eq $max_retries ]; then
            log_warning "External endpoints not accessible (may be DNS/ingress configuration)"
        fi
    fi

    log_success "Health checks completed"
}

# Function to display deployment summary
display_summary() {
    log_info "Deployment Summary:"
    echo
    echo "Namespace: $NAMESPACE"
    echo "Image Tag: $IMAGE_TAG"
    echo "External Database: $EXTERNAL_DB_HOST:$EXTERNAL_DB_PORT"
    echo

    # Pod status
    echo "Pod Status:"
    kubectl get pods -n "$NAMESPACE" -o wide
    echo

    # Service status
    echo "Service Status:"
    kubectl get services -n "$NAMESPACE"
    echo

    # Ingress status
    if kubectl get ingress -n "$NAMESPACE" &> /dev/null; then
        echo "Ingress Status:"
        kubectl get ingress -n "$NAMESPACE"
        echo
    fi

    # Endpoints
    local ingress_host
    ingress_host=$(kubectl get ingress fxml4-ingress -n "$NAMESPACE" -o jsonpath='{.spec.rules[0].host}' 2>/dev/null || echo "")

    if [ -n "$ingress_host" ] && [ "$ingress_host" != "null" ]; then
        echo "Available Endpoints:"
        echo "  API: https://$ingress_host"
        echo "  Health: https://$ingress_host/health"
        echo "  Docs: https://$ingress_host/docs"
    fi

    # Monitoring
    if kubectl get servicemonitor -n "$NAMESPACE" &> /dev/null; then
        echo "Monitoring: ServiceMonitor configured for Prometheus"
    fi

    echo
    log_success "FXML4 Production Deployment Completed Successfully!"
}

# Function to handle cleanup on error
cleanup_on_error() {
    log_warning "Deployment failed, checking for partial deployment state..."

    # Display recent events
    echo "Recent Events:"
    kubectl get events -n "$NAMESPACE" --sort-by='.lastTimestamp' | tail -10

    # Display pod logs if there are failures
    echo "Pod Status:"
    kubectl get pods -n "$NAMESPACE"

    # Show failing pod logs
    local failing_pods
    failing_pods=$(kubectl get pods -n "$NAMESPACE" --field-selector=status.phase!=Running --no-headers -o custom-columns=":metadata.name" 2>/dev/null || echo "")

    if [ -n "$failing_pods" ]; then
        echo "Logs from failing pods:"
        for pod in $failing_pods; do
            echo "--- $pod ---"
            kubectl logs "$pod" -n "$NAMESPACE" --tail=50 || true
            echo
        done
    fi
}

# Main deployment function
main() {
    echo "======================================"
    echo "FXML4 Production Kubernetes Deployment"
    echo "======================================"
    echo

    # Parse command line arguments
    while [[ $# -gt 0 ]]; do
        case $1 in
            --image-tag)
                IMAGE_TAG="$2"
                shift 2
                ;;
            --kube-context)
                KUBE_CONTEXT="$2"
                shift 2
                ;;
            --dry-run)
                DRY_RUN="true"
                shift
                ;;
            --help)
                echo "Usage: $0 [OPTIONS]"
                echo "Options:"
                echo "  --image-tag TAG     Docker image tag to deploy (default: latest)"
                echo "  --kube-context CTX  Kubernetes context to use"
                echo "  --dry-run          Validate manifests without deploying"
                echo "  --help             Show this help message"
                exit 0
                ;;
            *)
                log_error "Unknown option: $1"
                exit 1
                ;;
        esac
    done

    # Set trap for error handling
    trap cleanup_on_error ERR

    # Run deployment steps
    check_prerequisites
    validate_manifests

    if [ "$DRY_RUN" = "true" ]; then
        log_success "Dry run completed - all manifests are valid"
        exit 0
    fi

    deploy_base_infrastructure
    run_database_migrations
    deploy_supporting_services
    deploy_application
    wait_for_deployments
    deploy_ingress_monitoring
    deploy_operations
    run_health_checks
    display_summary
}

# Run main function
main "$@"
