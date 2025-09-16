#!/bin/bash
# FXML4 Kubernetes Deployment Validation Script
# Comprehensive validation of production deployment

set -e

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Configuration
NAMESPACE="fxml4"
VALIDATION_TIMEOUT=300
EXTERNAL_DB_HOST="postgres01.tailb381ec.ts.net"

# Counters
TOTAL_CHECKS=0
PASSED_CHECKS=0
FAILED_CHECKS=0
WARNING_CHECKS=0

# Logging functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[✓]${NC} $1"
    PASSED_CHECKS=$((PASSED_CHECKS + 1))
}

log_warning() {
    echo -e "${YELLOW}[⚠]${NC} $1"
    WARNING_CHECKS=$((WARNING_CHECKS + 1))
}

log_error() {
    echo -e "${RED}[✗]${NC} $1"
    FAILED_CHECKS=$((FAILED_CHECKS + 1))
}

check_result() {
    TOTAL_CHECKS=$((TOTAL_CHECKS + 1))
    if [ $1 -eq 0 ]; then
        log_success "$2"
    else
        log_error "$2"
    fi
}

# Validate namespace and basic resources
validate_namespace() {
    echo "=== 1. Namespace and Basic Resources ==="

    # Check namespace exists
    kubectl get namespace "$NAMESPACE" > /dev/null 2>&1
    check_result $? "Namespace '$NAMESPACE' exists"

    # Check secrets
    kubectl get secret fxml4-secrets -n "$NAMESPACE" > /dev/null 2>&1
    check_result $? "Application secrets exist"

    # Check configmaps
    kubectl get configmap fxml4-config -n "$NAMESPACE" > /dev/null 2>&1
    check_result $? "Application ConfigMap exists"

    # Check PVCs
    local pvc_count
    pvc_count=$(kubectl get pvc -n "$NAMESPACE" --no-headers | wc -l)
    if [ "$pvc_count" -gt 0 ]; then
        log_success "Persistent volumes configured ($pvc_count PVCs)"
        PASSED_CHECKS=$((PASSED_CHECKS + 1))
    else
        log_warning "No persistent volumes found"
        WARNING_CHECKS=$((WARNING_CHECKS + 1))
    fi
    TOTAL_CHECKS=$((TOTAL_CHECKS + 1))

    echo
}

# Validate deployments
validate_deployments() {
    echo "=== 2. Deployment Validation ==="

    local deployments=("fxml4-api")

    # Check if worker deployment exists
    if kubectl get deployment fxml4-worker -n "$NAMESPACE" > /dev/null 2>&1; then
        deployments+=("fxml4-worker")
    fi

    # Check if dashboard deployment exists
    if kubectl get deployment fxml4-dashboard -n "$NAMESPACE" > /dev/null 2>&1; then
        deployments+=("fxml4-dashboard")
    fi

    for deployment in "${deployments[@]}"; do
        # Check deployment exists
        kubectl get deployment "$deployment" -n "$NAMESPACE" > /dev/null 2>&1
        check_result $? "Deployment '$deployment' exists"

        if kubectl get deployment "$deployment" -n "$NAMESPACE" > /dev/null 2>&1; then
            # Check replica status
            local ready_replicas desired_replicas
            ready_replicas=$(kubectl get deployment "$deployment" -n "$NAMESPACE" -o jsonpath='{.status.readyReplicas}' 2>/dev/null || echo "0")
            desired_replicas=$(kubectl get deployment "$deployment" -n "$NAMESPACE" -o jsonpath='{.spec.replicas}' 2>/dev/null || echo "0")

            if [ "$ready_replicas" = "$desired_replicas" ] && [ "$ready_replicas" -gt 0 ]; then
                log_success "$deployment: $ready_replicas/$desired_replicas replicas ready"
                PASSED_CHECKS=$((PASSED_CHECKS + 1))
            else
                log_error "$deployment: $ready_replicas/$desired_replicas replicas ready"
                FAILED_CHECKS=$((FAILED_CHECKS + 1))
            fi
            TOTAL_CHECKS=$((TOTAL_CHECKS + 1))

            # Check deployment conditions
            local available_condition
            available_condition=$(kubectl get deployment "$deployment" -n "$NAMESPACE" -o jsonpath='{.status.conditions[?(@.type=="Available")].status}' 2>/dev/null || echo "")
            if [ "$available_condition" = "True" ]; then
                log_success "$deployment: Available condition is True"
                PASSED_CHECKS=$((PASSED_CHECKS + 1))
            else
                log_error "$deployment: Available condition is not True"
                FAILED_CHECKS=$((FAILED_CHECKS + 1))
            fi
            TOTAL_CHECKS=$((TOTAL_CHECKS + 1))
        fi
    done

    echo
}

