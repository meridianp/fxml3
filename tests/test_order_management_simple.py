"""
Comprehensive Test Suite for Order Management System

This test suite validates the core order management functionality that coordinates
all broker adapters (Interactive Brokers, FXCM, Manual) with proper lifecycle
tracking, intelligent routing, and performance monitoring.

Test Coverage:
- OrderManager: Central coordination with <100ms SLA
- Order State Machine: Complete lifecycle validation
- OrderRouter: Intelligent multi-broker routing logic
- OrderBook: Real-time tracking and updates
- Integration: All broker adapters coordination
- Performance: SLA compliance and monitoring
"""

import asyncio
import tempfile
from datetime import datetime, timedelta
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, Mock, patch
from uuid import uuid4

import pytest

from fxml4.messaging.messages import MessagePriority, OrderSide, OrderStatus, OrderType
from fxml4.order_management.order_manager import (
    FillData,
    Order,
    OrderBook,
    OrderManager,
    OrderRequest,
    OrderResponse,
    OrderRouter,
    OrderRoutingError,
    OrderState,
    OrderTimeoutError,
    OrderValidationError,
    RouteDecision,
)


class TestOrderState:
    """Test order state machine and transitions."""

    def test_order_state_initialization(self):
        """Test order state enum values."""
        assert OrderState.NEW.value == "NEW"
        assert OrderState.PENDING.value == "PENDING"
        assert OrderState.PARTIALLY_FILLED.value == "PARTIALLY_FILLED"
        assert OrderState.FILLED.value == "FILLED"
        assert OrderState.CANCELLED.value == "CANCELLED"
        assert OrderState.REJECTED.value == "REJECTED"

    def test_valid_state_transitions(self):
        """Test valid order state transitions."""
        # Test all valid transitions from NEW
        valid_from_new = [OrderState.PENDING, OrderState.CANCELLED, OrderState.REJECTED]
        for state in valid_from_new:
            assert OrderState.is_valid_transition(OrderState.NEW, state)

        # Test valid transitions from PENDING
        valid_from_pending = [
            OrderState.PARTIALLY_FILLED,
            OrderState.FILLED,
            OrderState.CANCELLED,
            OrderState.REJECTED,
        ]
        for state in valid_from_pending:
            assert OrderState.is_valid_transition(OrderState.PENDING, state)

        # Test valid transitions from PARTIALLY_FILLED
        valid_from_partial = [OrderState.FILLED, OrderState.CANCELLED]
        for state in valid_from_partial:
            assert OrderState.is_valid_transition(OrderState.PARTIALLY_FILLED, state)

    def test_invalid_state_transitions(self):
        """Test invalid order state transitions."""
        # Cannot go backwards in the lifecycle
        assert not OrderState.is_valid_transition(OrderState.FILLED, OrderState.NEW)
        assert not OrderState.is_valid_transition(
            OrderState.CANCELLED, OrderState.PENDING
        )
        assert not OrderState.is_valid_transition(
            OrderState.REJECTED, OrderState.PARTIALLY_FILLED
        )

        # Terminal states cannot transition
        assert not OrderState.is_valid_transition(
            OrderState.FILLED, OrderState.CANCELLED
        )
        assert not OrderState.is_valid_transition(
            OrderState.CANCELLED, OrderState.FILLED
        )


