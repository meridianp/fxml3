#!/usr/bin/env python3
"""
Compare Performance of ML Models With and Without Exogenous Data

This script:
1. Loads models trained with and without exogenous features
2. Evaluates them on the same test dataset
3. Compares performance metrics visually and statistically
4. Generates reports on feature importance and model differences

Usage:
    python compare_models.py --baseline-model PATH --enhanced-model PATH [--plot]
"""

import argparse
import json
import logging
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import joblib
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.ticker import MaxNLocator

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Add project root to path to import from fxml4
project_root = Path(__file__).resolve().parent.parent
sys.path.append(str(project_root))

# Import FXML4 modules
from fxml4.ml.features import create_target_labels, scale_features
from fxml4.ml.models import ClassicMLModel


def load_model(model_path: str) -> Any:
    """
    Load model from file.

    Args:
        model_path: Path to model file

    Returns:
        Loaded model object
    """
    try:
        if model_path.endswith(".joblib"):
            model = joblib.load(model_path)
        elif model_path.endswith(".pkl"):
            import pickle

            with open(model_path, "rb") as f:
                model = pickle.load(f)
        else:
            # Try joblib as default
            model = joblib.load(model_path)

        logger.info(f"Successfully loaded model from {model_path}")

        # For wrapped models, extract the actual model
        if hasattr(model, "model"):
            return model.model
        return model

    except Exception as e:
        logger.error(f"Failed to load model from {model_path}: {e}")
        return None


def load_feature_info(model_path: str) -> Dict[str, Any]:
    """
    Load feature info for a model.

    Args:
        model_path: Path to model file

    Returns:
        Dictionary with feature information
    """
    # Try to infer feature info path
    if model_path.endswith(".joblib"):
        feature_info_path = model_path.replace(".joblib", "_features.json")
    elif model_path.endswith(".pkl"):
        feature_info_path = model_path.replace(".pkl", "_features.json")
    else:
        # Try model name + _features.json
        feature_info_path = f"{model_path}_features.json"

    if os.path.exists(feature_info_path):
        with open(feature_info_path, "r") as f:
            return json.load(f)
    else:
        # Try to find any _features.json file in the same directory
        directory = os.path.dirname(model_path)
        json_files = [f for f in os.listdir(directory) if f.endswith("_features.json")]

        if json_files:
            with open(os.path.join(directory, json_files[0]), "r") as f:
                return json.load(f)

    logger.warning(
        f"Could not find feature info for {model_path}, returning empty dict"
    )
    return {}


def load_test_data(
    symbol: str = "GBPUSD", year: int = 2023, month: int = 10
) -> pd.DataFrame:
    """
    Load test data for model comparison.

    Args:
        symbol: Symbol to load data for
        year: Year of test data
        month: Month of test data

    Returns:
        DataFrame with test data
    """
    from ml_optimization.optimize_with_exogenous import (
        load_historical_data,
        prepare_features_with_exogenous,
    )

    # Load raw data
    df = load_historical_data(symbol=symbol, years=[year], months=[month])

    if df is None or df.empty:
        logger.error(f"No test data available for {symbol} in {year}-{month}")
        return pd.DataFrame()

    # Create three versions of features:
    # 1. Base features (technical only)
    # 2. Technical + Economic
    # 3. Technical + Sentiment

    # Base version (technical only)
    df_base = prepare_features_with_exogenous(
        df, symbol, include_economic=False, include_sentiment=False
    )

    # Economic version
    df_eco = prepare_features_with_exogenous(
        df, symbol, include_economic=True, include_sentiment=False
    )

    # Full version (both economic and sentiment)
    df_full = prepare_features_with_exogenous(
        df, symbol, include_economic=True, include_sentiment=True
    )

    return {"base": df_base, "economic": df_eco, "full": df_full}


