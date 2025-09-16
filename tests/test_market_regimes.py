#!/usr/bin/env python3
"""Test module for market regime classification."""

import os
import sys
from datetime import datetime, timedelta

import numpy as np
import pandas as pd
import pytest

# Add parent directory to path to allow importing fxml4
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fxml4.ml.features import FeatureEngineer
from fxml4.ml.market_regimes import (
    MarketRegimeClassifier,
    classify_market_regimes,
    get_regime_descriptions,
)


@pytest.fixture
def market_regime_data():
    """Create test fixtures for market regime testing."""
    # Create sample market data
    date_range = pd.date_range(start="2020-01-01", end="2022-12-31", freq="D")
    n_samples = len(date_range)

    # Create OHLCV data with some trends and cycles
    np.random.seed(42)  # For reproducibility

    # Generate a price series with trends and cycles
    t = np.linspace(0, 4 * np.pi, n_samples)  # 2 full cycles over the period

    # Trend component: linear trend with periodic reversals
    trend = np.linspace(100, 140, n_samples)

    # Add a market cycle (sine wave)
    cycle = 15 * np.sin(t) + 5 * np.sin(2.5 * t)

    # Add noise
    noise = np.random.normal(0, 3, n_samples)

    # Combine components
    close_prices = trend + cycle + noise

    # Create daily ranges based on local volatility
    local_vol = 2 + np.abs(cycle) / 5

    # Create OHLCV data
    high_prices = close_prices + local_vol * np.random.random(n_samples)
    low_prices = close_prices - local_vol * np.random.random(n_samples)
    open_prices = low_prices + (high_prices - low_prices) * np.random.random(n_samples)

    # Volume is higher in high volatility periods and trend changes
    cycle_change = np.diff(np.sign(np.diff(cycle)), prepend=[0, 0])
    volume = 1000 + 500 * np.abs(cycle) / 15 + 300 * np.abs(cycle_change)

    # Create DataFrame
    market_data = pd.DataFrame(
        {
            "open": open_prices,
            "high": high_prices,
            "low": low_prices,
            "close": close_prices,
            "volume": volume,
        },
        index=date_range,
    )

    # Add time column
    market_data["time"] = date_range

    # Create sample economic data
    # GDP data (quarterly frequency)
    gdp_dates = pd.date_range(start="2020-01-01", end="2022-12-31", freq="Q")
    gdp_values = [
        21.56,
        19.52,
        21.14,
        21.49,  # 2020 (with COVID drop)
        22.74,
        23.20,
        23.20,
        24.00,  # 2021 (recovery)
        24.39,
        24.86,
        25.72,
        26.13,  # 2022 (growth)
    ]
    gdp_data = pd.Series(index=gdp_dates, data=gdp_values)

    # Unemployment rate (monthly frequency)
    unemp_dates = pd.date_range(start="2020-01-01", end="2022-12-31", freq="M")

    # High unemployment in 2020 due to COVID, gradually decreasing
    unemp_values = [
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
    unemp_data = pd.Series(index=unemp_dates, data=unemp_values)

    # Inflation (CPI, monthly frequency)
    inflation_dates = unemp_dates
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
        1.4,  # 2020 (low)
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
        7.0,  # 2021 (rising)
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
        6.5,  # 2022 (high)
    ]
    # Convert to decimal form
    inflation_values = [v / 100 for v in inflation_values]
    inflation_data = pd.Series(index=inflation_dates, data=inflation_values)

    # VIX (daily, with gaps for weekends/holidays)
    vix_dates = pd.date_range(
        start="2020-01-01", end="2022-12-31", freq="B"
    )  # Business days

    # Simulate VIX - high in early 2020 (COVID), spikes at various points
    t_vix = np.linspace(0, n_samples / 252 * 2 * np.pi, len(vix_dates))
    vix_base = 20 + 10 * np.sin(t_vix / 2)

    # Add COVID spike in March 2020
    covid_spike = np.zeros_like(vix_base)
    covid_idx = (vix_dates >= "2020-03-01") & (vix_dates <= "2020-04-15")
    covid_spike[covid_idx] = 40 * np.exp(-((np.arange(sum(covid_idx)) - 10) ** 2) / 50)

    # Add smaller spikes at various points
    spike1_idx = (vix_dates >= "2020-06-01") & (vix_dates <= "2020-06-15")
    covid_spike[spike1_idx] = 15 * np.exp(-((np.arange(sum(spike1_idx)) - 5) ** 2) / 10)

    spike2_idx = (vix_dates >= "2021-01-15") & (vix_dates <= "2021-02-05")
    covid_spike[spike2_idx] = 20 * np.exp(
        -((np.arange(sum(spike2_idx)) - 10) ** 2) / 20
    )

    spike3_idx = (vix_dates >= "2022-02-20") & (vix_dates <= "2022-03-15")
    covid_spike[spike3_idx] = 25 * np.exp(
        -((np.arange(sum(spike3_idx)) - 10) ** 2) / 30
    )

    vix_values = vix_base + covid_spike + np.random.normal(0, 2, len(vix_dates))
    vix_values = np.maximum(vix_values, 10)  # VIX floor

    vix_data = pd.Series(index=vix_dates, data=vix_values)

    # Combine into economic data DataFrame
    economic_data = pd.DataFrame(
        {
            "GDP": gdp_data,
            "UNRATE": unemp_data,
            "CPIAUCSL": inflation_data,
            "VIXCLS": vix_data,
        }
    )

    # Generate features from market data
    feature_engineer = FeatureEngineer()
    feature_data = feature_engineer.create_features(market_data)

    return {
        "market_data": market_data,
        "economic_data": economic_data,
        "feature_data": feature_data,
    }


