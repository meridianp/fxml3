# Python API Examples

This guide provides comprehensive examples of using the FXML4 API with Python.

## Installation

```bash
pip install fxml4-api-client
# or install from source
pip install -e /path/to/fxml4/fxml4/api/client
```

## Basic Usage

### Synchronous Client

```python
from fxml4.api.client import FXML4Client
from datetime import datetime, timedelta

# Initialize client
client = FXML4Client(
    base_url="https://api.fxml4.com",
    api_key="your-api-key",
    version="v2"
)

# Get market data
data = client.get_data(
    symbol="EURUSD",
    timeframe="1h",
    start_date=datetime.now() - timedelta(days=30),
    end_date=datetime.now()
)

print(f"Retrieved {len(data['items'])} data points")
```

### Asynchronous Client

```python
import asyncio
from fxml4.api.client import AsyncFXML4Client

async def main():
    async with AsyncFXML4Client(api_key="your-api-key") as client:
        # Get data
        data = await client.get_data(
            symbol="EURUSD",
            timeframe="1h",
            start_date="2023-01-01",
            end_date="2023-12-31"
        )

        # Generate signals
        signals = await client.generate_signals(
            symbol="EURUSD",
            timeframe="1h",
            strategy="ml_strategy",
            confidence_threshold=0.8
        )

        print(f"Found {len(signals['signals'])} signals")

asyncio.run(main())
```

## Advanced Examples

### 1. Real-time Signal Streaming

```python
import asyncio
from fxml4.api.client import AsyncFXML4Client

async def stream_signals():
    async with AsyncFXML4Client(api_key="your-api-key") as client:
        # Connect to WebSocket
        async for signal in client.connect_websocket("signals", "EURUSD"):
            print(f"New signal: {signal['data']['signal_type']} at {signal['data']['price']}")

            # Process signal
            if signal['data']['confidence'] > 0.8:
                print("High confidence signal detected!")
                # Place trade logic here

asyncio.run(stream_signals())
```

### 2. Batch Operations

```python
# Execute multiple operations efficiently
operations = [
    {
        "id": "op1",
        "type": "data",
        "params": {
            "symbol": "EURUSD",
            "timeframe": "1h",
            "start_date": "2023-01-01T00:00:00Z",
            "end_date": "2023-01-31T23:59:59Z"
        }
    },
    {
        "id": "op2",
        "type": "signals",
        "params": {
            "symbol": "GBPUSD",
            "timeframe": "1h",
            "strategy": "ml_strategy"
        }
    },
    {
        "id": "op3",
        "type": "backtest",
        "params": {
            "symbol": "USDJPY",
            "timeframe": "1h",
            "strategy": "wave_strategy",
            "start_date": "2023-01-01T00:00:00Z",
            "end_date": "2023-12-31T23:59:59Z"
        }
    }
]

results = client.batch(operations)

for result in results["results"]:
    if result["status"] == "success":
        print(f"Operation {result['id']} completed successfully")
    else:
        print(f"Operation {result['id']} failed: {result['error']}")
```

### 3. Advanced Backtesting

```python
# Run backtest with Monte Carlo simulation
result = client.run_backtest(
    symbol="EURUSD",
    timeframe="1h",
    strategy=["ml_strategy", "wave_strategy"],  # Multiple strategies
    start_date="2023-01-01",
    end_date="2023-12-31",
    initial_capital=10000,
    commission=0.0002,
    slippage=0.0001,
    position_size=0.02,
    max_positions=5,
    parameters={
        "ml_model": "xgboost",
        "confidence_threshold": 0.7,
        "ensemble_method": "voting"
    },
    monte_carlo=True,
    walk_forward=True
)

# Analyze results
performance = result["performance"]
print(f"Total Return: {performance['total_return_pct']:.2f}%")
print(f"Sharpe Ratio: {performance['sharpe_ratio']:.2f}")
print(f"Max Drawdown: {performance['max_drawdown_pct']:.2f}%")

# Monte Carlo results
if "monte_carlo" in result:
    mc = result["monte_carlo"]
    print(f"Probability of Profit: {mc['probability_of_profit']:.1%}")
    print(f"95% Confidence Return Range: {mc['confidence_intervals']['return_95']}")
```

### 4. Data Analysis with Pandas

