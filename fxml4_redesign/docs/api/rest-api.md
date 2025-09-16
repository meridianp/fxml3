# REST API Reference

## Overview

The FXML4 REST API provides programmatic access to the trading system. All API endpoints are served by the Monitor service.

### Base URL

```
http://localhost:8000/api/v1
```

### Authentication

Currently, the API uses token-based authentication (development mode allows no auth):

```http
Authorization: Bearer <your-api-token>
```

### Response Format

All responses follow a consistent format:

```json
{
    "success": true,
    "data": { ... },
    "message": "Success",
    "timestamp": "2025-01-15T14:30:00Z"
}
```

Error responses:

```json
{
    "success": false,
    "error": {
        "code": "INVALID_SYMBOL",
        "message": "Symbol EURUSD not found",
        "details": { ... }
    },
    "timestamp": "2025-01-15T14:30:00Z"
}
```

## Health & Status

### System Health

<span class="api-endpoint get">GET</span> `/health`

Check overall system health.

**Response:**

```json
{
    "status": "healthy",
    "services": {
        "data_collector": "healthy",
        "signal_generator": "healthy",
        "rabbitmq": "healthy",
        "timescaledb": "healthy"
    },
    "timestamp": "2025-01-15T14:30:00Z",
    "uptime_seconds": 3600
}
```

### Service Status

<span class="api-endpoint get">GET</span> `/status`

Get detailed status of all services.

**Response:**

```json
{
    "services": [
        {
            "name": "data_collector",
            "status": "running",
            "health": "healthy",
            "metrics": {
                "messages_per_second": 150,
                "connected_brokers": ["IB", "OANDA"],
                "active_symbols": 7
            }
        }
    ]
}
```

## Market Data

### Get Symbol Data

<span class="api-endpoint get">GET</span> `/market/symbols/{symbol}`

Get current market data for a symbol.

**Parameters:**

| Name | Type | Location | Required | Description |
|------|------|----------|----------|-------------|
| symbol | string | path | Yes | Trading symbol (e.g., EURUSD) |

**Response:**

```json
{
    "symbol": "EURUSD",
    "bid": 1.0947,
    "ask": 1.0948,
    "last": 1.0948,
    "timestamp": "2025-01-15T14:30:00Z",
    "volume": 150000000,
    "high_24h": 1.0975,
    "low_24h": 1.0920,
    "change_24h": 0.0015,
    "change_percent_24h": 0.14
}
```

### Get Historical Data

<span class="api-endpoint get">GET</span> `/market/history/{symbol}`

Get historical price data.

**Parameters:**

| Name | Type | Location | Required | Description |
|------|------|----------|----------|-------------|
| symbol | string | path | Yes | Trading symbol |
| timeframe | string | query | No | Timeframe (1m, 5m, 15m, 1h, 4h, 1d) |
| start | datetime | query | No | Start time (ISO 8601) |
| end | datetime | query | No | End time (ISO 8601) |
| limit | integer | query | No | Max records (default: 1000) |

**Example Request:**

```bash
curl "http://localhost:8000/api/v1/market/history/EURUSD?timeframe=1h&limit=100"
```

**Response:**

```json
{
    "symbol": "EURUSD",
    "timeframe": "1h",
    "data": [
        {
            "timestamp": "2025-01-15T14:00:00Z",
            "open": 1.0945,
            "high": 1.0950,
            "low": 1.0943,
            "close": 1.0948,
            "volume": 5000000
        }
    ]
}
```

### Subscribe to Market Data

<span class="api-endpoint post">POST</span> `/market/subscribe`

Subscribe to real-time market data (WebSocket connection required).

**Request Body:**

```json
{
    "symbols": ["EURUSD", "GBPUSD", "USDJPY"],
    "data_types": ["quote", "trade", "bar"]
}
```

## Trading Signals

### Get Active Signals

<span class="api-endpoint get">GET</span> `/signals/active`

Get all currently active trading signals.

**Response:**

```json
{
    "signals": [
        {
            "id": "sig_123e4567",
            "symbol": "EURUSD",
            "strategy": "elliott_wave",
            "direction": "BUY",
            "entry_price": 1.0945,
            "stop_loss": 1.0920,
            "take_profit": 1.0995,
            "confidence": 0.85,
            "created_at": "2025-01-15T14:00:00Z",
            "expires_at": "2025-01-15T18:00:00Z"
        }
    ]
}
```

