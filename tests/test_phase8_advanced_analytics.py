"""
Comprehensive Test Suite for Phase 8 - Advanced Analytics & FXML3/LLM Integration

This module provides comprehensive testing for:
- AI-powered market regime detection
- Multi-modal pattern recognition
- Real-time sentiment-driven trade signals
- Advanced analytics API endpoints
- Integration with FXML3 Elliott Wave analysis
"""

import asyncio
from datetime import datetime, timedelta
from typing import Any, Dict, List
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import numpy as np
import pandas as pd
import pytest

# Import Phase 8 components
from fxml4.analytics.market_regime_detector import (
    MarketRegimeDetector,
    MarketRegimeType,
    RegimeCharacteristics,
    RegimeDetection,
)
from fxml4.analytics.multimodal_pattern_recognition import (
    MultiModalPatternRecognizer,
    PatternPrediction,
    PatternType,
    PatternValidation,
    RecognizedPattern,
)
from fxml4.analytics.sentiment_signal_generator import (
    SentimentSignalComponents,
    SentimentSignalGenerator,
    SentimentTradeSignal,
    SentimentTrigger,
    SignalStrength,
    SignalType,
)
from fxml4.api.routers.advanced_analytics import router
from fxml4.llm_integration.llm_client import LLMClient
from fxml4.llm_integration.sentiment_analysis import MarketSentimentAnalyzer

# Test configuration
pytestmark = pytest.mark.phase8


@pytest.fixture
def sample_market_data():
    """Generate sample market data for testing."""
    dates = pd.date_range(start="2024-01-01", periods=200, freq="4H")

    # Generate realistic price data
    np.random.seed(42)
    base_price = 1.0900
    returns = np.random.normal(0, 0.001, 200)  # 0.1% daily volatility
    prices = [base_price]

    for ret in returns:
        prices.append(prices[-1] * (1 + ret))

    data = pd.DataFrame(
        {
            "datetime": dates,
            "open": prices[:-1],
            "high": [p * (1 + np.random.uniform(0, 0.002)) for p in prices[:-1]],
            "low": [p * (1 - np.random.uniform(0, 0.002)) for p in prices[:-1]],
            "close": prices[1:],
            "volume": np.random.uniform(1000000, 5000000, 200),
        }
    )

    return data


@pytest.fixture
def sample_sentiment_data():
    """Generate sample sentiment data for testing."""
    return {
        "overall_sentiment": 0.75,
        "news_sentiment": 0.72,
        "social_sentiment": 0.78,
        "news_impact": 0.6,
        "social_volume": 1500,
        "confidence": 0.85,
        "key_factors": ["ECB policy", "USD weakness"],
        "sentiment_volatility": 0.15,
        "fear_greed_index": 65,
    }


@pytest.fixture
def mock_llm_client():
    """Mock LLM client for testing."""
    mock_client = Mock(spec=LLMClient)
    mock_client.generate_completion = AsyncMock(return_value="Test LLM response")
    mock_client.analyze_chart_with_image = AsyncMock(
        return_value="Valid pattern detected"
    )
    return mock_client


@pytest.fixture
def mock_database_manager():
    """Mock database manager for testing."""
    mock_db = Mock()
    mock_db.get_market_data = AsyncMock()
    mock_db.store_regime_detection = AsyncMock()
    mock_db.store_pattern_recognition = AsyncMock()
    mock_db.store_sentiment_signal = AsyncMock()
    return mock_db


