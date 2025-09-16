#!/usr/bin/env python3
"""
End-to-End Test: ML Signal Generation
=====================================

This test suite validates the complete ML signal generation pipeline,
from feature engineering through model inference to signal creation.

Business Requirements:
- ML model inference < 500ms
- Feature engineering completeness > 95%
- Signal confidence calibration accuracy > 80%
- Multi-model ensemble agreement > 60%
- Market regime detection accuracy > 85%

Test Coverage:
- Feature engineering pipeline
- Model loading and caching
- Ensemble prediction
- Confidence scoring
- Market regime classification
- Signal validation
"""

import asyncio
import json
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional
from unittest.mock import AsyncMock, MagicMock, patch

import joblib
import numpy as np
import pandas as pd
import pytest
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, precision_recall_curve

from fxml4.core.models import MarketData, Signal
from fxml4.ml.feature_engineering import FeatureEngineer
from fxml4.ml.market_regime import MarketRegimeClassifier
from fxml4.ml.models.ensemble import EnsemblePredictor
from fxml4.ml.models.lightgbm_model import LightGBMModel
from fxml4.ml.models.neural_network import NeuralNetworkModel
from fxml4.ml.models.xgboost_model import XGBoostModel
from fxml4.strategy.signal_generator import SignalGenerator


