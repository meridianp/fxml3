"""Performance analysis example.

This script demonstrates how to use the performance metrics and visualization tools
to analyze backtesting results.
"""

import os
from datetime import datetime, timedelta
from typing import Any, Dict, List

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from fxml4.backtesting.backtest_engine import run_backtest
from fxml4.backtesting.performance_metrics import PerformanceAnalyzer, ScenarioAnalyzer
from fxml4.visualization.performance_charts import (
    create_performance_dashboard,
    plot_comparative_metrics,
    plot_drawdowns,
    plot_equity_curve,
    plot_monthly_returns_heatmap,
    plot_regime_performance,
    plot_trade_distribution,
)

# Create output directory for plots
output_dir = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "output", "performance_analysis"
)
os.makedirs(output_dir, exist_ok=True)


def generate_sample_data(days: int = 365, initial_capital: float = 10000.0):
    """Generate sample backtest data for demonstration.

    Args:
        days: Number of days of data to generate.
        initial_capital: Initial capital amount.

    Returns:
        Tuple of (equity_curve, trades, benchmark_data)
    """
    # Generate dates
    end_date = datetime.now().date()
    start_date = end_date - timedelta(days=days)
    dates = pd.date_range(start=start_date, end=end_date, freq="D")

    # Generate synthetic equity curve with some realistic patterns
    equity = np.array([initial_capital])
    np.random.seed(42)  # For reproducibility

    # Generate returns with a slight positive drift and realistic volatility
    daily_returns = np.random.normal(
        0.0005, 0.008, len(dates) - 1
    )  # mean 0.05%, std 0.8%

    # Add some autocorrelation and trending behavior
    for i in range(len(daily_returns) - 1):
        if i > 0:
            # Add some momentum - returns tend to continue in the same direction
            daily_returns[i + 1] += daily_returns[i] * 0.1

    # Add a market crash somewhere in the middle
    crash_start = len(dates) // 3
    crash_end = crash_start + 20
    daily_returns[crash_start:crash_end] = np.random.normal(
        -0.01, 0.015, crash_end - crash_start
    )

    # Calculate equity from returns
    for ret in daily_returns:
        equity = np.append(equity, equity[-1] * (1 + ret))

    # Create equity curve DataFrame
    equity_curve = pd.DataFrame({"timestamp": dates, "equity": equity})

    # Generate synthetic trades
    trades = []

    # Parameters for trade generation
    n_trades = 80
    win_rate = 0.55
    avg_win_pct = 0.03  # 3%
    avg_loss_pct = 0.015  # 1.5%
    win_std = 0.01
    loss_std = 0.005

    # Generate trades with timestamps spread out across the period
    for i in range(n_trades):
        # Select a random entry date (excluding last 10 days)
        entry_idx = np.random.randint(0, len(dates) - 10)
        entry_time = dates[entry_idx]

        # Hold between 1 and 10 days
        hold_days = np.random.randint(1, 10)
        exit_time = entry_time + timedelta(days=hold_days)

        # Determine if trade is a win or loss
        is_win = np.random.random() < win_rate

        # Calculate trade P&L
        if is_win:
            pnl_pct = np.random.normal(avg_win_pct, win_std)
        else:
            pnl_pct = -np.random.normal(avg_loss_pct, loss_std)

        # Entry price is arbitrary for this example
        entry_price = 100.0
        exit_price = entry_price * (1 + pnl_pct)

        # Trade size is 10% of initial capital
        size = initial_capital * 0.1 / entry_price
        pnl = (exit_price - entry_price) * size

        # Create trade record
        trade = {
            "entry_time": entry_time,
            "exit_time": exit_time,
            "entry_price": entry_price,
            "exit_price": exit_price,
            "pnl": pnl,
            "pnl_pct": pnl_pct * 100,  # Convert to percentage
            "size": size,
            "symbol": np.random.choice(["EURUSD", "GBPUSD", "USDJPY"]),
            "side": "buy" if np.random.random() > 0.3 else "sell",
            "commission": np.random.uniform(5, 15),
            "slippage": np.random.uniform(1, 5),
            "metadata": {
                "market_regime": np.random.choice(
                    ["trend", "range", "volatile", "choppy"]
                ),
                "entry_signal": np.random.choice(
                    ["breakout", "pullback", "reversal", "pattern"]
                ),
                "exit_signal": np.random.choice(["target", "stop", "time", "reversal"]),
            },
        }

        trades.append(trade)

    # Generate benchmark data (e.g., S&P 500)
    benchmark_equity = np.array([initial_capital])
    benchmark_returns = np.random.normal(
        0.0003, 0.006, len(dates) - 1
    )  # Lower return, lower volatility

    for ret in benchmark_returns:
        benchmark_equity = np.append(benchmark_equity, benchmark_equity[-1] * (1 + ret))

    benchmark_data = pd.DataFrame(
        {"timestamp": dates, "close": benchmark_equity}
    ).set_index("timestamp")

    return equity_curve, trades, benchmark_data


