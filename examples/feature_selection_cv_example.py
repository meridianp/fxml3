#!/usr/bin/env python
"""
Example script demonstrating cross-validation for feature selection in FXML4.

This script shows how to:
1. Use cross-validation to find optimal feature subsets
2. Evaluate feature selection stability across CV folds
3. Compare feature selection methods with cross-validation
4. Visualize the results of cross-validated feature selection

Usage:
    python examples/feature_selection_cv_example.py
"""

import argparse
import logging
import os
import sys
from typing import Dict, List, Tuple

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.datasets import make_classification, make_regression
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
from sklearn.metrics import accuracy_score, mean_squared_error, r2_score
from sklearn.model_selection import KFold, StratifiedKFold, train_test_split

# Add the parent directory to the path to import the FXML4 package
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from fxml4.ml.feature_selection import (
    FeatureSelector,
    find_optimal_feature_set,
    plot_feature_selection_comparison,
)
from fxml4.ml.features import (
    analyze_feature_correlations,
    analyze_feature_importance_stability,
    cross_validate_feature_selection,
    recursive_elimination_with_cv,
    select_features_random_forest,
)

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def create_dataset(
    task="classification",
    n_samples=1000,
    n_features=20,
    n_informative=5,
    add_noise=True,
    random_state=42,
):
    """Create a synthetic dataset for feature selection examples."""
    if task == "classification":
        X, y = make_classification(
            n_samples=n_samples,
            n_features=n_features,
            n_informative=n_informative,
            n_redundant=int(n_features * 0.2),
            n_repeated=int(n_features * 0.1),
            class_sep=1.5,
            random_state=random_state,
        )
    else:  # regression
        X, y = make_regression(
            n_samples=n_samples,
            n_features=n_features,
            n_informative=n_informative,
            noise=0.1,
            random_state=random_state,
        )

    # Convert to DataFrame
    X_df = pd.DataFrame(X, columns=[f"feature_{i}" for i in range(n_features)])
    y_series = pd.Series(y, name="target")

    # Add correlated features
    for i in range(3):
        X_df[f"correlated_{i}"] = X_df[f"feature_{i}"] + np.random.normal(
            0, 0.1, size=n_samples
        )

    # Add noisy features
    if add_noise:
        for i in range(5):
            X_df[f"noise_{i}"] = np.random.normal(0, 1, size=n_samples)

    # For classification, convert target to binary
    if task == "classification":
        y_series = pd.Series((y > 0).astype(int), name="target")

    logger.info(f"Created {task} dataset with {X_df.shape[1]} features")
    logger.info(f"  {n_informative} informative features")
    logger.info(f"  3 correlated features")
    logger.info(f"  {5 if add_noise else 0} pure noise features")

    return X_df, y_series


def demonstrate_feature_stability(X, y, task="classification"):
    """Demonstrate feature importance stability across data samples."""
    logger.info("\n=== Feature Importance Stability Analysis ===")

    # Define feature selector function
    def rf_selector(X, y):
        return select_features_random_forest(X, y, k=10, plot=False)

    # Analyze stability
    stability_df = analyze_feature_importance_stability(
        X,
        y,
        feature_selector=rf_selector,
        n_iterations=20,
        sample_fraction=0.8,
        plot=True,
    )

    # Print most stable features
    logger.info("Most stable features by importance:")
    most_stable = stability_df.sort_values("cv_importance").head(10)
    for _, row in most_stable.iterrows():
        logger.info(
            f"  {row['feature']}: avg_importance={row['avg_importance']:.4f}, CV={row['cv_importance']:.4f}"
        )

    # Print most frequently selected features
    logger.info("\nMost frequently selected features:")
    most_frequent = stability_df.sort_values(
        "selection_frequency", ascending=False
    ).head(10)
    for _, row in most_frequent.iterrows():
        logger.info(
            f"  {row['feature']}: selection_frequency={row['selection_frequency']:.2f}"
        )

    return stability_df


