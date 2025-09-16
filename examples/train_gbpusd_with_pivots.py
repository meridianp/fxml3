"""Example script for training a GBP/USD model with pivot point analysis.

This script demonstrates how to train a model for GBP/USD pair
that incorporates weekly pivot point analysis from FXML2.

Usage:
    python train_gbpusd_with_pivots.py
"""

import logging
import os

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.metrics import classification_report, confusion_matrix

from fxml4.ml.features import (
    calculate_session_pivot_levels,
    calculate_weekly_pivot_points,
)
from fxml4.ml.gbpusd_model import GBPUSDModel

# Set up logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Directory paths
DATA_DIR = "input/C_GBPUSD"
OUTPUT_DIR = "output"
MODEL_DIR = "models"


def load_sample_data():
    """Load sample data for GBP/USD.

    Returns:
        DataFrame with OHLC price data
    """
    logger.info("Loading sample data")

    # Check if data directory exists
    if not os.path.exists(DATA_DIR):
        logger.error(f"Data directory {DATA_DIR} not found")
        raise FileNotFoundError(f"Data directory {DATA_DIR} not found")

    # Get a list of all CSV or parquet files in the directory
    files = []
    for year_dir in os.listdir(DATA_DIR):
        year_path = os.path.join(DATA_DIR, year_dir)
        if os.path.isdir(year_path) and year_dir.startswith("year="):
            for month_dir in os.listdir(year_path):
                month_path = os.path.join(year_path, month_dir)
                if os.path.isdir(month_path) and month_dir.startswith("month="):
                    for file in os.listdir(month_path):
                        if file.endswith(".csv") or file.endswith(".parquet"):
                            files.append(os.path.join(month_path, file))

    # Load and concatenate files
    dataframes = []
    for file in files[-20:]:  # Use the most recent 20 files for this example
        try:
            if file.endswith(".csv"):
                df = pd.read_csv(file, index_col=0, parse_dates=True)
            elif file.endswith(".parquet"):
                df = pd.read_parquet(file)

            # Ensure lowercase column names
            df.columns = [col.lower() for col in df.columns]

            dataframes.append(df)
        except Exception as e:
            logger.warning(f"Error loading file {file}: {e}")

    if not dataframes:
        logger.error("No data files could be loaded")
        raise ValueError("No data files could be loaded")

    # Concatenate data
    combined_df = pd.concat(dataframes, sort=True)
    combined_df = combined_df.sort_index()

    # Ensure required columns
    required_cols = ["open", "high", "low", "close"]
    missing_cols = [col for col in required_cols if col not in combined_df.columns]
    if missing_cols:
        logger.error(f"Missing required columns: {missing_cols}")
        raise ValueError(f"Missing required columns: {missing_cols}")

    # Resample to 4h timeframe
    combined_df = (
        combined_df.resample("4H")
        .agg({"open": "first", "high": "max", "low": "min", "close": "last"})
        .dropna()
    )

    logger.info(f"Loaded {len(combined_df)} samples from {len(files)} files")

    return combined_df


