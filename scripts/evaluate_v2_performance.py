#!/usr/bin/env python
"""Performance evaluation of Enhanced Production System V2."""

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))

import json
import os
import warnings
from datetime import datetime, timedelta
from typing import Dict, List, Optional

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns

warnings.filterwarnings("ignore")

# Import utilities
from fxml4.utils.performance_metrics import (
    calculate_calmar_ratio,
    calculate_expectancy,
    calculate_max_drawdown,
    calculate_profit_factor,
    calculate_sharpe_ratio,
    calculate_sortino_ratio,
    calculate_win_rate,
)

# Import V2 system
from scripts.enhanced_production_system_v2 import (
    EnhancedProductionConfigV2,
    EnhancedProductionSystemV2,
)

# Set up plotting style
plt.style.use("seaborn-v0_8-darkgrid")
sns.set_palette("husl")


def generate_test_data(symbol: str, days: int = 120) -> pd.DataFrame:
    """Generate realistic test data for evaluation."""

    # Generate 4H bars
    dates = pd.date_range(end=datetime.now(), periods=days * 6, freq="4h")

    # Base prices
    base_prices = {
        "EURUSD": 1.0850,
        "GBPUSD": 1.2700,
        "USDJPY": 155.00,
        "AUDUSD": 0.6600,
    }

    base_price = base_prices.get(symbol, 1.0000)

    # Generate realistic price movement
    np.random.seed(42)

    # Add trend and volatility
    trend = np.linspace(0, 0.02, len(dates))  # 2% uptrend
    volatility = 0.0008 + 0.0002 * np.sin(
        np.linspace(0, 4 * np.pi, len(dates))
    )  # Varying volatility

    # Generate returns
    returns = trend / len(dates) + np.random.randn(len(dates)) * volatility
    prices = base_price * np.exp(np.cumsum(returns))

    # Create OHLCV data
    data = pd.DataFrame(index=dates)
    data["close"] = prices
    data["open"] = data["close"].shift(1).fillna(prices[0]) * (
        1 + np.random.randn(len(dates)) * 0.0001
    )
    data["high"] = np.maximum(data["open"], data["close"]) * (
        1 + abs(np.random.randn(len(dates))) * 0.0003
    )
    data["low"] = np.minimum(data["open"], data["close"]) * (
        1 - abs(np.random.randn(len(dates))) * 0.0003
    )
    data["volume"] = np.random.randint(1000, 5000, len(dates))

    # Add technical indicators
    data["sma_20"] = data["close"].rolling(20).mean()
    data["sma_50"] = data["close"].rolling(50).mean()
    data["ema_12"] = data["close"].ewm(span=12).mean()
    data["ema_26"] = data["close"].ewm(span=26).mean()

    # RSI
    delta = data["close"].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    data["rsi_14"] = 100 - (100 / (1 + rs))

    # ATR
    high_low = data["high"] - data["low"]
    high_close = np.abs(data["high"] - data["close"].shift())
    low_close = np.abs(data["low"] - data["close"].shift())
    ranges = pd.concat([high_low, high_close, low_close], axis=1)
    true_range = np.max(ranges, axis=1)
    data["atr_14"] = true_range.rolling(14).mean()

    # Bollinger Bands
    data["bb_middle"] = data["close"].rolling(20).mean()
    bb_std = data["close"].rolling(20).std()
    data["bb_upper"] = data["bb_middle"] + 2 * bb_std
    data["bb_lower"] = data["bb_middle"] - 2 * bb_std

    # Fill NaN values
    data.fillna(method="ffill", inplace=True)
    data.fillna(method="bfill", inplace=True)

    return data


