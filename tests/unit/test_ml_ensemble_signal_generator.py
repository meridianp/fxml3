"""
Comprehensive retrospective test coverage for ML Ensemble Signal Generator.

This module provides comprehensive test coverage for the FXML4 ML Ensemble Signal Generator,
which combines multiple ML models and technical indicators to generate robust trading signals
for forex trading systems.

Following TDD principles with retrospective testing approach:
- Testing existing production ensemble signal generation functionality
- Ensuring comprehensive coverage of model combination strategies
- Validating signal confidence scoring and risk-adjusted outputs
"""

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple
from unittest.mock import ANY, AsyncMock, MagicMock, call, patch

import numpy as np
import pandas as pd
import pytest

from fxml4.ml.ensemble_signal_generator import (
    ConfidenceCalculator,
    EnsembleMethod,
    EnsembleSignalGenerator,
    MarketRegimeDetector,
    ModelWeight,
    RiskAdjustedSignal,
    SignalAggregator,
    SignalConfig,
    SignalOutput,
    SignalValidator,
)
from fxml4.ml.model_registry import ModelRegistry
from fxml4.ml.models import ClassicMLModel, EnsembleModel


class TestEnsembleSignalGenerator:
    """Test core ensemble signal generation functionality."""

    @pytest.fixture
    def signal_config(self):
        """Create signal configuration for testing."""
        return SignalConfig(
            ensemble_method="weighted_voting",
            confidence_threshold=0.6,
            min_models_agreement=2,
            max_signal_age_minutes=5,
            risk_adjustment=True,
            market_regime_aware=True,
            signal_classes=["HOLD", "BUY", "SELL"],
            feature_columns=["rsi", "macd", "bollinger_ratio", "volume", "returns"],
        )

    @pytest.fixture
    def sample_market_data(self):
        """Create sample market data for testing."""
        dates = pd.date_range("2024-01-01", periods=1000, freq="1H")
        return pd.DataFrame(
            {
                "timestamp": dates,
                "open": 1.1000 + np.random.randn(1000) * 0.001,
                "high": 1.1005 + np.random.randn(1000) * 0.001,
                "low": 1.0995 + np.random.randn(1000) * 0.001,
                "close": 1.1000 + np.random.randn(1000) * 0.001,
                "volume": np.random.exponential(1000, 1000),
                "rsi": np.random.uniform(20, 80, 1000),
                "macd": np.random.randn(1000) * 0.0001,
                "macd_signal": np.random.randn(1000) * 0.0001,
                "bollinger_upper": 1.1020 + np.random.randn(1000) * 0.0005,
                "bollinger_lower": 1.0980 + np.random.randn(1000) * 0.0005,
                "bollinger_ratio": np.random.uniform(-2, 2, 1000),
                "atr": np.random.uniform(0.0005, 0.002, 1000),
                "returns": np.random.randn(1000) * 0.001,
                "volatility": np.random.uniform(0.0001, 0.001, 1000),
            }
        )

    @pytest.fixture
    def mock_models(self):
        """Create mock ML models for testing."""
        models = {}

        # Random Forest Model
        rf_model = MagicMock()
        rf_model.predict.return_value = np.random.choice(
            [0, 1, 2], 100, p=[0.6, 0.2, 0.2]
        )
        rf_model.predict_proba.return_value = np.random.dirichlet([2, 1, 1], 100)
        models["random_forest"] = rf_model

        # Gradient Boosting Model
        gb_model = MagicMock()
        gb_model.predict.return_value = np.random.choice(
            [0, 1, 2], 100, p=[0.5, 0.3, 0.2]
        )
        gb_model.predict_proba.return_value = np.random.dirichlet([1, 2, 1], 100)
        models["gradient_boosting"] = gb_model

        # SVM Model
        svm_model = MagicMock()
        svm_model.predict.return_value = np.random.choice(
            [0, 1, 2], 100, p=[0.7, 0.15, 0.15]
        )
        svm_model.predict_proba.return_value = np.random.dirichlet([3, 1, 1], 100)
        models["svm"] = svm_model

        return models

    def test_ensemble_generator_initialization(self, signal_config):
        """Test ensemble signal generator initialization."""
        generator = EnsembleSignalGenerator(signal_config)

        assert generator.config == signal_config
        assert generator.models == {}
        assert generator.model_weights == {}
        assert generator.confidence_calculator is not None
        assert generator.signal_aggregator is not None

    def test_add_model_to_ensemble(self, signal_config, mock_models):
        """Test adding models to ensemble."""
        generator = EnsembleSignalGenerator(signal_config)

        # Add models with different weights
        generator.add_model("rf_model", mock_models["random_forest"], weight=0.4)
        generator.add_model("gb_model", mock_models["gradient_boosting"], weight=0.35)
        generator.add_model("svm_model", mock_models["svm"], weight=0.25)

        assert len(generator.models) == 3
        assert generator.model_weights["rf_model"] == 0.4
        assert generator.model_weights["gb_model"] == 0.35
        assert generator.model_weights["svm_model"] == 0.25

        # Test weight normalization
        total_weight = sum(generator.model_weights.values())
        assert abs(total_weight - 1.0) < 0.01

    def test_generate_ensemble_signals(
        self, signal_config, mock_models, sample_market_data
    ):
        """Test ensemble signal generation."""
        generator = EnsembleSignalGenerator(signal_config)

        # Add models
        generator.add_model("rf_model", mock_models["random_forest"], weight=0.5)
        generator.add_model("gb_model", mock_models["gradient_boosting"], weight=0.3)
        generator.add_model("svm_model", mock_models["svm"], weight=0.2)

        # Generate signals for last 100 rows
        recent_data = sample_market_data.tail(100)
        signals = generator.generate_signals(recent_data)

        assert len(signals) == len(recent_data)
        assert all(hasattr(signal, "prediction") for signal in signals)
        assert all(hasattr(signal, "confidence") for signal in signals)
        assert all(hasattr(signal, "timestamp") for signal in signals)

        # Verify signal classes
        predictions = [signal.prediction for signal in signals]
        assert all(pred in [0, 1, 2] for pred in predictions)

    def test_weighted_voting_method(
        self, signal_config, mock_models, sample_market_data
    ):
        """Test weighted voting ensemble method."""
        signal_config.ensemble_method = "weighted_voting"
        generator = EnsembleSignalGenerator(signal_config)

        # Add models with different weights
        generator.add_model("model_1", mock_models["random_forest"], weight=0.6)
        generator.add_model("model_2", mock_models["gradient_boosting"], weight=0.4)

        recent_data = sample_market_data.tail(10)
        signals = generator.generate_signals(recent_data)

        # Should use weighted voting
        assert len(signals) == 10
        assert all(0 <= signal.confidence <= 1 for signal in signals)

        # Verify models were called
        mock_models["random_forest"].predict_proba.assert_called()
        mock_models["gradient_boosting"].predict_proba.assert_called()

    def test_majority_voting_method(
        self, signal_config, mock_models, sample_market_data
    ):
        """Test majority voting ensemble method."""
        signal_config.ensemble_method = "majority_voting"
        generator = EnsembleSignalGenerator(signal_config)

        # Add models
        for name, model in mock_models.items():
            generator.add_model(name, model, weight=1.0 / len(mock_models))

        recent_data = sample_market_data.tail(10)
        signals = generator.generate_signals(recent_data)

        assert len(signals) == 10
        # Majority voting should produce discrete confidence levels
        confidences = [signal.confidence for signal in signals]
        assert all(conf >= 0.33 for conf in confidences)  # At least 1/3 agreement

    def test_stacking_ensemble_method(
        self, signal_config, mock_models, sample_market_data
    ):
        """Test stacking ensemble method."""
        signal_config.ensemble_method = "stacking"
        generator = EnsembleSignalGenerator(signal_config)

        # Add base models
        for name, model in mock_models.items():
            generator.add_model(name, model, weight=1.0 / len(mock_models))

        # Mock meta-learner
        meta_learner = MagicMock()
        meta_learner.predict.return_value = np.random.choice([0, 1, 2], 10)
        meta_learner.predict_proba.return_value = np.random.dirichlet([1, 1, 1], 10)

        generator.set_meta_learner(meta_learner)

        recent_data = sample_market_data.tail(10)
        signals = generator.generate_signals(recent_data)

        assert len(signals) == 10
        meta_learner.predict_proba.assert_called()

    def test_confidence_calculation(
        self, signal_config, mock_models, sample_market_data
    ):
        """Test signal confidence calculation."""
        generator = EnsembleSignalGenerator(signal_config)

        # Add models with known prediction patterns
        model_1 = MagicMock()
        model_1.predict_proba.return_value = np.array(
            [[0.1, 0.8, 0.1]]
        )  # High confidence BUY

        model_2 = MagicMock()
        model_2.predict_proba.return_value = np.array(
            [[0.2, 0.6, 0.2]]
        )  # Medium confidence BUY

        generator.add_model("high_conf", model_1, weight=0.6)
        generator.add_model("med_conf", model_2, weight=0.4)

        single_row = sample_market_data.tail(1)
        signals = generator.generate_signals(single_row)

        assert len(signals) == 1
        signal = signals[0]

        # Should be BUY signal with high confidence
        assert signal.prediction == 1  # BUY
        assert signal.confidence > 0.7  # High confidence from weighted combination

    def test_signal_filtering_by_confidence(
        self, signal_config, mock_models, sample_market_data
    ):
        """Test filtering signals by confidence threshold."""
        signal_config.confidence_threshold = 0.8  # High threshold
        generator = EnsembleSignalGenerator(signal_config)

        # Add models with varying confidence levels
        low_conf_model = MagicMock()
        low_conf_model.predict_proba.return_value = np.array(
            [[0.4, 0.3, 0.3]] * 10
        )  # Low confidence

        high_conf_model = MagicMock()
        high_conf_model.predict_proba.return_value = np.array(
            [[0.1, 0.85, 0.05]] * 10
        )  # High confidence

        generator.add_model("low_conf", low_conf_model, weight=0.5)
        generator.add_model("high_conf", high_conf_model, weight=0.5)

        recent_data = sample_market_data.tail(10)
        signals = generator.generate_signals(recent_data)

        # Should filter out low confidence signals
        high_conf_signals = [s for s in signals if s.confidence >= 0.8]
        assert len(high_conf_signals) > 0
        assert len(high_conf_signals) <= len(signals)

    def test_minimum_model_agreement(
        self, signal_config, mock_models, sample_market_data
    ):
        """Test minimum model agreement requirement."""
        signal_config.min_models_agreement = 2
        generator = EnsembleSignalGenerator(signal_config)

        # Add models with conflicting predictions
        model_1 = MagicMock()
        model_1.predict.return_value = np.array([1] * 10)  # Always BUY
        model_1.predict_proba.return_value = np.array([[0.1, 0.8, 0.1]] * 10)

        model_2 = MagicMock()
        model_2.predict.return_value = np.array([2] * 10)  # Always SELL
        model_2.predict_proba.return_value = np.array([[0.1, 0.1, 0.8]] * 10)

        model_3 = MagicMock()
        model_3.predict.return_value = np.array([1] * 10)  # Always BUY
        model_3.predict_proba.return_value = np.array([[0.1, 0.7, 0.2]] * 10)

        generator.add_model("buy_1", model_1, weight=0.33)
        generator.add_model("sell", model_2, weight=0.33)
        generator.add_model("buy_2", model_3, weight=0.34)

        recent_data = sample_market_data.tail(10)
        signals = generator.generate_signals(recent_data)

        # Should generate BUY signals (2 out of 3 models agree)
        buy_signals = [s for s in signals if s.prediction == 1]
        assert len(buy_signals) > 0

    def test_market_regime_aware_signals(self, signal_config, sample_market_data):
        """Test market regime aware signal generation."""
        signal_config.market_regime_aware = True
        generator = EnsembleSignalGenerator(signal_config)

        # Mock regime detector
        regime_detector = MagicMock()
        regime_detector.detect_regime.return_value = "trending"
        generator.regime_detector = regime_detector

        # Mock models with regime-specific behavior
        trending_model = MagicMock()
        trending_model.predict_proba.return_value = np.array([[0.1, 0.8, 0.1]] * 10)

        generator.add_model("trending_model", trending_model, weight=1.0)

        recent_data = sample_market_data.tail(10)
        signals = generator.generate_signals(recent_data)

        assert len(signals) == 10
        regime_detector.detect_regime.assert_called()

        # Verify regime information is included
        assert all(hasattr(signal, "market_regime") for signal in signals)

    def test_risk_adjusted_signals(self, signal_config, sample_market_data):
        """Test risk-adjusted signal generation."""
        signal_config.risk_adjustment = True
        generator = EnsembleSignalGenerator(signal_config)

        # Add model
        model = MagicMock()
        model.predict_proba.return_value = np.array([[0.1, 0.8, 0.1]] * 10)
        generator.add_model("test_model", model, weight=1.0)

        # Add high volatility to test risk adjustment
        high_vol_data = sample_market_data.tail(10).copy()
        high_vol_data["volatility"] = (
            high_vol_data["volatility"] * 5
        )  # 5x higher volatility
        high_vol_data["atr"] = high_vol_data["atr"] * 3  # 3x higher ATR

        signals = generator.generate_signals(high_vol_data)

        assert len(signals) == 10

        # Risk adjustment should modify confidence based on volatility
        assert all(hasattr(signal, "risk_adjusted_confidence") for signal in signals)
        assert all(hasattr(signal, "volatility_factor") for signal in signals)

    def test_signal_age_validation(
        self, signal_config, mock_models, sample_market_data
    ):
        """Test signal age validation and expiration."""
        signal_config.max_signal_age_minutes = 5
        generator = EnsembleSignalGenerator(signal_config)

        generator.add_model("test_model", mock_models["random_forest"], weight=1.0)

        # Generate signals
        recent_data = sample_market_data.tail(10)
        signals = generator.generate_signals(recent_data)

        # Check if signals are fresh
        current_time = datetime.now()
        fresh_signals = []

        for signal in signals:
            if hasattr(signal, "generated_at"):
                age_minutes = (current_time - signal.generated_at).total_seconds() / 60
                if age_minutes <= signal_config.max_signal_age_minutes:
                    fresh_signals.append(signal)

        assert len(fresh_signals) > 0

    def test_signal_validation_rules(
        self, signal_config, mock_models, sample_market_data
    ):
        """Test signal validation rules and filters."""
        generator = EnsembleSignalGenerator(signal_config)
        generator.add_model("test_model", mock_models["random_forest"], weight=1.0)

        # Add validation rules
        validation_rules = {
            "min_volume": 100,
            "max_spread_bps": 5,
            "exclude_news_periods": True,
            "market_hours_only": True,
        }

        generator.set_validation_rules(validation_rules)

        # Test data with some rows that should be filtered
        test_data = sample_market_data.tail(10).copy()
        test_data.loc[test_data.index[0], "volume"] = 50  # Below minimum volume

        signals = generator.generate_signals(test_data)

        # Should filter out signals that don't meet validation criteria
        valid_signals = [s for s in signals if s.is_valid]
        assert len(valid_signals) < len(signals)


