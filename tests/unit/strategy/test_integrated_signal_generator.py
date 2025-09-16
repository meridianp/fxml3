"""
Comprehensive unit tests for integrated signal generator.

Tests the combination of ML, Elliott Wave, and LLM sentiment analysis
following TDD methodology for increased test coverage.
"""

from datetime import datetime, timedelta
from typing import Dict, List, Optional
from unittest.mock import AsyncMock, Mock, patch

import numpy as np
import pandas as pd
import pytest

from fxml4.strategy.integrated_signal_generator import (
    IntegratedSignal,
    IntegratedSignalGenerator,
)


@pytest.fixture
def mock_ml_ensemble():
    """Mock ML ensemble predictor."""
    mock = AsyncMock()
    mock.predict.return_value = {
        "signal": 1,
        "confidence": 0.75,
        "probabilities": [0.25, 0.75],
        "models_agreement": 0.82,
    }
    return mock


@pytest.fixture
def mock_wave_signal_generator():
    """Mock Enhanced Wave Signal Generator."""
    mock = AsyncMock()
    mock.generate_signal.return_value = {
        "pattern": "impulse_wave_5",
        "confidence": 0.8,
        "direction": 1,
        "completion_probability": 0.65,
        "target_levels": [1.2680, 1.2720],
    }
    return mock


@pytest.fixture
def mock_sentiment_analyzer():
    """Mock LLM sentiment analyzer."""
    mock = AsyncMock()
    mock.analyze_market_sentiment.return_value = {
        "sentiment_score": 0.65,  # Bullish sentiment
        "confidence": 0.78,
        "key_factors": ["positive_economic_data", "risk_on_sentiment"],
        "news_impact": "positive",
    }
    return mock


@pytest.fixture
def mock_regime_detector():
    """Mock market regime detector."""
    mock = Mock()
    mock.detect_regime.return_value = {
        "regime": "trending",
        "confidence": 0.85,
        "volatility_cluster": "medium",
        "trend_strength": 0.72,
    }
    return mock


@pytest.fixture
def mock_sentiment_wave_validator():
    """Mock sentiment wave validator."""
    mock = Mock()
    mock.validate_signal.return_value = {
        "is_valid": True,
        "validation_score": 0.88,
        "sentiment_wave_alignment": "strong",
        "risk_factors": [],
    }
    return mock


@pytest.fixture
def sample_market_data():
    """Generate sample market data for testing."""
    dates = pd.date_range(start="2024-01-01 10:00:00", periods=24, freq="1H")
    np.random.seed(42)

    base_price = 1.2650
    returns = np.random.normal(0, 0.001, 24)
    prices = base_price + np.cumsum(returns)

    data = []
    for i, (date, close) in enumerate(zip(dates, prices)):
        open_price = prices[i - 1] if i > 0 else close
        high = max(open_price, close) + np.random.uniform(0, 0.002)
        low = min(open_price, close) - np.random.uniform(0, 0.002)
        volume = np.random.randint(8000, 15000)

        data.append(
            {
                "timestamp": date,
                "open": open_price,
                "high": high,
                "low": low,
                "close": close,
                "volume": volume,
            }
        )

    return pd.DataFrame(data)


@pytest.fixture
def generator_config():
    """Configuration for integrated signal generator."""
    return {
        "ml_weight": 0.4,
        "wave_weight": 0.35,
        "sentiment_weight": 0.25,
        "min_confidence_threshold": 0.6,
        "max_models_disagreement": 0.3,
        "sentiment_validation_required": True,
        "regime_filtering": True,
    }


@pytest.fixture
async def signal_generator(
    generator_config,
    mock_ml_ensemble,
    mock_wave_signal_generator,
    mock_sentiment_analyzer,
    mock_regime_detector,
    mock_sentiment_wave_validator,
):
    """Create integrated signal generator with mocked dependencies."""
    generator = IntegratedSignalGenerator(generator_config)

    # Inject mocked dependencies
    generator.ml_ensemble = mock_ml_ensemble
    generator.wave_generator = mock_wave_signal_generator
    generator.sentiment_analyzer = mock_sentiment_analyzer
    generator.regime_detector = mock_regime_detector
    generator.sentiment_validator = mock_sentiment_wave_validator

    await generator.initialize()
    return generator


