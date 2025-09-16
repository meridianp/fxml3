"""
Trading Models for FXML4.

Defines core trading data structures and models.
"""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship

# Import Position from risk_management module (already available)
from ..risk_management import Position

Base = declarative_base()


class OrderSide(Enum):
    """Order side enumeration."""

    BUY = "buy"
    SELL = "sell"


class OrderStatus(Enum):
    """Order status enumeration."""

    PENDING = "pending"
    SUBMITTED = "submitted"
    PARTIALLY_FILLED = "partially_filled"
    FILLED = "filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"


class Trade(Base):
    """
    Trading record model representing executed trades.

    This model stores all executed trade information for regulatory reporting
    and compliance tracking.
    """

    __tablename__ = "trades"

    id = Column(String, primary_key=True)
    timestamp = Column(DateTime, nullable=False, index=True)
    symbol = Column(String, nullable=False, index=True)
    side = Column(String, nullable=False)  # buy/sell
    quantity = Column(Float, nullable=False)
    price = Column(Float, nullable=False)
    counterparty = Column(String)
    execution_venue = Column(String)
    order_id = Column(String, index=True)
    settlement_date = Column(DateTime)
    commission = Column(Float, default=0.0)

    # Foreign key relationships
    user_id = Column(Integer, ForeignKey("users.id"))
    account_id = Column(String, index=True)

    # Relationships
    user = relationship("User", back_populates="trades")

    def __repr__(self):
        return f"<Trade(id={self.id}, symbol={self.symbol}, side={self.side}, quantity={self.quantity}, price={self.price})>"


@dataclass
class ExecutionReport:
    """
    Execution report data structure.

    Represents trade execution information received from brokers.
    Used for real-time trade processing and surveillance.
    """

    exec_id: str
    order_id: str
    symbol: str
    side: str
    quantity: float
    price: float
    exec_type: str  # NEW, PARTIAL_FILL, FILL, CANCELLED, etc.
    order_status: str
    leaves_qty: float  # Remaining quantity
    cum_qty: float  # Cumulative filled quantity
    avg_px: float  # Average fill price
    exec_time: datetime
    text: Optional[str] = None

    # Additional fields for compliance
    counterparty: Optional[str] = None
    execution_venue: Optional[str] = None
    trader_id: Optional[str] = None
    account_id: Optional[str] = None
    commission: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert execution report to dictionary."""
        return {
            "exec_id": self.exec_id,
            "order_id": self.order_id,
            "symbol": self.symbol,
            "side": self.side,
            "quantity": self.quantity,
            "price": self.price,
            "exec_type": self.exec_type,
            "order_status": self.order_status,
            "leaves_qty": self.leaves_qty,
            "cum_qty": self.cum_qty,
            "avg_px": self.avg_px,
            "exec_time": self.exec_time.isoformat() if self.exec_time else None,
            "text": self.text,
            "counterparty": self.counterparty,
            "execution_venue": self.execution_venue,
            "trader_id": self.trader_id,
            "account_id": self.account_id,
            "commission": self.commission,
        }


@dataclass
class NewOrderSingle:
    """
    New Order Single message data structure.

    Represents a new order being submitted to the market.
    """

    cl_ord_id: str  # Client Order ID
    symbol: str
    side: str
    quantity: float
    ord_type: str  # MARKET, LIMIT, STOP, etc.
    price: Optional[float] = None
    stop_px: Optional[float] = None
    time_in_force: str = "DAY"  # DAY, GTC, IOC, FOK

    # Additional fields
    account: Optional[str] = None
    trader_id: Optional[str] = None
    text: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert new order to dictionary."""
        return {
            "cl_ord_id": self.cl_ord_id,
            "symbol": self.symbol,
            "side": self.side,
            "quantity": self.quantity,
            "ord_type": self.ord_type,
            "price": self.price,
            "stop_px": self.stop_px,
            "time_in_force": self.time_in_force,
            "account": self.account,
            "trader_id": self.trader_id,
            "text": self.text,
        }


class Order(Base):
    """
    Order model for tracking submitted orders.
    """

    __tablename__ = "orders"

    id = Column(String, primary_key=True)
    cl_ord_id = Column(String, unique=True, index=True)  # Client Order ID
    symbol = Column(String, nullable=False, index=True)
    side = Column(String, nullable=False)
    quantity = Column(Float, nullable=False)
    ord_type = Column(String, nullable=False)  # MARKET, LIMIT, etc.
    price = Column(Float)
    stop_px = Column(Float)
    time_in_force = Column(String, default="DAY")

    # Status tracking
    status = Column(String, nullable=False, default="PENDING")
    leaves_qty = Column(Float, nullable=False)  # Remaining quantity
    cum_qty = Column(Float, default=0.0)  # Filled quantity
    avg_px = Column(Float, default=0.0)  # Average fill price

    # Timestamps
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(
        DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Foreign keys
    user_id = Column(Integer, ForeignKey("users.id"))
    account_id = Column(String, index=True)

    # Additional fields
    text = Column(Text)

    # Relationships
    user = relationship("User", back_populates="orders")

    def __repr__(self):
        return f"<Order(id={self.id}, symbol={self.symbol}, side={self.side}, quantity={self.quantity}, status={self.status})>"


# Re-export Position from risk_management for convenience
__all__ = [
    "Trade",
    "ExecutionReport",
    "NewOrderSingle",
    "Order",
    "Position",  # Re-exported from risk_management
    "OrderSide",
    "OrderStatus",
]
