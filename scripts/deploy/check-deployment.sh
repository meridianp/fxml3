#!/bin/bash
set -e

# FXML4 Deployment Health Check Script
# This script checks the health and status of the FXML4 deployment

echo "🔍 Checking FXML4 deployment health..."

# Configuration
NAMESPACE="fxml4"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
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

print_info() {
    echo -e "${BLUE}ℹ${NC} $1"
}

# Check namespace
check_namespace() {
    echo -e "\n${BLUE}Namespace Status:${NC}"
    echo "=================="

    if kubectl get namespace $NAMESPACE &> /dev/null; then
        print_status "Namespace $NAMESPACE exists"
    else
        print_error "Namespace $NAMESPACE not found"
        exit 1
    fi
}

# Check deployments
check_deployments() {
    echo -e "\n${BLUE}Deployment Status:${NC}"
    echo "==================="

    local deployments=("fxml4-api" "fxml4-dashboard" "fxml4-worker")
    local all_healthy=true

    for deployment in "${deployments[@]}"; do
        if kubectl get deployment $deployment -n $NAMESPACE &> /dev/null; then
            local ready=$(kubectl get deployment $deployment -n $NAMESPACE -o jsonpath='{.status.readyReplicas}')
            local desired=$(kubectl get deployment $deployment -n $NAMESPACE -o jsonpath='{.spec.replicas}')

            if [ "$ready" == "$desired" ] && [ -n "$ready" ]; then
                print_status "$deployment: $ready/$desired replicas ready"
            else
                print_error "$deployment: $ready/$desired replicas ready"
                all_healthy=false
            fi
        else
            print_error "$deployment not found"
            all_healthy=false
        fi
    done

    return $([ "$all_healthy" = true ] && echo 0 || echo 1)
}

# Check pods
check_pods() {
    echo -e "\n${BLUE}Pod Status:${NC}"
    echo "============"

    kubectl get pods -n $NAMESPACE --no-headers | while read line; do
        local name=$(echo $line | awk '{print $1}')
        local ready=$(echo $line | awk '{print $2}')
        local status=$(echo $line | awk '{print $3}')
        local restarts=$(echo $line | awk '{print $4}')

        if [ "$status" == "Running" ]; then
            print_status "$name: $status (Ready: $ready, Restarts: $restarts)"
        elif [ "$status" == "Pending" ] || [ "$status" == "ContainerCreating" ]; then
            print_warning "$name: $status"
        else
            print_error "$name: $status"
        fi
    done
}

# Check services
check_services() {
    echo -e "\n${BLUE}Service Status:${NC}"
    echo "================"

    local services=("fxml4-api" "fxml4-dashboard" "timescaledb" "redis" "rabbitmq")

    for service in "${services[@]}"; do
        if kubectl get service $service -n $NAMESPACE &> /dev/null; then
            local type=$(kubectl get service $service -n $NAMESPACE -o jsonpath='{.spec.type}')
            local cluster_ip=$(kubectl get service $service -n $NAMESPACE -o jsonpath='{.spec.clusterIP}')

            if [ "$type" == "LoadBalancer" ]; then
                local external_ip=$(kubectl get service $service -n $NAMESPACE -o jsonpath='{.status.loadBalancer.ingress[0].ip}')
                if [ -n "$external_ip" ]; then
                    print_status "$service: $type (External IP: $external_ip)"
                else
                    print_warning "$service: $type (External IP: pending)"
                fi
            else
                print_status "$service: $type (Cluster IP: $cluster_ip)"
            fi
        else
            print_error "$service not found"
        fi
    done
}

# Check persistent volumes
check_storage() {
    echo -e "\n${BLUE}Storage Status:${NC}"
    echo "================"

    kubectl get pvc -n $NAMESPACE --no-headers | while read line; do
        local name=$(echo $line | awk '{print $1}')
        local status=$(echo $line | awk '{print $2}')
        local volume=$(echo $line | awk '{print $3}')
        local capacity=$(echo $line | awk '{print $4}')

        if [ "$status" == "Bound" ]; then
            print_status "$name: $status ($capacity)"
        else
            print_error "$name: $status"
        fi
    done
}