class TestIntegratedSignalGeneratorInitialization:
    """Test signal generator initialization."""

    def test_generator_creation_with_valid_config(self, generator_config):
        """Test generator can be created with valid configuration."""
        generator = IntegratedSignalGenerator(generator_config)

        assert generator.ml_weight == 0.4
        assert generator.wave_weight == 0.35
        assert generator.sentiment_weight == 0.25
        assert (
            abs(
                generator.ml_weight
                + generator.wave_weight
                + generator.sentiment_weight
                - 1.0
            )
            < 1e-6
        )

    def test_generator_creation_with_invalid_weights(self, generator_config):
        """Test generator validates weight sum."""
        generator_config["ml_weight"] = 0.5
        generator_config["wave_weight"] = 0.5
        generator_config["sentiment_weight"] = 0.5  # Sum > 1.0

        with pytest.raises(ValueError, match="Weights must sum to 1.0"):
            IntegratedSignalGenerator(generator_config)

    def test_generator_creation_with_negative_weights(self, generator_config):
        """Test generator rejects negative weights."""
        generator_config["ml_weight"] = -0.1

        with pytest.raises(ValueError, match="Weights must be non-negative"):
            IntegratedSignalGenerator(generator_config)

    @pytest.mark.asyncio
    async def test_generator_initialization_success(self, signal_generator):
        """Test successful generator initialization."""
        assert signal_generator.is_initialized
        assert signal_generator.ml_ensemble is not None
        assert signal_generator.wave_generator is not None
        assert signal_generator.sentiment_analyzer is not None


class TestSignalGeneration:
    """Test integrated signal generation logic."""

    @pytest.mark.asyncio
    async def test_generate_strong_bullish_signal(
        self,
        signal_generator,
        sample_market_data,
        mock_ml_ensemble,
        mock_wave_signal_generator,
        mock_sentiment_analyzer,
    ):
        """Test generation of strong bullish signal with all components aligned."""
        # Setup all components for bullish signal
        mock_ml_ensemble.predict.return_value = {
            "signal": 1,
            "confidence": 0.85,
            "probabilities": [0.15, 0.85],
        }
        mock_wave_signal_generator.generate_signal.return_value = {
            "pattern": "impulse_wave_3",
            "confidence": 0.9,
            "direction": 1,
        }
        mock_sentiment_analyzer.analyze_market_sentiment.return_value = {
            "sentiment_score": 0.8,
            "confidence": 0.85,
        }

        signal = await signal_generator.generate_integrated_signal(sample_market_data)

        assert signal.direction == 1
        assert signal.confidence >= 0.8
        assert signal.ml_signal == 1
        assert signal.wave_pattern == "impulse_wave_3"
        assert signal.sentiment_score == 0.8
        assert "strong_bullish_consensus" in signal.reasoning

    @pytest.mark.asyncio
    async def test_generate_conflicting_signals(
        self,
        signal_generator,
        sample_market_data,
        mock_ml_ensemble,
        mock_wave_signal_generator,
        mock_sentiment_analyzer,
    ):
        """Test handling of conflicting signals from different components."""
        # Setup conflicting signals
        mock_ml_ensemble.predict.return_value = {
            "signal": 1,
            "confidence": 0.75,
            "probabilities": [0.25, 0.75],
        }
        mock_wave_signal_generator.generate_signal.return_value = {
            "pattern": "corrective_wave_c",
            "confidence": 0.8,
            "direction": -1,
        }
        mock_sentiment_analyzer.analyze_market_sentiment.return_value = {
            "sentiment_score": 0.3,
            "confidence": 0.7,  # Bearish sentiment
        }

        signal = await signal_generator.generate_integrated_signal(sample_market_data)

        # Should result in neutral or low confidence signal
        assert signal.confidence < 0.6 or signal.direction == 0
        assert "conflicting_signals" in signal.reasoning

    @pytest.mark.asyncio
    async def test_generate_signal_below_threshold(
        self, signal_generator, sample_market_data, mock_ml_ensemble
    ):
        """Test no signal generated when combined confidence below threshold."""
        # Setup low confidence across all components
        mock_ml_ensemble.predict.return_value = {
            "signal": 1,
            "confidence": 0.4,
            "probabilities": [0.6, 0.4],
        }
        signal_generator.wave_generator.generate_signal.return_value = {
            "pattern": None,
            "confidence": 0.2,
            "direction": 0,
        }
        signal_generator.sentiment_analyzer.analyze_market_sentiment.return_value = {
            "sentiment_score": 0.5,
            "confidence": 0.3,
        }

        signal = await signal_generator.generate_integrated_signal(sample_market_data)

        assert signal.direction == 0
        assert signal.confidence < 0.6
        assert "insufficient_confidence" in signal.reasoning


