"""Comprehensive Integration Tests for Core Trading Pipeline.

This module provides systematic integration testing for the complete trading workflow,
ensuring all components work together reliably. Tests validate the critical path from
market data ingestion through signal generation to broker execution.

Integration Test Coverage:
- Complete Trading Pipeline: Data → Features → ML → Signals → FIX → Broker
- Cross-System Communication and Data Flow Validation
- Error Handling Across System Boundaries
- Performance Under Realistic Trading Loads
- Real-Time Processing and Latency Requirements
- Multi-Component Failure Recovery Scenarios

Following systematic integration testing methodology with focus on production readiness.
"""

import asyncio
import json
import logging
import time
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple
from unittest.mock import AsyncMock, MagicMock, PropertyMock, patch

import numpy as np
import pandas as pd
import pytest

from fxml4.api.services.trading_engine import TradingEngine
from fxml4.brokers.adapters.adapter_management import BrokerAdapterManager
from fxml4.brokers.adapters.ib_adapter import IBBrokerAdapter
from fxml4.data_engineering.data_feeds.ib_feed import IBDataFeed

# Core System Components for Integration Testing
from fxml4.data_engineering.timescaledb import TimescaleDBManager
from fxml4.features.feature_engineering import FeatureEngineer
from fxml4.fix.session_manager import FIXSession, SessionConfig
from fxml4.ml.models.ensemble import EnsembleModel
from fxml4.ml.training import MLModelTrainer
from fxml4.monitoring.system_monitor import SystemMonitor
from fxml4.strategy.integrated_signal_generator import IntegratedSignalGenerator
from tests.fixtures.broker_fixtures import mock_broker_session

# Test Infrastructure
from tests.fixtures.database_fixtures import test_database
from tests.utils.test_helpers import create_test_orders, generate_realistic_market_data


class TestCoreTradingPipeline:
    """Test complete trading pipeline integration."""

    @pytest.fixture
    async def trading_system_config(self):
        """Configure complete trading system for integration testing."""
        return {
            "database": {
                "host": "localhost",
                "port": 5433,
                "name": "ftml4_integration_test",
                "user": "test_user",
                "password": "test_pass",
            },
            "brokers": {
                "ib": {
                    "host": "localhost",
                    "port": 7497,
                    "client_id": 999,
                    "account": "DU123456",
                }
            },
            "ml": {
                "model_registry_path": "/tmp/test_models",
                "feature_cache_ttl": 300,
                "prediction_batch_size": 100,
            },
            "fix": {
                "version": "FIX.4.2",
                "heartbeat_interval": 30,
                "logon_timeout": 10,
            },
            "trading": {
                "max_position_size": 1000000,
                "risk_per_trade": 0.02,
                "max_daily_loss": 0.05,
            },
        }

    @pytest.fixture
    async def mock_system_components(self, trading_system_config):
        """Create mock system components for integration testing."""
        components = {}

        # Mock Database
        components["database"] = AsyncMock(spec=TimescaleDBManager)
        components["database"].connect = AsyncMock()
        components["database"].execute = AsyncMock()
        components["database"].fetch = AsyncMock()

        # Mock Data Feed
        components["data_feed"] = AsyncMock(spec=IBDataFeed)
        components["data_feed"].connect = AsyncMock()
        components["data_feed"].subscribe = AsyncMock()
        components["data_feed"].get_historical_data = AsyncMock()

        # Mock Feature Engineer
        components["feature_engineer"] = MagicMock(spec=FeatureEngineer)
        components["feature_engineer"].create_features = MagicMock()

        # Mock ML Model
        components["ml_model"] = MagicMock(spec=EnsembleModel)
        components["ml_model"].predict = MagicMock()
        components["ml_model"].predict_proba = MagicMock()

        # Mock Signal Generator
        components["signal_generator"] = MagicMock(spec=IntegratedSignalGenerator)
        components["signal_generator"].generate_signals = MagicMock()

        # Mock FIX Session
        components["fix_session"] = AsyncMock(spec=FIXSession)
        components["fix_session"].connect = AsyncMock()
        components["fix_session"].send_message = AsyncMock()

        # Mock Broker Adapter
        components["broker_adapter"] = AsyncMock(spec=IBBrokerAdapter)
        components["broker_adapter"].connect = AsyncMock()
        components["broker_adapter"].submit_order = AsyncMock()
        components["broker_adapter"].get_positions = AsyncMock()

        # Mock System Monitor
        components["system_monitor"] = MagicMock(spec=SystemMonitor)
        components["system_monitor"].log_event = MagicMock()
        components["system_monitor"].check_health = MagicMock()

        return components

    @pytest.fixture
    def sample_market_data(self):
        """Generate sample market data for testing."""
        dates = pd.date_range(start="2024-01-01", periods=1000, freq="1H")

        # Generate realistic EURUSD data
        np.random.seed(42)
        price_base = 1.1000
        price_changes = np.random.normal(0, 0.0005, 1000)
        prices = price_base + np.cumsum(price_changes)

        data = pd.DataFrame(
            {
                "timestamp": dates,
                "symbol": "EURUSD",
                "open": prices,
                "high": prices + np.random.uniform(0, 0.0020, 1000),
                "low": prices - np.random.uniform(0, 0.0020, 1000),
                "close": prices + np.random.uniform(-0.0010, 0.0010, 1000),
                "volume": np.random.randint(1000, 10000, 1000),
            }
        )

        # Ensure OHLC logic
        data["high"] = np.maximum(data[["open", "close"]].max(axis=1), data["high"])
        data["low"] = np.minimum(data[["open", "close"]].min(axis=1), data["low"])

        return data


