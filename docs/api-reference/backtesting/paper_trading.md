# Paper Trading with Interactive Brokers

This guide explains how to use the FXML4 paper trading module to trade with Interactive Brokers in a simulated environment.

## Overview

The paper trading module connects to Interactive Brokers (IB) TWS or IB Gateway to:

1. Receive real-time market data
2. Process tick data into candles
3. Generate trading signals using various signal generators
4. Execute paper trades with realistic fill simulations
5. Track portfolio performance in real-time

This provides a bridge between backtesting and live trading, allowing you to test your strategies with real market data without risking real money.

## Prerequisites

Before using the paper trading module, you need:

1. Interactive Brokers account (paper trading account is sufficient)
2. TWS (Trader Workstation) or IB Gateway installed and running
3. API connections enabled in TWS/IB Gateway settings
4. IB API Python client installed (`pip install ibapi`)

## Paper Trading Engine

The `PaperTradingEngine` class is the core component of the paper trading system. It handles:

- Connection to Interactive Brokers
- Market data subscription and processing
- Signal generation and management
- Order execution simulation
- Position and portfolio tracking
- Performance reporting

### Basic Usage

```python
from fxml4.backtesting.paper_trading import PaperTradingEngine
from fxml4.strategy.gbpusd_signal_generator import GBPUSDSignalGenerator

# Create signal generators
generators = [GBPUSDSignalGenerator()]

# Configure the paper trading engine
config = {
    "symbols": ["GBPUSD"],
    "timeframes": ["1m", "5m", "15m", "1h", "4h"],
    "signal_timeframe": "1h",
    "initial_capital": 10000.0,
    "signal_generators": generators,
    "ib_config": {
        "host": "127.0.0.1",
        "port": 7497,  # Paper trading port (7496 for live)
        "client_id": 1,
        "real_time_updates": True
    }
}

# Create and start the engine
engine = PaperTradingEngine(config)
engine.connect()
engine.start()

# Let it run for a while...
# ...

# Stop the engine when done
engine.stop()

# Get performance metrics
metrics = engine.get_performance_metrics()
print(f"Total Return: {metrics['total_return']:.2f}%")
print(f"Win Rate: {metrics['win_rate']:.1f}%")
```

## Configuration Options

The paper trading engine supports the following configuration options:

### Basic Configuration

- `symbols` - List of symbols to trade (e.g., `["GBPUSD", "EURUSD"]`)
- `timeframes` - List of timeframes to process (e.g., `["1m", "5m", "15m", "1h", "4h", "1d"]`)
- `base_timeframe` - Base timeframe for tick aggregation (default: `"1m"`)
- `signal_timeframe` - Timeframe for signal generation (default: `"1h"`)
- `initial_capital` - Initial capital for paper trading (default: `10000.0`)
- `max_positions` - Maximum number of concurrent positions (default: `5`)

### Risk Management

- `risk_config` - Dictionary with risk management settings:
  - `max_drawdown` - Maximum allowable drawdown percentage (e.g., `5.0`)
  - `risk_per_trade` - Risk per trade as percentage of equity (e.g., `0.01` for 1%)
  - `max_risk_multiplier` - Maximum multiplier for risk sizing (e.g., `1.5`)
  - `position_size_method` - Method for position sizing (`"risk_based"` or `"fixed"`)
- `risk_per_trade` - Risk per trade as percentage of equity (e.g., `0.01` for 1%)
- `stop_loss_pips` - Default stop loss distance in pips (e.g., `50`)
- `max_leverage` - Maximum leverage to use (e.g., `20.0`)

### Signal Generation

- `signal_generators` - List of signal generator instances
- `signal_cooldown` - Cooldown period in minutes between signals for same symbol (default: `60`)

### Interactive Brokers Connection

