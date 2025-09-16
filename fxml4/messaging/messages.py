"""
Message classes for FXML4 async message routing system.

These classes define the core message types used throughout the trading system
for order management, risk checking, and execution coordination across brokers.
"""

import json
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, Optional
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator


class MessagePriority(Enum):
    """Message priority levels for queue processing."""

    LOW = 1
    NORMAL = 5
    HIGH = 8
    CRITICAL = 10


class OrderSide(Enum):
    """Order side enumeration."""

    BUY = "BUY"
    SELL = "SELL"


class OrderType(Enum):
    """Order type enumeration."""

    MARKET = "MARKET"
    LIMIT = "LIMIT"
    STOP = "STOP"
    STOP_LIMIT = "STOP_LIMIT"


class OrderStatus(Enum):
    """Order status enumeration."""

    NEW = "NEW"
    PENDING_NEW = "PENDING_NEW"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    FILLED = "FILLED"
    PENDING_CANCEL = "PENDING_CANCEL"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"


class RiskCheckStatus(Enum):
    """Risk check status enumeration."""

    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    REQUIRES_MANUAL_REVIEW = "REQUIRES_MANUAL_REVIEW"


class BaseMessage(BaseModel):
    """Base message class with common fields."""

    message_id: str = Field(default_factory=lambda: str(uuid4()))
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    correlation_id: Optional[str] = None
    priority: MessagePriority = MessagePriority.NORMAL
    retry_count: int = 0
    max_retries: int = 3

    model_config = ConfigDict(
        json_encoders={datetime: lambda v: v.isoformat(), Decimal: lambda v: str(v)}
    )


class OrderMessage(BaseMessage):
    """Order message for routing trade orders through the system."""

    order_id: str
    client_order_id: str
    symbol: str
    side: OrderSide
    order_type: OrderType
    quantity: Decimal
    price: Optional[Decimal] = None
    stop_price: Optional[Decimal] = None
    time_in_force: str = "DAY"
    broker: str
    account_id: str
    strategy_id: Optional[str] = None

    # Risk management fields
    position_size_usd: Optional[Decimal] = None
    max_loss_usd: Optional[Decimal] = None
    risk_score: Optional[float] = None

    # Execution tracking
    status: OrderStatus = OrderStatus.NEW
    filled_quantity: Decimal = Decimal("0")
    avg_fill_price: Optional[Decimal] = None
    commission: Optional[Decimal] = None

    @field_validator(
        "quantity",
        "price",
        "stop_price",
        "position_size_usd",
        "max_loss_usd",
        "filled_quantity",
        "avg_fill_price",
        "commission",
        mode="before",
    )
    @classmethod
    def convert_to_decimal(cls, v):
        """Convert numeric fields to Decimal for precision."""
        if v is None:
            return v
        return Decimal(str(v))

    def to_json(self) -> str:
        """Serialize message to JSON string."""
        return self.model_dump_json()

    @classmethod
    def from_json(cls, json_str: str) -> "OrderMessage":
        """Deserialize message from JSON string."""
        return cls.model_validate_json(json_str)

    def get_routing_key(self) -> str:
        """Get routing key for this message."""
        return f"order.{self.broker}.{self.symbol}"


class RiskCheckMessage(BaseMessage):
    """Risk check message for validating trades before execution."""

    order_id: str
    symbol: str
    side: OrderSide
    quantity: Decimal
    price: Optional[Decimal] = None
    account_id: str

    # Risk parameters
    position_size_usd: Decimal
    account_balance: Decimal
    current_exposure: Decimal
    max_position_size: Decimal
    max_daily_loss: Decimal
    current_daily_pnl: Decimal

    # Risk check results
    status: RiskCheckStatus = RiskCheckStatus.PENDING
    risk_score: Optional[float] = None
    risk_factors: Dict[str, Any] = Field(default_factory=dict)
    rejection_reason: Optional[str] = None
    approved_quantity: Optional[Decimal] = None

    @field_validator(
        "quantity",
        "price",
        "position_size_usd",
        "account_balance",
        "current_exposure",
        "max_position_size",
        "max_daily_loss",
        "current_daily_pnl",
        "approved_quantity",
        mode="before",
    )
    @classmethod
    def convert_to_decimal(cls, v):
        """Convert numeric fields to Decimal for precision."""
        if v is None:
            return v
        return Decimal(str(v))

    def to_json(self) -> str:
        """Serialize message to JSON string."""
        return self.model_dump_json()

    @classmethod
    def from_json(cls, json_str: str) -> "RiskCheckMessage":
        """Deserialize message from JSON string."""
        return cls.model_validate_json(json_str)

    def get_routing_key(self) -> str:
        """Get routing key for this message."""
        return f"risk.{self.account_id}.{self.symbol}"


class ExecutionMessage(BaseMessage):
    """Execution message for tracking trade execution results."""

    execution_id: str
    order_id: str
    client_order_id: str
    symbol: str
    side: OrderSide
    quantity: Decimal
    price: Decimal
    broker: str
    account_id: str

    # Execution details
    execution_time: datetime = Field(default_factory=datetime.utcnow)
    commission: Optional[Decimal] = None
    execution_venue: Optional[str] = None
    liquidity_flag: Optional[str] = None

    # Trade identification
    trade_id: Optional[str] = None
    contra_broker: Optional[str] = None

    # Performance metrics
    slippage_bps: Optional[float] = None
    execution_latency_ms: Optional[int] = None

    @field_validator("quantity", "price", "commission", mode="before")
    @classmethod
    def convert_to_decimal(cls, v):
        """Convert numeric fields to Decimal for precision."""
        if v is None:
            return v
        return Decimal(str(v))

    @field_validator("execution_time", mode="before")
    @classmethod
    def convert_execution_time(cls, v):
        """Convert execution time to datetime."""
        if isinstance(v, str):
            return datetime.fromisoformat(v.replace("Z", "+00:00"))
        return v

    def to_json(self) -> str:
        """Serialize message to JSON string."""
        return self.model_dump_json()

    @classmethod
    def from_json(cls, json_str: str) -> "ExecutionMessage":
        """Deserialize message from JSON string."""
        return cls.model_validate_json(json_str)

    def get_routing_key(self) -> str:
        """Get routing key for this message."""
        return f"execution.{self.broker}.{self.symbol}"

    def calculate_notional_value(self) -> Decimal:
        """Calculate notional value of the execution."""
        return self.quantity * self.price
