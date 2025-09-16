"""Example demonstrating the comprehensive performance metrics capabilities.

This script shows how to:
1. Run a backtest using both standard and event-driven engines
2. Access and use the performance metrics
3. Generate comprehensive performance reports
4. Visualize performance analytics including drawdowns and Monte Carlo simulations
"""

import logging
import sys
from datetime import datetime, timedelta
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

# Add the project root to Python path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fxml4.backtesting.backtest_engine import BacktestEngine, OrderSide
from fxml4.backtesting.event_driven_engine import (
    EventDrivenEngine,
    run_event_driven_backtest,
)
from fxml4.backtesting.performance_metrics import PerformanceAnalyzer, ScenarioAnalyzer
from fxml4.visualization.performance_charts import (
    create_performance_dashboard,
    plot_drawdowns,
    plot_equity_curve,
    plot_monte_carlo_simulation,
    plot_monthly_returns_heatmap,
    plot_trade_distribution,
)
from fxml4.visualization.report_generator import (
    create_performance_report,
    export_to_pdf,
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

# Reduce log volume for the demo
logging.getLogger("matplotlib").setLevel(logging.WARNING)


class MovingAverageCrossoverStrategy:
    """Simple moving average crossover strategy for demonstration."""

    def __init__(self, fast_window=20, slow_window=50):
        """Initialize with MA windows.

        Args:
            fast_window: Fast moving average window.
            slow_window: Slow moving average window.
        """
        self.fast_window = fast_window
        self.slow_window = slow_window
        self.name = f"MA_Cross_{fast_window}_{slow_window}"

    def __call__(self, data, idx, params):
        """Generate signals based on moving average crossover.

        Args:
            data: Price data.
            idx: Current index.
            params: Strategy parameters.

        Returns:
            Dictionary of signals.
        """
        signals = {}

        # Skip if not enough data
        if idx < self.slow_window:
            return signals

        # Calculate moving averages
        prices = data["close"].values
        fast_ma = np.mean(prices[idx - self.fast_window + 1 : idx + 1])
        slow_ma = np.mean(prices[idx - self.slow_window + 1 : idx + 1])

        # Check for previous values if possible
        if idx > 0:
            prev_prices = data["close"].values
            prev_fast_ma = np.mean(prev_prices[idx - self.fast_window : idx])
            prev_slow_ma = np.mean(prev_prices[idx - self.slow_window : idx])

            # Buy signal: fast MA crosses above slow MA
            if prev_fast_ma <= prev_slow_ma and fast_ma > slow_ma:
                signals["entry"] = True
                signals["direction"] = "buy"
                signals["risk_pct"] = 0.02
                signals["stop_loss"] = data["close"].iloc[idx] * 0.98  # 2% stop loss

            # Sell signal: fast MA crosses below slow MA
            elif prev_fast_ma >= prev_slow_ma and fast_ma < slow_ma:
                signals["exit"] = True

        return signals


def generate_sample_data(start_date="2022-01-01", end_date="2022-12-31", seed=42):
    """Generate sample price data for backtesting.

    Args:
        start_date: Start date for data.
        end_date: End date for data.
        seed: Random seed for reproducibility.

    Returns:
        DataFrame with price data.
    """
    np.random.seed(seed)

    # Create date range
    dates = pd.date_range(start=start_date, end=end_date, freq="D")

    # Generate price series with trend, seasonality, and noise
    time = np.arange(len(dates))
    trend = 0.0001 * time
    seasonality = 0.05 * np.sin(2 * np.pi * time / 252)
    noise = np.random.normal(0, 0.01, len(dates))

    change = trend + seasonality + noise
    price = 100.0
    prices = [price]

    for c in change[1:]:
        price = price * (1 + c)
        prices.append(price)

    # Create OHLC data
    data = pd.DataFrame(
        {
            "time": dates,
            "open": prices,
            "high": [p * (1 + np.random.uniform(0, 0.005)) for p in prices],
            "low": [p * (1 - np.random.uniform(0, 0.005)) for p in prices],
            "close": [p * (1 + np.random.normal(0, 0.001)) for p in prices],
            "volume": np.random.lognormal(mean=12, sigma=1, size=len(dates)),
            "symbol": "EXAMPLE",
        }
    )

    return data


def event_driven_strategy(symbol, current_bar, market_data, portfolio):
    """Event-driven strategy for moving average crossover.

    Args:
        symbol: Market symbol.
        current_bar: Current price bar.
        market_data: Historical market data.
        portfolio: Portfolio instance.

    Returns:
        Dictionary of signals.
    """
    # Skip if not enough data
    if market_data is None or len(market_data) < 50:
        return {}

    # Calculate moving averages
    fast_window = 20
    slow_window = 50

    close_prices = market_data["close"]
    fast_ma = close_prices.rolling(window=fast_window).mean()
    slow_ma = close_prices.rolling(window=slow_window).mean()

    # Get current and previous values
    current_fast = fast_ma.iloc[-1]
    current_slow = slow_ma.iloc[-1]

    signals = {}

    # Check for crossovers if we have enough data
    if len(fast_ma) > 1 and len(slow_ma) > 1:
        prev_fast = fast_ma.iloc[-2]
        prev_slow = slow_ma.iloc[-2]

        # Buy signal: fast MA crosses above slow MA
        if prev_fast <= prev_slow and current_fast > current_slow:
            signals["entry"] = {
                "side": "buy",
                "order_type": "market",
                "risk_pct": 0.02,
                "stop_loss": current_bar["close"] * 0.98,
            }

        # Sell signal: fast MA crosses below slow MA and we have a position
        elif prev_fast >= prev_slow and current_fast < current_slow:
            if portfolio and symbol in portfolio.positions:
                signals["exit"] = {
                    "order_type": "market",
                }

    return signals


def run_standard_backtest():
    """Run backtest using the standard backtest engine.

    Returns:
        Backtest results object.
    """
    print("\n=== Running Standard Backtest Engine ===")

    # Generate sample data
    data = generate_sample_data()

    # Create strategy
    strategy = MovingAverageCrossoverStrategy()

    # Create backtest engine
    engine = BacktestEngine(
        {
            "initial_capital": 100000,
            "commission": 0.001,
            "slippage": 0.0005,
        }
    )

    # Run backtest
    result = engine.run(
        strategy=strategy,
        data=data,
        strategy_params={"symbol": "EXAMPLE"},
    )

    return result


def run_event_driven_backtest():
    """Run backtest using the event-driven backtest engine.

    Returns:
        Backtest results object.
    """
    print("\n=== Running Event-Driven Backtest Engine ===")

    # Generate sample data
    data = generate_sample_data()

    # Run event-driven backtest
    result = run_event_driven_backtest(
        strategy=event_driven_strategy,
        data=data,
        initial_capital=100000,
        fee_model="percentage",
    )

    return result


def run_scenario_comparison():
    """Run multiple backtests with different parameters for comparison.

    Returns:
        ScenarioAnalyzer with results.
    """
    print("\n=== Running Scenario Comparison ===")

    # Generate sample data
    data = generate_sample_data()

    # Initialize scenario analyzer
    analyzer = ScenarioAnalyzer()

    # Run backtests with different parameters
    for fast_window in [10, 20, 30]:
        for slow_window in [40, 50, 60]:
            # Skip invalid combinations
            if fast_window >= slow_window:
                continue

            # Create strategy with specific parameters
            strategy = MovingAverageCrossoverStrategy(
                fast_window=fast_window,
                slow_window=slow_window,
            )

            # Create backtest engine
            engine = BacktestEngine(
                {
                    "initial_capital": 100000,
                    "commission": 0.001,
                    "slippage": 0.0005,
                }
            )

            # Run backtest
            result = engine.run(
                strategy=strategy,
                data=data,
                strategy_params={"symbol": "EXAMPLE"},
            )

            # Add scenario to analyzer
            analyzer.add_scenario(
                name=f"MA_{fast_window}_{slow_window}",
                equity_curve=result.equity_curve,
                trades=[
                    {
                        "entry_time": t.entry_timestamp,
                        "exit_time": t.exit_timestamp,
                        "symbol": t.symbol,
                        "side": t.side.value,
                        "pnl": t.pnl,
                    }
                    for t in result.trades
                ],
                parameters={
                    "fast_window": fast_window,
                    "slow_window": slow_window,
                },
                description=f"MA crossover with {fast_window}/{slow_window} windows",
            )

            print(f"  Completed scenario MA_{fast_window}_{slow_window}")

    return analyzer


def display_standard_results(result):
    """Display results from standard backtest engine.

    Args:
        result: Backtest result object.
    """
    print("\n=== Standard Backtest Results ===")
    print(result.get_summary())

    # Plot equity curve
    fig = plot_equity_curve(
        result.equity_curve, title="Equity Curve - Standard Backtest"
    )
    plt.show()

    # Plot drawdowns
    fig = plot_drawdowns(result.equity_curve, title="Drawdowns - Standard Backtest")
    plt.show()

    # Plot trade distribution
    trades_list = [
        {
            "pnl": t.pnl,
            "entry_time": t.entry_timestamp,
            "exit_time": t.exit_timestamp,
            "symbol": t.symbol,
            "side": t.side.value,
        }
        for t in result.trades
    ]

    fig = plot_trade_distribution(
        trades_list, title="Trade Distribution - Standard Backtest"
    )
    plt.show()

    # Extract monthly returns if available
    if result.performance_metrics and hasattr(
        result.performance_metrics, "monthly_returns"
    ):
        monthly_returns = result.performance_metrics.monthly_returns
        fig = plot_monthly_returns_heatmap(
            monthly_returns, title="Monthly Returns - Standard Backtest"
        )
        plt.show()

    # Plot Monte Carlo simulation if available
    if result.monte_carlo_results:
        fig = plot_monte_carlo_simulation(
            result.monte_carlo_results,
            initial_capital=result.initial_capital,
            title="Monte Carlo Simulation - Standard Backtest",
        )
        plt.show()


def display_event_driven_results(result):
    """Display results from event-driven backtest engine.

    Args:
        result: Backtest result object.
    """
    print("\n=== Event-Driven Backtest Results ===")
    print(result.get_summary())

    # Show advanced metrics if available
    if result.performance_metrics:
        print("\nAdvanced Metrics:")
        if hasattr(result.performance_metrics, "ulcer_index"):
            print(f"  Ulcer Index: {result.performance_metrics.ulcer_index:.4f}")
        if hasattr(result.performance_metrics, "cvar_95"):
            print(f"  CVaR (95%): {result.performance_metrics.cvar_95:.2f}%")
        if hasattr(result.performance_metrics, "recovery_factor"):
            print(
                f"  Recovery Factor: {result.performance_metrics.recovery_factor:.2f}"
            )
        if hasattr(result.performance_metrics, "kelly_percentage"):
            print(
                f"  Kelly Percentage: {result.performance_metrics.kelly_percentage:.2f}%"
            )

    # Create performance dashboard
    figures = create_performance_dashboard(
        equity_curve=result.equity_curve,
        trades=[
            {
                "entry_time": t.entry_timestamp,
                "exit_time": t.exit_timestamp,
                "symbol": t.symbol,
                "side": t.side.value,
                "pnl": t.pnl,
            }
            for t in result.trades
        ],
        risk_analysis=result.risk_analysis,
    )

    for fig in figures:
        plt.figure(fig.number)
        plt.show()


def display_scenario_comparison(analyzer):
    """Display results from scenario comparison.

    Args:
        analyzer: ScenarioAnalyzer with results.
    """
    print("\n=== Scenario Comparison Results ===")

    # Compare metrics across scenarios
    comparison = analyzer.compare_scenarios(
        key_metrics=[
            "total_return_pct",
            "sharpe_ratio",
            "max_drawdown_pct",
            "win_rate",
            "profit_factor",
        ]
    )

    print("\nMetric Comparison:")
    print(comparison)

    # Find optimal scenario based on Sharpe ratio
    best_name, best_scenario = analyzer.find_optimal_scenario("sharpe_ratio")
    print(f"\nBest scenario based on Sharpe ratio: {best_name}")
    print(f"  Sharpe Ratio: {best_scenario['metrics'].sharpe_ratio:.2f}")
    print(f"  Total Return: {best_scenario['metrics'].total_return_pct:.2f}%")
    print(f"  Max Drawdown: {best_scenario['metrics'].max_drawdown_pct:.2f}%")

    # Analyze parameter sensitivity to fast window
    sensitivity = analyzer.analyze_parameter_sensitivity("fast_window", "sharpe_ratio")

    print("\nParameter Sensitivity Analysis:")
    print(sensitivity)

    # Plot equity curves for all scenarios
    plt.figure(figsize=(12, 6))

    equity_curves = analyzer.compare_equity_curves()
    for name in equity_curves.columns:
        plt.plot(equity_curves.index, equity_curves[name], label=name)

    plt.title("Equity Curves for Different Scenarios")
    plt.xlabel("Date")
    plt.ylabel("Equity ($)")
    plt.legend()
    plt.grid(True)
    plt.tight_layout()
    plt.show()


def generate_performance_report(result):
    """Generate a performance report.

    Args:
        result: Backtest result object.
    """
    print("\n=== Generating Performance Report ===")

    # Generate report
    try:
        report_path = result.generate_report(
            output_dir="output/reports",
            include_figures=True,
            export_pdf=False,  # Set to True if WeasyPrint is installed
        )

        if report_path:
            print(f"Report generated successfully: {report_path}")
        else:
            print("Failed to generate report")

    except ImportError as e:
        print(f"Error generating report - missing dependencies: {e}")


def main():
    """Main execution function."""
    print("=== FXML4 Performance Metrics Example ===")

    # Run backtests
    std_result = run_standard_backtest()
    event_result = run_event_driven_backtest()

    # Display results
    display_standard_results(std_result)
    display_event_driven_results(event_result)

    # Run scenario comparison
    scenario_analyzer = run_scenario_comparison()
    display_scenario_comparison(scenario_analyzer)

    # Generate performance report
    generate_performance_report(std_result)

    print("\n=== Example Completed ===")


if __name__ == "__main__":
    main()