def analyze_single_backtest():
    """Analyze a single backtest with comprehensive metrics."""
    print("Analyzing single backtest...")

    # Generate sample data
    equity_curve, trades, benchmark_data = generate_sample_data()

    # Create performance analyzer
    analyzer = PerformanceAnalyzer(
        risk_free_rate=0.015,  # 1.5% annual risk-free rate
        benchmark_data=benchmark_data,
    )

    # Calculate metrics
    metrics = analyzer.calculate_metrics(equity_curve, trades)

    # Print summary metrics
    print("\nPerformance Summary:")
    print(metrics.summary())

    # Calculate additional analyses
    drawdowns = analyzer.analyze_drawdowns(equity_curve, min_drawdown_pct=0.02, top_n=3)
    risk_analysis = analyzer.risk_contribution_analysis(trades)
    monte_carlo = analyzer.create_monte_carlo_simulation(
        trades, initial_capital=10000.0, num_simulations=500
    )

    # Print drawdown analysis
    print("\nTop Drawdowns:")
    print(drawdowns)

    # Print risk analysis by market regime
    print("\nPerformance by Market Regime:")
    print(risk_analysis["by_regime"])

    # Print symbol analysis
    print("\nPerformance by Symbol:")
    print(risk_analysis["by_symbol"])

    # Print Monte Carlo simulation results
    print("\nMonte Carlo Simulation Results:")
    final_equity_percentiles = monte_carlo["final_equity_percentiles"]
    print(f"5th Percentile: ${final_equity_percentiles[5]:,.2f}")
    print(f"50th Percentile: ${final_equity_percentiles[50]:,.2f}")
    print(f"95th Percentile: ${final_equity_percentiles[95]:,.2f}")
    print(f"Probability of Profit: {monte_carlo['probability_of_profit']:.2%}")

    # Create and save visualizations
    print("\nCreating visualizations...")

    # Create equity curve plot
    fig1 = plot_equity_curve(equity_curve, benchmark_df=benchmark_data)
    fig1.savefig(
        os.path.join(output_dir, "equity_curve.png"), dpi=300, bbox_inches="tight"
    )

    # Create drawdown plot
    fig2 = plot_drawdowns(equity_curve)
    fig2.savefig(
        os.path.join(output_dir, "drawdowns.png"), dpi=300, bbox_inches="tight"
    )

    # Create trade distribution plot
    fig3 = plot_trade_distribution(trades)
    fig3.savefig(
        os.path.join(output_dir, "trade_distribution.png"), dpi=300, bbox_inches="tight"
    )

    # Create monthly returns heatmap
    fig4 = plot_monthly_returns_heatmap(metrics.monthly_returns)
    fig4.savefig(
        os.path.join(output_dir, "monthly_returns_heatmap.png"),
        dpi=300,
        bbox_inches="tight",
    )

    # Create regime performance plot
    fig5 = plot_regime_performance(risk_analysis["by_regime"], metric="total_pnl")
    fig5.savefig(
        os.path.join(output_dir, "regime_performance.png"), dpi=300, bbox_inches="tight"
    )

    print(f"Visualizations saved to {output_dir}")