# Validate services and networking
validate_networking() {
    echo "=== 3. Network and Service Validation ==="

    # Check services
    local services=("fxml4-api")

    if kubectl get service fxml4-dashboard -n "$NAMESPACE" > /dev/null 2>&1; then
        services+=("fxml4-dashboard")
    fi

    for service in "${services[@]}"; do
        kubectl get service "$service" -n "$NAMESPACE" > /dev/null 2>&1
        check_result $? "Service '$service' exists"

        if kubectl get service "$service" -n "$NAMESPACE" > /dev/null 2>&1; then
            # Check endpoints
            local endpoint_count
            endpoint_count=$(kubectl get endpoints "$service" -n "$NAMESPACE" -o jsonpath='{.subsets[*].addresses[*].ip}' 2>/dev/null | wc -w)
            if [ "$endpoint_count" -gt 0 ]; then
                log_success "$service: $endpoint_count endpoints available"
                PASSED_CHECKS=$((PASSED_CHECKS + 1))
            else
                log_error "$service: No endpoints available"
                FAILED_CHECKS=$((FAILED_CHECKS + 1))
            fi
            TOTAL_CHECKS=$((TOTAL_CHECKS + 1))
        fi
    done

    # Check ingress
    if kubectl get ingress fxml4-ingress -n "$NAMESPACE" > /dev/null 2>&1; then
        log_success "Ingress 'fxml4-ingress' exists"
        PASSED_CHECKS=$((PASSED_CHECKS + 1))

        # Check ingress hosts
        local hosts
        hosts=$(kubectl get ingress fxml4-ingress -n "$NAMESPACE" -o jsonpath='{.spec.rules[*].host}' 2>/dev/null)
        if [ -n "$hosts" ]; then
            log_success "Ingress hosts configured: $hosts"
            PASSED_CHECKS=$((PASSED_CHECKS + 1))
        else
            log_warning "No ingress hosts configured"
            WARNING_CHECKS=$((WARNING_CHECKS + 1))
        fi
        TOTAL_CHECKS=$((TOTAL_CHECKS + 2))
    else
        log_warning "Ingress not found (may be intentional)"
        WARNING_CHECKS=$((WARNING_CHECKS + 1))
        TOTAL_CHECKS=$((TOTAL_CHECKS + 1))
    fi

    # Check network policies
    local np_count
    np_count=$(kubectl get networkpolicy -n "$NAMESPACE" --no-headers 2>/dev/null | wc -l)
    if [ "$np_count" -gt 0 ]; then
        log_success "Network policies configured ($np_count policies)"
        PASSED_CHECKS=$((PASSED_CHECKS + 1))
    else
        log_warning "No network policies found"
        WARNING_CHECKS=$((WARNING_CHECKS + 1))
    fi
    TOTAL_CHECKS=$((TOTAL_CHECKS + 1))

    echo
}

