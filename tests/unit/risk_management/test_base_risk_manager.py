"""Tests for unified risk management base system."""

from datetime import datetime, timedelta
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from fxml4.risk_management.base import (
    BaseRiskManager,
    Position,
    RiskCheckResult,
    RiskCheckType,
    RiskLimits,
    RiskMetrics,
    RiskViolation,
)


class TestRiskLimits:
    """Test RiskLimits configuration."""

    def test_default_limits(self):
        """Test default risk limits."""
        limits = RiskLimits()

        assert limits.max_position_size == 0.1  # 10%
        assert limits.max_portfolio_risk == 0.06  # 6%
        assert limits.max_correlation == 0.7
        assert limits.max_leverage == 1.0
        assert limits.max_daily_loss == 0.03  # 3%
        assert limits.max_drawdown == 0.15  # 15%
        assert limits.max_order_size == 0.05  # 5%
        assert limits.min_risk_reward == 1.5
        assert limits.use_trailing_stop is True
        assert limits.position_sizing_method == "fixed_risk"

    def test_custom_limits(self):
        """Test custom risk limits."""
        limits = RiskLimits(
            max_position_size=0.05, max_daily_loss=0.02, use_trailing_stop=False
        )

        assert limits.max_position_size == 0.05
        assert limits.max_daily_loss == 0.02
        assert limits.use_trailing_stop is False


class TestPosition:
    """Test Position data class."""

    def test_position_creation(self):
        """Test position creation."""
        position = Position(
            symbol="EURUSD",
            side="buy",
            quantity=100000,
            entry_price=1.1000,
            current_price=1.1050,
            unrealized_pnl=500.0,
        )

        assert position.symbol == "EURUSD"
        assert position.side == "buy"
        assert position.quantity == 100000
        assert position.entry_price == 1.1000
        assert position.current_price == 1.1050
        assert position.unrealized_pnl == 500.0
        assert position.realized_pnl == 0.0
        assert isinstance(position.entry_time, datetime)

    def test_position_notional_value(self):
        """Test position notional value calculation."""
        position = Position(
            symbol="EURUSD",
            side="buy",
            quantity=100000,
            entry_price=1.1000,
            current_price=1.1050,
            unrealized_pnl=500.0,
        )

        assert position.notional_value == 110500.0  # 100000 * 1.1050

    def test_position_market_value(self):
        """Test position market value calculation."""
        position = Position(
            symbol="EURUSD",
            side="sell",  # Short position
            quantity=-100000,
            entry_price=1.1100,
            current_price=1.1050,
            unrealized_pnl=500.0,
        )

        assert position.market_value == -110500.0  # -100000 * 1.1050


class TestRiskViolation:
    """Test RiskViolation data class."""

    def test_violation_creation(self):
        """Test risk violation creation."""
        violation = RiskViolation(
            check_type=RiskCheckType.POSITION_LIMIT,
            result=RiskCheckResult.FAIL,
            message="Position size exceeds limit",
            current_value=0.15,
            limit_value=0.10,
            severity="high",
        )

        assert violation.check_type == RiskCheckType.POSITION_LIMIT
        assert violation.result == RiskCheckResult.FAIL
        assert violation.message == "Position size exceeds limit"
        assert violation.current_value == 0.15
        assert violation.limit_value == 0.10
        assert violation.severity == "high"
        assert isinstance(violation.timestamp, datetime)


class MockRiskManager(BaseRiskManager):
    """Mock implementation of BaseRiskManager for testing."""

    def validate_order(
        self, symbol, side, quantity, price, account_balance, current_positions=None
    ):
        """Mock validate_order implementation."""
        violations = []

        # Simple position size check
        position_value = quantity * price
        max_position = self.get_position_size_limit(symbol, account_balance)

        if position_value > max_position:
            violations.append(
                RiskViolation(
                    check_type=RiskCheckType.POSITION_LIMIT,
                    result=RiskCheckResult.FAIL,
                    message=f"Position size {position_value} exceeds limit {max_position}",
                    current_value=position_value,
                    limit_value=max_position,
                )
            )

        return len(violations) == 0, violations

    def update_position(self, position):
        """Mock update_position implementation."""
        self.positions[position.symbol] = position

    def calculate_risk_metrics(self):
        """Mock calculate_risk_metrics implementation."""
        total_exposure = sum(pos.notional_value for pos in self.positions.values())
        unrealized_pnl = sum(pos.unrealized_pnl for pos in self.positions.values())

        return RiskMetrics(
            total_exposure=total_exposure,
            unrealized_pnl=unrealized_pnl,
            portfolio_value=self.current_portfolio_value,
        )


