"""
Comprehensive unit tests for Trading Engine service.

This module provides complete test coverage for the core trading engine functionality,
following Test-Driven Development (TDD) principles.
"""

import asyncio
from datetime import datetime, timedelta
from typing import Any, Dict
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from fxml4.api.services.order_management import OrderData, OrderSide, OrderType
from fxml4.api.services.signal_processing import SignalData

# Import the classes we're testing
from fxml4.api.services.trading_engine import (
    PositionData,
    TradingEngine,
    TradingEngineConfig,
    TradingEngineMetrics,
    TradingEngineState,
    TradingMode,
)

# Use centralized event loop fixture
from tests.fixtures.event_loop_fixtures import event_loop


class TestTradingEngineConfig:
    """Test the TradingEngineConfig model."""

    def test_default_config_values(self):
        """Test default configuration values."""
        config = TradingEngineConfig()

        assert config.trading_mode == TradingMode.MANUAL
        assert config.enabled_symbols == set()
        assert config.min_signal_confidence == 0.5
        assert config.signal_timeout_minutes == 5
        assert config.max_position_size == 100000.0
        assert config.max_daily_volume == 1000000.0
        assert config.auto_execute_confidence == 0.8
        assert config.position_size_multiplier == 1.0
        assert config.max_concurrent_orders == 20
        assert config.order_timeout_minutes == 15

    def test_config_with_custom_values(self):
        """Test configuration with custom values."""
        config = TradingEngineConfig(
            trading_mode=TradingMode.FULLY_AUTO,
            enabled_symbols={"EURUSD", "GBPUSD"},
            min_signal_confidence=0.7,
            max_position_size=50000.0,
        )

        assert config.trading_mode == TradingMode.FULLY_AUTO
        assert config.enabled_symbols == {"EURUSD", "GBPUSD"}
        assert config.min_signal_confidence == 0.7
        assert config.max_position_size == 50000.0


class TestPositionData:
    """Test the PositionData model."""

    def test_default_position_values(self):
        """Test default position values."""
        position = PositionData(symbol="EURUSD")

        assert position.symbol == "EURUSD"
        assert position.quantity == 0.0
        assert position.avg_price is None
        assert position.market_value is None
        assert position.unrealized_pnl is None
        assert position.realized_pnl == 0.0
        assert position.open_orders == []
        assert isinstance(position.last_updated, datetime)

    def test_position_with_values(self):
        """Test position with specific values."""
        test_time = datetime.utcnow()
        position = PositionData(
            symbol="GBPUSD",
            quantity=10000.0,
            avg_price=1.2500,
            market_value=12500.0,
            unrealized_pnl=500.0,
            realized_pnl=250.0,
            open_orders=["order1", "order2"],
            last_updated=test_time,
        )

        assert position.symbol == "GBPUSD"
        assert position.quantity == 10000.0
        assert position.avg_price == 1.2500
        assert position.market_value == 12500.0
        assert position.unrealized_pnl == 500.0
        assert position.realized_pnl == 250.0
        assert position.open_orders == ["order1", "order2"]
        assert position.last_updated == test_time


class TestTradingEngineMetrics:
    """Test the TradingEngineMetrics model."""

    def test_default_metrics_values(self):
        """Test default metrics values."""
        metrics = TradingEngineMetrics()

        assert metrics.signals_processed == 0
        assert metrics.orders_created == 0
        assert metrics.orders_executed == 0
        assert metrics.orders_cancelled == 0
        assert metrics.successful_trades == 0
        assert metrics.failed_trades == 0
        assert metrics.total_pnl == 0.0
        assert metrics.active_positions == 0
        assert metrics.uptime_seconds == 0.0
        assert metrics.last_signal_time is None
        assert metrics.last_trade_time is None


