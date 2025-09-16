#!/usr/bin/env python3
"""
Train a simplified GBP/USD model with basic trading session features.

This script adds basic session information to the GBP/USD model
to improve prediction performance.
"""

import logging
import os
import sys
from datetime import datetime, time

import matplotlib.pyplot as plt
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


def add_session_features(df):
    """Add simple trading session features."""
    logger.info("Adding trading session features")

    # Make a copy of the dataframe
    result_df = df.copy()

    # Make sure index is datetime with timezone
    if not isinstance(result_df.index, pd.DatetimeIndex):
        raise ValueError("DataFrame must have a DatetimeIndex")

    # Force index to UTC if not already
    if result_df.index.tz is None:
        result_df.index = result_df.index.tz_localize("UTC")
    elif result_df.index.tz.zone != "UTC":
        result_df.index = result_df.index.tz_convert("UTC")

    # Extract hour of day
    result_df["hour"] = result_df.index.hour

    # Define trading sessions in UTC
    london_hours = range(8, 17)  # London: 8:00-17:00 UTC
    newyork_hours = range(13, 22)  # New York: 13:00-22:00 UTC
    tokyo_hours = list(range(0, 9))  # Tokyo: 0:00-9:00 UTC
    sydney_hours = list(range(21, 24)) + list(range(0, 6))  # Sydney: 21:00-6:00 UTC

    # Create session indicators
    result_df["is_london"] = result_df["hour"].isin(london_hours).astype(int)
    result_df["is_newyork"] = result_df["hour"].isin(newyork_hours).astype(int)
    result_df["is_tokyo"] = result_df["hour"].isin(tokyo_hours).astype(int)
    result_df["is_sydney"] = result_df["hour"].isin(sydney_hours).astype(int)

    # Create overlap indicators
    result_df["is_london_newyork"] = (
        result_df["is_london"] & result_df["is_newyork"]
    ).astype(int)
    result_df["is_tokyo_london"] = (
        result_df["is_tokyo"] & result_df["is_london"]
    ).astype(int)

    # Create high activity indicator (London or London-NY overlap)
    result_df["is_high_activity"] = (
        (result_df["is_london"] == 1) | (result_df["is_london_newyork"] == 1)
    ).astype(int)

    # Add day of week features (0 = Monday, 6 = Sunday)
    result_df["day_of_week"] = result_df.index.dayofweek

    # Create day of week one-hot encoding
    for day in range(7):
        result_df[f"day_{day}"] = (result_df["day_of_week"] == day).astype(int)

    # Add hour as cyclical features
    result_df["hour_sin"] = np.sin(2 * np.pi * result_df["hour"] / 24)
    result_df["hour_cos"] = np.cos(2 * np.pi * result_df["hour"] / 24)

    # Drop intermediate columns
    result_df.drop(["hour", "day_of_week"], axis=1, inplace=True)

    # Add volatility for sessions if price data available
    if "close" in result_df.columns:
        # Calculate returns
        result_df["returns"] = result_df["close"].pct_change()

        # Overall volatility
        result_df["volatility_20"] = result_df["returns"].rolling(window=20).std()

        # London session volatility
        london_returns = result_df["returns"].copy()
        london_returns[result_df["is_london"] == 0] = np.nan
        result_df["london_vol"] = london_returns.rolling(
            window=48, min_periods=12
        ).std()

        # New York session volatility
        newyork_returns = result_df["returns"].copy()
        newyork_returns[result_df["is_newyork"] == 0] = np.nan
        result_df["newyork_vol"] = newyork_returns.rolling(
            window=48, min_periods=12
        ).std()

        # London-NY overlap volatility
        overlap_returns = result_df["returns"].copy()
        overlap_returns[result_df["is_london_newyork"] == 0] = np.nan
        result_df["overlap_vol"] = overlap_returns.rolling(
            window=48, min_periods=6
        ).std()

        # Remove returns column
        result_df.drop("returns", axis=1, inplace=True)

    logger.info(f"Added {len(result_df.columns) - len(df.columns)} session features")
    return result_df


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

    # Add session features
    features = add_session_features(features)

    # Add lagged features
    lag_columns = [
        "close",
        "rsi_14",
        "bb_width",
        "atr_14",
        "volatility_14",
        "daily_return",
        "london_vol",
        "newyork_vol",
        "overlap_vol",
    ]

    # Only use columns that exist
    lag_columns = [col for col in lag_columns if col in features.columns]

    features = add_lagged_features(
        features, columns=lag_columns, lags=[1, 2, 3, 6, 12, 24], include_returns=True
    )

    # Boolean columns should not be lagged
    bool_columns = [
        "is_london",
        "is_newyork",
        "is_tokyo",
        "is_sydney",
        "is_london_newyork",
        "is_tokyo_london",
        "is_high_activity",
    ]

    for col in bool_columns:
        if col in features.columns:
            lag_columns.append(col)

    # Create target
    future_return = features["close"].shift(-target_horizon) / features["close"] - 1

    # Create target based on threshold
    target = np.zeros(len(features))
    target[future_return > target_threshold] = 1
    target[future_return < -target_threshold] = -1

    # Add target column
    features[f"target_{target_horizon}"] = target

    # Add future return column (for analysis)
    features[f"future_return_{target_horizon}"] = future_return

    # Drop rows with NaN values
    features = features.dropna()

    logger.info(f"Prepared {len(features)} rows with {len(features.columns)} features")

    return features


