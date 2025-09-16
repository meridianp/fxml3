# FXML4 Performance Dashboard

The FXML4 Performance Dashboard is an interactive web-based interface for backtesting trading strategies and analyzing their performance.

## Features

- **Backtest Runner**: Configure and run backtests with different strategies, symbols, and parameters
- **Performance Analysis**: Detailed analysis of backtest results with visualizations
- **Strategy Comparison**: Compare multiple strategies across various metrics
- **Report Generation**: Generate and download HTML/PDF performance reports

## Architecture

The dashboard consists of two main components:

1. **API Server**: FastAPI-based server that provides endpoints for backtesting, performance analysis, and report generation
2. **UI Application**: Streamlit-based web interface that consumes the API to provide an interactive dashboard

This separation of concerns allows for:
- Independent scaling of API and UI components
- Multiple UI implementations using the same API
- Programmatic access to backtesting capabilities via the API

## Getting Started

### Prerequisites

- Python 3.9+
- FXML4 dependencies installed (`pip install -r requirements.txt`)

### Running the Dashboard

The easiest way to run the dashboard is to use the provided script:

```bash
# Run both API and UI components
python run_dashboard.py
```

This will start both the API server and the UI application, with the following default URLs:
- API Server: http://localhost:8000
- UI Application: http://localhost:8501

You can also run the components separately:

```bash
# Run just the API server
python -m fxml4.api.main

# Run just the UI application
streamlit run fxml4/ui/streamlit_app.py
```

### Command-line Options

The dashboard runner supports the following options:

```
usage: run_dashboard.py [-h] [--api-host API_HOST] [--api-port API_PORT] [--ui-host UI_HOST] [--ui-port UI_PORT] [--debug]

Run the FXML4 Dashboard

options:
  -h, --help           show this help message and exit
  --api-host API_HOST  API server host
  --api-port API_PORT  API server port
  --ui-host UI_HOST    UI server host
  --ui-port UI_PORT    UI server port
  --debug              Enable debug mode
```

## Using the Dashboard

### Backtest Runner

1. Select a symbol, timeframe, and strategy
2. Set the backtest period and initial capital
3. Configure strategy-specific parameters in the "Advanced Parameters" section
4. Click "Run Backtest" to start the backtest
5. View summary results and charts
6. Access the full performance report via the provided link

### Performance Analysis

1. Select a backtest from the dropdown menu
2. View key performance metrics in the "Overview" tab
3. Analyze returns distribution in the "Returns" tab
4. Examine drawdowns in the "Drawdowns" tab
5. Review trade statistics in the "Trade Analysis" tab
6. Explore Monte Carlo simulation results in the "Monte Carlo" tab

### Strategy Comparison

1. Select multiple backtests to compare
2. Choose the metrics to include in the comparison
3. Click "Compare Strategies" to generate the comparison
4. View the metrics table, radar chart, and individual metric charts
5. Analyze the correlation matrix to identify diversification opportunities

### Reports

1. Browse available performance reports
2. View HTML reports in the browser
3. Download PDF reports for offline viewing or sharing

## API Integration

The dashboard's API can be used programmatically in custom scripts or external applications. See the [API Reference](/docs/api-reference/api/index.md) for detailed documentation of available endpoints.

Example:

```python
import requests

# Run a backtest
response = requests.post(
    "http://localhost:8000/backtest",
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
        }
    }
)

backtest_result = response.json()
print(f"Backtest ID: {backtest_result['backtest_id']}")
print(f"Total Return: {backtest_result['total_return_pct']}%")
```

### Using the Built-in API Client

The dashboard includes a built-in API client that simplifies API interactions:

```python
from fxml4.ui.dashboard import ApiClient

# Create API client
client = ApiClient()

# Check API health
health = client.get_health()

# Run a backtest
result = client.run_backtest(
    symbol="EURUSD",
    timeframe="1h",
    strategy="ml_strategy",
    start_date="2023-01-01",
    end_date="2023-12-31",
    initial_capital=10000.0,
    parameters={"model": "random_forest", "features": ["technical", "volatility"]}
)

# Get performance metrics
metrics = client.get_performance_metrics(
    backtest_id=result["backtest_id"],
    include_trades=True,
    include_equity_curve=True
)

# Compare strategies
comparison = client.compare_backtests(
    backtest_ids=[result1["backtest_id"], result2["backtest_id"]],
    metrics=["total_return_pct", "max_drawdown_pct", "sharpe_ratio"]
)
```

## Customization

### Configuration

The dashboard's behavior can be customized through the configuration file (`config/default.yaml`):

```yaml
# API Configuration
api:
  host: "0.0.0.0"
  port: 8000
  debug: false
  enable_docs: true
  cors_origins:
    - "*"

# UI Configuration
ui:
  host: "0.0.0.0"
  port: 8501
  theme: "dark"
  features:
    backtest_visualization: true
    live_dashboard: true
    strategy_editor: true
    performance_metrics: true
```

### Adding Custom Strategies

To add a custom strategy:

1. Implement the strategy in the appropriate module
2. Update the UI to include the new strategy in the dropdown
3. Add strategy-specific parameters to the UI if needed

## Troubleshooting

- **API Connection Error**: Ensure the API server is running and accessible from the UI host
- **Missing Dependencies**: Verify that all required packages are installed
- **Port Conflicts**: If ports are already in use, specify alternative ports using the command-line options
