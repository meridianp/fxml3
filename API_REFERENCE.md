# FXML4 API Reference v1.0.0

**Complete API Reference for Enterprise Trading Platform**

This comprehensive API reference covers all endpoints, components, and integrations available in FXML4 v1.0.0, including the advanced features developed across 3 TDD sprints.

---

## 🏗️ Architecture Overview

FXML4 provides a comprehensive REST API with WebSocket streaming, built on FastAPI with enterprise-grade security and performance optimizations.

### Base URLs

| Environment | Base URL | WebSocket URL |
|-------------|----------|---------------|
| Development | `http://localhost:8000` | `ws://localhost:8000/ws` |
| Production | `https://api.yourdomain.com` | `wss://api.yourdomain.com/ws` |
| Docker | `http://localhost:8000` | `ws://localhost:8000/ws` |

### API Versioning

All API endpoints are versioned with the `/api/v1` prefix. The current stable version is **v1.0.0**.

---

## 🔐 Authentication & Security

### JWT Authentication

FXML4 uses JWT (JSON Web Token) with refresh token rotation for secure authentication.

#### Get Access Token

**Endpoint:** `POST /api/v1/auth/token`

**Request:**
```http
POST /api/v1/auth/token HTTP/1.1
Content-Type: application/x-www-form-urlencoded

username=your_username&password=your_password
```

**Response:**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "expires_in": 3600,
  "scope": "trading read write"
}
```

**Status Codes:**
- `200`: Authentication successful
- `401`: Invalid credentials
- `429`: Too many login attempts

#### Refresh Token

**Endpoint:** `POST /api/v1/auth/refresh`

**Headers:**
```http
Authorization: Bearer <refresh_token>
```

**Response:**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "expires_in": 3600
}
```

#### Two-Factor Authentication

**Endpoint:** `POST /api/v1/auth/2fa/verify`

**Request:**
```json
{
  "token": "123456",
  "temp_token": "temporary_token_from_login"
}
```

**Response:**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "expires_in": 3600
}
```

### Using Authentication

Include the access token in the Authorization header for all authenticated endpoints:

```http
Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

---

## 📊 System Endpoints

### Health Check

**Endpoint:** `GET /health`

**Response:**
```json
{
  "status": "healthy",
  "timestamp": "2025-09-25T10:00:00Z",
  "version": "1.0.0",
  "uptime": "72h15m30s"
}
```

### System Status

**Endpoint:** `GET /api/v1/system/status`

**Authentication:** Required

**Response:**
```json
{
  "status": "operational",
  "services": {
    "database": {
      "status": "healthy",
      "latency_ms": 2.3,
      "connections": {
        "active": 15,
        "idle": 5,
        "total": 20
      }
    },
    "redis": {
      "status": "healthy",
      "memory_usage": "234MB",
      "connections": 12
    },
    "rabbitmq": {
      "status": "healthy",
      "queue_count": 5,
      "message_rate": 1250
    },
    "brokers": {
      "interactive_brokers": {
        "status": "connected",
        "latency_ms": 45.2
      },
      "fxcm": {
        "status": "connected",
        "latency_ms": 38.7
      }
    }
  },
  "performance_metrics": {
    "api_requests_per_second": 245,
    "websocket_connections": 18,
    "risk_calculations_per_second": 2700000,
    "fix_messages_per_second": 2300000,
    "compliance_checks_per_second": 2300000
  }
}
```

### Performance Metrics

**Endpoint:** `GET /api/v1/system/metrics`

**Authentication:** Required

**Query Parameters:**
- `timeframe`: `1h`, `24h`, `7d`, `30d` (default: `24h`)
- `include_detailed`: `true`/`false` (default: `false`)

**Response:**
```json
{
  "timeframe": "24h",
  "summary": {
    "uptime": "99.98%",
    "avg_response_time_ms": 28.5,
    "error_rate": 0.02,
    "throughput_rps": 245.7
  },
  "detailed_metrics": {
    "api_performance": {
      "p50_latency_ms": 18.2,
      "p95_latency_ms": 45.8,
      "p99_latency_ms": 89.3,
      "request_count": 21168000
    },
    "trading_performance": {
      "signals_generated": 1245,
      "orders_executed": 892,
      "position_updates": 15678,
      "risk_calculations": 233280000000
    },
    "data_processing": {
      "market_data_points": 5.2e6,
      "feature_extraction_avg_ms": 63,
      "ml_predictions": 3456
    }
  }
}
```

---

## 📈 Market Data API

### Enhanced Real-Time Market Data (WebSocket)

**Connection:** `wss://api.yourdomain.com/ws/market-data`

**Enhanced Features:**
- 10,000+ concurrent connections support
- Sub-millisecond message broadcasting
- Binary compression (ZLIB, GZIP, MessagePack)
- Priority-based message queuing
- Automatic failover and reconnection

**Authentication:** Include JWT token in connection headers

**Advanced Subscription:**
```json
{
  "action": "subscribe",
  "symbols": ["EURUSD", "GBPUSD", "USDJPY"],
  "timeframes": ["1m", "5m", "15m", "1h"],
  "data_types": ["tick", "ohlcv", "spread", "volume"],
  "providers": ["alpha_vantage", "polygon"],
  "compression": "zlib",
  "priority": "high",
  "quality_threshold": 0.95
}
```