def demonstrate_cross_validated_feature_selection(X, y, task="classification"):
    """Demonstrate cross-validated feature selection."""
    logger.info("\n=== Cross-Validated Feature Selection ===")

    # Create base model
    if task == "classification":
        model = RandomForestClassifier(n_estimators=100, random_state=42)
    else:
        model = RandomForestRegressor(n_estimators=100, random_state=42)

    # Define feature selector function
    def rf_selector(X, y):
        return select_features_random_forest(X, y, k=10, plot=False)[
            :2
        ]  # Return X_selected, features

    # Perform CV
    stability_df, cv_results = cross_validate_feature_selection(
        X,
        y,
        estimator=model,
        feature_selector=rf_selector,
        cv=5,
        plot=True,
        classification=(task == "classification"),
    )

    # Print results
    logger.info(f"Full model score: {cv_results['avg_full_score']:.4f}")
    logger.info(
        f"Selected features model score: {cv_results['avg_selected_score']:.4f}"
    )
    logger.info(
        f"Average number of selected features: {cv_results['avg_n_features']:.1f} / {X.shape[1]}"
    )

    # Print most stable features
    logger.info("\nMost stable features across CV folds:")
    most_stable = stability_df.sort_values("selection_frequency", ascending=False).head(
        10
    )
    for _, row in most_stable.iterrows():
        logger.info(
            f"  {row['feature']}: selection_frequency={row['selection_frequency']:.2f}"
        )

    return stability_df, cv_results


def demonstrate_rfecv(X, y, task="classification"):
    """Demonstrate recursive feature elimination with cross-validation."""
    logger.info("\n=== Recursive Feature Elimination with CV ===")

    # Create base model
    if task == "classification":
        model = RandomForestClassifier(n_estimators=100, random_state=42)
    else:
        model = RandomForestRegressor(n_estimators=100, random_state=42)

    # Perform RFECV
    selected_features, cv_results = recursive_elimination_with_cv(
        X,
        y,
        estimator=model,
        step=1,
        min_features=5,
        cv=5,
        classification=(task == "classification"),
        plot=True,
    )

    # Print results
    logger.info(f"Selected {len(selected_features)} features with RFECV")
    logger.info(f"Selected features: {selected_features}")

    # Print optimal number of features
    logger.info(f"Optimal number of features: {cv_results['n_features']}")

    # Print feature ranking
    ranking = pd.DataFrame(
        {"feature": X.columns, "ranking": cv_results["ranking"]}
    ).sort_values("ranking")

    logger.info("\nFeature ranking (lower is better):")
    for _, row in ranking.head(10).iterrows():
        logger.info(f"  {row['feature']}: {row['ranking']}")

    return selected_features, cv_results


def compare_cv_methods(X, y, task="classification"):
    """Compare different feature selection methods with cross-validation."""
    logger.info("\n=== Comparing Feature Selection Methods with CV ===")

    # Split data into train and test sets
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42
    )

    # Define methods to compare
    methods = ["random_forest", "mutual_info", "permutation", "rfe", "sequential"]
    k_values = [5, 10, 15, 20]

    # Find optimal feature set
    results = find_optimal_feature_set(
        X_train,
        y_train,
        methods=methods,
        k_values=k_values,
        cv=5,
        random_state=42,
        verbose=1,
        classification=(task == "classification"),
    )

    # Plot comparison
    plot_feature_selection_comparison(results)

    # Evaluate best method on test set
    best_selector = results["best_selector"]
    X_test_selected = best_selector.transform(X_test)

    # Create and fit model
    if task == "classification":
        model = RandomForestClassifier(n_estimators=100, random_state=42)
        model.fit(X_train[best_selector.selected_features_], y_train)
        y_pred = model.predict(X_test_selected)
        score = accuracy_score(y_test, y_pred)
        metric = "accuracy"
    else:
        model = RandomForestRegressor(n_estimators=100, random_state=42)
        model.fit(X_train[best_selector.selected_features_], y_train)
        y_pred = model.predict(X_test_selected)
        score = r2_score(y_test, y_pred)
        mse = mean_squared_error(y_test, y_pred)
        metric = f"r2={score:.4f}, mse={mse:.4f}"

    # Print results
    logger.info(f"Best method: {results['best_method']}")
    logger.info(f"Best k: {results['best_k']}")
    logger.info(f"Best CV score: {results['best_score']:.4f}")
    logger.info(f"Test set {metric}")
    logger.info(f"Selected features: {best_selector.selected_features_}")

    return results


