"""Advanced time series cross-validation utilities for financial ML models.

This module provides specialized cross-validation approaches for time series data
that respect temporal ordering and prevent look-ahead bias, with features specific
to financial data such as purging and embargo.
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


class CombinedSignalCV(BaseCrossValidator):
    """Cross-validation for combined trading signals.

    This cross-validator is specifically designed for financial time series where
    the prediction task involves combining signals from multiple sources (e.g., ML models
    and Elliott Wave analysis).

    Parameters
    ----------
    n_splits : int, default=5
        Number of splits.
    train_size : int or float, default=0.7
        Number of samples or proportion of the dataset to include in the training split.
    test_size : int or float, default=0.3
        Number of samples or proportion of the dataset to include in the testing split.
    embargo_size : int, default=0
        Number of samples to exclude after test set to prevent leakage.
    """

    def __init__(
        self,
        n_splits: int = 5,
        train_size: Union[int, float] = 0.7,
        test_size: Union[int, float] = 0.3,
        embargo_size: int = 0,
    ):
        self.n_splits = n_splits
        self.train_size = train_size
        self.test_size = test_size
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
            Signal source labels for samples.

        Yields
        ------
        train : ndarray
            The training set indices for that split.
        test : ndarray
            The testing set indices for that split.
        """
        n_samples = len(X)

        # Convert train_size and test_size to number of samples
        if isinstance(self.train_size, float):
            train_size = int(n_samples * self.train_size)
        else:
            train_size = self.train_size

        if isinstance(self.test_size, float):
            test_size = int(n_samples * self.test_size)
        else:
            test_size = self.test_size

        # Check if sizes are valid
        if train_size + test_size > n_samples:
            raise ValueError(
                f"train_size={train_size} + test_size={test_size} "
                f"should be less than or equal to n_samples={n_samples}"
            )

        # Create anchor points for splits
        anchor_points = np.linspace(
            0, n_samples - train_size - test_size, self.n_splits, dtype=int
        )

        for anchor in anchor_points:
            train_start = anchor
            train_end = train_start + train_size
            test_start = train_end + self.embargo_size
            test_end = min(test_start + test_size, n_samples)

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
        return self.n_splits


