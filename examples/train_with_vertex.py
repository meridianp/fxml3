#!/usr/bin/env python
"""
Example script for training ML models on forex data using Google Vertex AI.

This script demonstrates how to:
1. Load and preprocess forex data
2. Engineer features for ML models
3. Configure Vertex AI for model training
4. Train models using both custom training and AutoML
5. Evaluate models using both ML and trading metrics
6. Save models for later use

The script shows the seamless integration between local development
and cloud-based training for scalable machine learning.
"""

import argparse
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
from fxml4.ml.models import ClassicMLModel
from fxml4.ml.vertex_ai import AutoMLModel, VertexAIConfig, VertexAIModel

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


def train_with_vertex_ai(
    X_train,
    y_train,
    X_test,
    y_test,
    gcp_project_id,
    region="us-central1",
    use_automl=False,
):
    """
    Train models using Google Vertex AI.

    Args:
        X_train: Training features
        y_train: Training targets
        X_test: Test features
        y_test: Test targets
        gcp_project_id: Google Cloud project ID
        region: Google Cloud region
        use_automl: Whether to use AutoML

    Returns:
        Trained models
    """
    # Get the number of classes in the target
    n_classes = len(np.unique(y_train))
    logger.info(f"Target has {n_classes} classes")

    # Create VertexAI configuration
    vertex_config = VertexAIConfig(
        project_id=gcp_project_id, region=region, gcs_bucket=f"{gcp_project_id}-fxml4"
    )

    # Validate configuration
    if not vertex_config.validate():
        logger.error(
            "Failed to validate Vertex AI configuration. Please check your credentials and settings."
        )
        return None

    # Train with vertex AI
    if use_automl:
        # Using AutoML
        logger.info("Training with Vertex AI AutoML")
        model = AutoMLModel(
            name=f"automl_{SYMBOL}_{TIMEFRAME}",
            n_classes=n_classes,
            config=vertex_config,
            budget_milli_node_hours=1000,  # 1000 milli-node hours (~$20)
        )

        # Train AutoML model
        model.train(X_train, y_train)
    else:
        # Using custom training with XGBoost
        logger.info("Training with Vertex AI custom training")
        model = VertexAIModel(
            model_type="xgboost",
            name=f"vertex_xgb_{SYMBOL}_{TIMEFRAME}",
            n_classes=n_classes,
            config=vertex_config,
            model_params={
                "n_estimators": 200,
                "max_depth": 6,
                "learning_rate": 0.1,
                "subsample": 0.8,
            },
        )

        # Train model
        model.train(X_train, y_train, X_val=X_test, y_val=y_test)

    # Calculate future returns for trading metrics (this would typically be real returns data)
    future_returns = np.random.normal(0.0001, 0.001, size=len(X_test))

    # Evaluate model
    logger.info("Evaluating model")
    metrics = model.evaluate(X_test, y_test, returns=future_returns)

    logger.info(f"  Accuracy: {metrics['accuracy']:.4f}")
    logger.info(f"  Precision: {metrics['precision']:.4f}")
    logger.info(f"  Recall: {metrics['recall']:.4f}")
    logger.info(f"  F1: {metrics['f1']:.4f}")

    if "profit_factor" in metrics:
        logger.info(f"  Profit Factor: {metrics['profit_factor']:.4f}")
        logger.info(f"  Win Rate: {metrics['win_rate']:.4f}")

    # Save model
    model.save(OUTPUT_DIR)
    logger.info(f"Model saved to {OUTPUT_DIR}")

    return model


def compare_with_local_models(X_train, y_train, X_test, y_test, vertex_model):
    """
    Compare Vertex AI models with locally trained models.

    Args:
        X_train: Training features
        y_train: Training targets
        X_test: Test features
        y_test: Test targets
        vertex_model: Model trained on Vertex AI

    Returns:
        Comparison DataFrame
    """
    # Get the number of classes in the target
    n_classes = len(np.unique(y_train))

    # Train a local XGBoost model for comparison
    logger.info("Training local XGBoost model for comparison")
    local_xgb = ClassicMLModel(
        model_type="xgboost",
        name=f"local_xgb_{SYMBOL}_{TIMEFRAME}",
        n_classes=n_classes,
        model_params={
            "n_estimators": 100,  # Fewer estimators for quick local training
            "max_depth": 6,
            "learning_rate": 0.1,
            "subsample": 0.8,
        },
    )
    local_xgb.train(X_train, y_train)

    # Calculate future returns for trading metrics
    future_returns = np.random.normal(0.0001, 0.001, size=len(X_test))

    # Compare models
    from fxml4.ml.models import compare_models

    models = [local_xgb, vertex_model]

    comparison = compare_models(
        models, X_test, y_test, returns=future_returns, figsize=(12, 8)
    )

    logger.info(f"Model comparison:\n{comparison[['model_name', 'accuracy', 'f1']]}")

    return comparison


def main():
    """Main function for training forex models with Vertex AI."""
    # Parse command line arguments
    parser = argparse.ArgumentParser(
        description="Train ML models on forex data using Google Vertex AI"
    )
    parser.add_argument("--project-id", required=True, help="Google Cloud project ID")
    parser.add_argument("--region", default="us-central1", help="Google Cloud region")
    parser.add_argument(
        "--automl", action="store_true", help="Use AutoML instead of custom training"
    )
    parser.add_argument(
        "--start-date", default="2018-01-01", help="Start date for training data"
    )
    parser.add_argument(
        "--end-date", default="2022-12-31", help="End date for training data"
    )
    parser.add_argument(
        "--split-date",
        default="2021-12-31",
        help="Date to split training and test data",
    )

    args = parser.parse_args()

    # Load data
    data = load_data(SYMBOL, args.start_date, args.end_date)

    # Prepare features
    features, target = prepare_features(data)

    # Split data into train and test sets
    train_mask = data["timestamp"] <= args.split_date
    test_mask = data["timestamp"] > args.split_date

    X_train = features[train_mask].reset_index(drop=True)
    y_train = target[train_mask].reset_index(drop=True)
    X_test = features[test_mask].reset_index(drop=True)
    y_test = target[test_mask].reset_index(drop=True)

    logger.info(f"Training set: {len(X_train)} samples")
    logger.info(f"Test set: {len(X_test)} samples")

    # Train with Vertex AI
    vertex_model = train_with_vertex_ai(
        X_train,
        y_train,
        X_test,
        y_test,
        gcp_project_id=args.project_id,
        region=args.region,
        use_automl=args.automl,
    )

    if vertex_model is not None:
        # Compare with local models
        compare_with_local_models(X_train, y_train, X_test, y_test, vertex_model)

    logger.info("Script completed successfully")


if __name__ == "__main__":
    main()