def demonstrate_correlation_aware_selection(X, y, task="classification"):
    """Demonstrate correlation-aware feature selection."""
    logger.info("\n=== Correlation-Aware Feature Selection ===")

    # Analyze feature correlations
    corr_df, clusters = analyze_feature_correlations(
        X, threshold=0.7, plot=True, return_clusters=True
    )

    if len(clusters) > 0:
        logger.info(f"Found {len(clusters)} correlation clusters:")
        for i, cluster in enumerate(clusters):
            logger.info(f"  Cluster {i+1}: {cluster}")
    else:
        logger.info("No strong correlations found with threshold 0.7")

    # Create feature selectors with and without correlation removal
    selector_with_corr = FeatureSelector(
        method="random_forest",
        k=10,
        remove_correlated=True,
        correlation_threshold=0.7,
        cv=5,
        random_state=42,
        verbose=1,
        classification=(task == "classification"),
    )

    selector_without_corr = FeatureSelector(
        method="random_forest",
        k=10,
        remove_correlated=False,
        cv=5,
        random_state=42,
        verbose=1,
        classification=(task == "classification"),
    )

    # Fit selectors
    selector_with_corr.fit(X, y)
    selector_without_corr.fit(X, y)

    # Print selected features
    logger.info("\nFeatures selected WITH correlation removal:")
    logger.info(f"  {selector_with_corr.selected_features_}")

    logger.info("\nFeatures selected WITHOUT correlation removal:")
    logger.info(f"  {selector_without_corr.selected_features_}")

    # Print CV scores
    logger.info("\nCV scores:")
    logger.info(
        f"  WITH correlation removal: {selector_with_corr.cv_results_['mean_selected_score']:.4f}"
    )
    logger.info(
        f"  WITHOUT correlation removal: {selector_without_corr.cv_results_['mean_selected_score']:.4f}"
    )

    # Plot feature importance
    selector_with_corr.plot_importance()
    selector_without_corr.plot_importance()

    return selector_with_corr, selector_without_corr


def main():
    """Main function."""
    parser = argparse.ArgumentParser(
        description="FXML4 Feature Selection with CV Example"
    )
    parser.add_argument(
        "--task",
        choices=["classification", "regression"],
        default="classification",
        help="Type of task (classification or regression)",
    )
    parser.add_argument(
        "--n_features",
        type=int,
        default=30,
        help="Number of features in synthetic dataset",
    )
    parser.add_argument(
        "--n_samples",
        type=int,
        default=1000,
        help="Number of samples in synthetic dataset",
    )
    parser.add_argument(
        "--example",
        choices=["all", "stability", "cv", "rfecv", "compare", "correlation"],
        default="all",
        help="Specific example to run",
    )
    args = parser.parse_args()

    # Create dataset
    X, y = create_dataset(
        task=args.task,
        n_samples=args.n_samples,
        n_features=args.n_features,
        n_informative=min(10, args.n_features // 3),
        add_noise=True,
        random_state=42,
    )

    # Run specified example(s)
    if args.example in ["all", "stability"]:
        demonstrate_feature_stability(X, y, task=args.task)

    if args.example in ["all", "cv"]:
        demonstrate_cross_validated_feature_selection(X, y, task=args.task)

    if args.example in ["all", "rfecv"]:
        demonstrate_rfecv(X, y, task=args.task)

    if args.example in ["all", "compare"]:
        compare_cv_methods(X, y, task=args.task)

    if args.example in ["all", "correlation"]:
        demonstrate_correlation_aware_selection(X, y, task=args.task)


if __name__ == "__main__":
    main()
