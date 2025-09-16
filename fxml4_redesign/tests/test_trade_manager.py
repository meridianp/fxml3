"""Unit tests for Trade Manager Service components."""

import asyncio
from datetime import datetime, timedelta
from decimal import Decimal
from unittest.mock import AsyncMock, Mock, patch

import pytest
import pytest_asyncio
from services.trade_manager.exit_strategy_manager import (
    ExitLevel,
    ExitReason,
    ExitStrategy,
    ExitStrategyManager,
)
from services.trade_manager.pnl_tracker import (
    PnLMetrics,
    PnLPeriod,
    PnLTracker,
    TradeOutcome,
)
from services.trade_manager.position_manager import (
    Position,
    PositionManager,
    PositionState,
)
from services.trade_manager.risk_monitor import (
    RiskAlert,
    RiskLevel,
    RiskLimits,
    RiskMonitor,
    RiskType,
)
from shared.schemas.broker_messages import OrderSide, OrderType


# Fixtures
@pytest.fixture
def sample_position_data():
    """Sample position data for testing."""
    return {
        "position_id": "pos_test_123",
        "signal_id": "sig_test_456",
        "symbol": "EURUSD",
        "side": "BUY",
        "target_quantity": "10000",
        "target_entry": "1.0950",
        "stop_loss": "1.0920",
        "take_profit_1": "1.0980",
        "take_profit_2": "1.1000",
        "take_profit_3": "1.1020",
    }


@pytest.fixture
def sample_trade_request():
    """Sample trade request for risk checking."""
    return {
        "symbol": "EURUSD",
        "side": "BUY",
        "quantity": "10000",
        "price": "1.0950",
        "stop_loss": "1.0920",
    }


@pytest.fixture
def sample_account_data():
    """Sample account data."""
    return {
        "balance": Decimal("100000"),
        "equity": Decimal("100500"),
        "margin_used": Decimal("5000"),
        "margin_available": Decimal("95500"),
        "peak_balance": Decimal("102000"),
    }


@pytest_asyncio.fixture
async def position_manager():
    """Create position manager instance."""
    manager = PositionManager()
    return manager


@pytest_asyncio.fixture
async def exit_strategy_manager():
    """Create exit strategy manager instance."""
    manager = ExitStrategyManager()
    await manager.initialize()
    return manager


@pytest_asyncio.fixture
async def risk_monitor():
    """Create risk monitor instance."""
    monitor = RiskMonitor()
    await monitor.initialize()
    return monitor


@pytest_asyncio.fixture
async def pnl_tracker():
    """Create P&L tracker instance."""
    tracker = PnLTracker()
    await tracker.initialize()
    return tracker