class TestWeightedSignalCombination:
    """Test weighted combination of multiple signal sources."""

    @pytest.mark.asyncio
    async def test_ml_dominated_signal(self, signal_generator, sample_market_data):
        """Test signal where ML component dominates."""
        # Strong ML signal, weak others
        signal_generator.ml_ensemble.predict.return_value = {
            "signal": 1,
            "confidence": 0.95,
            "probabilities": [0.05, 0.95],
        }
        signal_generator.wave_generator.generate_signal.return_value = {
            "pattern": None,
            "confidence": 0.2,
            "direction": 0,
        }
        signal_generator.sentiment_analyzer.analyze_market_sentiment.return_value = {
            "sentiment_score": 0.52,
            "confidence": 0.3,
        }

        signal = await signal_generator.generate_integrated_signal(sample_market_data)

        # Should still be bullish due to strong ML signal and weighting
        weighted_confidence = 0.95 * 0.4 + 0.2 * 0.35 + 0.3 * 0.25
        assert signal.direction == 1
        assert abs(signal.confidence - weighted_confidence) < 0.1

    @pytest.mark.asyncio
    async def test_wave_dominated_signal(self, signal_generator, sample_market_data):
        """Test signal where Elliott Wave component dominates."""
        # Strong Wave signal, weak others
        signal_generator.ml_ensemble.predict.return_value = {
            "signal": 0,
            "confidence": 0.3,
            "probabilities": [0.5, 0.5],
        }
        signal_generator.wave_generator.generate_signal.return_value = {
            "pattern": "impulse_wave_5",
            "confidence": 0.95,
            "direction": 1,
        }
        signal_generator.sentiment_analyzer.analyze_market_sentiment.return_value = {
            "sentiment_score": 0.48,
            "confidence": 0.25,
        }

        signal = await signal_generator.generate_integrated_signal(sample_market_data)

        # Should be bullish due to strong Wave signal
        assert signal.direction == 1
        assert signal.wave_confidence == 0.95

    @pytest.mark.asyncio
    async def test_sentiment_influenced_signal(
        self, signal_generator, sample_market_data
    ):
        """Test how sentiment influences overall signal."""
        # Moderate ML and Wave, strong sentiment
        signal_generator.ml_ensemble.predict.return_value = {
            "signal": 1,
            "confidence": 0.65,
            "probabilities": [0.35, 0.65],
        }
        signal_generator.wave_generator.generate_signal.return_value = {
            "pattern": "impulse_wave_1",
            "confidence": 0.7,
            "direction": 1,
        }
        signal_generator.sentiment_analyzer.analyze_market_sentiment.return_value = {
            "sentiment_score": 0.9,
            "confidence": 0.85,  # Very bullish sentiment
        }

        signal = await signal_generator.generate_integrated_signal(sample_market_data)

        assert signal.direction == 1
        assert signal.sentiment_score == 0.9
        assert signal.confidence > 0.7  # Boosted by strong sentiment


class TestMarketRegimeFiltering:
    """Test market regime-based signal filtering."""

    @pytest.mark.asyncio
    async def test_trending_market_signal_boost(
        self, signal_generator, sample_market_data, mock_regime_detector
    ):
        """Test signals are boosted in trending markets."""
        mock_regime_detector.detect_regime.return_value = {
            "regime": "trending",
            "confidence": 0.9,
            "trend_strength": 0.8,
        }

        # Moderate signal
        signal_generator.ml_ensemble.predict.return_value = {
            "signal": 1,
            "confidence": 0.65,
            "probabilities": [0.35, 0.65],
        }

        signal = await signal_generator.generate_integrated_signal(sample_market_data)

        # Should be boosted due to trending regime
        assert signal.market_regime == "trending"
        assert signal.position_size_multiplier >= 1.0

    @pytest.mark.asyncio
    async def test_ranging_market_signal_dampening(
        self, signal_generator, sample_market_data, mock_regime_detector
    ):
        """Test signals are dampened in ranging markets."""
        mock_regime_detector.detect_regime.return_value = {
            "regime": "ranging",
            "confidence": 0.85,
            "volatility_cluster": "low",
        }

        # Strong signal
        signal_generator.ml_ensemble.predict.return_value = {
            "signal": 1,
            "confidence": 0.85,
            "probabilities": [0.15, 0.85],
        }

        signal = await signal_generator.generate_integrated_signal(sample_market_data)

        # Should be dampened due to ranging regime
        assert signal.market_regime == "ranging"
        assert signal.position_size_multiplier <= 0.8

    @pytest.mark.asyncio
    async def test_volatile_market_risk_adjustment(
        self, signal_generator, sample_market_data, mock_regime_detector
    ):
        """Test risk adjustments in volatile markets."""
        mock_regime_detector.detect_regime.return_value = {
            "regime": "volatile",
            "confidence": 0.9,
            "volatility_cluster": "high",
        }

        signal = await signal_generator.generate_integrated_signal(sample_market_data)

        assert signal.market_regime == "volatile"
        assert signal.risk_score >= 0.7  # Higher risk score
        assert signal.position_size_multiplier <= 0.6  # Reduced position size


