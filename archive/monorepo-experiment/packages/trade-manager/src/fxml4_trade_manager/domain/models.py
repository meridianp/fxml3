"""Domain models for Trade Manager - Local replacements for external dependencies."""

from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum


class OrderSide(str, Enum):
    """Order side enumeration."""
    BUY = "BUY"
    SELL = "SELL"


class OrderType(str, Enum):
    """Order type enumeration."""
    MARKET = "MARKET"
    LIMIT = "LIMIT"
    STOP = "STOP"
    STOP_LIMIT = "STOP_LIMIT"


class OrderStatus(str, Enum):
    """Order status enumeration."""
    PENDING = "PENDING"
    ACCEPTED = "ACCEPTED"
    FILLED = "FILLED"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"
    PENDING_CANCEL = "PENDING_CANCEL"
    MODIFIED = "MODIFIED"


class TimeInForce(str, Enum):
    """Time in force enumeration."""
    DAY = "DAY"
    GTC = "GTC"  # Good Till Cancelled
    IOC = "IOC"  # Immediate or Cancel
    FOK = "FOK"  # Fill or Kill
    GTD = "GTD"  # Good Till Date


class OrderRequest:
    """Order request domain model."""
    
    def __init__(
        self,
        symbol: str,
        side: OrderSide,
        quantity: Decimal,
        order_type: OrderType = OrderType.MARKET,
        price: Optional[Decimal] = None,
        stop_price: Optional[Decimal] = None,
        time_in_force: TimeInForce = TimeInForce.DAY,
        metadata: Optional[Dict[str, Any]] = None
    ):
        self.symbol = symbol
        self.side = side
        self.quantity = quantity
        self.order_type = order_type
        self.price = price
        self.stop_price = stop_price
        self.time_in_force = time_in_force
        self.metadata = metadata or {}
        self.created_at = datetime.now(timezone.utc)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            'symbol': self.symbol,
            'side': self.side.value,
            'quantity': str(self.quantity),
            'order_type': self.order_type.value,
            'price': str(self.price) if self.price else None,
            'stop_price': str(self.stop_price) if self.stop_price else None,
            'time_in_force': self.time_in_force.value,
            'metadata': self.metadata,
            'created_at': self.created_at.isoformat()
        }


class OrderResponse:
    """Order response domain model."""
    
    def __init__(
        self,
        broker_order_id: str,
        status: OrderStatus,
        symbol: str,
        side: OrderSide,
        quantity: Decimal,
        filled_quantity: Decimal = Decimal('0'),
        average_price: Optional[Decimal] = None,
        message: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ):
        self.broker_order_id = broker_order_id
        self.status = status
        self.symbol = symbol
        self.side = side
        self.quantity = quantity
        self.filled_quantity = filled_quantity
        self.average_price = average_price
        self.message = message
        self.metadata = metadata or {}
        self.created_at = datetime.now(timezone.utc)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            'broker_order_id': self.broker_order_id,
            'status': self.status.value,
            'symbol': self.symbol,
            'side': self.side.value,
            'quantity': str(self.quantity),
            'filled_quantity': str(self.filled_quantity),
            'average_price': str(self.average_price) if self.average_price else None,
            'message': self.message,
            'metadata': self.metadata,
            'created_at': self.created_at.isoformat()
        }


class OrderModifyRequest:
    """Order modification request domain model."""
    
    def __init__(
        self,
        broker_order_id: str,
        price: Optional[Decimal] = None,
        stop_price: Optional[Decimal] = None,
        quantity: Optional[Decimal] = None
    ):
        self.broker_order_id = broker_order_id
        self.price = price
        self.stop_price = stop_price
        self.quantity = quantity
        self.created_at = datetime.now(timezone.utc)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            'broker_order_id': self.broker_order_id,
            'price': str(self.price) if self.price else None,
            'stop_price': str(self.stop_price) if self.stop_price else None,
            'quantity': str(self.quantity) if self.quantity else None,
            'created_at': self.created_at.isoformat()
        }


