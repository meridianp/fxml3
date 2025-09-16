#!/usr/bin/env python
"""Debug why enhanced strategy generates no signals."""

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))

import json

import joblib
import numpy as np
import pandas as pd

# Load model and data
symbol = "GBPUSD"
model_dir = Path(f"models/{symbol}_integrated_simple")
model = joblib.load(model_dir / "model.joblib")
scaler = joblib.load(model_dir / "scaler.joblib")

with open(model_dir / "features.json", "r") as f:
    features = json.load(f)

# Load and prepare data
df = pd.read_parquet(f"data/features/{symbol}_4h_features_advanced.parquet")

# Add missing features
if "returns_log" not in df.columns:
    df["returns_log"] = np.log(df["close"] / df["close"].shift(1))

if "volatility_20" not in df.columns:
    df["volatility_20"] = df["returns_log"].rolling(20).std()
    df["volatility_ratio"] = (
        df["volatility_20"] / df["volatility_20"].rolling(100).mean()
    )

if "volume_ratio" not in df.columns and "volume" in df.columns:
    df["volume_ratio"] = df["volume"] / df["volume"].rolling(20).mean()
    df["price_volume"] = df["close"] * df["volume"]
    df["price_volume_ratio"] = (
        df["price_volume"] / df["price_volume"].rolling(20).mean()
    )

for period in [5, 10, 20]:
    if f"momentum_{period}" not in df.columns:
        df[f"momentum_{period}"] = df["close"] / df["close"].shift(period) - 1

for period in [20, 50]:
    if f"mean_reversion_{period}" not in df.columns:
        df[f"mean_reversion_{period}"] = (
            df["close"] - df["close"].rolling(period).mean()
        ) / df["close"].rolling(period).std()

# Add Elliott Wave features
if "wave_count" not in df.columns:
    window = 20
    df["high_rolling_max"] = df["high"].rolling(window, center=True).max()
    df["low_rolling_min"] = df["low"].rolling(window, center=True).min()
    df["is_peak"] = (df["high"] == df["high_rolling_max"]).astype(int)
    df["is_trough"] = (df["low"] == df["low_rolling_min"]).astype(int)
    df["wave_count"] = (df["is_peak"] | df["is_trough"]).cumsum()
    df["wave_length"] = df.groupby("wave_count").cumcount()
    df.drop(["high_rolling_max", "low_rolling_min"], axis=1, inplace=True)

# Test on recent data
test_data = df["2023-01-01":"2024-06-30"]

print("DEBUG: Signal Generation Analysis")
print("=" * 60)
print(f"Model features required: {len(features)}")
print(f"Available features: {len([f for f in features if f in test_data.columns])}")

# Check missing features
missing = [f for f in features if f not in test_data.columns]
if missing:
    print(f"\nMissing features: {missing[:10]}...")

# Test predictions
print(f"\nTesting {len(test_data)} bars...")

signals_by_prediction = {0: 0, 1: 0, 2: 0}
confidence_levels = []
high_confidence_signals = []

for i in range(100, min(500, len(test_data))):
    try:
        # Get available features
        available_features = [f for f in features if f in test_data.columns]
        X = test_data[available_features].iloc[i : i + 1]

        if X.isnull().any().any():
            continue

        X_scaled = scaler.transform(X)
        prediction = model.predict(X_scaled)[0]

        signals_by_prediction[prediction] += 1

        if hasattr(model, "predict_proba"):
            proba = model.predict_proba(X_scaled)[0]
            confidence = max(proba)
            confidence_levels.append(confidence)

            # Track high confidence non-hold signals
            if confidence > 0.65 and prediction != 1:
                high_confidence_signals.append(
                    {
                        "time": test_data.index[i],
                        "prediction": prediction,
                        "confidence": confidence,
                        "proba": proba,
                    }
                )

    except Exception as e:
        continue

print(f"\nPrediction Distribution (first 400 bars):")
print(f"Sell (0): {signals_by_prediction[0]}")
print(f"Hold (1): {signals_by_prediction[1]}")
print(f"Buy (2): {signals_by_prediction[2]}")

if confidence_levels:
    print(f"\nConfidence Statistics:")
    print(f"Mean: {np.mean(confidence_levels):.3f}")
    print(f"Max: {max(confidence_levels):.3f}")
    print(f"Min: {min(confidence_levels):.3f}")
    print(f">0.65: {sum(c > 0.65 for c in confidence_levels)}")

print(f"\nHigh Confidence Non-Hold Signals: {len(high_confidence_signals)}")

if high_confidence_signals:
    print("\nSample High Confidence Signals:")
    for sig in high_confidence_signals[:5]:
        signal_type = "BUY" if sig["prediction"] == 2 else "SELL"
        print(f"  {sig['time']}: {signal_type}, conf={sig['confidence']:.3f}")

# Analyze model's feature importance
if hasattr(model, "feature_importances_"):
    importances = model.feature_importances_
    feature_importance = pd.DataFrame(
        {
            "feature": available_features,
            "importance": importances[: len(available_features)],
        }
    ).sort_values("importance", ascending=False)

    print(f"\nTop 5 Important Features:")
    for _, row in feature_importance.head(5).iterrows():
        print(f"  {row['feature']}: {row['importance']:.4f}")

print("\nRECOMMENDATION:")
print("The model is heavily biased towards HOLD (94.5% in training)")
print("This is because the conservative thresholds (0.3% avg return)")
print("resulted in very few BUY/SELL labels during training.")
print("\nSolutions:")
print("1. Retrain with lower thresholds (0.1-0.2%)")
print("2. Use the original model with enhanced exits")
print("3. Combine multiple models with different thresholds")
