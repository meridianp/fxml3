"""Real-Time System Integration Tests for Live Trading Scenarios.

This module provides comprehensive integration testing for real-time trading operations,
focusing on WebSocket streams, live data processing, and concurrent system behavior
under production-like conditions.

Real-Time Integration Test Coverage:
- WebSocket Market Data Stream Processing
- Real-Time Signal Generation and Order Routing
- Concurrent Multi-Symbol Trading Operations
- Live Risk Management and Position Monitoring
- System Health Monitoring Under Load
- Market Session Transition Handling

Following real-time system testing methodology with focus on latency and reliability.
"""

import asyncio
import json
import logging
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from typing import Any, AsyncGenerator, Dict, List, Optional
from unittest.mock import AsyncMock, MagicMock, call, patch

import numpy as np
import pandas as pd
import pytest
import websockets

# Real-Time System Components
from fxml4.api.websocket_market_data import WebSocketMarketDataStreamer
from fxml4.brokers.adapters.realtime_adapter import RealTimeBrokerAdapter
from fxml4.data_engineering.live_data_handler import LiveDataHandler
from fxml4.features.realtime_features import RealTimeFeatureEngine
from fxml4.fix.session_manager import FIXSession, SessionState
from fxml4.ml.realtime_inference import RealTimeMLInference
from fxml4.monitoring.realtime_monitor import RealTimeSystemMonitor
from fxml4.risk_management.live import LiveRiskManager
from fxml4.strategy.realtime_signal_generator import RealTimeSignalGenerator