```python
import pandas as pd
import matplotlib.pyplot as plt

# Get data with indicators
data_response = client.get_data(
    symbol="EURUSD",
    timeframe="1h",
    start_date="2023-01-01",
    end_date="2023-12-31",
    include_indicators=["sma_20", "sma_50", "rsi_14", "macd"]
)

# Convert to DataFrame
df = pd.DataFrame(data_response["items"])
df['timestamp'] = pd.to_datetime(df['timestamp'])
df.set_index('timestamp', inplace=True)

# Plot price with indicators
fig, (ax1, ax2, ax3) = plt.subplots(3, 1, figsize=(12, 10), sharex=True)

# Price and moving averages
ax1.plot(df.index, df['close'], label='Close', linewidth=2)
ax1.plot(df.index, df['indicators'].apply(lambda x: x.get('sma_20')), label='SMA 20', alpha=0.7)
ax1.plot(df.index, df['indicators'].apply(lambda x: x.get('sma_50')), label='SMA 50', alpha=0.7)
ax1.set_ylabel('Price')
ax1.legend()
ax1.grid(True, alpha=0.3)

# RSI
ax2.plot(df.index, df['indicators'].apply(lambda x: x.get('rsi_14')), label='RSI 14', color='orange')
ax2.axhline(y=70, color='r', linestyle='--', alpha=0.5)
ax2.axhline(y=30, color='g', linestyle='--', alpha=0.5)
ax2.set_ylabel('RSI')
ax2.set_ylim(0, 100)
ax2.legend()
ax2.grid(True, alpha=0.3)

# Volume
ax3.bar(df.index, df['volume'], alpha=0.5)
ax3.set_ylabel('Volume')
ax3.set_xlabel('Date')
ax3.grid(True, alpha=0.3)

plt.tight_layout()
plt.show()
```

### 5. Signal Analysis

```python
# Get signals with filtering
signals_response = client.generate_signals(
    symbol="EURUSD",
    timeframe="1h",
    strategy="ml_strategy",
    lookback_periods=1000,
    confidence_threshold=0.75,
    parameters={
        "model": "ensemble",
        "feature_selection": "auto",
        "risk_adjusted": True
    }
)

# Analyze signal distribution
signals_df = pd.DataFrame(signals_response["signals"])

# Signal type distribution
signal_counts = signals_df['signal_type'].value_counts()
print("Signal Distribution:")
print(signal_counts)

# Confidence analysis
print(f"\nAverage Confidence: {signals_df['confidence'].mean():.3f}")
print(f"High Confidence Signals (>0.8): {len(signals_df[signals_df['confidence'] > 0.8])}")

# Time-based analysis
signals_df['timestamp'] = pd.to_datetime(signals_df['timestamp'])
signals_df['hour'] = signals_df['timestamp'].dt.hour

hourly_signals = signals_df.groupby('hour')['confidence'].agg(['count', 'mean'])
print("\nSignals by Hour:")
print(hourly_signals)
```

### 6. Error Handling and Retry Logic

```python
import time
from fxml4.api.client import FXML4Client
from fxml4.api.client.exceptions import RateLimitError, ServerError

class RobustClient:
    def __init__(self, api_key):
        self.client = FXML4Client(api_key=api_key)
        self.max_retries = 3
        self.retry_delay = 1.0

    def get_data_with_retry(self, **kwargs):
        """Get data with automatic retry on failure."""
        for attempt in range(self.max_retries):
            try:
                return self.client.get_data(**kwargs)

            except RateLimitError as e:
                if attempt < self.max_retries - 1:
                    wait_time = e.retry_after or (self.retry_delay * (2 ** attempt))
                    print(f"Rate limited. Waiting {wait_time} seconds...")
                    time.sleep(wait_time)
                else:
                    raise

            except ServerError as e:
                if attempt < self.max_retries - 1:
                    wait_time = self.retry_delay * (2 ** attempt)
                    print(f"Server error. Retrying in {wait_time} seconds...")
                    time.sleep(wait_time)
                else:
                    raise

            except Exception as e:
                print(f"Unexpected error: {e}")
                raise

        return None

# Usage
robust_client = RobustClient(api_key="your-api-key")
data = robust_client.get_data_with_retry(
    symbol="EURUSD",
    timeframe="1h",
    start_date="2023-01-01",
    end_date="2023-12-31"
)
```

### 7. Portfolio Analysis

