"""Broker message schemas for order execution and trade management.

This module defines the standardized message schemas for communicating with
different broker APIs (Interactive Brokers, FXCM, Oanda, Manual execution, etc.).
All broker adapters must conform to these schemas to ensure system interoperability.
"""

import uuid
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, Field, validator


class OrderType(str, Enum):
    """Order types supported across brokers."""

    MARKET = "MARKET"
    LIMIT = "LIMIT"
    STOP = "STOP"
    STOP_LIMIT = "STOP_LIMIT"
    TRAILING_STOP = "TRAILING_STOP"
    BRACKET = "BRACKET"  # OCO with stop and limit
    ONE_CANCELS_OTHER = "OCO"


class OrderSide(str, Enum):
    """Order side/direction."""

    BUY = "BUY"
    SELL = "SELL"


class OrderStatus(str, Enum):
    """Order status across all brokers."""

    PENDING = "PENDING"  # Order created but not submitted
    SUBMITTED = "SUBMITTED"  # Order sent to broker
    ACKNOWLEDGED = "ACKNOWLEDGED"  # Broker acknowledged receipt
    WORKING = "WORKING"  # Order is active in market
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    FILLED = "FILLED"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"
    SUSPENDED = "SUSPENDED"


class TimeInForce(str, Enum):
    """Time in force options."""

    DAY = "DAY"
    GTC = "GTC"  # Good Till Cancelled
    IOC = "IOC"  # Immediate or Cancel
    FOK = "FOK"  # Fill or Kill
    GTD = "GTD"  # Good Till Date


class BrokerType(str, Enum):
    """Supported broker types."""

    INTERACTIVE_BROKERS = "IB"
    MANUAL = "MANUAL"
    FXCM = "FXCM"
    OANDA = "OANDA"
    DUKASCOPY = "DUKASCOPY"
    ALPACA = "ALPACA"
    BINANCE = "BINANCE"


class ExecutionType(str, Enum):
    """Execution report types."""

    NEW = "NEW"
    PARTIAL_FILL = "PARTIAL_FILL"
    FILL = "FILL"
    DONE_FOR_DAY = "DONE_FOR_DAY"
    CANCELLED = "CANCELLED"
    REPLACED = "REPLACED"
    PENDING_CANCEL = "PENDING_CANCEL"
    STOPPED = "STOPPED"
    REJECTED = "REJECTED"
    SUSPENDED = "SUSPENDED"
    PENDING_NEW = "PENDING_NEW"
    CALCULATED = "CALCULATED"
    EXPIRED = "EXPIRED"
    RESTATED = "RESTATED"
    PENDING_REPLACE = "PENDING_REPLACE"
    TRADE = "TRADE"
    TRADE_CORRECT = "TRADE_CORRECT"
    TRADE_CANCEL = "TRADE_CANCEL"
    ORDER_STATUS = "ORDER_STATUS"


class CurrencyCode(str, Enum):
    """Major currency codes."""

    USD = "USD"
    EUR = "EUR"
    GBP = "GBP"
    JPY = "JPY"
    CHF = "CHF"
    CAD = "CAD"
    AUD = "AUD"
    NZD = "NZD"


# Base Message Schema
class BrokerMessage(BaseModel):
    """Base class for all broker messages."""

    message_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    broker_type: BrokerType
    account_id: str
    message_type: str
    correlation_id: Optional[str] = None  # For request/response correlation

    class Config:
        use_enum_values = True
        json_encoders = {datetime: lambda v: v.isoformat(), Decimal: lambda v: float(v)}


# Order Schemas
class OrderRequest(BrokerMessage):
    """Standard order request message."""

    message_type: str = Field(default="ORDER_REQUEST", const=True)

    # Order identification
    client_order_id: str = Field(..., description="Client-generated unique order ID")
    signal_id: Optional[str] = None  # Reference to originating signal

    # Instrument details
    symbol: str = Field(..., description="Trading symbol (e.g., EURUSD)")
    exchange: Optional[str] = None  # For stocks/futures
    security_type: str = Field(default="FOREX")  # FOREX, STOCK, FUTURE, OPTION, etc.
    currency: CurrencyCode = Field(default=CurrencyCode.USD)

    # Order details
    order_type: OrderType
    side: OrderSide
    quantity: Decimal = Field(..., gt=0, description="Order quantity/size")
    price: Optional[Decimal] = Field(None, description="Limit price (for limit orders)")
    stop_price: Optional[Decimal] = Field(
        None, description="Stop price (for stop orders)"
    )
    time_in_force: TimeInForce = Field(default=TimeInForce.GTC)
    good_till_date: Optional[datetime] = None

    # Advanced order parameters
    trail_amount: Optional[Decimal] = None  # For trailing stops
    trail_percent: Optional[Decimal] = None
    hidden: bool = Field(default=False)
    iceberg_qty: Optional[Decimal] = None

    # Bracket order components (if applicable)
    take_profit_price: Optional[Decimal] = None
    stop_loss_price: Optional[Decimal] = None

    # Risk management
    max_position_size: Optional[Decimal] = None
    risk_amount: Optional[Decimal] = None  # Max $ risk

    # Metadata
    strategy_name: Optional[str] = None
    tags: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @validator("quantity", "price", "stop_price")
    def validate_positive_numbers(cls, v):
        if v is not None and v <= 0:
            raise ValueError("Price and quantity values must be positive")
        return v


