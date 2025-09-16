#!/usr/bin/env python
"""Example demonstrating advanced time series cross-validation for forex models.

This example shows how to use the advanced time series cross-validation methods
from ml.advanced_cv to properly evaluate forex trading models.
"""

import argparse
import logging
import os

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import xgboost as xgb
from ml.advanced_cv import (
    BlockingTimeSeriesSplit,
    CombinedSignalCV,
    TimeSeriesWalkForwardCV,
    evaluate_trading_strategy,
)
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor

from fxml4.config import load_config
from fxml4.data_engineering.data_feeds.base_feed import DataFeed
from fxml4.data_engineering.data_feeds.csv_feed import CSVDataFeed

# Setup logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def load_forex_data(
    symbol: str,
    timeframe: str,
    start_date: str = None,
    end_date: str = None,
) -> pd.DataFrame:
    """Load forex data from CSV files.

    Args:
        symbol: Trading symbol (e.g., 'EURUSD').
        timeframe: Timeframe (e.g., '1h', '4h', '1d').
        start_date: Start date (YYYY-MM-DD).
        end_date: End date (YYYY-MM-DD).

    Returns:
        DataFrame with forex data.
    """
    # Default dates if not provided
    if not start_date:
        start_date = "2018-01-01"
    if not end_date:
        end_date = "2023-12-31"

    # Initialize data feed
    data_feed = CSVDataFeed(
        base_dir=os.path.join("input", f"C_{symbol}"),
        symbol=symbol,
        timeframe=timeframe,
    )

    # Load data
    data = data_feed.get_historical_data(
        start_date=start_date,
        end_date=end_date,
        include_technical_indicators=True,
    )

    logger.info(f"Loaded {len(data)} records for {symbol} ({timeframe})")
    return data


def prepare_features_and_target(data: pd.DataFrame, target_horizon: int = 5) -> tuple:
    """Prepare features and target variables for ML models.

    Args:
        data: Raw price data.
        target_horizon: Number of periods for future returns calculation.

    Returns:
        Tuple of (features_df, target_df, future_returns).
    """
    # Calculate future returns for target variable
    data["future_return"] = (
        data["close"].pct_change(target_horizon).shift(-target_horizon)
    )

    # Create binary target (direction prediction)
    data["target"] = (data["future_return"] > 0).astype(int)

    # Calculate future returns for strategy evaluation
    data["return"] = data["close"].pct_change()

    # Drop rows with NaN values
    data_clean = data.dropna()

    # Extract features (use some basic technical indicators)
    feature_columns = [
        "open",
        "high",
        "low",
        "close",
        "volume",
        "sma_5",
        "sma_10",
        "sma_20",
        "ema_5",
        "ema_10",
        "ema_20",
        "rsi",
        "macd",
        "macdsignal",
        "macd_hist",
        "bollinger_upper",
        "bollinger_middle",
        "bollinger_lower",
    ]

    # Only use available columns
    feature_columns = [col for col in feature_columns if col in data_clean.columns]

    features = data_clean[feature_columns]
    target = data_clean["target"]
    future_returns = data_clean["return"]

    return features, target, future_returns


def train_and_evaluate_with_time_series_cv(
    features: pd.DataFrame,
    target: pd.Series,
    returns: pd.Series,
    model_type: str = "rf",
    n_splits: int = 5,
    fixed_window: bool = False,
    gap: int = 0,
    test_size: float = 0.2,
    transaction_cost: float = 0.0001,
) -> dict:
    """Train and evaluate a model using time series cross-validation.

    Args:
        features: Feature data.
        target: Target variable.
        returns: Asset returns for performance evaluation.
        model_type: Type of model to use ('rf' or 'xgb').
        n_splits: Number of cross-validation splits.
        fixed_window: Whether to use fixed-size window for training.
        gap: Number of samples to exclude between train and test sets.
        test_size: Size of the test set (proportion).
        transaction_cost: Transaction cost per trade.

    Returns:
        Dictionary with evaluation results.
    """
    # Define cross-validation splitter
    cv = TimeSeriesWalkForwardCV(
        n_splits=n_splits, test_size=test_size, fixed_window=fixed_window, gap=gap
    )

    # Initialize model
    if model_type == "rf":
        model = RandomForestClassifier(
            n_estimators=100, max_depth=5, min_samples_split=10, random_state=42
        )
    elif model_type == "xgb":
        model = xgb.XGBClassifier(
            n_estimators=100, max_depth=5, learning_rate=0.1, random_state=42
        )
    else:
        raise ValueError(f"Unknown model type: {model_type}")

    # Evaluate model as a trading strategy
    results = evaluate_trading_strategy(
        model=model,
        X=features,
        y=target,
        returns=returns,
        cv=cv,
        transaction_cost=transaction_cost,
        hold_period=1,
        annualization_factor=252,
        return_trades=True,
    )

    # Extract performance metrics
    avg_metrics = results["avg_metrics"]
    logger.info(f"Cross-validation results ({n_splits} splits):")
    logger.info(
        f"  Average Sharpe ratio: {avg_metrics['sharpe_ratio_mean']:.4f} ± {avg_metrics['sharpe_ratio_std']:.4f}"
    )
    logger.info(
        f"  Average annualized return: {avg_metrics['annualized_return_mean']:.4f} ± {avg_metrics['annualized_return_std']:.4f}"
    )
    logger.info(
        f"  Average max drawdown: {avg_metrics['max_drawdown_mean']:.4f} ± {avg_metrics['max_drawdown_std']:.4f}"
    )
    logger.info(
        f"  Average win rate: {avg_metrics['win_rate_mean']:.4f} ± {avg_metrics['win_rate_std']:.4f}"
    )

    return results


