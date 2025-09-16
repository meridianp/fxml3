"""
Test position and portfolio limit enforcement.

This module tests that position limits are properly enforced to prevent
excessive risk exposure.
"""

import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock, Mock, patch

import pytest

from fxml4.brokers.risk.manager import FXRiskManager
from fxml4.brokers.risk.models import (
    PortfolioRiskMetrics,
    PositionRiskMetrics,
    RiskCheckResult,
    RiskLimits,
    RiskViolationType,
)
from fxml4.fix.messages.base import Order, Side


@pytest.fixture
def risk_limits():
    """Create test risk limits."""
    limits = RiskLimits()
    limits.max_portfolio_notional = 10_000_000  # $10M
    limits.max_single_position_notional = 1_000_000  # $1M
    limits.max_position_size = {
        "EUR/USD": 5_000_000,
        "GBP/USD": 3_000_000,
        "USD/JPY": 5_000_000,
        "DEFAULT": 1_000_000,
    }
    return limits


@pytest.fixture
def risk_manager(risk_limits):
    """Create risk manager instance."""
    manager = FXRiskManager(limits=risk_limits)
    return manager


@pytest.fixture
def sample_order():
    """Create sample order for testing."""
    order = Order()
    order.symbol = "EUR/USD"
    order.side = Side.BUY
    order.quantity = 100_000  # 100K units
    order.price = 1.1000
    order.notional = order.quantity * order.price
    return order


class TestPositionLimits:
    """Test position limit enforcement."""

    def test_single_position_within_limits(self, risk_manager, sample_order):
        """Test order within position limits."""
        # Order notional: 100K * 1.1 = $110K (within $1M limit)
        result = risk_manager.check_position_limits(sample_order)

        assert result.passed is True
        assert result.violations == []
        assert result.checks_performed == ["position_limit"]

    def test_single_position_exceeds_limit(self, risk_manager, sample_order):
        """Test order exceeding position limit."""
        # Set quantity to exceed limit
        sample_order.quantity = 1_000_000  # 1M units
        sample_order.notional = sample_order.quantity * sample_order.price  # $1.1M

        result = risk_manager.check_position_limits(sample_order)

        assert result.passed is False
        assert len(result.violations) == 1
        assert result.violations[0].type == RiskViolationType.POSITION_LIMIT
        assert "exceeds maximum single position" in result.violations[0].message

    def test_position_size_by_symbol(self, risk_manager):
        """Test symbol-specific position size limits."""
        # EUR/USD limit: 5M units
        order = Order()
        order.symbol = "EUR/USD"
        order.side = Side.BUY
        order.quantity = 4_000_000  # Within EUR/USD limit
        order.price = 1.1000
        order.notional = order.quantity * order.price

        result = risk_manager.check_position_limits(order)
        assert result.passed is True

        # Exceed EUR/USD limit
        order.quantity = 6_000_000
        order.notional = order.quantity * order.price

        result = risk_manager.check_position_limits(order)
        assert result.passed is False
        assert result.violations[0].type == RiskViolationType.POSITION_LIMIT

    def test_default_position_size_limit(self, risk_manager):
        """Test default position size for unknown symbols."""
        order = Order()
        order.symbol = "AUD/NZD"  # Not in specific limits
        order.side = Side.SELL
        order.quantity = 1_500_000  # Exceeds default 1M
        order.price = 1.0500
        order.notional = order.quantity * order.price

        result = risk_manager.check_position_limits(order)

        assert result.passed is False
        assert "exceeds maximum order size" in result.violations[0].message

    def test_position_aggregation_with_existing(self, risk_manager):
        """Test position limit check with existing positions."""
        # Add existing position
        risk_manager.positions["EUR/USD"] = Mock(
            symbol="EUR/USD",
            net_quantity=500_000,
            avg_price=1.0900,
            notional=545_000,  # 500K * 1.09
        )

        # New order that would exceed limit when combined
        order = Order()
        order.symbol = "EUR/USD"
        order.side = Side.BUY
        order.quantity = 600_000
        order.price = 1.1000
        order.notional = order.quantity * order.price

        # Combined notional: 545K + 660K = $1.205M (exceeds $1M limit)
        result = risk_manager.check_position_limits(order)

        assert result.passed is False
        assert result.violations[0].type == RiskViolationType.POSITION_LIMIT
        assert "combined position" in result.violations[0].message.lower()


