#!/usr/bin/env python3
"""
Quick GBP/USD Model Optimization Demo

This is a simplified version of optimize_gbpusd_model.py for demonstration purposes.
It reduces the parameter grid and data volume for faster execution.
"""

import logging
import os
import sys
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Add project root to path to import from fxml4
project_root = Path(__file__).resolve().parent.parent
sys.path.append(str(project_root))

# Import FXML4 modules
from fxml4.ml.features import (
    add_lagged_features,
    calculate_weekly_pivot_points,
    create_target_labels,
    create_technical_features,
    identify_trading_sessions,
    scale_features,
    select_features_random_forest,
)
from fxml4.ml.models import ClassicMLModel


class MLModelWrapper:
    """Wrapper class for ClassicMLModel that provides a scikit-learn compatible interface"""

    def __init__(self, model_type, n_classes, params):
        """Initialize with model params"""
        self.model_type = model_type
        self.n_classes = n_classes
        self.params = params
        self.model = None

    def fit(self, X, y):
        """Train the model"""
        # Create a new model with a unique name
        self.model = ClassicMLModel(
            model_type=self.model_type,
            name=f"gbpusd_{self.model_type}_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            n_classes=self.n_classes,
            model_params=self.params,
        )
        # Train the model
        self.model.train(X, y)
        return self

    def predict(self, X):
        """Make predictions"""
        return self.model.predict(X)

    def predict_proba(self, X):
        """Get prediction probabilities"""
        return self.model.predict_proba(X)


def load_sample_data(symbol="GBPUSD", year=2020, month=7, days=None):
    """
    Load a sample of GBPUSD data for testing.

    Args:
        symbol: Currency pair symbol
        year: Year to load data from
        month: Month to load data from
        days: List of days to load, if None loads all available days for the month

    Returns:
        DataFrame of OHLC data
    """
    data_frames = []

    try:
        base_path = f"input/C_{symbol}/year={year}/month={month}"

        # If days not specified, try to find all available days
        if days is None:
            import os

            if os.path.exists(base_path):
                days = [
                    int(d.replace("day=", ""))
                    for d in os.listdir(base_path)
                    if d.startswith("day=")
                ]
                days.sort()
            else:
                days = list(
                    range(1, 21)
                )  # Default to first 20 days if can't read directory

        # Try to load data for each day
        for day in days:
            try:
                path = f"{base_path}/day={day}/data.parquet"
                day_df = pd.read_parquet(path)
                data_frames.append(day_df)
                logger.info(f"Loaded data from {path}")
            except Exception as e:
                logger.warning(f"Couldn't load parquet data for {day}: {e}")

        # Combine all data frames
        if data_frames:
            df = pd.concat(data_frames)
            df = df.sort_index()

            # Remove duplicate timestamps
            if df.index.duplicated().any():
                logger.warning(
                    f"Found {df.index.duplicated().sum()} duplicate timestamps, keeping first occurrences"
                )
                df = df[~df.index.duplicated(keep="first")]

            logger.info(
                f"Successfully loaded {len(df)} rows from {len(data_frames)} days"
            )
            return df
    except Exception as e:
        logger.warning(f"Error loading data: {e}")

    # Create synthetic data if real data not available
    logger.info("Creating synthetic data for testing")
    n_samples = 5000
    np.random.seed(42)

    # Create datetime index starting from specified date
    start_date = pd.Timestamp(f"{year}-{month:02d}-01")
    index = pd.date_range(start=start_date, periods=n_samples, freq="1h")

    # Generate random price data with some trend and volatility
    close = 100 + np.cumsum(np.random.normal(0, 0.1, n_samples))
    high = close + np.random.normal(0, 0.5, n_samples).clip(0, None)
    low = close - np.random.normal(0, 0.5, n_samples).clip(0, None)
    open_prices = close.copy()
    np.random.shuffle(open_prices)

    # Create dataframe
    df = pd.DataFrame(
        {
            "open": open_prices,
            "high": high,
            "low": low,
            "close": close,
            "volume": np.random.randint(1000, 10000, n_samples),
        },
        index=index,
    )

    logger.info(f"Created synthetic data with {len(df)} rows")

    return df


