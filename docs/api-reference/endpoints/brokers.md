# Broker API Endpoints

The Broker API provides unified access to multiple trading brokers through standardized endpoints. All broker operations are subject to risk management and compliance checks.

## Authentication

All broker endpoints require authentication. Include your API key in the request headers:

```http
Authorization: Bearer YOUR_API_KEY
```

## Base URL

```
https://api.fxml4.com/v1
```

## Endpoints

### List Available Brokers

Get information about configured broker adapters.

```http
GET /brokers
```

**Response:**
```json
{
  "brokers": [
    {
      "id": "ib",
      "name": "Interactive Brokers",
      "status": "connected",
      "adapter_type": "tws",
      "capabilities": ["orders", "positions", "market_data"],
      "last_heartbeat": "2024-01-15T10:30:00Z"
    },
    {
      "id": "fix_broker",
      "name": "FIX Broker",
      "status": "connected",
      "adapter_type": "fix",
      "capabilities": ["orders", "positions"],
      "last_heartbeat": "2024-01-15T10:29:45Z"
    }
  ]
}
```

### Get Broker Status

Get detailed status information for a specific broker.

```http
GET /brokers/{broker_id}/status
```

**Parameters:**
- `broker_id` (string, required): Broker identifier

**Response:**
```json
{
  "broker_id": "ib",
  "status": "connected",
  "connection_time": "2024-01-15T08:00:00Z",
  "last_heartbeat": "2024-01-15T10:30:00Z",
  "orders_submitted": 150,
  "orders_filled": 145,
  "orders_rejected": 2,
  "avg_response_time_ms": 45,
  "error_rate": 0.013,
  "capabilities": {
    "orders": true,
    "positions": true,
    "market_data": true,
    "options": false
  }
}
```

### Submit Order

Submit a new trading order through the specified broker.

```http
POST /brokers/{broker_id}/orders
```

**Parameters:**
- `broker_id` (string, required): Broker identifier

**Request Body:**
```json
{
  "cl_ord_id": "ORDER_20240115_001",
  "symbol": "EURUSD",
  "side": "BUY",
  "order_qty": 100000,
  "ord_type": "LIMIT",
  "price": 1.1250,
  "time_in_force": "DAY",
  "client_id": "CLIENT001"
}
```

**Response:**
```json
{
  "execution_id": "EXEC_001",
  "cl_ord_id": "ORDER_20240115_001",
  "status": "PENDING_NEW",
  "broker_order_id": "IB_12345",
  "submitted_at": "2024-01-15T10:30:15Z",
  "compliance_result": "PASS",
  "risk_checks": {
    "position_limit": "PASS",
    "concentration": "PASS",
    "velocity": "PASS"
  }
}
```

**Error Response (Compliance Violation):**
```json
{
  "error": "COMPLIANCE_VIOLATION",
  "message": "Order blocked by compliance rules",
  "violations": [
    {
      "rule_id": "POS_LIMIT_001",
      "rule_name": "Position Size Limit",
      "severity": "HIGH",
      "message": "Position limit exceeded for EURUSD",
      "suggested_action": "Reduce order size or close existing positions"
    }
  ]
}
```

### Get Order Status

Retrieve the current status of an order.

```http
GET /brokers/{broker_id}/orders/{cl_ord_id}
```

**Parameters:**
- `broker_id` (string, required): Broker identifier
- `cl_ord_id` (string, required): Client order ID

**Response:**
```json
{
  "cl_ord_id": "ORDER_20240115_001",
  "broker_order_id": "IB_12345",
  "symbol": "EURUSD",
  "side": "BUY",
  "order_qty": 100000,
  "ord_type": "LIMIT",
  "price": 1.1250,
  "ord_status": "FILLED",
  "filled_qty": 100000,
  "avg_px": 1.1248,
  "leaves_qty": 0,
  "last_fill_time": "2024-01-15T10:31:22Z",
  "fills": [
    {
      "fill_id": "FILL_001",
      "fill_qty": 50000,
      "fill_px": 1.1247,
      "fill_time": "2024-01-15T10:31:20Z"
    },
    {
      "fill_id": "FILL_002",
      "fill_qty": 50000,
      "fill_px": 1.1249,
      "fill_time": "2024-01-15T10:31:22Z"
    }
  ]
}
```

### Cancel Order

Cancel an existing order.

```http
DELETE /brokers/{broker_id}/orders/{cl_ord_id}
```

**Parameters:**
- `broker_id` (string, required): Broker identifier
- `cl_ord_id` (string, required): Client order ID

**Response:**
```json
{
  "cl_ord_id": "ORDER_20240115_001",
  "cancel_status": "PENDING_CANCEL",
  "cancel_time": "2024-01-15T10:35:00Z"
}
```

### Modify Order

Modify an existing order (cancel/replace).

