# FXML4 API Documentation

This document provides an overview of the FXML4 API, its endpoints, authentication, and usage examples.

## Overview

The FXML4 API provides programmatic access to FXML4's trading platform functionality, including:

- Market data retrieval
- Signal generation
- Backtesting
- Performance analytics

## Authentication

The API uses JWT (JSON Web Token) authentication. To use the API, you must:

1. Obtain an access token via the `/token` endpoint
2. Include the token in the `Authorization` header of your requests

### Getting a Token

```bash
curl -X POST "http://localhost:8000/token" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=user&password=password"
```

This will return a JSON response with an access token:

```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer"
}
```

### Using the Token

Include the token in your requests:

```bash
curl -X GET "http://localhost:8000/data" \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..." \
  -H "Content-Type: application/json" \
  -d '{"symbol": "GBPUSD", "timeframe": "1h", "limit": 100}'
```

## Rate Limiting

The API has rate limiting to prevent abuse. By default, it allows 120 requests per minute per IP address. If you exceed this limit, you'll receive a 429 Too Many Requests response.

## API Endpoints

### Public Endpoints

These endpoints don't require authentication:

- `GET /` - Root endpoint (API health check)
- `GET /health` - Detailed health check
- `GET /docs` - Swagger UI documentation
- `GET /redoc` - ReDoc documentation

### Authenticated Endpoints

These endpoints require authentication:

#### User Management

- `POST /token` - Get an access token
- `GET /users/me` - Get current user information

#### Market Data

- `POST /data` - Get market data for a symbol

#### Signal Generation

- `POST /signals` - Generate trading signals

#### Backtesting

- `POST /backtest` - Run a backtest
- `GET /performance/metrics/{backtest_id}` - Get performance metrics for a backtest
- `GET /performance/report/{backtest_id}` - Get a performance report for a backtest
- `POST /performance/compare` - Compare multiple backtests

## Examples

### Getting Market Data

```python
import requests
import json

# Get token
token_response = requests.post(
    "http://localhost:8000/token",
    data={"username": "user", "password": "password"}
)
token = token_response.json()["access_token"]

# Get market data
data_response = requests.post(
    "http://localhost:8000/data",
    headers={
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    },
    json={
        "symbol": "GBPUSD",
        "timeframe": "1h",
        "limit": 100
    }
)

print(json.dumps(data_response.json(), indent=2))
```

### Running a Backtest

```python
import requests
import json

# Get token
token_response = requests.post(
    "http://localhost:8000/token",
    data={"username": "user", "password": "password"}
)
token = token_response.json()["access_token"]

# Run backtest
backtest_response = requests.post(
    "http://localhost:8000/backtest",
    headers={
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    },
    json={
        "symbol": "GBPUSD",
        "timeframe": "1h",
        "strategy": "integrated_strategy",
        "start_date": "2023-01-01",
        "end_date": "2023-12-31",
        "initial_capital": 10000.0,
        "parameters": {
            "risk_pct": 0.02
        }
    }
)

print(json.dumps(backtest_response.json(), indent=2))
```

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

## Pagination

For endpoints that return large amounts of data, pagination is supported via `limit` and `offset` parameters.

## Scopes and Permissions

The API uses a scope-based permission system:

- `read`: Read-only access
- `user`: Standard user access (includes read)
- `admin`: Administrative access (includes user and read)

Different endpoints require different scopes. The `/users/me` endpoint can be used to see your assigned scopes.