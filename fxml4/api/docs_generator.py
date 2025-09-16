"""Generate OpenAPI documentation with enhanced examples and descriptions."""

import json
from typing import Any, Dict, List

from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi


def custom_openapi(app: FastAPI) -> Dict[str, Any]:
    """Generate custom OpenAPI schema with enhanced documentation."""
    if app.openapi_schema:
        return app.openapi_schema

    openapi_schema = get_openapi(
        title="FXML4 Trading Platform API",
        version="2.0.0",
        description="""
# FXML4 API Documentation

The FXML4 API provides programmatic access to forex trading data, signals, and analytics.

## Features

- **Real-time market data** from multiple sources
- **AI-powered trading signals** using machine learning
- **Comprehensive backtesting** with Monte Carlo simulation
- **WebSocket support** for real-time updates
- **Batch operations** for efficient processing

## Authentication

The API uses Bearer token authentication. Include your API key in the Authorization header:

```
Authorization: Bearer YOUR_API_KEY
```

## Rate Limiting

| Tier | Requests/Hour | Burst | WebSocket Connections |
|------|---------------|-------|----------------------|
| Free | 100 | 10 | 1 |
| Basic | 1,000 | 100 | 5 |
| Pro | 10,000 | 1,000 | 20 |
| Enterprise | Unlimited | Unlimited | Unlimited |

## Versioning

This API uses URL-based versioning. The current version is v2.

### Version Negotiation

You can specify the API version in three ways:

1. **URL Path** (recommended): `/api/v2/endpoint`
2. **Accept Header**: `Accept: application/vnd.fxml4.v2+json`
3. **Query Parameter**: `?version=v2`

## Error Handling

All errors follow a consistent format:

```json
{
  "success": false,
  "message": "Human-readable error message",
  "error": "ErrorType",
  "details": [...],
  "help_url": "https://api.fxml4.com/docs/errors",
  "request_id": "req_123456"
}
```

## SDKs

Official SDKs are available for:

- **Python**: `pip install fxml4-api-client`
- **JavaScript/TypeScript**: `npm install @fxml4/api-client`
- **Go**: `go get github.com/fxml4/go-client`
- **Java**: Maven artifact `com.fxml4:api-client`

## Support

- Email: api-support@fxml4.com
- Documentation: https://api.fxml4.com/docs
- Status Page: https://status.fxml4.com
""",
        routes=app.routes,
        tags=[
            {
                "name": "authentication",
                "description": "Authentication endpoints for obtaining access tokens",
            },
            {"name": "data", "description": "Market data retrieval endpoints"},
            {"name": "signals", "description": "Trading signal generation endpoints"},
            {"name": "backtesting", "description": "Strategy backtesting and analysis"},
            {
                "name": "monitoring",
                "description": "System monitoring and health checks",
            },
            {
                "name": "risk-management",
                "description": "Risk management and position sizing",
            },
            {
                "name": "versioning",
                "description": "API version information and negotiation",
            },
        ],
        servers=[
            {"url": "https://api.fxml4.com", "description": "Production server"},
            {"url": "https://staging-api.fxml4.com", "description": "Staging server"},
            {"url": "http://localhost:8000", "description": "Local development server"},
        ],
    )

    # Add security schemes
    openapi_schema["components"]["securitySchemes"] = {
        "bearerAuth": {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "JWT",
            "description": "Enter your API key or JWT token",
        },
        "apiKey": {
            "type": "apiKey",
            "in": "header",
            "name": "X-API-Key",
            "description": "API key authentication (deprecated, use Bearer token)",
        },
    }

    # Add global security requirement
    openapi_schema["security"] = [{"bearerAuth": []}]

    # Add response headers
    openapi_schema["components"]["headers"] = {
        "X-RateLimit-Limit": {
            "description": "The number of allowed requests in the current period",
            "schema": {"type": "integer"},
        },
        "X-RateLimit-Remaining": {
            "description": "The number of remaining requests in the current period",
            "schema": {"type": "integer"},
        },
        "X-RateLimit-Reset": {
            "description": "The time at which the current rate limit window resets",
            "schema": {"type": "string", "format": "date-time"},
        },
        "X-API-Version": {
            "description": "The API version used for this request",
            "schema": {"type": "string"},
        },
        "X-Request-ID": {
            "description": "Unique identifier for this request",
            "schema": {"type": "string"},
        },
    }

    # Add examples to components
    openapi_schema["components"]["examples"] = {
        "DataRequestExample": {
            "summary": "Get hourly EURUSD data",
            "value": {
                "symbol": "EURUSD",
                "timeframe": "1h",
                "start_date": "2023-01-01T00:00:00Z",
                "end_date": "2023-12-31T23:59:59Z",
                "include_indicators": ["sma_20", "rsi_14"],
            },
        },
        "SignalRequestExample": {
            "summary": "Generate ML signals",
            "value": {
                "symbol": "EURUSD",
                "timeframe": "1h",
                "strategy": "ml_strategy",
                "confidence_threshold": 0.8,
                "parameters": {"model": "xgboost", "feature_set": "extended"},
            },
        },
        "BacktestRequestExample": {
            "summary": "Run comprehensive backtest",
            "value": {
                "symbol": "EURUSD",
                "timeframe": "1h",
                "strategy": "ml_strategy",
                "start_date": "2023-01-01T00:00:00Z",
                "end_date": "2023-12-31T23:59:59Z",
                "initial_capital": 10000,
                "monte_carlo": True,
                "parameters": {"risk_level": "medium"},
            },
        },
    }

    # Enhance endpoint documentation
    paths = openapi_schema.get("paths", {})

    # Add response examples
    for path, methods in paths.items():
        for method, operation in methods.items():
            if method in ["post", "get", "put", "delete"]:
                # Add response headers
                for response_code, response in operation.get("responses", {}).items():
                    if response_code.startswith("2"):
                        response["headers"] = {
                            "X-RateLimit-Limit": {
                                "$ref": "#/components/headers/X-RateLimit-Limit"
                            },
                            "X-RateLimit-Remaining": {
                                "$ref": "#/components/headers/X-RateLimit-Remaining"
                            },
                            "X-RateLimit-Reset": {
                                "$ref": "#/components/headers/X-RateLimit-Reset"
                            },
                            "X-API-Version": {
                                "$ref": "#/components/headers/X-API-Version"
                            },
                            "X-Request-ID": {
                                "$ref": "#/components/headers/X-Request-ID"
                            },
                        }

    # Add webhook definitions (for future use)
    openapi_schema["webhooks"] = {
        "signalAlert": {
            "post": {
                "requestBody": {
                    "description": "Signal alert notification",
                    "content": {
                        "application/json": {
                            "schema": {"$ref": "#/components/schemas/Signal"}
                        }
                    },
                },
                "responses": {"200": {"description": "Notification received"}},
            }
        }
    }

    app.openapi_schema = openapi_schema
    return app.openapi_schema


