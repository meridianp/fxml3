"""
ML Signal Generation Pipeline Tests (TDD - Enterprise Performance & Accuracy Focused)
================================================================================

Comprehensive Test-Driven Development tests for ML signal generation pipeline:
- Feature extraction performance and accuracy testing
- ML model prediction reliability and latency requirements
- Signal generation with risk management integration
- Real-time pipeline performance under trading conditions

Following RED-GREEN-REFACTOR cycle for production ML trading systems.

Performance Requirements:
- Sub-second feature extraction (< 200ms for 1000 bars)
- Model prediction latency < 50ms for ensemble models
- Signal generation throughput: 1000+ signals/second
- Memory-efficient processing for continuous operation
- 99.9% uptime during trading hours

Accuracy Requirements:
- Feature extraction precision: ±0.001% maximum error
- Model prediction consistency: 100% reproducible results
- Signal confidence calibration: ±2% maximum deviation
- Risk metrics accuracy: Financial-grade precision
"""

import asyncio
import queue
import threading
import time
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple
from unittest.mock import AsyncMock, Mock, patch

import numpy as np
import pandas as pd
import pytest

from core.features.feature_engineering import UnifiedFeatureEngineer
from core.ml.ml_trading_pipeline import MLTradingPipeline
from core.ml.signal_aggregator import SignalAggregator
from core.ml.signal_generator import SignalGenerator

# ============================================================================
# Mock Objects and Fixtures for TDD Testing
# ============================================================================


class MockMarketDataGenerator:
    """Generate realistic market data for ML pipeline testing."""

    def __init__(self, symbol: str = "EURUSD", bars: int = 1000):
        self.symbol = symbol
        self.bars = bars

    def generate_ohlcv_data(self) -> pd.DataFrame:
        """Generate realistic OHLCV market data."""
        np.random.seed(42)  # Reproducible results

        # Start price and generate realistic price movement
        base_price = 1.2000
        dates = pd.date_range(
            start=datetime.now() - timedelta(hours=self.bars),
            periods=self.bars,
            freq="H",
        )

        # Generate price series with realistic volatility
        returns = np.random.normal(0, 0.001, self.bars)  # 0.1% hourly volatility
        prices = base_price * np.cumprod(1 + returns)

        # Create OHLCV data
        data = []
        for i, (date, price) in enumerate(zip(dates, prices)):
            # Create realistic OHLC from close price
            volatility = np.random.uniform(0.0005, 0.002)  # Random intrabar volatility

            high = price * (1 + volatility)
            low = price * (1 - volatility)
            open_price = prices[i - 1] if i > 0 else price
            volume = np.random.randint(1000000, 5000000)  # Random volume

            data.append(
                {
                    "timestamp": date,
                    "symbol": self.symbol,
                    "open": open_price,
                    "high": high,
                    "low": low,
                    "close": price,
                    "volume": volume,
                }
            )

        return pd.DataFrame(data)


class MockMLModel:
    """Mock ML model for testing predictions."""

    def __init__(
        self,
        model_name: str = "random_forest",
        confidence_range: Tuple[float, float] = (0.5, 0.95),
    ):
        self.model_name = model_name
        self.confidence_range = confidence_range
        self.prediction_count = 0

    def predict(self, features: np.ndarray) -> Dict[str, Any]:
        """Mock model prediction with realistic confidence scores."""
        self.prediction_count += 1

        # Simulate processing time
        time.sleep(0.001)  # 1ms processing time

        # Generate consistent but varied predictions
        np.random.seed(int(features.sum()) % 1000)  # Consistent seed based on features

        confidence = np.random.uniform(*self.confidence_range)
        signal_prob = np.random.random()

        if signal_prob > 0.6:
            signal = "BUY"
        elif signal_prob < 0.4:
            signal = "SELL"
        else:
            signal = "HOLD"

        return {
            "signal": signal,
            "confidence": confidence,
            "model": self.model_name,
            "probabilities": {
                "BUY": max(0.1, signal_prob + np.random.normal(0, 0.1)),
                "SELL": max(0.1, (1 - signal_prob) + np.random.normal(0, 0.1)),
                "HOLD": max(0.1, np.random.uniform(0.2, 0.4)),
            },
        }