# Position Manager Tests
class TestPositionManager:
    """Test suite for PositionManager."""

    async def test_create_position(self, position_manager, sample_position_data):
        """Test position creation."""
        position = await position_manager.create_position(sample_position_data)

        assert position.position_id == "pos_test_123"
        assert position.symbol == "EURUSD"
        assert position.side == OrderSide.BUY
        assert position.target_quantity == Decimal("10000")
        assert position.state == PositionState.PENDING

        # Check position is indexed
        assert "pos_test_123" in position_manager.positions
        assert "sig_test_456" in position_manager.positions_by_signal
        assert "EURUSD" in position_manager.positions_by_symbol

    async def test_position_state_transitions(
        self, position_manager, sample_position_data
    ):
        """Test position state transitions."""
        position = await position_manager.create_position(sample_position_data)

        # Test state transition to OPENING
        success = await position_manager.update_position_state(
            "pos_test_123", PositionState.OPENING
        )
        assert success
        assert position.state == PositionState.OPENING

        # Test state transition to OPEN
        success = await position_manager.update_position_state(
            "pos_test_123", PositionState.OPEN
        )
        assert success
        assert position.state == PositionState.OPEN
        assert position.opened_at is not None

        # Test state transition to CLOSED
        success = await position_manager.update_position_state(
            "pos_test_123", PositionState.CLOSED
        )
        assert success
        assert position.state == PositionState.CLOSED
        assert position.closed_at is not None

        # Check position moved to closed positions
        assert "pos_test_123" not in position_manager.positions
        assert "pos_test_123" in position_manager.closed_positions

    async def test_position_fill_updates(self, position_manager, sample_position_data):
        """Test position fill updates."""
        position = await position_manager.create_position(sample_position_data)

        # Add first fill
        success = await position_manager.update_position_fill(
            "pos_test_123", Decimal("5000"), Decimal("1.0948"), Decimal("5")
        )
        assert success
        assert position.filled_quantity == Decimal("5000")
        assert position.avg_entry_price == Decimal("1.0948")
        assert position.commission == Decimal("5")

        # Add second fill
        success = await position_manager.update_position_fill(
            "pos_test_123", Decimal("5000"), Decimal("1.0952"), Decimal("5")
        )
        assert success
        assert position.filled_quantity == Decimal("10000")
        assert position.avg_entry_price == Decimal("1.0950")  # Average of two fills
        assert position.commission == Decimal("10")
        assert position.state == PositionState.OPEN  # Auto-transition when fully filled

    async def test_position_exit_updates(self, position_manager, sample_position_data):
        """Test position exit updates."""
        position = await position_manager.create_position(sample_position_data)
        position.filled_quantity = Decimal("10000")
        position.remaining_quantity = Decimal("10000")
        position.avg_entry_price = Decimal("1.0950")
        position.side = OrderSide.BUY

        # Partial exit
        success = await position_manager.update_position_exit(
            "pos_test_123", Decimal("3000"), Decimal("1.0980"), Decimal("3")
        )
        assert success
        assert position.remaining_quantity == Decimal("7000")
        assert position.realized_pnl == Decimal("90")  # 3000 * (1.0980 - 1.0950)

        # Full exit
        success = await position_manager.update_position_exit(
            "pos_test_123", Decimal("7000"), Decimal("1.0990"), Decimal("7")
        )
        assert success
        assert position.remaining_quantity == Decimal("0")
        assert position.realized_pnl == Decimal("370")  # 90 + 7000 * (1.0990 - 1.0950)
        assert position.state == PositionState.CLOSED

    async def test_trailing_stop_activation(
        self, position_manager, sample_position_data
    ):
        """Test trailing stop activation and calculation."""
        position = await position_manager.create_position(sample_position_data)
        position.current_price = Decimal("1.1000")
        position.side = OrderSide.BUY

        # Activate trailing stop
        success = await position_manager.activate_trailing_stop(
            "pos_test_123", Decimal("0.0020")  # 20 pips
        )
        assert success
        assert position.trailing_stop_active
        assert position.trailing_stop_distance == Decimal("0.0020")
        assert position.highest_price == Decimal("1.1000")

        # Update price and check trailing stop
        await position_manager.update_position_price("pos_test_123", Decimal("1.1020"))
        trailing_stop = await position_manager.calculate_trailing_stop("pos_test_123")
        assert trailing_stop == Decimal("1.1000")  # 1.1020 - 0.0020

    async def test_position_pnl_calculation(
        self, position_manager, sample_position_data
    ):
        """Test position P&L calculations."""
        position = await position_manager.create_position(sample_position_data)
        position.filled_quantity = Decimal("10000")
        position.avg_entry_price = Decimal("1.0950")
        position.side = OrderSide.BUY

        # Update price for unrealized P&L
        position.update_price(Decimal("1.0970"))
        assert position.unrealized_pnl == Decimal("200")  # 10000 * (1.0970 - 1.0950)

        # Test for SELL position
        position.side = OrderSide.SELL
        position.update_price(Decimal("1.0930"))
        assert position.unrealized_pnl == Decimal("200")  # 10000 * (1.0950 - 1.0930)


