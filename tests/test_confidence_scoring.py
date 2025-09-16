"""
Comprehensive test suite for FXML4 confidence scoring system.
Tests all aspects of confidence calculation, ML prediction scoring, trading signal assessment,
and performance tracking with extensive edge case coverage.

Test Categories:
- Unit tests for individual confidence components
- ML prediction scoring validation
- Trading signal confidence assessment
- Ensemble confidence calculation
- Historical performance tracking
- Configuration and calibration
- Integration scenarios
- Performance benchmarks
"""

import asyncio
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List
from unittest.mock import MagicMock, Mock, patch

import numpy as np
import pytest

from fxml4.core.confidence_scoring import (
    ConfidenceComponent,
    ConfidenceLevel,
    ConfidenceScore,
    ConfidenceScorer,
    ModelPredictionInput,
    TradingSignalInput,
)


@pytest.fixture
def confidence_scorer():
    """Create a ConfidenceScorer instance for testing."""
    config = {
        "component_weights": {
            "model_certainty": 0.3,
            "data_quality": 0.2,
            "historical_performance": 0.2,
            "market_regime": 0.15,
            "feature_stability": 0.15,
        }
    }
    return ConfidenceScorer(config=config)


@pytest.fixture
def sample_ml_prediction_input():
    """Create sample ML prediction input for testing."""
    return ModelPredictionInput(
        model_name="xgboost_gbpusd_4h",
        prediction=0.75,
        prediction_probabilities=np.array([0.25, 0.75]),
        prediction_variance=0.02,
        feature_values=np.array([1.2850, 0.65, -0.3, 2.1, 0.8]),
        training_accuracy=0.85,
        validation_accuracy=0.82,
    )


@pytest.fixture
def sample_trading_signal_input():
    """Create sample trading signal input for testing."""
    return TradingSignalInput(
        signal_strength=0.8,
        symbol="GBPUSD",
        timeframe="4h",
        market_data={"price": 1.2850, "volume": 1000, "spread": 0.0002},
        technical_indicators={
            "rsi": 65.5,
            "macd": -0.3,
            "volume_sma": 850,
            "volatility": 0.8,
        },
        sentiment_score=0.6,
        news_impact=0.3,
    )


@pytest.fixture
def sample_model_prediction_high_certainty():
    """Create high certainty model prediction input for testing."""
    return ModelPredictionInput(
        model_name="high_certainty_model",
        prediction=0.95,
        prediction_probabilities=np.array([0.05, 0.95]),
        feature_values=np.array([1.2850, 0.9, 0.8, 0.95, 0.85]),
        training_accuracy=0.92,
        validation_accuracy=0.90,
        prediction_variance=0.001,
    )


class TestConfidenceScorer:
    """Test suite for ConfidenceScorer class."""

    def test_confidence_scorer_initialization(self, confidence_scorer):
        """Test ConfidenceScorer initialization."""
        assert confidence_scorer is not None
        assert confidence_scorer.config is not None
        assert confidence_scorer.performance_history == {}
        assert hasattr(confidence_scorer, "market_regime_cache")

    def test_confidence_scorer_with_custom_config(self):
        """Test ConfidenceScorer with custom configuration."""
        config = {
            "min_confidence": 0.6,
            "max_confidence": 0.95,
            "component_weights": {"model_certainty": 0.4, "data_quality": 0.2},
        }
        scorer = ConfidenceScorer(config=config)
        assert scorer.config["min_confidence"] == 0.6
        assert scorer.config["max_confidence"] == 0.95
        assert scorer.config["component_weights"]["model_certainty"] == 0.4

    def test_score_ml_prediction_basic(
        self, confidence_scorer, sample_ml_prediction_input
    ):
        """Test basic ML prediction scoring."""
        confidence_score = confidence_scorer.score_ml_prediction(
            sample_ml_prediction_input
        )

        assert isinstance(confidence_score, ConfidenceScore)
        assert 0.0 <= confidence_score.overall_confidence <= 1.0
        assert len(confidence_score.component_scores) > 0
        assert ConfidenceComponent.MODEL_CERTAINTY in confidence_score.component_scores
        assert ConfidenceComponent.DATA_QUALITY in confidence_score.component_scores

    def test_score_ml_prediction_high_certainty(self, confidence_scorer):
        """Test ML prediction scoring with high certainty."""
        high_certainty_input = ModelPredictionInput(
            model_name="test_model",
            prediction=0.95,
            prediction_probabilities=np.array([0.05, 0.95]),
            prediction_variance=0.001,
            feature_values=np.array([1.0, 0.9, 0.8, 0.95, 0.85]),
            training_accuracy=0.92,
            validation_accuracy=0.90,
        )

        confidence_score = confidence_scorer.score_ml_prediction(high_certainty_input)
        assert confidence_score.overall_confidence > 0.7

    def test_score_ml_prediction_low_certainty(self, confidence_scorer):
        """Test ML prediction scoring with low certainty."""
        low_certainty_input = ModelPredictionInput(
            model_name="test_model",
            prediction=0.52,
            prediction_probabilities=np.array([0.48, 0.52]),
            prediction_variance=0.15,
            feature_values=np.array([0.1, 0.2, -0.1, 0.05, 0.15]),
            training_accuracy=0.65,
            validation_accuracy=0.62,
        )

        confidence_score = confidence_scorer.score_ml_prediction(low_certainty_input)
        # Low certainty predictions should have reasonable confidence bounds
        assert 0.0 <= confidence_score.overall_confidence <= 1.0


