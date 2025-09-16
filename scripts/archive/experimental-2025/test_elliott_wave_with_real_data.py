#!/usr/bin/env python
"""Test Elliott Wave detection with real Polygon data."""

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))

from datetime import datetime, timedelta

import numpy as np
import pandas as pd

from fxml4.data.data_loader import DataLoader
from fxml4.wave_analysis.elliott_wave import ElliottWaveAnalyzer


def test_elliott_wave_on_real_data():
    """Test Elliott Wave detection on real market data."""
    print("Testing Elliott Wave detection with real Polygon data...\n")

    # Initialize components
    analyzer = ElliottWaveAnalyzer()
    data_loader = DataLoader()

    # Test with EURUSD
    symbol = "EURUSD"
    print(f"Loading {symbol} data...")

    # Load 30 days of recent data
    end_date = datetime.now() - timedelta(days=10)
    start_date = end_date - timedelta(days=30)

    # Load 4H data
    df = data_loader.load_data(
        symbol=symbol,
        timeframe="4h",
        start_date=start_date.strftime("%Y-%m-%d"),
        end_date=end_date.strftime("%Y-%m-%d"),
    )

    if df is None or df.empty:
        print(f"❌ No data loaded for {symbol}")
        return

    print(f"✅ Loaded {len(df)} 4H bars")
    print(f"   Date range: {df.index[0]} to {df.index[-1]}")
    print(f"   Price range: {df['low'].min():.5f} to {df['high'].max():.5f}")
    print(
        f"   Price movement: {(df['close'].iloc[-1] / df['close'].iloc[0] - 1) * 100:.2f}%"
    )

    # Detect Elliott Waves
    print(f"\nDetecting Elliott Wave patterns...")
    patterns = analyzer.identify_elliott_wave(df)

    if patterns:
        print(f"✅ Found {len(patterns)} Elliott Wave patterns!")

        for i, pattern in enumerate(patterns[:3]):  # Show first 3
            print(f"\nPattern {i+1}:")
            print(f"   Type: {pattern.get('pattern_type', 'Unknown')}")
            print(f"   Confidence: {pattern.get('confidence', 0):.2%}")
            print(f"   Start: {pattern.get('start_idx', 'N/A')}")
            print(f"   End: {pattern.get('end_idx', 'N/A')}")

            if "waves" in pattern:
                print(f"   Waves detected: {len(pattern['waves'])}")
    else:
        print("❌ No Elliott Wave patterns detected")

        # Debug: Check if there's enough price movement
        price_change = abs(df["close"].pct_change().mean())
        volatility = df["close"].pct_change().std()

        print(f"\nDebug info:")
        print(f"   Average price change: {price_change:.4%}")
        print(f"   Price volatility: {volatility:.4%}")
        print(f"   Unique high values: {df['high'].nunique()}")

        # Try with more data
        print("\nTrying with 60 days of data...")
        start_date = end_date - timedelta(days=60)
        df_longer = data_loader.load_data(
            symbol=symbol,
            timeframe="4h",
            start_date=start_date.strftime("%Y-%m-%d"),
            end_date=end_date.strftime("%Y-%m-%d"),
        )

        if df_longer is not None and len(df_longer) > len(df):
            patterns_longer = analyzer.identify_elliott_wave(df_longer)
            if patterns_longer:
                print(f"✅ Found {len(patterns_longer)} patterns with more data!")
            else:
                print("❌ Still no patterns found with more data")


if __name__ == "__main__":
    test_elliott_wave_on_real_data()
