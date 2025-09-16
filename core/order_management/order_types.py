"""
Order types and enums for FXML4 Order Management System.

Defines all order-related data structures including:
- Order class with comprehensive attributes
- Order type enumerations
- Order status tracking
- Order side definitions
- Time-in-force options
"""

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, Optional


class OrderType(Enum):
    """Order type enumeration."""

    MARKET = "market"
    LIMIT = "limit"
    STOP = "stop"
    STOP_LIMIT = "stop_limit"
    TRAILING_STOP = "trailing_stop"
    OCO = "oco"  # One-Cancels-Other
    ICEBERG = "iceberg"


class OrderSide(Enum):
    """Order side enumeration."""

    BUY = "buy"
    SELL = "sell"


class OrderStatus(Enum):
    """Order status enumeration."""

    PENDING = "pending"
    SUBMITTED = "submitted"
    ACKNOWLEDGED = "acknowledged"
    PARTIALLY_FILLED = "partially_filled"
    FILLED = "filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"
    EXPIRED = "expired"


class TimeInForce(Enum):
    """Time in force enumeration."""

    DAY = "day"
    GTC = "gtc"  # Good Till Cancelled
    IOC = "ioc"  # Immediate or Cancel
    FOK = "fok"  # Fill or Kill
    GTD = "gtd"  # Good Till Date


@dataclass
class Order:
    """Comprehensive order data structure."""

    order_id: str
    symbol: str
    order_type: OrderType
    side: OrderSide
    quantity: int
    client_id: str
    created_at: datetime = field(default_factory=datetime.utcnow)

    # Optional price fields
    price: Optional[Decimal] = None
    stop_price: Optional[Decimal] = None
    trailing_amount: Optional[Decimal] = None

    # Order management
    time_in_force: str = "IOC"
    priority: str = "normal"
    status: OrderStatus = OrderStatus.PENDING

    # Execution details
    filled_quantity: int = 0
    remaining_quantity: Optional[int] = None
    average_fill_price: Optional[Decimal] = None

    # Routing information
    target_broker: Optional[str] = None
    routed_broker: Optional[str] = None
    routing_reason: Optional[str] = None

    # Timestamps
    submitted_at: Optional[datetime] = None
    acknowledged_at: Optional[datetime] = None
    filled_at: Optional[datetime] = None

    # Additional metadata
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        """Post-initialization processing."""
        if self.remaining_quantity is None:
            self.remaining_quantity = self.quantity

    @property
    def is_buy(self) -> bool:
        """Check if order is a buy order."""
        return self.side == OrderSide.BUY

    @property
    def is_sell(self) -> bool:
        """Check if order is a sell order."""
        return self.side == OrderSide.SELL

    @property
    def is_market_order(self) -> bool:
        """Check if order is a market order."""
        return self.order_type == OrderType.MARKET

    @property
    def is_limit_order(self) -> bool:
        """Check if order is a limit order."""
        return self.order_type == OrderType.LIMIT

    @property
    def is_partially_filled(self) -> bool:
        """Check if order is partially filled."""
        return 0 < self.filled_quantity < self.quantity

    @property
    def fill_percentage(self) -> float:
        """Get fill percentage."""
        if self.quantity == 0:
            return 0.0
        return (self.filled_quantity / self.quantity) * 100.0
