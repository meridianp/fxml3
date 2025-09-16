# API Specification & Integration Points

<!-- AUTODOC:START file="api_specification.md" section="overview" generated_by="docs-tdd-bot" -->
## API Architecture Overview

**Framework**: FastAPI with async/await support
**Base URL**: `http://localhost:8000` (development), `https://api.fxml4.com` (production)
**Authentication**: JWT tokens with 2FA support
**WebSocket**: Real-time market data and notifications
**Documentation**: Auto-generated OpenAPI/Swagger at `/docs`
<!-- AUTODOC:END -->

<!-- AUTODOC:START file="api_specification.md" section="authentication" generated_by="docs-tdd-bot" -->
## Authentication Endpoints

### POST /auth/login
**Validated by**: `tests/unit/api/auth/test_auth_comprehensive.py::test_login_success`
**Implementation**: `fxml4/api/auth/routes.py`

**Request**:
```json
{
  "email": "trader@example.com",
  "password": "secure_password",
  "totp_code": "123456"  // Optional 2FA code
}
```

**Response**:
```json
{
  "access_token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
  "refresh_token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
  "token_type": "bearer",
  "expires_in": 3600,
  "user": {
    "id": "123",
    "email": "trader@example.com",
    "role": "trader"
  }
}
```

### POST /auth/refresh
**Validated by**: `tests/unit/api/auth/test_auth_comprehensive.py::test_token_refresh`

**Headers**: `Authorization: Bearer <refresh_token>`

**Response**:
```json
{
  "access_token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
  "expires_in": 3600
}
```

### POST /auth/logout
**Validated by**: `tests/unit/api/auth/test_auth_comprehensive.py::test_logout_success`

**Headers**: `Authorization: Bearer <access_token>`

**Response**: `204 No Content`
<!-- AUTODOC:END -->

<!-- AUTODOC:START file="api_specification.md" section="market_data" generated_by="docs-tdd-bot" -->
## Market Data Endpoints

### GET /api/v1/market-data/symbols
**Validated by**: `tests/unit/api/test_endpoints.py::test_get_symbols`
**Implementation**: `fxml4/api/routers/market_data.py`

**Response**:
```json
{
  "symbols": [
    {
      "symbol": "EURUSD",
      "description": "Euro vs US Dollar",
      "min_size": 1000,
      "precision": 5,
      "is_active": true
    }
  ]
}
```

### GET /api/v1/market-data/prices/{symbol}
**Validated by**: `tests/unit/api/test_endpoints.py::test_get_current_price`

**Parameters**:
- `symbol`: Currency pair (e.g., EURUSD)
- `timeframe`: Optional (1m, 5m, 15m, 1h, 4h, 1d)

**Response**:
```json
{
  "symbol": "EURUSD",
  "bid": 1.0850,
  "ask": 1.0852,
  "timestamp": "2025-08-20T07:30:00Z",
  "spread": 0.0002
}
```

### GET /api/v1/market-data/history/{symbol}
**Validated by**: `tests/unit/api/test_endpoints.py::test_get_historical_data`

**Parameters**:
- `symbol`: Currency pair
- `timeframe`: Required (1m, 5m, 15m, 1h, 4h, 1d)
- `start_date`: ISO datetime
- `end_date`: ISO datetime
- `limit`: Max records (default: 1000)

**Response**:
```json
{
  "symbol": "EURUSD",
  "timeframe": "1h",
  "data": [
    {
      "timestamp": "2025-08-20T06:00:00Z",
      "open": 1.0845,
      "high": 1.0855,
      "low": 1.0840,
      "close": 1.0850,
      "volume": 1250000
    }
  ]
}
```

### WebSocket: /ws/market-data
**Validated by**: `tests/unit/test_websocket_market_data_streaming.py`
**Implementation**: `fxml4/api/websocket_market_data.py`

**Connection**: `ws://localhost:8000/ws/market-data`

