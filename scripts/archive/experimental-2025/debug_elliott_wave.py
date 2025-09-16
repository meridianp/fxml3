#!/usr/bin/env python
"""Debug Elliott Wave pattern detection."""

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))

import logging
from datetime import datetime

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

# Set up detailed logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

from fxml4.wave_analysis.elliott_wave import ElliottWaveAnalyzer
from scripts.enhanced_elliott_wave_signals import EnhancedElliottWaveSignalGenerator


def load_test_data(symbol: str = "EURUSD", days: int = 30) -> pd.DataFrame:
    """Load test data for debugging."""
    print(f"\nLoading {days} days of {symbol} data...")

    all_data = []
    data_path = Path(f"input/C_{symbol}")

    # Load October 2024 data
    for day in range(1, min(days + 1, 32)):
        file_path = data_path / f"year=2024/month=10/day={day}/data.parquet.gz"
        if file_path.exists():
            try:
                df = pd.read_parquet(file_path)
                if "timestamp" in df.columns:
                    df["timestamp"] = pd.to_datetime(df["timestamp"])
                    df = df.set_index("timestamp")
                all_data.append(df)
            except Exception as e:
                logger.error(f"Error loading {file_path}: {e}")

    if not all_data:
        print("No data loaded!")
        return None

    # Combine and resample to 4H
    data = pd.concat(all_data).sort_index()
    data = data[~data.index.duplicated(keep="first")]

    print(f"Loaded {len(data)} minute bars, resampling to 4H...")
    data_4h = (
        data.resample("4H")
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

    print(f"Prepared {len(data_4h)} 4H bars")
    return data_4h


def debug_elliott_wave_analyzer():
    """Debug the Elliott Wave analyzer step by step."""

    print("\n" + "=" * 80)
    print("DEBUGGING ELLIOTT WAVE ANALYZER")
    print("=" * 80)

    # Load data
    data = load_test_data("EURUSD", days=30)
    if data is None or len(data) < 50:
        print("Insufficient data for analysis")
        return

    # Test with different configurations
    configs = [
        {"min_wave_size": 0.001, "name": "Very Small Waves (10 pips)"},
        {"min_wave_size": 0.003, "name": "Default (30 pips)"},
        {"min_wave_size": 0.005, "name": "Large Waves (50 pips)"},
        {"min_wave_size": 0.0001, "name": "Tiny Waves (1 pip)"},
    ]

    for config in configs:
        print(f"\n{'='*60}")
        print(f"Testing with {config['name']}")
        print(
            f"Min wave size: {config['min_wave_size']} ({config['min_wave_size']*10000:.0f} pips)"
        )
        print(f"{'='*60}")

        # Create analyzer
        analyzer = ElliottWaveAnalyzer(min_wave_size=config["min_wave_size"])

        # Step 1: Detect peaks and troughs
        print("\n1. Detecting peaks and troughs...")
        try:
            extremes_df = analyzer.detect_peaks_and_troughs(data)

            # Count extremes
            peaks = extremes_df[extremes_df["is_peak"] == True]
            troughs = extremes_df[extremes_df["is_trough"] == True]

            print(f"   Found {len(peaks)} peaks and {len(troughs)} troughs")

            if len(peaks) > 0:
                print(f"   First peak: {peaks.index[0]} at {peaks['high'].iloc[0]:.5f}")
                print(
                    f"   Last peak: {peaks.index[-1]} at {peaks['high'].iloc[-1]:.5f}"
                )

            if len(troughs) > 0:
                print(
                    f"   First trough: {troughs.index[0]} at {troughs['low'].iloc[0]:.5f}"
                )
                print(
                    f"   Last trough: {troughs.index[-1]} at {troughs['low'].iloc[-1]:.5f}"
                )

        except Exception as e:
            print(f"   ERROR in peak/trough detection: {e}")
            import traceback

            traceback.print_exc()
            continue

        # Step 2: Compute waves
        print("\n2. Computing waves from extremes...")
        try:
            waves = analyzer.compute_waves(extremes_df)
            print(f"   Found {len(waves)} waves")

            if waves:
                # Show first few waves
                for i, wave in enumerate(waves[:3]):
                    print(f"   Wave {i+1}: {wave['start_type']} -> {wave['end_type']}")
                    print(
                        f"     Price: {wave['start_price']:.5f} -> {wave['end_price']:.5f}"
                    )
                    print(
                        f"     Size: {wave['wave_size']:.5f} ({wave['wave_size_pct']:.2f}%)"
                    )
                    print(f"     Length: {wave['wave_length']} bars")

        except Exception as e:
            print(f"   ERROR in wave computation: {e}")
            import traceback

            traceback.print_exc()
            continue

        # Step 3: Find impulse waves
        print("\n3. Finding impulse wave patterns...")
        try:
            impulse_patterns = analyzer.find_impulse_waves(waves)
            print(f"   Found {len(impulse_patterns)} impulse patterns")

            for i, pattern in enumerate(impulse_patterns[:2]):
                print(f"   Pattern {i+1}:")
                print(f"     Confidence: {pattern['confidence']:.2f}")
                print(f"     Waves: {len(pattern['waves'])}")
                print(f"     Start: {pattern['start_idx']} End: {pattern['end_idx']}")

        except Exception as e:
            print(f"   ERROR in impulse wave detection: {e}")
            import traceback

            traceback.print_exc()

        # Step 4: Find corrective waves
        print("\n4. Finding corrective wave patterns...")
        try:
            corrective_patterns = analyzer.find_corrective_waves(waves)
            print(f"   Found {len(corrective_patterns)} corrective patterns")

            for i, pattern in enumerate(corrective_patterns[:2]):
                print(f"   Pattern {i+1}:")
                print(f"     Type: {pattern['pattern_subtype']}")
                print(f"     Confidence: {pattern['confidence']:.2f}")

        except Exception as e:
            print(f"   ERROR in corrective wave detection: {e}")
            import traceback

            traceback.print_exc()

        # Step 5: Full analysis
        print("\n5. Running full analysis...")
        try:
            result = analyzer.analyze(data)

            if result and result.waves:
                print(f"   ✓ Analysis successful! Found {len(result.waves)} patterns")
                for i, pattern in enumerate(result.waves[:3]):
                    print(
                        f"   Pattern {i+1}: {pattern.wave_type} (confidence: {pattern.confidence:.2f})"
                    )
            else:
                print("   ✗ No patterns found in full analysis")

        except Exception as e:
            print(f"   ERROR in full analysis: {e}")
            import traceback

            traceback.print_exc()

    # Visualize the data and waves
    print("\n" + "=" * 60)
    print("VISUALIZING PRICE DATA AND WAVES")
    print("=" * 60)

    plt.figure(figsize=(15, 10))

    # Plot price data
    plt.subplot(2, 1, 1)
    plt.plot(data.index, data["close"], "b-", linewidth=1, label="Close Price")
    plt.plot(data.index, data["high"], "g-", alpha=0.5, linewidth=0.5, label="High")
    plt.plot(data.index, data["low"], "r-", alpha=0.5, linewidth=0.5, label="Low")
    plt.title(f"EURUSD 4H Price Data ({len(data)} bars)")
    plt.ylabel("Price")
    plt.legend()
    plt.grid(True, alpha=0.3)

    # Plot with detected extremes
    plt.subplot(2, 1, 2)
    plt.plot(data.index, data["close"], "b-", linewidth=1)

    # Mark peaks and troughs if we have them
    if "extremes_df" in locals() and not extremes_df.empty:
        peaks = extremes_df[extremes_df["is_peak"] == True]
        troughs = extremes_df[extremes_df["is_trough"] == True]

        if not peaks.empty:
            plt.scatter(
                peaks.index,
                peaks["high"],
                color="red",
                marker="v",
                s=100,
                label="Peaks",
            )
        if not troughs.empty:
            plt.scatter(
                troughs.index,
                troughs["low"],
                color="green",
                marker="^",
                s=100,
                label="Troughs",
            )

    plt.title("Price with Detected Peaks and Troughs")
    plt.ylabel("Price")
    plt.xlabel("Time")
    plt.legend()
    plt.grid(True, alpha=0.3)

    plt.tight_layout()
    plt.savefig("output/elliott_wave_debug.png", dpi=150)
    print(f"\nSaved visualization to output/elliott_wave_debug.png")


def test_signal_generator():
    """Test the signal generator with debug output."""

    print("\n" + "=" * 80)
    print("TESTING SIGNAL GENERATOR")
    print("=" * 80)

    # Load data
    data = load_test_data("EURUSD", days=30)
    if data is None or len(data) < 100:
        print("Insufficient data for signal generation")
        return

    # Test with different configurations
    configs = [
        {
            "min_wave_size": 0.0001,
            "confidence_threshold": 0.3,
            "use_trend_filter": False,
            "use_volume_confirmation": False,
            "name": "Ultra Aggressive",
        },
        {
            "min_wave_size": 0.001,
            "confidence_threshold": 0.5,
            "use_trend_filter": True,
            "use_volume_confirmation": False,
            "name": "Moderate",
        },
    ]

    for config in configs:
        print(f"\n{'='*40}")
        print(f"Testing {config['name']} configuration")
        print(f"{'='*40}")

        generator = EnhancedElliottWaveSignalGenerator(
            min_wave_size=config["min_wave_size"],
            confidence_threshold=config["confidence_threshold"],
            use_trend_filter=config["use_trend_filter"],
            use_volume_confirmation=config["use_volume_confirmation"],
        )

        # Test signal generation
        lookback_periods = [50, 100, 150]

        for lookback in lookback_periods:
            if len(data) < lookback:
                continue

            print(f"\nTesting with lookback={lookback}:")

            signal = generator.generate_signals(data, lookback=lookback)

            if signal:
                print(f"  ✓ Signal generated!")
                print(f"    Action: {signal.action}")
                print(f"    Confidence: {signal.confidence:.2f}")
                print(f"    Entry: {signal.entry:.5f}")
                print(f"    Stop Loss: {signal.stop_loss:.5f}")
                print(f"    Targets: {[f'{t:.5f}' for t in signal.targets]}")
                print(f"    Wave Position: {signal.wave_position}")
                print(f"    Reasoning: {signal.reasoning}")
            else:
                print(f"  ✗ No signal generated")

                # Debug why no signal
                print(f"  Debugging:")

                # Check analyzer directly
                analysis_data = data.tail(lookback)
                result = generator.analyzer.analyze(analysis_data)

                if not result or not result.waves:
                    print(f"    - No waves detected by analyzer")
                else:
                    print(f"    - {len(result.waves)} waves detected")
                    for wave in result.waves[:3]:
                        print(
                            f"      Wave: {wave.wave_type}, confidence: {wave.confidence:.2f}"
                        )
                        if wave.confidence < config["confidence_threshold"]:
                            print(
                                f"        (Below threshold {config['confidence_threshold']})"
                            )


def main():
    """Run all debug tests."""
    debug_elliott_wave_analyzer()
    test_signal_generator()

    print("\n" + "=" * 80)
    print("DEBUGGING COMPLETE")
    print("=" * 80)


if __name__ == "__main__":
    main()
