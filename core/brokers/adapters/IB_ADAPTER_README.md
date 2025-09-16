# Interactive Brokers Adapter

The IB adapter provides seamless integration between the FIX protocol-based broker abstraction layer and Interactive Brokers' TWS/Gateway API.

## Features

- **FIX Protocol Translation**: Converts between FIX 4.4 messages and IB API objects
- **RabbitMQ Integration**: Asynchronous message-based communication
- **Order Management**: Submit, modify, and cancel orders
- **Market Data**: Real-time and historical data subscriptions
- **Account Management**: Portfolio queries and position tracking
- **Error Handling**: Comprehensive error mapping and recovery
- **Rate Limiting**: Built-in order rate limiting to comply with IB restrictions

## Architecture

```
┌─────────────────┐     ┌──────────────┐     ┌─────────────┐
│   RabbitMQ      │────▶│  IB Adapter  │────▶│  IB Gateway │
│   Queues        │◀────│              │◀────│  /TWS       │
└─────────────────┘     └──────────────┘     └─────────────┘
        │                      │
        │                      ├── IBBrokerAdapter (Core IB logic)
        │                      ├── IBRabbitMQAdapter (MQ integration)
        │                      └── IBFIXTranslator (Message translation)
        │
        ├── orders.ib.inbound (New orders)
        ├── admin.ib.commands (Control commands)
        └── order.executions (Execution reports)
```

## Configuration

Configure the IB adapter in `config/brokers.yaml`:

```yaml
brokers:
  ib:
    enabled: true
    adapter_class: "fxml4.brokers.adapters.ib.IBRabbitMQAdapter"
    connection:
      # IB Gateway/TWS connection
      host: "localhost"
      port: 7497  # 7497 for paper, 7496 for live
      client_id: 1
      account_id: ""  # Leave empty to auto-detect

      # RabbitMQ connection
      rabbitmq:
        host: "rabbitmq"
        port: 5672
        username: "guest"
        password: "guest"

    features:
      market_data: true
      portfolio_queries: true
      order_modification: true
      historical_data: true

    limits:
      max_orders_per_second: 10
      max_orders_per_minute: 50
      max_daily_volume: 10000000
```

## Usage

### Starting the Adapter

```python
from fxml4.brokers.adapters.ib import IBRabbitMQAdapter
from fxml4.brokers.adapters.base import AdapterConfig

# Load configuration
config = AdapterConfig(
    adapter_type="ib",
    connection_params={...},
    features={...},
    limits={...}
)

# Create and connect adapter
adapter = IBRabbitMQAdapter(config)
await adapter.connect()
```

### Submitting Orders

Orders are submitted via RabbitMQ to the `orders.ib.inbound` queue:

```python
from fxml4.fix.messages.orders import NewOrderSingle
from fxml4.fix.messages.base import Side, OrdType

# Create FIX order
order = NewOrderSingle(
    cl_ord_id="ORDER_001",
    symbol="EURUSD",
    side=Side.BUY,
    order_qty=100000,
    ord_type=OrdType.LIMIT,
    price=1.1000
)

# Publish to RabbitMQ
envelope = {
    "fix_message": fix_builder.build(order),
    "timestamp": datetime.utcnow().isoformat(),
    "source": "strategy_engine"
}

channel.basic_publish(
    exchange='order.routing',
    routing_key='order.ib.new',
    body=json.dumps(envelope)
)
```

### Receiving Execution Reports

Execution reports are published to the `order.executions` exchange:

```python
# Subscribe to execution reports
channel.queue_bind(
    exchange='order.executions',
    queue='my_exec_queue',
    routing_key='execution.ib.*'
)

# Process execution reports
for method, properties, body in channel.consume('my_exec_queue'):
    envelope = json.loads(body)
    fix_message = envelope['fix_message']
    # Parse and process execution report
```

### Admin Commands

Control the adapter via admin commands:

```python
# Connect/disconnect
command = {"command": "connect"}

# Get status
command = {"command": "status"}

# Subscribe to market data
command = {
    "command": "subscribe_market_data",
    "symbols": ["EURUSD", "GBPUSD"]
}

# Publish command
channel.basic_publish(
    exchange='admin.control',
    routing_key='admin.ib.command',
    body=json.dumps(command)
)
```

## Testing

### Unit Tests

