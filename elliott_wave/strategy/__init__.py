"""
Strategy module for Elliott Wave-based trading.

This module implements trading strategies based on Elliott Wave pattern
detection, with support for entry/exit signals, risk management, and
position sizing.
"""

from fxml3.strategy.entry_signals import (
    EntrySignal,
    EntrySignalGenerator,
    SignalStrength,
    SignalType,
)
from fxml3.strategy.exit_signals import ExitSignal, ExitSignalGenerator
from fxml3.strategy.portfolio_manager import (
    AssetClass,
    CorrelationType,
    PortfolioManager,
    Position,
)
from fxml3.strategy.position_sizing import (
    PositionSize,
    PositionSizer,
    PositionSizingMethod,
)
from fxml3.strategy.risk_management import InvalidationLevel, RiskManager
