"""Time series cross-validation utilities for financial ML models.

This module provides specialized cross-validation approaches for time series data
that respect temporal ordering and prevent look-ahead bias.
"""

import logging
from typing import Any, Callable, Dict, Iterator, List, Optional, Tuple, Union

import numpy as np
import pandas as pd
from sklearn.base import BaseEstimator
from sklearn.metrics import (
    accuracy_score,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import BaseCrossValidator, TimeSeriesSplit

logger = logging.getLogger(__name__)


class TimeSeriesWalkForwardCV(BaseCrossValidator):
    """Time series walk-forward cross-validation.

    This cross-validator provides train/test indices to split time series data samples
    in a way that respects the temporal order, using a sliding window approach with
    fixed or expanding training window.

    Parameters
    ----------
    n_splits : int, default=5
        Number of splitting iterations.
    train_size : int or float, default=None
        Number of samples or proportion of the dataset to include in the training split.
        If None, the training size is set to the complement of the test size.
    test_size : int or float, default=0.2
        Number of samples or proportion of the dataset to include in the testing split.
    fixed_window : bool, default=False
        If True, use a fixed-size training window; if False, use an expanding window.
    gap : int, default=0
        Number of samples to exclude from the end of each training set before the test set.
    """

    def __init__(
        self,
        n_splits: int = 5,
        train_size: Optional[Union[int, float]] = None,
        test_size: Union[int, float] = 0.2,
        fixed_window: bool = False,
        gap: int = 0,
    ):
        self.n_splits = n_splits
        self.train_size = train_size
        self.test_size = test_size
        self.fixed_window = fixed_window
        self.gap = gap

    def split(
        self,
        X: Union[np.ndarray, pd.DataFrame],
        y: Optional[Union[np.ndarray, pd.Series]] = None,
        groups: Optional[Union[np.ndarray, pd.Series]] = None,
    ) -> Iterator[Tuple[np.ndarray, np.ndarray]]:
        """Generate indices to split data into training and test sets.

        Parameters
        ----------
        X : array-like of shape (n_samples, n_features)
            Training data, where n_samples is the number of samples
            and n_features is the number of features.
        y : array-like of shape (n_samples,), default=None
            Target variable.
        groups : array-like of shape (n_samples,), default=None
            Group labels for the samples. This parameter is not used.

        Yields
        ------
        train : ndarray
            The training set indices for that split.
        test : ndarray
            The testing set indices for that split.
        """
        n_samples = len(X)

        # Convert test_size to number of samples
        if isinstance(self.test_size, float):
            test_size = int(n_samples * self.test_size)
        else:
            test_size = self.test_size

        # Calculate train_size
        if self.train_size is None:
            # Default training size: use all available data before test set and gap
            max_train_size = n_samples - test_size - self.gap * self.n_splits
            train_size = max_train_size // self.n_splits
        elif isinstance(self.train_size, float):
            train_size = int(n_samples * self.train_size)
        else:
            train_size = self.train_size

        # Check if the sizes are valid
        if train_size <= 0 or test_size <= 0:
            raise ValueError(
                f"Both train_size={train_size} and test_size={test_size} "
                f"must be positive"
            )

        if train_size + test_size + self.gap > n_samples:
            raise ValueError(
                f"train_size={train_size} + test_size={test_size} + gap={self.gap} "
                f"should be less than or equal to n_samples={n_samples}"
            )

        # Generate the split indices
        if self.fixed_window:
            # Fixed-size window: training window size remains constant
            for i in range(self.n_splits):
                if (n_samples - train_size - test_size - i * test_size - self.gap) < 0:
                    # Not enough data for another split
                    break

                train_start = (
                    n_samples - train_size - test_size - i * test_size - self.gap
                )
                train_end = train_start + train_size
                test_start = train_end + self.gap
                test_end = test_start + test_size

                train_indices = np.arange(train_start, train_end)
                test_indices = np.arange(test_start, test_end)

                yield train_indices, test_indices
        else:
            # Expanding window: training window expands as we move back in time
            min_train_size = train_size  # Minimum initial training size

            for i in range(self.n_splits):
                if i == 0:
                    # First split uses initial train_size
                    train_start = n_samples - min_train_size - test_size - self.gap
                    train_end = n_samples - test_size - self.gap
                else:
                    # Expand training set backwards
                    train_start = (
                        n_samples - min_train_size - test_size * (i + 1) - self.gap
                    )
                    train_end = n_samples - test_size * i - self.gap

                if train_start < 0:
                    # Not enough data for another split
                    break

                test_start = train_end + self.gap
                test_end = test_start + test_size

                train_indices = np.arange(train_start, train_end)
                test_indices = np.arange(test_start, test_end)

                yield train_indices, test_indices

    def get_n_splits(
        self,
        X: Optional[Union[np.ndarray, pd.DataFrame]] = None,
        y: Optional[Union[np.ndarray, pd.Series]] = None,
        groups: Optional[Union[np.ndarray, pd.Series]] = None,
    ) -> int:
        """Returns the number of splitting iterations.

        Parameters
        ----------
        X : array-like, default=None
            Training data, where n_samples is the number of samples.
        y : array-like, default=None
            Always ignored, exists for compatibility.
        groups : array-like, default=None
            Always ignored, exists for compatibility.

        Returns
        -------
        n_splits : int
            The number of splits.
        """
        if X is not None:
            n_samples = len(X)

            # Convert test_size to number of samples
            if isinstance(self.test_size, float):
                test_size = int(n_samples * self.test_size)
            else:
                test_size = self.test_size

            # Calculate train_size
            if self.train_size is None:
                max_train_size = n_samples - test_size - self.gap * self.n_splits
                train_size = max_train_size // self.n_splits
            elif isinstance(self.train_size, float):
                train_size = int(n_samples * self.train_size)
            else:
                train_size = self.train_size

            if self.fixed_window:
                # Compute how many splits we can make with a fixed window
                available_samples = n_samples - train_size - self.gap
                possible_splits = available_samples // test_size
                return min(self.n_splits, possible_splits)
            else:
                # For expanding window, calculate how far back we can go
                min_train_size = train_size
                total_required = (
                    min_train_size
                    + test_size * self.n_splits
                    + self.gap * self.n_splits
                )

                if total_required > n_samples:
                    # Calculate how many splits we can actually make
                    return max(1, (n_samples - min_train_size - self.gap) // test_size)
                else:
                    return self.n_splits
        else:
            return self.n_splits


class BlockingTimeSeriesSplit(BaseCrossValidator):
    """Block time series cross-validation with purging and embargo.

    This cross-validator provides training/testing indices to split time series
    data by creating non-overlapping blocks of data. It also supports purging and
    embargo to prevent leakage in financial datasets where samples might overlap.

    Purging removes training observations that overlap with test set events.
    Embargo removes additional training observations after a test set event to
    prevent leakage from serial correlation.

    Parameters
    ----------
    n_splits : int, default=5
        Number of splits.
    block_size : int, default=None
        Size of each block in number of observations. If None, computed from n_splits.
    purge_window : int, default=0
        Number of observations to remove from training set before/after test set events.
    embargo_size : int, default=0
        Number of observations to remove after test set to account for serial correlation.
    """

    def __init__(
        self,
        n_splits: int = 5,
        block_size: Optional[int] = None,
        purge_window: int = 0,
        embargo_size: int = 0,
    ):
        self.n_splits = n_splits
        self.block_size = block_size
        self.purge_window = purge_window
        self.embargo_size = embargo_size

    def split(
        self,
        X: Union[np.ndarray, pd.DataFrame],
        y: Optional[Union[np.ndarray, pd.Series]] = None,
        groups: Optional[Union[np.ndarray, pd.Series]] = None,
    ) -> Iterator[Tuple[np.ndarray, np.ndarray]]:
        """Generate indices to split data into training and test set.

        Parameters
        ----------
        X : array-like of shape (n_samples, n_features)
            Training data, where n_samples is the number of samples
            and n_features is the number of features.
        y : array-like of shape (n_samples,), default=None
            Target variable.
        groups : array-like of shape (n_samples,), default=None
            Event labels or event timestamps for samples, used for purging.

        Yields
        ------
        train : ndarray
            The training set indices for that split.
        test : ndarray
            The testing set indices for that split.
        """
        n_samples = len(X)

        # Calculate block size if not specified
        if self.block_size is None:
            block_size = n_samples // self.n_splits
        else:
            block_size = self.block_size

        # Generate blocks
        for i in range(self.n_splits):
            test_start = i * block_size
            test_end = test_start + block_size

            if test_end > n_samples:
                break

            # Create initial train and test indices
            test_indices = np.arange(test_start, test_end)
            train_indices = np.concatenate(
                [np.arange(0, test_start), np.arange(test_end, n_samples)]
            )

            # Apply purging if groups are provided (event timestamps or labels)
            if groups is not None and self.purge_window > 0:
                train_indices = self._purge_indices(train_indices, test_indices, groups)

            # Apply embargo
            if self.embargo_size > 0:
                train_indices = self._apply_embargo(train_indices, test_indices)

            yield train_indices, test_indices

    def _purge_indices(
        self,
        train_indices: np.ndarray,
        test_indices: np.ndarray,
        groups: Union[np.ndarray, pd.Series],
    ) -> np.ndarray:
        """Apply purging to remove overlapping observations from training set.

        Parameters
        ----------
        train_indices : ndarray
            Training set indices.
        test_indices : ndarray
            Test set indices.
        groups : array-like
            Event labels or timestamps for samples.

        Returns
        -------
        purged_train_indices : ndarray
            Purged training set indices.
        """
        if isinstance(groups, pd.Series):
            groups = groups.values

        # Create mask of indices to keep
        keep_mask = np.ones(len(train_indices), dtype=bool)

        for test_idx in test_indices:
            test_event = groups[test_idx]

            # Find training indices that are close to this test event
            for i, train_idx in enumerate(train_indices):
                train_event = groups[train_idx]

                if hasattr(train_event, "timestamp") and hasattr(
                    test_event, "timestamp"
                ):
                    # For datetime objects
                    time_diff = abs((train_event - test_event).total_seconds())
                    if time_diff < self.purge_window:
                        keep_mask[i] = False
                elif isinstance(train_event, (int, float)) and isinstance(
                    test_event, (int, float)
                ):
                    # For numerical values
                    if abs(train_event - test_event) < self.purge_window:
                        keep_mask[i] = False
                else:
                    # For categorical/other types
                    if train_event == test_event:
                        keep_mask[i] = False

        return train_indices[keep_mask]

    def _apply_embargo(
        self, train_indices: np.ndarray, test_indices: np.ndarray
    ) -> np.ndarray:
        """Apply embargo to remove training samples after test period.

        Parameters
        ----------
        train_indices : ndarray
            Training set indices.
        test_indices : ndarray
            Test set indices.

        Returns
        -------
        embargoed_train_indices : ndarray
            Training indices with embargo applied.
        """
        if len(test_indices) == 0 or len(train_indices) == 0:
            return train_indices

        # Find min and max of test indices
        test_min, test_max = min(test_indices), max(test_indices)

        # Define embargo region
        embargo_min = max(0, test_min - self.embargo_size)
        embargo_max = min(test_max + self.embargo_size, max(train_indices) + 1)

        # Create mask for indices to keep
        keep_mask = np.ones(len(train_indices), dtype=bool)

        for i, idx in enumerate(train_indices):
            if embargo_min <= idx <= embargo_max:
                keep_mask[i] = False

        return train_indices[keep_mask]

    def get_n_splits(
        self,
        X: Optional[Union[np.ndarray, pd.DataFrame]] = None,
        y: Optional[Union[np.ndarray, pd.Series]] = None,
        groups: Optional[Union[np.ndarray, pd.Series]] = None,
    ) -> int:
        """Returns the number of splitting iterations.

        Parameters
        ----------
        X : array-like, default=None
            Training data, where n_samples is the number of samples.
        y : array-like, default=None
            Always ignored, exists for compatibility.
        groups : array-like, default=None
            Always ignored, exists for compatibility.

        Returns
        -------
        n_splits : int
            The number of splits.
        """
        if X is not None:
            n_samples = len(X)

            # Calculate block size if not specified
            if self.block_size is None:
                block_size = n_samples // self.n_splits
            else:
                block_size = self.block_size

            # Calculate how many complete blocks we can fit
            return min(self.n_splits, n_samples // block_size)

        return self.n_splits


def evaluate_timeseries_model(
    model: BaseEstimator,
    X: Union[np.ndarray, pd.DataFrame],
    y: Union[np.ndarray, pd.Series],
    cv: BaseCrossValidator = None,
    scoring_metrics: Optional[List[str]] = None,
    target_type: str = "classification",
    prediction_method: str = "predict",
    return_predictions: bool = False,
    custom_scorer: Optional[Callable] = None,
    **kwargs: Any,
) -> Dict[str, Union[float, List[float], Dict[str, List[float]]]]:
    """Evaluate a model using time series cross-validation.

    Parameters
    ----------
    model : BaseEstimator
        Scikit-learn compatible model to evaluate.
    X : array-like of shape (n_samples, n_features)
        Features dataset.
    y : array-like of shape (n_samples,)
        Target variable.
    cv : BaseCrossValidator, default=None
        Cross-validation splitter. If None, uses TimeSeriesWalkForwardCV with default settings.
    scoring_metrics : list of str, default=None
        List of metrics to compute. For classification: 'accuracy', 'precision', 'recall',
        'f1', 'roc_auc'. If None, uses all available metrics for the target type.
    target_type : str, default='classification'
        Type of prediction task: 'classification' or 'regression'.
    prediction_method : str, default='predict'
        Method to call on the model for predictions: 'predict', 'predict_proba'.
    return_predictions : bool, default=False
        If True, returns out-of-sample predictions.
    custom_scorer : callable, default=None
        Custom scoring function taking y_true, y_pred as input and returning a score.
    **kwargs : dict
        Additional arguments to pass to the model's fit method.

    Returns
    -------
    results : dict
        Dictionary containing evaluation metrics and optionally predictions.
    """
    if cv is None:
        cv = TimeSeriesWalkForwardCV(n_splits=5, test_size=0.2)

    if scoring_metrics is None:
        if target_type == "classification":
            scoring_metrics = ["accuracy", "precision", "recall", "f1", "roc_auc"]
        else:  # regression
            scoring_metrics = ["mse", "mae", "r2"]

    # Validate inputs
    if not isinstance(X, (np.ndarray, pd.DataFrame)):
        X = np.array(X)

    if not isinstance(y, (np.ndarray, pd.Series)):
        y = np.array(y)

    # Initialize results
    scores = {metric: [] for metric in scoring_metrics}
    all_test_indices = []
    all_predictions = []

    # Perform cross-validation
    for train_idx, test_idx in cv.split(X, y):
        # Get train/test split
        X_train = X[train_idx] if isinstance(X, np.ndarray) else X.iloc[train_idx]
        y_train = y[train_idx] if isinstance(y, np.ndarray) else y.iloc[train_idx]
        X_test = X[test_idx] if isinstance(X, np.ndarray) else X.iloc[test_idx]
        y_test = y[test_idx] if isinstance(y, np.ndarray) else y.iloc[test_idx]

        # Fit the model
        try:
            model.fit(X_train, y_train, **kwargs)
        except TypeError:
            model.fit(X_train, y_train)

        # Make predictions
        if prediction_method == "predict_proba" and hasattr(model, "predict_proba"):
            y_pred_proba = model.predict_proba(X_test)
            # For binary classification, use second column (probability of positive class)
            if y_pred_proba.shape[1] == 2:
                y_pred_score = y_pred_proba[:, 1]
            else:
                y_pred_score = y_pred_proba

            # For metrics requiring class labels
            y_pred = model.predict(X_test)
        else:
            y_pred = model.predict(X_test)
            y_pred_score = y_pred

        # Calculate metrics
        for metric in scoring_metrics:
            if metric == "accuracy":
                scores[metric].append(accuracy_score(y_test, y_pred))
            elif metric == "precision":
                scores[metric].append(
                    precision_score(y_test, y_pred, average="weighted", zero_division=0)
                )
            elif metric == "recall":
                scores[metric].append(
                    recall_score(y_test, y_pred, average="weighted", zero_division=0)
                )
            elif metric == "f1":
                scores[metric].append(
                    f1_score(y_test, y_pred, average="weighted", zero_division=0)
                )
            elif metric == "roc_auc":
                # Ensure binary classification for ROC AUC
                try:
                    if (
                        len(np.unique(y_test)) > 1
                    ):  # Need at least 2 classes in test set
                        scores[metric].append(roc_auc_score(y_test, y_pred_score))
                    else:
                        scores[metric].append(np.nan)
                except ValueError:
                    # Can happen with multi-class or when test set has only one class
                    scores[metric].append(np.nan)
            elif metric == "mse":
                scores[metric].append(np.mean((y_test - y_pred) ** 2))
            elif metric == "mae":
                scores[metric].append(np.mean(np.abs(y_test - y_pred)))
            elif metric == "r2":
                scores[metric].append(
                    1
                    - np.sum((y_test - y_pred) ** 2)
                    / np.sum((y_test - np.mean(y_test)) ** 2)
                )
            elif custom_scorer is not None:
                scores[metric].append(custom_scorer(y_test, y_pred))

        # Store predictions
        if return_predictions:
            all_test_indices.extend(test_idx)
            all_predictions.extend(y_pred)

    # Calculate mean and std of scores
    results = {
        "mean_scores": {
            metric: np.nanmean(scores[metric]) for metric in scoring_metrics
        },
        "std_scores": {metric: np.nanstd(scores[metric]) for metric in scoring_metrics},
        "cv_scores": scores,
    }

    # Add predictions if requested
    if return_predictions:
        # Sort predictions by original index
        sorted_idx = np.argsort(all_test_indices)
        results["predictions"] = np.array(all_predictions)[sorted_idx]
        results["indices"] = np.array(all_test_indices)[sorted_idx]

    return results


def strategy_performance_scoring(
    y_true: Union[np.ndarray, pd.Series],
    y_pred: Union[np.ndarray, pd.Series],
    returns: Optional[Union[np.ndarray, pd.Series]] = None,
    transaction_cost: float = 0.0,
    annualization_factor: int = 252,
) -> Dict[str, float]:
    """Calculate trading strategy performance metrics.

    Parameters
    ----------
    y_true : array-like
        True positions or directional signals (-1 for short, 0 for flat, 1 for long).
    y_pred : array-like
        Predicted positions or signals.
    returns : array-like, default=None
        Asset returns for each period. If provided, calculates profit metrics.
    transaction_cost : float, default=0.0
        Cost per transaction as a fraction of position value.
    annualization_factor : int, default=252
        Number of periods in a year for annualizing returns.

    Returns
    -------
    metrics : dict
        Dictionary of performance metrics.
    """
    if len(y_true) != len(y_pred):
        raise ValueError(
            f"Length mismatch: y_true has {len(y_true)} elements, "
            f"y_pred has {len(y_pred)} elements"
        )

    if returns is not None and len(returns) != len(y_true):
        raise ValueError(
            f"Length mismatch: y_true has {len(y_true)} elements, "
            f"returns has {len(returns)} elements"
        )

    # Convert to numpy arrays
    y_true = np.asarray(y_true)
    y_pred = np.asarray(y_pred)

    # Calculate directional accuracy
    directional_accuracy = np.mean(np.sign(y_true) == np.sign(y_pred))

    # Initialize results dictionary
    metrics = {
        "directional_accuracy": directional_accuracy,
    }

    # If returns are provided, calculate profit metrics
    if returns is not None:
        returns = np.asarray(returns)

        # Calculate strategy returns (without transaction costs)
        strategy_returns = (
            y_pred[:-1] * returns[1:]
        )  # Signals applied to next period's returns

        # Calculate transaction costs
        if transaction_cost > 0:
            # Identify position changes
            position_changes = np.diff(np.hstack([[0], y_pred]))
            transaction_costs = np.abs(position_changes) * transaction_cost

            # Apply transaction costs to strategy returns
            strategy_returns = strategy_returns - transaction_costs[:-1]

        # Calculate metrics
        total_return = np.prod(1 + strategy_returns) - 1
        mean_return = np.mean(strategy_returns)
        std_return = np.std(strategy_returns)

        # Annualized metrics
        periods_per_year = annualization_factor
        annualized_return = (1 + total_return) ** (
            periods_per_year / len(strategy_returns)
        ) - 1
        annualized_volatility = std_return * np.sqrt(periods_per_year)

        # Sharpe ratio (assuming risk-free rate = 0)
        sharpe_ratio = (
            mean_return / std_return * np.sqrt(periods_per_year)
            if std_return > 0
            else 0
        )

        # Maximum drawdown
        cumulative_returns = np.cumprod(1 + strategy_returns) - 1
        running_max = np.maximum.accumulate(cumulative_returns)
        drawdowns = (cumulative_returns - running_max) / (1 + running_max)
        max_drawdown = np.min(drawdowns)

        # Add to metrics
        metrics.update(
            {
                "total_return": total_return,
                "mean_return": mean_return,
                "std_return": std_return,
                "annualized_return": annualized_return,
                "annualized_volatility": annualized_volatility,
                "sharpe_ratio": sharpe_ratio,
                "max_drawdown": max_drawdown,
            }
        )

    return metrics
