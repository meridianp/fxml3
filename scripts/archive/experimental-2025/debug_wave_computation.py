#!/usr/bin/env python
"""Debug wave computation issues."""

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))

from datetime import datetime, timedelta

import numpy as np
import pandas as pd

from fxml4.wave_analysis.elliott_wave import ElliottWaveAnalyzer


def debug_wave_computation():
    """Debug why wave computation is producing NaN values."""

    print("Debugging wave computation...")
    print("=" * 80)

    # Load one day of realistic data
    file_path = Path("input/C_EURUSD_REAL/year=2024/month=10/day=1/data.parquet.gz")

    if not file_path.exists():
        print(
            "Realistic data not found. Please run generate_realistic_market_data.py first."
        )
        return

    df = pd.read_parquet(file_path)
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

    print(f"Loaded {len(df)} minute bars -> {len(data_4h)} 4H bars")
    print(f"\n4H Data sample:")
    print(data_4h.head())

    # Initialize analyzer with very relaxed parameters
    analyzer = ElliottWaveAnalyzer(
        min_wave_size=0.0001,  # 1 pip
        peak_detection_window=1,
        min_wave_length=1,
        fib_tolerance=0.5,
    )

    # Step 1: Detect peaks and troughs
    print("\n\nStep 1: Detecting peaks and troughs...")
    extremes_df = analyzer.detect_peaks_and_troughs(data_4h)

    print(f"Extremes DataFrame shape: {extremes_df.shape}")
    print(f"Extremes DataFrame index type: {type(extremes_df.index)}")
    print(f"Extremes DataFrame columns: {extremes_df.columns.tolist()}")
    print("\nFirst few rows of extremes_df:")
    print(extremes_df.head())

    peaks = extremes_df[extremes_df["is_peak"] == True]
    troughs = extremes_df[extremes_df["is_trough"] == True]

    print(f"\nPeaks found: {len(peaks)}")
    if len(peaks) > 0:
        print("Peak indices:", peaks.index.tolist())
        print("Peak dataframe:")
        print(peaks)

    print(f"\nTroughs found: {len(troughs)}")
    if len(troughs) > 0:
        print("Trough indices:", troughs.index.tolist())
        print("Trough low values:", troughs["low"].values)

    # Step 2: Manually compute waves to debug
    print("\n\nStep 2: Manually computing waves...")

    if len(peaks) > 0 or len(troughs) > 0:
        # Get all extremes
        all_peaks = [(idx, "peak") for idx in peaks.index]
        all_troughs = [(idx, "trough") for idx in troughs.index]
        all_extremes = all_peaks + all_troughs
        all_extremes.sort(key=lambda x: x[0])

        print(f"\nAll extremes (sorted): {len(all_extremes)}")
        for i, (idx, ext_type) in enumerate(all_extremes[:5]):
            print(f"  {i}: {idx} ({ext_type})")

        # Manually compute first wave
        if len(all_extremes) >= 2:
            print("\n\nManually computing first wave:")
            start_idx, start_type = all_extremes[0]
            end_idx, end_type = all_extremes[1]

            print(f"Start: {start_idx} ({start_type})")
            print(f"End: {end_idx} ({end_type})")

            # Get positions
            try:
                start_pos = extremes_df.index.get_loc(start_idx)
                end_pos = extremes_df.index.get_loc(end_idx)
                print(f"Start position: {start_pos}")
                print(f"End position: {end_pos}")

                # Get prices
                if start_type == "peak":
                    start_price = float(extremes_df.loc[start_idx, "high"])
                    end_price = float(extremes_df.loc[end_idx, "low"])
                else:
                    start_price = float(extremes_df.loc[start_idx, "low"])
                    end_price = float(extremes_df.loc[end_idx, "high"])

                print(f"Start price: {start_price}")
                print(f"End price: {end_price}")

                # Calculate wave properties
                wave_length = end_pos - start_pos
                wave_size = abs(end_price - start_price)
                wave_size_pct = (
                    (wave_size / abs(start_price)) * 100 if start_price != 0 else 0
                )

                print(f"Wave length: {wave_length}")
                print(f"Wave size: {wave_size:.5f}")
                print(f"Wave size %: {wave_size_pct:.2f}%")

            except Exception as e:
                print(f"Error computing wave: {e}")
                import traceback

                traceback.print_exc()

    # Step 3: Try compute_waves method
    print("\n\nStep 3: Using compute_waves method...")
    try:
        waves = analyzer.compute_waves(extremes_df)
        print(f"Waves computed: {len(waves)}")

        if waves:
            print("\nFirst wave details:")
            wave = waves[0]
            for key, value in wave.items():
                print(f"  {key}: {value}")

            # Check for NaN values
            if "wave_size_pct" in wave:
                if pd.isna(wave["wave_size_pct"]):
                    print("\n⚠️ Found NaN in wave_size_pct!")
                    print(f"  start_price: {wave.get('start_price')}")
                    print(f"  end_price: {wave.get('end_price')}")
                    print(f"  wave_size: {wave.get('wave_size')}")

    except Exception as e:
        print(f"Error in compute_waves: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    debug_wave_computation()