def generate_postman_collection(openapi_schema: Dict[str, Any]) -> Dict[str, Any]:
    """Generate Postman collection from OpenAPI schema."""
    collection = {
        "info": {
            "name": "FXML4 API",
            "description": openapi_schema.get("info", {}).get("description", ""),
            "schema": "https://schema.getpostman.com/json/collection/v2.1.0/collection.json",
        },
        "auth": {
            "type": "bearer",
            "bearer": [{"key": "token", "value": "{{api_key}}", "type": "string"}],
        },
        "variable": [
            {"key": "base_url", "value": "https://api.fxml4.com", "type": "string"},
            {"key": "api_key", "value": "your-api-key", "type": "string"},
        ],
        "item": [],
    }

    # Convert paths to Postman requests
    for path, methods in openapi_schema.get("paths", {}).items():
        folder = {
            "name": path.split("/")[3] if len(path.split("/")) > 3 else "root",
            "item": [],
        }

        for method, operation in methods.items():
            if method in ["get", "post", "put", "delete", "patch"]:
                request = {
                    "name": operation.get("summary", path),
                    "request": {
                        "method": method.upper(),
                        "header": [
                            {"key": "Content-Type", "value": "application/json"}
                        ],
                        "url": {
                            "raw": "{{base_url}}" + path,
                            "host": ["{{base_url}}"],
                            "path": path.split("/")[1:],
                        },
                    },
                }

                # Add request body if present
                if "requestBody" in operation:
                    content = operation["requestBody"].get("content", {})
                    if "application/json" in content:
                        schema = content["application/json"].get("schema", {})
                        if "example" in schema:
                            request["request"]["body"] = {
                                "mode": "raw",
                                "raw": json.dumps(schema["example"], indent=2),
                                "options": {"raw": {"language": "json"}},
                            }

                folder["item"].append(request)

        if folder["item"]:
            collection["item"].append(folder)

    return collection