class TestPortfolioLimits:
    """Test portfolio-wide limit enforcement."""

    def test_portfolio_within_limits(self, risk_manager):
        """Test portfolio within total notional limit."""
        # Add some positions
        risk_manager.positions = {
            "EUR/USD": Mock(symbol="EUR/USD", notional=2_000_000),
            "GBP/USD": Mock(symbol="GBP/USD", notional=1_500_000),
            "USD/JPY": Mock(symbol="USD/JPY", notional=1_000_000),
        }
        # Total: $4.5M (within $10M limit)

        # New order
        order = Order()
        order.symbol = "AUD/USD"
        order.side = Side.BUY
        order.quantity = 1_000_000
        order.price = 0.7500
        order.notional = 750_000

        result = risk_manager.check_portfolio_limits(order)

        assert result.passed is True
        assert result.checks_performed == ["portfolio_limit"]

    def test_portfolio_exceeds_limit(self, risk_manager):
        """Test order that would exceed portfolio limit."""
        # Add positions close to limit
        risk_manager.positions = {
            "EUR/USD": Mock(symbol="EUR/USD", notional=4_000_000),
            "GBP/USD": Mock(symbol="GBP/USD", notional=3_000_000),
            "USD/JPY": Mock(symbol="USD/JPY", notional=2_500_000),
        }
        # Total: $9.5M

        # New order that would exceed limit
        order = Order()
        order.symbol = "AUD/USD"
        order.side = Side.BUY
        order.quantity = 1_000_000
        order.price = 0.7500
        order.notional = 750_000  # Would make total $10.25M

        result = risk_manager.check_portfolio_limits(order)

        assert result.passed is False
        assert len(result.violations) == 1
        assert result.violations[0].type == RiskViolationType.PORTFOLIO_LIMIT
        assert "exceeds maximum portfolio" in result.violations[0].message

    def test_portfolio_metrics_calculation(self, risk_manager):
        """Test portfolio risk metrics calculation."""
        # Setup positions
        risk_manager.positions = {
            "EUR/USD": Mock(
                symbol="EUR/USD",
                notional=2_000_000,
                unrealized_pnl=-50_000,
                net_quantity=1_800_000,
            ),
            "GBP/USD": Mock(
                symbol="GBP/USD",
                notional=1_500_000,
                unrealized_pnl=30_000,
                net_quantity=-1_200_000,  # Short
            ),
        }

        metrics = risk_manager.get_portfolio_metrics()

        assert metrics.total_notional == 3_500_000
        assert metrics.position_count == 2
        assert metrics.unrealized_pnl == -20_000
        assert metrics.long_exposure == 2_000_000
        assert metrics.short_exposure == 1_500_000

    @pytest.mark.parametrize(
        "position_count,expected_concentration",
        [
            (1, 100.0),  # Single position = 100% concentration
            (2, 50.0),  # Two equal positions = 50% each
            (4, 25.0),  # Four equal positions = 25% each
        ],
    )
    def test_concentration_risk(
        self, risk_manager, position_count, expected_concentration
    ):
        """Test position concentration calculations."""
        # Create equal-sized positions
        notional_per_position = 1_000_000

        for i in range(position_count):
            symbol = f"PAIR{i}"
            risk_manager.positions[symbol] = Mock(
                symbol=symbol, notional=notional_per_position, unrealized_pnl=0
            )

        metrics = risk_manager.get_portfolio_metrics()

        # Check concentration
        assert metrics.position_count == position_count
        assert metrics.largest_position_pct == pytest.approx(
            expected_concentration, rel=0.01
        )


