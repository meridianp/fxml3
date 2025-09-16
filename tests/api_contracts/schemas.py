"""
API Contract Schemas for FXML4

This module defines comprehensive JSON schemas for validating API requests
and responses across all FXML4 endpoints. Schemas ensure data consistency,
validate input parameters, and maintain API contract integrity.

Schema Categories:
- Authentication & Authorization schemas
- Trading operation schemas
- Market data schemas
- Risk management schemas
- Machine Learning schemas
- Portfolio management schemas
- User management schemas
- System administration schemas
"""

from typing import Any, Dict

# Common schema components
COMMON_SCHEMAS = {
    "timestamp": {
        "type": "string",
        "format": "date-time",
        "description": "ISO 8601 timestamp",
    },
    "uuid": {
        "type": "string",
        "pattern": "^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
        "description": "UUID v4 format",
    },
    "currency_pair": {
        "type": "string",
        "pattern": "^[A-Z]{3}[A-Z]{3}$",
        "description": "Currency pair format (e.g., EURUSD)",
    },
    "decimal_price": {
        "type": "number",
        "multipleOf": 0.00001,
        "minimum": 0,
        "description": "Decimal price with 5 decimal places",
    },
    "positive_integer": {
        "type": "integer",
        "minimum": 1,
        "description": "Positive integer value",
    },
    "percentage": {
        "type": "number",
        "minimum": 0,
        "maximum": 100,
        "description": "Percentage value (0-100)",
    },
}

# Authentication & Authorization Schemas
AUTH_SCHEMAS = {
    "login_request": {
        "type": "object",
        "required": ["username", "password"],
        "properties": {
            "username": {
                "type": "string",
                "minLength": 3,
                "maxLength": 50,
                "pattern": "^[a-zA-Z0-9_.-]+$",
            },
            "password": {"type": "string", "minLength": 8, "maxLength": 128},
            "remember_me": {"type": "boolean", "default": False},
        },
        "additionalProperties": False,
    },
    "login_response": {
        "type": "object",
        "required": ["access_token", "token_type", "expires_in"],
        "properties": {
            "access_token": {"type": "string", "minLength": 20},
            "token_type": {"type": "string", "enum": ["bearer"]},
            "expires_in": {"type": "integer", "minimum": 300, "maximum": 86400},
            "refresh_token": {"type": "string", "minLength": 20},
            "scope": {"type": "string"},
        },
        "additionalProperties": False,
    },
    "user_profile_response": {
        "type": "object",
        "required": ["user_id", "username", "email", "created_at"],
        "properties": {
            "user_id": COMMON_SCHEMAS["uuid"],
            "username": {"type": "string", "minLength": 3, "maxLength": 50},
            "email": {"type": "string", "format": "email"},
            "first_name": {"type": "string", "maxLength": 50},
            "last_name": {"type": "string", "maxLength": 50},
            "role": {
                "type": "string",
                "enum": ["admin", "trader", "analyst", "viewer"],
            },
            "permissions": {"type": "array", "items": {"type": "string"}},
            "last_login": COMMON_SCHEMAS["timestamp"],
            "created_at": COMMON_SCHEMAS["timestamp"],
            "updated_at": COMMON_SCHEMAS["timestamp"],
        },
        "additionalProperties": False,
    },
}

