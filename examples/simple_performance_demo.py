"""Simple performance metrics demonstration.

This script demonstrates the core functionality of the performance metrics module
without relying on the full FXML4 package installation.
"""

import os
import sys
from datetime import datetime, timedelta

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import scipy.stats as stats

# Add the parent directory to the path so we can import modules directly
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from fxml4.backtesting.performance_metrics import (
    PerformanceAnalyzer,
    PerformanceMetrics,
)

# Create output directory for plots
output_dir = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "..",
    "output",
    "performance_simple_demo",
)
os.makedirs(output_dir, exist_ok=True)


def generate_sample_data(days: int = 252, initial_capital: float = 10000.0):
    """Generate sample backtest data for demonstration.

    Args:
        days: Number of days of data to generate.
        initial_capital: Initial capital amount.

    Returns:
        Tuple of (equity_curve, trades)
    """
    # Generate dates
    end_date = datetime.now().date()
    start_date = end_date - timedelta(days=days)
    dates = pd.date_range(start=start_date, end=end_date, freq="D")

    # Generate synthetic equity curve
    np.random.seed(42)  # For reproducibility
    daily_returns = np.random.normal(
        0.0006, 0.01, len(dates) - 1
    )  # 0.06% mean daily return (15% annual)

    # Simulate a drawdown period
    drawdown_start = len(dates) // 3
    drawdown_end = drawdown_start + 20
    daily_returns[drawdown_start:drawdown_end] = np.random.normal(
        -0.008, 0.015, drawdown_end - drawdown_start
    )

    # Calculate equity curve
    equity = [initial_capital]
    for ret in daily_returns:
        equity.append(equity[-1] * (1 + ret))

    # Create equity curve DataFrame
    equity_df = pd.DataFrame({"timestamp": dates, "equity": equity})

    # Generate synthetic trades (50 trades over the period)
    trades = []
    for i in range(50):
        # Random entry date
        entry_idx = np.random.randint(0, len(dates) - 10)
        entry_date = dates[entry_idx]

        # Random holding period (1-10 days)
        holding_period = np.random.randint(1, 10)
        exit_date = entry_date + timedelta(days=holding_period)

        # 55% win rate
        is_win = np.random.random() < 0.55

        # P&L calculation
        if is_win:
            pnl = np.random.normal(200, 50)  # Winners average $200
        else:
            pnl = np.random.normal(-100, 30)  # Losers average -$100

        # Create trade record
        trade = {
            "entry_time": entry_date,
            "exit_time": exit_date,
            "pnl": pnl,
            "symbol": np.random.choice(["EURUSD", "GBPUSD", "USDJPY"]),
            "side": "buy" if np.random.random() > 0.5 else "sell",
        }

        trades.append(trade)

    return equity_df, trades


def main():
    """Run the simple performance metrics demonstration."""
    print("Running performance metrics demonstration...")

    # Generate sample data
    equity_curve, trades = generate_sample_data()

    # Create analyzer and calculate metrics
    analyzer = PerformanceAnalyzer(risk_free_rate=0.02)  # 2% risk-free rate
    metrics = analyzer.calculate_metrics(equity_curve, trades)

    # Print summary metrics
    print("\nPerformance Summary:")
    print(metrics.summary())

    # Additional analyses
    drawdowns = analyzer.analyze_drawdowns(equity_curve, min_drawdown_pct=0.02, top_n=3)
    print("\nTop Drawdowns:")
    print(drawdowns)

    # Monte Carlo simulation
    monte_carlo = analyzer.create_monte_carlo_simulation(trades, num_simulations=500)
    print("\nMonte Carlo Simulation Results:")
    percentiles = monte_carlo["final_equity_percentiles"]
    print(f"5th Percentile: ${percentiles[5]:,.2f}")
    print(f"50th Percentile: ${percentiles[50]:,.2f}")
    print(f"95th Percentile: ${percentiles[95]:,.2f}")
    print(f"Probability of Profit: {monte_carlo['probability_of_profit']:.2%}")

    # Create some visualizations manually since we don't have the visualization module
    # 1. Equity curve
    plt.figure(figsize=(10, 6))
    plt.plot(equity_curve["timestamp"], equity_curve["equity"])
    plt.title("Equity Curve")
    plt.xlabel("Date")
    plt.ylabel("Equity")
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(os.path.join(output_dir, "equity_curve.png"), dpi=300)

    # 2. Drawdowns
    plt.figure(figsize=(10, 6))
    drawdown_series = (
        equity_curve["equity"] / equity_curve["equity"].cummax() - 1
    ) * 100
    plt.fill_between(
        equity_curve["timestamp"], 0, drawdown_series, color="red", alpha=0.3
    )
    plt.title("Drawdowns")
    plt.xlabel("Date")
    plt.ylabel("Drawdown (%)")
    plt.grid(True, alpha=0.3)
    plt.gca().invert_yaxis()  # Invert y-axis to show drawdowns as negative values going down
    plt.tight_layout()
    plt.savefig(os.path.join(output_dir, "drawdowns.png"), dpi=300)

    # 3. Monthly returns heatmap
    if not metrics.monthly_returns.empty:
        plt.figure(figsize=(12, 8))
        plt.imshow(metrics.monthly_returns.values, cmap="RdYlGn", aspect="auto")
        plt.colorbar(label="Returns (%)")
        plt.title("Monthly Returns Heatmap")
        plt.xlabel("Month")
        plt.ylabel("Year")
        plt.tight_layout()
        plt.savefig(os.path.join(output_dir, "monthly_returns.png"), dpi=300)

    print(f"\nVisualizations saved to {output_dir}")
    print("Performance analysis complete.")


if __name__ == "__main__":
    main()
