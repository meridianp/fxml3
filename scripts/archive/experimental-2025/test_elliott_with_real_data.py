#!/usr/bin/env python
"""Test Elliott Wave with realistic data and relaxed parameters."""

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))

import logging
from datetime import datetime, timedelta

import numpy as np
import pandas as pd

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

from fxml4.wave_analysis.elliott_wave import ElliottWaveAnalyzer
from scripts.enhanced_elliott_wave_signals import EnhancedElliottWaveSignalGenerator


def test_with_realistic_data():
    """Test Elliott Wave detection with realistic generated data."""

    print("Testing Elliott Wave with realistic market data...")
    print("=" * 80)

    # Load realistic data
    all_data = []
    base_path = Path("input/C_EURUSD_REAL")
    start_date = datetime(2024, 10, 1)

    # Load 15 days of data
    for day in range(15):
        date = start_date + timedelta(days=day)
        file_path = (
            base_path
            / f"year={date.year}/month={date.month}/day={date.day}/data.parquet.gz"
        )

        if file_path.exists():
            df = pd.read_parquet(file_path)
            df["timestamp"] = pd.to_datetime(df["timestamp"])
            df = df.set_index("timestamp")
            all_data.append(df)
            print(f"  Loaded {date.date()}")

    if not all_data:
        print("No realistic data found! Run generate_realistic_market_data.py first.")
        return

    # Combine and resample
    combined = pd.concat(all_data).sort_index()
    data_4h = (
        combined.resample("4h")
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

    print(f"\nData loaded: {len(combined)} minute bars -> {len(data_4h)} 4H bars")
    print(f"Price range: {data_4h['low'].min():.5f} to {data_4h['high'].max():.5f}")

    # Test with different configurations
    configs = [
        {
            "min_wave_size": 0.0005,  # 5 pips (very small)
            "peak_detection_window": 1,
            "min_wave_length": 2,
            "fib_tolerance": 0.3,
            "name": "Ultra Sensitive",
        },
        {
            "min_wave_size": 0.001,  # 10 pips
            "peak_detection_window": 2,
            "min_wave_length": 3,
            "fib_tolerance": 0.2,
            "name": "Sensitive",
        },
        {
            "min_wave_size": 0.002,  # 20 pips
            "peak_detection_window": 3,
            "min_wave_length": 5,
            "fib_tolerance": 0.15,
            "name": "Moderate",
        },
        {
            "min_wave_size": 0.003,  # 30 pips
            "peak_detection_window": 5,
            "min_wave_length": 8,
            "fib_tolerance": 0.1,
            "name": "Conservative",
        },
    ]

    best_config = None
    best_patterns = 0

    for config in configs:
        print(f"\n\n{'='*60}")
        print(f"Testing {config['name']} configuration")
        print(f"{'='*60}")

        analyzer = ElliottWaveAnalyzer(
            min_wave_size=config["min_wave_size"],
            peak_detection_window=config["peak_detection_window"],
            min_wave_length=config["min_wave_length"],
            fib_tolerance=config["fib_tolerance"],
        )

        # Detect extremes
        extremes_df = analyzer.detect_peaks_and_troughs(data_4h)
        peaks = extremes_df[extremes_df["is_peak"] == True]
        troughs = extremes_df[extremes_df["is_trough"] == True]

        print(f"Peaks: {len(peaks)}, Troughs: {len(troughs)}")

        if len(peaks) > 0 or len(troughs) > 0:
            # Compute waves
            waves = analyzer.compute_waves(extremes_df)
            print(f"Waves: {len(waves)}")

            if waves:
                # Show wave sizes
                wave_sizes = [w["wave_size_pct"] for w in waves]
                print(
                    f"Wave sizes (% of price): min={min(wave_sizes):.2f}%, "
                    f"max={max(wave_sizes):.2f}%, avg={np.mean(wave_sizes):.2f}%"
                )

                # Find patterns
                impulse_patterns = analyzer.find_impulse_waves(waves)
                corrective_patterns = analyzer.find_corrective_waves(waves)

                print(f"Impulse patterns: {len(impulse_patterns)}")
                print(f"Corrective patterns: {len(corrective_patterns)}")

                total_patterns = len(impulse_patterns) + len(corrective_patterns)
                if total_patterns > best_patterns:
                    best_patterns = total_patterns
                    best_config = config

                # Show pattern details
                if impulse_patterns:
                    print("\nImpulse pattern details:")
                    for i, pattern in enumerate(impulse_patterns[:2]):
                        print(f"  Pattern {i+1}:")
                        print(f"    Confidence: {pattern['confidence']:.2f}")
                        print(
                            f"    Wave 3/1 ratio: {pattern['wave3_to_wave1_ratio']:.2f}"
                        )
                        print(
                            f"    Wave 5/1 ratio: {pattern['wave5_to_wave1_ratio']:.2f}"
                        )

                if corrective_patterns:
                    print("\nCorrective pattern details:")
                    for i, pattern in enumerate(corrective_patterns[:2]):
                        print(f"  Pattern {i+1}:")
                        print(f"    Type: {pattern['pattern_subtype']}")
                        print(f"    Confidence: {pattern['confidence']:.2f}")
                        print(
                            f"    Wave C/A ratio: {pattern['wave_c_to_wave_a_ratio']:.2f}"
                        )

    # Test signal generation with best config
    if best_config:
        print(f"\n\n{'='*80}")
        print(f"Testing signal generation with best config: {best_config['name']}")
        print(f"{'='*80}")

        generator = EnhancedElliottWaveSignalGenerator(
            min_wave_size=best_config["min_wave_size"],
            confidence_threshold=0.3,  # Low threshold
            use_trend_filter=False,  # Disable filters for testing
            use_volume_confirmation=False,
        )

        # Test signal generation at different points
        lookback_periods = [50, 75, 100]
        signals_generated = 0

        for lookback in lookback_periods:
            if len(data_4h) < lookback:
                continue

            print(f"\nTesting with lookback={lookback}:")

            # Try multiple end points
            for offset in [0, 10, 20]:
                if offset > 0 and len(data_4h) < lookback + offset:
                    continue

                test_data = data_4h.iloc[:-(offset)] if offset > 0 else data_4h

                signal = generator.generate_signals(test_data, lookback=lookback)

                if signal:
                    signals_generated += 1
                    print(f"  ✅ Signal at offset {offset}:")
                    print(f"     Action: {signal.action}")
                    print(f"     Confidence: {signal.confidence:.2f}")
                    print(f"     Entry: {signal.entry:.5f}")
                    print(f"     Wave Position: {signal.wave_position}")
                else:
                    print(f"  ❌ No signal at offset {offset}")

        print(f"\nTotal signals generated: {signals_generated}")

    print("\n\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)

    if best_patterns > 0:
        print(f"✅ Elliott Wave detection is working!")
        print(f"Best configuration: {best_config['name']}")
        print(f"Total patterns found: {best_patterns}")
        print("\nRecommendations:")
        print("1. Use realistic market data instead of synthetic flat data")
        print("2. Use smaller window sizes (1-3) for 4H timeframe")
        print("3. Allow smaller minimum wave sizes (0.001 = 10 pips)")
        print("4. Increase Fibonacci tolerance for more flexible pattern matching")
    else:
        print("❌ No patterns found even with realistic data")
        print("The pattern detection logic may need further relaxation")


if __name__ == "__main__":
    test_with_realistic_data()