def train_model(features, target_col, test_size=0.2):
    """Train a Random Forest model."""
    logger.info("Training Random Forest model")

    # Split features and target
    X = features.drop(columns=[target_col, f'future_return_{target_col.split("_")[1]}'])
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

    logger.info("Top 20 features:")
    for _, row in importance_df.head(20).iterrows():
        logger.info(f"  {row['feature']}: {row['importance']:.4f}")

    # Save model
    import joblib

    os.makedirs("models", exist_ok=True)
    model_path = os.path.join("models", "gbpusd_rf_sessions.joblib")
    scaler_path = os.path.join("models", "gbpusd_rf_sessions_scaler.joblib")

    joblib.dump(model, model_path)
    joblib.dump(scaler, scaler_path)

    logger.info(f"Model saved to {model_path}")
    logger.info(f"Scaler saved to {scaler_path}")

    # Save top features
    importance_df.head(50).to_csv("models/session_feature_importance.csv", index=False)

    return model, scaler, importance_df


def analyze_session_influence(features, model, scaler, target_col):
    """Analyze how trading sessions influence model predictions."""
    logger.info("Analyzing session influence")

    # Get features and target
    X = features.drop(columns=[target_col, f'future_return_{target_col.split("_")[1]}'])
    y = features[target_col]

    # Scale features
    X_scaled = scaler.transform(X)
    X_scaled_df = pd.DataFrame(X_scaled, index=X.index, columns=X.columns)

    # Make predictions
    predictions = model.predict(X_scaled_df)

    # Create results dataframe
    results = pd.DataFrame(
        {
            "actual": y,
            "predicted": predictions,
            "future_return": features[f'future_return_{target_col.split("_")[1]}'],
        },
        index=features.index,
    )

    # Add session indicators
    session_columns = [
        "is_london",
        "is_newyork",
        "is_tokyo",
        "is_sydney",
        "is_london_newyork",
        "is_high_activity",
    ]

    for col in session_columns:
        if col in features.columns:
            results[col] = features[col]

    # Calculate session-specific accuracy
    session_performance = {}

    for session in session_columns:
        if session not in results.columns:
            continue

        # Get data for this session
        session_data = results[results[session] == 1]

        if len(session_data) == 0:
            continue

        # Calculate metrics
        metrics = {
            "samples": len(session_data),
            "accuracy": accuracy_score(
                session_data["actual"], session_data["predicted"]
            ),
            "precision": precision_score(
                session_data["actual"], session_data["predicted"], average="weighted"
            ),
            "f1": f1_score(
                session_data["actual"], session_data["predicted"], average="weighted"
            ),
            "mean_return": (
                session_data["predicted"] * session_data["future_return"]
            ).mean(),
            "win_rate": (
                (session_data["predicted"] * session_data["future_return"]) > 0
            ).mean(),
        }

        session_performance[session] = metrics

    # Create summary dataframe
    summary = pd.DataFrame(session_performance).T

    # Print session performance
    logger.info("Session performance summary:")
    logger.info(f"\n{summary}")

    # Create bar plot of metrics by session
    plt.figure(figsize=(14, 8))

    metrics = ["accuracy", "precision", "f1", "win_rate"]

    for i, metric in enumerate(metrics):
        plt.subplot(2, 2, i + 1)
        summary[metric].plot(kind="bar", color=plt.cm.tab10(i))
        plt.title(f"{metric.replace('_', ' ').title()} by Session")
        plt.ylabel(metric.replace("_", " ").title())
        plt.grid(True, alpha=0.3)
        plt.ylim(0, 1)

    plt.tight_layout()
    plt.savefig("models/session_influence.png")

    # Create a confusion matrix heatmap for each session
    plt.figure(figsize=(15, 10))

    for i, session in enumerate(session_columns):
        if session not in results.columns or i >= 6:  # Limit to 6 sessions
            continue

        # Get data for this session
        session_data = results[results[session] == 1]

        if len(session_data) == 0:
            continue

        # Calculate confusion matrix
        cm = confusion_matrix(session_data["actual"], session_data["predicted"])

        # Plot confusion matrix
        plt.subplot(2, 3, i + 1)
        plt.imshow(cm, interpolation="nearest", cmap=plt.cm.Blues)
        plt.title(f"Confusion Matrix: {session.replace('_', ' ').title()}")
        plt.colorbar()

        classes = [-1, 0, 1]
        tick_marks = np.arange(len(classes))
        plt.xticks(tick_marks, classes)
        plt.yticks(tick_marks, classes)

        # Add text annotations
        thresh = cm.max() / 2.0
        for i_cm, j_cm in np.ndindex(cm.shape):
            plt.text(
                j_cm,
                i_cm,
                format(cm[i_cm, j_cm], "d"),
                horizontalalignment="center",
                color="white" if cm[i_cm, j_cm] > thresh else "black",
            )

        plt.ylabel("True label")
        plt.xlabel("Predicted label")

    plt.tight_layout()
    plt.savefig("models/session_confusion_matrices.png")

    return summary


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
    target_col = "target_12"
    model, scaler, importance_df = train_model(features, target_col)

    # Analyze session influence
    session_analysis = analyze_session_influence(features, model, scaler, target_col)

    logger.info("Training with session features completed successfully")
    return 0


if __name__ == "__main__":
    sys.exit(main())