- `ib_config` - Dictionary with IB connection settings:
  - `host` - TWS/IB Gateway host (default: `"127.0.0.1"`)
  - `port` - TWS/IB Gateway port (default: `7497` for paper trading, `7496` for live)
  - `client_id` - Client ID for IB connection (default: `1`)
  - `real_time_updates` - Whether to enable real-time tick processing (default: `True`)
  - `update_interval` - How often to process ticks in seconds (default: `1.0`)
  - `tick_storage_limit` - Maximum number of ticks to store (default: `10000`)
  - `candle_storage_days` - Number of days of candle history to keep (default: `7`)

### Working Hours

- `working_hours` - Dictionary with trading hours settings:
  - `enabled` - Whether to enable trading hours restriction (default: `False`)
  - `start_time` - Trading start time in UTC (format: `"HH:MM"`, default: `"00:00"`)
  - `end_time` - Trading end time in UTC (format: `"HH:MM"`, default: `"23:59"`)
  - `weekend_trading` - Whether to allow weekend trading (default: `False`)

### Storage

- `enable_storage` - Whether to store trading results in database (default: `False`)

## Signal Generators

The paper trading engine uses signal generators to produce trading signals. You can use any of the existing signal generators or create custom ones. Some examples:

- `MLSignalGenerator` - Uses machine learning models to generate signals
- `GBPUSDSignalGenerator` - Specialized for GBP/USD trading
- `WaveSignalGenerator` - Uses Elliott Wave patterns for signal generation

Signal generators can be weighted to influence the importance of their signals in the final decision.

## Command-Line Example

The `paper_trading_example.py` script provides a command-line interface to the paper trading engine:

```bash
# Basic usage (trades GBPUSD by default)
python examples/paper_trading_example.py

# Specify symbols and timeframe
python examples/paper_trading_example.py --symbols EURUSD,GBPUSD --timeframe 4h

# Risk management settings
python examples/paper_trading_example.py --capital 25000 --risk-per-trade 1.5 --stop-loss-pips 30

# Use only specific signal generators
python examples/paper_trading_example.py --no-ml --no-gbpusd

# Enable trading hours restriction
python examples/paper_trading_example.py --working-hours --start-time 08:00 --end-time 16:00
```

## Database Integration

When `enable_storage` is set to `True`, the paper trading engine will store trading results in TimescaleDB. This requires running the migration script:

```bash
# Connect to TimescaleDB
docker exec -i timescaledb psql -U postgres -d fxml4 < db/migrations/005_add_paper_trading_schema.sql
```

The following tables will be created:

- `paper_trading_snapshots` - Periodic snapshots of portfolio status
- `paper_trading_fills` - Order fill events
- `paper_trading_trades` - Completed trades with P&L

Additionally, continuous aggregate views are created for daily performance metrics.

## Performance Metrics

The paper trading engine tracks various performance metrics:

- `total_return` - Total return percentage since inception
- `annualized_return` - Annualized return percentage
- `sharpe_ratio` - Risk-adjusted return ratio
- `max_drawdown` - Maximum drawdown percentage
- `win_rate` - Percentage of winning trades
- `profit_factor` - Ratio of gross profit to gross loss
- `total_trades` - Total number of completed trades

You can access these metrics using the `get_performance_metrics()` method.

## Risk Management

The paper trading engine implements risk management in several ways:

1. **Position Sizing** - Based on risk percentage and stop loss distance
2. **Maximum Positions** - Limits the number of concurrent positions
3. **Maximum Leverage** - Limits the leverage used per position
4. **Signal Cooldown** - Prevents overtrading by enforcing a cooldown period between signals
5. **Working Hours** - Optionally restricts trading to specific hours

## Best Practices

1. **Start Small** - Begin with low position sizes and limited symbols
2. **Verify Connection** - Use `test_ib_connection.py` to verify your IB connection first
3. **Monitor Carefully** - Regularly check logs and performance metrics
4. **Compare with Backtests** - Compare paper trading results with backtests
5. **Increase Gradually** - Once confident, gradually increase position sizes
6. **Use Paper Trading First** - Always start with paper trading before live trading
