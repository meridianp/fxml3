# Secrets Management Guide

This guide covers how to manage secrets for FXML4 deployment using GitHub Secrets and Kubernetes.

## Overview

FXML4 uses a two-tier approach for secrets management:
1. **GitHub Secrets**: For CI/CD pipeline and automated deployments
2. **Kubernetes Secrets**: For runtime application configuration

## Setting Up GitHub Secrets

### Quick Setup

Run the interactive setup script:

```bash
./scripts/setup-github-secrets.sh
```

This script will prompt you for all necessary secrets:
- Database passwords
- API keys for external services
- Service configurations

### Manual Setup

You can also set secrets manually using GitHub CLI:

```bash
# Set a single secret
gh secret set SECRET_NAME --repo meridianp/fxml4

# Set from a file
gh secret set SECRET_NAME --repo meridianp/fxml4 < secret_value.txt
```

### Required Secrets

| Secret Name | Description | Example |
|-------------|-------------|---------|
| KUBE_CONFIG | Base64-encoded Kubernetes config | (automated) |
| DB_HOST | External database host | postgres01.tailb381ec.ts.net |
| DB_PORT | External database port | 5431 |
| DB_USER | Database username | postgres |
| DB_PASSWORD | Database password | strong_password_123 |
| DB_NAME | Database name | fxml4 |
| REDIS_PASSWORD | Redis password | redis_secure_pass |
| RABBITMQ_PASSWORD | RabbitMQ password | rabbit_secure_pass |
| GRAFANA_PASSWORD | Grafana admin password | grafana_admin_pass |
| OPENAI_API_KEY | OpenAI API key | sk-... |
| ANTHROPIC_API_KEY | Anthropic API key | sk-ant-... |
| POLYGON_API_KEY | Polygon.io API key | your_polygon_key |
| ALPHA_VANTAGE_API_KEY | Alpha Vantage API key | your_av_key |
| FRED_API_KEY | FRED API key | your_fred_key |
| IB_GATEWAY_HOST | IB Gateway hostname | localhost or IP |
| IB_GATEWAY_PORT | IB Gateway port | 7497 |
| IB_CLIENT_ID | IB client ID | 1 |
| PINECONE_API_KEY | Pinecone API key | your_pinecone_key |
| PINECONE_ENVIRONMENT | Pinecone environment | us-east-1-aws |

## How Secrets Flow to Your Application

1. **GitHub Actions** reads secrets from repository settings
2. **CI/CD Pipeline** creates Kubernetes secrets during deployment
3. **Kubernetes** mounts secrets as environment variables
4. **Application** reads from environment variables

```
GitHub Secrets → CI/CD → Kubernetes Secrets → Pod Environment → Application
```

## Local Development

For local development, use `.env.production`:

```bash
# Copy template
cp .env.production.example .env.production

# Edit with your values
nano .env.production

# Deploy locally
./scripts/deploy/deploy.sh
```

## Viewing and Managing Secrets

### GitHub Secrets

```bash
# List all secrets
gh secret list --repo meridianp/fxml4

# Update a secret
gh secret set SECRET_NAME --repo meridianp/fxml4
```

### Kubernetes Secrets

```bash
# View secret names
kubectl get secrets -n fxml4

# Describe a secret (doesn't show values)
kubectl describe secret fxml4-secrets -n fxml4

# Get secret values (base64 encoded)
kubectl get secret fxml4-secrets -n fxml4 -o yaml

# Decode a specific value
kubectl get secret fxml4-secrets -n fxml4 -o jsonpath="{.data.openai-api-key}" | base64 -d
```

## Security Best Practices

1. **Never commit secrets** to version control
2. **Use strong passwords** for all services
3. **Rotate secrets regularly** (every 90 days)
4. **Limit access** to production secrets
5. **Use different secrets** for dev/staging/production
6. **Monitor secret usage** in logs and metrics

## Troubleshooting

### Secret Not Found

If your application can't find a secret:

1. Check GitHub secret exists:
   ```bash
   gh secret list --repo meridianp/fxml4 | grep SECRET_NAME
   ```

2. Check Kubernetes secret:
   ```bash
   kubectl get secret fxml4-secrets -n fxml4
   ```

3. Verify pod environment:
   ```bash
   kubectl exec -it <pod-name> -n fxml4 -- env | grep SECRET_NAME
   ```

### Updating Secrets

To update a secret:

1. Update in GitHub:
   ```bash
   gh secret set SECRET_NAME --repo meridianp/fxml4
   ```

2. Trigger redeployment:
   ```bash
   # Option 1: Push to trigger CI/CD
   git commit --allow-empty -m "Trigger deployment"
   git push

   # Option 2: Manual restart
   kubectl rollout restart deployment/fxml4-api -n fxml4
   ```

## Emergency Procedures

If you need to quickly update a secret in production:

```bash
# Direct Kubernetes update (temporary)
kubectl create secret generic fxml4-secrets-patch \
  --from-literal=openai-api-key=new_key \
  --dry-run=client -o yaml | kubectl apply -f -

# Then update GitHub secret for persistence
gh secret set OPENAI_API_KEY --repo meridianp/fxml4
```

Remember: Always update GitHub secrets to ensure persistence across deployments!
