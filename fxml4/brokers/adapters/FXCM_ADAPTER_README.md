# FXCM ForexConnect Adapter

The FXCM adapter provides integration with FXCM's ForexConnect API through a Docker-based bridge service, enabling forex trading while maintaining isolation due to Python version requirements.

## Architecture

```
┌─────────────────┐     ┌──────────────┐     ┌─────────────────┐
│   RabbitMQ      │────▶│ FXCM Adapter │────▶│  Bridge Service │
│   Queues        │◀────│              │◀────│  (Docker)       │
└─────────────────┘     └──────────────┘     └────────┬────────┘
                                                       │
                                                       ▼
                                              ┌─────────────────┐
                                              │   FXCM/         │
                                              │ ForexConnect    │
                                              └─────────────────┘
```

### Components

1. **FXCM Adapter** (`fxcm_adapter.py`):
   - Communicates with bridge service via HTTP/REST
   - Handles FIX message translation
   - Manages order lifecycle

2. **Bridge Service** (`docker/fxcm/bridge_service.py`):
   - Runs in Docker container with Python 3.7
   - Provides REST API for adapter communication
   - Handles ForexConnect API integration
   - Isolated environment for legacy SDK

3. **RabbitMQ Integration** (`fxcm_rabbitmq_adapter.py`):
   - Consumes orders from message queues
   - Publishes execution reports
   - Handles admin commands

## Setup

### 1. Download ForexConnect API

1. Visit https://fxcodebase.com/wiki/index.php/Download
2. Download ForexConnect API for Linux/Mac
3. Extract to `docker/fxcm/ForexConnectAPI/`

### 2. Configure Environment

```bash
cd docker/fxcm
cp .env.example .env
# Edit .env with your FXCM credentials
```

### 3. Build Docker Image

```bash
cd docker
docker-compose -f docker-compose.fxcm.yml build
```

### 4. Start Bridge Service

```bash
docker-compose -f docker-compose.fxcm.yml up -d
```

## Configuration

Configure in `config/brokers.yaml`:

```yaml
brokers:
  fxcm:
    enabled: true
    adapter_class: "fxml4.brokers.adapters.fxcm.FXCMRabbitMQAdapter"
    connection:
      # Bridge service connection
      bridge_url: "http://fxcm-bridge:9090"
      api_key: "${FXCM_BRIDGE_API_KEY}"  # Optional

      # RabbitMQ connection
      rabbitmq:
        host: "rabbitmq"
        port: 5672
        username: "guest"
        password: "guest"

    features:
      market_data: true
      fx_instruments: true
      bulk_operations: true

    limits:
      max_orders_per_second: 20
      max_daily_volume: 100000000
```

## Usage

### Starting the Adapter

```python
from fxml4.brokers.adapters.fxcm import FXCMRabbitMQAdapter
from fxml4.brokers.adapters.base import AdapterConfig

# Load configuration
config = AdapterConfig(
    adapter_type="fxcm",
    connection_params={
        "bridge_url": "http://fxcm-bridge:9090",
        "api_key": "your-api-key",  # Optional
        "rabbitmq": {
            "host": "rabbitmq",
            "port": 5672,
            "username": "guest",
            "password": "guest"
        }
    }
)

# Create and connect adapter
adapter = FXCMRabbitMQAdapter(config)
await adapter.connect()
```

### Submitting Orders

Orders are submitted via RabbitMQ to the `orders.fxcm.inbound` queue:

```python
from fxml4.fix.messages.orders import NewOrderSingle
from fxml4.fix.messages.base import Side, OrdType

# Create FIX order
order = NewOrderSingle(
    cl_ord_id="ORDER_001",
    symbol="EURUSD",  # Will be converted to EUR/USD
    side=Side.BUY,
    order_qty=100000,  # Units (will be converted to lots)
    ord_type=OrdType.MARKET
)

# Publish to RabbitMQ
envelope = {
    "fix_message": fix_builder.build(order),
    "timestamp": datetime.utcnow().isoformat()
}

channel.basic_publish(
    exchange='order.routing',
    routing_key='order.fxcm.new',
    body=json.dumps(envelope)
)
```

### Bridge Service API

The bridge service exposes these endpoints:

- `GET /health` - Health check
- `GET /status` - Service status and connection info
- `POST /orders` - Submit new order
- `DELETE /orders/{order_id}` - Cancel order
- `GET /orders/{order_id}` - Get order status
- `POST /market-data/subscribe` - Subscribe to market data

