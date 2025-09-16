"""
Test risk management under stress scenarios.

This module tests the risk management system's behavior under various
stress conditions including high load, market volatility, and system failures.
"""

import asyncio
import random
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, Mock, patch

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
    limits.max_portfolio_notional = 10_000_000  # $10M
    limits.max_single_position_notional = 1_000_000  # $1M
    limits.max_daily_loss = 50_000  # $50K
    limits.max_order_rate_per_minute = 100
    limits.max_concurrent_orders = 50
    return limits


@pytest.fixture
def risk_manager(risk_limits):
    """Create risk manager instance with market data."""
    manager = FXRiskManager(limits=risk_limits)

    # Add market data for multiple pairs
    pairs = ["EUR/USD", "GBP/USD", "USD/JPY", "AUD/USD", "USD/CHF"]
    base_prices = [1.1000, 1.2500, 111.00, 0.7500, 0.9500]

    for pair, base_price in zip(pairs, base_prices):
        manager.market_data[pair] = MarketData(
            symbol=pair,
            bid=base_price - 0.0005,
            ask=base_price + 0.0005,
            mid=base_price,
            last_update=datetime.now(timezone.utc),
        )

    return manager


class TestHighLoadScenarios:
    """Test system behavior under high load."""

    @pytest.mark.asyncio
    async def test_concurrent_order_validation(self, risk_manager):
        """Test handling many concurrent order validations."""
        # Create 100 random orders
        orders = []
        symbols = ["EUR/USD", "GBP/USD", "USD/JPY", "AUD/USD", "USD/CHF"]

        for i in range(100):
            order = Order()
            order.order_id = f"LOAD_TEST_{i}"
            order.symbol = random.choice(symbols)
            order.side = random.choice([Side.BUY, Side.SELL])
            order.quantity = random.randint(10_000, 500_000)
            order.price = risk_manager.market_data[order.symbol].mid * (
                1 + random.uniform(-0.01, 0.01)
            )
            order.notional = order.quantity * order.price
            orders.append(order)

        # Validate all orders concurrently
        start_time = time.time()

        async def validate_order(order):
            return await asyncio.to_thread(risk_manager.validate_order, order)

        results = await asyncio.gather(*[validate_order(order) for order in orders])

        elapsed_time = time.time() - start_time

        # Performance assertions
        assert len(results) == 100
        assert elapsed_time < 5.0  # Should complete within 5 seconds

        # Check results
        passed_count = sum(1 for r in results if r.passed)
        failed_count = sum(1 for r in results if not r.passed)

        print(
            f"Concurrent validation: {passed_count} passed, {failed_count} failed in {elapsed_time:.2f}s"
        )

        # Verify system stability
        assert all(isinstance(r, RiskCheckResult) for r in results)

    def test_order_rate_limiting(self, risk_manager):
        """Test order rate limiting under burst conditions."""
        # Track order submissions
        risk_manager.order_submission_times = []

        # Submit orders in burst
        results = []
        burst_size = 150  # Exceeds 100/minute limit

        for i in range(burst_size):
            order = Order()
            order.order_id = f"BURST_{i}"
            order.symbol = "EUR/USD"
            order.side = Side.BUY
            order.quantity = 100_000
            order.price = 1.1000

            result = risk_manager.check_order_rate_limit(order)
            results.append(result)

            # Record submission time
            risk_manager.order_submission_times.append(datetime.now(timezone.utc))

        # Check rate limiting kicked in
        passed_count = sum(1 for r in results if r.passed)
        assert passed_count <= risk_manager.limits.max_order_rate_per_minute

        # Verify appropriate error messages
        rate_limit_violations = [
            r
            for r in results
            if not r.passed
            and any(v.type == RiskViolationType.RATE_LIMIT for v in r.violations)
        ]
        assert len(rate_limit_violations) > 0

    def test_memory_usage_under_load(self, risk_manager):
        """Test memory usage doesn't grow unbounded."""
        import os

        import psutil

        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB

        # Create and validate many orders
        for i in range(10_000):
            order = Order()
            order.order_id = f"MEM_TEST_{i}"
            order.symbol = "EUR/USD"
            order.side = Side.BUY if i % 2 == 0 else Side.SELL
            order.quantity = 100_000
            order.price = 1.1000 + (i % 100) * 0.0001
            order.notional = order.quantity * order.price

            result = risk_manager.validate_order(order)

            # Simulate some position updates
            if result.passed and i % 10 == 0:
                risk_manager.update_position(order)

        # Check memory growth
        final_memory = process.memory_info().rss / 1024 / 1024  # MB
        memory_growth = final_memory - initial_memory

        print(f"Memory growth: {memory_growth:.2f} MB")

        # Should not grow excessively (less than 100MB for 10K orders)
        assert memory_growth < 100

        # Verify cleanup mechanisms
        assert len(risk_manager.order_history) <= risk_manager.max_order_history_size