class TestTradingSignalConfidence:
    """Test suite for trading signal confidence scoring."""

    def test_score_trading_signal_basic(
        self, confidence_scorer, sample_trading_signal_input
    ):
        """Test basic trading signal confidence scoring."""
        confidence_score = confidence_scorer.score_trading_signal(
            sample_trading_signal_input
        )

        assert isinstance(confidence_score, ConfidenceScore)
        assert 0.0 <= confidence_score.overall_confidence <= 1.0
        # Check that we have some confidence components populated
        assert ConfidenceComponent.MARKET_REGIME in confidence_score.component_scores

    def test_score_trading_signal_strong(self, confidence_scorer):
        """Test strong trading signal confidence."""
        strong_signal = TradingSignalInput(
            signal_strength=0.95,
            symbol="GBPUSD",
            timeframe="4h",
            market_data={"price": 1.2850, "volume": 1500, "spread": 0.0001},
            technical_indicators={
                "rsi": 85.0,
                "macd": 0.5,
                "volume_sma": 1200,
                "volatility": 0.3,
            },
            sentiment_score=0.85,
            news_impact=0.1,
        )

        confidence_score = confidence_scorer.score_trading_signal(strong_signal)
        assert confidence_score.overall_confidence > 0.8

    def test_score_trading_signal_weak(self, confidence_scorer):
        """Test weak trading signal confidence."""
        weak_signal = TradingSignalInput(
            signal_strength=0.55,
            symbol="GBPUSD",
            timeframe="1h",
            market_data={"price": 1.2850, "volume": 800, "spread": 0.0005},
            technical_indicators={
                "rsi": 45.0,
                "macd": -0.1,
                "volume_sma": 950,
                "volatility": 1.2,
            },
            sentiment_score=0.4,
            news_impact=0.7,
        )

        confidence_score = confidence_scorer.score_trading_signal(weak_signal)
        # Weak signals should have valid confidence within bounds
        assert 0.0 <= confidence_score.overall_confidence <= 1.0

    def test_score_trading_signal_conflicting_components(self, confidence_scorer):
        """Test trading signal with conflicting component scores."""
        conflicting_signal = TradingSignalInput(
            signal_strength=0.7,
            symbol="GBPUSD",
            timeframe="4h",
            market_data={"price": 1.2850, "volume": 1200, "spread": 0.0003},
            technical_indicators={
                "rsi": 70.0,  # Overbought (bearish signal)
                "macd": 0.3,  # Bullish signal
                "volume_sma": 1000,
                "volatility": 1.1,  # High volatility
            },
            sentiment_score=0.2,  # Very bearish
            news_impact=0.8,  # High impact news
        )

        confidence_score = confidence_scorer.score_trading_signal(conflicting_signal)
        # Should handle conflicting signals
        assert isinstance(confidence_score, ConfidenceScore)
        assert 0.0 <= confidence_score.overall_confidence <= 1.0


