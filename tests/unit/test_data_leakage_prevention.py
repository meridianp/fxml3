"""Unit tests to verify data leakage prevention in feature engineering.

This module contains comprehensive tests to ensure that feature engineering
processes do not introduce look-ahead bias or other forms of data leakage.
"""

import logging
from typing import Dict, List
from unittest.mock import patch

import numpy as np
import pandas as pd
import pytest

# Import the modules we're testing
from fxml4.features.feature_engineering import UnifiedFeatureEngineer
from fxml4.ml.features import (
    add_lagged_features,
    create_basic_technical_features,
    create_target_labels,
    validate_temporal_integrity,
)

logger = logging.getLogger(__name__)


class TestDataLeakagePrevention:
    """Test suite for data leakage prevention in feature engineering."""

    @pytest.fixture
    def sample_data(self) -> pd.DataFrame:
        """Create sample OHLCV data for testing."""
        np.random.seed(42)
        dates = pd.date_range("2023-01-01", periods=1000, freq="4H")

        # Create realistic forex data
        close_prices = 100 + np.cumsum(np.random.normal(0, 0.001, 1000))
        high_prices = close_prices + np.random.uniform(0, 0.002, 1000)
        low_prices = close_prices - np.random.uniform(0, 0.002, 1000)
        open_prices = close_prices + np.random.uniform(-0.001, 0.001, 1000)
        volume = np.random.uniform(1000, 10000, 1000)

        return pd.DataFrame(
            {
                "open": open_prices,
                "high": high_prices,
                "low": low_prices,
                "close": close_prices,
                "volume": volume,
            },
            index=dates,
        )

    def test_elliott_wave_no_look_ahead_bias(self, sample_data):
        """Test that Elliott Wave features don't use future data."""
        feature_engineer = UnifiedFeatureEngineer(
            {
                "elliott_wave_features": True,
                "advanced_features": False,
                "regime_features": False,
                "microstructure_features": False,
            }
        )

        # Generate features
        features = feature_engineer.generate_features(sample_data)

        # Test 1: Check that wave_trend at time t doesn't use data beyond time t
        for i in range(100, len(features) - 10):  # Skip edges
            current_wave_trend = features["wave_trend"].iloc[i]

            # Create a modified dataset where future data (after time i) is changed dramatically
            modified_data = sample_data.copy()
            modified_data.iloc[i + 1 :]["close"] *= 2  # Dramatic change in future

            # Regenerate features with modified future data
            modified_features = feature_engineer.generate_features(modified_data)
            modified_wave_trend = modified_features["wave_trend"].iloc[i]

            # Wave trend at time i should be identical despite future changes
            assert (
                abs(current_wave_trend - modified_wave_trend) < 1e-6
            ), f"Elliott Wave feature at time {i} changed when future data was modified"

    def test_fibonacci_levels_temporal_integrity(self, sample_data):
        """Test that Fibonacci levels are calculated using only historical data."""
        feature_engineer = UnifiedFeatureEngineer(
            {
                "elliott_wave_features": True,
                "advanced_features": False,
                "regime_features": False,
                "microstructure_features": False,
            }
        )

        features = feature_engineer.generate_features(sample_data)

        # Test that Fibonacci levels at time t don't use data beyond time t
        test_points = [200, 400, 600, 800]  # Various test points

        for i in test_points:
            current_fib_support = features["fib_support"].iloc[i]
            current_fib_resistance = features["fib_resistance"].iloc[i]

            # Modify future data dramatically
            modified_data = sample_data.copy()
            modified_data.iloc[i + 1 :]["high"] *= 1.5
            modified_data.iloc[i + 1 :]["low"] *= 0.5

            # Regenerate features
            modified_features = feature_engineer.generate_features(modified_data)

            # Fibonacci levels should be unchanged
            assert (
                abs(current_fib_support - modified_features["fib_support"].iloc[i])
                < 1e-6
            )
            assert (
                abs(
                    current_fib_resistance - modified_features["fib_resistance"].iloc[i]
                )
                < 1e-6
            )

    def test_technical_indicators_no_future_data(self, sample_data):
        """Test that technical indicators don't use future data."""
        # Test all basic indicators
        features = create_basic_technical_features(
            sample_data,
            indicators=[
                "sma",
                "ema",
                "rsi",
                "macd",
                "bollinger",
                "stoch",
                "atr",
                "adx",
            ],
            ma_periods=[5, 21, 55],
            include_original=True,
            fillna=True,
        )

        # Test point in the middle of the data
        test_idx = 500

        # Key indicators to test
        indicators_to_test = [
            "sma_21",
            "ema_21",
            "rsi_14",
            "macd",
            "bb_upper",
            "stoch_k",
            "atr_14",
            "adx_14",
        ]

        for indicator in indicators_to_test:
            if indicator not in features.columns:
                continue

            current_value = features[indicator].iloc[test_idx]

            # Modify future data
            modified_data = sample_data.copy()
            modified_data.iloc[test_idx + 1 :]["close"] += 10  # Large future change

            # Recalculate features
            modified_features = create_basic_technical_features(
                modified_data,
                indicators=[
                    "sma",
                    "ema",
                    "rsi",
                    "macd",
                    "bollinger",
                    "stoch",
                    "atr",
                    "adx",
                ],
                ma_periods=[5, 21, 55],
                include_original=True,
                fillna=True,
            )

            modified_value = modified_features[indicator].iloc[test_idx]

            # Values should be identical (no look-ahead bias)
            assert (
                abs(current_value - modified_value) < 1e-8
            ), f"Indicator {indicator} at time {test_idx} uses future data"

    def test_target_creation_proper_alignment(self, sample_data):
        """Test that target creation uses appropriate temporal alignment."""
        horizon = 10

        # Create targets
        data_with_targets = create_target_labels(
            sample_data, method="fixed_threshold", horizon=horizon, threshold=0.001
        )

        target_col = f"target_{horizon}"

        # Test 1: Check that exactly 'horizon' rows at the end have NaN targets
        nan_count = data_with_targets[target_col].isna().sum()
        assert nan_count == horizon, f"Expected {horizon} NaN targets, got {nan_count}"

        # Test 2: Check that NaN targets are at the end
        last_valid_idx = data_with_targets[target_col].last_valid_index()
        if last_valid_idx is not None:
            last_valid_pos = data_with_targets.index.get_loc(last_valid_idx)
            expected_pos = len(data_with_targets) - horizon - 1
            assert (
                abs(last_valid_pos - expected_pos) <= 1
            ), "Target NaN pattern is incorrect"

        # Test 3: Validate temporal integrity using our validation function
        feature_cols = [
            col
            for col in data_with_targets.columns
            if col not in ["open", "high", "low", "close", "volume", target_col]
        ]

        validation_results = validate_temporal_integrity(
            data_with_targets, feature_cols, target_col, horizon
        )

        assert validation_results[
            "temporal_integrity_passed"
        ], f"Temporal integrity validation failed: {validation_results['issues_found']}"

    def test_rolling_window_calculations(self, sample_data):
        """Test that rolling window calculations don't include current data point."""
        # Test moving averages specifically
        features = create_basic_technical_features(
            sample_data, indicators=["sma"], ma_periods=[20], include_original=True
        )

        # Test at various points
        for test_idx in [50, 100, 200, 500]:
            sma_20 = features["sma_20"].iloc[test_idx]

            # Calculate expected SMA using only historical data (excluding current point)
            historical_prices = sample_data["close"].iloc[
                test_idx - 19 : test_idx + 1
            ]  # 20 points including current
            expected_sma = historical_prices.mean()

            # They should be equal (within floating point precision)
            assert (
                abs(sma_20 - expected_sma) < 1e-10
            ), f"SMA calculation at index {test_idx} doesn't match expected value"

    def test_lagged_features_proper_shift(self, sample_data):
        """Test that lagged features use proper historical data."""
        # Add some basic features first
        features = create_basic_technical_features(
            sample_data,
            indicators=["sma", "rsi"],
            ma_periods=[21],
            include_original=True,
        )

        # Add lagged features
        lagged_features = add_lagged_features(
            features, columns=["close", "rsi_14"], lags=[1, 2, 5], include_returns=True
        )

        # Test that lag_1 features are correctly shifted
        test_idx = 100

        # close_lag_1 at time t should equal close at time t-1
        assert (
            abs(
                lagged_features["close_lag_1"].iloc[test_idx]
                - lagged_features["close"].iloc[test_idx - 1]
            )
            < 1e-10
        )

        # rsi_14_lag_2 at time t should equal rsi_14 at time t-2
        if not pd.isna(lagged_features["rsi_14_lag_2"].iloc[test_idx]):
            assert (
                abs(
                    lagged_features["rsi_14_lag_2"].iloc[test_idx]
                    - lagged_features["rsi_14"].iloc[test_idx - 2]
                )
                < 1e-10
            )

    def test_no_future_correlation_leakage(self, sample_data):
        """Test for subtle correlation-based data leakage."""
        feature_engineer = UnifiedFeatureEngineer()
        features = feature_engineer.generate_features(sample_data)

        # Remove non-feature columns
        feature_cols = [
            col
            for col in features.columns
            if col not in ["open", "high", "low", "close", "volume"]
        ]

        horizon = 10

        # Validate using our temporal integrity function
        data_with_targets = create_target_labels(features, horizon=horizon)
        target_col = f"target_{horizon}"

        validation_results = validate_temporal_integrity(
            data_with_targets,
            feature_cols[:5],  # Test first 5 features
            target_col,
            horizon,
        )

        # Should pass temporal integrity checks
        assert validation_results[
            "temporal_integrity_passed"
        ], f"Temporal integrity validation failed: {validation_results}"

        # Check for excessive correlations (potential leakage indicators)
        excessive_corr_warnings = [
            w for w in validation_results["warnings"] if "very high correlation" in w
        ]

        # Should not have excessive correlation warnings
        assert (
            len(excessive_corr_warnings) == 0
        ), f"Found potential data leakage through high correlations: {excessive_corr_warnings}"

    def test_feature_calculation_order_independence(self, sample_data):
        """Test that feature values don't depend on future data availability."""
        # Create two identical datasets but truncate the second one
        full_data = sample_data.copy()
        truncated_data = sample_data.iloc[:-50].copy()  # Remove last 50 rows

        feature_engineer = UnifiedFeatureEngineer()

        # Generate features for both datasets
        full_features = feature_engineer.generate_features(full_data)
        truncated_features = feature_engineer.generate_features(truncated_data)

        # Compare overlapping period - features should be identical
        overlap_end = len(truncated_features)
        feature_cols = [
            col
            for col in full_features.columns
            if col not in ["open", "high", "low", "close", "volume"]
        ]

        for col in feature_cols:
            if col not in truncated_features.columns:
                continue

            # Compare the overlapping period
            full_values = full_features[col].iloc[:overlap_end]
            truncated_values = truncated_features[col]

            # Values should be identical (allowing for small numerical differences)
            diff = (full_values - truncated_values).abs()
            max_diff = diff.max()

            assert max_diff < 1e-10 or pd.isna(
                max_diff
            ), f"Feature {col} shows dependency on future data: max_diff={max_diff}"

    def test_regime_features_no_future_leakage(self, sample_data):
        """Test that market regime features don't use future data."""
        feature_engineer = UnifiedFeatureEngineer(
            {
                "regime_features": True,
                "elliott_wave_features": False,
                "advanced_features": False,
                "microstructure_features": False,
            }
        )

        features = feature_engineer.generate_features(sample_data)

        # Test regime features
        regime_cols = ["vol_regime", "trend_regime", "momentum_regime"]
        test_idx = 500

        for col in regime_cols:
            if col not in features.columns:
                continue

            current_value = features[col].iloc[test_idx]

            # Modify future data
            modified_data = sample_data.copy()
            modified_data.iloc[test_idx + 1 :]["close"] *= 1.5  # Large future change

            # Recalculate features
            modified_features = feature_engineer.generate_features(modified_data)
            modified_value = modified_features[col].iloc[test_idx]

            # Values should be identical
            assert (
                abs(current_value - modified_value) < 1e-8
            ), f"Regime feature {col} at time {test_idx} uses future data"

    def test_validation_function_catches_leakage(self, sample_data):
        """Test that our validation function properly catches data leakage."""
        # Create a dataset with intentional data leakage
        leaky_data = sample_data.copy()

        # Add a feature that uses future data (this should be caught)
        leaky_data["leaky_feature"] = leaky_data["close"].shift(-5)  # Uses future data!

        # Add a proper target
        leaky_data = create_target_labels(leaky_data, horizon=10)
        target_col = "target_10"

        # Run validation
        validation_results = validate_temporal_integrity(
            leaky_data, ["leaky_feature"], target_col, 10
        )

        # Should detect the issue through correlation analysis
        warnings = validation_results["warnings"]
        correlation_warnings = [w for w in warnings if "correlation" in w.lower()]

        # Should find high correlation warning (indicating potential leakage)
        assert (
            len(correlation_warnings) > 0
        ), "Validation function failed to detect obvious data leakage"


if __name__ == "__main__":
    # Run tests if executed directly
    pytest.main([__file__, "-v"])