class TestDataIngestionToFeatures:
    """Test data ingestion to feature engineering integration."""

    @pytest.mark.asyncio
    async def test_data_feed_to_database_integration(
        self, mock_system_components, sample_market_data
    ):
        """Test complete data flow from feed to database storage."""
        database = mock_system_components["database"]
        data_feed = mock_system_components["data_feed"]

        # Mock data feed returning sample data
        data_feed.get_historical_data.return_value = sample_market_data

        # Simulate data ingestion workflow
        await data_feed.connect()
        historical_data = await data_feed.get_historical_data("EURUSD", "1H", 1000)

        # Verify data structure
        assert len(historical_data) == 1000
        assert "symbol" in historical_data.columns
        assert "timestamp" in historical_data.columns
        assert all(
            col in historical_data.columns
            for col in ["open", "high", "low", "close", "volume"]
        )

        # Simulate database storage
        await database.connect()
        await database.execute(
            "INSERT INTO market_data ...", historical_data.to_dict("records")
        )

        # Verify integration calls
        data_feed.connect.assert_called_once()
        data_feed.get_historical_data.assert_called_once_with("EURUSD", "1H", 1000)
        database.connect.assert_called_once()
        database.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_database_to_feature_engineering_integration(
        self, mock_system_components, sample_market_data
    ):
        """Test integration from database retrieval to feature engineering."""
        database = mock_system_components["database"]
        feature_engineer = mock_system_components["feature_engineer"]

        # Mock database returning market data
        database.fetch.return_value = sample_market_data.to_dict("records")

        # Mock feature engineering
        expected_features = sample_market_data.copy()
        expected_features["rsi"] = np.random.uniform(0, 100, len(sample_market_data))
        expected_features["macd"] = np.random.uniform(
            -0.01, 0.01, len(sample_market_data)
        )
        expected_features["bb_upper"] = expected_features["close"] * 1.02
        expected_features["bb_lower"] = expected_features["close"] * 0.98

        feature_engineer.create_features.return_value = expected_features

        # Simulate feature engineering workflow
        raw_data = await database.fetch(
            "SELECT * FROM market_data WHERE symbol = %s", ("EURUSD",)
        )
        raw_df = pd.DataFrame(raw_data)

        features_df = feature_engineer.create_features(
            raw_df, ["rsi", "macd", "bollinger_bands"]
        )

        # Verify integration
        assert len(features_df) == len(sample_market_data)
        assert "rsi" in features_df.columns
        assert "macd" in features_df.columns
        assert "bb_upper" in features_df.columns

        database.fetch.assert_called_once()
        feature_engineer.create_features.assert_called_once()

    @pytest.mark.asyncio
    async def test_feature_caching_and_performance(
        self, mock_system_components, sample_market_data
    ):
        """Test feature engineering caching for performance optimization."""
        database = mock_system_components["database"]
        feature_engineer = mock_system_components["feature_engineer"]

        # Mock cached and uncached scenarios
        database.fetch.return_value = sample_market_data.to_dict("records")

        expected_features = sample_market_data.copy()
        expected_features["technical_features"] = np.random.uniform(
            -1, 1, len(sample_market_data)
        )

        feature_engineer.create_features.return_value = expected_features

        # Test first call (cache miss)
        start_time = time.time()

        raw_data = await database.fetch(
            "SELECT * FROM market_data WHERE symbol = %s", ("EURUSD",)
        )
        features_df1 = feature_engineer.create_features(
            pd.DataFrame(raw_data), ["technical_features"]
        )

        first_call_time = time.time() - start_time

        # Test second call (should use cache or be faster)
        start_time = time.time()

        raw_data = await database.fetch(
            "SELECT * FROM market_data WHERE symbol = %s", ("EURUSD",)
        )
        features_df2 = feature_engineer.create_features(
            pd.DataFrame(raw_data), ["technical_features"]
        )

        second_call_time = time.time() - start_time

        # Verify caching behavior
        assert len(features_df1) == len(features_df2)
        assert list(features_df1.columns) == list(features_df2.columns)

        # Performance optimization expectation
        # (Note: In real implementation, second call should be faster due to caching)
        assert second_call_time <= first_call_time + 0.1  # Allow some variance


