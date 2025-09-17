"""
Order Management System for FXML4 Trading Platform

TDD-driven implementation of order lifecycle management.
Following Green phase - minimal implementation to pass tests.
"""

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, List, Optional


class OrderState(str, Enum):
    """Order state enumeration."""

    PENDING = "pending"
    VALIDATED = "validated"
    SUBMITTED = "submitted"
    PARTIALLY_FILLED = "partially_filled"
    FILLED = "filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"
    EXPIRED = "expired"


class OrderType(str, Enum):
    """Order type enumeration."""

    MARKET = "market"
    LIMIT = "limit"
    STOP = "stop"
    STOP_LIMIT = "stop_limit"
    TRAILING_STOP = "trailing_stop"


class OrderSide(str, Enum):
    """Order side enumeration."""

    BUY = "buy"
    SELL = "sell"


class OrderValidationError(Exception):
    """Raised when order validation fails."""

    pass


class InvalidStateTransition(Exception):
    """Raised when an invalid state transition is attempted."""

    pass


@dataclass
class Order:
    """Order model with lifecycle management."""

    # Required fields
    symbol: str
    side: OrderSide
    quantity: int
    order_type: OrderType
    user_id: str = ""

    # Optional fields
    limit_price: Optional[Decimal] = None
    stop_price: Optional[Decimal] = None
    time_in_force: str = "DAY"
    expire_time: Optional[datetime] = None
    notes: Optional[str] = None

    # System fields (set automatically)
    order_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    state: OrderState = field(default=OrderState.PENDING)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    # Execution fields
    filled_quantity: int = 0
    average_fill_price: Optional[Decimal] = None
    commission: Decimal = Decimal("0")

    # Broker fields
    broker_id: Optional[str] = None
    broker_order_id: Optional[str] = None

    # Status timestamps
    validated_at: Optional[datetime] = None
    submitted_at: Optional[datetime] = None
    filled_at: Optional[datetime] = None
    cancelled_at: Optional[datetime] = None
    rejected_at: Optional[datetime] = None
    expired_at: Optional[datetime] = None

    # Cancellation/rejection reasons
    cancel_reason: Optional[str] = None
    reject_reason: Optional[str] = None

    def __post_init__(self):
        """Validate order after initialization."""
        self._validate_initial_state()

    def _validate_initial_state(self):
        """Validate order parameters on creation."""
        # Validate minimum quantity (1000 for forex)
        if self.quantity < 1000:
            raise OrderValidationError("Quantity must be at least 1000")

        # Validate symbol format (XXX/YYY)
        if not self._is_valid_symbol(self.symbol):
            raise OrderValidationError("Invalid symbol format")

        # Validate limit price for limit orders
        if self.order_type in [OrderType.LIMIT, OrderType.STOP_LIMIT]:
            if self.limit_price is None:
                raise OrderValidationError("Limit price required for limit orders")

        # Validate stop price for stop orders
        if self.order_type in [
            OrderType.STOP,
            OrderType.STOP_LIMIT,
            OrderType.TRAILING_STOP,
        ]:
            if self.stop_price is None:
                raise OrderValidationError("Stop price required for stop orders")

    def _is_valid_symbol(self, symbol: str) -> bool:
        """Check if symbol is in XXX/YYY format."""
        parts = symbol.split("/")
        if len(parts) != 2:
            return False
        return len(parts[0]) == 3 and len(parts[1]) == 3

    @property
    def remaining_quantity(self) -> int:
        """Calculate remaining quantity to be filled."""
        return self.quantity - self.filled_quantity

    def validate(self):
        """Validate order and transition to VALIDATED state."""
        if self.state != OrderState.PENDING:
            raise InvalidStateTransition(
                f"Cannot transition from {self.state.value.upper()} to VALIDATED"
            )

        self.state = OrderState.VALIDATED
        self.validated_at = datetime.now()
        self.updated_at = datetime.now()

    def submit(self, broker_id: str, broker_order_id: str):
        """Submit order to broker."""
        if self.state != OrderState.VALIDATED:
            raise InvalidStateTransition(
                f"Cannot transition from {self.state.value.upper()} to SUBMITTED"
            )

        self.state = OrderState.SUBMITTED
        self.broker_id = broker_id
        self.broker_order_id = broker_order_id
        self.submitted_at = datetime.now()
        self.updated_at = datetime.now()

    def fill(self, filled_quantity: int, fill_price: Decimal, commission: Decimal):
        """Mark order as filled."""
        if self.state not in [OrderState.SUBMITTED, OrderState.PARTIALLY_FILLED]:
            raise InvalidStateTransition(
                f"Cannot fill order in state {self.state.value.upper()}"
            )

        self.state = OrderState.FILLED
        self.filled_quantity = filled_quantity
        self.average_fill_price = fill_price
        self.commission = commission
        self.filled_at = datetime.now()
        self.updated_at = datetime.now()

    def partial_fill(
        self, filled_quantity: int, fill_price: Decimal, commission: Decimal
    ):
        """Process partial fill."""
        if self.state not in [OrderState.SUBMITTED, OrderState.PARTIALLY_FILLED]:
            raise InvalidStateTransition(
                f"Cannot partially fill order in state {self.state.value.upper()}"
            )

        # Calculate weighted average fill price
        prev_value = self.filled_quantity * (self.average_fill_price or Decimal("0"))
        new_value = filled_quantity * fill_price
        total_quantity = self.filled_quantity + filled_quantity

        self.filled_quantity += filled_quantity
        self.average_fill_price = (prev_value + new_value) / Decimal(total_quantity)
        self.commission += commission

        # Update state based on fill status
        if self.filled_quantity >= self.quantity:
            self.state = OrderState.FILLED
            self.filled_at = datetime.now()
        else:
            self.state = OrderState.PARTIALLY_FILLED

        self.updated_at = datetime.now()

    def cancel(self, reason: str):
        """Cancel order."""
        if self.state in [OrderState.FILLED, OrderState.CANCELLED, OrderState.REJECTED]:
            raise InvalidStateTransition(
                f"Cannot cancel order in state {self.state.value.upper()}"
            )

        self.state = OrderState.CANCELLED
        self.cancel_reason = reason
        self.cancelled_at = datetime.now()
        self.updated_at = datetime.now()

    def reject(self, reason: str):
        """Reject order."""
        if self.state not in [OrderState.PENDING, OrderState.VALIDATED]:
            raise InvalidStateTransition(
                f"Cannot reject order in state {self.state.value.upper()}"
            )

        self.state = OrderState.REJECTED
        self.reject_reason = reason
        self.rejected_at = datetime.now()
        self.updated_at = datetime.now()

    def check_expiration(self):
        """Check if order has expired."""
        if self.expire_time and datetime.now() > self.expire_time:
            if self.state in [OrderState.SUBMITTED, OrderState.PARTIALLY_FILLED]:
                self.state = OrderState.EXPIRED
                self.expired_at = datetime.now()
                self.updated_at = datetime.now()

    def to_dict(self) -> Dict[str, Any]:
        """Convert order to dictionary."""
        return {
            "order_id": self.order_id,
            "symbol": self.symbol,
            "side": self.side.value,
            "quantity": self.quantity,
            "order_type": self.order_type.value,
            "state": self.state.value,
            "user_id": self.user_id,
            "limit_price": str(self.limit_price) if self.limit_price else None,
            "stop_price": str(self.stop_price) if self.stop_price else None,
            "time_in_force": self.time_in_force,
            "expire_time": self.expire_time.isoformat() if self.expire_time else None,
            "notes": self.notes,
            "filled_quantity": self.filled_quantity,
            "average_fill_price": (
                str(self.average_fill_price) if self.average_fill_price else None
            ),
            "commission": str(self.commission),
            "broker_id": self.broker_id,
            "broker_order_id": self.broker_order_id,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "validated_at": (
                self.validated_at.isoformat() if self.validated_at else None
            ),
            "submitted_at": (
                self.submitted_at.isoformat() if self.submitted_at else None
            ),
            "filled_at": self.filled_at.isoformat() if self.filled_at else None,
            "cancelled_at": (
                self.cancelled_at.isoformat() if self.cancelled_at else None
            ),
            "rejected_at": self.rejected_at.isoformat() if self.rejected_at else None,
            "expired_at": self.expired_at.isoformat() if self.expired_at else None,
            "cancel_reason": self.cancel_reason,
            "reject_reason": self.reject_reason,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Order":
        """Create order from dictionary."""
        # Parse enums
        side = OrderSide(data["side"])
        order_type = OrderType(data["order_type"])
        state = OrderState(data["state"])

        # Create order with basic fields
        order = cls(
            symbol=data["symbol"],
            side=side,
            quantity=data["quantity"],
            order_type=order_type,
            user_id=data.get("user_id", ""),
        )

        # Set order ID and state
        order.order_id = data["order_id"]
        order.state = state

        # Parse timestamps
        order.created_at = datetime.fromisoformat(data["created_at"])
        order.updated_at = datetime.fromisoformat(data["updated_at"])

        # Set optional fields
        if data.get("limit_price"):
            order.limit_price = Decimal(data["limit_price"])
        if data.get("stop_price"):
            order.stop_price = Decimal(data["stop_price"])

        return order


class OrderManager:
    """Manager for order lifecycle and broker integration."""

    def __init__(self, risk_manager=None, broker_client=None):
        """Initialize order manager."""
        self.orders: Dict[str, Order] = {}
        self.risk_manager = risk_manager
        self.broker_client = broker_client
        self.broker_orders: Dict[str, str] = {}  # broker_order_id -> order_id mapping

    async def create_order(
        self,
        user_id: str,
        symbol: str,
        side: OrderSide,
        quantity: int,
        order_type: OrderType,
        **kwargs,
    ) -> Order:
        """Create a new order."""
        order = Order(
            symbol=symbol,
            side=side,
            quantity=quantity,
            order_type=order_type,
            user_id=user_id,
            **kwargs,
        )

        self.orders[order.order_id] = order
        return order

    async def validate_order(self, order_id: str) -> Order:
        """Validate order with risk checks."""
        order = self.orders[order_id]

        # Perform risk checks if risk manager is available
        if self.risk_manager:
            risk_approved = await self.risk_manager.check_order_risk(order)
            if not risk_approved:
                order.reject("Risk check failed")
                return order

        order.validate()
        return order

    async def submit_order(self, order_id: str) -> Order:
        """Submit order to broker."""
        order = self.orders[order_id]

        # Submit to broker if client is available
        if self.broker_client:
            # Handle both sync and async broker clients
            if hasattr(self.broker_client.submit_order, "__call__"):
                result = self.broker_client.submit_order(order)
                if hasattr(result, "__await__"):
                    result = await result
            else:
                result = await self.broker_client.submit_order(order)

            broker_order_id = result.get("broker_order_id")

            if broker_order_id:
                order.submit(self.broker_client.__class__.__name__, broker_order_id)
                self.broker_orders[broker_order_id] = order_id
            else:
                order.reject("Broker submission failed")
        else:
            # Simulate submission for testing
            broker_order_id = f"TEST_{order_id[:8]}"
            order.submit("TEST", broker_order_id)
            self.broker_orders[broker_order_id] = order_id

        return order

    async def cancel_order(self, order_id: str, reason: str) -> Order:
        """Cancel an order."""
        order = self.orders[order_id]

        # Cancel with broker if submitted
        if self.broker_client and order.broker_order_id:
            # Handle both sync and async broker clients
            if hasattr(self.broker_client.cancel_order, "__call__"):
                result = self.broker_client.cancel_order(order.broker_order_id)
                if hasattr(result, "__await__"):
                    await result
            else:
                await self.broker_client.cancel_order(order.broker_order_id)

        order.cancel(reason)
        return order

    async def get_order(self, order_id: str) -> Order:
        """Get order by ID."""
        return self.orders.get(order_id)

    async def get_user_orders(self, user_id: str) -> List[Order]:
        """Get all orders for a user."""
        return [order for order in self.orders.values() if order.user_id == user_id]

    async def get_active_orders(self) -> List[Order]:
        """Get all active orders."""
        active_states = [
            OrderState.PENDING,
            OrderState.VALIDATED,
            OrderState.SUBMITTED,
            OrderState.PARTIALLY_FILLED,
        ]

        return [order for order in self.orders.values() if order.state in active_states]

    async def handle_fill(
        self,
        broker_order_id: str,
        filled_quantity: int,
        fill_price: Decimal,
        commission: Decimal,
    ):
        """Handle fill notification from broker."""
        order_id = self.broker_orders.get(broker_order_id)
        if order_id:
            order = self.orders[order_id]

            if filled_quantity >= order.quantity:
                order.fill(filled_quantity, fill_price, commission)
            else:
                order.partial_fill(filled_quantity, fill_price, commission)
