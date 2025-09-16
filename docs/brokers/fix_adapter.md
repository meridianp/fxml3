# Native FIX Protocol Broker Adapter

The Native FIX adapter provides direct FIX protocol connectivity to brokers, with optional RabbitMQ integration for message queue routing.

## Features

- Native FIX 4.2/4.4 protocol support using simplefix
- Lightweight session management without built-in networking
- Mock mode for testing without real connections
- RabbitMQ integration for order routing and execution distribution
- Support for multiple broker profiles (Currenex, LMAX, Hotspot, etc.)
- Automatic reconnection and session recovery
- Comprehensive metrics and monitoring

## Architecture

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│   FIX Broker    │────▶│   FIX Adapter   │────▶│   RabbitMQ      │
│   (External)    │◀────│                 │◀────│   Integration   │
└─────────────────┘     └─────────────────┘     └─────────────────┘
         ▲                       │                        │
         │                       │                        │
         └───────────────────────┴────────────────────────┘
                        FIX Protocol Messages
```

## Components

### 1. FixBrokerAdapter

Base FIX adapter with core protocol functionality:

```python
from fxml4.brokers.adapters.fix_adapter import FixBrokerAdapter
from fxml4.brokers.adapters.base import AdapterConfig

config = AdapterConfig(
    adapter_id="fix_prod",
    broker_type="fix",
    broker_name="Currenex",
    connection_params={
        'host': 'fix.currenex.com',
        'port': 9876,
        'use_ssl': True,
        'ssl_cert': '/path/to/cert.pem',
        'ssl_key': '/path/to/key.pem',
        'session': {
            'sender_comp_id': 'FXML4',
            'target_comp_id': 'CURRENEX',
            'fix_version': 'FIX.4.4',
            'heartbeat_interval': 30
        }
    }
)

adapter = FixBrokerAdapter(config)
await adapter.connect()
```

### 2. FixRabbitMQAdapter

Extended adapter with RabbitMQ integration:

```python
from fxml4.brokers.adapters.fix_rabbitmq_adapter import FixRabbitMQAdapter

config = AdapterConfig(
    adapter_id="fix_rmq",
    broker_type="fix",
    broker_name="LMAX",
    connection_params={
        'host': 'fix.lmax.com',
        'port': 443,
        'use_ssl': True,
        'session': {
            'sender_comp_id': 'FXML4',
            'target_comp_id': 'LMAX'
        },
        'rabbitmq': {
            'host': 'localhost',
            'port': 5672,
            'vhost': '/fxml4',
            'user': 'fxml4',
            'password': 'password'
        }
    }
)

adapter = FixRabbitMQAdapter(config)
await adapter.connect()
```

### 3. Session Management

The adapter includes lightweight session management:

```python
# Session automatically handles:
- Sequence number tracking
- Heartbeat monitoring
- Message persistence (optional)
- Automatic reconnection
- Session state tracking

# Access session info
if adapter.session:
    print(f"Session state: {adapter.session.state}")
    print(f"Messages sent: {adapter.session.stats.messages_sent}")
    print(f"Messages received: {adapter.session.stats.messages_received}")
```

### 4. Message Translation

Translation between internal FIX classes and simplefix format:

```python
from fxml4.fix.simplefix_translator import SimpleFIXTranslator
from fxml4.fix.messages.orders import NewOrderSingle

translator = SimpleFIXTranslator("FXML4", "BROKER")

# Convert to simplefix
order = NewOrderSingle(...)
sf_msg = translator.to_simplefix(order)

# Parse from bytes
fix_bytes = b"8=FIX.4.2|9=..."
message = translator.parse_bytes(fix_bytes)
```

## Configuration

### Using Broker Profiles

Pre-configured broker profiles are available:

```python
from fxml4.brokers.adapters.fix.registry import (
    get_broker_profile,
    create_fix_adapter_config
)

# List available profiles
profiles = list_available_profiles()
# {'currenex': 'Currenex (FIX.4.4)', 'lmax': 'LMAX (FIX.4.4)', ...}

# Use a profile
config = create_fix_adapter_config(
    adapter_id="fix_currenex",
    broker_name="currenex",
    rabbitmq_config={
        'host': 'localhost',
        'port': 5672
    }
)
```

### YAML Configuration

Configure sessions in `config/fix_sessions.yaml`:

```yaml
sessions:
  currenex_prod:
    enabled: true
    adapter_type: fix_rabbitmq
    connection:
      host: fix.currenex.com
      port: 9876
      use_ssl: true
      ssl_cert: /path/to/cert
    session:
      sender_comp_id: FXML4_PROD
      target_comp_id: CURRENEX
      fix_version: FIX.4.4
    features:
      supports_market_data: true
      supports_trading: true
    rabbitmq:
      host: localhost
      port: 5672
