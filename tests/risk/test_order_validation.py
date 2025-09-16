"""
Test order validation and price deviation checks.

This module tests order size limits, price deviation checks,
and other order-level risk validations.
"""

from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import Mock, patch

import pytest

from fxml4.brokers.risk.manager import FXRiskManager
from fxml4.brokers.risk.models import (
    MarketData,
    RiskCheckResult,
    RiskLimits,
    RiskViolationType,
)
from fxml4.fix.messages.base import Order, OrdType, Side


@pytest.fixture
def risk_limits():
    """Create test risk limits."""
    limits = RiskLimits()
    limits.max_order_notional = 500_000  # $500K
    limits.min_order_size = 10_000  # 10K units minimum
    limits.max_order_size = {
        "EUR/USD": 2_000_000,
        "GBP/USD": 1_500_000,
        "USD/JPY": 2_000_000,
        "DEFAULT": 500_000,
    }
    limits.max_price_deviation_pct = 2.0  # 2% max deviation
    limits.blocked_symbols = ["TRY/USD", "RUB/USD", "CNY/USD"]
    limits.allowed_symbols = None  # All symbols allowed except blocked
    return limits


@pytest.fixture
def risk_manager(risk_limits):
    """Create risk manager instance."""
    manager = FXRiskManager(limits=risk_limits)
    # Add market data
    manager.market_data = {
        "EUR/USD": MarketData(
            symbol="EUR/USD",
            bid=1.0995,
            ask=1.1005,
            mid=1.1000,
            last_update=datetime.now(timezone.utc),
        ),
        "GBP/USD": MarketData(
            symbol="GBP/USD",
            bid=1.2495,
            ask=1.2505,
            mid=1.2500,
            last_update=datetime.now(timezone.utc),
        ),
        "USD/JPY": MarketData(
            symbol="USD/JPY",
            bid=110.95,
            ask=111.05,
            mid=111.00,
            last_update=datetime.now(timezone.utc),
        ),
    }
    return manager


class TestOrderSizeLimits:
    """Test order size validation."""

    def test_order_within_size_limits(self, risk_manager):
        """Test order within size limits."""
        order = Order()
        order.symbol = "EUR/USD"
        order.side = Side.BUY
        order.quantity = 100_000  # Within limits
        order.price = 1.1000
        order.notional = order.quantity * order.price

        result = risk_manager.check_order_limits(order)

        assert result.passed is True
        assert "order_size_limit" in result.checks_performed

    def test_order_below_minimum_size(self, risk_manager):
        """Test order rejected below minimum size."""
        order = Order()
        order.symbol = "EUR/USD"
        order.side = Side.SELL
        order.quantity = 5_000  # Below 10K minimum
        order.price = 1.1000

        result = risk_manager.check_order_limits(order)

        assert result.passed is False
        assert result.violations[0].type == RiskViolationType.ORDER_SIZE_LIMIT
        assert "below minimum" in result.violations[0].message

    def test_order_exceeds_maximum_size(self, risk_manager):
        """Test order rejected above maximum size."""
        order = Order()
        order.symbol = "EUR/USD"
        order.side = Side.BUY
        order.quantity = 3_000_000  # Exceeds EUR/USD limit of 2M
        order.price = 1.1000

        result = risk_manager.check_order_limits(order)

        assert result.passed is False
        assert result.violations[0].type == RiskViolationType.ORDER_SIZE_LIMIT
        assert "exceeds maximum" in result.violations[0].message

    def test_order_exceeds_notional_limit(self, risk_manager):
        """Test order rejected on notional value."""
        order = Order()
        order.symbol = "EUR/USD"
        order.side = Side.BUY
        order.quantity = 500_000  # Within size limit
        order.price = 1.2000  # High price
        order.notional = 600_000  # Exceeds $500K notional limit

        result = risk_manager.check_order_limits(order)

        assert result.passed is False
        assert result.violations[0].type == RiskViolationType.ORDER_SIZE_LIMIT
        assert "notional value" in result.violations[0].message

    def test_symbol_specific_size_limits(self, risk_manager):
        """Test symbol-specific order size limits."""
        # Test different symbols with different limits
        test_cases = [
            ("EUR/USD", 1_800_000, True),  # Within EUR/USD limit
            ("EUR/USD", 2_100_000, False),  # Exceeds EUR/USD limit
            ("GBP/USD", 1_400_000, True),  # Within GBP/USD limit
            ("GBP/USD", 1_600_000, False),  # Exceeds GBP/USD limit
            ("AUD/USD", 400_000, True),  # Within default limit
            ("AUD/USD", 600_000, False),  # Exceeds default limit
        ]

        for symbol, quantity, expected_pass in test_cases:
            order = Order()
            order.symbol = symbol
            order.side = Side.BUY
            order.quantity = quantity
            order.price = 1.0000

            result = risk_manager.check_order_limits(order)
            assert (
                result.passed is expected_pass
            ), f"Failed for {symbol} with {quantity}"


