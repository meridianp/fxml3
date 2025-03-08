"""
Strategy module for Elliott Wave-based trading.

This module implements trading strategies based on Elliott Wave pattern
detection, with support for entry/exit signals, risk management, and
position sizing.
"""

from fxml3.strategy.entry_signals import EntrySignalGenerator
from fxml3.strategy.exit_signals import ExitSignalGenerator
from fxml3.strategy.risk_manager import RiskManager
from fxml3.strategy.position_sizer import PositionSizer
from fxml3.strategy.portfolio_manager import PortfolioManager
from fxml3.strategy.strategy_generator import StrategyGenerator