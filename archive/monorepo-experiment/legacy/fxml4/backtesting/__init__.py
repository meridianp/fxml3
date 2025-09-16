"""Backtesting package for FXML4.

This package provides backtesting capabilities for trading strategies.
"""

from .backtest_engine import (
    BacktestEngine, BacktestResult, run_backtest,
    OrderType, OrderSide, PositionStatus, Order, Position
)

from .performance_metrics import (
    PerformanceMetrics, PerformanceAnalyzer, ScenarioAnalyzer
)