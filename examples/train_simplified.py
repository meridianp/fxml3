#!/usr/bin/env python3
"""
Simplified script for training a GBP/USD model locally.

This script focuses on training a single Random Forest model
for GBP/USD prediction on the 4-hour timeframe.
"""

import logging
import os
import sys

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import (
    accuracy_score,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
)
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import MinMaxScaler

# Add parent directory to path
script_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(script_dir)
sys.path.append(parent_dir)

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Import feature engineering functions
from fxml4.ml.features import add_lagged_features, create_basic_technical_features


def prepare_features(data, target_horizon=12, target_threshold=0.001):
    """Prepare features for model training."""
    logger.info("Preparing features")

    # Create technical indicators
    features = create_basic_technical_features(
        data,
        indicators=["sma", "ema", "rsi", "bollinger", "atr"],
        ma_periods=[10, 20, 50, 200],
        include_original=True,
        fillna=True,
    )

    # Add lagged features
    lag_columns = [
        "close",
        "rsi_14",
        "bb_width",
        "atr_14",
        "volatility_14",
        "daily_return",
    ]

    # Only use columns that exist
    lag_columns = [col for col in lag_columns if col in features.columns]

    features = add_lagged_features(
        features, columns=lag_columns, lags=[1, 2, 3, 6, 12, 24], include_returns=True
    )

    # Create target
    future_return = features["close"].shift(-target_horizon) / features["close"] - 1

    # Create target based on threshold
    target = np.zeros(len(features))
    target[future_return > target_threshold] = 1
    target[future_return < -target_threshold] = -1

    # Add target column
    features[f"target_{target_horizon}"] = target

    # Drop rows with NaN values
    features = features.dropna()

    logger.info(f"Prepared {len(features)} rows with {len(features.columns)} features")

    return features


def train_model(features, target_col, test_size=0.2):
    """Train a Random Forest model."""
    logger.info("Training Random Forest model")

    # Split features and target
    X = features.drop(columns=[target_col])
    y = features[target_col]

    # Scale features
    scaler = MinMaxScaler()
    X_scaled = scaler.fit_transform(X)
    X_scaled_df = pd.DataFrame(X_scaled, index=X.index, columns=X.columns)

    # Split into train and test sets
    X_train, X_test, y_train, y_test = train_test_split(
        X_scaled_df, y, test_size=test_size, shuffle=False
    )

    # Create and train model
    model = RandomForestClassifier(
        n_estimators=200,
        max_depth=15,
        min_samples_split=5,
        min_samples_leaf=2,
        class_weight="balanced",
        random_state=42,
    )

    logger.info(f"Training on {len(X_train)} samples")
    logger.info(f"Class distribution: {pd.Series(y_train).value_counts().to_dict()}")

    model.fit(X_train, y_train)

    # Evaluate on test set
    y_pred = model.predict(X_test)

    # Calculate metrics
    accuracy = accuracy_score(y_test, y_pred)
    precision = precision_score(y_test, y_pred, average="weighted")
    recall = recall_score(y_test, y_pred, average="weighted")
    f1 = f1_score(y_test, y_pred, average="weighted")
    conf_matrix = confusion_matrix(y_test, y_pred)

    logger.info(f"Test set metrics:")
    logger.info(f"  Accuracy: {accuracy:.4f}")
    logger.info(f"  Precision: {precision:.4f}")
    logger.info(f"  Recall: {recall:.4f}")
    logger.info(f"  F1 Score: {f1:.4f}")
    logger.info(f"  Confusion Matrix:\n{conf_matrix}")

    # Calculate feature importance
    feature_importance = model.feature_importances_
    feature_names = X.columns

    # Get top features
    importance_df = pd.DataFrame(
        {"feature": feature_names, "importance": feature_importance}
    ).sort_values("importance", ascending=False)

    logger.info("Top 10 features:")
    for _, row in importance_df.head(10).iterrows():
        logger.info(f"  {row['feature']}: {row['importance']:.4f}")

    # Save model
    import joblib

    os.makedirs("models", exist_ok=True)
    model_path = os.path.join("models", "gbpusd_rf_simple.joblib")
    scaler_path = os.path.join("models", "gbpusd_rf_simple_scaler.joblib")

    joblib.dump(model, model_path)
    joblib.dump(scaler, scaler_path)

    logger.info(f"Model saved to {model_path}")
    logger.info(f"Scaler saved to {scaler_path}")

    # Save top features
    importance_df.head(20).to_csv("models/top_features.csv", index=False)

    return model, scaler, importance_df


def generate_signals(model, scaler, data, threshold=0.65):
    """Generate trading signals for recent data."""
    logger.info("Generating trading signals")

    # Use the entire dataset for feature preparation, then take the last 30 points
    # This ensures we have enough data for lagged features
    features = prepare_features(data, target_horizon=12)

    # Take the last 30 rows for signal generation
    recent_features = features.tail(30)

    if len(recent_features) == 0:
        logger.warning("No valid recent data available for signal generation")
        return []

    # Remove target column if exists
    target_col = "target_12"
    if target_col in recent_features.columns:
        recent_features = recent_features.drop(columns=[target_col])

    # Scale features
    X_scaled = scaler.transform(recent_features)

    # Make predictions
    predictions = model.predict(X_scaled)

    # Get probabilities for confidence
    probabilities = model.predict_proba(X_scaled)

    # Generate signals
    signals = []
    for i, (idx, row) in enumerate(recent_features.iterrows()):
        pred = predictions[i]

        if pred != 0:  # If not neutral
            # Get prediction probability
            pred_idx = int(pred + 1) if pred == -1 else int(pred)
            confidence = probabilities[i][pred_idx]

            if confidence >= threshold:
                signal_type = "BUY" if pred == 1 else "SELL"
                signals.append(
                    {
                        "timestamp": idx,
                        "type": signal_type,
                        "confidence": confidence,
                        "price": row["close"],
                    }
                )

    logger.info(f"Generated {len(signals)} signals")

    for signal in signals:
        logger.info(
            f"  {signal['timestamp']}: {signal['type']} with {signal['confidence']:.4f} confidence at {signal['price']}"
        )

    return signals


def main():
    """Main function."""
    # Load data
    data_path = "output/C_GBPUSD_4h.parquet"

    if not os.path.exists(data_path):
        logger.error(f"Data file not found: {data_path}")
        return 1

    data = pd.read_parquet(data_path)
    logger.info(f"Loaded {len(data)} rows of data")

    # Prepare features
    features = prepare_features(data, target_horizon=12)

    # Train model
    model, scaler, importance_df = train_model(features, "target_12")

    # Generate signals
    signals = generate_signals(model, scaler, data)

    logger.info("Testing completed successfully")
    return 0


if __name__ == "__main__":
    sys.exit(main())
