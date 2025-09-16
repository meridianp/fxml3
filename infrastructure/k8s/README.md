# FXML4 Kubernetes Production Deployment

This directory contains production-ready Kubernetes manifests for deploying FXML4 with external database connectivity, comprehensive monitoring, and enterprise-grade security.

## 🏗️ Architecture Overview

```
                    ┌─────────────────┐
                    │   Internet      │
                    └─────────┬───────┘
                              │
                    ┌─────────▼───────┐
                    │ Ingress         │
                    │ (NGINX/Traefik) │
                    └─────────┬───────┘
                              │
                    ┌─────────▼───────┐
                    │ FXML4 API       │
                    │ (3 replicas)    │
                    └─────────┬───────┘
                              │
    ┌─────────────────────────┼─────────────────────────┐
    │                         │                         │
    ▼                         ▼                         ▼
┌───────┐              ┌─────────────┐          ┌─────────────┐
│ Redis │              │ RabbitMQ    │          │ Worker Pods │
└───────┘              └─────────────┘          └─────────────┘
                              │
                              ▼
                    ┌─────────────────┐
                    │ External        │
                    │ TimescaleDB     │
                    │ postgres01...   │
                    └─────────────────┘
```

## 📁 Directory Structure

```
k8s/
├── namespace/              # Namespace definition
├── configmaps/             # Application configuration
├── secrets/                # Sensitive configuration
├── deployments/            # Basic service deployments
├── production/             # Production-ready deployments
├── services/               # Service definitions
├── ingress/                # External access configuration
├── security/               # Network policies and security
├── monitoring/             # Prometheus monitoring setup
├── operations/             # Backup, recovery, health checks
├── jobs/                   # Database migrations and one-time jobs
└── ci-cd/                  # CI/CD pipeline configuration
```

## 🚀 Quick Deployment

### Prerequisites

1. **Kubernetes Cluster** (v1.25+)
2. **kubectl** configured with cluster access
3. **External PostgreSQL/TimescaleDB** (postgres01.tailb381ec.ts.net:5432)
4. **Container Registry Access** (GitHub Container Registry)

### Deploy to Production

```bash
# 1. Configure secrets (required)
kubectl create secret generic ftml4-secrets \
  --from-literal=database-password="your-db-password" \
  --from-literal=openai-api-key="your-openai-key" \
  --from-literal=polygon-api-key="your-polygon-key" \
  --namespace=ftml4

# 2. Deploy using automated script
./scripts/deploy-production-k8s.sh

# 3. Validate deployment
./scripts/validate-k8s-deployment.sh
```

## 📋 Manual Deployment Steps

### 1. Base Infrastructure

```bash
# Create namespace
kubectl apply -f k8s/namespace/namespace.yaml

# Apply configuration
kubectl apply -f k8s/configmaps/app-config.yaml
kubectl apply -f k8s/secrets/app-secrets.yaml
```

### 2. Security Configuration

```bash
# Apply network policies
kubectl apply -f k8s/security/network-policies.yaml
```

### 3. Database Migration

```bash
# Run database migrations
kubectl apply -f k8s/jobs/db-migration.yaml
kubectl wait --for=condition=complete job/fxml4-db-migration --timeout=600s
```

### 4. Supporting Services

```bash
# Deploy Redis and RabbitMQ
kubectl apply -f k8s/deployments/redis.yaml
kubectl apply -f k8s/deployments/rabbitmq.yaml
kubectl apply -f k8s/services/redis-service.yaml
kubectl apply -f k8s/services/rabbitmq-service.yaml
```

### 5. Main Application

```bash
# Deploy production API
kubectl apply -f k8s/production/production-api.yaml
kubectl apply -f k8s/services/api-service.yaml

# Deploy workers (if needed)
kubectl apply -f k8s/deployments/worker.yaml
```

### 6. External Access

```bash
# Configure ingress
kubectl apply -f k8s/ingress/ingress.yaml
```

### 7. Monitoring and Operations

```bash
# Deploy monitoring (if Prometheus available)
kubectl apply -f k8s/monitoring/servicemonitor.yaml

# Deploy operational tools
kubectl apply -f k8s/operations/database-operations.yaml
kubectl apply -f k8s/operations/system-health-monitoring.yaml
```

## 🔧 Configuration

### Environment Variables

Key configuration is managed through ConfigMaps and Secrets:

| Variable | Source | Description |
|----------|--------|-------------|
| `FXML4_DATABASE_HOST` | ConfigMap | External TimescaleDB host |
| `FXML4_DATABASE_PASSWORD` | Secret | Database password |
| `OPENAI_API_KEY` | Secret | OpenAI API key |
| `POLYGON_API_KEY` | Secret | Polygon.io API key |

### External Database

The deployment connects to an external PostgreSQL/TimescaleDB instance:
- **Host**: `postgres01.tailb381ec.ts.net`
- **Port**: `5432`
- **Database**: `fxml4`
- **Extensions**: TimescaleDB, pgvector, pgcrypto

### Resource Requirements

#### Production API Deployment
- **Replicas**: 3 (with HPA scaling to 10)
- **CPU**: 250m requests, 500m limits
- **Memory**: 512Mi requests, 1Gi limits
- **Storage**: 50Gi data, 10Gi models

#### Supporting Services
- **Redis**: 128Mi memory, 100m CPU
- **RabbitMQ**: 256Mi memory, 200m CPU

## 🛡️ Security Features

### Network Security
- **Network Policies**: Restrict inter-pod communication
- **External Database**: Dedicated connection from authorized pods only
- **Ingress**: SSL/TLS termination with Let's Encrypt