# Trading Operation Schemas
TRADING_SCHEMAS = {
    "order_request": {
        "type": "object",
        "required": ["symbol", "side", "quantity", "order_type"],
        "properties": {
            "symbol": COMMON_SCHEMAS["currency_pair"],
            "side": {"type": "string", "enum": ["BUY", "SELL"]},
            "quantity": {
                "type": "integer",
                "minimum": 1000,
                "maximum": 10000000,
                "multipleOf": 1000,
            },
            "order_type": {
                "type": "string",
                "enum": ["MARKET", "LIMIT", "STOP", "STOP_LIMIT"],
            },
            "price": COMMON_SCHEMAS["decimal_price"],
            "stop_price": COMMON_SCHEMAS["decimal_price"],
            "time_in_force": {
                "type": "string",
                "enum": ["GTC", "IOC", "FOK", "DAY"],
                "default": "GTC",
            },
            "client_order_id": {"type": "string", "maxLength": 50},
        },
        "additionalProperties": False,
    },
    "order_response": {
        "type": "object",
        "required": ["order_id", "symbol", "side", "quantity", "status", "created_at"],
        "properties": {
            "order_id": COMMON_SCHEMAS["uuid"],
            "client_order_id": {"type": "string", "maxLength": 50},
            "symbol": COMMON_SCHEMAS["currency_pair"],
            "side": {"type": "string", "enum": ["BUY", "SELL"]},
            "quantity": COMMON_SCHEMAS["positive_integer"],
            "filled_quantity": {"type": "integer", "minimum": 0},
            "remaining_quantity": {"type": "integer", "minimum": 0},
            "order_type": {
                "type": "string",
                "enum": ["MARKET", "LIMIT", "STOP", "STOP_LIMIT"],
            },
            "price": COMMON_SCHEMAS["decimal_price"],
            "stop_price": COMMON_SCHEMAS["decimal_price"],
            "avg_fill_price": COMMON_SCHEMAS["decimal_price"],
            "status": {
                "type": "string",
                "enum": [
                    "PENDING",
                    "SUBMITTED",
                    "PARTIAL",
                    "FILLED",
                    "CANCELLED",
                    "REJECTED",
                ],
            },
            "time_in_force": {"type": "string", "enum": ["GTC", "IOC", "FOK", "DAY"]},
            "created_at": COMMON_SCHEMAS["timestamp"],
            "updated_at": COMMON_SCHEMAS["timestamp"],
            "expires_at": COMMON_SCHEMAS["timestamp"],
        },
        "additionalProperties": False,
    },
    "position_response": {
        "type": "object",
        "required": ["position_id", "symbol", "side", "quantity", "avg_price"],
        "properties": {
            "position_id": COMMON_SCHEMAS["uuid"],
            "symbol": COMMON_SCHEMAS["currency_pair"],
            "side": {"type": "string", "enum": ["LONG", "SHORT"]},
            "quantity": COMMON_SCHEMAS["positive_integer"],
            "avg_price": COMMON_SCHEMAS["decimal_price"],
            "current_price": COMMON_SCHEMAS["decimal_price"],
            "unrealized_pnl": {"type": "number"},
            "realized_pnl": {"type": "number"},
            "margin_used": {"type": "number", "minimum": 0},
            "opened_at": COMMON_SCHEMAS["timestamp"],
            "updated_at": COMMON_SCHEMAS["timestamp"],
        },
        "additionalProperties": False,
    },
    "account_balance_response": {
        "type": "object",
        "required": ["account_id", "currency", "balance", "available", "used"],
        "properties": {
            "account_id": COMMON_SCHEMAS["uuid"],
            "currency": {"type": "string", "pattern": "^[A-Z]{3}$"},
            "balance": {"type": "number"},
            "available": {"type": "number"},
            "used": {"type": "number", "minimum": 0},
            "equity": {"type": "number"},
            "margin": {"type": "number", "minimum": 0},
            "free_margin": {"type": "number"},
            "margin_level": COMMON_SCHEMAS["percentage"],
            "updated_at": COMMON_SCHEMAS["timestamp"],
        },
        "additionalProperties": False,
    },
}

