#!/usr/bin/env python
"""Test complete Enhanced System V2 with actual model."""

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))

import warnings
from datetime import datetime, timedelta

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")

import joblib

from scripts.enhanced_production_system_v2 import (
    EnhancedProductionConfigV2,
    EnhancedProductionSystemV2,
)


def load_sample_data(symbol: str = "EURUSD", days: int = 5) -> pd.DataFrame:
    """Load real historical data."""
    print(f"Loading {days} days of data for {symbol}...")

    all_data = []
    data_path = Path(f"input/C_{symbol}")

    # Load recent data
    for year_dir in sorted(data_path.glob("year=2024")):
        for month_dir in sorted(year_dir.glob("month=*"))[-2:]:  # Last 2 months
            for day_dir in sorted(month_dir.glob("day=*"))[-days:]:  # Last N days
                for parquet_file in day_dir.glob("*.parquet*"):
                    try:
                        df = pd.read_parquet(parquet_file)
                        if "timestamp" in df.columns:
                            df["timestamp"] = pd.to_datetime(df["timestamp"])
                            df = df.set_index("timestamp")
                        all_data.append(df)
                    except Exception as e:
                        print(f"Error loading {parquet_file}: {e}")

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

    # Calculate indicators
    data_4h["sma_20"] = data_4h["close"].rolling(20).mean()
    data_4h["sma_50"] = data_4h["close"].rolling(50).mean()
    data_4h["ema_12"] = data_4h["close"].ewm(span=12).mean()
    data_4h["ema_26"] = data_4h["close"].ewm(span=26).mean()

    # RSI
    delta = data_4h["close"].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    data_4h["rsi_14"] = 100 - (100 / (1 + rs))

    # ATR
    high_low = data_4h["high"] - data_4h["low"]
    high_close = np.abs(data_4h["high"] - data_4h["close"].shift())
    low_close = np.abs(data_4h["low"] - data_4h["close"].shift())
    ranges = pd.concat([high_low, high_close, low_close], axis=1)
    true_range = np.max(ranges, axis=1)
    data_4h["atr_14"] = true_range.rolling(14).mean()

    # Additional indicators
    data_4h["adx"] = 25.0
    data_4h["bb_middle"] = data_4h["close"].rolling(20).mean()
    bb_std = data_4h["close"].rolling(20).std()
    data_4h["bb_upper"] = data_4h["bb_middle"] + 2 * bb_std
    data_4h["bb_lower"] = data_4h["bb_middle"] - 2 * bb_std
    data_4h["volume_sma"] = data_4h["volume"].rolling(20).mean()

    data_4h.fillna(method="ffill", inplace=True)
    data_4h.fillna(method="bfill", inplace=True)

    print(f"Prepared {len(data_4h)} 4H bars with indicators")
    return data_4h