class TestSignalAggregation:
    """Test signal aggregation and combination methods."""

    @pytest.fixture
    def aggregator(self):
        """Create signal aggregator for testing."""
        return SignalAggregator()

    def test_weighted_probability_aggregation(self, aggregator):
        """Test weighted probability aggregation."""
        # Mock model predictions with probabilities
        model_predictions = {
            "model_1": np.array([[0.1, 0.8, 0.1], [0.3, 0.4, 0.3]]),
            "model_2": np.array([[0.2, 0.6, 0.2], [0.4, 0.3, 0.3]]),
            "model_3": np.array([[0.1, 0.7, 0.2], [0.2, 0.5, 0.3]]),
        }

        weights = {"model_1": 0.5, "model_2": 0.3, "model_3": 0.2}

        aggregated = aggregator.weighted_probability_aggregation(
            model_predictions, weights
        )

        assert aggregated.shape == (2, 3)  # 2 samples, 3 classes
        assert np.allclose(aggregated.sum(axis=1), 1.0)  # Probabilities sum to 1

        # First sample should favor class 1 (BUY) due to high model_1 weight
        assert aggregated[0, 1] > aggregated[0, 0]
        assert aggregated[0, 1] > aggregated[0, 2]

    def test_majority_vote_aggregation(self, aggregator):
        """Test majority vote aggregation."""
        model_predictions = {
            "model_1": np.array([1, 2, 0]),  # BUY, SELL, HOLD
            "model_2": np.array([1, 1, 0]),  # BUY, BUY, HOLD
            "model_3": np.array([0, 1, 2]),  # HOLD, BUY, SELL
        }

        majority_votes = aggregator.majority_vote_aggregation(model_predictions)

        assert len(majority_votes) == 3
        assert majority_votes[0] == 1  # BUY (2 out of 3)
        assert majority_votes[1] == 1  # BUY (2 out of 3)
        assert majority_votes[2] == 0  # HOLD (no majority, default to HOLD)

    def test_confidence_weighted_aggregation(self, aggregator):
        """Test confidence-weighted aggregation."""
        model_predictions = {
            "model_1": np.array([[0.1, 0.8, 0.1]]),  # High confidence BUY
            "model_2": np.array([[0.4, 0.3, 0.3]]),  # Low confidence prediction
        }

        model_confidences = {"model_1": np.array([0.8]), "model_2": np.array([0.3])}

        weights = {"model_1": 0.5, "model_2": 0.5}

        aggregated = aggregator.confidence_weighted_aggregation(
            model_predictions, model_confidences, weights
        )

        # Should favor high-confidence model's prediction
        assert aggregated[0, 1] > aggregated[0, 0]  # BUY > HOLD
        assert aggregated[0, 1] > aggregated[0, 2]  # BUY > SELL

    def test_temporal_aggregation(self, aggregator):
        """Test temporal signal aggregation."""
        # Historical signals over time
        historical_signals = [
            np.array([1, 1, 0]),  # t-2: BUY, BUY, HOLD
            np.array([1, 2, 0]),  # t-1: BUY, SELL, HOLD
            np.array([2, 1, 1]),  # t: SELL, BUY, BUY
        ]

        # Exponential decay weights (recent signals more important)
        temporal_weights = [0.25, 0.35, 0.4]

        aggregated = aggregator.temporal_aggregation(
            historical_signals, temporal_weights
        )

        assert len(aggregated) == 3
        # Recent signals should have more influence