def visualize_pivot_points(data, start_date=None, end_date=None):
    """Visualize price data with pivot points.

    Args:
        data: DataFrame with price data and pivot points
        start_date: Start date for visualization (optional)
        end_date: End date for visualization (optional)
    """
    logger.info("Visualizing pivot points")

    # Filter by date range if provided
    if start_date:
        data = data[data.index >= start_date]
    if end_date:
        data = data[data.index <= end_date]

    # Create visualization
    plt.figure(figsize=(15, 8))

    # Plot price data
    plt.plot(data.index, data["close"], label="Close Price", color="black")

    # Plot pivot points
    if "PP" in data.columns:
        plt.plot(
            data.index, data["PP"], label="Pivot Point", color="blue", linestyle="-"
        )

    # Plot resistance levels
    if "R1" in data.columns:
        plt.plot(data.index, data["R1"], label="R1", color="red", linestyle="--")
    if "R2" in data.columns:
        plt.plot(data.index, data["R2"], label="R2", color="darkred", linestyle="--")

    # Plot support levels
    if "S1" in data.columns:
        plt.plot(data.index, data["S1"], label="S1", color="green", linestyle="--")
    if "S2" in data.columns:
        plt.plot(data.index, data["S2"], label="S2", color="darkgreen", linestyle="--")

    # Add labels and title
    plt.title("GBP/USD with Weekly Pivot Points")
    plt.xlabel("Date")
    plt.ylabel("Price")
    plt.legend()
    plt.grid(True)

    # Save and show
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    plt.savefig(os.path.join(OUTPUT_DIR, "gbpusd_pivot_points.png"))
    logger.info(
        f"Visualization saved to {os.path.join(OUTPUT_DIR, 'gbpusd_pivot_points.png')}"
    )

    # Close plot to free memory
    plt.close()


def evaluate_model_with_pivots(model, X_test, y_test):
    """Evaluate model performance and analyze pivot-based features.

    Args:
        model: Trained model
        X_test: Test features
        y_test: Test targets
    """
    logger.info("Evaluating model with pivot point features")

    # Make predictions
    y_pred = model.predict(X_test)

    # Calculate basic metrics
    accuracy = np.mean(y_pred == y_test)

    # Generate confusion matrix
    cm = confusion_matrix(y_test, y_pred)

    # Generate classification report
    report = classification_report(y_test, y_pred, output_dict=True)

    # Calculate pivot-specific metrics
    pivot_features = [
        col
        for col in X_test.columns
        if "PP" in col or "R1" in col or "S1" in col or "R2" in col or "S2" in col
    ]

    # Get feature importance
    importance_df = model.get_top_features(20)

    # Check if any pivot features are in top features
    pivot_importance = importance_df[importance_df["feature"].isin(pivot_features)]

    logger.info(f"Model accuracy: {accuracy:.4f}")
    logger.info(f"Confusion matrix:\n{cm}")
    logger.info(f"Classification report:\n{pd.DataFrame(report).T}")

    if not pivot_importance.empty:
        logger.info("Pivot features in top importance:")
        for _, row in pivot_importance.iterrows():
            logger.info(f"  {row['feature']}: {row['importance']:.6f}")
    else:
        logger.info("No pivot features found in top importance")

    return {
        "accuracy": accuracy,
        "confusion_matrix": cm,
        "report": report,
        "pivot_importance": pivot_importance,
    }