# Validate external database connectivity
validate_external_database() {
    echo "=== 4. External Database Validation ==="

    # Test basic connectivity
    if kubectl run db-test-temp --rm -i --restart=Never --image=postgres:16-alpine -- \
        pg_isready -h "$EXTERNAL_DB_HOST" -p 5432 -U postgres > /dev/null 2>&1; then
        log_success "External database reachable at $EXTERNAL_DB_HOST"
        PASSED_CHECKS=$((PASSED_CHECKS + 1))
    else
        log_error "External database unreachable at $EXTERNAL_DB_HOST"
        FAILED_CHECKS=$((FAILED_CHECKS + 1))
    fi
    TOTAL_CHECKS=$((TOTAL_CHECKS + 1))

    # Test connectivity from API pod
    local api_pod
    api_pod=$(kubectl get pods -l app=fxml4-api -n "$NAMESPACE" -o jsonpath='{.items[0].metadata.name}' 2>/dev/null)

    if [ -n "$api_pod" ] && [ "$api_pod" != "null" ]; then
        if kubectl exec "$api_pod" -n "$NAMESPACE" -- python -c "
        import os
        import asyncio
        from fxml4.database.timescaledb import TimescaleDBManager

        async def test():
            try:
                db = TimescaleDBManager()
                await db.initialize()
                await db.cleanup()
                return True
            except Exception as e:
                print(f'Error: {e}')
                return False

        result = asyncio.run(test())
        exit(0 if result else 1)
        " > /dev/null 2>&1; then
            log_success "Database connectivity from API pod successful"
            PASSED_CHECKS=$((PASSED_CHECKS + 1))
        else
            log_error "Database connectivity from API pod failed"
            FAILED_CHECKS=$((FAILED_CHECKS + 1))
        fi
        TOTAL_CHECKS=$((TOTAL_CHECKS + 1))
    else
        log_warning "No API pod found for database connectivity test"
        WARNING_CHECKS=$((WARNING_CHECKS + 1))
        TOTAL_CHECKS=$((TOTAL_CHECKS + 1))
    fi

    echo
}

# Validate application health endpoints
validate_application_health() {
    echo "=== 5. Application Health Validation ==="

    local api_pod
    api_pod=$(kubectl get pods -l app=fxml4-api -n "$NAMESPACE" -o jsonpath='{.items[0].metadata.name}' 2>/dev/null)

    if [ -n "$api_pod" ] && [ "$api_pod" != "null" ]; then
        # Test health endpoint
        if kubectl exec "$api_pod" -n "$NAMESPACE" -- curl -sf http://localhost:8000/health > /dev/null 2>&1; then
            log_success "Health endpoint (/health) responding"
            PASSED_CHECKS=$((PASSED_CHECKS + 1))
        else
            log_error "Health endpoint (/health) not responding"
            FAILED_CHECKS=$((FAILED_CHECKS + 1))
        fi
        TOTAL_CHECKS=$((TOTAL_CHECKS + 1))

        # Test readiness endpoint
        if kubectl exec "$api_pod" -n "$NAMESPACE" -- curl -sf http://localhost:8000/ready > /dev/null 2>&1; then
            log_success "Readiness endpoint (/ready) responding"
            PASSED_CHECKS=$((PASSED_CHECKS + 1))
        else
            log_error "Readiness endpoint (/ready) not responding"
            FAILED_CHECKS=$((FAILED_CHECKS + 1))
        fi
        TOTAL_CHECKS=$((TOTAL_CHECKS + 1))

        # Test startup endpoint
        if kubectl exec "$api_pod" -n "$NAMESPACE" -- curl -sf http://localhost:8000/startup > /dev/null 2>&1; then
            log_success "Startup endpoint (/startup) responding"
            PASSED_CHECKS=$((PASSED_CHECKS + 1))
        else
            log_warning "Startup endpoint (/startup) not responding (may be normal)"
            WARNING_CHECKS=$((WARNING_CHECKS + 1))
        fi
        TOTAL_CHECKS=$((TOTAL_CHECKS + 1))

        # Test metrics endpoint
        if kubectl exec "$api_pod" -n "$NAMESPACE" -- curl -sf http://localhost:9090/metrics > /dev/null 2>&1; then
            log_success "Metrics endpoint (/metrics) responding"
            PASSED_CHECKS=$((PASSED_CHECKS + 1))
        else
            log_warning "Metrics endpoint (/metrics) not responding"
            WARNING_CHECKS=$((WARNING_CHECKS + 1))
        fi
        TOTAL_CHECKS=$((TOTAL_CHECKS + 1))

        # Test API documentation
        if kubectl exec "$api_pod" -n "$NAMESPACE" -- curl -sf http://localhost:8000/docs > /dev/null 2>&1; then
            log_success "API documentation (/docs) accessible"
            PASSED_CHECKS=$((PASSED_CHECKS + 1))
        else
            log_warning "API documentation (/docs) not accessible"
            WARNING_CHECKS=$((WARNING_CHECKS + 1))
        fi
        TOTAL_CHECKS=$((TOTAL_CHECKS + 1))

    else
        log_error "No API pod available for health endpoint testing"
        FAILED_CHECKS=$((FAILED_CHECKS + 5))
        TOTAL_CHECKS=$((TOTAL_CHECKS + 5))
    fi

    echo
}