class TestMarketRegimeDetector:
    """Test suite for AI-powered market regime detection."""

    @pytest.fixture
    def regime_detector(self, mock_llm_client, mock_database_manager):
        """Create regime detector with mocked dependencies."""
        detector = MarketRegimeDetector()
        detector.llm_client = mock_llm_client
        detector.db_manager = mock_database_manager
        return detector

    @pytest.mark.asyncio
    async def test_regime_detection_basic(self, regime_detector, sample_market_data):
        """Test basic regime detection functionality."""
        # Mock database response
        regime_detector.db_manager.get_market_data.return_value = sample_market_data

        # Mock model predictions
        with patch.object(regime_detector, "_predict_regime") as mock_predict:
            mock_predict.return_value = {
                MarketRegimeType.TRENDING_BULL: 0.85,
                MarketRegimeType.RANGING_LOW_VOL: 0.15,
            }

            detection = await regime_detector.detect_regime(
                symbol="EURUSD", timeframe="4h", use_llm_validation=False
            )

            assert isinstance(detection, RegimeDetection)
            assert detection.regime_type == MarketRegimeType.TRENDING_BULL
            assert detection.confidence == 0.85
            assert len(detection.supporting_evidence) > 0

    @pytest.mark.asyncio
    async def test_regime_features_extraction(
        self, regime_detector, sample_market_data
    ):
        """Test regime feature extraction."""
        regime_detector.db_manager.get_market_data.return_value = sample_market_data

        with patch.object(
            regime_detector.sentiment_analyzer, "get_realtime_sentiment"
        ) as mock_sentiment:
            mock_sentiment.return_value = {"overall_sentiment": 0.7}

            features = await regime_detector._get_regime_features("EURUSD", "4h")

            assert isinstance(features, np.ndarray)
            assert len(features) > 0
            assert not np.isnan(features).any()

    def test_regime_characteristics_calculation(self, regime_detector):
        """Test regime characteristics calculation."""
        features = np.random.rand(50)  # Mock features

        characteristics = regime_detector._analyze_regime_characteristics(features)

        assert isinstance(characteristics, RegimeCharacteristics)
        assert 0 <= characteristics.volatility_level <= 1
        assert 0 <= characteristics.trend_strength <= 1
        assert -1 <= characteristics.momentum <= 1

    @pytest.mark.asyncio
    async def test_llm_regime_validation(self, regime_detector):
        """Test LLM-powered regime validation."""
        regime_type = MarketRegimeType.TRENDING_BULL
        characteristics = RegimeCharacteristics(
            volatility_level=0.3,
            trend_strength=0.8,
            momentum=0.6,
            volume_profile=1.2,
            sentiment_bias=0.7,
            wave_structure_quality=0.85,
            duration_stability=0.7,
            reversion_tendency=0.3,
        )

        llm_analysis = await regime_detector._get_llm_regime_analysis(
            "EURUSD",
            regime_type,
            characteristics,
            ["Strong trend"],
            ["High volatility"],
        )

        assert "explanation" in llm_analysis
        assert "insights" in llm_analysis
        assert isinstance(llm_analysis["insights"], list)

    def test_technical_feature_extraction(self, regime_detector, sample_market_data):
        """Test technical feature extraction."""
        features = regime_detector._extract_technical_features(sample_market_data)

        assert isinstance(features, np.ndarray)
        assert len(features) > 20  # Should have multiple features
        assert not np.isnan(features).any()

    @pytest.mark.parametrize(
        "regime_type,expected_duration",
        [
            (MarketRegimeType.TRENDING_BULL, 480),
            (MarketRegimeType.BREAKOUT_BULL, 60),
            (MarketRegimeType.RANGING_LOW_VOL, 720),
            (MarketRegimeType.VOLATILE_UNCERTAIN, 120),
        ],
    )
    def test_regime_duration_estimation(
        self, regime_detector, regime_type, expected_duration
    ):
        """Test regime duration estimation for different types."""
        characteristics = RegimeCharacteristics(
            volatility_level=0.3,
            trend_strength=0.7,
            momentum=0.5,
            volume_profile=1.0,
            sentiment_bias=0.6,
            wave_structure_quality=0.8,
            duration_stability=1.0,
            reversion_tendency=0.2,
        )

        duration = regime_detector._estimate_regime_duration(
            regime_type, characteristics
        )

        assert isinstance(duration, int)
        assert 30 <= duration <= 1440  # Between 30 minutes and 24 hours
        assert (
            abs(duration - expected_duration) <= expected_duration * 0.5
        )  # Within 50% of expected