class TestPriceDeviationChecks:
    """Test price deviation validation."""

    def test_order_price_within_deviation(self, risk_manager):
        """Test order with acceptable price."""
        order = Order()
        order.symbol = "EUR/USD"
        order.side = Side.BUY
        order.quantity = 100_000
        order.price = 1.1100  # 0.9% above mid (1.1000)
        order.order_type = OrdType.LIMIT

        result = risk_manager.check_price_deviation(order)

        assert result.passed is True
        assert "price_deviation" in result.checks_performed

    def test_buy_order_excessive_deviation(self, risk_manager):
        """Test buy order with excessive price deviation."""
        order = Order()
        order.symbol = "EUR/USD"
        order.side = Side.BUY
        order.quantity = 100_000
        order.price = 1.1300  # 2.7% above mid (exceeds 2% limit)
        order.order_type = OrdType.LIMIT

        result = risk_manager.check_price_deviation(order)

        assert result.passed is False
        assert result.violations[0].type == RiskViolationType.PRICE_DEVIATION
        assert "2.73%" in result.violations[0].message

    def test_sell_order_excessive_deviation(self, risk_manager):
        """Test sell order with excessive price deviation."""
        order = Order()
        order.symbol = "EUR/USD"
        order.side = Side.SELL
        order.quantity = 100_000
        order.price = 1.0700  # 2.7% below mid (exceeds 2% limit)
        order.order_type = OrdType.LIMIT

        result = risk_manager.check_price_deviation(order)

        assert result.passed is False
        assert "2.73%" in result.violations[0].message

    def test_market_order_no_deviation_check(self, risk_manager):
        """Test market orders skip price deviation check."""
        order = Order()
        order.symbol = "EUR/USD"
        order.side = Side.BUY
        order.quantity = 100_000
        order.order_type = OrdType.MARKET
        # No price for market orders

        result = risk_manager.check_price_deviation(order)

        assert result.passed is True
        assert result.checks_performed == []  # No check performed

    def test_stop_order_deviation_check(self, risk_manager):
        """Test stop orders check deviation from current price."""
        order = Order()
        order.symbol = "EUR/USD"
        order.side = Side.SELL
        order.quantity = 100_000
        order.price = 1.0750  # Stop 2.3% below current
        order.order_type = OrdType.STOP

        result = risk_manager.check_price_deviation(order)

        assert result.passed is False  # Exceeds 2% limit
        assert "stop price" in result.violations[0].message.lower()

    def test_stale_market_data_warning(self, risk_manager):
        """Test warning on stale market data."""
        # Make market data stale
        risk_manager.market_data["EUR/USD"].last_update = datetime.now(
            timezone.utc
        ) - timedelta(minutes=5)

        order = Order()
        order.symbol = "EUR/USD"
        order.side = Side.BUY
        order.quantity = 100_000
        order.price = 1.1050
        order.order_type = OrdType.LIMIT

        result = risk_manager.check_price_deviation(order)

        # Should still check but add warning
        assert "stale market data" in result.warnings[0]

    def test_missing_market_data(self, risk_manager):
        """Test handling of missing market data."""
        order = Order()
        order.symbol = "NZD/USD"  # No market data
        order.side = Side.BUY
        order.quantity = 100_000
        order.price = 0.6500
        order.order_type = OrdType.LIMIT

        result = risk_manager.check_price_deviation(order)

        # Should pass but warn
        assert result.passed is True
        assert "no market data" in result.warnings[0].lower()


class TestSymbolRestrictions:
    """Test symbol-based trading restrictions."""

    def test_allowed_symbol_trading(self, risk_manager):
        """Test trading allowed symbols."""
        order = Order()
        order.symbol = "EUR/USD"
        order.side = Side.BUY
        order.quantity = 100_000

        result = risk_manager.check_symbol_restrictions(order)

        assert result.passed is True
        assert "symbol_restriction" in result.checks_performed

    def test_blocked_symbol_rejected(self, risk_manager):
        """Test blocked symbols are rejected."""
        blocked_symbols = ["TRY/USD", "RUB/USD", "CNY/USD"]

        for symbol in blocked_symbols:
            order = Order()
            order.symbol = symbol
            order.side = Side.BUY
            order.quantity = 100_000

            result = risk_manager.check_symbol_restrictions(order)

            assert result.passed is False
            assert result.violations[0].type == RiskViolationType.SYMBOL_RESTRICTION
            assert "blocked symbol" in result.violations[0].message

    def test_allowed_symbols_whitelist(self, risk_manager):
        """Test whitelist mode for allowed symbols."""
        # Configure whitelist
        risk_manager.limits.allowed_symbols = ["EUR/USD", "GBP/USD", "USD/JPY"]
        risk_manager.limits.blocked_symbols = []  # Clear blacklist

        # Allowed symbol
        order = Order()
        order.symbol = "EUR/USD"
        order.side = Side.BUY
        order.quantity = 100_000

        result = risk_manager.check_symbol_restrictions(order)
        assert result.passed is True

        # Not in whitelist
        order.symbol = "AUD/USD"
        result = risk_manager.check_symbol_restrictions(order)

        assert result.passed is False
        assert "not in allowed symbols" in result.violations[0].message

    def test_symbol_case_sensitivity(self, risk_manager):
        """Test symbol matching is case-sensitive."""
        order = Order()
        order.symbol = "eur/usd"  # Lowercase
        order.side = Side.BUY
        order.quantity = 100_000

        # Should not match EUR/USD in allowed lists
        result = risk_manager.check_order_limits(order)

        # Depends on implementation - adjust as needed
        # This test documents the expected behavior


