"""Risk Management Package for Broker Abstraction.

This package provides comprehensive risk management capabilities
for the FIX-based broker abstraction system.
"""

from .base import (
    Position,
    RiskCheck,
    RiskCheckResult,
    RiskCheckType,
    RiskLimits,
    RiskManager,
    RiskMetrics,
    RiskViolation,
)
from .checks import (
    CounterpartyLimitCheck,
    DailyLossLimitCheck,
    DuplicateOrderCheck,
    OrderSizeLimitCheck,
    PositionLimitCheck,
    PriceDeviationCheck,
    SymbolRestrictionCheck,
    TimeRestrictionCheck,
)

# Integration components will be imported when needed to avoid circular deps
from .integration import create_risk_limits_from_config
from .manager import FXRiskManager

__all__ = [
    # Base classes
    "RiskCheckType",
    "RiskCheckResult",
    "RiskViolation",
    "Position",
    "RiskLimits",
    "RiskMetrics",
    "RiskCheck",
    "RiskManager",
    # Check implementations
    "PositionLimitCheck",
    "OrderSizeLimitCheck",
    "DailyLossLimitCheck",
    "PriceDeviationCheck",
    "SymbolRestrictionCheck",
    "TimeRestrictionCheck",
    "DuplicateOrderCheck",
    "CounterpartyLimitCheck",
    # Manager
    "FXRiskManager",
    # Integration
    "create_risk_limits_from_config",
]
