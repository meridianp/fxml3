#!/usr/bin/env python
"""Comprehensive backtest for Enhanced Production System V2."""

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))

import json
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns

from fxml4.data_engineering.data_feeds.ib_data_feed import IBDataFeed
from fxml4.ml.model_loader import ModelLoader
from fxml4.utils.performance_metrics import (
    calculate_max_drawdown,
    calculate_sharpe_ratio,
)
from scripts.enhanced_production_system_v2 import (
    EnhancedProductionConfigV2,
    EnhancedProductionSystemV2,
)


def load_market_data(symbol: str, start_date: str, end_date: str) -> pd.DataFrame:
    """Load market data for backtesting."""
    print(f"\nLoading {symbol} data from {start_date} to {end_date}...")

    # Try to load from partitioned data
    data_path = Path(f"input/C_{symbol}")

    if data_path.exists():
        all_data = []

        # Parse dates
        start = pd.to_datetime(start_date)
        end = pd.to_datetime(end_date)

        # Iterate through year directories
        for year_dir in sorted(data_path.glob("year=*")):
            year = int(year_dir.name.split("=")[1])

            # Skip if year is outside our range
            if year < start.year or year > end.year:
                continue

            # Iterate through month directories
            for month_dir in sorted(year_dir.glob("month=*")):
                month = int(month_dir.name.split("=")[1])

                # Skip if month is outside our range for the year
                month_start = pd.Timestamp(year, month, 1)
                month_end = month_start + pd.offsets.MonthEnd(0)

                if month_end < start or month_start > end:
                    continue

                # Load parquet files
                for parquet_file in sorted(month_dir.glob("*.parquet")):
                    try:
                        df = pd.read_parquet(parquet_file)
                        all_data.append(df)
                    except Exception as e:
                        print(f"Error loading {parquet_file}: {e}")

        if all_data:
            data = pd.concat(all_data, ignore_index=True)
            data = data.sort_values("timestamp").reset_index(drop=True)
            data.set_index("timestamp", inplace=True)

            # Filter to exact date range
            data = data[start:end]

            print(f"Loaded {len(data)} bars of data")
            return data

    # Fallback: generate synthetic data for testing
    print("No partitioned data found, generating synthetic data...")
    dates = pd.date_range(start=start_date, end=end_date, freq="4h")

    # Generate realistic price movement
    base_price = 1.1000 if symbol == "EURUSD" else 1.2500
    returns = np.random.randn(len(dates)) * 0.001  # 0.1% volatility
    prices = base_price * np.exp(np.cumsum(returns))

    data = pd.DataFrame(
        {
            "open": prices * (1 + np.random.randn(len(dates)) * 0.0001),
            "high": prices * (1 + abs(np.random.randn(len(dates))) * 0.0002),
            "low": prices * (1 - abs(np.random.randn(len(dates))) * 0.0002),
            "close": prices,
            "volume": np.random.randint(1000, 5000, len(dates)),
        },
        index=dates,
    )

    # Add technical indicators
    data["sma_20"] = data["close"].rolling(20).mean()
    data["sma_50"] = data["close"].rolling(50).mean()
    data["rsi_14"] = 50 + np.random.randn(len(dates)) * 15
    data["atr_14"] = data["close"].rolling(14).std() * 2

    # Fill NaN values
    data.fillna(method="ffill", inplace=True)
    data.fillna(method="bfill", inplace=True)

    return data


def load_ml_model(symbol: str) -> Optional[object]:
    """Load trained ML model for the symbol."""
    model_path = Path(f"models/{symbol}/xgboost_model.pkl")

    if model_path.exists():
        try:
            loader = ModelLoader()
            model = loader.load_model(str(model_path))
            print(f"Loaded ML model for {symbol}")
            return model
        except Exception as e:
            print(f"Error loading model: {e}")

    print(f"No ML model found for {symbol}, system will use other signals")
    return None