@pytest.fixture
def mock_market_data():
    """Generate mock market data for testing."""
    generator = MockMarketDataGenerator("EURUSD", 1000)
    return generator.generate_ohlcv_data()


@pytest.fixture
def ml_pipeline():
    """Create ML trading pipeline for testing."""
    config = {
        "confidence_threshold": 0.65,
        "feature_config": {
            "technical_indicators": True,
            "statistical_features": True,
            "elliott_wave_features": True,
        },
        "model_config": {
            "ensemble_models": ["random_forest", "gradient_boost", "neural_network"],
            "prediction_horizon": "1h",
            "update_frequency": "realtime",
        },
    }
    return MLTradingPipeline(config)


@pytest.fixture
def feature_engineer():
    """Create feature engineering component."""
    config = {
        "basic_indicators": ["sma", "ema", "rsi", "macd", "bollinger"],
        "ma_periods": [21, 50, 200],
        "advanced_features": True,
        "elliott_wave_features": True,
    }
    return UnifiedFeatureEngineer(config)


@pytest.fixture
def signal_generator():
    """Create signal generator component."""
    return SignalGenerator(confidence_threshold=0.65)


@pytest.fixture
def signal_aggregator():
    """Create signal aggregator component."""
    return SignalAggregator({"method": "weighted_voting"})


# ============================================================================
# TDD Test Class 1: Feature Extraction Performance and Accuracy
# ============================================================================


