#!/usr/bin/env python
"""Compare performance of different model configurations.

This script compares:
1. Single-symbol models
2. Multi-symbol models
3. Ensemble methods
"""

import argparse
import json
import logging
import sys
import warnings
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
)

warnings.filterwarnings("ignore")

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent))

from fxml4.ml.ensemble_models import (
    BlendingEnsemble,
    DynamicEnsemble,
    StackingEnsemble,
    VotingEnsemble,
)
from scripts.train_all_symbols import create_labels, prepare_data

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def load_single_symbol_model(symbol: str, model_type: str, models_dir: Path) -> Tuple:
    """Load a trained single-symbol model.

    Args:
        symbol: Trading symbol.
        model_type: Model type ('rf', 'xgb', 'lgb').
        models_dir: Models directory.

    Returns:
        Model, scaler, and selected features.
    """
    symbol_dir = models_dir / symbol

    if not symbol_dir.exists():
        raise FileNotFoundError(f"Model directory not found: {symbol_dir}")

    # Load model
    model_file = symbol_dir / f"model_{model_type}.joblib"
    if not model_file.exists():
        raise FileNotFoundError(f"Model file not found: {model_file}")

    model = joblib.load(model_file)

    # Load scaler
    scaler = joblib.load(symbol_dir / "scaler.joblib")

    # Load selected features
    with open(symbol_dir / "selected_features.json", "r") as f:
        selected_features = json.load(f)

    return model, scaler, selected_features


def evaluate_single_symbol_models(
    symbols: List[str],
    feature_dir: Path,
    models_dir: Path,
) -> Dict:
    """Evaluate single-symbol models on their respective test sets.

    Args:
        symbols: List of symbols.
        feature_dir: Feature directory.
        models_dir: Models directory.

    Returns:
        Dictionary of results.
    """
    results = {}

    for symbol in symbols:
        logger.info(f"\nEvaluating single-symbol model for {symbol}")

        try:
            # Load data
            X, y, feature_cols = prepare_data(symbol, feature_dir)

            # Load metadata to get best model
            with open(models_dir / symbol / "training_metadata.json", "r") as f:
                metadata = json.load(f)

            best_model_type = metadata["best_model"]
            model_type_map = {
                "random_forest": "rf",
                "xgboost": "xgb",
                "lightgbm": "lgb",
            }

            # Load model
            model, scaler, selected_features = load_single_symbol_model(
                symbol, model_type_map.get(best_model_type, "rf"), models_dir
            )

            # Prepare test data
            split_idx = int(len(X) * 0.8)
            X_test = X[split_idx:]
            y_test = y[split_idx:]

            # Select features and scale
            X_test_selected = X_test[selected_features]
            X_test_scaled = scaler.transform(X_test_selected)

            # Make predictions
            if best_model_type in ["xgboost", "lightgbm"]:
                y_pred = model.predict(X_test_scaled) - 1
            else:
                y_pred = model.predict(X_test_scaled)

            # Calculate metrics
            accuracy = accuracy_score(y_test, y_pred)
            f1 = f1_score(y_test, y_pred, average="macro")
            precision = precision_score(
                y_test, y_pred, average="macro", zero_division=0
            )
            recall = recall_score(y_test, y_pred, average="macro", zero_division=0)

            # Trading-specific metrics
            buy_signals = y_pred == 1
            sell_signals = y_pred == -1

            if buy_signals.sum() > 0:
                buy_accuracy = (y_test[buy_signals] == 1).mean()
            else:
                buy_accuracy = 0

            if sell_signals.sum() > 0:
                sell_accuracy = (y_test[sell_signals] == -1).mean()
            else:
                sell_accuracy = 0

            # Directional accuracy
            directional_mask = (y_pred != 0) & (y_test != 0)
            if directional_mask.sum() > 0:
                directional_accuracy = (
                    (y_pred[directional_mask] * y_test[directional_mask]) > 0
                ).mean()
            else:
                directional_accuracy = 0

            results[symbol] = {
                "model_type": best_model_type,
                "test_samples": len(y_test),
                "accuracy": accuracy,
                "f1_score": f1,
                "precision": precision,
                "recall": recall,
                "buy_accuracy": buy_accuracy,
                "sell_accuracy": sell_accuracy,
                "directional_accuracy": directional_accuracy,
                "n_buy_signals": buy_signals.sum(),
                "n_sell_signals": sell_signals.sum(),
                "n_hold_signals": (y_pred == 0).sum(),
            }

        except Exception as e:
            logger.error(f"Error evaluating {symbol}: {e}")
            results[symbol] = {"error": str(e)}

    return results


