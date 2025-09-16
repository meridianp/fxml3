# FXML4 Deployment Guide

This comprehensive guide covers deploying FXML4 in various environments from development to production.

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Environment Setup](#environment-setup)
3. [Development Deployment](#development-deployment)
4. [Staging Deployment](#staging-deployment)
5. [Production Deployment](#production-deployment)
6. [Configuration Management](#configuration-management)
7. [Health Checks](#health-checks)
8. [Rollback Procedures](#rollback-procedures)
9. [Security Considerations](#security-considerations)

## Prerequisites

### System Requirements

**Minimum Requirements:**
- CPU: 2 cores, 2.0 GHz
- RAM: 4 GB
- Storage: 20 GB SSD
- Network: 100 Mbps

**Recommended for Production:**
- CPU: 8 cores, 3.0 GHz
- RAM: 16 GB
- Storage: 100 GB SSD
- Network: 1 Gbps

### Software Dependencies

- Docker Engine 20.10+
- Docker Compose 2.0+
- PostgreSQL 13+ (or Docker container)
- TimescaleDB extension
- Redis 6.0+ (for caching)
- Nginx 1.20+ (reverse proxy)

### External Services

- Google Cloud Project (for Vertex AI)
- Alpha Vantage API key
- Interactive Brokers account (optional)
- SSL certificates (production)

## Environment Setup

### 1. Clone Repository

```bash
git clone https://github.com/meridianp/fxml4.git
cd fxml4
git checkout main
```

### 2. Environment Variables

Create environment-specific `.env` files:

#### Development (.env.dev)

```bash
# Database Configuration
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/fxml4_dev
TIMESCALEDB_URL=postgresql://postgres:postgres@localhost:5433/fxml4_dev

# API Configuration
API_HOST=0.0.0.0
API_PORT=8000
API_DEBUG=true
SECRET_KEY=your-dev-secret-key-here

# External APIs
ALPHA_VANTAGE_API_KEY=your-alpha-vantage-key
OPENAI_API_KEY=your-openai-key

# Google Cloud
GCP_PROJECT=fxml4-dev
GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account.json

# Redis
REDIS_URL=redis://localhost:6379/0

# Logging
LOG_LEVEL=DEBUG
```

#### Production (.env.prod)

```bash
# Database Configuration
DATABASE_URL=postgresql://user:password@db-host:5432/fxml4_prod
TIMESCALEDB_URL=postgresql://user:password@timescale-host:5432/fxml4_prod

# API Configuration
API_HOST=0.0.0.0
API_PORT=8000
API_DEBUG=false
SECRET_KEY=your-production-secret-key-here

# External APIs
ALPHA_VANTAGE_API_KEY=your-alpha-vantage-key
OPENAI_API_KEY=your-openai-key

# Google Cloud
GCP_PROJECT=fxml4-prod
GOOGLE_APPLICATION_CREDENTIALS=/app/credentials/service-account.json

# Redis
REDIS_URL=redis://redis-host:6379/0

# Logging
LOG_LEVEL=INFO

# Security
CORS_ORIGINS=["https://your-domain.com"]
ALLOWED_HOSTS=["your-domain.com", "api.your-domain.com"]
```

## Development Deployment

### Local Docker Development

1. **Start Infrastructure Services**

```bash
# Start databases
docker-compose -f docker-compose.dev.yml up -d postgres timescaledb redis

# Wait for services to be ready
sleep 30

# Run database migrations
python scripts/init_db.py
```

2. **Start FXML4 Services**

```bash
# Build and start all services
docker-compose -f docker-compose.dev.yml up --build

# Or start individual services
docker-compose -f docker-compose.dev.yml up api worker dashboard
```

3. **Verify Deployment**

```bash
# Check API health
curl http://localhost:8000/health

# Check dashboard
curl http://localhost:8501

# View logs
docker-compose -f docker-compose.dev.yml logs -f api
```

### Local Python Development

1. **Setup Virtual Environment**

```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
# or
venv\Scripts\activate     # Windows

pip install -r requirements-stable.txt
```

2. **Initialize Database**

```bash
# Start only databases
docker-compose -f docker-compose.dev.yml up -d postgres timescaledb

# Run migrations
python scripts/init_db.py
```

3. **Start Services**

```bash
# Terminal 1: API Server
uvicorn fxml4.api.main:app --host 0.0.0.0 --port 8000 --reload

# Terminal 2: Background Worker
python -m fxml4.worker.main

# Terminal 3: Dashboard
streamlit run fxml4/ui/streamlit_app.py --server.port 8501
```

## Staging Deployment

### AWS/GCP Staging Environment

1. **Infrastructure Setup**

```bash
# Create staging namespace
kubectl create namespace fxml4-staging

# Deploy TimescaleDB
helm install timescaledb timescale/timescaledb-single \
  --namespace fxml4-staging \
  --set secrets.postgres.password=staging-password

# Deploy Redis
helm install redis bitnami/redis \
  --namespace fxml4-staging \
  --set auth.password=staging-redis-password
```

2. **Application Deployment**

```bash
# Build and push Docker image
docker build -t fxml4:staging .
docker tag fxml4:staging gcr.io/fxml4-staging/fxml4:latest
docker push gcr.io/fxml4-staging/fxml4:latest

# Deploy application
kubectl apply -f k8s/staging/ -n fxml4-staging

# Wait for deployment
kubectl rollout status deployment/fxml4-api -n fxml4-staging
```

3. **Post-Deployment Verification**

```bash
# Get service endpoints
kubectl get services -n fxml4-staging

# Run health checks
kubectl exec -it deployment/fxml4-api -n fxml4-staging -- \
  curl http://localhost:8000/health

# Check logs
kubectl logs -f deployment/fxml4-api -n fxml4-staging
```

## Production Deployment

### Production Checklist

- [ ] SSL certificates configured
- [ ] Database backups scheduled
- [ ] Monitoring and alerting active
- [ ] Security scanning completed
- [ ] Load testing completed
- [ ] Disaster recovery plan documented
- [ ] Health checks configured

### Blue-Green Deployment

1. **Prepare Green Environment**

```bash
# Create green deployment
kubectl apply -f k8s/production/green-deployment.yaml

# Wait for green to be ready
kubectl rollout status deployment/fxml4-api-green

# Run health checks on green
kubectl exec -it deployment/fxml4-api-green -- \
  curl http://localhost:8000/health
```

2. **Switch Traffic**

```bash
# Update service selector to point to green
kubectl patch service fxml4-api -p '{"spec":{"selector":{"version":"green"}}}'

# Verify traffic is flowing
curl https://api.yourdomain.com/health
```

3. **Cleanup Blue Environment**

```bash
# After verification, scale down blue
kubectl scale deployment fxml4-api-blue --replicas=0

# Later, delete blue deployment
kubectl delete deployment fxml4-api-blue
```

### Rolling Deployment

1. **Update Image**

```bash
# Build and push new image
docker build -t fxml4:v1.2.0 .
docker tag fxml4:v1.2.0 gcr.io/fxml4-prod/fxml4:v1.2.0
docker push gcr.io/fxml4-prod/fxml4:v1.2.0
```

2. **Deploy Update**

```bash
# Update deployment
kubectl set image deployment/fxml4-api \
  api=gcr.io/fxml4-prod/fxml4:v1.2.0

# Monitor rollout
kubectl rollout status deployment/fxml4-api

# Verify deployment
kubectl get pods -l app=fxml4-api
```

## Configuration Management

### Environment-Specific Configurations

```yaml
# config/environments/production.yaml
api:
  host: "0.0.0.0"
  port: 8000
  debug: false
  cors_origins:
    - "https://app.yourdomain.com"
    - "https://dashboard.yourdomain.com"

database:
  pool_size: 20
  max_overflow: 30
  pool_timeout: 30
  pool_recycle: 3600

backtesting:
  max_concurrent_backtests: 5
  result_retention_days: 90

logging:
  level: "INFO"
  format: "json"

monitoring:
  metrics_enabled: true
  tracing_enabled: true
  health_check_interval: 30
```

### Secret Management

```bash
# Kubernetes secrets
kubectl create secret generic fxml4-secrets \
  --from-literal=database-password=your-db-password \
  --from-literal=secret-key=your-secret-key \
  --from-literal=alpha-vantage-key=your-av-key

# Google Secret Manager
gcloud secrets create fxml4-database-password --data-file=password.txt
```

## Health Checks

### Readiness Probes

```yaml
readinessProbe:
  httpGet:
    path: /health
    port: 8000
  initialDelaySeconds: 30
  periodSeconds: 10
  timeoutSeconds: 5
  failureThreshold: 3
```

### Liveness Probes

```yaml
livenessProbe:
  httpGet:
    path: /health
    port: 8000
  initialDelaySeconds: 60
  periodSeconds: 30
  timeoutSeconds: 10
  failureThreshold: 3
```

### Custom Health Checks

```bash
#!/bin/bash
# health-check.sh

# Check API health
API_HEALTH=$(curl -s http://localhost:8000/health | jq -r '.status')
if [ "$API_HEALTH" != "ok" ]; then
  echo "API health check failed"
  exit 1
fi

# Check database connectivity
DB_HEALTH=$(python -c "from fxml4.config import get_db_connection; get_db_connection().execute('SELECT 1')")
if [ $? -ne 0 ]; then
  echo "Database connectivity check failed"
  exit 1
fi

# Check external API connectivity
AV_HEALTH=$(curl -s "https://www.alphavantage.co/query?function=TIME_SERIES_INTRADAY&symbol=IBM&interval=1min&apikey=$ALPHA_VANTAGE_API_KEY" | jq -r '.Meta Data')
if [ "$AV_HEALTH" == "null" ]; then
  echo "Alpha Vantage API check failed"
  exit 1
fi

echo "All health checks passed"
exit 0
```

## Rollback Procedures

### Immediate Rollback

```bash
# Rollback to previous deployment
kubectl rollout undo deployment/fxml4-api

# Check rollback status
kubectl rollout status deployment/fxml4-api

# Verify application health
curl https://api.yourdomain.com/health
```

### Database Rollback

```bash
# Stop application
kubectl scale deployment fxml4-api --replicas=0

# Restore database from backup
pg_restore -h db-host -U postgres -d fxml4_prod backup_file.sql

# Restart application
kubectl scale deployment fxml4-api --replicas=3
```

### Configuration Rollback

```bash
# Revert configuration changes
kubectl apply -f k8s/production/previous-config.yaml

# Restart pods to pick up configuration
kubectl rollout restart deployment/fxml4-api
```

## Security Considerations

### Network Security

- Use private subnets for databases
- Configure security groups/firewall rules
- Enable VPC flow logs
- Use WAF for API protection

### Application Security

- Enable HTTPS only
- Configure CORS properly
- Use secure session cookies
- Implement rate limiting
- Regular security scanning

### Data Security

- Encrypt data at rest
- Encrypt data in transit
- Regular database backups
- Access logging and monitoring
- Principle of least privilege

### Monitoring and Alerting

```yaml
# alerting-rules.yaml
groups:
  - name: fxml4-alerts
    rules:
      - alert: APIHighErrorRate
        expr: rate(http_requests_total{status=~"5.."}[5m]) > 0.1
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: "High error rate detected"

      - alert: DatabaseConnectionPoolExhausted
        expr: db_connection_pool_active / db_connection_pool_max > 0.9
        for: 2m
        labels:
          severity: warning
        annotations:
          summary: "Database connection pool nearly exhausted"
```

## Troubleshooting Quick Reference

### Common Issues

1. **Container won't start**
   ```bash
   # Check logs
   docker logs <container_id>
   kubectl logs <pod_name>

   # Check resource limits
   kubectl describe pod <pod_name>
   ```

2. **Database connection issues**
   ```bash
   # Test connection
   psql -h <host> -U <user> -d <database> -c "SELECT 1"

   # Check connection pool
   kubectl exec -it <pod> -- python -c "from fxml4.config import get_db_connection; print(get_db_connection())"
   ```

3. **Performance issues**
   ```bash
   # Check resource usage
   kubectl top pods
   kubectl top nodes

   # Check application metrics
   curl http://localhost:8000/metrics
   ```

For detailed troubleshooting, see [Troubleshooting Guide](troubleshooting-guide.md).