def run_backtest(
    symbol: str,
    start_date: str,
    end_date: str,
    config: EnhancedProductionConfigV2,
    ml_model: Optional[object] = None,
) -> Dict:
    """Run backtest for a single symbol."""
    print(f"\n{'='*60}")
    print(f"Running backtest for {symbol}")
    print(f"{'='*60}")

    # Load data
    data = load_market_data(symbol, start_date, end_date)

    if data.empty:
        print("No data available for backtesting")
        return {}

    # Initialize system
    system = EnhancedProductionSystemV2(config, ml_model=ml_model)

    # Track metrics
    equity_curve = [config.initial_capital]
    timestamps = [data.index[0]]

    # Run through each bar
    print("\nProcessing bars...")
    signal_count = 0

    for i in range(100, len(data)):  # Start at 100 to have enough history
        current_time = data.index[i]
        current_bar = data.iloc[i]
        historical_data = data.iloc[: i + 1]

        # Update existing positions
        system.update_positions(symbol, current_bar, current_time)

        # Generate signal every 4 bars (16 hours) to avoid overtrading
        if i % 4 == 0 and len(system.positions) < config.max_positions:
            signal = system.generate_combined_signal(
                historical_data, symbol, current_time
            )

            if signal:
                signal_count += 1
                print(f"\n{current_time}: Signal generated!")
                print(f"  Action: {signal['action']}")
                print(f"  Confidence: {signal['confidence']:.2f}")
                print(f"  Sources: {signal['confluences']}")

                # Execute trade
                system.execute_trade(signal, current_bar, current_time, symbol)

        # Track equity
        equity_curve.append(system.capital)
        timestamps.append(current_time)

        # Progress update
        if i % 100 == 0:
            progress = (i / len(data)) * 100
            print(f"Progress: {progress:.1f}% - Equity: ${system.capital:.2f}")

    # Close all remaining positions
    print("\nClosing remaining positions...")
    for position_id in list(system.positions.keys()):
        system._close_position(
            position_id, data.iloc[-1]["close"], data.index[-1], "Backtest End"
        )

    # Calculate performance metrics
    equity_series = pd.Series(equity_curve, index=timestamps)
    returns = equity_series.pct_change().dropna()

    # Calculate metrics
    total_return = (system.capital - config.initial_capital) / config.initial_capital
    sharpe_ratio = calculate_sharpe_ratio(returns) if len(returns) > 0 else 0
    max_drawdown = (
        calculate_max_drawdown(equity_series) if len(equity_series) > 0 else 0
    )

    # Win rate
    winning_trades = [t for t in system.trades if t["pnl"] > 0]
    win_rate = len(winning_trades) / len(system.trades) if system.trades else 0

    # Average trade metrics
    if system.trades:
        avg_win = np.mean([t["pnl"] for t in winning_trades]) if winning_trades else 0
        avg_loss = (
            np.mean([t["pnl"] for t in system.trades if t["pnl"] <= 0])
            if len(system.trades) > len(winning_trades)
            else 0
        )
        profit_factor = abs(avg_win / avg_loss) if avg_loss != 0 else 0
    else:
        avg_win = avg_loss = profit_factor = 0

    # Create results dictionary
    results = {
        "symbol": symbol,
        "start_date": start_date,
        "end_date": end_date,
        "initial_capital": config.initial_capital,
        "final_capital": system.capital,
        "total_return": total_return,
        "sharpe_ratio": sharpe_ratio,
        "max_drawdown": max_drawdown,
        "total_trades": len(system.trades),
        "winning_trades": len(winning_trades),
        "win_rate": win_rate,
        "avg_win": avg_win,
        "avg_loss": avg_loss,
        "profit_factor": profit_factor,
        "equity_curve": equity_series.to_dict(),
        "trades": system.trades,
        "performance_stats": system.performance_stats,
        "signals_generated": signal_count,
    }

    # Print summary
    print(f"\n{'='*60}")
    print("BACKTEST SUMMARY")
    print(f"{'='*60}")
    print(f"Total Return: {total_return:.2%}")
    print(f"Sharpe Ratio: {sharpe_ratio:.2f}")
    print(f"Max Drawdown: {max_drawdown:.2%}")
    print(f"Total Trades: {len(system.trades)}")
    print(f"Win Rate: {win_rate:.2%}")
    print(f"Profit Factor: {profit_factor:.2f}")
    print(f"\nSignal Statistics:")
    print(f"  Total Signals Generated: {signal_count}")
    print(f"  ML Signals: {system.performance_stats['ml_signals']}")
    print(f"  Elliott Wave Signals: {system.performance_stats['ew_signals']}")
    print(f"  Technical Analysis Signals: {system.performance_stats['ta_signals']}")
    print(f"  Sentiment Signals: {system.performance_stats['sentiment_signals']}")
    print(f"  Single Source Trades: {system.performance_stats['single_source_trades']}")
    print(f"  Multi-Confluence Trades: {system.performance_stats['multi_confluence']}")
    print(f"  Time-Based Exits: {system.performance_stats['time_exits']}")
    print(f"  Adaptive Adjustments: {system.performance_stats['adaptive_adjustments']}")

    return results