**High-Performance Market Data Stream:**
```json
{
  "type": "market_data",
  "symbol": "EURUSD",
  "timestamp": "2025-09-25T10:00:00Z",
  "timeframe": "1m",
  "provider": "polygon",
  "quality_score": 0.98,
  "latency_ms": 0.8,
  "data": {
    "open": 1.0850,
    "high": 1.0865,
    "low": 1.0848,
    "close": 1.0862,
    "volume": 125000,
    "tick_count": 1247,
    "vwap": 1.0856,
    "spread": 0.8,
    "bid": 1.0861,
    "ask": 1.0862
  },
  "metadata": {
    "compression_ratio": 0.3,
    "validation_passed": true,
    "anomaly_score": 0.02
  }
}
```

### Historical Market Data

**Endpoint:** `GET /api/v1/data/historical/{symbol}`

**Authentication:** Required

**Path Parameters:**
- `symbol`: Currency pair (e.g., `EURUSD`, `GBPUSD`)

**Query Parameters:**
- `timeframe`: `1m`, `5m`, `15m`, `30m`, `1h`, `4h`, `1d`, `1w`
- `start_date`: ISO format date (e.g., `2025-01-01T00:00:00Z`)
- `end_date`: ISO format date
- `limit`: Maximum records (default: 1000, max: 10000)
- `include_volume`: `true`/`false` (default: `true`)

**Response:**
```json
{
  "symbol": "EURUSD",
  "timeframe": "1h",
  "start_date": "2025-01-01T00:00:00Z",
  "end_date": "2025-01-02T00:00:00Z",
  "count": 24,
  "data": [
    {
      "timestamp": "2025-01-01T00:00:00Z",
      "open": 1.0850,
      "high": 1.0865,
      "low": 1.0848,
      "close": 1.0862,
      "volume": 125000,
      "spread": 0.8
    }
  ],
  "source": "polygon",
  "cached": false
}
```

### Multi-Provider Data Feed Management

**Endpoint:** `GET /api/v1/data/providers`

**Authentication:** Required

**Response:**
```json
{
  "providers": [
    {
      "name": "alpha_vantage",
      "status": "active",
      "capabilities": ["forex", "stocks", "economics", "commodities"],
      "rate_limit": "5_requests_per_minute",
      "latency_ms": 145.2,
      "data_quality": 0.96,
      "cost_per_request": 0.001
    },
    {
      "name": "polygon",
      "status": "active",
      "capabilities": ["forex", "stocks", "crypto", "options"],
      "rate_limit": "unlimited",
      "latency_ms": 38.7,
      "data_quality": 0.98,
      "cost_per_request": 0.002
    }
  ],
  "failover_configuration": {
    "primary_provider": "polygon",
    "fallback_providers": ["alpha_vantage"],
    "automatic_failover": true,
    "failover_threshold_ms": 1000
  }
}
```

**Endpoint:** `POST /api/v1/data/providers/configure`

**Authentication:** Required (Admin permissions)

**Request:**
```json
{
  "provider": "alpha_vantage",
  "config": {
    "api_key": "YOUR_API_KEY",
    "enabled": true,
    "priority": 2,
    "rate_limit_per_minute": 75,
    "data_types": ["forex", "economics"],
    "quality_threshold": 0.95
  }
}
```

**Response:**
```json
{
  "provider": "alpha_vantage",
  "status": "configured",
  "connection_test": "passed",
  "estimated_cost_per_day": 12.50
}
```

### Real-Time Data Quality Monitoring

**Endpoint:** `GET /api/v1/data/quality`

**Authentication:** Required

**Query Parameters:**
- `provider`: Filter by data provider
- `symbol`: Filter by currency pair
- `timeframe`: `1h`, `24h`, `7d`

**Response:**
```json
{
  "quality_summary": {
    "overall_score": 0.97,
    "data_completeness": 0.995,
    "anomaly_rate": 0.005,
    "validation_pass_rate": 0.999
  },
  "provider_performance": {
    "polygon": {
      "quality_score": 0.98,
      "latency_ms": 38.7,
      "uptime": 0.9998,
      "cost_efficiency": 0.85
    },
    "alpha_vantage": {
      "quality_score": 0.96,
      "latency_ms": 145.2,
      "uptime": 0.9995,
      "cost_efficiency": 0.92
    }
  },
  "quality_metrics": {
    "price_accuracy": 0.9999,
    "volume_accuracy": 0.9950,
    "timestamp_accuracy": 1.0000,
    "data_freshness": 0.9875
  }
}
```

### Advanced Market Data Validation

**Endpoint:** `POST /api/v1/data/validate`

**Authentication:** Required

**Request:**
```json
{
  "symbol": "EURUSD",
  "provider": "polygon",
  "validation_level": "comprehensive",
  "data": [
    {
      "timestamp": "2025-09-25T10:00:00Z",
      "open": 1.0850,
      "high": 1.0865,
      "low": 1.0848,
      "close": 1.0862,
      "volume": 125000
    }
  ],
  "validation_rules": {
    "price_bounds": {
      "min_price": 0.8000,
      "max_price": 1.5000
    },
    "volume_bounds": {
      "min_volume": 1000,
      "max_volume": 10000000
    },
    "anomaly_detection": true,
    "cross_provider_validation": true
  }
}
```

**Response:**
```json
{
  "valid": true,
  "validation_score": 0.98,
  "validation_results": {
    "price_validation": "passed",
    "volume_validation": "passed",
    "sequence_validation": "passed",
    "anomaly_detection": "passed",
    "cross_provider_validation": "passed",
    "temporal_consistency": "passed"
  },
  "quality_metrics": {
    "data_completeness": 1.0,
    "accuracy_score": 0.98,
    "consistency_score": 0.97
  },
  "issues": [],
  "corrections_applied": [],
  "provider_comparison": {
    "polygon_price": 1.0862,
    "alpha_vantage_price": 1.0861,
    "price_spread": 0.0001,
    "consensus_confidence": 0.95
  }
}
```