def prepare_features(df):
    """Prepare features for model training"""
    # Drop columns we don't need
    if "otc" in df.columns:
        df = df.drop(columns=["otc"])

    if "transactions" in df.columns:
        df = df.drop(columns=["transactions"])

    # 1. Create technical features with pandas_ta
    logger.info("Creating technical features")
    df_features = create_technical_features(
        df,
        indicators=["sma", "ema", "rsi", "macd", "bollinger", "stoch"],
        add_enhanced_features=True,
    )

    # 2. Add pivot points (weekly)
    logger.info("Adding pivot points")
    df_features = calculate_weekly_pivot_points(df_features)

    # 3. Add trading session information
    logger.info("Adding trading session information")
    df_features = identify_trading_sessions(df_features)

    # 4. Add lagged features
    logger.info("Adding lagged features")
    df_features = add_lagged_features(df_features)

    # 5. Create target labels with volatility-adjusted method
    logger.info("Creating target labels")
    df_features = create_target_labels(
        df_features,
        method="volatility_adjusted",
        horizon=10,
        volatility_window=20,
        volatility_multiplier=1.0,
        trend_adjusted=True,
        trend_window=100,
    )

    # 6. Handle NaN values - first fill NaN values with more sophisticated method
    # Forward fill first, then backward fill any remaining NaNs at the start
    df_features = df_features.ffill().bfill()

    # For any remaining NaNs (especially in calculated columns), replace with column median
    for col in df_features.columns:
        if df_features[col].isna().any():
            median_val = df_features[col].median()
            if pd.isna(median_val):  # If median is also NaN (e.g., all values are NaN)
                df_features[col] = df_features[col].fillna(0)
            else:
                df_features[col] = df_features[col].fillna(median_val)

    # Drop any still problematic rows
    df_clean = df_features.dropna()
    logger.info(f"Final dataset shape after cleaning: {df_clean.shape}")

    return df_clean


def main():
    """Main function for quick optimization demo"""
    logger.info("Starting quick GBP/USD model optimization demo")

    # Create output directory for results
    output_dir = "ml_optimization/results"
    os.makedirs(output_dir, exist_ok=True)

    # Load data - use a small set of data (two weeks)
    df = load_sample_data(symbol="GBPUSD", year=2020, month=7, days=list(range(10, 25)))

    if df is None or len(df) == 0:
        logger.error("No data loaded, exiting")
        return

    # Prepare features
    df_features = prepare_features(df)

    # Define target and features
    target_col = "target_10"

    # Exclude non-feature columns (targets, future returns)
    exclude_cols = [
        c
        for c in df_features.columns
        if c.startswith("target_") or c.startswith("future_return_")
    ]
    feature_cols = [c for c in df_features.columns if c not in exclude_cols]

    logger.info(f"Total features: {len(feature_cols)}")
    logger.info(f"Target column: {target_col}")

    # Scale features
    df_scaled, scaler = scale_features(df_features, exclude_cols=exclude_cols)

    # Define a simple grid of parameters to try
    param_grid = {
        "n_estimators": [50, 100],
        "max_depth": [10, 20],
        "min_samples_split": [2, 5],
        "random_state": [42],
    }

    # Try each parameter combination
    best_metrics = {"f1": 0, "accuracy": 0, "profit_factor": 0}
    best_params = None
    best_model = None

    logger.info("Testing parameter combinations...")

    train_size = int(0.8 * len(df_scaled))
    X_train = df_scaled.iloc[:train_size][feature_cols]
    y_train = df_scaled.iloc[:train_size][target_col]
    X_test = df_scaled.iloc[train_size:][feature_cols]
    y_test = df_scaled.iloc[train_size:][target_col]
    future_returns = df_scaled.iloc[train_size:][f"future_return_{10}"]

    # Feature selection
    X_train_selected, selected_features = select_features_random_forest(
        X_train, y_train, k=20, plot=False
    )
    X_test_selected = X_test[selected_features]

    # Grid search
    for n_estimators in param_grid["n_estimators"]:
        for max_depth in param_grid["max_depth"]:
            for min_samples_split in param_grid["min_samples_split"]:
                # Create and train model
                model_params = {
                    "n_estimators": n_estimators,
                    "max_depth": max_depth,
                    "min_samples_split": min_samples_split,
                    "random_state": 42,
                }

                # Use the wrapper class
                wrapper = MLModelWrapper(
                    model_type="random_forest", n_classes=3, params=model_params
                )

                # Train using the fit method
                wrapper.fit(X_train_selected, y_train)

                # Get the underlying model for evaluation
                model = wrapper.model

                # Evaluate model
                metrics = model.evaluate(
                    X_test_selected, y_test, returns=future_returns, plot=False
                )

                logger.info(
                    f"Params: {model_params}, F1: {metrics['f1']:.4f}, Accuracy: {metrics['accuracy']:.4f}, Profit Factor: {metrics.get('profit_factor', 0):.4f}"
                )

                # Check if this is the best model so far
                # Prioritize profit factor (financial metric) if available
                if metrics.get("profit_factor", 0) > best_metrics["profit_factor"]:
                    best_metrics = metrics
                    best_params = model_params
                    best_model = model
                elif (
                    metrics["f1"] > best_metrics["f1"]
                    and best_metrics["profit_factor"] == 0
                ):
                    best_metrics = metrics
                    best_params = model_params
                    best_model = model

    # Print results for the best model
    print("\nBest Model:")
    print(f"Parameters: {best_params}")
    print(
        f"Metrics: Accuracy={best_metrics['accuracy']:.4f}, F1={best_metrics['f1']:.4f}, Profit Factor={best_metrics.get('profit_factor', 0):.4f}"
    )

    # Save the best model
    if best_model:
        saved_files = best_model.save(directory=output_dir)
        logger.info(f"Best model saved to: {saved_files['model']}")

    logger.info("Quick optimization completed")


if __name__ == "__main__":
    main()
