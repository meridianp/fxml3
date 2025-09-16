#!/usr/bin/env python
"""Unit tests for enhanced ML signal generator."""

import sys
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import numpy as np
import pandas as pd
import pytest

sys.path.append(str(Path(__file__).parent.parent.parent))

from scripts.enhanced_ml_signal_generator import EnhancedMLSignalGenerator, MLSignal


@pytest.fixture
def ml_signal_generator():
    """Create enhanced ML signal generator for testing."""
    return EnhancedMLSignalGenerator(
        model=None,
        min_confidence=0.65,
        max_signals_per_week=3,
        use_market_regime_filter=True,
        use_volatility_filter=True,
        use_trend_filter=True,
        use_time_filter=True,
    )


@pytest.fixture
def sample_market_data():
    """Create sample OHLCV data with technical indicators."""
    bars = 200
    dates = pd.date_range(end=datetime.now(), periods=bars, freq="4h")

    # Generate trending data
    base_price = 1.1000
    trend = np.linspace(0, 0.05, bars)  # 5% uptrend
    noise = np.random.normal(0, 0.001, bars)

    close_prices = base_price + trend + noise

    data = pd.DataFrame(
        {
            "open": close_prices + np.random.uniform(-0.0002, 0.0002, bars),
            "high": close_prices + np.abs(np.random.uniform(0, 0.0005, bars)),
            "low": close_prices - np.abs(np.random.uniform(0, 0.0005, bars)),
            "close": close_prices,
            "volume": np.random.uniform(900000, 1100000, bars),
            "rsi_14": 50 + 20 * np.sin(np.linspace(0, 4 * np.pi, bars)),
            "adx": np.random.uniform(15, 35, bars),
            "returns_1": np.random.uniform(-0.001, 0.001, bars),
        },
        index=dates,
    )

    return data


@pytest.fixture
def current_time():
    """Get current timestamp for testing."""
    return pd.Timestamp.now()


