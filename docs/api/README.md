# FXML4 API Documentation

Welcome to the FXML4 API documentation. This comprehensive guide will help you integrate with our forex trading platform API.

## Overview

The FXML4 API provides programmatic access to:
- Real-time and historical market data
- Trading signal generation
- Backtesting capabilities
- Risk management tools
- Portfolio analytics

## API Versions

We support API versioning to ensure backward compatibility while continuously improving our services.

### Current Version: v2

- **Status**: Active
- **Release Date**: January 1, 2024
- **Features**:
  - WebSocket support for real-time data
  - Enhanced filtering and pagination
  - Batch operations
  - Advanced backtesting with Monte Carlo simulation
  - GraphQL endpoint (coming soon)

### Previous Version: v1

- **Status**: Deprecated
- **Deprecation Date**: January 1, 2024
- **Sunset Date**: July 1, 2024
- **Migration Guide**: [v1 to v2 Migration](./guides/migration-v1-to-v2.md)

## Quick Start

### 1. Authentication

```bash
# Get access token
curl -X POST https://api.fxml4.com/token \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=your_username&password=your_password&grant_type=password"
```

### 2. Make Your First Request

```bash
# Get market data
curl -X POST https://api.fxml4.com/api/v2/data \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "symbol": "EURUSD",
    "timeframe": "1h",
    "start_date": "2023-01-01T00:00:00Z",
    "end_date": "2023-12-31T23:59:59Z"
  }'
```

### 3. Install Client SDK

#### Python
```bash
pip install fxml4-api-client
```

```python
from fxml4.api.client import FXML4Client

client = FXML4Client(api_key="YOUR_API_KEY")
data = client.get_data(
    symbol="EURUSD",
    timeframe="1h",
    start_date="2023-01-01",
    end_date="2023-12-31"
)
```

#### JavaScript/TypeScript
```bash
npm install @fxml4/api-client
```

```typescript
import { FXML4Client } from '@fxml4/api-client';

const client = new FXML4Client({ apiKey: 'YOUR_API_KEY' });
const data = await client.getData({
  symbol: 'EURUSD',
  timeframe: '1h',
  startDate: '2023-01-01',
  endDate: '2023-12-31'
});
```

## API Reference

### Core Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v2/data` | POST | Get market data |
| `/api/v2/signals` | POST | Generate trading signals |
| `/api/v2/backtest` | POST | Run backtesting |
| `/api/v2/batch` | POST | Execute batch operations |
| `/api/v2/health` | GET | Check API status |

### WebSocket Endpoints

| Endpoint | Description |
|----------|-------------|
| `/api/v2/ws/signals/{symbol}` | Real-time signal updates |
| `/api/v2/ws/data/{symbol}` | Real-time market data |
| `/api/v2/ws/trades` | Real-time trade updates |

## Rate Limits

| Plan | Requests/Hour | WebSocket Connections |
|------|---------------|----------------------|
| Free | 100 | 1 |
| Basic | 1,000 | 5 |
| Pro | 10,000 | 20 |
| Enterprise | Unlimited | Unlimited |

Rate limit information is included in response headers:
- `X-RateLimit-Limit`: Total requests allowed
- `X-RateLimit-Remaining`: Requests remaining
- `X-RateLimit-Reset`: Reset timestamp

## Error Handling

All errors follow a consistent format:

```json
{
  "success": false,
  "message": "Human-readable error message",
  "error": "ErrorType",
  "details": [
    {
      "field": "symbol",
      "message": "Invalid symbol format",
      "code": "INVALID_FORMAT"
    }
  ],
  "help_url": "https://api.fxml4.com/docs/errors#validation",
  "request_id": "req_123456"
}
```

### Common Error Codes

| Code | Description | Resolution |
|------|-------------|------------|
| 400 | Bad Request | Check request parameters |
| 401 | Unauthorized | Verify authentication token |
| 403 | Forbidden | Check API permissions |
| 404 | Not Found | Verify endpoint URL |
| 429 | Rate Limited | Wait and retry |
| 500 | Server Error | Contact support |

## Best Practices

1. **Use Pagination**: Always paginate large result sets
2. **Cache Responses**: Cache data that doesn't change frequently
3. **Handle Rate Limits**: Implement exponential backoff
4. **Use WebSockets**: For real-time data, use WebSocket connections
5. **Batch Operations**: Group multiple requests when possible

## Support

- **Documentation**: [https://api.fxml4.com/docs](https://api.fxml4.com/docs)
- **API Status**: [https://status.fxml4.com](https://status.fxml4.com)
- **Support Email**: api-support@fxml4.com
- **Developer Forum**: [https://forum.fxml4.com](https://forum.fxml4.com)

## Changelog

See [CHANGELOG.md](./CHANGELOG.md) for a complete list of changes.

## License

Usage of the FXML4 API is subject to our [Terms of Service](https://fxml4.com/terms) and [API Agreement](https://fxml4.com/api-terms).