class TestPositionLimitStressScenarios:
    """Test position limits under stress scenarios."""

    @pytest.mark.asyncio
    async def test_concurrent_orders_same_symbol(self, risk_manager):
        """Test multiple concurrent orders for same symbol."""
        # Create multiple orders that individually pass but collectively exceed limits
        orders = []
        for i in range(5):
            order = Order()
            order.symbol = "EUR/USD"
            order.side = Side.BUY
            order.quantity = 300_000  # Each within limit
            order.price = 1.1000
            order.notional = order.quantity * order.price
            orders.append(order)

        # Process orders concurrently
        async def check_order(order):
            # Simulate processing delay
            await asyncio.sleep(0.01)
            return risk_manager.check_position_limits(order)

        # In real implementation, this would need proper locking
        results = await asyncio.gather(*[check_order(order) for order in orders])

        # At least some should fail due to aggregate limit
        failed_count = sum(1 for r in results if not r.passed)
        assert failed_count > 0

    def test_position_flip_scenario(self, risk_manager):
        """Test flipping from long to short position."""
        # Existing long position
        risk_manager.positions["EUR/USD"] = Mock(
            symbol="EUR/USD",
            net_quantity=500_000,  # Long
            avg_price=1.1000,
            notional=550_000,
            side=Side.BUY,
        )

        # Order to go short (flip position)
        order = Order()
        order.symbol = "EUR/USD"
        order.side = Side.SELL
        order.quantity = 1_200_000  # Would result in 700K short
        order.price = 1.1050
        order.notional = order.quantity * order.price

        result = risk_manager.check_position_limits(order)

        # Should check resulting position size
        assert result.passed is True  # 700K short is within 1M limit

    def test_market_gap_scenario(self, risk_manager):
        """Test position limits during market gaps."""
        # Existing position with old price
        risk_manager.positions["EUR/USD"] = Mock(
            symbol="EUR/USD",
            net_quantity=800_000,
            avg_price=1.0900,
            notional=872_000,
            last_price=1.0900,
        )

        # Market gaps up significantly
        order = Order()
        order.symbol = "EUR/USD"
        order.side = Side.BUY
        order.quantity = 100_000
        order.price = 1.1500  # 5.5% gap
        order.notional = order.quantity * order.price

        # Update position valuation at new price
        risk_manager.positions["EUR/USD"].notional = 800_000 * 1.1500  # $920K

        result = risk_manager.check_position_limits(order)

        # Combined would be $1.035M (exceeds $1M limit)
        assert result.passed is False
        assert "market movement" in result.violations[0].message.lower()


class TestPositionLimitConfiguration:
    """Test position limit configuration and updates."""

    def test_dynamic_limit_adjustment(self, risk_manager):
        """Test adjusting limits during trading."""
        # Initial check passes
        order = Order()
        order.symbol = "EUR/USD"
        order.side = Side.BUY
        order.quantity = 900_000
        order.price = 1.1000
        order.notional = 990_000

        result = risk_manager.check_position_limits(order)
        assert result.passed is True

        # Reduce limit
        risk_manager.limits.max_single_position_notional = 500_000

        # Same order now fails
        result = risk_manager.check_position_limits(order)
        assert result.passed is False

    def test_symbol_specific_overrides(self, risk_manager):
        """Test symbol-specific limit overrides."""
        # Add temporary override for specific symbol
        risk_manager.limits.max_position_size["TEST/USD"] = 10_000_000

        order = Order()
        order.symbol = "TEST/USD"
        order.side = Side.BUY
        order.quantity = 8_000_000
        order.price = 1.0000
        order.notional = 8_000_000

        result = risk_manager.check_position_limits(order)

        # Should use symbol-specific limit
        assert result.passed is True

        # Remove override
        del risk_manager.limits.max_position_size["TEST/USD"]

        # Now should use default
        result = risk_manager.check_position_limits(order)
        assert result.passed is False  # Exceeds default 1M