def evaluate_trading_strategy(
    model: BaseEstimator,
    X: Union[np.ndarray, pd.DataFrame],
    y: Optional[Union[np.ndarray, pd.Series]],
    returns: Union[np.ndarray, pd.Series],
    cv: BaseCrossValidator = None,
    transaction_cost: float = 0.0,
    hold_period: int = 1,
    annualization_factor: int = 252,
    return_trades: bool = False,
    **kwargs: Any,
) -> Dict[str, Any]:
    """Evaluate a trading strategy using time series cross-validation.

    Parameters
    ----------
    model : BaseEstimator
        Scikit-learn compatible model to evaluate.
    X : array-like of shape (n_samples, n_features)
        Features dataset.
    y : array-like of shape (n_samples,), default=None
        Target variable (optional for some strategies).
    returns : array-like of shape (n_samples,)
        Asset returns for each period.
    cv : BaseCrossValidator, default=None
        Cross-validation splitter. If None, uses TimeSeriesWalkForwardCV.
    transaction_cost : float, default=0.0
        Cost per transaction as a fraction of position value.
    hold_period : int, default=1
        Number of periods to hold each position.
    annualization_factor : int, default=252
        Number of periods in a year for annualizing returns.
    return_trades : bool, default=False
        If True, returns individual trades information.
    **kwargs : dict
        Additional arguments to pass to the model's fit method.

    Returns
    -------
    results : dict
        Dictionary containing strategy performance metrics.
    """
    if cv is None:
        cv = TimeSeriesWalkForwardCV(n_splits=5, test_size=0.2)

    # Validate inputs
    if not isinstance(X, (np.ndarray, pd.DataFrame)):
        X = np.array(X)

    if y is not None and not isinstance(y, (np.ndarray, pd.Series)):
        y = np.array(y)

    if not isinstance(returns, (np.ndarray, pd.Series)):
        returns = np.array(returns)

    # Ensure returns are aligned with X
    if len(returns) != len(X):
        raise ValueError(
            f"Length mismatch: X has {len(X)} samples, "
            f"returns has {len(returns)} samples"
        )

    # Initialize results
    all_metrics = []
    all_positions = []
    all_returns = []
    all_equity_curves = []
    all_trades = []

    # Perform cross-validation
    for train_idx, test_idx in cv.split(X):
        # Get train/test split
        X_train = X[train_idx] if isinstance(X, np.ndarray) else X.iloc[train_idx]
        X_test = X[test_idx] if isinstance(X, np.ndarray) else X.iloc[test_idx]

        y_train = (
            None
            if y is None
            else (y[train_idx] if isinstance(y, np.ndarray) else y.iloc[train_idx])
        )
        y_test = (
            None
            if y is None
            else (y[test_idx] if isinstance(y, np.ndarray) else y.iloc[test_idx])
        )

        returns_test = (
            returns[test_idx]
            if isinstance(returns, np.ndarray)
            else returns.iloc[test_idx]
        )

        # Fit the model
        if y is not None:
            try:
                model.fit(X_train, y_train, **kwargs)
            except TypeError:
                model.fit(X_train, y_train)
        else:
            try:
                model.fit(X_train, **kwargs)
            except TypeError:
                model.fit(X_train)

        # Generate positions
        positions = model.predict(X_test)

        # Apply hold period if needed
        if hold_period > 1:
            positions = _apply_hold_period(positions, hold_period)

        # Calculate strategy returns
        strategy_returns, trades_info = _calculate_strategy_returns(
            positions=positions, returns=returns_test, transaction_cost=transaction_cost
        )

        # Calculate equity curve
        equity_curve = (1 + strategy_returns).cumprod() - 1

        # Calculate performance metrics
        metrics = _calculate_performance_metrics(
            strategy_returns=strategy_returns, annualization_factor=annualization_factor
        )

        # Store results
        all_metrics.append(metrics)
        all_positions.append(positions)
        all_returns.append(strategy_returns)
        all_equity_curves.append(equity_curve)
        if return_trades:
            all_trades.extend(trades_info)

    # Calculate average metrics across CV folds
    avg_metrics = {}
    for key in all_metrics[0].keys():
        values = [m[key] for m in all_metrics]
        avg_metrics[f"{key}_mean"] = np.mean(values)
        avg_metrics[f"{key}_std"] = np.std(values)

    # Prepare final results
    results = {
        "cv_metrics": all_metrics,
        "avg_metrics": avg_metrics,
        "positions": all_positions,
        "strategy_returns": all_returns,
        "equity_curves": all_equity_curves,
    }

    if return_trades:
        results["trades"] = all_trades

    return results


def _apply_hold_period(positions: np.ndarray, hold_period: int) -> np.ndarray:
    """Apply holding period to position signals.

    Parameters
    ----------
    positions : ndarray
        Array of position signals.
    hold_period : int
        Number of periods to hold each position.

    Returns
    -------
    adjusted_positions : ndarray
        Positions adjusted for holding period.
    """
    if hold_period <= 1:
        return positions

    adjusted_positions = np.zeros_like(positions)
    current_position = 0
    hold_counter = 0

    for i in range(len(positions)):
        if hold_counter > 0:
            # Continue holding current position
            adjusted_positions[i] = current_position
            hold_counter -= 1
        else:
            # Check for new position
            if positions[i] != 0:
                current_position = positions[i]
                adjusted_positions[i] = current_position
                hold_counter = hold_period - 1
            else:
                adjusted_positions[i] = 0

    return adjusted_positions


