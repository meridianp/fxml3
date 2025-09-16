"""
FXML4 Backtesting Framework.

This package provides comprehensive backtesting capabilities for trading strategies.
"""

from fxml4_backtesting.engine import BacktestEngine, EventDrivenEngine
from fxml4_backtesting.strategy import Strategy, Signal
from fxml4_backtesting.portfolio import Portfolio, Position
from fxml4_backtesting.performance import PerformanceAnalyzer, PerformanceMetrics

__version__ = "0.1.0"
__all__ = [
    "BacktestEngine",
    "EventDrivenEngine", 
    "Strategy",
    "Signal",
    "Portfolio",
    "Position",
    "PerformanceAnalyzer",
    "PerformanceMetrics"
]