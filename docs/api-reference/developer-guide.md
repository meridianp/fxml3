# FXML4 API Developer Guide

This document provides guidance for developers integrating with the FXML4 API, including best practices, examples, and troubleshooting tips.

## Getting Started

### Prerequisites

To use the FXML4 API, you'll need:

1. API access credentials (username and password)
2. A programming language or tool capable of making HTTP requests

### API Overview

The FXML4 API provides the following capabilities:

- Market data retrieval
- Trading signal generation
- Backtesting with performance analytics
- Performance comparison and reporting

### Base URL

The base URL for the API depends on your deployment:

- Local development: `http://localhost:8000`
- Docker deployment: `http://localhost:8000` (or configured port)
- Production: `https://api.yourdomain.com` (replace with your actual domain)

## Authentication

The API uses JWT (JSON Web Token) authentication:

1. First, obtain a token using your credentials
2. Then, include the token in the `Authorization` header for subsequent requests

### Example: Obtaining a Token

```python
import requests

# Get token
response = requests.post(
    "http://localhost:8000/token",
    data={
        "username": "user",
        "password": "password"
    }
)

if response.status_code == 200:
    token = response.json()["access_token"]
    print(f"Token obtained: {token[:10]}...")
else:
    print(f"Error: {response.status_code} - {response.text}")
```

### Example: Using the Token

```python
import requests

# Assuming you have a token from the previous step
token = "your_token_here"

# Make an authenticated request
response = requests.post(
    "http://localhost:8000/data",
    headers={
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    },
    json={
        "symbol": "GBPUSD",
        "timeframe": "1h",
        "limit": 100
    }
)

if response.status_code == 200:
    data = response.json()
    print(f"Received {len(data['data'])} data points")
else:
    print(f"Error: {response.status_code} - {response.text}")
```

## Best Practices

### Token Management

- Store tokens securely (never in client-side code)
- Implement token refresh logic to handle expiration
- Don't share tokens between users or applications

### Error Handling

- Always check response status codes
- Implement retry logic for 429 Too Many Requests responses
- Log detailed error information for troubleshooting

```python
def make_api_request(url, method="GET", data=None, headers=None, max_retries=3):
    """Make an API request with retry logic."""
    import time

    for attempt in range(max_retries):
        try:
            if method.upper() == "GET":
                response = requests.get(url, headers=headers)
            elif method.upper() == "POST":
                response = requests.post(url, json=data, headers=headers)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")

            # Handle rate limiting
            if response.status_code == 429:
                retry_after = int(response.headers.get("Retry-After", 60))
                print(f"Rate limited, retrying after {retry_after} seconds")
                time.sleep(retry_after)
                continue

            # Return successful response
            response.raise_for_status()  # Raise exception for 4XX/5XX
            return response.json()

        except requests.exceptions.RequestException as e:
            if attempt < max_retries - 1:
                wait_time = 2 ** attempt  # Exponential backoff
                print(f"Request failed, retrying in {wait_time} seconds: {e}")
                time.sleep(wait_time)
            else:
                print(f"Request failed after {max_retries} attempts: {e}")
                raise

    return None
```

### Rate Limiting

- Implement client-side rate limiting to stay under limits
- Use exponential backoff for retries
- Consider caching frequently accessed data

### Backtesting Best Practices

1. Always specify a reasonable date range
2. Start with small date ranges to validate strategies
3. Save backtest IDs for later comparison
4. Use the performance metrics and reports for detailed analysis

