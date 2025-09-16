# Event-Driven Engine

The `event_driven_engine` module provides an advanced event-driven backtesting architecture for realistic simulation of trading strategies.

## Key Concepts

The event-driven architecture is based on the following key concepts:

- **Events**: Different types of events flow through the system (market, signal, order, fill)
- **Event Queue**: Central event processing system that manages the flow of events
- **Portfolio**: Tracks positions, orders, and equity in the simulation
- **Execution Handler**: Processes orders and generates fills with realistic slippage and market impact

## EventDrivenEngine Class

The `EventDrivenEngine` is the main backtesting engine, coordinating the flow of events through the system.

```python
from fxml4.backtesting.event_driven_engine import EventDrivenEngine
from fxml4.backtesting.execution import ExecutionHandler, HybridSlippageModel

# Create a slippage model
slippage_model = HybridSlippageModel(
    base_slippage_pct=0.0001,  # 0.01%
    volume_factor=0.1,
    volatility_factor=0.5,
    max_slippage_pct=0.001     # 0.1%
)

# Create execution handler
execution_handler = ExecutionHandler(slippage_model=slippage_model)

# Create event-driven engine
engine = EventDrivenEngine(
    strategy=my_strategy,
    execution_handler=execution_handler,
    initial_capital=100000.0,
    fee_model="forex",
)

# Load data
engine.load_data(historical_data)

# Run backtest
results = engine.run()

# Get comprehensive performance metrics
metrics = results.get_performance_metrics()
print(metrics.summary())
```

### Strategy Function

For the event-driven engine, the strategy function has a different signature than the standard backtest engine:

```python
def my_strategy(symbol, current_bar, market_data, portfolio):
    """Event-driven strategy function.

    Args:
        symbol: Market symbol.
        current_bar: Current price bar as a Series.
        market_data: Historical market data DataFrame.
        portfolio: Portfolio instance with current positions.

    Returns:
        Dictionary of signals.
    """
    signals = {}

    # Entry signal
    if entry_condition(market_data, current_bar):
        signals["entry"] = {
            "side": "buy",  # or "sell"
            "order_type": "market",  # "limit", "stop", etc.
            "risk_pct": 0.02,
            "stop_loss": current_bar["close"] * 0.98,  # 2% stop loss
            "position_sizing": "risk_pct",  # Sizing method
        }

    # Exit signal
    elif exit_condition(market_data, current_bar, portfolio):
        if symbol in portfolio.positions:
            signals["exit"] = {
                "order_type": "market",
            }

    return signals
```

## Portfolio Class

The `Portfolio` class tracks positions, orders, and capital throughout the simulation:

```python
from fxml4.backtesting.event_driven_engine import Portfolio

# Create portfolio
portfolio = Portfolio(
    initial_capital=100000.0,
    fee_model="forex",  # Fee model to use
)

# Get current positions
positions = portfolio.get_current_positions()

# Get closed positions
closed_positions = portfolio.get_closed_positions()

# Get equity curve
equity_df = portfolio.get_equity_curve()

# Calculate performance metrics
metrics = portfolio.calculate_metrics()
```

## EventQueue Class

The `EventQueue` manages the flow of events through the system:

```python
from fxml4.backtesting.event_driven_engine import EventQueue

# Create event queue
queue = EventQueue()

# Add event to queue
queue.put(market_event)

# Get next event
event = queue.get()

# Check if queue is empty
if queue.is_empty():
    print("All events processed")

# Get queue statistics
stats = queue.get_stats()
print(stats)
```

## Event Types

The event-driven engine uses different types of events:

- **MarketEvent**: Represents new market data
- **SignalEvent**: Represents a trading signal
- **OrderEvent**: Represents a trade order
- **FillEvent**: Represents an order fill

```python
from fxml4.backtesting.event import (
    MarketEvent,
    SignalEvent,
    OrderEvent,
    FillEvent,
    EventType
)

# Create a market event
market_event = MarketEvent(
    timestamp=datetime.now(),
    symbol="EURUSD",
    timeframe="1D",
    data=price_bar,
)

# Create a signal event
signal_event = SignalEvent(
    timestamp=datetime.now(),
    symbol="EURUSD",
    signal_type="entry",
    signal_data={"side": "buy", "risk_pct": 0.02},
)

# Create an order event
order_event = OrderEvent(
    timestamp=datetime.now(),
    order_id="order-123",
    symbol="EURUSD",
    order_type="market",
    side="buy",
    quantity=100,
    price=None,
)

# Check event type
if event.type == EventType.MARKET:
    process_market_event(event)
elif event.type == EventType.SIGNAL:
    process_signal_event(event)
```

## Helper Functions

### run_event_driven_backtest()

A convenience function to run an event-driven backtest without explicitly creating the components:

```python
from fxml4.backtesting.event_driven_engine import run_event_driven_backtest

results = run_event_driven_backtest(
    strategy=my_strategy,
    data=historical_data,
    initial_capital=100000.0,
    fee_model="forex",
    slippage_model=slippage_model,
    date_col="time",
)
```

### Automatic Report Generation

The event-driven engine supports automatic report generation, controlled through the configuration:

```yaml
backtesting:
  # Other settings...
  reporting:
    auto_generate: true  # Enable automatic report generation
    include_figures: true  # Include visualizations in reports
    export_pdf: false  # Don't export to PDF by default
    output_dir: "output/reports"  # Directory for reports
```

When enabled, a performance report is automatically generated at the end of each backtest, with no need for manual calls to `generate_report()`. You can toggle this feature and customize the report settings in the configuration file or via environment variables.

Environment variables can also control these settings:
```
FXML4_BACKTESTING_REPORTING_AUTO_GENERATE=true
FXML4_BACKTESTING_REPORTING_INCLUDE_FIGURES=true
FXML4_BACKTESTING_REPORTING_EXPORT_PDF=false
FXML4_BACKTESTING_REPORTING_OUTPUT_DIR=output/reports
```

## Integration with Performance Metrics

The event-driven engine is fully integrated with the comprehensive performance metrics system:

```python
# Run backtest
results = engine.run()

# Access standard metrics
print(f"Total Return: {results.total_return_pct:.2f}%")
print(f"Sharpe Ratio: {results.sharpe_ratio:.2f}")
print(f"Max Drawdown: {results.max_drawdown_pct:.2f}%")

# Access advanced performance metrics
if results.performance_metrics:
    print(f"Ulcer Index: {results.performance_metrics.ulcer_index:.4f}")
    print(f"Recovery Factor: {results.performance_metrics.recovery_factor:.2f}")
    print(f"CVaR (95%): {results.performance_metrics.cvar_95:.2f}%")

    # Get monthly returns heatmap
    monthly_returns = results.performance_metrics.monthly_returns

# Generate performance report
report_path = results.generate_report(
    output_dir="output/reports",
    include_figures=True,
    export_pdf=False,
)
```

## Realistic Market Simulation

The event-driven engine provides realistic market simulation with:

### Slippage Models

Various slippage models for realistic order execution:

```python
from fxml4.backtesting.execution import (
    FixedSlippageModel,
    PercentageSlippageModel,
    VolumeBasedSlippageModel,
    HybridSlippageModel,
)

# Create a hybrid slippage model
slippage_model = HybridSlippageModel(
    base_slippage_pct=0.0001,  # Base slippage of 0.01%
    volume_factor=0.1,         # Volume impact factor
    volatility_factor=0.5,     # Volatility impact factor
    random_factor=0.2,         # Random component factor
    max_slippage_pct=0.001,    # Maximum slippage of 0.1%
)
```

### Market Impact Models

Models for simulating the impact of large orders on the market:

```python
from fxml4.backtesting.market_impact import (
    MarketImpactHandler,
    PowerLawModel,
    LinearModel,
)

# Create market impact model
impact_model = PowerLawModel(
    k=0.1,               # Impact factor
    exponent=0.6,        # Power law exponent
    volatility_window=20, # Window for volatility calculation
    adv_window=20,       # Window for average daily volume
)

# Create market impact handler
impact_handler = MarketImpactHandler(model=impact_model)
```

## Example Usage

Here's a complete example of using the event-driven engine:

```python
from fxml4.backtesting.event_driven_engine import EventDrivenEngine, run_event_driven_backtest
from fxml4.backtesting.execution import HybridSlippageModel
from fxml4.visualization.performance_charts import create_performance_dashboard

# Define strategy
def ma_crossover_strategy(symbol, current_bar, market_data, portfolio):
    """Moving average crossover strategy."""
    if market_data is None or len(market_data) < 50:
        return {}

    # Calculate moving averages
    fast_window = 20
    slow_window = 50

    close_prices = market_data["close"]
    fast_ma = close_prices.rolling(window=fast_window).mean()
    slow_ma = close_prices.rolling(window=slow_window).mean()

    # Get current and previous values
    if len(fast_ma) > 1 and len(slow_ma) > 1:
        current_fast = fast_ma.iloc[-1]
        current_slow = slow_ma.iloc[-1]
        prev_fast = fast_ma.iloc[-2]
        prev_slow = slow_ma.iloc[-2]

        # Buy signal: fast MA crosses above slow MA
        if prev_fast <= prev_slow and current_fast > current_slow:
            return {
                "entry": {
                    "side": "buy",
                    "order_type": "market",
                    "risk_pct": 0.02,
                    "stop_loss": current_bar["close"] * 0.98,
                }
            }

        # Sell signal: fast MA crosses below slow MA
        elif prev_fast >= prev_slow and current_fast < current_slow:
            if portfolio and symbol in portfolio.positions:
                return {
                    "exit": {
                        "order_type": "market",
                    }
                }

    return {}

# Create slippage model
slippage_model = HybridSlippageModel(
    base_slippage_pct=0.0001,
    volume_factor=0.1,
    volatility_factor=0.5,
)

# Run backtest
results = run_event_driven_backtest(
    strategy=ma_crossover_strategy,
    data=historical_data,
    initial_capital=100000.0,
    fee_model="forex",
    slippage_model=slippage_model,
)

# Create performance dashboard
figures = create_performance_dashboard(
    equity_curve=results.equity_curve,
    trades=results.trades,
    risk_analysis=results.risk_analysis,
)

# Generate report
report_path = results.generate_report()
print(f"Report generated: {report_path}")
```
