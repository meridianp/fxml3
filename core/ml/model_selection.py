"""
Model Selection and Hyperparameter Tuning for FXML4

This module provides utilities for:
1. Grid search and random search for hyperparameter optimization
2. Bayesian optimization for efficient parameter search
3. Model comparison and selection
4. Cross-validation strategies for time series
5. Feature importance analysis
"""

import json
import logging
import warnings
from datetime import datetime
from itertools import product
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

import numpy as np
import pandas as pd
from sklearn.base import BaseEstimator, clone
from sklearn.metrics import (
    accuracy_score,
    f1_score,
    log_loss,
    make_scorer,
    mean_squared_error,
    precision_score,
    recall_score,
)

# Sklearn imports
from sklearn.model_selection import (
    GridSearchCV,
    ParameterGrid,
    ParameterSampler,
    RandomizedSearchCV,
    TimeSeriesSplit,
    cross_val_score,
)

from fxml4.ml.cross_validation import WalkForwardAnalysis

# FXML4 imports
from fxml4.ml.models import ClassicMLModel, create_model

# Optional imports for advanced optimization
try:
    from skopt import BayesSearchCV
    from skopt.space import Categorical, Integer, Real

    BAYESIAN_AVAILABLE = True
except ImportError:
    BAYESIAN_AVAILABLE = False

try:
    import optuna

    OPTUNA_AVAILABLE = True
except ImportError:
    OPTUNA_AVAILABLE = False

logger = logging.getLogger(__name__)


