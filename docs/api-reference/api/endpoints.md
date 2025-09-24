# FXML4 API Endpoints

This document provides detailed information about the FXML4 REST API endpoints. The API provides access to market data, backtesting, and performance analysis features.

## Base URL

All API requests should be sent to the base URL of the FXML4 API server, which defaults to:

```
http://localhost:8000
```

You can configure the host and port in the `config/default.yaml` file.

## Authentication - Sprint 1 Enhanced Security

### JWT Authentication with 2FA Support

The API implements enterprise-grade authentication with comprehensive security features:

#### Security Exception Handling
The authentication system includes enhanced exception classes:
- `TokenRotationError`: Handles JWT token rotation failures
- `SecurityAuditError`: Manages security audit operation failures
- `TwoFactorRequiredError`: Enforces 2FA authentication when required
- `TokenExpiredError`: Manages expired token scenarios
- `InsufficientPermissionsError`: Handles authorization failures

#### Authentication Flow

**Standard Login:**
```bash
POST /auth/login
Content-Type: application/json

{
  "username": "trader@example.com",
  "password": "secure_password"
}
```

**Response (2FA Required):**
```json
{
  "error": "TwoFactorRequiredError",
  "message": "Two-factor authentication required",
  "temp_token": "temp_jwt_token_here",
  "expires_in": 300
}
```

**2FA Completion:**
```bash
POST /auth/2fa/verify
Authorization: Bearer {temp_token}
Content-Type: application/json

{
  "code": "123456"
}
```

**Successful Authentication Response:**
```json
{
  "access_token": "jwt_access_token",
  "refresh_token": "jwt_refresh_token",
  "token_type": "bearer",
  "expires_in": 3600,
  "user_id": "uuid",
  "permissions": ["trading", "data_access"]
}
```

#### Token Management

**Token Refresh:**
```bash
POST /auth/refresh
Content-Type: application/json

{
  "refresh_token": "jwt_refresh_token"
}
```

#### Error Responses

**Token Rotation Error (500):**
```json
{
  "error": "TokenRotationError",
  "message": "Failed to rotate authentication token",
  "audit_id": "audit_12345"
}
```

**Security Audit Error (500):**
```json
{
  "error": "SecurityAuditError",
  "message": "Security audit operation failed",
  "incident_id": "sec_incident_67890"
}
```

### Request Headers
All authenticated requests must include:
```
Authorization: Bearer {access_token}
X-API-Version: v1
```

## API Endpoints

### Health Check

```
GET /health
```

Check if the API server is running and healthy.

**Response:**

```json
{
  "status": "ok"
}
```

### WebSocket Real-Time Market Data - Sprint 1 Implementation

#### WebSocket Connection

```
WS /ws/market-data
```

Establish WebSocket connection for real-time market data streaming with sub-millisecond latency.

**Connection Headers:**
```
Authorization: Bearer {access_token}
Upgrade: websocket
Connection: Upgrade
```

**Connection Confirmation:**
```json
{
  "type": "connection_confirmed",
  "client_id": "client_abc123",
  "timestamp": "2024-01-15T10:30:00.000Z",
  "status": "connected"
}
```

#### Subscribe to Symbol

**Client Message:**
```json
{
  "type": "subscribe",
  "symbol": "EURUSD",
  "timestamp": "2024-01-15T10:30:00.000Z"
}
```

**Subscription Confirmation:**
```json
{
  "type": "subscription_confirmed",
  "symbol": "EURUSD",
  "client_id": "client_abc123",
  "timestamp": "2024-01-15T10:30:00.000Z"
}
```

#### Real-Time Price Updates

```json
{
  "type": "price_update",
  "symbol": "EURUSD",
  "bid": 1.0955,
  "ask": 1.0957,
  "timestamp": "2024-01-15T10:30:00.123Z",
  "volume": 1000,
  "latency_ms": 0.8
}
```