class TestMarketVolatilityScenarios:
    """Test risk management during volatile market conditions."""

    def test_rapid_price_movements(self, risk_manager):
        """Test handling rapid price changes."""
        symbol = "EUR/USD"
        base_price = 1.1000

        # Simulate rapid price movements
        price_changes = [
            0.0000,  # Normal
            0.0050,  # +0.5%
            0.0150,  # +1.5%
            0.0300,  # +3% spike
            -0.0200,  # -2% drop
            -0.0400,  # -4% crash
        ]

        results = []
        for i, change in enumerate(price_changes):
            # Update market data
            new_price = base_price + change
            risk_manager.market_data[symbol] = MarketData(
                symbol=symbol,
                bid=new_price - 0.0005,
                ask=new_price + 0.0005,
                mid=new_price,
                last_update=datetime.now(timezone.utc),
            )

            # Try to place order at old price
            order = Order()
            order.order_id = f"VOLATILE_{i}"
            order.symbol = symbol
            order.side = Side.BUY
            order.quantity = 1_000_000
            order.price = base_price  # Using stale price
            order.order_type = OrdType.LIMIT

            result = risk_manager.check_price_deviation(order)
            results.append((change, result))

        # Check appropriate rejections
        for change, result in results:
            deviation_pct = abs(change / base_price) * 100
            if deviation_pct > 2.0:  # 2% deviation limit
                assert not result.passed
                assert any(
                    v.type == RiskViolationType.PRICE_DEVIATION
                    for v in result.violations
                )

    def test_market_gap_scenario(self, risk_manager):
        """Test handling market gaps (e.g., weekend gaps)."""
        # Friday close positions
        risk_manager.positions["EUR/USD"] = Mock(
            symbol="EUR/USD",
            net_quantity=1_000_000,  # Long 1M
            avg_price=1.1000,
            notional=1_100_000,
            unrealized_pnl=0,
        )

        # Simulate weekend gap - market opens 2% lower
        risk_manager.market_data["EUR/USD"] = MarketData(
            symbol="EUR/USD",
            bid=1.0780,
            ask=1.0785,
            mid=1.0782,  # ~2% gap down
            last_update=datetime.now(timezone.utc),
        )

        # Update position P&L
        gap_loss = 1_000_000 * (1.0782 - 1.1000)  # -$21,800
        risk_manager.positions["EUR/USD"].unrealized_pnl = gap_loss

        # Try to place new orders
        order = Order()
        order.order_id = "POST_GAP_1"
        order.symbol = "EUR/USD"
        order.side = Side.BUY  # Adding to losing position
        order.quantity = 500_000
        order.price = 1.0785

        # Should consider gap loss in risk checks
        result = risk_manager.validate_order(order)

        # If including unrealized P&L, might restrict new trades
        if abs(gap_loss) > risk_manager.limits.max_daily_loss * 0.5:
            assert len(result.warnings) > 0 or not result.passed

    def test_correlated_asset_stress(self, risk_manager):
        """Test risk during correlated asset movements."""
        # Set up correlated positions
        positions = {
            "EUR/USD": Mock(
                symbol="EUR/USD", net_quantity=1_000_000, notional=1_100_000
            ),
            "GBP/USD": Mock(symbol="GBP/USD", net_quantity=800_000, notional=1_000_000),
            "EUR/GBP": Mock(symbol="EUR/GBP", net_quantity=-500_000, notional=440_000),
        }
        risk_manager.positions = positions

        # Simulate USD strengthening (correlated move)
        stress_factor = 0.03  # 3% USD strength

        for symbol in ["EUR/USD", "GBP/USD"]:
            old_price = risk_manager.market_data[symbol].mid
            new_price = old_price * (1 - stress_factor)
            risk_manager.market_data[symbol].mid = new_price

            # Update unrealized P&L
            position = positions[symbol]
            position.unrealized_pnl = position.net_quantity * (new_price - old_price)

        # Check portfolio risk
        metrics = risk_manager.get_portfolio_metrics()
        total_unrealized = sum(p.unrealized_pnl for p in positions.values())

        # Should trigger risk warnings
        if abs(total_unrealized) > risk_manager.limits.max_daily_loss:
            # New orders should be restricted
            order = Order()
            order.symbol = "EUR/USD"
            order.side = Side.BUY
            order.quantity = 100_000

            result = risk_manager.validate_order(order)
            assert not result.passed or len(result.warnings) > 0