# Exit Strategy Manager Tests
class TestExitStrategyManager:
    """Test suite for ExitStrategyManager."""

    async def test_default_strategies_loaded(self, exit_strategy_manager):
        """Test that default strategies are loaded."""
        assert "conservative" in exit_strategy_manager.strategies
        assert "aggressive" in exit_strategy_manager.strategies
        assert "scalping" in exit_strategy_manager.strategies

    async def test_assign_strategy(self, exit_strategy_manager):
        """Test strategy assignment to position."""
        strategy = await exit_strategy_manager.assign_strategy(
            "pos_test_123", "aggressive"
        )

        assert strategy.name == "Aggressive"
        assert exit_strategy_manager.position_strategies["pos_test_123"] == "aggressive"

    async def test_calculate_exit_levels(self, exit_strategy_manager):
        """Test exit level calculations."""
        position_data = {
            "position_id": "pos_test_123",
            "entry_price": "1.0950",
            "side": "BUY",
            "symbol": "EURUSD",
        }

        # Assign conservative strategy
        await exit_strategy_manager.assign_strategy("pos_test_123", "conservative")

        levels = await exit_strategy_manager.calculate_exit_levels(position_data)

        assert "stop_loss" in levels
        assert "take_profit_1" in levels
        assert "take_profit_2" in levels
        assert "take_profit_3" in levels

        # Check stop loss is below entry for BUY
        assert levels["stop_loss"] < Decimal("1.0950")

        # Check take profits are above entry for BUY
        assert levels["take_profit_1"] > Decimal("1.0950")
        assert levels["take_profit_2"] > levels["take_profit_1"]
        assert levels["take_profit_3"] > levels["take_profit_2"]

    async def test_create_exit_orders(self, exit_strategy_manager):
        """Test exit order creation."""
        position_data = {
            "position_id": "pos_test_123",
            "symbol": "EURUSD",
            "side": "BUY",
            "quantity": "10000",
        }

        exit_levels = {
            "stop_loss": Decimal("1.0920"),
            "take_profit_1": Decimal("1.0980"),
            "take_profit_2": Decimal("1.1000"),
        }

        # Mock broker adapter
        mock_broker = AsyncMock()
        mock_broker.place_order = AsyncMock(
            return_value=Mock(status="ACCEPTED", broker_order_id="ord_123")
        )

        order_ids = await exit_strategy_manager.create_exit_orders(
            position_data, exit_levels, mock_broker
        )

        # Check orders were created
        assert "stop_loss" in order_ids
        assert mock_broker.place_order.call_count >= 2  # At least stop and one TP

    async def test_time_based_exits(self, exit_strategy_manager):
        """Test time-based exit checks."""
        position_data = {
            "position_id": "pos_test_123",
            "opened_at": datetime.utcnow() - timedelta(hours=80),  # Over 72 hours
        }

        # Assign scalping strategy with time exit
        await exit_strategy_manager.assign_strategy("pos_test_123", "scalping")

        should_exit, reason = await exit_strategy_manager.check_time_exits(
            position_data
        )

        assert should_exit
        assert reason == ExitReason.TIME_EXIT


# Risk Monitor Tests
class TestRiskMonitor:
    """Test suite for RiskMonitor."""

    async def test_pre_trade_risk_check_success(
        self, risk_monitor, sample_trade_request, sample_account_data
    ):
        """Test successful pre-trade risk check."""
        positions = []  # No existing positions

        allowed, violations = await risk_monitor.check_pre_trade_risk(
            sample_trade_request, sample_account_data, positions
        )

        assert allowed
        assert len(violations) == 0

    async def test_pre_trade_risk_check_position_limit(
        self, risk_monitor, sample_trade_request, sample_account_data
    ):
        """Test pre-trade risk check with position limit violation."""
        # Create max positions
        positions = [
            {"symbol": f"PAIR{i}", "quantity": 10000, "current_price": 1.0}
            for i in range(10)
        ]

        allowed, violations = await risk_monitor.check_pre_trade_risk(
            sample_trade_request, sample_account_data, positions
        )

        assert not allowed
        assert any("Maximum positions" in v for v in violations)

    async def test_daily_loss_limit_check(self, risk_monitor):
        """Test daily loss limit checking."""
        # Set daily loss
        await risk_monitor.update_daily_pnl(
            {
                "date": datetime.utcnow().date(),
                "amount": "-2500",  # 2.5% loss on 100k account
            }
        )

        # Check should trigger alert
        assert risk_monitor.daily_pnl[datetime.utcnow().date()] == Decimal("-2500")

    async def test_create_and_resolve_alert(self, risk_monitor):
        """Test alert creation and resolution."""
        alert = await risk_monitor.create_alert(
            RiskType.POSITION_SIZE,
            RiskLevel.HIGH,
            "Position size exceeds limit",
            details={"position_id": "pos_123"},
            action_required=True,
        )

        assert alert.alert_id in risk_monitor.active_alerts
        assert alert.risk_type == RiskType.POSITION_SIZE
        assert alert.risk_level == RiskLevel.HIGH
        assert alert.action_required

        # Resolve alert
        await risk_monitor.resolve_alert(alert.alert_id)
        assert alert.alert_id not in risk_monitor.active_alerts
        assert alert.alert_id in [a.alert_id for a in risk_monitor.alert_history]

    async def test_portfolio_risk_calculation(self, risk_monitor, sample_account_data):
        """Test portfolio risk calculations."""
        positions = [
            {
                "symbol": "EURUSD",
                "quantity": Decimal("10000"),
                "current_price": Decimal("1.0950"),
                "side": "BUY",
            },
            {
                "symbol": "GBPUSD",
                "quantity": Decimal("8000"),
                "current_price": Decimal("1.2650"),
                "side": "SELL",
            },
        ]

        metrics = await risk_monitor.check_portfolio_risk(
            positions, sample_account_data
        )

        assert "total_exposure" in metrics
        assert "portfolio_var" in metrics
        assert "max_drawdown" in metrics
        assert "correlation_risk" in metrics
        assert metrics["total_positions"] == 2


