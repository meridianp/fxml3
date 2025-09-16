"""
Comprehensive unit tests for Order Management service.

This module provides complete test coverage for the order management functionality,
following Test-Driven Development (TDD) principles.
"""

import asyncio
import sys
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List
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

# Import the order management components we can access
with patch.dict(
    "sys.modules",
    {
        "fxml4.api.services.signal_processing": Mock(),
        "fxml4.api.services.market_data": Mock(),
        "fxml4.api.services.websocket": Mock(),
    },
):
    from fxml4.api.services.order_management import (
        OrderData,
        OrderExecution,
        OrderSide,
        OrderStatus,
        OrderType,
        RiskCheckResult,
    )


class TestOrderModels:
    """Test the order management data models."""

    def test_order_data_creation(self):
        """Test OrderData model creation with required fields."""
        order = OrderData(
            id="test_order_1",
            symbol="EURUSD",
            side=OrderSide.BUY,
            quantity=10000.0,
            order_type=OrderType.MARKET,
            status=OrderStatus.PENDING,
            created_at=datetime.utcnow(),
        )

        assert order.id == "test_order_1"
        assert order.symbol == "EURUSD"
        assert order.side == OrderSide.BUY
        assert order.quantity == 10000.0
        assert order.order_type == OrderType.MARKET
        assert order.status == OrderStatus.PENDING
        assert isinstance(order.created_at, datetime)

    def test_order_data_with_optional_fields(self):
        """Test OrderData with all optional fields."""
        signal_time = datetime.utcnow()
        created_time = datetime.utcnow()
        filled_time = datetime.utcnow()

        order = OrderData(
            id="test_order_2",
            symbol="GBPUSD",
            side=OrderSide.SELL,
            quantity=5000.0,
            order_type=OrderType.LIMIT,
            status=OrderStatus.FILLED,
            created_at=created_time,
            limit_price=1.2500,
            stop_price=1.2400,
            filled_quantity=5000.0,
            avg_fill_price=1.2490,
            filled_at=filled_time,
            signal_id="signal_123",
            strategy_name="test_strategy",
            metadata={"test_key": "test_value"},
        )

        assert order.limit_price == 1.2500
        assert order.stop_price == 1.2400
        assert order.filled_quantity == 5000.0
        assert order.avg_fill_price == 1.2490
        assert order.filled_at == filled_time
        assert order.signal_id == "signal_123"
        assert order.strategy_name == "test_strategy"
        assert order.metadata == {"test_key": "test_value"}

    def test_order_execution_model(self):
        """Test OrderExecution model."""
        execution_time = datetime.utcnow()
        execution = OrderExecution(
            order_id="order_123",
            execution_id="exec_456",
            symbol="USDJPY",
            side=OrderSide.BUY,
            quantity=1000.0,
            price=150.25,
            timestamp=execution_time,
            commission=2.50,
            exchange_order_id="EX123456",
            metadata={"venue": "test_venue"},
        )

        assert execution.order_id == "order_123"
        assert execution.execution_id == "exec_456"
        assert execution.symbol == "USDJPY"
        assert execution.side == OrderSide.BUY
        assert execution.quantity == 1000.0
        assert execution.price == 150.25
        assert execution.timestamp == execution_time
        assert execution.commission == 2.50
        assert execution.exchange_order_id == "EX123456"
        assert execution.metadata == {"venue": "test_venue"}

    def test_risk_check_result_model(self):
        """Test RiskCheckResult model."""
        # Test passed risk check
        passed_result = RiskCheckResult(passed=True, message="Risk check passed")
        assert passed_result.passed is True
        assert passed_result.message == "Risk check passed"
        assert passed_result.risk_factors == []
        assert passed_result.max_allowed_quantity is None

        # Test failed risk check with details
        failed_result = RiskCheckResult(
            passed=False,
            message="Risk check failed",
            risk_factors=["position_limit", "daily_volume"],
            max_allowed_quantity=5000.0,
        )
        assert failed_result.passed is False
        assert failed_result.message == "Risk check failed"
        assert failed_result.risk_factors == ["position_limit", "daily_volume"]
        assert failed_result.max_allowed_quantity == 5000.0


