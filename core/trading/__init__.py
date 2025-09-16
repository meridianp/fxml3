"""Trading module."""

# Re-export from unified risk_management module
from ..risk_management import (  # Legacy compatibility
    BacktestRiskManager,
    BaseRiskManager,
    BrokerRiskManager,
    LiveRiskManager,
    Position,
    RiskConfig,
    RiskLimits,
    RiskManager,
    RiskMetrics,
    RiskViolation,
)

# Additional trading components (re-export for backward compatibility)
TradingBaseRiskManager = BaseRiskManager
TradingRiskLimits = RiskLimits
TradingLiveRiskManager = LiveRiskManager
TradingBacktestRiskManager = BacktestRiskManager
TradingBrokerRiskManager = BrokerRiskManager
TradingRiskManager = RiskManager
TradingRiskConfig = RiskConfig

__all__ = [
    # From risk_management
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
    # From trading.risk_manager
    "TradingBaseRiskManager",
    "TradingRiskLimits",
    "TradingLiveRiskManager",
    "TradingBacktestRiskManager",
    "TradingBrokerRiskManager",
    "TradingRiskManager",
    "TradingRiskConfig",
]