---

## 🤖 ML & Signal Generation API

### Signal Generation Pipeline

**Endpoint:** `POST /api/v1/ml/signals/generate`

**Authentication:** Required

**Request:**
```json
{
  "symbol": "EURUSD",
  "timeframe": "1h",
  "strategy_config": {
    "indicators": ["sma", "ema", "rsi", "macd", "bollinger"],
    "lookback_periods": [14, 20, 50, 200],
    "confidence_threshold": 0.7,
    "include_elliott_wave": true,
    "include_regime_features": true
  },
  "data_range": {
    "start_date": "2025-01-01T00:00:00Z",
    "end_date": "2025-09-25T10:00:00Z"
  }
}
```

**Response:**
```json
{
  "signal_id": "SIG_20250925_100000_EURUSD",
  "symbol": "EURUSD",
  "timeframe": "1h",
  "generated_at": "2025-09-25T10:00:00Z",
  "processing_time_ms": 63,
  "signals": [
    {
      "timestamp": "2025-09-25T09:00:00Z",
      "signal_type": "entry_long",
      "confidence": 0.85,
      "price": 1.0862,
      "indicators": {
        "rsi": 35.2,
        "macd": 0.0015,
        "sma_20": 1.0845,
        "ema_50": 1.0851,
        "bollinger_position": -0.3
      },
      "elliott_wave": {
        "current_wave": "wave_3",
        "wave_confidence": 0.78
      },
      "market_regime": "trending",
      "risk_score": 0.25
    }
  ],
  "feature_extraction_stats": {
    "features_computed": 74,
    "processing_time_ms": 45,
    "data_points_processed": 1000
  }
}
```

### Feature Engineering

**Endpoint:** `POST /api/v1/ml/features/extract`

**Authentication:** Required

**Request:**
```json
{
  "symbol": "EURUSD",
  "data": [
    {
      "timestamp": "2025-09-25T10:00:00Z",
      "open": 1.0850,
      "high": 1.0865,
      "low": 1.0848,
      "close": 1.0862,
      "volume": 125000
    }
  ],
  "feature_config": {
    "technical_indicators": true,
    "elliott_wave_features": true,
    "regime_features": true,
    "sentiment_features": false
  }
}
```

**Response:**
```json
{
  "feature_extraction_id": "FE_20250925_100000",
  "processing_time_ms": 63,
  "features": {
    "technical_indicators": {
      "sma_20": 1.0845,
      "ema_50": 1.0851,
      "rsi_14": 35.2,
      "macd": 0.0015,
      "bollinger_upper": 1.0890,
      "bollinger_lower": 1.0810,
      "atr_14": 0.0025
    },
    "elliott_wave_features": {
      "wave_pattern": "impulse",
      "current_wave": "wave_3",
      "wave_confidence": 0.78,
      "fibonacci_level": 0.618
    },
    "regime_features": {
      "market_regime": "trending",
      "volatility_regime": "normal",
      "correlation_regime": "stable"
    }
  },
  "statistics": {
    "features_extracted": 74,
    "computation_time_ms": 45,
    "data_quality_score": 0.95
  }
}
```

### Signal Aggregation

**Endpoint:** `POST /api/v1/ml/signals/aggregate`

**Authentication:** Required

**Request:**
```json
{
  "signals": [
    {
      "source": "ml_model_1",
      "signal_type": "entry_long",
      "confidence": 0.75,
      "weight": 0.4
    },
    {
      "source": "elliott_wave",
      "signal_type": "entry_long",
      "confidence": 0.82,
      "weight": 0.3
    },
    {
      "source": "technical_indicators",
      "signal_type": "entry_long",
      "confidence": 0.68,
      "weight": 0.3
    }
  ],
  "aggregation_method": "weighted_voting",
  "minimum_consensus": 0.7
}
```

**Response:**
```json
{
  "aggregated_signal": {
    "signal_type": "entry_long",
    "confidence": 0.746,
    "consensus": 1.0,
    "recommendation": "execute"
  },
  "contributing_signals": {
    "total_signals": 3,
    "agreeing_signals": 3,
    "weighted_confidence": 0.746
  },
  "risk_assessment": {
    "signal_strength": "strong",
    "risk_level": "moderate",
    "recommended_position_size": 0.02
  }
}
```

---

## ⚖️ Risk Management API

### Position Sizing

**Endpoint:** `POST /api/v1/risk/position-sizing`

**Authentication:** Required

**Request:**
```json
{
  "account_balance": 100000.0,
  "symbol": "EURUSD",
  "entry_price": 1.0862,
  "stop_loss": 1.0812,
  "risk_percentage": 0.02,
  "leverage": 10,
  "correlation_adjustment": true,
  "current_positions": [
    {
      "symbol": "GBPUSD",
      "size": 50000,
      "correlation": 0.74
    }
  ]
}
```

**Response:**
```json
{
  "recommended_position_size": 37500,
  "position_value": 40762.50,
  "margin_required": 4076.25,
  "risk_amount": 2000.0,
  "correlation_adjustment": {
    "original_size": 50000,
    "adjusted_size": 37500,
    "adjustment_factor": 0.75,
    "reason": "portfolio_correlation_0.74"
  },
  "risk_metrics": {
    "risk_per_pip": 3.75,
    "stop_distance_pips": 50,
    "risk_reward_ratio": 2.0
  },
  "portfolio_impact": {
    "total_risk_exposure": 0.035,
    "correlation_exposure": 0.018,
    "diversification_score": 0.82
  }
}
```