def generate_asyncapi_spec() -> Dict[str, Any]:
    """Generate AsyncAPI specification for WebSocket endpoints."""
    return {
        "asyncapi": "2.6.0",
        "info": {
            "title": "FXML4 WebSocket API",
            "version": "2.0.0",
            "description": "Real-time trading data and signals via WebSocket",
        },
        "servers": {
            "production": {
                "url": "wss://api.fxml4.com",
                "protocol": "wss",
                "description": "Production WebSocket server",
            }
        },
        "channels": {
            "/api/v2/ws/signals/{symbol}": {
                "parameters": {
                    "symbol": {
                        "description": "Trading symbol (e.g., EURUSD)",
                        "schema": {"type": "string"},
                    }
                },
                "subscribe": {
                    "summary": "Receive real-time trading signals",
                    "message": {"$ref": "#/components/messages/SignalMessage"},
                },
            },
            "/api/v2/ws/data/{symbol}": {
                "parameters": {
                    "symbol": {
                        "description": "Trading symbol",
                        "schema": {"type": "string"},
                    }
                },
                "subscribe": {
                    "summary": "Receive real-time market data",
                    "message": {"$ref": "#/components/messages/DataMessage"},
                },
            },
        },
        "components": {
            "messages": {
                "SignalMessage": {
                    "payload": {
                        "type": "object",
                        "properties": {
                            "type": {"type": "string", "const": "signal"},
                            "channel": {"type": "string"},
                            "data": {"$ref": "#/components/schemas/Signal"},
                            "timestamp": {"type": "string", "format": "date-time"},
                            "sequence": {"type": "integer"},
                        },
                    }
                },
                "DataMessage": {
                    "payload": {
                        "type": "object",
                        "properties": {
                            "type": {"type": "string", "const": "data"},
                            "channel": {"type": "string"},
                            "data": {"$ref": "#/components/schemas/MarketData"},
                            "timestamp": {"type": "string", "format": "date-time"},
                            "sequence": {"type": "integer"},
                        },
                    }
                },
            },
            "schemas": {
                "Signal": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "string"},
                        "signal_type": {"type": "string"},
                        "confidence": {"type": "number"},
                        "price": {"type": "number"},
                    },
                },
                "MarketData": {
                    "type": "object",
                    "properties": {
                        "symbol": {"type": "string"},
                        "price": {"type": "number"},
                        "volume": {"type": "number"},
                        "timestamp": {"type": "string"},
                    },
                },
            },
        },
    }


if __name__ == "__main__":
    # This would be run to generate documentation files
    from fxml4.api.main import app

    # Generate OpenAPI spec
    openapi_spec = custom_openapi(app)
    with open("docs/api/openapi.json", "w") as f:
        json.dump(openapi_spec, f, indent=2)

    # Generate Postman collection
    postman_collection = generate_postman_collection(openapi_spec)
    with open("docs/api/postman_collection.json", "w") as f:
        json.dump(postman_collection, f, indent=2)

    # Generate AsyncAPI spec
    asyncapi_spec = generate_asyncapi_spec()
    with open("docs/api/asyncapi.json", "w") as f:
        json.dump(asyncapi_spec, f, indent=2)

    print("API documentation generated successfully!")
