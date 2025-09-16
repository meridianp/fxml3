# Performance Visualization and Reporting

FXML4 provides powerful visualization and reporting capabilities for trading strategy performance analysis. These tools help traders understand strategy behavior, analyze risk patterns, and communicate results effectively.

## Performance Charts

The `fxml4.visualization.performance_charts` module offers a comprehensive set of plotting functions to visualize backtest results:

### Equity Curve Visualization

Plot equity curves with optional benchmark comparison:

```python
from fxml4.visualization.performance_charts import plot_equity_curve

fig = plot_equity_curve(
    equity_df=equity_df,
    benchmark_df=benchmark_df,
    title="Strategy Equity Curve",
    figsize=(12, 6)
)
```

![Equity Curve Example](../../assets/equity_curve_example.png)

### Drawdown Analysis

Visualize drawdowns over time to understand risk periods:

```python
from fxml4.visualization.performance_charts import plot_drawdowns

fig = plot_drawdowns(
    equity_df=equity_df,
    title="Portfolio Drawdowns",
    figsize=(12, 6)
)
```

![Drawdown Example](../../assets/drawdown_example.png)

### Monthly Returns Heatmap

Create heatmaps to identify seasonal patterns in returns:

```python
from fxml4.visualization.performance_charts import plot_monthly_returns_heatmap

fig = plot_monthly_returns_heatmap(
    monthly_returns_df=metrics.monthly_returns,
    title="Monthly Returns Heatmap",
    figsize=(14, 8),
    cmap="RdYlGn",
    annot=True
)
```

![Monthly Returns Heatmap Example](../../assets/monthly_returns_example.png)

### Market Regime Performance

Compare performance across different market regimes:

```python
from fxml4.visualization.performance_charts import plot_regime_performance

fig = plot_regime_performance(
    regime_performance_df=risk_analysis['by_regime'],
    metric="total_pnl",
    title="Performance by Market Regime"
)
```

### Trade Distribution Analysis

Analyze the distribution of trade returns:

```python
from fxml4.visualization.performance_charts import plot_trade_distribution

fig = plot_trade_distribution(
    trades=trades_list,
    title="Trade P&L Distribution",
    bins=20
)
```

### Strategy Comparison

Compare multiple strategies or parameter sets:

```python
from fxml4.visualization.performance_charts import plot_comparative_metrics

fig = plot_comparative_metrics(
    comparison_df=comparison_df,
    metrics=["sharpe_ratio", "max_drawdown_pct", "profit_factor"],
    title="Strategy Parameter Comparison"
)
```

### Monte Carlo Simulation Results

Visualize Monte Carlo simulation results to assess strategy robustness:

```python
from fxml4.visualization.performance_charts import plot_monte_carlo_simulation

fig = plot_monte_carlo_simulation(
    simulation_results=mc_results,
    initial_capital=10000,
    title="Monte Carlo Simulation Results"
)
```

### Comprehensive Performance Dashboard

Create a comprehensive dashboard with multiple plots:

```python
from fxml4.visualization.performance_charts import create_performance_dashboard

figures = create_performance_dashboard(
    equity_curve=equity_df,
    trades=trades_list,
    benchmark_data=benchmark_df,
    risk_analysis=risk_analysis,
    monthly_returns=monthly_returns_df,
    figsize=(12, 8),
    save_path="output/dashboard"
)
```

## HTML and PDF Reports

The `fxml4.visualization.report_generator` module provides functionality to generate professional HTML and PDF reports:

### Creating HTML Reports

Generate HTML reports with embedded visualizations:

```python
from fxml4.visualization.report_generator import create_performance_report

# Generate figures for report
figures = create_performance_dashboard(equity_df, trades_list)

html_path = create_performance_report(
    strategy_name="FXML4 Strategy",
    metrics=metrics,
    equity_curve=equity_df,
    trades=trades_list,
    figures=figures,
    additional_data={"Monte Carlo Results": mc_results},
    output_dir="output/reports"
)
```

The generated HTML report includes:

- Strategy overview and key metrics
- Return and risk metrics tables
- Trade statistics
- Cost analysis
- Interactive visualizations
- Monthly returns heatmap
- Recent trades table

### Exporting to PDF

Convert HTML reports to PDF format for sharing:

```python
from fxml4.visualization.report_generator import export_to_pdf

pdf_path = export_to_pdf(html_path)
```

**Note:** PDF export requires the WeasyPrint library to be installed:

```bash
pip install weasyprint
```

### Custom Report Templates

You can customize report templates by providing your own Jinja2 template:

```python
html_path = create_performance_report(
    strategy_name="Custom Strategy Report",
    metrics=metrics,
    equity_curve=equity_df,
    trades=trades_list,
    template_path="path/to/template/directory"
)
```

## Helper Functions

### Converting Figures to Base64

Convert matplotlib figures to base64 strings for embedding in HTML:

```python
from fxml4.visualization.report_generator import figure_to_base64

img_str = figure_to_base64(fig)
```

### Converting DataFrames to HTML Tables

Format DataFrames as HTML tables with styling:

```python
from fxml4.visualization.report_generator import dataframe_to_html

html_table = dataframe_to_html(
    df=comparison_df,
    classes="table table-striped"
)
```

## Example: Creating a Complete Performance Report

Here's a complete example demonstrating how to generate a performance report:

```python
from fxml4.backtesting.performance_metrics import PerformanceAnalyzer
from fxml4.visualization.performance_charts import create_performance_dashboard
from fxml4.visualization.report_generator import create_performance_report, export_to_pdf

# Initialize performance analyzer
analyzer = PerformanceAnalyzer()

# Calculate performance metrics
metrics = analyzer.calculate_metrics(equity_df, trades_list)

# Run additional analyses
drawdowns = analyzer.analyze_drawdowns(equity_df)
risk_analysis = analyzer.risk_contribution_analysis(trades_list)
mc_results = analyzer.create_monte_carlo_simulation(trades_list)

# Create visualization dashboard
figures = create_performance_dashboard(
    equity_curve=equity_df,
    trades=trades_list,
    risk_analysis=risk_analysis,
    monthly_returns=metrics.monthly_returns
)

# Generate HTML report
html_path = create_performance_report(
    strategy_name="FXML4 Strategy Report",
    metrics=metrics,
    equity_curve=equity_df,
    trades=trades_list,
    figures=figures,
    additional_data={
        "Monte Carlo Analysis": {
            "Probability of Profit": f"{mc_results['probability_of_profit']:.2%}",
            "95th Percentile Final Equity": f"${mc_results['final_equity_percentiles'][95]:,.2f}",
            "5th Percentile Final Equity": f"${mc_results['final_equity_percentiles'][5]:,.2f}",
            "Probability of >10% Drawdown": f"{mc_results['probability_of_10pct_drawdown']:.2%}"
        },
        "Top Drawdowns": drawdowns.to_dict()
    },
    output_dir="output/reports"
)

# Export to PDF
pdf_path = export_to_pdf(html_path)

print(f"HTML Report: {html_path}")
print(f"PDF Report: {pdf_path}")
```

## Dependencies

The visualization and reporting modules have the following dependencies:

- matplotlib (required for all plots)
- seaborn (required for heatmaps and enhanced styling)
- jinja2 (required for HTML report generation)
- weasyprint (optional, required for PDF export)

These dependencies can be installed via:

```bash
pip install matplotlib seaborn jinja2 weasyprint
```
