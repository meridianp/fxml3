"""
TDD Tests for Order Lifecycle State Machine

Tests comprehensive order management functionality including state transitions,
validation, and error handling for the FXML4 trading platform.
Following Red-Green-Refactor methodology.
"""

from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum
from typing import Optional
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from freezegun import freeze_time

from core.api.auth.models import User, UserRole


@pytest.mark.tdd
@pytest.mark.red
class TestOrderLifecycle:
    """
    RED Phase: Test order lifecycle state machine that doesn't exist yet.

    Tests cover order creation, validation, state transitions, and execution.
    """

    def test_order_model_import(self):
        """RED: Test that we can import the Order model."""
        from core.trading.orders import Order, OrderSide, OrderState, OrderType

        order = Order(
            symbol="EUR/USD",
            side=OrderSide.BUY,
            quantity=100000,
            order_type=OrderType.MARKET,
        )
        assert order is not None
        assert order.symbol == "EUR/USD"

    def test_order_state_enum(self):
        """RED: Test order state enumeration."""
        from core.trading.orders import OrderState

        # All expected order states
        assert OrderState.PENDING == "pending"
        assert OrderState.VALIDATED == "validated"
        assert OrderState.SUBMITTED == "submitted"
        assert OrderState.PARTIALLY_FILLED == "partially_filled"
        assert OrderState.FILLED == "filled"
        assert OrderState.CANCELLED == "cancelled"
        assert OrderState.REJECTED == "rejected"
        assert OrderState.EXPIRED == "expired"

    def test_order_type_enum(self):
        """RED: Test order type enumeration."""
        from core.trading.orders import OrderType

        assert OrderType.MARKET == "market"
        assert OrderType.LIMIT == "limit"
        assert OrderType.STOP == "stop"
        assert OrderType.STOP_LIMIT == "stop_limit"
        assert OrderType.TRAILING_STOP == "trailing_stop"

    def test_order_side_enum(self):
        """RED: Test order side enumeration."""
        from core.trading.orders import OrderSide

        assert OrderSide.BUY == "buy"
        assert OrderSide.SELL == "sell"

    def test_create_market_order(self):
        """RED: Test creating a market order."""
        from core.trading.orders import Order, OrderSide, OrderState, OrderType

        order = Order(
            symbol="EUR/USD",
            side=OrderSide.BUY,
            quantity=100000,
            order_type=OrderType.MARKET,
            user_id="trader_123",
        )

        # Check initial state
        assert order.state == OrderState.PENDING
        assert order.order_id is not None
        assert len(order.order_id) == 36  # UUID format
        assert order.created_at is not None
        assert order.updated_at is not None
        assert order.filled_quantity == 0
        assert order.average_fill_price is None
        assert order.commission == Decimal("0")

    def test_create_limit_order(self):
        """RED: Test creating a limit order."""
        from core.trading.orders import Order, OrderSide, OrderState, OrderType

        order = Order(
            symbol="GBP/USD",
            side=OrderSide.SELL,
            quantity=50000,
            order_type=OrderType.LIMIT,
            limit_price=Decimal("1.2750"),
            user_id="trader_456",
            time_in_force="GTC",  # Good Till Cancelled
        )

        assert order.state == OrderState.PENDING
        assert order.limit_price == Decimal("1.2750")
        assert order.time_in_force == "GTC"
        assert order.expire_time is None

    def test_create_stop_order(self):
        """RED: Test creating a stop order."""
        from core.trading.orders import Order, OrderSide, OrderType

        order = Order(
            symbol="USD/JPY",
            side=OrderSide.BUY,
            quantity=100000,
            order_type=OrderType.STOP,
            stop_price=Decimal("150.00"),
            user_id="trader_789",
        )

        assert order.stop_price == Decimal("150.00")
        assert order.order_type == OrderType.STOP

    def test_order_validation_minimum_quantity(self):
        """RED: Test order validation for minimum quantity."""
        from core.trading.orders import (
            Order,
            OrderSide,
            OrderType,
            OrderValidationError,
        )

        with pytest.raises(OrderValidationError) as exc_info:
            Order(
                symbol="EUR/USD",
                side=OrderSide.BUY,
                quantity=100,  # Below minimum (1000 for forex)
                order_type=OrderType.MARKET,
                user_id="trader_123",
            )

        assert "Quantity must be at least 1000" in str(exc_info.value)

    def test_order_validation_invalid_symbol(self):
        """RED: Test order validation for invalid symbol format."""
        from core.trading.orders import (
            Order,
            OrderSide,
            OrderType,
            OrderValidationError,
        )

        with pytest.raises(OrderValidationError) as exc_info:
            Order(
                symbol="INVALID",  # Not XXX/YYY format
                side=OrderSide.BUY,
                quantity=10000,
                order_type=OrderType.MARKET,
                user_id="trader_123",
            )

        assert "Invalid symbol format" in str(exc_info.value)

    def test_order_validation_limit_price_required(self):
        """RED: Test that limit orders require a limit price."""
        from core.trading.orders import (
            Order,
            OrderSide,
            OrderType,
            OrderValidationError,
        )

        with pytest.raises(OrderValidationError) as exc_info:
            Order(
                symbol="EUR/USD",
                side=OrderSide.BUY,
                quantity=10000,
                order_type=OrderType.LIMIT,
                # Missing limit_price
                user_id="trader_123",
            )

        assert "Limit price required for limit orders" in str(exc_info.value)

    def test_order_validation_stop_price_required(self):
        """RED: Test that stop orders require a stop price."""
        from core.trading.orders import (
            Order,
            OrderSide,
            OrderType,
            OrderValidationError,
        )

        with pytest.raises(OrderValidationError) as exc_info:
            Order(
                symbol="EUR/USD",
                side=OrderSide.SELL,
                quantity=10000,
                order_type=OrderType.STOP,
                # Missing stop_price
                user_id="trader_123",
            )

        assert "Stop price required for stop orders" in str(exc_info.value)

    def test_order_state_transition_pending_to_validated(self):
        """RED: Test state transition from pending to validated."""
        from core.trading.orders import Order, OrderSide, OrderState, OrderType

        order = Order(
            symbol="EUR/USD",
            side=OrderSide.BUY,
            quantity=10000,
            order_type=OrderType.MARKET,
            user_id="trader_123",
        )

        # Validate order
        order.validate()
        assert order.state == OrderState.VALIDATED
        assert order.validated_at is not None

    def test_order_state_transition_validated_to_submitted(self):
        """RED: Test state transition from validated to submitted."""
        from core.trading.orders import Order, OrderSide, OrderState, OrderType

        order = Order(
            symbol="EUR/USD",
            side=OrderSide.BUY,
            quantity=10000,
            order_type=OrderType.MARKET,
            user_id="trader_123",
        )

        order.validate()
        order.submit(broker_id="IB", broker_order_id="IB123456")

        assert order.state == OrderState.SUBMITTED
        assert order.broker_id == "IB"
        assert order.broker_order_id == "IB123456"
        assert order.submitted_at is not None

    def test_order_state_transition_submitted_to_filled(self):
        """RED: Test state transition from submitted to filled."""
        from core.trading.orders import Order, OrderSide, OrderState, OrderType

        order = Order(
            symbol="EUR/USD",
            side=OrderSide.BUY,
            quantity=10000,
            order_type=OrderType.MARKET,
            user_id="trader_123",
        )

        order.validate()
        order.submit(broker_id="IB", broker_order_id="IB123456")
        order.fill(
            filled_quantity=10000,
            fill_price=Decimal("1.0950"),
            commission=Decimal("2.50"),
        )

        assert order.state == OrderState.FILLED
        assert order.filled_quantity == 10000
        assert order.average_fill_price == Decimal("1.0950")
        assert order.commission == Decimal("2.50")
        assert order.filled_at is not None

    def test_order_partial_fill(self):
        """RED: Test partial order fill."""
        from core.trading.orders import Order, OrderSide, OrderState, OrderType

        order = Order(
            symbol="EUR/USD",
            side=OrderSide.BUY,
            quantity=10000,
            order_type=OrderType.LIMIT,
            limit_price=Decimal("1.0900"),
            user_id="trader_123",
        )

        order.validate()
        order.submit(broker_id="IB", broker_order_id="IB123456")

        # First partial fill
        order.partial_fill(
            filled_quantity=3000,
            fill_price=Decimal("1.0900"),
            commission=Decimal("0.75"),
        )

        assert order.state == OrderState.PARTIALLY_FILLED
        assert order.filled_quantity == 3000
        assert order.average_fill_price == Decimal("1.0900")
        assert order.remaining_quantity == 7000

        # Second partial fill
        order.partial_fill(
            filled_quantity=4000,
            fill_price=Decimal("1.0901"),
            commission=Decimal("1.00"),
        )

        assert order.state == OrderState.PARTIALLY_FILLED
        assert order.filled_quantity == 7000
        # Weighted average: (3000 * 1.0900 + 4000 * 1.0901) / 7000
        expected_avg = (
            Decimal("3000") * Decimal("1.0900") + Decimal("4000") * Decimal("1.0901")
        ) / Decimal("7000")
        assert abs(order.average_fill_price - expected_avg) < Decimal("0.0001")
        assert order.commission == Decimal("1.75")

        # Final fill
        order.partial_fill(
            filled_quantity=3000,
            fill_price=Decimal("1.0902"),
            commission=Decimal("0.75"),
        )

        assert order.state == OrderState.FILLED
        assert order.filled_quantity == 10000
        assert order.remaining_quantity == 0

    def test_order_cancellation(self):
        """RED: Test order cancellation."""
        from core.trading.orders import Order, OrderSide, OrderState, OrderType

        order = Order(
            symbol="EUR/USD",
            side=OrderSide.BUY,
            quantity=10000,
            order_type=OrderType.LIMIT,
            limit_price=Decimal("1.0900"),
            user_id="trader_123",
        )

        order.validate()
        order.submit(broker_id="IB", broker_order_id="IB123456")
        order.cancel(reason="User requested cancellation")

        assert order.state == OrderState.CANCELLED
        assert order.cancel_reason == "User requested cancellation"
        assert order.cancelled_at is not None

    def test_order_rejection(self):
        """RED: Test order rejection."""
        from core.trading.orders import Order, OrderSide, OrderState, OrderType

        order = Order(
            symbol="EUR/USD",
            side=OrderSide.BUY,
            quantity=1000000,  # Large order
            order_type=OrderType.MARKET,
            user_id="trader_123",
        )

        order.validate()
        order.reject(reason="Insufficient margin")

        assert order.state == OrderState.REJECTED
        assert order.reject_reason == "Insufficient margin"
        assert order.rejected_at is not None

    def test_order_expiration(self):
        """RED: Test order expiration for time-limited orders."""
        from core.trading.orders import Order, OrderSide, OrderState, OrderType

        expire_time = datetime.now() + timedelta(hours=1)
        order = Order(
            symbol="EUR/USD",
            side=OrderSide.BUY,
            quantity=10000,
            order_type=OrderType.LIMIT,
            limit_price=Decimal("1.0900"),
            user_id="trader_123",
            time_in_force="GTT",  # Good Till Time
            expire_time=expire_time,
        )

        order.validate()
        order.submit(broker_id="IB", broker_order_id="IB123456")

        # Simulate time passing
        with freeze_time(expire_time + timedelta(minutes=1)):
            order.check_expiration()

        assert order.state == OrderState.EXPIRED
        assert order.expired_at is not None

    def test_invalid_state_transition(self):
        """RED: Test that invalid state transitions are prevented."""
        from core.trading.orders import (
            InvalidStateTransition,
            Order,
            OrderSide,
            OrderState,
            OrderType,
        )

        order = Order(
            symbol="EUR/USD",
            side=OrderSide.BUY,
            quantity=10000,
            order_type=OrderType.MARKET,
            user_id="trader_123",
        )

        # Can't submit before validation
        with pytest.raises(InvalidStateTransition) as exc_info:
            order.submit(broker_id="IB", broker_order_id="IB123456")
        assert "Cannot transition from PENDING to SUBMITTED" in str(exc_info.value)

        # Validate and submit
        order.validate()
        order.submit(broker_id="IB", broker_order_id="IB123456")

        # Can't validate again
        with pytest.raises(InvalidStateTransition):
            order.validate()

        # Fill the order
        order.fill(
            filled_quantity=10000,
            fill_price=Decimal("1.0950"),
            commission=Decimal("2.50"),
        )

        # Can't cancel a filled order
        with pytest.raises(InvalidStateTransition) as exc_info:
            order.cancel(reason="Too late")
        assert "Cannot cancel order in state FILLED" in str(exc_info.value)

    def test_order_to_dict(self):
        """RED: Test order serialization to dictionary."""
        from core.trading.orders import Order, OrderSide, OrderType

        order = Order(
            symbol="EUR/USD",
            side=OrderSide.BUY,
            quantity=10000,
            order_type=OrderType.LIMIT,
            limit_price=Decimal("1.0900"),
            user_id="trader_123",
            time_in_force="GTC",
            notes="Test order",
        )

        order_dict = order.to_dict()

        assert order_dict["order_id"] == order.order_id
        assert order_dict["symbol"] == "EUR/USD"
        assert order_dict["side"] == "buy"
        assert order_dict["quantity"] == 10000
        assert order_dict["order_type"] == "limit"
        assert order_dict["limit_price"] == "1.0900"
        assert order_dict["state"] == "pending"
        assert order_dict["user_id"] == "trader_123"
        assert order_dict["time_in_force"] == "GTC"
        assert order_dict["notes"] == "Test order"
        assert "created_at" in order_dict
        assert "updated_at" in order_dict

    def test_order_from_dict(self):
        """RED: Test order deserialization from dictionary."""
        from core.trading.orders import Order

        order_data = {
            "order_id": "550e8400-e29b-41d4-a716-446655440000",
            "symbol": "GBP/USD",
            "side": "sell",
            "quantity": 50000,
            "order_type": "market",
            "state": "pending",
            "user_id": "trader_456",
            "created_at": "2024-01-15T10:30:00Z",
            "updated_at": "2024-01-15T10:30:00Z",
        }

        order = Order.from_dict(order_data)

        assert order.order_id == "550e8400-e29b-41d4-a716-446655440000"
        assert order.symbol == "GBP/USD"
        assert order.side.value == "sell"
        assert order.quantity == 50000
        assert order.order_type.value == "market"
        assert order.state.value == "pending"
        assert order.user_id == "trader_456"