# Market Data Schemas
MARKET_DATA_SCHEMAS = {
    "quote_response": {
        "type": "object",
        "required": ["symbol", "bid", "ask", "timestamp"],
        "properties": {
            "symbol": COMMON_SCHEMAS["currency_pair"],
            "bid": COMMON_SCHEMAS["decimal_price"],
            "ask": COMMON_SCHEMAS["decimal_price"],
            "last": COMMON_SCHEMAS["decimal_price"],
            "volume": {"type": "number", "minimum": 0},
            "high": COMMON_SCHEMAS["decimal_price"],
            "low": COMMON_SCHEMAS["decimal_price"],
            "open": COMMON_SCHEMAS["decimal_price"],
            "change": {"type": "number"},
            "change_percent": COMMON_SCHEMAS["percentage"],
            "timestamp": COMMON_SCHEMAS["timestamp"],
        },
        "additionalProperties": False,
    },
    "historical_bars_request": {
        "type": "object",
        "required": ["symbol", "timeframe", "start_date"],
        "properties": {
            "symbol": COMMON_SCHEMAS["currency_pair"],
            "timeframe": {
                "type": "string",
                "enum": ["1m", "5m", "15m", "30m", "1h", "4h", "1d", "1w", "1M"],
            },
            "start_date": COMMON_SCHEMAS["timestamp"],
            "end_date": COMMON_SCHEMAS["timestamp"],
            "limit": {"type": "integer", "minimum": 1, "maximum": 5000, "default": 100},
        },
        "additionalProperties": False,
    },
    "bar_data": {
        "type": "object",
        "required": ["timestamp", "open", "high", "low", "close", "volume"],
        "properties": {
            "timestamp": COMMON_SCHEMAS["timestamp"],
            "open": COMMON_SCHEMAS["decimal_price"],
            "high": COMMON_SCHEMAS["decimal_price"],
            "low": COMMON_SCHEMAS["decimal_price"],
            "close": COMMON_SCHEMAS["decimal_price"],
            "volume": {"type": "number", "minimum": 0},
            "tick_count": {"type": "integer", "minimum": 0},
        },
        "additionalProperties": False,
    },
    "historical_bars_response": {
        "type": "object",
        "required": ["symbol", "timeframe", "bars"],
        "properties": {
            "symbol": COMMON_SCHEMAS["currency_pair"],
            "timeframe": {
                "type": "string",
                "enum": ["1m", "5m", "15m", "30m", "1h", "4h", "1d", "1w", "1M"],
            },
            "bars": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": ["timestamp", "open", "high", "low", "close", "volume"],
                    "properties": {
                        "timestamp": COMMON_SCHEMAS["timestamp"],
                        "open": COMMON_SCHEMAS["decimal_price"],
                        "high": COMMON_SCHEMAS["decimal_price"],
                        "low": COMMON_SCHEMAS["decimal_price"],
                        "close": COMMON_SCHEMAS["decimal_price"],
                        "volume": {"type": "number", "minimum": 0},
                        "tick_count": {"type": "integer", "minimum": 0},
                    },
                    "additionalProperties": False,
                },
                "minItems": 0,
                "maxItems": 5000,
            },
            "count": {"type": "integer", "minimum": 0},
            "next_page_token": {"type": "string"},
        },
        "additionalProperties": False,
    },
}

# Risk Management Schemas
RISK_SCHEMAS = {
    "risk_limits_response": {
        "type": "object",
        "required": [
            "account_id",
            "max_position_size",
            "max_daily_loss",
            "max_leverage",
        ],
        "properties": {
            "account_id": COMMON_SCHEMAS["uuid"],
            "max_position_size": {"type": "number", "minimum": 0},
            "max_daily_loss": {"type": "number", "minimum": 0},
            "max_leverage": {"type": "number", "minimum": 1, "maximum": 500},
            "max_open_positions": {"type": "integer", "minimum": 1, "maximum": 100},
            "allowed_symbols": {
                "type": "array",
                "items": COMMON_SCHEMAS["currency_pair"],
            },
            "risk_score_threshold": {"type": "number", "minimum": 0, "maximum": 10},
            "var_limit": {"type": "number", "minimum": 0},
            "updated_at": COMMON_SCHEMAS["timestamp"],
        },
        "additionalProperties": False,
    },
    "var_calculation_response": {
        "type": "object",
        "required": [
            "portfolio_id",
            "var_1d",
            "var_5d",
            "confidence_level",
            "calculation_date",
        ],
        "properties": {
            "portfolio_id": COMMON_SCHEMAS["uuid"],
            "var_1d": {"type": "number"},
            "var_5d": {"type": "number"},
            "var_10d": {"type": "number"},
            "expected_shortfall": {"type": "number"},
            "confidence_level": COMMON_SCHEMAS["percentage"],
            "method": {
                "type": "string",
                "enum": ["historical", "parametric", "monte_carlo"],
            },
            "lookback_period": {"type": "integer", "minimum": 30, "maximum": 1000},
            "calculation_date": COMMON_SCHEMAS["timestamp"],
            "components": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "symbol": COMMON_SCHEMAS["currency_pair"],
                        "position_var": {"type": "number"},
                        "weight": COMMON_SCHEMAS["percentage"],
                    },
                },
            },
        },
        "additionalProperties": False,
    },
}