### Stop-Loss Management

**Endpoint:** `POST /api/v1/risk/stop-loss`

**Authentication:** Required

**Request:**
```json
{
  "position_id": "POS_20250925_100000",
  "symbol": "EURUSD",
  "entry_price": 1.0862,
  "current_price": 1.0885,
  "position_size": 50000,
  "stop_loss_type": "trailing_atr",
  "stop_loss_config": {
    "atr_multiplier": 2.0,
    "min_distance_pips": 20,
    "trail_frequency": "1m"
  }
}
```

**Response:**
```json
{
  "stop_loss_price": 1.0835,
  "stop_loss_type": "trailing_atr",
  "distance_pips": 50,
  "risk_amount": 1375.0,
  "trailing_config": {
    "atr_14": 0.0025,
    "trail_distance": 0.0050,
    "last_updated": "2025-09-25T10:00:00Z"
  },
  "adjustments": [
    {
      "timestamp": "2025-09-25T09:30:00Z",
      "old_stop": 1.0820,
      "new_stop": 1.0835,
      "reason": "price_advancement",
      "trail_distance": 0.0050
    }
  ],
  "next_adjustment_trigger": 1.0905
}
```

### Portfolio Risk Assessment

**Endpoint:** `GET /api/v1/risk/portfolio-assessment`

**Authentication:** Required

**Query Parameters:**
- `include_correlations`: `true`/`false`
- `risk_horizon`: `1d`, `1w`, `1m`

**Response:**
```json
{
  "portfolio_summary": {
    "total_value": 100000.0,
    "total_exposure": 75000.0,
    "available_margin": 25000.0,
    "risk_utilization": 0.45
  },
  "positions": [
    {
      "position_id": "POS_001",
      "symbol": "EURUSD",
      "size": 50000,
      "unrealized_pnl": 1150.0,
      "risk_amount": 2000.0,
      "days_held": 3
    }
  ],
  "risk_metrics": {
    "value_at_risk_95": 4500.0,
    "expected_shortfall": 6200.0,
    "maximum_drawdown": 0.08,
    "sharpe_ratio": 1.45,
    "sortino_ratio": 2.10
  },
  "correlations": {
    "EURUSD_GBPUSD": 0.74,
    "EURUSD_USDJPY": -0.31,
    "GBPUSD_USDJPY": -0.45
  },
  "diversification_score": 0.82,
  "risk_recommendations": [
    {
      "type": "reduce_correlation",
      "message": "Consider reducing GBPUSD position due to high correlation with EURUSD",
      "priority": "medium"
    }
  ]
}
```

### Real-Time Risk Monitoring

**WebSocket Endpoint:** `wss://api.yourdomain.com/ws/risk-monitoring`

**Subscribe to Risk Updates:**
```json
{
  "action": "subscribe",
  "risk_types": ["position_risk", "portfolio_risk", "margin_risk"],
  "alert_levels": ["warning", "critical"]
}
```

**Risk Alert Stream:**
```json
{
  "type": "risk_alert",
  "level": "warning",
  "timestamp": "2025-09-25T10:00:00Z",
  "alert": {
    "risk_type": "position_risk",
    "position_id": "POS_001",
    "symbol": "EURUSD",
    "message": "Position approaching stop-loss level",
    "current_price": 1.0825,
    "stop_loss": 1.0820,
    "risk_amount": 2000.0
  },
  "recommended_actions": [
    {
      "action": "adjust_stop_loss",
      "priority": "medium"
    }
  ]
}
```

---

## 🏛️ Compliance & Regulatory API

### Compliance Monitoring

**Endpoint:** `GET /api/v1/compliance/status`

**Authentication:** Required (Admin permissions)

**Query Parameters:**
- `framework`: `mifid2`, `emir`, `gdpr`, `soc2`, `pci_dss`, `dodd_frank`, `all`
- `timeframe`: `24h`, `7d`, `30d`

**Response:**
```json
{
  "compliance_status": "compliant",
  "last_check": "2025-09-25T10:00:00Z",
  "frameworks": {
    "mifid2": {
      "status": "compliant",
      "last_check": "2025-09-25T10:00:00Z",
      "violations": 0,
      "requirements_met": 45,
      "requirements_total": 45
    },
    "emir": {
      "status": "compliant",
      "last_check": "2025-09-25T10:00:00Z",
      "violations": 0,
      "trade_reports_submitted": 1250
    },
    "gdpr": {
      "status": "compliant",
      "data_retention_policy": "active",
      "privacy_controls": "implemented"
    },
    "soc2": {
      "status": "compliant",
      "audit_trail_integrity": "verified",
      "control_effectiveness": "high"
    }
  },
  "audit_summary": {
    "logs_retained": "7_years",
    "cryptographic_integrity": "verified",
    "access_controls": "enforced",
    "data_encryption": "active"
  }
}
```

### Transaction Reporting

**Endpoint:** `POST /api/v1/compliance/transaction-report`

**Authentication:** Required (Admin permissions)

**Request:**
```json
{
  "report_type": "mifid2",
  "trade_id": "TRD_20250925_100000",
  "symbol": "EURUSD",
  "quantity": 50000,
  "price": 1.0862,
  "side": "buy",
  "timestamp": "2025-09-25T10:00:00Z",
  "client_id": "CLIENT_001",
  "venue": "FXCM",
  "regulatory_data": {
    "lei": "LEI123456789",
    "transaction_type": "spot",
    "clearing_threshold": false
  }
}
```