class TestSystemFailureScenarios:
    """Test risk management during system failures."""

    def test_market_data_feed_failure(self, risk_manager):
        """Test handling when market data feed fails."""
        # Simulate stale market data
        for symbol, data in risk_manager.market_data.items():
            data.last_update = datetime.now(timezone.utc) - timedelta(minutes=10)

        order = Order()
        order.order_id = "STALE_DATA_1"
        order.symbol = "EUR/USD"
        order.side = Side.BUY
        order.quantity = 1_000_000
        order.price = 1.1000
        order.order_type = OrdType.LIMIT

        result = risk_manager.validate_order(order)

        # Should warn about stale data
        assert any("stale" in w.lower() for w in result.warnings)

        # Might restrict or reject orders
        if risk_manager.limits.reject_on_stale_data:
            assert not result.passed

    def test_database_connection_failure(self, risk_manager):
        """Test handling database connection failures."""
        # Mock database failure
        with patch.object(
            risk_manager, "persist_order", side_effect=Exception("DB Connection failed")
        ):
            order = Order()
            order.order_id = "DB_FAIL_1"
            order.symbol = "EUR/USD"
            order.side = Side.BUY
            order.quantity = 100_000

            # Should handle gracefully
            try:
                result = risk_manager.validate_order(order)
                # Might allow order but log error
                assert isinstance(result, RiskCheckResult)
            except Exception as e:
                # Should not crash the system
                pytest.fail(f"System crashed on DB failure: {e}")

    def test_partial_system_degradation(self, risk_manager):
        """Test risk management with partial system degradation."""
        # Simulate some services being slow/unavailable
        degraded_services = {
            "position_service": 0.5,  # 50% failure rate
            "market_data_service": 0.2,  # 20% failure rate
            "limit_service": 0.1,  # 10% failure rate
        }

        orders_processed = 0
        orders_failed = 0

        for i in range(100):
            order = Order()
            order.order_id = f"DEGRADED_{i}"
            order.symbol = random.choice(["EUR/USD", "GBP/USD", "USD/JPY"])
            order.side = random.choice([Side.BUY, Side.SELL])
            order.quantity = 100_000

            # Simulate service failures
            if random.random() < degraded_services["market_data_service"]:
                # Market data unavailable for this symbol
                risk_manager.market_data.pop(order.symbol, None)

            try:
                result = risk_manager.validate_order(order)
                orders_processed += 1

                # Should degrade gracefully
                if order.symbol not in risk_manager.market_data:
                    assert len(result.warnings) > 0 or not result.passed

            except Exception:
                orders_failed += 1

        # System should remain operational despite failures
        success_rate = orders_processed / (orders_processed + orders_failed)
        assert success_rate > 0.8  # At least 80% success rate

    def test_recovery_after_outage(self, risk_manager):
        """Test system recovery after brief outage."""
        # Simulate positions before outage
        risk_manager.positions = {
            "EUR/USD": Mock(
                symbol="EUR/USD", net_quantity=1_000_000, notional=1_100_000
            ),
            "GBP/USD": Mock(symbol="GBP/USD", net_quantity=-500_000, notional=625_000),
        }

        # Simulate outage - clear some state
        risk_manager.order_history.clear()
        risk_manager.active_orders.clear()

        # Simulate recovery - rebuild state
        risk_manager.recover_from_outage()

        # Test post-recovery validation
        order = Order()
        order.order_id = "POST_RECOVERY_1"
        order.symbol = "EUR/USD"
        order.side = Side.SELL
        order.quantity = 500_000

        result = risk_manager.validate_order(order)

        # Should be extra cautious after recovery
        assert isinstance(result, RiskCheckResult)
        if hasattr(risk_manager, "post_recovery_mode"):
            assert len(result.warnings) > 0  # Should warn about recovery mode


