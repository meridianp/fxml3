"""
TDD Tests for ML Pipeline Integration

Comprehensive test suite for ML pipeline components including
feature extraction, model predictions, and signal generation.
"""

import numpy as np
import pandas as pd
import pytest
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, List, Any
from unittest.mock import Mock, AsyncMock, patch


@pytest.mark.tdd
@pytest.mark.red
class TestMLPipeline:
    """Test suite for ML pipeline integration with trading system."""

    @pytest.fixture
    def sample_market_data(self):
        """Generate sample market data for testing."""
        dates = pd.date_range(start="2024-01-01", periods=100, freq="1h")

        data = pd.DataFrame(
            {
                "timestamp": dates,
                "open": np.random.uniform(1.08, 1.10, 100),
                "high": np.random.uniform(1.09, 1.11, 100),
                "low": np.random.uniform(1.07, 1.09, 100),
                "close": np.random.uniform(1.08, 1.10, 100),
                "volume": np.random.randint(1000, 10000, 100),
                "symbol": "EUR/USD",
            }
        )

        # Ensure high > low and high >= close, open
        data["high"] = data[["open", "close", "high"]].max(axis=1) + 0.0001
        data["low"] = data[["open", "close", "low"]].min(axis=1) - 0.0001

        return data

    @pytest.fixture
    def ml_config(self):
        """ML pipeline configuration."""
        return {
            "models": ["random_forest", "xgboost", "lstm"],
            "features": ["sma", "rsi", "macd", "volume_profile"],
            "lookback_period": 50,
            "prediction_horizon": 5,
            "confidence_threshold": 0.65,
            "ensemble_method": "weighted_average",
        }

    # -------------------------------------------------------------------------
    # Feature Extraction Tests
    # -------------------------------------------------------------------------

    @pytest.mark.red
    def test_feature_extractor_initialization(self, ml_config):
        """RED: Test feature extractor initialization."""
        from core.ml.feature_extractor import FeatureExtractor

        extractor = FeatureExtractor(config=ml_config)

        assert extractor.features == ml_config["features"]
        assert extractor.lookback_period == ml_config["lookback_period"]
        assert extractor.is_fitted is False

    @pytest.mark.red
    def test_extract_technical_features(self, sample_market_data):
        """RED: Test extraction of technical indicator features."""
        from core.ml.feature_extractor import FeatureExtractor

        extractor = FeatureExtractor()
        features = extractor.extract_technical_features(sample_market_data)

        assert "sma_20" in features.columns
        assert "rsi_14" in features.columns
        assert "macd_signal" in features.columns
        assert len(features) == len(sample_market_data)

    @pytest.mark.red
    def test_extract_price_patterns(self, sample_market_data):
        """RED: Test extraction of price pattern features."""
        from core.ml.feature_extractor import FeatureExtractor

        extractor = FeatureExtractor()
        patterns = extractor.extract_price_patterns(sample_market_data)

        assert "bullish_engulfing" in patterns
        assert "bearish_engulfing" in patterns
        assert "doji" in patterns
        assert all(isinstance(v, bool) or v in [0, 1] for v in patterns.values())

    @pytest.mark.red
    def test_extract_market_microstructure(self, sample_market_data):
        """RED: Test extraction of market microstructure features."""
        from core.ml.feature_extractor import FeatureExtractor

        extractor = FeatureExtractor()
        microstructure = extractor.extract_microstructure_features(sample_market_data)

        assert "bid_ask_spread" in microstructure
        assert "order_flow_imbalance" in microstructure
        assert "volume_weighted_price" in microstructure

    @pytest.mark.red
    def test_feature_normalization(self, sample_market_data):
        """RED: Test feature normalization and scaling."""
        from core.ml.feature_extractor import FeatureExtractor

        extractor = FeatureExtractor()
        features = extractor.extract_technical_features(sample_market_data)
        normalized = extractor.normalize_features(features)

        # Check normalization
        assert normalized.max().max() <= 1.0
        assert normalized.min().min() >= -1.0
        assert normalized.shape == features.shape

    # -------------------------------------------------------------------------
    # Model Prediction Tests
    # -------------------------------------------------------------------------

    @pytest.mark.red
    def test_model_predictor_initialization(self, ml_config):
        """RED: Test model predictor initialization."""
        from core.ml.model_predictor import ModelPredictor

        predictor = ModelPredictor(config=ml_config)

        assert predictor.models == ml_config["models"]
        assert predictor.prediction_horizon == ml_config["prediction_horizon"]
        assert predictor.ensemble_method == ml_config["ensemble_method"]

    @pytest.mark.red
    def test_load_pretrained_models(self):
        """RED: Test loading of pre-trained models."""
        from core.ml.model_predictor import ModelPredictor

        predictor = ModelPredictor()
        models = predictor.load_models()

        assert "random_forest" in models
        assert "xgboost" in models
        assert all(hasattr(model, "predict") for model in models.values())

    @pytest.mark.red
    def test_single_model_prediction(self, sample_market_data):
        """RED: Test prediction from a single model."""
        from core.ml.model_predictor import ModelPredictor

        predictor = ModelPredictor()
        features = np.random.randn(1, 50)  # Mock features

        prediction = predictor.predict_single_model("random_forest", features)

        assert "signal" in prediction
        assert prediction["signal"] in ["BUY", "SELL", "HOLD"]
        assert "confidence" in prediction
        assert 0 <= prediction["confidence"] <= 1

    @pytest.mark.red
    def test_ensemble_prediction(self, sample_market_data):
        """RED: Test ensemble model predictions."""
        from core.ml.model_predictor import ModelPredictor

        predictor = ModelPredictor()
        features = np.random.randn(1, 50)

        ensemble_pred = predictor.predict_ensemble(features)

        assert "signal" in ensemble_pred
        assert "confidence" in ensemble_pred
        assert "model_predictions" in ensemble_pred
        assert len(ensemble_pred["model_predictions"]) >= 2

    @pytest.mark.red
    def test_prediction_with_uncertainty(self, sample_market_data):
        """RED: Test prediction with uncertainty quantification."""
        from core.ml.model_predictor import ModelPredictor

        predictor = ModelPredictor()
        features = np.random.randn(1, 50)

        prediction = predictor.predict_with_uncertainty(features)

        assert "signal" in prediction
        assert "confidence" in prediction
        assert "uncertainty" in prediction
        assert "confidence_interval" in prediction

    # -------------------------------------------------------------------------
    # Signal Generation Tests
    # -------------------------------------------------------------------------

    @pytest.mark.red
    def test_signal_generator_initialization(self, ml_config):
        """RED: Test signal generator initialization."""
        from core.ml.signal_generator import SignalGenerator

        generator = SignalGenerator(config=ml_config)

        assert generator.confidence_threshold == ml_config["confidence_threshold"]
        assert generator.active_signals == {}

    @pytest.mark.red
    def test_generate_trading_signal(self, sample_market_data):
        """RED: Test trading signal generation from ML predictions."""
        from core.ml.signal_generator import SignalGenerator

        generator = SignalGenerator()

        prediction = {"signal": "BUY", "confidence": 0.75, "price": 1.0850}

        signal = generator.generate_signal(
            symbol="EUR/USD", prediction=prediction, current_price=1.0850
        )

        assert signal["symbol"] == "EUR/USD"
        assert signal["action"] == "BUY"
        assert signal["confidence"] == 0.75
        assert "timestamp" in signal
        assert "metadata" in signal

    @pytest.mark.red
    def test_signal_filtering(self):
        """RED: Test signal filtering based on confidence."""
        from core.ml.signal_generator import SignalGenerator

        generator = SignalGenerator(confidence_threshold=0.7)

        # Low confidence signal should be filtered
        low_conf = {"signal": "BUY", "confidence": 0.5}
        filtered = generator.filter_signal(low_conf)
        assert filtered is None

        # High confidence signal should pass
        high_conf = {"signal": "SELL", "confidence": 0.8}
        passed = generator.filter_signal(high_conf)
        assert passed is not None

    @pytest.mark.red
    def test_signal_risk_adjustment(self):
        """RED: Test risk-adjusted signal generation."""
        from core.ml.signal_generator import SignalGenerator

        generator = SignalGenerator()

        signal = {"action": "BUY", "confidence": 0.8, "price": 1.0850}

        risk_metrics = {
            "portfolio_var": 0.02,
            "max_drawdown": 0.05,
            "sharpe_ratio": 1.5,
        }

        adjusted = generator.apply_risk_adjustment(signal, risk_metrics)

        assert "position_size" in adjusted
        assert "stop_loss" in adjusted
        assert "take_profit" in adjusted
        assert adjusted["position_size"] > 0

    # -------------------------------------------------------------------------
    # Integration Tests
    # -------------------------------------------------------------------------

    @pytest.mark.red
    @pytest.mark.asyncio
    async def test_ml_pipeline_integration(self, sample_market_data):
        """RED: Test complete ML pipeline integration."""
        from core.ml.ml_trading_pipeline import MLTradingPipeline

        pipeline = MLTradingPipeline()

        # Process market data through pipeline
        signal = await pipeline.process_market_data(sample_market_data)

        assert signal is not None
        assert "symbol" in signal
        assert "action" in signal
        assert "confidence" in signal
        assert "features" in signal
        assert "models_used" in signal

    @pytest.mark.red
    @pytest.mark.asyncio
    async def test_ml_websocket_integration(self):
        """RED: Test ML integration with WebSocket service."""
        from core.ml.ml_trading_pipeline import MLTradingPipeline
        from core.services.websocket_service import WebSocketServer

        pipeline = MLTradingPipeline()
        ws_server = WebSocketServer()

        # Connect pipeline to WebSocket
        pipeline.connect_websocket(ws_server)

        # Generate signal
        signal = {"symbol": "EUR/USD", "action": "BUY", "confidence": 0.75}

        # Broadcast signal
        await pipeline.broadcast_signal(signal)

        # Verify broadcast
        assert pipeline.websocket_connected is True

    @pytest.mark.red
    def test_ml_signal_aggregation(self):
        """RED: Test aggregation of multiple ML signals."""
        from core.ml.signal_aggregator import SignalAggregator

        aggregator = SignalAggregator()

        signals = [
            {"symbol": "EUR/USD", "action": "BUY", "confidence": 0.7},
            {"symbol": "EUR/USD", "action": "BUY", "confidence": 0.8},
            {"symbol": "EUR/USD", "action": "SELL", "confidence": 0.6},
        ]

        aggregated = aggregator.aggregate_signals(signals)

        assert aggregated["action"] == "BUY"  # Majority vote
        assert aggregated["confidence"] == pytest.approx(0.75, rel=0.1)
        assert aggregated["signal_count"] == 3

    @pytest.mark.red
    def test_ml_confidence_scoring(self):
        """RED: Test ML confidence score calculation."""
        from core.ml.confidence_scorer import ConfidenceScorer

        scorer = ConfidenceScorer()

        model_predictions = {
            "random_forest": {"signal": "BUY", "probability": 0.8},
            "xgboost": {"signal": "BUY", "probability": 0.75},
            "lstm": {"signal": "HOLD", "probability": 0.6},
        }

        confidence = scorer.calculate_confidence(model_predictions)

        assert 0 <= confidence <= 1
        assert confidence < 1.0  # Not unanimous
        assert "agreement_score" in scorer.get_details()
        assert "weighted_confidence" in scorer.get_details()

    # -------------------------------------------------------------------------
    # Performance and Monitoring Tests
    # -------------------------------------------------------------------------

    @pytest.mark.red
    def test_model_performance_tracking(self):
        """RED: Test ML model performance tracking."""
        from core.ml.performance_tracker import ModelPerformanceTracker

        tracker = ModelPerformanceTracker()

        # Add prediction
        tracker.add_prediction(
            model="random_forest", prediction="BUY", actual="BUY", confidence=0.75
        )

        # Get metrics
        metrics = tracker.get_model_metrics("random_forest")

        assert "accuracy" in metrics
        assert "precision" in metrics
        assert "recall" in metrics
        assert "f1_score" in metrics
        assert metrics["accuracy"] == 1.0  # Single correct prediction

    @pytest.mark.red
    def test_model_drift_detection(self):
        """RED: Test model drift detection."""
        from core.ml.drift_detector import ModelDriftDetector

        detector = ModelDriftDetector()

        # Historical predictions
        historical = np.random.randn(1000)

        # Current predictions (with drift)
        current = np.random.randn(100) + 0.5  # Shifted mean

        drift_detected = detector.detect_drift(historical, current)

        assert isinstance(drift_detected, bool)
        assert "p_value" in detector.get_statistics()
        assert "drift_score" in detector.get_statistics()

    @pytest.mark.red
    @pytest.mark.asyncio
    async def test_ml_pipeline_performance(self, sample_market_data, performance_timer):
        """RED: Test ML pipeline performance requirements."""
        from core.ml.ml_trading_pipeline import MLTradingPipeline

        pipeline = MLTradingPipeline()

        performance_timer.start()
        signal = await pipeline.process_market_data(sample_market_data)
        elapsed = performance_timer.stop()

        assert elapsed < 0.1  # Should process in under 100ms
        assert signal is not None

    @pytest.mark.red
    def test_ml_model_versioning(self):
        """RED: Test ML model versioning and rollback."""
        from core.ml.model_manager import ModelManager

        manager = ModelManager()

        # Save model version
        model_id = manager.save_model(
            model_name="random_forest",
            model_object=Mock(),
            version="1.0.0",
            metrics={"accuracy": 0.85},
        )

        assert model_id is not None

        # Load specific version
        loaded = manager.load_model("random_forest", version="1.0.0")
        assert loaded is not None

        # Rollback to previous version
        success = manager.rollback_model("random_forest", version="0.9.0")
        assert isinstance(success, bool)