def run_backtest(
    data: pd.DataFrame, symbol: str, config: EnhancedProductionConfigV2
) -> Dict:
    """Run backtest with Enhanced System V2."""

    print(f"\nRunning backtest for {symbol}...")

    system = EnhancedProductionSystemV2(config)

    # Track metrics
    equity_curve = [config.initial_capital]
    timestamps = [data.index[0]]
    signals_analyzed = 0
    signals_generated = 0

    # Run through data
    for i in range(100, len(data)):
        if i % 200 == 0:
            progress = (i / len(data)) * 100
            print(f"  Progress: {progress:.1f}% - Equity: ${system.capital:.2f}")

        current_time = data.index[i]
        current_bar = data.iloc[i]
        historical_data = data.iloc[: i + 1]

        # Update positions
        system.update_positions(symbol, current_bar, current_time)

        # Generate signal every 4 bars (16 hours)
        if i % 4 == 0 and len(system.positions) < config.max_positions:
            signals_analyzed += 1
            signal = system.generate_combined_signal(
                historical_data, symbol, current_time
            )

            if signal:
                signals_generated += 1
                system.execute_trade(signal, current_bar, current_time, symbol)

        # Track equity
        equity_curve.append(system.capital)
        timestamps.append(current_time)

    # Close remaining positions
    for position_id in list(system.positions.keys()):
        system._close_position(
            position_id, data.iloc[-1]["close"], data.index[-1], "Backtest End"
        )

    # Calculate metrics
    equity_series = pd.Series(equity_curve, index=timestamps)
    returns = equity_series.pct_change().dropna()

    # Additional metrics
    winning_trades = [t for t in system.trades if t["pnl"] > 0]
    losing_trades = [t for t in system.trades if t["pnl"] <= 0]

    results = {
        "symbol": symbol,
        "initial_capital": config.initial_capital,
        "final_capital": system.capital,
        "total_return": (system.capital - config.initial_capital)
        / config.initial_capital,
        "sharpe_ratio": calculate_sharpe_ratio(
            returns, periods_per_year=1460
        ),  # 4H bars
        "sortino_ratio": calculate_sortino_ratio(returns, periods_per_year=1460),
        "max_drawdown": calculate_max_drawdown(equity_series),
        "calmar_ratio": calculate_calmar_ratio(
            returns, equity_series, periods_per_year=1460
        ),
        "total_trades": len(system.trades),
        "winning_trades": len(winning_trades),
        "losing_trades": len(losing_trades),
        "win_rate": calculate_win_rate(system.trades),
        "profit_factor": calculate_profit_factor(system.trades),
        "expectancy": calculate_expectancy(system.trades),
        "signals_analyzed": signals_analyzed,
        "signals_generated": signals_generated,
        "signal_conversion_rate": (
            signals_generated / signals_analyzed if signals_analyzed > 0 else 0
        ),
        "equity_curve": equity_series,
        "trades": system.trades,
        "performance_stats": system.performance_stats,
    }

    return results