#### Unsubscribe from Symbol

```json
{
  "type": "unsubscribe",
  "symbol": "EURUSD",
  "timestamp": "2024-01-15T10:30:00.000Z"
}
```

#### Error Handling

**Invalid Symbol:**
```json
{
  "type": "error",
  "error_code": "INVALID_SYMBOL",
  "message": "Symbol INVALID not supported",
  "timestamp": "2024-01-15T10:30:00.000Z"
}
```

**Data Validation Error:**
```json
{
  "type": "validation_error",
  "errors": ["Invalid bid price: -1.0", "Ask price cannot be NaN"],
  "symbol": "EURUSD",
  "timestamp": "2024-01-15T10:30:00.000Z"
}
```

#### Connection Management Features

- **Automatic Reconnection**: Exponential backoff with max 3 attempts
- **Data Buffering**: 100-message buffer per symbol for reconnection recovery
- **Connection Health**: Sub-millisecond latency monitoring
- **Feed Failover**: Automatic switching between data sources

### Get Historical Market Data

```
POST /data
```

Fetch historical market data for a specified symbol and timeframe.

**Request Body:**

```json
{
  "symbol": "EURUSD",
  "timeframe": "1h",
  "start_date": "2023-01-01",
  "end_date": "2023-12-31",
  "limit": 1000
}
```

| Field       | Type    | Description                                                |
|-------------|---------|------------------------------------------------------------|
| symbol      | string  | Trading symbol (e.g., "EURUSD", "AAPL")                    |
| timeframe   | string  | Data timeframe (e.g., "1m", "5m", "1h", "1d")              |
| start_date  | string  | Start date in ISO format (optional)                        |
| end_date    | string  | End date in ISO format (optional)                          |
| limit       | integer | Maximum number of data points to return (optional)         |

**Response:**

```json
{
  "symbol": "EURUSD",
  "timeframe": "1h",
  "start_date": "2023-01-01",
  "end_date": "2023-12-31",
  "data": [
    {
      "timestamp": "2023-01-01T00:00:00",
      "open": 1.0699,
      "high": 1.0712,
      "low": 1.0688,
      "close": 1.0705,
      "volume": 10500
    },
    // Additional data points...
  ],
  "count": 8760,
  "source": "alpha_vantage"
}
```

### Run Backtest

```
POST /backtest
```

Run a backtest for a specified trading strategy.

**Request Body:**

```json
{
  "symbol": "EURUSD",
  "timeframe": "1h",
  "strategy": "ml_strategy",
  "start_date": "2023-01-01",
  "end_date": "2023-12-31",
  "initial_capital": 10000.0,
  "parameters": {
    "model": "random_forest",
    "features": ["technical", "volatility"]
  },
  "auto_report": true
}
```

| Field           | Type    | Description                                                |
|-----------------|---------|------------------------------------------------------------|
| symbol          | string  | Trading symbol                                             |
| timeframe       | string  | Data timeframe                                             |
| strategy        | string  | Strategy to test ("ml_strategy", "wave_strategy", "integrated_strategy") |
| start_date      | string  | Start date in ISO format                                   |
| end_date        | string  | End date in ISO format                                     |
| initial_capital | number  | Initial capital for backtesting                            |
| parameters      | object  | Strategy-specific parameters                               |
| auto_report     | boolean | Whether to automatically generate a performance report     |

**Response:**

```json
{
  "backtest_id": "BT-20230101-123456",
  "symbol": "EURUSD",
  "timeframe": "1h",
  "strategy": "ml_strategy",
  "start_date": "2023-01-01",
  "end_date": "2023-12-31",
  "initial_capital": 10000.0,
  "final_capital": 12500.0,
  "total_return": 2500.0,
  "total_return_pct": 25.0,
  "max_drawdown": 800.0,
  "max_drawdown_pct": 8.0,
  "sharpe_ratio": 1.8,
  "sortino_ratio": 2.2,
  "win_rate": 0.65,
  "profit_factor": 2.1,
  "trade_count": 42,
  "report_url": "/performance/report/BT-20230101-123456"
}
```

