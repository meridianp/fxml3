"""Event-driven architecture for backtesting.

This module defines the event types and event queue for event-driven backtesting.
"""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum, auto
from typing import Any, Dict, Optional, Union

import pandas as pd


class EventType(Enum):
    """Enum for different event types in event-driven backtesting system."""
    
    MARKET = auto()  # New market data available
    SIGNAL = auto()  # Strategy generated a signal
    ORDER = auto()   # New order created
    FILL = auto()    # Order has been filled
    CUSTOM = auto()  # Custom event type for strategy-specific events


@dataclass
class Event:
    """Base class for all events in the system."""
    
    type: EventType
    timestamp: datetime
    
    def __str__(self) -> str:
        """Return string representation of the event."""
        return f"{self.type.name} Event ({self.timestamp})"


@dataclass
class MarketEvent(Event):
    """Event for new market data."""
    
    symbol: str
    timeframe: str
    data: pd.Series
    
    def __init__(
        self, 
        timestamp: datetime, 
        symbol: str, 
        timeframe: str, 
        data: pd.Series
    ):
        """Initialize a market event.
        
        Args:
            timestamp: Event timestamp.
            symbol: Market symbol.
            timeframe: Data timeframe.
            data: Market data.
        """
        super().__init__(EventType.MARKET, timestamp)
        self.symbol = symbol
        self.timeframe = timeframe
        self.data = data
    
    def __str__(self) -> str:
        """Return string representation of the event."""
        return f"MARKET Event: {self.symbol} ({self.timeframe}) @ {self.timestamp}"


@dataclass
class SignalEvent(Event):
    """Event for strategy signals."""
    
    symbol: str
    signal_type: str
    signal_data: Dict[str, Any]
    
    def __init__(
        self,
        timestamp: datetime,
        symbol: str,
        signal_type: str,
        signal_data: Dict[str, Any],
    ):
        """Initialize a signal event.
        
        Args:
            timestamp: Event timestamp.
            symbol: Market symbol.
            signal_type: Type of signal (entry, exit, adjust).
            signal_data: Signal data and parameters.
        """
        super().__init__(EventType.SIGNAL, timestamp)
        self.symbol = symbol
        self.signal_type = signal_type
        self.signal_data = signal_data
    
    def __str__(self) -> str:
        """Return string representation of the event."""
        return f"SIGNAL Event: {self.symbol} {self.signal_type} @ {self.timestamp}"


@dataclass
class OrderEvent(Event):
    """Event for order placement."""
    
    order_id: str
    symbol: str
    order_type: str
    side: str
    quantity: float
    price: Optional[float] = None
    stop_price: Optional[float] = None
    limit_price: Optional[float] = None
    time_in_force: str = "GTC"  # Good Till Cancelled
    parent_order_id: Optional[str] = None
    signal_id: Optional[str] = None
    additional_params: Optional[Dict[str, Any]] = None
    
    def __init__(
        self,
        timestamp: datetime,
        order_id: str,
        symbol: str,
        order_type: str,
        side: str,
        quantity: float,
        price: Optional[float] = None,
        stop_price: Optional[float] = None,
        limit_price: Optional[float] = None,
        time_in_force: str = "GTC",
        parent_order_id: Optional[str] = None,
        signal_id: Optional[str] = None,
        additional_params: Optional[Dict[str, Any]] = None,
    ):
        """Initialize an order event.
        
        Args:
            timestamp: Event timestamp.
            order_id: Unique order ID.
            symbol: Market symbol.
            order_type: Type of order (market, limit, stop, etc).
            side: Order side (buy or sell).
            quantity: Order quantity.
            price: Order price for limit orders.
            stop_price: Trigger price for stop orders.
            limit_price: Limit price for stop-limit orders.
            time_in_force: Time in force (GTC, IOC, etc).
            parent_order_id: Parent order ID for OCO or bracket orders.
            signal_id: ID of the signal that generated this order.
            additional_params: Additional order parameters.
        """
        super().__init__(EventType.ORDER, timestamp)
        self.order_id = order_id
        self.symbol = symbol
        self.order_type = order_type
        self.side = side
        self.quantity = quantity
        self.price = price
        self.stop_price = stop_price
        self.limit_price = limit_price
        self.time_in_force = time_in_force
        self.parent_order_id = parent_order_id
        self.signal_id = signal_id
        self.additional_params = additional_params or {}
    
    def __str__(self) -> str:
        """Return string representation of the event."""
        return (
            f"ORDER Event: {self.symbol} {self.side} {self.quantity} "
            f"@ {self.price or self.stop_price or 'MARKET'} ({self.order_type})"
        )


@dataclass
class FillEvent(Event):
    """Event for order fills."""
    
    order_id: str
    symbol: str
    side: str
    quantity: float
    filled_price: float
    commission: float
    slippage: float
    fill_time: datetime
    
    def __init__(
        self,
        timestamp: datetime,
        order_id: str,
        symbol: str,
        side: str,
        quantity: float,
        filled_price: float,
        commission: float,
        slippage: float,
        fill_time: Optional[datetime] = None,
    ):
        """Initialize a fill event.
        
        Args:
            timestamp: Event timestamp.
            order_id: ID of the filled order.
            symbol: Market symbol.
            side: Order side (buy or sell).
            quantity: Filled quantity.
            filled_price: Fill price.
            commission: Commission paid.
            slippage: Slippage amount.
            fill_time: Time of the fill (defaults to timestamp).
        """
        super().__init__(EventType.FILL, timestamp)
        self.order_id = order_id
        self.symbol = symbol
        self.side = side
        self.quantity = quantity
        self.filled_price = filled_price
        self.commission = commission
        self.slippage = slippage
        self.fill_time = fill_time or timestamp
    
    def __str__(self) -> str:
        """Return string representation of the event."""
        return (
            f"FILL Event: {self.symbol} {self.side} {self.quantity} "
            f"@ {self.filled_price} (Commission: {self.commission}, Slippage: {self.slippage})"
        )


@dataclass
class CustomEvent(Event):
    """Custom event for strategy-specific events."""
    
    name: str
    data: Dict[str, Any]
    
    def __init__(
        self,
        timestamp: datetime,
        name: str,
        data: Dict[str, Any],
    ):
        """Initialize a custom event.
        
        Args:
            timestamp: Event timestamp.
            name: Custom event name.
            data: Event data.
        """
        super().__init__(EventType.CUSTOM, timestamp)
        self.name = name
        self.data = data
    
    def __str__(self) -> str:
        """Return string representation of the event."""
        return f"CUSTOM Event: {self.name} @ {self.timestamp}"


# Type alias for all event types
EventUnion = Union[Event, MarketEvent, SignalEvent, OrderEvent, FillEvent, CustomEvent]