class ModelSelector:
    """Advanced model selection and hyperparameter tuning."""

    def __init__(
        self,
        scoring: Union[str, Callable] = "f1_weighted",
        cv_strategy: str = "time_series",
        n_splits: int = 5,
        verbose: int = 1,
        n_jobs: int = -1,
        random_state: int = 42,
    ):
        """
        Initialize model selector.

        Args:
            scoring: Scoring metric or callable
            cv_strategy: Cross-validation strategy ("time_series", "walk_forward")
            n_splits: Number of CV splits
            verbose: Verbosity level
            n_jobs: Number of parallel jobs
            random_state: Random seed
        """
        self.scoring = scoring
        self.cv_strategy = cv_strategy
        self.n_splits = n_splits
        self.verbose = verbose
        self.n_jobs = n_jobs
        self.random_state = random_state

        # Results storage
        self.results = {}
        self.best_models = {}
        self.search_history = []

    def _get_cv_splitter(self, X: np.ndarray, y: np.ndarray):
        """Get cross-validation splitter based on strategy."""
        if self.cv_strategy == "time_series":
            return TimeSeriesSplit(n_splits=self.n_splits)
        elif self.cv_strategy == "walk_forward":
            # Use walk-forward analysis
            n_samples = len(X)
            train_size = int(0.6 * n_samples)
            test_size = int(0.2 * n_samples)
            step_size = test_size // self.n_splits

            # Generate walk-forward splits
            splits = []
            for i in range(self.n_splits):
                train_end = train_size + i * step_size
                test_start = train_end
                test_end = min(test_start + test_size, n_samples)

                train_idx = np.arange(0, train_end)
                test_idx = np.arange(test_start, test_end)
                splits.append((train_idx, test_idx))

            return splits
        else:
            raise ValueError(f"Unknown CV strategy: {self.cv_strategy}")

    def grid_search(
        self,
        X: Union[pd.DataFrame, np.ndarray],
        y: Union[pd.Series, np.ndarray],
        model_type: str,
        param_grid: Dict[str, List[Any]],
        refit: bool = True,
        return_train_score: bool = True,
    ) -> Dict[str, Any]:
        """
        Perform grid search for hyperparameter tuning.

        Args:
            X: Features
            y: Target
            model_type: Type of model to tune
            param_grid: Parameter grid
            refit: Whether to refit on full data
            return_train_score: Whether to return training scores

        Returns:
            Dictionary with results
        """
        logger.info(f"Starting grid search for {model_type}")

        # Create base model
        base_model = create_model(model_type)

        # Get CV splitter
        cv = self._get_cv_splitter(X, y)

        # Create grid search
        grid_search = GridSearchCV(
            estimator=base_model.model,
            param_grid=param_grid,
            scoring=self.scoring,
            cv=cv,
            refit=refit,
            return_train_score=return_train_score,
            n_jobs=self.n_jobs,
            verbose=self.verbose,
        )

        # Fit grid search
        start_time = datetime.now()
        grid_search.fit(X, y)
        end_time = datetime.now()

        # Store results
        results = {
            "model_type": model_type,
            "method": "grid_search",
            "best_params": grid_search.best_params_,
            "best_score": grid_search.best_score_,
            "cv_results": pd.DataFrame(grid_search.cv_results_),
            "search_time": (end_time - start_time).total_seconds(),
            "n_candidates": len(ParameterGrid(param_grid)),
        }

        # Create best model with FXML4 wrapper
        if refit:
            best_model = create_model(
                model_type=model_type, model_params=grid_search.best_params_
            )
            best_model.model = grid_search.best_estimator_
            results["best_model"] = best_model
            self.best_models[model_type] = best_model

        # Store in results
        self.results[f"{model_type}_grid"] = results
        self.search_history.append(results)

        logger.info(f"Grid search completed. Best score: {grid_search.best_score_:.4f}")
        logger.info(f"Best params: {grid_search.best_params_}")

        return results

    def random_search(
        self,
        X: Union[pd.DataFrame, np.ndarray],
        y: Union[pd.Series, np.ndarray],
        model_type: str,
        param_distributions: Dict[str, Any],
        n_iter: int = 50,
        refit: bool = True,
        return_train_score: bool = True,
    ) -> Dict[str, Any]:
        """
        Perform random search for hyperparameter tuning.

        Args:
            X: Features
            y: Target
            model_type: Type of model to tune
            param_distributions: Parameter distributions
            n_iter: Number of iterations
            refit: Whether to refit on full data
            return_train_score: Whether to return training scores

        Returns:
            Dictionary with results
        """
        logger.info(f"Starting random search for {model_type} with {n_iter} iterations")

        # Create base model
        base_model = create_model(model_type)

        # Get CV splitter
        cv = self._get_cv_splitter(X, y)

        # Create random search
        random_search = RandomizedSearchCV(
            estimator=base_model.model,
            param_distributions=param_distributions,
            n_iter=n_iter,
            scoring=self.scoring,
            cv=cv,
            refit=refit,
            return_train_score=return_train_score,
            n_jobs=self.n_jobs,
            verbose=self.verbose,
            random_state=self.random_state,
        )

        # Fit random search
        start_time = datetime.now()
        random_search.fit(X, y)
        end_time = datetime.now()

        # Store results
        results = {
            "model_type": model_type,
            "method": "random_search",
            "best_params": random_search.best_params_,
            "best_score": random_search.best_score_,
            "cv_results": pd.DataFrame(random_search.cv_results_),
            "search_time": (end_time - start_time).total_seconds(),
            "n_candidates": n_iter,
        }

        # Create best model with FXML4 wrapper
        if refit:
            best_model = create_model(
                model_type=model_type, model_params=random_search.best_params_
            )
            best_model.model = random_search.best_estimator_
            results["best_model"] = best_model
            self.best_models[model_type] = best_model

        # Store in results
        self.results[f"{model_type}_random"] = results
        self.search_history.append(results)

        logger.info(
            f"Random search completed. Best score: {random_search.best_score_:.4f}"
        )
        logger.info(f"Best params: {random_search.best_params_}")

        return results

    def bayesian_search(
        self,
        X: Union[pd.DataFrame, np.ndarray],
        y: Union[pd.Series, np.ndarray],
        model_type: str,
        search_spaces: Dict[str, Any],
        n_iter: int = 50,
        refit: bool = True,
    ) -> Dict[str, Any]:
        """
        Perform Bayesian optimization for hyperparameter tuning.

        Args:
            X: Features
            y: Target
            model_type: Type of model to tune
            search_spaces: Search spaces for Bayesian optimization
            n_iter: Number of iterations
            refit: Whether to refit on full data

        Returns:
            Dictionary with results
        """
        if not BAYESIAN_AVAILABLE:
            raise ImportError(
                "scikit-optimize not available. Install with: pip install scikit-optimize"
            )

        logger.info(
            f"Starting Bayesian search for {model_type} with {n_iter} iterations"
        )

        # Create base model
        base_model = create_model(model_type)

        # Get CV splitter
        cv = self._get_cv_splitter(X, y)

        # Create Bayesian search
        bayes_search = BayesSearchCV(
            estimator=base_model.model,
            search_spaces=search_spaces,
            n_iter=n_iter,
            scoring=self.scoring,
            cv=cv,
            refit=refit,
            n_jobs=self.n_jobs,
            verbose=self.verbose,
            random_state=self.random_state,
        )

        # Fit Bayesian search
        start_time = datetime.now()
        bayes_search.fit(X, y)
        end_time = datetime.now()

        # Store results
        results = {
            "model_type": model_type,
            "method": "bayesian_search",
            "best_params": bayes_search.best_params_,
            "best_score": bayes_search.best_score_,
            "cv_results": pd.DataFrame(bayes_search.cv_results_),
            "search_time": (end_time - start_time).total_seconds(),
            "n_candidates": n_iter,
        }

        # Create best model with FXML4 wrapper
        if refit:
            best_model = create_model(
                model_type=model_type, model_params=bayes_search.best_params_
            )
            best_model.model = bayes_search.best_estimator_
            results["best_model"] = best_model
            self.best_models[model_type] = best_model

        # Store in results
        self.results[f"{model_type}_bayes"] = results
        self.search_history.append(results)

        logger.info(
            f"Bayesian search completed. Best score: {bayes_search.best_score_:.4f}"
        )
        logger.info(f"Best params: {bayes_search.best_params_}")

        return results

    def optuna_search(
        self,
        X: Union[pd.DataFrame, np.ndarray],
        y: Union[pd.Series, np.ndarray],
        model_type: str,
        objective_func: Optional[Callable] = None,
        n_trials: int = 100,
        direction: str = "maximize",
    ) -> Dict[str, Any]:
        """
        Perform Optuna-based hyperparameter optimization.

        Args:
            X: Features
            y: Target
            model_type: Type of model to tune
            objective_func: Custom objective function (if None, uses default)
            n_trials: Number of trials
            direction: Optimization direction ("maximize" or "minimize")

        Returns:
            Dictionary with results
        """
        if not OPTUNA_AVAILABLE:
            raise ImportError("Optuna not available. Install with: pip install optuna")

        logger.info(f"Starting Optuna search for {model_type} with {n_trials} trials")

        # Convert to numpy if needed
        if isinstance(X, pd.DataFrame):
            X_values = X.values
        else:
            X_values = X
        if isinstance(y, pd.Series):
            y_values = y.values
        else:
            y_values = y

        # Get CV splitter
        cv = self._get_cv_splitter(X_values, y_values)

        # Define objective function if not provided
        if objective_func is None:

            def objective(trial):
                # Define hyperparameters based on model type
                params = self._get_optuna_params(trial, model_type)

                # Create model
                model = create_model(model_type, model_params=params)

                # Perform cross-validation
                scores = []
                for train_idx, val_idx in (
                    cv if isinstance(cv, list) else cv.split(X_values, y_values)
                ):
                    X_train, X_val = X_values[train_idx], X_values[val_idx]
                    y_train, y_val = y_values[train_idx], y_values[val_idx]

                    # Clone and train model
                    model_clone = clone(model.model)
                    model_clone.fit(X_train, y_train)

                    # Evaluate
                    if self.scoring == "f1_weighted":
                        y_pred = model_clone.predict(X_val)
                        score = f1_score(y_val, y_pred, average="weighted")
                    elif self.scoring == "accuracy":
                        y_pred = model_clone.predict(X_val)
                        score = accuracy_score(y_val, y_pred)
                    else:
                        # Use sklearn scorer
                        scorer = make_scorer(self.scoring)
                        score = scorer(model_clone, X_val, y_val)

                    scores.append(score)

                return np.mean(scores)

            objective_func = objective

        # Create study
        study = optuna.create_study(
            direction=direction,
            sampler=optuna.samplers.TPESampler(seed=self.random_state),
        )

        # Run optimization
        start_time = datetime.now()
        study.optimize(
            objective_func, n_trials=n_trials, n_jobs=1
        )  # Single job to avoid issues
        end_time = datetime.now()

        # Get best parameters
        best_params = study.best_params
        best_value = study.best_value

        # Create best model
        best_model = create_model(model_type, model_params=best_params)
        best_model.train(X, y)

        # Store results
        results = {
            "model_type": model_type,
            "method": "optuna_search",
            "best_params": best_params,
            "best_score": best_value,
            "study": study,
            "search_time": (end_time - start_time).total_seconds(),
            "n_candidates": n_trials,
            "best_model": best_model,
        }

        # Store in results
        self.results[f"{model_type}_optuna"] = results
        self.search_history.append(results)
        self.best_models[model_type] = best_model

        logger.info(f"Optuna search completed. Best score: {best_value:.4f}")
        logger.info(f"Best params: {best_params}")

        return results

    def _get_optuna_params(self, trial, model_type: str) -> Dict[str, Any]:
        """Get Optuna parameter suggestions based on model type."""
        if model_type == "random_forest":
            return {
                "n_estimators": trial.suggest_int("n_estimators", 50, 500),
                "max_depth": trial.suggest_int("max_depth", 3, 20),
                "min_samples_split": trial.suggest_int("min_samples_split", 2, 20),
                "min_samples_leaf": trial.suggest_int("min_samples_leaf", 1, 10),
                "max_features": trial.suggest_categorical(
                    "max_features", ["sqrt", "log2", None]
                ),
                "random_state": self.random_state,
            }
        elif model_type == "xgboost":
            return {
                "n_estimators": trial.suggest_int("n_estimators", 50, 500),
                "max_depth": trial.suggest_int("max_depth", 3, 15),
                "learning_rate": trial.suggest_float(
                    "learning_rate", 0.01, 0.3, log=True
                ),
                "subsample": trial.suggest_float("subsample", 0.6, 1.0),
                "colsample_bytree": trial.suggest_float("colsample_bytree", 0.6, 1.0),
                "gamma": trial.suggest_float("gamma", 0, 5),
                "reg_alpha": trial.suggest_float("reg_alpha", 0, 2),
                "reg_lambda": trial.suggest_float("reg_lambda", 0, 2),
                "random_state": self.random_state,
            }
        elif model_type == "logistic":
            return {
                "C": trial.suggest_float("C", 0.001, 100, log=True),
                "penalty": trial.suggest_categorical("penalty", ["l1", "l2"]),
                "solver": trial.suggest_categorical("solver", ["liblinear", "saga"]),
                "max_iter": 1000,
                "random_state": self.random_state,
            }
        else:
            raise ValueError(f"Unknown model type for Optuna: {model_type}")

    def compare_models(
        self,
        X: Union[pd.DataFrame, np.ndarray],
        y: Union[pd.Series, np.ndarray],
        model_configs: List[Dict[str, Any]],
        metrics: Optional[List[str]] = None,
    ) -> pd.DataFrame:
        """
        Compare multiple models with specified configurations.

        Args:
            X: Features
            y: Target
            model_configs: List of model configurations
                Each config should have: model_type, params (optional)
            metrics: List of metrics to evaluate

        Returns:
            DataFrame with comparison results
        """
        if metrics is None:
            metrics = ["accuracy", "precision", "recall", "f1"]

        logger.info(f"Comparing {len(model_configs)} models")

        # Get CV splitter
        cv = self._get_cv_splitter(X, y)

        comparison_results = []

        for config in model_configs:
            model_type = config.get("model_type")
            model_params = config.get("params", {})
            model_name = config.get("name", f"{model_type}_{len(comparison_results)}")

            logger.info(f"Evaluating {model_name}")

            # Create model
            model = create_model(model_type, model_params=model_params)

            # Evaluate with cross-validation
            scores = {metric: [] for metric in metrics}

            for train_idx, val_idx in cv if isinstance(cv, list) else cv.split(X, y):
                if isinstance(X, pd.DataFrame):
                    X_train, X_val = X.iloc[train_idx], X.iloc[val_idx]
                    y_train, y_val = y.iloc[train_idx], y.iloc[val_idx]
                else:
                    X_train, X_val = X[train_idx], X[val_idx]
                    y_train, y_val = y[train_idx], y[val_idx]

                # Train model
                model_clone = create_model(model_type, model_params=model_params)
                model_clone.train(X_train, y_train)

                # Get predictions
                y_pred = model_clone.predict(X_val)

                # Calculate metrics
                for metric in metrics:
                    if metric == "accuracy":
                        score = accuracy_score(y_val, y_pred)
                    elif metric == "precision":
                        score = precision_score(
                            y_val, y_pred, average="weighted", zero_division=0
                        )
                    elif metric == "recall":
                        score = recall_score(
                            y_val, y_pred, average="weighted", zero_division=0
                        )
                    elif metric == "f1":
                        score = f1_score(
                            y_val, y_pred, average="weighted", zero_division=0
                        )
                    else:
                        raise ValueError(f"Unknown metric: {metric}")

                    scores[metric].append(score)

            # Calculate mean and std for each metric
            result = {
                "model_name": model_name,
                "model_type": model_type,
                "params": json.dumps(model_params),
            }

            for metric in metrics:
                result[f"{metric}_mean"] = np.mean(scores[metric])
                result[f"{metric}_std"] = np.std(scores[metric])

            comparison_results.append(result)

        # Create comparison DataFrame
        comparison_df = pd.DataFrame(comparison_results)

        # Sort by primary metric (first in list)
        primary_metric = f"{metrics[0]}_mean"
        comparison_df = comparison_df.sort_values(primary_metric, ascending=False)

        logger.info("Model comparison completed")

        return comparison_df

    def get_feature_importance(
        self,
        model_type: str,
        X: Union[pd.DataFrame, np.ndarray],
        y: Union[pd.Series, np.ndarray],
        n_repeats: int = 10,
    ) -> pd.DataFrame:
        """
        Get feature importance using permutation importance.

        Args:
            model_type: Type of model
            X: Features
            y: Target
            n_repeats: Number of permutation repeats

        Returns:
            DataFrame with feature importance
        """
        from sklearn.inspection import permutation_importance

        # Get best model or create new one
        if model_type in self.best_models:
            model = self.best_models[model_type]
        else:
            model = create_model(model_type)
            model.train(X, y)

        # Calculate permutation importance
        if isinstance(X, pd.DataFrame):
            feature_names = X.columns.tolist()
            X_values = X.values
        else:
            feature_names = [f"feature_{i}" for i in range(X.shape[1])]
            X_values = X

        # Get base model
        base_model = model.model

        # Calculate importance
        result = permutation_importance(
            base_model,
            X_values,
            y,
            n_repeats=n_repeats,
            random_state=self.random_state,
            n_jobs=self.n_jobs,
        )

        # Create DataFrame
        importance_df = pd.DataFrame(
            {
                "feature": feature_names,
                "importance_mean": result.importances_mean,
                "importance_std": result.importances_std,
            }
        )

        # Sort by importance
        importance_df = importance_df.sort_values("importance_mean", ascending=False)

        return importance_df

    def get_summary(self) -> pd.DataFrame:
        """
        Get summary of all model selection results.

        Returns:
            DataFrame with summary
        """
        summary_data = []

        for key, result in self.results.items():
            summary_data.append(
                {
                    "model": key,
                    "method": result["method"],
                    "best_score": result["best_score"],
                    "search_time": result["search_time"],
                    "n_candidates": result["n_candidates"],
                    "best_params": json.dumps(result["best_params"]),
                }
            )

        summary_df = pd.DataFrame(summary_data)
        summary_df = summary_df.sort_values("best_score", ascending=False)

        return summary_df


