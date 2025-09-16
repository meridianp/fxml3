"""
FXML4 Market Sessions Package

This package provides comprehensive market session management for the FXML4
trading system, ensuring proper handling of forex market hours, session
transitions, weekend closures, and holiday schedules.

Key Components:
- Market Session Manager: Central session state management
- Session Calendar: Trading hours and holiday schedules
- Session Transitions: Overlap periods and transition logic
- Weekend/Holiday Handler: Non-trading period management

Features:
- Real-time market status monitoring
- Automatic trading suspension during market closures
- Session transition detection and handling
- Holiday calendar integration
- Timezone-aware session management
- Liquidity and volatility session mapping
"""

from .market_session_manager import (
    MarketSession,
    MarketSessionManager,
    MarketState,
    SessionStatus,
    SessionTransition,
)
from .session_calendar import (
    HolidayType,
    MarketHoliday,
    SessionCalendar,
    SessionOverlap,
    SessionType,
    TradingSession,
)
from .session_validator import (
    SessionValidationResult,
    SessionValidator,
    ValidationLevel,
    ValidationRule,
)
from .weekend_holiday_handler import (
    ClosureType,
    HolidaySchedule,
    WeekendHolidayHandler,
    WeekendSchedule,
)

__all__ = [
    # Market Session Manager
    "MarketSessionManager",
    "MarketSession",
    "SessionStatus",
    "SessionTransition",
    "MarketState",
    # Session Calendar
    "SessionCalendar",
    "TradingSession",
    "SessionOverlap",
    "MarketHoliday",
    "SessionType",
    "HolidayType",
    # Session Validator
    "SessionValidator",
    "SessionValidationResult",
    "ValidationRule",
    "ValidationLevel",
    # Weekend/Holiday Handler
    "WeekendHolidayHandler",
    "WeekendSchedule",
    "HolidaySchedule",
    "ClosureType",
]

__version__ = "1.0.0"
__author__ = "FXML4 Development Team"
__description__ = "Market session management and trading hours validation"