class OrderResponse(BrokerMessage):
    """Order response from broker."""

    message_type: str = Field(default="ORDER_RESPONSE", const=True)

    client_order_id: str
    broker_order_id: Optional[str] = None  # Broker's internal order ID
    status: OrderStatus

    # Response details
    success: bool
    error_code: Optional[str] = None
    error_message: Optional[str] = None

    # Order confirmation details
    symbol: str
    side: OrderSide
    quantity: Decimal
    filled_quantity: Decimal = Field(default=Decimal("0"))
    remaining_quantity: Optional[Decimal] = None
    average_price: Optional[Decimal] = None

    # Timing
    order_time: Optional[datetime] = None
    acknowledged_time: Optional[datetime] = None

    # Fees and costs
    commission: Optional[Decimal] = None
    commission_currency: Optional[CurrencyCode] = None

    metadata: Dict[str, Any] = Field(default_factory=dict)


class OrderCancelRequest(BrokerMessage):
    """Order cancellation request."""

    message_type: str = Field(default="ORDER_CANCEL_REQUEST", const=True)

    client_order_id: str
    broker_order_id: Optional[str] = None
    symbol: str
    reason: Optional[str] = None


class OrderModifyRequest(BrokerMessage):
    """Order modification request."""

    message_type: str = Field(default="ORDER_MODIFY_REQUEST", const=True)

    client_order_id: str
    broker_order_id: Optional[str] = None

    # New order parameters
    new_quantity: Optional[Decimal] = None
    new_price: Optional[Decimal] = None
    new_stop_price: Optional[Decimal] = None
    new_time_in_force: Optional[TimeInForce] = None


# Execution and Fill Schemas
class ExecutionReport(BrokerMessage):
    """Execution report for order fills."""

    message_type: str = Field(default="EXECUTION_REPORT", const=True)

    # Order identification
    client_order_id: str
    broker_order_id: str
    execution_id: str = Field(..., description="Unique execution ID")

    # Execution details
    execution_type: ExecutionType
    order_status: OrderStatus
    symbol: str
    side: OrderSide

    # Fill information
    last_quantity: Decimal = Field(default=Decimal("0"))  # Quantity of this fill
    last_price: Optional[Decimal] = None  # Price of this fill
    cumulative_quantity: Decimal = Field(default=Decimal("0"))  # Total filled
    leaves_quantity: Decimal = Field(default=Decimal("0"))  # Remaining quantity
    average_price: Optional[Decimal] = None  # Average fill price

    # Order details
    order_quantity: Decimal
    order_type: OrderType
    time_in_force: TimeInForce

    # Timing
    transaction_time: datetime = Field(default_factory=datetime.utcnow)

    # Costs
    commission: Optional[Decimal] = None
    commission_currency: Optional[CurrencyCode] = None
    net_money: Optional[Decimal] = None  # Net cash impact

    # Market data at execution
    bid_price: Optional[Decimal] = None
    ask_price: Optional[Decimal] = None
    spread: Optional[Decimal] = None

    # Additional execution details
    liquidity_indicator: Optional[str] = None  # Added/Removed liquidity
    execution_venue: Optional[str] = None

    metadata: Dict[str, Any] = Field(default_factory=dict)


# Position and Account Schemas
class PositionReport(BrokerMessage):
    """Position report from broker."""

    message_type: str = Field(default="POSITION_REPORT", const=True)

    symbol: str
    position_size: Decimal  # Positive for long, negative for short
    average_price: Decimal
    market_price: Decimal
    unrealized_pnl: Decimal
    realized_pnl: Decimal = Field(default=Decimal("0"))

    # Position details
    currency: CurrencyCode
    margin_used: Optional[Decimal] = None
    margin_requirement: Optional[Decimal] = None

    # Timing
    position_date: datetime = Field(default_factory=datetime.utcnow)

    metadata: Dict[str, Any] = Field(default_factory=dict)