# Predefined parameter grids for common models
PARAM_GRIDS = {
    "random_forest": {
        "n_estimators": [100, 200, 300],
        "max_depth": [5, 10, 15, None],
        "min_samples_split": [2, 5, 10],
        "min_samples_leaf": [1, 2, 4],
        "max_features": ["sqrt", "log2", None],
    },
    "xgboost": {
        "n_estimators": [100, 200, 300],
        "max_depth": [3, 6, 9],
        "learning_rate": [0.01, 0.1, 0.3],
        "subsample": [0.7, 0.8, 0.9],
        "colsample_bytree": [0.7, 0.8, 0.9],
    },
    "logistic": {
        "C": [0.001, 0.01, 0.1, 1, 10, 100],
        "penalty": ["l1", "l2"],
        "solver": ["liblinear", "saga"],
    },
}

# Predefined parameter distributions for random search
PARAM_DISTRIBUTIONS = {
    "random_forest": {
        "n_estimators": [50, 100, 200, 300, 400, 500],
        "max_depth": list(range(3, 21)) + [None],
        "min_samples_split": list(range(2, 21)),
        "min_samples_leaf": list(range(1, 11)),
        "max_features": ["sqrt", "log2", None, 0.5, 0.7, 0.9],
    },
    "xgboost": {
        "n_estimators": list(range(50, 501, 50)),
        "max_depth": list(range(3, 16)),
        "learning_rate": np.logspace(-3, -0.5, 20),
        "subsample": np.linspace(0.6, 1.0, 10),
        "colsample_bytree": np.linspace(0.6, 1.0, 10),
        "gamma": np.linspace(0, 5, 10),
        "reg_alpha": np.linspace(0, 2, 10),
        "reg_lambda": np.linspace(0, 2, 10),
    },
    "logistic": {
        "C": np.logspace(-4, 2, 20),
        "penalty": ["l1", "l2"],
        "solver": ["liblinear", "saga"],
        "max_iter": [500, 1000, 2000],
    },
}