class TestTradingEngine:
    """Comprehensive test suite for TradingEngine class."""

    @pytest.fixture
    def engine(self):
        """Create a fresh TradingEngine instance for each test."""
        return TradingEngine()

    @pytest.fixture
    def mock_market_data_service(self):
        """Mock market data service."""
        mock_service = AsyncMock()
        mock_service.get_connection_pool.return_value = AsyncMock()
        mock_service.get_available_symbols.return_value = ["EURUSD", "GBPUSD", "USDJPY"]
        mock_service.get_latest_tick.return_value = {
            "price": 1.2500,
            "timestamp": datetime.utcnow(),
        }
        return mock_service

    @pytest.fixture
    def mock_signal_processing_service(self):
        """Mock signal processing service."""
        mock_service = AsyncMock()
        mock_service.initialize.return_value = None
        mock_service.start_signal_processing.return_value = None
        mock_service.stop_signal_processing.return_value = None
        mock_service.get_recent_signals.return_value = []
        return mock_service

    @pytest.fixture
    def mock_order_management_service(self):
        """Mock order management service."""
        mock_service = AsyncMock()
        mock_service.initialize.return_value = None
        mock_service.get_orders.return_value = []
        mock_service.create_order_from_signal.return_value = OrderData(
            id="test_order_1",
            symbol="EURUSD",
            side=OrderSide.BUY,
            quantity=10000.0,
            order_type=OrderType.MARKET,
            status="pending",
            created_at=datetime.utcnow(),
        )
        mock_service.cancel_order.return_value = None
        mock_service.add_order_update_callback = MagicMock()
        mock_service.add_execution_callback = MagicMock()
        return mock_service

    def test_initial_state(self, engine):
        """Test engine initial state."""
        assert engine.state == TradingEngineState.INACTIVE
        assert isinstance(engine.config, TradingEngineConfig)
        assert isinstance(engine.metrics, TradingEngineMetrics)
        assert engine.positions == {}
        assert engine.start_time is None
        assert engine.error_message is None
        assert engine.engine_task is None
        assert engine.monitoring_task is None
        assert engine.position_update_task is None

    @pytest.mark.asyncio
    async def test_initialization(
        self,
        engine,
        mock_market_data_service,
        mock_signal_processing_service,
        mock_order_management_service,
    ):
        """Test engine initialization."""
        with (
            patch(
                "fxml4.api.services.trading_engine.market_data_service",
                mock_market_data_service,
            ),
            patch(
                "fxml4.api.services.trading_engine.signal_processing_service",
                mock_signal_processing_service,
            ),
            patch(
                "fxml4.api.services.trading_engine.order_management_service",
                mock_order_management_service,
            ),
        ):

            await engine.initialize()

            assert engine.state == TradingEngineState.INACTIVE
            assert engine.start_time is not None
            assert engine._pool is not None
            mock_signal_processing_service.initialize.assert_called_once()
            mock_order_management_service.initialize.assert_called_once()

    def test_configuration_methods(self, engine):
        """Test configuration update methods."""
        # Test set_trading_mode
        engine.set_trading_mode(TradingMode.FULLY_AUTO)
        assert engine.config.trading_mode == TradingMode.FULLY_AUTO

        # Test set_enabled_symbols
        symbols = ["EURUSD", "GBPUSD"]
        engine.set_enabled_symbols(symbols)
        assert engine.config.enabled_symbols == set(symbols)

        # Test set_confidence_threshold
        engine.set_confidence_threshold(0.8)
        assert engine.config.min_signal_confidence == 0.8

        # Test boundary conditions for confidence threshold
        engine.set_confidence_threshold(1.5)  # Should be clamped to 1.0
        assert engine.config.min_signal_confidence == 1.0

        engine.set_confidence_threshold(-0.1)  # Should be clamped to 0.0
        assert engine.config.min_signal_confidence == 0.0

    def test_get_status(self, engine):
        """Test get_status method."""
        status = engine.get_status()

        assert isinstance(status, dict)
        assert "state" in status
        assert "trading_mode" in status
        assert "enabled_symbols" in status
        assert "metrics" in status
        assert "error_message" in status
        assert "start_time" in status

        assert status["state"] == TradingEngineState.INACTIVE.value
        assert status["trading_mode"] == TradingMode.MANUAL.value
        assert status["enabled_symbols"] == []

    def test_get_positions(self, engine):
        """Test get_positions method."""
        # Add a test position
        engine.positions["EURUSD"] = PositionData(
            symbol="EURUSD", quantity=10000.0, avg_price=1.2500, unrealized_pnl=250.0
        )

        positions = engine.get_positions()

        assert isinstance(positions, dict)
        assert "EURUSD" in positions
        assert positions["EURUSD"]["quantity"] == 10000.0
        assert positions["EURUSD"]["avg_price"] == 1.2500
        assert positions["EURUSD"]["unrealized_pnl"] == 250.0

    def test_calculate_position_size(self, engine):
        """Test position size calculation."""
        signal = SignalData(
            timestamp=datetime.utcnow(),
            symbol="EURUSD",
            timeframe="1h",
            direction=1,
            confidence=0.8,
            signal_type="test",
            source="test",
        )

        position_size = engine._calculate_position_size(signal)

        assert isinstance(position_size, float)
        assert position_size > 0
        assert position_size <= engine.config.max_position_size

        # Test with high confidence
        signal.confidence = 0.9
        high_confidence_size = engine._calculate_position_size(signal)

        # Test with low confidence
        signal.confidence = 0.1
        low_confidence_size = engine._calculate_position_size(signal)

        # Higher confidence should generally result in larger position size
        assert high_confidence_size >= low_confidence_size

    @pytest.mark.asyncio
    async def test_risk_limits_check(self, engine):
        """Test risk limits checking."""
        symbol = "EURUSD"

        # Test within limits
        small_position = 1000.0
        assert await engine._check_risk_limits(symbol, small_position) is True

        # Test exceeding position size limit
        large_position = engine.config.max_position_size + 1000.0
        assert await engine._check_risk_limits(symbol, large_position) is False

        # Test with existing position
        engine.positions[symbol] = PositionData(symbol=symbol, quantity=50000.0)
        medium_position = 60000.0  # Would exceed limit when combined with existing
        assert await engine._check_risk_limits(symbol, medium_position) is False

    @pytest.mark.asyncio
    async def test_start_stop_lifecycle(
        self,
        engine,
        mock_market_data_service,
        mock_signal_processing_service,
        mock_order_management_service,
    ):
        """Test engine start and stop lifecycle."""
        with (
            patch(
                "fxml4.api.services.trading_engine.market_data_service",
                mock_market_data_service,
            ),
            patch(
                "fxml4.api.services.trading_engine.signal_processing_service",
                mock_signal_processing_service,
            ),
            patch(
                "fxml4.api.services.trading_engine.order_management_service",
                mock_order_management_service,
            ),
        ):

            # Initialize first
            await engine.initialize()

            # Test start
            await engine.start(symbols=["EURUSD"])
            assert engine.state == TradingEngineState.ACTIVE
            assert "EURUSD" in engine.config.enabled_symbols
            assert engine.engine_task is not None
            assert engine.monitoring_task is not None
            assert engine.position_update_task is not None

            # Test pause
            await engine.pause()
            assert engine.state == TradingEngineState.PAUSED

            # Test resume
            await engine.resume()
            assert engine.state == TradingEngineState.ACTIVE

            # Test stop
            await engine.stop()
            assert engine.state == TradingEngineState.INACTIVE

    @pytest.mark.asyncio
    async def test_invalid_state_transitions(self, engine):
        """Test invalid state transitions."""
        # Try to start when not initialized
        with pytest.raises(Exception):
            await engine.start()

        # Try to resume when not paused
        with pytest.raises(ValueError):
            await engine.resume()

    @pytest.mark.asyncio
    async def test_signal_handling(self, engine, mock_order_management_service):
        """Test signal processing and handling."""
        with patch(
            "fxml4.api.services.trading_engine.order_management_service",
            mock_order_management_service,
        ):

            # Create test signal
            signal = SignalData(
                timestamp=datetime.utcnow(),
                symbol="EURUSD",
                timeframe="1h",
                direction=1,
                confidence=0.8,
                signal_type="test_signal",
                source="test",
            )

            # Test signal handling
            await engine._handle_signal(signal)

            # Verify order creation was called
            mock_order_management_service.create_order_from_signal.assert_called_once()

            # Verify metrics were updated
            assert engine.metrics.signals_processed == 1
            assert engine.metrics.orders_created == 1

    @pytest.mark.asyncio
    async def test_signal_confidence_filtering(self, engine):
        """Test signal filtering based on confidence threshold."""
        engine.config.min_signal_confidence = 0.7

        # Low confidence signal - should be filtered out
        low_confidence_signal = SignalData(
            timestamp=datetime.utcnow(),
            symbol="EURUSD",
            timeframe="1h",
            direction=1,
            confidence=0.5,  # Below threshold
            signal_type="test",
            source="test",
        )

        with patch.object(engine, "_calculate_position_size") as mock_calc:
            await engine._handle_signal(low_confidence_signal)
            mock_calc.assert_not_called()  # Should not reach position calculation

    def test_position_update_from_order(self, engine):
        """Test position updates from order fills."""
        symbol = "EURUSD"

        # Create initial position
        engine.positions[symbol] = PositionData(symbol=symbol)

        # Create filled order
        filled_order = OrderData(
            id="test_order",
            symbol=symbol,
            side=OrderSide.BUY,
            quantity=10000.0,
            order_type=OrderType.MARKET,
            status="filled",
            created_at=datetime.utcnow(),
            filled_quantity=10000.0,
            avg_fill_price=1.2500,
            filled_at=datetime.utcnow(),
        )

        # Update position
        asyncio.run(engine._update_position_from_order(filled_order))

        position = engine.positions[symbol]
        assert position.quantity == 10000.0
        assert position.avg_price == 1.2500

    def test_metrics_updates(self, engine):
        """Test metrics calculation and updates."""
        # Add some positions with P&L
        engine.positions["EURUSD"] = PositionData(
            symbol="EURUSD", unrealized_pnl=100.0, realized_pnl=50.0
        )
        engine.positions["GBPUSD"] = PositionData(
            symbol="GBPUSD", quantity=5000.0, unrealized_pnl=-50.0, realized_pnl=75.0
        )

        # Set start time for uptime calculation
        engine.start_time = datetime.utcnow() - timedelta(seconds=120)

        # Update metrics
        engine._update_metrics()

        assert engine.metrics.total_pnl == 175.0  # (100-50) + (50+75)
        assert engine.metrics.active_positions == 1  # Only GBPUSD has quantity > 0
        assert engine.metrics.uptime_seconds >= 120

    def test_event_callbacks(self, engine):
        """Test event callback functionality."""
        # Test adding callbacks
        signal_callback = MagicMock()
        order_callback = MagicMock()
        execution_callback = MagicMock()
        state_callback = MagicMock()

        engine.add_signal_callback(signal_callback)
        engine.add_order_callback(order_callback)
        engine.add_execution_callback(execution_callback)
        engine.add_state_callback(state_callback)

        assert signal_callback in engine.signal_callbacks
        assert order_callback in engine.order_callbacks
        assert execution_callback in engine.execution_callbacks
        assert state_callback in engine.state_callbacks

    def test_state_change_notifications(self, engine):
        """Test state change notifications."""
        state_callback = MagicMock()
        engine.add_state_callback(state_callback)

        # Trigger state change
        engine._update_state(TradingEngineState.ACTIVE)

        assert engine.state == TradingEngineState.ACTIVE
        state_callback.assert_called_once_with(TradingEngineState.ACTIVE)

    def test_error_state_handling(self, engine):
        """Test error state handling."""
        error_message = "Test error message"

        engine._update_state(TradingEngineState.ERROR, error_message)

        assert engine.state == TradingEngineState.ERROR
        assert engine.error_message == error_message

        status = engine.get_status()
        assert status["error_message"] == error_message

    @pytest.mark.asyncio
    async def test_health_check(self, engine, mock_market_data_service):
        """Test health check functionality."""
        mock_pool = AsyncMock()
        mock_conn = AsyncMock()
        mock_conn.fetchval.return_value = 1
        mock_pool.acquire.return_value.__aenter__.return_value = mock_conn
        mock_pool.acquire.return_value.__aexit__.return_value = None

        engine._pool = mock_pool

        with patch(
            "fxml4.api.services.trading_engine.market_data_service",
            mock_market_data_service,
        ):
            await engine._health_check()

            # Verify database connectivity check
            mock_conn.fetchval.assert_called_once_with("SELECT 1")

            # Verify service health check
            mock_market_data_service.get_available_symbols.assert_called_once()

    @pytest.mark.asyncio
    async def test_order_management_integration(self, engine):
        """Test integration with order management callbacks."""
        # Create test order
        test_order = OrderData(
            id="test_order",
            symbol="EURUSD",
            side=OrderSide.BUY,
            quantity=10000.0,
            order_type=OrderType.MARKET,
            status="filled",
            created_at=datetime.utcnow(),
        )

        # Test order update callback
        initial_successful_trades = engine.metrics.successful_trades
        engine._on_order_update(test_order)
        assert engine.metrics.successful_trades == initial_successful_trades + 1

        # Test cancelled order
        test_order.status = "cancelled"
        initial_cancelled = engine.metrics.orders_cancelled
        engine._on_order_update(test_order)
        assert engine.metrics.orders_cancelled == initial_cancelled + 1

    @pytest.mark.asyncio
    async def test_concurrent_order_limits(self, engine, mock_order_management_service):
        """Test concurrent order limits."""
        # Mock many active orders
        mock_orders = [
            OrderData(
                id=f"order_{i}",
                symbol="EURUSD",
                side=OrderSide.BUY,
                quantity=1000.0,
                order_type=OrderType.MARKET,
                status="pending",
                created_at=datetime.utcnow(),
            )
            for i in range(engine.config.max_concurrent_orders + 1)
        ]

        mock_order_management_service.get_orders.return_value = mock_orders

        with patch(
            "fxml4.api.services.trading_engine.order_management_service",
            mock_order_management_service,
        ):
            # Should fail due to too many concurrent orders
            result = await engine._check_risk_limits("EURUSD", 1000.0)
            assert result is False

    @pytest.mark.asyncio
    async def test_cleanup(self, engine):
        """Test engine cleanup."""
        # Set up engine in active state
        engine.state = TradingEngineState.ACTIVE
        engine.engine_task = AsyncMock()
        engine.monitoring_task = AsyncMock()
        engine.position_update_task = AsyncMock()

        await engine.close()

        assert engine.state == TradingEngineState.INACTIVE


class TestTradingEngineIntegration:
    """Integration tests for trading engine with other services."""

    @pytest.mark.asyncio
    async def test_full_trading_workflow(self):
        """Test complete trading workflow integration."""
        # This would be a comprehensive integration test
        # that tests the full signal → order → execution → position flow
        # Implementation would require proper mocking of all services
        pass

    @pytest.mark.asyncio
    async def test_error_recovery(self):
        """Test error recovery scenarios."""
        # Test database connection failures
        # Test service unavailability
        # Test network failures
        pass

    @pytest.mark.asyncio
    async def test_performance_under_load(self):
        """Test performance with high signal volume."""
        # Test handling many signals simultaneously
        # Test memory usage and cleanup
        # Test response times
        pass


# Pytest configuration and fixtures
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


if __name__ == "__main__":
    # Run the tests
    pytest.main([__file__, "-v"])
