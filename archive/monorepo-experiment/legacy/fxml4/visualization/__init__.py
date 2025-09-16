"""Visualization package for FXML4.

This package provides visualization tools for trading results and analysis.
"""

from .performance_charts import (
    plot_equity_curve, plot_drawdowns, plot_monthly_returns_heatmap,
    plot_regime_performance, plot_trade_distribution, plot_comparative_metrics,
    plot_monte_carlo_simulation, create_performance_dashboard
)