### Admin Commands

Control the adapter via admin commands:

```python
# Restart bridge connection
command = {"command": "restart_bridge"}

# Get status
command = {"command": "status"}

# Subscribe to market data
command = {
    "command": "subscribe_market_data",
    "symbols": ["EURUSD", "GBPUSD", "USDJPY"]
}

channel.basic_publish(
    exchange='admin.control',
    routing_key='admin.fxcm.command',
    body=json.dumps(command)
)
```

## ForexConnect Specifics

### Symbol Format

- FIX format: `EURUSD` (6 characters)
- ForexConnect format: `EUR/USD` (with slash)
- Conversion handled automatically

### Order Quantities

- FIX uses units (e.g., 100,000)
- ForexConnect uses lots (e.g., 100)
- 1 lot = 1,000 units
- Conversion handled automatically

### Supported Order Types

| FIX OrdType | ForexConnect Type | Description |
|-------------|-------------------|-------------|
| MARKET | M | Market order |
| LIMIT | L | Limit order |
| STOP | S | Stop order |
| STOP_LIMIT | SL | Stop limit order |

### Order Status Mapping

| ForexConnect Status | FIX OrdStatus |
|--------------------|---------------|
| Waiting | PENDING_NEW |
| InProcess | PENDING_NEW |
| Executing | NEW |
| Executed | FILLED |
| Canceled | CANCELED |
| Rejected | REJECTED |
| Expired | EXPIRED |

## Docker Management

### View Logs

```bash
docker-compose -f docker-compose.fxcm.yml logs -f fxcm-bridge
```

### Restart Service

```bash
docker-compose -f docker-compose.fxcm.yml restart fxcm-bridge
```

### Stop Service

```bash
docker-compose -f docker-compose.fxcm.yml down
```

### Update Service

```bash
docker-compose -f docker-compose.fxcm.yml build --no-cache
docker-compose -f docker-compose.fxcm.yml up -d
```

## Monitoring

### Bridge Status

```bash
curl -H "X-API-Key: your-api-key" http://localhost:9090/status
```

### Health Check

```bash
curl http://localhost:9090/health
```

### Container Stats

```bash
docker stats fxcm-bridge
```

## Troubleshooting

### Common Issues

1. **Bridge Not Connecting**
   - Check FXCM credentials in `.env`
   - Verify ForexConnect API is properly installed
   - Check Docker logs for errors
   - Ensure FXCM account has API access enabled

2. **Orders Rejected**
   - Verify symbol format (forex pairs need slash)
   - Check account balance and margin
   - Ensure market is open
   - Verify order size meets minimum requirements

3. **Docker Build Fails**
   - Ensure ForexConnect API is downloaded
   - Check Python 3.7 compatibility
   - Verify all requirements can be installed

4. **Connection Timeouts**
   - Check firewall settings
   - Verify Docker network configuration
   - Ensure RabbitMQ is accessible

### Debug Mode

Enable debug logging:

```yaml
# In docker-compose.fxcm.yml
environment:
  LOG_LEVEL: "DEBUG"
```

### Manual Testing

Test bridge service directly:

```bash
# Submit test order
curl -X POST http://localhost:9090/orders \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-api-key" \
  -d '{
    "fix_message": "8=FIX.4.4|35=D|49=TEST|56=FXCM|11=TEST001|55=EURUSD|54=1|38=100000|40=1|",
    "correlation_id": "TEST001"
  }'
```

## Security Considerations

1. **API Key Protection**: Always use API key for bridge service
2. **Network Isolation**: Bridge runs in isolated Docker network
3. **Credential Security**: Use environment variables, never hardcode
4. **TLS/SSL**: Enable HTTPS for production bridge service
5. **Rate Limiting**: Implement rate limits to prevent abuse

## Performance Tuning

1. **Connection Pooling**: HTTP keep-alive for adapter-bridge communication
2. **Batch Operations**: Group market data subscriptions
3. **Resource Limits**: Adjust Docker CPU/memory limits as needed
4. **Monitoring**: Use Prometheus/Grafana for metrics

## Future Enhancements

- WebSocket support for real-time updates
- Historical data retrieval
- Advanced order types (OCO, trailing stops)
- Multi-account support
- Built-in backtesting capabilities
