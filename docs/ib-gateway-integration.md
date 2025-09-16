# Interactive Brokers Gateway Integration

This document explains how to use the containerized Interactive Brokers Gateway with FXML4 for automated trading.

## Overview

FXML4 uses a containerized IB Gateway approach for production-ready automated trading:

- **Containerized IB Gateway**: Runs in Docker with automatic session management
- **IBC Automation**: Handles login, 2FA, and session restarts automatically
- **API Integration**: FXML4 connects to Gateway via port 8888
- **Browser Monitoring**: Optional GUI access via noVNC on port 6080

## Architecture Benefits

### Why Containerized Gateway?

1. **Full Automation**: No manual intervention required
2. **Production Ready**: Integrates with Kubernetes deployment
3. **Session Management**: Automatic reconnection and restart policies
4. **Resource Efficiency**: Minimal GUI overhead vs full TWS
5. **Monitoring Integration**: Built-in health checks and logging

### vs Desktop TWS

| Feature | Containerized Gateway | Desktop TWS |
|---------|----------------------|-------------|
| Automation | ✅ Full automation | ❌ Manual session management |
| Resource Usage | ✅ Minimal | ❌ High (full GUI) |
| Production Deploy | ✅ Kubernetes ready | ❌ Desktop dependencies |
| API Access | ✅ Complete | ✅ Complete |
| Session Reliability | ✅ Auto-restart | ❌ Manual intervention |

## Quick Start

### 1. Environment Setup

Add to your `.env` file:

```bash
# Interactive Brokers Configuration
IB_USERNAME=your_username  # Use edemo/demouser for testing
IB_PASSWORD=your_password
IB_TRADING_MODE=paper  # paper or live
IB_HOST=127.0.0.1
IB_PORT=8888
IB_CLIENT_ID=0
```

### 2. Start Services

```bash
# Start all services including IB Gateway
docker-compose -f docker-compose.yml -f docker-compose.ib-gateway.yml up -d

# Or start IB Gateway only
docker-compose up -d ib-gateway
```

### 3. Monitor Startup

```bash
# Check container status
docker-compose ps

# View IB Gateway logs
docker-compose logs -f ib-gateway

# Access Gateway GUI in browser (optional)
# Navigate to: http://localhost:6080
```

### 4. Test Connection

```bash
# Test containerized connection
python scripts/test_containerized_ib_connection.py

# Test with FXML4 API
python scripts/test_api_backtest.py --url http://localhost:8001
```

## Configuration Options

### IB Gateway Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `USERNAME` | IB username | `edemo` |
| `PASSWORD` | IB password | `demouser` |
| `GATEWAY_OR_TWS` | Run gateway or TWS | `gateway` |
| `IBC_TradingMode` | Trading mode | `paper` |
| `IBC_ReadOnlyApi` | Read-only API access | `no` |
| `TWOFA_TIMEOUT_ACTION` | 2FA timeout behavior | `restart` |

### FXML4 Connection Settings

```python
# RobustIBClient configuration
ib_config = {
    "host": "127.0.0.1",        # Use "ib-gateway" for Docker networking
    "port": 8888,               # Containerized gateway port
    "client_id": 0,             # Unique client identifier
    "reconnect_attempts": 10,   # Connection retry attempts
    "circuit_breaker_threshold": 5  # Error threshold
}
```

## Production Deployment

### Kubernetes Integration

```yaml
# k8s/ib-gateway-deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: ib-gateway
spec:
  replicas: 1
  selector:
    matchLabels:
      app: ib-gateway
  template:
    metadata:
      labels:
        app: ib-gateway
    spec:
      containers:
      - name: ib-gateway
        image: ghcr.io/extrange/ibkr:stable
        ports:
        - containerPort: 8888
          name: api
        - containerPort: 6080
          name: vnc
        env:
        - name: USERNAME
          valueFrom:
            secretKeyRef:
              name: ib-credentials
              key: username
        - name: PASSWORD
          valueFrom:
            secretKeyRef:
              name: ib-credentials
              key: password
        - name: IBC_TradingMode
          value: "live"  # or paper
        resources:
          requests:
            memory: "512Mi"
            cpu: "250m"
          limits:
            memory: "1Gi"
            cpu: "500m"
```

### Secrets Management

```bash
# Create IB credentials secret
kubectl create secret generic ib-credentials \
  --from-literal=username='your_username' \
  --from-literal=password='your_password'
```

## Monitoring and Troubleshooting

### Health Checks

The container includes built-in health checks:

```bash
# Check container health
docker-compose ps ib-gateway

# View health check logs
docker inspect --format='{{json .State.Health}}' <container_id>
```

### Common Issues

#### Connection Refused (Error 502)

```bash
# Check if container is running
docker-compose ps ib-gateway

# View startup logs
docker-compose logs ib-gateway

# Check port accessibility
curl http://localhost:8888
```

#### Authentication Issues

1. Verify credentials in environment variables
2. Check IB account permissions for API access
3. Ensure paper trading is enabled if using demo account

#### Session Management

- IBC handles automatic login and 2FA
- Sessions restart automatically on connection loss
- Manual restart: `docker-compose restart ib-gateway`

### Browser Access

Access the IB Gateway GUI through your browser:

1. Navigate to: http://localhost:6080
2. Use for manual configuration or debugging
3. Not required for automated trading

## API Integration

### Connection Example

```python
from fxml4.data_engineering.data_feeds.robust_ib_client import RobustIBClient

# Configure for containerized gateway
config = {
    "host": "127.0.0.1",  # Use "ib-gateway" in Docker network
    "port": 8888,         # Containerized port
    "client_id": 0
}

# Connect and use
client = RobustIBClient(config)
if client.connect():
    print("Connected to containerized IB Gateway!")
    # Your trading logic here
    client.disconnect()
```

### FXML4 Integration

The RobustIBClient automatically:
- Connects to port 8888 by default
- Implements circuit breaker pattern
- Provides automatic reconnection
- Includes comprehensive error handling

## Security Considerations

### Credentials

- Never commit credentials to version control
- Use environment variables or Kubernetes secrets
- Rotate credentials regularly
- Use read-only API access when possible

### Network Security

- Bind ports to localhost only: `127.0.0.1:8888:8888`
- Use Docker networks for service communication
- Implement proper firewall rules in production

## Performance

### Resource Usage

- **Memory**: ~500MB typical, 1GB limit
- **CPU**: Minimal under normal load
- **Disk**: ~2GB for container image
- **Network**: Low bandwidth requirements

### Scaling Considerations

- One IB Gateway per trading account
- Use different client IDs for multiple connections
- Consider load balancing for high-frequency trading

## Development vs Production

### Development Setup

```bash
# Use demo credentials
docker-compose -f docker-compose.yml -f docker-compose.ib-gateway.yml up -d
```

### Production Setup

```bash
# Use production credentials and live trading mode
export IB_USERNAME="your_live_username"
export IB_PASSWORD="your_live_password"
export IB_TRADING_MODE="live"

docker-compose up -d ib-gateway
```

## Next Steps

1. **Test Connection**: Run `scripts/test_containerized_ib_connection.py`
2. **Verify API Access**: Test market data and order placement
3. **Configure Monitoring**: Set up alerts for connection issues
4. **Production Deploy**: Move to Kubernetes with proper secrets
5. **Scale Strategy**: Plan for multiple accounts or higher throughput

For more information, see:
- [Interactive Brokers API Documentation](https://interactivebrokers.github.io/tws-api/)
- [IBC Project Documentation](https://github.com/IbcAlpha/IBC)
- [FXML4 Architecture Overview](./architecture.md)