class TestMarketRegimes:
    """Test case for market regime classification."""

    @pytest.mark.parametrize(
        "config,expected_regimes,expected_economic,expected_pca",
        [
            (None, 5, True, None),  # Default config
            (
                {
                    "market_regimes": {
                        "n_regimes": 3,
                        "use_economic_data": False,
                        "use_pca": False,
                    }
                },
                3,
                False,
                False,
            ),
        ],
    )
    def test_market_regime_classifier_init(
        self, config, expected_regimes, expected_economic, expected_pca
    ):
        """Test MarketRegimeClassifier initialization."""
        classifier = MarketRegimeClassifier(config)
        assert classifier.n_regimes == expected_regimes
        assert classifier.use_economic_data == expected_economic
        if expected_pca is not None:
            assert classifier.use_pca == expected_pca

    def test_market_regime_fit_predict(self, market_regime_data):
        """Test regime classification fitting and prediction."""
        # Create classifier
        classifier = MarketRegimeClassifier({"market_regimes": {"n_regimes": 4}})

        # Fit classifier
        classifier.fit(
            market_regime_data["feature_data"], market_regime_data["economic_data"]
        )

        # Check that models are fitted
        assert classifier.scaler is not None
        assert classifier.kmeans_model is not None

        # Check regime labels
        assert classifier.regime_labels is not None
        assert len(classifier.regime_labels) == len(market_regime_data["feature_data"])

        # Check that we have multiple regimes
        unique_regimes = classifier.regime_labels.unique()
        assert len(unique_regimes) > 1

        # Predict regimes
        predicted = classifier.predict(
            market_regime_data["feature_data"], market_regime_data["economic_data"]
        )

        # Check predictions
        assert len(predicted) == len(market_regime_data["feature_data"])
        assert predicted.equals(classifier.regime_labels)

    def test_detect_regime_shifts(self, market_regime_data):
        """Test regime shift detection."""
        # Create classifier
        classifier = MarketRegimeClassifier({"market_regimes": {"n_regimes": 3}})

        # Fit classifier
        classifier.fit(
            market_regime_data["feature_data"], market_regime_data["economic_data"]
        )

        # Detect regime shifts with default window
        shifts = classifier.detect_regime_shifts(classifier.regime_labels)

        # Check that shifts are detected
        assert len(shifts) == len(classifier.regime_labels)
        assert shifts.any()  # At least one shift detected

        # Test with custom window
        small_window = 30
        shifts_small = classifier.detect_regime_shifts(
            classifier.regime_labels, window=small_window
        )

        # Smaller window should detect more shifts
        assert shifts_small.sum() >= shifts.sum()

    def test_get_regime_characteristics(self, market_regime_data):
        """Test getting regime characteristics."""
        # Create classifier
        classifier = MarketRegimeClassifier({"market_regimes": {"n_regimes": 3}})

        # Fit classifier
        classifier.fit(
            market_regime_data["feature_data"], market_regime_data["economic_data"]
        )

        # Get regime characteristics
        characteristics = classifier.get_regime_characteristics()

        # Check that we have expected columns
        assert len(characteristics) == 3  # 3 regimes

        # Check that we have frequency column
        assert "frequency" in characteristics.columns

        # Check that frequencies sum to approximately 1
        assert abs(characteristics["frequency"].sum() - 1.0) < 0.0001

    def test_describe_regimes(self, market_regime_data):
        """Test getting regime descriptions."""
        # Create classifier
        classifier = MarketRegimeClassifier({"market_regimes": {"n_regimes": 3}})

        # Fit classifier
        classifier.fit(
            market_regime_data["feature_data"], market_regime_data["economic_data"]
        )

        # Get regime descriptions
        descriptions = classifier.describe_regimes()

        # Check that we have expected keys
        assert len(descriptions) == 3  # 3 regimes

        # Check that each description has required keys
        for regime_id, desc in descriptions.items():
            assert "volatility" in desc
            assert "trend" in desc
            assert "momentum" in desc
            assert "summary" in desc

            # Check that summary is not empty
            assert len(desc["summary"]) > 0

    def test_helper_functions(self, market_regime_data):
        """Test helper functions for market regime classification."""
        # Test classify_market_regimes function
        regimes = classify_market_regimes(
            market_regime_data["feature_data"],
            market_regime_data["economic_data"],
            n_regimes=3,
        )

        # Check that we have expected number of regimes
        assert len(regimes) == len(market_regime_data["feature_data"])
        assert len(regimes.unique()) <= 3

        # Test get_regime_descriptions function
        descriptions = get_regime_descriptions(
            market_regime_data["feature_data"],
            regimes,
            market_regime_data["economic_data"],
        )

        # Check that we have descriptions for each unique regime
        assert len(descriptions) == len(regimes.unique())

        # Check that descriptions have expected keys
        for regime_id, desc in descriptions.items():
            assert "volatility" in desc
            assert "trend" in desc
            assert "summary" in desc


# Pytest markers for test categorization
pytestmark = [pytest.mark.unit, pytest.mark.ml, pytest.mark.slow]