class TestMLFeatureExtractionPerformance:
    """
    RED Phase Tests for ML Feature Extraction Performance and Accuracy.

    Enterprise ML Requirements:
    - Sub-200ms feature extraction for 1000 market data points
    - Mathematical precision in technical indicator calculations
    - Memory-efficient processing for continuous operation
    - Concurrent feature extraction for multiple symbols
    """

    @pytest.mark.tdd
    @pytest.mark.red
    def test_feature_extraction_performance_benchmark(
        self, feature_engineer, mock_market_data
    ):
        """
        RED: Feature extraction must complete within 200ms for 1000 data points.

        Performance Requirement: High-frequency feature extraction for real-time trading
        """
        # Arrange
        iterations = 10  # Test sustained performance
        extraction_times = []

        # Act - Measure feature extraction performance
        for _ in range(iterations):
            start_time = time.perf_counter()

            try:
                features = feature_engineer.generate_features(mock_market_data)

                extraction_time = (
                    time.perf_counter() - start_time
                ) * 1000  # milliseconds
                extraction_times.append(extraction_time)

                # Verify features were generated
                assert features is not None
                assert len(features) > 0
                assert len(features.columns) > 10  # Should have multiple features

            except AttributeError:
                # Expected in RED phase - generate_features method might not exist
                pytest.fail(
                    "Feature extraction capability not implemented - required for ML pipeline"
                )

        # Assert - Performance requirements (will fail until optimized)
        if extraction_times:
            avg_time = sum(extraction_times) / len(extraction_times)
            max_time = max(extraction_times)

            assert (
                avg_time < 200
            ), f"Average extraction time {avg_time:.2f}ms exceeds 200ms requirement"
            assert (
                max_time < 500
            ), f"Maximum extraction time {max_time:.2f}ms exceeds 500ms limit"

    @pytest.mark.tdd
    @pytest.mark.red
    def test_technical_indicator_precision_accuracy(self, feature_engineer):
        """
        RED: Technical indicators must maintain financial-grade precision.

        Accuracy Requirement: ±0.001% maximum error in calculations
        """
        # Arrange - Create test data with known values
        test_data = pd.DataFrame(
            {
                "timestamp": pd.date_range("2024-01-01", periods=100, freq="1H"),
                "symbol": ["EURUSD"] * 100,
                "open": [1.2000] * 100,
                "high": [1.2010] * 100,
                "low": [1.1990] * 100,
                "close": [1.2005] * 100,
                "volume": [1000000] * 100,
            }
        )

        try:
            features = feature_engineer.generate_features(test_data)

            # Test SMA calculation precision
            if "sma_21" in features.columns:
                expected_sma = test_data["close"].rolling(21).mean()
                actual_sma = features["sma_21"]

                # Calculate maximum relative error
                max_error = abs((actual_sma - expected_sma) / expected_sma).max()
                assert (
                    max_error < 0.00001
                ), f"SMA precision error {max_error:.6f} exceeds 0.001% tolerance"

            # Test RSI calculation bounds
            if "rsi_14" in features.columns:
                rsi_values = features["rsi_14"].dropna()
                assert (rsi_values >= 0).all() and (
                    rsi_values <= 100
                ).all(), "RSI values outside valid range [0,100]"

            # Test MACD signal alignment
            if "macd" in features.columns and "macd_signal" in features.columns:
                macd_diff = features["macd"] - features["macd_signal"]
                assert macd_diff.notna().sum() > 0, "MACD signal calculation failed"

        except (AttributeError, KeyError):
            # Expected in RED phase - feature calculations not implemented
            pytest.fail("Technical indicator precision calculations not implemented")

    @pytest.mark.tdd
    @pytest.mark.red
    def test_feature_extraction_memory_efficiency(self, feature_engineer):
        """
        RED: Feature extraction must be memory-efficient for continuous operation.

        Memory Requirement: No memory leaks in continuous feature extraction
        """
        import os

        import psutil

        # Arrange - Get initial memory usage
        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB

        # Act - Perform many feature extraction cycles
        cycles = 100
        data_generator = MockMarketDataGenerator("EURUSD", 500)

        try:
            for cycle in range(cycles):
                # Generate fresh market data for each cycle
                market_data = data_generator.generate_ohlcv_data()

                # Extract features
                features = feature_engineer.generate_features(market_data)

                # Force garbage collection periodically
                if cycle % 20 == 0:
                    import gc

                    gc.collect()

                    # Check memory usage
                    current_memory = process.memory_info().rss / 1024 / 1024  # MB
                    memory_increase = current_memory - initial_memory

                    # Allow some memory growth but not unbounded
                    max_allowed_increase = 100  # MB
                    assert (
                        memory_increase < max_allowed_increase
                    ), f"Memory leak detected: {memory_increase:.1f}MB increase after {cycle} cycles"

        except AttributeError:
            # Expected in RED phase
            pytest.fail("Memory-efficient feature extraction not implemented")

    @pytest.mark.tdd
    @pytest.mark.red
    def test_concurrent_feature_extraction_thread_safety(self, feature_engineer):
        """
        RED: Feature extraction must be thread-safe for multiple symbol processing.

        Concurrency Requirement: Multiple threads extracting features simultaneously
        """
        import queue
        import threading

        # Arrange - Create market data for multiple symbols
        symbols = ["EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCAD"]
        market_data_sets = {}

        for symbol in symbols:
            generator = MockMarketDataGenerator(symbol, 200)
            market_data_sets[symbol] = generator.generate_ohlcv_data()

        results_queue = queue.Queue()
        errors_queue = queue.Queue()

        def extract_features(symbol, data):
            """Extract features in separate thread."""
            try:
                start_time = time.perf_counter()
                features = feature_engineer.generate_features(data)
                extraction_time = time.perf_counter() - start_time

                results_queue.put((symbol, len(features.columns), extraction_time))

            except Exception as e:
                errors_queue.put((symbol, str(e)))

        # Act - Start concurrent feature extraction
        threads = []
        for symbol, data in market_data_sets.items():
            thread = threading.Thread(target=extract_features, args=(symbol, data))
            threads.append(thread)
            thread.start()

        # Wait for all threads to complete
        for thread in threads:
            thread.join()

        # Assert - All extractions should succeed
        try:
            assert results_queue.qsize() == len(
                symbols
            ), f"Expected {len(symbols)} successful extractions, got {results_queue.qsize()}"

            # Verify no data corruption between concurrent operations
            results = []
            while not results_queue.empty():
                results.append(results_queue.get())

            # Check that all symbols were processed
            processed_symbols = [result[0] for result in results]
            assert set(processed_symbols) == set(
                symbols
            ), "Missing symbols in concurrent processing"

            # Check performance consistency across threads
            extraction_times = [result[2] for result in results]
            max_time = max(extraction_times)
            assert max_time < 0.5, f"Concurrent extraction too slow: {max_time:.3f}s"

        except AssertionError:
            # In RED phase, we expect this to fail due to missing implementation
            error_count = errors_queue.qsize()
            if error_count > 0:
                first_error = errors_queue.get()
                if "AttributeError" in first_error[1]:
                    pytest.fail(
                        "Concurrent feature extraction not implemented - required for multi-symbol trading"
                    )
                else:
                    pytest.fail(f"Thread safety issues detected: {first_error[1]}")