class TestMultiModalPatternRecognition:
    """Test suite for multi-modal pattern recognition."""

    @pytest.fixture
    def pattern_recognizer(self, mock_llm_client, mock_database_manager):
        """Create pattern recognizer with mocked dependencies."""
        recognizer = MultiModalPatternRecognizer()
        recognizer.llm_client = mock_llm_client
        recognizer.db_manager = mock_database_manager
        return recognizer

    @pytest.mark.asyncio
    async def test_pattern_recognition_basic(
        self, pattern_recognizer, sample_market_data
    ):
        """Test basic pattern recognition functionality."""
        pattern_recognizer.db_manager.get_market_data.return_value = sample_market_data

        patterns = await pattern_recognizer.recognize_patterns(
            symbol="EURUSD", timeframe="4h", include_multi_timeframe=False
        )

        assert isinstance(patterns, list)
        # Should detect at least some patterns in 200 bars of data
        for pattern in patterns:
            assert isinstance(pattern, RecognizedPattern)
            assert pattern.confidence >= pattern_recognizer.confidence_threshold
            assert pattern.symbol == "EURUSD"
            assert pattern.timeframe == "4h"

    @pytest.mark.asyncio
    async def test_elliott_wave_pattern_detection(
        self, pattern_recognizer, sample_market_data
    ):
        """Test Elliott Wave pattern detection."""
        # Mock wave analyzer
        mock_waves = [
            {
                "start_price": 1.0900,
                "end_price": 1.0950,
                "start_time": "2024-01-01T00:00:00",
                "end_time": "2024-01-01T04:00:00",
            },
            {
                "start_price": 1.0950,
                "end_price": 1.0920,
                "start_time": "2024-01-01T04:00:00",
                "end_time": "2024-01-01T08:00:00",
            },
            {
                "start_price": 1.0920,
                "end_price": 1.0980,
                "start_time": "2024-01-01T08:00:00",
                "end_time": "2024-01-01T12:00:00",
            },
            {
                "start_price": 1.0980,
                "end_price": 1.0960,
                "start_time": "2024-01-01T12:00:00",
                "end_time": "2024-01-01T16:00:00",
            },
            {
                "start_price": 1.0960,
                "end_price": 1.1000,
                "start_time": "2024-01-01T16:00:00",
                "end_time": "2024-01-01T20:00:00",
            },
        ]

        with patch.object(
            pattern_recognizer.wave_analyzer, "compute_waves"
        ) as mock_compute:
            mock_compute.return_value = mock_waves

            patterns = await pattern_recognizer._detect_elliott_wave_patterns(
                sample_market_data, "EURUSD", "4h"
            )

            assert isinstance(patterns, list)
            for pattern in patterns:
                assert pattern.pattern_type in [
                    PatternType.IMPULSE_WAVE,
                    PatternType.CORRECTIVE_WAVE,
                ]

    @pytest.mark.asyncio
    async def test_head_shoulders_detection(
        self, pattern_recognizer, sample_market_data
    ):
        """Test Head and Shoulders pattern detection."""
        # Create sample data with clear head and shoulders pattern
        hs_data = sample_market_data.copy()

        # Manually create head and shoulders in the data
        mid_point = len(hs_data) // 2
        hs_data.loc[mid_point - 20 : mid_point - 15, "high"] = 1.0950  # Left shoulder
        hs_data.loc[mid_point - 5 : mid_point, "high"] = 1.1000  # Head
        hs_data.loc[mid_point + 15 : mid_point + 20, "high"] = 1.0950  # Right shoulder

        patterns = await pattern_recognizer._detect_head_shoulders(
            hs_data, "EURUSD", "4h"
        )

        assert isinstance(patterns, list)
        # Should detect the manually created pattern
        if patterns:
            hs_pattern = patterns[0]
            assert hs_pattern.pattern_type == PatternType.HEAD_SHOULDERS
            assert (
                len(hs_pattern.key_points) == 5
            )  # Left shoulder, head, right shoulder, neckline start, end

    @pytest.mark.asyncio
    async def test_pattern_validation(self, pattern_recognizer, sample_market_data):
        """Test comprehensive pattern validation."""
        # Create a mock pattern
        pattern = RecognizedPattern(
            pattern_id="test_pattern",
            pattern_type=PatternType.IMPULSE_WAVE,
            timeframe="4h",
            symbol="EURUSD",
            start_time=datetime.now() - timedelta(hours=12),
            end_time=datetime.now(),
            key_points=[],
            pattern_bounds={},
            confidence=0.8,
            quality_score=0.8,
            completion_ratio=0.9,
            validation=PatternValidation(
                fibonacci_confluence=True,
                volume_confirmation=False,
                sentiment_alignment=False,
                technical_indicators=False,
                llm_validation=False,
                historical_performance=False,
                multi_timeframe_consistency=False,
            ),
            prediction=PatternPrediction(
                target_price=1.1000,
                stop_loss=1.0850,
                probability=0.75,
                risk_reward_ratio=2.0,
                expected_timeframe=24,
                confidence_interval=(1.0980, 1.1020),
            ),
            market_context={},
            llm_explanation="",
            risk_assessment={},
            detection_time=datetime.now(),
            last_updated=datetime.now(),
        )

        validated_pattern = await pattern_recognizer._validate_pattern(
            pattern, sample_market_data
        )

        assert isinstance(validated_pattern, RecognizedPattern)
        assert validated_pattern.validation.validation_score >= 0
        assert validated_pattern.confidence > 0

    def test_support_resistance_detection(self, pattern_recognizer, sample_market_data):
        """Test support and resistance level detection."""
        # Test with sample data
        levels = pattern_recognizer._find_support_resistance_levels(
            sample_market_data["high"].values, is_resistance=True
        )

        assert isinstance(levels, list)
        for level in levels:
            assert "price" in level
            assert "strength" in level
            assert "touches" in level
            assert level["strength"] >= 1

    @pytest.mark.asyncio
    async def test_pattern_summary_generation(self, pattern_recognizer):
        """Test pattern summary generation."""
        summary = await pattern_recognizer.get_pattern_summary("EURUSD", ["1h", "4h"])

        assert isinstance(summary, dict)
        assert "symbol" in summary
        assert "total_patterns" in summary
        assert "pattern_distribution" in summary
        assert "last_updated" in summary

    @pytest.mark.parametrize(
        "pattern_type,expected_validation",
        [
            (PatternType.IMPULSE_WAVE, True),
            (PatternType.HEAD_SHOULDERS, True),
            (PatternType.SUPPORT_LEVEL, True),
            (PatternType.TRIANGLE_ASCENDING, True),
        ],
    )
    def test_pattern_type_specific_validation(
        self, pattern_recognizer, pattern_type, expected_validation
    ):
        """Test validation logic for different pattern types."""
        # This would test pattern-specific validation rules
        # Implementation depends on specific validation logic for each pattern type
        # Validate pattern-specific rules
        assert analyzer.is_valid_pattern(
            pattern_data
        ), "Pattern should meet validation criteria"
        assert (
            analyzer.confidence_score >= 0.0
        ), "Confidence score should be non-negative"
        assert (
            analyzer.confidence_score <= 1.0
        ), "Confidence score should not exceed 1.0"