# Validate supporting services
validate_supporting_services() {
    echo "=== 6. Supporting Services Validation ==="

    # Redis validation
    if kubectl get deployment redis -n "$NAMESPACE" > /dev/null 2>&1; then
        if kubectl exec deployment/redis -n "$NAMESPACE" -- redis-cli ping > /dev/null 2>&1; then
            log_success "Redis service responding"
            PASSED_CHECKS=$((PASSED_CHECKS + 1))
        else
            log_error "Redis service not responding"
            FAILED_CHECKS=$((FAILED_CHECKS + 1))
        fi
        TOTAL_CHECKS=$((TOTAL_CHECKS + 1))
    else
        log_warning "Redis deployment not found"
        WARNING_CHECKS=$((WARNING_CHECKS + 1))
        TOTAL_CHECKS=$((TOTAL_CHECKS + 1))
    fi

    # RabbitMQ validation
    if kubectl get deployment rabbitmq -n "$NAMESPACE" > /dev/null 2>&1; then
        if kubectl exec deployment/rabbitmq -n "$NAMESPACE" -- rabbitmq-diagnostics -q ping > /dev/null 2>&1; then
            log_success "RabbitMQ service responding"
            PASSED_CHECKS=$((PASSED_CHECKS + 1))
        else
            log_error "RabbitMQ service not responding"
            FAILED_CHECKS=$((FAILED_CHECKS + 1))
        fi
        TOTAL_CHECKS=$((TOTAL_CHECKS + 1))
    else
        log_warning "RabbitMQ deployment not found"
        WARNING_CHECKS=$((WARNING_CHECKS + 1))
        TOTAL_CHECKS=$((TOTAL_CHECKS + 1))
    fi

    echo
}

# Validate monitoring and operations
validate_monitoring() {
    echo "=== 7. Monitoring and Operations Validation ==="

    # Check ServiceMonitor
    if kubectl get crd servicemonitors.monitoring.coreos.com > /dev/null 2>&1; then
        if kubectl get servicemonitor -n "$NAMESPACE" > /dev/null 2>&1; then
            local sm_count
            sm_count=$(kubectl get servicemonitor -n "$NAMESPACE" --no-headers | wc -l)
            log_success "ServiceMonitors configured ($sm_count monitors)"
            PASSED_CHECKS=$((PASSED_CHECKS + 1))
        else
            log_warning "No ServiceMonitors found"
            WARNING_CHECKS=$((WARNING_CHECKS + 1))
        fi
        TOTAL_CHECKS=$((TOTAL_CHECKS + 1))
    else
        log_warning "Prometheus Operator not installed (ServiceMonitor CRD not found)"
        WARNING_CHECKS=$((WARNING_CHECKS + 1))
        TOTAL_CHECKS=$((TOTAL_CHECKS + 1))
    fi

    # Check backup jobs
    if kubectl get cronjob fxml4-db-backup -n "$NAMESPACE" > /dev/null 2>&1; then
        log_success "Database backup CronJob configured"
        PASSED_CHECKS=$((PASSED_CHECKS + 1))
    else
        log_warning "Database backup CronJob not found"
        WARNING_CHECKS=$((WARNING_CHECKS + 1))
    fi
    TOTAL_CHECKS=$((TOTAL_CHECKS + 1))

    # Check health monitoring
    if kubectl get cronjob ftml4-system-health-monitor -n "$NAMESPACE" > /dev/null 2>&1; then
        log_success "System health monitoring CronJob configured"
        PASSED_CHECKS=$((PASSED_CHECKS + 1))
    else
        log_warning "System health monitoring CronJob not found"
        WARNING_CHECKS=$((WARNING_CHECKS + 1))
    fi
    TOTAL_CHECKS=$((TOTAL_CHECKS + 1))

    echo
}