**Response:**
```json
{
  "report_id": "RPT_20250925_100000",
  "status": "submitted",
  "submission_timestamp": "2025-09-25T10:00:15Z",
  "regulatory_references": {
    "mifid2_reference": "UK-MIF-RPT-2025092510000001",
    "submission_id": "SUB_20250925_100000"
  },
  "validation_status": "passed",
  "acknowledgment": {
    "regulator": "FCA",
    "acknowledgment_code": "ACK_2025092510000001",
    "received_at": "2025-09-25T10:00:20Z"
  }
}
```

### Audit Log Access

**Endpoint:** `GET /api/v1/compliance/audit-logs`

**Authentication:** Required (Audit permissions)

**Query Parameters:**
- `start_date`: ISO format date
- `end_date`: ISO format date
- `event_type`: `authentication`, `trading`, `access`, `configuration`
- `user_id`: Specific user ID
- `limit`: Maximum records (default: 100, max: 1000)

**Response:**
```json
{
  "total_records": 15623,
  "returned_records": 100,
  "audit_logs": [
    {
      "log_id": "LOG_20250925_100000_001",
      "timestamp": "2025-09-25T10:00:00Z",
      "event_type": "trading",
      "user_id": "user_001",
      "action": "place_order",
      "details": {
        "symbol": "EURUSD",
        "order_type": "market",
        "quantity": 50000,
        "order_id": "ORD_20250925_100000"
      },
      "ip_address": "192.168.1.100",
      "user_agent": "FXML4-WebClient/1.0.0",
      "compliance_tags": ["mifid2", "emir"],
      "cryptographic_hash": "sha256:abc123..."
    }
  ],
  "integrity_status": {
    "verified": true,
    "chain_intact": true,
    "last_verification": "2025-09-25T10:00:00Z"
  }
}
```

### Data Retention Management

**Endpoint:** `GET /api/v1/compliance/data-retention`

**Authentication:** Required (Admin permissions)

**Response:**
```json
{
  "retention_policies": {
    "trading_data": {
      "retention_period": "7_years",
      "current_size": "2.5TB",
      "oldest_record": "2018-09-25T00:00:00Z",
      "auto_archival": "enabled"
    },
    "audit_logs": {
      "retention_period": "7_years",
      "current_size": "500GB",
      "encryption": "AES-256",
      "integrity_checks": "daily"
    },
    "user_data": {
      "retention_period": "5_years",
      "gdpr_compliance": "active",
      "right_to_deletion": "implemented"
    }
  },
  "compliance_status": {
    "mifid2": "compliant",
    "emir": "compliant",
    "gdpr": "compliant",
    "soc2": "compliant"
  }
}
```

---

## 🔄 Trading & Order Management API

### Order Placement

**Endpoint:** `POST /api/v1/trading/orders`

**Authentication:** Required

**Request:**
```json
{
  "symbol": "EURUSD",
  "side": "buy",
  "order_type": "market",
  "quantity": 50000,
  "price": 1.0862,
  "stop_loss": 1.0812,
  "take_profit": 1.0912,
  "time_in_force": "GTC",
  "broker": "interactive_brokers",
  "risk_parameters": {
    "max_slippage_pips": 2,
    "position_sizing_method": "fixed_risk",
    "risk_amount": 2000.0
  }
}
```

**Response:**
```json
{
  "order_id": "ORD_20250925_100000",
  "status": "pending",
  "symbol": "EURUSD",
  "side": "buy",
  "quantity": 50000,
  "submitted_at": "2025-09-25T10:00:00Z",
  "broker_order_id": "IB_123456789",
  "estimated_execution": "2025-09-25T10:00:02Z",
  "risk_check": {
    "passed": true,
    "margin_required": 4076.25,
    "available_margin": 25000.0,
    "position_size_valid": true
  },
  "compliance_check": {
    "passed": true,
    "mifid2_validation": "passed",
    "position_limits": "within_limits"
  }
}
```

### Order Status & Management

**Endpoint:** `GET /api/v1/trading/orders/{order_id}`

**Authentication:** Required

**Response:**
```json
{
  "order_id": "ORD_20250925_100000",
  "status": "filled",
  "symbol": "EURUSD",
  "side": "buy",
  "quantity": 50000,
  "filled_quantity": 50000,
  "avg_fill_price": 1.0863,
  "submitted_at": "2025-09-25T10:00:00Z",
  "filled_at": "2025-09-25T10:00:02Z",
  "execution_details": {
    "fills": [
      {
        "quantity": 50000,
        "price": 1.0863,
        "timestamp": "2025-09-25T10:00:02Z",
        "execution_id": "EXEC_001",
        "commission": 5.0
      }
    ],
    "total_commission": 5.0,
    "slippage_pips": 0.1
  },
  "position_created": {
    "position_id": "POS_20250925_100000",
    "entry_price": 1.0863,
    "stop_loss": 1.0812,
    "take_profit": 1.0912
  }
}
```

### FIX Protocol Integration

**Endpoint:** `POST /api/v1/trading/fix/translate`

**Authentication:** Required

**Request:**
```json
{
  "order_data": {
    "symbol": "EURUSD",
    "side": "buy",
    "quantity": 50000,
    "order_type": "market",
    "client_order_id": "CLIENT_ORD_001"
  },
  "broker": "interactive_brokers",
  "fix_version": "4.4"
}
```

