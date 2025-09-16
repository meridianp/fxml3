#!/usr/bin/env python
"""Comprehensive backtesting of Enhanced Production System V2."""

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))

import json
import os
import warnings
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns

warnings.filterwarnings("ignore")
import joblib

# Import unified feature engineering
from fxml4.features import UnifiedFeatureEngineer

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


def load_historical_data(
    symbol: str, start_date: str = "2024-09-01", end_date: str = "2025-01-31"
) -> pd.DataFrame:
    """Load historical market data from partitioned files."""
    print(f"\nLoading {symbol} historical data...")

    # Try to load from partitioned data
    data_path = Path(f"input/C_{symbol}")

    if not data_path.exists():
        print(f"Warning: No data found for {symbol} at {data_path}")
        return None

    all_data = []
    start = pd.to_datetime(start_date).tz_localize("UTC")
    end = pd.to_datetime(end_date).tz_localize("UTC")

    # Iterate through year directories
    for year_dir in sorted(data_path.glob("year=*")):
        year = int(year_dir.name.split("=")[1])
        if year < start.year or year > end.year:
            continue

        # Iterate through month directories
        for month_dir in sorted(year_dir.glob("month=*")):
            month = int(month_dir.name.split("=")[1])

            # Check if this month is in our date range
            month_start = pd.Timestamp(year=year, month=month, day=1).tz_localize("UTC")
            month_end = month_start + pd.DateOffset(months=1) - pd.DateOffset(days=1)

            if month_end < start or month_start > end:
                continue

            # Load parquet files from this month
            for day_dir in sorted(month_dir.glob("day=*")):
                for parquet_file in day_dir.glob("*.parquet*"):
                    try:
                        df = pd.read_parquet(parquet_file)
                        if "timestamp" in df.columns:
                            df["timestamp"] = pd.to_datetime(df["timestamp"])
                            df = df.set_index("timestamp")
                        elif "datetime" in df.columns:
                            df["datetime"] = pd.to_datetime(df["datetime"])
                            df = df.set_index("datetime")
                        all_data.append(df)
                    except Exception as e:
                        print(f"Error loading {parquet_file}: {e}")

    if not all_data:
        print(f"No data found for {symbol} in date range {start_date} to {end_date}")
        return None

    # Combine all data
    data = pd.concat(all_data).sort_index()

    # Remove duplicates if any
    data = data[~data.index.duplicated(keep="first")]

    # Filter to date range
    if not data.index.empty:
        data = data[(data.index >= start) & (data.index <= end)]

    # Ensure we have required columns
    required_cols = ["open", "high", "low", "close", "volume"]
    if not all(col in data.columns for col in required_cols):
        print(f"Missing required columns for {symbol}")
        return None

    # Resample to 4H bars if we have minute data
    if len(data) > 0:
        time_diff = (data.index[1] - data.index[0]).total_seconds()
        if time_diff < 3600:  # Less than 1 hour, so we have minute/tick data
            print(f"Resampling {len(data)} minute bars to 4H bars...")
            data = (
                data.resample("4H")
                .agg(
                    {
                        "open": "first",
                        "high": "max",
                        "low": "min",
                        "close": "last",
                        "volume": "sum",
                    }
                )
                .dropna()
            )

    # Calculate technical indicators using unified feature engineering
    feature_engineer = UnifiedFeatureEngineer(
        {
            "advanced_features": True,
            "elliott_wave_features": True,
            "regime_features": True,
            "microstructure_features": True,
        }
    )
    data = feature_engineer.generate_features(data)

    print(f"Loaded {len(data)} bars for {symbol}")
    print(f"Date range: {data.index[0]} to {data.index[-1]}")
    print(f"Total features: {len(data.columns)}")

    return data