```python
import requests
import json
from datetime import datetime, timedelta

def run_backtest(token, symbol, timeframe, strategy, days=30):
    """Run a backtest for the specified number of days from today."""
    end_date = datetime.now().strftime("%Y-%m-%d")
    start_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")

    response = requests.post(
        "http://localhost:8000/backtest",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        },
        json={
            "symbol": symbol,
            "timeframe": timeframe,
            "strategy": strategy,
            "start_date": start_date,
            "end_date": end_date,
            "initial_capital": 10000.0,
            "parameters": {
                "risk_pct": 0.02
            }
        }
    )

    if response.status_code == 200:
        result = response.json()
        print(f"Backtest ID: {result['backtest_id']}")
        print(f"Total Return: {result['total_return_pct']:.2f}%")
        print(f"Sharpe Ratio: {result['sharpe_ratio']:.2f}")
        print(f"Max Drawdown: {result['max_drawdown_pct']:.2f}%")

        # Save results to file
        with open(f"backtest_{result['backtest_id']}.json", "w") as f:
            json.dump(result, f, indent=2)

        return result['backtest_id']
    else:
        print(f"Error: {response.status_code} - {response.text}")
        return None
```

## Common Tasks

### Retrieving Historical Data

```python
def get_historical_data(token, symbol, timeframe, start_date=None, end_date=None, limit=1000):
    """Get historical data for a symbol."""
    request_data = {
        "symbol": symbol,
        "timeframe": timeframe,
        "limit": limit
    }

    if start_date:
        request_data["start_date"] = start_date

    if end_date:
        request_data["end_date"] = end_date

    response = requests.post(
        "http://localhost:8000/data",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        },
        json=request_data
    )

    if response.status_code == 200:
        result = response.json()

        # Convert to pandas DataFrame for analysis
        import pandas as pd

        if result["data"]:
            df = pd.DataFrame(result["data"])
            df["timestamp"] = pd.to_datetime(df["timestamp"])
            df.set_index("timestamp", inplace=True)
            return df
        else:
            print("No data returned")
            return pd.DataFrame()
    else:
        print(f"Error: {response.status_code} - {response.text}")
        return None
```

### Generating Trading Signals

```python
def generate_signals(token, symbol, timeframe, strategy, parameters=None):
    """Generate trading signals using the specified strategy."""
    request_data = {
        "symbol": symbol,
        "timeframe": timeframe,
        "strategy": strategy
    }

    if parameters:
        request_data["parameters"] = parameters

    response = requests.post(
        "http://localhost:8000/signals",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        },
        json=request_data
    )

    if response.status_code == 200:
        result = response.json()
        signals = result.get("signals", [])

        if signals:
            print(f"Generated {len(signals)} signals:")
            for signal in signals:
                print(f"  {signal['timestamp']} - {signal['signal_type']} at {signal['price']} (confidence: {signal['confidence']:.2f})")
        else:
            print("No signals generated")

        return signals
    else:
        print(f"Error: {response.status_code} - {response.text}")
        return None
```

### Comparing Multiple Backtests

```python
def compare_backtests(token, backtest_ids, metrics=None):
    """Compare multiple backtests."""
    if metrics is None:
        metrics = ["total_return_pct", "max_drawdown_pct", "sharpe_ratio", "sortino_ratio", "win_rate"]

    response = requests.post(
        "http://localhost:8000/performance/compare",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        },
        json={
            "backtest_ids": backtest_ids,
            "metrics": metrics
        }
    )

    if response.status_code == 200:
        result = response.json()

        # Print comparison table
        print("\nBacktest Comparison:")

        # Print header
        header = "Metric".ljust(20)
        for backtest_id in backtest_ids:
            header += backtest_id[-8:].ljust(15)
        print(header)
        print("-" * 80)

        # Print metrics
        for metric in metrics:
            row = metric.ljust(20)
            for backtest_id in backtest_ids:
                value = result["metrics"][metric].get(backtest_id, "N/A")
                if isinstance(value, (int, float)):
                    row += f"{value:.2f}".ljust(15)
                else:
                    row += str(value).ljust(15)
            print(row)

        # Print ranking
        print("\nRanking (best to worst):")
        for metric in metrics:
            ranks = result["ranking"].get(metric, [])
            print(f"{metric}:".ljust(20), " > ".join([id[-8:] for id in ranks]))

        return result
    else:
        print(f"Error: {response.status_code} - {response.text}")
        return None
```