def train_and_evaluate_with_blocking_cv(
    features: pd.DataFrame,
    target: pd.Series,
    returns: pd.Series,
    model_type: str = "rf",
    n_splits: int = 5,
    purge_window: int = 0,
    embargo_size: int = 0,
    transaction_cost: float = 0.0001,
) -> dict:
    """Train and evaluate a model using blocking time series cross-validation.

    Args:
        features: Feature data.
        target: Target variable.
        returns: Asset returns for performance evaluation.
        model_type: Type of model to use ('rf' or 'xgb').
        n_splits: Number of cross-validation splits.
        purge_window: Number of observations to purge.
        embargo_size: Number of observations to embargo.
        transaction_cost: Transaction cost per trade.

    Returns:
        Dictionary with evaluation results.
    """
    # Define cross-validation splitter
    cv = BlockingTimeSeriesSplit(
        n_splits=n_splits, purge_window=purge_window, embargo_size=embargo_size
    )

    # Initialize model
    if model_type == "rf":
        model = RandomForestClassifier(
            n_estimators=100, max_depth=5, min_samples_split=10, random_state=42
        )
    elif model_type == "xgb":
        model = xgb.XGBClassifier(
            n_estimators=100, max_depth=5, learning_rate=0.1, random_state=42
        )
    else:
        raise ValueError(f"Unknown model type: {model_type}")

    # Evaluate model as a trading strategy
    results = evaluate_trading_strategy(
        model=model,
        X=features,
        y=target,
        returns=returns,
        cv=cv,
        transaction_cost=transaction_cost,
        hold_period=1,
        annualization_factor=252,
        return_trades=True,
    )

    # Extract performance metrics
    avg_metrics = results["avg_metrics"]
    logger.info(f"Blocking CV results ({n_splits} splits):")
    logger.info(
        f"  Average Sharpe ratio: {avg_metrics['sharpe_ratio_mean']:.4f} ± {avg_metrics['sharpe_ratio_std']:.4f}"
    )
    logger.info(
        f"  Average annualized return: {avg_metrics['annualized_return_mean']:.4f} ± {avg_metrics['annualized_return_std']:.4f}"
    )
    logger.info(
        f"  Average max drawdown: {avg_metrics['max_drawdown_mean']:.4f} ± {avg_metrics['max_drawdown_std']:.4f}"
    )
    logger.info(
        f"  Average win rate: {avg_metrics['win_rate_mean']:.4f} ± {avg_metrics['win_rate_std']:.4f}"
    )

    return results