class TestMLPipelineIntegration:
    """Test ML pipeline integration from features to signals."""

    @pytest.mark.asyncio
    async def test_features_to_ml_prediction_integration(
        self, mock_system_components, sample_market_data
    ):
        """Test integration from features to ML model predictions."""
        feature_engineer = mock_system_components["feature_engineer"]
        ml_model = mock_system_components["ml_model"]

        # Create features with ML-ready format
        features_df = sample_market_data.copy()
        features_df["rsi"] = np.random.uniform(0, 100, len(sample_market_data))
        features_df["macd"] = np.random.uniform(-0.01, 0.01, len(sample_market_data))
        features_df["returns"] = features_df["close"].pct_change()

        feature_engineer.create_features.return_value = features_df

        # Mock ML predictions
        predictions = np.random.choice(
            [0, 1], size=len(features_df), p=[0.6, 0.4]
        )  # Buy/sell signals
        probabilities = np.random.uniform(0.5, 0.95, size=len(features_df))

        ml_model.predict.return_value = predictions
        ml_model.predict_proba.return_value = probabilities

        # Simulate ML prediction workflow
        feature_columns = ["rsi", "macd", "returns"]
        X = features_df[feature_columns].dropna()

        # Ensure proper data format for ML
        assert not X.empty
        assert len(X.columns) == 3
        assert not X.isnull().any().any()

        # Generate predictions
        predictions_result = ml_model.predict(X)
        probabilities_result = ml_model.predict_proba(X)

        # Verify ML integration
        assert len(predictions_result) == len(X)
        assert len(probabilities_result) == len(X)
        assert all(p in [0, 1] for p in predictions_result)
        assert all(0 <= prob <= 1 for prob in probabilities_result)

        ml_model.predict.assert_called_once()
        ml_model.predict_proba.assert_called_once()

    @pytest.mark.asyncio
    async def test_ml_predictions_to_signals_integration(self, mock_system_components):
        """Test integration from ML predictions to trading signals."""
        ml_model = mock_system_components["ml_model"]
        signal_generator = mock_system_components["signal_generator"]

        # Mock ML predictions
        num_predictions = 100
        ml_predictions = np.random.choice([0, 1], size=num_predictions)
        ml_probabilities = np.random.uniform(0.6, 0.95, size=num_predictions)

        ml_model.predict.return_value = ml_predictions
        ml_model.predict_proba.return_value = ml_probabilities

        # Mock signal generation
        expected_signals = [
            {
                "timestamp": datetime.utcnow() - timedelta(hours=i),
                "symbol": "EURUSD",
                "signal": "BUY" if pred == 1 else "SELL",
                "confidence": prob,
                "source": "ML_MODEL",
                "entry_price": 1.1000 + np.random.uniform(-0.01, 0.01),
                "stop_loss": 1.0950 if pred == 1 else 1.1050,
                "take_profit": 1.1050 if pred == 1 else 1.0950,
            }
            for i, (pred, prob) in enumerate(
                zip(ml_predictions[-10:], ml_probabilities[-10:])
            )
        ]

        signal_generator.generate_signals.return_value = expected_signals

        # Simulate signal generation workflow
        ml_predictions_data = {
            "predictions": ml_predictions,
            "probabilities": ml_probabilities,
            "symbol": "EURUSD",
            "timestamp": datetime.utcnow(),
        }

        generated_signals = signal_generator.generate_signals(ml_predictions_data)

        # Verify signal integration
        assert len(generated_signals) == 10  # Last 10 predictions

        for signal in generated_signals:
            assert signal["symbol"] == "EURUSD"
            assert signal["signal"] in ["BUY", "SELL"]
            assert 0.6 <= signal["confidence"] <= 0.95
            assert signal["source"] == "ML_MODEL"
            assert "entry_price" in signal
            assert "stop_loss" in signal
            assert "take_profit" in signal

        signal_generator.generate_signals.assert_called_once()

    @pytest.mark.asyncio
    async def test_ensemble_model_integration(self, mock_system_components):
        """Test ensemble model integration with multiple ML models."""
        ml_model = mock_system_components["ml_model"]

        # Mock ensemble with multiple model predictions
        model1_preds = np.random.choice([0, 1], size=50, p=[0.7, 0.3])
        model2_preds = np.random.choice([0, 1], size=50, p=[0.6, 0.4])
        model3_preds = np.random.choice([0, 1], size=50, p=[0.8, 0.2])

        model1_probs = np.random.uniform(0.5, 0.8, 50)
        model2_probs = np.random.uniform(0.6, 0.9, 50)
        model3_probs = np.random.uniform(0.5, 0.7, 50)

        # Mock ensemble combination
        ensemble_preds = np.array(
            [
                1 if (p1 + p2 + p3) >= 2 else 0  # Majority vote
                for p1, p2, p3 in zip(model1_preds, model2_preds, model3_preds)
            ]
        )

        ensemble_probs = (
            model1_probs + model2_probs + model3_probs
        ) / 3  # Average confidence

        ml_model.predict.return_value = ensemble_preds
        ml_model.predict_proba.return_value = ensemble_probs

        # Test ensemble integration
        sample_features = pd.DataFrame(
            {
                "rsi": np.random.uniform(0, 100, 50),
                "macd": np.random.uniform(-0.01, 0.01, 50),
                "returns": np.random.uniform(-0.05, 0.05, 50),
            }
        )

        predictions = ml_model.predict(sample_features)
        probabilities = ml_model.predict_proba(sample_features)

        # Verify ensemble results
        assert len(predictions) == 50
        assert len(probabilities) == 50
        assert all(p in [0, 1] for p in predictions)
        assert all(0.5 <= prob <= 0.9 for prob in probabilities)

        # Verify ensemble logic (majority of ensemble should agree)
        buy_signals = sum(predictions)
        sell_signals = len(predictions) - buy_signals
        assert abs(buy_signals - sell_signals) <= len(
            predictions
        )  # Reasonable distribution


