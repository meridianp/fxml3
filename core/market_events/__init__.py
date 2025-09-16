"""
FXML4 Market Events Package

This package provides comprehensive economic news event handling for the FXML4
trading system, ensuring trading operations are automatically paused during
high-impact economic events to prevent losses from extreme market volatility.

Key Components:
- Economic Calendar Service: Fetches and manages economic event data
- Event Classification System: Categorizes events by impact level and affected currencies
- News Event Monitor: Real-time monitoring and alert system
- Trading Suspension Manager: Controls trading pause/resume logic

Features:
- Automatic trading suspension during high-impact events (NFP, CPI, Fed decisions)
- Currency-specific suspension logic
- Configurable pre/post-event timing windows
- Real-time event monitoring and alerting
- Integration with existing trading and risk management systems
"""

from .economic_calendar import (
    CalendarProvider,
    EconomicCalendar,
    EconomicEvent,
    EventImpact,
    EventStatus,
)
from .event_classifier import (
    ClassificationRule,
    CurrencyImpactMap,
    EventCategory,
    EventClassifier,
)
from .news_monitor import AlertLevel, EventAlert, MonitoringStatus, NewsEventMonitor
from .trading_suspension_manager import (
    SuspensionEvent,
    SuspensionReason,
    SuspensionStatus,
    TradingState,
    TradingSuspensionManager,
)

__all__ = [
    # Economic Calendar
    "EconomicCalendar",
    "EconomicEvent",
    "EventImpact",
    "EventStatus",
    "CalendarProvider",
    # Event Classification
    "EventClassifier",
    "EventCategory",
    "CurrencyImpactMap",
    "ClassificationRule",
    # News Monitoring
    "NewsEventMonitor",
    "EventAlert",
    "MonitoringStatus",
    "AlertLevel",
    # Trading Suspension
    "TradingSuspensionManager",
    "SuspensionReason",
    "SuspensionStatus",
    "SuspensionEvent",
    "TradingState",
]

__version__ = "1.0.0"
__author__ = "FXML4 Development Team"
__description__ = "Economic news event handling and trading suspension management"