**Response:**
```json
{
  "fix_message": "8=FIX.4.4|9=000158|35=D|34=1|49=SENDER|52=20250925-10:00:00|56=TARGET|11=CLIENT_ORD_001|21=1|38=50000|40=1|54=1|55=EUR/USD|10=123|",
  "translation_success": true,
  "message_components": {
    "header": {
      "msg_type": "NewOrderSingle",
      "sender_comp_id": "SENDER",
      "target_comp_id": "TARGET"
    },
    "body": {
      "cl_ord_id": "CLIENT_ORD_001",
      "symbol": "EUR/USD",
      "side": "Buy",
      "order_qty": 50000,
      "ord_type": "Market"
    }
  },
  "validation_status": "valid",
  "estimated_execution_time": "2025-09-25T10:00:02Z"
}
```

### Position Management

**Endpoint:** `GET /api/v1/trading/positions`

**Authentication:** Required

**Query Parameters:**
- `symbol`: Filter by currency pair
- `status`: `open`, `closed`, `all`
- `include_pnl`: `true`/`false`

**Response:**
```json
{
  "positions": [
    {
      "position_id": "POS_20250925_100000",
      "symbol": "EURUSD",
      "side": "long",
      "quantity": 50000,
      "entry_price": 1.0863,
      "current_price": 1.0885,
      "unrealized_pnl": 1100.0,
      "realized_pnl": 0.0,
      "opened_at": "2025-09-25T10:00:02Z",
      "stop_loss": 1.0812,
      "take_profit": 1.0912,
      "risk_amount": 2000.0,
      "margin_used": 4076.25,
      "days_held": 0.5,
      "broker": "interactive_brokers"
    }
  ],
  "summary": {
    "total_positions": 1,
    "total_unrealized_pnl": 1100.0,
    "total_margin_used": 4076.25,
    "portfolio_value": 101100.0
  }
}
```

---

## 📊 Performance & Analytics API

### Backtesting Engine

**Endpoint:** `POST /api/v1/performance/backtest`

**Authentication:** Required

**Request:**
```json
{
  "strategy": "ml_signal_strategy",
  "symbol": "EURUSD",
  "timeframe": "1h",
  "start_date": "2024-01-01T00:00:00Z",
  "end_date": "2025-01-01T00:00:00Z",
  "initial_capital": 100000.0,
  "parameters": {
    "risk_per_trade": 0.02,
    "max_positions": 3,
    "confidence_threshold": 0.7
  },
  "benchmark": "buy_and_hold",
  "include_costs": true
}
```

**Response:**
```json
{
  "backtest_id": "BT_20250925_100000",
  "status": "completed",
  "execution_time_ms": 1250,
  "results": {
    "total_return": 0.185,
    "total_return_pct": 18.5,
    "annualized_return": 0.195,
    "volatility": 0.12,
    "sharpe_ratio": 1.62,
    "sortino_ratio": 2.15,
    "calmar_ratio": 1.85,
    "max_drawdown": -0.08,
    "max_drawdown_pct": -8.0,
    "win_rate": 0.64,
    "profit_factor": 2.1,
    "expectancy": 245.5,
    "recovery_factor": 2.31
  },
  "trade_statistics": {
    "total_trades": 127,
    "winning_trades": 81,
    "losing_trades": 46,
    "avg_win": 850.2,
    "avg_loss": -320.5,
    "largest_win": 2100.0,
    "largest_loss": -1200.0,
    "avg_trade_duration": "2.5_days"
  },
  "benchmark_comparison": {
    "strategy_return": 0.185,
    "benchmark_return": 0.045,
    "excess_return": 0.140,
    "information_ratio": 1.85
  }
}
```

### Performance Analytics

**Endpoint:** `GET /api/v1/performance/analytics`

**Authentication:** Required

**Query Parameters:**
- `timeframe`: `1d`, `1w`, `1m`, `3m`, `6m`, `1y`, `all`
- `include_drawdowns`: `true`/`false`
- `include_trades`: `true`/`false`

**Response:**
```json
{
  "performance_summary": {
    "period": "1m",
    "start_date": "2025-08-25T00:00:00Z",
    "end_date": "2025-09-25T00:00:00Z",
    "total_return": 0.045,
    "volatility": 0.08,
    "sharpe_ratio": 1.25,
    "max_drawdown": -0.03
  },
  "monthly_returns": {
    "2025-09": 0.045,
    "2025-08": 0.032,
    "2025-07": -0.015
  },
  "risk_metrics": {
    "value_at_risk_95": -2500.0,
    "expected_shortfall": -3200.0,
    "tracking_error": 0.05,
    "information_ratio": 1.15
  },
  "attribution_analysis": {
    "strategy_contribution": {
      "ml_signals": 0.025,
      "risk_management": 0.015,
      "execution_alpha": 0.005
    },
    "symbol_contribution": {
      "EURUSD": 0.020,
      "GBPUSD": 0.015,
      "USDJPY": 0.010
    }
  }
}
```

### Trade Analysis

**Endpoint:** `GET /api/v1/performance/trades`

**Authentication:** Required

**Query Parameters:**
- `start_date`: ISO format date
- `end_date`: ISO format date
- `symbol`: Currency pair filter
- `min_pnl`: Minimum PnL filter
- `include_analysis`: `true`/`false`