def compare_multiple_scenarios():
    """Compare multiple trading scenarios."""
    print("\nComparing multiple trading scenarios...")

    # Create scenario analyzer
    scenario_analyzer = ScenarioAnalyzer()

    # Generate three scenarios with different parameters
    # 1. Baseline scenario
    equity1, trades1, benchmark = generate_sample_data(
        days=365, initial_capital=10000.0
    )

    # 2. Higher win rate scenario
    np.random.seed(43)  # Different seed for variation
    equity2 = equity1.copy()
    equity2["equity"] = equity2["equity"] * 1.15  # 15% better performance

    # Modify trades with higher win rate
    trades2 = []
    for trade in trades1:
        new_trade = trade.copy()
        # 60% chance of increasing return, 40% chance of decreasing
        if np.random.random() < 0.6:
            new_trade["pnl"] *= 1.2  # Increase P&L by 20%
        else:
            new_trade["pnl"] *= 0.9  # Decrease P&L by 10%
        trades2.append(new_trade)

    # 3. Lower drawdown scenario
    np.random.seed(44)  # Different seed for variation
    equity3 = equity1.copy()
    # Smooth out the biggest drawdowns
    equity_array = equity3["equity"].values
    for i in range(50, len(equity_array) - 50):
        if equity_array[i] < equity_array[i - 30] * 0.9:  # If it's a big drawdown
            # Reduce the drawdown
            equity_array[i : i + 30] = equity_array[i : i + 30] * 1.05
    equity3["equity"] = equity_array

    # Copy trades but with less severe losses
    trades3 = []
    for trade in trades1:
        new_trade = trade.copy()
        if new_trade["pnl"] < 0:
            new_trade["pnl"] *= 0.7  # Reduce losses by 30%
        trades3.append(new_trade)

    # Add scenarios to the analyzer
    scenario_analyzer.add_scenario(
        name="Baseline",
        equity_curve=equity1,
        trades=trades1,
        description="Standard strategy configuration",
        parameters={"stop_loss": 0.02, "take_profit": 0.04, "risk_per_trade": 0.01},
    )

    scenario_analyzer.add_scenario(
        name="Higher Win Rate",
        equity_curve=equity2,
        trades=trades2,
        description="Optimized entry conditions for higher win rate",
        parameters={"stop_loss": 0.025, "take_profit": 0.05, "risk_per_trade": 0.01},
    )

    scenario_analyzer.add_scenario(
        name="Lower Drawdown",
        equity_curve=equity3,
        trades=trades3,
        description="Enhanced risk management for lower drawdowns",
        parameters={"stop_loss": 0.015, "take_profit": 0.035, "risk_per_trade": 0.008},
    )

    # Compare scenarios
    comparison = scenario_analyzer.compare_scenarios(
        key_metrics=[
            "total_return_pct",
            "annualized_return",
            "sharpe_ratio",
            "max_drawdown_pct",
            "win_rate",
            "profit_factor",
        ]
    )

    # Print comparison
    print("\nScenario Comparison:")
    print(comparison)

    # Analyze parameter sensitivity
    sensitivity = scenario_analyzer.analyze_parameter_sensitivity(
        "stop_loss", "sharpe_ratio"
    )
    print("\nParameter Sensitivity Analysis:")
    print(sensitivity)

    # Find optimal scenario
    optimal_name, optimal_scenario = scenario_analyzer.find_optimal_scenario(
        "sharpe_ratio"
    )
    print(f"\nOptimal scenario based on Sharpe ratio: {optimal_name}")
    print(f"Sharpe ratio: {optimal_scenario['metrics'].sharpe_ratio:.2f}")

    # Compare equity curves
    equity_comparison = scenario_analyzer.compare_equity_curves()

    # Create and save comparison visualizations
    print("\nCreating comparison visualizations...")

    # Plot comparative metrics
    fig1 = plot_comparative_metrics(comparison)
    fig1.savefig(
        os.path.join(output_dir, "scenario_comparison.png"),
        dpi=300,
        bbox_inches="tight",
    )

    # Plot equity curves comparison
    fig2 = plt.figure(figsize=(10, 6))
    for col in equity_comparison.columns:
        plt.plot(equity_comparison.index, equity_comparison[col], label=col)
    plt.title("Equity Curve Comparison")
    plt.xlabel("Date")
    plt.ylabel("Equity")
    plt.legend()
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    fig2.savefig(
        os.path.join(output_dir, "equity_comparison.png"), dpi=300, bbox_inches="tight"
    )

    print(f"Comparison visualizations saved to {output_dir}")