class TestWebSocketMarketDataIntegration:
    """Test WebSocket market data streaming integration."""

    @pytest.fixture
    async def mock_websocket_server(self):
        """Create mock WebSocket server for testing."""

        async def mock_market_data_handler(websocket, path):
            """Mock market data stream."""
            symbols = ["EURUSD", "GBPUSD", "USDJPY", "USDCHF"]

            try:
                while True:
                    for symbol in symbols:
                        # Generate realistic tick data
                        base_prices = {
                            "EURUSD": 1.1050,
                            "GBPUSD": 1.2500,
                            "USDJPY": 108.50,
                            "USDCHF": 0.9200,
                        }

                        price = base_prices[symbol] + np.random.uniform(-0.01, 0.01)

                        tick_data = {
                            "symbol": symbol,
                            "bid": round(price - 0.0002, 5),
                            "ask": round(price + 0.0002, 5),
                            "timestamp": datetime.utcnow().isoformat(),
                            "volume": np.random.randint(1000, 50000),
                        }

                        await websocket.send(json.dumps(tick_data))
                        await asyncio.sleep(0.1)  # 10 ticks per second per symbol

            except websockets.exceptions.ConnectionClosed:
                pass

        # Start mock server
        server = await websockets.serve(mock_market_data_handler, "localhost", 8765)
        yield server
        server.close()
        await server.wait_closed()

    @pytest.fixture
    def mock_realtime_components(self):
        """Create mock real-time system components."""
        components = {}

        # Mock WebSocket streamer
        components["ws_streamer"] = AsyncMock(spec=WebSocketMarketDataStreamer)
        components["ws_streamer"].connect = AsyncMock()
        components["ws_streamer"].subscribe = AsyncMock()
        components["ws_streamer"].get_latest_ticks = AsyncMock()

        # Mock live data handler
        components["live_data_handler"] = AsyncMock(spec=LiveDataHandler)
        components["live_data_handler"].process_tick = AsyncMock()
        components["live_data_handler"].get_current_candle = AsyncMock()

        # Mock real-time feature engine
        components["rt_feature_engine"] = MagicMock(spec=RealTimeFeatureEngine)
        components["rt_feature_engine"].update_features = MagicMock()
        components["rt_feature_engine"].get_current_features = MagicMock()

        # Mock real-time ML inference
        components["rt_ml_inference"] = AsyncMock(spec=RealTimeMLInference)
        components["rt_ml_inference"].predict_live = AsyncMock()
        components["rt_ml_inference"].update_model_cache = AsyncMock()

        # Mock real-time signal generator
        components["rt_signal_gen"] = AsyncMock(spec=RealTimeSignalGenerator)
        components["rt_signal_gen"].process_live_signal = AsyncMock()
        components["rt_signal_gen"].get_active_signals = AsyncMock()

        # Mock real-time broker adapter
        components["rt_broker"] = AsyncMock(spec=RealTimeBrokerAdapter)
        components["rt_broker"].stream_executions = AsyncMock()
        components["rt_broker"].submit_order_async = AsyncMock()

        # Mock live risk manager
        components["live_risk"] = AsyncMock(spec=LiveRiskManager)
        components["live_risk"].validate_order_realtime = AsyncMock()
        components["live_risk"].monitor_positions = AsyncMock()

        return components

    @pytest.mark.asyncio
    async def test_websocket_data_stream_integration(
        self, mock_websocket_server, mock_realtime_components
    ):
        """Test WebSocket market data streaming and processing."""
        ws_streamer = mock_realtime_components["ws_streamer"]
        live_data_handler = mock_realtime_components["live_data_handler"]

        # Mock WebSocket connection and data reception
        mock_ticks = [
            {
                "symbol": "EURUSD",
                "bid": 1.1048,
                "ask": 1.1050,
                "timestamp": datetime.utcnow().isoformat(),
                "volume": 25000,
            },
            {
                "symbol": "GBPUSD",
                "bid": 1.2498,
                "ask": 1.2502,
                "timestamp": datetime.utcnow().isoformat(),
                "volume": 30000,
            },
        ]

        ws_streamer.get_latest_ticks.return_value = mock_ticks

        # Mock live data processing
        processed_candles = {}
        for tick in mock_ticks:
            candle = {
                "symbol": tick["symbol"],
                "open": tick["bid"],
                "high": tick["ask"],
                "low": tick["bid"],
                "close": (tick["bid"] + tick["ask"]) / 2,
                "volume": tick["volume"],
                "timestamp": tick["timestamp"],
            }
            processed_candles[tick["symbol"]] = candle

        live_data_handler.get_current_candle.side_effect = (
            lambda symbol: processed_candles.get(symbol)
        )

        # Test WebSocket integration workflow
        await ws_streamer.connect("ws://localhost:8765")
        await ws_streamer.subscribe(["EURUSD", "GBPUSD"])

        # Process incoming ticks
        latest_ticks = await ws_streamer.get_latest_ticks()

        for tick in latest_ticks:
            await live_data_handler.process_tick(tick)

        # Verify integration
        assert len(latest_ticks) == 2
        assert all("symbol" in tick for tick in latest_ticks)
        assert all("bid" in tick and "ask" in tick for tick in latest_ticks)

        ws_streamer.connect.assert_called_once()
        ws_streamer.subscribe.assert_called_once_with(["EURUSD", "GBPUSD"])
        assert live_data_handler.process_tick.call_count == 2

    @pytest.mark.asyncio
    async def test_realtime_feature_computation_integration(
        self, mock_realtime_components
    ):
        """Test real-time feature computation from live data."""
        live_data_handler = mock_realtime_components["live_data_handler"]
        rt_feature_engine = mock_realtime_components["rt_feature_engine"]

        # Mock current market data
        current_candles = {
            "EURUSD": {
                "open": 1.1045,
                "high": 1.1055,
                "low": 1.1040,
                "close": 1.1052,
                "volume": 125000,
                "timestamp": datetime.utcnow(),
            }
        }

        live_data_handler.get_current_candle.return_value = current_candles["EURUSD"]

        # Mock feature computation
        computed_features = {
            "rsi": 55.2,
            "macd": 0.0012,
            "bb_upper": 1.1065,
            "bb_lower": 1.1035,
            "ema_20": 1.1048,
            "volume_ma": 115000,
            "volatility": 0.0008,
        }

        rt_feature_engine.get_current_features.return_value = computed_features

        # Test feature computation integration
        current_candle = await live_data_handler.get_current_candle("EURUSD")

        # Update features with new candle
        rt_feature_engine.update_features("EURUSD", current_candle)

        # Get computed features
        features = rt_feature_engine.get_current_features("EURUSD")

        # Verify feature integration
        assert features is not None
        assert len(features) == 7
        assert "rsi" in features
        assert "macd" in features
        assert "bb_upper" in features
        assert 0 <= features["rsi"] <= 100
        assert abs(features["macd"]) < 0.01  # Reasonable MACD value

        rt_feature_engine.update_features.assert_called_once_with(
            "EURUSD", current_candle
        )
        rt_feature_engine.get_current_features.assert_called_once_with("EURUSD")

    @pytest.mark.asyncio
    async def test_realtime_ml_inference_integration(self, mock_realtime_components):
        """Test real-time ML inference integration with live features."""
        rt_feature_engine = mock_realtime_components["rt_feature_engine"]
        rt_ml_inference = mock_realtime_components["rt_ml_inference"]

        # Mock current features
        live_features = {
            "EURUSD": {
                "rsi": 65.8,
                "macd": 0.0015,
                "bb_position": 0.7,
                "volume_ratio": 1.2,
                "price_momentum": 0.0008,
            }
        }

        rt_feature_engine.get_current_features.return_value = live_features["EURUSD"]

        # Mock ML predictions
        ml_predictions = {
            "prediction": 1,  # Buy signal
            "probability": 0.78,
            "confidence": 0.82,
            "model_version": "v2.1",
            "timestamp": datetime.utcnow(),
        }

        rt_ml_inference.predict_live.return_value = ml_predictions

        # Test real-time ML integration
        current_features = rt_feature_engine.get_current_features("EURUSD")

        # Generate live prediction
        prediction_result = await rt_ml_inference.predict_live(
            "EURUSD", current_features
        )

        # Verify ML integration
        assert prediction_result is not None
        assert prediction_result["prediction"] in [0, 1]
        assert 0.5 <= prediction_result["probability"] <= 1.0
        assert 0.5 <= prediction_result["confidence"] <= 1.0
        assert "model_version" in prediction_result
        assert isinstance(prediction_result["timestamp"], datetime)

        rt_ml_inference.predict_live.assert_called_once_with("EURUSD", current_features)

    @pytest.mark.asyncio
    async def test_realtime_signal_generation_integration(
        self, mock_realtime_components
    ):
        """Test real-time signal generation from ML predictions."""
        rt_ml_inference = mock_realtime_components["rt_ml_inference"]
        rt_signal_gen = mock_realtime_components["rt_signal_gen"]

        # Mock ML prediction
        ml_prediction = {
            "prediction": 1,  # Buy
            "probability": 0.85,
            "confidence": 0.88,
            "symbol": "EURUSD",
            "timestamp": datetime.utcnow(),
        }

        rt_ml_inference.predict_live.return_value = ml_prediction

        # Mock signal generation
        generated_signal = {
            "signal_id": "RT_SIG_001",
            "symbol": "EURUSD",
            "action": "BUY",
            "confidence": 0.88,
            "entry_price": 1.1052,
            "stop_loss": 1.1027,
            "take_profit": 1.1102,
            "quantity": 100000,
            "timestamp": datetime.utcnow(),
            "source": "REALTIME_ML",
            "model_confidence": 0.85,
        }

        rt_signal_gen.process_live_signal.return_value = generated_signal

        # Test signal generation integration
        prediction = await rt_ml_inference.predict_live("EURUSD", {})

        # Process prediction into trading signal
        signal = await rt_signal_gen.process_live_signal(prediction)

        # Verify signal integration
        assert signal is not None
        assert signal["symbol"] == "EURUSD"
        assert signal["action"] == "BUY"
        assert signal["confidence"] == 0.88
        assert signal["entry_price"] > 0
        assert signal["stop_loss"] < signal["entry_price"]  # Valid stop loss for buy
        assert (
            signal["take_profit"] > signal["entry_price"]
        )  # Valid take profit for buy
        assert signal["source"] == "REALTIME_ML"

        rt_signal_gen.process_live_signal.assert_called_once_with(prediction)


