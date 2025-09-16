"""
Training and Evaluation Module for ML Models in FXML4

This module provides utilities for training, validating, and evaluating machine
learning models for forex trading, including:
- Training pipelines for different model types
- Time series cross-validation
- Hyperparameter optimization
- Model evaluation with trading-specific metrics
- Visualization of results
"""

import json
import logging
import os
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.model_selection import TimeSeriesSplit

from fxml4.ml.models import ClassicMLModel, EnsembleModel, compare_models

logger = logging.getLogger(__name__)


def create_time_series_splits(
    X: pd.DataFrame,
    y: pd.Series,
    n_splits: int = 5,
    train_pct: float = 0.8,
    gap: int = 0,
) -> List[Tuple[np.ndarray, np.ndarray]]:
    """
    Create time series cross-validation splits.

    Args:
        X: Feature data
        y: Target data
        n_splits: Number of time series splits
        train_pct: Percentage of data used for training in each split
        gap: Number of samples to exclude between train and test sets

    Returns:
        List of (train_idx, test_idx) tuples
    """
    tscv = TimeSeriesSplit(n_splits=n_splits, gap=gap)
    splits = []

    for train_idx, test_idx in tscv.split(X):
        # If train_pct < 1.0, limit training data
        if train_pct < 1.0:
            train_size = int(len(train_idx) * train_pct)
            train_idx = train_idx[-train_size:]

        splits.append((train_idx, test_idx))

    return splits


def train_with_cv(
    model_type: str,
    X: pd.DataFrame,
    y: pd.Series,
    n_splits: int = 5,
    train_pct: float = 0.8,
    gap: int = 0,
    model_params: Optional[Dict[str, Any]] = None,
    future_returns: Optional[np.ndarray] = None,
    visualize: bool = True,
    figsize: Tuple[int, int] = (14, 10),
) -> Dict[str, Any]:
    """
    Train a model with time series cross-validation.

    Args:
        model_type: Type of model to train
        X: Feature data
        y: Target data
        n_splits: Number of time series splits
        train_pct: Percentage of data used for training in each split
        gap: Number of samples to exclude between train and test sets
        model_params: Parameters for the model
        future_returns: Future returns for trading metrics calculation
        visualize: Whether to visualize results
        figsize: Figure size for visualization

    Returns:
        Dictionary with cross-validation results
    """
    # Create time series splits
    splits = create_time_series_splits(X, y, n_splits, train_pct, gap)

    # Track evaluation metrics across splits
    metrics = {"accuracy": [], "precision": [], "recall": [], "f1": [], "models": []}

    # Add trading metrics if future returns are provided
    if future_returns is not None:
        trading_metrics = [
            "profit_factor",
            "win_rate",
            "max_drawdown",
            "calmar_ratio",
            "sharpe_ratio",
        ]

        for metric in trading_metrics:
            metrics[metric] = []

    # Train and evaluate model on each split
    for i, (train_idx, test_idx) in enumerate(splits):
        logger.info(f"Cross-validation split {i+1}/{n_splits}")

        # Split data
        X_train, X_test = X.iloc[train_idx], X.iloc[test_idx]
        y_train, y_test = y.iloc[train_idx], y.iloc[test_idx]

        # Create and train model
        model = ClassicMLModel(
            model_type=model_type,
            model_params=model_params,
            name=f"{model_type}_cv_split_{i+1}",
            n_classes=len(np.unique(y)),
            random_state=42,
        )

        model.train(X_train, y_train)

        # Prepare future returns for this split if provided
        split_returns = None
        if future_returns is not None:
            split_returns = future_returns[test_idx]

        # Evaluate model
        eval_metrics = model.evaluate(X_test, y_test, returns=split_returns, plot=False)

        # Store metrics
        metrics["accuracy"].append(eval_metrics["accuracy"])
        metrics["precision"].append(eval_metrics["precision"])
        metrics["recall"].append(eval_metrics["recall"])
        metrics["f1"].append(eval_metrics["f1"])
        metrics["models"].append(model)

        # Store trading metrics if available
        if future_returns is not None:
            for metric in trading_metrics:
                if metric in eval_metrics:
                    metrics[metric].append(eval_metrics[metric])

        logger.info(f"  Accuracy: {eval_metrics['accuracy']:.4f}")
        logger.info(f"  F1 Score: {eval_metrics['f1']:.4f}")

        if future_returns is not None and "profit_factor" in eval_metrics:
            logger.info(f"  Profit Factor: {eval_metrics['profit_factor']:.4f}")

    # Calculate mean and standard deviation for each metric
    summary = {}
    for metric in metrics.keys():
        if metric != "models":
            values = metrics[metric]
            summary[f"{metric}_mean"] = np.mean(values)
            summary[f"{metric}_std"] = np.std(values)
            summary[f"{metric}_values"] = values

    # Log summary results
    logger.info(f"Cross-validation results for {model_type}:")
    logger.info(
        f"  Accuracy: {summary['accuracy_mean']:.4f} ± {summary['accuracy_std']:.4f}"
    )
    logger.info(f"  F1 Score: {summary['f1_mean']:.4f} ± {summary['f1_std']:.4f}")

    if future_returns is not None and "profit_factor_mean" in summary:
        logger.info(
            f"  Profit Factor: {summary['profit_factor_mean']:.4f} ± {summary['profit_factor_std']:.4f}"
        )

    # Create visualization if requested
    if visualize:
        visualize_cv_results(metrics, future_returns is not None, figsize)

    # Return full results
    return {"metrics": metrics, "summary": summary}


