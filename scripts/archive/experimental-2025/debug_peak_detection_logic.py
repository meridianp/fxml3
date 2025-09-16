#!/usr/bin/env python
"""Debug peak/trough detection logic in detail."""

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))

import numpy as np
import pandas as pd


def debug_peak_detection():
    """Debug the peak detection algorithm step by step."""

    # Load data
    file_path = Path("input/C_EURUSD/year=2024/month=10/day=15/data.parquet.gz")
    df = pd.read_parquet(file_path)

    if "timestamp" in df.columns:
        df["timestamp"] = pd.to_datetime(df["timestamp"])
        df = df.set_index("timestamp")

    # Resample to 4H
    data_4h = (
        df.resample("4h")
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

    print(f"Data shape: {data_4h.shape}")
    print(f"\nFirst few rows:")
    print(data_4h.head())

    # Get the high values
    high_values = data_4h["high"].values
    low_values = data_4h["low"].values

    print(f"\nHigh values: {high_values}")
    print(f"Low values: {low_values}")

    # Test peak detection with window size 1
    window = 1
    print(f"\n\nTesting peak detection with window={window}")
    print("=" * 60)

    for i in range(window, len(high_values) - window):
        print(f"\nChecking index {i} (value={high_values[i]:.5f}):")

        # Check if it's a peak
        is_peak = True

        # Check left side
        for j in range(1, window + 1):
            left_val = high_values[i - j]
            print(
                f"  Compare with left[{i-j}]: {high_values[i]:.5f} > {left_val:.5f} = {high_values[i] > left_val}"
            )
            if high_values[i] <= left_val:
                is_peak = False
                break

        # Check right side
        if is_peak:
            for j in range(1, window + 1):
                right_val = high_values[i + j]
                print(
                    f"  Compare with right[{i+j}]: {high_values[i]:.5f} > {right_val:.5f} = {high_values[i] > right_val}"
                )
                if high_values[i] <= right_val:
                    is_peak = False
                    break

        if is_peak:
            print(f"  ✓ PEAK FOUND at index {i}")
        else:
            print(f"  ✗ Not a peak")

    # Also check with less strict conditions
    print("\n\n" + "=" * 60)
    print("Testing with LESS STRICT conditions (>= instead of >)")
    print("=" * 60)

    peaks_found = []
    troughs_found = []

    for i in range(1, len(high_values) - 1):
        # Less strict peak detection
        if (
            high_values[i] >= high_values[i - 1]
            and high_values[i] >= high_values[i + 1]
        ):
            if (
                high_values[i] > high_values[i - 1]
                or high_values[i] > high_values[i + 1]
            ):
                peaks_found.append(i)

        # Less strict trough detection
        if low_values[i] <= low_values[i - 1] and low_values[i] <= low_values[i + 1]:
            if low_values[i] < low_values[i - 1] or low_values[i] < low_values[i + 1]:
                troughs_found.append(i)

    print(f"\nWith less strict conditions:")
    print(f"Peaks found: {len(peaks_found)} at indices {peaks_found}")
    print(f"Troughs found: {len(troughs_found)} at indices {troughs_found}")

    # Check if all values are the same
    print("\n\nChecking for flat data:")
    print(f"Unique high values: {len(np.unique(high_values))}")
    print(f"Unique low values: {len(np.unique(low_values))}")
    print(f"Standard deviation of highs: {np.std(high_values):.6f}")
    print(f"Standard deviation of lows: {np.std(low_values):.6f}")

    # Show price movements
    print("\n\nPrice movements between consecutive bars:")
    for i in range(1, min(10, len(high_values))):
        high_diff = high_values[i] - high_values[i - 1]
        low_diff = low_values[i] - low_values[i - 1]
        print(f"Bar {i}: High diff={high_diff:.5f}, Low diff={low_diff:.5f}")


if __name__ == "__main__":
    debug_peak_detection()