# P&L Tracker Tests
class TestPnLTracker:
    """Test suite for PnLTracker."""

    async def test_record_trade_open(self, pnl_tracker):
        """Test recording trade opening."""
        trade_data = {
            "position_id": "pos_test_123",
            "symbol": "EURUSD",
            "side": "BUY",
            "quantity": "10000",
            "entry_price": "1.0950",
            "strategy": "elliott_wave",
            "commission": "10",
        }

        await pnl_tracker.record_trade_open(trade_data)

        assert "pos_test_123" in pnl_tracker.open_positions
        position = pnl_tracker.open_positions["pos_test_123"]
        assert position["symbol"] == "EURUSD"
        assert position["quantity"] == Decimal("10000")
        assert position["entry_price"] == Decimal("1.0950")
        assert pnl_tracker.current_metrics.commission_paid == Decimal("10")

    async def test_update_position_pnl(self, pnl_tracker):
        """Test updating position P&L."""
        # First open a position
        await pnl_tracker.record_trade_open(
            {
                "position_id": "pos_test_123",
                "symbol": "EURUSD",
                "side": "BUY",
                "quantity": "10000",
                "entry_price": "1.0950",
            }
        )

        # Update with new price
        await pnl_tracker.update_position_pnl("pos_test_123", Decimal("1.0970"))

        position = pnl_tracker.open_positions["pos_test_123"]
        assert position["unrealized_pnl"] == Decimal("200")  # 10000 * 0.0020

    async def test_record_trade_close(self, pnl_tracker):
        """Test recording trade closing."""
        # Open position first
        await pnl_tracker.record_trade_open(
            {
                "position_id": "pos_test_123",
                "symbol": "EURUSD",
                "side": "BUY",
                "quantity": "10000",
                "entry_price": "1.0950",
                "commission": "10",
            }
        )

        # Close position
        await pnl_tracker.record_trade_close(
            "pos_test_123", Decimal("1.0980"), commission=Decimal("10")
        )

        # Check position removed from open
        assert "pos_test_123" not in pnl_tracker.open_positions

        # Check trade recorded in history
        assert len(pnl_tracker.trades_history) == 1
        trade = pnl_tracker.trades_history[0]
        assert trade["gross_pnl"] == 300.0  # 10000 * 0.0030
        assert trade["net_pnl"] == 290.0  # 300 - 10 commission
        assert trade["outcome"] == TradeOutcome.WIN

        # Check metrics updated
        assert pnl_tracker.current_metrics.realized_pnl == Decimal("290")
        assert pnl_tracker.current_metrics.total_trades == 1
        assert pnl_tracker.current_metrics.winning_trades == 1

    async def test_performance_metrics_calculation(self, pnl_tracker):
        """Test performance metrics calculations."""
        # Record multiple trades
        trades = [
            {"id": "1", "pnl": 100, "outcome": "win"},
            {"id": "2", "pnl": -50, "outcome": "loss"},
            {"id": "3", "pnl": 150, "outcome": "win"},
            {"id": "4", "pnl": -30, "outcome": "loss"},
            {"id": "5", "pnl": 80, "outcome": "win"},
        ]

        for i, trade in enumerate(trades):
            await pnl_tracker.record_trade_open(
                {
                    "position_id": f"pos_{i}",
                    "symbol": "EURUSD",
                    "side": "BUY",
                    "quantity": "10000",
                    "entry_price": "1.0950",
                }
            )

            exit_price = Decimal("1.0950") + (Decimal(str(trade["pnl"])) / 10000)
            await pnl_tracker.record_trade_close(f"pos_{i}", exit_price)

        # Check calculated metrics
        metrics = pnl_tracker.current_metrics
        assert metrics.total_trades == 5
        assert metrics.winning_trades == 3
        assert metrics.losing_trades == 2
        assert metrics.win_rate == 0.6
        assert metrics.gross_profit == Decimal("330")
        assert metrics.gross_loss == Decimal("80")
        assert metrics.profit_factor == pytest.approx(4.125, rel=0.01)

    async def test_equity_curve_tracking(self, pnl_tracker):
        """Test equity curve tracking."""
        initial_balance = pnl_tracker.account_balance

        # Record a winning trade
        await pnl_tracker.record_trade_open(
            {
                "position_id": "pos_1",
                "symbol": "EURUSD",
                "side": "BUY",
                "quantity": "10000",
                "entry_price": "1.0950",
            }
        )

        await pnl_tracker.record_trade_close("pos_1", Decimal("1.0980"))

        # Check equity curve
        assert len(pnl_tracker.equity_curve) > 1
        assert pnl_tracker.account_balance > initial_balance
        assert pnl_tracker.peak_balance == pnl_tracker.account_balance

        # Record a losing trade
        await pnl_tracker.record_trade_open(
            {
                "position_id": "pos_2",
                "symbol": "EURUSD",
                "side": "BUY",
                "quantity": "10000",
                "entry_price": "1.0950",
            }
        )

        await pnl_tracker.record_trade_close("pos_2", Decimal("1.0920"))

        # Check drawdown
        assert pnl_tracker.current_metrics.current_drawdown > 0

    async def test_get_performance_summary(self, pnl_tracker):
        """Test getting performance summary."""
        # Record some trades
        await pnl_tracker.record_trade_open(
            {
                "position_id": "pos_1",
                "symbol": "EURUSD",
                "side": "BUY",
                "quantity": "10000",
                "entry_price": "1.0950",
                "strategy": "elliott_wave",
            }
        )

        await pnl_tracker.record_trade_close("pos_1", Decimal("1.0980"))

        summary = await pnl_tracker.get_performance_summary()

        assert "realized_pnl" in summary
        assert "unrealized_pnl" in summary
        assert "total_trades" in summary
        assert "win_rate" in summary
        assert "profit_factor" in summary
        assert "sharpe_ratio" in summary
        assert "max_drawdown" in summary
        assert "account_balance" in summary
        assert "best_symbol" in summary
        assert "best_strategy" in summary