```bash
# Run all IB adapter tests
pytest tests/unit/test_ib_adapter.py -v
pytest tests/unit/test_ib_rabbitmq_adapter.py -v

# Run specific test
pytest tests/unit/test_ib_adapter.py::TestIBFIXTranslator::test_fix_to_ib_contract_forex -v
```

### Integration Tests

```bash
# Requires RabbitMQ running
pytest tests/integration/test_ib_adapter_integration.py -v -m integration
```

### Manual Testing

```bash
# Test script with mock IB connection
python scripts/test_ib_adapter.py

# Test with real IB Gateway (requires IB Gateway running)
# 1. Start IB Gateway on port 7497 (paper trading)
# 2. Run test script
python scripts/test_ib_adapter.py
```

## IB Gateway Setup

1. **Download IB Gateway**: From Interactive Brokers website
2. **Configure for API**:
   - Enable API connections in Configure > API > Settings
   - Set socket port (7496 for live, 7497 for paper)
   - Add trusted IP (127.0.0.1 for local)
   - Disable read-only mode for trading
3. **Paper Trading**: Use separate login for paper account
4. **Keep Alive**: IB Gateway auto-disconnects after ~24 hours

## Error Handling

The adapter handles various IB error scenarios:

| Error Code | Type | Description | Action |
|------------|------|-------------|--------|
| 1100 | Connection Lost | TWS/Gateway connection lost | Set status to ERROR |
| 1102 | Connection Restored | Connection restored | Set status to READY |
| 201 | Order Rejected | Invalid order parameters | Send rejection report |
| 110 | Price Invalid | Price violates tick rules | Send rejection report |
| 399 | Order Too Large | Size exceeds limits | Send rejection report |

## Performance Considerations

- **Rate Limits**: IB enforces various rate limits:
  - 50 messages/second for market data
  - 10 orders/second
  - 100 requests/2 seconds for historical data

- **Connection Limits**: Maximum 8 client connections per username

- **Market Data Lines**: Limited number of simultaneous market data subscriptions

## Troubleshooting

### Common Issues

1. **Connection Failed**
   - Verify IB Gateway is running
   - Check port configuration (7496/7497)
   - Ensure API permissions enabled
   - Check firewall settings

2. **Order Rejected**
   - Verify symbol format (EUR for EURUSD forex)
   - Check account permissions
   - Ensure sufficient margin
   - Verify market hours

3. **No Market Data**
   - Check market data subscriptions in IB account
   - Verify symbol is valid
   - Ensure market is open

4. **RabbitMQ Connection Issues**
   - Verify RabbitMQ is running
   - Check credentials and host
   - Ensure queues are created

### Debug Logging

Enable debug logging for detailed diagnostics:

```python
import logging

# Set IB adapter to DEBUG
logging.getLogger('fxml4.brokers.adapters.ib_adapter').setLevel(logging.DEBUG)
logging.getLogger('fxml4.brokers.adapters.ib_rabbitmq_adapter').setLevel(logging.DEBUG)
```

## API Mappings

### Order Type Mappings

| FIX OrdType | IB OrderType |
|-------------|--------------|
| MARKET | MKT |
| LIMIT | LMT |
| STOP | STP |
| STOP_LIMIT | STP LMT |
| MARKET_ON_CLOSE | MOC |
| LIMIT_ON_CLOSE | LOC |

### Time in Force Mappings

| FIX TimeInForce | IB TIF |
|-----------------|--------|
| DAY | DAY |
| GOOD_TILL_CANCEL | GTC |
| IMMEDIATE_OR_CANCEL | IOC |
| FILL_OR_KILL | FOK |
| AT_THE_OPENING | OPG |
| GOOD_TILL_DATE | GTD |

### Status Mappings

| IB Status | FIX OrdStatus | FIX ExecType |
|-----------|---------------|--------------|
| PendingSubmit | PENDING_NEW | PENDING_NEW |
| Submitted | NEW | NEW |
| Filled | FILLED | TRADE |
| PartiallyFilled | PARTIALLY_FILLED | TRADE |
| Cancelled | CANCELED | CANCELED |
| Inactive | REJECTED | REJECTED |

## Next Steps

- Implement advanced order types (brackets, OCO)
- Add options trading support
- Implement portfolio sync on startup
- Add historical data retrieval
- Implement order modification logic
- Add fractional share support
- Implement smart routing preferences