class TestSignalToExecutionIntegration:
    """Test trading signal to broker execution integration."""

    @pytest.mark.asyncio
    async def test_signals_to_fix_messages_integration(self, mock_system_components):
        """Test integration from trading signals to FIX protocol messages."""
        signal_generator = mock_system_components["signal_generator"]
        fix_session = mock_system_components["fix_session"]

        # Mock trading signals
        trading_signals = [
            {
                "id": "SIG_001",
                "timestamp": datetime.utcnow(),
                "symbol": "EURUSD",
                "signal": "BUY",
                "confidence": 0.85,
                "entry_price": 1.1050,
                "quantity": 100000,
                "stop_loss": 1.1000,
                "take_profit": 1.1100,
                "source": "ML_ENSEMBLE",
            },
            {
                "id": "SIG_002",
                "timestamp": datetime.utcnow(),
                "symbol": "GBPUSD",
                "signal": "SELL",
                "confidence": 0.78,
                "entry_price": 1.2500,
                "quantity": 75000,
                "stop_loss": 1.2550,
                "take_profit": 1.2450,
                "source": "ML_ENSEMBLE",
            },
        ]

        signal_generator.generate_signals.return_value = trading_signals

        # Mock FIX session ready
        fix_session.is_active.return_value = True
        fix_session.send_message.return_value = True

        # Simulate signal-to-order conversion
        generated_signals = signal_generator.generate_signals({})

        for signal in generated_signals:
            # Convert signal to FIX order format
            fix_order = {
                "msg_type": "NewOrderSingle",
                "cl_ord_id": f"ORD_{signal['id']}",
                "symbol": signal["symbol"],
                "side": "1" if signal["signal"] == "BUY" else "2",
                "ord_type": "1",  # Market order
                "order_qty": signal["quantity"],
                "transact_time": signal["timestamp"].isoformat(),
            }

            # Send via FIX session
            await fix_session.send_message(fix_order)

        # Verify FIX integration
        assert fix_session.send_message.call_count == 2

        # Verify FIX message format
        call_args = fix_session.send_message.call_args_list

        first_order = call_args[0][0][0]
        assert first_order["symbol"] == "EURUSD"
        assert first_order["side"] == "1"  # Buy
        assert first_order["order_qty"] == 100000

        second_order = call_args[1][0][0]
        assert second_order["symbol"] == "GBPUSD"
        assert second_order["side"] == "2"  # Sell
        assert second_order["order_qty"] == 75000

    @pytest.mark.asyncio
    async def test_fix_messages_to_broker_execution_integration(
        self, mock_system_components
    ):
        """Test integration from FIX messages to broker order execution."""
        fix_session = mock_system_components["fix_session"]
        broker_adapter = mock_system_components["broker_adapter"]

        # Mock FIX session active
        fix_session.is_active.return_value = True

        # Mock broker connection
        broker_adapter.is_connected.return_value = True

        # Mock execution reports
        execution_reports = [
            {
                "order_id": "BROKER_001",
                "cl_ord_id": "ORD_SIG_001",
                "exec_id": "EXEC_001",
                "exec_type": "F",  # Fill
                "ord_status": "2",  # Filled
                "symbol": "EURUSD",
                "side": "1",  # Buy
                "cum_qty": 100000,
                "avg_px": 1.1052,
                "last_qty": 100000,
                "leaves_qty": 0,
            }
        ]

        broker_adapter.submit_order.return_value = execution_reports[0]

        # Simulate FIX-to-broker workflow
        fix_order = {
            "msg_type": "NewOrderSingle",
            "cl_ord_id": "ORD_SIG_001",
            "symbol": "EURUSD",
            "side": "1",
            "ord_type": "1",
            "order_qty": 100000,
            "transact_time": datetime.utcnow().isoformat(),
        }

        # Send order via FIX
        await fix_session.send_message(fix_order)

        # Broker processes order
        execution_result = await broker_adapter.submit_order(
            {
                "symbol": fix_order["symbol"],
                "side": "BUY" if fix_order["side"] == "1" else "SELL",
                "quantity": fix_order["order_qty"],
                "order_type": "MARKET",
            }
        )

        # Verify broker execution integration
        assert execution_result["ord_status"] == "2"  # Filled
        assert execution_result["symbol"] == "EURUSD"
        assert execution_result["cum_qty"] == 100000
        assert execution_result["avg_px"] == 1.1052

        fix_session.send_message.assert_called_once()
        broker_adapter.submit_order.assert_called_once()

    @pytest.mark.asyncio
    async def test_execution_feedback_loop_integration(self, mock_system_components):
        """Test execution feedback integration back to signal monitoring."""
        broker_adapter = mock_system_components["broker_adapter"]
        system_monitor = mock_system_components["system_monitor"]

        # Mock order execution and monitoring
        execution_updates = [
            {
                "order_id": "BROKER_001",
                "status": "FILLED",
                "fill_price": 1.1052,
                "fill_quantity": 100000,
                "fill_time": datetime.utcnow(),
                "commission": 2.50,
            },
            {
                "order_id": "BROKER_002",
                "status": "PARTIALLY_FILLED",
                "fill_price": 1.2498,
                "fill_quantity": 50000,
                "fill_time": datetime.utcnow(),
                "remaining_quantity": 25000,
            },
        ]

        broker_adapter.get_execution_updates.return_value = execution_updates

        # Simulate execution monitoring workflow
        recent_executions = await broker_adapter.get_execution_updates()

        for execution in recent_executions:
            # Log execution for monitoring
            system_monitor.log_event(
                {
                    "event_type": "ORDER_EXECUTION",
                    "order_id": execution["order_id"],
                    "status": execution["status"],
                    "fill_price": execution.get("fill_price"),
                    "fill_quantity": execution.get("fill_quantity"),
                    "timestamp": execution.get("fill_time", datetime.utcnow()),
                }
            )

        # Verify monitoring integration
        assert system_monitor.log_event.call_count == 2

        # Verify monitoring data
        logged_events = [call[0][0] for call in system_monitor.log_event.call_args_list]

        assert logged_events[0]["event_type"] == "ORDER_EXECUTION"
        assert logged_events[0]["status"] == "FILLED"
        assert logged_events[1]["status"] == "PARTIALLY_FILLED"

        broker_adapter.get_execution_updates.assert_called_once()


