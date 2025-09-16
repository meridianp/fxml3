# Compliance API Endpoints

The Compliance API provides access to compliance monitoring, regulatory checks, audit trails, and violation management. All compliance operations are logged for regulatory audit purposes.

## Authentication

All compliance endpoints require authenticated access with appropriate permissions:

```http
Authorization: Bearer YOUR_API_KEY
X-Permission-Scope: compliance
```

## Base URL

```
https://api.fxml4.com/v1
```

## Endpoints

### Get Compliance Stats

Retrieve overall compliance engine statistics.

```http
GET /compliance/stats
```

**Response:**
```json
{
  "total_checks": 15423,
  "total_violations": 89,
  "total_blocked": 12,
  "active_rules": 18,
  "total_rules": 20,
  "violation_rate": 0.58,
  "block_rate": 0.08,
  "rules": {
    "POS_LIMIT_001": {
      "rule_name": "Position Size Limit",
      "enabled": true,
      "checks_performed": 1250,
      "violations_found": 8,
      "violation_rate": 0.64,
      "last_check_time": "2024-01-15T10:30:15Z"
    }
  },
  "recent_violations": [
    {
      "rule_id": "POS_LIMIT_001",
      "violation_type": "POSITION_LIMIT_EXCEEDED",
      "severity": "HIGH",
      "message": "Position limit exceeded for EURUSD",
      "cl_ord_id": "ORDER_001",
      "timestamp": "2024-01-15T10:25:00Z"
    }
  ]
}
```

### Check Order Compliance

Perform compliance check on an order without submitting it.

```http
POST /compliance/check-order
```

**Request Body:**
```json
{
  "cl_ord_id": "ORDER_TEST_001",
  "symbol": "EURUSD",
  "side": "BUY",
  "order_qty": 100000,
  "ord_type": "LIMIT",
  "price": 1.1250,
  "client_id": "CLIENT001",
  "context": {
    "positions": {
      "EURUSD": 500000
    },
    "portfolio_value": 1000000,
    "regulatory_context": {
      "jurisdiction": "US_SEC",
      "client_type": "retail"
    }
  }
}
```

**Response (Compliant):**
```json
{
  "result": "PASS",
  "violations": [],
  "risk_assessment": {
    "position_impact": {
      "current_position": 500000,
      "new_position": 600000,
      "position_limit": 10000000,
      "utilization_pct": 6.0
    },
    "concentration_impact": {
      "current_exposure_pct": 15.5,
      "new_exposure_pct": 18.2,
      "limit_pct": 25.0
    }
  }
}
```

**Response (Violation):**
```json
{
  "result": "BLOCKED",
  "violations": [
    {
      "rule_id": "POS_LIMIT_001",
      "rule_name": "Position Size Limit",
      "violation_type": "POSITION_LIMIT_EXCEEDED",
      "severity": "HIGH",
      "message": "Position limit exceeded for EURUSD",
      "details": {
        "current_position": 9500000,
        "order_quantity": 1000000,
        "new_position": 10500000,
        "position_limit": 10000000,
        "excess_amount": 500000
      },
      "suggested_action": "Reduce order size or close existing positions",
      "auto_block": true,
      "requires_manual_review": false
    }
  ]
}
```

### Get Compliance Rules

List all compliance rules and their configuration.

```http
GET /compliance/rules
```

**Query Parameters:**
- `enabled` (boolean, optional): Filter by enabled status
- `rule_type` (string, optional): Filter by rule type

**Response:**
```json
{
  "rules": [
    {
      "rule_id": "POS_LIMIT_001",
      "rule_name": "Position Size Limit",
      "description": "Monitors position sizes against configured limits",
      "enabled": true,
      "severity": "HIGH",
      "rule_type": "position_limit",
      "configuration": {
        "position_limits": {
          "EURUSD": 10000000,
          "GBPUSD": 5000000,
          "default": 1000000
        }
      },
      "statistics": {
        "checks_performed": 1250,
        "violations_found": 8,
        "last_check_time": "2024-01-15T10:30:15Z"
      }
    }
  ]
}
```

### Enable/Disable Compliance Rule

Enable or disable a specific compliance rule.

```http
PUT /compliance/rules/{rule_id}/status
```