def create_performance_report(results: Dict, output_dir: str):
    """Create comprehensive performance report with visualizations."""

    symbol = results["symbol"]

    # Create figure with subplots
    fig = plt.figure(figsize=(20, 16))

    # 1. Equity Curve
    ax1 = plt.subplot(3, 3, 1)
    results["equity_curve"].plot(ax=ax1, linewidth=2, color="blue")
    ax1.axhline(
        y=results["initial_capital"],
        color="red",
        linestyle="--",
        alpha=0.5,
        label="Initial Capital",
    )
    ax1.set_title("Equity Curve", fontsize=14, fontweight="bold")
    ax1.set_ylabel("Portfolio Value ($)")
    ax1.legend()
    ax1.grid(True, alpha=0.3)

    # 2. Drawdown
    ax2 = plt.subplot(3, 3, 2)
    equity = results["equity_curve"]
    drawdown = (equity - equity.expanding().max()) / equity.expanding().max() * 100
    drawdown.plot(ax=ax2, linewidth=2, color="red")
    ax2.fill_between(drawdown.index, drawdown.values, 0, color="red", alpha=0.3)
    ax2.set_title("Drawdown", fontsize=14, fontweight="bold")
    ax2.set_ylabel("Drawdown (%)")
    ax2.grid(True, alpha=0.3)

    # 3. Trade P&L Distribution
    ax3 = plt.subplot(3, 3, 3)
    if results["trades"]:
        pnls = [t["pnl"] for t in results["trades"]]
        ax3.hist(pnls, bins=30, color="green", alpha=0.7, edgecolor="black")
        ax3.axvline(x=0, color="red", linestyle="--", linewidth=2)
        ax3.set_title("Trade P&L Distribution", fontsize=14, fontweight="bold")
        ax3.set_xlabel("P&L ($)")
        ax3.set_ylabel("Frequency")

        # Add statistics
        avg_win = np.mean([p for p in pnls if p > 0]) if any(p > 0 for p in pnls) else 0
        avg_loss = (
            np.mean([p for p in pnls if p <= 0]) if any(p <= 0 for p in pnls) else 0
        )
        ax3.text(
            0.05,
            0.95,
            f"Avg Win: ${avg_win:.2f}\nAvg Loss: ${avg_loss:.2f}",
            transform=ax3.transAxes,
            verticalalignment="top",
            bbox=dict(boxstyle="round", facecolor="wheat", alpha=0.5),
        )

    # 4. Monthly Returns
    ax4 = plt.subplot(3, 3, 4)
    monthly_returns = (
        results["equity_curve"].resample("M").last().pct_change().dropna() * 100
    )
    monthly_returns.plot(kind="bar", ax=ax4, color="purple", alpha=0.7)
    ax4.axhline(y=0, color="black", linestyle="-", linewidth=0.5)
    ax4.set_title("Monthly Returns", fontsize=14, fontweight="bold")
    ax4.set_ylabel("Return (%)")
    ax4.set_xticklabels(
        [d.strftime("%Y-%m") for d in monthly_returns.index], rotation=45
    )
    ax4.grid(True, alpha=0.3)

    # 5. Signal Analysis
    ax5 = plt.subplot(3, 3, 5)
    stats = results["performance_stats"]
    signal_sources = {
        "ML": stats.get("ml_signals", 0),
        "Elliott Wave": stats.get("ew_signals", 0),
        "Technical": stats.get("ta_signals", 0),
        "Sentiment": stats.get("sentiment_signals", 0),
    }

    ax5.bar(
        signal_sources.keys(),
        signal_sources.values(),
        color="skyblue",
        edgecolor="black",
    )
    ax5.set_title("Signals by Source", fontsize=14, fontweight="bold")
    ax5.set_ylabel("Count")

    # 6. Trade Types
    ax6 = plt.subplot(3, 3, 6)
    trade_types = {
        "Single Source": stats.get("single_source_trades", 0),
        "Multi-Confluence": stats.get("multi_confluence", 0),
        "Time Exits": stats.get("time_exits", 0),
        "Stop Loss": len(
            [t for t in results["trades"] if t.get("exit_reason") == "Stop Loss"]
        ),
        "Target": len(
            [t for t in results["trades"] if t.get("exit_reason") == "Target"]
        ),
    }

    ax6.pie(
        [v for v in trade_types.values() if v > 0],
        labels=[k for k, v in trade_types.items() if v > 0],
        autopct="%1.1f%%",
        startangle=90,
    )
    ax6.set_title("Trade Types & Exit Reasons", fontsize=14, fontweight="bold")

    # 7. Rolling Sharpe Ratio
    ax7 = plt.subplot(3, 3, 7)
    window = 120  # ~20 days of 4H bars
    returns = results["equity_curve"].pct_change()
    rolling_sharpe = returns.rolling(window).apply(
        lambda x: (
            calculate_sharpe_ratio(x, periods_per_year=1460) if len(x) > 20 else np.nan
        )
    )
    rolling_sharpe.plot(ax=ax7, linewidth=2, color="green")
    ax7.axhline(y=0, color="black", linestyle="--", alpha=0.5)
    ax7.axhline(y=1, color="blue", linestyle="--", alpha=0.5, label="Sharpe = 1")
    ax7.set_title("Rolling Sharpe Ratio (20-day)", fontsize=14, fontweight="bold")
    ax7.set_ylabel("Sharpe Ratio")
    ax7.legend()
    ax7.grid(True, alpha=0.3)

    # 8. Cumulative Returns by Signal Source
    ax8 = plt.subplot(3, 3, 8)
    if results["trades"]:
        # Group trades by primary signal source
        source_returns = {}
        for trade in results["trades"]:
            source = trade.get("signal_source", "Unknown")
            if source not in source_returns:
                source_returns[source] = []
            source_returns[source].append(trade["pnl"])

        # Plot cumulative returns by source
        for source, pnls in source_returns.items():
            cumulative = np.cumsum(pnls)
            ax8.plot(cumulative, label=source, linewidth=2, marker="o", markersize=4)

        ax8.set_title("Cumulative P&L by Signal Source", fontsize=14, fontweight="bold")
        ax8.set_xlabel("Trade Number")
        ax8.set_ylabel("Cumulative P&L ($)")
        ax8.legend()
        ax8.grid(True, alpha=0.3)

    # 9. Performance Summary
    ax9 = plt.subplot(3, 3, 9)
    ax9.axis("tight")
    ax9.axis("off")

    summary_text = f"""
    PERFORMANCE SUMMARY - {symbol}

    Returns:
      Total Return: {results['total_return']:.2%}
      Sharpe Ratio: {results['sharpe_ratio']:.2f}
      Sortino Ratio: {results['sortino_ratio']:.2f}
      Max Drawdown: {results['max_drawdown']:.2%}
      Calmar Ratio: {results['calmar_ratio']:.2f}

    Trading Activity:
      Total Trades: {results['total_trades']}
      Win Rate: {results['win_rate']:.2%}
      Profit Factor: {results['profit_factor']:.2f}
      Expectancy: ${results['expectancy']:.2f}

    Signal Generation:
      Signals Analyzed: {results['signals_analyzed']}
      Signals Generated: {results['signals_generated']}
      Conversion Rate: {results['signal_conversion_rate']:.2%}

    Enhanced Features:
      Single Source Trades: {stats.get('single_source_trades', 0)}
      Adaptive Adjustments: {stats.get('adaptive_adjustments', 0)}
      Time-Based Exits: {stats.get('time_exits', 0)}
    """

    ax9.text(
        0.1,
        0.5,
        summary_text,
        transform=ax9.transAxes,
        fontsize=11,
        verticalalignment="center",
        fontfamily="monospace",
        bbox=dict(boxstyle="round", facecolor="lightgray", alpha=0.8),
    )

    plt.suptitle(
        f"Enhanced Production System V2 - Performance Report\n{symbol}",
        fontsize=16,
        fontweight="bold",
    )
    plt.tight_layout()

    # Save plot
    output_path = os.path.join(output_dir, f"{symbol}_v2_performance_report.png")
    plt.savefig(output_path, dpi=300, bbox_inches="tight")
    plt.close()

    print(f"\nSaved performance report to {output_path}")

    # Save detailed results
    results_copy = results.copy()
    results_copy["equity_curve"] = results_copy["equity_curve"].to_dict()
    results_file = os.path.join(output_dir, f"{symbol}_v2_results.json")

    with open(results_file, "w") as f:
        json.dump(results_copy, f, indent=2, default=str)

    print(f"Saved detailed results to {results_file}")


