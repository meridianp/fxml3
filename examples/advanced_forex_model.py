#!/usr/bin/env python
"""
Advanced Forex Model Training Script

This script demonstrates the full capabilities of FXML4's ML components:
1. Time series data loading and preprocessing
2. Advanced feature engineering
3. Multiple model types with hardware acceleration
4. Time series cross-validation
5. Trading-specific hyperparameter optimization
6. Ensemble model creation
7. Performance evaluation with trading metrics
8. Model persistence and visualization
"""

import argparse
import logging
import os
from datetime import datetime
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

# Import FXML4 modules
from fxml4.ml.models import ClassicMLModel, EnsembleModel, compare_models
from fxml4.ml.training import (
    optimize_hyperparameters,
    save_training_results,
    train_multiple_models,
    train_with_cv,
)

# Set up logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def load_forex_data(
    symbol: str = "EURUSD",
    start_date: str = "2020-01-01",
    end_date: str = "2023-01-01",
    timeframe: str = "1h",
    data_dir: str = "../input",
) -> pd.DataFrame:
    """
    Load and preprocess forex data.

    Args:
        symbol: Currency pair symbol
        start_date: Start date for training data
        end_date: End date for training data
        timeframe: Data timeframe (e.g., '1h', '4h', '1d')
        data_dir: Directory containing the data

    Returns:
        DataFrame with preprocessed forex data
    """
    logger.info(f"Loading {symbol} data from {start_date} to {end_date}")

    # Construct path to data directory
    symbol_dir = Path(data_dir) / f"C_{symbol}"

    if not symbol_dir.exists():
        raise ValueError(f"Data directory not found: {symbol_dir}")

    # Collect all parquet files within the date range
    data_files = []

    for year_dir in symbol_dir.glob("year=*"):
        year = int(year_dir.name.split("=")[1])
        year_str = str(year)

        if year_str >= start_date[:4] and year_str <= end_date[:4]:
            for month_dir in year_dir.glob("month=*"):
                month = int(month_dir.name.split("=")[1])
                month_str = f"{month:02d}"

                if (
                    f"{year_str}-{month_str}" >= start_date[:7]
                    and f"{year_str}-{month_str}" <= end_date[:7]
                ):
                    for day_file in month_dir.glob("**/*.parquet"):
                        if day_file.exists():
                            data_files.append(day_file)

    if not data_files:
        raise ValueError(
            f"No data files found for {symbol} between {start_date} and {end_date}"
        )

    # Load and concatenate all parquet files
    dfs = []
    for file in data_files:
        try:
            df = pd.read_parquet(file)
            dfs.append(df)
        except Exception as e:
            logger.warning(f"Error loading {file}: {e}")

    if not dfs:
        raise ValueError("No data could be loaded")

    # Concatenate and sort by timestamp
    data = pd.concat(dfs)
    data = data.sort_values("timestamp")

    # Convert timestamp to datetime if not already
    if not pd.api.types.is_datetime64_any_dtype(data["timestamp"]):
        data["timestamp"] = pd.to_datetime(data["timestamp"])

    # Filter by date range
    data = data[
        (data["timestamp"] >= pd.to_datetime(start_date))
        & (data["timestamp"] <= pd.to_datetime(end_date))
    ]

    # Resample to desired timeframe
    if timeframe == "1h":
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
    elif timeframe == "4h":
        data = (
            data.set_index("timestamp")
            .resample("4H")
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
    elif timeframe == "1d":
        data = (
            data.set_index("timestamp")
            .resample("1D")
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

    logger.info(f"Loaded {len(data)} rows of {timeframe} data for {symbol}")

    return data


def engineer_features(data: pd.DataFrame) -> pd.DataFrame:
    """
    Engineer features for ML models.

    Args:
        data: DataFrame with OHLCV data

    Returns:
        DataFrame with engineered features
    """
    logger.info("Engineering features")

    # Create copy to avoid modifying original data
    df = data.copy()

    # Basic returns
    df["return_1"] = df["close"].pct_change(1)
    df["log_return_1"] = np.log(df["close"] / df["close"].shift(1))

    # Moving averages
    for window in [5, 10, 20, 50, 100]:
        # Price moving averages
        df[f"sma_{window}"] = df["close"].rolling(window=window).mean()
        df[f"ema_{window}"] = df["close"].ewm(span=window, adjust=False).mean()

        # Relative price to moving average
        df[f"close_to_sma_{window}"] = df["close"] / df[f"sma_{window}"] - 1
        df[f"close_to_ema_{window}"] = df["close"] / df[f"ema_{window}"] - 1

        # Volume moving averages
        df[f"volume_sma_{window}"] = df["volume"].rolling(window=window).mean()
        df[f"volume_ratio_{window}"] = df["volume"] / df[f"volume_sma_{window}"]

    # Volatility indicators
    for window in [5, 10, 20, 50]:
        # Traditional volatility (standard deviation of returns)
        df[f"volatility_{window}"] = df["return_1"].rolling(window=window).std()

        # True Range based volatility
        df["true_range"] = np.maximum(
            df["high"] - df["low"],
            np.maximum(
                np.abs(df["high"] - df["close"].shift(1)),
                np.abs(df["low"] - df["close"].shift(1)),
            ),
        )
        df[f"atr_{window}"] = df["true_range"].rolling(window=window).mean()
        df[f"atr_ratio_{window}"] = df["true_range"] / df[f"atr_{window}"]

    # Bollinger Bands
    for window in [20]:
        df[f"bb_middle_{window}"] = df["close"].rolling(window=window).mean()
        df[f"bb_std_{window}"] = df["close"].rolling(window=window).std()
        df[f"bb_upper_{window}"] = (
            df[f"bb_middle_{window}"] + 2 * df[f"bb_std_{window}"]
        )
        df[f"bb_lower_{window}"] = (
            df[f"bb_middle_{window}"] - 2 * df[f"bb_std_{window}"]
        )
        df[f"bb_width_{window}"] = (
            df[f"bb_upper_{window}"] - df[f"bb_lower_{window}"]
        ) / df[f"bb_middle_{window}"]
        df[f"bb_position_{window}"] = (df["close"] - df[f"bb_lower_{window}"]) / (
            df[f"bb_upper_{window}"] - df[f"bb_lower_{window}"]
        )

    # Momentum indicators
    for window in [5, 10, 20]:
        # Rate of Change
        df[f"roc_{window}"] = df["close"].pct_change(window)

        # RSI (Relative Strength Index)
        delta = df["close"].diff()
        gain = delta.where(delta > 0, 0)
        loss = -delta.where(delta < 0, 0)

        avg_gain = gain.rolling(window=window).mean()
        avg_loss = loss.rolling(window=window).mean()

        rs = avg_gain / avg_loss.where(avg_loss != 0, 1)
        df[f"rsi_{window}"] = 100 - (100 / (1 + rs))

    # MACD (Moving Average Convergence Divergence)
    df["ema_12"] = df["close"].ewm(span=12, adjust=False).mean()
    df["ema_26"] = df["close"].ewm(span=26, adjust=False).mean()
    df["macd"] = df["ema_12"] - df["ema_26"]
    df["macd_signal"] = df["macd"].ewm(span=9, adjust=False).mean()
    df["macd_hist"] = df["macd"] - df["macd_signal"]

    # Add time-based features
    df["hour"] = df["timestamp"].dt.hour
    df["day_of_week"] = df["timestamp"].dt.dayofweek
    df["month"] = df["timestamp"].dt.month
    df["quarter"] = df["timestamp"].dt.quarter

    # Trading sessions (approximate times for major forex sessions)
    df["session_asia"] = ((df["hour"] >= 0) & (df["hour"] < 9)).astype(int)
    df["session_europe"] = ((df["hour"] >= 7) & (df["hour"] < 16)).astype(int)
    df["session_us"] = ((df["hour"] >= 13) & (df["hour"] < 22)).astype(int)
    df["session_overlap"] = (
        (df["session_europe"] == 1) & (df["session_us"] == 1)
    ).astype(int)

    # Lagged features
    for lag in [1, 2, 3, 5, 10]:
        for col in ["return_1", "true_range", "bb_width_20", "rsi_14", "macd"]:
            if col in df.columns:
                df[f"{col}_lag_{lag}"] = df[col].shift(lag)

    # Drop NaN values from feature engineering
    df = df.dropna()

    logger.info(f"Engineered {df.shape[1]} features from {len(df)} rows")

    return df


def create_target_labels(
    df: pd.DataFrame,
    price_col: str = "close",
    horizon: int = 24,
    method: str = "fixed_threshold",
    threshold: float = 0.0015,
) -> pd.DataFrame:
    """
    Create target labels for ML models.

    Args:
        df: DataFrame with price data
        price_col: Column with price data
        horizon: Prediction horizon in periods
        method: Labeling method ('fixed_threshold' or 'quantile')
        threshold: Threshold for price movement (if method='fixed_threshold')

    Returns:
        DataFrame with added target labels
    """
    logger.info(f"Creating target labels with horizon {horizon} using {method} method")

    # Create copy to avoid modifying original
    data = df.copy()

    # Calculate future returns
    future_return = data[price_col].shift(-horizon) / data[price_col] - 1

    # Add future returns to DataFrame for later use
    data[f"future_return_{horizon}"] = future_return

    # Create target column name
    target_col = f"target_{horizon}"

    # Apply labeling method
    if method == "fixed_threshold":
        # 1 = up, 0 = sideways, -1 = down
        data[target_col] = 0
        data.loc[future_return > threshold, target_col] = 1
        data.loc[future_return < -threshold, target_col] = -1

    elif method == "quantile":
        # Use quantiles to determine thresholds
        upper_threshold = future_return.quantile(0.7)  # Top 30%
        lower_threshold = future_return.quantile(0.3)  # Bottom 30%

        data[target_col] = 0
        data.loc[future_return > upper_threshold, target_col] = 1
        data.loc[future_return < lower_threshold, target_col] = -1

    elif method == "binary":
        # Binary classification: 1 = up, 0 = down
        data[target_col] = (future_return > 0).astype(int)

    else:
        raise ValueError(f"Unknown labeling method: {method}")

    # Log target distribution
    target_counts = data[target_col].value_counts(normalize=True) * 100

    logger.info(f"Target distribution:")
    for label, count in target_counts.items():
        logger.info(f"  Class {int(label)}: {count:.2f}%")

    return data


def run_model_training(args):
    """
    Run the model training process with command line arguments.

    Args:
        args: Command line arguments
    """
    # Load forex data
    data = load_forex_data(
        symbol=args.symbol,
        start_date=args.start_date,
        end_date=args.end_date,
        timeframe=args.timeframe,
        data_dir=args.data_dir,
    )

    # Engineer features
    features_df = engineer_features(data)

    # Create target labels
    labeled_df = create_target_labels(
        features_df,
        horizon=args.horizon,
        method=args.label_method,
        threshold=args.threshold,
    )

    # Prepare features and target
    target_col = f"target_{args.horizon}"
    future_return_col = f"future_return_{args.horizon}"

    # Exclude non-feature columns
    exclude_cols = ["timestamp", target_col, future_return_col]
    if "date" in labeled_df.columns:
        exclude_cols.append("date")

    feature_cols = [col for col in labeled_df.columns if col not in exclude_cols]

    # Create X and y
    X = labeled_df[feature_cols]
    y = labeled_df[target_col]
    future_returns = labeled_df[future_return_col].values

    # Split data into train, validation, and test sets (chronological)
    train_size = int(len(X) * args.train_size)
    val_size = int(len(X) * args.val_size)

    X_train = X.iloc[:train_size]
    y_train = y.iloc[:train_size]
    future_returns_train = future_returns[:train_size]

    X_val = X.iloc[train_size : train_size + val_size]
    y_val = y.iloc[train_size : train_size + val_size]
    future_returns_val = future_returns[train_size : train_size + val_size]

    X_test = X.iloc[train_size + val_size :]
    y_test = y.iloc[train_size + val_size :]
    future_returns_test = future_returns[train_size + val_size :]

    logger.info(
        f"Data split: train={len(X_train)}, val={len(X_val)}, test={len(X_test)}"
    )

    # Create results dictionary
    results = {}

    # Perform cross-validation if requested
    if args.cv:
        logger.info("Performing cross-validation")

        # Cross-validate Random Forest
        logger.info("Cross-validating Random Forest")
        cv_results_rf = train_with_cv(
            model_type="random_forest",
            X=X_train,
            y=y_train,
            n_splits=args.n_splits,
            train_pct=0.8,
            model_params={"n_estimators": 100, "max_depth": 10},
            future_returns=future_returns_train,
            visualize=args.visualize,
        )
        results["cv_random_forest"] = cv_results_rf

        # Cross-validate XGBoost
        logger.info("Cross-validating XGBoost")
        cv_results_xgb = train_with_cv(
            model_type="xgboost",
            X=X_train,
            y=y_train,
            n_splits=args.n_splits,
            train_pct=0.8,
            model_params={"n_estimators": 100, "max_depth": 6, "learning_rate": 0.1},
            future_returns=future_returns_train,
            visualize=args.visualize,
        )
        results["cv_xgboost"] = cv_results_xgb

    # Perform hyperparameter optimization if requested
    if args.optimize:
        logger.info("Performing hyperparameter optimization")

        # Optimize XGBoost
        logger.info("Optimizing XGBoost")
        xgb_param_grid = {
            "max_depth": [3, 5, 7],
            "learning_rate": [0.01, 0.05, 0.1],
            "n_estimators": [50, 100, 200],
            "subsample": [0.8, 0.9, 1.0],
            "colsample_bytree": [0.8, 0.9, 1.0],
        }

        opt_results_xgb = optimize_hyperparameters(
            model_type="xgboost",
            X_train=X_train,
            y_train=y_train,
            X_val=X_val,
            y_val=y_val,
            param_grid=xgb_param_grid,
            future_returns=future_returns_val,
            metric=args.optimize_metric,
            visualize=args.visualize,
        )
        results["opt_xgboost"] = opt_results_xgb

        # Optimize Random Forest
        logger.info("Optimizing Random Forest")
        rf_param_grid = {
            "max_depth": [5, 10, 15, None],
            "n_estimators": [50, 100, 200],
            "min_samples_split": [2, 5, 10],
            "min_samples_leaf": [1, 2, 4],
        }

        opt_results_rf = optimize_hyperparameters(
            model_type="random_forest",
            X_train=X_train,
            y_train=y_train,
            X_val=X_val,
            y_val=y_val,
            param_grid=rf_param_grid,
            future_returns=future_returns_val,
            metric=args.optimize_metric,
            visualize=args.visualize,
        )
        results["opt_random_forest"] = opt_results_rf

    # Train final models
    logger.info("Training final models")

    # Define model configurations
    model_configs = [
        {
            "model_type": "random_forest",
            "name": f"rf_{args.symbol}_{args.timeframe}",
            "model_params": {"n_estimators": 100, "max_depth": 10},
        },
        {
            "model_type": "xgboost",
            "name": f"xgb_{args.symbol}_{args.timeframe}",
            "model_params": {"n_estimators": 100, "max_depth": 6, "learning_rate": 0.1},
        },
        {"model_type": "logistic", "name": f"lr_{args.symbol}_{args.timeframe}"},
    ]

    # Use optimized parameters if available
    if args.optimize:
        if "opt_random_forest" in results:
            model_configs[0]["model_params"] = results["opt_random_forest"][
                "best_params"
            ]
        if "opt_xgboost" in results:
            model_configs[1]["model_params"] = results["opt_xgboost"]["best_params"]

    # Train models
    training_results = train_multiple_models(
        X_train=pd.concat(
            [X_train, X_val]
        ),  # Use both train and validation for final training
        y_train=pd.concat([y_train, y_val]),
        X_test=X_test,
        y_test=y_test,
        model_configs=model_configs,
        create_ensemble=True,
        future_returns=future_returns_test,
        visualize=args.visualize,
    )
    results["training"] = training_results

    # Create timestamp for results
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    results_name = f"{args.symbol}_{args.timeframe}_{args.horizon}_{timestamp}"

    # Save results
    output_path = save_training_results(
        results=results, directory=args.output_dir, name=results_name
    )

    logger.info(f"All results saved to: {output_path}")

    return results


def main():
    """Parse command line arguments and run the model training process."""
    parser = argparse.ArgumentParser(description="Advanced Forex Model Training Script")

    # Data parameters
    parser.add_argument(
        "--symbol", type=str, default="EURUSD", help="Currency pair symbol"
    )
    parser.add_argument(
        "--timeframe", type=str, default="1h", help="Data timeframe (e.g., 1h, 4h, 1d)"
    )
    parser.add_argument(
        "--start-date", type=str, default="2020-01-01", help="Start date (YYYY-MM-DD)"
    )
    parser.add_argument(
        "--end-date", type=str, default="2023-01-01", help="End date (YYYY-MM-DD)"
    )
    parser.add_argument(
        "--data-dir", type=str, default="../input", help="Data directory"
    )

    # Target parameters
    parser.add_argument(
        "--horizon", type=int, default=24, help="Prediction horizon in periods"
    )
    parser.add_argument(
        "--label-method",
        type=str,
        default="fixed_threshold",
        choices=["fixed_threshold", "quantile", "binary"],
        help="Method for creating target labels",
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=0.0015,
        help="Threshold for price movement (if using fixed_threshold)",
    )

    # Training parameters
    parser.add_argument(
        "--train-size",
        type=float,
        default=0.6,
        help="Fraction of data to use for training",
    )
    parser.add_argument(
        "--val-size",
        type=float,
        default=0.2,
        help="Fraction of data to use for validation",
    )
    parser.add_argument("--cv", action="store_true", help="Perform cross-validation")
    parser.add_argument(
        "--n-splits", type=int, default=5, help="Number of cross-validation splits"
    )
    parser.add_argument(
        "--optimize", action="store_true", help="Perform hyperparameter optimization"
    )
    parser.add_argument(
        "--optimize-metric",
        type=str,
        default="f1",
        choices=["accuracy", "f1", "profit_factor", "sharpe_ratio"],
        help="Metric to optimize hyperparameters for",
    )

    # Output parameters
    parser.add_argument(
        "--output-dir", type=str, default="results", help="Directory to save results"
    )
    parser.add_argument("--visualize", action="store_true", help="Visualize results")

    args = parser.parse_args()

    try:
        # Run model training
        run_model_training(args)
    except Exception as e:
        logger.error(f"Error in model training: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    main()
