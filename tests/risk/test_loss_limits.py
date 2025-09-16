"""
Test loss limit enforcement.

This module tests daily, weekly, and monthly loss limit enforcement
to prevent catastrophic losses.
"""

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import Mock, patch

import pytest

from fxml4.brokers.risk.manager import FXRiskManager
from fxml4.brokers.risk.models import (
    LossTracker,
    RiskCheckResult,
    RiskLimits,
    RiskViolationType,
)
from fxml4.fix.messages.base import ExecType, ExecutionReport, Order, Side


@pytest.fixture
def risk_limits():
    """Create test risk limits."""
    limits = RiskLimits()
    limits.max_daily_loss = 50_000  # $50K
    limits.max_weekly_loss = 150_000  # $150K
    limits.max_monthly_loss = 500_000  # $500K
    return limits


@pytest.fixture
def risk_manager(risk_limits):
    """Create risk manager instance."""
    return FXRiskManager(limits=risk_limits)


@pytest.fixture
def sample_order():
    """Create sample order for testing."""
    order = Order()
    order.order_id = "TEST123"
    order.symbol = "EUR/USD"
    order.side = Side.BUY
    order.quantity = 100_000
    order.price = 1.1000
    order.notional = order.quantity * order.price
    return order


class TestDailyLossLimits:
    """Test daily loss limit enforcement."""

    def test_no_loss_allows_trading(self, risk_manager, sample_order):
        """Test trading allowed when no losses."""
        result = risk_manager.check_loss_limits(sample_order)

        assert result.passed is True
        assert result.violations == []
        assert "daily_loss_limit" in result.checks_performed

    def test_loss_within_daily_limit(self, risk_manager, sample_order):
        """Test trading allowed when losses within limit."""
        # Add some realized losses
        risk_manager.loss_tracker.daily_loss = -30_000  # $30K loss

        result = risk_manager.check_loss_limits(sample_order)

        assert result.passed is True
        assert risk_manager.loss_tracker.get_remaining_daily_limit() == 20_000

    def test_daily_loss_limit_exceeded(self, risk_manager, sample_order):
        """Test order rejected when daily loss limit exceeded."""
        # Set loss at limit
        risk_manager.loss_tracker.daily_loss = -50_000

        result = risk_manager.check_loss_limits(sample_order)

        assert result.passed is False
        assert len(result.violations) == 1
        assert result.violations[0].type == RiskViolationType.DAILY_LOSS_LIMIT
        assert "daily loss limit" in result.violations[0].message

    def test_daily_loss_with_open_positions(self, risk_manager, sample_order):
        """Test loss calculation includes unrealized P&L."""
        # Realized loss
        risk_manager.loss_tracker.daily_loss = -20_000

        # Add position with unrealized loss
        risk_manager.positions["GBP/USD"] = Mock(
            symbol="GBP/USD",
            unrealized_pnl=-35_000,  # Would exceed limit if realized
            notional=1_000_000,
        )

        # With conservative risk check, should consider unrealized
        result = risk_manager.check_loss_limits(sample_order, include_unrealized=True)

        assert result.passed is False
        assert "including unrealized" in result.violations[0].message

    def test_daily_loss_reset(self, risk_manager):
        """Test daily loss counter reset at day boundary."""
        # Set loss for previous day
        yesterday = datetime.now(timezone.utc) - timedelta(days=1)
        risk_manager.loss_tracker.last_reset_date = yesterday.date()
        risk_manager.loss_tracker.daily_loss = -45_000

        # Check should trigger reset
        risk_manager.loss_tracker.check_and_reset_counters()

        assert risk_manager.loss_tracker.daily_loss == 0
        assert (
            risk_manager.loss_tracker.last_reset_date
            == datetime.now(timezone.utc).date()
        )

    def test_intraday_recovery_allows_trading(self, risk_manager, sample_order):
        """Test that profitable trades reduce daily loss."""
        # Morning losses
        risk_manager.loss_tracker.record_trade_pnl(-40_000)
        assert risk_manager.loss_tracker.daily_loss == -40_000

        # Afternoon recovery
        risk_manager.loss_tracker.record_trade_pnl(25_000)
        assert risk_manager.loss_tracker.daily_loss == -15_000

        # Should allow new trades
        result = risk_manager.check_loss_limits(sample_order)
        assert result.passed is True