**Subscription Message**:
```json
{
  "action": "subscribe",
  "symbols": ["EURUSD", "GBPUSD"],
  "types": ["tick", "candle"]
}
```

**Data Stream**:
```json
{
  "type": "tick",
  "symbol": "EURUSD",
  "bid": 1.0850,
  "ask": 1.0852,
  "timestamp": "2025-08-20T07:30:01.123Z"
}
```
<!-- AUTODOC:END -->

<!-- AUTODOC:START file="api_specification.md" section="trading" generated_by="docs-tdd-bot" -->
## Trading Endpoints

### GET /api/v1/account/info
**Validated by**: `tests/unit/test_account_monitoring.py::test_get_account_info`
**Implementation**: `fxml4/api/account_monitoring.py`

**Headers**: `Authorization: Bearer <access_token>`

**Response**:
```json
{
  "account_id": "12345",
  "balance": 50000.00,
  "equity": 50300.00,
  "margin_used": 1200.00,
  "margin_available": 49100.00,
  "unrealized_pl": 300.00,
  "currency": "USD",
  "leverage": "50:1",
  "last_update": "2025-08-20T07:30:00Z"
}
```

### POST /api/v1/orders
**Validated by**: `tests/unit/test_order_management.py::test_place_order`
**Implementation**: `fxml4/brokers/adapters/order_management.py`

**Request**:
```json
{
  "symbol": "EURUSD",
  "side": "buy",
  "order_type": "market",
  "quantity": 10000,
  "stop_loss": 1.0800,
  "take_profit": 1.0900,
  "time_in_force": "GTC"
}
```

**Response**:
```json
{
  "order_id": "ORD_20250820_001",
  "status": "pending",
  "symbol": "EURUSD",
  "side": "buy",
  "quantity": 10000,
  "filled_quantity": 0,
  "average_price": null,
  "timestamp": "2025-08-20T07:30:01Z"
}
```

### GET /api/v1/orders
**Validated by**: `tests/unit/test_order_management.py::test_get_orders`

**Parameters**:
- `status`: Optional (pending, filled, cancelled)
- `symbol`: Optional currency pair filter
- `limit`: Max records (default: 100)

**Response**:
```json
{
  "orders": [
    {
      "order_id": "ORD_20250820_001",
      "status": "filled",
      "symbol": "EURUSD",
      "side": "buy",
      "quantity": 10000,
      "filled_quantity": 10000,
      "average_price": 1.0851,
      "timestamp": "2025-08-20T07:30:01Z",
      "fill_timestamp": "2025-08-20T07:30:02Z"
    }
  ]
}
```

### GET /api/v1/positions
**Validated by**: `tests/unit/test_account_monitoring.py::test_get_positions`

**Response**:
```json
{
  "positions": [
    {
      "position_id": "POS_EURUSD_001",
      "symbol": "EURUSD",
      "side": "long",
      "quantity": 10000,
      "entry_price": 1.0851,
      "current_price": 1.0855,
      "unrealized_pl": 40.00,
      "timestamp": "2025-08-20T07:30:02Z"
    }
  ]
}
```

### DELETE /api/v1/orders/{order_id}
**Validated by**: `tests/unit/test_order_management.py::test_cancel_order`

**Response**:
```json
{
  "order_id": "ORD_20250820_001",
  "status": "cancelled",
  "timestamp": "2025-08-20T07:31:00Z"
}
```
<!-- AUTODOC:END -->

<!-- AUTODOC:START file="api_specification.md" section="ml_endpoints" generated_by="docs-tdd-bot" -->
## ML & Analytics Endpoints

### GET /api/v1/models
**Validated by**: `tests/unit/test_ml_models.py::test_list_models`
**Implementation**: `fxml4/ml/model_registry.py`

