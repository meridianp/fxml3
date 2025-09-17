"""
Risk Management Module for FXML4

Comprehensive risk management including position sizing, margin calculations,
portfolio risk assessment, stop loss automation, and emergency controls.
"""

from core.risk.emergency_manager import EmergencyAction, EmergencyLevel, EmergencyManager
from core.risk.risk_manager import RiskManager
from core.risk.stop_loss_manager import (
    StopLossConfig,
    StopLossManager,
    StopLossType,
    TakeProfitConfig,
    TakeProfitType,
)

__all__ = [
    "RiskManager",
    "StopLossManager",
    "StopLossType",
    "StopLossConfig",
    "TakeProfitType",
    "TakeProfitConfig",
    "EmergencyManager",
    "EmergencyLevel",
    "EmergencyAction",
]