class TestWeeklyLossLimits:
    """Test weekly loss limit enforcement."""

    def test_weekly_loss_tracking(self, risk_manager):
        """Test weekly loss accumulation."""
        # Simulate daily losses over a week
        daily_losses = [-10_000, -5_000, 15_000, -20_000, -30_000]  # Net: -50K

        for loss in daily_losses:
            risk_manager.loss_tracker.record_trade_pnl(loss)
            risk_manager.loss_tracker.update_weekly_loss(loss)

        assert risk_manager.loss_tracker.weekly_loss == -50_000
        assert risk_manager.loss_tracker.get_remaining_weekly_limit() == 100_000

    def test_weekly_loss_limit_exceeded(self, risk_manager, sample_order):
        """Test order rejected when weekly loss limit exceeded."""
        # Set weekly loss at limit
        risk_manager.loss_tracker.weekly_loss = -150_000
        risk_manager.loss_tracker.daily_loss = -30_000  # Within daily

        result = risk_manager.check_loss_limits(sample_order)

        assert result.passed is False
        assert any(
            v.type == RiskViolationType.WEEKLY_LOSS_LIMIT for v in result.violations
        )

    def test_weekly_reset_on_monday(self, risk_manager):
        """Test weekly loss counter reset on Monday."""
        # Set loss for previous week
        risk_manager.loss_tracker.weekly_loss = -120_000
        risk_manager.loss_tracker.week_start_date = datetime.now(
            timezone.utc
        ).date() - timedelta(days=7)

        # Reset should occur
        risk_manager.loss_tracker.check_and_reset_counters()

        assert risk_manager.loss_tracker.weekly_loss == 0

    def test_daily_limit_prevents_weekly_breach(self, risk_manager, sample_order):
        """Test daily limit prevents exceeding weekly limit."""
        # Near weekly limit
        risk_manager.loss_tracker.weekly_loss = -140_000
        risk_manager.loss_tracker.daily_loss = -45_000  # Near daily limit

        result = risk_manager.check_loss_limits(sample_order)

        # Should fail on daily limit first
        assert result.passed is False
        violations = [v.type for v in result.violations]
        assert RiskViolationType.DAILY_LOSS_LIMIT in violations


class TestMonthlyLossLimits:
    """Test monthly loss limit enforcement."""

    def test_monthly_loss_tracking(self, risk_manager):
        """Test monthly loss accumulation."""
        # Simulate losses over a month
        weekly_losses = [-50_000, -30_000, 20_000, -60_000]  # Net: -120K

        for loss in weekly_losses:
            risk_manager.loss_tracker.record_trade_pnl(loss)
            risk_manager.loss_tracker.update_monthly_loss(loss)

        assert risk_manager.loss_tracker.monthly_loss == -120_000
        assert risk_manager.loss_tracker.get_remaining_monthly_limit() == 380_000

    def test_monthly_loss_limit_exceeded(self, risk_manager, sample_order):
        """Test order rejected when monthly loss limit exceeded."""
        # Set monthly loss at limit
        risk_manager.loss_tracker.monthly_loss = -500_000

        result = risk_manager.check_loss_limits(sample_order)

        assert result.passed is False
        assert any(
            v.type == RiskViolationType.MONTHLY_LOSS_LIMIT for v in result.violations
        )

    def test_monthly_reset(self, risk_manager):
        """Test monthly loss counter reset on month boundary."""
        # Set loss for previous month
        last_month = datetime.now(timezone.utc).replace(day=1) - timedelta(days=1)
        risk_manager.loss_tracker.month_start_date = last_month.replace(day=1).date()
        risk_manager.loss_tracker.monthly_loss = -400_000

        # Reset should occur
        risk_manager.loss_tracker.check_and_reset_counters()

        assert risk_manager.loss_tracker.monthly_loss == 0

    def test_cascading_limit_checks(self, risk_manager, sample_order):
        """Test all loss limits checked in order."""
        # Set various loss levels
        risk_manager.loss_tracker.daily_loss = -45_000  # Near daily
        risk_manager.loss_tracker.weekly_loss = -140_000  # Near weekly
        risk_manager.loss_tracker.monthly_loss = -450_000  # Near monthly

        result = risk_manager.check_loss_limits(sample_order)

        # Should check all limits
        assert "daily_loss_limit" in result.checks_performed
        assert "weekly_loss_limit" in result.checks_performed
        assert "monthly_loss_limit" in result.checks_performed