**Response**:
```json
{
  "models": [
    {
      "model_id": "EURUSD_RF_v1.2",
      "symbol": "EURUSD",
      "algorithm": "RandomForest",
      "accuracy": 0.72,
      "status": "active",
      "version": "1.2",
      "created_at": "2025-08-15T10:00:00Z",
      "last_trained": "2025-08-20T02:00:00Z"
    }
  ]
}
```

### POST /api/v1/models/train
**Validated by**: `tests/unit/test_ml_models.py::test_train_model`

**Request**:
```json
{
  "symbol": "EURUSD",
  "algorithm": "RandomForest",
  "features": ["sma_20", "rsi_14", "macd"],
  "lookback_days": 180,
  "target": "price_direction"
}
```

**Response**:
```json
{
  "training_job_id": "JOB_20250820_001",
  "status": "started",
  "estimated_duration": "15-30 minutes",
  "progress_url": "/api/v1/training-jobs/JOB_20250820_001"
}
```

### GET /api/v1/signals/{symbol}
**Validated by**: `tests/unit/test_enhanced_ml_signal_generator.py::test_generate_signals`
**Implementation**: `fxml4/strategy/integrated_signal_generator.py`

**Response**:
```json
{
  "symbol": "EURUSD",
  "signal": "buy",
  "confidence": 0.75,
  "models_consensus": {
    "ml_ensemble": "buy",
    "elliott_wave": "neutral",
    "sentiment": "buy"
  },
  "target_price": 1.0900,
  "stop_loss": 1.0800,
  "timestamp": "2025-08-20T07:30:00Z",
  "expires_at": "2025-08-20T11:30:00Z"
}
```

### POST /api/v1/backtest
**Validated by**: `tests/integration/test_ml_pipeline.py::test_backtest_integration`

**Request**:
```json
{
  "strategy": "ml_ensemble",
  "symbols": ["EURUSD"],
  "start_date": "2024-01-01",
  "end_date": "2024-12-31",
  "initial_balance": 10000,
  "parameters": {
    "risk_per_trade": 0.02,
    "max_positions": 3
  }
}
```

**Response**:
```json
{
  "backtest_id": "BT_20250820_001",
  "status": "running",
  "progress": 0,
  "estimated_completion": "2025-08-20T07:35:00Z",
  "results_url": "/api/v1/backtest/BT_20250820_001/results"
}
```
<!-- AUTODOC:END -->

<!-- AUTODOC:START file="api_specification.md" section="websocket_spec" generated_by="docs-tdd-bot" -->
## WebSocket Specifications

### Market Data WebSocket
**Endpoint**: `/ws/market-data`
**Validated by**: `tests/unit/test_websocket_market_data_streaming.py`

#### Connection Management
```javascript
const ws = new WebSocket('ws://localhost:8000/ws/market-data');

ws.onopen = function() {
    // Subscribe to symbols
    ws.send(JSON.stringify({
        action: 'subscribe',
        symbols: ['EURUSD', 'GBPUSD'],
        types: ['tick', 'candle_1m']
    }));
};
```

#### Message Types
**Tick Data**:
```json
{
  "type": "tick",
  "symbol": "EURUSD",
  "bid": 1.0850,
  "ask": 1.0852,
  "timestamp": "2025-08-20T07:30:01.123Z",
  "volume": 1000000
}
```

**Candle Data**:
```json
{
  "type": "candle_1m",
  "symbol": "EURUSD",
  "timestamp": "2025-08-20T07:30:00Z",
  "open": 1.0845,
  "high": 1.0855,
  "low": 1.0840,
  "close": 1.0850,
  "volume": 15000000
}
```

### Notifications WebSocket
**Endpoint**: `/ws/notifications`
**Headers**: `Authorization: Bearer <access_token>`

**Order Update**:
```json
{
  "type": "order_update",
  "order_id": "ORD_20250820_001",
  "status": "filled",
  "filled_quantity": 10000,
  "average_price": 1.0851,
  "timestamp": "2025-08-20T07:30:02Z"
}
```

