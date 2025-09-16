# FXML4 API Endpoints

This document provides detailed information about the FXML4 REST API endpoints. The API provides access to market data, backtesting, and performance analysis features.

## Base URL

All API requests should be sent to the base URL of the FXML4 API server, which defaults to:

```
http://localhost:8000
```

You can configure the host and port in the `config/default.yaml` file.

## Authentication

Currently, the API does not require authentication. Authentication will be added in a future release.

## API Endpoints

### Health Check

```
GET /health
```

Check if the API server is running and healthy.

**Response:**

```json
{
  "status": "ok"
}
```

### Get Market Data

```
POST /data
```

Fetch market data for a specified symbol and timeframe.

**Request Body:**

```json
{
  "symbol": "EURUSD",
  "timeframe": "1h",
  "start_date": "2023-01-01",
  "end_date": "2023-12-31",
  "limit": 1000
}
```

| Field       | Type    | Description                                                |
|-------------|---------|------------------------------------------------------------|
| symbol      | string  | Trading symbol (e.g., "EURUSD", "AAPL")                    |
| timeframe   | string  | Data timeframe (e.g., "1m", "5m", "1h", "1d")              |
| start_date  | string  | Start date in ISO format (optional)                        |
| end_date    | string  | End date in ISO format (optional)                          |
| limit       | integer | Maximum number of data points to return (optional)         |

**Response:**

```json
{
  "symbol": "EURUSD",
  "timeframe": "1h",
  "start_date": "2023-01-01",
  "end_date": "2023-12-31",
  "data": [
    {
      "timestamp": "2023-01-01T00:00:00",
      "open": 1.0699,
      "high": 1.0712,
      "low": 1.0688,
      "close": 1.0705,
      "volume": 10500
    },
    // Additional data points...
  ],
  "count": 8760,
  "source": "alpha_vantage"
}
```

### Run Backtest

```
POST /backtest
```

Run a backtest for a specified trading strategy.

**Request Body:**

```json
{
  "symbol": "EURUSD",
  "timeframe": "1h",
  "strategy": "ml_strategy",
  "start_date": "2023-01-01",
  "end_date": "2023-12-31",
  "initial_capital": 10000.0,
  "parameters": {
    "model": "random_forest",
    "features": ["technical", "volatility"]
  },
  "auto_report": true
}
```

| Field           | Type    | Description                                                |
|-----------------|---------|------------------------------------------------------------|
| symbol          | string  | Trading symbol                                             |
| timeframe       | string  | Data timeframe                                             |
| strategy        | string  | Strategy to test ("ml_strategy", "wave_strategy", "integrated_strategy") |
| start_date      | string  | Start date in ISO format                                   |
| end_date        | string  | End date in ISO format                                     |
| initial_capital | number  | Initial capital for backtesting                            |
| parameters      | object  | Strategy-specific parameters                               |
| auto_report     | boolean | Whether to automatically generate a performance report     |

**Response:**

```json
{
  "backtest_id": "BT-20230101-123456",
  "symbol": "EURUSD",
  "timeframe": "1h",
  "strategy": "ml_strategy",
  "start_date": "2023-01-01",
  "end_date": "2023-12-31",
  "initial_capital": 10000.0,
  "final_capital": 12500.0,
  "total_return": 2500.0,
  "total_return_pct": 25.0,
  "max_drawdown": 800.0,
  "max_drawdown_pct": 8.0,
  "sharpe_ratio": 1.8,
  "sortino_ratio": 2.2,
  "win_rate": 0.65,
  "profit_factor": 2.1,
  "trade_count": 42,
  "report_url": "/performance/report/BT-20230101-123456"
}
```

### Get Performance Metrics

```
GET /performance/metrics/{backtest_id}
```

Get detailed performance metrics for a backtest.

**Path Parameters:**

| Parameter    | Description                       |
|--------------|-----------------------------------|
| backtest_id  | ID of the backtest                |

**Query Parameters:**

| Parameter           | Type    | Description                                                |
|---------------------|---------|------------------------------------------------------------|
| include_trades      | boolean | Whether to include trade details (default: false)          |
| include_equity_curve| boolean | Whether to include equity curve data (default: false)      |

**Response:**