class TestEnhancedMLSignalGenerator:
    """Test cases for Enhanced ML Signal Generator."""

    def test_initialization(self, ml_signal_generator):
        """Test generator initialization."""
        assert ml_signal_generator.min_confidence == 0.65
        assert ml_signal_generator.max_signals_per_week == 3
        assert ml_signal_generator.use_market_regime_filter is True
        assert ml_signal_generator.use_volatility_filter is True
        assert ml_signal_generator.use_trend_filter is True
        assert ml_signal_generator.use_time_filter is True
        assert len(ml_signal_generator.recent_signals) == 0

    def test_check_signal_frequency(self, ml_signal_generator, current_time):
        """Test signal frequency limiting."""
        # No recent signals - should pass
        assert ml_signal_generator._check_signal_frequency(current_time) is True

        # Add 3 recent signals
        for i in range(3):
            ml_signal_generator.recent_signals.append(
                {
                    "time": current_time - pd.Timedelta(days=i),
                    "action": "LONG",
                    "confidence": 0.7,
                }
            )

        # Should fail - already at limit
        assert ml_signal_generator._check_signal_frequency(current_time) is False

        # Clear and test with mix of old and new signals
        ml_signal_generator.recent_signals = []

        # Add 2 recent signals
        for i in range(2):
            ml_signal_generator.recent_signals.append(
                {
                    "time": current_time - pd.Timedelta(days=i),
                    "action": "LONG",
                    "confidence": 0.7,
                }
            )

        # Add old signal (>7 days) - should be removed
        old_time = current_time - pd.Timedelta(days=8)
        ml_signal_generator.recent_signals.append(
            {"time": old_time, "action": "SHORT", "confidence": 0.8}
        )

        # Should pass - old signal will be filtered out, leaving only 2
        assert ml_signal_generator._check_signal_frequency(current_time) is True
        # Old signal should be removed
        assert len(ml_signal_generator.recent_signals) == 2

    def test_determine_market_regime(self, ml_signal_generator, sample_market_data):
        """Test market regime determination."""
        # Strong uptrend
        uptrend_data = sample_market_data.copy()
        uptrend_data["adx"] = 30
        uptrend_data["close"] = np.linspace(1.10, 1.15, len(uptrend_data))

        regime = ml_signal_generator._determine_market_regime(uptrend_data)
        assert regime == "strong_uptrend"

        # Ranging market
        ranging_data = sample_market_data.copy()
        ranging_data["adx"] = 18

        regime = ml_signal_generator._determine_market_regime(ranging_data)
        assert regime == "ranging"

        # Strong downtrend
        downtrend_data = sample_market_data.copy()
        downtrend_data["adx"] = 28
        downtrend_data["close"] = np.linspace(1.15, 1.10, len(downtrend_data))

        regime = ml_signal_generator._determine_market_regime(downtrend_data)
        assert regime == "strong_downtrend"

    def test_determine_volatility_regime(self, ml_signal_generator, sample_market_data):
        """Test volatility regime determination."""
        # Normal volatility
        normal_vol = ml_signal_generator._determine_volatility_regime(
            sample_market_data
        )
        assert normal_vol in [
            "low_volatility",
            "normal_volatility",
            "elevated_volatility",
            "high_volatility",
        ]

        # Create high volatility in recent data only
        high_vol_data = sample_market_data.copy()
        # Keep historical data (100+ bars ago) calm
        high_vol_data["close"] = 1.10 + np.random.normal(0, 0.0001, len(high_vol_data))

        # Create high volatility in last 20 bars only
        for i in range(len(high_vol_data) - 20, len(high_vol_data)):
            if i % 2 == 0:
                high_vol_data.loc[high_vol_data.index[i], "close"] = (
                    high_vol_data["close"].iloc[i - 1] * 1.02
                )
            else:
                high_vol_data.loc[high_vol_data.index[i], "close"] = (
                    high_vol_data["close"].iloc[i - 1] * 0.98
                )

        vol_regime = ml_signal_generator._determine_volatility_regime(high_vol_data)
        # Should be high volatility - recent vol much higher than historical
        assert vol_regime == "high_volatility"

    def test_calculate_trend_strength(self, ml_signal_generator, sample_market_data):
        """Test trend strength calculation."""
        # With ADX
        trend_strength = ml_signal_generator._calculate_trend_strength(
            sample_market_data
        )
        assert trend_strength >= 0
        assert trend_strength <= 1

        # High ADX
        high_adx_data = sample_market_data.copy()
        high_adx_data["adx"] = 45

        trend_strength = ml_signal_generator._calculate_trend_strength(high_adx_data)
        assert trend_strength > 0.8

    def test_check_market_regime_filter(self, ml_signal_generator):
        """Test market regime filtering."""
        # Long in strong downtrend - should fail
        assert (
            ml_signal_generator._check_market_regime_filter("LONG", "strong_downtrend")
            is False
        )

        # Short in strong uptrend - should fail
        assert (
            ml_signal_generator._check_market_regime_filter("SHORT", "strong_uptrend")
            is False
        )

        # Any action in ranging market - should fail
        assert (
            ml_signal_generator._check_market_regime_filter("LONG", "ranging") is False
        )

        # Long in uptrend - should pass
        assert (
            ml_signal_generator._check_market_regime_filter("LONG", "strong_uptrend")
            is True
        )

    def test_check_volatility_filter(self, ml_signal_generator):
        """Test volatility filtering."""
        # High volatility - should fail
        assert ml_signal_generator._check_volatility_filter("high_volatility") is False

        # Normal volatility - should pass
        assert ml_signal_generator._check_volatility_filter("normal_volatility") is True

        # Low volatility - should pass
        assert ml_signal_generator._check_volatility_filter("low_volatility") is True

    def test_check_trend_filter(self, ml_signal_generator, sample_market_data):
        """Test trend alignment filtering."""
        # Long above SMA20 - should pass
        data = sample_market_data.copy()
        data["close"].iloc[-1] = data["close"].iloc[-20:].mean() + 0.001

        assert ml_signal_generator._check_trend_filter("LONG", data) is True

        # Long below SMA20 - should fail
        data["close"].iloc[-1] = data["close"].iloc[-20:].mean() - 0.001

        assert ml_signal_generator._check_trend_filter("LONG", data) is False

        # Short below SMA20 - should pass
        assert ml_signal_generator._check_trend_filter("SHORT", data) is True

    def test_check_time_filter(self, ml_signal_generator):
        """Test time-based filtering."""
        # Good trading hours
        good_time = pd.Timestamp("2024-01-15 14:00:00")
        assert ml_signal_generator._check_time_filter(good_time) is True

        # Bad trading hours (overnight)
        bad_time = pd.Timestamp("2024-01-15 03:00:00")
        assert ml_signal_generator._check_time_filter(bad_time) is False

        # Late evening
        late_time = pd.Timestamp("2024-01-15 23:00:00")
        assert ml_signal_generator._check_time_filter(late_time) is False

    @patch("scripts.enhanced_ml_signal_generator.create_technical_features")
    @patch("scripts.enhanced_ml_signal_generator.add_lagged_features")
    def test_create_enhanced_features(
        self, mock_lagged, mock_technical, ml_signal_generator, sample_market_data
    ):
        """Test enhanced feature creation."""
        # Mock the imported functions with correct shape
        mock_features = pd.DataFrame(
            {"feature1": np.random.randn(len(sample_market_data))},
            index=sample_market_data.index,
        )
        mock_technical.return_value = mock_features
        mock_lagged.return_value = mock_features

        features = ml_signal_generator._create_enhanced_features(sample_market_data)

        # Should have added features
        assert "trend_strength" in features.columns
        assert "volatility_ratio" in features.columns

        # Should have time features
        assert "hour" in features.columns
        assert "day_of_week" in features.columns
        assert "is_london_session" in features.columns
        assert "is_ny_session" in features.columns

    def test_generate_signal_no_model(
        self, ml_signal_generator, sample_market_data, current_time
    ):
        """Test signal generation without model."""
        signal = ml_signal_generator.generate_signal(sample_market_data, current_time)
        assert signal is None

    @patch("scripts.enhanced_ml_signal_generator.create_technical_features")
    @patch("scripts.enhanced_ml_signal_generator.add_lagged_features")
    def test_generate_signal_with_model(
        self, mock_lagged, mock_technical, sample_market_data, current_time
    ):
        """Test signal generation with mock model."""
        # Create a generator with relaxed filters for testing
        test_generator = EnhancedMLSignalGenerator(
            model=None,
            min_confidence=0.5,  # Lower threshold
            max_signals_per_week=10,  # Higher limit
            use_market_regime_filter=False,  # Disable for test
            use_volatility_filter=False,  # Disable for test
            use_trend_filter=False,  # Disable for test
            use_time_filter=False,  # Disable for test
        )

        # Mock feature engineering
        mock_features = pd.DataFrame(
            np.random.randn(len(sample_market_data), 10), index=sample_market_data.index
        )
        mock_features["trend_strength"] = 0.7
        mock_features["volatility_ratio"] = 1.0
        mock_technical.return_value = mock_features
        mock_lagged.return_value = mock_features

        # Mock model
        mock_model = Mock()
        mock_model.predict.return_value = np.array([0.5])  # Positive signal
        mock_model.predict_proba.return_value = np.array([[0.2, 0.8]])  # 80% confidence

        test_generator.model = mock_model

        # Generate signal
        signal = test_generator.generate_signal(sample_market_data, current_time)

        assert signal is not None
        assert signal.action == "LONG"
        assert abs(signal.confidence - 0.8) < 0.1
        assert isinstance(signal.feature_importance, dict)

    def test_ml_signal_dataclass(self):
        """Test MLSignal dataclass."""
        signal = MLSignal(
            action="LONG",
            confidence=0.75,
            predicted_return=0.002,
            market_regime="strong_uptrend",
            volatility_regime="normal_volatility",
            trend_strength=0.65,
            feature_importance={"rsi_14": 0.15, "trend_strength": 0.12},
            filters_passed=["market_regime", "volatility", "trend"],
            filters_failed=["time"],
        )

        assert signal.action == "LONG"
        assert signal.confidence == 0.75
        assert signal.predicted_return == 0.002
        assert signal.market_regime == "strong_uptrend"
        assert signal.volatility_regime == "normal_volatility"
        assert signal.trend_strength == 0.65
        assert len(signal.feature_importance) == 2
        assert len(signal.filters_passed) == 3
        assert len(signal.filters_failed) == 1

    def test_calculate_predicted_return(self, ml_signal_generator):
        """Test predicted return calculation."""
        features = pd.DataFrame({"volatility_ratio": [1.2]})

        # Base calculation
        predicted_return = ml_signal_generator._calculate_predicted_return(
            features, 2.0
        )

        # Should be positive and adjusted for volatility
        assert predicted_return > 0
        assert predicted_return < 0.01  # Reasonable range

    def test_get_feature_importance(self, ml_signal_generator):
        """Test feature importance retrieval."""
        features = pd.DataFrame({"feature1": [1], "feature2": [2]})

        importance = ml_signal_generator._get_feature_importance(features)

        assert isinstance(importance, dict)
        assert len(importance) > 0
        assert "rsi_14" in importance
        assert "trend_strength" in importance
