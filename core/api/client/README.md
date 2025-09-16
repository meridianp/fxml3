# FXML4 API Python Client

Official Python client library for the FXML4 Trading Platform API.

## Features

- Full API coverage with type hints
- Synchronous and asynchronous clients
- Automatic retry with exponential backoff
- WebSocket support for real-time data
- Comprehensive error handling
- CLI tool for quick testing

## Installation

```bash
pip install fxml4-api-client
```

Or install from source:

```bash
git clone https://github.com/fxml4/python-client.git
cd python-client
pip install -e .
```

## Quick Start

### Synchronous Client

```python
from fxml4_api_client import FXML4Client

# Initialize client
client = FXML4Client(api_key="your-api-key")

# Get market data
data = client.get_data(
    symbol="EURUSD",
    timeframe="1h",
    start_date="2023-01-01",
    end_date="2023-12-31"
)

# Generate signals
signals = client.generate_signals(
    symbol="EURUSD",
    timeframe="1h",
    strategy="ml_strategy",
    confidence_threshold=0.8
)

# Run backtest
result = client.run_backtest(
    symbol="EURUSD",
    timeframe="1h",
    strategy="ml_strategy",
    start_date="2023-01-01",
    end_date="2023-12-31",
    initial_capital=10000
)
```

### Asynchronous Client

```python
import asyncio
from fxml4_api_client import AsyncFXML4Client

async def main():
    async with AsyncFXML4Client(api_key="your-api-key") as client:
        # Parallel requests
        data_task = client.get_data(symbol="EURUSD", timeframe="1h", start_date="2023-01-01", end_date="2023-12-31")
        signals_task = client.generate_signals(symbol="EURUSD", timeframe="1h", strategy="ml_strategy")

        data, signals = await asyncio.gather(data_task, signals_task)

        # WebSocket streaming
        async for signal in client.connect_websocket("signals", "EURUSD"):
            print(f"New signal: {signal}")

asyncio.run(main())
```

## CLI Usage

```bash
# Set API key
export FXML4_API_KEY="your-api-key"

# Get market data
fxml4 data EURUSD --timeframe 1h --start-date 2023-01-01 --end-date 2023-12-31

# Generate signals
fxml4 signals EURUSD --strategy ml_strategy --confidence 0.8

# Run backtest
fxml4 backtest EURUSD --strategy ml_strategy --start-date 2023-01-01 --end-date 2023-12-31

# Check API health
fxml4 health
```

## Authentication

The client supports multiple authentication methods:

### API Key (Recommended)

```python
client = FXML4Client(api_key="your-api-key")
```

### Username/Password

```python
client = FXML4Client(username="your-username", password="your-password")
```

### Environment Variable

```bash
export FXML4_API_KEY="your-api-key"
```

```python
client = FXML4Client()  # Will use FXML4_API_KEY env var
```

## Error Handling

```python
from fxml4_api_client import FXML4Client, RateLimitError, ValidationError

client = FXML4Client(api_key="your-api-key")

try:
    data = client.get_data(symbol="INVALID", timeframe="1h", start_date="2023-01-01", end_date="2023-12-31")
except ValidationError as e:
    print(f"Validation error: {e.message}")
    for error in e.errors:
        print(f"  {error['field']}: {error['message']}")
except RateLimitError as e:
    print(f"Rate limited. Retry after {e.retry_after} seconds")
except Exception as e:
    print(f"Unexpected error: {e}")
```

## Advanced Usage

### Pagination

```python
# Get all data with automatic pagination
all_data = []
page = 1

while True:
    response = client.get_data(
        symbol="EURUSD",
        timeframe="1h",
        start_date="2023-01-01",
        end_date="2023-12-31",
        page=page,
        page_size=1000
    )

    all_data.extend(response["items"])

    if not response["meta"]["has_next"]:
        break

    page += 1
```

### Batch Operations

```python
operations = [
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

results = client.batch(operations)
```

### Custom Retry Logic

```python
client = FXML4Client(
    api_key="your-api-key",
    retry_count=5,
    retry_backoff=0.5  # exponential backoff factor
)
```

## API Versioning

```python
# Use specific API version
client = FXML4Client(api_key="your-api-key", version="v2")

# Check version info
version_info = client.get_version_info()
print(f"Current version: {version_info['current_version']}")

# Switch versions
client.set_version("v1")  # Use v1 (deprecated)
```

## Rate Limiting

The client automatically handles rate limiting:

- Includes rate limit info in response headers
- Automatic retry with exponential backoff
- Respects `Retry-After` headers

```python
# Check remaining rate limit
response = client.get_data(...)
print(f"Remaining requests: {response.headers.get('X-RateLimit-Remaining')}")
```

## Contributing

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## Testing

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Run with coverage
pytest --cov=fxml4_api_client

# Type checking
mypy fxml4_api_client

# Linting
flake8 fxml4_api_client
black fxml4_api_client
isort fxml4_api_client
```

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Support

- Documentation: https://api.fxml4.com/docs
- API Status: https://status.fxml4.com
- Issues: https://github.com/fxml4/python-client/issues
- Email: api-support@fxml4.com

## Changelog

See [CHANGELOG.md](CHANGELOG.md) for a list of changes.
