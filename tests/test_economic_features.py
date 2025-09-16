#!/usr/bin/env python3
"""Test module for economic feature engineering and regime classification."""

import os
import sys
from datetime import datetime, timedelta

import numpy as np
import pandas as pd
import pytest

# Add parent directory to path to allow importing fxml4
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fxml4.ml.economic_features import (
    EconomicFeatureEngineer,
    adjust_signals,
    create_economic_features,
    detect_regime,
)


@pytest.fixture
def economic_data():
    """Create sample economic data for testing."""
    # Create sample economic data
    date_range = pd.date_range(start="2020-01-01", end="2022-12-31", freq="M")

    # GDP data (quarterly frequency)
    gdp_dates = pd.date_range(start="2020-01-01", end="2022-12-31", freq="Q")
    gdp_values = [
        21.56,
        19.52,
        21.14,
        21.49,  # 2020
        22.74,
        23.20,
        23.20,
        24.00,  # 2021
        24.39,
        24.86,
        25.72,
        26.13,  # 2022
    ]
    gdp_data = pd.Series(index=gdp_dates, data=gdp_values)

    # Unemployment rate (monthly frequency)
    unemployment_dates = date_range
    unemployment_values = [
        3.6,
        3.5,
        4.4,
        14.7,
        13.3,
        11.1,
        10.2,
        8.4,
        7.8,
        6.9,
        6.7,
        6.7,  # 2020
        6.4,
        6.2,
        6.0,
        6.1,
        5.8,
        5.9,
        5.4,
        5.2,
        4.7,
        4.5,
        4.2,
        3.9,  # 2021
        4.0,
        3.8,
        3.6,
        3.6,
        3.6,
        3.6,
        3.5,
        3.7,
        3.5,
        3.7,
        3.6,
        3.5,  # 2022
    ]
    unemployment_data = pd.Series(index=unemployment_dates, data=unemployment_values)

    # Inflation (CPI, monthly frequency)
    inflation_dates = date_range
    inflation_values = [
        2.5,
        2.3,
        1.5,
        0.3,
        0.1,
        0.6,
        1.0,
        1.3,
        1.4,
        1.2,
        1.2,
        1.4,  # 2020
        1.4,
        1.7,
        2.6,
        4.2,
        5.0,
        5.4,
        5.4,
        5.3,
        5.4,
        6.2,
        6.8,
        7.0,  # 2021
        7.5,
        7.9,
        8.5,
        8.3,
        8.6,
        9.1,
        8.5,
        8.3,
        8.2,
        7.7,
        7.1,
        6.5,  # 2022
    ]
    # Convert to decimal form
    inflation_values = [v / 100 for v in inflation_values]
    inflation_data = pd.Series(index=inflation_dates, data=inflation_values)

    # Fed funds rate (monthly frequency)
    fed_funds_dates = date_range
    fed_funds_values = [
        1.55,
        1.58,
        0.65,
        0.05,
        0.05,
        0.08,
        0.09,
        0.10,
        0.09,
        0.09,
        0.09,
        0.09,  # 2020
        0.09,
        0.08,
        0.07,
        0.07,
        0.06,
        0.08,
        0.10,
        0.09,
        0.08,
        0.08,
        0.08,
        0.08,  # 2021
        0.08,
        0.08,
        0.20,
        0.33,
        0.77,
        1.21,
        1.68,
        2.33,
        2.56,
        3.08,
        3.78,
        4.33,  # 2022
    ]
    # Convert to decimal form
    fed_funds_values = [v / 100 for v in fed_funds_values]
    fed_funds_data = pd.Series(index=fed_funds_dates, data=fed_funds_values)

    # 10Y-2Y Treasury spread (monthly frequency, sometimes negative in inversions)
    yield_curve_dates = date_range
    yield_curve_values = [
        0.34,
        0.29,
        0.47,
        0.49,
        0.48,
        0.51,
        0.43,
        0.54,
        0.55,
        0.72,
        0.80,
        0.82,  # 2020
        1.03,
        1.25,
        1.58,
        1.46,
        1.40,
        1.17,
        1.09,
        1.03,
        1.15,
        1.07,
        0.75,
        0.77,  # 2021
        0.63,
        0.40,
        0.20,
        0.19,
        0.29,
        0.05,
        -0.05,
        -0.30,
        -0.32,
        -0.39,
        -0.70,
        -0.57,  # 2022
    ]
    # Convert to decimal form
    yield_curve_values = [v / 100 for v in yield_curve_values]
    yield_curve_data = pd.Series(index=yield_curve_dates, data=yield_curve_values)

    # Combine into one DataFrame
    return pd.DataFrame(
        {
            "GDP": gdp_data,
            "UNRATE": unemployment_data,
            "CPIAUCSL": inflation_data,
            "FEDFUNDS": fed_funds_data,
            "T10Y2Y": yield_curve_data,
        }
    )


@pytest.fixture
def trading_signals():
    """Create simulated trading signals for testing."""
    signal_dates = pd.date_range(start="2022-01-01", end="2022-12-31", freq="D")
    np.random.seed(42)  # For reproducibility
    return pd.Series(
        index=signal_dates, data=np.random.uniform(-1, 1, len(signal_dates))
    )