# Validate security configuration
validate_security() {
    echo "=== 8. Security Configuration Validation ==="

    # Check ServiceAccounts
    if kubectl get serviceaccount fxml4-api-sa -n "$NAMESPACE" > /dev/null 2>&1; then
        log_success "API ServiceAccount configured"
        PASSED_CHECKS=$((PASSED_CHECKS + 1))
    else
        log_warning "API ServiceAccount not found"
        WARNING_CHECKS=$((WARNING_CHECKS + 1))
    fi
    TOTAL_CHECKS=$((TOTAL_CHECKS + 1))

    # Check RBAC
    if kubectl get role fxml4-api-role -n "$NAMESPACE" > /dev/null 2>&1; then
        log_success "RBAC Role configured"
        PASSED_CHECKS=$((PASSED_CHECKS + 1))
    else
        log_warning "RBAC Role not found"
        WARNING_CHECKS=$((WARNING_CHECKS + 1))
    fi
    TOTAL_CHECKS=$((TOTAL_CHECKS + 1))

    # Check PodDisruptionBudget
    if kubectl get pdb fxml4-api-pdb -n "$NAMESPACE" > /dev/null 2>&1; then
        log_success "PodDisruptionBudget configured"
        PASSED_CHECKS=$((PASSED_CHECKS + 1))
    else
        log_warning "PodDisruptionBudget not found"
        WARNING_CHECKS=$((WARNING_CHECKS + 1))
    fi
    TOTAL_CHECKS=$((TOTAL_CHECKS + 1))

    # Check HorizontalPodAutoscaler
    if kubectl get hpa fxml4-api-hpa -n "$NAMESPACE" > /dev/null 2>&1; then
        log_success "HorizontalPodAutoscaler configured"
        PASSED_CHECKS=$((PASSED_CHECKS + 1))
    else
        log_warning "HorizontalPodAutoscaler not found"
        WARNING_CHECKS=$((WARNING_CHECKS + 1))
    fi
    TOTAL_CHECKS=$((TOTAL_CHECKS + 1))

    echo
}