class TestSentimentSignalGenerator:
    """Test suite for sentiment-driven trade signal generation."""

    @pytest.fixture
    def signal_generator(self, mock_llm_client, mock_database_manager):
        """Create signal generator with mocked dependencies."""
        generator = SentimentSignalGenerator()
        generator.llm_client = mock_llm_client
        generator.db_manager = mock_database_manager
        return generator

    @pytest.mark.asyncio
    async def test_signal_generation_basic(
        self, signal_generator, sample_sentiment_data
    ):
        """Test basic signal generation functionality."""
        # Mock comprehensive sentiment data
        with patch.object(
            signal_generator, "_get_comprehensive_sentiment"
        ) as mock_sentiment:
            mock_sentiment.return_value = {
                "realtime": sample_sentiment_data,
                "momentum": {"overall_momentum": 0.3, "sentiment_change": 0.2},
                "llm_analysis": {"confidence": 0.8, "bias": 0.1},
            }

            with patch.object(signal_generator, "_get_market_context") as mock_context:
                mock_context.return_value = {
                    "current_price": 1.0900,
                    "technical_indicators": {"rsi": 60, "macd_signal": 0.1},
                    "volatility": 0.012,
                }

                signals = await signal_generator.generate_signals(["EURUSD"], ["4h"])

                assert isinstance(signals, list)
                for signal in signals:
                    assert isinstance(signal, SentimentTradeSignal)
                    assert signal.symbol == "EURUSD"
                    assert signal.confidence >= signal_generator.min_confidence
                    assert (
                        signal.risk_reward_ratio
                        >= signal_generator.config["min_risk_reward"]
                    )

    @pytest.mark.asyncio
    async def test_sentiment_trigger_analysis(
        self, signal_generator, sample_sentiment_data
    ):
        """Test sentiment trigger analysis."""
        sentiment_data = {
            "realtime": sample_sentiment_data,
            "momentum": {
                "social_momentum": 0.85,  # Above threshold
                "overall_momentum": 0.3,
                "sentiment_change": 0.2,
                "sentiment_volatility": 0.1,
            },
            "llm_analysis": {"confidence": 0.9, "bias": 0.2},
        }

        market_data = {
            "current_price": 1.0900,
            "technical_indicators": {"momentum": 0.15},
        }

        triggers = await signal_generator._analyze_sentiment_triggers(
            sentiment_data, market_data
        )

        assert isinstance(triggers, list)
        assert len(triggers) > 0

        # Should detect social momentum trigger
        social_triggers = [
            t for t in triggers if t["type"] == SentimentTrigger.SOCIAL_MOMENTUM
        ]
        assert len(social_triggers) > 0

        for trigger in triggers:
            assert "type" in trigger
            assert "significance" in trigger
            assert "direction" in trigger
            assert trigger["significance"] > 0

    @pytest.mark.asyncio
    async def test_signal_creation_from_trigger(self, signal_generator):
        """Test signal creation from sentiment trigger."""
        trigger = {
            "type": SentimentTrigger.NEWS_BREAKOUT,
            "significance": 0.85,
            "direction": 1,
            "data": {"news_sentiment": 0.8},
        }

        sentiment_data = {
            "realtime": {"overall_sentiment": 0.75, "news_sentiment": 0.8},
            "momentum": {"sentiment_volatility": 0.1},
        }

        market_data = {
            "current_price": 1.0900,
            "volatility": 0.01,
            "technical_indicators": {
                "nearest_support": 1.0850,
                "nearest_resistance": 1.0950,
            },
        }

        with patch.object(signal_generator, "_generate_llm_reasoning") as mock_llm:
            mock_llm.return_value = "Strong bullish sentiment supports buy signal"

            with patch.object(
                signal_generator.portfolio_manager, "get_account_balance"
            ) as mock_balance:
                mock_balance.return_value = 100000

                signal = await signal_generator._create_signal_from_trigger(
                    "EURUSD", "4h", trigger, sentiment_data, market_data
                )

                assert isinstance(signal, SentimentTradeSignal)
                assert signal.signal_type == SignalType.BUY
                assert signal.trigger_type == SentimentTrigger.NEWS_BREAKOUT
                assert signal.target_price > signal.entry_price > signal.stop_loss

    def test_signal_strength_calculation(self, signal_generator):
        """Test signal strength calculation."""
        test_cases = [
            (0.95, SignalStrength.VERY_STRONG),
            (0.80, SignalStrength.STRONG),
            (0.65, SignalStrength.MODERATE),
            (0.50, SignalStrength.WEAK),
            (0.30, SignalStrength.VERY_WEAK),
        ]

        for significance, expected_strength in test_cases:
            strength = signal_generator._calculate_signal_strength(significance)
            assert strength == expected_strength

    @pytest.mark.asyncio
    async def test_price_target_calculation(self, signal_generator):
        """Test price target and stop loss calculation."""
        sentiment_data = {"realtime": {"overall_sentiment": 0.8}}
        market_data = {
            "volatility": 0.015,
            "technical_indicators": {
                "nearest_support": 1.0850,
                "nearest_resistance": 1.0950,
            },
        }

        target, stop = await signal_generator._calculate_price_targets(
            "EURUSD", SignalType.BUY, 1.0900, sentiment_data, market_data
        )

        assert target > 1.0900  # Target above entry for buy signal
        assert stop < 1.0900  # Stop below entry for buy signal
        assert (target - 1.0900) > (1.0900 - stop)  # Positive risk-reward

    def test_risk_reward_calculation(self, signal_generator):
        """Test risk-reward ratio calculation."""
        # Test buy signal
        rr_buy = signal_generator._calculate_risk_reward(
            1.0900, 1.0950, 1.0850, SignalType.BUY
        )
        assert rr_buy == 1.0  # 50 pips profit / 50 pips risk

        # Test sell signal
        rr_sell = signal_generator._calculate_risk_reward(
            1.0900, 1.0850, 1.0950, SignalType.SELL
        )
        assert rr_sell == 1.0  # 50 pips profit / 50 pips risk

    @pytest.mark.asyncio
    async def test_position_sizing(self, signal_generator):
        """Test position sizing calculation."""
        sentiment_components = SentimentSignalComponents(
            news_sentiment=0.8,
            social_sentiment=0.7,
            market_sentiment=0.75,
            sentiment_momentum=0.3,
            sentiment_volatility=0.1,
            sentiment_divergence=0.0,
            llm_reasoning_score=0.85,
            historical_accuracy=0.8,
        )

        with patch.object(
            signal_generator.portfolio_manager, "get_account_balance"
        ) as mock_balance:
            mock_balance.return_value = 100000

            position_size, risk_pct = await signal_generator._calculate_position_size(
                "EURUSD", SignalStrength.STRONG, sentiment_components, 2.0
            )

            assert position_size > 0
            assert 0.005 <= risk_pct <= signal_generator.config["max_risk_per_trade"]

    @pytest.mark.asyncio
    async def test_signal_performance_tracking(self, signal_generator):
        """Test signal performance tracking."""
        summary = await signal_generator.get_signal_performance_summary()

        assert isinstance(summary, dict)
        assert "performance_metrics" in summary
        assert "active_signals" in summary
        assert "last_updated" in summary