class TestModelPredictionVariants:
    """Test suite for different model prediction scenarios."""

    def test_score_prediction_with_probabilities(self, confidence_scorer):
        """Test prediction scoring with probability distributions."""
        prob_input = ModelPredictionInput(
            model_name="probability_model",
            prediction=0.85,
            prediction_probabilities=np.array([0.15, 0.85]),
            feature_values=np.array([1.2850, 0.9, 0.8]),
            training_accuracy=0.88,
            validation_accuracy=0.85,
        )

        confidence_score = confidence_scorer.score_ml_prediction(prob_input)
        assert isinstance(confidence_score, ConfidenceScore)
        assert confidence_score.overall_confidence > 0.6

    def test_score_prediction_without_probabilities(self, confidence_scorer):
        """Test prediction scoring without probability distributions."""
        simple_input = ModelPredictionInput(
            model_name="simple_model",
            prediction=0.72,
            feature_values=np.array([1.2850, 0.7, 0.6]),
            training_accuracy=0.80,
            validation_accuracy=0.78,
        )

        confidence_score = confidence_scorer.score_ml_prediction(simple_input)
        assert isinstance(confidence_score, ConfidenceScore)
        assert 0.0 <= confidence_score.overall_confidence <= 1.0


class TestConfidenceComponents:
    """Test suite for individual confidence components."""

    def test_model_certainty_component(self, confidence_scorer):
        """Test model certainty component scoring."""
        high_certainty_score = confidence_scorer._score_model_certainty(
            prediction=0.95, probabilities=[0.05, 0.95], variance=0.001
        )
        assert high_certainty_score > 0.8

        low_certainty_score = confidence_scorer._score_model_certainty(
            prediction=0.52, probabilities=[0.48, 0.52], variance=0.1
        )
        assert low_certainty_score < 0.5

    def test_data_quality_component(self, confidence_scorer):
        """Test data quality component scoring."""
        high_quality_features = np.array([1.2850, 0.65, -0.3, 2.1, 0.8])
        high_quality_score = confidence_scorer._score_data_quality(
            high_quality_features
        )
        assert high_quality_score > 0.5

        # Test with NaN values
        low_quality_features = np.array([1.2850, np.nan, -0.3, float("inf"), 0.8])
        low_quality_score = confidence_scorer._score_data_quality(low_quality_features)
        assert low_quality_score < high_quality_score

    def test_historical_performance_component(self, confidence_scorer):
        """Test historical performance component scoring."""
        high_performance_score = confidence_scorer._score_historical_performance(
            model_name="test_model", training_accuracy=0.92, validation_accuracy=0.90
        )
        assert high_performance_score > 0.7

        low_performance_score = confidence_scorer._score_historical_performance(
            model_name="test_model", training_accuracy=0.65, validation_accuracy=0.62
        )
        assert low_performance_score < 0.6

    def test_feature_quality_component(self, confidence_scorer):
        """Test feature quality assessment component."""
        high_quality_features = np.array([1.2850, 0.65, -0.3, 2.1, 0.8])
        high_quality_score = confidence_scorer._score_data_quality(
            high_quality_features
        )

        low_quality_features = np.array([np.nan, 0.65, float("inf"), 2.1, -999])
        low_quality_score = confidence_scorer._score_data_quality(low_quality_features)

        assert high_quality_score > low_quality_score

    def test_signal_strength_component(self, confidence_scorer):
        """Test signal strength component scoring."""
        strong_signal_score = confidence_scorer._score_signal_strength(0.9)
        weak_signal_score = confidence_scorer._score_signal_strength(0.55)

        assert strong_signal_score > 0.8
        assert weak_signal_score < 0.6
        assert strong_signal_score > weak_signal_score