class TestConfidenceCalculation:
    """Test signal confidence calculation methods."""

    @pytest.fixture
    def confidence_calculator(self):
        """Create confidence calculator for testing."""
        return ConfidenceCalculator()

    def test_entropy_based_confidence(self, confidence_calculator):
        """Test entropy-based confidence calculation."""
        # High confidence prediction (low entropy)
        high_conf_proba = np.array([[0.1, 0.85, 0.05]])
        high_conf = confidence_calculator.entropy_based_confidence(high_conf_proba)

        # Low confidence prediction (high entropy)
        low_conf_proba = np.array([[0.33, 0.34, 0.33]])
        low_conf = confidence_calculator.entropy_based_confidence(low_conf_proba)

        assert high_conf[0] > low_conf[0]
        assert 0 <= high_conf[0] <= 1
        assert 0 <= low_conf[0] <= 1

    def test_max_probability_confidence(self, confidence_calculator):
        """Test maximum probability confidence calculation."""
        probabilities = np.array(
            [
                [0.1, 0.85, 0.05],  # High max prob
                [0.4, 0.35, 0.25],  # Medium max prob
                [0.33, 0.34, 0.33],  # Low max prob
            ]
        )

        confidences = confidence_calculator.max_probability_confidence(probabilities)

        assert len(confidences) == 3
        assert confidences[0] > confidences[1] > confidences[2]
        assert all(0 <= conf <= 1 for conf in confidences)

    def test_consensus_based_confidence(self, confidence_calculator):
        """Test consensus-based confidence calculation."""
        model_predictions = [
            np.array([1, 1, 2]),  # Models agree on first two, disagree on third
            np.array([1, 2, 2]),
            np.array([1, 0, 1]),
        ]

        consensus_conf = confidence_calculator.consensus_based_confidence(
            model_predictions
        )

        assert len(consensus_conf) == 3
        assert consensus_conf[0] == 1.0  # Perfect consensus
        assert consensus_conf[1] < consensus_conf[0]  # Partial consensus
        assert consensus_conf[2] < consensus_conf[0]  # No consensus

    def test_historical_performance_confidence(self, confidence_calculator):
        """Test historical performance-based confidence."""
        # Mock historical performance data
        model_performance = {
            "model_1": {"accuracy": 0.85, "sharpe_ratio": 1.5},
            "model_2": {"accuracy": 0.78, "sharpe_ratio": 1.2},
            "model_3": {"accuracy": 0.90, "sharpe_ratio": 1.8},
        }

        model_predictions = {
            "model_1": np.array([[0.2, 0.7, 0.1]]),
            "model_2": np.array([[0.3, 0.4, 0.3]]),
            "model_3": np.array([[0.1, 0.8, 0.1]]),
        }

        weights = {"model_1": 0.33, "model_2": 0.33, "model_3": 0.34}

        perf_conf = confidence_calculator.historical_performance_confidence(
            model_predictions, model_performance, weights
        )

        assert len(perf_conf) == 1
        assert 0 <= perf_conf[0] <= 1
        # Should weight model_3 higher due to better performance