# ============================================================================
# TDD Test Class 2: ML Model Prediction Reliability and Performance
# ============================================================================


class TestMLModelPredictionReliability:
    """
    RED Phase Tests for ML Model Prediction Reliability and Performance.

    Requirements:
    - Model prediction latency < 50ms for ensemble predictions
    - Prediction reproducibility and consistency
    - Confidence score calibration accuracy
    - Model performance monitoring and drift detection
    """

    @pytest.mark.tdd
    @pytest.mark.red
    def test_model_prediction_latency_benchmark(self, ml_pipeline, mock_market_data):
        """
        RED: Model predictions must complete within 50ms for trading decisions.

        Performance Requirement: Ultra-low latency for algorithmic trading systems
        """
        # Arrange
        test_features = np.random.random((1, 50))  # 50 features
        iterations = 100
        prediction_times = []

        # Act - Measure model prediction performance
        for _ in range(iterations):
            start_time = time.perf_counter()

            try:
                # This will fail in RED phase - predict_ensemble method doesn't exist
                prediction = ml_pipeline.model_predictor.predict_ensemble(test_features)

                prediction_time = (
                    time.perf_counter() - start_time
                ) * 1000  # milliseconds
                prediction_times.append(prediction_time)

                # Verify prediction format
                assert "signal" in prediction
                assert "confidence" in prediction
                assert prediction["confidence"] >= 0 and prediction["confidence"] <= 1

            except AttributeError:
                # Expected in RED phase - model predictor doesn't exist
                pytest.fail(
                    "Model prediction capability not implemented - required for trading signals"
                )

        # Assert - Performance requirements (will fail until optimized)
        if prediction_times:
            avg_time = sum(prediction_times) / len(prediction_times)
            p95_time = np.percentile(prediction_times, 95)

            assert (
                avg_time < 50
            ), f"Average prediction time {avg_time:.2f}ms exceeds 50ms requirement"
            assert (
                p95_time < 100
            ), f"P95 prediction time {p95_time:.2f}ms exceeds 100ms SLA"

    @pytest.mark.tdd
    @pytest.mark.red
    def test_prediction_reproducibility_consistency(self, ml_pipeline):
        """
        RED: Model predictions must be 100% reproducible for same inputs.

        Reliability Requirement: Consistent predictions for regulatory compliance
        """
        # Arrange - Create identical feature sets
        test_features = np.array([[1.2, 0.75, -0.3, 0.95, 0.12] * 10])  # 50 features

        predictions = []

        try:
            # Act - Generate multiple predictions with same input
            for i in range(10):
                prediction = ml_pipeline.model_predictor.predict_ensemble(test_features)
                predictions.append(prediction)

            # Assert - All predictions should be identical
            first_prediction = predictions[0]
            for i, pred in enumerate(predictions[1:], 2):
                assert (
                    pred["signal"] == first_prediction["signal"]
                ), f"Signal inconsistency: prediction {i} = {pred['signal']}, expected {first_prediction['signal']}"
                assert (
                    abs(pred["confidence"] - first_prediction["confidence"]) < 1e-10
                ), f"Confidence inconsistency: prediction {i} = {pred['confidence']:.10f}, expected {first_prediction['confidence']:.10f}"

        except AttributeError:
            # Expected in RED phase
            pytest.fail(
                "Model prediction reproducibility not implemented - regulatory compliance failure"
            )

    @pytest.mark.tdd
    @pytest.mark.red
    def test_confidence_score_calibration_accuracy(self, ml_pipeline):
        """
        RED: Model confidence scores must be properly calibrated for risk management.

        Accuracy Requirement: Confidence scores must reflect actual prediction accuracy
        """
        # Arrange - Generate predictions across confidence ranges
        test_cases = []
        confidence_buckets = {"high": [], "medium": [], "low": []}

        try:
            for i in range(1000):
                # Generate varied feature inputs
                features = np.random.random((1, 50))
                prediction = ml_pipeline.model_predictor.predict_ensemble(features)

                test_cases.append(prediction)

                # Bucket by confidence level
                confidence = prediction["confidence"]
                if confidence >= 0.8:
                    confidence_buckets["high"].append(prediction)
                elif confidence >= 0.6:
                    confidence_buckets["medium"].append(prediction)
                else:
                    confidence_buckets["low"].append(prediction)

            # Assert - Confidence distribution should be meaningful
            assert (
                len(confidence_buckets["high"]) > 0
            ), "No high-confidence predictions generated"
            assert (
                len(confidence_buckets["medium"]) > 0
            ), "No medium-confidence predictions generated"
            assert (
                len(confidence_buckets["low"]) > 0
            ), "No low-confidence predictions generated"

            # Check confidence score ranges
            high_confidences = [p["confidence"] for p in confidence_buckets["high"]]
            medium_confidences = [p["confidence"] for p in confidence_buckets["medium"]]
            low_confidences = [p["confidence"] for p in confidence_buckets["low"]]

            assert (
                min(high_confidences) >= 0.8
            ), "High-confidence bucket contains low-confidence predictions"
            assert (
                max(low_confidences) < 0.6
            ), "Low-confidence bucket contains high-confidence predictions"

        except AttributeError:
            # Expected in RED phase
            pytest.fail(
                "Confidence score calibration not implemented - risk management failure"
            )

    @pytest.mark.tdd
    @pytest.mark.red
    async def test_real_time_pipeline_integration_performance(
        self, ml_pipeline, mock_market_data
    ):
        """
        RED: Complete ML pipeline must process market data in real-time.

        Integration Requirement: End-to-end pipeline performance under trading load
        """
        # Arrange - Simulate real-time market data feed
        processed_signals = []
        processing_times = []

        try:
            # Act - Process market data through complete pipeline
            for i in range(0, len(mock_market_data), 100):  # Process in chunks
                chunk = mock_market_data.iloc[
                    max(0, i - 200) : i + 100
                ]  # Rolling window

                if len(chunk) < 50:  # Need minimum data for features
                    continue

                start_time = time.perf_counter()

                # This will fail in RED phase - process_market_data method doesn't exist
                signal = await ml_pipeline.process_market_data(chunk)

                processing_time = (
                    time.perf_counter() - start_time
                ) * 1000  # milliseconds
                processing_times.append(processing_time)

                if signal and signal.get("confidence", 0) > 0.5:
                    processed_signals.append(signal)

            # Assert - Pipeline performance requirements
            assert len(processed_signals) > 0, "No signals generated from pipeline"

            if processing_times:
                avg_time = sum(processing_times) / len(processing_times)
                max_time = max(processing_times)

                assert (
                    avg_time < 1000
                ), f"Average pipeline processing {avg_time:.2f}ms exceeds 1s requirement"
                assert (
                    max_time < 2000
                ), f"Maximum processing time {max_time:.2f}ms exceeds 2s limit"

            # Verify signal quality
            for signal in processed_signals[:10]:  # Check first 10 signals
                assert "symbol" in signal, "Signal missing symbol field"
                assert "action" in signal, "Signal missing action field"
                assert "confidence" in signal, "Signal missing confidence field"
                assert signal["action"] in [
                    "BUY",
                    "SELL",
                    "HOLD",
                ], f"Invalid signal action: {signal['action']}"

        except AttributeError:
            # Expected in RED phase - pipeline integration not implemented
            pytest.fail(
                "Real-time ML pipeline integration not implemented - trading system failure"
            )


