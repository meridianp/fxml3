#!/usr/bin/env python
"""
Example script for training ML models on forex data.

This script demonstrates how to:
1. Load and preprocess forex data
2. Engineer features for ML models
3. Train multiple model types (Random Forest, XGBoost, Logistic Regression)
4. Create an ensemble model
5. Evaluate models using both ML and trading metrics
6. Save models for later use

The script is designed to work with Apple Silicon for local development
but can also leverage GPUs when available.
"""

import logging
import os
from datetime import datetime
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from fxml4.ml.economic_features import add_economic_features
from fxml4.ml.features import add_regime_features, extract_features

# Import FXML4 modules
from fxml4.ml.models import ClassicMLModel, EnsembleModel, compare_models

# Set up logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Constants
DATA_DIR = Path("../input/C_EURUSD")
OUTPUT_DIR = Path("models")
SYMBOL = "EURUSD"
TIMEFRAME = "1h"


def load_data(symbol=SYMBOL, start_date="2018-01-01", end_date="2022-12-31"):
    """
    Load forex data from parquet files.

    Args:
        symbol: Currency pair symbol
        start_date: Start date for training data
        end_date: End date for training data

    Returns:
        DataFrame with OHLCV data
    """
    logger.info(f"Loading data for {symbol} from {start_date} to {end_date}")

    # Generate a list of all parquet files
    data_files = []
    for year_dir in DATA_DIR.glob("year=*"):
        year = year_dir.name.split("=")[1]
        if year >= start_date[:4] and year <= end_date[:4]:
            for month_dir in year_dir.glob("month=*"):
                month = month_dir.name.split("=")[1].zfill(2)
                if (
                    f"{year}-{month}" >= start_date[:7]
                    and f"{year}-{month}" <= end_date[:7]
                ):
                    for day_dir in month_dir.glob("day=*"):
                        day = day_dir.name.split("=")[1].zfill(2)
                        date = f"{year}-{month}-{day}"
                        if date >= start_date and date <= end_date:
                            data_file = day_dir / "data.parquet"
                            if data_file.exists():
                                data_files.append(data_file)

    if not data_files:
        raise ValueError(
            f"No data files found for {symbol} from {start_date} to {end_date}"
        )

    # Load and concatenate all parquet files
    dfs = []
    for file in data_files:
        try:
            df = pd.read_parquet(file)
            dfs.append(df)
        except Exception as e:
            logger.warning(f"Error loading {file}: {e}")

    # Concatenate and sort by timestamp
    if not dfs:
        raise ValueError("No data could be loaded")

    data = pd.concat(dfs)
    data = data.sort_values("timestamp")

    # Resample to target timeframe if needed
    if TIMEFRAME == "1h":
        data = (
            data.set_index("timestamp")
            .resample("1H")
            .agg(
                {
                    "open": "first",
                    "high": "max",
                    "low": "min",
                    "close": "last",
                    "volume": "sum",
                }
            )
            .reset_index()
        )

    logger.info(f"Loaded {len(data)} rows of data")
    return data


def prepare_features(data):
    """
    Prepare features for ML models.

    Args:
        data: DataFrame with OHLCV data

    Returns:
        Tuple of (features_df, target_series)
    """
    logger.info("Preparing features")

    # Extract technical features
    features = extract_features(data)

    # Add economic features (if available)
    try:
        features = add_economic_features(features)
    except Exception as e:
        logger.warning(f"Error adding economic features: {e}")

    # Add market regime features
    features = add_regime_features(features)

    # Create target labels (future price direction)
    # 1 = up, 0 = neutral, -1 = down
    horizon = 24  # 24 hours ahead prediction
    price_change = data["close"].shift(-horizon) / data["close"] - 1
    threshold = 0.0015  # 15 pips for EURUSD (approximate)

    target = pd.Series(0, index=data.index)
    target[price_change > threshold] = 1
    target[price_change < -threshold] = -1

    # Drop NaN values
    features = features.dropna()
    target = target.loc[features.index]

    logger.info(f"Prepared {len(features)} rows with {features.shape[1]} features")
    logger.info(f"Target distribution: {target.value_counts().to_dict()}")

    return features, target


