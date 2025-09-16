# FXML4 API Reference

This document provides a reference for the FXML4 API, including endpoint descriptions, request/response formats, and examples.

## Base URL

The base URL for the API depends on your deployment:

- Local development: `http://localhost:8000`
- Docker deployment: `http://localhost:8000` (or configured port)
- Production: `https://api.yourdomain.com` (replace with your actual domain)

## Authentication

The API uses JWT (JSON Web Token) authentication. To use authenticated endpoints, you must:

1. Obtain an access token via the `/token` endpoint
2. Include the token in the `Authorization` header of your requests

### Getting a Token

**Endpoint:** `POST /token`

**Request:**
```http
POST /token HTTP/1.1
Content-Type: application/x-www-form-urlencoded

username=user&password=password
```

**Response:**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer"
}
```

**Status Codes:**
- 200: Success
- 401: Invalid credentials

### Using the Token

Include the token in the `Authorization` header:

```http
GET /data HTTP/1.1
Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
Content-Type: application/json

{
  "symbol": "GBPUSD",
  "timeframe": "1h"
}
```

## Endpoints

### Public Endpoints

#### Health Check

**Endpoint:** `GET /health`

**Response:**
```json
{
  "status": "ok"
}
```

**Status Codes:**
- 200: API is healthy

### Authenticated Endpoints

#### Get User Information

**Endpoint:** `GET /users/me`

**Headers:**
- `Authorization`: Bearer token

**Response:**
```json
{
  "username": "user",
  "email": "user@example.com",
  "full_name": "Test User",
  "disabled": false,
  "scopes": ["user", "read"]
}
```

**Status Codes:**
- 200: Success
- 401: Unauthorized

#### Get Market Data

**Endpoint:** `POST /data`

**Headers:**
- `Authorization`: Bearer token

**Request:**
```json
{
  "symbol": "GBPUSD",
  "timeframe": "1h",
  "start_date": "2023-01-01",
  "end_date": "2023-12-31",
  "limit": 100
}
```

**Response:**
```json
{
  "symbol": "GBPUSD",
  "timeframe": "1h",
  "start_date": "2023-01-01",
  "end_date": "2023-12-31",
  "data": [
    {
      "timestamp": "2023-01-01T00:00:00",
      "open": 1.2345,
      "high": 1.2456,
      "low": 1.2321,
      "close": 1.2401,
      "volume": 1234
    },
    // ... more data
  ],
  "count": 100,
  "source": "alpha_vantage"
}
```

**Status Codes:**
- 200: Success
- 401: Unauthorized
- 500: Internal server error

#### Generate Trading Signals

**Endpoint:** `POST /signals`

**Headers:**
- `Authorization`: Bearer token

**Request:**
```json
{
  "symbol": "GBPUSD",
  "timeframe": "1h",
  "strategy": "integrated_strategy",
  "parameters": {
    "threshold": 0.7
  }
}
```

**Response:**
```json
{
  "symbol": "GBPUSD",
  "timeframe": "1h",
  "strategy": "integrated_strategy",
  "signals": [
    {
      "symbol": "GBPUSD",
      "timestamp": "2023-01-01T12:00:00",
      "signal_type": "entry_long",
      "confidence": 0.85,
      "price": 1.2345,
      "description": "Strong buying opportunity"
    }
  ]
}
```

**Status Codes:**
- 200: Success
- 401: Unauthorized
- 500: Internal server error

#### Run Backtest

**Endpoint:** `POST /backtest`

**Headers:**
- `Authorization`: Bearer token

**Request:**
```json
{
  "symbol": "GBPUSD",
  "timeframe": "1h",
  "strategy": "integrated_strategy",
  "start_date": "2023-01-01",
  "end_date": "2023-12-31",
  "initial_capital": 10000.0,
  "parameters": {
    "risk_pct": 0.02
  },
  "auto_report": true
}
```

**Response:**
```json
{
  "backtest_id": "BT-20230101-123456",
  "symbol": "GBPUSD",
  "timeframe": "1h",
  "strategy": "integrated_strategy",
  "start_date": "2023-01-01",
  "end_date": "2023-12-31",
  "initial_capital": 10000.0,
  "final_capital": 12000.0,
  "total_return": 2000.0,
  "total_return_pct": 20.0,
  "max_drawdown": 500.0,
  "max_drawdown_pct": 5.0,
  "sharpe_ratio": 1.5,
  "sortino_ratio": 2.0,
  "win_rate": 0.6,
  "profit_factor": 1.8,
  "trade_count": 50,
  "report_url": "/performance/report/BT-20230101-123456"
}
```

**Status Codes:**
- 200: Success
- 401: Unauthorized
- 500: Internal server error

#### Get Performance Metrics

**Endpoint:** `GET /performance/metrics/{backtest_id}`

**Headers:**
- `Authorization`: Bearer token

**Query Parameters:**
- `include_trades`: Whether to include trade details (default: false)
- `include_equity_curve`: Whether to include equity curve data (default: false)

**Response:**
```json
{
  "backtest_id": "BT-20230101-123456",
  "metrics": {
    "total_return_pct": 20.0,
    "annualized_return": 21.5,
    "sharpe_ratio": 1.5,
    "sortino_ratio": 2.0,
    "max_drawdown_pct": 5.0,
    "win_rate": 0.6,
    "profit_factor": 1.8,
    "recovery_factor": 4.0,
    "expectancy": 0.5,
    "avg_win": 250.0,
    "avg_loss": -100.0,
    "risk_of_ruin": 0.01,
    "trades_per_month": 8.3,
    "max_consecutive_wins": 5,
    "max_consecutive_losses": 3
  },
  "monthly_returns": {
    "2023-01": 2.5,
    "2023-02": 1.8,
    // ... more months
  },
  "drawdowns": [
    {
      "start": "2023-03-15T10:00:00",
      "end": "2023-03-22T14:00:00",
      "depth_pct": 5.0,
      "recovery_days": 5
    }
  ],
  "trades": [
    // Only included if include_trades=true
    {
      "position_id": "P-123",
      "symbol": "GBPUSD",
      "side": "buy",
      "entry_price": 1.2345,
      "entry_time": "2023-01-02T10:00:00",
      "quantity": 10000,
      "exit_price": 1.2456,
      "exit_time": "2023-01-03T14:00:00",
      "pnl": 111.0,
      "pnl_pct": 0.9,
      "status": "closed"
    }
  ],
  "equity_curve": [
    // Only included if include_equity_curve=true
    {
      "timestamp": "2023-01-01T00:00:00",
      "equity": 10000.0
    },
    {
      "timestamp": "2023-01-02T00:00:00",
      "equity": 10111.0
    }
  ]
}
```

**Status Codes:**
- 200: Success
- 401: Unauthorized
- 404: Backtest not found
- 500: Internal server error

#### Get Performance Report

**Endpoint:** `GET /performance/report/{backtest_id}`

**Headers:**
- `Authorization`: Bearer token

**Query Parameters:**
- `format`: Report format (html or pdf, default: html)

**Response:**
HTML or PDF file with the performance report

**Status Codes:**
- 200: Success
- 401: Unauthorized
- 404: Backtest not found
- 500: Internal server error

#### Compare Backtests

**Endpoint:** `POST /performance/compare`

**Headers:**
- `Authorization`: Bearer token

**Request:**
```json
{
  "backtest_ids": ["BT-20230101-123456", "BT-20230201-123456"],
  "metrics": ["total_return_pct", "max_drawdown_pct", "sharpe_ratio"]
}
```

**Response:**
```json
{
  "backtest_ids": ["BT-20230101-123456", "BT-20230201-123456"],
  "metrics": {
    "total_return_pct": {
      "BT-20230101-123456": 20.0,
      "BT-20230201-123456": 15.0
    },
    "max_drawdown_pct": {
      "BT-20230101-123456": 5.0,
      "BT-20230201-123456": 4.0
    },
    "sharpe_ratio": {
      "BT-20230101-123456": 1.5,
      "BT-20230201-123456": 1.2
    }
  },
  "ranking": {
    "total_return_pct": ["BT-20230101-123456", "BT-20230201-123456"],
    "max_drawdown_pct": ["BT-20230201-123456", "BT-20230101-123456"],
    "sharpe_ratio": ["BT-20230101-123456", "BT-20230201-123456"]
  },
  "correlation_matrix": {
    "BT-20230101-123456": {
      "BT-20230101-123456": 1.0,
      "BT-20230201-123456": 0.7
    },
    "BT-20230201-123456": {
      "BT-20230101-123456": 0.7,
      "BT-20230201-123456": 1.0
    }
  }
}
```

**Status Codes:**
- 200: Success
- 401: Unauthorized
- 404: One or more backtests not found
- 500: Internal server error

## Data Structures

### TimeframeEnum

Supported timeframes:

- `1m`: 1 minute
- `5m`: 5 minutes
- `15m`: 15 minutes
- `30m`: 30 minutes
- `1h`: 1 hour
- `4h`: 4 hours
- `1d`: 1 day
- `1w`: 1 week
- `1M`: 1 month

### StrategyEnum

Supported strategies:

- `integrated_strategy`: Combined strategy with technical indicators
- `ml_strategy`: Machine learning based strategy
- `wave_strategy`: Elliott Wave based strategy
- `sentiment_strategy`: Sentiment analysis based strategy

### SignalTypeEnum

Signal types:

- `entry_long`: Enter a long position
- `entry_short`: Enter a short position
- `exit_long`: Exit a long position
- `exit_short`: Exit a short position

### OrderSideEnum

Order side types:

- `buy`: Buy order
- `sell`: Sell order

## Error Handling

The API returns standard HTTP status codes:

- 200: Success
- 400: Bad Request
- 401: Unauthorized
- 403: Forbidden
- 404: Not Found
- 429: Too Many Requests
- 500: Internal Server Error

Error responses include a JSON body with details:

```json
{
  "detail": "Error message describing the issue"
}
```

## Rate Limiting

The API has rate limiting to prevent abuse. By default, it allows 120 requests per minute per IP address. If you exceed this limit, you'll receive a 429 Too Many Requests response with a Retry-After header indicating when you can try again.