# Machine Learning Schemas
ML_SCHEMAS = {
    "prediction_request": {
        "type": "object",
        "required": ["symbol", "model_id", "features"],
        "properties": {
            "symbol": COMMON_SCHEMAS["currency_pair"],
            "model_id": COMMON_SCHEMAS["uuid"],
            "features": {
                "type": "object",
                "properties": {
                    "technical_indicators": {
                        "type": "object",
                        "additionalProperties": {"type": "number"},
                    },
                    "market_data": {
                        "type": "object",
                        "properties": {
                            "current_price": COMMON_SCHEMAS["decimal_price"],
                            "volume": {"type": "number", "minimum": 0},
                            "volatility": {"type": "number", "minimum": 0},
                        },
                    },
                    "fundamental_data": {
                        "type": "object",
                        "additionalProperties": {"type": "number"},
                    },
                },
            },
            "prediction_horizon": {
                "type": "string",
                "enum": ["1h", "4h", "1d", "1w"],
                "default": "1h",
            },
        },
        "additionalProperties": False,
    },
    "prediction_response": {
        "type": "object",
        "required": [
            "prediction_id",
            "symbol",
            "model_id",
            "prediction",
            "confidence",
            "created_at",
        ],
        "properties": {
            "prediction_id": COMMON_SCHEMAS["uuid"],
            "symbol": COMMON_SCHEMAS["currency_pair"],
            "model_id": COMMON_SCHEMAS["uuid"],
            "prediction": {
                "type": "object",
                "required": ["direction", "price_target", "probability"],
                "properties": {
                    "direction": {"type": "string", "enum": ["BUY", "SELL", "HOLD"]},
                    "price_target": COMMON_SCHEMAS["decimal_price"],
                    "probability": {"type": "number", "minimum": 0, "maximum": 1},
                    "expected_return": {"type": "number"},
                    "risk_score": {"type": "number", "minimum": 0, "maximum": 10},
                },
            },
            "confidence": {"type": "number", "minimum": 0, "maximum": 1},
            "model_version": {"type": "string"},
            "feature_importance": {
                "type": "object",
                "additionalProperties": {"type": "number", "minimum": 0, "maximum": 1},
            },
            "created_at": COMMON_SCHEMAS["timestamp"],
            "expires_at": COMMON_SCHEMAS["timestamp"],
        },
        "additionalProperties": False,
    },
    "backtest_request": {
        "type": "object",
        "required": ["strategy_id", "start_date", "end_date", "initial_capital"],
        "properties": {
            "strategy_id": COMMON_SCHEMAS["uuid"],
            "start_date": COMMON_SCHEMAS["timestamp"],
            "end_date": COMMON_SCHEMAS["timestamp"],
            "initial_capital": {"type": "number", "minimum": 1000},
            "symbols": {
                "type": "array",
                "items": COMMON_SCHEMAS["currency_pair"],
                "minItems": 1,
                "maxItems": 10,
            },
            "commission": {"type": "number", "minimum": 0, "default": 0.0001},
            "slippage": {"type": "number", "minimum": 0, "default": 0.0001},
        },
        "additionalProperties": False,
    },
}

# System Administration Schemas
ADMIN_SCHEMAS = {
    "health_check_response": {
        "type": "object",
        "required": ["status", "timestamp"],
        "properties": {
            "status": {"type": "string", "enum": ["healthy", "degraded", "unhealthy"]},
            "timestamp": COMMON_SCHEMAS["timestamp"],
            "version": {"type": "string", "pattern": "^\\d+\\.\\d+\\.\\d+$"},
            "uptime_seconds": {"type": "integer", "minimum": 0},
            "services": {
                "type": "object",
                "additionalProperties": {
                    "type": "object",
                    "properties": {
                        "status": {
                            "type": "string",
                            "enum": ["healthy", "degraded", "unhealthy"],
                        },
                        "response_time_ms": {"type": "number", "minimum": 0},
                        "last_check": COMMON_SCHEMAS["timestamp"],
                    },
                },
            },
            "metrics": {
                "type": "object",
                "properties": {
                    "cpu_usage_percent": COMMON_SCHEMAS["percentage"],
                    "memory_usage_percent": COMMON_SCHEMAS["percentage"],
                    "disk_usage_percent": COMMON_SCHEMAS["percentage"],
                    "active_connections": {"type": "integer", "minimum": 0},
                    "requests_per_minute": {"type": "number", "minimum": 0},
                },
            },
        },
        "additionalProperties": False,
    },
    "system_metrics_response": {
        "type": "object",
        "required": ["timestamp", "metrics"],
        "properties": {
            "timestamp": COMMON_SCHEMAS["timestamp"],
            "metrics": {
                "type": "object",
                "required": ["performance", "usage", "errors"],
                "properties": {
                    "performance": {
                        "type": "object",
                        "properties": {
                            "avg_response_time_ms": {"type": "number", "minimum": 0},
                            "p95_response_time_ms": {"type": "number", "minimum": 0},
                            "p99_response_time_ms": {"type": "number", "minimum": 0},
                            "requests_per_second": {"type": "number", "minimum": 0},
                            "throughput_mbps": {"type": "number", "minimum": 0},
                        },
                    },
                    "usage": {
                        "type": "object",
                        "properties": {
                            "cpu_usage_percent": COMMON_SCHEMAS["percentage"],
                            "memory_usage_mb": {"type": "number", "minimum": 0},
                            "memory_usage_percent": COMMON_SCHEMAS["percentage"],
                            "disk_usage_gb": {"type": "number", "minimum": 0},
                            "network_io_mbps": {"type": "number", "minimum": 0},
                        },
                    },
                    "errors": {
                        "type": "object",
                        "properties": {
                            "error_rate_percent": COMMON_SCHEMAS["percentage"],
                            "total_errors": {"type": "integer", "minimum": 0},
                            "error_types": {
                                "type": "object",
                                "additionalProperties": {
                                    "type": "integer",
                                    "minimum": 0,
                                },
                            },
                        },
                    },
                },
            },
        },
        "additionalProperties": False,
    },
}