# Validate pod security and resource limits
validate_pod_security() {
    echo "=== 9. Pod Security and Resources Validation ==="

    local api_pod
    api_pod=$(kubectl get pods -l app=fxml4-api -n "$NAMESPACE" -o jsonpath='{.items[0].metadata.name}' 2>/dev/null)

    if [ -n "$api_pod" ] && [ "$api_pod" != "null" ]; then
        # Check security context
        local run_as_user
        run_as_user=$(kubectl get pod "$api_pod" -n "$NAMESPACE" -o jsonpath='{.spec.securityContext.runAsUser}' 2>/dev/null)
        if [ "$run_as_user" != "0" ] && [ -n "$run_as_user" ]; then
            log_success "Pod running as non-root user ($run_as_user)"
            PASSED_CHECKS=$((PASSED_CHECKS + 1))
        else
            log_warning "Pod may be running as root"
            WARNING_CHECKS=$((WARNING_CHECKS + 1))
        fi
        TOTAL_CHECKS=$((TOTAL_CHECKS + 1))

        # Check resource limits
        local memory_limit cpu_limit
        memory_limit=$(kubectl get pod "$api_pod" -n "$NAMESPACE" -o jsonpath='{.spec.containers[0].resources.limits.memory}' 2>/dev/null)
        cpu_limit=$(kubectl get pod "$api_pod" -n "$NAMESPACE" -o jsonpath='{.spec.containers[0].resources.limits.cpu}' 2>/dev/null)

        if [ -n "$memory_limit" ] && [ -n "$cpu_limit" ]; then
            log_success "Resource limits configured (CPU: $cpu_limit, Memory: $memory_limit)"
            PASSED_CHECKS=$((PASSED_CHECKS + 1))
        else
            log_warning "Resource limits not fully configured"
            WARNING_CHECKS=$((WARNING_CHECKS + 1))
        fi
        TOTAL_CHECKS=$((TOTAL_CHECKS + 1))

        # Check readiness probe
        local readiness_probe
        readiness_probe=$(kubectl get pod "$api_pod" -n "$NAMESPACE" -o jsonpath='{.spec.containers[0].readinessProbe.httpGet.path}' 2>/dev/null)
        if [ -n "$readiness_probe" ]; then
            log_success "Readiness probe configured ($readiness_probe)"
            PASSED_CHECKS=$((PASSED_CHECKS + 1))
        else
            log_warning "Readiness probe not configured"
            WARNING_CHECKS=$((WARNING_CHECKS + 1))
        fi
        TOTAL_CHECKS=$((TOTAL_CHECKS + 1))

        # Check liveness probe
        local liveness_probe
        liveness_probe=$(kubectl get pod "$api_pod" -n "$NAMESPACE" -o jsonpath='{.spec.containers[0].livenessProbe.httpGet.path}' 2>/dev/null)
        if [ -n "$liveness_probe" ]; then
            log_success "Liveness probe configured ($liveness_probe)"
            PASSED_CHECKS=$((PASSED_CHECKS + 1))
        else
            log_warning "Liveness probe not configured"
            WARNING_CHECKS=$((WARNING_CHECKS + 1))
        fi
        TOTAL_CHECKS=$((TOTAL_CHECKS + 1))

    else
        log_error "No API pod available for security validation"
        FAILED_CHECKS=$((FAILED_CHECKS + 4))
        TOTAL_CHECKS=$((TOTAL_CHECKS + 4))
    fi

    echo
}

# Generate final report
generate_report() {
    echo "======================================"
    echo "FXML4 Deployment Validation Report"
    echo "======================================"
    echo

    local success_rate=0
    if [ $TOTAL_CHECKS -gt 0 ]; then
        success_rate=$(( (PASSED_CHECKS * 100) / TOTAL_CHECKS ))
    fi

    echo "Total Checks: $TOTAL_CHECKS"
    echo -e "${GREEN}Passed: $PASSED_CHECKS${NC}"
    echo -e "${YELLOW}Warnings: $WARNING_CHECKS${NC}"
    echo -e "${RED}Failed: $FAILED_CHECKS${NC}"
    echo "Success Rate: $success_rate%"
    echo

    if [ $FAILED_CHECKS -eq 0 ] && [ $success_rate -ge 80 ]; then
        echo -e "${GREEN}✓ VALIDATION PASSED${NC}"
        echo "The FXML4 deployment is ready for production use."
        echo
        echo "Next steps:"
        echo "1. Configure external monitoring (Grafana/Prometheus)"
        echo "2. Set up SSL certificates for ingress"
        echo "3. Configure backup retention policies"
        echo "4. Run load testing"
        return 0
    elif [ $FAILED_CHECKS -eq 0 ]; then
        echo -e "${YELLOW}⚠ VALIDATION PASSED WITH WARNINGS${NC}"
        echo "The deployment is functional but has some recommendations."
        echo "Review the warnings above for optimization opportunities."
        return 0
    else
        echo -e "${RED}✗ VALIDATION FAILED${NC}"
        echo "Critical issues found that need to be addressed before production."
        echo "Review the failed checks above and fix the issues."
        return 1
    fi
}

# Main validation function
main() {
    echo "======================================"
    echo "FXML4 Kubernetes Deployment Validation"
    echo "======================================"
    echo
    echo "Namespace: $NAMESPACE"
    echo "External Database: $EXTERNAL_DB_HOST"
    echo "Timestamp: $(date)"
    echo

    # Run all validation checks
    validate_namespace
    validate_deployments
    validate_networking
    validate_external_database
    validate_application_health
    validate_supporting_services
    validate_monitoring
    validate_security
    validate_pod_security

    # Generate final report
    generate_report
}

# Execute main function
main "$@"