# Check ingress
check_ingress() {
    echo -e "\n${BLUE}Ingress Status:${NC}"
    echo "==============="

    if kubectl get ingress -n $NAMESPACE &> /dev/null; then
        kubectl get ingress -n $NAMESPACE --no-headers | while read line; do
            local name=$(echo $line | awk '{print $1}')
            local hosts=$(echo $line | awk '{print $3}')
            local address=$(echo $line | awk '{print $4}')

            if [ -n "$address" ]; then
                print_status "$name: $hosts → $address"
            else
                print_warning "$name: $hosts → (no address yet)"
            fi
        done
    else
        print_info "No ingress resources found"
    fi
}

# Check API health
check_api_health() {
    echo -e "\n${BLUE}API Health Check:${NC}"
    echo "=================="

    # Try to get API service endpoint
    local api_ip=$(kubectl get svc fxml4-api-external -n $NAMESPACE -o jsonpath='{.status.loadBalancer.ingress[0].ip}' 2>/dev/null)

    if [ -z "$api_ip" ]; then
        # Try port-forward as fallback
        print_info "External IP not available, trying port-forward..."
        kubectl port-forward svc/fxml4-api 8000:8000 -n $NAMESPACE &> /dev/null &
        local pf_pid=$!
        sleep 3

        if curl -s -f http://localhost:8000/health > /dev/null; then
            print_status "API health check passed (via port-forward)"
        else
            print_error "API health check failed"
        fi

        kill $pf_pid 2>/dev/null || true
    else
        if curl -s -f http://${api_ip}/health > /dev/null; then
            print_status "API health check passed"
        else
            print_error "API health check failed"
        fi
    fi
}

# Check recent events
check_events() {
    echo -e "\n${BLUE}Recent Events:${NC}"
    echo "=============="

    local events=$(kubectl get events -n $NAMESPACE --sort-by='.lastTimestamp' --field-selector type=Warning -o json | jq -r '.items[-5:] | .[] | "\(.lastTimestamp) [\(.reason)] \(.message)"' 2>/dev/null)

    if [ -n "$events" ]; then
        print_warning "Recent warning events:"
        echo "$events"
    else
        print_status "No warning events in the last 5 minutes"
    fi
}

# Generate summary
generate_summary() {
    echo -e "\n${BLUE}=======================
Deployment Summary
=======================${NC}"

    # Overall health
    local healthy=true

    # Check critical components
    for deployment in "fxml4-api" "fxml4-dashboard" "fxml4-worker"; do
        if ! kubectl get deployment $deployment -n $NAMESPACE &> /dev/null; then
            healthy=false
            break
        fi

        local ready=$(kubectl get deployment $deployment -n $NAMESPACE -o jsonpath='{.status.readyReplicas}')
        local desired=$(kubectl get deployment $deployment -n $NAMESPACE -o jsonpath='{.spec.replicas}')

        if [ "$ready" != "$desired" ] || [ -z "$ready" ]; then
            healthy=false
            break
        fi
    done

    if [ "$healthy" = true ]; then
        echo -e "${GREEN}✅ Deployment is healthy!${NC}"
    else
        echo -e "${RED}❌ Deployment has issues that need attention.${NC}"
    fi

    echo -e "\nQuick actions:"
    echo "• View logs: kubectl logs -f deployment/[deployment-name] -n $NAMESPACE"
    echo "• Describe pod: kubectl describe pod [pod-name] -n $NAMESPACE"
    echo "• Get events: kubectl get events -n $NAMESPACE --sort-by='.lastTimestamp'"
    echo "• Port forward: kubectl port-forward svc/fxml4-api 8000:8000 -n $NAMESPACE"
}

# Main function
main() {
    check_namespace
    check_deployments
    check_pods
    check_services
    check_storage
    check_ingress
    check_api_health
    check_events
    generate_summary
}

# Run main function
main