# Error Response Schemas
ERROR_SCHEMAS = {
    "error_response": {
        "type": "object",
        "required": ["error", "message", "timestamp"],
        "properties": {
            "error": {
                "type": "string",
                "enum": [
                    "AUTHENTICATION_ERROR",
                    "AUTHORIZATION_ERROR",
                    "VALIDATION_ERROR",
                    "NOT_FOUND",
                    "CONFLICT",
                    "RATE_LIMIT_EXCEEDED",
                    "INTERNAL_SERVER_ERROR",
                    "SERVICE_UNAVAILABLE",
                    "INSUFFICIENT_FUNDS",
                    "INVALID_ORDER",
                    "MARKET_CLOSED",
                ],
            },
            "message": {"type": "string", "maxLength": 500},
            "details": {"type": "object", "additionalProperties": True},
            "error_code": {"type": "integer", "minimum": 1000, "maximum": 9999},
            "request_id": COMMON_SCHEMAS["uuid"],
            "timestamp": COMMON_SCHEMAS["timestamp"],
        },
        "additionalProperties": False,
    },
    "validation_error_response": {
        "type": "object",
        "required": ["error", "message", "validation_errors", "timestamp"],
        "properties": {
            "error": {"type": "string", "const": "VALIDATION_ERROR"},
            "message": {"type": "string"},
            "validation_errors": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": ["field", "message"],
                    "properties": {
                        "field": {"type": "string"},
                        "message": {"type": "string"},
                        "value": {},
                        "code": {"type": "string"},
                    },
                },
            },
            "request_id": COMMON_SCHEMAS["uuid"],
            "timestamp": COMMON_SCHEMAS["timestamp"],
        },
        "additionalProperties": False,
    },
}

# Compile all schemas
ALL_SCHEMAS = {
    "common": COMMON_SCHEMAS,
    "auth": AUTH_SCHEMAS,
    "trading": TRADING_SCHEMAS,
    "market_data": MARKET_DATA_SCHEMAS,
    "risk": RISK_SCHEMAS,
    "ml": ML_SCHEMAS,
    "admin": ADMIN_SCHEMAS,
    "errors": ERROR_SCHEMAS,
}


def get_schema(category: str, schema_name: str) -> Dict[str, Any]:
    """Get a specific schema by category and name."""
    return ALL_SCHEMAS.get(category, {}).get(schema_name, {})


def get_request_schema(endpoint_path: str, method: str) -> Dict[str, Any]:
    """Get request schema for a specific endpoint."""
    # Map endpoints to schemas
    endpoint_schema_map = {
        "POST:/auth/login": get_schema("auth", "login_request"),
        "POST:/trading/orders": get_schema("trading", "order_request"),
        "GET:/market-data/bars": get_schema("market_data", "historical_bars_request"),
        "POST:/ml/predictions": get_schema("ml", "prediction_request"),
        "POST:/ml/backtests": get_schema("ml", "backtest_request"),
    }

    key = f"{method}:{endpoint_path}"
    return endpoint_schema_map.get(key, {})


