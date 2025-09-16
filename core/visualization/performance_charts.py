"""Performance visualization module for backtesting results.

This module provides functions for visualizing performance metrics, equity curves,
drawdowns, and other analysis results.
"""

import logging
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

try:
    import matplotlib.dates as mdates
    import matplotlib.pyplot as plt
    import seaborn as sns
    from matplotlib.ticker import FuncFormatter

    HAS_PLOTTING = True
except ImportError:
    logger.warning(
        "Matplotlib and/or seaborn not installed. Plotting functions will not work."
    )
    HAS_PLOTTING = False


def plot_equity_curve(
    equity_df: pd.DataFrame,
    benchmark_df: Optional[pd.DataFrame] = None,
    title: str = "Equity Curve",
    figsize: Tuple[int, int] = (10, 6),
) -> Any:
    """Plot the equity curve with optional benchmark comparison.

    Args:
        equity_df: DataFrame with equity data (must have 'equity' column)
        benchmark_df: Optional benchmark DataFrame
        title: Plot title
        figsize: Figure size (width, height) in inches

    Returns:
        Matplotlib figure object or None if plotting libraries not available
    """
    if not HAS_PLOTTING:
        logger.warning("Matplotlib not installed. Cannot create plot.")
        return None

    fig, ax = plt.subplots(figsize=figsize)

    # Ensure we have datetime index for equity curve
    if (
        not isinstance(equity_df.index, pd.DatetimeIndex)
        and "timestamp" in equity_df.columns
    ):
        equity_df = equity_df.set_index("timestamp")

    # Plot equity curve
    ax.plot(equity_df.index, equity_df["equity"], label="Strategy", linewidth=2)

    # Plot benchmark if provided
    if benchmark_df is not None:
        # If benchmark is a DataFrame, assume it has a column named 'close'
        # If it's a Series, use it directly
        if isinstance(benchmark_df, pd.DataFrame):
            if "close" in benchmark_df.columns:
                bench_col = "close"
            else:
                bench_col = benchmark_df.columns[0]

            # Normalize benchmark to start at the same value as equity
            benchmark_values = benchmark_df[bench_col] * (
                equity_df["equity"].iloc[0] / benchmark_df[bench_col].iloc[0]
            )
            ax.plot(
                benchmark_df.index,
                benchmark_values,
                label="Benchmark",
                linewidth=2,
                alpha=0.7,
            )

    # Format the plot
    ax.set_title(title, fontsize=14)
    ax.set_xlabel("Date", fontsize=12)
    ax.set_ylabel("Equity", fontsize=12)
    ax.grid(True, alpha=0.3)
    ax.legend()

    # Format dates on x-axis
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m-%d"))
    plt.xticks(rotation=45)

    # Format y-axis with commas for thousands
    ax.yaxis.set_major_formatter(FuncFormatter(lambda x, _: f"${x:,.0f}"))

    plt.tight_layout()
    return fig


def plot_drawdowns(
    equity_df: pd.DataFrame,
    title: str = "Portfolio Drawdowns",
    figsize: Tuple[int, int] = (10, 6),
) -> Any:
    """Plot drawdowns over time.

    Args:
        equity_df: DataFrame with equity data (must have 'equity' column)
        title: Plot title
        figsize: Figure size (width, height) in inches

    Returns:
        Matplotlib figure object or None if plotting libraries not available
    """
    if not HAS_PLOTTING:
        logger.warning("Matplotlib not installed. Cannot create plot.")
        return None

    fig, ax = plt.subplots(figsize=figsize)

    # Ensure we have datetime index
    if (
        not isinstance(equity_df.index, pd.DatetimeIndex)
        and "timestamp" in equity_df.columns
    ):
        equity_df = equity_df.set_index("timestamp")

    # Calculate drawdown if not already in the DataFrame
    if "drawdown" not in equity_df.columns:
        equity_df["peak"] = equity_df["equity"].cummax()
        equity_df["drawdown"] = (
            (equity_df["equity"] - equity_df["peak"]) / equity_df["peak"] * 100
        )

    # Plot drawdown
    ax.fill_between(
        equity_df.index,
        0,
        equity_df["drawdown"],
        color="red",
        alpha=0.3,
        step="mid",
        label="Drawdown",
    )

    # Format the plot
    ax.set_title(title, fontsize=14)
    ax.set_xlabel("Date", fontsize=12)
    ax.set_ylabel("Drawdown (%)", fontsize=12)
    ax.grid(True, alpha=0.3)

    # Format dates on x-axis
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m-%d"))
    plt.xticks(rotation=45)

    # Format y-axis as percentage
    ax.yaxis.set_major_formatter(FuncFormatter(lambda x, _: f"{x:.1f}%"))

    # Invert y-axis for better visualization (drawdowns are negative)
    ax.invert_yaxis()

    plt.tight_layout()
    return fig


