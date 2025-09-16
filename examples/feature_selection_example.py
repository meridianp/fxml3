#!/usr/bin/env python
"""
Example script demonstrating feature selection capabilities in FXML4.

This script shows how to:
1. Create a synthetic dataset with redundant features
2. Apply different feature selection techniques
3. Compare performance of different selection methods
4. Visualize feature importance
5. Use ensemble feature selection

Usage:
    python examples/feature_selection_example.py
"""

import argparse
import logging
import os
import sys

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.datasets import make_classification, make_regression
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
from sklearn.metrics import accuracy_score, r2_score
from sklearn.model_selection import train_test_split

# Add the parent directory to the path to import the FXML4 package
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from fxml4.ml.feature_selection import (
    FeatureSelector,
    ensemble_feature_selection,
    find_optimal_feature_set,
    plot_feature_selection_comparison,
)
from fxml4.ml.features import (
    analyze_feature_correlations,
    permutation_importance_cv,
    select_features_mutual_info,
    select_features_random_forest,
)

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def create_synthetic_classification_data(
    n_samples=1000,
    n_features=20,
    n_informative=5,
    n_redundant=5,
    n_repeated=2,
    random_state=42,
):
    """Create a synthetic classification dataset with redundant features."""
    X, y = make_classification(
        n_samples=n_samples,
        n_features=n_features,
        n_informative=n_informative,
        n_redundant=n_redundant,
        n_repeated=n_repeated,
        random_state=random_state,
        n_classes=2,
        class_sep=1.5,
    )

    # Convert to DataFrame for better interpretability
    feature_names = [f"feature_{i}" for i in range(n_features)]
    X_df = pd.DataFrame(X, columns=feature_names)
    y_series = pd.Series(y, name="target")

    return X_df, y_series


def create_synthetic_regression_data(
    n_samples=1000, n_features=20, n_informative=5, random_state=42
):
    """Create a synthetic regression dataset with redundant features."""
    X, y = make_regression(
        n_samples=n_samples,
        n_features=n_features,
        n_informative=n_informative,
        random_state=random_state,
        noise=0.1,
    )

    # Add some correlated features
    X_df = pd.DataFrame(X, columns=[f"feature_{i}" for i in range(n_features)])

    # Add highly correlated versions of first 3 informative features
    for i in range(3):
        X_df[f"correlated_{i}"] = X_df[f"feature_{i}"] + np.random.normal(
            0, 0.1, size=n_samples
        )

    # Add some random noise features
    for i in range(5):
        X_df[f"noise_{i}"] = np.random.normal(0, 1, size=n_samples)

    y_series = pd.Series(y, name="target")

    return X_df, y_series


def evaluate_model(
    X_train, X_test, y_train, y_test, selected_features=None, task="classification"
):
    """Evaluate a model with selected features."""
    if selected_features is not None:
        X_train_selected = X_train[selected_features]
        X_test_selected = X_test[selected_features]
    else:
        X_train_selected = X_train
        X_test_selected = X_test

    if task == "classification":
        model = RandomForestClassifier(n_estimators=100, random_state=42)
        model.fit(X_train_selected, y_train)
        y_pred = model.predict(X_test_selected)
        score = accuracy_score(y_test, y_pred)
        metric = "accuracy"
    else:  # regression
        model = RandomForestRegressor(n_estimators=100, random_state=42)
        model.fit(X_train_selected, y_train)
        y_pred = model.predict(X_test_selected)
        score = r2_score(y_test, y_pred)
        metric = "r2 score"

    n_features = X_train_selected.shape[1]
    logger.info(f"Model with {n_features} features, {metric}: {score:.4f}")

    return score, model


def basic_feature_selection_example(task="classification"):
    """Demonstrate basic feature selection methods."""
    logger.info("=== Basic Feature Selection Example ===")

    # Create synthetic data
    if task == "classification":
        X, y = create_synthetic_classification_data()
        logger.info("Created synthetic classification dataset")
    else:
        X, y = create_synthetic_regression_data()
        logger.info("Created synthetic regression dataset")

    # Split data
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42
    )

    # Evaluate model with all features
    logger.info("Evaluating model with all features...")
    baseline_score, baseline_model = evaluate_model(
        X_train, X_test, y_train, y_test, task=task
    )

    # Analyze feature correlations
    logger.info("Analyzing feature correlations...")
    corr_result = analyze_feature_correlations(X_train, threshold=0.7, plot=True)

    # Try different feature selection methods
    methods = {
        "Random Forest": lambda: select_features_random_forest(
            X_train, y_train, k=10, plot=True
        ),
        "Mutual Information": lambda: select_features_mutual_info(
            X_train, y_train, k=10, plot=True
        ),
        "Permutation Importance": lambda: (
            None,  # X_selected is not returned by this function
            permutation_importance_cv(X_train, y_train, plot=True)["feature"]
            .iloc[:10]
            .tolist(),
        ),
    }

    results = {}

    for name, method in methods.items():
        logger.info(f"Selecting features with {name}...")
        result = method()

        if isinstance(result, tuple) and len(result) >= 2:
            _, selected_features = result[:2]
        else:
            selected_features = result

        score, _ = evaluate_model(
            X_train, X_test, y_train, y_test, selected_features, task=task
        )
        results[name] = {"selected_features": selected_features, "score": score}

    # Print summary
    logger.info("\nFeature Selection Results:")
    logger.info(f"Baseline ({X_train.shape[1]} features): {baseline_score:.4f}")

    for name, result in results.items():
        logger.info(
            f"{name} ({len(result['selected_features'])} features): {result['score']:.4f}"
        )
        logger.info(f"  Selected: {result['selected_features']}")

    return X_train, X_test, y_train, y_test, results