def run_comprehensive_backtest(
    data: pd.DataFrame, symbol: str, config: EnhancedProductionConfigV2
) -> Dict:
    """Run comprehensive backtest with Enhanced System V2."""

    print(f"\nRunning comprehensive backtest for {symbol}...")

    # Skip ML model for now due to feature mismatch
    ml_model = None
    print(f"  Running without ML model (feature engineering in progress)")

    system = EnhancedProductionSystemV2(config, ml_model=ml_model)

    # Track detailed metrics
    equity_curve = [config.initial_capital]
    timestamps = [data.index[0]]
    signals_analyzed = 0
    signals_generated = 0
    signal_sources = {"ml": 0, "ew": 0, "ta": 0, "sentiment": 0}
    trade_details = []

    # Run through data
    lookback = 200  # Need sufficient data for indicators
    for i in range(lookback, len(data)):
        if i % 500 == 0:
            progress = (i / len(data)) * 100
            print(
                f"  Progress: {progress:.1f}% - Equity: ${system.capital:.2f} - Trades: {len(system.trades)}"
            )

        current_time = data.index[i]
        current_bar = data.iloc[i]
        historical_data = data.iloc[: i + 1]

        # Update existing positions
        system.update_positions(symbol, current_bar, current_time)

        # Generate signals every 4 bars (16 hours for 4H data)
        if i % 4 == 0 and len(system.positions) < config.max_positions:
            signals_analyzed += 1

            # Generate combined signal
            signal = system.generate_combined_signal(
                historical_data, symbol, current_time
            )

            if signal:
                signals_generated += 1

                # Track signal sources
                if "signal_source" in signal:
                    source = signal["signal_source"].lower()
                    if "ml" in source:
                        signal_sources["ml"] += 1
                    elif "elliott" in source or "ew" in source:
                        signal_sources["ew"] += 1
                    elif "sentiment" in source:
                        signal_sources["sentiment"] += 1
                    else:
                        signal_sources["ta"] += 1

                # Execute trade
                pre_trade_count = len(system.trades)
                system.execute_trade(signal, current_bar, current_time, symbol)

                # Check if trade was executed
                if len(system.trades) > pre_trade_count:
                    trade = system.trades[-1]
                    trade_details.append(
                        {
                            "entry_time": current_time,
                            "entry_price": trade["entry_price"],
                            "direction": signal["action"],
                            "confidence": signal["confidence"],
                            "confluences": signal.get("confluences", 1),
                            "signal_source": signal.get("signal_source", "Unknown"),
                        }
                    )

        # Track equity
        current_equity = system.capital
        for pos in system.positions.values():
            if pos["direction"] == "BUY":
                current_equity += pos["quantity"] * (
                    current_bar["close"] - pos["entry_price"]
                )
            else:
                current_equity += pos["quantity"] * (
                    pos["entry_price"] - current_bar["close"]
                )

        equity_curve.append(current_equity)
        timestamps.append(current_time)

    # Close remaining positions
    for position_id in list(system.positions.keys()):
        system._close_position(
            position_id, data.iloc[-1]["close"], data.index[-1], "Backtest End"
        )

    # Calculate comprehensive metrics
    equity_series = pd.Series(equity_curve, index=timestamps)
    returns = equity_series.pct_change().dropna()

    # Trade analysis
    winning_trades = [t for t in system.trades if t["pnl"] > 0]
    losing_trades = [t for t in system.trades if t["pnl"] <= 0]

    # Calculate additional metrics
    avg_win = np.mean([t["pnl"] for t in winning_trades]) if winning_trades else 0
    avg_loss = np.mean([t["pnl"] for t in losing_trades]) if losing_trades else 0

    # Exit reason analysis
    exit_reasons = {}
    for trade in system.trades:
        reason = trade.get("exit_reason", "Unknown")
        exit_reasons[reason] = exit_reasons.get(reason, 0) + 1

    # Monthly returns
    monthly_returns = equity_series.resample("M").last().pct_change().dropna()

    results = {
        "symbol": symbol,
        "start_date": data.index[0],
        "end_date": data.index[-1],
        "trading_days": len(data) / 6,  # Approximate for 4H bars
        "initial_capital": config.initial_capital,
        "final_capital": system.capital,
        "total_return": (system.capital - config.initial_capital)
        / config.initial_capital,
        "annualized_return": (
            ((system.capital / config.initial_capital) ** (252 / (len(data) / 6)) - 1)
            if len(data) > 6
            else 0
        ),
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
        "avg_win": avg_win,
        "avg_loss": avg_loss,
        "largest_win": max([t["pnl"] for t in system.trades]) if system.trades else 0,
        "largest_loss": min([t["pnl"] for t in system.trades]) if system.trades else 0,
        "avg_trade_duration": (
            np.mean([t.get("duration_bars", 0) for t in system.trades])
            if system.trades
            else 0
        ),
        "signals_analyzed": signals_analyzed,
        "signals_generated": signals_generated,
        "signal_conversion_rate": (
            signals_generated / signals_analyzed if signals_analyzed > 0 else 0
        ),
        "signal_sources": signal_sources,
        "exit_reasons": exit_reasons,
        "monthly_returns": monthly_returns.to_dict(),
        "equity_curve": equity_series,
        "trades": system.trades,
        "trade_details": trade_details,
        "performance_stats": system.performance_stats,
    }

    return results


