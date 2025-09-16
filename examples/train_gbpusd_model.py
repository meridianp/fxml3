#!/usr/bin/env python3
"""
Train GBP/USD ML model for 4h timeframe analysis.

This script:
1. Loads GBP/USD historical data from parquet files
2. Prepares the data for the 4h timeframe
3. Adds technical features and creates labels
4. Trains and optimizes ML models for GBP/USD trading
5. Saves the trained models for use in signal generation
"""

import argparse
import logging
import os
import sys
from datetime import datetime
from typing import Any, Dict, List, Optional

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.metrics import accuracy_score, f1_score, precision_score, recall_score

# Add FXML4 directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fxml4.ml.gbpusd_model import GBPUSDModel, train_gbpusd_model
from fxml4.strategy.gbpusd_signal_generator import GBPUSDSignalGenerator

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def load_gbpusd_data(
    input_dir: str = "input/C_GBPUSD",
    years: Optional[List[int]] = None,
    timeframe: str = "1h",
    output_file: Optional[str] = None,
) -> pd.DataFrame:
    """
    Load GBP/USD historical data from parquet files and resample to desired timeframe.

    Args:
        input_dir: Directory containing GBP/USD data
        years: List of years to include (default: all available)
        timeframe: Timeframe to resample to
        output_file: Path to save the resampled data

    Returns:
        DataFrame with resampled OHLCV data
    """
    # Find parquet files
    parquet_files = []

    for root, _, files in os.walk(input_dir):
        for file in files:
            if file.endswith(".parquet"):
                file_path = os.path.join(root, file)

                # Filter by year if specified
                if years:
                    year_match = False
                    for year in years:
                        if f"/year={year}/" in file_path:
                            year_match = True
                            break
                    if not year_match:
                        continue

                parquet_files.append(file_path)

    if not parquet_files:
        logger.error(f"No parquet files found in {input_dir}")
        return pd.DataFrame()

    logger.info(f"Found {len(parquet_files)} parquet files")

    # Load and combine data
    dfs = []

    for file in parquet_files:
        try:
            df = pd.read_parquet(file)
            dfs.append(df)
        except Exception as e:
            logger.warning(f"Error loading {file}: {e}")

    if not dfs:
        logger.error("No data loaded")
        return pd.DataFrame()

    # Combine data
    combined = pd.concat(dfs, ignore_index=False)

    # Ensure timestamp is the index
    if "timestamp" in combined.columns and combined.index.name != "timestamp":
        combined["timestamp"] = pd.to_datetime(combined["timestamp"], utc=True)
        combined = combined.set_index("timestamp")

    # Ensure columns are lower case
    combined.columns = [col.lower() for col in combined.columns]

    # Sort by timestamp
    combined = combined.sort_index()

    logger.info(f"Loaded {len(combined)} rows of data")

    # Resample to desired timeframe if needed
    if timeframe != "1m":
        # Map timeframe string to pandas frequency
        freq_map = {
            "1m": "1min",
            "5m": "5min",
            "15m": "15min",
            "30m": "30min",
            "1h": "1H",
            "4h": "4H",
            "1d": "1D",
        }

        freq = freq_map.get(timeframe)
        if not freq:
            logger.error(f"Invalid timeframe: {timeframe}")
            return combined

        # Resample OHLCV data
        resampled = pd.DataFrame()
        resampled["open"] = combined["open"].resample(freq).first()
        resampled["high"] = combined["high"].resample(freq).max()
        resampled["low"] = combined["low"].resample(freq).min()
        resampled["close"] = combined["close"].resample(freq).last()

        if "volume" in combined.columns:
            resampled["volume"] = combined["volume"].resample(freq).sum()
        else:
            # Create placeholder volume
            resampled["volume"] = 0

        # Drop NaN rows
        resampled = resampled.dropna()

        logger.info(f"Resampled to {timeframe}: {len(resampled)} rows")

        # Save to file if specified
        if output_file:
            os.makedirs(os.path.dirname(output_file), exist_ok=True)
            resampled.to_parquet(output_file)
            logger.info(f"Saved resampled data to {output_file}")

        return resampled

    return combined


