"""Unit tests for the backtesting engine."""

from datetime import datetime
from unittest.mock import Mock, patch

import numpy as np
import pandas as pd
import pytest

from fxml4.backtesting.backtest_engine import (
    BacktestEngine,
    BacktestResult,
    Order,
    OrderSide,
    OrderType,
    Position,
    PositionStatus,
    run_backtest,
)


class TestEnums:
    """Test the enum classes."""

    def test_order_type_enum(self):
        """Test OrderType enum."""
        assert OrderType.MARKET.value == "market"
        assert OrderType.LIMIT.value == "limit"
        assert OrderType.STOP.value == "stop"
        assert OrderType.STOP_LIMIT.value == "stop_limit"

    def test_order_side_enum(self):
        """Test OrderSide enum."""
        assert OrderSide.BUY.value == "buy"
        assert OrderSide.SELL.value == "sell"

    def test_position_status_enum(self):
        """Test PositionStatus enum."""
        assert PositionStatus.OPEN.value == "open"
        assert PositionStatus.CLOSED.value == "closed"


class TestDataClasses:
    """Test the data classes."""

    def test_order_creation(self):
        """Test Order data class creation."""
        order = Order(
            order_id="ORDER-1",
            symbol="EURUSD",
            order_type=OrderType.MARKET,
            side=OrderSide.BUY,
            quantity=1000,
            price=1.1000,
            stop_price=None,
            timestamp=datetime.now(),
            status="pending",
        )
        assert order.order_id == "ORDER-1"
        assert order.symbol == "EURUSD"
        assert order.order_type == OrderType.MARKET
        assert order.side == OrderSide.BUY

    def test_position_creation(self):
        """Test Position data class creation."""
        position = Position(
            position_id="POS-1",
            symbol="EURUSD",
            side=OrderSide.BUY,
            entry_price=1.1000,
            entry_timestamp=datetime.now(),
            quantity=1000,
            status=PositionStatus.OPEN,
        )
        assert position.position_id == "POS-1"
        assert position.symbol == "EURUSD"
        assert position.side == OrderSide.BUY
        assert position.status == PositionStatus.OPEN