def evaluate_model_on_data(
    model: Any,
    data: pd.DataFrame,
    feature_info: Dict[str, Any],
    target_col: str = "target_10",
) -> Dict[str, Any]:
    """
    Evaluate a model on a dataset.

    Args:
        model: Trained model to evaluate
        data: DataFrame with test data
        feature_info: Feature information dictionary
        target_col: Target column name

    Returns:
        Dictionary with evaluation metrics
    """
    # Get the feature lists
    all_features = feature_info.get("all_features", [])
    selected_features = feature_info.get("selected_features", all_features)

    # Check if all required features are in the data
    missing_features = [f for f in selected_features if f not in data.columns]
    if missing_features:
        logger.warning(f"Missing {len(missing_features)} features from test data")

        # Use only available features
        available_features = [f for f in selected_features if f in data.columns]
        logger.info(
            f"Using {len(available_features)} available features out of {len(selected_features)}"
        )

        if len(available_features) < 0.7 * len(selected_features):
            logger.error("Too many missing features, evaluation may be inaccurate")
            return {}
    else:
        available_features = selected_features

    # Get target and features
    y_true = data[target_col]
    X_test = data[available_features]

    # Get future returns for financial metrics
    future_returns = data[f"future_return_{target_col.split('_')[-1]}"]

    # Make predictions
    try:
        if hasattr(model, "predict"):
            y_pred = model.predict(X_test)
        else:
            logger.error("Model does not have predict method")
            return {}

        # Evaluate with model's built-in method if available
        if hasattr(model, "evaluate"):
            metrics = model.evaluate(X_test, y_true, returns=future_returns, plot=False)

        else:
            # Manual evaluation
            from sklearn.metrics import (
                accuracy_score,
                f1_score,
                precision_score,
                recall_score,
            )

            accuracy = accuracy_score(y_true, y_pred)
            precision = precision_score(
                y_true, y_pred, average="weighted", zero_division=0
            )
            recall = recall_score(y_true, y_pred, average="weighted", zero_division=0)
            f1 = f1_score(y_true, y_pred, average="weighted", zero_division=0)

            metrics = {
                "accuracy": accuracy,
                "precision": precision,
                "recall": recall,
                "f1": f1,
            }

            # Calculate financial metrics if we have returns
            if future_returns is not None:
                metrics.update(calculate_financial_metrics(y_pred, future_returns))

        # Calculate confusion matrix
        confusion_matrix = pd.crosstab(
            y_true,
            y_pred,
            rownames=["Actual"],
            colnames=["Predicted"],
            normalize="index",
        )

        metrics["confusion_matrix"] = confusion_matrix

        # Get feature importance if available
        if hasattr(model, "get_feature_importance"):
            metrics["feature_importance"] = dict(
                zip(available_features, model.get_feature_importance())
            )
        elif hasattr(model, "feature_importances_"):
            metrics["feature_importance"] = dict(
                zip(available_features, model.feature_importances_)
            )

        return metrics

    except Exception as e:
        logger.error(f"Error evaluating model: {e}")
        return {}


def calculate_financial_metrics(
    predictions: np.ndarray, returns: pd.Series
) -> Dict[str, float]:
    """
    Calculate financial performance metrics.

    Args:
        predictions: Array of predicted signals (-1, 0, 1)
        returns: Series of actual returns

    Returns:
        Dictionary with financial metrics
    """
    # Filter out positions where prediction is 0 (no position)
    positions = np.array(predictions)

    # Calculate profit for each trade
    trade_returns = positions * returns.values

    # Calculate basic financial metrics
    win_mask = trade_returns > 0
    loss_mask = trade_returns < 0

    total_wins = np.sum(win_mask)
    total_losses = np.sum(loss_mask)

    # Win rate
    win_rate = total_wins / len(returns) if len(returns) > 0 else 0

    # Profit factor (sum of gains / sum of losses)
    total_gain = np.sum(trade_returns[win_mask]) if total_wins > 0 else 0
    total_loss = np.abs(np.sum(trade_returns[loss_mask])) if total_losses > 0 else 0
    profit_factor = total_gain / total_loss if total_loss > 0 else total_gain

    # Calculate equity curve
    equity_curve = (1 + trade_returns).cumprod()

    # Calculate drawdowns
    running_max = np.maximum.accumulate(equity_curve)
    drawdown = (equity_curve - running_max) / running_max
    max_drawdown = np.min(drawdown)

    # Calculate Sharpe ratio (annualized)
    sharpe_ratio = (
        np.mean(trade_returns) / np.std(trade_returns) * np.sqrt(252)
        if np.std(trade_returns) > 0
        else 0
    )

    # Create metrics dictionary
    metrics = {
        "profit_factor": profit_factor,
        "win_rate": win_rate,
        "sharpe_ratio": sharpe_ratio,
        "max_drawdown": max_drawdown,
    }

    return metrics