def plot_monthly_returns_heatmap(
    monthly_returns_df: pd.DataFrame,
    title: str = "Monthly Returns Heatmap",
    figsize: Tuple[int, int] = (12, 8),
    cmap: str = "RdYlGn",
    annot: bool = True,
) -> Any:
    """Plot monthly returns as a heatmap.

    Args:
        monthly_returns_df: DataFrame with monthly returns
        title: Plot title
        figsize: Figure size (width, height) in inches
        cmap: Colormap name
        annot: Whether to annotate cells with values

    Returns:
        Matplotlib figure object or None if plotting libraries not available
    """
    if not HAS_PLOTTING:
        logger.warning("Matplotlib not installed. Cannot create plot.")
        return None

    if monthly_returns_df.empty:
        logger.warning("Empty monthly returns DataFrame. Cannot create heatmap.")
        return None

    # Create figure
    fig, ax = plt.subplots(figsize=figsize)

    # Create heatmap using seaborn
    sns.heatmap(
        monthly_returns_df,
        cmap=cmap,
        annot=annot,
        fmt=".2f",
        center=0,
        linewidths=0.5,
        ax=ax,
        cbar_kws={"label": "Returns (%)"},
    )

    # Format the plot
    ax.set_title(title, fontsize=14)

    # Format month names
    month_names = [
        "Jan",
        "Feb",
        "Mar",
        "Apr",
        "May",
        "Jun",
        "Jul",
        "Aug",
        "Sep",
        "Oct",
        "Nov",
        "Dec",
        "Annual",
    ]
    ax.set_xticklabels(month_names, rotation=45)

    plt.tight_layout()
    return fig


def plot_regime_performance(
    regime_performance_df: pd.DataFrame,
    metric: str = "total_pnl",
    title: str = "Performance by Market Regime",
    figsize: Tuple[int, int] = (10, 6),
) -> Any:
    """Plot performance metrics by market regime.

    Args:
        regime_performance_df: DataFrame with regime performance data
        metric: Column name to plot
        title: Plot title
        figsize: Figure size (width, height) in inches

    Returns:
        Matplotlib figure object or None if plotting libraries not available
    """
    if not HAS_PLOTTING:
        logger.warning("Matplotlib not installed. Cannot create plot.")
        return None

    if regime_performance_df.empty or "regime" not in regime_performance_df.columns:
        logger.warning("Invalid regime performance DataFrame. Cannot create plot.")
        return None

    # Create figure
    fig, ax = plt.subplots(figsize=figsize)

    # Sort by the metric value
    sorted_df = regime_performance_df.sort_values(metric, ascending=False)

    # Create bar chart
    colors = ["green" if x > 0 else "red" for x in sorted_df[metric]]
    ax.bar(sorted_df["regime"], sorted_df[metric], color=colors)

    # Format the plot
    ax.set_title(title, fontsize=14)
    ax.set_xlabel("Market Regime", fontsize=12)
    ax.set_ylabel(metric.replace("_", " ").title(), fontsize=12)
    ax.grid(True, alpha=0.3, axis="y")

    plt.tight_layout()
    return fig