def optimize_model_parameters(
    data: pd.DataFrame,
    model_type: str = "random_forest",
    cv_folds: int = 5,
    target_horizon: int = 12,
) -> Dict[str, Any]:
    """
    Optimize model parameters using grid search.

    Args:
        data: DataFrame with OHLCV data
        model_type: Type of model to optimize
        cv_folds: Number of cross-validation folds
        target_horizon: Number of periods ahead for prediction

    Returns:
        Dictionary with optimized parameters
    """
    import joblib
    from sklearn.model_selection import GridSearchCV, TimeSeriesSplit

    # Create model with default parameters
    model = GBPUSDModel(model_type=model_type)

    # Prepare features
    features = model.prepare_features(
        data, target_horizon=target_horizon, add_lag_features=True, create_target=True
    )

    # Split features and target
    target_col = f"target_{target_horizon}"
    X = features.drop(columns=[target_col])
    y = features[target_col]

    # Scale features
    X_scaled = model.scale_features(X, refit=True)[0]

    # Define parameter grid based on model type
    if model_type == "random_forest":
        param_grid = {
            "n_estimators": [100, 200, 300],
            "max_depth": [10, 15, 20, None],
            "min_samples_split": [2, 5, 10],
            "min_samples_leaf": [1, 2, 4],
            "class_weight": ["balanced", "balanced_subsample", None],
        }
    elif model_type == "xgboost":
        param_grid = {
            "n_estimators": [100, 200, 300],
            "max_depth": [3, 6, 9],
            "learning_rate": [0.01, 0.1, 0.2],
            "subsample": [0.6, 0.8, 1.0],
            "colsample_bytree": [0.6, 0.8, 1.0],
        }
    elif model_type == "logistic":
        param_grid = {
            "C": [0.1, 1.0, 10.0],
            "penalty": ["l1", "l2"],
            "solver": ["liblinear", "saga"],
            "class_weight": ["balanced", None],
        }
    else:
        logger.error(f"Unsupported model type: {model_type}")
        return {}

    # Create cross-validation strategy
    cv = TimeSeriesSplit(n_splits=cv_folds)

    # Create grid search
    grid_search = GridSearchCV(
        estimator=model.model,
        param_grid=param_grid,
        cv=cv,
        scoring="f1_weighted",
        n_jobs=-1,
        verbose=1,
    )

    # Run grid search
    logger.info(f"Running grid search for {model_type} model")
    grid_search.fit(X_scaled, y)

    # Get best parameters
    best_params = grid_search.best_params_
    best_score = grid_search.best_score_

    logger.info(f"Best parameters: {best_params}")
    logger.info(f"Best score: {best_score:.4f}")

    # Save grid search results
    results_dir = "results"
    os.makedirs(results_dir, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    results_file = os.path.join(
        results_dir, f"grid_search_{model_type}_{timestamp}.joblib"
    )
    joblib.dump(grid_search, results_file)

    logger.info(f"Saved grid search results to {results_file}")

    return best_params


def train_multiple_models(
    data_path: str,
    target_horizon: int = 12,
    models_dir: str = "models",
) -> Dict[str, Any]:
    """
    Train multiple model types and create an ensemble.

    Args:
        data_path: Path to the data file
        target_horizon: Number of periods ahead for prediction
        models_dir: Directory to save the models

    Returns:
        Dictionary with model names and evaluation results
    """
    # Load data
    if data_path.endswith(".parquet"):
        data = pd.read_parquet(data_path)
    elif data_path.endswith(".csv"):
        data = pd.read_csv(data_path, index_col=0, parse_dates=True)
    else:
        raise ValueError(f"Unsupported file format: {data_path}")

    # Create directory for models
    os.makedirs(models_dir, exist_ok=True)

    # Train models
    model_types = ["random_forest", "xgboost", "logistic"]
    models = {}
    results = {}

    for model_type in model_types:
        logger.info(f"Training {model_type} model")

        # Train model
        model = train_gbpusd_model(
            data_path=data_path,
            model_type=model_type,
            timeframe="4h",
            target_horizon=target_horizon,
            save_dir=models_dir,
        )

        models[model_type] = model

        # Get top features
        top_features = model.get_top_features(n=10)
        logger.info(f"Top 10 features for {model_type}:")
        for _, row in top_features.iterrows():
            logger.info(f"  {row['feature']}: {row['importance']:.4f}")

        # Prepare features for evaluation
        features = model.prepare_features(
            data,
            target_horizon=target_horizon,
            add_lag_features=True,
            create_target=True,
        )

        # Split features and target
        target_col = f"target_{target_horizon}"
        X = features.drop(columns=[target_col])
        y = features[target_col]

        # Make predictions
        y_pred = model.predict(X)

        # Calculate metrics
        metrics = {
            "accuracy": accuracy_score(y, y_pred),
            "precision": precision_score(y, y_pred, average="weighted"),
            "recall": recall_score(y, y_pred, average="weighted"),
            "f1": f1_score(y, y_pred, average="weighted"),
        }

        results[model_type] = metrics

        logger.info(f"Evaluation results for {model_type}:")
        for metric, value in metrics.items():
            logger.info(f"  {metric}: {value:.4f}")

    # Plot feature importance comparison
    plt.figure(figsize=(15, 10))

    for i, (model_type, model) in enumerate(models.items()):
        top_features = model.get_top_features(n=10)

        plt.subplot(1, len(models), i + 1)
        plt.barh(np.arange(len(top_features)), top_features["importance"][::-1])
        plt.yticks(np.arange(len(top_features)), top_features["feature"][::-1])
        plt.title(f"{model_type} top features")
        plt.tight_layout()

    # Save figure
    plt.savefig(os.path.join(models_dir, "feature_importance_comparison.png"))

    # Plot metrics comparison
    plt.figure(figsize=(12, 6))

    metrics = ["accuracy", "precision", "recall", "f1"]
    model_names = list(results.keys())

    # Create grouped bar chart
    x = np.arange(len(model_names))
    width = 0.2

    for i, metric in enumerate(metrics):
        values = [results[model][metric] for model in model_names]
        plt.bar(x + i * width, values, width, label=metric)

    plt.xlabel("Model")
    plt.ylabel("Score")
    plt.title("Model comparison")
    plt.xticks(x + width * 1.5, model_names)
    plt.legend()
    plt.tight_layout()

    # Save figure
    plt.savefig(os.path.join(models_dir, "model_comparison.png"))

    # Create ensemble generator
    from fxml4.strategy.gbpusd_signal_generator import create_ensemble_generator

    model_paths = [
        (f"gbpusd_{model_type}_{datetime.now().strftime('%Y%m%d')}", models_dir)
        for model_type in model_types
    ]
    weights = [0.5, 0.3, 0.2]  # Weight RF higher, then XGB, then logistic

    ensemble_generator = create_ensemble_generator(
        model_paths=model_paths, weights=weights, config={"threshold": 0.65}
    )

    logger.info(
        f"Created ensemble generator with {len(ensemble_generator.generators)} models"
    )

    return results


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Train GBP/USD ML models")
    parser.add_argument(
        "--data-dir", default="input/C_GBPUSD", help="Directory with GBP/USD data"
    )
    parser.add_argument("--timeframe", default="4h", help="Timeframe for analysis")
    parser.add_argument(
        "--years", type=int, nargs="+", default=[2023, 2024], help="Years to include"
    )
    parser.add_argument(
        "--target-horizon", type=int, default=12, help="Target horizon for prediction"
    )
    parser.add_argument(
        "--optimize", action="store_true", help="Optimize model parameters"
    )
    parser.add_argument(
        "--model-type", default="random_forest", help="Model type for optimization"
    )
    parser.add_argument(
        "--train-all", action="store_true", help="Train all model types"
    )
    parser.add_argument(
        "--models-dir", default="models", help="Directory to save models"
    )
    args = parser.parse_args()

    # Create output directories
    os.makedirs("output", exist_ok=True)
    os.makedirs(args.models_dir, exist_ok=True)

    # Load and resample data
    output_file = f"output/C_GBPUSD_{args.timeframe}.parquet"

    data = load_gbpusd_data(
        input_dir=args.data_dir,
        years=args.years,
        timeframe=args.timeframe,
        output_file=output_file,
    )

    if data.empty:
        logger.error("No data loaded. Exiting.")
        return 1

    # Optimize model parameters if requested
    if args.optimize:
        best_params = optimize_model_parameters(
            data=data,
            model_type=args.model_type,
            cv_folds=5,
            target_horizon=args.target_horizon,
        )

        logger.info(f"Optimized parameters for {args.model_type}: {best_params}")

        # Train model with optimized parameters
        model = GBPUSDModel(model_type=args.model_type, model_params=best_params)

        # Prepare features
        features = model.prepare_features(
            data,
            target_horizon=args.target_horizon,
            add_lag_features=True,
            create_target=True,
        )

        # Train model
        target_col = f"target_{args.target_horizon}"
        results = model.train(
            features, target_col=target_col, test_size=0.2, use_cv=True, n_splits=5
        )

        # Save model
        timestamp = datetime.now().strftime("%Y%m%d")
        model.name = f"gbpusd_{args.model_type}_optimized_{timestamp}"
        model.save(directory=args.models_dir)

        logger.info(f"Trained and saved optimized {args.model_type} model")

    # Train multiple models if requested
    if args.train_all:
        results = train_multiple_models(
            data_path=output_file,
            target_horizon=args.target_horizon,
            models_dir=args.models_dir,
        )

        logger.info("Trained all model types")

    logger.info("Completed successfully")
    return 0


if __name__ == "__main__":
    sys.exit(main())