def plot_results(results: Dict, output_dir: str = "output/backtest_v2"):
    """Plot backtest results."""
    os.makedirs(output_dir, exist_ok=True)

    # Convert equity curve to series
    equity_series = pd.Series(results["equity_curve"])
    equity_series.index = pd.to_datetime(equity_series.index)

    # Create figure with subplots
    fig, axes = plt.subplots(3, 2, figsize=(15, 12))
    fig.suptitle(
        f"Enhanced Production System V2 Backtest - {results['symbol']}", fontsize=16
    )

    # 1. Equity Curve
    ax = axes[0, 0]
    equity_series.plot(ax=ax, color="blue", linewidth=2)
    ax.set_title("Equity Curve")
    ax.set_ylabel("Portfolio Value ($)")
    ax.grid(True, alpha=0.3)

    # 2. Drawdown
    ax = axes[0, 1]
    drawdown = (
        equity_series - equity_series.expanding().max()
    ) / equity_series.expanding().max()
    drawdown.plot(ax=ax, color="red", linewidth=2)
    ax.fill_between(drawdown.index, drawdown.values, 0, color="red", alpha=0.3)
    ax.set_title("Drawdown")
    ax.set_ylabel("Drawdown (%)")
    ax.grid(True, alpha=0.3)

    # 3. Trade Distribution
    ax = axes[1, 0]
    if results["trades"]:
        pnls = [t["pnl"] for t in results["trades"]]
        ax.hist(pnls, bins=30, color="green", alpha=0.7, edgecolor="black")
        ax.axvline(x=0, color="red", linestyle="--", linewidth=2)
        ax.set_title("Trade P&L Distribution")
        ax.set_xlabel("P&L ($)")
        ax.set_ylabel("Frequency")

    # 4. Win Rate by Signal Source
    ax = axes[1, 1]
    if results["trades"]:
        # Count trades by source
        source_wins = {}
        source_total = {}
        for trade in results["trades"]:
            source = trade.get("signal_source", "Unknown")
            if source not in source_total:
                source_total[source] = 0
                source_wins[source] = 0
            source_total[source] += 1
            if trade["pnl"] > 0:
                source_wins[source] += 1

        # Calculate win rates
        sources = list(source_total.keys())
        win_rates = [
            source_wins[s] / source_total[s] * 100 if source_total[s] > 0 else 0
            for s in sources
        ]

        ax.bar(sources, win_rates, color="skyblue", edgecolor="black")
        ax.set_title("Win Rate by Signal Source")
        ax.set_ylabel("Win Rate (%)")
        ax.set_ylim(0, 100)
        for i, (s, wr) in enumerate(zip(sources, win_rates)):
            ax.text(i, wr + 2, f"{wr:.1f}%", ha="center")

    # 5. Monthly Returns
    ax = axes[2, 0]
    if len(equity_series) > 30:
        monthly_returns = equity_series.resample("M").last().pct_change().dropna()
        monthly_returns.plot(kind="bar", ax=ax, color="purple", alpha=0.7)
        ax.set_title("Monthly Returns")
        ax.set_ylabel("Return (%)")
        ax.set_xticklabels(
            [d.strftime("%Y-%m") for d in monthly_returns.index], rotation=45
        )

    # 6. Performance Metrics
    ax = axes[2, 1]
    ax.axis("off")
    metrics_text = f"""
    Performance Metrics:

    Total Return: {results['total_return']:.2%}
    Sharpe Ratio: {results['sharpe_ratio']:.2f}
    Max Drawdown: {results['max_drawdown']:.2%}

    Total Trades: {results['total_trades']}
    Win Rate: {results['win_rate']:.2%}
    Profit Factor: {results['profit_factor']:.2f}

    Avg Win: ${results['avg_win']:.2f}
    Avg Loss: ${abs(results['avg_loss']):.2f}

    Signals Generated: {results['signals_generated']}
    """
    ax.text(
        0.1,
        0.5,
        metrics_text,
        transform=ax.transAxes,
        fontsize=12,
        verticalalignment="center",
        fontfamily="monospace",
        bbox=dict(boxstyle="round", facecolor="wheat", alpha=0.5),
    )

    plt.tight_layout()

    # Save plot
    output_file = os.path.join(output_dir, f"{results['symbol']}_backtest_v2.png")
    plt.savefig(output_file, dpi=300, bbox_inches="tight")
    print(f"\nSaved plot to {output_file}")

    # Save detailed results
    results_file = os.path.join(output_dir, f"{results['symbol']}_results_v2.json")
    with open(results_file, "w") as f:
        # Convert non-serializable objects
        save_results = results.copy()
        save_results["equity_curve"] = list(results["equity_curve"].items())
        json.dump(save_results, f, indent=2, default=str)
    print(f"Saved results to {results_file}")