**Account Update**:
```json
{
  "type": "account_update",
  "balance": 50040.00,
  "equity": 50340.00,
  "unrealized_pl": 340.00,
  "timestamp": "2025-08-20T07:30:02Z"
}
```
<!-- AUTODOC:END -->

<!-- AUTODOC:START file="api_specification.md" section="error_handling" generated_by="docs-tdd-bot" -->
## Error Handling & Status Codes

### HTTP Status Codes
- `200 OK` - Successful request
- `201 Created` - Resource created successfully
- `204 No Content` - Successful request with no response body
- `400 Bad Request` - Invalid request format or parameters
- `401 Unauthorized` - Authentication required or invalid token
- `403 Forbidden` - Insufficient permissions
- `404 Not Found` - Resource not found
- `409 Conflict` - Resource conflict (e.g., duplicate order)
- `422 Unprocessable Entity` - Validation errors
- `429 Too Many Requests` - Rate limit exceeded
- `500 Internal Server Error` - Server error

### Error Response Format
**Validated by**: `tests/unit/api/test_security_middleware.py::test_error_handling`

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Invalid order parameters",
    "details": {
      "quantity": ["Must be greater than minimum size of 1000"],
      "symbol": ["Invalid currency pair"]
    },
    "correlation_id": "req_20250820_073001_abc123",
    "timestamp": "2025-08-20T07:30:01Z"
  }
}
```

### Rate Limiting
**Implementation**: `fxml4/api/middleware/rate_limiting.py`
**Validated by**: `tests/unit/api/test_security_middleware.py::test_rate_limiting`

- **Default Limit**: 100 requests per minute per user
- **Trading Endpoints**: 10 orders per minute
- **Market Data**: 1000 requests per minute
- **WebSocket**: 1 connection per user per endpoint

**Rate Limit Headers**:
```
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 95
X-RateLimit-Reset: 1692520260
```
<!-- AUTODOC:END -->

<!-- AUTODOC:START file="api_specification.md" section="integration_testing" generated_by="docs-tdd-bot" -->
## Integration Testing Examples

### Authentication Flow Test
**File**: `tests/integration/test_api_endpoints.py`

```python
@pytest.mark.integration
async def test_complete_authentication_flow():
    """Test complete authentication workflow"""
    async with AsyncClient(app=app, base_url="http://test") as client:
        # Register new user
        response = await client.post("/auth/register", json={
            "email": "test@example.com",
            "password": "secure_password"
        })
        assert response.status_code == 201

        # Login
        response = await client.post("/auth/login", json={
            "email": "test@example.com",
            "password": "secure_password"
        })
        assert response.status_code == 200
        token = response.json()["access_token"]

        # Access protected endpoint
        headers = {"Authorization": f"Bearer {token}"}
        response = await client.get("/api/v1/account/info", headers=headers)
        assert response.status_code == 200
```

### Trading Workflow Test
**File**: `tests/integration/test_signal_to_execution_flow.py`

```python
@pytest.mark.integration
async def test_signal_to_order_execution():
    """Test complete signal generation to order execution"""
    # Generate signal
    signal_generator = IntegratedSignalGenerator()
    signal = await signal_generator.generate_signal("EURUSD")

    assert signal.confidence > 0.7

    # Place order based on signal
    order_manager = OrderManager()
    order_result = await order_manager.place_order({
        "symbol": signal.symbol,
        "side": signal.direction,
        "quantity": 10000,
        "stop_loss": signal.stop_loss,
        "take_profit": signal.target_price
    })

    assert order_result.status == "pending"

    # Verify order in database
    async with AsyncSession() as session:
        order = await session.get(Order, order_result.order_id)
        assert order is not None
        assert order.symbol == "EURUSD"
```
<!-- AUTODOC:END -->

---

*API specification validated through comprehensive test suite*
*All endpoints tested with TDD methodology and integration validation*