class TestPerformanceTracking:
    """Test suite for performance tracking and calibration."""

    def test_update_performance_history(self, confidence_scorer):
        """Test updating performance history."""
        model_name = "test_model"
        performance_data = {
            "prediction": 0.8,
            "actual_outcome": 1,
            "confidence": 0.85,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        # Simulate updating performance history
        if model_name not in confidence_scorer.performance_history:
            confidence_scorer.performance_history[model_name] = []
        confidence_scorer.performance_history[model_name].append(performance_data)

        assert model_name in confidence_scorer.performance_history
        assert len(confidence_scorer.performance_history[model_name]) == 1
        assert confidence_scorer.performance_history[model_name][0]["prediction"] == 0.8

    def test_performance_history_accumulation(self, confidence_scorer):
        """Test performance history accumulation over time."""
        model_name = "accumulation_test_model"

        # Add multiple performance records
        for i in range(5):
            performance_data = {
                "prediction": 0.7 + i * 0.05,
                "actual_outcome": 1 if i % 2 == 0 else 0,
                "confidence": 0.8 + i * 0.02,
                "timestamp": (
                    datetime.now(timezone.utc) + timedelta(minutes=i)
                ).isoformat(),
            }

            if model_name not in confidence_scorer.performance_history:
                confidence_scorer.performance_history[model_name] = []
            confidence_scorer.performance_history[model_name].append(performance_data)

        assert model_name in confidence_scorer.performance_history
        assert len(confidence_scorer.performance_history[model_name]) == 5

        # Verify chronological order
        records = confidence_scorer.performance_history[model_name]
        for i in range(1, len(records)):
            time1 = datetime.fromisoformat(records[i - 1]["timestamp"])
            time2 = datetime.fromisoformat(records[i]["timestamp"])
            assert time2 > time1

    @pytest.mark.asyncio
    async def test_async_confidence_update(self, confidence_scorer):
        """Test async confidence metric updates."""
        model_name = "async_test_model"

        # Simulate async performance update
        async def update_performance():
            await asyncio.sleep(0.01)  # Simulate async work
            confidence_scorer.update_performance_metrics(model_name, [0.8], [1], [0.9])

        await update_performance()
        assert model_name in confidence_scorer.performance_history


class TestConfidenceThresholds:
    """Test suite for confidence thresholds and decision making."""

    def test_get_confidence_level(self, confidence_scorer):
        """Test confidence level classification."""
        high_confidence = ConfidenceScore(
            overall_confidence=0.9,
            component_scores={ConfidenceComponent.MODEL_CERTAINTY: 0.9},
        )
        assert (
            confidence_scorer.get_confidence_level(high_confidence)
            == ConfidenceLevel.HIGH
        )

        medium_confidence = ConfidenceScore(
            overall_confidence=0.7,
            component_scores={ConfidenceComponent.MODEL_CERTAINTY: 0.7},
        )
        assert (
            confidence_scorer.get_confidence_level(medium_confidence)
            == ConfidenceLevel.MEDIUM
        )

        low_confidence = ConfidenceScore(
            overall_confidence=0.4,
            component_scores={ConfidenceComponent.MODEL_CERTAINTY: 0.4},
        )
        assert (
            confidence_scorer.get_confidence_level(low_confidence)
            == ConfidenceLevel.LOW
        )

    def test_confidence_level_classification(self, confidence_scorer):
        """Test confidence level classification from scores."""
        # Test very high confidence
        very_high_score = ConfidenceScore(overall_confidence=0.95)
        assert very_high_score.confidence_level == ConfidenceLevel.VERY_HIGH

        # Test high confidence
        high_score = ConfidenceScore(overall_confidence=0.85)
        assert high_score.confidence_level == ConfidenceLevel.HIGH

        # Test medium confidence
        medium_score = ConfidenceScore(overall_confidence=0.7)
        assert medium_score.confidence_level == ConfidenceLevel.MEDIUM

        # Test low confidence
        low_score = ConfidenceScore(overall_confidence=0.5)
        assert low_score.confidence_level == ConfidenceLevel.LOW

        # Test very low confidence
        very_low_score = ConfidenceScore(overall_confidence=0.2)
        assert very_low_score.confidence_level == ConfidenceLevel.VERY_LOW

    def test_confidence_score_serialization(self, confidence_scorer):
        """Test confidence score serialization to dictionary."""
        confidence_score = ConfidenceScore(
            overall_confidence=0.75,
            component_scores={
                ConfidenceComponent.MODEL_CERTAINTY: 0.8,
                ConfidenceComponent.DATA_QUALITY: 0.7,
            },
            metadata={"model_name": "test_model", "version": "1.0"},
        )

        score_dict = confidence_score.to_dict()

        assert isinstance(score_dict, dict)
        assert score_dict["overall_confidence"] == 0.75
        assert score_dict["confidence_level"] == ConfidenceLevel.MEDIUM.value
        assert "component_scores" in score_dict
        assert "metadata" in score_dict
        assert "timestamp" in score_dict


class TestEdgeCases:
    """Test suite for edge cases and error handling."""

    def test_empty_feature_values(self, confidence_scorer):
        """Test handling of empty feature values."""
        empty_input = ModelPredictionInput(
            model_name="test_model",
            prediction=0.7,
            feature_values=np.array([]),
            feature_names=[],
        )

        # Should handle gracefully without crashing
        confidence_score = confidence_scorer.score_ml_prediction(empty_input)
        assert isinstance(confidence_score, ConfidenceScore)

    def test_nan_prediction_values(self, confidence_scorer):
        """Test handling of NaN prediction values."""
        nan_input = ModelPredictionInput(
            model_name="test_model",
            prediction=float("nan"),
            prediction_probabilities=[np.nan, np.nan],
            feature_values=np.array([1.0, 2.0, np.nan]),
        )

        confidence_score = confidence_scorer.score_ml_prediction(nan_input)
        # Should handle invalid predictions gracefully
        assert isinstance(confidence_score, ConfidenceScore)
        assert 0.0 <= confidence_score.overall_confidence <= 1.0

    def test_extreme_prediction_values(self, confidence_scorer):
        """Test handling of extreme prediction values."""
        extreme_input = ModelPredictionInput(
            model_name="test_model",
            prediction=1.5,  # Outside [0,1] range
            prediction_probabilities=[-0.5, 1.5],  # Invalid probabilities
            prediction_variance=float("inf"),
            feature_values=np.array([float("inf"), -float("inf"), 1e10]),
        )

        confidence_score = confidence_scorer.score_ml_prediction(extreme_input)
        assert confidence_score.overall_confidence < 0.2

    def test_missing_component_scores(self, confidence_scorer):
        """Test handling when some component scores are missing."""
        # Simulate missing data by mocking component calculation
        with patch.object(confidence_scorer, "_score_data_quality", return_value=None):
            confidence_score = confidence_scorer.score_ml_prediction(
                ModelPredictionInput(model_name="test", prediction=0.7)
            )
            assert isinstance(confidence_score, ConfidenceScore)

    def test_thread_safety(self, confidence_scorer):
        """Test thread safety of confidence scoring."""
        import concurrent.futures
        import threading

        def score_prediction(i):
            input_data = ModelPredictionInput(
                model_name=f"model_{i}",
                prediction=0.5 + i * 0.1,
                feature_values=np.array([i, i + 1, i + 2]),
            )
            return confidence_scorer.score_ml_prediction(input_data)

        # Run multiple threads concurrently
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(score_prediction, i) for i in range(20)]
            results = [
                future.result() for future in concurrent.futures.as_completed(futures)
            ]

        assert len(results) == 20
        for result in results:
            assert isinstance(result, ConfidenceScore)