### Pod Security
- **Non-root users**: All containers run as UID 1000+
- **Read-only filesystems**: Containers use read-only root filesystems
- **Security contexts**: Dropped capabilities, no privilege escalation
- **Resource limits**: CPU, memory, and storage quotas

### RBAC
- **ServiceAccounts**: Minimal permissions per service
- **Roles**: Least-privilege access patterns
- **Secrets**: Separate storage for sensitive data

## 📊 Monitoring

### Health Checks
- **Liveness Probe**: `/health` endpoint (30s interval)
- **Readiness Probe**: `/ready` endpoint (10s interval)
- **Startup Probe**: `/startup` endpoint (5s interval)

### Metrics Collection
- **Prometheus**: ServiceMonitor for metrics scraping
- **Grafana**: Dashboard templates for visualization
- **Alerts**: Critical system and business alerts

### System Monitoring
- **CronJob**: System health checks every 10 minutes
- **Database**: Connection, query performance, table sizes
- **Application**: Response times, error rates, business metrics

## 💾 Backup and Recovery

### Automated Backups
- **Schedule**: Daily at 2 AM UTC
- **Retention**: 30 days local, cloud storage optional
- **Format**: Both SQL dump and pg_dump custom format
- **Verification**: Integrity checks on all backups

### Recovery Procedures
```bash
# Create recovery database
kubectl apply -f k8s/operations/database-operations.yaml

# Monitor recovery job
kubectl logs job/fxml4-db-recovery -f
```

## 🔄 CI/CD Integration

### GitHub Actions Pipeline
The included CI/CD pipeline (`k8s/ci-cd/deployment-pipeline.yaml`) provides:

- **Testing**: Unit, integration, security, performance
- **Building**: Multi-arch container images with signing
- **Staging**: Automated deployment to staging environment
- **Production**: Blue-green deployment with health validation
- **Rollback**: Automatic rollback on deployment failure

### Deployment Workflow
1. **Push to main** → Deploy to staging
2. **Create tag** → Deploy to production
3. **Health checks** → Validate deployment
4. **Performance tests** → Load testing

## 🚨 Troubleshooting

### Common Issues

#### Pods Not Starting
```bash
# Check pod events
kubectl describe pod <pod-name> -n fxml4

# Check logs
kubectl logs <pod-name> -n fxml4

# Check resource constraints
kubectl top pods -n fxml4
```

#### Database Connection Issues
```bash
# Test database connectivity
kubectl run db-test --rm -i --restart=Never --image=postgres:16-alpine -- \
  pg_isready -h postgres01.tailb381ec.ts.net -p 5432 -U postgres

# Check from application pod
kubectl exec deployment/fxml4-api -- \
  python -c "from fxml4.database.timescaledb import TimescaleDBManager; import asyncio; asyncio.run(TimescaleDBManager().initialize())"
```

#### Service Discovery Issues
```bash
# Check services and endpoints
kubectl get services -n ftml4
kubectl get endpoints -n fxml4

# Test internal connectivity
kubectl exec deployment/fxml4-api -- curl http://redis:6379
```

### Debug Commands

```bash
# Comprehensive validation
./scripts/validate-k8s-deployment.sh

# Manual health check
kubectl exec deployment/fxml4-api -- curl http://localhost:8000/health

# Database migration status
kubectl logs job/fxml4-db-migration

# Resource usage
kubectl top nodes
kubectl top pods -n fxml4

# Recent events
kubectl get events -n fxml4 --sort-by='.lastTimestamp'
```

## 🔄 Updates and Maintenance

### Rolling Updates
```bash
# Update image version
kubectl set image deployment/fxml4-api api=ghcr.io/meridianp/fxml4-api:v1.2.0 -n ftml4

# Monitor rollout
kubectl rollout status deployment/fxml4-api -n fxml4

# Rollback if needed
kubectl rollout undo deployment/fxml4-api -n fxml4
```

### Scaling
```bash
# Manual scaling
kubectl scale deployment fxml4-api --replicas=5 -n fxml4

# Check HPA status
kubectl get hpa -n fxml4

# Adjust HPA settings
kubectl patch hpa fxml4-api-hpa -p '{"spec":{"maxReplicas":15}}' -n fxml4
```

## 📈 Performance Optimization

### Resource Tuning
- Monitor resource usage with `kubectl top`
- Adjust requests/limits based on observed usage
- Configure HPA metrics for optimal scaling

### Database Performance
- Monitor connection pools and query performance
- Use continuous aggregates for time-series data
- Implement data retention policies

### Caching Strategy
- Redis for frequently accessed data
- Application-level caching for ML features
- CDN for static assets

## 🔐 Production Checklist

Before deploying to production, ensure:

- [ ] External database connectivity tested
- [ ] All secrets properly configured
- [ ] SSL certificates installed and valid
- [ ] Network policies tested and validated
- [ ] Backup procedures tested
- [ ] Monitoring and alerting configured
- [ ] Resource limits appropriate for load
- [ ] Health checks responding correctly
- [ ] Security scanning completed
- [ ] Performance testing passed
- [ ] Disaster recovery plan documented
- [ ] Team has access to monitoring dashboards
- [ ] On-call procedures established

## 📞 Support

For deployment issues:
1. Check this README for common solutions
2. Run the validation script: `./scripts/validate-k8s-deployment.sh`
3. Review logs and events
4. Consult the troubleshooting section

## 🗂️ Related Documentation

- [FXML4 Architecture](../docs/architecture.md)
- [Database Setup](../docs/deployment/external-database-setup.md)
- [Security Guide](../docs/deployment/secrets-management.md)
- [Monitoring Setup](../docs/deployment/monitoring-guide.md)
- [Operational Procedures](../docs/deployment/operational-runbook.md)