def visualize_cv_results(results: dict, title: str = "Strategy Performance"):
    """Visualize cross-validation results.

    Args:
        results: Dictionary with evaluation results.
        title: Plot title.
    """
    plt.figure(figsize=(16, 12))

    # Plot equity curves for each fold
    plt.subplot(2, 2, 1)
    for i, curve in enumerate(results["equity_curves"]):
        plt.plot(curve, label=f"Fold {i+1}")
    plt.title("Equity Curves")
    plt.xlabel("Time")
    plt.ylabel("Cumulative Return")
    plt.legend()
    plt.grid(True, alpha=0.3)

    # Plot key metrics
    plt.subplot(2, 2, 2)
    metrics = ["sharpe_ratio", "annualized_return", "max_drawdown", "win_rate"]
    metric_values = [results["avg_metrics"][f"{m}_mean"] for m in metrics]
    metric_stds = [results["avg_metrics"][f"{m}_std"] for m in metrics]

    # Adjust max_drawdown sign for visualization
    metric_values[2] = abs(metric_values[2])

    plt.bar(metrics, metric_values, yerr=metric_stds, capsize=10)
    plt.title("Key Performance Metrics")
    plt.ylabel("Value")
    plt.grid(True, axis="y", alpha=0.3)

    # Add annotations
    for i, value in enumerate(metric_values):
        plt.text(i, value + 0.02, f"{value:.4f}", ha="center")

    # Plot trade distribution
    if "trades" in results:
        plt.subplot(2, 2, 3)
        trade_returns = [trade["return"] for trade in results["trades"]]
        plt.hist(trade_returns, bins=20)
        plt.title("Trade Returns Distribution")
        plt.xlabel("Return")
        plt.ylabel("Frequency")
        plt.grid(True, alpha=0.3)

        # Plot trade duration vs. return
        plt.subplot(2, 2, 4)
        durations = [trade["duration"] for trade in results["trades"]]
        returns = [trade["return"] for trade in results["trades"]]
        plt.scatter(durations, returns, alpha=0.5)
        plt.title("Trade Duration vs. Return")
        plt.xlabel("Duration (periods)")
        plt.ylabel("Return")
        plt.grid(True, alpha=0.3)

    plt.suptitle(title, fontsize=16)
    plt.tight_layout(rect=[0, 0, 1, 0.95])
    plt.show()


def compare_cv_methods(
    features: pd.DataFrame,
    target: pd.Series,
    returns: pd.Series,
    model_type: str = "rf",
):
    """Compare different cross-validation methods.

    Args:
        features: Feature data.
        target: Target variable.
        returns: Asset returns for performance evaluation.
        model_type: Type of model to use ('rf' or 'xgb').
    """
    cv_methods = {
        "Standard TimeSeriesCV": TimeSeriesWalkForwardCV(
            n_splits=5, test_size=0.2, fixed_window=False
        ),
        "Fixed Window CV": TimeSeriesWalkForwardCV(
            n_splits=5, test_size=0.2, fixed_window=True
        ),
        "Blocking CV": BlockingTimeSeriesSplit(n_splits=5),
        "Purged Blocking CV": BlockingTimeSeriesSplit(
            n_splits=5, purge_window=5, embargo_size=5
        ),
    }

    # Initialize model
    if model_type == "rf":
        model = RandomForestClassifier(
            n_estimators=100, max_depth=5, min_samples_split=10, random_state=42
        )
    elif model_type == "xgb":
        model = xgb.XGBClassifier(
            n_estimators=100, max_depth=5, learning_rate=0.1, random_state=42
        )
    else:
        raise ValueError(f"Unknown model type: {model_type}")

    # Evaluate model with each CV method
    results = {}
    for name, cv in cv_methods.items():
        logger.info(f"\nEvaluating with {name}...")
        result = evaluate_trading_strategy(
            model=model,
            X=features,
            y=target,
            returns=returns,
            cv=cv,
            transaction_cost=0.0001,
            hold_period=1,
            annualization_factor=252,
        )
        results[name] = result

    # Compare results
    plt.figure(figsize=(14, 8))

    # Plot Sharpe ratios
    sharpe_means = [
        results[name]["avg_metrics"]["sharpe_ratio_mean"] for name in cv_methods
    ]
    sharpe_stds = [
        results[name]["avg_metrics"]["sharpe_ratio_std"] for name in cv_methods
    ]

    plt.subplot(2, 2, 1)
    plt.bar(cv_methods.keys(), sharpe_means, yerr=sharpe_stds, capsize=10)
    plt.title("Sharpe Ratio Comparison")
    plt.xticks(rotation=45)
    plt.grid(True, axis="y", alpha=0.3)

    # Plot annualized returns
    return_means = [
        results[name]["avg_metrics"]["annualized_return_mean"] for name in cv_methods
    ]
    return_stds = [
        results[name]["avg_metrics"]["annualized_return_std"] for name in cv_methods
    ]

    plt.subplot(2, 2, 2)
    plt.bar(cv_methods.keys(), return_means, yerr=return_stds, capsize=10)
    plt.title("Annualized Return Comparison")
    plt.xticks(rotation=45)
    plt.grid(True, axis="y", alpha=0.3)

    # Plot max drawdowns
    drawdown_means = [
        abs(results[name]["avg_metrics"]["max_drawdown_mean"]) for name in cv_methods
    ]
    drawdown_stds = [
        results[name]["avg_metrics"]["max_drawdown_std"] for name in cv_methods
    ]

    plt.subplot(2, 2, 3)
    plt.bar(cv_methods.keys(), drawdown_means, yerr=drawdown_stds, capsize=10)
    plt.title("Max Drawdown Comparison")
    plt.xticks(rotation=45)
    plt.grid(True, axis="y", alpha=0.3)

    # Plot win rates
    winrate_means = [
        results[name]["avg_metrics"]["win_rate_mean"] for name in cv_methods
    ]
    winrate_stds = [results[name]["avg_metrics"]["win_rate_std"] for name in cv_methods]

    plt.subplot(2, 2, 4)
    plt.bar(cv_methods.keys(), winrate_means, yerr=winrate_stds, capsize=10)
    plt.title("Win Rate Comparison")
    plt.xticks(rotation=45)
    plt.grid(True, axis="y", alpha=0.3)

    plt.suptitle(
        f"Cross-Validation Method Comparison - {model_type.upper()} Model", fontsize=16
    )
    plt.tight_layout(rect=[0, 0, 1, 0.95])
    plt.show()

    # Print summary
    logger.info("\nCross-validation method comparison summary:")
    for name in cv_methods:
        r = results[name]["avg_metrics"]
        logger.info(f"  {name}:")
        logger.info(
            f"    Sharpe ratio: {r['sharpe_ratio_mean']:.4f} ± {r['sharpe_ratio_std']:.4f}"
        )
        logger.info(
            f"    Ann. return: {r['annualized_return_mean']:.4f} ± {r['annualized_return_std']:.4f}"
        )
        logger.info(
            f"    Max drawdown: {r['max_drawdown_mean']:.4f} ± {r['max_drawdown_std']:.4f}"
        )
        logger.info(f"    Win rate: {r['win_rate_mean']:.4f} ± {r['win_rate_std']:.4f}")