def create_comparison_plots(
    baseline_metrics: Dict[str, Any],
    enhanced_metrics: Dict[str, Dict[str, Any]],
    output_dir: str,
    include_feature_importance: bool = True,
) -> None:
    """
    Create comparison plots for baseline vs. enhanced models.

    Args:
        baseline_metrics: Metrics for baseline model
        enhanced_metrics: Dictionary mapping model type to metrics
        output_dir: Directory to save plots
        include_feature_importance: Whether to include feature importance plots
    """
    try:
        import seaborn as sns

        os.makedirs(output_dir, exist_ok=True)

        # Define model names and colors
        models = ["baseline"] + list(enhanced_metrics.keys())
        colors = ["lightblue", "lightgreen", "salmon"]

        # 1. Classification metrics comparison
        classification_metrics = ["accuracy", "precision", "recall", "f1"]

        fig, ax = plt.subplots(figsize=(10, 6))

        x = np.arange(len(classification_metrics))
        width = 0.2

        # Plot baseline
        baseline_values = [baseline_metrics[m] for m in classification_metrics]
        ax.bar(
            x - width,
            baseline_values,
            width,
            label="Baseline (Technical Only)",
            color=colors[0],
        )

        # Plot enhanced models
        for i, (model_type, metrics) in enumerate(enhanced_metrics.items()):
            model_values = [metrics[m] for m in classification_metrics]
            ax.bar(
                x + i * width,
                model_values,
                width,
                label=f"Enhanced ({model_type.title()})",
                color=colors[i + 1],
            )

        ax.set_xticks(x)
        ax.set_xticklabels(classification_metrics, rotation=0)
        ax.set_ylim(0, 1)
        ax.set_title("Classification Metrics Comparison")
        ax.set_ylabel("Score")
        ax.legend()

        plt.tight_layout()
        plt.savefig(os.path.join(output_dir, "classification_metrics_comparison.png"))

        # 2. Financial metrics comparison
        financial_metrics = [
            "profit_factor",
            "win_rate",
            "sharpe_ratio",
            "max_drawdown",
        ]

        fig, ax = plt.subplots(figsize=(10, 6))

        x = np.arange(len(financial_metrics))
        width = 0.2

        # Plot baseline
        baseline_values = [baseline_metrics.get(m, 0) for m in financial_metrics]
        ax.bar(
            x - width,
            baseline_values,
            width,
            label="Baseline (Technical Only)",
            color=colors[0],
        )

        # Plot enhanced models
        for i, (model_type, metrics) in enumerate(enhanced_metrics.items()):
            model_values = [metrics.get(m, 0) for m in financial_metrics]
            ax.bar(
                x + i * width,
                model_values,
                width,
                label=f"Enhanced ({model_type.title()})",
                color=colors[i + 1],
            )

        ax.set_xticks(x)
        ax.set_xticklabels(financial_metrics, rotation=0)
        ax.set_title("Financial Metrics Comparison")
        ax.set_ylabel("Score")
        ax.legend()

        plt.tight_layout()
        plt.savefig(os.path.join(output_dir, "financial_metrics_comparison.png"))

        # 3. Feature importance comparison
        if include_feature_importance:
            for model_name, metrics in {
                "baseline": baseline_metrics,
                **enhanced_metrics,
            }.items():
                if "feature_importance" not in metrics:
                    continue

                feature_importance = metrics["feature_importance"]

                # Sort by importance
                sorted_features = sorted(
                    feature_importance.items(), key=lambda x: x[1], reverse=True
                )

                # Plot top 20 features
                top_n = min(20, len(sorted_features))
                top_features = sorted_features[:top_n]

                fig, ax = plt.subplots(figsize=(10, 8))

                y_pos = np.arange(len(top_features))
                importances = [x[1] for x in top_features]
                feature_names = [x[0] for x in top_features]

                ax.barh(y_pos, importances, align="center")
                ax.set_yticks(y_pos)
                ax.set_yticklabels(feature_names)
                ax.invert_yaxis()  # labels read top-to-bottom
                ax.set_xlabel("Feature Importance")
                ax.set_title(f"Top {top_n} Features: {model_name.title()} Model")

                plt.tight_layout()
                plt.savefig(
                    os.path.join(output_dir, f"feature_importance_{model_name}.png")
                )

        # 4. Confusion matrix heatmaps
        for model_name, metrics in {
            "baseline": baseline_metrics,
            **enhanced_metrics,
        }.items():
            if "confusion_matrix" not in metrics:
                continue

            conf_matrix = metrics["confusion_matrix"]

            plt.figure(figsize=(8, 6))
            sns.heatmap(conf_matrix, annot=True, fmt=".2%", cmap="Blues")
            plt.title(f"Confusion Matrix: {model_name.title()} Model")
            plt.ylabel("Actual")
            plt.xlabel("Predicted")

            plt.tight_layout()
            plt.savefig(os.path.join(output_dir, f"confusion_matrix_{model_name}.png"))

        logger.info(f"Saved comparison plots to {output_dir}")

    except Exception as e:
        logger.error(f"Error creating comparison plots: {e}")


