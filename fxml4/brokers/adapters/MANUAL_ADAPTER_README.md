# Manual Broker Adapter Documentation

## Overview

The Manual Broker Adapter provides a human-in-the-loop order approval system for the FXML4 trading platform. It allows traders and risk managers to review, approve, modify, or reject orders before execution, providing an additional layer of control and compliance.

## Features

- **Order Queue Management**: Orders are queued for manual review with configurable timeout periods
- **Real-time Notifications**: WebSocket support for instant order notifications
- **Approval Workflow**: Multi-level approval based on order value or risk metrics
- **Order Modification**: Ability to modify order parameters during approval
- **Risk Override**: Authorized users can override risk limits with proper documentation
- **Audit Trail**: Complete audit logging of all decisions and modifications
- **Simulated Execution**: Built-in order execution simulator for testing
- **RabbitMQ Integration**: Message queue support for distributed deployments
- **REST API**: Comprehensive API for web interface integration

## Architecture

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│  Trading System │────▶│  Manual Adapter  │────▶│   Web Interface │
│   (FIX Orders)  │     │  (Order Queue)   │     │  (React/Vue)    │
└─────────────────┘     └────────┬─────────┘     └─────────────────┘
                                 │
                                 │ RabbitMQ
                                 │
                        ┌────────▼─────────┐
                        │ Approval Queue   │
                        │ & Notifications  │
                        └──────────────────┘
```

## Components

### 1. Core Manual Adapter (`manual_adapter.py`)

The base adapter implementation with order queue management:

```python
from fxml4.brokers.adapters.base import AdapterConfig
from fxml4.brokers.adapters.manual_adapter import ManualBrokerAdapter

# Configure adapter
config = AdapterConfig(
    broker_type='manual',
    adapter_type='manual',
    connection_params={},
    features={
        'auto_reject_timeout': 300,  # 5 minutes
        'simulate_execution': True,
        'approval_levels': {
            'standard': 0,
            'senior': 100000,
            'executive': 1000000
        }
    }
)

# Create and connect
adapter = ManualBrokerAdapter(config)
await adapter.connect()

# Submit order for approval
order_id = await adapter.submit_order(new_order_single)

# Approve order
await adapter.approve_order(
    cl_ord_id=order.cl_ord_id,
    reviewer="john_doe",
    notes="Approved per trading plan"
)
```

### 2. RabbitMQ Integration (`manual_rabbitmq_adapter.py`)

Enhanced adapter with message queue support:

```python
from fxml4.brokers.adapters.manual_rabbitmq_adapter import ManualRabbitMQAdapter

config = AdapterConfig(
    broker_type='manual',
    adapter_type='manual_rabbitmq',
    connection_params={
        'rabbitmq': {
            'host': 'localhost',
            'port': 5672,
            'username': 'guest',
            'password': 'guest'
        }
    },
    features={
        'auto_reject_timeout': 300
    }
)

adapter = ManualRabbitMQAdapter(config)
await adapter.connect()

# Adapter now consumes from RabbitMQ queues
# Orders arrive via: orders.manual.inbound
# Admin commands via: admin.manual.commands
# Approval requests published to: manual.approval.requests
```

### 3. FastAPI Backend (`manual_execution.py`)

REST API and WebSocket endpoints for web interface:

```python
# API Endpoints:
GET  /manual/status              # Adapter status
GET  /manual/orders/pending      # List pending orders
GET  /manual/orders/history      # Order history
GET  /manual/orders/{cl_ord_id}  # Specific order details
POST /manual/orders/{cl_ord_id}/approve  # Approve order
POST /manual/orders/{cl_ord_id}/reject   # Reject order
WS   /manual/ws                  # WebSocket for real-time updates
```

## Configuration

### Adapter Configuration

```yaml
manual:
  enabled: true
  adapter_class: "fxml4.brokers.adapters.manual_adapter.ManualBrokerAdapter"
  connection:
    review_interface: "http://localhost:8001/manual"
  features:
    auto_reject_timeout: 300      # Seconds before auto-rejection
    require_two_factor: false     # Require 2FA for approvals
    allow_risk_override: true     # Allow risk limit overrides
    simulate_execution: true      # Simulate order fills
    simulated_fill_delay: 2       # Seconds before simulated fill
    approval_levels:
      standard: 0                 # No special approval needed
      senior: 100000             # Senior trader approval
      executive: 1000000         # Executive approval
    audit_trail: true            # Enable audit logging
  limits:
    max_override_amount: 10000000  # Maximum risk override
```

### RabbitMQ Queue Configuration

The adapter uses these queues:

- **orders.manual.inbound**: Incoming orders for approval
- **admin.manual.commands**: Administrative commands
- **manual.approval.requests**: Approval request notifications
- **executions.manual**: Execution reports

## Usage Examples

### Basic Order Approval Workflow

```python
# 1. Order arrives for manual approval
order = NewOrderSingle(
    cl_ord_id="ORD123",
    symbol="EUR/USD",
    side=Side.BUY,
    order_qty=1000000,
    ord_type=OrdType.LIMIT,
    price=1.0850
)

order_id = await adapter.submit_order(order)

# 2. Get pending orders for review
pending = await adapter.get_pending_orders()
# Returns: [{
#     'order_id': 'MANUAL_A1B2C3D4',
#     'cl_ord_id': 'ORD123',
#     'symbol': 'EUR/USD',
#     'side': 'BUY',
#     'quantity': 1000000,
#     'price': 1.0850,
#     'approval_level': 'senior',
#     'time_remaining': 285
# }]