**Parameters:**
- `rule_id` (string, required): Rule identifier

**Request Body:**
```json
{
  "enabled": false,
  "reason": "Temporarily disabled for system maintenance"
}
```

**Response:**
```json
{
  "rule_id": "POS_LIMIT_001",
  "enabled": false,
  "updated_at": "2024-01-15T10:35:00Z",
  "updated_by": "admin@fxml4.com"
}
```

### Get Violations

Retrieve compliance violations with filtering options.

```http
GET /compliance/violations
```

**Query Parameters:**
- `rule_id` (string, optional): Filter by rule ID
- `severity` (string, optional): Filter by severity (LOW, MEDIUM, HIGH, CRITICAL)
- `start_date` (string, optional): Start date (ISO 8601)
- `end_date` (string, optional): End date (ISO 8601)
- `cl_ord_id` (string, optional): Filter by order ID
- `symbol` (string, optional): Filter by symbol
- `limit` (integer, optional): Maximum results (default: 100)
- `offset` (integer, optional): Pagination offset

**Response:**
```json
{
  "violations": [
    {
      "rule_id": "POS_LIMIT_001",
      "rule_name": "Position Size Limit",
      "violation_type": "POSITION_LIMIT_EXCEEDED",
      "severity": "HIGH",
      "message": "Position limit exceeded for EURUSD",
      "details": {
        "excess_amount": 500000,
        "position_limit": 10000000
      },
      "cl_ord_id": "ORDER_001",
      "symbol": "EURUSD",
      "user_id": "trader001",
      "timestamp": "2024-01-15T10:25:00Z",
      "suggested_action": "Reduce order size or close existing positions",
      "requires_manual_review": false,
      "auto_block": true
    }
  ],
  "total": 89,
  "pagination": {
    "limit": 100,
    "offset": 0,
    "has_more": false
  }
}
```

### Get Blocked Orders

Retrieve orders currently blocked by compliance.

```http
GET /compliance/blocked-orders
```

**Response:**
```json
{
  "blocked_orders": [
    {
      "cl_ord_id": "ORDER_002",
      "symbol": "EURUSD",
      "side": "BUY",
      "order_qty": 2000000,
      "blocked_at": "2024-01-15T10:28:00Z",
      "violations": [
        {
          "rule_id": "POS_LIMIT_001",
          "severity": "HIGH",
          "message": "Position limit exceeded"
        }
      ],
      "can_override": true,
      "override_authority_required": "SENIOR_TRADER"
    }
  ]
}
```

### Unblock Order

Manually unblock a compliance-blocked order.

```http
POST /compliance/unblock-order
```

**Request Body:**
```json
{
  "cl_ord_id": "ORDER_002",
  "reason": "Risk reviewed and approved by senior trader",
  "override_authority": "SENIOR_TRADER",
  "user_id": "senior.trader@fxml4.com"
}
```

**Response:**
```json
{
  "cl_ord_id": "ORDER_002",
  "unblocked": true,
  "unblocked_at": "2024-01-15T10:40:00Z",
  "unblocked_by": "senior.trader@fxml4.com",
  "audit_event_id": "audit_12345"
}
```

### Get Regulatory Checks

Retrieve regulatory compliance check results.

```http
GET /compliance/regulatory-checks
```

**Query Parameters:**
- `jurisdiction` (string, optional): SEC, MIFID_II, FISCA
- `client_id` (string, optional): Filter by client ID
- `start_date` (string, optional): Start date
- `end_date` (string, optional): End date

**Response:**
```json
{
  "regulatory_checks": [
    {
      "check_id": "REG_001",
      "jurisdiction": "US_SEC",
      "rule_id": "SEC_PDT_001",
      "rule_name": "Pattern Day Trading Rule",
      "client_id": "CLIENT001",
      "result": "VIOLATION",
      "details": {
        "account_equity": 20000,
        "min_equity_requirement": 25000,
        "recent_day_trades": 4
      },
      "checked_at": "2024-01-15T10:30:00Z"
    }
  ]
}
```

### Generate Compliance Report

Generate a compliance report in various formats.

```http
POST /compliance/reports
```

