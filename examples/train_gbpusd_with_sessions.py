#!/usr/bin/env python3
"""
Train a GBP/USD model with trading session features.

This script enhances the GBP/USD ML model by incorporating:
1. Trading session identification (London, New York, Tokyo, Sydney)
2. Session distance calculations
3. Session overlap detection
4. Session-specific volatility
5. Session momentum indicators

These features are especially important for the GBP/USD pair since it's
most active during the London and New York sessions and their overlap.
"""

import logging
import os
import sys
from datetime import datetime, time

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import pytz
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

# ============ Trading Session Definitions ============


class TradingSession:
    """Definition of trading session with open/close times in UTC."""

    def __init__(
        self, name: str, open_time: time, close_time: time, timezone: str = "UTC"
    ):
        self.name = name
        self.open_time = open_time
        self.close_time = close_time
        self.timezone = timezone

    def __repr__(self) -> str:
        return f"TradingSession({self.name}, {self.open_time} - {self.close_time} {self.timezone})"


# Standard session definitions (UTC times)
TRADING_SESSIONS = {
    "Sydney": TradingSession(
        "Sydney", time(21, 0), time(6, 0), "UTC"
    ),  # 21:00-06:00 UTC
    "Tokyo": TradingSession("Tokyo", time(0, 0), time(9, 0), "UTC"),  # 00:00-09:00 UTC
    "London": TradingSession(
        "London", time(8, 0), time(17, 0), "UTC"
    ),  # 08:00-17:00 UTC
    "New York": TradingSession(
        "New York", time(13, 0), time(22, 0), "UTC"
    ),  # 13:00-22:00 UTC
}

# Session overlaps
SESSION_OVERLAPS = {
    "Tokyo-London": ("Tokyo", "London"),  # 08:00-09:00 UTC
    "London-NY": ("London", "New York"),  # 13:00-17:00 UTC
    "NY-Sydney": ("New York", "Sydney"),  # 21:00-22:00 UTC
}


# ============ Session Time Functions ============


def is_in_session(dt: pd.Timestamp, session_name: str) -> bool:
    """Check if a timestamp is within a specific trading session."""
    if session_name not in TRADING_SESSIONS:
        raise KeyError(f"Unknown session: {session_name}")

    session = TRADING_SESSIONS[session_name]

    # Ensure timestamp is in UTC
    if dt.tzinfo is None:
        dt = dt.tz_localize("UTC")
    elif dt.tzinfo != pytz.UTC:
        dt = dt.tz_convert("UTC")

    # Handle sessions that cross midnight
    if session.open_time < session.close_time:
        return session.open_time <= dt.time() < session.close_time
    else:
        return dt.time() >= session.open_time or dt.time() < session.close_time


def is_in_session_overlap(dt: pd.Timestamp, overlap_name: str) -> bool:
    """Check if a timestamp is within a session overlap period."""
    if overlap_name not in SESSION_OVERLAPS:
        raise KeyError(f"Unknown overlap: {overlap_name}")

    session1_name, session2_name = SESSION_OVERLAPS[overlap_name]
    return is_in_session(dt, session1_name) and is_in_session(dt, session2_name)