@pytest.fixture
def custom_config():
    """Create custom configuration for testing EconomicFeatureEngineer."""
    return {
        "economic_features": {
            "indicator_thresholds": {
                "UNRATE": {"high_threshold": 7.0},  # Higher threshold than default
                "CPIAUCSL": {"high_threshold": 0.05},  # Higher threshold than default
            },
            "regime_adjustment_factors": {
                "inflation": 0.6,  # Custom adjustment
                "recession_risk": 0.4,  # Custom adjustment
            },
        }
    }


class TestEconomicFeatures:
    """Test case for economic feature engineering."""

    def test_create_features(self, economic_data):
        """Test feature creation from economic data."""
        # Create features
        features = create_economic_features(economic_data)

        # Check that features were created
        assert len(features.columns) > len(economic_data.columns)

        # Check for specific feature types
        feature_columns = features.columns.tolist()

        # Check for rate of change features
        assert "GDP_4q_change" in feature_columns
        assert "CPIAUCSL_12m_change" in feature_columns

        # Check for z-score features
        assert "GDP_zscore" in feature_columns
        assert "UNRATE_zscore" in feature_columns

        # Check for relationship features
        assert "real_interest_rate" in feature_columns

    def test_regime_detection(self, economic_data):
        """Test economic regime detection."""
        # Create features first
        features = create_economic_features(economic_data)

        # Detect regimes
        regimes = detect_regime(features)

        # Check that regime is detected for each date
        assert len(regimes) == len(features)

        # Check that we have multiple regime types
        unique_regimes = regimes.unique()
        assert len(unique_regimes) > 1

        # Given our sample data, we should see inflation and recession_risk regimes
        regime_types = regimes.value_counts().to_dict()

        # In our sample data, we should definitely have high inflation in 2022
        assert "inflation" in regime_types

        # We should also have yield curve inversion (recession_risk) in late 2022
        assert "recession_risk" in regime_types

    def test_signal_adjustment(self, economic_data, trading_signals):
        """Test trading signal adjustment based on economic regime."""
        # Create features
        features = create_economic_features(economic_data)

        # Detect regimes
        regimes = detect_regime(features)

        # Align regimes with signal dates
        aligned_regimes = regimes.reindex(
            pd.date_range(
                start=trading_signals.index[0], end=trading_signals.index[-1], freq="D"
            )
        ).ffill()
        aligned_regimes = aligned_regimes.reindex(trading_signals.index).ffill()

        # Define adjustment factors
        adjustment_factors = {
            "normal": 1.0,
            "growth": 1.2,
            "inflation": 0.7,
            "recession_risk": 0.5,
            "recession": 0.3,
            "stagflation": 0.2,
            "unknown": 0.8,
        }

        # Adjust signals
        adjusted_signals = adjust_signals(
            trading_signals, aligned_regimes, adjustment_factors
        )

        # Check that signals were adjusted
        assert len(adjusted_signals) == len(trading_signals)

        # Check that the adjustment worked as expected
        # For inflation regime, signals should be reduced by 0.7
        inflation_mask = aligned_regimes == "inflation"
        if inflation_mask.any():
            orig_signals = trading_signals[inflation_mask]
            adj_signals = adjusted_signals[inflation_mask]
            # Check a sample point
            sample_idx = orig_signals.index[0]
            assert abs(adj_signals[sample_idx] - orig_signals[sample_idx] * 0.7) < 1e-6

        # For recession_risk regime, signals should be reduced by 0.5
        recession_risk_mask = aligned_regimes == "recession_risk"
        if recession_risk_mask.any():
            orig_signals = trading_signals[recession_risk_mask]
            adj_signals = adjusted_signals[recession_risk_mask]
            # Check a sample point
            sample_idx = orig_signals.index[0]
            assert abs(adj_signals[sample_idx] - orig_signals[sample_idx] * 0.5) < 1e-6

    def test_feature_engineer_custom_config(
        self, economic_data, trading_signals, custom_config
    ):
        """Test EconomicFeatureEngineer with custom configuration."""
        # Create engineer with custom config
        engineer = EconomicFeatureEngineer(custom_config)

        # Create features
        features = engineer.create_features(economic_data)

        # Detect regimes
        regimes = engineer.detect_economic_regime(features)

        # Check that the custom thresholds were used
        # With a higher unemployment threshold, we should have fewer recession periods
        assert (regimes == "recession").sum() <= (
            detect_regime(features) == "recession"
        ).sum()

        # Test signal adjustment with custom factors
        aligned_regimes = regimes.reindex(
            pd.date_range(
                start=trading_signals.index[0], end=trading_signals.index[-1], freq="D"
            )
        ).ffill()
        aligned_regimes = aligned_regimes.reindex(trading_signals.index).ffill()

        adjusted_signals = engineer.adjust_signals_for_regime(
            trading_signals, aligned_regimes
        )

        # Check that the custom adjustment factors were used
        inflation_mask = aligned_regimes == "inflation"
        if inflation_mask.any():
            orig_signals = trading_signals[inflation_mask]
            adj_signals = adjusted_signals[inflation_mask]
            # Check a sample point
            sample_idx = orig_signals.index[0]
            assert (
                abs(adj_signals[sample_idx] - orig_signals[sample_idx] * 0.6) < 1e-6
            )  # Custom factor from config
