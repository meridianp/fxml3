"""
Event classes for event-driven backtesting.
"""

from abc import ABC
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Dict, Any, Optional
import pandas as pd


class EventType(Enum):
    """Event types."""
    MARKET = "MARKET"
    SIGNAL = "SIGNAL"
    ORDER = "ORDER"
    FILL = "FILL"


class OrderType(Enum):
    """Order types."""
    MARKET = "MARKET"
    LIMIT = "LIMIT"
    STOP = "STOP"
    STOP_LIMIT = "STOP_LIMIT"


class OrderSide(Enum):
    """Order sides."""
    BUY = "BUY"
    SELL = "SELL"


@dataclass
class Event(ABC):
    """Base event class."""
    timestamp: datetime


@dataclass
class MarketEvent(Event):
    """Market data event."""
    symbol: str
    data: pd.Series
    type: EventType = EventType.MARKET


@dataclass
class SignalEvent(Event):
    """Trading signal event."""
    symbol: str
    signal_type: str  # 'BUY', 'SELL', 'EXIT'
    strength: float  # Signal strength/confidence
    price: float
    quantity: Optional[float] = None
    metadata: Optional[Dict[str, Any]] = None
    type: EventType = EventType.SIGNAL
    
    def __post_init__(self):
        super().__init__()
        if self.metadata is None:
            self.metadata = {}


@dataclass
class OrderEvent(Event):
    """Order event."""
    symbol: str
    order_type: OrderType
    side: OrderSide
    quantity: float
    price: Optional[float] = None  # For limit/stop orders
    stop_price: Optional[float] = None  # For stop orders
    order_id: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    type: EventType = EventType.ORDER
    
    def __post_init__(self):
        super().__init__()
        if self.metadata is None:
            self.metadata = {}


@dataclass
class FillEvent(Event):
    """Order fill event."""
    symbol: str
    order_id: str
    exchange: str
    side: OrderSide
    quantity: float
    price: float
    commission: float
    slippage: float
    metadata: Optional[Dict[str, Any]] = None
    type: EventType = EventType.FILL
    
    def __post_init__(self):
        super().__init__()
        if self.metadata is None:
            self.metadata = {}
    
    @property
    def total_cost(self) -> float:
        """Calculate total cost including commission."""
        if self.side == OrderSide.BUY:
            return self.quantity * self.price + self.commission
        else:
            return self.quantity * self.price - self.commission