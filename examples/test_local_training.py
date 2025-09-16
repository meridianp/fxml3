#!/usr/bin/env python3
"""
Test local model training for GBP/USD with the ML pipeline.

This script:
1. Prepares training data for GBP/USD
2. Trains different model types (Random Forest, XGBoost, Logistic Regression)
3. Evaluates model performance
4. Compares the models
5. Generates trading signals
"""

import logging
import os
import sys
import time
from datetime import datetime
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

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

# Import FXML4 modules
from fxml4.ml.gbpusd_model import GBPUSDModel
from fxml4.strategy.gbpusd_signal_generator import (
    GBPUSDSignalGenerator,
    SignalType,
    create_ensemble_generator,
)


def load_data(data_path):
    """Load market data from parquet file."""
    logger.info(f"Loading data from {data_path}")

    if not os.path.exists(data_path):
        logger.error(f"Data file not found: {data_path}")
        return None

    data = pd.read_parquet(data_path)
    logger.info(f"Loaded {len(data)} rows of data")

    return data


def prepare_features(data, model_type="random_forest"):
    """Prepare features for model training."""
    logger.info(f"Preparing features for {model_type} model")

    # Create model instance
    model = GBPUSDModel(model_type=model_type)

    # Prepare features
    features = model.prepare_features(
        data,
        target_horizon=12,  # 12 periods for 4h timeframe
        add_lag_features=True,
        create_target=True,
    )

    logger.info(f"Created {len(features)} rows with {len(features.columns)} features")

    # Split into train and test sets
    target_col = "target_12"
    train_size = 0.8
    split_idx = int(len(features) * train_size)

    train_features = features.iloc[:split_idx]
    test_features = features.iloc[split_idx:]

    logger.info(f"Training set: {len(train_features)} rows")
    logger.info(f"Test set: {len(test_features)} rows")

    return model, features, train_features, test_features, target_col


def train_and_evaluate(model, train_features, test_features, target_col):
    """Train and evaluate a model."""
    logger.info(f"Training {model.model_type} model")
    start_time = time.time()

    # Train the model
    train_results = model.train(
        train_features,
        target_col=target_col,
        test_size=0.2,  # Further split training data for validation
        use_cv=True,  # Use cross-validation
        n_splits=5,
    )

    training_time = time.time() - start_time
    logger.info(f"Training completed in {training_time:.2f} seconds")

    # Display top features
    top_features = model.get_top_features(n=10)
    logger.info(f"Top 10 features for {model.model_type}:")
    for _, row in top_features.iterrows():
        logger.info(f"  {row['feature']}: {row['importance']:.4f}")

    # Evaluate on test set
    X_test = test_features.drop(columns=[target_col])
    y_test = test_features[target_col]

    # Make predictions
    y_pred = model.predict(X_test)

    # Calculate metrics
    from sklearn.metrics import (
        accuracy_score,
        confusion_matrix,
        f1_score,
        precision_score,
        recall_score,
    )

    accuracy = accuracy_score(y_test, y_pred)
    precision = precision_score(y_test, y_pred, average="weighted")
    recall = recall_score(y_test, y_pred, average="weighted")
    f1 = f1_score(y_test, y_pred, average="weighted")
    conf_matrix = confusion_matrix(y_test, y_pred)

    logger.info(f"Test set metrics for {model.model_type}:")
    logger.info(f"  Accuracy: {accuracy:.4f}")
    logger.info(f"  Precision: {precision:.4f}")
    logger.info(f"  Recall: {recall:.4f}")
    logger.info(f"  F1 Score: {f1:.4f}")
    logger.info(f"  Confusion Matrix:\n{conf_matrix}")

    # Return model and evaluation metrics
    eval_metrics = {
        "accuracy": accuracy,
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "training_time": training_time,
        "confusion_matrix": conf_matrix,
    }

    return model, eval_metrics


