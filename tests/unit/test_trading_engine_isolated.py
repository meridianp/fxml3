"""
Isolated unit tests for Trading Engine service core functionality.

This module tests the trading engine in isolation without external dependencies,
following Test-Driven Development (TDD) principles.
"""

import asyncio
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

# Use centralized event loop fixture
from tests.fixtures.event_loop_fixtures import event_loop

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

# Mock all external dependencies before importing
sys.modules["openai"] = Mock()
sys.modules["fxml4.strategy.integrated_signal_generator"] = Mock()
sys.modules["fxml4.wave_analysis.sentiment_wave_validator"] = Mock()
sys.modules["fxml4.llm_integration.sentiment_analysis"] = Mock()
sys.modules["fxml4.llm_integration.llm_client"] = Mock()


# Create mock classes for dependencies
class MockSignalData:
    def __init__(
        self,
        timestamp,
        symbol,
        timeframe,
        direction,
        confidence,
        signal_type,
        source,
        metadata=None,
    ):
        self.timestamp = timestamp
        self.symbol = symbol
        self.timeframe = timeframe
        self.direction = direction
        self.confidence = confidence
        self.signal_type = signal_type
        self.source = source
        self.metadata = metadata or {}


class MockOrderData:
    def __init__(
        self,
        id,
        symbol,
        side,
        quantity,
        order_type,
        status,
        created_at,
        filled_quantity=0,
        avg_fill_price=None,
        filled_at=None,
        signal_id=None,
        strategy_name=None,
    ):
        self.id = id
        self.symbol = symbol
        self.side = side
        self.quantity = quantity
        self.order_type = order_type
        self.status = status
        self.created_at = created_at
        self.filled_quantity = filled_quantity
        self.avg_fill_price = avg_fill_price
        self.filled_at = filled_at
        self.signal_id = signal_id
        self.strategy_name = strategy_name


# Mock enums
class MockOrderSide:
    BUY = "BUY"
    SELL = "SELL"


class MockOrderType:
    MARKET = "MARKET"
    LIMIT = "LIMIT"


# Mock execution class
class MockOrderExecution:
    def __init__(
        self, order_id, execution_id, symbol, side, quantity, price, timestamp
    ):
        self.order_id = order_id
        self.execution_id = execution_id
        self.symbol = symbol
        self.side = side
        self.quantity = quantity
        self.price = price
        self.timestamp = timestamp


# Now import the actual trading engine components
with patch.dict(
    "sys.modules",
    {
        "fxml4.api.services.signal_processing": Mock(),
        "fxml4.api.services.order_management": Mock(),
        "fxml4.api.services.market_data": Mock(),
    },
):
    from fxml4.api.services.trading_engine import (
        PositionData,
        TradingEngineConfig,
        TradingEngineMetrics,
        TradingEngineState,
        TradingMode,
    )


class TestTradingEngineModels:
    """Test the trading engine data models."""

    def test_trading_engine_config_defaults(self):
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

    def test_trading_engine_config_custom(self):
        """Test configuration with custom values."""
        config = TradingEngineConfig(
            trading_mode=TradingMode.FULLY_AUTO,
            enabled_symbols={"EURUSD", "GBPUSD"},
            min_signal_confidence=0.7,
            max_position_size=50000.0,
            auto_execute_confidence=0.9,
        )

        assert config.trading_mode == TradingMode.FULLY_AUTO
        assert config.enabled_symbols == {"EURUSD", "GBPUSD"}
        assert config.min_signal_confidence == 0.7
        assert config.max_position_size == 50000.0
        assert config.auto_execute_confidence == 0.9

    def test_position_data_defaults(self):
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

    def test_position_data_with_values(self):
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

    def test_trading_engine_metrics_defaults(self):
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