class TestMarketRegimeDetection:
    """Test market regime detection functionality."""

    @pytest.fixture
    def regime_detector(self):
        """Create market regime detector for testing."""
        return MarketRegimeDetector()

    @pytest.fixture
    def trending_market_data(self):
        """Create trending market data for testing."""
        dates = pd.date_range("2024-01-01", periods=100, freq="1H")
        trend = np.linspace(1.1000, 1.1500, 100)  # Strong uptrend
        noise = np.random.randn(100) * 0.0005

        return pd.DataFrame(
            {
                "timestamp": dates,
                "close": trend + noise,
                "high": trend + noise + 0.0002,
                "low": trend + noise - 0.0002,
                "volume": np.random.exponential(1000, 100),
                "volatility": np.random.uniform(0.0001, 0.0005, 100),
            }
        )

    @pytest.fixture
    def sideways_market_data(self):
        """Create sideways market data for testing."""
        dates = pd.date_range("2024-01-01", periods=100, freq="1H")
        base_price = 1.1000
        noise = np.random.randn(100) * 0.0010

        return pd.DataFrame(
            {
                "timestamp": dates,
                "close": base_price + noise,
                "high": base_price + noise + 0.0005,
                "low": base_price + noise - 0.0005,
                "volume": np.random.exponential(800, 100),
                "volatility": np.random.uniform(0.0008, 0.0015, 100),
            }
        )

    def test_trending_regime_detection(self, regime_detector, trending_market_data):
        """Test detection of trending market regime."""
        regime = regime_detector.detect_regime(trending_market_data)

        assert regime in ["trending_up", "trending_down", "strong_trend"]

        # Should detect trend characteristics
        trend_strength = regime_detector.calculate_trend_strength(trending_market_data)
        assert trend_strength > 0.5  # Strong trend

    def test_sideways_regime_detection(self, regime_detector, sideways_market_data):
        """Test detection of sideways market regime."""
        regime = regime_detector.detect_regime(sideways_market_data)

        assert regime in ["sideways", "consolidation", "range_bound"]

        # Should detect range-bound characteristics
        trend_strength = regime_detector.calculate_trend_strength(sideways_market_data)
        assert trend_strength < 0.3  # Weak trend (sideways)

    def test_volatility_regime_classification(
        self, regime_detector, trending_market_data
    ):
        """Test volatility-based regime classification."""
        # Modify data to have high volatility
        high_vol_data = trending_market_data.copy()
        high_vol_data["volatility"] = high_vol_data["volatility"] * 5

        vol_regime = regime_detector.classify_volatility_regime(high_vol_data)

        assert vol_regime in ["high_volatility", "extreme_volatility"]

        # Compare with low volatility
        low_vol_regime = regime_detector.classify_volatility_regime(
            trending_market_data
        )
        assert low_vol_regime in ["low_volatility", "normal_volatility"]

    def test_regime_transition_detection(self, regime_detector):
        """Test detection of regime transitions."""
        # Create data with regime change
        dates = pd.date_range("2024-01-01", periods=200, freq="1H")

        # First 100 points: trending up
        trend_part = np.linspace(1.1000, 1.1200, 100)

        # Last 100 points: sideways
        sideways_part = 1.1200 + np.random.randn(100) * 0.0005

        combined_prices = np.concatenate([trend_part, sideways_part])

        data = pd.DataFrame(
            {
                "timestamp": dates,
                "close": combined_prices,
                "volume": np.random.exponential(1000, 200),
                "volatility": np.random.uniform(0.0001, 0.001, 200),
            }
        )

        # Detect regime for each half
        first_half_regime = regime_detector.detect_regime(data.iloc[:100])
        second_half_regime = regime_detector.detect_regime(data.iloc[100:])

        assert first_half_regime != second_half_regime

        # Test transition detection
        transition_point = regime_detector.detect_regime_transition(data)
        assert transition_point is not None
        assert 80 <= transition_point <= 120  # Should detect around point 100