class TestBaseRiskManager:
    """Test BaseRiskManager abstract base class."""

    @pytest.fixture
    def risk_manager(self):
        """Create a test risk manager."""
        return MockRiskManager()

    @pytest.fixture
    def custom_risk_manager(self):
        """Create a risk manager with custom limits."""
        limits = RiskLimits(max_position_size=0.05, max_drawdown=0.10)  # 5%  # 10%
        return MockRiskManager(limits)

    def test_initialization(self, risk_manager):
        """Test risk manager initialization."""
        assert isinstance(risk_manager.limits, RiskLimits)
        assert risk_manager.positions == {}
        assert risk_manager.daily_pnl == []
        assert risk_manager.peak_portfolio_value == 0.0
        assert risk_manager.current_portfolio_value == 0.0
        assert risk_manager.violations == []

    def test_custom_limits_initialization(self, custom_risk_manager):
        """Test initialization with custom limits."""
        assert custom_risk_manager.limits.max_position_size == 0.05
        assert custom_risk_manager.limits.max_drawdown == 0.10

    def test_get_position_size_limit(self, risk_manager):
        """Test position size limit calculation."""
        account_balance = 100000.0
        limit = risk_manager.get_position_size_limit("EURUSD", account_balance)

        expected_limit = account_balance * risk_manager.limits.max_position_size
        assert limit == expected_limit  # 10000.0

    def test_validate_order_success(self, risk_manager):
        """Test successful order validation."""
        is_valid, violations = risk_manager.validate_order(
            symbol="EURUSD",
            side="buy",
            quantity=50000,  # Small position
            price=1.1000,
            account_balance=100000.0,
        )

        assert is_valid is True
        assert len(violations) == 0

    def test_validate_order_position_limit_exceeded(self, risk_manager):
        """Test order validation with position limit exceeded."""
        is_valid, violations = risk_manager.validate_order(
            symbol="EURUSD",
            side="buy",
            quantity=200000,  # Large position (220k > 10k limit)
            price=1.1000,
            account_balance=100000.0,
        )

        assert is_valid is False
        assert len(violations) == 1
        assert violations[0].check_type == RiskCheckType.POSITION_LIMIT
        assert violations[0].result == RiskCheckResult.FAIL

    def test_update_position(self, risk_manager):
        """Test position update."""
        position = Position(
            symbol="EURUSD",
            side="buy",
            quantity=100000,
            entry_price=1.1000,
            current_price=1.1050,
            unrealized_pnl=500.0,
        )

        risk_manager.update_position(position)

        assert "EURUSD" in risk_manager.positions
        assert risk_manager.positions["EURUSD"] == position

    def test_calculate_risk_metrics(self, risk_manager):
        """Test risk metrics calculation."""
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

        risk_manager.update_position(position1)
        risk_manager.update_position(position2)
        risk_manager.current_portfolio_value = 100000.0

        metrics = risk_manager.calculate_risk_metrics()

        assert metrics.total_exposure == 110500.0 + 64750.0  # Sum of notional values
        assert metrics.unrealized_pnl == 750.0  # 500 + 250
        assert metrics.portfolio_value == 100000.0

    def test_check_drawdown_limit_no_violation(self, risk_manager):
        """Test drawdown check with no violation."""
        risk_manager.peak_portfolio_value = 100000.0
        current_value = 95000.0  # 5% drawdown, within 15% limit

        violation = risk_manager.check_drawdown_limit(current_value)

        assert violation is None
        assert risk_manager.current_portfolio_value == current_value

    def test_check_drawdown_limit_violation(self, risk_manager):
        """Test drawdown check with violation."""
        risk_manager.peak_portfolio_value = 100000.0
        current_value = 80000.0  # 20% drawdown, exceeds 15% limit

        violation = risk_manager.check_drawdown_limit(current_value)

        assert violation is not None
        assert violation.check_type == RiskCheckType.DRAWDOWN_LIMIT
        assert violation.result == RiskCheckResult.FAIL
        assert violation.severity == "high"
        assert "20.00%" in violation.message

    def test_check_drawdown_limit_new_peak(self, risk_manager):
        """Test drawdown check when setting new peak."""
        risk_manager.peak_portfolio_value = 100000.0
        current_value = 110000.0  # New peak

        violation = risk_manager.check_drawdown_limit(current_value)

        assert violation is None
        assert risk_manager.peak_portfolio_value == 110000.0

    def test_check_correlation_limit_no_violation(self, risk_manager):
        """Test correlation check with no violation."""
        violation = risk_manager.check_correlation_limit("EURUSD", "buy")

        assert violation is None

    def test_check_correlation_limit_warning(self, risk_manager):
        """Test correlation check with warning."""
        # Add multiple EUR positions
        positions = [
            Position("EURUSD", "buy", 100000, 1.1000, 1.1050, 500),
            Position("EURJPY", "buy", 100000, 130.00, 131.00, 1000),
            Position("EURGBP", "sell", -100000, 0.8500, 0.8480, 200),
        ]

        for pos in positions:
            risk_manager.update_position(pos)

        violation = risk_manager.check_correlation_limit("EURCHF", "buy")

        assert violation is not None
        assert violation.check_type == RiskCheckType.CORRELATION_LIMIT
        assert violation.result == RiskCheckResult.WARN
        assert violation.severity == "medium"

    def test_add_violation(self, risk_manager):
        """Test adding violations."""
        violation1 = RiskViolation(
            check_type=RiskCheckType.POSITION_LIMIT,
            result=RiskCheckResult.FAIL,
            message="Test violation 1",
            current_value=0.15,
            limit_value=0.10,
        )

        violation2 = RiskViolation(
            check_type=RiskCheckType.DAILY_LOSS_LIMIT,
            result=RiskCheckResult.WARN,
            message="Test violation 2",
            current_value=0.04,
            limit_value=0.03,
        )

        risk_manager.add_violation(violation1)
        risk_manager.add_violation(violation2)

        assert len(risk_manager.violations) == 2
        assert risk_manager.violations[0] == violation1
        assert risk_manager.violations[1] == violation2

    def test_violation_limit(self, risk_manager):
        """Test that violations are limited to prevent memory issues."""
        # Add 1200 violations
        for i in range(1200):
            violation = RiskViolation(
                check_type=RiskCheckType.POSITION_LIMIT,
                result=RiskCheckResult.FAIL,
                message=f"Violation {i}",
                current_value=i,
                limit_value=100,
            )
            risk_manager.add_violation(violation)

        # Should keep only the last 1000
        assert len(risk_manager.violations) == 1000
        assert (
            risk_manager.violations[0].message == "Violation 200"
        )  # First kept violation
        assert risk_manager.violations[-1].message == "Violation 1199"  # Last violation