### Get Signal History

<span class="api-endpoint get">GET</span> `/signals/history`

Get historical signals with performance metrics.

**Parameters:**

| Name | Type | Location | Required | Description |
|------|------|----------|----------|-------------|
| strategy | string | query | No | Filter by strategy |
| symbol | string | query | No | Filter by symbol |
| start_date | datetime | query | No | Start date filter |
| end_date | datetime | query | No | End date filter |

**Response:**

```json
{
    "signals": [
        {
            "id": "sig_123e4567",
            "symbol": "EURUSD",
            "strategy": "elliott_wave",
            "direction": "BUY",
            "entry_price": 1.0945,
            "exit_price": 1.0965,
            "pnl": 20,
            "pnl_percent": 0.18,
            "duration_minutes": 45,
            "outcome": "win"
        }
    ],
    "summary": {
        "total_signals": 150,
        "win_rate": 0.65,
        "average_pnl": 15.5,
        "sharpe_ratio": 1.85
    }
}
```

## Orders & Positions

### Place Order

<span class="api-endpoint post">POST</span> `/orders`

Submit a new trading order.

**Request Body:**

```json
{
    "symbol": "EURUSD",
    "side": "BUY",
    "quantity": 10000,
    "order_type": "LIMIT",
    "price": 1.0945,
    "time_in_force": "GTC",
    "stop_loss": 1.0920,
    "take_profit": 1.0995,
    "broker": "IB",
    "metadata": {
        "strategy": "elliott_wave",
        "signal_id": "sig_123e4567"
    }
}
```

**Response:**

```json
{
    "order_id": "ord_789abc",
    "client_order_id": "client_123",
    "status": "SUBMITTED",
    "created_at": "2025-01-15T14:30:00Z"
}
```

### Get Orders

<span class="api-endpoint get">GET</span> `/orders`

Get list of orders.

**Parameters:**

| Name | Type | Location | Required | Description |
|------|------|----------|----------|-------------|
| status | string | query | No | Filter by status (OPEN, FILLED, CANCELLED) |
| symbol | string | query | No | Filter by symbol |
| start_date | datetime | query | No | Start date filter |

### Cancel Order

<span class="api-endpoint delete">DELETE</span> `/orders/{order_id}`

Cancel an open order.

**Response:**

```json
{
    "order_id": "ord_789abc",
    "status": "CANCELLED",
    "cancelled_at": "2025-01-15T14:31:00Z"
}
```

### Get Positions

<span class="api-endpoint get">GET</span> `/positions`

Get all open positions.

**Response:**

```json
{
    "positions": [
        {
            "id": "pos_456def",
            "symbol": "EURUSD",
            "side": "LONG",
            "quantity": 10000,
            "entry_price": 1.0945,
            "current_price": 1.0955,
            "unrealized_pnl": 100,
            "unrealized_pnl_percent": 0.09,
            "opened_at": "2025-01-15T14:00:00Z"
        }
    ],
    "summary": {
        "total_positions": 3,
        "total_unrealized_pnl": 250,
        "margin_used": 3000,
        "margin_available": 97000
    }
}
```

## Account Information

### Get Account Summary

<span class="api-endpoint get">GET</span> `/account`

Get account balance and summary.

**Response:**

```json
{
    "account_id": "ACC123456",
    "balance": 100000,
    "equity": 100250,
    "margin_used": 3000,
    "margin_available": 97250,
    "unrealized_pnl": 250,
    "realized_pnl": 1500,
    "currency": "USD",
    "updated_at": "2025-01-15T14:30:00Z"
}
```

### Get Trading Performance

<span class="api-endpoint get">GET</span> `/account/performance`

Get detailed trading performance metrics.

**Parameters:**

| Name | Type | Location | Required | Description |
|------|------|----------|----------|-------------|
| period | string | query | No | Period (day, week, month, year) |

**Response:**

```json
{
    "period": "month",
    "metrics": {
        "total_trades": 150,
        "winning_trades": 98,
        "losing_trades": 52,
        "win_rate": 0.653,
        "profit_factor": 1.85,
        "sharpe_ratio": 2.1,
        "max_drawdown": 0.08,
        "total_pnl": 5000,
        "average_win": 75,
        "average_loss": -45,
        "best_trade": 250,
        "worst_trade": -120
    }
}
```

## System Configuration

### Get Configuration

<span class="api-endpoint get">GET</span> `/config`