class BrokerMessageFactory:
    """Factory for creating broker messages."""
    
    @staticmethod
    def create_order_request(
        symbol: str,
        side: OrderSide,
        quantity: Decimal,
        order_type: OrderType = OrderType.MARKET,
        price: Optional[Decimal] = None,
        stop_price: Optional[Decimal] = None,
        time_in_force: TimeInForce = TimeInForce.DAY,
        metadata: Optional[Dict[str, Any]] = None
    ) -> OrderRequest:
        """Create an order request."""
        return OrderRequest(
            symbol=symbol,
            side=side,
            quantity=quantity,
            order_type=order_type,
            price=price,
            stop_price=stop_price,
            time_in_force=time_in_force,
            metadata=metadata
        )
    
    @staticmethod
    def create_order_modify_request(
        broker_order_id: str,
        price: Optional[Decimal] = None,
        stop_price: Optional[Decimal] = None,
        quantity: Optional[Decimal] = None
    ) -> 'OrderModifyRequest':
        """Create an order modification request."""
        return OrderModifyRequest(
            broker_order_id=broker_order_id,
            price=price,
            stop_price=stop_price,
            quantity=quantity
        )


class OrderModifyRequest:
    """Order modification request domain model."""
    
    def __init__(
        self,
        broker_order_id: str,
        price: Optional[Decimal] = None,
        stop_price: Optional[Decimal] = None,
        quantity: Optional[Decimal] = None,
        metadata: Optional[Dict[str, Any]] = None
    ):
        self.broker_order_id = broker_order_id
        self.price = price
        self.stop_price = stop_price
        self.quantity = quantity
        self.metadata = metadata or {}
        self.created_at = datetime.now(timezone.utc)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            'broker_order_id': self.broker_order_id,
            'price': str(self.price) if self.price else None,
            'stop_price': str(self.stop_price) if self.stop_price else None,
            'quantity': str(self.quantity) if self.quantity else None,
            'metadata': self.metadata,
            'created_at': self.created_at.isoformat()
        }


class TradeData:
    """Trade data domain model."""
    
    def __init__(
        self,
        symbol: str,
        side: OrderSide,
        quantity: Decimal,
        price: Optional[Decimal] = None,
        stop_loss: Optional[Decimal] = None,
        take_profit: Optional[Decimal] = None,
        metadata: Optional[Dict[str, Any]] = None
    ):
        self.symbol = symbol
        self.side = side
        self.quantity = quantity
        self.price = price
        self.stop_loss = stop_loss
        self.take_profit = take_profit
        self.metadata = metadata or {}
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            'symbol': self.symbol,
            'side': self.side.value,
            'quantity': str(self.quantity),
            'price': str(self.price) if self.price else None,
            'stop_loss': str(self.stop_loss) if self.stop_loss else None,
            'take_profit': str(self.take_profit) if self.take_profit else None,
            'metadata': self.metadata
        }


class AccountData:
    """Account data domain model."""
    
    def __init__(
        self,
        balance: Decimal,
        equity: Optional[Decimal] = None,
        margin_used: Optional[Decimal] = None,
        margin_available: Optional[Decimal] = None,
        peak_balance: Optional[Decimal] = None,
        currency: str = "USD"
    ):
        self.balance = balance
        self.equity = equity or balance
        self.margin_used = margin_used or Decimal('0')
        self.margin_available = margin_available or balance
        self.peak_balance = peak_balance or balance
        self.currency = currency
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            'balance': str(self.balance),
            'equity': str(self.equity),
            'margin_used': str(self.margin_used),
            'margin_available': str(self.margin_available),
            'peak_balance': str(self.peak_balance),
            'currency': self.currency
        }


class MarketData:
    """Market data domain model."""
    
    def __init__(
        self,
        symbol: str,
        current_price: Decimal,
        bid: Optional[Decimal] = None,
        ask: Optional[Decimal] = None,
        volume: Optional[Decimal] = None,
        volatility: Optional[Decimal] = None,
        atr: Optional[Decimal] = None,
        timestamp: Optional[datetime] = None
    ):
        self.symbol = symbol
        self.current_price = current_price
        self.bid = bid or current_price
        self.ask = ask or current_price
        self.volume = volume
        self.volatility = volatility
        self.atr = atr
        self.timestamp = timestamp or datetime.now(timezone.utc)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            'symbol': self.symbol,
            'current_price': str(self.current_price),
            'bid': str(self.bid),
            'ask': str(self.ask),
            'volume': str(self.volume) if self.volume else None,
            'volatility': str(self.volatility) if self.volatility else None,
            'atr': str(self.atr) if self.atr else None,
            'timestamp': self.timestamp.isoformat()
        }