@pytest.mark.unit
class TestRiskManagerIntegration:
    """Integration tests for risk manager components."""

    def test_complete_risk_workflow(self):
        """Test complete risk management workflow."""
        risk_manager = MockRiskManager()

        # 1. Validate order
        is_valid, violations = risk_manager.validate_order(
            symbol="EURUSD",
            side="buy",
            quantity=50000,
            price=1.1000,
            account_balance=100000.0,
        )

        assert is_valid is True

        # 2. Create and update position
        position = Position(
            symbol="EURUSD",
            side="buy",
            quantity=50000,
            entry_price=1.1000,
            current_price=1.1050,
            unrealized_pnl=250.0,
        )

        risk_manager.update_position(position)

        # 3. Check risk metrics
        risk_manager.current_portfolio_value = 100250.0
        metrics = risk_manager.calculate_risk_metrics()

        assert metrics.total_exposure == 55250.0  # 50000 * 1.1050
        assert metrics.unrealized_pnl == 250.0
        assert metrics.portfolio_value == 100250.0

        # 4. Check drawdown (none expected)
        violation = risk_manager.check_drawdown_limit(100250.0)
        assert violation is None
        assert risk_manager.peak_portfolio_value == 100250.0

        # 5. Simulate loss and check drawdown
        violation = risk_manager.check_drawdown_limit(85000.0)  # 15.2% drawdown
        assert violation is not None
        assert violation.check_type == RiskCheckType.DRAWDOWN_LIMIT

        # 6. Verify violation is logged
        risk_manager.add_violation(violation)
        assert len(risk_manager.violations) == 1


@pytest.mark.performance
def test_risk_manager_performance():
    """Test risk manager performance with many positions."""
    risk_manager = MockRiskManager()

    # Add 1000 positions
    start_time = datetime.utcnow()

    for i in range(1000):
        position = Position(
            symbol=f"PAIR{i:03d}",
            side="buy" if i % 2 == 0 else "sell",
            quantity=10000,
            entry_price=1.0000 + (i * 0.0001),
            current_price=1.0000 + (i * 0.0001) + 0.0010,
            unrealized_pnl=10.0,
        )
        risk_manager.update_position(position)

    # Calculate metrics
    metrics = risk_manager.calculate_risk_metrics()

    end_time = datetime.utcnow()
    execution_time = (end_time - start_time).total_seconds()

    # Should complete in under 1 second
    assert execution_time < 1.0
    assert len(risk_manager.positions) == 1000
    assert metrics.unrealized_pnl == 10000.0  # 1000 * 10.0