Get current system configuration.

**Response:**

```json
{
    "trading": {
        "enabled": true,
        "max_positions": 10,
        "max_position_size": 100000,
        "default_stop_loss_pips": 50,
        "default_take_profit_pips": 100
    },
    "brokers": {
        "active": ["IB", "OANDA"],
        "primary": "IB"
    },
    "strategies": {
        "elliott_wave": {
            "enabled": true,
            "confidence_threshold": 0.7
        },
        "ml_ensemble": {
            "enabled": false,
            "models": ["xgboost", "lstm"]
        }
    }
}
```

### Update Configuration

<span class="api-endpoint put">PUT</span> `/config`

Update system configuration.

**Request Body:**

```json
{
    "trading": {
        "enabled": false,
        "max_positions": 5
    }
}
```

## WebSocket API

### Connection

Connect to WebSocket endpoint:

```javascript
const ws = new WebSocket('ws://localhost:8001/ws');

ws.onopen = () => {
    // Subscribe to events
    ws.send(JSON.stringify({
        type: 'subscribe',
        channels: ['market.EURUSD', 'signals', 'trades']
    }));
};

ws.onmessage = (event) => {
    const data = JSON.parse(event.data);
    console.log('Received:', data);
};
```

### Event Types

| Channel | Event | Description |
|---------|-------|-------------|
| `market.{symbol}` | `quote` | Real-time quotes |
| `market.{symbol}` | `bar` | New candlestick data |
| `signals` | `new_signal` | New trading signal |
| `signals` | `signal_closed` | Signal closed |
| `trades` | `order_placed` | Order submitted |
| `trades` | `order_filled` | Order executed |
| `trades` | `position_closed` | Position closed |
| `system` | `alert` | System alerts |

## Error Codes

| Code | Description | HTTP Status |
|------|-------------|-------------|
| `INVALID_REQUEST` | Malformed request | 400 |
| `UNAUTHORIZED` | Invalid or missing auth | 401 |
| `FORBIDDEN` | Insufficient permissions | 403 |
| `NOT_FOUND` | Resource not found | 404 |
| `RATE_LIMITED` | Too many requests | 429 |
| `INTERNAL_ERROR` | Server error | 500 |
| `SERVICE_UNAVAILABLE` | Service down | 503 |

## Rate Limiting

API rate limits:

| Endpoint Type | Limit | Window |
|--------------|-------|--------|
| Public endpoints | 100 | 1 minute |
| Trading endpoints | 10 | 1 minute |
| Data endpoints | 300 | 1 minute |

Rate limit headers:

```http
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 95
X-RateLimit-Reset: 1642261830
```

## SDKs & Examples

### Python Example

```python
import requests

class FXML4Client:
    def __init__(self, base_url="http://localhost:8000/api/v1"):
        self.base_url = base_url
        self.session = requests.Session()

    def get_market_data(self, symbol):
        response = self.session.get(f"{self.base_url}/market/symbols/{symbol}")
        response.raise_for_status()
        return response.json()

    def place_order(self, order_data):
        response = self.session.post(f"{self.base_url}/orders", json=order_data)
        response.raise_for_status()
        return response.json()

# Usage
client = FXML4Client()
data = client.get_market_data("EURUSD")
print(f"EURUSD: {data['bid']}/{data['ask']}")
```

### JavaScript Example

```javascript
class FXML4Client {
    constructor(baseUrl = 'http://localhost:8000/api/v1') {
        this.baseUrl = baseUrl;
    }

    async getMarketData(symbol) {
        const response = await fetch(`${this.baseUrl}/market/symbols/${symbol}`);
        return response.json();
    }

    async placeOrder(orderData) {
        const response = await fetch(`${this.baseUrl}/orders`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(orderData)
        });
        return response.json();
    }
}

// Usage
const client = new FXML4Client();
const data = await client.getMarketData('EURUSD');
console.log(`EURUSD: ${data.bid}/${data.ask}`);
```

## Testing

Test the API using curl:

```bash
# Health check
curl http://localhost:8000/api/v1/health

# Get market data
curl http://localhost:8000/api/v1/market/symbols/EURUSD

# Place order (requires auth in production)
curl -X POST http://localhost:8000/api/v1/orders \
  -H "Content-Type: application/json" \
  -d '{
    "symbol": "EURUSD",
    "side": "BUY",
    "quantity": 10000,
    "order_type": "MARKET"
  }'
```