def generate_signals(model, test_data):
    """Generate trading signals using the trained model."""
    logger.info(f"Generating signals with {model.model_type} model")

    # Create signal generator
    signal_generator = GBPUSDSignalGenerator(
        model=model,
        config={
            "threshold": 0.65,  # Confidence threshold
            "probability_mode": True,
            "signal_cooldown": 4 * 3600,  # 4 hours in seconds
        },
    )

    # Generate signals for test data
    signals = signal_generator.generate_signals(
        test_data, symbol="GBPUSD", timeframe="4h"
    )

    logger.info(f"Generated {len(signals)} signals")

    # Display signals
    if signals:
        logger.info("Signal details:")
        for i, signal in enumerate(signals):
            logger.info(f"  Signal {i+1}:")
            logger.info(f"    Type: {signal.signal_type}")
            logger.info(f"    Strength: {signal.strength:.4f}")
            logger.info(f"    Timestamp: {signal.timestamp}")
            logger.info(f"    Metadata: {signal.metadata}")

    # Run backtest
    backtest_results = signal_generator.backtest(test_data, target_horizon=12)

    if not backtest_results.empty:
        # Calculate performance metrics
        total_trades = len(backtest_results[backtest_results["prediction"] != 0])
        winning_trades = len(
            backtest_results[
                (backtest_results["prediction"] != 0)
                & (backtest_results["signal_return"] > 0)
            ]
        )
        win_rate = winning_trades / total_trades if total_trades > 0 else 0
        cumulative_return = backtest_results["cum_return"].iloc[-1]
        max_drawdown = backtest_results["drawdown"].min()

        logger.info(f"Backtest results for {model.model_type}:")
        logger.info(f"  Total trades: {total_trades}")
        logger.info(f"  Win rate: {win_rate:.4f}")
        logger.info(f"  Cumulative return: {cumulative_return:.4f}")
        logger.info(f"  Max drawdown: {max_drawdown:.4f}")

        # Calculate Sharpe ratio (assuming daily returns)
        returns = backtest_results["signal_return"].fillna(0)
        if len(returns) > 0 and returns.std() > 0:
            sharpe_ratio = (returns.mean() / returns.std()) * np.sqrt(252)
            logger.info(f"  Sharpe ratio: {sharpe_ratio:.4f}")

        return signals, backtest_results
    else:
        logger.warning("Backtest returned empty results")
        return signals, pd.DataFrame()


def create_ensemble(models, test_features, test_data, target_col):
    """Create and test an ensemble model."""
    logger.info(f"Creating ensemble model with {len(models)} base models")

    # Extract model names and create paths
    model_paths = []
    weights = []

    # Save models if not already saved
    os.makedirs("models", exist_ok=True)

    for model in models:
        model_name = model.name
        model_path = os.path.join("models", f"{model_name}.joblib")

        # Check if model is already saved
        if not os.path.exists(model_path):
            model.save(directory="models")

        model_paths.append((model_name, "models"))

        # Weight models by their F1 score on test data
        X_test = test_features.drop(columns=[target_col])
        y_test = test_features[target_col]
        y_pred = model.predict(X_test)
        f1 = f1_score(y_test, y_pred, average="weighted")
        weights.append(f1)

    # Normalize weights
    sum_weights = sum(weights)
    weights = [w / sum_weights for w in weights]

    # Create ensemble generator
    ensemble_generator = create_ensemble_generator(
        model_paths=model_paths,
        weights=weights,
        config={"threshold": 0.7, "probability_mode": True},
    )

    # Generate signals with ensemble
    logger.info("Generating signals with ensemble model")
    ensemble_signals = ensemble_generator.generate_signals(
        test_data, symbol="GBPUSD", timeframe="4h"
    )

    logger.info(f"Generated {len(ensemble_signals)} ensemble signals")

    # Display ensemble signals
    if ensemble_signals:
        logger.info("Ensemble signal details:")
        for i, signal in enumerate(ensemble_signals):
            logger.info(f"  Signal {i+1}:")
            logger.info(f"    Type: {signal.signal_type}")
            logger.info(f"    Strength: {signal.strength:.4f}")
            logger.info(f"    Timestamp: {signal.timestamp}")
            # Display weighted contributions
            weighted_signals = signal.metadata.get("weighted_signals", [])
            logger.info(f"    Contributions from {len(weighted_signals)} models:")
            for ws in weighted_signals:
                logger.info(
                    f"      {ws['model']}: {ws['contribution']:.4f} (strength: {ws['strength']:.4f}, weight: {ws['weight']:.4f})"
                )

    return ensemble_generator, ensemble_signals