def visualize_cv_results(
    metrics: Dict[str, List],
    has_trading_metrics: bool = False,
    figsize: Tuple[int, int] = (14, 10),
):
    """
    Visualize cross-validation results.

    Args:
        metrics: Dictionary with metric values across CV splits
        has_trading_metrics: Whether trading metrics are included
        figsize: Figure size for visualization
    """
    n_splits = len(metrics["accuracy"])

    # Create figure with appropriate subplots
    n_plots = 2 if has_trading_metrics else 1
    fig, axes = plt.subplots(1, n_plots, figsize=figsize)

    if n_plots == 1:
        axes = [axes]

    # Plot ML metrics
    ml_metrics = ["accuracy", "precision", "recall", "f1"]

    ml_means = [np.mean(metrics[m]) for m in ml_metrics]
    ml_stds = [np.std(metrics[m]) for m in ml_metrics]

    # Create bar plot for ML metrics
    axes[0].bar(ml_metrics, ml_means, yerr=ml_stds, capsize=10)
    axes[0].set_ylim(0, 1)
    axes[0].set_ylabel("Score")
    axes[0].set_title("ML Metrics")

    # Add values on top of bars
    for i, (mean, std) in enumerate(zip(ml_means, ml_stds)):
        axes[0].text(
            i,
            mean + std + 0.05,
            f"{mean:.4f} ± {std:.4f}",
            ha="center",
            va="bottom",
            fontsize=9,
        )

    # Add grid
    axes[0].grid(axis="y", alpha=0.3)

    # Plot trading metrics if available
    if has_trading_metrics:
        trading_metrics = [
            m
            for m in metrics.keys()
            if m in ["profit_factor", "win_rate", "sharpe_ratio"]
        ]

        if trading_metrics:
            # Create bar plot for trading metrics
            trading_values = []
            trading_labels = []
            trading_errors = []

            for m in trading_metrics:
                if m in metrics and len(metrics[m]) > 0:
                    mean = np.mean(metrics[m])
                    std = np.std(metrics[m])

                    trading_values.append(mean)
                    trading_errors.append(std)
                    trading_labels.append(m.replace("_", " ").title())

            if trading_values:
                axes[1].bar(
                    trading_labels, trading_values, yerr=trading_errors, capsize=10
                )
                axes[1].set_ylabel("Value")
                axes[1].set_title("Trading Metrics")

                # Add values on top of bars
                for i, (mean, std) in enumerate(zip(trading_values, trading_errors)):
                    axes[1].text(
                        i,
                        mean + std + 0.05,
                        f"{mean:.4f} ± {std:.4f}",
                        ha="center",
                        va="bottom",
                        fontsize=9,
                    )

                # Add grid
                axes[1].grid(axis="y", alpha=0.3)

    # Add overall title
    plt.suptitle(f"Cross-Validation Results ({n_splits} splits)", fontsize=16)
    plt.tight_layout(rect=[0, 0, 1, 0.95])
    plt.show()


