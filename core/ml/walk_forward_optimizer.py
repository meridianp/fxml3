"""Walk-forward optimization to prevent overfitting and improve out-of-sample performance."""

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

import joblib
import numpy as np
import pandas as pd
from sklearn.base import BaseEstimator
from sklearn.metrics import accuracy_score, precision_score, recall_score
from sklearn.preprocessing import StandardScaler

logger = logging.getLogger(__name__)


class WalkForwardOptimizer:
    """
    Implements walk-forward optimization for time series ML models.

    This prevents overfitting by:
    1. Training on historical window
    2. Validating on next period
    3. Testing on out-of-sample future period
    4. Rolling forward and repeating
    """

    def __init__(
        self,
        train_window_days: int = 365,
        validation_days: int = 90,
        test_days: int = 30,
        step_days: int = 30,
        purge_days: int = 2,
    ):
        """
        Initialize walk-forward optimizer.

        Args:
            train_window_days: Days of data for training
            validation_days: Days for validation/parameter tuning
            test_days: Days for out-of-sample testing
            step_days: Days to step forward each iteration
            purge_days: Days to skip between sets (prevent leakage)
        """
        self.train_window_days = train_window_days
        self.validation_days = validation_days
        self.test_days = test_days
        self.step_days = step_days
        self.purge_days = purge_days

    def create_folds(
        self, data: pd.DataFrame, start_date: Optional[datetime] = None
    ) -> List[Dict[str, Tuple[datetime, datetime]]]:
        """
        Create walk-forward folds with proper time gaps.

        Returns:
            List of fold dictionaries with train/val/test date ranges
        """
        if start_date is None:
            start_date = data.index.min() + timedelta(days=self.train_window_days)

        end_date = data.index.max() - timedelta(days=self.test_days)

        folds = []
        current_date = start_date

        while current_date < end_date:
            fold = {
                "train": (
                    current_date - timedelta(days=self.train_window_days),
                    current_date,
                ),
                "validation": (
                    current_date + timedelta(days=self.purge_days),
                    current_date
                    + timedelta(days=self.purge_days + self.validation_days),
                ),
                "test": (
                    current_date
                    + timedelta(
                        days=self.purge_days + self.validation_days + self.purge_days
                    ),
                    current_date
                    + timedelta(
                        days=self.purge_days
                        + self.validation_days
                        + self.purge_days
                        + self.test_days
                    ),
                ),
            }

            # Ensure test end doesn't exceed data
            if fold["test"][1] <= data.index.max():
                folds.append(fold)

            current_date += timedelta(days=self.step_days)

        return folds

    def optimize_parameters(
        self,
        model_class,
        param_grid: Dict[str, List],
        X_train: pd.DataFrame,
        y_train: pd.Series,
        X_val: pd.DataFrame,
        y_val: pd.Series,
        sample_weight: Optional[np.ndarray] = None,
    ) -> Tuple[BaseEstimator, Dict[str, Any]]:
        """
        Find optimal parameters using validation set.

        Returns:
            Best model and parameters
        """
        best_score = -np.inf
        best_params = None
        best_model = None

        # Grid search over parameters
        from itertools import product

        param_names = list(param_grid.keys())
        param_values = list(param_grid.values())

        for params in product(*param_values):
            param_dict = dict(zip(param_names, params))

            try:
                # Train model with current parameters
                model = model_class(**param_dict)

                if sample_weight is not None:
                    model.fit(X_train, y_train, sample_weight=sample_weight)
                else:
                    model.fit(X_train, y_train)

                # Evaluate on validation set
                val_pred = model.predict(X_val)
                val_score = accuracy_score(y_val, val_pred)

                # Track best model
                if val_score > best_score:
                    best_score = val_score
                    best_params = param_dict
                    best_model = model

            except Exception as e:
                logger.warning(f"Failed to train with params {param_dict}: {e}")
                continue

        return best_model, best_params

    def create_sample_weights(
        self, dates: pd.DatetimeIndex, decay_factor: float = 0.95
    ) -> np.ndarray:
        """
        Create exponentially decaying weights for recent data emphasis.
        """
        # Convert to numpy array to handle calculations
        dates_array = pd.to_datetime(dates)
        max_date = dates_array.max()
        days_ago = np.array([(max_date - d).days for d in dates_array])
        weights = decay_factor ** (days_ago / 30)  # Monthly decay
        return weights / weights.sum() * len(weights)

    def run_backtest(
        self,
        model_class,
        param_grid: Dict[str, List],
        data: pd.DataFrame,
        feature_cols: List[str],
        target_col: str,
        use_sample_weights: bool = True,
    ) -> Dict[str, Any]:
        """
        Run complete walk-forward optimization backtest.

        Returns:
            Dictionary with results and performance metrics
        """
        folds = self.create_folds(data)
        logger.info(f"Created {len(folds)} walk-forward folds")

        results = {"folds": [], "predictions": [], "models": [], "parameters": []}

        for i, fold in enumerate(folds):
            logger.info(f"Processing fold {i+1}/{len(folds)}")

            # Extract data for each period
            train_mask = (data.index >= fold["train"][0]) & (
                data.index <= fold["train"][1]
            )
            val_mask = (data.index >= fold["validation"][0]) & (
                data.index <= fold["validation"][1]
            )
            test_mask = (data.index >= fold["test"][0]) & (
                data.index <= fold["test"][1]
            )

            X_train = data.loc[train_mask, feature_cols]
            y_train = data.loc[train_mask, target_col]
            X_val = data.loc[val_mask, feature_cols]
            y_val = data.loc[val_mask, target_col]
            X_test = data.loc[test_mask, feature_cols]
            y_test = data.loc[test_mask, target_col]

            # Skip if insufficient data
            if len(X_train) < 100 or len(X_val) < 20 or len(X_test) < 10:
                continue

            # Standardize features
            scaler = StandardScaler()
            X_train_scaled = scaler.fit_transform(X_train)
            X_val_scaled = scaler.transform(X_val)
            X_test_scaled = scaler.transform(X_test)

            # Create sample weights if requested
            sample_weight = None
            if use_sample_weights:
                sample_weight = self.create_sample_weights(X_train.index)

            # Optimize parameters on validation set
            best_model, best_params = self.optimize_parameters(
                model_class,
                param_grid,
                X_train_scaled,
                y_train,
                X_val_scaled,
                y_val,
                sample_weight,
            )

            # Evaluate on test set
            test_pred = best_model.predict(X_test_scaled)
            test_proba = (
                best_model.predict_proba(X_test_scaled)
                if hasattr(best_model, "predict_proba")
                else None
            )

            # Calculate metrics
            fold_results = {
                "fold": i,
                "train_period": fold["train"],
                "val_period": fold["validation"],
                "test_period": fold["test"],
                "test_accuracy": accuracy_score(y_test, test_pred),
                "test_precision": precision_score(
                    y_test, test_pred, average="weighted", zero_division=0
                ),
                "test_recall": recall_score(
                    y_test, test_pred, average="weighted", zero_division=0
                ),
                "n_train": len(X_train),
                "n_val": len(X_val),
                "n_test": len(X_test),
                "best_params": best_params,
            }

            # Store predictions
            for j, (idx, pred) in enumerate(zip(X_test.index, test_pred)):
                results["predictions"].append(
                    {
                        "timestamp": idx,
                        "fold": i,
                        "prediction": pred,
                        "probability": (
                            test_proba[j].max() if test_proba is not None else None
                        ),
                        "actual": y_test.iloc[j],
                    }
                )

            results["folds"].append(fold_results)
            results["models"].append(best_model)
            results["parameters"].append(best_params)

        # Calculate aggregate metrics
        all_predictions = pd.DataFrame(results["predictions"])

        if not all_predictions.empty:
            # Remove duplicate predictions (keep last fold's prediction)
            all_predictions = all_predictions.sort_values(["timestamp", "fold"])
            all_predictions = all_predictions.drop_duplicates("timestamp", keep="last")

            results["aggregate_metrics"] = {
                "total_predictions": len(all_predictions),
                "accuracy": accuracy_score(
                    all_predictions["actual"], all_predictions["prediction"]
                ),
                "precision": precision_score(
                    all_predictions["actual"],
                    all_predictions["prediction"],
                    average="weighted",
                    zero_division=0,
                ),
                "recall": recall_score(
                    all_predictions["actual"],
                    all_predictions["prediction"],
                    average="weighted",
                    zero_division=0,
                ),
                "avg_fold_accuracy": np.mean(
                    [f["test_accuracy"] for f in results["folds"]]
                ),
                "std_fold_accuracy": np.std(
                    [f["test_accuracy"] for f in results["folds"]]
                ),
            }

            # Analyze parameter stability
            param_counts = {}
            for params in results["parameters"]:
                param_str = str(sorted(params.items()))
                param_counts[param_str] = param_counts.get(param_str, 0) + 1

            results["parameter_stability"] = {
                "unique_param_sets": len(param_counts),
                "most_common_params": (
                    max(param_counts.items(), key=lambda x: x[1])[0]
                    if param_counts
                    else None
                ),
                "parameter_consistency": (
                    max(param_counts.values()) / len(results["parameters"])
                    if results["parameters"]
                    else 0
                ),
            }

        return results

    def combine_models(
        self, models: List[BaseEstimator], weights: Optional[List[float]] = None
    ) -> "EnsembleModel":
        """
        Combine multiple models from different folds into ensemble.
        """
        if weights is None:
            # Equal weights by default
            weights = [1.0 / len(models)] * len(models)

        return EnsembleModel(models, weights)


class EnsembleModel:
    """Simple ensemble of models with weighted voting."""

    def __init__(self, models: List[BaseEstimator], weights: List[float]):
        self.models = models
        self.weights = np.array(weights)

    def predict(self, X):
        """Weighted majority vote prediction."""
        predictions = np.array([model.predict(X) for model in self.models])

        # Weighted voting
        weighted_votes = np.zeros((X.shape[0], 3))  # Assuming 3 classes

        for i, (pred, weight) in enumerate(zip(predictions, self.weights)):
            for j in range(X.shape[0]):
                weighted_votes[j, pred[j]] += weight

        return np.argmax(weighted_votes, axis=1)

    def predict_proba(self, X):
        """Average probability predictions."""
        if not hasattr(self.models[0], "predict_proba"):
            return None

        probas = np.array([model.predict_proba(X) for model in self.models])

        # Weighted average
        weighted_proba = np.zeros_like(probas[0])
        for proba, weight in zip(probas, self.weights):
            weighted_proba += proba * weight

        return weighted_proba