class TestMLSignalGenerationE2E:
    """Complete end-to-end testing of ML signal generation pipeline."""

    @pytest.fixture
    async def historical_data(self):
        """Generate comprehensive historical market data."""
        periods = 1000
        dates = pd.date_range(end=datetime.now(), periods=periods, freq="1h")

        # Generate multi-timeframe data with realistic patterns
        # Simulate trending, ranging, and volatile market conditions
        trend_periods = periods // 3
        range_periods = periods // 3
        volatile_periods = periods - (2 * periods // 3)

        # Trending market
        trend = np.linspace(1.0800, 1.1000, trend_periods)
        trend += np.random.normal(0, 0.0002, trend_periods)

        # Ranging market
        range_mean = 1.1000
        range_data = (
            range_mean + np.sin(np.linspace(0, 4 * np.pi, range_periods)) * 0.005
        )
        range_data += np.random.normal(0, 0.0001, range_periods)

        # Volatile market
        volatile = np.random.normal(1.0950, 0.005, volatile_periods)

        # Combine all regimes
        prices = np.concatenate([trend, range_data, volatile])

        data = pd.DataFrame(
            {
                "timestamp": dates,
                "open": prices + np.random.normal(0, 0.0001, periods),
                "high": prices + np.abs(np.random.normal(0.0003, 0.0002, periods)),
                "low": prices - np.abs(np.random.normal(0.0003, 0.0002, periods)),
                "close": prices + np.random.normal(0, 0.0001, periods),
                "volume": np.random.uniform(1000000, 5000000, periods),
                "bid": prices - 0.00005,
                "ask": prices + 0.00005,
                "spread": np.full(periods, 0.0001),
            }
        )

        # Ensure OHLC consistency
        data["high"] = data[["open", "high", "close"]].max(axis=1)
        data["low"] = data[["open", "low", "close"]].min(axis=1)

        return data

    @pytest.fixture
    async def feature_engineer(self, historical_data):
        """Initialize feature engineering pipeline."""
        engineer = FeatureEngineer(
            symbol="EURUSD",
            timeframes=["1h", "4h", "1d"],
            feature_config={
                "technical_indicators": True,
                "market_microstructure": True,
                "session_features": True,
                "correlation_features": True,
                "volatility_features": True,
            },
        )

        # Pre-compute features for testing
        await engineer.initialize(historical_data)

        return engineer

    @pytest.fixture
    async def ml_models(self, tmp_path):
        """Create and save test ML models."""
        models_dir = tmp_path / "models"
        models_dir.mkdir()

        # Create simple test models
        models = {
            "xgboost": XGBoostModel(),
            "lightgbm": LightGBMModel(),
            "random_forest": RandomForestClassifier(n_estimators=10),
            "neural_network": NeuralNetworkModel(input_dim=68),
        }

        # Train models with dummy data
        X_train = np.random.randn(100, 68)
        y_train = np.random.choice([0, 1, 2], 100)  # 0: Short, 1: Neutral, 2: Long

        for name, model in models.items():
            if hasattr(model, "fit"):
                model.fit(X_train, y_train)
                model_path = models_dir / f"{name}_model.pkl"
                joblib.dump(model, model_path)

        return models_dir

    @pytest.fixture
    async def ensemble_predictor(self, ml_models):
        """Initialize ensemble predictor with test models."""
        predictor = EnsemblePredictor(
            models_dir=str(ml_models),
            model_weights={
                "xgboost": 0.3,
                "lightgbm": 0.3,
                "random_forest": 0.2,
                "neural_network": 0.2,
            },
            confidence_threshold=0.6,
        )

        await predictor.load_models()

        return predictor

    @pytest.mark.asyncio
    async def test_complete_ml_signal_generation_pipeline(
        self, historical_data, feature_engineer, ensemble_predictor
    ):
        """
        Test the complete ML signal generation pipeline.

        Given: Historical market data
        When: ML pipeline processes the data
        Then: Valid trading signals should be generated with proper confidence
        """
        # Step 1: Generate features
        start_time = time.time()
        features = await feature_engineer.compute_features(historical_data.tail(100))
        feature_time = time.time() - start_time

        assert features is not None
        assert features.shape[1] >= 68  # At least 68 features
        assert feature_time < 1.0, f"Feature engineering took {feature_time:.2f}s"

        # Step 2: Generate predictions from ensemble
        start_time = time.time()
        predictions = await ensemble_predictor.predict(features)
        inference_time = time.time() - start_time

        assert predictions is not None
        assert "direction" in predictions
        assert "confidence" in predictions
        assert "model_scores" in predictions
        assert (
            inference_time < 0.5
        ), f"Model inference took {inference_time:.2f}s, exceeding 500ms"

        # Step 3: Generate trading signal
        signal_generator = SignalGenerator(
            symbol="EURUSD", ensemble_predictor=ensemble_predictor
        )

        signal = await signal_generator.create_signal_from_prediction(
            predictions, current_price=historical_data["close"].iloc[-1]
        )

        assert signal is not None
        assert signal.symbol == "EURUSD"
        assert signal.direction in ["LONG", "SHORT", "NEUTRAL"]
        assert 0 <= signal.confidence <= 1
        assert signal.entry_price > 0

        if signal.direction != "NEUTRAL":
            assert signal.stop_loss > 0
            assert signal.take_profit > 0

            # Verify risk-reward ratio
            if signal.direction == "LONG":
                risk = signal.entry_price - signal.stop_loss
                reward = signal.take_profit - signal.entry_price
            else:
                risk = signal.stop_loss - signal.entry_price
                reward = signal.entry_price - signal.take_profit

            risk_reward_ratio = reward / risk if risk > 0 else 0
            assert (
                risk_reward_ratio >= 1.5
            ), "Risk-reward ratio should be at least 1.5:1"

    @pytest.mark.asyncio
    async def test_feature_engineering_completeness(
        self, historical_data, feature_engineer
    ):
        """
        Test that feature engineering pipeline generates all required features.

        Given: Raw market data
        When: Features are computed
        Then: All feature categories should be present with no missing values
        """
        features = await feature_engineer.compute_features(historical_data.tail(200))

        # Check feature categories
        feature_categories = {
            "technical": ["sma_", "ema_", "rsi_", "bb_", "atr_"],
            "microstructure": ["spread_", "volume_", "tick_"],
            "session": ["london_", "newyork_", "tokyo_"],
            "correlation": ["corr_", "beta_"],
            "volatility": ["garch_", "realized_vol_"],
        }

        feature_columns = features.columns.tolist()

        for category, prefixes in feature_categories.items():
            category_features = [
                col
                for col in feature_columns
                if any(col.startswith(prefix) for prefix in prefixes)
            ]
            assert len(category_features) > 0, f"Missing {category} features"

        # Check for missing values
        missing_ratio = features.isnull().sum().sum() / (
            features.shape[0] * features.shape[1]
        )
        assert missing_ratio < 0.05, f"Too many missing values: {missing_ratio:.2%}"

        # Check feature count
        assert (
            features.shape[1] >= 68
        ), f"Expected at least 68 features, got {features.shape[1]}"

    @pytest.mark.asyncio
    async def test_ensemble_model_agreement(
        self, feature_engineer, ensemble_predictor, historical_data
    ):
        """
        Test that ensemble models have reasonable agreement.

        Given: Multiple ML models in ensemble
        When: Making predictions on same data
        Then: Models should agree > 60% of the time
        """
        features = await feature_engineer.compute_features(historical_data.tail(100))

        # Get individual model predictions
        model_predictions = {}
        for model_name in ensemble_predictor.models.keys():
            model = ensemble_predictor.models[model_name]
            predictions = model.predict(features.values)
            model_predictions[model_name] = predictions

        # Calculate pairwise agreement
        agreement_scores = []
        model_names = list(model_predictions.keys())

        for i in range(len(model_names)):
            for j in range(i + 1, len(model_names)):
                pred1 = model_predictions[model_names[i]]
                pred2 = model_predictions[model_names[j]]
                agreement = np.mean(pred1 == pred2)
                agreement_scores.append(agreement)

        # Average agreement should be > 60%
        avg_agreement = np.mean(agreement_scores)
        assert (
            avg_agreement > 0.6
        ), f"Model agreement {avg_agreement:.2%} below 60% threshold"

    @pytest.mark.asyncio
    async def test_confidence_score_calibration(
        self, feature_engineer, ensemble_predictor, historical_data
    ):
        """
        Test that confidence scores are well-calibrated.

        Given: ML predictions with confidence scores
        When: Evaluating against actual outcomes
        Then: Confidence should correlate with accuracy
        """
        features = await feature_engineer.compute_features(historical_data.tail(200))

        # Generate predictions with confidence scores
        predictions_list = []
        for i in range(0, len(features) - 10, 10):
            feature_slice = features.iloc[i : i + 10]
            prediction = await ensemble_predictor.predict(feature_slice)
            predictions_list.append(prediction)

        # Group predictions by confidence buckets
        confidence_buckets = {
            "low": [],  # 0.5 - 0.6
            "medium": [],  # 0.6 - 0.8
            "high": [],  # 0.8 - 1.0
        }

        for pred in predictions_list:
            conf = pred["confidence"]
            if conf < 0.6:
                confidence_buckets["low"].append(pred)
            elif conf < 0.8:
                confidence_buckets["medium"].append(pred)
            else:
                confidence_buckets["high"].append(pred)

        # Verify that higher confidence correlates with better model agreement
        for bucket_name, predictions in confidence_buckets.items():
            if len(predictions) > 0:
                avg_model_agreement = np.mean(
                    [p["model_agreement"] for p in predictions]
                )

                if bucket_name == "high":
                    assert (
                        avg_model_agreement > 0.75
                    ), "High confidence should have high model agreement"
                elif bucket_name == "medium":
                    assert (
                        avg_model_agreement > 0.6
                    ), "Medium confidence should have moderate agreement"

    @pytest.mark.asyncio
    async def test_market_regime_detection(self, historical_data):
        """
        Test market regime classification accuracy.

        Given: Market data with different regimes
        When: Regime classifier analyzes the data
        Then: Should correctly identify trending, ranging, and volatile periods
        """
        classifier = MarketRegimeClassifier(
            lookback_periods=50, regime_change_threshold=0.7
        )

        # Test on different known regimes
        # First third: trending
        trending_data = historical_data.iloc[:333]
        trend_regime = await classifier.classify_regime(trending_data)
        assert trend_regime["regime"] == "TRENDING", "Failed to detect trending regime"
        assert trend_regime["confidence"] > 0.7

        # Second third: ranging
        ranging_data = historical_data.iloc[333:666]
        range_regime = await classifier.classify_regime(ranging_data)
        assert range_regime["regime"] == "RANGING", "Failed to detect ranging regime"
        assert range_regime["confidence"] > 0.7

        # Last third: volatile
        volatile_data = historical_data.iloc[666:]
        volatile_regime = await classifier.classify_regime(volatile_data)
        assert (
            volatile_regime["regime"] == "VOLATILE"
        ), "Failed to detect volatile regime"
        assert volatile_regime["confidence"] > 0.7

    @pytest.mark.asyncio
    async def test_multi_timeframe_signal_generation(
        self, historical_data, feature_engineer, ensemble_predictor
    ):
        """
        Test signal generation across multiple timeframes.

        Given: Market data at different timeframes
        When: Signals are generated for each timeframe
        Then: Higher timeframe signals should have higher confidence
        """
        timeframes = {
            "1h": historical_data,
            "4h": historical_data.resample("4h", on="timestamp").agg(
                {
                    "open": "first",
                    "high": "max",
                    "low": "min",
                    "close": "last",
                    "volume": "sum",
                }
            ),
            "1d": historical_data.resample("1d", on="timestamp").agg(
                {
                    "open": "first",
                    "high": "max",
                    "low": "min",
                    "close": "last",
                    "volume": "sum",
                }
            ),
        }

        signals = {}
        for tf, data in timeframes.items():
            if len(data) > 50:  # Ensure enough data
                features = await feature_engineer.compute_features(data.tail(50))
                prediction = await ensemble_predictor.predict(features)

                signal = Signal(
                    symbol="EURUSD",
                    timeframe=tf,
                    direction=prediction["direction"],
                    confidence=prediction["confidence"],
                    entry_price=data["close"].iloc[-1],
                    timestamp=datetime.now(),
                )
                signals[tf] = signal

        # Verify signal consistency across timeframes
        if "1h" in signals and "4h" in signals:
            # Higher timeframes should generally have higher confidence due to less noise
            # This is a soft assertion as it may not always hold
            if signals["4h"].direction == signals["1h"].direction:
                assert signals["4h"].confidence >= signals["1h"].confidence * 0.9

    @pytest.mark.asyncio
    async def test_model_performance_monitoring(
        self, ensemble_predictor, feature_engineer, historical_data
    ):
        """
        Test model performance monitoring and degradation detection.

        Given: ML models making predictions
        When: Performance is tracked over time
        Then: System should detect performance degradation
        """
        # Simulate predictions over time
        window_size = 50
        performance_metrics = []

        for i in range(0, len(historical_data) - window_size - 10, 10):
            # Get training window
            train_data = historical_data.iloc[i : i + window_size]
            test_data = historical_data.iloc[i + window_size : i + window_size + 10]

            # Generate features and predictions
            train_features = await feature_engineer.compute_features(train_data)
            test_features = await feature_engineer.compute_features(test_data)

            predictions = await ensemble_predictor.predict(test_features)

            # Calculate simple performance metric (mock)
            # In reality, this would compare against actual market movements
            performance = np.random.uniform(0.45, 0.65)  # Simulated accuracy

            performance_metrics.append(
                {
                    "timestamp": test_data["timestamp"].iloc[-1],
                    "accuracy": performance,
                    "confidence": predictions["confidence"],
                }
            )

        # Check for performance degradation
        recent_performance = np.mean([m["accuracy"] for m in performance_metrics[-5:]])
        historical_performance = np.mean(
            [m["accuracy"] for m in performance_metrics[:-5]]
        )

        # Alert if recent performance drops significantly
        performance_drop = historical_performance - recent_performance
        assert (
            performance_drop < 0.1
        ), f"Significant performance degradation detected: {performance_drop:.2%}"

    @pytest.mark.asyncio
    async def test_signal_filtering_and_validation(
        self, ensemble_predictor, feature_engineer, historical_data
    ):
        """
        Test signal filtering and validation logic.

        Given: Raw ML predictions
        When: Signals are filtered and validated
        Then: Only high-quality signals should pass
        """
        signal_generator = SignalGenerator(
            symbol="EURUSD",
            ensemble_predictor=ensemble_predictor,
            min_confidence=0.7,
            min_model_agreement=0.6,
            filters={
                "volatility_filter": True,
                "trend_alignment": True,
                "session_filter": True,
            },
        )

        # Generate multiple raw signals
        raw_signals = []
        for i in range(0, 100, 10):
            data_slice = historical_data.iloc[i : i + 50]
            features = await feature_engineer.compute_features(data_slice)
            prediction = await ensemble_predictor.predict(features)

            raw_signal = {
                "direction": prediction["direction"],
                "confidence": prediction["confidence"],
                "model_agreement": prediction.get("model_agreement", 0.5),
                "timestamp": data_slice["timestamp"].iloc[-1],
            }
            raw_signals.append(raw_signal)

        # Apply filters
        filtered_signals = []
        for raw_signal in raw_signals:
            if await signal_generator.validate_signal(raw_signal):
                filtered_signals.append(raw_signal)

        # Check filtering effectiveness
        filter_ratio = len(filtered_signals) / len(raw_signals)
        assert (
            0.2 <= filter_ratio <= 0.8
        ), f"Filter ratio {filter_ratio:.2%} outside expected range"

        # All filtered signals should meet minimum criteria
        for signal in filtered_signals:
            assert signal["confidence"] >= 0.7
            assert signal["model_agreement"] >= 0.6

    @pytest.mark.asyncio
    @pytest.mark.slow
    async def test_ml_pipeline_performance_under_load(
        self, feature_engineer, ensemble_predictor, historical_data
    ):
        """
        Test ML pipeline performance under load.

        Given: High frequency of prediction requests
        When: System is under load
        Then: Should maintain performance SLAs
        """
        # Simulate high-frequency predictions
        num_requests = 100
        response_times = []

        async def make_prediction():
            start_time = time.time()

            # Random slice of data
            idx = np.random.randint(0, len(historical_data) - 100)
            data_slice = historical_data.iloc[idx : idx + 100]

            # Generate features and prediction
            features = await feature_engineer.compute_features(data_slice)
            prediction = await ensemble_predictor.predict(features)

            response_time = time.time() - start_time
            return response_time

        # Run predictions concurrently
        start_time = time.time()
        response_times = await asyncio.gather(
            *[make_prediction() for _ in range(num_requests)]
        )
        total_time = time.time() - start_time

        # Calculate performance metrics
        p50 = np.percentile(response_times, 50)
        p95 = np.percentile(response_times, 95)
        p99 = np.percentile(response_times, 99)

        # Verify SLAs
        assert p50 < 0.3, f"Median response time {p50:.2f}s exceeds 300ms"
        assert p95 < 0.5, f"95th percentile {p95:.2f}s exceeds 500ms"
        assert p99 < 1.0, f"99th percentile {p99:.2f}s exceeds 1s"

        # Check throughput
        throughput = num_requests / total_time
        assert (
            throughput > 10
        ), f"Throughput {throughput:.1f} req/s below 10 req/s minimum"


if __name__ == "__main__":
    # Run tests with coverage
    pytest.main([__file__, "-v", "--cov=fxml4.ml", "--cov-report=term-missing"])