def session_time_distance(
    dt: pd.Timestamp, session_name: str, reference: str = "both"
) -> float:
    """
    Calculate the distance from a timestamp to session open, close, or both.

    Args:
        dt: Timestamp to measure from
        session_name: Name of the session
        reference: Which reference point to use ("open", "close", or "both")
                 "both" returns the minimum of distances to open and close

    Returns:
        Distance in hours (float) to the specified reference point
    """
    if reference not in ["open", "close", "both"]:
        raise ValueError("Reference must be 'open', 'close', or 'both'")

    if session_name not in TRADING_SESSIONS:
        raise KeyError(f"Unknown session: {session_name}")

    session = TRADING_SESSIONS[session_name]

    # Ensure timestamp is in UTC
    if dt.tzinfo is None:
        dt = dt.tz_localize("UTC")
    elif dt.tzinfo != pytz.UTC:
        dt = dt.tz_convert("UTC")

    dt_time = dt.time()
    dt_date = dt.date()

    # Calculate hours between two times, handling midnight crossing
    def hours_between(t1, t2, cross_midnight=False):
        dt1 = datetime.combine(dt_date, t1)
        dt2 = datetime.combine(dt_date, t2)

        if cross_midnight and dt2 < dt1:
            dt2 = datetime.combine(dt_date + pd.Timedelta(days=1), t2)

        return (dt2 - dt1).total_seconds() / 3600

    # Calculate open distance
    if reference in ["open", "both"]:
        if session.open_time < session.close_time:  # Simple case
            if dt_time >= session.open_time:
                open_distance = hours_between(session.open_time, dt_time)
            else:
                open_distance = -hours_between(dt_time, session.open_time)
        else:  # Session crosses midnight
            if (
                dt_time >= session.open_time or dt_time < session.close_time
            ):  # In session
                if dt_time >= session.open_time:
                    open_distance = hours_between(session.open_time, dt_time)
                else:
                    # Calculate distance with day boundary in between
                    midnight = time(0, 0, 0)
                    day_end = time(23, 59, 59)
                    open_distance = (
                        hours_between(session.open_time, day_end)
                        + hours_between(midnight, dt_time)
                        + 1 / 3600
                    )
            else:  # Outside session
                if dt_time < session.open_time:
                    open_distance = -hours_between(dt_time, session.open_time)
                else:
                    # Calculate distance with day boundary in between
                    midnight = time(0, 0, 0)
                    day_end = time(23, 59, 59)
                    open_distance = -(
                        hours_between(dt_time, day_end)
                        + hours_between(midnight, session.open_time)
                        + 1 / 3600
                    )

    # Calculate close distance
    if reference in ["close", "both"]:
        if session.open_time < session.close_time:  # Simple case
            if dt_time < session.close_time:
                close_distance = -hours_between(dt_time, session.close_time)
            else:
                close_distance = hours_between(session.close_time, dt_time)
        else:  # Session crosses midnight
            if (
                dt_time >= session.open_time or dt_time < session.close_time
            ):  # In session
                if dt_time < session.close_time:
                    close_distance = -hours_between(dt_time, session.close_time)
                else:
                    # Calculate distance with day boundary in between
                    midnight = time(0, 0, 0)
                    day_end = time(23, 59, 59)
                    close_distance = -(
                        hours_between(dt_time, day_end)
                        + hours_between(midnight, session.close_time)
                        + 1 / 3600
                    )
            else:  # Outside session
                if dt_time < session.close_time:
                    close_distance = -hours_between(dt_time, session.close_time)
                else:
                    close_distance = hours_between(session.close_time, dt_time)

    # Return appropriate distance
    if reference == "open":
        return open_distance
    elif reference == "close":
        return close_distance
    else:  # both
        return (
            open_distance
            if abs(open_distance) < abs(close_distance)
            else close_distance
        )


# ============ Session Feature Engineering ============


