"""
Strategy module for Elliott Wave-based trading.

This module implements trading strategies based on Elliott Wave pattern
detection, with support for entry/exit signals, risk management, and
position sizing.
"""

from fxml3.strategy.entry_signals import EntrySignalGenerator, EntrySignal, SignalType, SignalStrength
from fxml3.strategy.exit_signals import ExitSignalGenerator, ExitSignal
from fxml3.strategy.risk_management import RiskManager, InvalidationLevel
from fxml3.strategy.position_sizing import PositionSizer, PositionSize, PositionSizingMethod
from fxml3.strategy.portfolio_manager import PortfolioManager, Position, AssetClass, CorrelationType