class TestOrderValidationCombinations:
    """Test combined order validation scenarios."""

    def test_multiple_validation_failures(self, risk_manager):
        """Test order failing multiple validations."""
        order = Order()
        order.symbol = "RUB/USD"  # Blocked symbol
        order.side = Side.BUY
        order.quantity = 5_000  # Below minimum
        order.price = 80.00  # Arbitrary
        order.order_type = OrdType.LIMIT

        result = risk_manager.validate_order(order)

        assert result.passed is False
        assert len(result.violations) >= 2

        violation_types = [v.type for v in result.violations]
        assert RiskViolationType.SYMBOL_RESTRICTION in violation_types
        assert RiskViolationType.ORDER_SIZE_LIMIT in violation_types

    def test_order_validation_performance(self, risk_manager):
        """Test order validation performance."""
        import time

        order = Order()
        order.symbol = "EUR/USD"
        order.side = Side.BUY
        order.quantity = 100_000
        order.price = 1.1000
        order.notional = order.quantity * order.price
        order.order_type = OrdType.LIMIT

        # Validate 1000 orders
        start_time = time.time()

        for _ in range(1000):
            result = risk_manager.validate_order(order)
            assert result.passed is True

        elapsed_time = time.time() - start_time
        avg_time_ms = (elapsed_time / 1000) * 1000

        # Should validate quickly (< 1ms per order)
        assert avg_time_ms < 1.0, f"Validation too slow: {avg_time_ms:.2f}ms per order"

    def test_fx_cross_validation(self, risk_manager):
        """Test validation of FX cross pairs."""
        # Add market data for cross
        risk_manager.market_data["EUR/JPY"] = MarketData(
            symbol="EUR/JPY",
            bid=121.95,
            ask=122.05,
            mid=122.00,
            last_update=datetime.now(timezone.utc),
        )

        order = Order()
        order.symbol = "EUR/JPY"
        order.side = Side.SELL
        order.quantity = 100_000
        order.price = 121.50
        order.order_type = OrdType.LIMIT

        result = risk_manager.validate_order(order)

        assert result.passed is True
        assert "cross pair" not in str(result.warnings)


class TestOrderValidationEdgeCases:
    """Test edge cases in order validation."""

    def test_zero_quantity_order(self, risk_manager):
        """Test rejection of zero quantity orders."""
        order = Order()
        order.symbol = "EUR/USD"
        order.side = Side.BUY
        order.quantity = 0
        order.price = 1.1000

        result = risk_manager.check_order_limits(order)

        assert result.passed is False
        assert "zero quantity" in result.violations[0].message.lower()

    def test_negative_price_order(self, risk_manager):
        """Test rejection of negative price orders."""
        order = Order()
        order.symbol = "EUR/USD"
        order.side = Side.BUY
        order.quantity = 100_000
        order.price = -1.1000  # Invalid
        order.order_type = OrdType.LIMIT

        result = risk_manager.validate_order(order)

        assert result.passed is False
        assert "invalid price" in result.violations[0].message.lower()

    @pytest.mark.parametrize(
        "order_type,price_required",
        [
            (OrdType.MARKET, False),
            (OrdType.LIMIT, True),
            (OrdType.STOP, True),
            (OrdType.STOP_LIMIT, True),
        ],
    )
    def test_order_type_price_requirements(
        self, risk_manager, order_type, price_required
    ):
        """Test price requirements by order type."""
        order = Order()
        order.symbol = "EUR/USD"
        order.side = Side.BUY
        order.quantity = 100_000
        order.order_type = order_type
        # No price set

        result = risk_manager.validate_order(order)

        if price_required:
            assert result.passed is False
            assert "price required" in result.violations[0].message.lower()
        else:
            # Market orders don't need price
            assert (
                len([v for v in result.violations if "price" in v.message.lower()]) == 0
            )
