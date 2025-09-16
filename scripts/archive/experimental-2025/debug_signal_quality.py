#!/usr/bin/env python
"""Debug signal quality to understand why no trades are being taken."""

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))

import pandas as pd

from scripts.create_optimized_4h_backtester import Optimized4HBacktester


def debug_signals():
    """Debug signal generation and quality."""

    backtester = Optimized4HBacktester(["EURUSD"])

    # Load data
    features = backtester.load_4h_data("EURUSD")
    prices = backtester.load_4h_price_data("EURUSD", "2024-01-01", "2024-01-31")

    # Filter to date range
    features = features[
        (features.index >= "2024-01-01") & (features.index <= "2024-01-31")
    ]

    # Align indices
    common_index = features.index.intersection(prices.index)
    features = features.loc[common_index]
    prices = prices.loc[common_index]

    print(f"Analyzing {len(features)} 4H bars...")

    # Generate signals for each bar
    signals_generated = 0
    high_quality_signals = 0
    signal_qualities = []

    for timestamp in features.index[:20]:  # Check first 20 bars
        current_bar = features.loc[timestamp]
        signal = backtester.generate_signal("EURUSD", current_bar)

        if signal["signal"] != 0:
            signals_generated += 1
            signal_qualities.append(signal["quality"])

            if signal["quality"] >= backtester.signal_quality_threshold:
                high_quality_signals += 1

            print(f"\nSignal at {timestamp}:")
            print(f"  Direction: {signal['signal']}")
            print(f"  Quality: {signal['quality']:.2f}")
            print(f"  Confidence: {signal['confidence']:.1f}")
            print(f"  Prediction: {signal['prediction']:.6f}")
            print(
                f"  Meets threshold: {signal['quality'] >= backtester.signal_quality_threshold}"
            )

    print(f"\n\nSummary:")
    print(f"  Total signals: {signals_generated}")
    print(f"  High quality signals: {high_quality_signals}")
    print(f"  Quality threshold: {backtester.signal_quality_threshold:.1%}")

    if signal_qualities:
        print(f"  Avg quality: {sum(signal_qualities)/len(signal_qualities):.2f}")
        print(f"  Min quality: {min(signal_qualities):.2f}")
        print(f"  Max quality: {max(signal_qualities):.2f}")


if __name__ == "__main__":
    debug_signals()