# Convenience function for quick model selection
def select_best_model(
    X: Union[pd.DataFrame, np.ndarray],
    y: Union[pd.Series, np.ndarray],
    model_types: List[str] = ["random_forest", "xgboost", "logistic"],
    method: str = "random",
    n_iter: int = 20,
    scoring: str = "f1_weighted",
    cv_strategy: str = "time_series",
    n_splits: int = 5,
) -> Dict[str, Any]:
    """
    Quick model selection across multiple model types.

    Args:
        X: Features
        y: Target
        model_types: List of model types to try
        method: Search method ("grid", "random", "bayesian")
        n_iter: Number of iterations for random/bayesian search
        scoring: Scoring metric
        cv_strategy: Cross-validation strategy
        n_splits: Number of CV splits

    Returns:
        Dictionary with best model and results
    """
    selector = ModelSelector(
        scoring=scoring, cv_strategy=cv_strategy, n_splits=n_splits
    )

    best_score = -np.inf
    best_model = None
    best_model_type = None

    for model_type in model_types:
        logger.info(f"Selecting hyperparameters for {model_type}")

        if method == "grid":
            param_grid = PARAM_GRIDS.get(model_type, {})
            result = selector.grid_search(X, y, model_type, param_grid)
        elif method == "random":
            param_dist = PARAM_DISTRIBUTIONS.get(model_type, {})
            result = selector.random_search(X, y, model_type, param_dist, n_iter=n_iter)
        elif method == "bayesian" and BAYESIAN_AVAILABLE:
            # Convert to Bayesian search spaces
            param_dist = PARAM_DISTRIBUTIONS.get(model_type, {})
            search_spaces = {}
            for param, values in param_dist.items():
                if isinstance(values[0], (int, float)):
                    search_spaces[param] = Real(min(values), max(values))
                else:
                    search_spaces[param] = Categorical(values)
            result = selector.bayesian_search(
                X, y, model_type, search_spaces, n_iter=n_iter
            )
        else:
            raise ValueError(f"Unknown method: {method}")

        if result["best_score"] > best_score:
            best_score = result["best_score"]
            best_model = result.get("best_model")
            best_model_type = model_type

    # Get summary
    summary = selector.get_summary()

    return {
        "best_model": best_model,
        "best_model_type": best_model_type,
        "best_score": best_score,
        "summary": summary,
        "selector": selector,
    }