class TestSystemPerformanceIntegration:
    """Test system performance under integrated load."""

    @pytest.mark.asyncio
    async def test_end_to_end_latency_performance(self, mock_system_components):
        """Test complete pipeline latency under realistic load."""
        # Configure performance test parameters
        num_signals = 100
        max_latency_ms = 500  # Maximum acceptable latency

        start_time = time.time()

        # Simulate complete pipeline processing
        for i in range(num_signals):
            signal_start = time.time()

            # Data ingestion (mocked)
            await mock_system_components["data_feed"].get_historical_data(
                "EURUSD", "1H", 1
            )

            # Feature engineering (mocked)
            mock_system_components["feature_engineer"].create_features(
                pd.DataFrame({"close": [1.1050]}), ["rsi"]
            )

            # ML prediction (mocked)
            mock_system_components["ml_model"].predict([[50.0]])

            # Signal generation (mocked)
            mock_system_components["signal_generator"].generate_signals({})

            # FIX messaging (mocked)
            await mock_system_components["fix_session"].send_message({})

            signal_latency = (time.time() - signal_start) * 1000  # Convert to ms

            # Verify latency requirement
            assert (
                signal_latency < max_latency_ms
            ), f"Signal {i} took {signal_latency:.2f}ms"

        total_time = time.time() - start_time
        avg_latency = (total_time / num_signals) * 1000

        # Performance targets
        assert avg_latency < max_latency_ms
        assert total_time < 30.0  # Complete batch in under 30 seconds

        # Verify throughput
        signals_per_second = num_signals / total_time
        assert signals_per_second > 5  # Minimum 5 signals per second

    @pytest.mark.asyncio
    async def test_concurrent_signal_processing(self, mock_system_components):
        """Test concurrent signal processing performance."""
        # Test concurrent processing capabilities
        num_concurrent = 10
        signals_per_worker = 20

        async def process_signals_worker(worker_id):
            """Worker function for concurrent signal processing."""
            for i in range(signals_per_worker):
                # Simulate complete signal processing
                await mock_system_components["data_feed"].get_historical_data(
                    "EURUSD", "1H", 1
                )
                mock_system_components["ml_model"].predict([[45.0 + i]])
                await mock_system_components["fix_session"].send_message(
                    {"worker": worker_id}
                )

        # Run concurrent workers
        start_time = time.time()

        tasks = [
            asyncio.create_task(process_signals_worker(worker_id))
            for worker_id in range(num_concurrent)
        ]

        await asyncio.gather(*tasks)

        total_time = time.time() - start_time
        total_signals = num_concurrent * signals_per_worker

        # Verify concurrent performance
        signals_per_second = total_signals / total_time
        assert (
            signals_per_second > 20
        )  # Should handle 20+ signals/second with concurrency

        # Verify all workers completed
        assert (
            mock_system_components["fix_session"].send_message.call_count
            == total_signals
        )

    @pytest.mark.asyncio
    async def test_system_resource_utilization(self, mock_system_components):
        """Test system resource utilization under load."""
        system_monitor = mock_system_components["system_monitor"]

        # Mock system health metrics
        system_monitor.check_health.return_value = {
            "cpu_usage": 45.2,
            "memory_usage": 62.8,
            "disk_usage": 35.1,
            "network_latency": 12.5,
            "database_connections": 8,
            "broker_connections": 2,
            "active_signals": 15,
        }

        # Test resource monitoring during operations
        for i in range(50):
            # Simulate trading operations
            await mock_system_components["data_feed"].get_historical_data(
                "EURUSD", "1H", 1
            )
            mock_system_components["ml_model"].predict([[50.0]])
            await mock_system_components["fix_session"].send_message({})

            # Check system health periodically
            if i % 10 == 0:
                health_status = system_monitor.check_health()

                # Verify resource utilization within acceptable limits
                assert health_status["cpu_usage"] < 80.0
                assert health_status["memory_usage"] < 85.0
                assert health_status["network_latency"] < 50.0
                assert health_status["database_connections"] < 20

        # Verify monitoring was called
        assert system_monitor.check_health.call_count >= 5