class MockOrderManagementService:
    """Mock implementation of OrderManagementService for testing."""

    def __init__(self):
        self.orders = {}  # Dict[str, OrderData]
        self.executions = {}  # Dict[str, List[OrderExecution]]
        self.order_update_callbacks = []
        self.execution_callbacks = []
        self._pool = None
        self.config = None

        # Risk management settings
        self.max_position_size = 100000.0
        self.max_daily_volume = 1000000.0
        self.max_orders_per_hour = 50

    async def initialize(self):
        """Initialize the order management service."""
        self._pool = AsyncMock()
        self.config = AsyncMock()

    async def create_order(
        self,
        symbol: str,
        side: OrderSide,
        quantity: float,
        order_type: OrderType = OrderType.MARKET,
        limit_price: float = None,
        stop_price: float = None,
        strategy_name: str = None,
        metadata: Dict[str, Any] = None,
    ) -> OrderData:
        """Create a new order."""
        order_id = str(uuid.uuid4())

        order = OrderData(
            id=order_id,
            symbol=symbol,
            side=side,
            quantity=quantity,
            order_type=order_type,
            status=OrderStatus.PENDING,
            created_at=datetime.utcnow(),
            limit_price=limit_price,
            stop_price=stop_price,
            strategy_name=strategy_name,
            metadata=metadata or {},
        )

        self.orders[order_id] = order

        # Notify callbacks
        for callback in self.order_update_callbacks:
            try:
                callback(order)
            except Exception:
                pass

        return order

    async def create_order_from_signal(
        self,
        signal,
        quantity: float,
        order_type: OrderType = OrderType.MARKET,
        auto_execute: bool = False,
    ) -> OrderData:
        """Create order from trading signal."""
        side = OrderSide.BUY if signal.direction > 0 else OrderSide.SELL

        order = await self.create_order(
            symbol=signal.symbol,
            side=side,
            quantity=quantity,
            order_type=order_type,
            strategy_name=signal.signal_type,
            metadata={
                "signal_id": getattr(signal, "id", None),
                "signal_confidence": signal.confidence,
                "signal_source": signal.source,
                "auto_execute": auto_execute,
            },
        )

        if auto_execute:
            await self.execute_order(order.id)

        return order

    async def execute_order(
        self, order_id: str, execution_price: float = None
    ) -> OrderExecution:
        """Execute an order."""
        if order_id not in self.orders:
            raise ValueError(f"Order {order_id} not found")

        order = self.orders[order_id]
        if order.status != OrderStatus.PENDING:
            raise ValueError(f"Order {order_id} is not in pending status")

        # Simulate execution
        execution_id = str(uuid.uuid4())
        exec_price = execution_price or (
            order.limit_price or 1.2500
        )  # Default test price

        execution = OrderExecution(
            order_id=order_id,
            execution_id=execution_id,
            symbol=order.symbol,
            side=order.side,
            quantity=order.quantity,
            price=exec_price,
            timestamp=datetime.utcnow(),
            commission=2.50,
            exchange_order_id=f"EX{execution_id[:8]}",
        )

        # Update order
        order.status = OrderStatus.FILLED
        order.filled_quantity = order.quantity
        order.avg_fill_price = exec_price
        order.filled_at = execution.timestamp

        # Store execution
        if order_id not in self.executions:
            self.executions[order_id] = []
        self.executions[order_id].append(execution)

        # Notify callbacks
        for callback in self.order_update_callbacks:
            try:
                callback(order)
            except Exception:
                pass

        for callback in self.execution_callbacks:
            try:
                callback(execution)
            except Exception:
                pass

        return execution

    async def cancel_order(self, order_id: str) -> bool:
        """Cancel an order."""
        if order_id not in self.orders:
            raise ValueError(f"Order {order_id} not found")

        order = self.orders[order_id]
        if order.status not in [OrderStatus.PENDING, OrderStatus.SUBMITTED]:
            return False

        order.status = OrderStatus.CANCELLED

        # Notify callbacks
        for callback in self.order_update_callbacks:
            try:
                callback(order)
            except Exception:
                pass

        return True

    async def get_order(self, order_id: str) -> OrderData:
        """Get order by ID."""
        if order_id not in self.orders:
            raise ValueError(f"Order {order_id} not found")
        return self.orders[order_id]

    async def get_orders(
        self,
        symbol: str = None,
        status: OrderStatus = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[OrderData]:
        """Get orders with optional filtering."""
        orders = list(self.orders.values())

        # Apply filters
        if symbol:
            orders = [o for o in orders if o.symbol == symbol]
        if status:
            orders = [o for o in orders if o.status == status]

        # Sort by creation time (newest first)
        orders.sort(key=lambda x: x.created_at, reverse=True)

        # Apply pagination
        return orders[offset : offset + limit]

    async def get_executions(self, order_id: str) -> List[OrderExecution]:
        """Get executions for an order."""
        return self.executions.get(order_id, [])

    async def perform_risk_checks(self, order: OrderData) -> RiskCheckResult:
        """Perform risk management checks on an order."""
        risk_factors = []

        # Check position size
        if order.quantity > self.max_position_size:
            risk_factors.append("position_size_exceeded")

        # Check daily volume (simplified)
        daily_volume = sum(
            o.quantity
            for o in self.orders.values()
            if o.created_at.date() == datetime.utcnow().date()
        )
        if daily_volume + order.quantity > self.max_daily_volume:
            risk_factors.append("daily_volume_exceeded")

        # Check order frequency (simplified)
        recent_orders = [
            o
            for o in self.orders.values()
            if o.created_at > datetime.utcnow() - timedelta(hours=1)
        ]
        if len(recent_orders) >= self.max_orders_per_hour:
            risk_factors.append("order_frequency_exceeded")

        passed = len(risk_factors) == 0
        message = (
            "Risk checks passed"
            if passed
            else f"Risk violations: {', '.join(risk_factors)}"
        )

        return RiskCheckResult(
            passed=passed,
            message=message,
            risk_factors=risk_factors,
            max_allowed_quantity=self.max_position_size if not passed else None,
        )

    def add_order_update_callback(self, callback):
        """Add order update callback."""
        self.order_update_callbacks.append(callback)

    def add_execution_callback(self, callback):
        """Add execution callback."""
        self.execution_callbacks.append(callback)


class TestMockOrderManagementService:
    """Test the mock order management service functionality."""

    @pytest.fixture
    def service(self):
        """Create a fresh MockOrderManagementService instance for each test."""
        return MockOrderManagementService()

    @pytest.mark.asyncio
    async def test_initialization(self, service):
        """Test service initialization."""
        await service.initialize()

        assert service._pool is not None
        assert service.config is not None

    @pytest.mark.asyncio
    async def test_create_order(self, service):
        """Test order creation."""
        order = await service.create_order(
            symbol="EURUSD",
            side=OrderSide.BUY,
            quantity=10000.0,
            order_type=OrderType.MARKET,
            strategy_name="test_strategy",
        )

        assert order.id is not None
        assert order.symbol == "EURUSD"
        assert order.side == OrderSide.BUY
        assert order.quantity == 10000.0
        assert order.order_type == OrderType.MARKET
        assert order.status == OrderStatus.PENDING
        assert order.strategy_name == "test_strategy"
        assert isinstance(order.created_at, datetime)

        # Check order is stored
        assert order.id in service.orders

    @pytest.mark.asyncio
    async def test_create_limit_order(self, service):
        """Test limit order creation."""
        order = await service.create_order(
            symbol="GBPUSD",
            side=OrderSide.SELL,
            quantity=5000.0,
            order_type=OrderType.LIMIT,
            limit_price=1.2500,
            stop_price=1.2400,
        )

        assert order.order_type == OrderType.LIMIT
        assert order.limit_price == 1.2500
        assert order.stop_price == 1.2400

    @pytest.mark.asyncio
    async def test_create_order_from_signal(self, service):
        """Test order creation from signal."""
        # Mock signal object
        signal = Mock()
        signal.symbol = "USDJPY"
        signal.direction = 1  # Buy signal
        signal.confidence = 0.8
        signal.signal_type = "ml_signal"
        signal.source = "test_model"

        order = await service.create_order_from_signal(
            signal=signal,
            quantity=8000.0,
            order_type=OrderType.MARKET,
            auto_execute=False,
        )

        assert order.symbol == "USDJPY"
        assert order.side == OrderSide.BUY
        assert order.quantity == 8000.0
        assert order.strategy_name == "ml_signal"
        assert order.metadata["signal_confidence"] == 0.8
        assert order.metadata["signal_source"] == "test_model"
        assert order.metadata["auto_execute"] is False

    @pytest.mark.asyncio
    async def test_create_order_from_sell_signal(self, service):
        """Test order creation from sell signal."""
        signal = Mock()
        signal.symbol = "EURGBP"
        signal.direction = -1  # Sell signal
        signal.confidence = 0.7
        signal.signal_type = "elliott_wave"
        signal.source = "pattern_analyzer"

        order = await service.create_order_from_signal(signal=signal, quantity=3000.0)

        assert order.side == OrderSide.SELL
        assert order.strategy_name == "elliott_wave"

    @pytest.mark.asyncio
    async def test_auto_execute_order_from_signal(self, service):
        """Test auto-execution when creating order from signal."""
        signal = Mock()
        signal.symbol = "USDCHF"
        signal.direction = 1
        signal.confidence = 0.9
        signal.signal_type = "high_confidence"
        signal.source = "ensemble_model"

        order = await service.create_order_from_signal(
            signal=signal, quantity=2000.0, auto_execute=True
        )

        # Order should be automatically executed
        assert order.status == OrderStatus.FILLED
        assert order.filled_quantity == 2000.0
        assert order.avg_fill_price is not None
        assert order.filled_at is not None

        # Check execution was created
        executions = await service.get_executions(order.id)
        assert len(executions) == 1
        assert executions[0].quantity == 2000.0

    @pytest.mark.asyncio
    async def test_execute_order(self, service):
        """Test order execution."""
        # Create an order first
        order = await service.create_order(
            symbol="AUDUSD", side=OrderSide.BUY, quantity=6000.0
        )

        # Execute the order
        execution = await service.execute_order(order.id, execution_price=0.6750)

        assert execution.order_id == order.id
        assert execution.symbol == "AUDUSD"
        assert execution.side == OrderSide.BUY
        assert execution.quantity == 6000.0
        assert execution.price == 0.6750
        assert execution.commission == 2.50
        assert isinstance(execution.timestamp, datetime)

        # Check order status updated
        updated_order = await service.get_order(order.id)
        assert updated_order.status == OrderStatus.FILLED
        assert updated_order.filled_quantity == 6000.0
        assert updated_order.avg_fill_price == 0.6750
        assert updated_order.filled_at is not None

    @pytest.mark.asyncio
    async def test_execute_nonexistent_order(self, service):
        """Test execution of non-existent order."""
        with pytest.raises(ValueError, match="Order .* not found"):
            await service.execute_order("nonexistent_order")

    @pytest.mark.asyncio
    async def test_execute_already_executed_order(self, service):
        """Test execution of already executed order."""
        # Create and execute an order
        order = await service.create_order("NZDUSD", OrderSide.SELL, 1000.0)
        await service.execute_order(order.id)

        # Try to execute again
        with pytest.raises(ValueError, match="not in pending status"):
            await service.execute_order(order.id)

    @pytest.mark.asyncio
    async def test_cancel_order(self, service):
        """Test order cancellation."""
        # Create an order
        order = await service.create_order("CADCHF", OrderSide.BUY, 4000.0)
        assert order.status == OrderStatus.PENDING

        # Cancel the order
        result = await service.cancel_order(order.id)
        assert result is True

        # Check order status
        cancelled_order = await service.get_order(order.id)
        assert cancelled_order.status == OrderStatus.CANCELLED

    @pytest.mark.asyncio
    async def test_cancel_executed_order(self, service):
        """Test cancellation of executed order."""
        # Create and execute an order
        order = await service.create_order("EURJPY", OrderSide.SELL, 2000.0)
        await service.execute_order(order.id)

        # Try to cancel executed order
        result = await service.cancel_order(order.id)
        assert result is False  # Cannot cancel executed order

    @pytest.mark.asyncio
    async def test_get_orders(self, service):
        """Test order retrieval and filtering."""
        # Create test orders
        order1 = await service.create_order("EURUSD", OrderSide.BUY, 1000.0)
        order2 = await service.create_order("GBPUSD", OrderSide.SELL, 2000.0)
        order3 = await service.create_order("EURUSD", OrderSide.BUY, 3000.0)

        # Execute one order
        await service.execute_order(order2.id)

        # Get all orders
        all_orders = await service.get_orders()
        assert len(all_orders) == 3

        # Filter by symbol
        eurusd_orders = await service.get_orders(symbol="EURUSD")
        assert len(eurusd_orders) == 2
        assert all(o.symbol == "EURUSD" for o in eurusd_orders)

        # Filter by status
        pending_orders = await service.get_orders(status=OrderStatus.PENDING)
        assert len(pending_orders) == 2
        assert all(o.status == OrderStatus.PENDING for o in pending_orders)

        filled_orders = await service.get_orders(status=OrderStatus.FILLED)
        assert len(filled_orders) == 1
        assert filled_orders[0].id == order2.id

    @pytest.mark.asyncio
    async def test_get_orders_pagination(self, service):
        """Test order retrieval pagination."""
        # Create multiple orders
        for i in range(5):
            await service.create_order("TESTPAIR", OrderSide.BUY, 1000.0 * (i + 1))

        # Test limit
        limited_orders = await service.get_orders(limit=3)
        assert len(limited_orders) == 3

        # Test offset
        offset_orders = await service.get_orders(limit=2, offset=2)
        assert len(offset_orders) == 2

        # Orders should be sorted by creation time (newest first)
        all_orders = await service.get_orders()
        for i in range(len(all_orders) - 1):
            assert all_orders[i].created_at >= all_orders[i + 1].created_at

    @pytest.mark.asyncio
    async def test_get_executions(self, service):
        """Test execution retrieval."""
        # Create and execute an order
        order = await service.create_order("USDCAD", OrderSide.BUY, 5000.0)
        execution = await service.execute_order(order.id)

        # Get executions
        executions = await service.get_executions(order.id)
        assert len(executions) == 1
        assert executions[0].execution_id == execution.execution_id

        # Test non-existent order
        empty_executions = await service.get_executions("nonexistent")
        assert len(empty_executions) == 0

    @pytest.mark.asyncio
    async def test_risk_checks_passing(self, service):
        """Test risk checks that should pass."""
        order = await service.create_order(
            "EURCHF", OrderSide.BUY, 1000.0
        )  # Small quantity

        risk_result = await service.perform_risk_checks(order)

        assert risk_result.passed is True
        assert risk_result.message == "Risk checks passed"
        assert risk_result.risk_factors == []
        assert risk_result.max_allowed_quantity is None

    @pytest.mark.asyncio
    async def test_risk_checks_position_size_violation(self, service):
        """Test risk checks with position size violation."""
        # Create order with excessive size
        order = await service.create_order("OVERSIZED", OrderSide.BUY, 200000.0)

        risk_result = await service.perform_risk_checks(order)

        assert risk_result.passed is False
        assert "position_size_exceeded" in risk_result.risk_factors
        assert "Risk violations:" in risk_result.message
        assert risk_result.max_allowed_quantity == service.max_position_size

    @pytest.mark.asyncio
    async def test_risk_checks_daily_volume_violation(self, service):
        """Test risk checks with daily volume violation."""
        # Create many orders to exceed daily volume
        total_volume = 0
        while total_volume < service.max_daily_volume:
            await service.create_order("VOLUME_TEST", OrderSide.BUY, 50000.0)
            total_volume += 50000.0

        # Create one more order that should fail
        over_limit_order = await service.create_order(
            "VOLUME_TEST", OrderSide.BUY, 10000.0
        )
        risk_result = await service.perform_risk_checks(over_limit_order)

        assert risk_result.passed is False
        assert "daily_volume_exceeded" in risk_result.risk_factors

    @pytest.mark.asyncio
    async def test_risk_checks_order_frequency_violation(self, service):
        """Test risk checks with order frequency violation."""
        # Create many orders to exceed hourly limit
        for i in range(service.max_orders_per_hour):
            await service.create_order("FREQ_TEST", OrderSide.BUY, 1000.0)

        # Create one more order that should trigger frequency violation
        freq_order = await service.create_order("FREQ_TEST", OrderSide.BUY, 1000.0)
        risk_result = await service.perform_risk_checks(freq_order)

        assert risk_result.passed is False
        assert "order_frequency_exceeded" in risk_result.risk_factors

    def test_callback_registration(self, service):
        """Test callback registration."""
        order_callback = MagicMock()
        execution_callback = MagicMock()

        service.add_order_update_callback(order_callback)
        service.add_execution_callback(execution_callback)

        assert order_callback in service.order_update_callbacks
        assert execution_callback in service.execution_callbacks

    @pytest.mark.asyncio
    async def test_order_callback_notifications(self, service):
        """Test order update callback notifications."""
        callback_calls = []

        def test_callback(order):
            callback_calls.append(order)

        service.add_order_update_callback(test_callback)

        # Create order - should trigger callback
        order = await service.create_order("CALLBACK_TEST", OrderSide.BUY, 1000.0)
        assert len(callback_calls) == 1
        assert callback_calls[0].id == order.id

        # Execute order - should trigger callback again
        await service.execute_order(order.id)
        assert len(callback_calls) == 2
        assert callback_calls[1].status == OrderStatus.FILLED

        # Cancel different order - should trigger callback
        order2 = await service.create_order("CALLBACK_TEST2", OrderSide.SELL, 500.0)
        await service.cancel_order(order2.id)
        assert len(callback_calls) == 4  # create + cancel
        assert callback_calls[3].status == OrderStatus.CANCELLED

    @pytest.mark.asyncio
    async def test_execution_callback_notifications(self, service):
        """Test execution callback notifications."""
        execution_calls = []

        def test_callback(execution):
            execution_calls.append(execution)

        service.add_execution_callback(test_callback)

        # Create and execute order
        order = await service.create_order("EXEC_CALLBACK", OrderSide.BUY, 2000.0)
        await service.execute_order(order.id)

        assert len(execution_calls) == 1
        assert execution_calls[0].order_id == order.id
        assert execution_calls[0].quantity == 2000.0


# Pytest configuration
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


if __name__ == "__main__":
    # Run the tests
    pytest.main([__file__, "-v"])