def advanced_feature_selection_example(
    X_train, X_test, y_train, y_test, task="classification"
):
    """Demonstrate advanced feature selection using FeatureSelector class."""
    logger.info("\n=== Advanced Feature Selection Example ===")

    # Create and fit feature selector with different methods
    methods = ["random_forest", "mutual_info", "permutation", "rfe", "sequential"]

    for method in methods:
        logger.info(f"\nSelecting features with method: {method}")

        # Create selector
        selector = FeatureSelector(
            method=method,
            k=10,
            cv=5,
            random_state=42,
            verbose=1,
            classification=(task == "classification"),
            remove_correlated=True,
        )

        # Fit selector
        selector.fit(X_train, y_train)

        # Plot feature importance
        selector.plot_importance()

        # Plot CV results
        selector.plot_cv_results()

        # Transform data
        X_train_selected = selector.transform(X_train)
        X_test_selected = selector.transform(X_test)

        # Evaluate model
        score, _ = evaluate_model(
            X_train_selected, X_test_selected, y_train, y_test, task=task
        )

        logger.info(
            f"Method: {method}, Score: {score:.4f}, Features: {selector.selected_features_}"
        )

    return methods


def optimal_feature_set_example(
    X_train, X_test, y_train, y_test, methods, task="classification"
):
    """Find the optimal feature set across methods and feature counts."""
    logger.info("\n=== Finding Optimal Feature Set ===")

    # Find optimal feature set
    results = find_optimal_feature_set(
        X_train,
        y_train,
        methods=methods,
        k_values=[5, 10, 15, 20, 25],
        cv=5,
        random_state=42,
        verbose=1,
        classification=(task == "classification"),
    )

    # Plot comparison
    plot_feature_selection_comparison(results)

    # Get best selector
    best_selector = results["best_selector"]

    # Transform data with best selector
    X_train_selected = best_selector.transform(X_train)
    X_test_selected = best_selector.transform(X_test)

    # Evaluate model
    score, _ = evaluate_model(
        X_train_selected, X_test_selected, y_train, y_test, task=task
    )

    logger.info(f"Best Method: {results['best_method']}")
    logger.info(f"Best k: {results['best_k']}")
    logger.info(f"Best Score: {results['best_score']:.4f}")
    logger.info(f"Test Score: {score:.4f}")
    logger.info(f"Selected Features: {best_selector.selected_features_}")

    return results


def ensemble_selection_example(
    X_train, X_test, y_train, y_test, methods, task="classification"
):
    """Demonstrate ensemble feature selection."""
    logger.info("\n=== Ensemble Feature Selection ===")

    # Perform ensemble selection
    selected_features, feature_importance = ensemble_feature_selection(
        X_train,
        y_train,
        methods=methods[:3],  # Use first 3 methods for ensemble
        k=10,
        cv=5,
        random_state=42,
        verbose=1,
        classification=(task == "classification"),
    )

    # Plot ensemble feature importance
    plt.figure(figsize=(10, 8))
    top_features = feature_importance.head(20).sort_values(
        "total_importance", ascending=True
    )
    plt.barh(np.arange(len(top_features)), top_features["total_importance"])
    plt.yticks(np.arange(len(top_features)), top_features["feature"])
    plt.xlabel("Ensemble Importance")
    plt.title("Ensemble Feature Importance")
    plt.tight_layout()
    plt.show()

    # Evaluate model
    score, _ = evaluate_model(
        X_train, X_test, y_train, y_test, selected_features, task=task
    )

    logger.info(f"Ensemble Selection Score: {score:.4f}")
    logger.info(f"Selected Features: {selected_features}")


def main():
    """Main function."""
    parser = argparse.ArgumentParser(description="FXML4 Feature Selection Example")
    parser.add_argument(
        "--task",
        choices=["classification", "regression"],
        default="classification",
        help="Type of task (classification or regression)",
    )
    args = parser.parse_args()

    # Run examples
    X_train, X_test, y_train, y_test, _ = basic_feature_selection_example(
        task=args.task
    )
    methods = advanced_feature_selection_example(
        X_train, X_test, y_train, y_test, task=args.task
    )
    optimal_feature_set_example(
        X_train, X_test, y_train, y_test, methods, task=args.task
    )
    ensemble_selection_example(
        X_train, X_test, y_train, y_test, methods, task=args.task
    )


if __name__ == "__main__":
    main()