**Response:**
```json
{
  "trades": [
    {
      "trade_id": "TRD_20250925_100000",
      "symbol": "EURUSD",
      "side": "long",
      "entry_time": "2025-09-25T10:00:00Z",
      "exit_time": "2025-09-25T14:30:00Z",
      "entry_price": 1.0863,
      "exit_price": 1.0895,
      "quantity": 50000,
      "pnl": 1600.0,
      "pnl_pct": 0.029,
      "commission": 10.0,
      "slippage": 0.5,
      "hold_time": "4h30m",
      "exit_reason": "take_profit",
      "signal_confidence": 0.85,
      "risk_reward_realized": 1.8
    }
  ],
  "trade_analysis": {
    "total_trades": 25,
    "avg_pnl": 245.5,
    "win_rate": 0.64,
    "avg_hold_time": "2.5_days",
    "best_trade": 2100.0,
    "worst_trade": -1200.0
  },
  "pattern_analysis": {
    "winning_patterns": [
      {
        "pattern": "ml_confidence_above_0.8",
        "win_rate": 0.78,
        "avg_pnl": 450.0
      }
    ],
    "losing_patterns": [
      {
        "pattern": "high_correlation_positions",
        "win_rate": 0.45,
        "avg_pnl": -125.0
      }
    ]
  }
}
```

---

## 🔌 Enhanced WebSocket API

### High-Performance Connection Management

**Connection URL:** `wss://api.yourdomain.com/ws`

**Enhanced Features:**
- **10,000+ concurrent connections** support
- **Sub-millisecond message broadcasting**
- **Binary compression** (ZLIB, GZIP, MessagePack)
- **Automatic failover and reconnection**
- **Priority-based message queuing**
- **Real-time performance monitoring**

**Headers:**
```http
Authorization: Bearer <access_token>
Sec-WebSocket-Protocol: fxml4-v1
X-Compression: zlib
X-Priority: high
X-Buffer-Size: 1000
```

**Enhanced Connection Acknowledgment:**
```json
{
  "type": "connection_ack",
  "session_id": "WS_20250925_100000",
  "server_time": "2025-09-25T10:00:00Z",
  "server_capabilities": {
    "max_connections": 10000,
    "compression_support": ["zlib", "gzip", "msgpack"],
    "broadcast_latency_ms": 0.8,
    "priority_queuing": true,
    "failover_enabled": true
  },
  "supported_channels": [
    "market_data",
    "signals",
    "positions",
    "orders",
    "risk_alerts",
    "performance_metrics",
    "data_quality"
  ],
  "connection_metrics": {
    "server_load": 0.45,
    "active_connections": 2847,
    "estimated_latency_ms": 0.6
  }
}
```

### Channel Subscriptions

**Market Data Channel:**
```json
{
  "action": "subscribe",
  "channel": "market_data",
  "symbols": ["EURUSD", "GBPUSD"],
  "timeframes": ["1m", "5m"],
  "data_types": ["ohlcv", "bid_ask"]
}
```

**Signals Channel:**
```json
{
  "action": "subscribe",
  "channel": "signals",
  "symbols": ["EURUSD", "GBPUSD"],
  "confidence_threshold": 0.7,
  "signal_types": ["entry", "exit"]
}
```

**Risk Alerts Channel:**
```json
{
  "action": "subscribe",
  "channel": "risk_alerts",
  "alert_levels": ["warning", "critical"],
  "position_ids": ["POS_001", "POS_002"]
}
```

### Real-Time Data Streams

**Market Data Stream:**
```json
{
  "channel": "market_data",
  "type": "price_update",
  "symbol": "EURUSD",
  "timestamp": "2025-09-25T10:00:00Z",
  "data": {
    "bid": 1.0861,
    "ask": 1.0862,
    "spread": 0.0001,
    "volume": 1000
  }
}
```

**Signal Stream:**
```json
{
  "channel": "signals",
  "type": "new_signal",
  "signal_id": "SIG_20250925_100000",
  "symbol": "EURUSD",
  "timestamp": "2025-09-25T10:00:00Z",
  "signal": {
    "type": "entry_long",
    "confidence": 0.85,
    "price": 1.0862,
    "stop_loss": 1.0812,
    "take_profit": 1.0912
  }
}
```

---

## 📚 Data Structures & Enums

### Currency Pairs (Symbols)

```python
SUPPORTED_SYMBOLS = [
    "EURUSD", "GBPUSD", "USDJPY", "USDCHF",
    "AUDUSD", "USDCAD", "NZDUSD", "EURJPY",
    "GBPJPY", "EURGBP", "AUDNZD", "GBPCHF"
]
```

### Timeframes

```python
class Timeframe(str, Enum):
    MINUTE_1 = "1m"
    MINUTE_5 = "5m"
    MINUTE_15 = "15m"
    MINUTE_30 = "30m"
    HOUR_1 = "1h"
    HOUR_4 = "4h"
    DAY_1 = "1d"
    WEEK_1 = "1w"
    MONTH_1 = "1M"
```

### Order Types

```python
class OrderType(str, Enum):
    MARKET = "market"
    LIMIT = "limit"
    STOP = "stop"
    STOP_LIMIT = "stop_limit"
```

### Position Sides

```python
class PositionSide(str, Enum):
    LONG = "long"
    SHORT = "short"
```

### Signal Types

```python
class SignalType(str, Enum):
    ENTRY_LONG = "entry_long"
    ENTRY_SHORT = "entry_short"
    EXIT_LONG = "exit_long"
    EXIT_SHORT = "exit_short"
    HOLD = "hold"
```

### Risk Levels

```python
class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"
```

### Compliance Frameworks

```python
class ComplianceFramework(str, Enum):
    MIFID2 = "mifid2"
    EMIR = "emir"
    GDPR = "gdpr"
    SOC2 = "soc2"
    PCI_DSS = "pci_dss"
    DODD_FRANK = "dodd_frank"
```

---

## ⚠️ Error Handling

### HTTP Status Codes

