"""
Business Intelligence Dashboard Module

Provides comprehensive dashboard capabilities for executive and operational analytics.
"""

from .executive import ExecutiveDashboard
from .operational import OperationalDashboard
from .performance import PerformanceDashboard
from .risk import RiskDashboard

__all__ = [
    "ExecutiveDashboard",
    "OperationalDashboard",
    "RiskDashboard",
    "PerformanceDashboard",
]