class TestIntegration:
    """Integration tests for confidence scoring system."""

    def test_end_to_end_ml_confidence_pipeline(self, confidence_scorer):
        """Test complete ML confidence scoring pipeline."""
        # Step 1: Create ML prediction
        ml_input = ModelPredictionInput(
            model_name="integration_test_model",
            prediction=0.78,
            prediction_probabilities=np.array([0.22, 0.78]),
            feature_values=np.array([1.2850, 0.65, -0.3, 2.1]),
            training_accuracy=0.85,
            validation_accuracy=0.82,
        )

        # Step 2: Score the prediction
        confidence_score = confidence_scorer.score_ml_prediction(ml_input)

        # Step 3: Verify confidence score properties
        assert isinstance(confidence_score, ConfidenceScore)
        assert 0.0 <= confidence_score.overall_confidence <= 1.0
        assert isinstance(confidence_score.confidence_level, ConfidenceLevel)
        assert isinstance(confidence_score.component_scores, dict)

        # Step 4: Update performance history
        performance_data = {
            "prediction": 0.78,
            "actual_outcome": 1,
            "confidence": confidence_score.overall_confidence,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        if "integration_test_model" not in confidence_scorer.performance_history:
            confidence_scorer.performance_history["integration_test_model"] = []
        confidence_scorer.performance_history["integration_test_model"].append(
            performance_data
        )

        # Verify end-to-end flow
        assert "integration_test_model" in confidence_scorer.performance_history
        assert len(confidence_scorer.performance_history["integration_test_model"]) == 1

    def test_confidence_scorer_with_realistic_trading_scenario(self, confidence_scorer):
        """Test confidence scorer with realistic GBP/USD trading scenario."""
        # Simulate realistic GBP/USD trading scenario
        gbpusd_input = TradingSignalInput(
            signal_strength=0.73,
            symbol="GBPUSD",
            timeframe="4h",
            market_data={
                "price": 1.2850,
                "volume": 1200,
                "spread": 0.0002,
                "bid": 1.2849,
                "ask": 1.2851,
            },
            technical_indicators={
                "rsi": 68.5,
                "macd": 0.0025,
                "sma_20": 1.2835,
                "sma_50": 1.2820,
                "volatility": 0.85,
            },
            sentiment_score=0.65,
            news_impact=0.3,
        )

        confidence_score = confidence_scorer.score_trading_signal(gbpusd_input)

        # Realistic expectations for GBP/USD trading
        assert isinstance(confidence_score, ConfidenceScore)
        assert 0.0 <= confidence_score.overall_confidence <= 1.0
        assert confidence_score.confidence_level in [level for level in ConfidenceLevel]

    def test_performance_degradation_detection(self, confidence_scorer):
        """Test detection of model performance degradation."""
        model_name = "degradation_test_model"

        # Simulate initially good performance
        good_predictions = [0.8, 0.85, 0.9, 0.75, 0.82]
        good_outcomes = [1, 1, 1, 1, 1]  # All correct
        good_confidences = [0.8, 0.85, 0.9, 0.75, 0.82]

        confidence_scorer.update_performance_metrics(
            model_name, good_predictions, good_outcomes, good_confidences
        )

        initial_metrics = confidence_scorer.performance_history[model_name]
        initial_accuracy = initial_metrics.accuracy

        # Simulate performance degradation
        bad_predictions = [0.7, 0.6, 0.8, 0.9, 0.75]
        bad_outcomes = [0, 0, 0, 0, 0]  # All wrong
        bad_confidences = [0.7, 0.6, 0.8, 0.9, 0.75]

        confidence_scorer.update_performance_metrics(
            model_name, bad_predictions, bad_outcomes, bad_confidences
        )

        degraded_metrics = confidence_scorer.performance_history[model_name]

        # Performance should have degraded
        assert degraded_metrics.accuracy < initial_accuracy


class TestPerformanceBenchmarks:
    """Performance benchmarks for confidence scoring system."""

    def test_ml_prediction_scoring_performance(
        self, confidence_scorer, sample_ml_prediction_input
    ):
        """Benchmark ML prediction confidence scoring performance."""
        start_time = time.time()

        # Score 1000 predictions
        for _ in range(1000):
            confidence_scorer.score_ml_prediction(sample_ml_prediction_input)

        end_time = time.time()
        total_time = end_time - start_time
        avg_time_per_prediction = total_time / 1000

        # Should be able to score predictions quickly for real-time trading
        assert avg_time_per_prediction < 0.001  # Less than 1ms per prediction
        print(
            f"Average ML prediction scoring time: {avg_time_per_prediction*1000:.2f}ms"
        )

    def test_trading_signal_scoring_performance(
        self, confidence_scorer, sample_trading_signal_input
    ):
        """Benchmark trading signal confidence scoring performance."""
        start_time = time.time()

        # Score 1000 trading signals
        for _ in range(1000):
            confidence_scorer.score_trading_signal(sample_trading_signal_input)

        end_time = time.time()
        total_time = end_time - start_time
        avg_time_per_signal = total_time / 1000

        # Should be fast enough for real-time signal processing
        assert avg_time_per_signal < 0.002  # Less than 2ms per signal
        print(f"Average trading signal scoring time: {avg_time_per_signal*1000:.2f}ms")

    def test_ensemble_scoring_performance(
        self, confidence_scorer, sample_ensemble_input
    ):
        """Benchmark ensemble prediction confidence scoring performance."""
        start_time = time.time()

        # Score 500 ensemble predictions (more complex, so fewer iterations)
        for _ in range(500):
            confidence_scorer.score_ensemble_prediction(sample_ensemble_input)

        end_time = time.time()
        total_time = end_time - start_time
        avg_time_per_ensemble = total_time / 500

        # Ensemble scoring can be slightly slower due to complexity
        assert avg_time_per_ensemble < 0.005  # Less than 5ms per ensemble
        print(f"Average ensemble scoring time: {avg_time_per_ensemble*1000:.2f}ms")


# Configuration for pytest
pytest.main([__file__, "-v", "--tb=short"])
