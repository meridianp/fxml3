"""Tests for LiveRiskManager implementation."""

import asyncio
from collections import deque
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from fxml4.risk_management.base import (
    Position,
    RiskCheckResult,
    RiskCheckType,
    RiskLimits,
    RiskMetrics,
    RiskViolation,
)
from fxml4.risk_management.live import LiveRiskManager


class TestLiveRiskManager:
    """Test LiveRiskManager class."""

    @pytest.fixture
    def live_risk_manager(self):
        """Create a live risk manager."""
        limits = RiskLimits(
            max_position_size=0.1, max_daily_loss=0.03, max_drawdown=0.15
        )
        return LiveRiskManager(limits=limits, circuit_breaker_enabled=True)

    @pytest.fixture
    def risk_manager_no_circuit_breaker(self):
        """Create a live risk manager without circuit breaker."""
        return LiveRiskManager(circuit_breaker_enabled=False)

    def test_initialization(self, live_risk_manager):
        """Test live risk manager initialization."""
        assert isinstance(live_risk_manager.limits, RiskLimits)
        assert live_risk_manager.circuit_breaker_enabled is True
        assert live_risk_manager.circuit_breaker_triggered is False
        assert live_risk_manager.circuit_breaker_trigger_time is None
        assert live_risk_manager.circuit_breaker_reset_time is None

        # Check monitoring structures
        assert isinstance(live_risk_manager.order_history, deque)
        assert live_risk_manager.order_history.maxlen == 1000
        assert isinstance(live_risk_manager.pnl_history, deque)
        assert live_risk_manager.pnl_history.maxlen == 1000

        # Check trade limits
        assert live_risk_manager.daily_trade_count == 0
        assert live_risk_manager.hourly_trade_count == 0
        assert live_risk_manager.max_daily_trades == 100
        assert live_risk_manager.max_hourly_trades == 20

    def test_initialization_without_circuit_breaker(
        self, risk_manager_no_circuit_breaker
    ):
        """Test initialization without circuit breaker."""
        assert risk_manager_no_circuit_breaker.circuit_breaker_enabled is False

    def test_validate_order_success(self, live_risk_manager):
        """Test successful order validation."""
        is_valid, violations = live_risk_manager.validate_order(
            symbol="EURUSD",
            side="buy",
            quantity=50000,
            price=1.1000,
            account_balance=100000.0,
        )

        assert is_valid is True
        assert len(violations) == 0

    def test_validate_order_circuit_breaker_triggered(self, live_risk_manager):
        """Test order validation when circuit breaker is triggered."""
        # Trigger circuit breaker
        live_risk_manager.circuit_breaker_triggered = True
        live_risk_manager.circuit_breaker_trigger_time = datetime.now()

        is_valid, violations = live_risk_manager.validate_order(
            symbol="EURUSD",
            side="buy",
            quantity=50000,
            price=1.1000,
            account_balance=100000.0,
        )

        assert is_valid is False
        assert len(violations) == 1
        assert (
            violations[0].check_type == RiskCheckType.POSITION_LIMIT
        )  # Using available enum
        assert "circuit breaker" in violations[0].message.lower()

    def test_validate_order_daily_trade_limit(self, live_risk_manager):
        """Test order validation with daily trade limit exceeded."""
        live_risk_manager.daily_trade_count = 101  # Exceeds max_daily_trades (100)

        is_valid, violations = live_risk_manager.validate_order(
            symbol="EURUSD",
            side="buy",
            quantity=50000,
            price=1.1000,
            account_balance=100000.0,
        )

        assert is_valid is False
        assert len(violations) == 1
        assert "daily trade limit" in violations[0].message.lower()

    def test_validate_order_hourly_trade_limit(self, live_risk_manager):
        """Test order validation with hourly trade limit exceeded."""
        live_risk_manager.hourly_trade_count = 21  # Exceeds max_hourly_trades (20)

        is_valid, violations = live_risk_manager.validate_order(
            symbol="EURUSD",
            side="buy",
            quantity=50000,
            price=1.1000,
            account_balance=100000.0,
        )

        assert is_valid is False
        assert len(violations) == 1
        assert "hourly trade limit" in violations[0].message.lower()

    def test_validate_order_position_size_exceeded(self, live_risk_manager):
        """Test order validation with position size exceeded."""
        is_valid, violations = live_risk_manager.validate_order(
            symbol="EURUSD",
            side="buy",
            quantity=200000,  # Large position exceeding 10% limit
            price=1.1000,
            account_balance=100000.0,
        )

        assert is_valid is False
        assert len(violations) >= 1
        position_violations = [
            v for v in violations if v.check_type == RiskCheckType.POSITION_LIMIT
        ]
        assert len(position_violations) >= 1

    def test_update_position(self, live_risk_manager):
        """Test position update."""
        position = Position(
            symbol="EURUSD",
            side="buy",
            quantity=100000,
            entry_price=1.1000,
            current_price=1.1050,
            unrealized_pnl=500.0,
        )

        live_risk_manager.update_position(position)

        assert "EURUSD" in live_risk_manager.positions
        assert live_risk_manager.positions["EURUSD"] == position

    def test_calculate_risk_metrics(self, live_risk_manager):
        """Test risk metrics calculation."""
        # Add positions
        position1 = Position(
            symbol="EURUSD",
            side="buy",
            quantity=100000,
            entry_price=1.1000,
            current_price=1.1050,
            unrealized_pnl=500.0,
        )

        position2 = Position(
            symbol="GBPUSD",
            side="sell",
            quantity=-50000,
            entry_price=1.3000,
            current_price=1.2950,
            unrealized_pnl=250.0,
        )

        live_risk_manager.update_position(position1)
        live_risk_manager.update_position(position2)

        # Add P&L history
        live_risk_manager.pnl_history.extend([100.0, -50.0, 200.0, -75.0])
        live_risk_manager.current_portfolio_value = 100750.0

        metrics = live_risk_manager.calculate_risk_metrics()

        assert isinstance(metrics, RiskMetrics)
        assert metrics.total_exposure > 0
        assert metrics.unrealized_pnl == 750.0  # 500 + 250
        assert metrics.portfolio_value == 100750.0
        assert metrics.daily_pnl == 175.0  # Sum of P&L history

    def test_trigger_circuit_breaker(self, live_risk_manager):
        """Test circuit breaker triggering."""
        # Test conditions that should trigger circuit breaker
        live_risk_manager.current_portfolio_value = 100000.0
        live_risk_manager.peak_portfolio_value = 120000.0  # 16.67% drawdown > 15% limit

        triggered = live_risk_manager.trigger_circuit_breaker("High drawdown detected")

        assert triggered is True
        assert live_risk_manager.circuit_breaker_triggered is True
        assert live_risk_manager.circuit_breaker_trigger_time is not None
        assert live_risk_manager.circuit_breaker_reset_time is not None

    def test_trigger_circuit_breaker_disabled(self, risk_manager_no_circuit_breaker):
        """Test circuit breaker when disabled."""
        triggered = risk_manager_no_circuit_breaker.trigger_circuit_breaker(
            "Test reason"
        )

        assert triggered is False
        assert risk_manager_no_circuit_breaker.circuit_breaker_triggered is False

    def test_reset_circuit_breaker(self, live_risk_manager):
        """Test circuit breaker reset."""
        # First trigger the circuit breaker
        live_risk_manager.trigger_circuit_breaker("Test trigger")
        assert live_risk_manager.circuit_breaker_triggered is True

        # Reset it
        live_risk_manager.reset_circuit_breaker()

        assert live_risk_manager.circuit_breaker_triggered is False
        assert live_risk_manager.circuit_breaker_trigger_time is None
        assert live_risk_manager.circuit_breaker_reset_time is None

    def test_can_reset_circuit_breaker_time_elapsed(self, live_risk_manager):
        """Test circuit breaker auto-reset after time elapsed."""
        # Trigger circuit breaker with past time
        past_time = datetime.now() - timedelta(minutes=35)  # 35 minutes ago
        live_risk_manager.circuit_breaker_triggered = True
        live_risk_manager.circuit_breaker_trigger_time = past_time
        live_risk_manager.circuit_breaker_reset_time = past_time + timedelta(minutes=30)

        can_reset = live_risk_manager.can_reset_circuit_breaker()

        assert can_reset is True

    def test_can_reset_circuit_breaker_time_not_elapsed(self, live_risk_manager):
        """Test circuit breaker cannot reset before time elapsed."""
        # Trigger circuit breaker recently
        recent_time = datetime.now() - timedelta(minutes=10)  # 10 minutes ago
        live_risk_manager.circuit_breaker_triggered = True
        live_risk_manager.circuit_breaker_trigger_time = recent_time
        live_risk_manager.circuit_breaker_reset_time = recent_time + timedelta(
            minutes=30
        )

        can_reset = live_risk_manager.can_reset_circuit_breaker()

        assert can_reset is False

    def test_record_trade(self, live_risk_manager):
        """Test trade recording."""
        trade_data = {
            "symbol": "EURUSD",
            "side": "buy",
            "quantity": 100000,
            "price": 1.1000,
            "timestamp": datetime.now(),
        }

        live_risk_manager.record_trade(trade_data)

        assert len(live_risk_manager.order_history) == 1
        assert live_risk_manager.order_history[0] == trade_data
        assert live_risk_manager.daily_trade_count == 1
        assert live_risk_manager.hourly_trade_count == 1
        assert live_risk_manager.last_trade_time is not None

    def test_record_pnl(self, live_risk_manager):
        """Test P&L recording."""
        pnl_data = {"pnl": 500.0, "timestamp": datetime.now(), "symbol": "EURUSD"}

        live_risk_manager.record_pnl(pnl_data)

        assert len(live_risk_manager.pnl_history) == 1
        assert live_risk_manager.pnl_history[0] == pnl_data

    def test_reset_daily_counters(self, live_risk_manager):
        """Test daily counter reset."""
        # Set some trade counts
        live_risk_manager.daily_trade_count = 50
        live_risk_manager.hourly_trade_count = 10

        live_risk_manager.reset_daily_counters()

        assert live_risk_manager.daily_trade_count == 0
        # Hourly count should not reset on daily reset
        assert live_risk_manager.hourly_trade_count == 10

    def test_reset_hourly_counters(self, live_risk_manager):
        """Test hourly counter reset."""
        live_risk_manager.hourly_trade_count = 15

        live_risk_manager.reset_hourly_counters()

        assert live_risk_manager.hourly_trade_count == 0

    def test_get_violation_summary(self, live_risk_manager):
        """Test violation summary."""
        # Add some violations
        violation1 = RiskViolation(
            check_type=RiskCheckType.POSITION_LIMIT,
            result=RiskCheckResult.FAIL,
            message="Position limit exceeded",
            current_value=0.15,
            limit_value=0.10,
        )

        violation2 = RiskViolation(
            check_type=RiskCheckType.DRAWDOWN_LIMIT,
            result=RiskCheckResult.WARN,
            message="Drawdown warning",
            current_value=0.12,
            limit_value=0.15,
        )

        live_risk_manager.add_violation(violation1)
        live_risk_manager.add_violation(violation2)
        live_risk_manager.violation_counts[RiskCheckType.POSITION_LIMIT] = 3
        live_risk_manager.violation_counts[RiskCheckType.DRAWDOWN_LIMIT] = 1

        summary = live_risk_manager.get_violation_summary()

        assert "total_violations" in summary
        assert "violation_counts" in summary
        assert "recent_violations" in summary
        assert summary["total_violations"] == 2
        assert summary["violation_counts"][RiskCheckType.POSITION_LIMIT] == 3
        assert summary["violation_counts"][RiskCheckType.DRAWDOWN_LIMIT] == 1

    def test_is_trading_hours(self, live_risk_manager):
        """Test trading hours check."""
        # Mock current time to be within trading hours (10 AM)
        with patch("fxml4.risk_management.live.datetime") as mock_dt:
            mock_dt.now.return_value = datetime.now().replace(hour=10, minute=0)

            assert live_risk_manager.is_trading_hours() is True

        # Mock current time to be outside trading hours (2 AM)
        with patch("fxml4.risk_management.live.datetime") as mock_dt:
            mock_dt.now.return_value = datetime.now().replace(hour=2, minute=0)

            assert live_risk_manager.is_trading_hours() is False