def test_with_model():
    """Test system with an actual trained model."""
    print("\n" + "=" * 60)
    print("TESTING WITH TRAINED MODEL")
    print("=" * 60)

    # Try to load a model
    model = None
    scaler = None

    # Check different model locations
    model_paths = [
        Path("models/EURUSD/"),
        Path("models/EURUSD_robust/"),
        Path("models/EURUSD_integrated_simple/"),
    ]

    for model_path in model_paths:
        if model_path.exists():
            try:
                # Look for model files
                model_files = list(model_path.glob("model_*.joblib")) + list(
                    model_path.glob("best_model_*.joblib")
                )
                if model_files:
                    model = joblib.load(model_files[0])

                    # Try to load scaler
                    scaler_path = model_path / "scaler.joblib"
                    if scaler_path.exists():
                        scaler = joblib.load(scaler_path)

                    print(f"✓ Loaded model from {model_path}")
                    break
            except Exception as e:
                print(f"✗ Failed to load from {model_path}: {e}")

    if model is None:
        print("✗ No model found in any location")

    # Load data
    data = load_sample_data("EURUSD", days=10)
    if data is None or len(data) < 100:
        print("Insufficient data")
        return

    # Test configurations
    configs = {
        "Aggressive V2": EnhancedProductionConfigV2(
            min_confluences=1,
            min_signal_confidence=0.5,
            use_adaptive_thresholds=True,
            use_news_filter=False,  # Disable for testing
        ),
        "Default V2": EnhancedProductionConfigV2(),
    }

    for config_name, config in configs.items():
        print(f"\n{'='*40}")
        print(f"Testing {config_name}")
        print(f"{'='*40}")

        # Initialize system with model
        system = EnhancedProductionSystemV2(config, ml_model=model)

        # Run through recent data
        signals_generated = 0
        trades_executed = 0

        for i in range(100, len(data), 4):  # Every 4 bars
            current_time = data.index[i]
            current_bar = data.iloc[i]
            historical_data = data.iloc[: i + 1]

            # Generate signal
            signal = system.generate_combined_signal(
                historical_data, "EURUSD", current_time
            )

            if signal:
                signals_generated += 1
                print(f"\n✓ Signal at {current_time}:")
                print(f"  Action: {signal['action']}")
                print(f"  Confidence: {signal['confidence']:.2f}")
                print(f"  Confluences: {signal.get('confluences', 'N/A')}")
                print(f"  Sources: {[s['source'] for s in signal.get('signals', [])]}")

                # Try to execute
                if len(system.positions) < config.max_positions:
                    system.execute_trade(signal, current_bar, current_time, "EURUSD")
                    if len(system.trades) > trades_executed:
                        trades_executed = len(system.trades)
                        print(f"  ✓ Trade executed!")

            # Update positions
            system.update_positions("EURUSD", current_bar, current_time)

        print(f"\nResults for {config_name}:")
        print(f"  Signals generated: {signals_generated}")
        print(f"  Trades executed: {trades_executed}")
        print(f"  Performance stats: {system.performance_stats}")


def test_without_model():
    """Test system without ML model (using other signals)."""
    print("\n" + "=" * 60)
    print("TESTING WITHOUT ML MODEL")
    print("=" * 60)

    # Load data
    data = load_sample_data("EURUSD", days=5)
    if data is None or len(data) < 50:
        print("Insufficient data")
        return

    # Ultra aggressive config
    config = EnhancedProductionConfigV2(
        min_confluences=1,
        min_signal_confidence=0.4,
        use_adaptive_thresholds=False,
        use_news_filter=False,
        use_economic_data=False,
    )

    # Initialize system without model
    system = EnhancedProductionSystemV2(config, ml_model=None)

    # Test individual generators
    current_time = data.index[-10]
    historical_data = data.iloc[:-10]

    print("\nTesting individual signal generators:")

    # Elliott Wave
    print("\n1. Elliott Wave:")
    try:
        ew_signal = system.ew_generator.generate_signals(historical_data)
        print(f"   Result: {ew_signal}")
        if ew_signal:
            print(f"   Action: {ew_signal.action}, Confidence: {ew_signal.confidence}")
    except Exception as e:
        print(f"   Error: {e}")

    # Technical Analysis
    print("\n2. Technical Analysis:")
    try:
        ta_signal = system.ta_analyzer.analyze_market(historical_data, "EURUSD")
        print(f"   Result: {ta_signal}")
        if ta_signal:
            print(f"   Bias: {ta_signal.bias}, Confidence: {ta_signal.confidence}")
    except Exception as e:
        print(f"   Error: {e}")

    # Combined signal
    print("\n3. Combined Signal:")
    signal = system.generate_combined_signal(historical_data, "EURUSD", current_time)
    if signal:
        print(f"   ✓ SUCCESS! Generated combined signal")
        print(f"   Action: {signal['action']}")
        print(f"   Confidence: {signal['confidence']}")
    else:
        print(f"   ✗ No combined signal generated")


def main():
    """Run complete system test."""
    print("\n" + "=" * 80)
    print("ENHANCED SYSTEM V2 - COMPLETE SYSTEM TEST")
    print("=" * 80)
    print(f"Generated: {datetime.now()}")

    # Test with model if available
    test_with_model()

    # Test without model
    test_without_model()

    print("\n" + "=" * 80)
    print("Test complete!")
    print("=" * 80)


if __name__ == "__main__":
    main()