```python
# Analyze multiple symbols
symbols = ["EURUSD", "GBPUSD", "USDJPY", "AUDUSD"]
portfolio_results = {}

for symbol in symbols:
    # Run backtest for each symbol
    result = client.run_backtest(
        symbol=symbol,
        timeframe="1h",
        strategy="ml_strategy",
        start_date="2023-01-01",
        end_date="2023-12-31",
        initial_capital=10000 / len(symbols),  # Equal allocation
        parameters={
            "risk_level": "medium",
            "stop_loss_pct": 0.02,
            "take_profit_pct": 0.04
        }
    )

    portfolio_results[symbol] = result

# Calculate portfolio metrics
total_return = sum(r["performance"]["total_return"] for r in portfolio_results.values())
total_initial = sum(r["performance"]["initial_capital"] for r in portfolio_results.values())
portfolio_return_pct = (total_return / total_initial) * 100

print(f"Portfolio Total Return: ${total_return:.2f} ({portfolio_return_pct:.2f}%)")

# Correlation analysis
correlations = {}
for s1 in symbols:
    for s2 in symbols:
        if s1 != s2:
            # Calculate correlation between returns
            # This is simplified - in practice, you'd calculate from equity curves
            correlations[f"{s1}-{s2}"] = 0.5  # Placeholder

print("\nPortfolio Correlations:")
for pair, corr in correlations.items():
    print(f"{pair}: {corr:.3f}")
```

### 8. Custom Strategy Testing

```python
# Define custom strategy parameters
custom_strategy_params = {
    "entry_rules": {
        "rsi_oversold": 30,
        "rsi_overbought": 70,
        "trend_filter": "sma_200",
        "volume_confirmation": True
    },
    "exit_rules": {
        "profit_target": 0.03,
        "stop_loss": 0.015,
        "trailing_stop": True,
        "time_exit": 72  # hours
    },
    "risk_management": {
        "max_risk_per_trade": 0.02,
        "max_daily_loss": 0.06,
        "max_correlation": 0.7
    }
}

# Run backtest with custom strategy
result = client.run_backtest(
    symbol="EURUSD",
    timeframe="1h",
    strategy="custom_strategy",
    start_date="2023-01-01",
    end_date="2023-12-31",
    parameters=custom_strategy_params,
    monte_carlo=True
)

# Get detailed report
report = client.get_backtest_report(
    backtest_id=result["backtest_id"],
    format="json"
)

# Analyze trade statistics
trades = report.get("trades", [])
winning_trades = [t for t in trades if t["pnl"] > 0]
losing_trades = [t for t in trades if t["pnl"] < 0]

print(f"Win Rate: {len(winning_trades) / len(trades) * 100:.1f}%")
print(f"Average Win: ${sum(t['pnl'] for t in winning_trades) / len(winning_trades):.2f}")
print(f"Average Loss: ${sum(t['pnl'] for t in losing_trades) / len(losing_trades):.2f}")
```

## Best Practices

1. **Always use context managers** with async client
2. **Implement proper error handling** for all API calls
3. **Use pagination** for large data requests
4. **Cache frequently accessed data** to reduce API calls
5. **Monitor rate limits** and implement backoff strategies
6. **Use batch operations** when making multiple requests
7. **Subscribe to WebSockets** for real-time updates instead of polling

## Troubleshooting

### Common Issues

1. **Authentication Errors**
   ```python
   # Check if token is expired
   try:
       client.health_check()
   except AuthenticationError:
       # Refresh token
       client._authenticate()
   ```

2. **Rate Limiting**
   ```python
   # Use exponential backoff
   def exponential_backoff(func, max_retries=5):
       for i in range(max_retries):
           try:
               return func()
           except RateLimitError as e:
               if i == max_retries - 1:
                   raise
               wait_time = min(60, 2 ** i)
               time.sleep(wait_time)
   ```

3. **Large Data Requests**
   ```python
   # Use pagination and date chunking
   def get_large_dataset(symbol, start_date, end_date):
       all_data = []
       current_date = start_date
       chunk_size = timedelta(days=30)

       while current_date < end_date:
           chunk_end = min(current_date + chunk_size, end_date)

           page = 1
           while True:
               response = client.get_data(
                   symbol=symbol,
                   timeframe="1h",
                   start_date=current_date,
                   end_date=chunk_end,
                   page=page,
                   page_size=1000
               )

               all_data.extend(response["items"])

               if not response["meta"]["has_next"]:
                   break
               page += 1

           current_date = chunk_end

       return all_data
   ```
