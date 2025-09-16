# GitHub Container Registry Deployment Guide

This guide covers deploying FXML4 using GitHub Container Registry (ghcr.io) for container image storage.

## Prerequisites

- GitHub account with repository access
- Docker installed locally
- kubectl configured for your Kubernetes cluster
- GitHub Personal Access Token (PAT) with appropriate scopes

## Setup GitHub Container Registry

### 1. Create GitHub Personal Access Token

1. Go to GitHub Settings → Developer settings → Personal access tokens
2. Click "Generate new token (classic)"
3. Select the following scopes:
   - `read:packages` - Download packages from GitHub Package Registry
   - `write:packages` - Upload packages to GitHub Package Registry
   - `delete:packages` - Delete packages from GitHub Package Registry (optional)
   - `repo` - Full control of private repositories (if using private repos)

4. Save the token securely

### 2. Login to GitHub Container Registry

```bash
# Using Docker CLI
docker login ghcr.io -u YOUR_GITHUB_USERNAME -p YOUR_GITHUB_TOKEN

# Or use environment variable
echo $GITHUB_TOKEN | docker login ghcr.io -u YOUR_GITHUB_USERNAME --password-stdin
```

### 3. Configure Kubernetes Secret

```bash
# Create namespace first
kubectl apply -f k8s/namespace/namespace.yaml

# Create image pull secret
kubectl create secret docker-registry ghcr-secret \
  --docker-server=ghcr.io \
  --docker-username=YOUR_GITHUB_USERNAME \
  --docker-password=YOUR_GITHUB_TOKEN \
  --docker-email=YOUR_EMAIL \
  --namespace=fxml4
```

## Building and Pushing Images

### Manual Build and Push

```bash
# Build images
docker build -t ghcr.io/meridianp/fxml4-api:latest .
docker build -t ghcr.io/meridianp/fxml4-dashboard:latest .
docker build -t ghcr.io/meridianp/fxml4-worker:latest .

# Push images
docker push ghcr.io/meridianp/fxml4-api:latest
docker push ghcr.io/meridianp/fxml4-dashboard:latest
docker push ghcr.io/meridianp/fxml4-worker:latest
```

### Automated CI/CD

The GitHub Actions workflow (`.github/workflows/deploy.yml`) automatically:
1. Runs tests on every push
2. Builds multi-architecture images (amd64, arm64)
3. Pushes to ghcr.io with appropriate tags
4. Deploys to Kubernetes on main/develop branches

## Deployment

### 1. Prepare Environment

```bash
# Copy and edit production environment file
cp .env.production.example .env.production
# Edit .env.production with your actual values
```

### 2. Deploy to Kubernetes

```bash
# Run the deployment script
./scripts/deploy/deploy.sh
```

This script will:
- Check prerequisites
- Create/update secrets
- Deploy infrastructure services (TimescaleDB, Redis, RabbitMQ)
- Deploy application services (API, Dashboard, Worker)
- Wait for all services to be ready
- Display connection information

### 3. Verify Deployment

```bash
# Check deployment health
./scripts/deploy/check-deployment.sh

# View pods
kubectl get pods -n fxml4

# View services
kubectl get svc -n fxml4

# Check logs
kubectl logs -f deployment/fxml4-api -n fxml4
```

## Using Docker Compose (Alternative)

For non-Kubernetes deployments, use the production docker-compose:

```bash
# Pull latest images
docker-compose -f docker-compose.prod.yml pull

# Start services
docker-compose -f docker-compose.prod.yml up -d

# View logs
docker-compose -f docker-compose.prod.yml logs -f
```

## Rollback Procedures

If issues occur after deployment:

```bash
# Interactive rollback
./scripts/deploy/rollback.sh

# Rollback specific service
./scripts/deploy/rollback.sh fxml4-api

# Rollback to specific revision
./scripts/deploy/rollback.sh fxml4-api 3
```

## Monitoring and Maintenance

### Access Services

```bash
# Port forward to access services locally
kubectl port-forward svc/fxml4-api 8000:8000 -n fxml4
kubectl port-forward svc/fxml4-dashboard 8501:8501 -n fxml4
kubectl port-forward svc/rabbitmq 15672:15672 -n fxml4
```

### View Metrics

```bash
# Prometheus metrics
kubectl port-forward svc/prometheus 9090:9090 -n fxml4

# Grafana dashboards
kubectl port-forward svc/grafana 3000:3000 -n fxml4
```

### Update Images

To update to new versions:

1. Build and push new images with appropriate tags
2. Update deployments:
   ```bash
   kubectl set image deployment/fxml4-api api=ghcr.io/meridianp/fxml4-api:v1.2.0 -n fxml4
   ```
3. Monitor rollout:
   ```bash
   kubectl rollout status deployment/fxml4-api -n fxml4
   ```

## Security Best Practices

1. **Image Scanning**: Enable vulnerability scanning in GitHub
2. **Secret Management**: Use Kubernetes secrets, never hardcode credentials
3. **Network Policies**: Implement Kubernetes network policies
4. **RBAC**: Configure proper role-based access control
5. **Image Signing**: Consider using cosign for image signing

## Troubleshooting

### Image Pull Errors

```bash
# Check secret exists
kubectl get secret ghcr-secret -n fxml4

# Verify secret content
kubectl get secret ghcr-secret -n fxml4 -o yaml

# Test pull manually
docker pull ghcr.io/meridianp/fxml4-api:latest
```

### Pod Startup Issues

```bash
# Describe pod for events
kubectl describe pod <pod-name> -n fxml4

# Check container logs
kubectl logs <pod-name> -n fxml4 --previous
```

### Service Connectivity

```bash
# Test service DNS
kubectl run test-pod --image=busybox -it --rm --restart=Never -- nslookup fxml4-api.fxml4.svc.cluster.local

# Test service endpoint
kubectl run test-pod --image=curlimages/curl -it --rm --restart=Never -- curl http://fxml4-api:8000/health
```

## Additional Resources

- [GitHub Container Registry Documentation](https://docs.github.com/en/packages/working-with-a-github-packages-registry/working-with-the-container-registry)
- [Kubernetes Documentation](https://kubernetes.io/docs/)
- [Docker Documentation](https://docs.docker.com/)