def main():
    """Run comprehensive backtest."""
    print("\n" + "=" * 80)
    print("ENHANCED PRODUCTION SYSTEM V2 - COMPREHENSIVE BACKTEST")
    print("=" * 80)
    print(f"Generated: {datetime.now()}")

    # Configuration
    symbols = ["EURUSD", "GBPUSD"]
    start_date = "2024-01-01"
    end_date = "2024-12-31"

    # Create configuration
    config = EnhancedProductionConfigV2()

    print("\nConfiguration:")
    print(f"  Initial Capital: ${config.initial_capital:,.2f}")
    print(f"  Min Confluences: {config.min_confluences}")
    print(f"  Min Confidence: {config.min_signal_confidence}")
    print(f"  Single Source Reduction: {config.single_source_position_reduction:.0%}")
    print(f"  Max Bars in Trade: {config.max_bars_in_trade}")
    print(
        f"  Adaptive Thresholds: {'Enabled' if config.use_adaptive_thresholds else 'Disabled'}"
    )

    # Run backtests
    all_results = {}

    for symbol in symbols:
        # Load ML model if available
        ml_model = load_ml_model(symbol)

        # Run backtest
        results = run_backtest(symbol, start_date, end_date, config, ml_model)

        if results:
            all_results[symbol] = results

            # Plot results
            plot_results(results)

    # Combined summary
    if all_results:
        print("\n" + "=" * 80)
        print("COMBINED SUMMARY")
        print("=" * 80)

        total_return = np.mean([r["total_return"] for r in all_results.values()])
        avg_sharpe = np.mean([r["sharpe_ratio"] for r in all_results.values()])
        avg_win_rate = np.mean([r["win_rate"] for r in all_results.values()])
        total_trades = sum([r["total_trades"] for r in all_results.values()])

        print(f"Average Return: {total_return:.2%}")
        print(f"Average Sharpe: {avg_sharpe:.2f}")
        print(f"Average Win Rate: {avg_win_rate:.2%}")
        print(f"Total Trades: {total_trades}")

        # Save combined results
        output_dir = "output/backtest_v2"
        combined_file = os.path.join(output_dir, "combined_results_v2.json")
        with open(combined_file, "w") as f:
            json.dump(
                {
                    "config": config.__dict__,
                    "summary": {
                        "avg_return": total_return,
                        "avg_sharpe": avg_sharpe,
                        "avg_win_rate": avg_win_rate,
                        "total_trades": total_trades,
                    },
                    "symbols": list(all_results.keys()),
                    "date_range": f"{start_date} to {end_date}",
                },
                f,
                indent=2,
                default=str,
            )

        print(f"\nSaved combined results to {combined_file}")

    print("\n" + "=" * 80)
    print("Backtest complete!")
    print("=" * 80)


if __name__ == "__main__":
    main()
