# API Architecture

This document outlines the API architecture for FXML3, providing a robust foundation for frontend applications to interact with the system.

## Overview

The FXML3 API follows RESTful principles with OpenAPI specification. It implements proper authentication, rate limiting, and versioning to ensure secure and scalable access to the system's capabilities.

```
┌────────────────┐      ┌────────────────┐      ┌────────────────┐
│                │      │                │      │                │
│  Client Apps   │──────│  FXML3 API     │──────│  FXML3 Core    │
│  (Web/Mobile)  │      │  Gateway       │      │  System        │
│                │      │                │      │                │
└────────────────┘      └────────────────┘      └────────────────┘
                               │                        │
                               │                        │
                        ┌──────┴───────┐         ┌──────┴───────┐
                        │              │         │              │
                        │  Auth        │         │  Data        │
                        │  Service     │         │  Storage     │
                        │              │         │              │
                        └──────────────┘         └──────────────┘
```

## API Gateway

The API Gateway serves as the single entry point for all client requests. It provides:

- Request routing
- Authentication and authorization
- Rate limiting and throttling
- Request/response transformation
- Monitoring and logging
- OpenAPI documentation

## Authentication

The API implements multiple authentication methods to support different client types:

### API Key Authentication

For server-to-server integrations and automated workflows:

```http
GET /api/v1/wave-analysis/eurusd/daily
X-API-Key: your_api_key_here
```

### JWT Authentication

For web and mobile applications with user sessions:

```http
GET /api/v1/wave-analysis/eurusd/daily
Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

### OAuth 2.0

For third-party application integrations with scoped permissions:

- Authorization Code Flow for web applications
- PKCE Flow for mobile/SPA applications
- Client Credentials Flow for trusted backend services

## API Versioning

All endpoints are versioned to ensure backward compatibility:

```
/api/v1/...  # Current stable version
/api/v2/...  # Future version (when available)
```

## Resource Hierarchy

The API follows a logical resource hierarchy:

```
/api/v1/symbols                            # Available trading symbols
/api/v1/symbols/{symbol}/timeframes        # Available timeframes for symbol
/api/v1/symbols/{symbol}/data              # Historical price data
/api/v1/analysis/waves                     # Wave analysis endpoints
/api/v1/analysis/waves/{id}                # Specific wave analysis
/api/v1/strategies                         # Trading strategies
/api/v1/strategies/{id}                    # Specific strategy
/api/v1/backtests                          # Backtest requests
/api/v1/backtests/{id}                     # Specific backtest result
/api/v1/agents                             # Agent system endpoints
/api/v1/agents/{agent_type}                # Specific agent type operations
/api/v1/user                               # User-specific endpoints
/api/v1/settings                           # System settings
```

## Core Endpoints

### Wave Analysis Endpoints

#### Request Wave Analysis

```http
POST /api/v1/analysis/waves
Content-Type: application/json
Authorization: Bearer {token}

{
  "symbol": "EURUSD",
  "timeframe": "H1",
  "start_date": "2023-01-01",
  "end_date": "2023-12-31",
  "wave_options": {
    "include_subwaves": true,
    "min_wave_points": 5,
    "confidence_threshold": 0.7
  }
}
```

#### Get Wave Analysis

```http
GET /api/v1/analysis/waves/{analysis_id}
Authorization: Bearer {token}
```

### Strategy Endpoints

#### Generate Strategy

```http
POST /api/v1/strategies
Content-Type: application/json
Authorization: Bearer {token}

{
  "wave_analysis_id": "123e4567-e89b-12d3-a456-426614174000",
  "strategy_type": "impulse_wave",
  "risk_parameters": {
    "risk_per_trade": 0.02,
    "max_drawdown": 0.10,
    "profit_target_multiplier": 1.5
  }
}
```

#### Get Strategy

```http
GET /api/v1/strategies/{strategy_id}
Authorization: Bearer {token}
```

### Backtest Endpoints

#### Create Backtest

```http
POST /api/v1/backtests
Content-Type: application/json
Authorization: Bearer {token}

{
  "strategy_id": "123e4567-e89b-12d3-a456-426614174000",
  "start_date": "2023-01-01",
  "end_date": "2023-12-31",
  "initial_capital": 10000,
  "validation_methods": ["monte_carlo", "walk_forward"],
  "slippage_model": "normal",
  "spread_model": "variable",
  "commission_model": "fixed"
}
```

#### Get Backtest Results

```http
GET /api/v1/backtests/{backtest_id}
Authorization: Bearer {token}
```

### Agent System Endpoints

#### Execute Agent Workflow

```http
POST /api/v1/agents/workflow
Content-Type: application/json
Authorization: Bearer {token}