class TestSentimentWaveValidation:
    """Test sentiment-wave alignment validation."""

    @pytest.mark.asyncio
    async def test_sentiment_wave_alignment_validation(
        self, signal_generator, sample_market_data, mock_sentiment_wave_validator
    ):
        """Test sentiment-wave alignment enhances signal confidence."""
        mock_sentiment_wave_validator.validate_signal.return_value = {
            "is_valid": True,
            "validation_score": 0.92,
            "sentiment_wave_alignment": "strong",
        }

        signal = await signal_generator.generate_integrated_signal(sample_market_data)

        # Signal should be enhanced due to strong alignment
        assert "sentiment_wave_aligned" in signal.reasoning
        assert signal.confidence >= 0.7

    @pytest.mark.asyncio
    async def test_sentiment_wave_misalignment_penalty(
        self, signal_generator, sample_market_data, mock_sentiment_wave_validator
    ):
        """Test misaligned sentiment-wave reduces signal confidence."""
        mock_sentiment_wave_validator.validate_signal.return_value = {
            "is_valid": False,
            "validation_score": 0.25,
            "sentiment_wave_alignment": "weak",
            "risk_factors": ["sentiment_divergence", "wave_pattern_unclear"],
        }

        signal = await signal_generator.generate_integrated_signal(sample_market_data)

        # Signal confidence should be reduced
        assert signal.confidence < 0.6
        assert "sentiment_wave_misaligned" in signal.reasoning


class TestErrorHandling:
    """Test error handling and fallback mechanisms."""

    @pytest.mark.asyncio
    async def test_ml_component_failure(
        self, signal_generator, sample_market_data, mock_ml_ensemble
    ):
        """Test graceful handling of ML component failure."""
        mock_ml_ensemble.predict.side_effect = Exception("ML model unavailable")

        signal = await signal_generator.generate_integrated_signal(sample_market_data)

        # Should still generate signal using other components
        assert signal is not None
        assert signal.ml_confidence == 0.0
        assert "ml_component_failed" in signal.reasoning

    @pytest.mark.asyncio
    async def test_wave_component_failure(
        self, signal_generator, sample_market_data, mock_wave_signal_generator
    ):
        """Test graceful handling of Wave component failure."""
        mock_wave_signal_generator.generate_signal.side_effect = Exception(
            "Wave analysis failed"
        )

        signal = await signal_generator.generate_integrated_signal(sample_market_data)

        assert signal is not None
        assert signal.wave_confidence == 0.0
        assert signal.wave_pattern is None

    @pytest.mark.asyncio
    async def test_sentiment_component_failure(
        self, signal_generator, sample_market_data, mock_sentiment_analyzer
    ):
        """Test graceful handling of sentiment component failure."""
        mock_sentiment_analyzer.analyze_market_sentiment.side_effect = Exception(
            "Sentiment API unavailable"
        )

        signal = await signal_generator.generate_integrated_signal(sample_market_data)

        assert signal is not None
        assert signal.sentiment_score == 0.5  # Neutral fallback
        assert "sentiment_component_failed" in signal.reasoning

    @pytest.mark.asyncio
    async def test_all_components_failure(self, signal_generator, sample_market_data):
        """Test handling when all components fail."""
        signal_generator.ml_ensemble.predict.side_effect = Exception("ML failed")
        signal_generator.wave_generator.generate_signal.side_effect = Exception(
            "Wave failed"
        )
        signal_generator.sentiment_analyzer.analyze_market_sentiment.side_effect = (
            Exception("Sentiment failed")
        )

        signal = await signal_generator.generate_integrated_signal(sample_market_data)

        # Should return neutral signal with error indication
        assert signal.direction == 0
        assert signal.confidence == 0.0
        assert "all_components_failed" in signal.reasoning