def main():
    """Main function to train and evaluate a GBP/USD model with pivot points."""
    logger.info("Starting GBP/USD model training with pivot point analysis")

    # Create output directories
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    os.makedirs(MODEL_DIR, exist_ok=True)

    # Load data
    try:
        data = load_sample_data()
    except Exception as e:
        logger.error(f"Error loading data: {e}")
        # Generate synthetic data for demonstration if loading fails
        logger.info("Using synthetic data for demonstration")

        dates = pd.date_range(start="2023-01-01", periods=1000, freq="4H")
        data = pd.DataFrame(
            {
                "open": np.random.normal(1.25, 0.02, 1000),
                "high": np.random.normal(1.26, 0.02, 1000),
                "low": np.random.normal(1.24, 0.02, 1000),
                "close": np.random.normal(1.25, 0.02, 1000),
            },
            index=dates,
        )

        # Ensure high is the highest, low is the lowest
        for i in range(len(data)):
            values = [data.iloc[i]["open"], data.iloc[i]["close"]]
            data.iloc[i, data.columns.get_loc("high")] = max(values) + abs(
                np.random.normal(0, 0.002)
            )
            data.iloc[i, data.columns.get_loc("low")] = min(values) - abs(
                np.random.normal(0, 0.002)
            )

    # Add pivot points
    data_with_pivots = calculate_weekly_pivot_points(data)
    data_with_pivots = calculate_session_pivot_levels(data_with_pivots)

    # Visualize pivot points
    visualize_pivot_points(
        data_with_pivots,
        start_date=data_with_pivots.index[-100],
        end_date=data_with_pivots.index[-1],
    )

    # Create and train model
    model = GBPUSDModel(
        model_type="random_forest",
        model_params={"n_estimators": 100, "max_depth": 10, "min_samples_split": 5},
        name=f'gbpusd_with_pivots_{pd.Timestamp.now().strftime("%Y%m%d_%H%M%S")}',
        n_classes=3,
    )

    # Prepare features with pivot points
    features_with_pivots = model.prepare_features(
        data_with_pivots,
        target_horizon=12,  # 48 hours ahead for 4h timeframe
        target_threshold=0.0025,  # 0.25% threshold
        add_lag_features=True,
        add_pivot_points=True,
        create_target=True,
    )

    # Prepare features without pivot points for comparison
    model_no_pivots = GBPUSDModel(
        model_type="random_forest",
        model_params={"n_estimators": 100, "max_depth": 10, "min_samples_split": 5},
        name=f'gbpusd_without_pivots_{pd.Timestamp.now().strftime("%Y%m%d_%H%M%S")}',
        n_classes=3,
    )

    features_no_pivots = model_no_pivots.prepare_features(
        data,
        target_horizon=12,
        target_threshold=0.0025,
        add_lag_features=True,
        add_pivot_points=False,
        create_target=True,
    )

    logger.info(f"Prepared {len(features_with_pivots)} samples with pivots")
    logger.info(f"Prepared {len(features_no_pivots)} samples without pivots")

    # Split data for model training
    train_size = int(len(features_with_pivots) * 0.7)
    val_size = int(len(features_with_pivots) * 0.15)

    # Training with pivot features
    target_col = "target_12"
    train_with_pivots = features_with_pivots.iloc[:train_size]
    val_with_pivots = features_with_pivots.iloc[train_size : train_size + val_size]
    test_with_pivots = features_with_pivots.iloc[train_size + val_size :]

    X_train = train_with_pivots.drop(columns=[target_col])
    y_train = train_with_pivots[target_col]
    X_val = val_with_pivots.drop(columns=[target_col])
    y_val = val_with_pivots[target_col]
    X_test = test_with_pivots.drop(columns=[target_col])
    y_test = test_with_pivots[target_col]

    # Train model with pivots
    logger.info("Training model with pivot features")
    results_with_pivots = model.train(
        train_with_pivots,
        target_col=target_col,
        test_size=0.15,
        use_cv=True,
        n_splits=5,
    )

    # Training without pivot features
    train_no_pivots = features_no_pivots.iloc[:train_size]
    val_no_pivots = features_no_pivots.iloc[train_size : train_size + val_size]
    test_no_pivots = features_no_pivots.iloc[train_size + val_size :]

    X_train_no_pivots = train_no_pivots.drop(columns=[target_col])
    y_train_no_pivots = train_no_pivots[target_col]
    X_test_no_pivots = test_no_pivots.drop(columns=[target_col])
    y_test_no_pivots = test_no_pivots[target_col]

    # Train model without pivots
    logger.info("Training model without pivot features")
    results_no_pivots = model_no_pivots.train(
        train_no_pivots, target_col=target_col, test_size=0.15, use_cv=True, n_splits=5
    )

    # Evaluate both models
    logger.info("Evaluating models")
    eval_with_pivots = evaluate_model_with_pivots(model, X_test, y_test)

    # Compare results
    logger.info("=== Model Comparison ===")
    logger.info(f"With pivots - Accuracy: {eval_with_pivots['accuracy']:.4f}")
    logger.info(f"Without pivots - Accuracy: {results_no_pivots['accuracy']:.4f}")

    # Save models
    model.save(directory=MODEL_DIR)
    model_no_pivots.save(directory=MODEL_DIR)

    logger.info("Training and evaluation complete")


if __name__ == "__main__":
    main()
