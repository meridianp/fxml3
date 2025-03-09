# Backtesting Framework

The FXML3 backtesting framework provides comprehensive tools for evaluating and validating Elliott Wave trading strategies with realistic market conditions and robust statistical analysis. It enables traders to test their strategies on historical data while accounting for real-world challenges like slippage, spread, and commission costs.

## Overview

The backtesting system is designed to evaluate Elliott Wave pattern detection and trading strategies through multiple approaches:

1. **Realistic Market Simulation**: Simulate real-world trading conditions
2. **Strategy Performance Analysis**: Comprehensive metrics to evaluate strategy performance
3. **Statistical Validation**: Robust statistical methods to validate strategy consistency
4. **Visualization Tools**: Rich visualization of backtest results and analysis

## Key Components

### WaveBacktester

The `WaveBacktester` class serves as the main entry point for backtesting Elliott Wave pattern detection. It provides various simulation methods:

```python
from fxml3.backtesting.wave_backtester import WaveBacktester

# Initialize with custom market simulation parameters
backtester = WaveBacktester(
    slippage_model="normal",   # Options: "none", "fixed", "normal", "pareto"
    spread_model="variable",   # Options: "fixed", "variable", "volatile" 
    commission_model="fixed",  # Options: "none", "fixed", "percentage"
)

# Run basic rolling window backtest with realistic simulation
results = backtester.run_rolling_window_backtest(
    data=price_data,
    window_size=100,
    step_size=20,
    prediction_horizon=20,
    initial_capital=10000.0,
    use_realistic_simulation=True
)
```

### Realistic Market Simulation

The backtesting framework includes realistic market conditions that reflect the challenges of real-world trading:

1. **Slippage Modeling**:
   - Fixed slippage: Constant slippage per trade
   - Normal distribution: Random slippage following a normal distribution
   - Pareto distribution: Heavy-tailed slippage distribution for rare extreme events

2. **Spread Simulation**:
   - Fixed spread: Constant spread for all trades
   - Variable spread: Spread that varies with market volatility
   - Volatile spread: Occasional spread spikes during volatile periods

3. **Commission Calculation**:
   - Fixed commission: Flat fee per trade
   - Percentage commission: Fee based on trade value

### Advanced Validation Techniques

#### Monte Carlo Simulation

Monte Carlo simulation provides statistical robustness by randomly resampling trades to generate thousands of possible equity curves:

```python
mc_results = backtester.run_monte_carlo_simulation(
    backtest_result=results,
    num_simulations=1000,
    confidence_level=0.95,
    initial_capital=10000.0
)
```

Key Monte Carlo metrics include:
- Expected final capital (mean across all simulations)
- Worst-case capital (at selected confidence level)
- Expected drawdown
- Probability of profit
- Sharpe ratio and profit factor

#### Walk-Forward Analysis

Walk-forward analysis prevents overfitting by optimizing parameters on in-sample data and testing on out-of-sample data:

```python
wfa_results = backtester.run_walk_forward_analysis(
    symbol="EURUSD",
    start_date="2020-01-01",
    end_date="2022-12-31",
    timeframe="1D",
    n_folds=5,
    window_size=100,
    validation_size=50,
    use_realistic_simulation=True
)
```

This process includes:
- Parameter optimization on each training window
- Out-of-sample testing on validation windows
- Parameter stability metrics to detect overfitting
- Fold-by-fold performance tracking

#### Cross-Market Validation

Cross-market validation tests strategy robustness across different markets:

```python
cross_market_results = backtester.run_cross_market_validation(
    symbols=["EURUSD", "GBPUSD", "USDJPY", "AUDUSD"],
    start_date="2020-01-01",
    end_date="2022-12-31",
    timeframe="1D",
    use_realistic_simulation=True
)
```

Key cross-market metrics include:
- Performance consistency across markets
- Correlation analysis between markets
- Market-specific performance metrics
- Overall strategy robustness score

### Performance Metrics

The `PerformanceMetrics` class calculates extensive performance statistics:

```python
from fxml3.backtesting.performance_metrics import PerformanceMetrics

# Calculate profitability metrics with realistic costs
profitability = PerformanceMetrics.calculate_profitability(
    actual_outcomes=results["actual_outcomes"],
    account_size=10000.0,
    use_realistic_costs=True
)

# Calculate market impact metrics
impact_metrics = PerformanceMetrics.calculate_market_impact_metrics(
    actual_outcomes=results["actual_outcomes"],
    atr_values=atr_data  # Optional ATR values for volatility context
)
```

Available metrics include:
- Win rate and win/loss ratio
- Profit factor and expectancy
- Maximum drawdown and recovery time
- Risk-adjusted return (Sharpe, Sortino ratios)
- Transaction cost analysis
- Kelly criterion for optimal position sizing

### Visualization Tools

The `ResultVisualizer` class provides rich visualization of backtest results:

```python
from fxml3.backtesting.result_visualizer import ResultVisualizer

# Plot advanced equity curve with Monte Carlo results
fig = ResultVisualizer.plot_advanced_equity_curve(
    equity_curve=profitability["equity_curve"],
    trade_outcomes=results["actual_outcomes"],
    monte_carlo_results=mc_results
)

# Plot walk-forward analysis results
wfa_fig = ResultVisualizer.plot_walk_forward_analysis(
    wfa_results=wfa_results
)

# Plot cross-market validation results
cm_fig = ResultVisualizer.plot_cross_market_validation(
    cross_market_results=cross_market_results
)
```

Visualization capabilities include:
- Advanced equity curves with drawdown analysis
- Transaction cost overlay on performance charts
- Monte Carlo simulation confidence intervals
- Parameter stability across walk-forward folds
- Market correlation heatmaps
- Performance consistency metrics

## Integration with Strategy Components

The backtesting framework integrates seamlessly with the Elliott Wave detection and trading strategy components:

```python
from fxml3.wave_analysis.elliott_wave import ElliottWaveAnalyzer
from fxml3.strategy.risk_management import RiskManager
from fxml3.strategy.position_sizing import PositionSizer

# Create wave detector with optimized parameters
wave_detector = ElliottWaveAnalyzer(
    peak_distance_min=5,
    wave_threshold=0.382
)

# Initialize backtester with custom components
backtester = WaveBacktester(
    wave_analyzer=wave_detector
)

# Run backtest and analyze results
results = backtester.run_rolling_window_backtest(data=price_data)

# Apply risk management rules to backtest results
risk_manager = RiskManager()
position_sizer = PositionSizer()

# Calculate optimal position sizes based on backtest results
position_sizes = position_sizer.calculate_position_sizes(
    results=results,
    risk_per_trade=0.02
)
```

## Multi-Agent Integration

The backtesting framework is fully integrated with the FXML3 multi-agent system through the `BacktestAgent` class, which provides a high-level interface for agent-based backtesting operations:

```python
from fxml3.llm_integration.agent_framework import BacktestAgent, AgentCoordinator

# Create a backtest agent
backtest_agent = BacktestAgent()

# Process a backtest request directly
result = backtest_agent.process({
    "task": "backtest_strategy",
    "data": {
        "symbol": "EURUSD",
        "timeframe": "H1",
        "start_date": "2021-01-01",
        "end_date": "2022-12-31",
        "strategy_params": {
            "wave_type": "impulse",
            "entry_wave": 3,
            "exit_wave": 5
        }
    }
})

# Or use via the agent coordinator in a multi-agent workflow
coordinator = AgentCoordinator()
coordinator.register_agent("wave_detection", WaveDetectionAgent())
coordinator.register_agent("strategy", StrategyAgent())
coordinator.register_agent("backtest", BacktestAgent())

# Execute a complete workflow
full_analysis = coordinator.execute_workflow([
    {"agent": "wave_detection", "task": "detect_waves", "params": {...}},
    {"agent": "strategy", "task": "generate_strategy", "params": {...}},
    {"agent": "backtest", "task": "validate_strategy", "params": {...}}
])
```

### LLM-Enhanced Backtest Analysis

The `BacktestAgent` leverages LLM capabilities to provide enhanced analysis of backtest results:

```python
# Get AI-powered analysis of backtest results
analysis = backtest_agent.analyze_results(
    backtest_results=results,
    include_strengths_weaknesses=True,
    include_improvement_suggestions=True
)

# Example result structure
{
    "summary": "The strategy shows promising results with a 62% win rate and 1.8 profit factor...",
    "strengths": [
        "Consistent performance across different market conditions",
        "Low drawdown relative to returns",
        "Good performance in trending markets"
    ],
    "weaknesses": [
        "Underperforms in choppy market conditions",
        "Significant dependency on accurate wave 3 identification",
        "Higher than optimal transaction costs due to frequent trading"
    ],
    "improvements": [
        "Consider adding a market regime filter to avoid choppy conditions",
        "Implement tighter stop-loss management for wave 3 entries",
        "Reduce trade frequency by focusing only on highest-probability setups"
    ],
    "confidence_score": 0.78  # AI confidence in the strategy's robustness
}
```

## Best Practices

To get the most out of the backtesting framework:

1. **Start simple**: Use basic backtesting before adding realistic costs
2. **Add realism gradually**: Incrementally add slippage, spread, and commission
3. **Validate properly**: Use walk-forward analysis to prevent overfitting
4. **Test across markets**: Ensure strategy works on multiple instruments
5. **Use Monte Carlo**: Validate statistical significance of results
6. **Check consistency**: Monitor parameter stability across different time periods
7. **Consider transaction costs**: Ensure strategy remains profitable after costs

The FXML3 backtesting framework provides a robust foundation for developing and validating Elliott Wave trading strategies, ensuring they work consistently across different market conditions before deploying them in live trading environments.