class TestOrder:
    """Test Order model and validation."""

    def test_order_creation(self):
        """Test order creation with all fields."""
        order = Order(
            order_id="ORD_001",
            client_order_id="CLI_001",
            symbol="EUR/USD",
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            quantity=Decimal("100000"),
            price=Decimal("1.1000"),
            stop_price=Decimal("1.0950"),
            time_in_force="DAY",
            account_id="TEST123",
        )

        assert order.order_id == "ORD_001"
        assert order.symbol == "EUR/USD"
        assert order.side == OrderSide.BUY
        assert order.quantity == Decimal("100000")
        assert order.state == OrderState.NEW  # Default state
        assert order.filled_quantity == Decimal("0")
        assert len(order.fills) == 0

    def test_order_validation_valid(self):
        """Test valid order validation."""
        order = Order(
            order_id="ORD_VALID",
            symbol="GBP/USD",
            side=OrderSide.SELL,
            order_type=OrderType.LIMIT,
            quantity=Decimal("50000"),
            price=Decimal("1.2500"),
        )

        validation = order.validate()
        assert validation.is_valid is True
        assert len(validation.errors) == 0

    def test_order_validation_errors(self):
        """Test order validation with errors."""
        invalid_order = Order(
            order_id="",  # Invalid empty order_id
            symbol="",  # Invalid empty symbol
            side=OrderSide.BUY,
            order_type=OrderType.LIMIT,
            quantity=Decimal("-1000"),  # Invalid negative quantity
            price=Decimal("0"),  # Invalid zero price
        )

        validation = invalid_order.validate()
        assert validation.is_valid is False
        assert len(validation.errors) >= 4


class TestOrderRouter:
    """Test intelligent order routing logic."""

    def test_router_initialization(self):
        """Test order router initialization."""
        router = OrderRouter(
            available_brokers=["IB", "FXCM", "MANUAL"],
            default_broker="IB",
            routing_preferences={"EUR/USD": "IB", "GBP/USD": "FXCM"},
        )

        assert len(router.available_brokers) == 3
        assert router.default_broker == "IB"
        assert router.routing_preferences["EUR/USD"] == "IB"

    @pytest.mark.asyncio
    async def test_route_order_by_symbol_preference(self):
        """Test routing based on symbol preferences."""
        router = OrderRouter(
            routing_preferences={
                "EUR/USD": "IB",
                "GBP/USD": "FXCM",
                "USD/JPY": "MANUAL",
            }
        )

        # Test preferred routing
        order_eur = Order(
            symbol="EUR/USD",
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            quantity=Decimal("100000"),
        )
        route = await router.determine_route(order_eur)
        assert route.broker == "IB"
        assert route.confidence > 0.8

        order_gbp = Order(
            symbol="GBP/USD",
            side=OrderSide.SELL,
            order_type=OrderType.MARKET,
            quantity=Decimal("75000"),
        )
        route = await router.determine_route(order_gbp)
        assert route.broker == "FXCM"

        # Test fallback to default
        order_other = Order(
            symbol="AUD/USD",
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            quantity=Decimal("50000"),
        )
        route = await router.determine_route(order_other)
        assert route.broker == router.default_broker

    @pytest.mark.asyncio
    async def test_route_order_by_size(self):
        """Test routing based on order size."""
        router = OrderRouter(
            size_based_routing={
                "small": ("IB", 50000),  # Orders < 50k to IB
                "medium": ("FXCM", 200000),  # Orders 50k-200k to FXCM
                "large": ("MANUAL", float("inf")),  # Orders > 200k to Manual
            }
        )

        # Small order
        small_order = Order(
            symbol="EUR/USD",
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            quantity=Decimal("25000"),
        )
        route = await router.determine_route(small_order)
        assert route.broker == "IB"

        # Large order requiring manual approval
        large_order = Order(
            symbol="EUR/USD",
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            quantity=Decimal("500000"),
        )
        route = await router.determine_route(large_order)
        assert route.broker == "MANUAL"
        assert route.requires_approval is True

    @pytest.mark.asyncio
    async def test_broker_health_routing(self):
        """Test routing based on broker health."""
        router = OrderRouter(available_brokers=["IB", "FXCM", "MANUAL"])

        # Mock health checks
        with patch.object(
            router, "_check_broker_health", new_callable=AsyncMock
        ) as mock_health:
            # Only FXCM is healthy
            mock_health.side_effect = lambda broker: broker == "FXCM"

            order = Order(
                symbol="EUR/USD",
                side=OrderSide.BUY,
                order_type=OrderType.MARKET,
                quantity=Decimal("100000"),
            )
            route = await router.determine_route(order, check_health=True)
            assert route.broker == "FXCM"
            assert route.reason == "healthy_broker_selected"