**Request Body:**
```json
{
  "report_type": "DAILY_COMPLIANCE",
  "format": "HTML",
  "start_date": "2024-01-14T00:00:00Z",
  "end_date": "2024-01-15T00:00:00Z",
  "filters": {
    "client_ids": ["CLIENT001", "CLIENT002"],
    "severities": ["HIGH", "CRITICAL"]
  },
  "options": {
    "include_details": true,
    "anonymize_data": false
  }
}
```

**Response:**
```json
{
  "report_id": "RPT_20240115_001",
  "status": "COMPLETED",
  "report_type": "DAILY_COMPLIANCE",
  "format": "HTML",
  "generated_at": "2024-01-15T10:45:00Z",
  "output_file": "/reports/compliance/daily_compliance_20240115_104500.html",
  "file_size_bytes": 245760,
  "record_count": 25,
  "download_url": "https://api.fxml4.com/v1/reports/RPT_20240115_001/download"
}
```

### Download Report

Download a generated compliance report.

```http
GET /compliance/reports/{report_id}/download
```

**Parameters:**
- `report_id` (string, required): Report identifier

**Response:**
- File download (content-type depends on format)

### Get Audit Events

Retrieve audit events for compliance monitoring.

```http
GET /compliance/audit-events
```

**Query Parameters:**
- `category` (string, optional): COMPLIANCE, TRADING, RISK, etc.
- `severity` (string, optional): INFO, WARNING, ERROR, CRITICAL
- `start_date` (string, optional): Start date
- `end_date` (string, optional): End date
- `user_id` (string, optional): Filter by user
- `limit` (integer, optional): Maximum results (default: 100)

**Response:**
```json
{
  "audit_events": [
    {
      "event_id": "audit_12345",
      "timestamp": "2024-01-15T10:30:15Z",
      "category": "COMPLIANCE",
      "severity": "COMPLIANCE",
      "event_type": "COMPLIANCE_VIOLATION",
      "message": "Compliance violation: Position limit exceeded for EURUSD",
      "details": {
        "rule_id": "POS_LIMIT_001",
        "cl_ord_id": "ORDER_001",
        "violation_type": "POSITION_LIMIT_EXCEEDED"
      },
      "user_id": "trader001",
      "cl_ord_id": "ORDER_001",
      "symbol": "EURUSD",
      "compliance_flags": ["POS_LIMIT_001"],
      "hash": "sha256:abc123..."
    }
  ],
  "total": 1523,
  "pagination": {
    "limit": 100,
    "offset": 0,
    "has_more": true
  }
}
```

## Compliance Results

| Result | Description |
|--------|-------------|
| PASS | Order passes all compliance checks |
| WARNING | Minor violations detected, order allowed |
| FAIL | Violations detected, manual review required |
| BLOCKED | Critical violations, order automatically blocked |
| REQUIRES_APPROVAL | Manual approval needed before execution |

## Violation Severities

| Severity | Description |
|----------|-------------|
| LOW | Informational, no action required |
| MEDIUM | Monitoring required, no blocking |
| HIGH | Significant risk, may require review |
| CRITICAL | Immediate action required, auto-block |

## Rule Types

| Type | Description |
|------|-------------|
| position_limit | Position size constraints |
| concentration | Portfolio concentration limits |
| trading_hours | Time-based trading restrictions |
| velocity | Order rate limiting |
| regulatory | Jurisdiction-specific compliance |

## Error Codes

| Code | Description |
|------|-------------|
| COMPLIANCE_RULE_NOT_FOUND | Specified rule does not exist |
| INSUFFICIENT_PERMISSIONS | User lacks compliance access |
| INVALID_JURISDICTION | Unsupported regulatory jurisdiction |
| REPORT_GENERATION_FAILED | Error generating compliance report |
| AUDIT_LOG_CORRUPTION | Audit trail integrity issue |

## Webhooks

Subscribe to compliance events via webhooks:

```json
{
  "event_type": "compliance.violation",
  "data": {
    "rule_id": "POS_LIMIT_001",
    "violation_type": "POSITION_LIMIT_EXCEEDED",
    "cl_ord_id": "ORDER_001",
    "severity": "HIGH",
    "timestamp": "2024-01-15T10:30:15Z"
  }
}
```

## See Also

- [Risk Management API](risk.md)
- [Broker API](brokers.md)
- [Monitoring API](monitoring.md)