def main():
    """Run the advanced CV example."""
    parser = argparse.ArgumentParser(description="Advanced Cross-Validation Example")
    parser.add_argument("--symbol", type=str, default="EURUSD", help="Trading symbol")
    parser.add_argument("--timeframe", type=str, default="1h", help="Timeframe")
    parser.add_argument(
        "--start", type=str, default="2018-01-01", help="Start date (YYYY-MM-DD)"
    )
    parser.add_argument(
        "--end", type=str, default="2023-12-31", help="End date (YYYY-MM-DD)"
    )
    parser.add_argument(
        "--model", type=str, default="rf", choices=["rf", "xgb"], help="Model type"
    )
    parser.add_argument("--n_splits", type=int, default=5, help="Number of CV splits")
    parser.add_argument("--compare", action="store_true", help="Compare CV methods")

    args = parser.parse_args()

    # Load data
    data = load_forex_data(
        symbol=args.symbol,
        timeframe=args.timeframe,
        start_date=args.start,
        end_date=args.end,
    )

    # Prepare features and target
    features, target, returns = prepare_features_and_target(data)

    # Compare different CV methods
    if args.compare:
        compare_cv_methods(
            features=features, target=target, returns=returns, model_type=args.model
        )
    else:
        # Run standard TimeSeriesWalkForwardCV
        logger.info("\nEvaluating with TimeSeriesWalkForwardCV...")
        ts_results = train_and_evaluate_with_time_series_cv(
            features=features,
            target=target,
            returns=returns,
            model_type=args.model,
            n_splits=args.n_splits,
        )

        # Visualize results
        visualize_cv_results(
            ts_results,
            title=f"{args.symbol} {args.timeframe} - TimeSeriesWalkForwardCV Results",
        )

        # Run BlockingTimeSeriesSplit
        logger.info("\nEvaluating with BlockingTimeSeriesSplit...")
        block_results = train_and_evaluate_with_blocking_cv(
            features=features,
            target=target,
            returns=returns,
            model_type=args.model,
            n_splits=args.n_splits,
            purge_window=5,
            embargo_size=5,
        )

        # Visualize results
        visualize_cv_results(
            block_results,
            title=f"{args.symbol} {args.timeframe} - BlockingTimeSeriesSplit Results",
        )


if __name__ == "__main__":
    main()
