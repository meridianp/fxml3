#!/usr/bin/env python
"""Test EURUSD signal generation to understand the low trade count."""

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from scripts.create_optimized_4h_backtester import Optimized4HBacktester


def test_eurusd_signals():
    """Test signal generation for all symbols to compare."""

    # Initialize backtester
    symbols = ["EURUSD", "GBPUSD", "USDJPY", "USDCHF"]
    backtester = Optimized4HBacktester(symbols)

    # Test period - 1 month
    start_date = "2024-10-01"
    end_date = "2024-10-31"

    signal_stats = {}

    for symbol in symbols:
        # Load feature data
        features = backtester.load_4h_data(symbol)
        if features is None:
            continue

        # Filter to test period
        features = features[
            (features.index >= start_date) & (features.index <= end_date)
        ]

        # Generate signals for each bar
        signals = []
        qualities = []
        predictions = []

        for timestamp in features.index:
            bar = features.loc[timestamp]
            signal = backtester.generate_signal(symbol, bar)

            signals.append(signal["signal"])
            qualities.append(signal["quality"])
            predictions.append(signal.get("prediction", 0))

        # Calculate statistics
        signals_array = np.array(signals)
        qualities_array = np.array(qualities)
        predictions_array = np.array(predictions)

        # Count actual signals (non-zero)
        total_signals = (signals_array != 0).sum()
        buy_signals = (signals_array == 1).sum()
        sell_signals = (signals_array == -1).sum()

        # Count quality signals
        quality_signals = (
            (signals_array != 0)
            & (qualities_array >= backtester.signal_quality_threshold)
        ).sum()

        signal_stats[symbol] = {
            "total_bars": len(features),
            "total_signals": total_signals,
            "buy_signals": buy_signals,
            "sell_signals": sell_signals,
            "quality_signals": quality_signals,
            "signal_rate": total_signals / len(features),
            "quality_rate": quality_signals / len(features),
            "avg_quality": (
                qualities_array[signals_array != 0].mean() if total_signals > 0 else 0
            ),
            "avg_prediction": np.mean(np.abs(predictions_array)),
            "predictions": predictions_array,
        }

        print(f"\n{symbol} Signal Analysis:")
        print(f"  Total bars: {signal_stats[symbol]['total_bars']}")
        print(
            f"  Total signals: {total_signals} ({signal_stats[symbol]['signal_rate']:.1%})"
        )
        print(f"  Buy signals: {buy_signals}")
        print(f"  Sell signals: {sell_signals}")
        print(
            f"  Quality signals (>{backtester.signal_quality_threshold:.0%}): {quality_signals}"
        )
        print(f"  Average quality: {signal_stats[symbol]['avg_quality']:.3f}")
        print(f"  Average |prediction|: {signal_stats[symbol]['avg_prediction']:.6f}")

    # Create comparison chart
    fig, axes = plt.subplots(2, 2, figsize=(15, 10))

    # 1. Signal rates by symbol
    ax = axes[0, 0]
    signal_rates = [signal_stats[s]["signal_rate"] for s in symbols]
    quality_rates = [signal_stats[s]["quality_rate"] for s in symbols]

    x = np.arange(len(symbols))
    width = 0.35

    ax.bar(x - width / 2, signal_rates, width, label="All signals")
    ax.bar(x + width / 2, quality_rates, width, label="Quality signals")
    ax.set_xlabel("Symbol")
    ax.set_ylabel("Signal Rate")
    ax.set_title("Signal Generation Rate by Symbol")
    ax.set_xticks(x)
    ax.set_xticklabels(symbols)
    ax.legend()

    # 2. Buy/Sell distribution
    ax = axes[0, 1]
    buy_pcts = [
        signal_stats[s]["buy_signals"] / max(signal_stats[s]["total_signals"], 1)
        for s in symbols
    ]
    sell_pcts = [
        signal_stats[s]["sell_signals"] / max(signal_stats[s]["total_signals"], 1)
        for s in symbols
    ]

    ax.bar(x - width / 2, buy_pcts, width, label="Buy %")
    ax.bar(x + width / 2, sell_pcts, width, label="Sell %")
    ax.set_xlabel("Symbol")
    ax.set_ylabel("Percentage")
    ax.set_title("Buy/Sell Signal Distribution")
    ax.set_xticks(x)
    ax.set_xticklabels(symbols)
    ax.legend()
    ax.axhline(y=0.5, color="r", linestyle="--", alpha=0.5)

    # 3. Average prediction magnitude
    ax = axes[1, 0]
    avg_preds = [
        signal_stats[s]["avg_prediction"] * 10000 for s in symbols
    ]  # Convert to pips
    ax.bar(symbols, avg_preds)
    ax.set_ylabel("Average |Prediction| (pips)")
    ax.set_title("Average Prediction Magnitude")

    # 4. Prediction distribution for EURUSD
    ax = axes[1, 1]
    eurusd_preds = signal_stats["EURUSD"]["predictions"] * 10000  # Convert to pips
    ax.hist(eurusd_preds, bins=50, alpha=0.7, label="EURUSD")
    ax.axvline(x=0, color="r", linestyle="--", alpha=0.5)
    ax.axvline(x=0.5, color="g", linestyle="--", alpha=0.5, label="Signal threshold")
    ax.axvline(x=-0.5, color="g", linestyle="--", alpha=0.5)
    ax.set_xlabel("Prediction (pips)")
    ax.set_ylabel("Frequency")
    ax.set_title("EURUSD Prediction Distribution")
    ax.legend()

    plt.tight_layout()
    plt.savefig("output/eurusd_signal_analysis.png", dpi=150)
    print("\n✅ Saved analysis to output/eurusd_signal_analysis.png")


if __name__ == "__main__":
    test_eurusd_signals()