def main():
    """Run performance evaluation of Enhanced System V2."""

    print("\n" + "=" * 80)
    print("ENHANCED PRODUCTION SYSTEM V2 - PERFORMANCE EVALUATION")
    print("=" * 80)
    print(f"Generated: {datetime.now()}")

    # Test configuration
    symbols = ["EURUSD", "GBPUSD", "USDJPY"]
    test_days = 120  # 4 months of data

    # Create output directory
    output_dir = "output/v2_performance_evaluation"
    os.makedirs(output_dir, exist_ok=True)

    # Configure Enhanced System V2
    config = EnhancedProductionConfigV2(
        initial_capital=10000,
        min_confluences=1,  # Allow single source
        min_signal_confidence=0.6,  # Lower threshold
        single_source_position_reduction=0.5,  # Risk management
        max_bars_in_trade=120,  # Time-based exits
        use_adaptive_thresholds=True,
        use_news_filter=True,
        use_economic_data=True,
        max_trades_per_week=5,
    )

    print("\nSystem Configuration:")
    print(f"  Initial Capital: ${config.initial_capital:,.2f}")
    print(f"  Min Confluences: {config.min_confluences}")
    print(f"  Min Confidence: {config.min_signal_confidence}")
    print(f"  Single Source Reduction: {config.single_source_position_reduction:.0%}")
    print(f"  Max Bars in Trade: {config.max_bars_in_trade}")
    print(
        f"  Adaptive Thresholds: {'Enabled' if config.use_adaptive_thresholds else 'Disabled'}"
    )
    print(f"  News Filter: {'Enabled' if config.use_news_filter else 'Disabled'}")

    # Aggregate results
    all_results = {}
    total_return = 0
    total_trades = 0

    for symbol in symbols:
        print(f"\n{'='*60}")
        print(f"Evaluating {symbol}")
        print(f"{'='*60}")

        # Generate test data
        data = generate_test_data(symbol, days=test_days)
        print(f"Generated {len(data)} bars of test data")
        print(f"Date range: {data.index[0]} to {data.index[-1]}")

        # Run backtest
        try:
            results = run_backtest(data, symbol, config)
            all_results[symbol] = results

            # Print summary
            print(f"\n{symbol} Results:")
            print(f"  Total Return: {results['total_return']:.2%}")
            print(f"  Sharpe Ratio: {results['sharpe_ratio']:.2f}")
            print(f"  Max Drawdown: {results['max_drawdown']:.2%}")
            print(f"  Total Trades: {results['total_trades']}")
            print(f"  Win Rate: {results['win_rate']:.2%}")
            print(f"  Signal Conversion: {results['signal_conversion_rate']:.2%}")

            # Create performance report
            create_performance_report(results, output_dir)

            # Update aggregates
            total_return += results["total_return"]
            total_trades += results["total_trades"]

        except Exception as e:
            print(f"Error evaluating {symbol}: {e}")
            import traceback

            traceback.print_exc()

    # Overall summary
    if all_results:
        print("\n" + "=" * 80)
        print("OVERALL SUMMARY")
        print("=" * 80)

        avg_return = total_return / len(all_results)
        avg_sharpe = np.mean([r["sharpe_ratio"] for r in all_results.values()])
        avg_win_rate = np.mean([r["win_rate"] for r in all_results.values()])
        avg_conversion = np.mean(
            [r["signal_conversion_rate"] for r in all_results.values()]
        )

        print(f"Average Return: {avg_return:.2%}")
        print(f"Average Sharpe: {avg_sharpe:.2f}")
        print(f"Average Win Rate: {avg_win_rate:.2%}")
        print(f"Total Trades: {total_trades}")
        print(f"Average Signal Conversion: {avg_conversion:.2%}")

        # Key improvements summary
        print("\nKey System Features:")
        print("✓ Single-source trading enabled (with 50% position reduction)")
        print("✓ Adaptive thresholds based on market volatility")
        print("✓ Time-based position exits after 120 bars")
        print("✓ Alpha Vantage news sentiment integration")
        print("✓ Economic context awareness")
        print("✓ Enhanced risk management controls")

        # Save overall summary
        summary = {
            "evaluation_date": datetime.now().isoformat(),
            "symbols_tested": list(all_results.keys()),
            "test_period_days": test_days,
            "average_return": avg_return,
            "average_sharpe": avg_sharpe,
            "average_win_rate": avg_win_rate,
            "total_trades": total_trades,
            "average_signal_conversion": avg_conversion,
            "config": {
                "initial_capital": config.initial_capital,
                "min_confluences": config.min_confluences,
                "min_signal_confidence": config.min_signal_confidence,
                "single_source_position_reduction": config.single_source_position_reduction,
                "max_bars_in_trade": config.max_bars_in_trade,
            },
        }

        summary_file = os.path.join(output_dir, "overall_summary.json")
        with open(summary_file, "w") as f:
            json.dump(summary, f, indent=2)

        print(f"\nSaved overall summary to {summary_file}")

    print("\n" + "=" * 80)
    print("Evaluation complete!")
    print(f"All results saved to {output_dir}")
    print("=" * 80)


if __name__ == "__main__":
    main()