def plot_trade_distribution(
    trades: List[Dict[str, Any]],
    title: str = "Trade P&L Distribution",
    figsize: Tuple[int, int] = (10, 6),
    bins: int = 20,
) -> Any:
    """Plot the distribution of trade returns.

    Args:
        trades: List of trade dictionaries
        title: Plot title
        figsize: Figure size (width, height) in inches
        bins: Number of histogram bins

    Returns:
        Matplotlib figure object or None if plotting libraries not available
    """
    if not HAS_PLOTTING:
        logger.warning("Matplotlib not installed. Cannot create plot.")
        return None

    if not trades:
        logger.warning("Empty trades list. Cannot create plot.")
        return None

    # Extract P&L values
    pnl_values = [trade.get("pnl", 0) for trade in trades]

    # Create figure
    fig, ax = plt.subplots(figsize=figsize)

    # Create histogram
    ax.hist(pnl_values, bins=bins, color="skyblue", alpha=0.7, edgecolor="black")

    # Add vertical line at zero
    ax.axvline(x=0, color="red", linestyle="--", alpha=0.7)

    # Format the plot
    ax.set_title(title, fontsize=14)
    ax.set_xlabel("P&L", fontsize=12)
    ax.set_ylabel("Frequency", fontsize=12)
    ax.grid(True, alpha=0.3)

    # Add stats annotation
    win_count = sum(1 for p in pnl_values if p > 0)
    loss_count = sum(1 for p in pnl_values if p <= 0)
    win_rate = win_count / len(pnl_values) if pnl_values else 0
    avg_win = np.mean([p for p in pnl_values if p > 0]) if win_count > 0 else 0
    avg_loss = np.mean([p for p in pnl_values if p <= 0]) if loss_count > 0 else 0

    stats_text = (
        f"Win Rate: {win_rate:.2%}\n"
        f"Wins: {win_count} / Losses: {loss_count}\n"
        f"Avg Win: ${avg_win:.2f}\n"
        f"Avg Loss: ${avg_loss:.2f}"
    )

    ax.text(
        0.05,
        0.95,
        stats_text,
        transform=ax.transAxes,
        verticalalignment="top",
        bbox=dict(boxstyle="round", facecolor="white", alpha=0.7),
    )

    plt.tight_layout()
    return fig


def plot_comparative_metrics(
    comparison_df: pd.DataFrame,
    metrics: Optional[List[str]] = None,
    title: str = "Strategy Comparison",
    figsize: Tuple[int, int] = (12, 8),
) -> Any:
    """Plot comparative metrics for multiple strategies/scenarios.

    Args:
        comparison_df: DataFrame with strategies as rows and metrics as columns
        metrics: List of metric columns to plot (if None, uses all numeric columns)
        title: Plot title
        figsize: Figure size (width, height) in inches

    Returns:
        Matplotlib figure object or None if plotting libraries not available
    """
    if not HAS_PLOTTING:
        logger.warning("Matplotlib not installed. Cannot create plot.")
        return None

    if comparison_df.empty:
        logger.warning("Empty comparison DataFrame. Cannot create plot.")
        return None

    # Select metrics to plot
    if metrics is None:
        metrics = comparison_df.select_dtypes(include=[np.number]).columns.tolist()
    else:
        # Filter to only include existing columns
        metrics = [m for m in metrics if m in comparison_df.columns]

    if not metrics:
        logger.warning("No numeric metrics found for plotting.")
        return None

    # Number of metrics to plot
    n_metrics = len(metrics)

    # Create figure with subplots
    fig, axes = plt.subplots(nrows=n_metrics, figsize=figsize, sharex=True)
    if n_metrics == 1:
        axes = [axes]  # Make single axis iterable

    # Plot each metric
    for i, (ax, metric) in enumerate(zip(axes, metrics)):
        # Sort by the metric value (descending)
        sorted_df = comparison_df.sort_values(metric, ascending=False)

        # Create horizontal bar chart
        bars = ax.barh(sorted_df.index, sorted_df[metric], height=0.6)

        # Color bars based on value (positive green, negative red)
        for bar, value in zip(bars, sorted_df[metric]):
            bar.set_color("green" if value >= 0 else "red")

        # Add metric values as text
        for j, value in enumerate(sorted_df[metric]):
            text_color = "black"
            if abs(value) < sorted_df[metric].max() * 0.05:  # For very small values
                text_color = "black"
            ax.text(
                value + (sorted_df[metric].max() * 0.01),
                j,
                f"{value:.4g}",
                va="center",
                color=text_color,
            )

        # Format axis
        ax.set_title(metric.replace("_", " ").title(), fontsize=12)
        ax.grid(True, alpha=0.3)

    # Set overall title
    fig.suptitle(title, fontsize=14, y=0.98)

    plt.tight_layout(rect=[0, 0, 1, 0.96])
    return fig


