"""
Position Tracking and P&L Calculation System for FXML4

TDD-driven implementation of position management and P&L calculation.
Following Green phase - minimal implementation to pass tests.
"""

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, List, Optional


class PositionSide(str, Enum):
    """Position side enumeration."""

    LONG = "long"
    SHORT = "short"
    FLAT = "flat"


@dataclass
class Position:
    """Position model with P&L tracking."""

    # Required fields
    symbol: str
    quantity: int
    entry_price: Decimal
    side: PositionSide
    user_id: str

    # Optional fields
    notes: Optional[str] = None

    # System fields (set automatically)
    position_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    # Position status
    is_open: bool = True
    exit_price: Optional[Decimal] = None
    closed_at: Optional[datetime] = None

    # P&L tracking
    realized_pnl: Decimal = Decimal("0")
    commission_paid: Decimal = Decimal("0")

    # Related orders
    entry_order_id: Optional[str] = None
    exit_order_id: Optional[str] = None

    def calculate_unrealized_pnl(self, current_price: Decimal) -> Decimal:
        """Calculate unrealized P&L based on current market price."""
        if not self.is_open:
            return Decimal("0")

        if self.side == PositionSide.LONG:
            # Long position: profit when price increases
            return (current_price - self.entry_price) * Decimal(self.quantity)
        elif self.side == PositionSide.SHORT:
            # Short position: profit when price decreases
            return (self.entry_price - current_price) * Decimal(self.quantity)
        else:
            return Decimal("0")

    def close(self, exit_price: Decimal, commission: Decimal = Decimal("0")):
        """Close the position and calculate realized P&L."""
        if not self.is_open:
            raise ValueError("Position is already closed")

        self.exit_price = exit_price
        self.closed_at = datetime.now()
        self.is_open = False
        self.commission_paid += commission

        # Calculate realized P&L
        if self.side == PositionSide.LONG:
            gross_pnl = (exit_price - self.entry_price) * Decimal(self.quantity)
        elif self.side == PositionSide.SHORT:
            gross_pnl = (self.entry_price - exit_price) * Decimal(self.quantity)
        else:
            gross_pnl = Decimal("0")

        self.realized_pnl = gross_pnl - commission
        self.updated_at = datetime.now()

    def partial_close(
        self, close_quantity: int, exit_price: Decimal, commission: Decimal = Decimal("0")
    ) -> "Position":
        """Partially close position and return the closed portion."""
        if close_quantity > self.quantity:
            raise ValueError("Cannot close more than the position quantity")

        # Calculate P&L for closed portion
        if self.side == PositionSide.LONG:
            gross_pnl = (exit_price - self.entry_price) * Decimal(close_quantity)
        elif self.side == PositionSide.SHORT:
            gross_pnl = (self.entry_price - exit_price) * Decimal(close_quantity)
        else:
            gross_pnl = Decimal("0")

        # Create new position for closed portion
        closed_position = Position(
            symbol=self.symbol,
            quantity=close_quantity,
            entry_price=self.entry_price,
            side=self.side,
            user_id=self.user_id,
        )
        closed_position.is_open = False
        closed_position.exit_price = exit_price
        closed_position.closed_at = datetime.now()
        closed_position.realized_pnl = gross_pnl - commission
        closed_position.commission_paid = commission

        # Reduce original position
        self.quantity -= close_quantity
        self.updated_at = datetime.now()

        return closed_position

    def add_to_position(self, add_quantity: int, add_price: Decimal, commission: Decimal = Decimal("0")):
        """Add to existing position and recalculate average entry price."""
        # Calculate new weighted average entry price
        total_value = (self.quantity * self.entry_price) + (add_quantity * add_price)
        new_quantity = self.quantity + add_quantity

        self.entry_price = total_value / Decimal(new_quantity)
        self.quantity = new_quantity
        self.commission_paid += commission
        self.updated_at = datetime.now()

    def to_dict(self) -> Dict[str, Any]:
        """Convert position to dictionary."""
        return {
            "position_id": self.position_id,
            "symbol": self.symbol,
            "quantity": self.quantity,
            "entry_price": str(self.entry_price),
            "side": self.side.value,
            "user_id": self.user_id,
            "notes": self.notes,
            "is_open": self.is_open,
            "exit_price": str(self.exit_price) if self.exit_price else None,
            "realized_pnl": str(self.realized_pnl),
            "commission_paid": str(self.commission_paid),
            "entry_order_id": self.entry_order_id,
            "exit_order_id": self.exit_order_id,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "closed_at": self.closed_at.isoformat() if self.closed_at else None,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Position":
        """Create position from dictionary."""
        position = cls(
            symbol=data["symbol"],
            quantity=data["quantity"],
            entry_price=Decimal(data["entry_price"]),
            side=PositionSide(data["side"]),
            user_id=data["user_id"],
        )

        # Set position ID
        position.position_id = data["position_id"]

        # Set optional fields
        position.is_open = data.get("is_open", True)
        position.realized_pnl = Decimal(data.get("realized_pnl", "0"))
        position.commission_paid = Decimal(data.get("commission_paid", "0"))

        # Parse timestamps
        position.created_at = datetime.fromisoformat(data["created_at"])
        position.updated_at = datetime.fromisoformat(data["updated_at"])

        if data.get("exit_price"):
            position.exit_price = Decimal(data["exit_price"])
        if data.get("closed_at"):
            position.closed_at = datetime.fromisoformat(data["closed_at"])

        return position


class PositionManager:
    """Manager for position lifecycle and P&L calculations."""

    def __init__(self, price_provider=None):
        """Initialize position manager."""
        self.positions: Dict[str, Position] = {}
        self.price_provider = price_provider

    async def open_position_from_order(self, order) -> Position:
        """Open a new position from a filled order."""
        from core.trading.orders import OrderSide, OrderState

        if order.state != OrderState.FILLED:
            raise ValueError("Order must be filled to open a position")

        # Determine position side from order side
        if order.side == OrderSide.BUY:
            position_side = PositionSide.LONG
        else:
            position_side = PositionSide.SHORT

        position = Position(
            symbol=order.symbol,
            quantity=order.filled_quantity,
            entry_price=order.average_fill_price,
            side=position_side,
            user_id=order.user_id,
        )
        position.entry_order_id = order.order_id
        position.commission_paid = order.commission

        self.positions[position.position_id] = position
        return position

    async def update_position_from_order(self, position_id: str, order) -> Position:
        """Update existing position from a new order in the same direction."""
        from core.trading.orders import OrderState

        if order.state != OrderState.FILLED:
            raise ValueError("Order must be filled to update position")

        position = self.positions.get(position_id)
        if not position:
            raise ValueError(f"Position {position_id} not found")

        position.add_to_position(
            add_quantity=order.filled_quantity,
            add_price=order.average_fill_price,
            commission=order.commission
        )

        return position

    async def close_position_from_order(self, position_id: str, order) -> Position:
        """Close a position from an opposite order."""
        from core.trading.orders import OrderState

        if order.state != OrderState.FILLED:
            raise ValueError("Order must be filled to close position")

        position = self.positions.get(position_id)
        if not position:
            raise ValueError(f"Position {position_id} not found")

        position.close(
            exit_price=order.average_fill_price,
            commission=order.commission
        )
        position.exit_order_id = order.order_id

        return position

    async def get_open_positions(self) -> List[Position]:
        """Get all open positions."""
        return [p for p in self.positions.values() if p.is_open]

    async def get_user_positions(self, user_id: str) -> List[Position]:
        """Get all positions for a user."""
        return [p for p in self.positions.values() if p.user_id == user_id]

    async def get_position_by_symbol(
        self, user_id: str, symbol: str
    ) -> Optional[Position]:
        """Get open position for a user and symbol."""
        for position in self.positions.values():
            if (
                position.user_id == user_id
                and position.symbol == symbol
                and position.is_open
            ):
                return position
        return None

    async def calculate_total_pnl(self, user_id: str) -> Dict[str, Decimal]:
        """Calculate total P&L for a user."""
        unrealized_pnl = Decimal("0")
        realized_pnl = Decimal("0")

        for position in self.positions.values():
            if position.user_id != user_id:
                continue

            if position.is_open:
                # Get current price for unrealized P&L
                if self.price_provider:
                    current_price = await self.price_provider.get_price(position.symbol)
                    unrealized_pnl += position.calculate_unrealized_pnl(current_price)
            else:
                # Add realized P&L from closed positions
                realized_pnl += position.realized_pnl

        return {
            "unrealized_pnl": unrealized_pnl,
            "realized_pnl": realized_pnl,
            "total_pnl": unrealized_pnl + realized_pnl,
        }

    async def aggregate_positions(
        self, user_id: str, symbol: str
    ) -> Dict[str, Any]:
        """Aggregate multiple positions for the same symbol."""
        long_positions = []
        short_positions = []

        for position in self.positions.values():
            if (
                position.user_id == user_id
                and position.symbol == symbol
                and position.is_open
            ):
                if position.side == PositionSide.LONG:
                    long_positions.append(position)
                elif position.side == PositionSide.SHORT:
                    short_positions.append(position)

        # Calculate aggregates
        long_quantity = sum(p.quantity for p in long_positions)
        short_quantity = sum(p.quantity for p in short_positions)
        net_quantity = long_quantity - short_quantity

        # Calculate weighted average prices
        avg_long_price = Decimal("0")
        if long_quantity > 0:
            total_long_value = sum(
                p.quantity * p.entry_price for p in long_positions
            )
            avg_long_price = total_long_value / Decimal(long_quantity)

        avg_short_price = Decimal("0")
        if short_quantity > 0:
            total_short_value = sum(
                p.quantity * p.entry_price for p in short_positions
            )
            avg_short_price = total_short_value / Decimal(short_quantity)

        return {
            "symbol": symbol,
            "net_quantity": abs(net_quantity),
            "net_side": "long" if net_quantity > 0 else ("short" if net_quantity < 0 else "flat"),
            "long_quantity": long_quantity,
            "short_quantity": short_quantity,
            "average_long_price": avg_long_price,
            "average_short_price": avg_short_price,
        }