def _calculate_strategy_returns(
    positions: np.ndarray, returns: np.ndarray, transaction_cost: float = 0.0
) -> Tuple[np.ndarray, List[Dict[str, Any]]]:
    """Calculate strategy returns from positions and price returns.

    Parameters
    ----------
    positions : ndarray
        Array of position signals.
    returns : ndarray
        Asset returns for each period.
    transaction_cost : float, default=0.0
        Cost per transaction as a fraction of position value.

    Returns
    -------
    strategy_returns : ndarray
        Strategy returns accounting for positions and costs.
    trades_info : list
        List of dictionaries with information about each trade.
    """
    if len(positions) != len(returns):
        raise ValueError(
            f"Length mismatch: positions has {len(positions)} elements, "
            f"returns has {len(returns)} elements"
        )

    # Initialize arrays
    strategy_returns = np.zeros(len(returns))
    trades_info = []

    # Track current position and entry price
    current_position = 0
    entry_idx = -1

    for i in range(len(returns) - 1):  # Skip the last return (no next period)
        # Calculate strategy return (position * next period's return)
        strategy_returns[i] = positions[i] * returns[i + 1]

        # Check for position change
        if positions[i] != current_position:
            # Record trade exit if we had a position
            if current_position != 0 and entry_idx >= 0:
                # Calculate trade result
                exit_price = 1.0  # Placeholder for price level
                if i > 0:
                    exit_price = (1 + returns[i]).cumprod()[-1]

                entry_price = 1.0  # Placeholder for price level
                if entry_idx > 0:
                    entry_price = (1 + returns[entry_idx]).cumprod()[-1]

                # Calculate trade profit/loss
                trade_return = (exit_price / entry_price - 1) * current_position
                trade_return -= transaction_cost  # Exit cost

                # Record trade
                trades_info.append(
                    {
                        "entry_idx": entry_idx,
                        "exit_idx": i,
                        "position": current_position,
                        "entry_price": entry_price,
                        "exit_price": exit_price,
                        "return": trade_return,
                        "duration": i - entry_idx,
                    }
                )

            # Apply transaction cost for new position
            if positions[i] != 0:
                strategy_returns[i] -= transaction_cost

            # Update position
            current_position = positions[i]
            entry_idx = i

    # Handle any open position at the end
    if current_position != 0 and entry_idx >= 0:
        # Record final trade using the last price
        exit_idx = len(returns) - 1

        exit_price = 1.0
        if exit_idx > 0:
            exit_price = (1 + returns[exit_idx]).cumprod()[-1]

        entry_price = 1.0
        if entry_idx > 0:
            entry_price = (1 + returns[entry_idx]).cumprod()[-1]

        trade_return = (exit_price / entry_price - 1) * current_position
        trade_return -= transaction_cost  # Exit cost

        trades_info.append(
            {
                "entry_idx": entry_idx,
                "exit_idx": exit_idx,
                "position": current_position,
                "entry_price": entry_price,
                "exit_price": exit_price,
                "return": trade_return,
                "duration": exit_idx - entry_idx,
            }
        )

    return strategy_returns, trades_info


def _calculate_performance_metrics(
    strategy_returns: np.ndarray, annualization_factor: int = 252
) -> Dict[str, float]:
    """Calculate performance metrics for a trading strategy.

    Parameters
    ----------
    strategy_returns : ndarray
        Strategy returns.
    annualization_factor : int, default=252
        Number of periods in a year for annualizing returns.

    Returns
    -------
    metrics : dict
        Dictionary of performance metrics.
    """
    # Basic return metrics
    total_return = (1 + strategy_returns).prod() - 1
    mean_return = np.mean(strategy_returns)
    std_return = np.std(strategy_returns)

    # Annualized metrics
    annualized_return = (1 + total_return) ** (
        annualization_factor / len(strategy_returns)
    ) - 1
    annualized_volatility = std_return * np.sqrt(annualization_factor)
    sharpe_ratio = (
        (mean_return / std_return) * np.sqrt(annualization_factor)
        if std_return > 0
        else 0
    )

    # Drawdown analysis
    cumulative_returns = (1 + strategy_returns).cumprod() - 1
    peak = np.maximum.accumulate(cumulative_returns)
    drawdown = (cumulative_returns - peak) / (1 + peak)
    max_drawdown = np.min(drawdown)

    # Calmar ratio
    calmar_ratio = annualized_return / abs(max_drawdown) if max_drawdown < 0 else np.inf

    # Winning trades analysis
    positive_returns = strategy_returns[strategy_returns > 0]
    negative_returns = strategy_returns[strategy_returns < 0]

    win_rate = (
        len(positive_returns) / len(strategy_returns)
        if len(strategy_returns) > 0
        else 0
    )
    profit_factor = (
        abs(np.sum(positive_returns) / np.sum(negative_returns))
        if np.sum(negative_returns) < 0
        else np.inf
    )

    # Combine metrics
    metrics = {
        "total_return": total_return,
        "mean_return": mean_return,
        "std_return": std_return,
        "annualized_return": annualized_return,
        "annualized_volatility": annualized_volatility,
        "sharpe_ratio": sharpe_ratio,
        "max_drawdown": max_drawdown,
        "calmar_ratio": calmar_ratio,
        "win_rate": win_rate,
        "profit_factor": profit_factor,
    }

    return metrics
