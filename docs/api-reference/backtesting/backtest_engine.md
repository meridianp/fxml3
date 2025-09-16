# Backtest Engine

The `backtest_engine` module provides a backtesting system for trading strategies, allowing traders to test their strategies on historical data and evaluate performance.

## BacktestEngine Class

The `BacktestEngine` class is the main backtesting engine, providing a framework for running strategy backtests.

```python
from fxml4.backtesting.backtest_engine import BacktestEngine

# Initialize with configuration
engine = BacktestEngine({
    "initial_capital": 10000,
    "commission": 0.001,  # 0.1%
    "slippage": 0.0005,   # 0.05%
})

# Run a backtest
results = engine.run(
    strategy=my_strategy,
    data=historical_data,
    strategy_params={"symbol": "EURUSD"}
)

# Get performance metrics
metrics = results.get_performance_metrics()
print(metrics.summary())

# Generate a performance report
report_path = results.generate_report(
    output_dir="output/reports",
    include_figures=True
)
```

### Configuration Options

The `BacktestEngine` accepts a configuration dictionary with the following options:

- `initial_capital`: Initial capital for the backtest (default: 10000)
- `commission`: Commission rate (default: 0.0002, i.e., 0.02%)
- `slippage`: Slippage rate (default: 0.0001, i.e., 0.01%)

Additionally, you can configure automatic report generation in the YAML configuration:

```yaml
backtesting:
  # Other backtesting settings...
  reporting:
    auto_generate: true  # Automatically generate reports after backtests
    include_figures: true  # Include figures in auto-generated reports
    export_pdf: false  # Don't export to PDF by default
    output_dir: "output/reports"  # Directory for auto-generated reports
```

When `auto_generate` is set to `true`, performance reports will be automatically generated after each backtest completes.

### Strategy Function

The strategy function is called for each bar in the backtest and should return a dictionary of signals:

```python
def my_strategy(data, index, params):
    """Strategy function.

    Args:
        data: DataFrame of historical data up to current bar.
        index: Index of current bar.
        params: Strategy parameters.

    Returns:
        Dictionary of signals.
    """
    signals = {}

    # Entry signal
    if entry_condition(data, index):
        signals["entry"] = True
        signals["direction"] = "buy"  # or "sell"
        signals["risk_pct"] = 0.02  # Risk 2% of capital
        signals["stop_loss"] = stop_price  # Optional stop loss

    # Exit signal
    elif exit_condition(data, index):
        signals["exit"] = True

    return signals
```

## BacktestResult Class

The `BacktestResult` class encapsulates the results of a backtest and provides access to performance metrics.

### Basic Properties

- `strategy_name`: Name of the strategy
- `symbol`: Symbol that was traded
- `timeframe`: Timeframe that was used
- `start_date`: Start date of the backtest
- `end_date`: End date of the backtest
- `initial_capital`: Initial capital
- `final_capital`: Final capital
- `total_return`: Total return in currency units
- `total_return_pct`: Total return percentage
- `annualized_return`: Annualized return percentage
- `max_drawdown`: Maximum drawdown
- `max_drawdown_pct`: Maximum drawdown percentage
- `sharpe_ratio`: Sharpe ratio
- `sortino_ratio`: Sortino ratio
- `win_rate`: Win rate
- `profit_factor`: Profit factor
- `avg_profit_per_trade`: Average profit per winning trade
- `avg_loss_per_trade`: Average loss per losing trade
- `trades`: List of trades
- `equity_curve`: DataFrame with equity curve

### Advanced Properties

- `performance_metrics`: Comprehensive performance metrics object
- `drawdown_analysis`: DataFrame with detailed drawdown analysis
- `risk_analysis`: Dictionary with risk contribution analysis by various factors
- `monte_carlo_results`: Dictionary with Monte Carlo simulation results

### Methods

#### get_performance_metrics()

Returns the complete performance metrics object with comprehensive analytics.

```python
metrics = results.get_performance_metrics()
print(metrics.sharpe_ratio)
print(metrics.ulcer_index)
print(metrics.kelly_percentage)
```

#### get_summary()

Returns a formatted string with a summary of key performance metrics.

```python
summary = results.get_summary()
print(summary)
```

#### generate_report()

Generates an HTML report of backtest results, optionally exporting to PDF.

```python
report_path = results.generate_report(
    output_dir="output/reports",
    include_figures=True,
    export_pdf=False  # Set to True to export as PDF
)
```

## Position and Order Classes

### Position

The `Position` class represents a trading position:

```python
from fxml4.backtesting.backtest_engine import Position, OrderSide, PositionStatus

position = Position(
    position_id="pos-1",
    symbol="EURUSD",
    side=OrderSide.BUY,
    entry_price=1.1234,
    entry_timestamp=datetime.now(),
    quantity=100,
    status=PositionStatus.OPEN
)
```

### Order

The `Order` class represents a trading order:

```python
from fxml4.backtesting.backtest_engine import Order, OrderType, OrderSide

order = Order(
    order_id="order-1",
    symbol="EURUSD",
    order_type=OrderType.MARKET,
    side=OrderSide.BUY,
    quantity=100,
    price=None,  # Market order
    stop_price=None,
    timestamp=datetime.now(),
    status="new"
)
```

## Integration with Performance Metrics

The backtest engine is now fully integrated with the comprehensive performance metrics system, providing advanced analytics:

```python
# Run backtest
results = engine.run(strategy, data)

# Access advanced performance metrics
if results.performance_metrics:
    # Print advanced risk metrics
    print(f"Ulcer Index: {results.performance_metrics.ulcer_index:.4f}")
    print(f"Conditional VaR (95%): {results.performance_metrics.cvar_95:.2f}%")
    print(f"Recovery Factor: {results.performance_metrics.recovery_factor:.2f}")

    # Get monthly returns table
    monthly_returns = results.performance_metrics.monthly_returns
    print(monthly_returns)

# Analyze drawdowns
if results.drawdown_analysis is not None:
    print("\nTop Drawdowns:")
    print(results.drawdown_analysis)

# Analyze risk contribution by various factors
if results.risk_analysis:
    print("\nPerformance by Market Regime:")
    print(results.risk_analysis['by_regime'])

    print("\nPerformance by Symbol:")
    print(results.risk_analysis['by_symbol'])

# Check Monte Carlo simulation results
if results.monte_carlo_results:
    prob_profit = results.monte_carlo_results['probability_of_profit']
    prob_drawdown = results.monte_carlo_results['probability_of_10pct_drawdown']
    print(f"\nProbability of Profit: {prob_profit:.2%}")
    print(f"Probability of >10% Drawdown: {prob_drawdown:.2%}")

    # Get percentile values
    percentile_95 = results.monte_carlo_results['final_equity_percentiles'][95]
    print(f"95th Percentile Final Equity: ${percentile_95:,.2f}")
```

## Helper Functions

### run_backtest()

A convenience function to run a backtest without explicitly creating a `BacktestEngine` instance:

```python
from fxml4.backtesting.backtest_engine import run_backtest

results = run_backtest(
    strategy=my_strategy,
    data=historical_data,
    strategy_params={"symbol": "EURUSD"},
    config={"initial_capital": 10000}
)
```