def train_multiple_models(
    X_train: pd.DataFrame,
    y_train: pd.Series,
    X_test: pd.DataFrame,
    y_test: pd.Series,
    model_configs: List[Dict[str, Any]],
    create_ensemble: bool = True,
    future_returns: Optional[np.ndarray] = None,
    visualize: bool = True,
    figsize: Tuple[int, int] = (14, 10),
) -> Dict[str, Any]:
    """
    Train multiple models and optionally create an ensemble.

    Args:
        X_train: Training features
        y_train: Training targets
        X_test: Test features
        y_test: Test targets
        model_configs: List of model configuration dictionaries
                      Each dict should have 'model_type' and may have 'model_params' and 'name'
        create_ensemble: Whether to create an ensemble of the models
        future_returns: Future returns for trading metrics
        visualize: Whether to visualize results
        figsize: Figure size for visualization

    Returns:
        Dictionary with trained models and evaluation results
    """
    # List to track trained models
    models = []

    # Track evaluation metrics for each model
    model_metrics = []

    # Train each model
    for i, config in enumerate(model_configs):
        # Extract configuration
        model_type = config["model_type"]
        model_params = config.get("model_params", {})
        name = config.get("name", f"{model_type}_{i}")

        logger.info(f"Training model: {name}")

        # Create and train model
        model = ClassicMLModel(
            model_type=model_type,
            model_params=model_params,
            name=name,
            n_classes=len(np.unique(y_train)),
            random_state=42,
        )

        model.train(X_train, y_train)

        # Evaluate model
        metrics = model.evaluate(X_test, y_test, returns=future_returns, plot=False)

        # Log evaluation results
        logger.info(f"  Accuracy: {metrics['accuracy']:.4f}")
        logger.info(f"  F1 Score: {metrics['f1']:.4f}")

        if future_returns is not None and "profit_factor" in metrics:
            logger.info(f"  Profit Factor: {metrics['profit_factor']:.4f}")

        # Add model to list
        models.append(model)

        # Add metrics to list
        metrics["model_name"] = name
        metrics["model_type"] = model_type
        model_metrics.append(metrics)

    # Create ensemble if requested
    ensemble = None
    if create_ensemble and len(models) > 1:
        logger.info("Creating ensemble model")

        # Calculate weights based on F1 scores
        f1_scores = [m["f1"] for m in model_metrics]
        weights = [s / sum(f1_scores) for s in f1_scores]

        # Create ensemble
        ensemble = EnsembleModel(
            models=models,
            name="weighted_ensemble",
            ensemble_method="weighted",
            weights=weights,
        )

        # Evaluate ensemble
        ensemble_metrics = ensemble.evaluate(
            X_test, y_test, returns=future_returns, plot=False
        )

        # Log evaluation results
        logger.info(f"Ensemble Accuracy: {ensemble_metrics['accuracy']:.4f}")
        logger.info(f"Ensemble F1 Score: {ensemble_metrics['f1']:.4f}")

        if future_returns is not None and "profit_factor" in ensemble_metrics:
            logger.info(
                f"Ensemble Profit Factor: {ensemble_metrics['profit_factor']:.4f}"
            )

        # Add ensemble to models list
        models.append(ensemble)

        # Add ensemble metrics to list
        ensemble_metrics["model_name"] = "weighted_ensemble"
        ensemble_metrics["model_type"] = "ensemble"
        model_metrics.append(ensemble_metrics)

    # Create visualization if requested
    if visualize and len(models) > 0:
        # Use the compare_models function from models.py
        comparison_df = compare_models(
            models, X_test, y_test, future_returns, figsize=figsize
        )

    # Return results
    return {"models": models, "metrics": model_metrics, "ensemble": ensemble}