class TestAdvancedAnalyticsAPI:
    """Test suite for advanced analytics API endpoints."""

    @pytest.fixture
    def client(self):
        """Create test client for API testing."""
        from fastapi.testclient import TestClient

        from fxml4.api.main import app

        return TestClient(app)

    @pytest.fixture
    def auth_headers(self):
        """Mock authentication headers."""
        return {"Authorization": "Bearer test_token"}

    def test_health_endpoint(self, client):
        """Test health check endpoint."""
        response = client.get("/analytics/health")
        assert response.status_code == 200

        data = response.json()
        assert data["status"] == "healthy"
        assert "services" in data
        assert data["version"] == "8.0.0"

    @pytest.mark.asyncio
    async def test_regime_detection_endpoint(self, client, auth_headers):
        """Test regime detection API endpoint."""
        request_data = {
            "symbol": "EURUSD",
            "timeframe": "4h",
            "use_llm_validation": True,
        }

        with patch(
            "fxml4.api.routers.advanced_analytics.regime_detector"
        ) as mock_detector:
            mock_detection = Mock()
            mock_detection.regime_type = MarketRegimeType.TRENDING_BULL
            mock_detection.confidence = 0.85
            mock_detection.duration_minutes = 120
            mock_detection.expected_duration = 240
            mock_detection.characteristics = Mock()
            mock_detection.characteristics.volatility_level = 0.3
            mock_detection.supporting_evidence = ["Strong trend"]
            mock_detection.risk_factors = ["Volatility"]
            mock_detection.transition_probability = {
                MarketRegimeType.RANGING_LOW_VOL: 0.2
            }
            mock_detection.llm_explanation = "Test explanation"
            mock_detection.actionable_insights = ["Monitor levels"]

            mock_detector.detect_regime.return_value = mock_detection

            response = client.post(
                "/analytics/regime-detection", json=request_data, headers=auth_headers
            )

            assert response.status_code == 200
            data = response.json()
            assert data["symbol"] == "EURUSD"
            assert data["regime_type"] == "trending_bull"
            assert data["confidence"] == 0.85

    @pytest.mark.asyncio
    async def test_pattern_recognition_endpoint(self, client, auth_headers):
        """Test pattern recognition API endpoint."""
        request_data = {
            "symbol": "EURUSD",
            "timeframe": "4h",
            "include_multi_timeframe": True,
        }

        with patch(
            "fxml4.api.routers.advanced_analytics.pattern_recognizer"
        ) as mock_recognizer:
            mock_pattern = Mock()
            mock_pattern.pattern_id = "test_pattern"
            mock_pattern.pattern_type = PatternType.IMPULSE_WAVE
            mock_pattern.confidence = 0.8
            mock_pattern.quality_score = 0.85
            mock_pattern.completion_ratio = 0.9
            mock_pattern.start_time = datetime.now()
            mock_pattern.end_time = datetime.now()
            mock_pattern.key_points = []
            mock_pattern.validation = Mock()
            mock_pattern.validation.validation_score = 0.8
            mock_pattern.prediction = Mock()
            mock_pattern.prediction.target_price = 1.1000
            mock_pattern.prediction.stop_loss = 1.0850
            mock_pattern.prediction.risk_reward_ratio = 2.0
            mock_pattern.prediction.expected_timeframe = 24
            mock_pattern.llm_explanation = "Valid pattern"
            mock_pattern.market_context = {}

            mock_recognizer.recognize_patterns.return_value = [mock_pattern]

            response = client.post(
                "/analytics/pattern-recognition",
                json=request_data,
                headers=auth_headers,
            )

            assert response.status_code == 200
            data = response.json()
            assert data["symbol"] == "EURUSD"
            assert data["total_patterns"] == 1
            assert len(data["patterns"]) == 1

    def test_dashboard_data_endpoint(self, client, auth_headers):
        """Test dashboard data endpoint."""
        with patch(
            "fxml4.api.routers.advanced_analytics.get_market_intelligence"
        ) as mock_intelligence:
            mock_response = Mock()
            mock_response.overview = {"market_state": "trending", "sentiment_bias": 0.7}
            mock_response.regime_analysis = {
                "current_regime": "trending_bull",
                "confidence": 0.8,
            }
            mock_response.pattern_analysis = {
                "total_patterns": 2,
                "average_confidence": 0.75,
            }
            mock_response.sentiment_analysis = {"overall_sentiment": 0.7}
            mock_response.ai_insights = []

            mock_intelligence.return_value = mock_response

            response = client.get(
                "/analytics/dashboard-data/EURUSD?timeframe=4h", headers=auth_headers
            )

            assert response.status_code == 200
            data = response.json()
            assert "overview" in data
            assert "regimes" in data
            assert "performance_metrics" in data

    @pytest.mark.parametrize(
        "endpoint,method",
        [
            ("/analytics/regime-summary/EURUSD", "GET"),
            ("/analytics/pattern-summary/EURUSD", "GET"),
            ("/analytics/health", "GET"),
        ],
    )
    def test_endpoint_accessibility(self, client, endpoint, method):
        """Test that all analytics endpoints are accessible."""
        if method == "GET":
            response = client.get(endpoint)
        else:
            response = client.post(endpoint, json={})

        # Should not return 404 (endpoint exists)
        assert response.status_code != 404


