#!/usr/bin/env python
"""Test Elliott Wave with tuned parameters for real data."""

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

    return df_4h


def main():
    """Test Elliott Wave with different parameters."""
    print("Testing Elliott Wave detection with tuned parameters...\n")

    # Test different analyzer configurations
    configs = [
        {"min_points": 5, "threshold": 0.0005},  # More sensitive
        {"min_points": 3, "threshold": 0.001},  # Balanced
        {"min_points": 7, "threshold": 0.0001},  # Less sensitive
    ]

    symbol = "EURUSD"
    df = load_4h_data(symbol, days=90)  # More data

    if df is None or df.empty:
        print(f"❌ No data loaded for {symbol}")
        return

    print(f"✅ Loaded {len(df)} 4H bars")
    print(f"   Date range: {df.index[0]} to {df.index[-1]}")

    # Calculate metrics
    returns = df["close"].pct_change().dropna()
    avg_move = abs(returns).mean() * 100
    max_move = abs(returns).max() * 100

    print(f"   Average bar movement: {avg_move:.3f}%")
    print(f"   Maximum bar movement: {max_move:.3f}%")

    # Test each configuration
    for i, config in enumerate(configs):
        print(f"\n{'='*60}")
        print(
            f"Configuration {i+1}: min_points={config['min_points']}, threshold={config['threshold']}"
        )
        print(f"{'='*60}")

        analyzer = ElliottWaveAnalyzer(
            min_wave_size=config["threshold"],
            peak_detection_window=config["min_points"],
        )

        try:
            result = analyzer.analyze(df)

            if result and result.waves:
                print(f"✅ Found {len(result.waves)} Elliott Wave patterns!")

                # Group by wave type
                by_type = {}
                for wave in result.waves:
                    wave_type = str(wave.wave_type)
                    if wave_type not in by_type:
                        by_type[wave_type] = []
                    by_type[wave_type].append(wave)

                for wave_type, waves in by_type.items():
                    print(f"\n{wave_type}: {len(waves)} patterns")

                    # Show best pattern
                    best = max(waves, key=lambda w: w.confidence)
                    print(f"   Best confidence: {best.confidence:.2%}")
                    print(
                        f"   Period: {df.index[best.start_idx]} to {df.index[best.end_idx]}"
                    )

                    # Show price range
                    price_slice = df.iloc[best.start_idx : best.end_idx + 1]
                    price_range = price_slice["high"].max() - price_slice["low"].min()
                    price_move = (
                        price_slice["close"].iloc[-1] / price_slice["close"].iloc[0] - 1
                    ) * 100

                    print(f"   Price range: {price_range:.5f} ({price_move:+.2f}%)")

            else:
                print("❌ No Elliott Wave patterns detected")

        except Exception as e:
            print(f"❌ Error: {e}")

    # Try with daily data for longer-term patterns
    print(f"\n{'='*60}")
    print("Testing with Daily timeframe for longer-term patterns")
    print(f"{'='*60}")

    # Resample to daily
    df_daily = (
        df.resample("1D")
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

    print(f"✅ Resampled to {len(df_daily)} daily bars")

    analyzer = ElliottWaveAnalyzer(min_wave_size=0.001, peak_detection_window=5)
    result = analyzer.analyze(df_daily)

    if result and result.waves:
        print(f"✅ Found {len(result.waves)} patterns on daily timeframe!")
    else:
        print("❌ No patterns on daily timeframe")


if __name__ == "__main__":
    main()
