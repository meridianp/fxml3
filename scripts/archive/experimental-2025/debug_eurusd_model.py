#!/usr/bin/env python
"""Debug EURUSD model to understand low signal generation."""

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))

import json

import joblib
import numpy as np
import pandas as pd

from scripts.create_optimized_4h_backtester import Optimized4HBacktester


def debug_eurusd_model():
    """Analyze EURUSD model predictions in detail."""

    # Load the model
    model_file = Path("models/h4_models/EURUSD_h4_models.joblib")
    if not model_file.exists():
        print("EURUSD model not found!")
        return

    model_data = joblib.load(model_file)

    # Check what's in the model data
    print("EURUSD Model Contents:")
    print("Keys:", model_data.keys())

    # Load feature data
    feature_file = Path("data/h4_processed/EURUSD_h4_features.parquet")
    df = pd.read_parquet(feature_file)

    # Get recent data
    recent_df = df.tail(1000)  # Last 1000 bars

    # Load features list
    feature_meta = Path("models/h4_models/EURUSD_h4_features.json")
    with open(feature_meta, "r") as f:
        meta = json.load(f)
    features = meta["features"]

    # Get the ensemble model
    ensemble_model = model_data["models"].get("ensemble")
    ensemble_scaler = model_data["scalers"].get("ensemble")

    if ensemble_model is None:
        print("No ensemble model found!")
        return

    # Make predictions
    X = recent_df[features].values

    if ensemble_scaler is not None:
        X_scaled = ensemble_scaler.transform(X)
    else:
        X_scaled = X

    # Get predictions based on model type
    model_type = type(ensemble_model).__name__
    print(f"\nModel type: {model_type}")

    if "Booster" in model_type:
        if "xgb" in str(type(ensemble_model)):
            import xgboost as xgb

            dmatrix = xgb.DMatrix(X_scaled, feature_names=features)
            predictions = ensemble_model.predict(dmatrix)
        else:  # LightGBM
            predictions = ensemble_model.predict(X_scaled)
    else:
        predictions = ensemble_model.predict(X_scaled)

    # Analyze predictions
    print(f"\nPrediction Analysis (last 1000 bars):")
    print(f"Mean prediction: {np.mean(predictions):.6f}")
    print(f"Std prediction: {np.std(predictions):.6f}")
    print(f"Min prediction: {np.min(predictions):.6f}")
    print(f"Max prediction: {np.max(predictions):.6f}")

    # Check signal generation with different thresholds
    thresholds = [0.00001, 0.00005, 0.0001, 0.0002]

    print("\nSignal Generation by Threshold:")
    for thresh in thresholds:
        buy_signals = (predictions > thresh).sum()
        sell_signals = (predictions < -thresh).sum()
        total_signals = buy_signals + sell_signals
        signal_rate = total_signals / len(predictions)

        print(f"\nThreshold: {thresh:.5f} ({thresh*10000:.1f} pips)")
        print(f"  Buy signals: {buy_signals} ({buy_signals/len(predictions):.1%})")
        print(f"  Sell signals: {sell_signals} ({sell_signals/len(predictions):.1%})")
        print(f"  Total signals: {total_signals} ({signal_rate:.1%})")
        print(f"  Signals per day: {signal_rate * 6:.1f}")

    # Compare with other symbols
    print("\n\nCOMPARING WITH OTHER SYMBOLS:")
    print("=" * 60)

    symbols = ["EURUSD", "GBPUSD", "USDJPY", "USDCHF"]

    for symbol in symbols:
        model_file = Path(f"models/h4_models/{symbol}_h4_models.joblib")
        if not model_file.exists():
            continue

        model_data = joblib.load(model_file)
        results = model_data.get("training_results", {})

        if "ensemble" in results:
            metrics = results["ensemble"]
            print(f"\n{symbol}:")
            print(
                f"  Direction accuracy: {metrics.get('test_direction_accuracy', 0):.1%}"
            )
            print(f"  Signal accuracy: {metrics.get('test_signal_accuracy', 0):.1%}")
            print(f"  Model type: {metrics.get('model_type', 'Unknown')}")

    # Check feature importance for EURUSD
    print("\n\nEURUSD TOP FEATURES:")
    print("=" * 60)

    # Get feature importance from the best individual model
    for model_name in ["random_forest", "xgboost", "lightgbm"]:
        if model_name in model_data["models"]:
            model = model_data["models"][model_name]

            if hasattr(model, "feature_importances_"):
                importances = model.feature_importances_

                # Create importance DataFrame
                importance_df = pd.DataFrame(
                    {"feature": features, "importance": importances}
                ).sort_values("importance", ascending=False)

                print(f"\n{model_name} top 10 features:")
                for _, row in importance_df.head(10).iterrows():
                    print(f"  {row['feature']:30s} {row['importance']:.4f}")

                break


if __name__ == "__main__":
    debug_eurusd_model()