class TestOrderBook:
    """Test real-time order tracking."""

    def test_order_book_initialization(self):
        """Test order book setup."""
        order_book = OrderBook(max_orders=1000)

        assert order_book.max_orders == 1000
        assert len(order_book.active_orders) == 0
        assert len(order_book.order_history) == 0
        assert len(order_book.symbol_orders) == 0

    @pytest.mark.asyncio
    async def test_add_order_to_book(self):
        """Test adding orders to order book."""
        order_book = OrderBook()

        order = Order(
            order_id="BOOK_001",
            symbol="EUR/USD",
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            quantity=Decimal("100000"),
        )

        await order_book.add_order(order)

        assert "BOOK_001" in order_book.active_orders
        assert len(order_book.symbol_orders.get("EUR/USD", [])) == 1
        assert order_book.active_orders["BOOK_001"].state == OrderState.NEW

    @pytest.mark.asyncio
    async def test_update_order_status(self):
        """Test order status updates."""
        order_book = OrderBook()

        order = Order(
            order_id="UPDATE_001",
            symbol="GBP/USD",
            side=OrderSide.SELL,
            order_type=OrderType.MARKET,
            quantity=Decimal("50000"),
        )
        await order_book.add_order(order)

        # Update to FILLED
        fill_data = FillData(
            fill_price=Decimal("1.2550"),
            fill_quantity=Decimal("50000"),
            fill_time=datetime.utcnow(),
            commission=Decimal("5.0"),
        )

        # First transition to PENDING, then to FILLED (valid state machine)
        await order_book.update_order_status("UPDATE_001", OrderState.PENDING)
        await order_book.update_order_status("UPDATE_001", OrderState.FILLED, fill_data)

        # Should be moved to history
        assert "UPDATE_001" not in order_book.active_orders
        assert "UPDATE_001" in order_book.order_history
        assert order_book.order_history["UPDATE_001"].state == OrderState.FILLED

    def test_order_book_statistics(self):
        """Test order book statistics calculation."""
        order_book = OrderBook()

        # Add some test data
        order_book.order_history["HIST_001"] = Order(
            order_id="HIST_001",
            symbol="EUR/USD",
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            quantity=Decimal("100000"),
            state=OrderState.FILLED,
        )
        order_book.order_history["HIST_002"] = Order(
            order_id="HIST_002",
            symbol="EUR/USD",
            side=OrderSide.SELL,
            order_type=OrderType.MARKET,
            quantity=Decimal("50000"),
            state=OrderState.CANCELLED,
        )

        stats = order_book.get_statistics()

        assert stats["total_orders"] == 2
        assert stats["filled_orders"] == 1
        assert stats["cancelled_orders"] == 1
        assert stats["fill_rate"] == 0.5