class TestLossLimitWithExecutions:
    """Test loss limit updates with trade executions."""

    def test_realized_loss_on_execution(self, risk_manager):
        """Test loss tracking on trade execution."""
        # Open position
        risk_manager.positions["EUR/USD"] = Mock(
            symbol="EUR/USD", net_quantity=100_000, avg_price=1.1000, side=Side.BUY
        )

        # Execution closing at loss
        execution = ExecutionReport()
        execution.symbol = "EUR/USD"
        execution.side = Side.SELL
        execution.quantity = 100_000
        execution.price = 1.0950  # Loss of 50 pips
        execution.exec_type = ExecType.TRADE

        # Process execution
        pnl = risk_manager.calculate_execution_pnl(execution)
        risk_manager.loss_tracker.record_trade_pnl(pnl)

        assert pnl == -5_000  # 100K * 0.0050
        assert risk_manager.loss_tracker.daily_loss == -5_000

    def test_partial_close_loss_tracking(self, risk_manager):
        """Test loss tracking on partial position close."""
        # Open position
        risk_manager.positions["EUR/USD"] = Mock(
            symbol="EUR/USD", net_quantity=200_000, avg_price=1.1000, side=Side.BUY
        )

        # Partial close at loss
        execution = ExecutionReport()
        execution.symbol = "EUR/USD"
        execution.side = Side.SELL
        execution.quantity = 50_000  # Close 25%
        execution.price = 1.0980
        execution.exec_type = ExecType.TRADE

        pnl = risk_manager.calculate_execution_pnl(execution)
        risk_manager.loss_tracker.record_trade_pnl(pnl)

        assert pnl == -1_000  # 50K * 0.0020
        assert risk_manager.loss_tracker.daily_loss == -1_000

    def test_loss_limit_with_multiple_positions(self, risk_manager, sample_order):
        """Test loss limits with portfolio of positions."""
        # Multiple positions with mixed P&L
        risk_manager.positions = {
            "EUR/USD": Mock(symbol="EUR/USD", unrealized_pnl=-15_000),
            "GBP/USD": Mock(symbol="GBP/USD", unrealized_pnl=8_000),
            "USD/JPY": Mock(symbol="USD/JPY", unrealized_pnl=-12_000),
        }

        # Realized losses
        risk_manager.loss_tracker.daily_loss = -25_000

        # Check with unrealized P&L
        result = risk_manager.check_loss_limits(sample_order, include_unrealized=True)

        # Total: -25K realized + (-15K + 8K - 12K) unrealized = -44K
        assert result.passed is True  # Still within 50K limit

        # Add more unrealized loss
        risk_manager.positions["AUD/USD"] = Mock(
            symbol="AUD/USD", unrealized_pnl=-10_000
        )

        result = risk_manager.check_loss_limits(sample_order, include_unrealized=True)
        assert result.passed is False  # Now exceeds 50K limit


class TestLossLimitEdgeCases:
    """Test edge cases in loss limit enforcement."""

    def test_zero_loss_limits(self, risk_manager):
        """Test behavior with zero loss limits (no losses allowed)."""
        risk_manager.limits.max_daily_loss = 0

        # Any loss should trigger limit
        risk_manager.loss_tracker.daily_loss = -1

        order = Mock(order_id="TEST")
        result = risk_manager.check_loss_limits(order)

        assert result.passed is False

    def test_profitable_day_no_restrictions(self, risk_manager, sample_order):
        """Test no restrictions on profitable days."""
        # Profitable day
        risk_manager.loss_tracker.daily_loss = 25_000  # Positive = profit

        result = risk_manager.check_loss_limits(sample_order)

        assert result.passed is True
        assert result.violations == []

    @pytest.mark.parametrize(
        "loss,limit,expected",
        [
            (-49_999, 50_000, True),  # Just under limit
            (-50_000, 50_000, False),  # At limit
            (-50_001, 50_000, False),  # Just over limit
        ],
    )
    def test_loss_limit_boundaries(
        self, risk_manager, sample_order, loss, limit, expected
    ):
        """Test loss limit boundary conditions."""
        risk_manager.limits.max_daily_loss = limit
        risk_manager.loss_tracker.daily_loss = loss

        result = risk_manager.check_loss_limits(sample_order)

        assert result.passed is expected

    def test_loss_limit_with_fees_and_slippage(self, risk_manager):
        """Test loss calculation including fees and slippage."""
        # Position with loss
        execution = Mock(
            symbol="EUR/USD",
            side=Side.SELL,
            quantity=100_000,
            price=1.0950,
            commission=50,  # $50 commission
            slippage=25,  # $25 slippage
        )

        # Base P&L: -5000
        # Total with costs: -5075
        pnl = risk_manager.calculate_execution_pnl(execution, include_costs=True)

        assert pnl == -5_075

        risk_manager.loss_tracker.record_trade_pnl(pnl)
        assert risk_manager.loss_tracker.daily_loss == -5_075