def add_session_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Add trading session features to a DataFrame.

    Args:
        df: DataFrame with a DatetimeIndex in UTC (or convertible to UTC)

    Returns:
        DataFrame with additional session features
    """
    logger.info("Adding trading session features")

    # Ensure DataFrame index is datetime
    if not isinstance(df.index, pd.DatetimeIndex):
        raise ValueError("DataFrame index must be a DatetimeIndex")

    # Force UTC timezone if not set
    if df.index.tz is None:
        df.index = df.index.tz_localize("UTC")
    elif df.index.tz != pytz.UTC:
        df.index = df.index.tz_convert("UTC")

    # Add session indicator columns
    result_df = df.copy()
    for session_name in TRADING_SESSIONS:
        col_name = f"is_{session_name.lower()}_session"
        result_df[col_name] = result_df.index.map(
            lambda x: is_in_session(x, session_name)
        )

        dist_col_name = f"{session_name.lower()}_distance"
        result_df[dist_col_name] = result_df.index.map(
            lambda x: session_time_distance(x, session_name, "both")
        )

    # Add overlap indicator columns
    for overlap_name in SESSION_OVERLAPS:
        col_name = f"is_{overlap_name.lower()}_overlap"
        result_df[col_name] = result_df.index.map(
            lambda x: is_in_session_overlap(x, overlap_name)
        )

    # Add high-activity flag (London or London-NY overlap)
    result_df["is_high_activity"] = (
        result_df["is_london_session"] | result_df["is_london-ny_overlap"]
    )

    # Add session volatility
    if "close" in result_df.columns:
        result_df["returns"] = result_df["close"].pct_change()

        # Standard volatility
        result_df["volatility_20"] = result_df["returns"].rolling(window=20).std()

        # Session-specific volatility for key sessions
        for session_name in ["London", "New York"]:
            session_lower = session_name.lower().replace(" ", "_")
            session_col = f"is_{session_lower}_session"
            vol_col = f"{session_lower}_volatility"

            # Create masked returns with non-session times as NaN
            session_returns = result_df["returns"].copy()
            session_returns[~result_df[session_col]] = np.nan

            # Calculate rolling standard deviation
            result_df[vol_col] = session_returns.rolling(
                window=48, min_periods=12
            ).std()

        # Overlap volatility (London-NY is most important for GBP/USD)
        overlap_col = "is_london-ny_overlap"
        if overlap_col in result_df.columns:
            overlap_returns = result_df["returns"].copy()
            overlap_returns[~result_df[overlap_col]] = np.nan
            result_df["london-ny_volatility"] = overlap_returns.rolling(
                window=48, min_periods=6
            ).std()

        # Remove the temporary returns column
        result_df.drop("returns", axis=1, inplace=True)

    # Add time-based cyclical features
    result_df["hour_sin"] = np.sin(2 * np.pi * result_df.index.hour / 24)
    result_df["hour_cos"] = np.cos(2 * np.pi * result_df.index.hour / 24)

    # Day of week (1=Monday, 7=Sunday)
    result_df["day_of_week"] = result_df.index.day_of_week + 1

    # Create dummy variables for day of week
    for day in range(1, 8):
        result_df[f"day_{day}"] = (result_df["day_of_week"] == day).astype(int)

    # Drop the original day_of_week column
    result_df.drop("day_of_week", axis=1, inplace=True)

    logger.info(f"Added {len(result_df.columns) - len(df.columns)} session features")
    return result_df


def prepare_features(data, target_horizon=12, target_threshold=0.001):
    """Prepare features for model training, including session features."""
    logger.info("Preparing technical features")

    # Create technical indicators
    features = create_basic_technical_features(
        data,
        indicators=["sma", "ema", "rsi", "bollinger", "atr"],
        ma_periods=[10, 20, 50, 200],
        include_original=True,
        fillna=True,
    )

    # Add session features
    logger.info("Adding session features")
    features = add_session_features(features)

    # Add lagged features
    logger.info("Adding lagged features")
    lag_columns = [
        "close",
        "rsi_14",
        "bb_width",
        "atr_14",
        "volatility_14",
        "daily_return",
    ]

    # Add session-specific columns if they exist
    session_cols = [
        "london_volatility",
        "new_york_volatility",
        "london-ny_volatility",
        "london_distance",
        "new_york_distance",
    ]

    for col in session_cols:
        if col in features.columns:
            lag_columns.append(col)

    # Only use columns that exist
    lag_columns = [col for col in lag_columns if col in features.columns]

    features = add_lagged_features(
        features, columns=lag_columns, lags=[1, 2, 3, 6, 12, 24], include_returns=True
    )

    # Create target
    logger.info("Creating target labels")
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
    model_path = os.path.join("models", "gbpusd_rf_with_sessions.joblib")
    scaler_path = os.path.join("models", "gbpusd_rf_with_sessions_scaler.joblib")

    joblib.dump(model, model_path)
    joblib.dump(scaler, scaler_path)

    logger.info(f"Model saved to {model_path}")
    logger.info(f"Scaler saved to {scaler_path}")

    # Save top features
    importance_df.head(50).to_csv("models/session_features_importance.csv", index=False)

    # Save feature list for reference
    with open("models/feature_list.txt", "w") as f:
        for feature in X.columns:
            f.write(f"{feature}\n")

    return model, scaler, importance_df


def analyze_session_performance(features, model, scaler, target_col):
    """Analyze model performance by trading session."""
    logger.info("Analyzing performance by trading session")

    # Get feature columns
    X = features.drop(columns=[target_col, f'future_return_{target_col.split("_")[1]}'])
    y = features[target_col]

    # Scale features
    X_scaled = scaler.transform(X)
    X_scaled_df = pd.DataFrame(X_scaled, index=X.index, columns=X.columns)

    # Make predictions
    predictions = model.predict(X_scaled_df)
    probabilities = model.predict_proba(X_scaled_df)

    # Create results DataFrame
    results = pd.DataFrame(
        {
            "actual": y,
            "predicted": predictions,
            "future_return": features[f'future_return_{target_col.split("_")[1]}'],
        },
        index=features.index,
    )

    # Add probability columns
    for i in range(len(probabilities[0])):
        results[f"prob_{i-1 if i == 0 else (0 if i == 1 else 1)}"] = [
            p[i] for p in probabilities
        ]

    # Add signal return column
    results["signal_return"] = results["predicted"] * results["future_return"]

    # Add session columns
    for session in TRADING_SESSIONS:
        session_name = session.lower()
        results[f"is_{session_name}_session"] = features[f"is_{session_name}_session"]

    # Add overlap columns
    for overlap in SESSION_OVERLAPS:
        overlap_name = overlap.lower()
        results[f"is_{overlap_name}_overlap"] = features[f"is_{overlap_name}_overlap"]

    # Analyze performance by session
    session_performance = {}

    for session in list(TRADING_SESSIONS.keys()) + list(SESSION_OVERLAPS.keys()):
        session_name = session.lower()
        column = (
            f"is_{session_name}_session"
            if session in TRADING_SESSIONS
            else f"is_{session_name}_overlap"
        )

        if column not in results.columns:
            continue

        session_data = results[results[column]]

        if len(session_data) == 0:
            continue

        # Calculate metrics
        metrics = {
            "accuracy": accuracy_score(
                session_data["actual"], session_data["predicted"]
            ),
            "precision": precision_score(
                session_data["actual"], session_data["predicted"], average="weighted"
            ),
            "recall": recall_score(
                session_data["actual"], session_data["predicted"], average="weighted"
            ),
            "f1": f1_score(
                session_data["actual"], session_data["predicted"], average="weighted"
            ),
            "samples": len(session_data),
            "mean_return": session_data["signal_return"].mean(),
            "win_rate": (session_data["signal_return"] > 0).mean(),
            "loss_rate": (session_data["signal_return"] < 0).mean(),
        }

        session_performance[session_name] = metrics

    # Create summary DataFrame
    summary = pd.DataFrame(session_performance).T

    # Sort by F1 score
    summary = summary.sort_values("f1", ascending=False)

    logger.info("Session performance summary:")
    logger.info(f"\n{summary}")

    # Save session performance data
    summary.to_csv("models/session_performance.csv")

    # Create performance chart
    plt.figure(figsize=(12, 8))

    # Plot F1 score by session
    plt.subplot(2, 2, 1)
    summary["f1"].plot(kind="bar", color="skyblue")
    plt.title("F1 Score by Session")
    plt.ylabel("F1 Score")
    plt.grid(True, alpha=0.3)

    # Plot accuracy by session
    plt.subplot(2, 2, 2)
    summary["accuracy"].plot(kind="bar", color="lightgreen")
    plt.title("Accuracy by Session")
    plt.ylabel("Accuracy")
    plt.grid(True, alpha=0.3)

    # Plot mean return by session
    plt.subplot(2, 2, 3)
    summary["mean_return"].plot(kind="bar", color="salmon")
    plt.title("Mean Return by Session")
    plt.ylabel("Mean Return")
    plt.grid(True, alpha=0.3)

    # Plot win rate by session
    plt.subplot(2, 2, 4)
    summary["win_rate"].plot(kind="bar", color="gold")
    plt.title("Win Rate by Session")
    plt.ylabel("Win Rate")
    plt.grid(True, alpha=0.3)

    plt.tight_layout()
    plt.savefig("models/session_performance.png")

    logger.info(
        "Session performance analysis saved to models/session_performance.csv and models/session_performance.png"
    )

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

    # Analyze session performance
    session_performance = analyze_session_performance(
        features, model, scaler, target_col
    )

    logger.info("Training with session features completed successfully")
    return 0


if __name__ == "__main__":
    sys.exit(main())