def main():
    """Main function for model comparison"""
    parser = argparse.ArgumentParser(
        description="Compare ML models with and without exogenous data"
    )
    parser.add_argument(
        "--baseline-model",
        type=str,
        help="Path to baseline model without exogenous features",
    )
    parser.add_argument(
        "--enhanced-model",
        type=str,
        help="Path to enhanced model with exogenous features",
    )
    parser.add_argument(
        "--test-symbol", type=str, default="GBPUSD", help="Symbol to use for test data"
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="ml_optimization/comparison_results",
        help="Directory to save comparison results",
    )
    parser.add_argument(
        "--plot",
        action="store_true",
        help="Generate and display plots (will save plots regardless)",
    )
    args = parser.parse_args()

    # Create output directory
    os.makedirs(args.output_dir, exist_ok=True)

    # Find models if not specified
    if args.baseline_model is None or args.enhanced_model is None:
        logger.info("Looking for models in results directory...")

        # Try to find models in results directory
        results_dir = "ml_optimization/results"

        if os.path.exists(results_dir):
            model_files = [f for f in os.listdir(results_dir) if f.endswith(".joblib")]

            # Try to identify baseline and enhanced models
            baseline_candidates = [
                f for f in model_files if "baseline" in f or "gbpusd_rf_" in f
            ]
            enhanced_candidates = [
                f for f in model_files if "exog" in f or "enhanced" in f
            ]

            if baseline_candidates and not args.baseline_model:
                args.baseline_model = os.path.join(results_dir, baseline_candidates[0])
                logger.info(f"Found baseline model: {args.baseline_model}")

            if enhanced_candidates and not args.enhanced_model:
                args.enhanced_model = os.path.join(results_dir, enhanced_candidates[0])
                logger.info(f"Found enhanced model: {args.enhanced_model}")

    # Ensure we have both models
    if not args.baseline_model or not args.enhanced_model:
        logger.error("Both baseline and enhanced models must be specified")
        return

    # 1. Load models
    baseline_model = load_model(args.baseline_model)
    enhanced_model = load_model(args.enhanced_model)

    if baseline_model is None or enhanced_model is None:
        logger.error("Failed to load models")
        return

    # 2. Load feature info
    baseline_features = load_feature_info(args.baseline_model)
    enhanced_features = load_feature_info(args.enhanced_model)

    # 3. Load test data
    test_data = load_test_data(args.test_symbol)

    if not test_data or not any(test_data.values()):
        logger.error("Failed to load test data")
        return

    # 4. Evaluate models on test data
    logger.info("Evaluating baseline model...")
    baseline_metrics = evaluate_model_on_data(
        baseline_model, test_data["base"], baseline_features
    )

    # Evaluate enhanced model with economic features
    logger.info("Evaluating enhanced model with economic features...")
    economic_metrics = evaluate_model_on_data(
        enhanced_model, test_data["economic"], enhanced_features
    )

    # Evaluate enhanced model with economic + sentiment features
    logger.info("Evaluating enhanced model with full features...")
    full_metrics = evaluate_model_on_data(
        enhanced_model, test_data["full"], enhanced_features
    )

    # 5. Create comparison plots
    logger.info("Creating comparison plots...")
    enhanced_metrics = {"economic": economic_metrics, "full": full_metrics}

    create_comparison_plots(
        baseline_metrics,
        enhanced_metrics,
        args.output_dir,
        include_feature_importance=True,
    )

    # 6. Print summary
    print("\nModel Comparison Summary")
    print("=======================")
    print(f"{'Metric':<15} {'Baseline':<10} {'Economic':<10} {'Full':<10}")
    print("-" * 45)

    for metric in ["accuracy", "f1", "profit_factor", "sharpe_ratio"]:
        baseline_val = baseline_metrics.get(metric, 0)
        economic_val = economic_metrics.get(metric, 0)
        full_val = full_metrics.get(metric, 0)

        print(f"{metric:<15} {baseline_val:.4f}   {economic_val:.4f}   {full_val:.4f}")

    # Calculate percentage improvements
    for metric in ["profit_factor", "sharpe_ratio"]:
        if baseline_metrics.get(metric, 0) > 0:
            eco_improvement = (
                economic_metrics.get(metric, 0) / baseline_metrics.get(metric, 1) - 1
            ) * 100
            full_improvement = (
                full_metrics.get(metric, 0) / baseline_metrics.get(metric, 1) - 1
            ) * 100

            print(f"\n{metric} improvement:")
            print(f"  Economic: {eco_improvement:+.2f}%")
            print(f"  Full: {full_improvement:+.2f}%")

    # Save metrics to JSON
    results = {
        "baseline": baseline_metrics,
        "economic": economic_metrics,
        "full": full_metrics,
        "test_symbol": args.test_symbol,
        "baseline_model": os.path.basename(args.baseline_model),
        "enhanced_model": os.path.basename(args.enhanced_model),
    }

    # Remove non-serializable objects
    for model_metrics in results.values():
        if isinstance(model_metrics, dict):
            if "confusion_matrix" in model_metrics:
                model_metrics.pop("confusion_matrix")

    # Write to file
    with open(os.path.join(args.output_dir, "comparison_results.json"), "w") as f:
        json.dump(results, f, indent=4, default=str)

    logger.info(
        f"Saved comparison results to {args.output_dir}/comparison_results.json"
    )

    # Show plots if requested
    if args.plot:
        try:
            import matplotlib.pyplot as plt

            plt.show()
        except Exception as e:
            logger.error(f"Error showing plots: {e}")


if __name__ == "__main__":
    main()