```json
{
  "backtest_id": "BT-20230101-123456",
  "metrics": {
    "total_return_pct": 25.0,
    "annualized_return": 18.2,
    "sharpe_ratio": 1.8,
    "sortino_ratio": 2.2,
    "max_drawdown_pct": 8.0,
    "win_rate": 0.65,
    "profit_factor": 2.1,
    "recovery_factor": 3.1,
    "expectancy": 0.52,
    "avg_win": 350.0,
    "avg_loss": -200.0,
    "risk_of_ruin": 0.05,
    "trades_per_month": 6.3,
    "max_consecutive_wins": 5,
    "max_consecutive_losses": 3
  },
  "monthly_returns": {
    "2023-01": 2.1,
    "2023-02": -1.5,
    "2023-03": 3.2,
    // Additional months...
  },
  "drawdowns": [
    {
      "start_date": "2023-02-15",
      "end_date": "2023-02-28",
      "recovery_date": "2023-03-10",
      "depth_pct": 8.0,
      "duration_days": 13,
      "recovery_days": 10
    },
    // Additional drawdowns...
  ],
  "monte_carlo": {
    "mean_return": 25.8,
    "median_return": 24.9,
    "worst_case": 15.2,
    "best_case": 35.6,
    "probability_of_profit": 0.996,
    "probability_of_10pct_drawdown": 0.32,
    "percentiles": {
      "5": 18.5,
      "25": 22.4,
      "50": 24.9,
      "75": 28.1,
      "95": 32.7
    }
  },
  // Optional fields if requested:
  "trades": [
    {
      "entry_time": "2023-01-05T10:30:00",
      "exit_time": "2023-01-07T14:45:00",
      "symbol": "EURUSD",
      "side": "buy",
      "entry_price": 1.0650,
      "exit_price": 1.0720,
      "quantity": 10000,
      "pnl": 700.0,
      "pnl_pct": 0.657
    },
    // Additional trades...
  ],
  "equity_curve": [
    {
      "timestamp": "2023-01-01T00:00:00",
      "equity": 10000.0
    },
    // Additional equity points...
  ]
}
```

### Get Performance Report

```
GET /performance/report/{backtest_id}
```

Get a performance report for a backtest.

**Path Parameters:**

| Parameter    | Description                       |
|--------------|-----------------------------------|
| backtest_id  | ID of the backtest                |

**Query Parameters:**

| Parameter | Type   | Description                                 |
|-----------|--------|---------------------------------------------|
| format    | string | Report format: "html" or "pdf" (default: "html") |

**Response:**

Returns the report file in the requested format.

### Compare Backtests

```
POST /performance/compare
```

Compare multiple backtests.

**Request Body:**

```json
{
  "backtest_ids": ["BT-20230101-123456", "BT-20230215-123456", "BT-20230310-123456"],
  "metrics": ["total_return_pct", "max_drawdown_pct", "sharpe_ratio"]
}
```

| Field        | Type     | Description                                                |
|--------------|---------|------------------------------------------------------------|
| backtest_ids | array   | List of backtest IDs to compare                            |
| metrics      | array   | List of metrics to compare                                 |

**Response:**

```json
{
  "backtest_ids": ["BT-20230101-123456", "BT-20230215-123456", "BT-20230310-123456"],
  "metrics": {
    "total_return_pct": {
      "BT-20230101-123456": 25.0,
      "BT-20230215-123456": 18.5,
      "BT-20230310-123456": 22.3
    },
    "max_drawdown_pct": {
      "BT-20230101-123456": 8.0,
      "BT-20230215-123456": 6.5,
      "BT-20230310-123456": 7.2
    },
    "sharpe_ratio": {
      "BT-20230101-123456": 1.8,
      "BT-20230215-123456": 1.5,
      "BT-20230310-123456": 1.7
    }
  },
  "ranking": {
    "total_return_pct": ["BT-20230101-123456", "BT-20230310-123456", "BT-20230215-123456"],
    "max_drawdown_pct": ["BT-20230215-123456", "BT-20230310-123456", "BT-20230101-123456"],
    "sharpe_ratio": ["BT-20230101-123456", "BT-20230310-123456", "BT-20230215-123456"]
  },
  "correlation_matrix": {
    "BT-20230101-123456": {
      "BT-20230101-123456": 1.0,
      "BT-20230215-123456": 0.75,
      "BT-20230310-123456": 0.82
    },
    "BT-20230215-123456": {
      "BT-20230101-123456": 0.75,
      "BT-20230215-123456": 1.0,
      "BT-20230310-123456": 0.68
    },
    "BT-20230310-123456": {
      "BT-20230101-123456": 0.82,
      "BT-20230215-123456": 0.68,
      "BT-20230310-123456": 1.0
    }
  }
}
```

## Error Handling

The API returns standard HTTP status codes:

- 200: Success
- 400: Bad Request
- 404: Not Found
- 500: Internal Server Error

Error responses include a detail message:

```json
{
  "detail": "Error message describing the issue"
}
```

## Strategy Parameters

### ML Strategy Parameters

```json
{
  "model": "random_forest",  // or "xgboost", "logistic"
  "features": ["technical", "price_patterns", "volatility", "sentiment", "economic"],
  "risk_pct": 0.02
}
```

### Wave Strategy Parameters

```json
{
  "strictness": 0.5,  // 0.0 to 1.0, higher values enforce stricter Elliott Wave rules
  "wave_validation": true,  // Whether to use LLM for wave validation
  "risk_pct": 0.02
}
```

### Integrated Strategy Parameters

```json
{
  "ml_weight": 0.5,  // Weight of ML signals (0.0 to 1.0)
  "wave_weight": 0.3,  // Weight of wave signals (0.0 to 1.0)
  "sentiment_weight": 0.2,  // Weight of sentiment signals (0.0 to 1.0)
  "risk_pct": 0.02
}
```
