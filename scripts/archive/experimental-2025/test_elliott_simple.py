#!/usr/bin/env python
"""Simple test of Elliott Wave detection with real data."""

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))

from datetime import datetime, timedelta

import numpy as np
import pandas as pd

from fxml4.wave_analysis.elliott_wave import ElliottWaveAnalyzer


def load_4h_data(symbol: str, days: int = 30):
    """Load and resample minute data to 4H."""
    base_path = Path(f"input/C_{symbol}")

    # Get recent dates
    end_date = datetime.now() - timedelta(days=10)
    start_date = end_date - timedelta(days=days)

    all_data = []

    # Load daily files
    current = start_date
    while current <= end_date:
        file_path = (
            base_path
            / f"year={current.year}"
            / f"month={current.month}"
            / f"day={current.day}"
            / "data.parquet.gz"
        )

        if file_path.exists():
            try:
                df = pd.read_parquet(file_path)
                df.set_index("timestamp", inplace=True)
                all_data.append(df)
            except:
                pass

        current += timedelta(days=1)

    if not all_data:
        return None

    # Combine all data
    df = pd.concat(all_data).sort_index()

    # Resample to 4H
    df_4h = (
        df.resample("4H")
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

    return df_4h


def main():
    """Test Elliott Wave on real data."""
    print("Testing Elliott Wave detection with real Polygon data...\n")

    analyzer = ElliottWaveAnalyzer()

    # Test with EURUSD
    symbol = "EURUSD"
    print(f"Loading {symbol} data...")

    df = load_4h_data(symbol, days=60)

    if df is None or df.empty:
        print(f"❌ No data loaded for {symbol}")
        return

    print(f"✅ Loaded {len(df)} 4H bars")
    print(f"   Date range: {df.index[0]} to {df.index[-1]}")
    print(f"   Price range: {df['low'].min():.5f} to {df['high'].max():.5f}")

    # Calculate price movement
    price_change = (df["close"].iloc[-1] / df["close"].iloc[0] - 1) * 100
    volatility = df["close"].pct_change().std() * 100

    print(f"   Price change: {price_change:.2f}%")
    print(f"   Daily volatility: {volatility:.2f}%")

    # Show recent price action
    print(f"\nRecent price action (last 10 bars):")
    recent = df.tail(10)
    for idx, row in recent.iterrows():
        change = (row["close"] / row["open"] - 1) * 100
        print(
            f"   {idx}: O={row['open']:.5f} H={row['high']:.5f} L={row['low']:.5f} C={row['close']:.5f} ({change:+.2f}%)"
        )

    # Try Elliott Wave detection
    print(f"\nDetecting Elliott Wave patterns...")

    try:
        result = analyzer.analyze(df)

        if result and result.waves:
            print(f"✅ Found {len(result.waves)} Elliott Wave patterns!")
            for i, wave in enumerate(result.waves[:3]):
                print(f"\nWave {i+1}:")
                print(f"   Type: {wave.wave_type}")
                print(f"   Degree: {wave.degree}")
                print(f"   Start: {wave.start_idx} -> End: {wave.end_idx}")
                print(f"   Confidence: {wave.confidence:.2%}")
        else:
            print("❌ No Elliott Wave patterns detected")

            # Try manual wave detection
            print("\nTrying simplified wave detection...")

            # Look for 5-wave impulse pattern
            highs = df["high"].values
            lows = df["low"].values

            # Find local extrema
            from scipy.signal import argrelextrema

            local_max = argrelextrema(highs, np.greater, order=5)[0]
            local_min = argrelextrema(lows, np.less, order=5)[0]

            print(f"   Found {len(local_max)} local highs")
            print(f"   Found {len(local_min)} local lows")

            if len(local_max) >= 3 and len(local_min) >= 2:
                print("   ✅ Sufficient extrema for potential wave pattern")
            else:
                print("   ❌ Not enough extrema for wave pattern")

    except Exception as e:
        print(f"❌ Error during detection: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    main()
