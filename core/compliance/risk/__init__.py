"""
Compliance Risk Management Module for FXML4.

Provides comprehensive risk limit enforcement and real-time position monitoring:
- Real-time risk limit enforcement
- Position and exposure monitoring
- Automatic enforcement actions
- Violation tracking and alerting
"""

from .limit_enforcement import (
    EnforcementAction,
    LimitType,
    LimitViolation,
    PositionExposure,
    RealTimeRiskMonitor,
    RiskExposure,
    RiskLimit,
    RiskLimitEnforcer,
    ViolationSeverity,
    risk_limit_enforcer,
)

__all__ = [
    "RiskLimitEnforcer",
    "RealTimeRiskMonitor",
    "RiskLimit",
    "PositionExposure",
    "RiskExposure",
    "LimitViolation",
    "LimitType",
    "ViolationSeverity",
    "EnforcementAction",
    "risk_limit_enforcer",
]