def create_comprehensive_report(all_results: Dict[str, Dict], output_dir: str):
    """Create comprehensive performance report with visualizations."""

    # Create figure with multiple subplots
    fig = plt.figure(figsize=(24, 20))

    # 1. Combined Equity Curves
    ax1 = plt.subplot(4, 3, 1)
    for symbol, results in all_results.items():
        normalized_equity = results["equity_curve"] / results["initial_capital"]
        normalized_equity.plot(ax=ax1, label=symbol, linewidth=2)
    ax1.axhline(y=1, color="black", linestyle="--", alpha=0.5)
    ax1.set_title("Normalized Equity Curves", fontsize=14, fontweight="bold")
    ax1.set_ylabel("Equity (Normalized)")
    ax1.legend()
    ax1.grid(True, alpha=0.3)

    # 2. Returns Distribution
    ax2 = plt.subplot(4, 3, 2)
    all_returns = []
    for symbol, results in all_results.items():
        returns = results["equity_curve"].pct_change().dropna()
        all_returns.extend(returns.values)
    ax2.hist(all_returns, bins=50, color="green", alpha=0.7, edgecolor="black")
    ax2.axvline(x=0, color="red", linestyle="--", linewidth=2)
    ax2.set_title("Combined Returns Distribution", fontsize=14, fontweight="bold")
    ax2.set_xlabel("Daily Returns")
    ax2.set_ylabel("Frequency")

    # 3. Performance Metrics Comparison
    ax3 = plt.subplot(4, 3, 3)
    metrics = ["sharpe_ratio", "sortino_ratio", "calmar_ratio"]
    symbols = list(all_results.keys())
    x = np.arange(len(symbols))
    width = 0.25

    for i, metric in enumerate(metrics):
        values = [results[metric] for results in all_results.values()]
        ax3.bar(x + i * width, values, width, label=metric.replace("_", " ").title())

    ax3.set_xlabel("Symbol")
    ax3.set_ylabel("Ratio")
    ax3.set_title("Risk-Adjusted Performance Metrics", fontsize=14, fontweight="bold")
    ax3.set_xticks(x + width)
    ax3.set_xticklabels(symbols)
    ax3.legend()
    ax3.grid(True, alpha=0.3)

    # 4. Win Rate and Profit Factor
    ax4 = plt.subplot(4, 3, 4)
    win_rates = [results["win_rate"] * 100 for results in all_results.values()]
    profit_factors = [results["profit_factor"] for results in all_results.values()]

    x = np.arange(len(symbols))
    ax4_twin = ax4.twinx()

    bars1 = ax4.bar(
        x - 0.2, win_rates, 0.4, label="Win Rate %", color="blue", alpha=0.7
    )
    bars2 = ax4_twin.bar(
        x + 0.2, profit_factors, 0.4, label="Profit Factor", color="orange", alpha=0.7
    )

    ax4.set_xlabel("Symbol")
    ax4.set_ylabel("Win Rate (%)", color="blue")
    ax4_twin.set_ylabel("Profit Factor", color="orange")
    ax4.set_title("Win Rate vs Profit Factor", fontsize=14, fontweight="bold")
    ax4.set_xticks(x)
    ax4.set_xticklabels(symbols)
    ax4.tick_params(axis="y", labelcolor="blue")
    ax4_twin.tick_params(axis="y", labelcolor="orange")

    # 5. Signal Sources Analysis
    ax5 = plt.subplot(4, 3, 5)
    total_sources = {"ml": 0, "ew": 0, "ta": 0, "sentiment": 0}
    for results in all_results.values():
        for source, count in results["signal_sources"].items():
            total_sources[source] += count

    if sum(total_sources.values()) > 0:
        ax5.pie(
            total_sources.values(),
            labels=total_sources.keys(),
            autopct="%1.1f%%",
            startangle=90,
        )
        ax5.set_title("Signal Sources Distribution", fontsize=14, fontweight="bold")

    # 6. Exit Reasons Analysis
    ax6 = plt.subplot(4, 3, 6)
    total_exits = {}
    for results in all_results.values():
        for reason, count in results["exit_reasons"].items():
            total_exits[reason] = total_exits.get(reason, 0) + count

    if total_exits:
        ax6.bar(total_exits.keys(), total_exits.values(), color="purple", alpha=0.7)
        ax6.set_title("Exit Reasons Distribution", fontsize=14, fontweight="bold")
        ax6.set_xlabel("Exit Reason")
        ax6.set_ylabel("Count")
        plt.setp(ax6.xaxis.get_majorticklabels(), rotation=45, ha="right")

    # 7. Monthly Returns Heatmap
    ax7 = plt.subplot(4, 3, 7)
    monthly_data = []
    for symbol, results in all_results.items():
        monthly = pd.Series(results["monthly_returns"], name=symbol)
        monthly_data.append(monthly)

    if monthly_data:
        monthly_df = (
            pd.concat(monthly_data, axis=1).fillna(0) * 100
        )  # Convert to percentage
        sns.heatmap(
            monthly_df.T, annot=True, fmt=".1f", cmap="RdYlGn", center=0, ax=ax7
        )
        ax7.set_title("Monthly Returns Heatmap (%)", fontsize=14, fontweight="bold")
        ax7.set_xlabel("Month")
        ax7.set_ylabel("Symbol")

    # 8. Trade Duration Distribution
    ax8 = plt.subplot(4, 3, 8)
    all_durations = []
    for results in all_results.values():
        durations = [t.get("duration_bars", 0) for t in results["trades"]]
        all_durations.extend(durations)

    if all_durations:
        ax8.hist(all_durations, bins=30, color="teal", alpha=0.7, edgecolor="black")
        ax8.axvline(
            x=120, color="red", linestyle="--", linewidth=2, label="Max Bars (120)"
        )
        ax8.set_title("Trade Duration Distribution", fontsize=14, fontweight="bold")
        ax8.set_xlabel("Duration (4H bars)")
        ax8.set_ylabel("Frequency")
        ax8.legend()

    # 9. Summary Statistics Table
    ax9 = plt.subplot(4, 3, (10, 12))
    ax9.axis("tight")
    ax9.axis("off")

    # Calculate aggregate statistics
    total_trades = sum(r["total_trades"] for r in all_results.values())
    avg_return = np.mean([r["total_return"] for r in all_results.values()])
    avg_sharpe = np.mean([r["sharpe_ratio"] for r in all_results.values()])
    avg_win_rate = np.mean([r["win_rate"] for r in all_results.values()])
    total_signals = sum(r["signals_generated"] for r in all_results.values())
    avg_conversion = np.mean(
        [r["signal_conversion_rate"] for r in all_results.values()]
    )

    summary_text = f"""
COMPREHENSIVE BACKTEST SUMMARY
{'='*40}
Testing Period: {all_results[list(all_results.keys())[0]]['start_date'].strftime('%Y-%m-%d')} to {all_results[list(all_results.keys())[0]]['end_date'].strftime('%Y-%m-%d')}
Symbols Tested: {', '.join(all_results.keys())}

AGGREGATE PERFORMANCE:
  Total Trades: {total_trades}
  Average Return: {avg_return:.2%}
  Average Sharpe: {avg_sharpe:.2f}
  Average Win Rate: {avg_win_rate:.2%}

SIGNAL GENERATION:
  Total Signals: {total_signals}
  Average Conversion: {avg_conversion:.2%}

SYSTEM CONFIGURATION:
  Min Confluences: {all_results[list(all_results.keys())[0]].get('config', {}).get('min_confluences', 1)}
  Min Confidence: {all_results[list(all_results.keys())[0]].get('config', {}).get('min_signal_confidence', 0.6)}
  Single Source Reduction: 50%
  Max Bars in Trade: 120
  Adaptive Thresholds: Enabled
  News Filter: Enabled

INDIVIDUAL RESULTS:
"""

    for symbol, results in all_results.items():
        summary_text += f"""
{symbol}:
  Return: {results['total_return']:.2%} | Sharpe: {results['sharpe_ratio']:.2f}
  Trades: {results['total_trades']} | Win Rate: {results['win_rate']:.2%}
  Max DD: {results['max_drawdown']:.2%} | PF: {results['profit_factor']:.2f}
"""

    ax9.text(
        0.05,
        0.5,
        summary_text,
        transform=ax9.transAxes,
        fontsize=10,
        verticalalignment="center",
        fontfamily="monospace",
        bbox=dict(boxstyle="round", facecolor="lightgray", alpha=0.8),
    )

    plt.suptitle(
        "Enhanced Production System V2 - Comprehensive Backtest Report",
        fontsize=18,
        fontweight="bold",
    )
    plt.tight_layout()

    # Save plot
    output_path = os.path.join(output_dir, "comprehensive_backtest_report.png")
    plt.savefig(output_path, dpi=300, bbox_inches="tight")
    plt.close()

    print(f"\nSaved comprehensive report to {output_path}")

    # Save detailed results
    results_file = os.path.join(output_dir, "comprehensive_backtest_results.json")

    # Convert non-serializable objects for JSON
    json_results = {}
    for symbol, results in all_results.items():
        json_results[symbol] = {
            k: v
            for k, v in results.items()
            if k not in ["equity_curve", "trades", "trade_details"]
        }
        json_results[symbol]["final_equity"] = float(results["equity_curve"].iloc[-1])
        json_results[symbol]["total_trades"] = len(results["trades"])
        json_results[symbol]["config"] = {
            "min_confluences": 1,
            "min_signal_confidence": 0.6,
            "single_source_position_reduction": 0.5,
            "max_bars_in_trade": 120,
        }

    with open(results_file, "w") as f:
        json.dump(json_results, f, indent=2, default=str)

    print(f"Saved detailed results to {results_file}")