class MockTradingEngine:
    """Mock implementation of TradingEngine for isolated testing."""

    def __init__(self):
        self.state = TradingEngineState.INACTIVE
        self.config = TradingEngineConfig()
        self.metrics = TradingEngineMetrics()
        self.positions = {}
        self.start_time = None
        self.error_message = None

        # Background tasks
        self.engine_task = None
        self.monitoring_task = None
        self.position_update_task = None

        # Event handlers
        self.signal_callbacks = []
        self.order_callbacks = []
        self.execution_callbacks = []
        self.state_callbacks = []

        # Database connection
        self._pool = None

    def set_trading_mode(self, mode: TradingMode):
        """Set trading mode."""
        self.config.trading_mode = mode

    def set_enabled_symbols(self, symbols):
        """Set enabled trading symbols."""
        self.config.enabled_symbols = set(symbols)

    def set_confidence_threshold(self, threshold: float):
        """Set minimum signal confidence threshold."""
        self.config.min_signal_confidence = max(0.0, min(1.0, threshold))

    def get_status(self):
        """Get current engine status."""
        return {
            "state": self.state.value,
            "trading_mode": self.config.trading_mode.value,
            "enabled_symbols": list(self.config.enabled_symbols),
            "metrics": {
                "signals_processed": self.metrics.signals_processed,
                "orders_created": self.metrics.orders_created,
                "orders_executed": self.metrics.orders_executed,
                "successful_trades": self.metrics.successful_trades,
                "active_positions": self.metrics.active_positions,
                "total_pnl": self.metrics.total_pnl,
                "uptime_seconds": self.metrics.uptime_seconds,
            },
            "error_message": self.error_message,
            "start_time": self.start_time.isoformat() if self.start_time else None,
        }

    def get_positions(self):
        """Get current positions."""
        return {
            symbol: {
                "quantity": pos.quantity,
                "avg_price": pos.avg_price,
                "market_value": pos.market_value,
                "unrealized_pnl": pos.unrealized_pnl,
                "realized_pnl": pos.realized_pnl,
                "last_updated": pos.last_updated.isoformat(),
            }
            for symbol, pos in self.positions.items()
        }

    def _calculate_position_size(self, signal):
        """Calculate position size for a signal."""
        base_size = 10000.0
        confidence_multiplier = signal.confidence
        position_multiplier = self.config.position_size_multiplier
        position_size = base_size * confidence_multiplier * position_multiplier
        position_size = min(position_size, self.config.max_position_size)
        return round(position_size, 2)

    async def _check_risk_limits(self, symbol: str, position_size: float) -> bool:
        """Check if trade meets risk management limits."""
        # Check maximum position size
        if position_size > self.config.max_position_size:
            return False

        # Check current position exposure
        current_position = self.positions.get(symbol, PositionData(symbol=symbol))
        if (
            abs(current_position.quantity + position_size)
            > self.config.max_position_size
        ):
            return False

        return True

    def _update_state(self, new_state: TradingEngineState, error_message=None):
        """Update engine state and notify callbacks."""
        old_state = self.state
        self.state = new_state
        self.error_message = error_message

        # Notify callbacks
        for callback in self.state_callbacks:
            try:
                callback(new_state)
            except Exception:
                pass

    def _update_metrics(self):
        """Update engine metrics."""
        if self.start_time:
            self.metrics.uptime_seconds = (
                datetime.utcnow() - self.start_time
            ).total_seconds()

        # Calculate total P&L
        total_pnl = sum(
            (pos.unrealized_pnl or 0.0) + pos.realized_pnl
            for pos in self.positions.values()
        )
        self.metrics.total_pnl = total_pnl

        # Count active positions
        self.metrics.active_positions = sum(
            1 for pos in self.positions.values() if pos.quantity != 0
        )

    def add_signal_callback(self, callback):
        """Add callback for signal events."""
        self.signal_callbacks.append(callback)

    def add_order_callback(self, callback):
        """Add callback for order events."""
        self.order_callbacks.append(callback)

    def add_execution_callback(self, callback):
        """Add callback for execution events."""
        self.execution_callbacks.append(callback)

    def add_state_callback(self, callback):
        """Add callback for state changes."""
        self.state_callbacks.append(callback)

    async def _update_position_from_order(self, order):
        """Update position based on filled order."""
        if order.symbol not in self.positions:
            self.positions[order.symbol] = PositionData(symbol=order.symbol)

        position = self.positions[order.symbol]

        # Calculate new position
        if order.side == MockOrderSide.BUY:
            new_quantity = position.quantity + order.filled_quantity
        else:
            new_quantity = position.quantity - order.filled_quantity

        # Update average price
        if new_quantity != 0 and order.avg_fill_price:
            if position.quantity == 0:
                position.avg_price = order.avg_fill_price
            else:
                total_cost = (position.quantity * (position.avg_price or 0)) + (
                    order.filled_quantity
                    * order.avg_fill_price
                    * (1 if order.side == MockOrderSide.BUY else -1)
                )
                position.avg_price = total_cost / new_quantity

        position.quantity = new_quantity
        position.last_updated = datetime.utcnow()

        # Update metrics
        if order.status == "filled":
            self.metrics.orders_executed += 1
            self.metrics.successful_trades += 1


