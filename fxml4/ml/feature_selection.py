"""
Feature Selection Module for FXML4

This module provides automated feature selection capabilities using cross-validation
to ensure robust performance. It integrates various feature selection methods
and provides pipelines for systematic selection of optimal features.
"""

import logging
import warnings
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.base import BaseEstimator, clone
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
from sklearn.feature_selection import (
    SelectKBest,
    f_classif,
    f_regression,
    mutual_info_classif,
    mutual_info_regression,
)
from sklearn.metrics import get_scorer
from sklearn.model_selection import KFold, StratifiedKFold, cross_val_score

# Import local features module
from .features import (
    analyze_feature_correlations,
    analyze_feature_importance_stability,
    boruta_feature_selection,
    cross_validate_feature_selection,
    permutation_importance_cv,
    recursive_elimination_with_cv,
    select_features_from_model,
    select_features_mutual_info,
    select_features_random_forest,
    select_features_rfe,
    select_features_sequential,
    select_uncorrelated_features,
)

logger = logging.getLogger(__name__)


class FeatureSelector:
    """
    Feature selector class providing a unified interface for feature selection
    with automatic cross-validation and optimization.
    """

    def __init__(
        self,
        method: str = "random_forest",
        k: Optional[int] = None,
        k_fraction: float = 0.5,
        estimator: Optional[BaseEstimator] = None,
        cv: int = 5,
        scoring: Optional[str] = None,
        random_state: int = 42,
        n_jobs: int = -1,
        verbose: int = 1,
        classification: Optional[bool] = None,
        correlation_threshold: float = 0.7,
        remove_correlated: bool = True,
    ):
        """
        Initialize feature selector.

        Args:
            method: Feature selection method
                "random_forest": Random Forest importance
                "mutual_info": Mutual information
                "rfe": Recursive feature elimination
                "rfecv": Recursive feature elimination with cross-validation
                "boruta": Boruta feature selection
                "permutation": Permutation importance
                "sequential": Sequential feature selection
                "shap": SHAP-based selection
            k: Number of features to select. If None, k_fraction is used.
            k_fraction: Fraction of features to select if k is None
            estimator: Estimator to use for feature selection
            cv: Number of cross-validation folds
            scoring: Scoring metric for cross-validation
            random_state: Random state for reproducibility
            n_jobs: Number of parallel jobs
            verbose: Verbosity level
            classification: Whether it's a classification or regression problem
            correlation_threshold: Threshold for feature correlation
            remove_correlated: Whether to remove highly correlated features
        """
        self.method = method
        self.k = k
        self.k_fraction = k_fraction
        self.estimator = estimator
        self.cv = cv
        self.scoring = scoring
        self.random_state = random_state
        self.n_jobs = n_jobs
        self.verbose = verbose
        self.classification = classification
        self.correlation_threshold = correlation_threshold
        self.remove_correlated = remove_correlated

        self.selected_features_ = None
        self.feature_importance_ = None
        self.cv_results_ = None

    def fit(self, X: pd.DataFrame, y: pd.Series) -> "FeatureSelector":
        """
        Fit feature selector.

        Args:
            X: Feature DataFrame
            y: Target Series

        Returns:
            Fitted feature selector
        """
        if self.verbose:
            logger.info(f"Selecting features with method: {self.method}")

        # Configure estimator and scoring
        self._configure_estimator_and_scoring(X, y)

        # Determine k if not provided
        self._determine_k(X)

        # Handle correlation analysis
        corr_clusters = self._handle_correlation_analysis(X)

        # Select features by method
        self._select_features_by_method(X, y)

        # Remove correlated features if requested
        self._remove_correlated_features(X, corr_clusters)

        # Cross-validate the feature selection
        self._cross_validate_selection(X, y)

        return self

    def _configure_estimator_and_scoring(self, X: pd.DataFrame, y: pd.Series) -> None:
        """
        Configure estimator and scoring for feature selection.

        Args:
            X: Feature DataFrame
            y: Target Series
        """
        # Auto-detect if classification or regression
        if self.classification is None:
            self.classification = len(np.unique(y)) < 10

        # Determine default estimator if not provided
        if self.estimator is None:
            if self.classification:
                self.estimator = RandomForestClassifier(
                    n_estimators=100, random_state=self.random_state, n_jobs=self.n_jobs
                )
                default_scoring = "accuracy"
            else:
                self.estimator = RandomForestRegressor(
                    n_estimators=100, random_state=self.random_state, n_jobs=self.n_jobs
                )
                default_scoring = "r2"

            # Set default scoring if not provided
            if self.scoring is None:
                self.scoring = default_scoring

    def _determine_k(self, X: pd.DataFrame) -> None:
        """
        Determine number of features to select.

        Args:
            X: Feature DataFrame
        """
        if self.k is None:
            self.k = max(int(X.shape[1] * self.k_fraction), 5)

    def _handle_correlation_analysis(self, X: pd.DataFrame) -> List:
        """
        Handle correlation analysis if requested.

        Args:
            X: Feature DataFrame

        Returns:
            List of correlation clusters
        """
        corr_clusters = []

        if self.remove_correlated:
            corr_result = analyze_feature_correlations(
                X,
                threshold=self.correlation_threshold,
                plot=False,
                return_clusters=True,
            )

            if isinstance(corr_result, tuple) and len(corr_result) > 1:
                corr_df, corr_clusters = corr_result
                if len(corr_clusters) > 0 and self.verbose:
                    logger.info(
                        f"Found {len(corr_clusters)} correlation clusters with {self.correlation_threshold} threshold"
                    )

        return corr_clusters

    def _select_features_by_method(self, X: pd.DataFrame, y: pd.Series) -> None:
        """
        Select features based on the chosen method.

        Args:
            X: Feature DataFrame
            y: Target Series
        """
        if self.method == "random_forest":
            self._select_features_random_forest(X, y)
        elif self.method == "mutual_info":
            self._select_features_mutual_info(X, y)
        elif self.method == "rfe":
            self._select_features_rfe(X, y)
        elif self.method == "rfecv":
            self._select_features_rfecv(X, y)
        elif self.method == "boruta":
            self._select_features_boruta(X, y)
        elif self.method == "permutation":
            self._select_features_permutation(X, y)
        elif self.method == "sequential":
            self._select_features_sequential(X, y)
        elif self.method == "shap":
            self._select_features_shap(X, y)
        else:
            raise ValueError(f"Unknown method: {self.method}")

    def _select_features_random_forest(self, X: pd.DataFrame, y: pd.Series) -> None:
        """Select features using Random Forest importance."""
        X_selected, self.selected_features_, importances = (
            select_features_random_forest(
                X,
                y,
                k=self.k,
                classification=self.classification,
                random_state=self.random_state,
                plot=False,
            )
        )

        self.feature_importance_ = pd.DataFrame(
            {"feature": X.columns, "importance": importances}
        ).sort_values("importance", ascending=False)

    def _select_features_mutual_info(self, X: pd.DataFrame, y: pd.Series) -> None:
        """Select features using Mutual Information."""
        X_selected, self.selected_features_ = select_features_mutual_info(
            X, y, k=self.k, plot=False
        )

        # Get feature importance from mutual info
        if self.classification:
            mi_scores = mutual_info_classif(X, y, random_state=self.random_state)
        else:
            mi_scores = mutual_info_regression(X, y, random_state=self.random_state)

        self.feature_importance_ = pd.DataFrame(
            {"feature": X.columns, "importance": mi_scores}
        ).sort_values("importance", ascending=False)

    def _select_features_rfe(self, X: pd.DataFrame, y: pd.Series) -> None:
        """Select features using Recursive Feature Elimination."""
        X_selected, self.selected_features_ = select_features_rfe(
            X,
            y,
            estimator=self.estimator,
            n_features_to_select=self.k,
            classification=self.classification,
            plot=False,
        )

        # Get feature importance from estimator
        self.feature_importance_ = self._extract_feature_importance(X, y)

    def _select_features_rfecv(self, X: pd.DataFrame, y: pd.Series) -> None:
        """Select features using Recursive Feature Elimination with CV."""
        self.selected_features_, self.cv_results_ = recursive_elimination_with_cv(
            X,
            y,
            estimator=self.estimator,
            min_features=min(5, self.k // 2),
            cv=self.cv,
            scoring=self.scoring,
            classification=self.classification,
            random_state=self.random_state,
            plot=False,
        )

        # Get feature importance from estimator
        self.feature_importance_ = self._extract_feature_importance(X, y)

    def _select_features_boruta(self, X: pd.DataFrame, y: pd.Series) -> None:
        """Select features using Boruta algorithm."""
        try:
            confirmed_features, tentative_features, _ = boruta_feature_selection(
                X,
                y,
                estimator=self.estimator,
                classification=self.classification,
                random_state=self.random_state,
                verbose=0,
                plot=False,
            )

            # Use confirmed and tentative features
            self.selected_features_ = confirmed_features + tentative_features

            # Limit to k features if needed
            if len(self.selected_features_) > self.k:
                self._limit_boruta_features(X, y)

        except ImportError:
            if self.verbose:
                logger.warning(
                    "Boruta not available. Falling back to random forest importance."
                )
            self._select_features_random_forest(X, y)

    def _select_features_permutation(self, X: pd.DataFrame, y: pd.Series) -> None:
        """Select features using Permutation Importance."""
        importance_df = permutation_importance_cv(
            X,
            y,
            estimator=self.estimator,
            cv=self.cv,
            classification=self.classification,
            scoring=self.scoring,
            random_state=self.random_state,
            n_jobs=self.n_jobs,
            plot=False,
        )

        self.feature_importance_ = importance_df
        self.selected_features_ = importance_df["feature"][: self.k].tolist()

    def _select_features_sequential(self, X: pd.DataFrame, y: pd.Series) -> None:
        """Select features using Sequential Feature Selection."""
        X_selected, self.selected_features_ = select_features_sequential(
            X,
            y,
            estimator=self.estimator,
            n_features_to_select=self.k,
            direction="forward",
            classification=self.classification,
            cv=self.cv,
            scoring=self.scoring,
            plot=False,
        )

        # Get feature importance from estimator
        self.feature_importance_ = self._extract_feature_importance(X, y)

    def _select_features_shap(self, X: pd.DataFrame, y: pd.Series) -> None:
        """Select features using SHAP values."""
        try:
            import shap

            # Fit model
            model = clone(self.estimator)
            model.fit(X, y)

            # Calculate SHAP values
            try:
                explainer = shap.Explainer(model)
                shap_values = explainer(X)

                # Get mean absolute SHAP values
                if len(shap_values.shape) > 2:  # Multi-class case
                    mean_abs_shap = np.abs(shap_values.values).mean(axis=(0, 1))
                else:
                    mean_abs_shap = np.abs(shap_values.values).mean(axis=0)

                # Create importance DataFrame
                self.feature_importance_ = pd.DataFrame(
                    {"feature": X.columns, "importance": mean_abs_shap}
                ).sort_values("importance", ascending=False)

                # Select top k features
                self.selected_features_ = self.feature_importance_["feature"][
                    : self.k
                ].tolist()

            except Exception as e:
                logger.warning(f"Error calculating SHAP values: {e}")
                logger.warning("Falling back to permutation importance")
                self._select_features_permutation(X, y)

        except ImportError:
            logger.warning(
                "SHAP not available. Falling back to permutation importance."
            )
            self._select_features_permutation(X, y)

    def _extract_feature_importance(
        self, X: pd.DataFrame, y: pd.Series
    ) -> pd.DataFrame:
        """
        Extract feature importance from fitted estimator.

        Args:
            X: Feature DataFrame
            y: Target Series

        Returns:
            Feature importance DataFrame
        """
        temp_model = clone(self.estimator)
        temp_model.fit(X, y)

        if hasattr(temp_model, "feature_importances_"):
            importances = temp_model.feature_importances_
        elif hasattr(temp_model, "coef_"):
            importances = np.abs(temp_model.coef_)
            if importances.ndim > 1:
                importances = np.mean(importances, axis=0)
        else:
            importances = np.ones(X.shape[1])

        return pd.DataFrame(
            {"feature": X.columns, "importance": importances}
        ).sort_values("importance", ascending=False)

    def _limit_boruta_features(self, X: pd.DataFrame, y: pd.Series) -> None:
        """
        Limit Boruta features to k by importance ranking.

        Args:
            X: Feature DataFrame
            y: Target Series
        """
        # Get feature importances to select top k
        temp_model = clone(self.estimator)
        temp_model.fit(X[self.selected_features_], y)

        if hasattr(temp_model, "feature_importances_"):
            sub_importances = temp_model.feature_importances_
        elif hasattr(temp_model, "coef_"):
            sub_importances = np.abs(temp_model.coef_)
            if sub_importances.ndim > 1:
                sub_importances = np.mean(sub_importances, axis=0)
        else:
            sub_importances = np.ones(len(self.selected_features_))

        # Sort by importance and select top k
        feature_ranking = pd.DataFrame(
            {"feature": self.selected_features_, "importance": sub_importances}
        ).sort_values("importance", ascending=False)

        self.selected_features_ = feature_ranking["feature"][: self.k].tolist()

    def _remove_correlated_features(self, X: pd.DataFrame, corr_clusters: List) -> None:
        """
        Remove correlated features if requested.

        Args:
            X: Feature DataFrame
            corr_clusters: List of correlation clusters
        """
        if not self.remove_correlated or len(corr_clusters) == 0:
            return

        # Use existing feature importance to select uncorrelated features
        uncorrelated_features = select_uncorrelated_features(
            X,
            correlation_threshold=self.correlation_threshold,
            importance_df=self.feature_importance_,
            keep_cols=[],  # Don't force any features to be kept
        )

        # Intersect with already selected features to get final set
        final_features = [
            f for f in self.selected_features_ if f in uncorrelated_features
        ]

        # If intersection is too small, add features from uncorrelated_features
        if len(final_features) < self.k:
            self._supplement_uncorrelated_features(
                uncorrelated_features, final_features
            )

        if self.verbose:
            logger.info(
                f"Reduced features from {len(self.selected_features_)} to {len(final_features)} after removing correlated features"
            )

        self.selected_features_ = final_features[: self.k]  # Ensure we don't exceed k

    def _supplement_uncorrelated_features(
        self, uncorrelated_features: List[str], final_features: List[str]
    ) -> None:
        """
        Supplement final features with additional uncorrelated features.

        Args:
            uncorrelated_features: List of uncorrelated features
            final_features: Current final features list (modified in place)
        """
        # Get remaining features from uncorrelated features that weren't in selected features
        remaining = [f for f in uncorrelated_features if f not in final_features]

        # Get importance of remaining features
        remaining_importance = self.feature_importance_[
            self.feature_importance_["feature"].isin(remaining)
        ].sort_values("importance", ascending=False)

        # Add remaining features by importance until we reach k
        n_to_add = min(self.k - len(final_features), len(remaining_importance))
        if n_to_add > 0:
            final_features.extend(remaining_importance["feature"][:n_to_add].tolist())

    def _cross_validate_selection(self, X: pd.DataFrame, y: pd.Series) -> None:
        """
        Cross-validate the selected features.

        Args:
            X: Feature DataFrame
            y: Target Series
        """
        if self.selected_features_ is None or len(self.selected_features_) == 0:
            logger.warning("No features selected for cross-validation")
            return

        # Create CV splitter
        if self.classification:
            cv_splitter = StratifiedKFold(
                n_splits=self.cv, shuffle=True, random_state=self.random_state
            )
        else:
            cv_splitter = KFold(
                n_splits=self.cv, shuffle=True, random_state=self.random_state
            )

        # Initialize models
        full_model = clone(self.estimator)
        selected_model = clone(self.estimator)

        # Get scorer
        scorer = get_scorer(self.scoring)

        # Track scores
        full_scores = []
        selected_scores = []

        # Perform CV
        for train_idx, test_idx in cv_splitter.split(X, y):
            X_train, X_test = X.iloc[train_idx], X.iloc[test_idx]
            y_train, y_test = y.iloc[train_idx], y.iloc[test_idx]

            # Train and evaluate model with all features
            full_model.fit(X_train, y_train)
            full_score = scorer(full_model, X_test, y_test)
            full_scores.append(full_score)

            # Train and evaluate model with selected features
            X_train_selected = X_train[self.selected_features_]
            X_test_selected = X_test[self.selected_features_]

            selected_model.fit(X_train_selected, y_train)
            selected_score = scorer(selected_model, X_test_selected, y_test)
            selected_scores.append(selected_score)

        # Store results
        self.cv_results_ = {
            "full_scores": full_scores,
            "selected_scores": selected_scores,
            "mean_full_score": np.mean(full_scores),
            "mean_selected_score": np.mean(selected_scores),
            "std_full_score": np.std(full_scores),
            "std_selected_score": np.std(selected_scores),
            "n_features_full": X.shape[1],
            "n_features_selected": len(self.selected_features_),
        }

        if self.verbose:
            logger.info(f"CV results:")
            logger.info(
                f"  Full model ({X.shape[1]} features): {self.cv_results_['mean_full_score']:.4f} ± {self.cv_results_['std_full_score']:.4f}"
            )
            logger.info(
                f"  Selected model ({len(self.selected_features_)} features): {self.cv_results_['mean_selected_score']:.4f} ± {self.cv_results_['std_selected_score']:.4f}"
            )

    def transform(self, X: pd.DataFrame) -> pd.DataFrame:
        """
        Transform data by selecting features.

        Args:
            X: Feature DataFrame

        Returns:
            DataFrame with selected features
        """
        if self.selected_features_ is None:
            raise ValueError("Feature selector not fitted")

        return X[self.selected_features_]

    def fit_transform(self, X: pd.DataFrame, y: pd.Series) -> pd.DataFrame:
        """
        Fit and transform.

        Args:
            X: Feature DataFrame
            y: Target Series

        Returns:
            DataFrame with selected features
        """
        self.fit(X, y)
        return self.transform(X)

    def get_support(self, indices: bool = False) -> Union[List[str], np.ndarray]:
        """
        Get support mask or indices.

        Args:
            indices: Whether to return indices or mask

        Returns:
            Support mask or indices
        """
        if self.selected_features_ is None:
            raise ValueError("Feature selector not fitted")

        if indices:
            return [
                list(self.feature_importance_["feature"]).index(f)
                for f in self.selected_features_
            ]
        else:
            return [
                f in self.selected_features_
                for f in self.feature_importance_["feature"]
            ]

    def plot_importance(
        self,
        max_features: int = 20,
        figsize: Tuple[int, int] = (10, 8),
        show_threshold: bool = True,
    ) -> None:
        """
        Plot feature importance.

        Args:
            max_features: Maximum number of features to display
            figsize: Figure size
            show_threshold: Whether to show selection threshold
        """
        if self.feature_importance_ is None:
            raise ValueError("Feature selector not fitted")

        # Get top features
        top_features = self.feature_importance_.head(max_features).copy()

        # Sort by importance for better visualization
        top_features = top_features.sort_values("importance", ascending=True)

        plt.figure(figsize=figsize)

        # Plot importance
        plt.barh(
            y=np.arange(len(top_features)),
            width=top_features["importance"],
            align="center",
        )
        plt.yticks(np.arange(len(top_features)), top_features["feature"])

        # Highlight selected features
        is_selected = [f in self.selected_features_ for f in top_features["feature"]]

        for i, selected in enumerate(is_selected):
            color = "darkgreen" if selected else "darkred"
            plt.barh(
                y=i,
                width=top_features["importance"].iloc[i],
                align="center",
                color=color,
            )

        # Show threshold if requested
        if show_threshold and len(self.selected_features_) < len(
            self.feature_importance_
        ):
            # Find threshold
            min_selected_importance = min(
                [
                    self.feature_importance_[self.feature_importance_["feature"] == f][
                        "importance"
                    ].values[0]
                    for f in self.selected_features_
                ]
            )

            plt.axvline(
                x=min_selected_importance,
                color="red",
                linestyle="--",
                label=f"Selection threshold",
            )
            plt.legend()

        plt.xlabel("Feature Importance")
        plt.title(f"Feature Importance ({self.method})")
        plt.tight_layout()
        plt.show()

    def plot_cv_results(self, figsize: Tuple[int, int] = (10, 6)) -> None:
        """
        Plot cross-validation results.

        Args:
            figsize: Figure size
        """
        if self.cv_results_ is None:
            raise ValueError("Cross-validation results not available")

        plt.figure(figsize=figsize)

        # Create bar chart
        labels = ["Full model", "Selected features"]
        means = [
            self.cv_results_["mean_full_score"],
            self.cv_results_["mean_selected_score"],
        ]
        stds = [
            self.cv_results_["std_full_score"],
            self.cv_results_["std_selected_score"],
        ]

        x = np.arange(len(labels))
        width = 0.35

        plt.bar(x, means, width, yerr=stds)
        plt.xticks(x, labels)
        plt.ylabel(f"{self.scoring} score")
        plt.title("Model Performance Comparison")

        # Add text with number of features
        plt.figtext(
            0.5,
            0.01,
            f"Features: {self.cv_results_['n_features_full']} (full) vs {self.cv_results_['n_features_selected']} (selected)",
            ha="center",
        )

        plt.tight_layout()
        plt.show()


def find_optimal_feature_set(
    X: pd.DataFrame,
    y: pd.Series,
    methods: List[str] = ["random_forest", "mutual_info", "permutation", "shap"],
    estimator=None,
    cv: int = 5,
    scoring: str = None,
    k_values: List[int] = None,
    k_fractions: List[float] = [0.1, 0.2, 0.3, 0.5, 0.7],
    random_state: int = 42,
    n_jobs: int = -1,
    verbose: int = 1,
) -> Dict:
    """
    Find optimal feature set by comparing multiple methods and feature counts.

    Args:
        X: Feature DataFrame
        y: Target Series
        methods: List of feature selection methods to try
        estimator: Estimator to use for feature selection
        cv: Number of cross-validation folds
        scoring: Scoring metric for cross-validation
        k_values: List of specific k values to try
        k_fractions: List of feature fraction values to try (used if k_values is None)
        random_state: Random state for reproducibility
        n_jobs: Number of parallel jobs
        verbose: Verbosity level

    Returns:
        Dictionary with results
    """
    # Auto-detect if classification or regression
    classification = len(np.unique(y)) < 10

    # Determine default estimator if not provided
    if estimator is None:
        if classification:
            estimator = RandomForestClassifier(
                n_estimators=100, random_state=random_state, n_jobs=n_jobs
            )
            default_scoring = "accuracy"
        else:
            estimator = RandomForestRegressor(
                n_estimators=100, random_state=random_state, n_jobs=n_jobs
            )
            default_scoring = "r2"

        # Set default scoring if not provided
        if scoring is None:
            scoring = default_scoring

    # Determine k values if not provided
    if k_values is None:
        k_values = [max(int(X.shape[1] * frac), 5) for frac in k_fractions]

    # Make sure k values are unique and sorted
    k_values = sorted(list(set(k_values)))

    if verbose:
        logger.info(
            f"Finding optimal feature set with {len(methods)} methods and {len(k_values)} k values"
        )
        logger.info(f"Methods: {methods}")
        logger.info(f"k values: {k_values}")

    # Track results
    results = {
        "methods": methods,
        "k_values": k_values,
        "selectors": {},
        "best_method": None,
        "best_k": None,
        "best_score": -np.inf,
        "best_selector": None,
    }

    # Try all combinations
    for method in methods:
        results["selectors"][method] = {}

        for k in k_values:
            # Create and fit selector
            selector = FeatureSelector(
                method=method,
                k=k,
                estimator=estimator,
                cv=cv,
                scoring=scoring,
                random_state=random_state,
                n_jobs=n_jobs,
                verbose=0,
                classification=classification,
            )

            # Fit selector
            selector.fit(X, y)

            # Store selector
            results["selectors"][method][k] = selector

            # Check if this is the best score
            if selector.cv_results_["mean_selected_score"] > results["best_score"]:
                results["best_method"] = method
                results["best_k"] = k
                results["best_score"] = selector.cv_results_["mean_selected_score"]
                results["best_selector"] = selector

    if verbose:
        logger.info(f"Best method: {results['best_method']}")
        logger.info(f"Best k: {results['best_k']}")
        logger.info(f"Best score: {results['best_score']:.4f}")
        logger.info(f"Selected features: {results['best_selector'].selected_features_}")

    # Create comparison DataFrame
    comparison_data = []

    for method in methods:
        for k in k_values:
            selector = results["selectors"][method][k]

            comparison_data.append(
                {
                    "method": method,
                    "k": k,
                    "score": selector.cv_results_["mean_selected_score"],
                    "std": selector.cv_results_["std_selected_score"],
                    "full_score": selector.cv_results_["mean_full_score"],
                    "full_std": selector.cv_results_["std_full_score"],
                }
            )

    results["comparison"] = pd.DataFrame(comparison_data)

    return results


def plot_feature_selection_comparison(
    results: Dict, figsize: Tuple[int, int] = (12, 8), include_full_model: bool = True
) -> None:
    """
    Plot comparison of feature selection methods.

    Args:
        results: Results from find_optimal_feature_set
        figsize: Figure size
        include_full_model: Whether to include full model score
    """
    comparison = results["comparison"]
    methods = results["methods"]
    k_values = results["k_values"]

    plt.figure(figsize=figsize)

    # Colors for different methods
    colors = plt.cm.tab10(np.linspace(0, 1, len(methods)))

    # Plot scores for each method
    for i, method in enumerate(methods):
        method_data = comparison[comparison["method"] == method]

        plt.plot(
            method_data["k"], method_data["score"], "o-", label=method, color=colors[i]
        )

        # Add error bars
        plt.fill_between(
            method_data["k"],
            method_data["score"] - method_data["std"],
            method_data["score"] + method_data["std"],
            alpha=0.2,
            color=colors[i],
        )

    # Add full model score if requested
    if include_full_model:
        full_score = comparison["full_score"].mean()
        full_std = comparison["full_std"].mean()

        plt.axhline(
            y=full_score,
            color="black",
            linestyle="--",
            label=f"Full model ({comparison['full_score'].iloc[0]:.4f})",
        )

        plt.fill_between(
            k_values,
            [full_score - full_std] * len(k_values),
            [full_score + full_std] * len(k_values),
            alpha=0.1,
            color="black",
        )

    # Highlight best model
    best_method = results["best_method"]
    best_k = results["best_k"]
    best_score = results["best_score"]

    plt.scatter(
        [best_k],
        [best_score],
        marker="*",
        s=200,
        color="red",
        label=f"Best: {best_method}, k={best_k}",
    )

    plt.xlabel("Number of features")
    plt.ylabel("Cross-validation score")
    plt.title("Feature Selection Methods Comparison")
    plt.legend()
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.show()


def ensemble_feature_selection(
    X: pd.DataFrame,
    y: pd.Series,
    methods: List[str] = ["random_forest", "mutual_info", "permutation"],
    weights: List[float] = None,
    k: int = None,
    k_fraction: float = 0.3,
    cv: int = 5,
    scoring: str = None,
    estimator=None,
    random_state: int = 42,
    n_jobs: int = -1,
    verbose: int = 1,
) -> Tuple[List[str], pd.DataFrame]:
    """
    Perform ensemble feature selection by combining multiple methods.

    Args:
        X: Feature DataFrame
        y: Target Series
        methods: List of feature selection methods to combine
        weights: Weights for each method (if None, equal weights)
        k: Number of features to select
        k_fraction: Fraction of features to select if k is None
        cv: Number of cross-validation folds
        scoring: Scoring metric for cross-validation
        estimator: Estimator to use for feature selection
        random_state: Random state for reproducibility
        n_jobs: Number of parallel jobs
        verbose: Verbosity level

    Returns:
        Tuple of (selected features, feature importance DataFrame)
    """
    if weights is None:
        weights = [1.0] * len(methods)

    if len(methods) != len(weights):
        raise ValueError("Number of methods must match number of weights")

    # Determine k if not provided
    if k is None:
        k = max(int(X.shape[1] * k_fraction), 5)

    if verbose:
        logger.info(
            f"Performing ensemble feature selection with {len(methods)} methods"
        )
        logger.info(f"Methods: {methods}")
        logger.info(f"Weights: {weights}")

    # Create selectors for each method
    selectors = []

    for method in methods:
        selector = FeatureSelector(
            method=method,
            k=X.shape[1],  # Select all features initially
            estimator=estimator,
            cv=cv,
            scoring=scoring,
            random_state=random_state,
            n_jobs=n_jobs,
            verbose=0,
        )

        # Fit selector
        selector.fit(X, y)
        selectors.append(selector)

    # Combine feature importance scores
    combined_importance = pd.DataFrame({"feature": X.columns})

    # Add importance from each method
    for i, (selector, method, weight) in enumerate(zip(selectors, methods, weights)):
        # Get normalized importance (divide by max to get 0-1 scale)
        importance = selector.feature_importance_.copy()
        max_importance = importance["importance"].max()
        importance["importance"] = importance["importance"] / max_importance

        # Add to combined importance
        combined_importance = combined_importance.merge(
            importance, on="feature", how="left", suffixes=("", f"_{method}")
        )

        # Rename column
        combined_importance.rename(
            columns={"importance": f"importance_{method}"}, inplace=True
        )

        # Apply weight
        combined_importance[f"weighted_importance_{method}"] = (
            combined_importance[f"importance_{method}"] * weight
        )

    # Calculate total weighted importance
    weighted_cols = [f"weighted_importance_{method}" for method in methods]
    combined_importance["total_importance"] = combined_importance[weighted_cols].sum(
        axis=1
    )

    # Select top k features
    top_features = combined_importance.sort_values(
        "total_importance", ascending=False
    ).head(k)
    selected_features = top_features["feature"].tolist()

    if verbose:
        logger.info(
            f"Selected {len(selected_features)} features with ensemble selection"
        )

    # Create final importance DataFrame
    feature_importance = combined_importance[
        ["feature", "total_importance"]
    ].sort_values("total_importance", ascending=False)

    return selected_features, feature_importance