class TestConcurrentTradingOperations:
    """Test concurrent trading operations across multiple symbols."""

    @pytest.fixture
    def trading_symbols(self):
        """Define trading symbols for concurrent testing."""
        return ["EURUSD", "GBPUSD", "USDJPY", "USDCHF", "AUDUSD"]

    @pytest.mark.asyncio
    async def test_multi_symbol_concurrent_processing(
        self, mock_realtime_components, trading_symbols
    ):
        """Test concurrent processing across multiple trading symbols."""
        rt_feature_engine = mock_realtime_components["rt_feature_engine"]
        rt_ml_inference = mock_realtime_components["rt_ml_inference"]
        rt_signal_gen = mock_realtime_components["rt_signal_gen"]

        # Mock features for all symbols
        symbol_features = {
            symbol: {
                "rsi": np.random.uniform(30, 70),
                "macd": np.random.uniform(-0.01, 0.01),
                "bb_position": np.random.uniform(0, 1),
            }
            for symbol in trading_symbols
        }

        rt_feature_engine.get_current_features.side_effect = (
            lambda symbol: symbol_features[symbol]
        )

        # Mock ML predictions for all symbols
        symbol_predictions = {
            symbol: {
                "prediction": np.random.choice([0, 1]),
                "probability": np.random.uniform(0.6, 0.9),
                "confidence": np.random.uniform(0.7, 0.95),
                "symbol": symbol,
            }
            for symbol in trading_symbols
        }

        rt_ml_inference.predict_live.side_effect = (
            lambda symbol, features: symbol_predictions[symbol]
        )

        # Mock signal generation
        rt_signal_gen.process_live_signal.side_effect = lambda pred: {
            "signal_id": f"SIG_{pred['symbol']}_{int(time.time())}",
            "symbol": pred["symbol"],
            "action": "BUY" if pred["prediction"] == 1 else "SELL",
            "confidence": pred["confidence"],
        }

        async def process_symbol(symbol):
            """Process single symbol concurrently."""
            features = rt_feature_engine.get_current_features(symbol)
            prediction = await rt_ml_inference.predict_live(symbol, features)
            signal = await rt_signal_gen.process_live_signal(prediction)
            return signal

        # Test concurrent processing
        start_time = time.time()

        # Process all symbols concurrently
        tasks = [
            asyncio.create_task(process_symbol(symbol)) for symbol in trading_symbols
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        processing_time = time.time() - start_time

        # Verify concurrent processing results
        assert len(results) == len(trading_symbols)
        assert all(not isinstance(result, Exception) for result in results)

        # Verify all symbols processed
        processed_symbols = {result["symbol"] for result in results}
        assert processed_symbols == set(trading_symbols)

        # Verify concurrent performance (should be faster than sequential)
        assert processing_time < 2.0  # Should complete in under 2 seconds

        # Verify all components called for each symbol
        assert rt_feature_engine.get_current_features.call_count == len(trading_symbols)
        assert rt_ml_inference.predict_live.call_count == len(trading_symbols)
        assert rt_signal_gen.process_live_signal.call_count == len(trading_symbols)

    @pytest.mark.asyncio
    async def test_concurrent_order_execution_integration(
        self, mock_realtime_components, trading_symbols
    ):
        """Test concurrent order execution across multiple symbols."""
        rt_broker = mock_realtime_components["rt_broker"]
        live_risk = mock_realtime_components["live_risk"]

        # Mock risk validation
        live_risk.validate_order_realtime.return_value = True

        # Mock order execution results
        execution_results = {}
        for i, symbol in enumerate(trading_symbols):
            execution_results[symbol] = {
                "order_id": f"ORDER_{symbol}_{i}",
                "status": "FILLED",
                "fill_price": 1.1050 + (i * 0.01),
                "fill_quantity": 100000,
                "commission": 2.50,
            }

        rt_broker.submit_order_async.side_effect = lambda order: execution_results[
            order["symbol"]
        ]

        # Create orders for concurrent execution
        orders = [
            {
                "symbol": symbol,
                "side": "BUY" if i % 2 == 0 else "SELL",
                "quantity": 100000,
                "order_type": "MARKET",
                "timestamp": datetime.utcnow(),
            }
            for i, symbol in enumerate(trading_symbols)
        ]

        async def execute_order(order):
            """Execute single order with risk validation."""
            # Validate order
            is_valid = await live_risk.validate_order_realtime(order)
            if not is_valid:
                return {"error": "Risk validation failed"}

            # Execute order
            result = await rt_broker.submit_order_async(order)
            return result

        # Test concurrent order execution
        start_time = time.time()

        tasks = [asyncio.create_task(execute_order(order)) for order in orders]
        execution_results_list = await asyncio.gather(*tasks)

        execution_time = time.time() - start_time

        # Verify concurrent execution
        assert len(execution_results_list) == len(trading_symbols)
        assert all("error" not in result for result in execution_results_list)
        assert all(result["status"] == "FILLED" for result in execution_results_list)

        # Verify performance
        assert execution_time < 3.0  # Should complete in under 3 seconds

        # Verify risk validation called for all orders
        assert live_risk.validate_order_realtime.call_count == len(trading_symbols)
        assert rt_broker.submit_order_async.call_count == len(trading_symbols)

    @pytest.mark.asyncio
    async def test_position_monitoring_concurrent_updates(
        self, mock_realtime_components, trading_symbols
    ):
        """Test concurrent position monitoring and updates."""
        rt_broker = mock_realtime_components["rt_broker"]
        live_risk = mock_realtime_components["live_risk"]

        # Mock current positions for all symbols
        current_positions = {
            symbol: {
                "symbol": symbol,
                "side": "LONG" if i % 2 == 0 else "SHORT",
                "quantity": 100000 + (i * 25000),
                "avg_price": 1.1000 + (i * 0.01),
                "unrealized_pnl": np.random.uniform(-500, 1000),
                "margin_used": 2000 + (i * 500),
            }
            for i, symbol in enumerate(trading_symbols)
        }

        rt_broker.get_positions.return_value = list(current_positions.values())

        # Mock position monitoring
        live_risk.monitor_positions.side_effect = lambda positions: {
            "total_exposure": sum(pos["quantity"] for pos in positions),
            "total_margin": sum(pos["margin_used"] for pos in positions),
            "net_pnl": sum(pos["unrealized_pnl"] for pos in positions),
            "risk_level": (
                "NORMAL"
                if sum(pos["unrealized_pnl"] for pos in positions) > -2000
                else "HIGH"
            ),
        }

        async def monitor_symbol_positions():
            """Monitor positions concurrently."""
            positions = await rt_broker.get_positions()
            risk_status = await live_risk.monitor_positions(positions)
            return risk_status

        # Test concurrent position monitoring
        monitoring_tasks = [
            asyncio.create_task(monitor_symbol_positions())
            for _ in range(5)  # Multiple concurrent monitoring tasks
        ]

        monitoring_results = await asyncio.gather(*monitoring_tasks)

        # Verify concurrent monitoring
        assert len(monitoring_results) == 5
        assert all("total_exposure" in result for result in monitoring_results)
        assert all("risk_level" in result for result in monitoring_results)

        # Verify consistent results across concurrent calls
        first_result = monitoring_results[0]
        assert all(
            result["total_exposure"] == first_result["total_exposure"]
            for result in monitoring_results
        )


class TestSystemHealthMonitoring:
    """Test system health monitoring during live operations."""

    @pytest.fixture
    def mock_system_monitor(self):
        """Create mock system monitor."""
        monitor = MagicMock(spec=RealTimeSystemMonitor)

        # Mock health metrics
        monitor.get_system_metrics.return_value = {
            "cpu_usage": 45.2,
            "memory_usage": 67.8,
            "disk_io": 12.5,
            "network_latency": 8.3,
            "active_connections": 15,
            "message_queue_depth": 23,
            "error_rate": 0.02,
        }

        # Mock component health
        monitor.check_component_health.return_value = {
            "database": "HEALTHY",
            "broker_connections": "HEALTHY",
            "ml_models": "HEALTHY",
            "websocket_streams": "HEALTHY",
            "fix_sessions": "HEALTHY",
        }

        return monitor

    @pytest.mark.asyncio
    async def test_system_health_monitoring_integration(
        self, mock_realtime_components, mock_system_monitor
    ):
        """Test integrated system health monitoring during operations."""

        # Simulate trading operations
        async def simulate_trading_load():
            """Simulate realistic trading load."""
            for i in range(50):
                # Simulate data processing
                await mock_realtime_components["live_data_handler"].process_tick({})

                # Simulate ML inference
                await mock_realtime_components["rt_ml_inference"].predict_live(
                    "EURUSD", {}
                )

                # Simulate order execution
                await mock_realtime_components["rt_broker"].submit_order_async({})

                # Small delay to simulate realistic timing
                await asyncio.sleep(0.01)

        # Run trading simulation with health monitoring
        trading_task = asyncio.create_task(simulate_trading_load())

        # Monitor system health during operations
        health_checks = []
        for i in range(10):
            await asyncio.sleep(0.05)  # Check every 50ms

            system_metrics = mock_system_monitor.get_system_metrics()
            component_health = mock_system_monitor.check_component_health()

            health_checks.append(
                {
                    "timestamp": datetime.utcnow(),
                    "metrics": system_metrics,
                    "components": component_health,
                }
            )

        # Wait for trading simulation to complete
        await trading_task

        # Verify health monitoring results
        assert len(health_checks) == 10

        for check in health_checks:
            metrics = check["metrics"]
            components = check["components"]

            # Verify system metrics within acceptable ranges
            assert 0 <= metrics["cpu_usage"] <= 100
            assert 0 <= metrics["memory_usage"] <= 100
            assert metrics["network_latency"] < 100  # Under 100ms
            assert metrics["error_rate"] < 0.1  # Under 10%

            # Verify all components healthy
            assert all(status == "HEALTHY" for status in components.values())

        # Verify monitoring was called regularly
        assert mock_system_monitor.get_system_metrics.call_count == 10
        assert mock_system_monitor.check_component_health.call_count == 10

    @pytest.mark.asyncio
    async def test_error_detection_and_alerting(self, mock_system_monitor):
        """Test error detection and alerting during system monitoring."""

        # Mock degraded system state
        degraded_metrics = {
            "cpu_usage": 95.5,  # High CPU
            "memory_usage": 88.2,  # High memory
            "network_latency": 250.0,  # High latency
            "error_rate": 0.15,  # High error rate
        }

        unhealthy_components = {
            "database": "DEGRADED",
            "broker_connections": "HEALTHY",
            "ml_models": "ERROR",
            "websocket_streams": "HEALTHY",
            "fix_sessions": "DEGRADED",
        }

        mock_system_monitor.get_system_metrics.return_value = degraded_metrics
        mock_system_monitor.check_component_health.return_value = unhealthy_components

        # Mock alert generation
        expected_alerts = [
            {"type": "CPU_HIGH", "value": 95.5, "threshold": 80.0},
            {"type": "MEMORY_HIGH", "value": 88.2, "threshold": 80.0},
            {"type": "LATENCY_HIGH", "value": 250.0, "threshold": 100.0},
            {"type": "ERROR_RATE_HIGH", "value": 0.15, "threshold": 0.05},
            {"type": "COMPONENT_ERROR", "component": "ml_models", "status": "ERROR"},
            {
                "type": "COMPONENT_DEGRADED",
                "component": "database",
                "status": "DEGRADED",
            },
        ]

        mock_system_monitor.generate_alerts.return_value = expected_alerts

        # Test error detection
        system_metrics = mock_system_monitor.get_system_metrics()
        component_health = mock_system_monitor.check_component_health()

        # Generate alerts based on system state
        alerts = mock_system_monitor.generate_alerts(system_metrics, component_health)

        # Verify error detection and alerting
        assert len(alerts) >= 4  # Should have multiple alerts

        alert_types = [alert["type"] for alert in alerts]
        assert "CPU_HIGH" in alert_types
        assert "MEMORY_HIGH" in alert_types
        assert "LATENCY_HIGH" in alert_types
        assert "ERROR_RATE_HIGH" in alert_types

        # Verify component-specific alerts
        component_alerts = [alert for alert in alerts if "COMPONENT" in alert["type"]]
        assert len(component_alerts) >= 2

        mock_system_monitor.generate_alerts.assert_called_once()


class TestMarketSessionTransitions:
    """Test system behavior during market session transitions."""

    @pytest.fixture
    def market_sessions(self):
        """Define market session information."""
        return {
            "london_open": {"time": "08:00", "timezone": "Europe/London"},
            "london_close": {"time": "17:00", "timezone": "Europe/London"},
            "ny_open": {"time": "08:00", "timezone": "America/New_York"},
            "ny_close": {"time": "17:00", "timezone": "America/New_York"},
            "tokyo_open": {"time": "08:00", "timezone": "Asia/Tokyo"},
            "tokyo_close": {"time": "17:00", "timezone": "Asia/Tokyo"},
        }

    @pytest.mark.asyncio
    async def test_session_transition_handling(
        self, mock_realtime_components, market_sessions
    ):
        """Test system behavior during market session transitions."""
        ws_streamer = mock_realtime_components["ws_streamer"]
        rt_signal_gen = mock_realtime_components["rt_signal_gen"]
        live_risk = mock_realtime_components["live_risk"]

        # Mock session state changes
        session_states = [
            "PRE_MARKET",
            "MARKET_OPEN",
            "MARKET_ACTIVE",
            "MARKET_CLOSE",
            "POST_MARKET",
        ]

        for i, session_state in enumerate(session_states):
            # Mock market data availability based on session
            if session_state in ["MARKET_OPEN", "MARKET_ACTIVE"]:
                ws_streamer.get_latest_ticks.return_value = [
                    {
                        "symbol": "EURUSD",
                        "bid": 1.1048,
                        "ask": 1.1050,
                        "volume": 50000 if session_state == "MARKET_ACTIVE" else 10000,
                    }
                ]
            else:
                ws_streamer.get_latest_ticks.return_value = (
                    []
                )  # No data during off-hours

            # Mock signal generation based on session
            if session_state == "MARKET_ACTIVE":
                rt_signal_gen.get_active_signals.return_value = [
                    {"signal_id": "SIG_001", "symbol": "EURUSD", "action": "BUY"}
                ]
            else:
                rt_signal_gen.get_active_signals.return_value = []

            # Mock risk management based on session
            risk_settings = {
                "PRE_MARKET": {"max_position_size": 50000, "trading_enabled": False},
                "MARKET_OPEN": {"max_position_size": 75000, "trading_enabled": True},
                "MARKET_ACTIVE": {"max_position_size": 100000, "trading_enabled": True},
                "MARKET_CLOSE": {"max_position_size": 25000, "trading_enabled": False},
                "POST_MARKET": {"max_position_size": 0, "trading_enabled": False},
            }

            live_risk.get_session_settings.return_value = risk_settings[session_state]

            # Test session-specific behavior
            latest_ticks = await ws_streamer.get_latest_ticks()
            active_signals = await rt_signal_gen.get_active_signals()
            session_settings = await live_risk.get_session_settings()

            # Verify session-appropriate behavior
            if session_state in ["MARKET_OPEN", "MARKET_ACTIVE"]:
                assert len(latest_ticks) > 0
                assert session_settings["trading_enabled"] == True
                assert session_settings["max_position_size"] > 0
            else:
                assert len(latest_ticks) == 0

            if session_state == "MARKET_ACTIVE":
                assert len(active_signals) > 0

            # Verify risk settings adjusted for session
            expected_max_size = risk_settings[session_state]["max_position_size"]
            assert session_settings["max_position_size"] == expected_max_size

        # Verify all session states were tested
        assert ws_streamer.get_latest_ticks.call_count == len(session_states)
        assert rt_signal_gen.get_active_signals.call_count == len(session_states)
        assert live_risk.get_session_settings.call_count == len(session_states)

    @pytest.mark.asyncio
    async def test_weekend_market_closure_handling(self, mock_realtime_components):
        """Test system behavior during weekend market closure."""
        ws_streamer = mock_realtime_components["ws_streamer"]
        rt_broker = mock_realtime_components["rt_broker"]
        live_risk = mock_realtime_components["live_risk"]

        # Mock weekend market closure
        ws_streamer.get_latest_ticks.return_value = []
        rt_broker.get_market_status.return_value = "CLOSED"

        # Mock weekend risk settings
        weekend_settings = {
            "trading_enabled": False,
            "max_position_size": 0,
            "close_all_positions": True,
            "emergency_only": True,
        }

        live_risk.get_weekend_settings.return_value = weekend_settings

        # Test weekend behavior
        market_status = await rt_broker.get_market_status()
        latest_ticks = await ws_streamer.get_latest_ticks()
        weekend_config = await live_risk.get_weekend_settings()

        # Verify weekend market closure handling
        assert market_status == "CLOSED"
        assert len(latest_ticks) == 0
        assert weekend_config["trading_enabled"] == False
        assert weekend_config["max_position_size"] == 0
        assert weekend_config["close_all_positions"] == True

        # Verify weekend-specific calls
        rt_broker.get_market_status.assert_called_once()
        live_risk.get_weekend_settings.assert_called_once()


# Performance Benchmarks for Real-Time Systems
class TestRealTimePerformanceBenchmarks:
    """Performance benchmarks for real-time trading operations."""

    @pytest.mark.asyncio
    async def test_tick_processing_latency_benchmark(self, mock_realtime_components):
        """Benchmark tick processing latency under load."""
        live_data_handler = mock_realtime_components["live_data_handler"]
        rt_feature_engine = mock_realtime_components["rt_feature_engine"]

        # Generate high-frequency tick data
        num_ticks = 1000
        ticks = [
            {
                "symbol": "EURUSD",
                "bid": 1.1048 + (i * 0.00001),
                "ask": 1.1050 + (i * 0.00001),
                "timestamp": datetime.utcnow().isoformat(),
                "volume": 1000 + i,
            }
            for i in range(num_ticks)
        ]

        # Benchmark tick processing
        start_time = time.time()

        for tick in ticks:
            await live_data_handler.process_tick(tick)
            rt_feature_engine.update_features("EURUSD", tick)

        total_time = time.time() - start_time
        avg_latency = (total_time / num_ticks) * 1000  # Convert to milliseconds

        # Performance targets for real-time processing
        assert avg_latency < 5.0  # Under 5ms per tick
        assert total_time < 5.0  # Process 1000 ticks in under 5 seconds

        ticks_per_second = num_ticks / total_time
        assert ticks_per_second > 200  # Minimum 200 ticks/second processing

        # Verify all ticks processed
        assert live_data_handler.process_tick.call_count == num_ticks
        assert rt_feature_engine.update_features.call_count == num_ticks

    @pytest.mark.asyncio
    async def test_concurrent_symbol_processing_benchmark(
        self, mock_realtime_components
    ):
        """Benchmark concurrent multi-symbol processing performance."""
        symbols = ["EURUSD", "GBPUSD", "USDJPY", "USDCHF", "AUDUSD", "NZDUSD"]
        ticks_per_symbol = 100

        rt_ml_inference = mock_realtime_components["rt_ml_inference"]
        rt_signal_gen = mock_realtime_components["rt_signal_gen"]

        # Mock fast ML inference
        rt_ml_inference.predict_live.return_value = {
            "prediction": 1,
            "probability": 0.75,
            "confidence": 0.80,
        }

        rt_signal_gen.process_live_signal.return_value = {
            "signal_id": "BENCH_SIG",
            "action": "BUY",
            "confidence": 0.80,
        }

        async def process_symbol_batch(symbol):
            """Process batch of ticks for single symbol."""
            for _ in range(ticks_per_symbol):
                prediction = await rt_ml_inference.predict_live(symbol, {})
                await rt_signal_gen.process_live_signal(prediction)

        # Benchmark concurrent processing
        start_time = time.time()

        tasks = [
            asyncio.create_task(process_symbol_batch(symbol)) for symbol in symbols
        ]
        await asyncio.gather(*tasks)

        total_time = time.time() - start_time
        total_operations = (
            len(symbols) * ticks_per_symbol * 2
        )  # 2 ops per tick (ML + signal)

        # Performance targets for concurrent processing
        operations_per_second = total_operations / total_time
        assert operations_per_second > 500  # Minimum 500 operations/second
        assert total_time < 10.0  # Complete all operations in under 10 seconds

        # Verify all operations completed
        expected_ml_calls = len(symbols) * ticks_per_symbol
        expected_signal_calls = len(symbols) * ticks_per_symbol

        assert rt_ml_inference.predict_live.call_count == expected_ml_calls
        assert rt_signal_gen.process_live_signal.call_count == expected_signal_calls


if __name__ == "__main__":
    """Run real-time integration tests directly."""
    pytest.main([__file__, "-v", "--tb=short", "-x"])