def evaluate_multi_symbol_model(
    symbols: List[str],
    feature_dir: Path,
    models_dir: Path,
) -> Dict:
    """Evaluate multi-symbol model on all symbols.

    Args:
        symbols: List of symbols.
        feature_dir: Feature directory.
        models_dir: Models directory.

    Returns:
        Dictionary of results.
    """
    logger.info("\nEvaluating multi-symbol model")

    multi_dir = models_dir / "multi_symbol"
    if not multi_dir.exists():
        return {"error": "Multi-symbol model not found"}

    try:
        # Load model and metadata
        model = joblib.load(multi_dir / "model_rf.joblib")
        scaler = joblib.load(multi_dir / "scaler.joblib")

        with open(multi_dir / "training_metadata.json", "r") as f:
            metadata = json.load(f)

        selected_features = metadata["selected_features"]

        # Prepare test data from all symbols
        all_X_test = []
        all_y_test = []
        symbol_indices = []

        for symbol in symbols:
            X, y, feature_cols = prepare_data(symbol, feature_dir)

            # Add symbol column
            X["symbol"] = symbol

            # Split data
            split_idx = int(len(X) * 0.8)
            X_test = X[split_idx:]
            y_test = y[split_idx:]

            all_X_test.append(X_test)
            all_y_test.append(y_test)
            symbol_indices.extend([symbol] * len(y_test))

        # Combine data
        X_test_combined = pd.concat(all_X_test, ignore_index=True)
        y_test_combined = pd.concat(all_y_test, ignore_index=True)

        # One-hot encode symbol
        X_test_combined = pd.get_dummies(
            X_test_combined, columns=["symbol"], prefix="symbol"
        )

        # Select features and scale
        X_test_selected = X_test_combined[selected_features]
        X_test_scaled = scaler.transform(X_test_selected)

        # Make predictions
        y_pred = model.predict(X_test_scaled)

        # Overall metrics
        accuracy = accuracy_score(y_test_combined, y_pred)
        f1 = f1_score(y_test_combined, y_pred, average="macro")

        # Per-symbol metrics
        symbol_results = {}
        symbol_indices = np.array(symbol_indices)

        for symbol in symbols:
            mask = symbol_indices == symbol
            if mask.sum() > 0:
                symbol_accuracy = accuracy_score(y_test_combined[mask], y_pred[mask])
                symbol_f1 = f1_score(
                    y_test_combined[mask], y_pred[mask], average="macro"
                )

                symbol_results[symbol] = {
                    "accuracy": symbol_accuracy,
                    "f1_score": symbol_f1,
                    "n_samples": mask.sum(),
                }

        return {
            "overall_accuracy": accuracy,
            "overall_f1": f1,
            "total_samples": len(y_test_combined),
            "symbol_results": symbol_results,
        }

    except Exception as e:
        logger.error(f"Error evaluating multi-symbol model: {e}")
        return {"error": str(e)}