```http
PUT /brokers/{broker_id}/orders/{cl_ord_id}
```

**Parameters:**
- `broker_id` (string, required): Broker identifier
- `cl_ord_id` (string, required): Client order ID

**Request Body:**
```json
{
  "order_qty": 75000,
  "price": 1.1245
}
```

**Response:**
```json
{
  "orig_cl_ord_id": "ORDER_20240115_001",
  "cl_ord_id": "ORDER_20240115_001_REV1",
  "status": "PENDING_REPLACE",
  "replace_time": "2024-01-15T10:36:00Z"
}
```

### Get Open Orders

Retrieve all open orders for a broker.

```http
GET /brokers/{broker_id}/orders
```

**Query Parameters:**
- `symbol` (string, optional): Filter by symbol
- `client_id` (string, optional): Filter by client ID
- `limit` (integer, optional): Maximum number of orders (default: 100)

**Response:**
```json
{
  "orders": [
    {
      "cl_ord_id": "ORDER_20240115_002",
      "symbol": "GBPUSD",
      "side": "SELL",
      "order_qty": 50000,
      "ord_status": "NEW",
      "leaves_qty": 50000,
      "submit_time": "2024-01-15T10:25:00Z"
    }
  ],
  "total": 1
}
```

### Get Positions

Retrieve current positions for a broker.

```http
GET /brokers/{broker_id}/positions
```

**Query Parameters:**
- `symbol` (string, optional): Filter by symbol
- `client_id` (string, optional): Filter by client ID

**Response:**
```json
{
  "positions": [
    {
      "symbol": "EURUSD",
      "position": 100000,
      "avg_px": 1.1248,
      "unrealized_pnl": 125.50,
      "realized_pnl": 0.00,
      "market_value": 112480.00,
      "last_update": "2024-01-15T10:31:22Z"
    }
  ]
}
```

### Get Account Information

Retrieve account information from broker.

```http
GET /brokers/{broker_id}/account
```

**Response:**
```json
{
  "account_id": "DU123456",
  "account_type": "MARGIN",
  "base_currency": "USD",
  "net_liquidation": 1000000.00,
  "total_cash": 950000.00,
  "buying_power": 2000000.00,
  "maintenance_margin": 25000.00,
  "initial_margin": 50000.00,
  "day_trades_remaining": 3,
  "pdt_status": false
}
```

## Order Types

| Type | Description | Required Fields |
|------|-------------|-----------------|
| MARKET | Market order | symbol, side, order_qty |
| LIMIT | Limit order | symbol, side, order_qty, price |
| STOP | Stop order | symbol, side, order_qty, stop_px |
| STOP_LIMIT | Stop limit order | symbol, side, order_qty, price, stop_px |

## Order Sides

- `BUY`: Buy order
- `SELL`: Sell order

## Order Status Values

| Status | Description |
|--------|-------------|
| PENDING_NEW | Order submitted but not yet acknowledged |
| NEW | Order acknowledged and working |
| PARTIALLY_FILLED | Order partially executed |
| FILLED | Order completely executed |
| PENDING_CANCEL | Cancel request submitted |
| CANCELLED | Order cancelled |
| PENDING_REPLACE | Modify request submitted |
| REPLACED | Order successfully modified |
| REJECTED | Order rejected by broker |

## Time in Force

| Value | Description |
|-------|-------------|
| DAY | Good for day |
| GTC | Good till cancelled |
| IOC | Immediate or cancel |
| FOK | Fill or kill |

## Error Codes

| Code | Description |
|------|-------------|
| BROKER_DISCONNECTED | Broker adapter not connected |
| INVALID_SYMBOL | Symbol not supported by broker |
| INSUFFICIENT_MARGIN | Insufficient buying power |
| POSITION_LIMIT_EXCEEDED | Position size limit violation |
| INVALID_ORDER_TYPE | Order type not supported |
| COMPLIANCE_VIOLATION | Order blocked by compliance rules |
| INVALID_PRICE | Price outside valid range |
| MARKET_CLOSED | Market not open for trading |

## Rate Limits

- 100 requests per minute per API key
- 1000 orders per hour per broker
- 10 concurrent connections per API key

## WebSocket Events

Subscribe to real-time order and position updates:

```javascript
const ws = new WebSocket('wss://api.fxml4.com/v1/ws/brokers');

ws.onmessage = (event) => {
  const data = JSON.parse(event.data);

  switch(data.type) {
    case 'order_update':
      console.log('Order update:', data.order);
      break;
    case 'position_update':
      console.log('Position update:', data.position);
      break;
    case 'execution_report':
      console.log('Execution:', data.execution);
      break;
  }
};
```

## See Also

- [Risk Management API](risk.md)
- [Manual Execution API](manual-execution.md)
- [Monitoring API](monitoring.md)
