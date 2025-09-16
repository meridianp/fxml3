"""Risk management module for FXML4."""

# Import from unified risk management system
from .base import BaseRiskManager, Position, RiskLimits, RiskMetrics, RiskViolation
from .live import LiveRiskManager

# Optional imports for modules that may have missing dependencies
try:
    from .backtest import BacktestRiskManager
except ImportError:
    BacktestRiskManager = None

try:
    from .broker import BrokerRiskManager
except ImportError:
    BrokerRiskManager = None

# Legacy compatibility imports
try:
    from ..backtesting.risk import (
        AdvancedRiskManager,
        DynamicStopLossManager,
        FixedFractional,
        KellyCriterion,
        VolatilityScaler,
    )
except ImportError:
    # Define placeholders or skip
    AdvancedRiskManager = None
    DynamicStopLossManager = None
    VolatilityScaler = None
    KellyCriterion = None
    FixedFractional = None

# Legacy compatibility - map old class names to new ones
RiskManager = LiveRiskManager  # Default to live risk manager
RiskConfig = RiskLimits  # Map old config to new limits

try:
    from .position_sizing import (
        DynamicPositionSizer,
        FixedRiskSizer,
        KellyCriterionSizer,
        VolatilityBasedSizer,
    )
except ImportError:
    # Position sizing modules may not exist yet
    KellyCriterionSizer = None
    VolatilityBasedSizer = None
    FixedRiskSizer = None
    DynamicPositionSizer = None

# Advanced drawdown control system
try:
    from .drawdown_control import (
        AdvancedDrawdownController,
        DrawdownLevel,
        DrawdownMetrics,
        PositionRisk,
        RiskAction,
        RiskParameters,
    )
except ImportError:
    # Drawdown control may have missing dependencies
    AdvancedDrawdownController = None
    DrawdownLevel = None
    RiskAction = None
    DrawdownMetrics = None
    PositionRisk = None
    RiskParameters = None

__all__ = [
    # Unified risk management system
    "BaseRiskManager",
    "RiskLimits",
    "RiskMetrics",
    "Position",
    "RiskViolation",
    "LiveRiskManager",
    "BacktestRiskManager",
    "BrokerRiskManager",
    # Legacy compatibility
    "RiskManager",
    "RiskConfig",
    # From backtesting (if available)
    "AdvancedRiskManager",
    "DynamicStopLossManager",
    "VolatilityScaler",
    "KellyCriterion",
    "FixedFractional",
    # Position sizing (if available)
    "KellyCriterionSizer",
    "VolatilityBasedSizer",
    "FixedRiskSizer",
    "DynamicPositionSizer",
    # Advanced drawdown control
    "AdvancedDrawdownController",
    "DrawdownLevel",
    "RiskAction",
    "DrawdownMetrics",
    "PositionRisk",
    "RiskParameters",
]