class TestSignalReasoningLogic:
    """Test signal reasoning and explanation generation."""

    @pytest.mark.asyncio
    async def test_bullish_consensus_reasoning(
        self, signal_generator, sample_market_data
    ):
        """Test reasoning when all components agree on bullish signal."""
        # Setup bullish consensus
        signal_generator.ml_ensemble.predict.return_value = {
            "signal": 1,
            "confidence": 0.8,
            "probabilities": [0.2, 0.8],
        }
        signal_generator.wave_generator.generate_signal.return_value = {
            "pattern": "impulse_wave_3",
            "confidence": 0.85,
            "direction": 1,
        }
        signal_generator.sentiment_analyzer.analyze_market_sentiment.return_value = {
            "sentiment_score": 0.75,
            "confidence": 0.8,
        }

        signal = await signal_generator.generate_integrated_signal(sample_market_data)

        reasoning_components = [
            "ML models bullish",
            "Elliott Wave impulse_wave_3",
            "positive sentiment",
            "strong consensus",
        ]

        for component in reasoning_components:
            assert any(comp.lower() in signal.reasoning.lower() for comp in [component])

    @pytest.mark.asyncio
    async def test_mixed_signals_reasoning(self, signal_generator, sample_market_data):
        """Test reasoning for mixed/conflicting signals."""
        # Setup mixed signals
        signal_generator.ml_ensemble.predict.return_value = {
            "signal": 1,
            "confidence": 0.7,
            "probabilities": [0.3, 0.7],
        }
        signal_generator.wave_generator.generate_signal.return_value = {
            "pattern": "corrective_wave_b",
            "confidence": 0.6,
            "direction": -1,
        }
        signal_generator.sentiment_analyzer.analyze_market_sentiment.return_value = {
            "sentiment_score": 0.45,
            "confidence": 0.5,
        }

        signal = await signal_generator.generate_integrated_signal(sample_market_data)

        assert (
            "mixed signals" in signal.reasoning.lower()
            or "conflicting" in signal.reasoning.lower()
        )
        assert "caution" in signal.reasoning.lower()


@pytest.mark.performance
class TestPerformanceRequirements:
    """Test performance requirements for signal generation."""

    @pytest.mark.asyncio
    async def test_signal_generation_speed(self, signal_generator, sample_market_data):
        """Test signal generation completes within performance requirements."""
        import time

        start_time = time.time()
        signal = await signal_generator.generate_integrated_signal(sample_market_data)
        end_time = time.time()

        execution_time = end_time - start_time
        assert execution_time < 1.5, f"Signal generation took {execution_time:.2f}s"

    @pytest.mark.asyncio
    async def test_concurrent_signal_generation(
        self, signal_generator, sample_market_data
    ):
        """Test multiple concurrent signal generations."""
        import asyncio
        import time

        start_time = time.time()

        # Generate 5 signals concurrently
        tasks = [
            signal_generator.generate_integrated_signal(sample_market_data)
            for _ in range(5)
        ]
        signals = await asyncio.gather(*tasks)

        end_time = time.time()
        execution_time = end_time - start_time

        assert len(signals) == 5
        assert all(signal is not None for signal in signals)
        assert execution_time < 3.0, f"Concurrent generation took {execution_time:.2f}s"


@pytest.mark.integration
class TestIntegrationScenarios:
    """Test integrated scenarios with real-world complexity."""

    @pytest.mark.asyncio
    async def test_news_event_impact(self, signal_generator, sample_market_data):
        """Test signal adaptation during news events."""
        # Simulate major news event affecting sentiment
        signal_generator.sentiment_analyzer.analyze_market_sentiment.return_value = {
            "sentiment_score": 0.95,  # Extremely bullish
            "confidence": 0.95,
            "key_factors": ["major_economic_announcement", "currency_intervention"],
            "news_impact": "major_positive",
        }

        signal = await signal_generator.generate_integrated_signal(sample_market_data)

        # Signal should reflect news impact
        assert signal.sentiment_score >= 0.9
        assert "news_event" in signal.reasoning or "announcement" in signal.reasoning

    @pytest.mark.asyncio
    async def test_market_stress_conditions(self, signal_generator, sample_market_data):
        """Test signal generation during market stress."""
        # Setup stress conditions
        signal_generator.regime_detector.detect_regime.return_value = {
            "regime": "crisis",
            "confidence": 0.9,
            "volatility_cluster": "extreme",
        }
        signal_generator.sentiment_analyzer.analyze_market_sentiment.return_value = {
            "sentiment_score": 0.1,
            "confidence": 0.8,  # Panic sentiment
        }

        signal = await signal_generator.generate_integrated_signal(sample_market_data)

        # Should have high risk score and conservative positioning
        assert signal.risk_score >= 0.8
        assert signal.position_size_multiplier <= 0.3
        assert "high_risk" in signal.reasoning or "stress" in signal.reasoning