def optimize_hyperparameters(
    model_type: str,
    X_train: pd.DataFrame,
    y_train: pd.Series,
    X_val: pd.DataFrame,
    y_val: pd.Series,
    param_grid: Dict[str, List[Any]],
    future_returns: Optional[np.ndarray] = None,
    n_splits: int = 3,
    time_series: bool = True,
    metric: str = "f1",
    visualize: bool = True,
    figsize: Tuple[int, int] = (14, 10),
) -> Dict[str, Any]:
    """
    Optimize hyperparameters for a given model type.

    Args:
        model_type: Type of model to optimize
        X_train: Training features
        y_train: Training targets
        X_val: Validation features
        y_val: Validation targets
        param_grid: Parameter grid for hyperparameter search
        future_returns: Future returns for trading metrics
        n_splits: Number of cross-validation splits
        time_series: Whether to use time series cross-validation
        metric: Metric to optimize ('accuracy', 'f1', 'profit_factor', etc.)
        visualize: Whether to visualize results
        figsize: Figure size for visualization

    Returns:
        Dictionary with optimization results
    """
    logger.info(f"Optimizing hyperparameters for {model_type}")
    logger.info(f"Parameter grid: {param_grid}")

    # Create base model
    model = ClassicMLModel(
        model_type=model_type,
        name=f"{model_type}_optimizer",
        n_classes=len(np.unique(y_train)),
        random_state=42,
    )

    # Determine scoring based on metric
    scoring = "f1_weighted"
    if metric == "accuracy":
        scoring = "accuracy"
    elif metric == "profit_factor" and future_returns is not None:
        # For profit factor, we'll need a custom approach
        # We can't use GridSearchCV directly with trading metrics
        logger.info("Using custom optimization for trading metrics")
        return custom_hyperparameter_optimization(
            model_type,
            X_train,
            y_train,
            X_val,
            y_val,
            param_grid,
            future_returns,
            metric,
            visualize,
            figsize,
        )

    # Run hyperparameter tuning
    tuning_results = model.tune_hyperparameters(
        X_train,
        y_train,
        param_grid=param_grid,
        n_splits=n_splits,
        time_series=time_series,
        scoring=scoring,
        plot=visualize,
        figsize=figsize,
    )

    # Extract best parameters
    best_params = tuning_results["best_params"]
    best_score = tuning_results["best_score"]

    logger.info(f"Best parameters: {best_params}")
    logger.info(f"Best {metric} score: {best_score:.4f}")

    # Create and train model with best parameters
    best_model = ClassicMLModel(
        model_type=model_type,
        model_params=best_params,
        name=f"{model_type}_optimized",
        n_classes=len(np.unique(y_train)),
        random_state=42,
    )

    best_model.train(X_train, y_train)

    # Evaluate on validation set
    eval_metrics = best_model.evaluate(
        X_val, y_val, returns=future_returns, plot=visualize, figsize=figsize
    )

    logger.info(f"Validation accuracy: {eval_metrics['accuracy']:.4f}")
    logger.info(f"Validation F1 score: {eval_metrics['f1']:.4f}")

    if future_returns is not None and "profit_factor" in eval_metrics:
        logger.info(f"Validation profit factor: {eval_metrics['profit_factor']:.4f}")

    # Return results
    return {
        "best_params": best_params,
        "best_score": best_score,
        "best_model": best_model,
        "validation_metrics": eval_metrics,
        "tuning_results": tuning_results,
    }


