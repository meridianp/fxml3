# FXML4 Risk Management Framework

The FXML4 Risk Management Framework provides a comprehensive set of tools for managing risk in algorithmic trading systems. This document outlines the key components and usage guidelines.

## Overview

The risk management framework in FXML4 is designed to protect your trading capital through multiple layers of protection:

1. **Position Sizing**: Dynamically determine appropriate position sizes based on various methods
2. **Stop-Loss Management**: Automatically place and manage stop-loss orders
3. **Drawdown Control**: Monitor and limit drawdowns at portfolio and symbol levels
4. **Portfolio Risk Metrics**: Track and analyze various risk metrics
5. **News Event Filtering**: Avoid trading during high-impact economic events

## Position Sizing Algorithms

FXML4 provides several position sizing algorithms:

### Fixed Position Sizer

Allocates a fixed amount of capital to each position.

```python
from fxml4.backtesting.risk_management import FixedPositionSizer

# Create position sizer with $1,000 per trade
position_sizer = FixedPositionSizer(fixed_amount=1000.0)
```

### Percentage Position Sizer

Allocates a percentage of portfolio equity to each position.

```python
from fxml4.backtesting.risk_management import PercentagePositionSizer

# Create position sizer with 2% equity per trade
position_sizer = PercentagePositionSizer(percentage=0.02)
```

### Volatility Position Sizer

Adjusts position size based on market volatility (ATR).

```python
from fxml4.backtesting.risk_management import VolatilityPositionSizer

# Risk 1% of equity per trade, with position size adjusted for volatility
position_sizer = VolatilityPositionSizer(
    risk_pct=0.01,             # 1% risk per trade
    volatility_window=20,      # 20-bar window for ATR calculation
    atr_multiplier=2.0,        # Stop loss at 2 ATR from entry
)
```

### Kelly Position Sizer

Uses the Kelly criterion to calculate optimal position size based on expected win rate and win/loss ratio.

```python
from fxml4.backtesting.risk_management import KellyPositionSizer

# Create Kelly position sizer
position_sizer = KellyPositionSizer(
    default_win_rate=0.55,         # 55% win rate
    default_win_loss_ratio=1.5,    # Win 1.5x what we lose on average
    max_allocation=0.2,            # Max 20% allocation to a single position
    fraction=0.5,                  # Half-Kelly for conservatism
)
```

### Optimal-F Position Sizer

Uses Ralph Vince's Optimal-F method for position sizing.

```python
from fxml4.backtesting.risk_management import OptimalFPositionSizer

# Create Optimal-F position sizer
position_sizer = OptimalFPositionSizer(
    default_optimal_f=0.1,      # Default value if no history available
    max_allocation=0.2,         # Max 20% allocation to a single position
    lookback_trades=20,         # Consider last 20 trades
)
```

## Stop-Loss Management

The `StopLossManager` provides various types of stop-loss orders:

- Fixed amount stops
- Percentage-based stops
- Volatility-based stops (ATR)
- Trailing stops
- Chandelier exits
- Time-based stops

```python
from fxml4.backtesting.risk_management import StopLossManager, StopLossType

# Create stop-loss manager with percentage stops by default
stop_manager = StopLossManager(
    default_type=StopLossType.PERCENTAGE,
    default_percentage=0.02,            # 2% stop loss
    default_atr_multiple=2.0,           # 2x ATR for volatility stops
    default_trailing_percentage=0.01,   # 1% trailing stop
    default_time_limit=timedelta(days=5), # 5-day time stop
)
```

## Drawdown Control

The `DrawdownControl` class monitors and limits drawdowns:

```python
from fxml4.backtesting.risk_management import DrawdownControl

# Create drawdown control
drawdown_control = DrawdownControl(
    max_drawdown_pct=0.20,          # 20% max portfolio drawdown
    per_symbol_drawdown_pct=0.10,   # 10% max drawdown per symbol
    cooling_off_days=5,             # 5-day cooling off period
    reduction_factor=0.5,           # 50% size reduction during cooling off
)
```

## Portfolio Risk Metrics

The `PortfolioRiskMetrics` class calculates various risk metrics:

```python
from fxml4.backtesting.risk_management import PortfolioRiskMetrics

# Create risk metrics calculator
risk_metrics = PortfolioRiskMetrics(
    lookback_days=90,               # 90-day lookback period
    benchmark_symbol="EURUSD",      # Benchmark symbol
    risk_free_rate=0.02,            # 2% annual risk-free rate
    calculation_frequency="daily",  # Calculate metrics daily
)

# Get metrics
metrics = risk_metrics.calculate_metrics(portfolio, current_time)

# Available metrics include:
# - Sharpe ratio
# - Sortino ratio
# - Maximum drawdown
# - Value at Risk (VaR)
# - Conditional VaR (CVaR)
# - Beta, alpha, correlation to benchmark
# - Portfolio concentration
# - Exposure metrics
```

## News Event Filtering

The news event filtering system helps avoid trading during major economic events:

```python
from fxml4.backtesting.news_filter import IntegratedNewsFilter

# Create news filter
news_filter = IntegratedNewsFilter(
    high_impact_only=True,          # Only filter high-impact events
    event_buffer_before=120,        # Avoid trading 2 hours before events
    event_buffer_after=60,          # Avoid trading 1 hour after events
    currency_specific=True,         # Only filter events affecting our pair
    scheduled_updates=True,         # Automatically update calendar
    update_interval_hours=12,       # Update every 12 hours
)

# Check if current time is during a news event
is_news_time, events, reason = news_filter.is_news_event_time(
    timestamp=current_time,
    symbol="EURUSD",
    current_bar=current_bar,        # For spread analysis
    market_data=market_data,        # For spread analysis
)

# Get upcoming events
upcoming = news_filter.get_upcoming_events(
    from_time=datetime.now(),
    days_ahead=7,
    symbol="EURUSD"
)
```

## Integrating with the Risk Manager

The `RiskManager` class integrates all risk management components:

```python
from fxml4.backtesting.risk_management import RiskManager

# Create risk manager with all components
risk_manager = RiskManager(
    position_sizer=VolatilityPositionSizer(risk_pct=0.01),
    stop_loss_manager=StopLossManager(),
    drawdown_control=DrawdownControl(),
    news_filter=IntegratedNewsFilter(),
    avoid_high_impact_news=True,    # Avoid trading during news events
    max_positions=10,               # Maximum 10 simultaneous positions
    max_correlated_positions=3,     # Maximum 3 correlated positions
    correlation_threshold=0.7,      # Correlation threshold
    leverage_limit=2.0,             # Maximum 2x leverage
    risk_per_trade_pct=0.01,        # 1% risk per trade
    max_risk_per_day_pct=0.03,      # 3% maximum daily risk
)

# Integrate with portfolio
portfolio.risk_manager = risk_manager
```

## Example: Complete Backtest with Risk Management

```python
from fxml4.backtesting.event_driven_engine import EventDrivenEngine, Portfolio
from fxml4.backtesting.execution import ExecutionHandler
from fxml4.backtesting.risk_management import RiskManager, VolatilityPositionSizer

# Create portfolio with risk manager
portfolio = Portfolio(initial_capital=10000.0)
portfolio.risk_manager = RiskManager(
    position_sizer=VolatilityPositionSizer(risk_pct=0.01),
    max_positions=5,
    risk_per_trade_pct=0.01,
    avoid_high_impact_news=True,
)

# Create execution handler
execution_handler = ExecutionHandler()

# Create engine and run backtest
engine = EventDrivenEngine(
    strategy=your_strategy_function,
    portfolio=portfolio,
    execution_handler=execution_handler,
)

# Run backtest
engine.load_data(data)
result = engine.run()
```

## Further Reading

For complete examples, see:
- `examples/risk_management_example.py` - Demonstrates all risk management features
- `examples/news_filter_example.py` - Shows how news event filtering works

## Best Practices

1. **Start Conservative**: Begin with more conservative settings and gradually adjust as needed
2. **Combine Strategies**: Use multiple risk management techniques together for robust protection
3. **Regular Monitoring**: Regularly review risk metrics to identify potential issues early
4. **Stress Testing**: Test your risk management settings under extreme market conditions
5. **Customization**: Adjust parameters for different market conditions and instruments