def evaluate_ensemble_methods(
    symbols: List[str],
    feature_dir: Path,
    models_dir: Path,
) -> Dict:
    """Evaluate different ensemble methods.

    Args:
        symbols: List of symbols.
        feature_dir: Feature directory.
        models_dir: Models directory.

    Returns:
        Dictionary of results.
    """
    logger.info("\nEvaluating ensemble methods")

    results = {}

    # For simplicity, we'll ensemble models for a single symbol (EURUSD)
    test_symbol = "EURUSD"

    try:
        # Load data
        X, y, feature_cols = prepare_data(test_symbol, feature_dir)

        # Split data
        split_idx = int(len(X) * 0.8)
        X_train, X_test = X[:split_idx], X[split_idx:]
        y_train, y_test = y[:split_idx], y[split_idx:]

        # Load pre-trained models for ensemble
        base_models = []

        # Try to load different model types
        for model_type, file_suffix in [("rf", "rf"), ("xgb", "xgb"), ("lgb", "lgb")]:
            try:
                model, scaler, features = load_single_symbol_model(
                    test_symbol, file_suffix, models_dir
                )
                base_models.append((model_type, model))
            except:
                logger.warning(f"Could not load {model_type} model for {test_symbol}")

        if len(base_models) < 2:
            return {"error": "Not enough base models for ensemble"}

        # Select features and scale (using first model's features)
        _, scaler, selected_features = load_single_symbol_model(
            test_symbol, "rf", models_dir
        )

        X_train_selected = X_train[selected_features]
        X_test_selected = X_test[selected_features]

        X_train_scaled = scaler.transform(X_train_selected)
        X_test_scaled = scaler.transform(X_test_selected)

        # 1. Voting Ensemble (Soft)
        logger.info("Testing Voting Ensemble (Soft)...")
        voting_soft = VotingEnsemble(base_models, voting="soft")
        voting_soft.fit(X_train_scaled, y_train)

        y_pred_soft = voting_soft.predict(X_test_scaled)

        results["voting_soft"] = {
            "accuracy": accuracy_score(y_test, y_pred_soft),
            "f1_score": f1_score(y_test, y_pred_soft, average="macro"),
            "n_models": len(base_models),
        }

        # 2. Voting Ensemble (Hard)
        logger.info("Testing Voting Ensemble (Hard)...")
        voting_hard = VotingEnsemble(base_models, voting="hard")
        voting_hard.fit(X_train_scaled, y_train)

        y_pred_hard = voting_hard.predict(X_test_scaled)

        results["voting_hard"] = {
            "accuracy": accuracy_score(y_test, y_pred_hard),
            "f1_score": f1_score(y_test, y_pred_hard, average="macro"),
            "n_models": len(base_models),
        }

        # 3. Stacking Ensemble
        logger.info("Testing Stacking Ensemble...")
        meta_model = LogisticRegression(max_iter=1000, random_state=42)
        stacking = StackingEnsemble(base_models, meta_model, cv_folds=3)
        stacking.fit(X_train_scaled, y_train)

        y_pred_stack = stacking.predict(X_test_scaled)

        results["stacking"] = {
            "accuracy": accuracy_score(y_test, y_pred_stack),
            "f1_score": f1_score(y_test, y_pred_stack, average="macro"),
            "meta_model": "LogisticRegression",
            "n_base_models": len(base_models),
        }

        # 4. Blending Ensemble
        logger.info("Testing Blending Ensemble...")
        blending = BlendingEnsemble(
            base_models,
            LogisticRegression(max_iter=1000, random_state=42),
            blend_size=0.2,
        )
        blending.fit(X_train_scaled, y_train)

        y_pred_blend = blending.predict(X_test_scaled)

        results["blending"] = {
            "accuracy": accuracy_score(y_test, y_pred_blend),
            "f1_score": f1_score(y_test, y_pred_blend, average="macro"),
            "blend_size": 0.2,
            "n_base_models": len(base_models),
        }

        # 5. Compare with best single model
        best_single_accuracy = 0
        best_single_name = None

        for name, model in base_models:
            if hasattr(model, "predict"):
                y_pred_single = model.predict(X_test_scaled)
                if name in ["xgb", "lgb"]:
                    y_pred_single = y_pred_single - 1

                acc = accuracy_score(y_test, y_pred_single)
                if acc > best_single_accuracy:
                    best_single_accuracy = acc
                    best_single_name = name

        results["best_single_model"] = {
            "name": best_single_name,
            "accuracy": best_single_accuracy,
        }

    except Exception as e:
        logger.error(f"Error evaluating ensemble methods: {e}")
        results["error"] = str(e)

    return results


