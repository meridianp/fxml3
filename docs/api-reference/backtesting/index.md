# Backtesting Framework

The FXML4 backtesting framework provides comprehensive tools for developing, testing, and analyzing trading strategies across multiple markets and timeframes.

## Key Components

- **Event-Driven Backtesting**: Realistic simulation with event-driven architecture
- **Market Impact Simulation**: Accurate modeling of slippage and market impact
- **Risk Management**: Advanced position sizing and drawdown control
- **Performance Metrics**: Comprehensive analysis of strategy performance
- **Visualization**: Rich visualization of equity curves, drawdowns, and trade statistics
- **Reporting**: Professional HTML and PDF performance reports

## Module Overview

| Module | Description |
|--------|-------------|
| [backtest_engine](backtest_engine.md) | Core backtesting engine for strategy evaluation |
| [event_driven_engine](event_driven_engine.md) | Event-driven architecture for realistic execution simulation |
| [execution](execution.md) | Order execution models with realistic slippage |
| [market_impact](market_impact.md) | Market impact models for realistic large order simulation |
| [news_filter](news_filter.md) | News-based filters for avoiding high-volatility events |
| [performance_metrics](performance_metrics.md) | Comprehensive performance analysis tools |
| [risk_management](risk_management.md) | Advanced risk management and position sizing |

## Getting Started

```python
from fxml4.backtesting.backtest_engine import BacktestEngine
from fxml4.backtesting.risk_management import RiskManager
from fxml4.strategy.integrated_strategy import IntegratedStrategy

# Initialize strategy
strategy = IntegratedStrategy(
    name="Example Strategy",
    parameters={
        "lookback": 20,
        "entry_threshold": 1.5,
        "exit_threshold": 0.5
    }
)

# Initialize risk manager
risk_manager = RiskManager(
    max_drawdown_pct=10.0,
    max_position_size_pct=2.0,
    max_correlation_exposure=4.0
)

# Initialize backtest engine
engine = BacktestEngine(
    strategy=strategy,
    risk_manager=risk_manager,
    initial_capital=100000,
    commission_model="percentage",
    commission_value=0.001
)

# Run backtest
results = engine.run(
    data=data,
    start_date="2023-01-01",
    end_date="2023-12-31"
)

# Analyze performance
metrics = results.get_performance_metrics()
print(metrics.summary())

# Generate report
from fxml4.visualization.performance_charts import create_performance_dashboard
from fxml4.visualization.report_generator import create_performance_report

figures = create_performance_dashboard(
    equity_curve=results.equity_curve,
    trades=results.trades
)

report_path = create_performance_report(
    strategy_name="Example Strategy Backtest",
    metrics=metrics,
    equity_curve=results.equity_curve,
    trades=results.trades,
    figures=figures
)
```

## Key Features

### Event-Driven Architecture

The event-driven backtesting engine provides a realistic simulation environment with:

- Order matching based on volume and price
- Queue-based execution model
- Advanced slippage and market impact models
- Support for limit, market, and stop orders
- Realistic order fills based on volume and liquidity

### Advanced Performance Metrics

Comprehensive performance metrics calculation includes:

- Return metrics (total return, annualized return, volatility)
- Risk-adjusted metrics (Sharpe ratio, Sortino ratio, Calmar ratio)
- Drawdown analysis (maximum drawdown, drawdown duration, recovery factor)
- Trade statistics (win rate, profit factor, expectancy)
- Risk metrics (VaR, CVaR, ulcer index)
- Benchmark comparison (alpha, beta, correlation, information ratio)

### Scenario Analysis

Compare multiple strategy configurations:

- Parallel backtesting of multiple parameter sets
- Parameter sensitivity analysis
- Optimal parameter identification
- Multi-scenario comparison reports

### Professional Reporting

Generate professional-quality reports:

- Interactive HTML reports with embedded visualizations
- PDF export for sharing and documentation
- Customizable templates for report generation
- Comprehensive performance dashboards

## Advanced Usage

### Monte Carlo Simulation

Test strategy robustness through Monte Carlo simulation:

```python
from fxml4.backtesting.performance_metrics import PerformanceAnalyzer

analyzer = PerformanceAnalyzer()
mc_results = analyzer.create_monte_carlo_simulation(
    trades=results.trades,
    initial_capital=100000,
    num_simulations=1000
)

print(f"Probability of Profit: {mc_results['probability_of_profit']:.2%}")
print(f"Probability of >10% Drawdown: {mc_results['probability_of_10pct_drawdown']:.2%}")
```

### Market Regime Analysis

Analyze strategy performance across different market regimes:

```python
risk_analysis = analyzer.risk_contribution_analysis(results.trades)
regime_performance = risk_analysis['by_regime']

print("Performance by Market Regime:")
print(regime_performance)
```

### Parameter Optimization

Optimize strategy parameters:

```python
from fxml4.backtesting.performance_metrics import ScenarioAnalyzer

scenario_analyzer = ScenarioAnalyzer()

# Add multiple parameter scenarios
for stop_loss in [0.01, 0.02, 0.03]:
    for take_profit in [0.02, 0.03, 0.04]:
        # Run backtest with these parameters
        strategy.set_parameters({
            "stop_loss": stop_loss,
            "take_profit": take_profit
        })

        results = engine.run(data)

        scenario_analyzer.add_scenario(
            name=f"SL_{stop_loss}_TP_{take_profit}",
            equity_curve=results.equity_curve,
            trades=results.trades,
            parameters={"stop_loss": stop_loss, "take_profit": take_profit}
        )

# Find optimal parameters
best_scenario, scenario_data = scenario_analyzer.find_optimal_scenario("sharpe_ratio")
print(f"Best parameters: {scenario_data['parameters']}")

# Analyze parameter sensitivity
sensitivity = scenario_analyzer.analyze_parameter_sensitivity("stop_loss", "sharpe_ratio")
print(sensitivity)
```
