#!/usr/bin/env python
"""Debug data quality issues."""

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))

import numpy as np
import pandas as pd


def check_data_quality():
    """Check the quality of the minute data."""

    # Load minute data
    file_path = Path("input/C_EURUSD/year=2024/month=10/day=15/data.parquet.gz")
    df = pd.read_parquet(file_path)

    print("Minute data analysis:")
    print(f"Shape: {df.shape}")
    print(f"\nColumns: {df.columns.tolist()}")
    print(f"\nFirst 10 rows:")
    print(df.head(10))

    print(f"\nLast 10 rows:")
    print(df.tail(10))

    # Check for unique values
    print(f"\n\nUnique values analysis:")
    print(f"Unique open values: {df['open'].nunique()}")
    print(f"Unique high values: {df['high'].nunique()}")
    print(f"Unique low values: {df['low'].nunique()}")
    print(f"Unique close values: {df['close'].nunique()}")

    # Check price range
    print(f"\n\nPrice range:")
    print(f"Open: {df['open'].min():.5f} to {df['open'].max():.5f}")
    print(f"High: {df['high'].min():.5f} to {df['high'].max():.5f}")
    print(f"Low: {df['low'].min():.5f} to {df['low'].max():.5f}")
    print(f"Close: {df['close'].min():.5f} to {df['close'].max():.5f}")

    # Check standard deviations
    print(f"\n\nStandard deviations:")
    print(f"Open: {df['open'].std():.6f}")
    print(f"High: {df['high'].std():.6f}")
    print(f"Low: {df['low'].std():.6f}")
    print(f"Close: {df['close'].std():.6f}")

    # Check volume
    print(f"\n\nVolume analysis:")
    print(f"Total volume: {df['volume'].sum()}")
    print(f"Non-zero volume bars: {(df['volume'] > 0).sum()}")

    # Load a different day for comparison
    print("\n\n" + "=" * 60)
    print("Comparing with October 21 data:")
    print("=" * 60)

    file_path2 = Path("input/C_EURUSD/year=2024/month=10/day=21/data.parquet.gz")
    if file_path2.exists():
        df2 = pd.read_parquet(file_path2)

        print(f"\nShape: {df2.shape}")
        print(f"\nUnique values:")
        print(f"High: {df2['high'].nunique()}")
        print(f"Low: {df2['low'].nunique()}")

        print(f"\nPrice range:")
        print(f"High: {df2['high'].min():.5f} to {df2['high'].max():.5f}")
        print(f"Low: {df2['low'].min():.5f} to {df2['low'].max():.5f}")

        print(f"\nStandard deviations:")
        print(f"High: {df2['high'].std():.6f}")
        print(f"Low: {df2['low'].std():.6f}")

    # Test with multiple days combined
    print("\n\n" + "=" * 60)
    print("Testing with multiple days combined:")
    print("=" * 60)

    all_data = []
    base_path = Path("input/C_EURUSD/year=2024/month=10")

    for day in range(15, 25):
        file_path = base_path / f"day={day}/data.parquet.gz"
        if file_path.exists():
            try:
                day_df = pd.read_parquet(file_path)
                if "timestamp" in day_df.columns:
                    day_df["timestamp"] = pd.to_datetime(day_df["timestamp"])
                    day_df = day_df.set_index("timestamp")
                all_data.append(day_df)
            except:
                pass

    if all_data:
        combined_df = pd.concat(all_data).sort_index()
        combined_df = combined_df[~combined_df.index.duplicated(keep="first")]

        # Resample to 4H
        data_4h = (
            combined_df.resample("4h")
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

        print(f"\nCombined minute data: {len(combined_df)} bars")
        print(f"4H resampled data: {len(data_4h)} bars")

        print(f"\n4H data statistics:")
        print(f"High std dev: {data_4h['high'].std():.6f}")
        print(f"Low std dev: {data_4h['low'].std():.6f}")

        # Show actual price movements in 4H data
        print(f"\n4H price movements (first 10):")
        for i in range(1, min(10, len(data_4h))):
            high_change = data_4h["high"].iloc[i] - data_4h["high"].iloc[i - 1]
            low_change = data_4h["low"].iloc[i] - data_4h["low"].iloc[i - 1]
            print(
                f"Bar {i}: High change={high_change:.5f}, Low change={low_change:.5f}"
            )


if __name__ == "__main__":
    check_data_quality()