# Integration Tests
class TestTradeManagerIntegration:
    """Integration tests for Trade Manager components."""

    async def test_full_position_lifecycle(
        self, position_manager, exit_strategy_manager, risk_monitor, pnl_tracker
    ):
        """Test full position lifecycle from open to close."""
        # Create position
        position_data = {
            "position_id": "pos_integration_test",
            "signal_id": "sig_test",
            "symbol": "EURUSD",
            "side": "BUY",
            "target_quantity": "10000",
            "target_entry": "1.0950",
        }

        position = await position_manager.create_position(position_data)

        # Record in P&L tracker
        await pnl_tracker.record_trade_open(
            {
                "position_id": position.position_id,
                "symbol": position.symbol,
                "side": position.side.value,
                "quantity": str(position.target_quantity),
                "entry_price": str(position.target_entry),
            }
        )

        # Assign exit strategy
        strategy = await exit_strategy_manager.assign_strategy(
            position.position_id, "conservative"
        )

        # Calculate exit levels
        levels = await exit_strategy_manager.calculate_exit_levels(
            {
                "position_id": position.position_id,
                "entry_price": str(position.target_entry),
                "side": position.side.value,
                "symbol": position.symbol,
            }
        )

        # Update position with fill
        await position_manager.update_position_fill(
            position.position_id, position.target_quantity, position.target_entry
        )

        # Update position risk
        await risk_monitor.update_position_risk(
            position.to_dict(), {"current_price": position.target_entry}
        )

        # Simulate price movement and exit
        exit_price = levels["take_profit_1"]
        await position_manager.update_position_exit(
            position.position_id, position.target_quantity, exit_price
        )

        # Record close in P&L tracker
        await pnl_tracker.record_trade_close(position.position_id, exit_price)

        # Verify final state
        assert position.state == PositionState.CLOSED
        assert position.realized_pnl > 0
        assert len(pnl_tracker.trades_history) == 1
        assert pnl_tracker.current_metrics.winning_trades == 1