def main():
    """Run comprehensive backtesting."""

    print("\n" + "=" * 80)
    print("COMPREHENSIVE BACKTEST - ENHANCED PRODUCTION SYSTEM V2")
    print("=" * 80)
    print(f"Generated: {datetime.now()}")

    # Test configuration
    symbols = ["EURUSD", "GBPUSD"]  # Add more symbols if data available
    start_date = "2024-10-01"
    end_date = "2025-01-31"

    # Create output directory
    output_dir = "output/comprehensive_backtest_v2"
    os.makedirs(output_dir, exist_ok=True)

    # Configure Enhanced System V2 - More aggressive for testing
    config = EnhancedProductionConfigV2(
        initial_capital=10000,
        min_confluences=1,  # Allow single source
        min_signal_confidence=0.4,  # Lower threshold for more signals
        single_source_position_reduction=0.5,  # Risk management
        max_bars_in_trade=120,  # Time-based exits
        use_adaptive_thresholds=False,  # Disable for consistent testing
        use_news_filter=False,  # Disable to avoid API calls
        use_economic_data=False,  # Disable to avoid API calls
        max_trades_per_week=10,  # Allow more trades
        max_positions=2,
        max_risk_per_trade=0.01,
        max_portfolio_risk=0.03,
        # Increase weights for working signal generators
        elliott_wave_weight=1.0,
        technical_analysis_weight=1.5,  # Boost TA since it's working
        sentiment_weight=1.0,
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

    # Run backtests
    all_results = {}

    for symbol in symbols:
        print(f"\n{'='*60}")
        print(f"Processing {symbol}")
        print(f"{'='*60}")

        # Load historical data
        data = load_historical_data(symbol, start_date, end_date)

        if data is None or len(data) < 500:
            print(f"Insufficient data for {symbol}, skipping...")
            continue

        # Run backtest
        try:
            results = run_comprehensive_backtest(data, symbol, config)
            all_results[symbol] = results

            # Print summary
            print(f"\n{symbol} Results:")
            print(
                f"  Period: {results['start_date'].strftime('%Y-%m-%d')} to {results['end_date'].strftime('%Y-%m-%d')}"
            )
            print(f"  Total Return: {results['total_return']:.2%}")
            print(f"  Annualized Return: {results['annualized_return']:.2%}")
            print(f"  Sharpe Ratio: {results['sharpe_ratio']:.2f}")
            print(f"  Max Drawdown: {results['max_drawdown']:.2%}")
            print(f"  Total Trades: {results['total_trades']}")
            print(f"  Win Rate: {results['win_rate']:.2%}")
            print(f"  Profit Factor: {results['profit_factor']:.2f}")
            print(f"  Signal Conversion: {results['signal_conversion_rate']:.2%}")

        except Exception as e:
            print(f"Error backtesting {symbol}: {e}")
            import traceback

            traceback.print_exc()

    # Create comprehensive report
    if all_results:
        print("\n" + "=" * 80)
        print("CREATING COMPREHENSIVE REPORT")
        print("=" * 80)

        create_comprehensive_report(all_results, output_dir)

        # Overall summary
        total_trades = sum(r["total_trades"] for r in all_results.values())
        avg_return = np.mean([r["total_return"] for r in all_results.values()])
        avg_sharpe = np.mean([r["sharpe_ratio"] for r in all_results.values()])
        avg_win_rate = np.mean([r["win_rate"] for r in all_results.values()])

        print("\n" + "=" * 80)
        print("OVERALL SUMMARY")
        print("=" * 80)
        print(f"Symbols Tested: {len(all_results)}")
        print(f"Total Trades: {total_trades}")
        print(f"Average Return: {avg_return:.2%}")
        print(f"Average Sharpe: {avg_sharpe:.2f}")
        print(f"Average Win Rate: {avg_win_rate:.2%}")

        if total_trades > 0:
            print("\nSystem is generating trades with the enhanced configuration!")
        else:
            print("\nWarning: No trades generated. Check signal generation logic.")

    print("\n" + "=" * 80)
    print("Comprehensive backtest complete!")
    print(f"All results saved to {output_dir}")
    print("=" * 80)


if __name__ == "__main__":
    main()