### Get Performance Metrics

```
GET /performance/metrics/{backtest_id}
```

Get detailed performance metrics for a backtest.

**Path Parameters:**

| Parameter    | Description                       |
|--------------|-----------------------------------|
| backtest_id  | ID of the backtest                |

**Query Parameters:**

| Parameter           | Type    | Description                                                |
|---------------------|---------|------------------------------------------------------------|
| include_trades      | boolean | Whether to include trade details (default: false)          |
| include_equity_curve| boolean | Whether to include equity curve data (default: false)      |

**Response:**

```json
{
  "backtest_id": "BT-20230101-123456",
  "metrics": {
    "total_return_pct": 25.0,
    "annualized_return": 18.2,
    "sharpe_ratio": 1.8,
    "sortino_ratio": 2.2,
    "max_drawdown_pct": 8.0,
    "win_rate": 0.65,
    "profit_factor": 2.1,
    "recovery_factor": 3.1,
    "expectancy": 0.52,
    "avg_win": 350.0,
    "avg_loss": -200.0,
    "risk_of_ruin": 0.05,
    "trades_per_month": 6.3,
    "max_consecutive_wins": 5,
    "max_consecutive_losses": 3
  },
  "monthly_returns": {
    "2023-01": 2.1,
    "2023-02": -1.5,
    "2023-03": 3.2,
    // Additional months...
  },
  "drawdowns": [
    {
      "start_date": "2023-02-15",
      "end_date": "2023-02-28",
      "recovery_date": "2023-03-10",
      "depth_pct": 8.0,
      "duration_days": 13,
      "recovery_days": 10
    },
    // Additional drawdowns...
  ],
  "monte_carlo": {
    "mean_return": 25.8,
    "median_return": 24.9,
    "worst_case": 15.2,
    "best_case": 35.6,
    "probability_of_profit": 0.996,
    "probability_of_10pct_drawdown": 0.32,
    "percentiles": {
      "5": 18.5,
      "25": 22.4,
      "50": 24.9,
      "75": 28.1,
      "95": 32.7
    }
  },
  // Optional fields if requested:
  "trades": [
    {
      "entry_time": "2023-01-05T10:30:00",
      "exit_time": "2023-01-07T14:45:00",
      "symbol": "EURUSD",
      "side": "buy",
      "entry_price": 1.0650,
      "exit_price": 1.0720,
      "quantity": 10000,
      "pnl": 700.0,
      "pnl_pct": 0.657
    },
    // Additional trades...
  ],
  "equity_curve": [
    {
      "timestamp": "2023-01-01T00:00:00",
      "equity": 10000.0
    },
    // Additional equity points...
  ]
}
```

### Get Performance Report

```
GET /performance/report/{backtest_id}
```

Get a performance report for a backtest.

**Path Parameters:**

| Parameter    | Description                       |
|--------------|-----------------------------------|
| backtest_id  | ID of the backtest                |

**Query Parameters:**

| Parameter | Type   | Description                                 |
|-----------|--------|---------------------------------------------|
| format    | string | Report format: "html" or "pdf" (default: "html") |

**Response:**

Returns the report file in the requested format.

### Compare Backtests

```
POST /performance/compare
```

Compare multiple backtests.

**Request Body:**

```json
{
  "backtest_ids": ["BT-20230101-123456", "BT-20230215-123456", "BT-20230310-123456"],
  "metrics": ["total_return_pct", "max_drawdown_pct", "sharpe_ratio"]
}
```

| Field        | Type     | Description                                                |
|--------------|---------|------------------------------------------------------------|
| backtest_ids | array   | List of backtest IDs to compare                            |
| metrics      | array   | List of metrics to compare                                 |