class TestExtremeMarketConditions:
    """Test handling of extreme market conditions."""

    def test_flash_crash_scenario(self, risk_manager):
        """Test behavior during flash crash."""
        # Normal market
        normal_price = 1.1000

        # Flash crash - 10% drop in seconds
        crash_prices = [
            1.1000,  # T+0s
            1.0800,  # T+1s (-1.8%)
            1.0500,  # T+2s (-4.5%)
            1.0000,  # T+3s (-9.1%)
            0.9900,  # T+4s (-10%)
            1.0200,  # T+5s (partial recovery)
        ]

        for i, price in enumerate(crash_prices):
            # Update market with increasing volatility
            risk_manager.market_data["EUR/USD"] = MarketData(
                symbol="EUR/USD",
                bid=price - 0.0050,  # Wider spread during crash
                ask=price + 0.0050,
                mid=price,
                last_update=datetime.now(timezone.utc),
            )

            # Try to trade
            order = Order()
            order.order_id = f"FLASH_CRASH_{i}"
            order.symbol = "EUR/USD"
            order.side = Side.BUY if i > 3 else Side.SELL  # Try to catch falling knife
            order.quantity = 1_000_000
            order.price = price
            order.order_type = OrdType.LIMIT

            result = risk_manager.validate_order(order)

            # Should implement circuit breakers
            if abs(price - normal_price) / normal_price > 0.05:  # 5% move
                # Might halt trading or require overrides
                assert not result.passed or result.requires_override

    def test_liquidity_crisis(self, risk_manager):
        """Test handling of liquidity crisis."""
        # Simulate widening spreads and poor liquidity
        liquidity_levels = [
            (0.0005, 1_000_000),  # Normal: 5 pip spread, 1M available
            (0.0020, 500_000),  # Degraded: 20 pip spread, 500K available
            (0.0100, 100_000),  # Poor: 100 pip spread, 100K available
            (0.0500, 10_000),  # Crisis: 500 pip spread, 10K available
        ]

        for spread, available_liquidity in liquidity_levels:
            # Update market data with liquidity info
            risk_manager.market_data["EUR/USD"].bid = 1.1000 - spread / 2
            risk_manager.market_data["EUR/USD"].ask = 1.1000 + spread / 2
            risk_manager.market_data["EUR/USD"].available_liquidity = (
                available_liquidity
            )

            # Try to place large order
            order = Order()
            order.order_id = f"LIQUIDITY_{spread}"
            order.symbol = "EUR/USD"
            order.side = Side.BUY
            order.quantity = 1_000_000  # Large order
            order.price = risk_manager.market_data["EUR/USD"].ask

            result = risk_manager.check_liquidity(order)

            # Should warn or reject based on liquidity
            if order.quantity > available_liquidity:
                assert not result.passed or len(result.warnings) > 0

            # Should consider spread cost
            spread_cost = order.quantity * spread
            if spread_cost > risk_manager.limits.max_acceptable_spread_cost:
                assert not result.passed

    @pytest.mark.parametrize(
        "scenario",
        [
            "black_swan",
            "sovereign_default",
            "currency_peg_break",
            "central_bank_intervention",
        ],
    )
    def test_extreme_event_scenarios(self, risk_manager, scenario):
        """Test various extreme market events."""
        if scenario == "black_swan":
            # Sudden 20% move
            risk_manager.handle_black_swan_event(
                symbol="EUR/USD", magnitude=0.20, direction="down"
            )
        elif scenario == "sovereign_default":
            # Specific currency crash
            risk_manager.handle_sovereign_crisis(
                affected_currencies=["EUR"], severity="severe"
            )
        elif scenario == "currency_peg_break":
            # E.g., CHF cap removal
            risk_manager.handle_peg_break(
                symbol="USD/CHF", old_peg=1.2000, new_level=1.0000
            )
        elif scenario == "central_bank_intervention":
            # Sudden policy change
            risk_manager.handle_central_bank_action(
                currency="JPY", action="intervention", magnitude="large"
            )

        # All positions should be frozen or limited
        order = Order()
        order.symbol = "EUR/USD"
        order.side = Side.BUY
        order.quantity = 100_000

        result = risk_manager.validate_order(order)

        # During extreme events, should be very restrictive
        assert not result.passed or result.requires_emergency_override