| Code | Meaning | Description |
|------|---------|-------------|
| 200 | OK | Request successful |
| 201 | Created | Resource created successfully |
| 400 | Bad Request | Invalid request parameters |
| 401 | Unauthorized | Invalid or missing authentication |
| 403 | Forbidden | Insufficient permissions |
| 404 | Not Found | Resource not found |
| 409 | Conflict | Resource conflict (e.g., duplicate order) |
| 429 | Too Many Requests | Rate limit exceeded |
| 500 | Internal Server Error | Server-side error |
| 503 | Service Unavailable | Service temporarily unavailable |

### Error Response Format

```json
{
  "error": {
    "code": "INVALID_SYMBOL",
    "message": "The specified symbol 'INVALID' is not supported",
    "details": {
      "supported_symbols": ["EURUSD", "GBPUSD", "USDJPY"],
      "provided_symbol": "INVALID"
    },
    "timestamp": "2025-09-25T10:00:00Z",
    "request_id": "REQ_20250925_100000"
  }
}
```

### Common Error Codes

```python
ERROR_CODES = {
    # Authentication Errors
    "TOKEN_EXPIRED": "JWT token has expired",
    "TOKEN_INVALID": "JWT token is invalid or malformed",
    "2FA_REQUIRED": "Two-factor authentication required",

    # Trading Errors
    "INSUFFICIENT_MARGIN": "Insufficient margin for trade",
    "POSITION_LIMIT_EXCEEDED": "Maximum position limit exceeded",
    "INVALID_SYMBOL": "Currency pair not supported",
    "MARKET_CLOSED": "Market is currently closed",

    # Risk Management Errors
    "RISK_LIMIT_EXCEEDED": "Trade exceeds risk limits",
    "CORRELATION_LIMIT": "High correlation detected with existing positions",
    "STOP_LOSS_REQUIRED": "Stop loss is required for this trade",

    # Data Errors
    "DATA_UNAVAILABLE": "Market data not available for specified period",
    "DATA_QUALITY_POOR": "Data quality below acceptable threshold",

    # System Errors
    "BROKER_DISCONNECTED": "Broker connection is unavailable",
    "DATABASE_ERROR": "Database operation failed",
    "SERVICE_OVERLOADED": "Service temporarily overloaded"
}
```

---

## 🔒 Rate Limiting

### Rate Limit Headers

All API responses include rate limiting information:

```http
X-RateLimit-Limit: 1000
X-RateLimit-Remaining: 999
X-RateLimit-Reset: 1632825600
X-RateLimit-Retry-After: 60
```

### Rate Limits by Endpoint Category

| Category | Requests per Minute | Burst Limit |
|----------|-------------------|-------------|
| Authentication | 10 | 20 |
| Market Data | 300 | 500 |
| Trading | 100 | 150 |
| Risk Management | 500 | 750 |
| Analytics | 60 | 100 |
| WebSocket Connections | 5 | 10 |

### Rate Limit Response

When rate limit is exceeded:

```json
{
  "error": {
    "code": "RATE_LIMIT_EXCEEDED",
    "message": "Rate limit exceeded. Try again in 60 seconds",
    "details": {
      "limit": 1000,
      "window": "1 minute",
      "retry_after": 60
    }
  }
}
```

---

## 🛠️ SDKs & Integration Examples

### Python SDK Example

```python
import fxml4

# Initialize client
client = fxml4.Client(
    base_url="https://api.yourdomain.com",
    api_key="your_api_key",
    secret="your_secret"
)

# Get market data
data = client.market_data.get_historical(
    symbol="EURUSD",
    timeframe="1h",
    limit=1000
)

# Generate signals
signals = client.ml.generate_signals(
    symbol="EURUSD",
    strategy="ml_signal_strategy",
    confidence_threshold=0.7
)

# Place order
order = client.trading.place_order(
    symbol="EURUSD",
    side="buy",
    quantity=50000,
    order_type="market",
    stop_loss=1.0812,
    take_profit=1.0912
)
```

### JavaScript/TypeScript SDK Example

```typescript
import { FXML4Client } from '@fxml4/sdk';

const client = new FXML4Client({
  baseUrl: 'https://api.yourdomain.com',
  apiKey: 'your_api_key',
  secret: 'your_secret'
});

// WebSocket connection
const ws = client.websocket.connect();

ws.subscribe('market_data', {
  symbols: ['EURUSD', 'GBPUSD'],
  timeframes: ['1m']
});

ws.on('market_data', (data) => {
  console.log('Market data update:', data);
});

// REST API calls
const positions = await client.trading.getPositions();
const performance = await client.performance.getAnalytics({
  timeframe: '1m'
});
```

---

## 📞 Support & Resources

### API Support

**Documentation:**
- Interactive API docs: `https://api.yourdomain.com/docs`
- ReDoc documentation: `https://api.yourdomain.com/redoc`
- OpenAPI specification: `https://api.yourdomain.com/openapi.json`

**Support Channels:**
- Email: `api-support@fxml.io`
- GitHub Issues: `https://github.com/fxml/fxml4/issues`
- Developer Discord: `https://discord.gg/fxml4-dev`

### Rate Limits & Quotas

Contact `enterprise@fxml.io` for higher rate limits or custom quotas for production trading systems.

### Status Page

Monitor API status and incidents: `https://status.fxml.io`

---

**Last Updated:** September 25, 2025
**API Version:** v1.0.0
**Specification:** OpenAPI 3.0.3

*This API reference reflects the production-ready FXML4 v1.0.0 release with comprehensive trading, risk management, ML, and compliance capabilities achieved through rigorous TDD methodology.*