def plot_monte_carlo_simulation(
    simulation_results: Dict[str, Any],
    initial_capital: float = 10000.0,
    title: str = "Monte Carlo Simulation Results",
    figsize: Tuple[int, int] = (10, 6),
) -> Any:
    """Plot Monte Carlo simulation results.

    Args:
        simulation_results: Dictionary with Monte Carlo simulation results
        initial_capital: Initial capital amount
        title: Plot title
        figsize: Figure size (width, height) in inches

    Returns:
        Matplotlib figure object or None if plotting libraries not available
    """
    if not HAS_PLOTTING:
        logger.warning("Matplotlib not installed. Cannot create plot.")
        return None

    if not simulation_results or "final_equity_percentiles" not in simulation_results:
        logger.warning("Invalid Monte Carlo simulation results. Cannot create plot.")
        return None

    # Create figure
    fig, ax = plt.subplots(figsize=figsize)

    # Extract percentiles
    percentiles = simulation_results["final_equity_percentiles"]

    # Sort percentiles by their values (the percentile number)
    sorted_percentiles = sorted(percentiles.items())

    # Plot percentiles
    x_values = [p[0] for p in sorted_percentiles]
    y_values = [p[1] for p in sorted_percentiles]

    ax.plot(x_values, y_values, "o-", linewidth=2, markersize=8)

    # Add reference line for initial capital
    ax.axhline(
        y=initial_capital,
        color="red",
        linestyle="--",
        label=f"Initial Capital (${initial_capital:,.0f})",
    )

    # Format the plot
    ax.set_title(title, fontsize=14)
    ax.set_xlabel("Percentile", fontsize=12)
    ax.set_ylabel("Final Equity", fontsize=12)
    ax.grid(True, alpha=0.3)

    # Format y-axis with commas for thousands
    ax.yaxis.set_major_formatter(FuncFormatter(lambda x, _: f"${x:,.0f}"))

    # Add stats annotation
    prob_profit = simulation_results.get("probability_of_profit", 0)
    prob_dd_10 = simulation_results.get("probability_of_10pct_drawdown", 0)

    stats_text = (
        f"Probability of Profit: {prob_profit:.2%}\n"
        f"Probability of >10% Drawdown: {prob_dd_10:.2%}\n"
        f"Mean Final Equity: ${simulation_results.get('final_equity_mean', 0):,.0f}"
    )

    ax.text(
        0.05,
        0.05,
        stats_text,
        transform=ax.transAxes,
        verticalalignment="bottom",
        bbox=dict(boxstyle="round", facecolor="white", alpha=0.7),
    )

    ax.legend()
    plt.tight_layout()
    return fig


def create_performance_dashboard(
    equity_curve: pd.DataFrame,
    trades: List[Dict[str, Any]],
    benchmark_data: Optional[pd.DataFrame] = None,
    risk_analysis: Optional[Dict[str, pd.DataFrame]] = None,
    monthly_returns: Optional[pd.DataFrame] = None,
    figsize: Tuple[int, int] = (12, 10),
    save_path: Optional[str] = None,
) -> List[Any]:
    """Create a comprehensive performance dashboard with multiple plots.

    Args:
        equity_curve: DataFrame with equity data
        trades: List of trade dictionaries
        benchmark_data: Optional benchmark price data
        risk_analysis: Optional risk contribution analysis results
        monthly_returns: Optional monthly returns DataFrame
        figsize: Base figure size for plots
        save_path: Optional path to save the dashboard plots

    Returns:
        List of Matplotlib figure objects or empty list if plotting not available
    """
    if not HAS_PLOTTING:
        logger.warning("Matplotlib not installed. Cannot create dashboard.")
        return []

    figures = []

    # 1. Equity Curve
    equity_fig = plot_equity_curve(
        equity_curve,
        benchmark_df=benchmark_data,
        title="Strategy Equity Curve",
        figsize=figsize,
    )
    figures.append(equity_fig)

    # 2. Drawdowns
    drawdown_fig = plot_drawdowns(
        equity_curve, title="Strategy Drawdowns", figsize=figsize
    )
    figures.append(drawdown_fig)

    # 3. Trade Distribution
    trade_dist_fig = plot_trade_distribution(
        trades, title="Trade P&L Distribution", figsize=figsize
    )
    figures.append(trade_dist_fig)

    # 4. Monthly Returns Heatmap (if available)
    if monthly_returns is not None and not monthly_returns.empty:
        heatmap_fig = plot_monthly_returns_heatmap(
            monthly_returns, title="Monthly Returns Heatmap", figsize=figsize
        )
        figures.append(heatmap_fig)

    # 5. Regime Performance (if available)
    if risk_analysis is not None and "by_regime" in risk_analysis:
        regime_fig = plot_regime_performance(
            risk_analysis["by_regime"],
            title="Performance by Market Regime",
            figsize=figsize,
        )
        figures.append(regime_fig)

    # Save figures if path provided
    if save_path:
        for i, fig in enumerate(figures):
            if fig is not None:
                fig.savefig(
                    f"{save_path}/performance_plot_{i+1}.png",
                    dpi=300,
                    bbox_inches="tight",
                )

    return figures