def train_and_evaluate_models(X_train, y_train, X_test, y_test):
    """
    Train and evaluate multiple models.

    Args:
        X_train: Training features
        y_train: Training targets
        X_test: Test features
        y_test: Test targets

    Returns:
        Dictionary of trained models
    """
    # Calculate future returns for trading metrics
    horizon = 24  # Match the horizon used for target generation
    future_returns = np.zeros(len(X_test))

    # Get the number of classes in the target
    n_classes = len(np.unique(y_train))
    logger.info(f"Target has {n_classes} classes")

    # Train Random Forest model
    logger.info("Training Random Forest model")
    rf_model = ClassicMLModel(
        model_type="random_forest",
        name=f"rf_{SYMBOL}_{TIMEFRAME}",
        n_classes=n_classes,
        model_params={"n_estimators": 100, "max_depth": 10, "min_samples_split": 5},
    )
    rf_model.train(X_train, y_train)

    # Train XGBoost model
    logger.info("Training XGBoost model")
    xgb_model = ClassicMLModel(
        model_type="xgboost",
        name=f"xgb_{SYMBOL}_{TIMEFRAME}",
        n_classes=n_classes,
        model_params={
            "n_estimators": 100,
            "max_depth": 6,
            "learning_rate": 0.1,
            "subsample": 0.8,
        },
    )
    xgb_model.train(X_train, y_train)

    # Train Logistic Regression model
    logger.info("Training Logistic Regression model")
    lr_model = ClassicMLModel(
        model_type="logistic", name=f"lr_{SYMBOL}_{TIMEFRAME}", n_classes=n_classes
    )
    lr_model.train(X_train, y_train)

    # Create an ensemble model
    logger.info("Creating ensemble model")
    ensemble = EnsembleModel(
        models=[rf_model, xgb_model, lr_model],
        name=f"ensemble_{SYMBOL}_{TIMEFRAME}",
        ensemble_method="weighted",
        weights=[0.4, 0.5, 0.1],  # Weights based on model performance
    )

    # Add all models to a dictionary
    models = {
        "random_forest": rf_model,
        "xgboost": xgb_model,
        "logistic_regression": lr_model,
        "ensemble": ensemble,
    }

    # Evaluate all models
    logger.info("Evaluating models")
    for name, model in models.items():
        logger.info(f"Evaluating {name} model")
        metrics = model.evaluate(X_test, y_test, returns=future_returns)

        logger.info(f"  Accuracy: {metrics['accuracy']:.4f}")
        logger.info(f"  Precision: {metrics['precision']:.4f}")
        logger.info(f"  Recall: {metrics['recall']:.4f}")
        logger.info(f"  F1: {metrics['f1']:.4f}")

    # Compare all models
    comparison = compare_models(
        list(models.values()), X_test, y_test, returns=future_returns, figsize=(12, 8)
    )

    logger.info(f"Model comparison:\n{comparison[['model_name', 'accuracy', 'f1']]}")

    return models


def save_models(models, output_dir=OUTPUT_DIR):
    """
    Save trained models to disk.

    Args:
        models: Dictionary of models to save
        output_dir: Directory to save models
    """
    # Create output directory if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)

    # Save each model
    for name, model in models.items():
        logger.info(f"Saving {name} model")
        model.save(output_dir)

    logger.info(f"All models saved to {output_dir}")


def main():
    """Main function for training forex models."""
    # Load data
    start_date = "2018-01-01"
    end_date = "2022-12-31"
    split_date = "2021-12-31"  # Use 2018-2021 for training, 2022 for testing

    data = load_data(SYMBOL, start_date, end_date)

    # Prepare features
    features, target = prepare_features(data)

    # Split data into train and test sets
    train_mask = data["timestamp"] <= split_date
    test_mask = data["timestamp"] > split_date

    X_train = features[train_mask].reset_index(drop=True)
    y_train = target[train_mask].reset_index(drop=True)
    X_test = features[test_mask].reset_index(drop=True)
    y_test = target[test_mask].reset_index(drop=True)

    logger.info(f"Training set: {len(X_train)} samples")
    logger.info(f"Test set: {len(X_test)} samples")

    # Train and evaluate models
    models = train_and_evaluate_models(X_train, y_train, X_test, y_test)

    # Save models
    save_models(models)

    logger.info("Script completed successfully")


if __name__ == "__main__":
    main()
