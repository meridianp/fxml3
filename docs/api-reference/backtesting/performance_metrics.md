# Performance Metrics and Analysis

The FXML4 backtesting framework includes comprehensive performance metrics, analysis, visualization, and reporting capabilities to evaluate and communicate trading strategy results.

## Core Components

### PerformanceMetrics

A dataclass that stores all calculated performance metrics including:

- **Basic metrics**: total return, annualized return, volatility, Sharpe ratio, Sortino ratio
- **Drawdown metrics**: maximum drawdown, average drawdown, drawdown duration, recovery factor, Calmar ratio, Ulcer index
- **Trade metrics**: number of trades, win rate, profit factor, average profit/loss per trade, trade duration
- **Value at Risk metrics**: VaR/CVaR at 95% and 99% confidence levels
- **Benchmark comparison**: alpha, beta, correlation, information ratio, Treynor ratio, up/down capture
- **Exposure metrics**: average exposure, max leverage, concentration
- **Cost metrics**: total fees, total slippage, cost per trade, cost as percentage of profit
- **Additional metrics**: expectancy, Kelly percentage, R-squared, skewness, kurtosis

### PerformanceAnalyzer

A class for calculating comprehensive performance metrics from equity curves and trade data:

```python
from fxml4.backtesting.performance_metrics import PerformanceAnalyzer

# Initialize the analyzer
analyzer = PerformanceAnalyzer(
    risk_free_rate=0.02,      # Annual risk-free rate
    annualization_factor=252, # Trading days per year
    benchmark_data=spy_data,  # Optional benchmark data
)

# Calculate metrics
metrics = analyzer.calculate_metrics(
    equity_curve=equity_df,
    trades=trades_list,
    include_benchmark=True
)

# Get a summary of metrics
print(metrics.summary())

# Access specific metrics
print(f"Sharpe Ratio: {metrics.sharpe_ratio:.2f}")
print(f"Maximum Drawdown: {metrics.max_drawdown_pct:.2f}%")
```

Key methods:

- `calculate_metrics()`: Calculate comprehensive performance metrics
- `compare_strategies()`: Compare multiple strategies
- `analyze_drawdowns()`: Analyze major drawdown periods
- `risk_contribution_analysis()`: Analyze risk contribution from different factors
- `create_monte_carlo_simulation()`: Run Monte Carlo simulation by randomly reordering trades

### ScenarioAnalyzer

A class for comparing multiple trading scenarios:

```python
from fxml4.backtesting.performance_metrics import ScenarioAnalyzer

# Initialize scenario analyzer
scenario_analyzer = ScenarioAnalyzer()

# Add multiple backtest scenarios
scenario_analyzer.add_scenario(
    name="Scenario 1",
    equity_curve=equity_df_1,
    trades=trades_list_1,
    parameters={"stop_loss": 0.02, "take_profit": 0.04}
)

scenario_analyzer.add_scenario(
    name="Scenario 2",
    equity_curve=equity_df_2,
    trades=trades_list_2,
    parameters={"stop_loss": 0.03, "take_profit": 0.06}
)

# Compare scenarios
comparison_df = scenario_analyzer.compare_scenarios(
    key_metrics=["sharpe_ratio", "max_drawdown_pct", "win_rate"]
)

# Find optimal scenario
best_scenario, scenario_data = scenario_analyzer.find_optimal_scenario(
    metric_name="sharpe_ratio"
)
```

Key methods:

- `add_scenario()`: Add a backtest scenario
- `compare_scenarios()`: Compare all scenarios
- `compare_equity_curves()`: Compare equity curves across scenarios
- `compare_drawdowns()`: Compare drawdown periods across scenarios
- `analyze_parameter_sensitivity()`: Analyze sensitivity of a metric to a specific parameter
- `find_optimal_scenario()`: Find the optimal scenario based on a specific metric

## Visualization

The `fxml4.visualization.performance_charts` module provides functions for visualizing performance metrics:

```python
from fxml4.visualization.performance_charts import (
    plot_equity_curve,
    plot_drawdowns,
    plot_monthly_returns_heatmap,
    plot_regime_performance,
    plot_trade_distribution,
    plot_comparative_metrics,
    plot_monte_carlo_simulation,
    create_performance_dashboard
)

# Plot equity curve
fig = plot_equity_curve(
    equity_df=equity_df,
    benchmark_df=benchmark_df,
    title="Strategy Equity Curve"
)

# Create comprehensive dashboard
figures = create_performance_dashboard(
    equity_curve=equity_df,
    trades=trades_list,
    benchmark_data=benchmark_df,
    risk_analysis=risk_analysis,
    monthly_returns=monthly_returns_df,
    save_path="output/dashboard"
)
```

Available visualization functions:

- `plot_equity_curve()`: Plot the equity curve with optional benchmark comparison
- `plot_drawdowns()`: Plot drawdowns over time
- `plot_monthly_returns_heatmap()`: Plot monthly returns as a heatmap
- `plot_regime_performance()`: Plot performance metrics by market regime
- `plot_trade_distribution()`: Plot the distribution of trade returns
- `plot_comparative_metrics()`: Plot comparative metrics for multiple strategies/scenarios
- `plot_monte_carlo_simulation()`: Plot Monte Carlo simulation results
- `create_performance_dashboard()`: Create a comprehensive performance dashboard with multiple plots

## Report Generation

The `fxml4.visualization.report_generator` module provides functionality to generate HTML and PDF reports:

```python
from fxml4.visualization.report_generator import (
    create_performance_report,
    export_to_pdf
)

# Generate figures for report
figures = create_performance_dashboard(equity_df, trades_list)

# Create HTML report
html_path = create_performance_report(
    strategy_name="FXML4 Strategy",
    metrics=metrics,
    equity_curve=equity_df,
    trades=trades_list,
    figures=figures,
    output_dir="output/reports"
)

# Export to PDF
pdf_path = export_to_pdf(html_path)
```

Key functions:

- `create_performance_report()`: Create HTML performance report
- `export_to_pdf()`: Export HTML report to PDF

The generated reports include:

- Summary of key performance metrics
- Equity curve and drawdown visualizations
- Trade statistics and analysis
- Monthly returns heatmap
- Risk analysis visualizations
- Recent trades table

## Example Usage

Here's a complete example demonstrating the performance analysis capabilities:

```python
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from fxml4.backtesting.performance_metrics import PerformanceAnalyzer, ScenarioAnalyzer
from fxml4.visualization.performance_charts import create_performance_dashboard
from fxml4.visualization.report_generator import create_performance_report, export_to_pdf

# Sample data generation (in real use, this would be your backtest results)
def generate_sample_data(annual_return=0.15, volatility=0.20, days=252, seed=42):
    np.random.seed(seed)

    # Generate dates
    start_date = datetime(2023, 1, 1)
    dates = [start_date + timedelta(days=i) for i in range(days)]

    # Generate returns
    daily_return = annual_return / days
    daily_vol = volatility / np.sqrt(days)
    returns = np.random.normal(daily_return, daily_vol, days)

    # Generate equity curve
    equity = 10000 * np.cumprod(1 + returns)

    # Create DataFrame
    equity_df = pd.DataFrame({
        'equity': equity
    }, index=dates)

    # Generate sample trades
    trades = []
    for i in range(50):
        entry_date = start_date + timedelta(days=np.random.randint(0, days-10))
        exit_date = entry_date + timedelta(days=np.random.randint(1, 10))

        win = np.random.random() < 0.55  # 55% win rate
        pnl = np.random.normal(200, 100) if win else np.random.normal(-150, 75)

        trades.append({
            'entry_time': entry_date,
            'exit_time': exit_date,
            'symbol': 'EURUSD',
            'side': 'BUY' if np.random.random() < 0.5 else 'SELL',
            'pnl': pnl,
            'pnl_pct': pnl / 10000 * 100,
            'commission': np.random.uniform(5, 15),
            'slippage': np.random.uniform(2, 10),
            'metadata': {
                'market_regime': np.random.choice(['trending', 'ranging', 'volatile'])
            }
        })

    return equity_df, trades

# Generate sample data for two scenarios
equity_df1, trades1 = generate_sample_data(annual_return=0.15, volatility=0.20, seed=42)
equity_df2, trades2 = generate_sample_data(annual_return=0.18, volatility=0.25, seed=43)

# Initialize performance analyzer
analyzer = PerformanceAnalyzer(risk_free_rate=0.02)

# Calculate metrics for first scenario
metrics1 = analyzer.calculate_metrics(equity_df1, trades1)
print(metrics1.summary())

# Analyze drawdowns
drawdowns = analyzer.analyze_drawdowns(equity_df1)
print("\nTop Drawdowns:")
print(drawdowns)

# Run Monte Carlo simulation
mc_results = analyzer.create_monte_carlo_simulation(trades1)
print("\nMonte Carlo Results:")
for percentile, value in mc_results['final_equity_percentiles'].items():
    print(f"{percentile}th percentile: ${value:.2f}")

# Analyze risk contribution by market regime
risk_analysis = analyzer.risk_contribution_analysis(trades1)
print("\nPerformance by Market Regime:")
print(risk_analysis['by_regime'])

# Compare multiple scenarios
scenario_analyzer = ScenarioAnalyzer(analyzer)

# Add scenarios
scenario_analyzer.add_scenario(
    name="Conservative",
    equity_curve=equity_df1,
    trades=trades1,
    parameters={"stop_loss": 0.02, "take_profit": 0.04}
)

scenario_analyzer.add_scenario(
    name="Aggressive",
    equity_curve=equity_df2,
    trades=trades2,
    parameters={"stop_loss": 0.03, "take_profit": 0.06}
)

# Compare scenarios
comparison = scenario_analyzer.compare_scenarios()
print("\nScenario Comparison:")
print(comparison)

# Find optimal scenario
best_name, best_scenario = scenario_analyzer.find_optimal_scenario("sharpe_ratio")
print(f"\nBest scenario: {best_name} with Sharpe ratio: {best_scenario['metrics'].sharpe_ratio:.2f}")

# Create visualizations and dashboard
figures = create_performance_dashboard(
    equity_curve=equity_df1,
    trades=trades1,
    risk_analysis=risk_analysis,
    monthly_returns=metrics1.monthly_returns
)

# Generate HTML report
report_path = create_performance_report(
    strategy_name="FXML4 Sample Strategy",
    metrics=metrics1,
    equity_curve=equity_df1,
    trades=trades1,
    figures=figures,
    additional_data={
        "Monte Carlo Results": {
            "Probability of Profit": f"{mc_results['probability_of_profit']:.2%}",
            "Probability of >10% Drawdown": f"{mc_results['probability_of_10pct_drawdown']:.2%}"
        },
        "Scenario Comparison": comparison.to_dict()
    }
)

# Export to PDF
pdf_path = export_to_pdf(report_path)
print(f"\nReport generated: {report_path}")
print(f"PDF exported: {pdf_path}")
```