def custom_hyperparameter_optimization(
    model_type: str,
    X_train: pd.DataFrame,
    y_train: pd.Series,
    X_val: pd.DataFrame,
    y_val: pd.Series,
    param_grid: Dict[str, List[Any]],
    future_returns: np.ndarray,
    metric: str = "profit_factor",
    visualize: bool = True,
    figsize: Tuple[int, int] = (14, 10),
) -> Dict[str, Any]:
    """
    Custom hyperparameter optimization for trading metrics.

    Args:
        model_type: Type of model to optimize
        X_train: Training features
        y_train: Training targets
        X_val: Validation features
        y_val: Validation targets
        param_grid: Parameter grid for hyperparameter search
        future_returns: Future returns for trading metrics
        metric: Trading metric to optimize
        visualize: Whether to visualize results
        figsize: Figure size for visualization

    Returns:
        Dictionary with optimization results
    """
    # Generate all parameter combinations
    from itertools import product

    param_names = list(param_grid.keys())
    param_values = [param_grid[name] for name in param_names]
    param_combinations = list(product(*param_values))

    logger.info(f"Testing {len(param_combinations)} parameter combinations")

    # Track results
    results = []

    # Test each parameter combination
    for i, combination in enumerate(param_combinations):
        # Create parameter dictionary
        params = {name: value for name, value in zip(param_names, combination)}

        logger.info(f"Combination {i+1}/{len(param_combinations)}: {params}")

        # Create and train model
        model = ClassicMLModel(
            model_type=model_type,
            model_params=params,
            name=f"{model_type}_test_{i}",
            n_classes=len(np.unique(y_train)),
            random_state=42,
        )

        model.train(X_train, y_train)

        # Evaluate on validation set
        metrics = model.evaluate(X_val, y_val, returns=future_returns, plot=False)

        # Record results
        result = {
            "params": params,
            "accuracy": metrics["accuracy"],
            "f1": metrics["f1"],
        }

        # Add trading metrics
        for key in [
            "profit_factor",
            "win_rate",
            "max_drawdown",
            "sharpe_ratio",
            "calmar_ratio",
        ]:
            if key in metrics:
                result[key] = metrics[key]

        results.append(result)

        # Log progress
        logger.info(f"  {metric}: {result.get(metric, 0):.4f}")

    # Find best parameters based on target metric
    if metric in results[0]:
        # Sort by target metric (descending for most metrics, ascending for drawdown)
        if metric == "max_drawdown":
            sorted_results = sorted(results, key=lambda x: x[metric])
        else:
            sorted_results = sorted(results, key=lambda x: x[metric], reverse=True)

        best_result = sorted_results[0]
        best_params = best_result["params"]
        best_score = best_result[metric]
    else:
        # Fall back to F1 score if metric not available
        logger.warning(f"Metric '{metric}' not available, falling back to F1 score")
        sorted_results = sorted(results, key=lambda x: x["f1"], reverse=True)
        best_result = sorted_results[0]
        best_params = best_result["params"]
        best_score = best_result["f1"]

    logger.info(f"Best parameters: {best_params}")
    logger.info(f"Best {metric} score: {best_score:.4f}")

    # Create and train model with best parameters
    best_model = ClassicMLModel(
        model_type=model_type,
        model_params=best_params,
        name=f"{model_type}_optimized",
        n_classes=len(np.unique(y_train)),
        random_state=42,
    )

    best_model.train(X_train, y_train)

    # Evaluate on validation set
    eval_metrics = best_model.evaluate(
        X_val, y_val, returns=future_returns, plot=visualize, figsize=figsize
    )

    # Visualize parameter grid results if requested
    if visualize:
        visualize_param_grid_results(results, param_grid, metric, figsize)

    # Return results
    return {
        "best_params": best_params,
        "best_score": best_score,
        "best_model": best_model,
        "validation_metrics": eval_metrics,
        "all_results": results,
    }


def visualize_param_grid_results(
    results: List[Dict[str, Any]],
    param_grid: Dict[str, List[Any]],
    metric: str,
    figsize: Tuple[int, int] = (14, 10),
):
    """
    Visualize parameter grid search results.

    Args:
        results: List of dictionaries with results for each parameter combination
        param_grid: Parameter grid used for search
        metric: Metric to visualize
        figsize: Figure size for visualization
    """
    # Check if we can visualize 1D or 2D plots
    param_names = list(param_grid.keys())

    if len(param_names) >= 2:
        # Create 2D visualization for first two parameters
        param1, param2 = param_names[:2]
        param1_values = param_grid[param1]
        param2_values = param_grid[param2]

        # Create a 2D grid of metric values
        grid = np.zeros((len(param1_values), len(param2_values)))

        # Fill grid
        for result in results:
            params = result["params"]
            value = result.get(metric, 0)

            # Find indices in grid
            idx1 = param1_values.index(params[param1])
            idx2 = param2_values.index(params[param2])

            grid[idx1, idx2] = value

        # Create visualization
        plt.figure(figsize=figsize)
        plt.imshow(grid, interpolation="nearest", cmap="viridis")
        plt.colorbar(label=metric)

        # Add labels
        plt.xticks(np.arange(len(param2_values)), param2_values)
        plt.yticks(np.arange(len(param1_values)), param1_values)

        plt.xlabel(param2)
        plt.ylabel(param1)
        plt.title(f"Grid Search Results for {metric}")

        # Add text annotations
        for i in range(len(param1_values)):
            for j in range(len(param2_values)):
                plt.text(
                    j,
                    i,
                    f"{grid[i, j]:.4f}",
                    ha="center",
                    va="center",
                    color="white" if grid[i, j] < np.max(grid) * 0.8 else "black",
                )

        plt.tight_layout()
        plt.show()

        # If more than 2 parameters, create 1D plots for other parameters
        if len(param_names) > 2:
            remaining_params = param_names[2:]

            # Create subplots
            n_remaining = len(remaining_params)
            fig, axes = plt.subplots(1, n_remaining, figsize=figsize)

            if n_remaining == 1:
                axes = [axes]

            # Create plot for each remaining parameter
            for i, param in enumerate(remaining_params):
                param_values = param_grid[param]

                # Group results by parameter value
                grouped_values = {value: [] for value in param_values}

                for result in results:
                    value = result["params"][param]
                    grouped_values[value].append(result.get(metric, 0))

                # Calculate mean for each parameter value
                means = [np.mean(grouped_values[value]) for value in param_values]

                # Plot
                axes[i].plot(param_values, means, marker="o")
                axes[i].set_xlabel(param)
                axes[i].set_ylabel(f"Mean {metric}")
                axes[i].set_title(f"Effect of {param}")

                # Add value labels
                for x, y in zip(param_values, means):
                    axes[i].text(x, y, f"{y:.4f}", ha="center", va="bottom")

            plt.tight_layout()
            plt.show()

    elif len(param_names) == 1:
        # Create 1D visualization
        param = param_names[0]
        param_values = param_grid[param]

        # Group results by parameter value
        grouped_values = {value: [] for value in param_values}

        for result in results:
            value = result["params"][param]
            grouped_values[value].append(result.get(metric, 0))

        # Calculate mean and std for each parameter value
        means = [np.mean(grouped_values[value]) for value in param_values]
        stds = [
            np.std(grouped_values[value]) if len(grouped_values[value]) > 1 else 0
            for value in param_values
        ]

        # Create visualization
        plt.figure(figsize=figsize)
        plt.errorbar(param_values, means, yerr=stds, marker="o", capsize=10)

        plt.xlabel(param)
        plt.ylabel(metric)
        plt.title(f"Parameter Search Results for {metric}")

        # Add value labels
        for x, y in zip(param_values, means):
            plt.text(x, y, f"{y:.4f}", ha="center", va="bottom")

        plt.grid(True, alpha=0.3)
        plt.tight_layout()
        plt.show()