def get_response_schema(
    endpoint_path: str, method: str, status_code: int = 200
) -> Dict[str, Any]:
    """Get response schema for a specific endpoint and status code."""
    # Map endpoints to response schemas
    endpoint_schema_map = {
        "POST:/auth/login:200": get_schema("auth", "login_response"),
        "GET:/auth/profile:200": get_schema("auth", "user_profile_response"),
        "POST:/trading/orders:201": get_schema("trading", "order_response"),
        "GET:/trading/orders:200": {
            "type": "object",
            "properties": {
                "orders": {
                    "type": "array",
                    "items": get_schema("trading", "order_response"),
                },
                "total": COMMON_SCHEMAS["positive_integer"],
                "page": COMMON_SCHEMAS["positive_integer"],
                "per_page": COMMON_SCHEMAS["positive_integer"],
            },
        },
        "GET:/trading/positions:200": {
            "type": "object",
            "properties": {
                "positions": {
                    "type": "array",
                    "items": get_schema("trading", "position_response"),
                },
                "total": COMMON_SCHEMAS["positive_integer"],
            },
        },
        "GET:/trading/balance:200": get_schema("trading", "account_balance_response"),
        "GET:/market-data/quotes:200": get_schema("market_data", "quote_response"),
        "GET:/market-data/bars:200": get_schema(
            "market_data", "historical_bars_response"
        ),
        "GET:/risk/limits:200": get_schema("risk", "risk_limits_response"),
        "GET:/risk/var:200": get_schema("risk", "var_calculation_response"),
        "POST:/ml/predictions:200": get_schema("ml", "prediction_response"),
        "GET:/admin/health:200": get_schema("admin", "health_check_response"),
        "GET:/admin/metrics:200": get_schema("admin", "system_metrics_response"),
    }

    # Error response schemas for different status codes
    error_schemas = {
        400: get_schema("errors", "validation_error_response"),
        401: get_schema("errors", "error_response"),
        403: get_schema("errors", "error_response"),
        404: get_schema("errors", "error_response"),
        409: get_schema("errors", "error_response"),
        429: get_schema("errors", "error_response"),
        500: get_schema("errors", "error_response"),
        503: get_schema("errors", "error_response"),
    }

    key = f"{method}:{endpoint_path}:{status_code}"

    # Return specific schema if available
    if key in endpoint_schema_map:
        return endpoint_schema_map[key]

    # Return error schema for error status codes
    if status_code in error_schemas:
        return error_schemas[status_code]

    # Default empty schema
    return {}


def validate_schema_completeness() -> Dict[str, Any]:
    """Validate that schemas are complete and well-formed."""
    validation_results = {"total_schemas": 0, "categories": {}, "issues": []}

    for category, schemas in ALL_SCHEMAS.items():
        category_info = {"schema_count": len(schemas), "schemas": list(schemas.keys())}
        validation_results["categories"][category] = category_info
        validation_results["total_schemas"] += len(schemas)

        # Validate each schema has required properties
        for schema_name, schema in schemas.items():
            if not isinstance(schema, dict):
                validation_results["issues"].append(
                    f"{category}.{schema_name}: Not a valid schema object"
                )
            elif "type" not in schema and schema_name not in [
                "timestamp",
                "uuid",
                "currency_pair",
                "decimal_price",
                "positive_integer",
                "percentage",
            ]:
                validation_results["issues"].append(
                    f"{category}.{schema_name}: Missing 'type' property"
                )

    return validation_results


if __name__ == "__main__":
    # Validate schema completeness
    results = validate_schema_completeness()

    print("FXML4 API Contract Schemas Validation")
    print("=" * 50)
    print(f"Total Schemas: {results['total_schemas']}")
    print(f"Categories: {len(results['categories'])}")

    for category, info in results["categories"].items():
        print(f"  {category}: {info['schema_count']} schemas")

    if results["issues"]:
        print(f"\nIssues Found: {len(results['issues'])}")
        for issue in results["issues"]:
            print(f"  - {issue}")
    else:
        print("\n✅ All schemas are valid!")

    # Test specific schema retrieval
    print(f"\nSample Schema Retrieval:")
    login_schema = get_request_schema("/auth/login", "POST")
    print(f"Login request schema: {bool(login_schema)}")

    health_schema = get_response_schema("/admin/health", "GET", 200)
    print(f"Health response schema: {bool(health_schema)}")

    error_schema = get_response_schema("/any/endpoint", "GET", 404)
    print(f"404 error schema: {bool(error_schema)}")