def generate_report():
    """Generate an HTML performance report."""
    print("\nGenerating performance report...")

    # Generate sample data
    equity_curve, trades, benchmark_data = generate_sample_data()

    # Create performance analyzer
    analyzer = PerformanceAnalyzer(
        risk_free_rate=0.015,  # 1.5% annual risk-free rate
        benchmark_data=benchmark_data,
    )

    # Calculate metrics
    metrics = analyzer.calculate_metrics(equity_curve, trades)

    # Create visualizations for the report
    figures = []

    # Equity curve plot
    fig1 = plot_equity_curve(equity_curve, benchmark_df=benchmark_data)
    figures.append(fig1)

    # Drawdown plot
    fig2 = plot_drawdowns(equity_curve)
    figures.append(fig2)

    # Trade distribution plot
    fig3 = plot_trade_distribution(trades)
    figures.append(fig3)

    # Monthly returns heatmap
    fig4 = plot_monthly_returns_heatmap(metrics.monthly_returns)
    figures.append(fig4)

    # Calculate additional analyses for the report
    risk_analysis = analyzer.risk_contribution_analysis(trades)
    monte_carlo = analyzer.create_monte_carlo_simulation(
        trades, initial_capital=10000.0, num_simulations=500
    )

    # Create a figure for regime performance
    fig5 = plot_regime_performance(risk_analysis["by_regime"], metric="total_pnl")
    figures.append(fig5)

    # Additional data to include in the report
    additional_data = {
        "Strategy Parameters": {
            "risk_per_trade": "2%",
            "stop_loss": "1.5%",
            "take_profit": "3%",
            "timeframe": "4h",
            "market_data_source": "Interactive Brokers",
        },
        "Monte Carlo Simulation": {
            "5th Percentile": f"${monte_carlo['final_equity_percentiles'][5]:,.2f}",
            "50th Percentile": f"${monte_carlo['final_equity_percentiles'][50]:,.2f}",
            "95th Percentile": f"${monte_carlo['final_equity_percentiles'][95]:,.2f}",
            "Probability of Profit": f"{monte_carlo['probability_of_profit']:.2%}",
            "Probability of >10% Drawdown": f"{monte_carlo['probability_of_10pct_drawdown']:.2%}",
        },
    }

    try:
        # Import the report generator module
        from fxml4.visualization.report_generator import (
            create_performance_report,
            export_to_pdf,
        )

        # Create output directory for reports
        report_dir = os.path.join(output_dir, "reports")
        os.makedirs(report_dir, exist_ok=True)

        # Generate HTML report
        html_path = create_performance_report(
            strategy_name="Integrated Strategy Demo",
            metrics=metrics,
            equity_curve=equity_curve,
            trades=trades,
            figures=figures,
            additional_data=additional_data,
            output_dir=report_dir,
        )

        print(f"HTML report generated: {html_path}")

        # Try to export to PDF if WeasyPrint is available
        try:
            pdf_path = export_to_pdf(html_path)
            if pdf_path:
                print(f"PDF report generated: {pdf_path}")
        except ImportError:
            print("WeasyPrint not available. PDF report not generated.")

    except ImportError as e:
        print(f"Error generating report: {e}")
        print("Make sure jinja2 is installed: pip install jinja2")


def main():
    """Run the performance analysis example."""
    # Analyze a single backtest
    analyze_single_backtest()

    # Compare multiple scenarios
    compare_multiple_scenarios()

    # Generate performance report
    generate_report()

    print(
        "\nPerformance analysis complete. Check the output directory for visualizations and reports."
    )


if __name__ == "__main__":
    main()
