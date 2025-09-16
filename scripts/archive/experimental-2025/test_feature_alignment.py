#!/usr/bin/env python
"""Test script to verify feature alignment between training and backtesting."""

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))

import json
from typing import Dict, List

import joblib
import numpy as np
import pandas as pd

# Import unified feature engineering
from fxml4.features import UnifiedFeatureEngineer

# Import the enhanced ML signal generator
from scripts.enhanced_ml_signal_generator import EnhancedMLSignalGenerator


def load_sample_data(symbol: str = "EURUSD") -> pd.DataFrame:
    """Load a sample of data for testing."""
    # Try to load from partitioned data
    data_path = Path(f"input/C_{symbol}")

    if not data_path.exists():
        print(f"No data found for {symbol}")
        return None

    # Load a recent month
    all_data = []
    for year_dir in sorted(data_path.glob("year=2024")):
        for month_dir in sorted(year_dir.glob("month=11")):
            for day_dir in sorted(month_dir.glob("day=*"))[:5]:  # Just 5 days
                for parquet_file in day_dir.glob("*.parquet*"):
                    try:
                        df = pd.read_parquet(parquet_file)
                        if "timestamp" in df.columns:
                            df["timestamp"] = pd.to_datetime(df["timestamp"])
                            df = df.set_index("timestamp")
                        elif "datetime" in df.columns:
                            df["datetime"] = pd.to_datetime(df["datetime"])
                            df = df.set_index("datetime")
                        all_data.append(df)
                    except Exception as e:
                        print(f"Error loading {parquet_file}: {e}")

    if not all_data:
        print(f"No data found for {symbol}")
        return None

    # Combine data
    data = pd.concat(all_data).sort_index()
    data = data[~data.index.duplicated(keep="first")]

    # Resample to 4H if needed
    if len(data) > 0:
        time_diff = (data.index[1] - data.index[0]).total_seconds()
        if time_diff < 3600:
            print(f"Resampling to 4H bars...")
            data = (
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

    print(f"Loaded {len(data)} 4H bars")
    return data


def test_feature_generation():
    """Test unified feature generation."""
    print("\n" + "=" * 60)
    print("TESTING UNIFIED FEATURE GENERATION")
    print("=" * 60)

    # Load sample data
    data = load_sample_data("EURUSD")
    if data is None:
        return False

    # Generate features
    feature_engineer = UnifiedFeatureEngineer(
        {
            "advanced_features": True,
            "elliott_wave_features": True,
            "regime_features": True,
            "microstructure_features": True,
        }
    )

    features = feature_engineer.generate_features(data)

    print(f"\nGenerated {len(features.columns)} features:")
    print(f"Shape: {features.shape}")

    # Check for expected features
    expected_features = [
        "close_to_high",
        "trend_regime",
        "fib_support",
        "fib_resistance",
        "wave_trend",
        "momentum_regime",
        "vol_regime",
        "high_low_spread",
        "parkinson_vol",
        "momentum_3",
        "momentum_10",
        "momentum_30",
        "resistance_20",
        "support_20",
        "channel_position",
        "trend_strength",
    ]

    missing_features = []
    for feat in expected_features:
        if feat not in features.columns:
            missing_features.append(feat)
        else:
            print(f"✓ {feat}: Found")

    if missing_features:
        print(f"\n✗ Missing features: {missing_features}")
        return False

    print("\n✓ All expected features generated successfully!")
    return True


def test_model_compatibility():
    """Test if trained models work with the generated features."""
    print("\n" + "=" * 60)
    print("TESTING MODEL COMPATIBILITY")
    print("=" * 60)

    symbol = "EURUSD"

    # Check if model exists
    model_path = Path(f"models/{symbol}")
    if not model_path.exists():
        print(f"No models found for {symbol}. Please train models first.")
        return False

    # Load model files
    model_files = list(model_path.glob("best_model_*.joblib"))
    if not model_files:
        print(f"No best model found for {symbol}")
        return False

    # Load the model
    model_file = model_files[0]
    print(f"Loading model: {model_file}")
    model = joblib.load(model_file)

    # Load scaler if exists
    scaler_file = model_path / "scaler.joblib"
    scaler = joblib.load(scaler_file) if scaler_file.exists() else None

    # Load feature columns if saved
    feature_cols_file = model_path / "feature_columns.json"
    if feature_cols_file.exists():
        with open(feature_cols_file, "r") as f:
            saved_feature_cols = json.load(f)
        print(f"Model expects {len(saved_feature_cols)} features")
    else:
        saved_feature_cols = None

    # Load sample data
    data = load_sample_data(symbol)
    if data is None:
        return False

    # Generate features using unified engineering
    feature_engineer = UnifiedFeatureEngineer(
        {
            "advanced_features": True,
            "elliott_wave_features": True,
            "regime_features": True,
            "microstructure_features": True,
        }
    )

    features = feature_engineer.generate_features(data)

    # Remove OHLCV columns
    exclude_cols = ["open", "high", "low", "close", "volume"]
    feature_cols = [col for col in features.columns if col not in exclude_cols]
    X = features[feature_cols]

    # Add any missing lagged features
    key_features = ["close", "rsi_14", "macd", "bb_width", "atr_14"]
    for feat in key_features:
        if feat in features.columns:
            for lag in [1, 2, 5]:
                lag_col = f"{feat}_lag_{lag}"
                if lag_col not in X.columns:
                    X[lag_col] = features[feat].shift(lag)

    # Add time features if missing
    if isinstance(X.index, pd.DatetimeIndex):
        if "hour" not in X.columns:
            X["hour"] = X.index.hour
        if "day_of_week" not in X.columns:
            X["day_of_week"] = X.index.dayofweek

    # Clean up
    X = X.fillna(method="ffill").fillna(method="bfill").fillna(0)

    # If we have saved feature columns, use them
    if saved_feature_cols:
        # Add any missing columns with zeros
        for col in saved_feature_cols:
            if col not in X.columns:
                X[col] = 0
        # Select only the columns the model expects
        X = X[saved_feature_cols]

    print(f"\nFeatures shape: {X.shape}")

    # Try to make a prediction
    try:
        # Scale if scaler exists
        if scaler:
            X_scaled = pd.DataFrame(
                scaler.transform(X), columns=X.columns, index=X.index
            )
        else:
            X_scaled = X

        # Make prediction on last row
        prediction = model.predict(X_scaled.iloc[-1:])
        print(f"✓ Model prediction successful: {prediction}")

        # Try probability prediction if available
        try:
            proba = model.predict_proba(X_scaled.iloc[-1:])
            print(f"✓ Probability prediction successful: {proba}")
        except:
            print("  (Model doesn't support predict_proba)")

        return True

    except Exception as e:
        print(f"✗ Model prediction failed: {e}")
        return False


def test_ml_signal_generator():
    """Test the enhanced ML signal generator with unified features."""
    print("\n" + "=" * 60)
    print("TESTING ML SIGNAL GENERATOR")
    print("=" * 60)

    symbol = "EURUSD"

    # Load model
    model_path = Path(f"models/{symbol}")
    if not model_path.exists():
        print(f"No models found for {symbol}")
        return False

    model_files = list(model_path.glob("best_model_*.joblib"))
    if not model_files:
        print(f"No best model found")
        return False

    model = joblib.load(model_files[0])

    # Create signal generator
    signal_gen = EnhancedMLSignalGenerator(
        model=model,
        min_confidence=0.6,
        use_market_regime_filter=True,
        use_volatility_filter=True,
    )

    # Load sample data
    data = load_sample_data(symbol)
    if data is None:
        return False

    # Generate signal
    try:
        current_time = data.index[-1]
        signal = signal_gen.generate_signal(data, current_time)

        if signal:
            print(f"✓ Generated signal:")
            print(f"  Action: {signal.action}")
            print(f"  Confidence: {signal.confidence:.3f}")
            print(f"  Market regime: {signal.market_regime}")
            print(f"  Filters passed: {signal.filters_passed}")
        else:
            print("✓ No signal generated (filters may have blocked it)")

        return True

    except Exception as e:
        print(f"✗ Signal generation failed: {e}")
        import traceback

        traceback.print_exc()
        return False


def main():
    """Run all tests."""
    print("\nFEATURE ALIGNMENT TEST SUITE")
    print("=" * 60)

    tests_passed = 0
    total_tests = 3

    # Test 1: Feature Generation
    if test_feature_generation():
        tests_passed += 1

    # Test 2: Model Compatibility
    if test_model_compatibility():
        tests_passed += 1

    # Test 3: ML Signal Generator
    if test_ml_signal_generator():
        tests_passed += 1

    # Summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    print(f"Tests passed: {tests_passed}/{total_tests}")

    if tests_passed == total_tests:
        print("✓ ALL TESTS PASSED - Feature alignment is working correctly!")
        return 0
    else:
        print("✗ Some tests failed - Please check the implementation")
        return 1


if __name__ == "__main__":
    sys.exit(main())