class AccountReport(BrokerMessage):
    """Account balance and margin report."""

    message_type: str = Field(default="ACCOUNT_REPORT", const=True)

    # Account balances
    account_value: Decimal
    cash_balance: Decimal
    equity: Decimal
    buying_power: Decimal

    # Margin information
    initial_margin: Decimal = Field(default=Decimal("0"))
    maintenance_margin: Decimal = Field(default=Decimal("0"))
    available_margin: Decimal = Field(default=Decimal("0"))
    margin_level: Optional[Decimal] = None  # Margin level percentage

    # P&L
    unrealized_pnl: Decimal = Field(default=Decimal("0"))
    realized_pnl: Decimal = Field(default=Decimal("0"))
    daily_pnl: Decimal = Field(default=Decimal("0"))

    # Currency
    base_currency: CurrencyCode = Field(default=CurrencyCode.USD)

    # Timestamp
    report_time: datetime = Field(default_factory=datetime.utcnow)

    metadata: Dict[str, Any] = Field(default_factory=dict)


# Market Data Schemas
class MarketDataRequest(BrokerMessage):
    """Market data subscription request."""

    message_type: str = Field(default="MARKET_DATA_REQUEST", const=True)

    request_id: str
    symbols: List[str]
    data_types: List[str] = Field(
        default=["BID", "ASK", "LAST"]
    )  # BID, ASK, LAST, VOLUME, etc.
    snapshot: bool = Field(default=False)  # True for snapshot, False for streaming


class MarketDataSnapshot(BrokerMessage):
    """Market data snapshot."""

    message_type: str = Field(default="MARKET_DATA_SNAPSHOT", const=True)

    symbol: str
    bid_price: Optional[Decimal] = None
    ask_price: Optional[Decimal] = None
    last_price: Optional[Decimal] = None
    bid_size: Optional[Decimal] = None
    ask_size: Optional[Decimal] = None
    last_size: Optional[Decimal] = None
    volume: Optional[Decimal] = None
    high: Optional[Decimal] = None
    low: Optional[Decimal] = None
    open_price: Optional[Decimal] = None
    close_price: Optional[Decimal] = None

    market_time: datetime = Field(default_factory=datetime.utcnow)

    metadata: Dict[str, Any] = Field(default_factory=dict)


# Error and Status Schemas
class BrokerError(BrokerMessage):
    """Broker error message."""

    message_type: str = Field(default="BROKER_ERROR", const=True)

    error_code: str
    error_message: str
    error_type: str  # CONNECTION, AUTHENTICATION, ORDER, MARKET_DATA, etc.
    severity: str = Field(default="ERROR")  # INFO, WARNING, ERROR, CRITICAL

    # Context
    related_order_id: Optional[str] = None
    related_request_id: Optional[str] = None

    recovery_suggestion: Optional[str] = None

    metadata: Dict[str, Any] = Field(default_factory=dict)


class BrokerStatus(BrokerMessage):
    """Broker connection status."""

    message_type: str = Field(default="BROKER_STATUS", const=True)

    status: str  # CONNECTED, DISCONNECTED, CONNECTING, RECONNECTING, ERROR
    connection_quality: Optional[str] = None  # EXCELLENT, GOOD, FAIR, POOR

    # Connection details
    server_time: Optional[datetime] = None
    next_valid_order_id: Optional[int] = None
    market_open: bool = Field(default=True)

    # Capabilities
    supported_order_types: List[OrderType] = Field(default_factory=list)
    supported_time_in_force: List[TimeInForce] = Field(default_factory=list)
    max_order_size: Optional[Decimal] = None

    metadata: Dict[str, Any] = Field(default_factory=dict)


# Manual Trading Schemas (for manual execution tool)
class ManualTradeNotification(BrokerMessage):
    """Manual trade notification for manual execution tool."""

    message_type: str = Field(default="MANUAL_TRADE_NOTIFICATION", const=True)
    broker_type: BrokerType = Field(default=BrokerType.MANUAL, const=True)

    # Trade details
    trade_id: str
    symbol: str
    side: OrderSide
    quantity: Decimal
    price: Decimal
    execution_time: datetime

    # Manual entry context
    entry_method: str  # WEB, MOBILE, PHONE, API
    trader_id: Optional[str] = None
    notes: Optional[str] = None

    # Associated order
    related_signal_id: Optional[str] = None
    related_order_id: Optional[str] = None

    metadata: Dict[str, Any] = Field(default_factory=dict)


class ManualTradeConfirmation(BrokerMessage):
    """Confirmation request for manual trades."""

    message_type: str = Field(default="MANUAL_TRADE_CONFIRMATION", const=True)
    broker_type: BrokerType = Field(default=BrokerType.MANUAL, const=True)

    trade_notification_id: str
    confirmed: bool
    confirmer_id: str
    confirmation_time: datetime = Field(default_factory=datetime.utcnow)
    rejection_reason: Optional[str] = None

    metadata: Dict[str, Any] = Field(default_factory=dict)


