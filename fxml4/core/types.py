"""
Core Types and Enums for FXML4

This module defines the fundamental types, enums, and data structures
used throughout the FXML4 trading system.
"""

from decimal import Decimal
from enum import Enum
from typing import NewType

# Type aliases for better code clarity
Symbol = NewType("Symbol", str)
Timeframe = NewType("Timeframe", str)


class SignalStrength(Enum):
    """Signal strength levels for trading signals"""

    VERY_WEAK = "very_weak"
    WEAK = "weak"
    MODERATE = "moderate"
    STRONG = "strong"
    VERY_STRONG = "very_strong"


class MarketRegime(Enum):
    """Market regime classification"""

    TRENDING_BULLISH = "trending_bullish"
    TRENDING_BEARISH = "trending_bearish"
    RANGING = "ranging"
    VOLATILE = "volatile"
    LOW_VOLATILITY = "low_volatility"
    BREAKOUT = "breakout"
    CONSOLIDATION = "consolidation"
    REVERSAL = "reversal"


class OrderSide(Enum):
    """Order side for trading operations"""

    BUY = "buy"
    SELL = "sell"


class OrderType(Enum):
    """Order types supported by the trading system"""

    MARKET = "market"
    LIMIT = "limit"
    STOP = "stop"
    STOP_LIMIT = "stop_limit"
    TRAILING_STOP = "trailing_stop"


class PositionSide(Enum):
    """Position sides"""

    LONG = "long"
    SHORT = "short"


class OrderStatus(Enum):
    """Order execution status"""

    PENDING = "pending"
    FILLED = "filled"
    PARTIALLY_FILLED = "partially_filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"
    EXPIRED = "expired"


class DataProvider(Enum):
    """Data provider sources"""

    INTERACTIVE_BROKERS = "ib"
    POLYGON = "polygon"
    ALPHA_VANTAGE = "alphavantage"
    FXCM = "fxcm"
    MANUAL = "manual"


class Currency(Enum):
    """Major currency codes"""

    USD = "USD"
    EUR = "EUR"
    GBP = "GBP"
    JPY = "JPY"
    CHF = "CHF"
    CAD = "CAD"
    AUD = "AUD"
    NZD = "NZD"


class CurrencyPair(Enum):
    """Major forex currency pairs"""

    EURUSD = "EURUSD"
    GBPUSD = "GBPUSD"
    USDJPY = "USDJPY"
    USDCHF = "USDCHF"
    USDCAD = "USDCAD"
    AUDUSD = "AUDUSD"
    NZDUSD = "NZDUSD"
    EURGBP = "EURGBP"
    EURJPY = "EURJPY"
    GBPJPY = "GBPJPY"


class TimeframeType(Enum):
    """Standard timeframe types"""

    TICK = "tick"
    SECOND_1 = "1s"
    SECOND_5 = "5s"
    SECOND_10 = "10s"
    SECOND_15 = "15s"
    SECOND_30 = "30s"
    MINUTE_1 = "1m"
    MINUTE_2 = "2m"
    MINUTE_3 = "3m"
    MINUTE_5 = "5m"
    MINUTE_10 = "10m"
    MINUTE_15 = "15m"
    MINUTE_30 = "30m"
    HOUR_1 = "1H"
    HOUR_2 = "2H"
    HOUR_4 = "4H"
    HOUR_6 = "6H"
    HOUR_8 = "8H"
    HOUR_12 = "12H"
    DAY_1 = "1D"
    WEEK_1 = "1W"
    MONTH_1 = "1M"


class TradingSession(Enum):
    """Trading session classifications"""

    SYDNEY = "sydney"
    TOKYO = "tokyo"
    LONDON = "london"
    NEW_YORK = "new_york"
    OVERNIGHT = "overnight"
    WEEKEND = "weekend"


class RiskLevel(Enum):
    """Risk level classifications"""

    VERY_LOW = "very_low"
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    VERY_HIGH = "very_high"


class VolatilityRegime(Enum):
    """Volatility regime classifications"""

    VERY_LOW = "very_low"
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    VERY_HIGH = "very_high"
    EXTREME = "extreme"
