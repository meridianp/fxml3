#!/usr/bin/env python
"""Debug 4H timestamp alignment issues."""

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))

import pandas as pd

from scripts.create_optimized_4h_backtester import Optimized4HBacktester


def debug_timestamps():
    """Check timestamp alignment between features and prices."""

    backtester = Optimized4HBacktester(["EURUSD"])

    # Load feature data
    features = backtester.load_4h_data("EURUSD")
    if features is not None:
        print("Feature data timestamps:")
        print(f"  Start: {features.index[0]}")
        print(f"  End: {features.index[-1]}")
        print(f"  Count: {len(features)}")
        print(f"  Sample: {features.index[:5].tolist()}")
        print(f"  Timezone: {features.index.tz}")
    else:
        print("No feature data found")

    # Load price data
    prices = backtester.load_4h_price_data("EURUSD", "2024-01-01", "2024-01-31")
    if prices is not None:
        print("\nPrice data timestamps:")
        print(f"  Start: {prices.index[0]}")
        print(f"  End: {prices.index[-1]}")
        print(f"  Count: {len(prices)}")
        print(f"  Sample: {prices.index[:5].tolist()}")
        print(f"  Timezone: {prices.index.tz}")

        # Check overlap
        if features is not None:
            overlap = features.index.intersection(prices.index)
            print(f"\nOverlapping timestamps: {len(overlap)}")
            if len(overlap) > 0:
                print(f"  Sample overlap: {overlap[:5].tolist()}")
    else:
        print("No price data found")


if __name__ == "__main__":
    debug_timestamps()
