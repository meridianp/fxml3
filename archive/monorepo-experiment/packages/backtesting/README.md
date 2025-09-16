# FXML4 Backtesting Framework

Advanced backtesting framework for forex trading strategies with event-driven architecture.

## Features

- Event-driven backtesting engine
- Realistic execution modeling (slippage, fees, market impact)
- Multi-asset portfolio support
- Advanced risk management
- Performance metrics and analysis
- Walk-forward optimization
- Monte Carlo simulation
- Trade analytics and visualization

## Installation

```bash
poetry install
```

## Quick Start

```python
from fxml4_backtesting import BacktestEngine, Strategy
from fxml4_backtesting.performance import PerformanceAnalyzer

# Create strategy
class MyStrategy(Strategy):
    def on_data(self, data):
        # Implement your strategy logic
        if self.should_buy(data):
            self.buy(size=0.1)
        elif self.should_sell(data):
            self.sell(size=0.1)

# Run backtest
engine = BacktestEngine(
    initial_capital=10000,
    commission=0.001,
    slippage_model="fixed"
)

results = engine.run(
    strategy=MyStrategy(),
    data=market_data,
    start_date="2023-01-01",
    end_date="2023-12-31"
)

# Analyze performance
analyzer = PerformanceAnalyzer()
metrics = analyzer.calculate_metrics(results)
analyzer.plot_performance(results)
```

## Components

### Backtesting Engine
- Event-driven architecture
- Realistic order execution
- Position tracking
- Portfolio management

### Risk Management
- Position sizing algorithms
- Stop-loss management
- Drawdown controls
- Risk metrics calculation

### Performance Analysis
- Sharpe ratio
- Maximum drawdown
- Win rate and profit factor
- Trade distribution analysis
- Monthly/yearly returns

### Optimization
- Parameter optimization
- Walk-forward analysis
- Overfitting detection
- Robustness testing

## Development

```bash
# Run tests
poetry run pytest

# Format code
poetry run black src tests
poetry run isort src tests

# Type checking
poetry run mypy src
```