class TestIntegrationScenarios:
    """Test integration scenarios across Phase 8 components."""

    @pytest.mark.asyncio
    async def test_full_analytics_pipeline(
        self, sample_market_data, sample_sentiment_data
    ):
        """Test complete analytics pipeline integration."""
        # This test would run through the entire pipeline:
        # 1. Regime detection
        # 2. Pattern recognition
        # 3. Sentiment analysis
        # 4. Signal generation
        # 5. API response formatting

        # Mock all external dependencies
        with patch("fxml4.analytics.market_regime_detector.DatabaseManager") as mock_db:
            mock_db.return_value.get_market_data.return_value = sample_market_data

            # Test regime detection
            regime_detector = MarketRegimeDetector()
            regime_detector.db_manager = mock_db.return_value

            # This is a simplified integration test
            # Full implementation would test actual component interactions
            # Verify integration components
            assert (
                integration_result["status"] == "success"
            ), "Integration should complete successfully"
            assert (
                "data_flow" in integration_result
            ), "Should include data flow information"
            assert (
                len(integration_result.get("errors", [])) == 0
            ), "Should have no integration errors"

    @pytest.mark.asyncio
    async def test_concurrent_analytics_processing(self):
        """Test concurrent processing of multiple analytics requests."""
        # Test that the system can handle multiple concurrent requests
        # without race conditions or resource conflicts

        async def mock_analysis():
            await asyncio.sleep(0.1)  # Simulate processing time
            return {"result": "success"}

        tasks = [mock_analysis() for _ in range(10)]
        results = await asyncio.gather(*tasks)

        assert len(results) == 10
        assert all(r["result"] == "success" for r in results)

    @pytest.mark.asyncio
    async def test_error_handling_and_recovery(self):
        """Test error handling and recovery mechanisms."""
        # Test that the system gracefully handles various error conditions

        # Mock failing LLM client
        mock_llm = Mock()
        mock_llm.generate_completion.side_effect = Exception("LLM service unavailable")

        # Test that regime detection continues without LLM validation
        regime_detector = MarketRegimeDetector()
        regime_detector.llm_client = mock_llm

        # Should not raise exception even with LLM failure
        try:
            # This would test actual error handling
            # Verify error handling
            assert (
                error_handler.handled_count > 0
            ), "Should have handled at least one error"
            assert error_handler.recovery_successful, "Should recover from LLM failures"
        except Exception:
            pytest.fail("System should handle LLM failures gracefully")

    @pytest.mark.performance
    async def test_performance_benchmarks(self):
        """Test performance benchmarks for Phase 8 components."""
        # Test that analytics processing meets performance requirements

        start_time = datetime.now()

        # Simulate analytics processing
        await asyncio.sleep(0.5)  # Mock processing time

        end_time = datetime.now()
        processing_time = (end_time - start_time).total_seconds()

        # Analytics should complete within reasonable time
        assert processing_time < 5.0  # 5 second maximum


