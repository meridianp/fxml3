# FXML4 Backtesting and Performance API

This documentation covers the API endpoints related to backtesting and performance analysis in FXML4.

## Overview

The backtesting and performance API provides endpoints for:

1. Running backtests
2. Retrieving performance metrics
3. Generating performance reports
4. Comparing multiple strategies

## API Endpoints

### Run Backtest

```
POST /api/backtest
```

Runs a backtest for a given strategy.

**Request body:**
```json
{
  "symbol": "EURUSD",
  "timeframe": "1h",
  "strategy": "ml_strategy",
  "start_date": "2023-01-01",
  "end_date": "2023-12-31",
  "initial_capital": 10000,
  "parameters": {
    "model": "random_forest",
    "features": ["technical", "volatility"]
  },
  "auto_report": true
}
```

**Response:**
```json
{
  "backtest_id": "BT-20230101-123456",
  "symbol": "EURUSD",
  "timeframe": "1h",
  "strategy": "ml_strategy",
  "start_date": "2023-01-01",
  "end_date": "2023-12-31",
  "initial_capital": 10000,
  "final_capital": 12500,
  "total_return": 2500,
  "total_return_pct": 25.0,
  "max_drawdown": 800,
  "max_drawdown_pct": 8.0,
  "trade_count": 42,
  "report_url": "/api/performance/report/BT-20230101-123456"
}
```

### Get Performance Metrics

```
GET /api/performance/metrics/{backtest_id}
```

Retrieves detailed performance metrics for a backtest.

**Query parameters:**
- `include_trades` (boolean): Whether to include trade details
- `include_equity_curve` (boolean): Whether to include equity curve data

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
    // ...
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
    // ...
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
  }
}
```

### Get Performance Report

```
GET /api/performance/report/{backtest_id}
```

Returns a performance report for a backtest.

**Query parameters:**
- `format` (string): Report format, either `html` or `pdf`

**Response:**
The report file in the requested format.

### Compare Strategies

```
POST /api/performance/compare
```

Compares multiple backtests.

**Request body:**
```json
{
  "backtest_ids": ["BT-20230101-123456", "BT-20230215-123456", "BT-20230310-123456"],
  "metrics": ["total_return_pct", "max_drawdown_pct", "sharpe_ratio"]
}
```

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

## Using the API

The API can be consumed by:

1. The FXML4 web dashboard
2. Custom scripts using the requests library
3. External applications that need backtesting capabilities

## Example Usage

```python
import requests

# Run a backtest
response = requests.post(
    "http://localhost:8000/api/backtest",
    json={
        "symbol": "EURUSD",
        "timeframe": "1h",
        "strategy": "ml_strategy",
        "start_date": "2023-01-01",
        "end_date": "2023-12-31",
        "initial_capital": 10000,
        "parameters": {
            "model": "random_forest",
            "features": ["technical", "volatility"]
        },
        "auto_report": True
    }
)

backtest_result = response.json()
backtest_id = backtest_result["backtest_id"]

# Get performance metrics
metrics_response = requests.get(
    f"http://localhost:8000/api/performance/metrics/{backtest_id}",
    params={"include_equity_curve": True}
)

metrics = metrics_response.json()
print(f"Total Return: {metrics['metrics']['total_return_pct']}%")
print(f"Sharpe Ratio: {metrics['metrics']['sharpe_ratio']}")
```
