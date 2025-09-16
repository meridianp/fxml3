# FXML4 UI Production Deployment Guide

## Overview

This guide covers the production deployment of the FXML4 Trading Platform Frontend. The application is designed for high availability, scalability, and security in production environments.

## Architecture

### Production Stack
- **Frontend**: Next.js React application with TypeScript
- **Reverse Proxy**: Nginx for load balancing and SSL termination
- **Caching**: Redis for session storage and application caching
- **Container Runtime**: Docker with multi-stage builds
- **Orchestration**: Kubernetes with horizontal pod autoscaling
- **Registry**: GitHub Container Registry (GHCR)

### Security Features
- Non-root container execution
- Security headers and CSP policies
- SSL/TLS encryption
- Container vulnerability scanning
- Network policies and ingress controls

## Quick Start

### Docker Deployment

1. **Clone and setup**:
   ```bash
   git clone <repository>
   cd fxml4-ui
   cp .env.production.example .env.production
   # Edit .env.production with your configuration
   ```

2. **Deploy with Docker Compose**:
   ```bash
   ./scripts/deploy.sh deploy production
   ```

3. **Verify deployment**:
   ```bash
   ./scripts/deploy.sh health
   ```

### Kubernetes Deployment

1. **Prerequisites**:
   - Kubernetes cluster (v1.24+)
   - kubectl configured
   - Nginx Ingress Controller
   - Cert-manager (for SSL certificates)

2. **Deploy to Kubernetes**:
   ```bash
   # Create namespace and apply manifests
   kubectl apply -f k8s/namespace.yaml
   kubectl apply -f k8s/configmap.yaml
   kubectl apply -f k8s/secrets.yaml  # Update with real secrets first
   kubectl apply -f k8s/deployment.yaml
   ```

3. **Verify deployment**:
   ```bash
   kubectl get pods -n fxml4-ui
   kubectl logs -f deployment/fxml4-ui -n fxml4-ui
   ```

## Configuration

### Environment Variables

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `NODE_ENV` | Environment mode | `production` | Yes |
| `PORT` | Application port | `3000` | No |
| `NEXT_PUBLIC_API_URL` | Backend API URL | - | Yes |
| `NEXT_PUBLIC_WS_URL` | WebSocket URL | - | Yes |
| `REDIS_URL` | Redis connection string | - | Yes |
| `UI_DOMAIN` | Application domain | `localhost` | No |

### Performance Settings

| Variable | Description | Default |
|----------|-------------|---------|
| `NEXT_PUBLIC_ENABLE_PERFORMANCE_MONITORING` | Enable performance tracking | `true` |
| `NEXT_PUBLIC_PERFORMANCE_SAMPLE_RATE` | Performance sampling rate | `0.1` |

### Security Configuration

| Variable | Description | Default |
|----------|-------------|---------|
| `SECURE_COOKIES` | Enable secure cookies | `true` |
| `NEXT_PUBLIC_CSP_NONCE` | Content Security Policy nonce | `auto` |

## Deployment Scripts

### Available Commands

```bash
# Full deployment
./scripts/deploy.sh deploy

# Build only
./scripts/deploy.sh build

# Start services
./scripts/deploy.sh up

# Stop services
./scripts/deploy.sh down

# Restart services
./scripts/deploy.sh restart

# View logs
./scripts/deploy.sh logs

# Check status
./scripts/deploy.sh status

# Health check
./scripts/deploy.sh health

# Cleanup unused resources
./scripts/deploy.sh cleanup

# Rollback deployment
./scripts/deploy.sh rollback
```

## CI/CD Pipeline

### GitHub Actions Workflow

The production deployment is automated through GitHub Actions:

1. **Build & Test**: Code quality, unit tests, E2E tests
2. **Security Scan**: Container vulnerability scanning
3. **Deploy Staging**: Automatic staging deployment
4. **Deploy Production**: Manual approval for production
5. **Notification**: Slack notifications for deployment status

### Triggering Deployments

- **Automatic**: Push to `main` branch deploys to staging
- **Manual**: Create release tag (`v*`) for production
- **Emergency**: Use workflow dispatch for immediate deployment

## Monitoring & Observability

### Health Checks

- **Application**: `GET /api/health`
- **Load Balancer**: `GET /health`
- **Kubernetes**: Liveness, readiness, and startup probes

### Performance Monitoring