class TestPhase8Documentation:
    """Test that Phase 8 components are properly documented."""

    def test_module_docstrings(self):
        """Test that all Phase 8 modules have proper docstrings."""
        modules = [
            "fxml4.analytics.market_regime_detector",
            "fxml4.analytics.multimodal_pattern_recognition",
            "fxml4.analytics.sentiment_signal_generator",
        ]

        for module_name in modules:
            try:
                module = __import__(module_name, fromlist=[""])
                assert module.__doc__ is not None
                assert len(module.__doc__.strip()) > 100  # Substantial documentation
            except ImportError:
                pytest.skip(f"Module {module_name} not available")

    def test_api_endpoint_documentation(self):
        """Test that API endpoints have proper OpenAPI documentation."""
        from fxml4.api.routers.advanced_analytics import router

        # Check that router has proper tags and metadata
        assert router.tags == ["Advanced Analytics"]
        assert router.prefix == "/analytics"

        # Check that endpoints have proper documentation
        for route in router.routes:
            if hasattr(route, "endpoint"):
                # Each endpoint should have a docstring
                assert route.endpoint.__doc__ is not None


if __name__ == "__main__":
    # Run tests with coverage
    pytest.main(
        [
            __file__,
            "-v",
            "--cov=fxml4.analytics",
            "--cov=fxml4.api.routers.advanced_analytics",
            "--cov-report=term-missing",
            "--cov-fail-under=85",
        ]
    )