@pytest.mark.unit
class TestLiveRiskManagerIntegration:
    """Integration tests for LiveRiskManager."""

    def test_complete_live_trading_workflow(self):
        """Test complete live trading workflow."""
        live_manager = LiveRiskManager()

        # 1. Check trading hours
        is_trading_time = live_manager.is_trading_hours()

        # 2. Validate order
        is_valid, violations = live_manager.validate_order(
            symbol="EURUSD",
            side="buy",
            quantity=50000,
            price=1.1000,
            account_balance=100000.0,
        )

        if is_trading_time:
            assert is_valid is True
            assert len(violations) == 0

        # 3. Record trade
        trade_data = {
            "symbol": "EURUSD",
            "side": "buy",
            "quantity": 50000,
            "price": 1.1000,
            "timestamp": datetime.now(),
        }
        live_manager.record_trade(trade_data)

        # 4. Update position
        position = Position(
            symbol="EURUSD",
            side="buy",
            quantity=50000,
            entry_price=1.1000,
            current_price=1.1050,
            unrealized_pnl=250.0,
        )
        live_manager.update_position(position)

        # 5. Record P&L
        pnl_data = {"pnl": 250.0, "timestamp": datetime.now(), "symbol": "EURUSD"}
        live_manager.record_pnl(pnl_data)

        # 6. Calculate metrics
        metrics = live_manager.calculate_risk_metrics()
        assert metrics.unrealized_pnl == 250.0

        # 7. Check for violations and circuit breaker
        violation_summary = live_manager.get_violation_summary()
        assert violation_summary["total_violations"] >= 0
        assert live_manager.circuit_breaker_triggered is False

    def test_circuit_breaker_workflow(self):
        """Test circuit breaker workflow."""
        live_manager = LiveRiskManager(circuit_breaker_enabled=True)

        # Simulate high drawdown scenario
        live_manager.peak_portfolio_value = 100000.0
        live_manager.current_portfolio_value = 80000.0  # 20% drawdown

        # This should trigger circuit breaker
        triggered = live_manager.trigger_circuit_breaker("Excessive drawdown")
        assert triggered is True
        assert live_manager.circuit_breaker_triggered is True

        # Orders should be rejected while circuit breaker is active
        is_valid, violations = live_manager.validate_order(
            symbol="EURUSD",
            side="buy",
            quantity=10000,
            price=1.1000,
            account_balance=80000.0,
        )

        assert is_valid is False
        assert any("circuit breaker" in v.message.lower() for v in violations)

        # Reset circuit breaker
        live_manager.reset_circuit_breaker()
        assert live_manager.circuit_breaker_triggered is False

        # Orders should now be allowed again
        is_valid, violations = live_manager.validate_order(
            symbol="EURUSD",
            side="buy",
            quantity=5000,
            price=1.1000,
            account_balance=80000.0,
        )

        assert is_valid is True


@pytest.mark.performance
def test_live_risk_manager_performance():
    """Test LiveRiskManager performance with many operations."""
    live_manager = LiveRiskManager()

    start_time = datetime.now()

    # Perform 1000 validations
    for i in range(1000):
        live_manager.validate_order(
            symbol=f"PAIR{i % 10}",
            side="buy" if i % 2 == 0 else "sell",
            quantity=10000,
            price=1.0000 + (i % 100) * 0.0001,
            account_balance=100000.0,
        )

    # Record 1000 trades
    for i in range(1000):
        trade_data = {
            "symbol": f"PAIR{i % 10}",
            "side": "buy" if i % 2 == 0 else "sell",
            "quantity": 10000,
            "price": 1.0000 + (i % 100) * 0.0001,
            "timestamp": datetime.now(),
        }
        live_manager.record_trade(trade_data)

    end_time = datetime.now()
    execution_time = (end_time - start_time).total_seconds()

    # Should complete in under 2 seconds
    assert execution_time < 2.0

    # Check that deque limits are respected
    assert len(live_manager.order_history) <= 1000