- **Core Web Vitals**: FCP, LCP, CLS, FID tracking
- **Resource Usage**: Memory, CPU, network monitoring
- **Bundle Analysis**: Automated bundle size tracking
- **Performance Budgets**: Configurable performance thresholds

### Logging

- **Application Logs**: Structured JSON logging
- **Access Logs**: Nginx request/response logging
- **Error Tracking**: Integration with Sentry (optional)

## Security

### Container Security

- Multi-stage Docker builds for minimal attack surface
- Non-root user execution (`uid: 1001`)
- Read-only root filesystem where possible
- Regular base image updates

### Network Security

- Network policies to restrict pod-to-pod communication
- Ingress controls with SSL termination
- Rate limiting on API endpoints
- CORS configuration for cross-origin requests

### Application Security

- Content Security Policy (CSP) headers
- XSS and CSRF protection
- Secure cookie configuration
- Environment variable encryption for secrets

## Scaling

### Horizontal Scaling

```bash
# Scale pods in Kubernetes
kubectl scale deployment fxml4-ui --replicas=5 -n fxml4-ui

# Auto-scaling based on CPU/memory
kubectl autoscale deployment fxml4-ui --cpu-percent=70 --min=2 --max=10 -n fxml4-ui
```

### Vertical Scaling

Update resource requests/limits in `k8s/deployment.yaml`:

```yaml
resources:
  requests:
    memory: "512Mi"
    cpu: "400m"
  limits:
    memory: "1Gi"
    cpu: "1000m"
```

## Backup & Recovery

### Application State

- **Redis Data**: Automated backups to persistent storage
- **Configuration**: GitOps approach with version control
- **Container Images**: Multi-architecture builds with retention policy

### Disaster Recovery

1. **Rollback Deployment**:
   ```bash
   ./scripts/deploy.sh rollback
   ```

2. **Manual Recovery**:
   ```bash
   # Restore from specific image tag
   kubectl set image deployment/fxml4-ui fxml4-ui=ghcr.io/fxml4/ui:v1.0.0 -n fxml4-ui
   ```

## Troubleshooting

### Common Issues

1. **Application Won't Start**:
   ```bash
   # Check pod logs
   kubectl logs -f deployment/fxml4-ui -n fxml4-ui

   # Check events
   kubectl get events -n fxml4-ui --sort-by='.lastTimestamp'
   ```

2. **High Memory Usage**:
   ```bash
   # Monitor resource usage
   kubectl top pods -n fxml4-ui

   # Check for memory leaks
   ./scripts/deploy.sh health
   ```

3. **SSL Certificate Issues**:
   ```bash
   # Check certificate status
   kubectl describe certificate fxml4-ui-tls -n fxml4-ui

   # Force certificate renewal
   kubectl delete certificate fxml4-ui-tls -n fxml4-ui
   ```

### Performance Issues

1. **Slow Response Times**:
   - Check Redis connectivity
   - Review application logs for errors
   - Monitor network latency between services

2. **High CPU Usage**:
   - Review performance benchmarks
   - Check for infinite loops or inefficient algorithms
   - Consider horizontal scaling

### Debug Mode

Enable debug logging:

```bash
# Set log level to debug
kubectl set env deployment/fxml4-ui LOG_LEVEL=debug -n fxml4-ui
```

## Maintenance

### Regular Updates

1. **Security Updates**:
   - Monitor for CVEs in base images
   - Update dependencies monthly
   - Rotate secrets quarterly

2. **Performance Optimization**:
   - Review bundle size monthly
   - Update performance budgets
   - Optimize Docker layers

3. **Monitoring**:
   - Review logs weekly
   - Check performance metrics
   - Update alerting thresholds

### Scheduled Maintenance

```bash
# Schedule maintenance window
kubectl annotate deployment fxml4-ui deployment.kubernetes.io/revision=maintenance-$(date +%Y%m%d)

# Perform rolling restart
kubectl rollout restart deployment/fxml4-ui -n fxml4-ui
```

## Support

### Documentation

- [API Documentation](./docs/api.md)
- [Component Documentation](./docs/components.md)
- [Testing Guide](./docs/testing.md)

### Contacts

- **DevOps Team**: devops@fxml4.com
- **Development Team**: dev@fxml4.com
- **Security Team**: security@ftml4.com

### Emergency Procedures

1. **Critical Bug**: Immediate rollback + hotfix
2. **Security Incident**: Take offline + investigate
3. **Performance Issue**: Scale up + investigate

---

*This guide is maintained by the FXML4 DevOps team. Last updated: $(date +%Y-%m-%d)*