def plot_results(models_results, backtest_results, save_path=None):
    """Plot comparison of model performances."""
    logger.info("Plotting model performance comparison")

    # Create figure with subplots
    fig, axes = plt.subplots(2, 2, figsize=(15, 10))
    fig.suptitle("GBP/USD Model Comparison", fontsize=16)

    # Plot metrics comparison
    metrics = ["accuracy", "precision", "recall", "f1"]
    model_names = list(models_results.keys())
    x = np.arange(len(model_names))
    width = 0.2

    for i, metric in enumerate(metrics):
        values = [models_results[model][metric] for model in model_names]
        axes[0, 0].bar(x + i * width, values, width, label=metric)

    axes[0, 0].set_xlabel("Model")
    axes[0, 0].set_ylabel("Score")
    axes[0, 0].set_title("Performance Metrics")
    axes[0, 0].set_xticks(x + width * 1.5)
    axes[0, 0].set_xticklabels(model_names)
    axes[0, 0].legend()
    axes[0, 0].grid(True, alpha=0.3)

    # Plot training time
    times = [models_results[model]["training_time"] for model in model_names]
    axes[0, 1].bar(model_names, times)
    axes[0, 1].set_xlabel("Model")
    axes[0, 1].set_ylabel("Time (seconds)")
    axes[0, 1].set_title("Training Time")
    axes[0, 1].grid(True, alpha=0.3)

    # Plot cumulative returns for each model
    for model in model_names:
        if (
            model in backtest_results
            and "cum_return" in backtest_results[model].columns
        ):
            returns = backtest_results[model]["cum_return"]
            axes[1, 0].plot(returns.index, returns, label=model)

    axes[1, 0].set_xlabel("Date")
    axes[1, 0].set_ylabel("Cumulative Return")
    axes[1, 0].set_title("Backtest Performance")
    axes[1, 0].legend()
    axes[1, 0].grid(True, alpha=0.3)

    # Plot signals by type
    signal_counts = {}
    for model in model_names:
        if (
            model in backtest_results
            and "prediction" in backtest_results[model].columns
        ):
            predictions = backtest_results[model]["prediction"]
            counts = predictions.value_counts()
            signal_counts[model] = [
                counts.get(1, 0),  # Long signals
                counts.get(-1, 0),  # Short signals
            ]

    if signal_counts:
        bars_positions = np.arange(len(model_names))
        bar_width = 0.35
        axes[1, 1].bar(
            bars_positions - bar_width / 2,
            [signal_counts[m][0] for m in model_names],
            bar_width,
            label="Long",
        )
        axes[1, 1].bar(
            bars_positions + bar_width / 2,
            [signal_counts[m][1] for m in model_names],
            bar_width,
            label="Short",
        )

        axes[1, 1].set_xlabel("Model")
        axes[1, 1].set_ylabel("Count")
        axes[1, 1].set_title("Signal Distribution")
        axes[1, 1].set_xticks(bars_positions)
        axes[1, 1].set_xticklabels(model_names)
        axes[1, 1].legend()
        axes[1, 1].grid(True, alpha=0.3)

    plt.tight_layout()

    # Save figure if path provided
    if save_path:
        plt.savefig(save_path)
        logger.info(f"Saved performance plot to {save_path}")

    plt.show()


def main():
    """Main function."""
    # Set paths
    data_path = "output/C_GBPUSD_4h.parquet"

    # Create output directory
    os.makedirs("output", exist_ok=True)

    # Load data
    data = load_data(data_path)
    if data is None:
        return 1

    # Initialize dictionaries to store results
    models = {}
    model_results = {}
    backtest_results = {}

    # Train and evaluate different model types
    model_types = ["random_forest", "xgboost", "logistic"]

    for model_type in model_types:
        logger.info(f"\n{'='*30}\nProcessing {model_type} model\n{'='*30}")

        # Prepare features
        model, features, train_features, test_features, target_col = prepare_features(
            data, model_type
        )

        # Train and evaluate model
        trained_model, eval_metrics = train_and_evaluate(
            model, train_features, test_features, target_col
        )

        # Generate signals
        signals, backtest_result = generate_signals(trained_model, test_features)

        # Store results
        models[model_type] = trained_model
        model_results[model_type] = eval_metrics
        backtest_results[model_type] = backtest_result

    # Create ensemble model
    ensemble_generator, ensemble_signals = create_ensemble(
        models=list(models.values()),
        test_features=test_features,
        test_data=test_features,
        target_col=target_col,
    )

    # Plot results
    plot_results(
        models_results=model_results,
        backtest_results=backtest_results,
        save_path="output/gbpusd_model_comparison.png",
    )

    # Save best model
    best_model = None
    best_f1 = -1

    for model_type, metrics in model_results.items():
        if metrics["f1"] > best_f1:
            best_f1 = metrics["f1"]
            best_model = models[model_type]

    if best_model:
        logger.info(
            f"Best model is {best_model.model_type} with F1 score of {best_f1:.4f}"
        )

        # Save the best model if not already saved
        os.makedirs("models/best", exist_ok=True)
        best_model.name = f"gbpusd_{best_model.model_type}_best"
        best_model.save(directory="models/best")

        logger.info(f"Saved best model to models/best/{best_model.name}")

    logger.info("Testing completed successfully")
    return 0


if __name__ == "__main__":
    sys.exit(main())