class TestBacktestEngine:
    """Test the BacktestEngine class."""

    def test_init_default_config(self):
        """Test engine initialization with default config."""
        engine = BacktestEngine()
        assert engine.initial_capital == 10000  # Default from config
        assert engine.commission >= 0
        assert engine.slippage >= 0
        assert engine.capital == engine.initial_capital

    def test_init_custom_config(self):
        """Test engine initialization with custom config."""
        config = {"initial_capital": 50000, "commission": 0.001, "slippage": 0.0005}
        engine = BacktestEngine(config)
        assert engine.initial_capital == 50000
        assert engine.commission == 0.001
        assert engine.slippage == 0.0005

    def test_reset(self):
        """Test engine reset functionality."""
        engine = BacktestEngine()

        # Modify engine state
        engine.capital = 5000
        engine.equity = 5000
        engine.orders = [Mock()]
        engine.positions = [Mock()]
        engine.open_positions = {"EURUSD": Mock()}

        # Reset and verify
        engine.reset()
        assert engine.capital == engine.initial_capital
        assert engine.equity == engine.initial_capital
        assert len(engine.orders) == 0
        assert len(engine.positions) == 0
        assert len(engine.open_positions) == 0

    def test_calculate_position_size_fixed_percentage(self, sample_ohlc_data):
        """Test position size calculation with fixed percentage."""
        engine = BacktestEngine()
        signals = {"risk_pct": 0.02}
        bar = sample_ohlc_data.iloc[0]

        position_size = engine._calculate_position_size(signals, bar)
        expected_size = (engine.capital * 0.02) / bar["close"]
        assert abs(position_size - expected_size) < 0.001

    def test_calculate_position_size_with_stop_loss(self, sample_ohlc_data):
        """Test position size calculation with stop loss."""
        engine = BacktestEngine()
        bar = sample_ohlc_data.iloc[0]
        stop_loss = bar["close"] * 0.99  # 1% stop loss

        signals = {"risk_pct": 0.02, "stop_loss": stop_loss}

        position_size = engine._calculate_position_size(signals, bar)
        assert position_size > 0

    def test_calculate_equity_no_positions(self, sample_ohlc_data):
        """Test equity calculation with no open positions."""
        engine = BacktestEngine()
        bar = sample_ohlc_data.iloc[0]

        initial_equity = engine.equity
        engine._calculate_equity(bar)
        assert engine.equity == initial_equity

    def test_process_entry_signal(self, sample_ohlc_data):
        """Test processing entry signals."""
        engine = BacktestEngine()
        bar = sample_ohlc_data.iloc[0]
        engine.current_timestamp = bar["time"]

        signals = {
            "entry": True,
            "direction": "buy",
            "symbol": "EURUSD",
            "risk_pct": 0.02,
        }

        initial_positions = len(engine.positions)
        engine._process_signals(signals, bar)

        assert len(engine.positions) == initial_positions + 1
        assert "EURUSD" in engine.open_positions
        assert engine.open_positions["EURUSD"].side == OrderSide.BUY

    def test_process_exit_signal(self, sample_ohlc_data):
        """Test processing exit signals."""
        engine = BacktestEngine()
        bar = sample_ohlc_data.iloc[0]
        engine.current_timestamp = bar["time"]

        # First create a position
        signals_entry = {
            "entry": True,
            "direction": "buy",
            "symbol": "EURUSD",
            "risk_pct": 0.02,
        }
        engine._process_signals(signals_entry, bar)

        # Then exit the position
        signals_exit = {"exit": True, "symbol": "EURUSD"}

        initial_capital = engine.capital
        engine._process_signals(signals_exit, bar)

        assert "EURUSD" not in engine.open_positions
        assert engine.positions[-1].status == PositionStatus.CLOSED

    def test_close_position_profit(self, sample_ohlc_data):
        """Test closing a profitable position."""
        engine = BacktestEngine()

        # Create a position manually
        entry_price = 1.1000
        exit_price = 1.1100  # Profitable
        quantity = 1000

        position = Position(
            position_id="POS-1",
            symbol="EURUSD",
            side=OrderSide.BUY,
            entry_price=entry_price,
            entry_timestamp=datetime.now(),
            quantity=quantity,
            status=PositionStatus.OPEN,
        )

        engine.open_positions["EURUSD"] = position
        engine.positions.append(position)

        # Create exit bar
        bar = sample_ohlc_data.iloc[0].copy()
        bar["close"] = exit_price

        initial_capital = engine.capital
        engine._close_position("EURUSD", bar)

        # Check that position was closed profitably
        assert position.status == PositionStatus.CLOSED
        assert position.pnl > 0
        assert "EURUSD" not in engine.open_positions

    def test_close_position_loss(self, sample_ohlc_data):
        """Test closing a losing position."""
        engine = BacktestEngine()

        # Create a position manually
        entry_price = 1.1000
        exit_price = 1.0900  # Loss
        quantity = 1000

        position = Position(
            position_id="POS-1",
            symbol="EURUSD",
            side=OrderSide.BUY,
            entry_price=entry_price,
            entry_timestamp=datetime.now(),
            quantity=quantity,
            status=PositionStatus.OPEN,
        )

        engine.open_positions["EURUSD"] = position
        engine.positions.append(position)

        # Create exit bar
        bar = sample_ohlc_data.iloc[0].copy()
        bar["close"] = exit_price

        engine._close_position("EURUSD", bar)

        # Check that position was closed with loss
        assert position.status == PositionStatus.CLOSED
        assert position.pnl < 0

    def test_run_backtest_simple_strategy(self, sample_ohlc_data):
        """Test running a complete backtest with simple strategy."""

        def simple_strategy(data, current_idx, params):
            """Simple buy and hold strategy."""
            if current_idx == 10:  # Buy after 10 bars
                return {
                    "entry": True,
                    "direction": "buy",
                    "symbol": params.get("symbol", "EURUSD"),
                    "risk_pct": 0.02,
                }
            elif current_idx == 50:  # Sell after 50 bars
                return {"exit": True, "symbol": params.get("symbol", "EURUSD")}
            return {}

        engine = BacktestEngine()
        strategy_params = {"symbol": "EURUSD", "timeframe": "1h"}

        result = engine.run(simple_strategy, sample_ohlc_data, strategy_params)

        assert isinstance(result, BacktestResult)
        assert result.strategy_name == "simple_strategy"
        assert result.symbol == "EURUSD"
        assert result.timeframe == "1h"
        assert len(result.trades) >= 0  # May or may not have trades
        assert isinstance(result.equity_curve, pd.DataFrame)


class TestRunBacktestFunction:
    """Test the run_backtest function."""

    def test_run_backtest_function(self, sample_ohlc_data):
        """Test the run_backtest convenience function."""

        def dummy_strategy(data, current_idx, params):
            return {}

        result = run_backtest(
            dummy_strategy,
            sample_ohlc_data,
            {"symbol": "EURUSD"},
            {"initial_capital": 5000},
        )

        assert isinstance(result, BacktestResult)
        assert result.initial_capital == 5000