# 3. Approve with modifications
await adapter.approve_order(
    cl_ord_id="ORD123",
    reviewer="senior_trader",
    notes="Reduced size due to market conditions",
    modifications={'order_qty': 500000}
)

# 4. Or reject with reason
await adapter.reject_order(
    cl_ord_id="ORD124",
    reviewer="risk_manager",
    reason="Exceeds daily EUR exposure limit",
    notes="Current EUR exposure: $8.5M, limit: $10M"
)
```

### WebSocket Real-time Updates

```javascript
// Connect to WebSocket
const ws = new WebSocket('ws://localhost:8001/manual/ws');

ws.onmessage = (event) => {
    const data = JSON.parse(event.data);

    switch(data.type) {
        case 'new_order':
            // New order pending approval
            console.log(`New order: ${data.cl_ord_id}`);
            break;

        case 'order_approved':
            // Order was approved
            console.log(`Approved: ${data.cl_ord_id} by ${data.reviewer}`);
            break;

        case 'order_rejected':
            // Order was rejected
            console.log(`Rejected: ${data.cl_ord_id} - ${data.reason}`);
            break;

        case 'order_filled':
            // Order was filled (simulated or real)
            console.log(`Filled: ${data.cl_ord_id} @ ${data.fill_price}`);
            break;
    }
};

// Request pending orders
ws.send(JSON.stringify({type: 'get_pending'}));
```

### Risk Override Example

```python
# Large order requiring executive approval and risk override
large_order = NewOrderSingle(
    cl_ord_id="LARGE001",
    symbol="USD/JPY",
    side=Side.SELL,
    order_qty=50000000,  # $50M
    ord_type=OrdType.MARKET
)

# Submit order
order_id = await adapter.submit_order(large_order)

# Approve with risk override
await adapter.approve_order(
    cl_ord_id="LARGE001",
    reviewer="ceo",
    notes="Strategic hedge for acquisition",
    risk_overrides={
        'max_position_size': 100000000,
        'daily_volume_limit': 200000000,
        'override_reason': 'M&A hedge requirement',
        'override_expiry': '2025-02-01'
    }
)
```

## API Authentication

The REST API uses bearer token authentication:

```bash
# Get pending orders with authentication
curl -H "Authorization: Bearer valid_trader_token" \
     http://localhost:8001/manual/orders/pending

# Approve order
curl -X POST \
     -H "Authorization: Bearer valid_senior_token" \
     -H "Content-Type: application/json" \
     -d '{
       "cl_ord_id": "ORD123",
       "reviewer": "john_doe",
       "notes": "Approved per daily strategy"
     }' \
     http://localhost:8001/manual/orders/ORD123/approve
```

## Testing

### Unit Tests

```bash
# Run unit tests
pytest tests/unit/test_manual_adapter.py -v
```

### Integration Tests

```bash
# Start RabbitMQ if testing with message queues
docker-compose up -d rabbitmq

# Run integration tests
pytest tests/integration/test_manual_adapter_integration.py -v
```

### Manual Testing

```bash
# Run test script
python scripts/test_manual_adapter.py
```

## Monitoring and Metrics

The adapter provides these metrics:

- **Pending Orders**: Current number of orders awaiting approval
- **Approval Rate**: Percentage of orders approved vs rejected
- **Average Review Time**: Time from submission to decision
- **Timeout Rate**: Percentage of orders auto-rejected
- **Reviewer Statistics**: Approvals/rejections per user

Access metrics via API:

```bash
# Get adapter statistics
curl http://localhost:8001/manual/stats

# Response:
{
  "total_orders": 1543,
  "approved": 1289,
  "rejected": 187,
  "expired": 67,
  "pending": 12,
  "approval_rate": 83.6,
  "reviewer_stats": {
    "john_doe": {"approved": 456, "rejected": 23, "total": 479},
    "jane_smith": {"approved": 312, "rejected": 45, "total": 357}
  }
}
```

## Security Considerations

1. **Authentication**: All API endpoints require bearer token authentication
2. **Authorization**: Role-based access control for approval levels
3. **Audit Trail**: Complete logging of all actions with timestamps
4. **Data Encryption**: TLS for all API communications
5. **Input Validation**: Strict validation of all order modifications
6. **Rate Limiting**: Configurable rate limits per user/IP

## Troubleshooting

### Common Issues

1. **Orders not appearing in queue**
   - Check adapter connection status
   - Verify RabbitMQ connectivity
   - Check order routing configuration

2. **WebSocket disconnections**
   - Implement reconnection logic in client
   - Check firewall/proxy settings
   - Monitor WebSocket ping/pong

3. **Auto-rejection not working**
   - Verify cleanup task is running
   - Check auto_reject_timeout configuration
   - Look for errors in adapter logs

### Debug Logging

Enable debug logging for detailed troubleshooting:

```python
import logging
logging.getLogger('fxml4.brokers.adapters.manual_adapter').setLevel(logging.DEBUG)
```

## Future Enhancements

1. **Mobile App Integration**: Native iOS/Android apps for on-the-go approvals
2. **Machine Learning**: Automated approval suggestions based on historical patterns
3. **Voice Authentication**: Biometric security for high-value approvals
4. **Blockchain Audit Trail**: Immutable audit logging for regulatory compliance
5. **Multi-person Approval**: Require multiple approvers for certain thresholds

## Support

For issues or questions:
- Check the logs: `logs/manual_adapter.log`
- Review test examples: `scripts/test_manual_adapter.py`
- See integration guide: `docs/BROKER_INTEGRATION.md`
