# Quick Start

This guide will help you quickly get started with FXML4. We'll walk through setting up the environment, fetching data, and running a simple backtest.

## Prerequisites

Before starting, make sure you have:

- Completed the [installation](installation.md) process
- Set up Interactive Brokers TWS (for live/paper trading)

## Basic Usage

### Import Key Modules

```python
import pandas as pd
from datetime import datetime, timedelta

# Data engineering
from fxml4.data_engineering.data_feeds.ib_feed import IBDataFeed
from fxml4.data_engineering.data_feeds.base_feed import DataFeedFactory

# Strategy
from fxml4.strategy.integrated_strategy import IntegratedStrategy

# Backtesting
from fxml4.backtesting.backtest_engine import BacktestEngine
```

### Fetching Market Data

First, let's fetch some historical data for GBP/USD using the Interactive Brokers data feed:

```python
# Configure the IB data feed for paper trading
config = {
    "port": 7497,  # Paper trading port
    "client_id": 0,
    "timeout": 30
}

# Create and connect to the data feed
feed = IBDataFeed(config)
feed.connect()

try:
    # Fetch 1-hour data for GBP/USD for the past month
    end_date = datetime.now()
    start_date = end_date - timedelta(days=30)

    df = feed.fetch_data(
        symbol="GBP.USD",
        timeframe="1h",
        start_date=start_date,
        end_date=end_date
    )

    # Print the first few rows
    print(df.head())

    # Save to CSV (optional)
    df.to_csv("gbpusd_1h_data.csv")

finally:
    # Always disconnect when done
    feed.disconnect()
```

### Creating a Simple Strategy

Now, let's create a simple moving average crossover strategy:

```python
from fxml4.strategy.strategy_base import Strategy
import numpy as np

class MovingAverageCrossover(Strategy):
    def __init__(self, config=None):
        config = config or {}
        self.fast_period = config.get("fast_period", 10)
        self.slow_period = config.get("slow_period", 30)

    def generate_signals(self, data):
        # Calculate moving averages
        data['fast_ma'] = data['close'].rolling(self.fast_period).mean()
        data['slow_ma'] = data['close'].rolling(self.slow_period).mean()

        # Generate signals (1 for buy, -1 for sell, 0 for hold)
        data['signal'] = 0
        data.loc[data['fast_ma'] > data['slow_ma'], 'signal'] = 1
        data.loc[data['fast_ma'] < data['slow_ma'], 'signal'] = -1

        # Generate entry/exit signals
        data['entry_long'] = (data['signal'] == 1) & (data['signal'].shift(1) != 1)
        data['exit_long'] = (data['signal'] != 1) & (data['signal'].shift(1) == 1)
        data['entry_short'] = (data['signal'] == -1) & (data['signal'].shift(1) != -1)
        data['exit_short'] = (data['signal'] != -1) & (data['signal'].shift(1) == -1)

        return data
```

### Running a Backtest

Now, let's run a backtest using our moving average strategy:

```python
# Create the strategy with custom parameters
strategy = MovingAverageCrossover({
    "fast_period": 5,
    "slow_period": 20
})

# Generate signals
data_with_signals = strategy.generate_signals(df.copy())

# Configure the backtest
backtest_config = {
    "initial_capital": 10000,
    "position_size": 0.1,  # 10% of capital per trade
    "commission": 0.0001,  # 1 pip commission
    "slippage": 0.0001     # 1 pip slippage
}

# Create and run the backtest
backtest = BacktestEngine(backtest_config)
results = backtest.run(data_with_signals)

# Display results
print(f"Final portfolio value: ${results['final_value']:.2f}")
print(f"Total return: {results['total_return']:.2%}")
print(f"Sharpe ratio: {results['sharpe_ratio']:.2f}")
print(f"Max drawdown: {results['max_drawdown']:.2%}")
print(f"Win rate: {results['win_rate']:.2%}")

# Plot equity curve
backtest.plot_equity_curve()
```

## Using the Integrated Strategy

FXML4 provides an `IntegratedStrategy` that combines multiple signal generators:

```python
from fxml4.ml.features import create_technical_features
from fxml4.strategy.integrated_strategy import IntegratedStrategy
from fxml4.wave_analysis.elliott_wave import ElliottWaveAnalyzer

# Create signal generators
ml_config = {"model_path": "models/gbpusd_model.pkl"}
wave_config = {"min_wave_length": 5}

# Prepare the data with features
data = create_technical_features(df.copy())

# Create and configure the integrated strategy
strategy = IntegratedStrategy({
    "ml_weight": 0.6,
    "wave_weight": 0.4,
    "signal_threshold": 0.7
})

# Generate signals
signals = strategy.generate_signals(data)

# Run backtest
backtest = BacktestEngine(backtest_config)
results = backtest.run(signals)

# Display results
print(f"Integrated strategy performance:")
print(f"Total return: {results['total_return']:.2%}")
print(f"Sharpe ratio: {results['sharpe_ratio']:.2f}")
```

## Next Steps

Now that you've got a basic understanding of FXML4, you can:

1. Learn how to [set up Interactive Brokers](../tutorials/ib-api-integration.md) for real-time data and trading
2. Explore [creating custom strategies](../tutorials/custom-strategies.md)
3. Understand the [architecture](../architecture.md) of FXML4
4. Check out the [API reference](../api-reference/data-engineering/data-feeds.md) for detailed documentation