def create_comparison_report(
    single_symbol_results: Dict,
    multi_symbol_results: Dict,
    ensemble_results: Dict,
    output_file: Path,
) -> None:
    """Create a comprehensive comparison report.

    Args:
        single_symbol_results: Results from single-symbol models.
        multi_symbol_results: Results from multi-symbol model.
        ensemble_results: Results from ensemble methods.
        output_file: Output file path.
    """
    report = []
    report.append("# Model Comparison Report")
    report.append(f"\nGenerated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # Single-Symbol Models
    report.append("\n## Single-Symbol Models")
    report.append(
        "\n| Symbol | Model | Accuracy | F1-Score | Buy Acc | Sell Acc | Direction |"
    )
    report.append(
        "|--------|-------|----------|----------|---------|----------|-----------|"
    )

    for symbol, results in single_symbol_results.items():
        if "error" not in results:
            report.append(
                f"| {symbol} | {results['model_type']} | "
                f"{results['accuracy']:.4f} | {results['f1_score']:.4f} | "
                f"{results['buy_accuracy']:.4f} | {results['sell_accuracy']:.4f} | "
                f"{results['directional_accuracy']:.4f} |"
            )

    # Average metrics
    if single_symbol_results:
        avg_accuracy = np.mean(
            [r["accuracy"] for r in single_symbol_results.values() if "error" not in r]
        )
        avg_f1 = np.mean(
            [r["f1_score"] for r in single_symbol_results.values() if "error" not in r]
        )
        report.append(f"\n**Average Single-Symbol Performance:**")
        report.append(f"- Accuracy: {avg_accuracy:.4f}")
        report.append(f"- F1-Score: {avg_f1:.4f}")

    # Multi-Symbol Model
    report.append("\n## Multi-Symbol Model")

    if "error" not in multi_symbol_results:
        report.append(f"\n**Overall Performance:**")
        report.append(f"- Accuracy: {multi_symbol_results['overall_accuracy']:.4f}")
        report.append(f"- F1-Score: {multi_symbol_results['overall_f1']:.4f}")
        report.append(f"- Total Samples: {multi_symbol_results['total_samples']}")

        if "symbol_results" in multi_symbol_results:
            report.append("\n**Per-Symbol Performance:**")
            report.append("\n| Symbol | Accuracy | F1-Score | Samples |")
            report.append("|--------|----------|----------|---------|")

            for symbol, metrics in multi_symbol_results["symbol_results"].items():
                report.append(
                    f"| {symbol} | {metrics['accuracy']:.4f} | "
                    f"{metrics['f1_score']:.4f} | {metrics['n_samples']} |"
                )
    else:
        report.append(f"\nError: {multi_symbol_results['error']}")

    # Ensemble Methods
    report.append("\n## Ensemble Methods")

    if ensemble_results and "error" not in ensemble_results:
        report.append("\n| Method | Accuracy | F1-Score | Details |")
        report.append("|--------|----------|----------|---------|")

        for method, results in ensemble_results.items():
            if method != "best_single_model" and isinstance(results, dict):
                details = f"n_models={results.get('n_models', 'N/A')}"
                if "meta_model" in results:
                    details = f"meta={results['meta_model']}"
                elif "blend_size" in results:
                    details = f"blend={results['blend_size']}"

                report.append(
                    f"| {method} | {results['accuracy']:.4f} | "
                    f"{results['f1_score']:.4f} | {details} |"
                )

        if "best_single_model" in ensemble_results:
            best = ensemble_results["best_single_model"]
            report.append(
                f"\n**Best Single Model:** {best['name']} (Accuracy: {best['accuracy']:.4f})"
            )

    # Key Insights
    report.append("\n## Key Insights")

    # Compare single vs multi
    if single_symbol_results and "error" not in multi_symbol_results:
        avg_single = np.mean(
            [r["accuracy"] for r in single_symbol_results.values() if "error" not in r]
        )
        multi_acc = multi_symbol_results["overall_accuracy"]

        if multi_acc > avg_single:
            report.append(
                f"\n1. **Multi-symbol model outperforms** average single-symbol models "
                f"({multi_acc:.4f} vs {avg_single:.4f})"
            )
        else:
            report.append(
                f"\n1. **Single-symbol models perform better** on average than multi-symbol model "
                f"({avg_single:.4f} vs {multi_acc:.4f})"
            )

    # Ensemble performance
    if ensemble_results and "error" not in ensemble_results:
        best_ensemble = max(
            [
                (k, v["accuracy"])
                for k, v in ensemble_results.items()
                if k != "best_single_model" and isinstance(v, dict)
            ],
            key=lambda x: x[1],
        )

        if "best_single_model" in ensemble_results:
            single_acc = ensemble_results["best_single_model"]["accuracy"]
            if best_ensemble[1] > single_acc:
                report.append(
                    f"\n2. **Ensemble methods improve performance**: "
                    f"{best_ensemble[0]} achieves {best_ensemble[1]:.4f} vs "
                    f"best single model {single_acc:.4f}"
                )

    # Write report
    with open(output_file, "w") as f:
        f.write("\n".join(report))

    logger.info(f"\nReport saved to: {output_file}")


def main():
    """Main comparison function."""
    parser = argparse.ArgumentParser(description="Compare model performance")
    parser.add_argument(
        "--symbols",
        nargs="+",
        default=["EURUSD", "GBPUSD", "USDJPY", "USDCHF"],
        help="Symbols to evaluate",
    )
    args = parser.parse_args()

    # Setup directories
    project_dir = Path(__file__).parent.parent
    feature_dir = project_dir / "data" / "features"
    models_dir = project_dir / "models"

    logger.info("=" * 80)
    logger.info("MODEL COMPARISON ANALYSIS")
    logger.info("=" * 80)

    # 1. Evaluate single-symbol models
    logger.info("\n1. Evaluating Single-Symbol Models")
    single_symbol_results = evaluate_single_symbol_models(
        args.symbols, feature_dir, models_dir
    )

    # 2. Evaluate multi-symbol model
    logger.info("\n2. Evaluating Multi-Symbol Model")
    multi_symbol_results = evaluate_multi_symbol_model(
        args.symbols, feature_dir, models_dir
    )

    # 3. Evaluate ensemble methods
    logger.info("\n3. Evaluating Ensemble Methods")
    ensemble_results = evaluate_ensemble_methods(args.symbols, feature_dir, models_dir)

    # 4. Create comparison report
    output_file = project_dir / "MODEL_COMPARISON_REPORT.md"
    create_comparison_report(
        single_symbol_results, multi_symbol_results, ensemble_results, output_file
    )

    # Summary
    logger.info("\n" + "=" * 80)
    logger.info("COMPARISON SUMMARY")
    logger.info("=" * 80)

    # Best single-symbol model
    if single_symbol_results:
        best_single = max(
            [
                (k, v["accuracy"])
                for k, v in single_symbol_results.items()
                if "error" not in v
            ],
            key=lambda x: x[1],
        )
        logger.info(
            f"\nBest Single-Symbol Model: {best_single[0]} (Accuracy: {best_single[1]:.4f})"
        )

    # Multi-symbol performance
    if "error" not in multi_symbol_results:
        logger.info(
            f"Multi-Symbol Model Accuracy: {multi_symbol_results['overall_accuracy']:.4f}"
        )

    # Best ensemble
    if ensemble_results and "error" not in ensemble_results:
        best_ensemble = max(
            [
                (k, v["accuracy"])
                for k, v in ensemble_results.items()
                if k != "best_single_model" and isinstance(v, dict)
            ],
            key=lambda x: x[1],
        )
        logger.info(
            f"Best Ensemble Method: {best_ensemble[0]} (Accuracy: {best_ensemble[1]:.4f})"
        )


if __name__ == "__main__":
    main()
