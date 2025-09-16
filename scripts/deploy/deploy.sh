#!/bin/bash
set -e

# FXML4 Kubernetes Deployment Script
# This script deploys the FXML4 application to a Kubernetes cluster

echo "🚀 Starting FXML4 deployment..."

# Configuration
NAMESPACE="fxml4"
REGISTRY="ghcr.io"
REPO_OWNER="meridianp"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${GREEN}✓${NC} $1"
}

print_error() {
    echo -e "${RED}✗${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}⚠${NC} $1"
}

# Check prerequisites
check_prerequisites() {
    echo "Checking prerequisites..."

    # Check kubectl
    if ! command -v kubectl &> /dev/null; then
        print_error "kubectl not found. Please install kubectl."
        exit 1
    fi
    print_status "kubectl found"

    # Check cluster connection
    if ! kubectl cluster-info &> /dev/null; then
        print_error "Cannot connect to Kubernetes cluster. Please check your kubeconfig."
        exit 1
    fi
    print_status "Connected to Kubernetes cluster"

    # Check if namespace exists
    if ! kubectl get namespace $NAMESPACE &> /dev/null; then
        print_warning "Namespace $NAMESPACE does not exist. Creating..."
        kubectl apply -f k8s/namespace/namespace.yaml
        print_status "Namespace created"
    else
        print_status "Namespace $NAMESPACE exists"
    fi
}

# Create secrets
create_secrets() {
    echo -e "\nCreating secrets..."

    # Check if secrets file exists
    if [ ! -f ".env.production" ]; then
        print_error ".env.production file not found. Please create it from .env.production.example"
        exit 1
    fi

    # Source environment variables
    source .env.production

    # Create docker registry secret
    if [ -n "$GITHUB_TOKEN" ]; then
        kubectl create secret docker-registry ghcr-secret \
            --docker-server=$REGISTRY \
            --docker-username=$GITHUB_USERNAME \
            --docker-password=$GITHUB_TOKEN \
            --docker-email="${GITHUB_USERNAME}@users.noreply.github.com" \
            --namespace=$NAMESPACE \
            --dry-run=client -o yaml | kubectl apply -f -
        print_status "Docker registry secret created/updated"
    else
        print_warning "GITHUB_TOKEN not set, skipping docker registry secret"
    fi

    # Apply app secrets (check if template exists for local deployment)
    if [ -f "k8s/secrets/app-secrets.yaml" ]; then
        kubectl apply -f k8s/secrets/app-secrets.yaml
        print_status "Application secrets created/updated"
    else
        print_warning "Using app-secrets-template.yaml - ensure GitHub Actions has set the secrets"
        # For local deployment, you need to manually create app-secrets.yaml
        if [ -f ".env.production" ]; then
            # Source environment and apply template
            source .env.production
            envsubst < k8s/secrets/app-secrets-template.yaml | kubectl apply -f -
            print_status "Application secrets created from .env.production"
        else
            print_error "No app-secrets.yaml or .env.production found. Please create one."
            print_info "Run ./scripts/setup-github-secrets.sh to set up GitHub secrets"
            print_info "Or copy k8s/secrets/app-secrets-template.yaml to app-secrets.yaml and fill in values"
            exit 1
        fi
    fi
}

# Deploy infrastructure services
deploy_infrastructure() {
    echo -e "\nDeploying infrastructure services..."

    # Note: Using external PostgreSQL/TimescaleDB database
    print_info "Using external database at postgres01.tailb381ec.ts.net:5431"

    # Deploy Redis
    kubectl apply -f k8s/deployments/redis.yaml
    kubectl apply -f k8s/services/redis-service.yaml
    print_status "Redis deployed"

    # Deploy RabbitMQ
    kubectl apply -f k8s/deployments/rabbitmq.yaml
    kubectl apply -f k8s/services/rabbitmq-service.yaml
    print_status "RabbitMQ deployed"

    # Wait for infrastructure to be ready
    echo "Waiting for infrastructure services to be ready..."
    kubectl wait --for=condition=ready pod -l app=redis -n $NAMESPACE --timeout=300s
    kubectl wait --for=condition=ready pod -l app=rabbitmq -n $NAMESPACE --timeout=300s
    print_status "Infrastructure services ready"
}

# Deploy application services
deploy_application() {
    echo -e "\nDeploying application services..."

    # Apply ConfigMap
    kubectl apply -f k8s/configmaps/app-config.yaml
    print_status "ConfigMap applied"

    # Get the latest image tag or use 'latest'
    IMAGE_TAG=${IMAGE_TAG:-latest}

    # Deploy API
    export IMAGE_TAG
    envsubst < k8s/deployments/api.yaml | kubectl apply -f -
    kubectl apply -f k8s/services/api-service.yaml
    print_status "API deployed"

    # Deploy Dashboard
    envsubst < k8s/deployments/dashboard.yaml | kubectl apply -f -
    kubectl apply -f k8s/services/dashboard-service.yaml
    print_status "Dashboard deployed"

    # Deploy Worker
    envsubst < k8s/deployments/worker.yaml | kubectl apply -f -
    print_status "Worker deployed"

    # Deploy Ingress
    kubectl apply -f k8s/ingress/ingress.yaml
    print_status "Ingress deployed"
}

# Wait for deployment
wait_for_deployment() {
    echo -e "\nWaiting for deployments to be ready..."

    kubectl rollout status deployment/fxml4-api -n $NAMESPACE --timeout=300s
    print_status "API deployment ready"

    kubectl rollout status deployment/fxml4-dashboard -n $NAMESPACE --timeout=300s
    print_status "Dashboard deployment ready"

    kubectl rollout status deployment/fxml4-worker -n $NAMESPACE --timeout=300s
    print_status "Worker deployment ready"
}

# Display deployment info
display_info() {
    echo -e "\n${GREEN}✅ Deployment completed successfully!${NC}"
    echo -e "\nDeployment Information:"
    echo "======================"

    # Get service endpoints
    API_IP=$(kubectl get svc fxml4-api-external -n $NAMESPACE -o jsonpath='{.status.loadBalancer.ingress[0].ip}' 2>/dev/null || echo "pending")
    DASHBOARD_IP=$(kubectl get svc fxml4-dashboard-external -n $NAMESPACE -o jsonpath='{.status.loadBalancer.ingress[0].ip}' 2>/dev/null || echo "pending")

    echo "API Endpoint: http://${API_IP}"
    echo "Dashboard Endpoint: http://${DASHBOARD_IP}"
    echo ""
    echo "To check pod status:"
    echo "  kubectl get pods -n $NAMESPACE"
    echo ""
    echo "To view logs:"
    echo "  kubectl logs -f deployment/fxml4-api -n $NAMESPACE"
    echo "  kubectl logs -f deployment/fxml4-dashboard -n $NAMESPACE"
    echo "  kubectl logs -f deployment/fxml4-worker -n $NAMESPACE"
    echo ""
    echo "To access services via port-forward:"
    echo "  kubectl port-forward svc/fxml4-api 8000:8000 -n $NAMESPACE"
    echo "  kubectl port-forward svc/fxml4-dashboard 8501:8501 -n $NAMESPACE"
}

# Main deployment flow
main() {
    check_prerequisites
    create_secrets
    deploy_infrastructure
    deploy_application
    wait_for_deployment
    display_info
}

# Run main function
main