class TestEnsembleSignalIntegration:
    """Test complete ensemble signal generation integration."""

    @pytest.fixture
    def complete_ensemble(self, signal_config, mock_models):
        """Create complete ensemble system for integration testing."""
        generator = EnsembleSignalGenerator(signal_config)

        # Add models with realistic weights
        generator.add_model("rf_primary", mock_models["random_forest"], weight=0.4)
        generator.add_model(
            "gb_secondary", mock_models["gradient_boosting"], weight=0.35
        )
        generator.add_model("svm_tertiary", mock_models["svm"], weight=0.25)

        # Configure regime detection
        regime_detector = MarketRegimeDetector()
        generator.regime_detector = regime_detector

        return generator

    def test_complete_signal_generation_workflow(
        self, complete_ensemble, sample_market_data
    ):
        """Test complete signal generation workflow."""
        # Generate signals for realistic market data
        recent_data = sample_market_data.tail(50)
        signals = complete_ensemble.generate_signals(recent_data)

        assert len(signals) == 50

        # Verify signal structure
        for signal in signals:
            assert hasattr(signal, "prediction")
            assert hasattr(signal, "confidence")
            assert hasattr(signal, "timestamp")
            assert hasattr(signal, "model_contributions")
            assert hasattr(signal, "market_regime")

            # Verify value ranges
            assert signal.prediction in [0, 1, 2]
            assert 0 <= signal.confidence <= 1
            assert isinstance(signal.timestamp, (datetime, pd.Timestamp))

    def test_signal_performance_under_different_regimes(self, complete_ensemble):
        """Test signal performance across different market regimes."""
        # Create different market regime data
        regimes_data = {
            "trending": self._create_trending_data(),
            "sideways": self._create_sideways_data(),
            "volatile": self._create_volatile_data(),
        }

        regime_signals = {}

        for regime_name, data in regimes_data.items():
            signals = complete_ensemble.generate_signals(data.tail(20))
            regime_signals[regime_name] = signals

        # Analyze signal characteristics by regime
        for regime_name, signals in regime_signals.items():
            avg_confidence = np.mean([s.confidence for s in signals])
            signal_distribution = np.bincount([s.prediction for s in signals])

            assert len(signals) == 20
            assert 0 <= avg_confidence <= 1

            # Different regimes should produce different signal patterns
            if regime_name == "trending":
                # Trending markets should have more directional signals
                directional_signals = signal_distribution[1] + signal_distribution[2]
                hold_signals = signal_distribution[0]
                assert directional_signals >= hold_signals

            elif regime_name == "sideways":
                # Sideways markets should have more hold signals
                hold_signals = signal_distribution[0]
                assert hold_signals > 0

    def test_ensemble_robustness_to_model_failures(
        self, complete_ensemble, sample_market_data
    ):
        """Test ensemble robustness when individual models fail."""
        # Mock one model to fail
        complete_ensemble.models["rf_primary"].predict_proba.side_effect = Exception(
            "Model failed"
        )

        recent_data = sample_market_data.tail(10)

        # Should still generate signals with remaining models
        signals = complete_ensemble.generate_signals(recent_data)

        assert len(signals) > 0
        # Signals might have lower confidence but should still be generated
        avg_confidence = np.mean([s.confidence for s in signals])
        assert 0 <= avg_confidence <= 1

    def test_signal_latency_performance(self, complete_ensemble, sample_market_data):
        """Test signal generation latency performance."""
        # Test with varying data sizes
        data_sizes = [10, 50, 100, 500]
        latencies = {}

        for size in data_sizes:
            test_data = sample_market_data.tail(size)

            start_time = datetime.now()
            signals = complete_ensemble.generate_signals(test_data)
            end_time = datetime.now()

            latency = (end_time - start_time).total_seconds()
            latencies[size] = latency

            assert len(signals) == size
            # Should generate signals quickly
            assert latency < 2.0  # Less than 2 seconds for any size

        # Latency should scale reasonably
        assert latencies[500] < latencies[100] * 10  # Not exponential growth

    def _create_trending_data(self):
        """Helper to create trending market data."""
        dates = pd.date_range("2024-01-01", periods=50, freq="1H")
        trend = np.linspace(1.1000, 1.1300, 50)

        return pd.DataFrame(
            {
                "timestamp": dates,
                "close": trend + np.random.randn(50) * 0.0002,
                "volume": np.random.exponential(1000, 50),
                "rsi": np.random.uniform(40, 70, 50),
                "macd": np.random.randn(50) * 0.0001,
                "bollinger_ratio": np.random.uniform(-1, 2, 50),
                "returns": np.random.randn(50) * 0.001,
                "volatility": np.random.uniform(0.0001, 0.0005, 50),
            }
        )

    def _create_sideways_data(self):
        """Helper to create sideways market data."""
        dates = pd.date_range("2024-01-01", periods=50, freq="1H")
        base_price = 1.1150

        return pd.DataFrame(
            {
                "timestamp": dates,
                "close": base_price + np.random.randn(50) * 0.0008,
                "volume": np.random.exponential(800, 50),
                "rsi": np.random.uniform(30, 70, 50),
                "macd": np.random.randn(50) * 0.00005,
                "bollinger_ratio": np.random.uniform(-1.5, 1.5, 50),
                "returns": np.random.randn(50) * 0.0005,
                "volatility": np.random.uniform(0.0002, 0.0008, 50),
            }
        )

    def _create_volatile_data(self):
        """Helper to create volatile market data."""
        dates = pd.date_range("2024-01-01", periods=50, freq="1H")
        base_price = 1.1000

        return pd.DataFrame(
            {
                "timestamp": dates,
                "close": base_price + np.random.randn(50) * 0.002,  # High volatility
                "volume": np.random.exponential(1500, 50),
                "rsi": np.random.uniform(10, 90, 50),  # Extreme RSI values
                "macd": np.random.randn(50) * 0.0005,
                "bollinger_ratio": np.random.uniform(-3, 3, 50),
                "returns": np.random.randn(50) * 0.003,
                "volatility": np.random.uniform(0.001, 0.005, 50),
            }
        )