class TestMockTradingEngine:
    """Test the mock trading engine functionality."""

    @pytest.fixture
    def engine(self):
        """Create a fresh MockTradingEngine instance for each test."""
        return MockTradingEngine()

    def test_initial_state(self, engine):
        """Test engine initial state."""
        assert engine.state == TradingEngineState.INACTIVE
        assert isinstance(engine.config, TradingEngineConfig)
        assert isinstance(engine.metrics, TradingEngineMetrics)
        assert engine.positions == {}
        assert engine.start_time is None
        assert engine.error_message is None

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
        signal = MockSignalData(
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

        # Higher confidence should result in larger position size
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

    def test_state_management(self, engine):
        """Test state change functionality."""
        # Test normal state change
        engine._update_state(TradingEngineState.ACTIVE)
        assert engine.state == TradingEngineState.ACTIVE
        assert engine.error_message is None

        # Test error state
        error_message = "Test error"
        engine._update_state(TradingEngineState.ERROR, error_message)
        assert engine.state == TradingEngineState.ERROR
        assert engine.error_message == error_message

    def test_state_change_callbacks(self, engine):
        """Test state change notifications."""
        callback_called = []

        def test_callback(new_state):
            callback_called.append(new_state)

        engine.add_state_callback(test_callback)

        # Trigger state change
        engine._update_state(TradingEngineState.ACTIVE)

        assert len(callback_called) == 1
        assert callback_called[0] == TradingEngineState.ACTIVE

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

    @pytest.mark.asyncio
    async def test_position_update_from_order(self, engine):
        """Test position updates from order fills."""
        symbol = "EURUSD"

        # Create initial position
        engine.positions[symbol] = PositionData(symbol=symbol)

        # Create filled order
        filled_order = MockOrderData(
            id="test_order",
            symbol=symbol,
            side=MockOrderSide.BUY,
            quantity=10000.0,
            order_type=MockOrderType.MARKET,
            status="filled",
            created_at=datetime.utcnow(),
            filled_quantity=10000.0,
            avg_fill_price=1.2500,
            filled_at=datetime.utcnow(),
        )

        # Update position
        await engine._update_position_from_order(filled_order)

        position = engine.positions[symbol]
        assert position.quantity == 10000.0
        assert position.avg_price == 1.2500
        assert engine.metrics.orders_executed == 1
        assert engine.metrics.successful_trades == 1

    def test_callback_management(self, engine):
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


class TestTradingEngineBusinessLogic:
    """Test trading engine business logic and workflows."""

    @pytest.fixture
    def engine(self):
        return MockTradingEngine()

    def test_trading_mode_configurations(self, engine):
        """Test different trading mode configurations."""
        # Test MANUAL mode
        engine.set_trading_mode(TradingMode.MANUAL)
        assert engine.config.trading_mode == TradingMode.MANUAL

        # Test SEMI_AUTO mode
        engine.set_trading_mode(TradingMode.SEMI_AUTO)
        assert engine.config.trading_mode == TradingMode.SEMI_AUTO

        # Test FULLY_AUTO mode
        engine.set_trading_mode(TradingMode.FULLY_AUTO)
        assert engine.config.trading_mode == TradingMode.FULLY_AUTO

    def test_symbol_management(self, engine):
        """Test enabled symbols management."""
        symbols = ["EURUSD", "GBPUSD", "USDJPY"]
        engine.set_enabled_symbols(symbols)

        assert engine.config.enabled_symbols == set(symbols)

        # Test empty symbols
        engine.set_enabled_symbols([])
        assert engine.config.enabled_symbols == set()

    def test_confidence_threshold_validation(self, engine):
        """Test confidence threshold validation and clamping."""
        # Test valid threshold
        engine.set_confidence_threshold(0.75)
        assert engine.config.min_signal_confidence == 0.75

        # Test upper boundary
        engine.set_confidence_threshold(1.0)
        assert engine.config.min_signal_confidence == 1.0

        # Test lower boundary
        engine.set_confidence_threshold(0.0)
        assert engine.config.min_signal_confidence == 0.0

        # Test clamping above 1.0
        engine.set_confidence_threshold(1.5)
        assert engine.config.min_signal_confidence == 1.0

        # Test clamping below 0.0
        engine.set_confidence_threshold(-0.5)
        assert engine.config.min_signal_confidence == 0.0

    def test_position_size_scaling(self, engine):
        """Test position size calculation with different confidence levels."""
        base_signal = MockSignalData(
            timestamp=datetime.utcnow(),
            symbol="EURUSD",
            timeframe="1h",
            direction=1,
            confidence=0.5,
            signal_type="test",
            source="test",
        )

        # Test different confidence levels
        confidences = [0.1, 0.3, 0.5, 0.7, 0.9]
        sizes = []

        for conf in confidences:
            base_signal.confidence = conf
            size = engine._calculate_position_size(base_signal)
            sizes.append(size)

        # Position sizes should generally increase with confidence
        for i in range(1, len(sizes)):
            assert (
                sizes[i] >= sizes[i - 1]
            ), f"Size {sizes[i]} should be >= {sizes[i-1]} for confidence {confidences[i]} >= {confidences[i-1]}"

    def test_position_size_multiplier(self, engine):
        """Test position size multiplier effect."""
        signal = MockSignalData(
            timestamp=datetime.utcnow(),
            symbol="EURUSD",
            timeframe="1h",
            direction=1,
            confidence=0.8,
            signal_type="test",
            source="test",
        )

        # Test default multiplier
        default_size = engine._calculate_position_size(signal)

        # Test with doubled multiplier
        engine.config.position_size_multiplier = 2.0
        doubled_size = engine._calculate_position_size(signal)

        # Should be roughly doubled (within rounding)
        assert abs(doubled_size - (default_size * 2)) < 1.0

        # Test with halved multiplier
        engine.config.position_size_multiplier = 0.5
        halved_size = engine._calculate_position_size(signal)

        # Should be roughly halved
        assert abs(halved_size - (default_size * 0.5)) < 1.0


# Pytest configuration
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


if __name__ == "__main__":
    # Run the tests
    pytest.main([__file__, "-v"])
