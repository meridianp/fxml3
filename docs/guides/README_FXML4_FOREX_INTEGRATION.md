# FXML4-ForexConnect Integration 🚀

A complete integration between FXML4's advanced trading platform and FXCM's ForexConnect API, enabling production-ready forex trading with modern Python infrastructure.

## Overview

This integration bridges two powerful systems:

- **FXML4**: Modern FastAPI-based trading platform with ML capabilities, real-time WebSocket streaming, and comprehensive risk management
- **ForexConnect Middleware**: Production-ready RabbitMQ bridge to FXCM's ForexConnect API with Python 3.7 compatibility

## Architecture

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────────┐
│   FXML4 API     │    │   Shared         │    │  ForexConnect       │
│   (Python 3.11) │◀──▶│   RabbitMQ       │◀──▶│  Middleware         │
│                 │    │                  │    │  (Python 3.7)      │
└─────────────────┘    └──────────────────┘    └─────────────────────┘
         │                        │                        │
         ▼                        ▼                        ▼
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────────┐
│  TimescaleDB    │    │    Prometheus    │    │   FXCM API          │
│  (Time-series)  │    │   (Monitoring)   │    │   (ForexConnect)    │
└─────────────────┘    └──────────────────┘    └─────────────────────┘
```

## Key Features

### 🔗 Seamless Integration
- **Bidirectional Message Translation**: Automatic conversion between FIX and ForexConnect formats
- **Symbol Mapping**: Intelligent currency pair format conversion (EURUSD ↔ EUR/USD)
- **Quantity Conversion**: Automatic units/lots conversion based on instrument specifications
- **Real-time Synchronization**: Live order status updates and market data streaming

### 🛡️ Enterprise-Ready
- **Health Monitoring**: Comprehensive system health checks and alerting
- **Error Handling**: Robust error handling with automatic retry mechanisms
- **Configuration Management**: Environment-specific configuration with credential protection
- **Docker Orchestration**: Complete containerized deployment with service dependencies

### 📊 Advanced Monitoring
- **Prometheus Metrics**: Performance monitoring for all system components
- **Grafana Dashboards**: Real-time visualization of trading metrics and system health
- **Structured Logging**: Comprehensive audit trails with correlation tracking
- **Alerting**: Proactive alerts for system issues and trading anomalies

### 🚀 High Performance
- **Async Architecture**: Non-blocking I/O for maximum throughput
- **Connection Pooling**: Efficient resource utilization for database and message queue connections
- **Message Batching**: Optimized message processing for high-frequency trading
- **Caching**: Redis-based caching for frequently accessed data

## Quick Start

### Prerequisites

- Docker and Docker Compose
- FXCM trading account (demo or live)
- Valid FXCM ForexConnect API access

### 1. Clone and Setup

```bash
git clone <repository>
cd fxml4

# Copy and configure environment
cp .env.fxml4-forex .env
# Edit .env with your FXCM credentials and database passwords
```

### 2. Configure FXCM Credentials

Edit `.env` file:

```bash
# FXCM ForexConnect API Credentials
FOREX_USER_ID=your_fxcm_username
FOREX_PASSWORD=your_fxcm_password
FOREX_CONNECTION=Demo  # Use "Demo" for demo account, "Real" for live
```

### 3. Start the Integrated System

```bash
# Start everything with orchestration script
python scripts/start_fxml4_forex_integration.py

# Or manually with docker-compose
docker-compose -f docker-compose.fxml4-forex.yml up -d
```

### 4. Verify System Health

The startup script will automatically verify all components are healthy. You can also check manually:

```bash
# Check system status
python scripts/start_fxml4_forex_integration.py --status