# Routing and Adapter Schemas
class BrokerRouting(BaseModel):
    """Routing configuration for broker selection."""

    symbol: str
    order_type: OrderType
    preferred_brokers: List[BrokerType]
    fallback_brokers: List[BrokerType] = Field(default_factory=list)

    # Routing rules
    min_order_size: Optional[Decimal] = None
    max_order_size: Optional[Decimal] = None
    market_hours_only: bool = Field(default=False)

    # Cost considerations
    commission_structure: Optional[str] = None
    spread_tolerance: Optional[Decimal] = None

    metadata: Dict[str, Any] = Field(default_factory=dict)


class BrokerCapabilities(BaseModel):
    """Broker capabilities and limitations."""

    broker_type: BrokerType

    # Supported features
    supported_order_types: List[OrderType]
    supported_time_in_force: List[TimeInForce]
    supported_symbols: List[str] = Field(default_factory=list)

    # Limitations
    min_order_size: Dict[str, Decimal] = Field(default_factory=dict)  # By symbol
    max_order_size: Dict[str, Decimal] = Field(default_factory=dict)  # By symbol
    max_orders_per_second: Optional[int] = None
    max_orders_per_minute: Optional[int] = None

    # Market data capabilities
    provides_market_data: bool = Field(default=False)
    real_time_data: bool = Field(default=False)
    historical_data: bool = Field(default=False)

    # Trading sessions
    trading_sessions: List[Dict[str, Any]] = Field(default_factory=list)

    # Fees
    commission_structure: Optional[Dict[str, Any]] = None
    margin_requirements: Optional[Dict[str, Decimal]] = None

    metadata: Dict[str, Any] = Field(default_factory=dict)


# Message Union Types for easy handling
BrokerMessageTypes = Union[
    OrderRequest,
    OrderResponse,
    OrderCancelRequest,
    OrderModifyRequest,
    ExecutionReport,
    PositionReport,
    AccountReport,
    MarketDataRequest,
    MarketDataSnapshot,
    BrokerError,
    BrokerStatus,
    ManualTradeNotification,
    ManualTradeConfirmation,
]


# Message Factory
class BrokerMessageFactory:
    """Factory for creating broker messages."""

    @staticmethod
    def create_order_request(
        broker_type: BrokerType,
        account_id: str,
        symbol: str,
        side: OrderSide,
        quantity: Decimal,
        order_type: OrderType = OrderType.MARKET,
        **kwargs,
    ) -> OrderRequest:
        """Create a standard order request."""
        return OrderRequest(
            broker_type=broker_type,
            account_id=account_id,
            client_order_id=str(uuid.uuid4()),
            symbol=symbol,
            side=side,
            quantity=quantity,
            order_type=order_type,
            **kwargs,
        )

    @staticmethod
    def create_market_order(
        broker_type: BrokerType,
        account_id: str,
        symbol: str,
        side: OrderSide,
        quantity: Decimal,
        **kwargs,
    ) -> OrderRequest:
        """Create a market order request."""
        return BrokerMessageFactory.create_order_request(
            broker_type=broker_type,
            account_id=account_id,
            symbol=symbol,
            side=side,
            quantity=quantity,
            order_type=OrderType.MARKET,
            **kwargs,
        )

    @staticmethod
    def create_limit_order(
        broker_type: BrokerType,
        account_id: str,
        symbol: str,
        side: OrderSide,
        quantity: Decimal,
        price: Decimal,
        **kwargs,
    ) -> OrderRequest:
        """Create a limit order request."""
        return BrokerMessageFactory.create_order_request(
            broker_type=broker_type,
            account_id=account_id,
            symbol=symbol,
            side=side,
            quantity=quantity,
            order_type=OrderType.LIMIT,
            price=price,
            **kwargs,
        )

    @staticmethod
    def create_bracket_order(
        broker_type: BrokerType,
        account_id: str,
        symbol: str,
        side: OrderSide,
        quantity: Decimal,
        entry_price: Optional[Decimal] = None,
        take_profit_price: Optional[Decimal] = None,
        stop_loss_price: Optional[Decimal] = None,
        **kwargs,
    ) -> OrderRequest:
        """Create a bracket order (entry + stop + limit)."""
        order_type = OrderType.MARKET if entry_price is None else OrderType.LIMIT

        return BrokerMessageFactory.create_order_request(
            broker_type=broker_type,
            account_id=account_id,
            symbol=symbol,
            side=side,
            quantity=quantity,
            order_type=order_type,
            price=entry_price,
            take_profit_price=take_profit_price,
            stop_loss_price=stop_loss_price,
            **kwargs,
        )