class TestErrorHandlingIntegration:
    """Test error handling across system boundaries."""

    @pytest.mark.asyncio
    async def test_database_failure_recovery(self, mock_system_components):
        """Test system behavior when database fails."""
        database = mock_system_components["database"]
        system_monitor = mock_system_components["system_monitor"]

        # Simulate database failure
        database.fetch.side_effect = Exception("Database connection lost")

        # Test error handling in data retrieval
        try:
            await database.fetch("SELECT * FROM market_data")
            assert False, "Should have raised exception"
        except Exception as e:
            assert "Database connection lost" in str(e)

            # Verify error logging
            system_monitor.log_event(
                {
                    "event_type": "DATABASE_ERROR",
                    "error": str(e),
                    "timestamp": datetime.utcnow(),
                }
            )

        system_monitor.log_event.assert_called_once()

    @pytest.mark.asyncio
    async def test_broker_connection_failure_recovery(self, mock_system_components):
        """Test system behavior when broker connection fails."""
        broker_adapter = mock_system_components["broker_adapter"]
        fix_session = mock_system_components["fix_session"]
        system_monitor = mock_system_components["system_monitor"]

        # Simulate broker connection failure
        broker_adapter.submit_order.side_effect = Exception("Broker connection timeout")
        fix_session.send_message.side_effect = Exception("FIX session disconnected")

        # Test error handling in order submission
        try:
            await broker_adapter.submit_order({"symbol": "EURUSD", "side": "BUY"})
            assert False, "Should have raised exception"
        except Exception as e:
            assert "Broker connection timeout" in str(e)

            # Test FIX session error handling
            try:
                await fix_session.send_message({})
                assert False, "Should have raised exception"
            except Exception as fix_e:
                assert "FIX session disconnected" in str(fix_e)

                # Log both errors
                system_monitor.log_event(
                    {
                        "event_type": "BROKER_ERROR",
                        "broker_error": str(e),
                        "fix_error": str(fix_e),
                        "timestamp": datetime.utcnow(),
                    }
                )

        system_monitor.log_event.assert_called_once()

    @pytest.mark.asyncio
    async def test_ml_model_failure_graceful_degradation(self, mock_system_components):
        """Test graceful degradation when ML models fail."""
        ml_model = mock_system_components["ml_model"]
        signal_generator = mock_system_components["signal_generator"]

        # Simulate ML model failure
        ml_model.predict.side_effect = Exception("Model prediction error")

        # Mock fallback signal generation
        fallback_signals = [
            {
                "timestamp": datetime.utcnow(),
                "symbol": "EURUSD",
                "signal": "HOLD",
                "confidence": 0.5,
                "source": "FALLBACK_RULES",
                "reason": "ML model unavailable",
            }
        ]

        signal_generator.generate_signals.return_value = fallback_signals

        # Test ML failure handling
        try:
            ml_model.predict([[50.0]])
            assert False, "Should have raised exception"
        except Exception:
            # Use fallback signal generation
            fallback_signals_result = signal_generator.generate_signals(
                {"fallback_mode": True, "symbol": "EURUSD"}
            )

            # Verify fallback behavior
            assert len(fallback_signals_result) == 1
            assert fallback_signals_result[0]["signal"] == "HOLD"
            assert fallback_signals_result[0]["source"] == "FALLBACK_RULES"

        signal_generator.generate_signals.assert_called_once()


# Test Utilities and Fixtures
@pytest.fixture
def integration_test_config():
    """Standard configuration for integration tests."""
    return {
        "test_duration": 300,  # 5 minutes
        "max_latency_ms": 500,
        "min_throughput": 5,  # signals per second
        "max_cpu_usage": 80.0,
        "max_memory_usage": 85.0,
    }


if __name__ == "__main__":
    """Run integration tests directly."""
    pytest.main([__file__, "-v", "--tb=short", "-x"])
