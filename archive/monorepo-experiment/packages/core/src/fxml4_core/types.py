"""Shared type definitions for fxml4."""

import os
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, TypeVar, Union

# Generic type variable
T = TypeVar("T")

# JSON types
JSONPrimitive = Union[str, int, float, bool, None]
JSONType = Union[JSONPrimitive, Dict[str, Any], List[Any]]

# File system types
PathLike = Union[str, os.PathLike]

# Trading types
Symbol = str
Price = Decimal
Quantity = Decimal
Timestamp = datetime

# Callback types
AsyncCallback = Callable[..., Any]
ErrorHandler = Callable[[Exception], None]

# Data types
DataFrame = Any  # Placeholder for pandas DataFrame when needed


class TimeFrame(str, Enum):
    """Trading timeframes."""
    
    M1 = "1m"
    M5 = "5m"
    M15 = "15m"
    M30 = "30m"
    H1 = "1h"
    H4 = "4h"
    D1 = "1d"
    W1 = "1w"
    MN1 = "1M"


class OrderSide(str, Enum):
    """Order side (buy/sell)."""
    
    BUY = "BUY"
    SELL = "SELL"


class OrderType(str, Enum):
    """Order types."""
    
    MARKET = "MARKET"
    LIMIT = "LIMIT"
    STOP = "STOP"
    STOP_LIMIT = "STOP_LIMIT"


class OrderStatus(str, Enum):
    """Order status."""
    
    PENDING = "PENDING"
    SUBMITTED = "SUBMITTED"
    FILLED = "FILLED"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"


# Type aliases for clarity
ConfigDict = Dict[str, Any]
MetricsDict = Dict[str, Union[float, int]]
FeatureDict = Dict[str, float]