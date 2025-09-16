# FXML4 API Reference

## Overview

The FXML4 API provides a RESTful interface for accessing the platform's functionality, including market data retrieval, backtesting, and performance analysis. The API is designed to be used by both the FXML4 dashboard UI and external applications.

## Getting Started

To use the API, you need to start the API server:

```bash
python -m fxml4.api.main
```

The server will start at the configured host and port (default: `http://localhost:8000`).

## API Endpoints

The API provides the following main endpoints:

1. **Health**: Check if the API server is running and healthy
2. **Data**: Fetch market data for different symbols and timeframes
3. **Backtest**: Run backtests for different trading strategies
4. **Performance Metrics**: Get detailed performance metrics for backtests
5. **Performance Reports**: Generate and retrieve performance reports
6. **Backtest Comparison**: Compare multiple backtests

For detailed information about each endpoint, including request and response formats, see the [API Endpoints Documentation](endpoints.md).

## API Client

The FXML4 dashboard UI includes an API client that provides convenient methods for interacting with the API. You can find the client implementation in `/fxml4/ui/dashboard.py`.

Example usage:

```python
from fxml4.ui.dashboard import ApiClient

# Create API client
client = ApiClient()

# Check API health
health = client.get_health()

# Get market data
data = client.get_market_data(
    symbol="EURUSD",
    timeframe="1h",
    start_date="2023-01-01",
    end_date="2023-12-31"
)

# Run a backtest
result = client.run_backtest(
    symbol="EURUSD",
    timeframe="1h",
    strategy="ml_strategy",
    start_date="2023-01-01",
    end_date="2023-12-31",
    initial_capital=10000.0,
    parameters={"model": "random_forest"}
)

# Get performance metrics
metrics = client.get_performance_metrics(
    backtest_id=result["backtest_id"],
    include_trades=True,
    include_equity_curve=True
)

# Get report URL
report_url = client.get_performance_report_url(
    backtest_id=result["backtest_id"],
    format="html"
)

# Compare multiple backtests
comparison = client.compare_backtests(
    backtest_ids=[result1["backtest_id"], result2["backtest_id"]],
    metrics=["total_return_pct", "max_drawdown_pct", "sharpe_ratio"]
)
```

## Error Handling

The API returns standard HTTP status codes and error messages in a consistent format. The API client handles these errors and raises appropriate exceptions.

## Future Enhancements

Planned enhancements for the API include:

1. Authentication and authorization
2. Rate limiting
3. Pagination for large responses
4. Streaming data support
5. WebSocket support for real-time updates
6. API versioning