class TestOrderManager:
    """Test main order manager coordination."""

    def test_order_manager_initialization(self):
        """Test order manager setup."""
        with tempfile.NamedTemporaryFile() as tmp:
            manager = OrderManager(
                audit_config={"log_file": tmp.name},
                performance_targets={"ack_time_ms": 100, "fill_time_ms": 5000},
            )

            assert manager.performance_targets["ack_time_ms"] == 100
            assert manager.order_router is not None
            assert manager.order_book is not None
            assert manager.audit_logger is not None

    @pytest.mark.asyncio
    async def test_create_order_success(self):
        """Test successful order creation."""
        with tempfile.NamedTemporaryFile() as tmp:
            manager = OrderManager(audit_config={"log_file": tmp.name})

            # Mock broker adapter
            mock_broker = AsyncMock()
            mock_broker.execute_order.return_value = {
                "order_id": "BROKER_001",
                "status": "PENDING",
                "ack_time_ms": 50,
            }

            manager.broker_adapters["IB"] = mock_broker

            order_request = OrderRequest(
                symbol="EUR/USD",
                side=OrderSide.BUY,
                order_type=OrderType.MARKET,
                quantity=Decimal("100000"),
                account_id="TEST123",
            )

            response = await manager.create_order(order_request)

            assert response.success is True
            assert response.order_id is not None
            assert response.ack_time_ms < 100
            mock_broker.execute_order.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_order_validation_failure(self):
        """Test order creation with validation failure."""
        with tempfile.NamedTemporaryFile() as tmp:
            manager = OrderManager(audit_config={"log_file": tmp.name})

            # Invalid order request
            invalid_request = OrderRequest(
                symbol="",  # Invalid empty symbol
                side=OrderSide.BUY,
                order_type=OrderType.MARKET,
                quantity=Decimal("-1000"),  # Invalid negative quantity
            )

            with pytest.raises(OrderValidationError, match="Invalid order request"):
                await manager.create_order(invalid_request)

    @pytest.mark.asyncio
    async def test_cancel_order(self):
        """Test order cancellation."""
        with tempfile.NamedTemporaryFile() as tmp:
            manager = OrderManager(audit_config={"log_file": tmp.name})

            # Add order to book
            order = Order(
                order_id="CANCEL_001",
                symbol="EUR/USD",
                side=OrderSide.BUY,
                order_type=OrderType.MARKET,
                quantity=Decimal("100000"),
            )
            order.broker = "IB"  # Assign broker so cancellation can work
            await manager.order_book.add_order(order)

            # Mock broker adapter
            mock_broker = AsyncMock()
            mock_broker.cancel_order.return_value = {"status": "CANCELLED"}
            manager.broker_adapters["IB"] = mock_broker

            result = await manager.cancel_order("CANCEL_001")

            assert result.success is True
            # Check that the order was indeed cancelled (moved to history in CANCELLED state)
            cancelled_order = manager.order_book.order_history.get("CANCEL_001")
            assert cancelled_order is not None
            assert cancelled_order.state == OrderState.CANCELLED

    @pytest.mark.asyncio
    async def test_performance_monitoring(self):
        """Test performance SLA monitoring."""
        with tempfile.NamedTemporaryFile() as tmp:
            manager = OrderManager(
                audit_config={"log_file": tmp.name},
                performance_targets={"ack_time_ms": 100},
            )

            # Simulate some orders for performance tracking
            manager.performance_stats.total_orders = 100
            manager.performance_stats.ack_times = [
                50,
                75,
                80,
                45,
                120,
            ]  # One exceeds SLA

            stats = manager.get_performance_statistics()

            assert stats["total_orders"] == 100
            assert stats["average_ack_time_ms"] == 74  # Average of ack times
            assert stats["sla_compliance_rate"] == 0.8  # 4 out of 5 meet <100ms SLA

    def test_broker_adapter_management(self):
        """Test broker adapter registration."""
        with tempfile.NamedTemporaryFile() as tmp:
            manager = OrderManager(audit_config={"log_file": tmp.name})

            # Register mock adapters
            mock_ib = Mock()
            mock_fxcm = Mock()
            mock_manual = Mock()

            manager.add_broker_adapter("IB", mock_ib)
            manager.add_broker_adapter("FXCM", mock_fxcm)
            manager.add_broker_adapter("MANUAL", mock_manual)

            assert len(manager.broker_adapters) == 3
            assert "IB" in manager.broker_adapters
            assert "FXCM" in manager.broker_adapters
            assert "MANUAL" in manager.broker_adapters

    @pytest.mark.asyncio
    async def test_order_routing_integration(self):
        """Test integration between routing and execution."""
        with tempfile.NamedTemporaryFile() as tmp:
            manager = OrderManager(audit_config={"log_file": tmp.name})

            # Setup routing preferences
            manager.order_router.routing_preferences = {"EUR/USD": "FXCM"}

            # Mock FXCM adapter
            mock_fxcm = AsyncMock()
            mock_fxcm.execute_order.return_value = {
                "order_id": "FXCM_001",
                "status": "PENDING",
            }
            manager.broker_adapters["FXCM"] = mock_fxcm

            order_request = OrderRequest(
                symbol="EUR/USD",  # Should route to FXCM
                side=OrderSide.BUY,
                order_type=OrderType.MARKET,
                quantity=Decimal("100000"),
            )

            response = await manager.create_order(order_request)

            assert response.success is True
            assert response.broker_used == "FXCM"
            mock_fxcm.execute_order.assert_called_once()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