```

## Mock Mode

For testing without real connections:

```python
config = AdapterConfig(
    adapter_id="fix_test",
    broker_type="fix",
    broker_name="Mock",
    connection_params={
        'host': 'localhost',
        'port': 9876,
        'mock': True,  # Enable mock mode
        'session': {
            'sender_comp_id': 'TEST',
            'target_comp_id': 'MOCK'
        }
    },
    features={
        'simulate_fills': True,
        'fill_delay_ms': 1000,
        'simulate_partial_fills': True,
        'reject_rate': 0.05  # 5% rejection
    }
)
```

## Usage Examples

### Basic Order Flow

```python
# Submit order
order = NewOrderSingle(
    cl_ord_id="ORD_123",
    symbol="EUR/USD",
    side=Side.BUY,
    order_qty=100000,
    ord_type=OrdType.LIMIT,
    price=1.0850,
    time_in_force=TimeInForce.GTC
)

order_id = await adapter.submit_order(order)
print(f"Order submitted: {order_id}")

# Cancel order
cancel = OrderCancelRequest(
    cl_ord_id="CXL_456",
    orig_cl_ord_id="ORD_123",
    symbol="EUR/USD",
    side=Side.BUY
)

success = await adapter.cancel_order(cancel)
```

### With RabbitMQ Integration

```python
# Orders are automatically consumed from queue
# Execution reports are published to exchanges

# The adapter listens on:
# - orders.fix.inbound (for new orders)
# - admin.fix.commands (for admin commands)

# And publishes to:
# - orders.executions (execution reports)
# - admin.status (status updates)
```

### Administrative Commands

Send admin commands via RabbitMQ:

```python
# Status request
channel.basic_publish(
    exchange='admin.commands',
    routing_key='fix',
    body=json.dumps({'command': 'status'})
)

# Reconnect
channel.basic_publish(
    exchange='admin.commands',
    routing_key='fix',
    body=json.dumps({'command': 'reconnect'})
)

# Cancel all orders
channel.basic_publish(
    exchange='admin.commands',
    routing_key='fix',
    body=json.dumps({'command': 'cancel_all'})
)
```

## Monitoring

### Metrics

Access adapter metrics:

```python
metrics = adapter.metrics
print(f"Total orders: {metrics.total_orders}")
print(f"Filled orders: {metrics.filled_orders}")
print(f"Rejected orders: {metrics.rejected_orders}")
print(f"Failed orders: {metrics.failed_orders}")
```

### Session Statistics

```python
if adapter.session:
    stats = adapter.session.stats
    print(f"Messages sent: {stats.messages_sent}")
    print(f"Messages received: {stats.messages_received}")
    print(f"Bytes sent: {stats.bytes_sent}")
    print(f"Heartbeats sent: {stats.heartbeats_sent}")
    print(f"Last activity: {stats.last_sent_time}")
```

## Testing

Run tests:

```bash
# Unit tests
pytest tests/brokers/adapters/test_fix_adapter.py -v

# Integration tests with mock
pytest tests/integration/test_fix_integration.py -v

# Load testing
python scripts/test_fix_load.py --orders 1000 --rate 10
```

## Troubleshooting

### Connection Issues

1. **SSL/TLS Errors**
   - Verify certificate paths
   - Check certificate validity
   - Ensure correct TLS version

2. **Logon Rejection**
   - Verify comp IDs match broker config
   - Check FIX version compatibility
   - Ensure sequence numbers are correct

3. **Message Rejection**
   - Check required fields for broker
   - Verify symbol format
   - Ensure order quantities meet minimums

### Session Issues

1. **Sequence Number Mismatch**
   ```python
   # Reset sequence numbers
   if adapter.session:
       adapter.session.reset_sequence_numbers()
   ```

2. **Heartbeat Timeout**
   - Check network latency
   - Adjust heartbeat interval
   - Verify bidirectional connectivity

### Debugging

Enable debug logging:

```python
import logging

# Enable FIX adapter debug logs
logging.getLogger('fxml4.brokers.adapters.fix_adapter').setLevel(logging.DEBUG)

# Enable simplefix logs
logging.getLogger('simplefix').setLevel(logging.DEBUG)

# Enable session manager logs
logging.getLogger('fxml4.fix.session_manager').setLevel(logging.DEBUG)
```

## Performance Considerations

1. **Message Rate Limiting**
   - Respect broker rate limits
   - Use features.max_orders_per_second
   - Implement backpressure handling

2. **Memory Management**
   - Configure max_messages_in_memory
   - Enable/disable message persistence
   - Monitor queue depths

3. **Network Optimization**
   - Use persistent connections
   - Enable TCP keepalive
   - Configure appropriate timeouts

## Security

1. **Credentials**
   - Store certificates securely
   - Use environment variables for passwords
   - Rotate credentials regularly

2. **Network Security**
   - Always use SSL/TLS for production
   - Verify certificate chains
   - Implement IP whitelisting if supported

3. **Message Security**
   - Validate all incoming messages
   - Sanitize order parameters
   - Log security events

## Next Steps

1. Configure broker-specific sessions
2. Implement custom message handlers
3. Set up monitoring and alerting
4. Integrate with risk management
5. Add performance metrics collection