## Troubleshooting

### Common Issues

#### Authentication Problems

- **Issue**: 401 Unauthorized responses
- **Solution**:
  - Verify your credentials
  - Check that your token is valid and not expired
  - Ensure you're including the token in the correct format (`Bearer <token>`)

#### Rate Limiting

- **Issue**: 429 Too Many Requests responses
- **Solution**:
  - Implement exponential backoff retries
  - Reduce request frequency
  - Cache results when possible

#### Data Retrieval Issues

- **Issue**: Empty data responses
- **Solution**:
  - Check that the symbol exists and is supported
  - Verify the date range is valid
  - Ensure the timeframe is supported

#### Backtest Errors

- **Issue**: 500 Internal Server Error during backtesting
- **Solution**:
  - Try a smaller date range
  - Verify strategy parameters are valid
  - Check for missing data in the date range

### Debugging Tips

1. Enable debug logging in your client
2. Check response headers for additional information
3. Use smaller data samples for testing
4. Validate request JSON before sending

## Code Examples

### Complete Python Client Example

```python
import requests
import pandas as pd
import json
from datetime import datetime, timedelta
import time
import os

class FXML4Client:
    """Python client for the FXML4 API."""

    def __init__(self, base_url="http://localhost:8000"):
        self.base_url = base_url
        self.token = None

    def login(self, username, password):
        """Log in and get a token."""
        response = requests.post(
            f"{self.base_url}/token",
            data={"username": username, "password": password}
        )

        if response.status_code == 200:
            self.token = response.json()["access_token"]
            return True
        else:
            print(f"Login failed: {response.status_code} - {response.text}")
            return False

    def _get_headers(self):
        """Get request headers with authentication."""
        if not self.token:
            raise ValueError("Not logged in. Call login() first.")

        return {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json"
        }

    def get_data(self, symbol, timeframe, start_date=None, end_date=None, limit=1000):
        """Get historical data."""
        request_data = {
            "symbol": symbol,
            "timeframe": timeframe,
            "limit": limit
        }

        if start_date:
            request_data["start_date"] = start_date

        if end_date:
            request_data["end_date"] = end_date

        response = requests.post(
            f"{self.base_url}/data",
            headers=self._get_headers(),
            json=request_data
        )

        if response.status_code == 200:
            result = response.json()

            # Convert to pandas DataFrame
            if result["data"]:
                df = pd.DataFrame(result["data"])
                df["timestamp"] = pd.to_datetime(df["timestamp"])
                df.set_index("timestamp", inplace=True)
                return df
            else:
                return pd.DataFrame()
        else:
            print(f"Error getting data: {response.status_code} - {response.text}")
            return None

    def generate_signals(self, symbol, timeframe, strategy, parameters=None):
        """Generate trading signals."""
        request_data = {
            "symbol": symbol,
            "timeframe": timeframe,
            "strategy": strategy
        }

        if parameters:
            request_data["parameters"] = parameters

        response = requests.post(
            f"{self.base_url}/signals",
            headers=self._get_headers(),
            json=request_data
        )

        if response.status_code == 200:
            return response.json().get("signals", [])
        else:
            print(f"Error generating signals: {response.status_code} - {response.text}")
            return None

    def run_backtest(self, symbol, timeframe, strategy, start_date, end_date,
                    initial_capital=10000.0, parameters=None, auto_report=True):
        """Run a backtest."""
        request_data = {
            "symbol": symbol,
            "timeframe": timeframe,
            "strategy": strategy,
            "start_date": start_date,
            "end_date": end_date,
            "initial_capital": initial_capital,
            "auto_report": auto_report
        }

        if parameters:
            request_data["parameters"] = parameters

        response = requests.post(
            f"{self.base_url}/backtest",
            headers=self._get_headers(),
            json=request_data
        )

        if response.status_code == 200:
            return response.json()
        else:
            print(f"Error running backtest: {response.status_code} - {response.text}")
            return None

    def get_performance_metrics(self, backtest_id, include_trades=False, include_equity_curve=False):
        """Get performance metrics for a backtest."""
        params = {
            "include_trades": "true" if include_trades else "false",
            "include_equity_curve": "true" if include_equity_curve else "false"
        }

        response = requests.get(
            f"{self.base_url}/performance/metrics/{backtest_id}",
            headers=self._get_headers(),
            params=params
        )

        if response.status_code == 200:
            return response.json()
        else:
            print(f"Error getting metrics: {response.status_code} - {response.text}")
            return None

    def download_report(self, backtest_id, format="html", output_path=None):
        """Download a performance report."""
        if not output_path:
            output_path = f"report_{backtest_id}.{format}"

        response = requests.get(
            f"{self.base_url}/performance/report/{backtest_id}",
            headers=self._get_headers(),
            params={"format": format},
            stream=True
        )

        if response.status_code == 200:
            with open(output_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)

            print(f"Report downloaded to {output_path}")
            return output_path
        else:
            print(f"Error downloading report: {response.status_code} - {response.text}")
            return None

    def compare_backtests(self, backtest_ids, metrics=None):
        """Compare multiple backtests."""
        if metrics is None:
            metrics = ["total_return_pct", "max_drawdown_pct", "sharpe_ratio", "sortino_ratio", "win_rate"]

        response = requests.post(
            f"{self.base_url}/performance/compare",
            headers=self._get_headers(),
            json={
                "backtest_ids": backtest_ids,
                "metrics": metrics
            }
        )

        if response.status_code == 200:
            return response.json()
        else:
            print(f"Error comparing backtests: {response.status_code} - {response.text}")
            return None
```

