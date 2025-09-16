"""
Trade Execution Engine for FXML4 Trading Platform

This module provides enterprise-grade trade execution capabilities that convert
ML signals and Elliott Wave patterns into executed trades through the Order
Management System and broker adapters.

Key Components:
- TradeExecutionEngine: Main orchestrator for signal-to-trade conversion
- SignalProcessor: ML signal interpretation and trade decision logic
- ExecutionStrategy: Market/TWAP/VWAP execution algorithms
- PositionManager: Cross-broker position tracking and risk monitoring
- ExecutionMonitor: Performance attribution and execution cost analysis

Architecture Integration:
- Input: Phase 2 ML ensemble and Elliott Wave signals
- Risk: Phase 1 advanced risk management and drawdown controls
- Orders: Order Management System for broker coordination
- Data: TimescaleDB for position tracking, Redis for performance caching
"""

from .trade_execution_engine import (
    ExecutionMonitor,
    ExecutionResult,
    ExecutionStrategy,
    InsufficientCapitalError,
    Position,
    PositionManager,
    SignalProcessor,
    TradeExecution,
    TradeExecutionEngine,
    TradeExecutionError,
    TradeRequest,
    TradingSignal,
)

__all__ = [
    "TradeExecutionEngine",
    "SignalProcessor",
    "ExecutionStrategy",
    "PositionManager",
    "ExecutionMonitor",
    "TradingSignal",
    "TradeRequest",
    "TradeExecution",
    "Position",
    "ExecutionResult",
    "TradeExecutionError",
    "InsufficientCapitalError",
]