@pytest.mark.tdd
@pytest.mark.red
class TestOrderManager:
    """
    RED Phase: Test order manager that doesn't exist yet.

    Tests cover order lifecycle management, persistence, and broker integration.
    """

    def test_order_manager_import(self):
        """RED: Test that we can import the OrderManager."""
        from core.trading.orders import OrderManager

        manager = OrderManager()
        assert manager is not None

    @pytest.mark.asyncio
    async def test_create_order(self):
        """RED: Test creating an order through the manager."""
        from core.trading.orders import OrderManager, OrderSide, OrderType

        manager = OrderManager()

        order = await manager.create_order(
            user_id="trader_123",
            symbol="EUR/USD",
            side=OrderSide.BUY,
            quantity=10000,
            order_type=OrderType.MARKET,
        )

        assert order.order_id is not None
        assert order.state.value == "pending"
        assert order.symbol == "EUR/USD"

    @pytest.mark.asyncio
    async def test_validate_order_with_risk_checks(self):
        """RED: Test order validation with risk management."""
        from core.trading.orders import OrderManager, OrderSide, OrderType

        # Mock risk manager
        risk_manager = MagicMock()
        risk_manager.check_order_risk = AsyncMock(return_value=True)

        manager = OrderManager(risk_manager=risk_manager)

        order = await manager.create_order(
            user_id="trader_123",
            symbol="EUR/USD",
            side=OrderSide.BUY,
            quantity=10000,
            order_type=OrderType.MARKET,
        )

        # Validate with risk checks
        validated = await manager.validate_order(order.order_id)

        assert validated.state.value == "validated"
        risk_manager.check_order_risk.assert_called_once_with(order)

    @pytest.mark.asyncio
    async def test_submit_order_to_broker(self):
        """RED: Test submitting order to broker."""
        from core.trading.orders import OrderManager, OrderSide, OrderType

        # Mock broker client
        broker_client = MagicMock()
        broker_client.submit_order = AsyncMock(
            return_value={"broker_order_id": "IB123456", "status": "accepted"}
        )

        manager = OrderManager(broker_client=broker_client)

        order = await manager.create_order(
            user_id="trader_123",
            symbol="EUR/USD",
            side=OrderSide.BUY,
            quantity=10000,
            order_type=OrderType.MARKET,
        )

        await manager.validate_order(order.order_id)
        submitted = await manager.submit_order(order.order_id)

        assert submitted.state.value == "submitted"
        assert submitted.broker_order_id == "IB123456"
        broker_client.submit_order.assert_called_once()

    @pytest.mark.asyncio
    async def test_cancel_order(self):
        """RED: Test cancelling an order."""
        from core.trading.orders import OrderManager, OrderSide, OrderType

        # Mock broker client
        broker_client = MagicMock()
        broker_client.cancel_order = AsyncMock(return_value={"status": "cancelled"})

        manager = OrderManager(broker_client=broker_client)

        order = await manager.create_order(
            user_id="trader_123",
            symbol="EUR/USD",
            side=OrderSide.BUY,
            quantity=10000,
            order_type=OrderType.LIMIT,
            limit_price=Decimal("1.0900"),
        )

        await manager.validate_order(order.order_id)
        await manager.submit_order(order.order_id)

        # Cancel the order
        cancelled = await manager.cancel_order(order.order_id, reason="User requested")

        assert cancelled.state.value == "cancelled"
        assert cancelled.cancel_reason == "User requested"
        broker_client.cancel_order.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_order_by_id(self):
        """RED: Test retrieving order by ID."""
        from core.trading.orders import OrderManager, OrderSide, OrderType

        manager = OrderManager()

        order = await manager.create_order(
            user_id="trader_123",
            symbol="EUR/USD",
            side=OrderSide.BUY,
            quantity=10000,
            order_type=OrderType.MARKET,
        )

        retrieved = await manager.get_order(order.order_id)

        assert retrieved.order_id == order.order_id
        assert retrieved.symbol == order.symbol

    @pytest.mark.asyncio
    async def test_get_orders_by_user(self):
        """RED: Test retrieving orders by user."""
        from core.trading.orders import OrderManager, OrderSide, OrderType

        manager = OrderManager()

        # Create multiple orders
        order1 = await manager.create_order(
            user_id="trader_123",
            symbol="EUR/USD",
            side=OrderSide.BUY,
            quantity=10000,
            order_type=OrderType.MARKET,
        )

        order2 = await manager.create_order(
            user_id="trader_123",
            symbol="GBP/USD",
            side=OrderSide.SELL,
            quantity=5000,
            order_type=OrderType.LIMIT,
            limit_price=Decimal("1.2750"),
        )

        order3 = await manager.create_order(
            user_id="trader_456",
            symbol="USD/JPY",
            side=OrderSide.BUY,
            quantity=100000,
            order_type=OrderType.MARKET,
        )

        # Get orders for trader_123
        user_orders = await manager.get_user_orders("trader_123")

        assert len(user_orders) == 2
        order_ids = [o.order_id for o in user_orders]
        assert order1.order_id in order_ids
        assert order2.order_id in order_ids
        assert order3.order_id not in order_ids

    @pytest.mark.asyncio
    async def test_get_active_orders(self):
        """RED: Test retrieving active orders."""
        from core.trading.orders import OrderManager, OrderSide, OrderType

        manager = OrderManager()

        # Create and submit an order
        order1 = await manager.create_order(
            user_id="trader_123",
            symbol="EUR/USD",
            side=OrderSide.BUY,
            quantity=10000,
            order_type=OrderType.LIMIT,
            limit_price=Decimal("1.0900"),
        )
        await manager.validate_order(order1.order_id)

        # Create and fill an order
        order2 = await manager.create_order(
            user_id="trader_123",
            symbol="GBP/USD",
            side=OrderSide.SELL,
            quantity=5000,
            order_type=OrderType.MARKET,
        )
        await manager.validate_order(order2.order_id)
        await manager.submit_order(order2.order_id)  # Must submit before filling
        order2.fill(
            filled_quantity=5000,
            fill_price=Decimal("1.2750"),
            commission=Decimal("1.25"),
        )

        # Get active orders
        active_orders = await manager.get_active_orders()

        assert len(active_orders) == 1
        assert active_orders[0].order_id == order1.order_id

    @pytest.mark.asyncio
    async def test_handle_fill_notification(self):
        """RED: Test handling fill notification from broker."""
        from core.trading.orders import OrderManager, OrderSide, OrderType

        manager = OrderManager()

        order = await manager.create_order(
            user_id="trader_123",
            symbol="EUR/USD",
            side=OrderSide.BUY,
            quantity=10000,
            order_type=OrderType.MARKET,
        )

        await manager.validate_order(order.order_id)
        submitted = await manager.submit_order(order.order_id)

        # Handle fill notification
        await manager.handle_fill(
            broker_order_id=submitted.broker_order_id,
            filled_quantity=10000,
            fill_price=Decimal("1.0950"),
            commission=Decimal("2.50"),
        )

        updated_order = await manager.get_order(order.order_id)
        assert updated_order.state.value == "filled"
        assert updated_order.filled_quantity == 10000
        assert updated_order.average_fill_price == Decimal("1.0950")