### Example Usage

```python
# Create client and login
client = FXML4Client()
if client.login("user", "password"):
    print("Logged in successfully")

    # Get historical data
    df = client.get_data("GBPUSD", "1h", start_date="2023-01-01", end_date="2023-01-31")
    if df is not None:
        print(f"Retrieved {len(df)} data points")
        print(df.head())

    # Run a backtest
    backtest_result = client.run_backtest(
        symbol="GBPUSD",
        timeframe="1h",
        strategy="integrated_strategy",
        start_date="2023-01-01",
        end_date="2023-01-31",
        parameters={"risk_pct": 0.02}
    )

    if backtest_result:
        backtest_id = backtest_result["backtest_id"]
        print(f"Backtest ID: {backtest_id}")
        print(f"Total Return: {backtest_result['total_return_pct']:.2f}%")

        # Download the report
        client.download_report(backtest_id)

        # Run another backtest with different parameters
        backtest_result2 = client.run_backtest(
            symbol="GBPUSD",
            timeframe="1h",
            strategy="integrated_strategy",
            start_date="2023-01-01",
            end_date="2023-01-31",
            parameters={"risk_pct": 0.03}
        )

        if backtest_result2:
            backtest_id2 = backtest_result2["backtest_id"]

            # Compare the backtests
            comparison = client.compare_backtests(
                [backtest_id, backtest_id2],
                metrics=["total_return_pct", "max_drawdown_pct", "sharpe_ratio"]
            )

            if comparison:
                print("\nComparison Results:")
                for metric in ["total_return_pct", "max_drawdown_pct", "sharpe_ratio"]:
                    print(f"{metric}:")
                    for bt_id in [backtest_id, backtest_id2]:
                        value = comparison["metrics"][metric].get(bt_id, "N/A")
                        print(f"  {bt_id}: {value:.2f}")
```

## API Enhancements in Development

These features are planned for future API releases:

1. Webhook notifications for signal generation
2. Streaming data support
3. More authentication methods (API keys, OAuth)
4. Expanded strategy parameter customization
5. Custom indicator support

## Getting Help

If you encounter issues or have questions:

1. Check the API reference documentation
2. Look for similar issues in the troubleshooting section
3. Contact support at [support@yourdomain.com](mailto:support@yourdomain.com)