def save_training_results(
    results: Dict[str, Any], directory: str = "results", name: str = None
) -> str:
    """
    Save training results to disk.

    Args:
        results: Dictionary with training results
        directory: Directory to save results
        name: Name for the results (default: auto-generated)

    Returns:
        Path to the saved results
    """
    # Create directory if it doesn't exist
    os.makedirs(directory, exist_ok=True)

    # Generate name if not provided
    if name is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        name = f"training_results_{timestamp}"

    # Create results subdirectory
    results_dir = os.path.join(directory, name)
    os.makedirs(results_dir, exist_ok=True)

    # Save models if available
    if "models" in results:
        models_dir = os.path.join(results_dir, "models")
        os.makedirs(models_dir, exist_ok=True)

        for model in results["models"]:
            model.save(models_dir)

    if "best_model" in results:
        models_dir = os.path.join(results_dir, "models")
        os.makedirs(models_dir, exist_ok=True)

        results["best_model"].save(models_dir)

    # Extract and save metadata
    metadata = {}

    # Save metrics
    if "metrics" in results:
        # If metrics is a list of dictionaries (per model metrics)
        if isinstance(results["metrics"], list):
            metadata["model_metrics"] = [
                {
                    k: v
                    for k, v in m.items()
                    if k not in ["confusion_matrix", "class_report"]
                }
                for m in results["metrics"]
            ]
        else:
            # If metrics is a dictionary (CV metrics)
            metadata["metrics"] = {
                k: v for k, v in results["metrics"].items() if k != "models"
            }

    # Save summary if available
    if "summary" in results:
        metadata["summary"] = results["summary"]

    # Save best parameters if available
    if "best_params" in results:
        metadata["best_params"] = results["best_params"]
        metadata["best_score"] = results["best_score"]

    # Save validation metrics if available
    if "validation_metrics" in results:
        metadata["validation_metrics"] = {
            k: v
            for k, v in results["validation_metrics"].items()
            if k not in ["confusion_matrix", "class_report"]
        }

    # Add timestamp
    metadata["timestamp"] = datetime.now().isoformat()

    # Save metadata
    metadata_path = os.path.join(results_dir, "metadata.json")
    with open(metadata_path, "w") as f:
        json.dump(metadata, f, indent=4)

    logger.info(f"Training results saved to {results_dir}")

    return results_dir
