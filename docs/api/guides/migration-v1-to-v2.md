# Migration Guide: v1 to v2

This guide helps you migrate from FXML4 API v1 to v2. While we've maintained backward compatibility where possible, some breaking changes were necessary to improve the API.

## Overview

API v2 introduces several improvements:
- Better performance and reliability
- Enhanced features and functionality
- Consistent response formats
- Improved error handling

## Timeline

- **January 1, 2024**: v2 released, v1 deprecated
- **July 1, 2024**: v1 sunset (read-only)
- **January 1, 2025**: v1 retired (no access)

## Breaking Changes

### 1. URL Structure

**v1:**
```
https://api.fxml4.com/data
https://api.fxml4.com/signals
```

**v2:**
```
https://api.fxml4.com/api/v2/data
https://api.fxml4.com/api/v2/signals
```

### 2. Request Format

#### Data Endpoint

**v1:**
```json
{
  "symbol": "EURUSD",
  "timeframe": "1h",
  "start_date": "2023-01-01",
  "end_date": "2023-12-31"
}
```

**v2:**
```json
{
  "symbol": "EURUSD",
  "timeframe": "1h",
  "start_date": "2023-01-01T00:00:00Z",
  "end_date": "2023-12-31T23:59:59Z",
  "source": "alpha_vantage",
  "include_indicators": ["sma_20", "rsi_14"]
}
```

Changes:
- Dates must be in ISO 8601 format with timezone
- New optional fields: `source`, `include_indicators`
- Pagination is now required for large datasets

### 3. Response Format

#### Success Response

**v1:**
```json
{
  "data": [...],
  "count": 1000
}
```

**v2:**
```json
{
  "success": true,
  "message": "Data retrieved successfully",
  "timestamp": "2024-01-15T10:30:00Z",
  "request_id": "req_abc123",
  "data": {
    "symbol": "EURUSD",
    "timeframe": "1h",
    "items": [...],
    "meta": {
      "page": 1,
      "page_size": 100,
      "total_items": 1000,
      "total_pages": 10,
      "has_next": true,
      "has_previous": false
    }
  }
}
```

#### Error Response

**v1:**
```json
{
  "error": "Invalid symbol"
}
```

**v2:**
```json
{
  "success": false,
  "message": "Validation error",
  "timestamp": "2024-01-15T10:30:00Z",
  "request_id": "req_abc123",
  "error": "ValidationError",
  "details": [
    {
      "field": "symbol",
      "message": "Invalid symbol format",
      "code": "INVALID_FORMAT"
    }
  ],
  "help_url": "https://api.fxml4.com/docs/errors#validation"
}
```

### 4. Authentication

**v1:** API key in query parameter
```
GET https://api.fxml4.com/data?api_key=YOUR_KEY
```

**v2:** Bearer token in header
```
GET https://api.fxml4.com/api/v2/data
Authorization: Bearer YOUR_TOKEN
```

### 5. Pagination

**v1:** Optional, inconsistent
```
GET /data?limit=100&offset=0
```

**v2:** Required, standardized
```
GET /api/v2/data?page=1&page_size=100
```

## New Features in v2

### 1. WebSocket Support

```javascript
const ws = new WebSocket('wss://api.fxml4.com/api/v2/ws/signals/EURUSD');

ws.onmessage = (event) => {
  const signal = JSON.parse(event.data);
  console.log('New signal:', signal);
};
```

### 2. Batch Operations

```json
POST /api/v2/batch
{
  "operations": [
    {
      "type": "data",
      "params": {
        "symbol": "EURUSD",
        "timeframe": "1h",
        "start_date": "2023-01-01T00:00:00Z",
        "end_date": "2023-01-31T23:59:59Z"
      }
    },
    {
      "type": "signals",
      "params": {
        "symbol": "GBPUSD",
        "timeframe": "1h",
        "strategy": "ml_strategy"
      }
    }
  ]
}
```

### 3. Advanced Filtering

```json
POST /api/v2/signals?page=1&page_size=20
{
  "symbol": "EURUSD",
  "timeframe": "1h",
  "strategy": "ml_strategy",
  "confidence_threshold": 0.8,
  "lookback_periods": 500
}
```

## Migration Steps

### Step 1: Update Base URLs

Replace all v1 endpoints with v2 equivalents:

```python
# Old
BASE_URL = "https://api.fxml4.com"

# New
BASE_URL = "https://api.fxml4.com/api/v2"
```

### Step 2: Update Authentication

```python
# Old
params = {"api_key": API_KEY}
response = requests.get(f"{BASE_URL}/data", params=params)

# New
headers = {"Authorization": f"Bearer {API_KEY}"}
response = requests.post(f"{BASE_URL}/data", headers=headers, json=data)
```

### Step 3: Handle Pagination

```python
def get_all_data(symbol, timeframe, start_date, end_date):
    all_data = []
    page = 1

    while True:
        response = client.get_data(
            symbol=symbol,
            timeframe=timeframe,
            start_date=start_date,
            end_date=end_date,
            page=page,
            page_size=100
        )

        all_data.extend(response["items"])

        if not response["meta"]["has_next"]:
            break

        page += 1

    return all_data
```

### Step 4: Update Error Handling

```python
try:
    response = client.get_data(...)
except ValidationError as e:
    for error in e.errors:
        print(f"Field {error['field']}: {error['message']}")
except RateLimitError as e:
    print(f"Rate limited. Retry after {e.retry_after} seconds")
    time.sleep(e.retry_after)
```

### Step 5: Test Thoroughly

1. Run your test suite against v2
2. Monitor for deprecation warnings
3. Check response format compatibility
4. Verify performance improvements

## Using Both Versions

During migration, you can use both versions:

```python
# Version header
headers = {"Accept": "application/vnd.fxml4.v1+json"}  # Use v1
headers = {"Accept": "application/vnd.fxml4.v2+json"}  # Use v2

# URL parameter
response = requests.get("https://api.fxml4.com/api/data?version=v1")
```

## Common Issues

### Issue 1: Date Format Errors

**Problem:** Dates without timezone are rejected

**Solution:** Always use ISO 8601 format with timezone:
```python
from datetime import datetime, timezone

date_str = datetime.now(timezone.utc).isoformat()
```

### Issue 2: Missing Pagination

**Problem:** Large requests fail without pagination

**Solution:** Always include pagination parameters:
```python
params = {
    "page": 1,
    "page_size": 100
}
```

### Issue 3: Authentication Failures

**Problem:** API key in URL no longer works

**Solution:** Move to header-based authentication:
```python
headers = {"Authorization": f"Bearer {API_KEY}"}
```

## Support

If you encounter issues during migration:

1. Check the [API Status Page](https://status.fxml4.com)
2. Review [API Documentation](https://api.fxml4.com/docs)
3. Contact support: api-support@fxml4.com

## Deprecation Notices

When using deprecated features, you'll see headers:
```
X-API-Deprecated: true
X-API-Sunset-Date: 2024-07-01
X-API-Successor-Version: v2
X-API-Warning: API version v1 is deprecated and will be sunset on 2024-07-01. Please migrate to v2
```