# Check individual services
curl http://localhost:8000/health      # FXML4 API
curl http://localhost:8080/health      # ForexConnect Middleware
```

## Web Interfaces

| Service | URL | Description |
|---------|-----|-------------|
| FXML4 API | http://localhost:8000 | REST API and documentation |
| FXML4 Dashboard | http://localhost:8501 | Streamlit trading dashboard |
| RabbitMQ Management | http://localhost:15672 | Message queue monitoring |
| Grafana | http://localhost:3000 | System monitoring dashboards |
| Prometheus | http://localhost:9090 | Metrics and alerting |

Default credentials:
- RabbitMQ: `fxml4` / `<RABBITMQ_PASSWORD>`
- Grafana: `admin` / `<GRAFANA_PASSWORD>`

## Trading Operations

### Submit Orders via API

```python
import requests

# Market order
order = {
    "symbol": "EURUSD",
    "side": "buy",
    "quantity": 100000,
    "order_type": "market"
}

response = requests.post("http://localhost:8000/orders", json=order)
print(f"Order ID: {response.json()['order_id']}")
```

### Subscribe to Market Data

```python
import asyncio
import websockets
import json

async def listen_to_prices():
    uri = "ws://localhost:8000/ws"
    async with websockets.connect(uri) as websocket:
        # Subscribe to EUR/USD prices
        subscribe_msg = {
            "action": "subscribe",
            "type": "market_data",
            "symbols": ["EURUSD"]
        }
        await websocket.send(json.dumps(subscribe_msg))

        # Listen for updates
        async for message in websocket:
            data = json.loads(message)
            print(f"EUR/USD: {data['bid']}/{data['ask']}")

asyncio.run(listen_to_prices())
```

## Configuration

### System Configuration

Main configuration is in `config/fxcm_integration.yaml`:

```yaml
# RabbitMQ settings
rabbitmq:
  host: rabbitmq
  port: 5672
  username: fxml4

# FXCM bridge settings
fxml4:
  brokers:
    fxcm_bridge:
      enabled: true
      bridge_url: http://forex-middleware:8080
      features:
        market_data: true
        order_management: true
      limits:
        max_orders_per_second: 20
        max_position_size: 10000000
```

### Environment Variables

Key environment variables in `.env`:

```bash
# System
ENVIRONMENT=development
LOG_LEVEL=INFO

# Database
POSTGRES_PASSWORD=your_secure_password

# RabbitMQ
RABBITMQ_PASSWORD=your_secure_password

# FXCM
FOREX_USER_ID=your_username
FOREX_PASSWORD=your_password
FOREX_CONNECTION=Demo
```

## Message Flow

### Order Submission
1. **FXML4 API** receives order via REST/WebSocket
2. **Bridge Adapter** translates FIX message to ForexConnect format
3. **RabbitMQ** routes message to ForexConnect middleware
4. **ForexConnect Middleware** submits order to FXCM API
5. **Execution Report** flows back through the same path in reverse

### Market Data Streaming
1. **ForexConnect Middleware** subscribes to FXCM price feeds
2. **RabbitMQ** distributes market data updates
3. **Bridge Adapter** translates to FXML4 format
4. **FXML4 API** broadcasts via WebSocket to connected clients

## Monitoring and Alerting

### Prometheus Metrics

Key metrics tracked:

- `fxml4_orders_submitted_total` - Total orders submitted
- `fxml4_orders_executed_total` - Total orders executed
- `fxml4_order_latency_seconds` - Order processing latency
- `forex_connection_status` - ForexConnect connection status
- `rabbitmq_queue_depth` - Message queue backlogs

### Grafana Dashboards

Pre-configured dashboards show:

- **Trading Overview**: Order flow, execution rates, P&L
- **System Health**: Service status, resource utilization
- **Performance**: Latency metrics, throughput analysis
- **ForexConnect**: API connection status, error rates

### Alerting Rules

Automatic alerts for:

- ForexConnect API disconnection
- High order rejection rates (>5%)
- Excessive latency (>2s P95)
- Queue depth thresholds
- Database connectivity issues

## Development and Testing

### Running Tests

```bash
# Unit tests
pytest tests/unit/ -v

