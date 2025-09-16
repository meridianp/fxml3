#!/bin/bash
set -e

# FXML4 Kubernetes Rollback Script
# This script rolls back deployments to the previous version

echo "🔄 Starting FXML4 rollback..."

# Configuration
NAMESPACE="fxml4"

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
        print_error "Namespace $NAMESPACE does not exist."
        exit 1
    fi
    print_status "Namespace $NAMESPACE exists"
}

# Show rollout history
show_history() {
    echo -e "\nCurrent rollout history:"
    echo "========================"

    echo -e "\nAPI:"
    kubectl rollout history deployment/fxml4-api -n $NAMESPACE || print_warning "No API deployment found"

    echo -e "\nDashboard:"
    kubectl rollout history deployment/fxml4-dashboard -n $NAMESPACE || print_warning "No Dashboard deployment found"

    echo -e "\nWorker:"
    kubectl rollout history deployment/fxml4-worker -n $NAMESPACE || print_warning "No Worker deployment found"
}

# Rollback deployment
rollback_deployment() {
    local deployment=$1
    local revision=$2

    echo -e "\nRolling back $deployment..."

    if [ -z "$revision" ]; then
        # Rollback to previous version
        kubectl rollout undo deployment/$deployment -n $NAMESPACE
        print_status "$deployment rolled back to previous version"
    else
        # Rollback to specific revision
        kubectl rollout undo deployment/$deployment -n $NAMESPACE --to-revision=$revision
        print_status "$deployment rolled back to revision $revision"
    fi

    # Wait for rollback to complete
    kubectl rollout status deployment/$deployment -n $NAMESPACE --timeout=300s
    print_status "$deployment rollback completed"
}

# Interactive rollback
interactive_rollback() {
    echo -e "\nWhich deployment would you like to rollback?"
    echo "1) API"
    echo "2) Dashboard"
    echo "3) Worker"
    echo "4) All deployments"
    echo "5) Cancel"

    read -p "Enter choice (1-5): " choice

    case $choice in
        1)
            rollback_deployment "fxml4-api"
            ;;
        2)
            rollback_deployment "fxml4-dashboard"
            ;;
        3)
            rollback_deployment "fxml4-worker"
            ;;
        4)
            rollback_deployment "fxml4-api"
            rollback_deployment "fxml4-dashboard"
            rollback_deployment "fxml4-worker"
            ;;
        5)
            echo "Rollback cancelled"
            exit 0
            ;;
        *)
            print_error "Invalid choice"
            exit 1
            ;;
    esac
}

# Display deployment status
display_status() {
    echo -e "\n${GREEN}Current deployment status:${NC}"
    echo "=========================="
    kubectl get deployments -n $NAMESPACE
    echo ""
    kubectl get pods -n $NAMESPACE
}

# Main function
main() {
    check_prerequisites

    # Check if specific deployment is provided as argument
    if [ $# -eq 0 ]; then
        show_history
        interactive_rollback
    elif [ $# -eq 1 ]; then
        # Rollback specific deployment to previous version
        rollback_deployment "$1"
    elif [ $# -eq 2 ]; then
        # Rollback specific deployment to specific revision
        rollback_deployment "$1" "$2"
    else
        echo "Usage: $0 [deployment-name] [revision]"
        echo "Examples:"
        echo "  $0                    # Interactive mode"
        echo "  $0 fxml4-api         # Rollback API to previous version"
        echo "  $0 fxml4-api 3       # Rollback API to revision 3"
        exit 1
    fi

    display_status
    echo -e "\n${GREEN}✅ Rollback completed successfully!${NC}"
}

# Run main function
main "$@"
