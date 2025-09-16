#!/usr/bin/env python
"""Debug signal generation in Enhanced System V2."""

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))

import warnings
from datetime import datetime

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")

from scripts.enhanced_production_system_v2 import (
    EnhancedProductionConfigV2,
    EnhancedProductionSystemV2,
)


def load_sample_data(symbol: str = "EURUSD") -> pd.DataFrame:
    """Load a small sample of real data."""
    print(f"Loading sample data for {symbol}...")

    # Load one day of data
    file = f"input/C_{symbol}/year=2024/month=10/day=15/data.parquet.gz"

    try:
        df = pd.read_parquet(file)
        if "timestamp" in df.columns:
            df["timestamp"] = pd.to_datetime(df["timestamp"])
            df = df.set_index("timestamp")

        # Resample to 4H
        print(f"Resampling {len(df)} minute bars to 4H...")
        data = (
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

        # Calculate indicators
        data["sma_20"] = data["close"].rolling(20).mean()
        data["sma_50"] = data["close"].rolling(50).mean()
        data["ema_12"] = data["close"].ewm(span=12).mean()
        data["ema_26"] = data["close"].ewm(span=26).mean()

        # RSI
        delta = data["close"].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        data["rsi_14"] = 100 - (100 / (1 + rs))

        # ATR
        high_low = data["high"] - data["low"]
        high_close = np.abs(data["high"] - data["close"].shift())
        low_close = np.abs(data["low"] - data["close"].shift())
        ranges = pd.concat([high_low, high_close, low_close], axis=1)
        true_range = np.max(ranges, axis=1)
        data["atr_14"] = true_range.rolling(14).mean()

        # Additional indicators
        data["adx"] = 25.0
        data["bb_middle"] = data["close"].rolling(20).mean()
        bb_std = data["close"].rolling(20).std()
        data["bb_upper"] = data["bb_middle"] + 2 * bb_std
        data["bb_lower"] = data["bb_middle"] - 2 * bb_std
        data["volume_sma"] = data["volume"].rolling(20).mean()

        data.fillna(method="ffill", inplace=True)
        data.fillna(method="bfill", inplace=True)

        print(f"Loaded {len(data)} 4H bars")
        return data

    except Exception as e:
        print(f"Error loading data: {e}")
        return None


def debug_signal_generation():
    """Debug why signals aren't being generated."""

    print("\n" + "=" * 60)
    print("DEBUGGING SIGNAL GENERATION")
    print("=" * 60)

    # Load sample data
    data = load_sample_data("EURUSD")
    if data is None or len(data) < 200:
        print("Insufficient data for debugging")
        return

    # Test with different configurations
    configs = {
        "Ultra Aggressive": EnhancedProductionConfigV2(
            min_confluences=1,
            min_signal_confidence=0.3,  # Very low
            use_adaptive_thresholds=False,
            use_news_filter=False,
            use_economic_data=False,
        ),
        "Default V2": EnhancedProductionConfigV2(),
        "Conservative": EnhancedProductionConfigV2(
            min_confluences=2, min_signal_confidence=0.7
        ),
    }

    for config_name, config in configs.items():
        print(f"\n{'='*40}")
        print(f"Testing with {config_name} configuration")
        print(f"{'='*40}")
        print(f"Min confluences: {config.min_confluences}")
        print(f"Min confidence: {config.min_signal_confidence}")
        print(f"Adaptive thresholds: {config.use_adaptive_thresholds}")
        print(f"News filter: {config.use_news_filter}")

        # Initialize system
        system = EnhancedProductionSystemV2(config)

        # Try to generate a signal
        current_time = data.index[-1]
        historical_data = data.iloc[:-1]

        print(f"\nGenerating signal at {current_time}...")

        # Debug individual signal generators
        print("\n1. Testing ML Signal Generator:")
        try:
            ml_signal = system.ml_generator.generate_signals(historical_data, "EURUSD")
            print(f"   ML Signal: {ml_signal}")
        except Exception as e:
            print(f"   ML Error: {e}")

        print("\n2. Testing Elliott Wave Generator:")
        try:
            ew_signal = system.ew_generator.generate_signals(historical_data, "EURUSD")
            print(f"   EW Signal: {ew_signal}")
        except Exception as e:
            print(f"   EW Error: {e}")

        print("\n3. Testing Technical Analysis Generator:")
        try:
            ta_signal = system.ta_analyzer.analyze_market(
                historical_data, "EURUSD", current_time
            )
            print(f"   TA Signal: {ta_signal}")
        except Exception as e:
            print(f"   TA Error: {e}")

        # Try combined signal
        print("\n4. Testing Combined Signal:")
        try:
            combined_signal = system.generate_combined_signal(
                historical_data, "EURUSD", current_time
            )
            if combined_signal:
                print(f"   ✓ Generated signal: {combined_signal}")
            else:
                print(f"   ✗ No signal generated")
        except Exception as e:
            print(f"   Error: {e}")
            import traceback

            traceback.print_exc()


def test_minimal_signal():
    """Test with minimal requirements."""
    print("\n" + "=" * 60)
    print("TESTING MINIMAL SIGNAL REQUIREMENTS")
    print("=" * 60)

    # Create synthetic data that should trigger signals
    dates = pd.date_range(end=datetime.now(), periods=300, freq="4h")

    # Create trending data
    trend = np.linspace(1.0800, 1.1000, len(dates))
    noise = np.random.randn(len(dates)) * 0.0002
    prices = trend + noise

    data = pd.DataFrame(
        {
            "open": prices * 0.9999,
            "high": prices * 1.0001,
            "low": prices * 0.9998,
            "close": prices,
            "volume": 1000000,
            "sma_20": prices,
            "sma_50": prices * 0.99,
            "ema_12": prices,
            "ema_26": prices * 0.999,
            "rsi_14": 60,  # Bullish
            "atr_14": 0.0010,
            "adx": 30,  # Trending
            "bb_middle": prices,
            "bb_upper": prices * 1.002,
            "bb_lower": prices * 0.998,
            "volume_sma": 1000000,
        },
        index=dates,
    )

    # Ultra minimal config
    config = EnhancedProductionConfigV2(
        min_confluences=1,
        min_signal_confidence=0.1,  # Extremely low
        use_adaptive_thresholds=False,
        use_news_filter=False,
        use_economic_data=False,
    )

    system = EnhancedProductionSystemV2(config)

    # Test signal generation
    current_time = data.index[-1]
    signal = system.generate_combined_signal(data, "EURUSD", current_time)

    if signal:
        print(f"✓ SUCCESS! Generated signal: {signal}")
    else:
        print(f"✗ FAILED! No signal even with minimal requirements")

        # Check if generators exist
        print("\nChecking generators:")
        print(f"ML Generator: {hasattr(system, 'ml_generator')}")
        print(f"EW Generator: {hasattr(system, 'ew_generator')}")
        print(f"TA Analyzer: {hasattr(system, 'ta_analyzer')}")


def main():
    """Run debugging."""
    print("\n" + "=" * 80)
    print("ENHANCED SYSTEM V2 - SIGNAL GENERATION DEBUG")
    print("=" * 80)
    print(f"Generated: {datetime.now()}")

    # Run debug tests
    debug_signal_generation()
    test_minimal_signal()

    print("\n" + "=" * 80)
    print("Debug complete!")
    print("=" * 80)


if __name__ == "__main__":
    main()
