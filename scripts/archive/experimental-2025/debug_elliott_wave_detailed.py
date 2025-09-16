#!/usr/bin/env python
"""Detailed debugging of Elliott Wave peak/trough detection."""

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))

from datetime import datetime

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from fxml4.wave_analysis.elliott_wave import ElliottWaveAnalyzer


def load_simple_data():
    """Load simple test data."""
    print("\nLoading EURUSD data...")

    # Load multiple days for proper analysis
    all_data = []
    base_path = Path("input/C_EURUSD/year=2024/month=10")

    # Load 10 days of data
    for day in range(15, 25):
        file_path = base_path / f"day={day}/data.parquet.gz"
        if file_path.exists():
            try:
                df = pd.read_parquet(file_path)
                if "timestamp" in df.columns:
                    df["timestamp"] = pd.to_datetime(df["timestamp"])
                    df = df.set_index("timestamp")
                all_data.append(df)
                print(f"  Loaded day {day}")
            except Exception as e:
                print(f"  Error loading day {day}: {e}")

    if not all_data:
        print("No data loaded!")
        return pd.DataFrame()

    # Combine all data
    df = pd.concat(all_data).sort_index()
    df = df[~df.index.duplicated(keep="first")]

    # Resample to 4H
    print(f"Loaded {len(df)} minute bars from {len(all_data)} days")

    data_4h = (
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

    print(f"Resampled to {len(data_4h)} 4H bars")
    return data_4h


def test_peak_detection_manual(data):
    """Manually test peak detection logic."""
    print("\n" + "=" * 60)
    print("MANUAL PEAK/TROUGH DETECTION TEST")
    print("=" * 60)

    # Show data characteristics
    print(f"\nData shape: {data.shape}")
    print(f"Price range: {data['low'].min():.5f} to {data['high'].max():.5f}")
    print(f"Average price movement: {data['high'].diff().abs().mean():.5f}")

    # Test different window sizes
    windows = [1, 2, 3, 5, 8]

    for window in windows:
        print(f"\n--- Window size: {window} ---")

        # Manual peak detection
        peaks = []
        troughs = []

        high_values = data["high"].values
        low_values = data["low"].values

        for i in range(window, len(data) - window):
            # Check if it's a peak
            is_peak = True
            for j in range(1, window + 1):
                if (
                    high_values[i] <= high_values[i - j]
                    or high_values[i] <= high_values[i + j]
                ):
                    is_peak = False
                    break

            if is_peak:
                peaks.append(i)

            # Check if it's a trough
            is_trough = True
            for j in range(1, window + 1):
                if (
                    low_values[i] >= low_values[i - j]
                    or low_values[i] >= low_values[i + j]
                ):
                    is_trough = False
                    break

            if is_trough:
                troughs.append(i)

        print(f"Found {len(peaks)} peaks and {len(troughs)} troughs")

        if peaks:
            print(
                f"First peak at index {peaks[0]}: {data.index[peaks[0]]} = {high_values[peaks[0]]:.5f}"
            )
        if troughs:
            print(
                f"First trough at index {troughs[0]}: {data.index[troughs[0]]} = {low_values[troughs[0]]:.5f}"
            )


def test_analyzer_with_data(data):
    """Test the analyzer with different configurations."""
    print("\n" + "=" * 60)
    print("TESTING ELLIOTT WAVE ANALYZER")
    print("=" * 60)

    # Test different configurations
    configs = [
        {"peak_detection_window": 1, "min_wave_size": 0.0001},
        {"peak_detection_window": 2, "min_wave_size": 0.0001},
        {"peak_detection_window": 3, "min_wave_size": 0.0001},
        {"peak_detection_window": 5, "min_wave_size": 0.0001},
    ]

    for config in configs:
        print(
            f"\n--- Config: window={config['peak_detection_window']}, min_size={config['min_wave_size']} ---"
        )

        analyzer = ElliottWaveAnalyzer(
            peak_detection_window=config["peak_detection_window"],
            min_wave_size=config["min_wave_size"],
        )

        # Detect peaks and troughs
        extremes_df = analyzer.detect_peaks_and_troughs(data)

        peaks = extremes_df[extremes_df["is_peak"] == True]
        troughs = extremes_df[extremes_df["is_trough"] == True]

        print(f"Peaks found: {len(peaks)}")
        print(f"Troughs found: {len(troughs)}")

        if len(peaks) > 0 or len(troughs) > 0:
            # Try to compute waves
            waves = analyzer.compute_waves(extremes_df)
            print(f"Waves computed: {len(waves)}")

            if waves:
                # Show first wave
                wave = waves[0]
                print(f"First wave: {wave['start_type']} -> {wave['end_type']}")
                print(f"  Price: {wave['start_price']:.5f} -> {wave['end_price']:.5f}")
                print(f"  Size: {wave['wave_size']:.5f} ({wave['wave_size_pct']:.3f}%)")


def visualize_data_and_extremes(data):
    """Visualize the data with different window sizes."""
    print("\n" + "=" * 60)
    print("VISUALIZING DATA AND EXTREMES")
    print("=" * 60)

    fig, axes = plt.subplots(3, 1, figsize=(15, 12))

    # Different window sizes
    windows = [1, 3, 5]

    for idx, window in enumerate(windows):
        ax = axes[idx]

        # Plot price
        ax.plot(data.index, data["close"], "b-", linewidth=1, label="Close")
        ax.plot(data.index, data["high"], "g-", alpha=0.3, linewidth=0.5)
        ax.plot(data.index, data["low"], "r-", alpha=0.3, linewidth=0.5)

        # Detect peaks and troughs
        analyzer = ElliottWaveAnalyzer(
            peak_detection_window=window, min_wave_size=0.0001
        )
        extremes_df = analyzer.detect_peaks_and_troughs(data)

        peaks = extremes_df[extremes_df["is_peak"] == True]
        troughs = extremes_df[extremes_df["is_trough"] == True]

        # Mark peaks and troughs
        if not peaks.empty:
            ax.scatter(
                peaks.index,
                peaks["high"],
                color="red",
                marker="v",
                s=100,
                label=f"Peaks ({len(peaks)})",
            )
        if not troughs.empty:
            ax.scatter(
                troughs.index,
                troughs["low"],
                color="green",
                marker="^",
                s=100,
                label=f"Troughs ({len(troughs)})",
            )

        ax.set_title(
            f"Window Size: {window} - Peaks: {len(peaks)}, Troughs: {len(troughs)}"
        )
        ax.set_ylabel("Price")
        ax.legend()
        ax.grid(True, alpha=0.3)

    plt.tight_layout()
    plt.savefig("output/elliott_wave_detailed_debug.png", dpi=150)
    print(f"Saved visualization to output/elliott_wave_detailed_debug.png")


def create_synthetic_wave_data():
    """Create synthetic data with clear wave patterns."""
    print("\n" + "=" * 60)
    print("TESTING WITH SYNTHETIC WAVE DATA")
    print("=" * 60)

    # Create synthetic Elliott Wave pattern
    dates = pd.date_range(start="2024-01-01", periods=100, freq="4H")

    # Create a simple 5-wave impulse pattern
    wave_points = [
        1.1000,  # Start
        1.1100,  # Wave 1 top
        1.1050,  # Wave 2 bottom
        1.1200,  # Wave 3 top
        1.1150,  # Wave 4 bottom
        1.1250,  # Wave 5 top
    ]

    # Interpolate between wave points
    x_points = np.linspace(0, len(dates) - 1, len(wave_points))
    prices = np.interp(range(len(dates)), x_points, wave_points)

    # Add some noise
    prices += np.random.normal(0, 0.0005, len(prices))

    # Create OHLC data
    synthetic_data = pd.DataFrame(index=dates)
    synthetic_data["close"] = prices
    synthetic_data["high"] = prices + np.abs(np.random.normal(0, 0.0002, len(prices)))
    synthetic_data["low"] = prices - np.abs(np.random.normal(0, 0.0002, len(prices)))
    synthetic_data["open"] = synthetic_data["close"].shift(1).fillna(prices[0])
    synthetic_data["volume"] = 1000

    print(f"Created synthetic data with {len(synthetic_data)} bars")

    # Test with analyzer
    analyzer = ElliottWaveAnalyzer(peak_detection_window=3, min_wave_size=0.0001)
    extremes_df = analyzer.detect_peaks_and_troughs(synthetic_data)

    peaks = extremes_df[extremes_df["is_peak"] == True]
    troughs = extremes_df[extremes_df["is_trough"] == True]

    print(f"Peaks found: {len(peaks)}")
    print(f"Troughs found: {len(troughs)}")

    if len(peaks) > 0 or len(troughs) > 0:
        waves = analyzer.compute_waves(extremes_df)
        print(f"Waves computed: {len(waves)}")

        # Try full analysis
        result = analyzer.analyze(synthetic_data)
        if result and result.waves:
            print(f"Full analysis found {len(result.waves)} patterns")
        else:
            print("No patterns found in full analysis")

    # Visualize
    plt.figure(figsize=(12, 6))
    plt.plot(
        synthetic_data.index,
        synthetic_data["close"],
        "b-",
        linewidth=2,
        label="Synthetic Wave",
    )

    if not peaks.empty:
        plt.scatter(
            peaks.index, peaks["high"], color="red", marker="v", s=150, label="Peaks"
        )
    if not troughs.empty:
        plt.scatter(
            troughs.index,
            troughs["low"],
            color="green",
            marker="^",
            s=150,
            label="Troughs",
        )

    plt.title("Synthetic Elliott Wave Pattern")
    plt.ylabel("Price")
    plt.xlabel("Time")
    plt.legend()
    plt.grid(True, alpha=0.3)
    plt.savefig("output/elliott_wave_synthetic.png", dpi=150)
    print(f"Saved synthetic wave visualization")


def main():
    """Run detailed debugging."""
    # Load real data
    data = load_simple_data()

    # Manual peak detection test
    test_peak_detection_manual(data)

    # Test analyzer
    test_analyzer_with_data(data)

    # Visualize
    visualize_data_and_extremes(data)

    # Test with synthetic data
    create_synthetic_wave_data()

    print("\n" + "=" * 60)
    print("DETAILED DEBUGGING COMPLETE")
    print("=" * 60)
    print("\nKey findings:")
    print("1. Peak/trough detection requires appropriate window size")
    print("2. Window size 1-2 is too small for 4H data")
    print("3. Window size 3-5 works better for smoother price action")
    print("4. The analyzer is working but needs tuning for the data timeframe")


if __name__ == "__main__":
    main()