# ============================================================================
# TDD Test Class 3: Signal Generation and Risk Management Integration
# ============================================================================


class TestMLSignalGenerationRiskManagement:
    """
    RED Phase Tests for ML Signal Generation and Risk Management Integration.

    Requirements:
    - Signal generation throughput: 1000+ signals/second
    - Risk-adjusted position sizing and stop-loss calculation
    - Signal aggregation from multiple models/timeframes
    - Real-time risk monitoring and signal filtering
    """

    @pytest.mark.tdd
    @pytest.mark.red
    def test_signal_generation_throughput_benchmark(self, signal_generator):
        """
        RED: Signal generation must handle 1000+ signals per second.

        Throughput Requirement: High-frequency signal generation for scalping strategies
        """
        # Arrange - Create batch of mock predictions
        batch_size = 1000
        predictions = []

        for i in range(batch_size):
            prediction = {
                "signal": "BUY" if i % 3 == 0 else ("SELL" if i % 3 == 1 else "HOLD"),
                "confidence": 0.5 + (i % 50) / 100,  # Varying confidence 0.5-0.99
                "model": f"model_{i % 5}",
                "probabilities": {"BUY": 0.4, "SELL": 0.3, "HOLD": 0.3},
            }
            predictions.append(prediction)

        # Act - Measure signal generation throughput
        start_time = time.perf_counter()

        generated_signals = []
        for i, prediction in enumerate(predictions):
            try:
                signal = signal_generator.generate_signal(
                    symbol=f"PAIR{i % 10:03d}",
                    prediction=prediction,
                    current_price=1.2000 + (i % 1000) / 10000,
                )
                generated_signals.append(signal)

            except AttributeError:
                # Expected in RED phase if generate_signal not optimized
                pytest.fail("High-throughput signal generation not implemented")

        end_time = time.perf_counter()
        duration = end_time - start_time
        throughput = len(generated_signals) / duration  # signals per second

        # Assert - Throughput requirements
        assert (
            throughput >= 1000
        ), f"Signal generation throughput {throughput:.0f}/sec below 1000 requirement"
        assert (
            len(generated_signals) == batch_size
        ), f"Expected {batch_size} signals, got {len(generated_signals)}"

    @pytest.mark.tdd
    @pytest.mark.red
    def test_risk_adjusted_signal_generation(self, signal_generator):
        """
        RED: Signals must include risk-adjusted position sizing and stop-losses.

        Risk Management Requirement: Every signal must include risk parameters
        """
        # Arrange - Create prediction with risk metrics
        prediction = {
            "signal": "BUY",
            "confidence": 0.85,
            "model": "ensemble",
            "probabilities": {"BUY": 0.7, "SELL": 0.2, "HOLD": 0.1},
        }

        risk_metrics = {
            "portfolio_var": 0.012,  # 1.2% VaR
            "max_drawdown": 0.025,  # 2.5% drawdown
            "sharpe_ratio": 1.4,  # Good Sharpe ratio
            "volatility": 0.15,  # 15% volatility
        }

        try:
            # Act - Generate signal with risk adjustments
            signal = signal_generator.generate_signal("EURUSD", prediction, 1.2500)
            risk_adjusted_signal = signal_generator.apply_risk_adjustment(
                signal, risk_metrics
            )

            # Assert - Risk parameters must be present
            required_risk_fields = ["position_size", "stop_loss", "take_profit"]
            for field in required_risk_fields:
                assert field in risk_adjusted_signal, f"Missing risk field: {field}"

            # Verify position sizing logic
            assert (
                risk_adjusted_signal["position_size"] > 0
            ), "Position size must be positive"
            assert (
                risk_adjusted_signal["position_size"] <= 200000
            ), "Position size exceeds maximum limit"

            # Verify stop-loss and take-profit levels
            if risk_adjusted_signal["stop_loss"]:
                current_price = risk_adjusted_signal["price"]
                stop_loss = risk_adjusted_signal["stop_loss"]

                if signal["action"] == "BUY":
                    assert (
                        stop_loss < current_price
                    ), "Buy stop-loss should be below current price"
                elif signal["action"] == "SELL":
                    assert (
                        stop_loss > current_price
                    ), "Sell stop-loss should be above current price"

        except AttributeError:
            # Expected in RED phase
            pytest.fail(
                "Risk-adjusted signal generation not implemented - financial risk exposure"
            )

    @pytest.mark.tdd
    @pytest.mark.red
    def test_multi_model_signal_aggregation(self, signal_aggregator):
        """
        RED: Signal aggregation must combine multiple model predictions intelligently.

        Ensemble Requirement: Robust signal consensus from multiple ML models
        """
        # Arrange - Create signals from different models
        model_signals = [
            {
                "symbol": "GBPUSD",
                "action": "BUY",
                "confidence": 0.85,
                "model": "random_forest",
            },
            {
                "symbol": "GBPUSD",
                "action": "BUY",
                "confidence": 0.78,
                "model": "gradient_boost",
            },
            {
                "symbol": "GBPUSD",
                "action": "HOLD",
                "confidence": 0.65,
                "model": "neural_network",
            },
            {"symbol": "GBPUSD", "action": "BUY", "confidence": 0.72, "model": "svm"},
            {
                "symbol": "GBPUSD",
                "action": "SELL",
                "confidence": 0.60,
                "model": "logistic_regression",
            },
        ]

        try:
            # Act - Aggregate multiple model signals
            aggregated_signal = signal_aggregator.aggregate_signals(model_signals)

            # Assert - Aggregation quality checks
            assert "symbol" in aggregated_signal, "Aggregated signal missing symbol"
            assert "action" in aggregated_signal, "Aggregated signal missing action"
            assert (
                "confidence" in aggregated_signal
            ), "Aggregated signal missing confidence"
            assert (
                "signal_count" in aggregated_signal
            ), "Aggregated signal missing count"
            assert (
                "action_distribution" in aggregated_signal
            ), "Missing action distribution"

            # Verify aggregation logic
            assert aggregated_signal["signal_count"] == len(model_signals)
            assert aggregated_signal["action"] in ["BUY", "SELL", "HOLD"]
            assert 0 <= aggregated_signal["confidence"] <= 1

            # Check that majority vote was applied correctly
            action_counts = aggregated_signal["action_distribution"]
            most_voted_action = max(action_counts, key=action_counts.get)
            assert (
                aggregated_signal["action"] == most_voted_action
            ), "Aggregation didn't follow majority vote"

        except AttributeError:
            # Expected in RED phase
            pytest.fail(
                "Multi-model signal aggregation not implemented - ensemble trading failure"
            )

    @pytest.mark.tdd
    @pytest.mark.red
    def test_real_time_signal_filtering_and_validation(self, ml_pipeline):
        """
        RED: Real-time signal filtering must prevent invalid/dangerous signals.

        Safety Requirement: Signal validation for production trading protection
        """
        # Arrange - Create various signal scenarios including edge cases
        test_scenarios = [
            {
                "name": "high_confidence_valid",
                "prediction": {
                    "signal": "BUY",
                    "confidence": 0.95,
                    "model": "ensemble",
                },
                "expected_pass": True,
            },
            {
                "name": "low_confidence_filtered",
                "prediction": {
                    "signal": "BUY",
                    "confidence": 0.45,
                    "model": "weak_model",
                },
                "expected_pass": False,
            },
            {
                "name": "invalid_signal_type",
                "prediction": {
                    "signal": "INVALID",
                    "confidence": 0.85,
                    "model": "test",
                },
                "expected_pass": False,
            },
            {
                "name": "confidence_out_of_bounds",
                "prediction": {"signal": "SELL", "confidence": 1.5, "model": "broken"},
                "expected_pass": False,
            },
            {
                "name": "missing_required_fields",
                "prediction": {"confidence": 0.75},  # Missing signal field
                "expected_pass": False,
            },
        ]

        try:
            validated_signals = []

            # Act - Test signal validation for each scenario
            for scenario in test_scenarios:
                try:
                    # This will fail in RED phase - signal validation not implemented
                    is_valid = ml_pipeline.signal_generator.validate_signal(
                        scenario["prediction"]
                    )

                    if is_valid and scenario["expected_pass"]:
                        signal = ml_pipeline.signal_generator.generate_signal(
                            "TESTPAIR", scenario["prediction"], 1.2000
                        )
                        validated_signals.append((scenario["name"], signal))
                    elif not is_valid and not scenario["expected_pass"]:
                        validated_signals.append(
                            (scenario["name"], None)
                        )  # Correctly filtered
                    else:
                        pytest.fail(
                            f"Signal validation failed for scenario: {scenario['name']}"
                        )

                except Exception as e:
                    if scenario["expected_pass"]:
                        pytest.fail(f"Valid signal rejected: {scenario['name']} - {e}")

            # Assert - Validation results
            assert len(validated_signals) == len(
                test_scenarios
            ), "Not all scenarios were processed"

            # Check that dangerous signals were filtered
            valid_signals = [item for item in validated_signals if item[1] is not None]
            assert (
                len(valid_signals) == 1
            ), "Only high-confidence valid signal should pass"

        except AttributeError:
            # Expected in RED phase
            pytest.fail(
                "Real-time signal filtering and validation not implemented - trading safety failure"
            )