**Response:**

```json
{
  "backtest_ids": ["BT-20230101-123456", "BT-20230215-123456", "BT-20230310-123456"],
  "metrics": {
    "total_return_pct": {
      "BT-20230101-123456": 25.0,
      "BT-20230215-123456": 18.5,
      "BT-20230310-123456": 22.3
    },
    "max_drawdown_pct": {
      "BT-20230101-123456": 8.0,
      "BT-20230215-123456": 6.5,
      "BT-20230310-123456": 7.2
    },
    "sharpe_ratio": {
      "BT-20230101-123456": 1.8,
      "BT-20230215-123456": 1.5,
      "BT-20230310-123456": 1.7
    }
  },
  "ranking": {
    "total_return_pct": ["BT-20230101-123456", "BT-20230310-123456", "BT-20230215-123456"],
    "max_drawdown_pct": ["BT-20230215-123456", "BT-20230310-123456", "BT-20230101-123456"],
    "sharpe_ratio": ["BT-20230101-123456", "BT-20230310-123456", "BT-20230215-123456"]
  },
  "correlation_matrix": {
    "BT-20230101-123456": {
      "BT-20230101-123456": 1.0,
      "BT-20230215-123456": 0.75,
      "BT-20230310-123456": 0.82
    },
    "BT-20230215-123456": {
      "BT-20230101-123456": 0.75,
      "BT-20230215-123456": 1.0,
      "BT-20230310-123456": 0.68
    },
    "BT-20230310-123456": {
      "BT-20230101-123456": 0.82,
      "BT-20230215-123456": 0.68,
      "BT-20230310-123456": 1.0
    }
  }
}
```

## Error Handling

The API returns standard HTTP status codes with enhanced security error handling:

### Standard HTTP Status Codes
- 200: Success
- 400: Bad Request
- 401: Unauthorized (authentication required)
- 403: Forbidden (insufficient permissions)
- 404: Not Found
- 422: Validation Error
- 429: Rate Limit Exceeded
- 500: Internal Server Error

### Authentication Error Responses

**Invalid Credentials (401):**
```json
{
  "error": "InvalidCredentialsError",
  "message": "Invalid username or password",
  "auth_attempt_id": "attempt_123"
}
```

**Token Expired (401):**
```json
{
  "error": "TokenExpiredError",
  "message": "Access token has expired",
  "expired_at": "2024-01-15T10:30:00Z"
}
```

**Insufficient Permissions (403):**
```json
{
  "error": "InsufficientPermissionsError",
  "message": "User lacks required trading permissions",
  "required_permissions": ["trading.execute"]
}
```

**Session Error (401):**
```json
{
  "error": "SessionError",
  "message": "User session has been invalidated",
  "reason": "concurrent_login_detected"
}
```

### Standard Error Response
```json
{
  "detail": "Error message describing the issue",
  "error_code": "SPECIFIC_ERROR_CODE",
  "timestamp": "2024-01-15T10:30:00Z",
  "request_id": "req_abc123"
}
```

## Strategy Parameters

### ML Strategy Parameters

```json
{
  "model": "random_forest",  // or "xgboost", "logistic"
  "features": ["technical", "price_patterns", "volatility", "sentiment", "economic"],
  "risk_pct": 0.02
}
```

### Wave Strategy Parameters

```json
{
  "strictness": 0.5,  // 0.0 to 1.0, higher values enforce stricter Elliott Wave rules
  "wave_validation": true,  // Whether to use LLM for wave validation
  "risk_pct": 0.02
}
```

### Integrated Strategy Parameters

```json
{
  "ml_weight": 0.5,  // Weight of ML signals (0.0 to 1.0)
  "wave_weight": 0.3,  // Weight of wave signals (0.0 to 1.0)
  "sentiment_weight": 0.2,  // Weight of sentiment signals (0.0 to 1.0)
  "risk_pct": 0.02
}
```