{
  "workflow_name": "complete_analysis",
  "tasks": [
    {"agent": "wave_detection", "method": "detect_waves", "params": {...}},
    {"agent": "strategy", "method": "generate_strategy", "params": {...}},
    {"agent": "backtest", "method": "validate_strategy", "params": {...}}
  ]
}
```

## Response Format

All API responses follow a consistent format:

```json
{
  "status": "success",  // or "error"
  "data": {             // Main response data (null if error)
    // Response-specific data
  },
  "meta": {             // Metadata about the response
    "timestamp": "2025-09-03T10:15:30Z",
    "version": "1.0",
    "processor_time": 1.234
  },
  "error": {            // Error details (null if success)
    "code": "RESOURCE_NOT_FOUND",
    "message": "Requested resource not found",
    "details": {}
  }
}
```

## Error Handling

Errors follow HTTP status codes with detailed error messages:

- 400 Bad Request - Invalid input
- 401 Unauthorized - Missing or invalid authentication
- 403 Forbidden - Authenticated but not authorized
- 404 Not Found - Resource not found
- 429 Too Many Requests - Rate limit exceeded
- 500 Internal Server Error - Unexpected server error

Example error response:

```json
{
  "status": "error",
  "data": null,
  "meta": {
    "timestamp": "2025-09-03T10:15:30Z",
    "version": "1.0"
  },
  "error": {
    "code": "INVALID_PARAMETERS",
    "message": "Invalid parameter values provided",
    "details": {
      "fields": {
        "symbol": "Unknown symbol 'BTCUSDT'",
        "timeframe": "Timeframe must be one of: M1, M5, M15, H1, H4, D1"
      }
    }
  }
}
```

## Rate Limiting

API requests are rate-limited based on client authentication:

- Free tier: 100 requests per hour
- Basic tier: 1,000 requests per hour
- Premium tier: 10,000 requests per hour

Rate limit headers are included in responses:

```
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 92
X-RateLimit-Reset: 1631022658
```

## Asynchronous Operations

Long-running operations use asynchronous processing:

1. Client submits request and receives a task ID
2. Client polls status endpoint or subscribes to WebSocket notifications
3. When processing completes, the result is made available

Example:

```http
POST /api/v1/backtests
Content-Type: application/json
Authorization: Bearer {token}

{
  "strategy_id": "123e4567-e89b-12d3-a456-426614174000",
  "start_date": "2020-01-01",
  "end_date": "2023-12-31"
}
```

Response:

```json
{
  "status": "success",
  "data": {
    "task_id": "56b3d2a5-7ae3-40ad-bd48-bc2a2df94f2e",
    "status": "processing",
    "estimated_completion_time": "2025-09-03T10:20:30Z"
  },
  "meta": {
    "timestamp": "2025-09-03T10:15:30Z"
  },
  "error": null
}
```

Status check:

```http
GET /api/v1/tasks/56b3d2a5-7ae3-40ad-bd48-bc2a2df94f2e
Authorization: Bearer {token}
```

## WebSocket API

In addition to the REST API, a WebSocket interface is provided for real-time updates:

```
wss://api.fxml3.com/v1/ws
```

### Authentication

WebSocket connections require authentication via:

```
wss://api.fxml3.com/v1/ws?token={jwt_token}
```

### Channels

Clients can subscribe to specific channels:

```json
{
  "action": "subscribe",
  "channel": "backtest_updates",
  "params": {
    "backtest_id": "56b3d2a5-7ae3-40ad-bd48-bc2a2df94f2e"
  }
}
```

Available channels:
- `backtest_updates` - Real-time backtest progress and results
- `task_status` - Status updates for asynchronous tasks
- `wave_detection` - Real-time wave detection updates

## API Documentation

The API is documented using OpenAPI 3.0 specification, available at:

```
/api/v1/docs
```

Interactive documentation is provided via Swagger UI:

```
/api/v1/docs/ui
```

## Security Considerations

- All API communication uses HTTPS
- JWT tokens expire after 1 hour
- Refresh tokens are rotated on use
- API keys can be scoped to specific endpoints
- Sensitive data is redacted in logs
- Request origin validation via CORS
- WebSocket connections have maximum lifetime

## Implementation

The API will be implemented using:

- FastAPI for the REST endpoints and OpenAPI documentation
- Pydantic for request/response model validation
- JWT for token-based authentication
- Redis for rate limiting and caching
- WebSockets for real-time communication

## Deployment Architecture

The API will be deployed using:

```
┌────────────────┐      ┌────────────────┐      ┌────────────────┐
│                │      │                │      │                │
│  NGINX         │──────│  FastAPI       │──────│  FXML3 Core    │
│  Load Balancer │      │  API Server    │      │  Modules       │
│                │      │                │      │                │
└────────────────┘      └────────────────┘      └────────────────┘
                               │                        │
                        ┌──────┴───────┐         ┌──────┴───────┐
                        │              │         │              │
                        │  Redis       │         │  PostgreSQL  │
                        │  Cache       │         │  Database    │
                        │              │         │              │
                        └──────────────┘         └──────────────┘
```

- Containerized deployment with Docker
- Kubernetes for orchestration
- Horizontal scaling for API servers
- Vertical scaling for database