# Integration tests (requires running system)
pytest tests/integration/test_fxcm_bridge_integration.py -v

# All tests
pytest tests/ -v --cov=fxml4
```

### Local Development

```bash
# Start core services only
docker-compose -f docker-compose.fxml4-forex.yml up -d rabbitmq db redis

# Run FXML4 API locally
export PYTHONPATH=/path/to/fxml4
python -m fxml4.api.main

# Run ForexConnect middleware
cd /path/to/forex-connect
python src/main.py
```

### Mock Testing

For testing without FXCM connection:

```bash
# Enable mock mode
export MOCK_FOREX_CONNECT=true
export FOREX_CONNECT_DEBUG=true

python scripts/start_fxml4_forex_integration.py
```

## Production Deployment

### Security Considerations

1. **Credential Management**: Use strong passwords and consider secret management systems
2. **Network Security**: Deploy behind firewall, use VPN for admin access
3. **API Authentication**: Enable JWT authentication for production
4. **TLS Encryption**: Enable HTTPS for all web interfaces
5. **Audit Logging**: Ensure comprehensive audit trails

### Performance Tuning

1. **Database**: Optimize PostgreSQL/TimescaleDB settings for time-series workloads
2. **RabbitMQ**: Configure appropriate memory and disk limits
3. **Container Resources**: Allocate sufficient CPU/memory for each service
4. **Connection Pooling**: Tune pool sizes based on expected load

### High Availability

1. **Database**: Set up TimescaleDB clustering or replication
2. **RabbitMQ**: Configure RabbitMQ clustering for redundancy
3. **Load Balancing**: Use nginx/HAProxy for API load balancing
4. **Health Checks**: Implement comprehensive health monitoring
5. **Backup Strategy**: Regular database backups and configuration backups

## Troubleshooting

### Common Issues

#### ForexConnect Connection Fails
```bash
# Check credentials
docker-compose -f docker-compose.fxml4-forex.yml logs forex-middleware

# Test connection manually
curl http://localhost:8080/health
```

#### Orders Not Executing
```bash
# Check bridge adapter status
curl http://localhost:8000/health/brokers

# Check RabbitMQ queues
# Visit http://localhost:15672 and check queue depths
```

#### High Latency
```bash
# Check system resources
docker stats

# Monitor metrics
# Visit http://localhost:3000 (Grafana)
```

### Debug Mode

Enable detailed logging:

```bash
# Set in .env
LOG_LEVEL=DEBUG
FOREX_CONNECT_DEBUG=true
FXML4_DEBUG=true

# Restart services
docker-compose -f docker-compose.fxml4-forex.yml restart
```

### Log Analysis

```bash
# View all logs
docker-compose -f docker-compose.fxml4-forex.yml logs -f

# Specific service logs
docker-compose -f docker-compose.fxml4-forex.yml logs -f forex-middleware
docker-compose -f docker-compose.fxml4-forex.yml logs -f api
```

## Support and Documentation

### Resources

- **FXML4 Documentation**: [Internal documentation]
- **ForexConnect API**: https://fxcodebase.com/bin/forexconnect/1.6.5/help/Python/
- **FXCM API**: https://github.com/fxcm/ForexConnectAPI
- **Docker Compose**: https://docs.docker.com/compose/

### Getting Help

For issues and support:

1. Check the troubleshooting section above
2. Review system logs for error messages
3. Verify configuration matches examples
4. Test with demo account before live trading

## License and Disclaimer

This integration is provided for educational and development purposes.

**Important**:
- Always test thoroughly with demo accounts before live trading
- Understand the risks associated with automated trading
- Ensure compliance with relevant financial regulations
- Monitor system performance and have appropriate safeguards

---

Built with ❤️ using Python, FastAPI, RabbitMQ, TimescaleDB, and Docker.
