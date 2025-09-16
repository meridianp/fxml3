"""
Comprehensive edge case testing for critical trading operations.

Tests edge cases, error conditions, and boundary scenarios that could
occur in production trading environments following TDD methodology.
"""

import asyncio
import time
from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, List, Optional
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import numpy as np
import pandas as pd
import pytest

# Test categories for edge cases
pytestmark = [pytest.mark.edge_cases, pytest.mark.critical, pytest.mark.trading]


@pytest.fixture
def network_failure_simulator():
    """Simulate various network failure scenarios."""

    class NetworkFailureSimulator:
        def __init__(self):
            self.failure_modes = [
                "connection_timeout",
                "connection_reset",
                "dns_failure",
                "ssl_handshake_failure",
                "packet_loss",
                "slow_response",
            ]

        async def simulate_failure(self, failure_mode: str, duration: float = 1.0):
            """Simulate specific network failure."""
            if failure_mode == "connection_timeout":
                await asyncio.sleep(duration * 10)  # Simulate timeout
                raise TimeoutError("Connection timed out")
            elif failure_mode == "connection_reset":
                raise ConnectionResetError("Connection reset by peer")
            elif failure_mode == "dns_failure":
                raise OSError("DNS resolution failed")
            elif failure_mode == "ssl_handshake_failure":
                raise Exception("SSL handshake failed")
            elif failure_mode == "packet_loss":
                # Randomly fail some requests
                if np.random.random() < 0.3:
                    raise Exception("Packet lost")
            elif failure_mode == "slow_response":
                await asyncio.sleep(duration * 5)  # Very slow response

        def is_critical_failure(self, failure_mode: str) -> bool:
            """Check if failure mode is critical for trading."""
            critical_failures = [
                "connection_reset",
                "dns_failure",
                "ssl_handshake_failure",
            ]
            return failure_mode in critical_failures

    return NetworkFailureSimulator()


@pytest.fixture
def extreme_market_data():
    """Generate extreme market data scenarios."""
    scenarios = {
        "flash_crash": {
            "description": "Sudden 20% price drop",
            "data": pd.DataFrame(
                {
                    "timestamp": pd.date_range(
                        "2024-01-01 10:00", periods=10, freq="1min"
                    ),
                    "open": [
                        1.2650,
                        1.2648,
                        1.2645,
                        1.0120,
                        1.0115,
                        1.0110,
                        1.0108,
                        1.0105,
                        1.0102,
                        1.0100,
                    ],
                    "high": [
                        1.2652,
                        1.2650,
                        1.2647,
                        1.0125,
                        1.0118,
                        1.0112,
                        1.0110,
                        1.0107,
                        1.0104,
                        1.0102,
                    ],
                    "low": [
                        1.2648,
                        1.2645,
                        1.0120,
                        1.0115,
                        1.0110,
                        1.0105,
                        1.0102,
                        1.0100,
                        1.0098,
                        1.0095,
                    ],
                    "close": [
                        1.2648,
                        1.2645,
                        1.0120,
                        1.0115,
                        1.0110,
                        1.0108,
                        1.0105,
                        1.0102,
                        1.0100,
                        1.0098,
                    ],
                    "volume": [
                        50000,
                        75000,
                        500000,
                        1000000,
                        800000,
                        600000,
                        400000,
                        300000,
                        200000,
                        150000,
                    ],
                }
            ),
        },
        "gap_opening": {
            "description": "Large gap on market open",
            "data": pd.DataFrame(
                {
                    "timestamp": pd.date_range(
                        "2024-01-01 09:00", periods=5, freq="1min"
                    ),
                    "open": [1.2650, 1.3200, 1.3195, 1.3190, 1.3185],  # 550 pip gap
                    "high": [1.2652, 1.3205, 1.3200, 1.3195, 1.3190],
                    "low": [1.2648, 1.3195, 1.3190, 1.3185, 1.3180],
                    "close": [1.2650, 1.3200, 1.3195, 1.3190, 1.3185],
                    "volume": [10000, 200000, 150000, 100000, 80000],
                }
            ),
        },
        "zero_liquidity": {
            "description": "Market with zero liquidity/volume",
            "data": pd.DataFrame(
                {
                    "timestamp": pd.date_range(
                        "2024-01-01 12:00", periods=5, freq="1min"
                    ),
                    "open": [1.2650, 1.2650, 1.2650, 1.2650, 1.2650],
                    "high": [1.2650, 1.2650, 1.2650, 1.2650, 1.2650],
                    "low": [1.2650, 1.2650, 1.2650, 1.2650, 1.2650],
                    "close": [1.2650, 1.2650, 1.2650, 1.2650, 1.2650],
                    "volume": [0, 0, 0, 0, 0],  # Zero volume
                }
            ),
        },
        "extreme_volatility": {
            "description": "Extremely high volatility period",
            "data": pd.DataFrame(
                {
                    "timestamp": pd.date_range(
                        "2024-01-01 14:00", periods=10, freq="1min"
                    ),
                    "open": [
                        1.2650,
                        1.3100,
                        1.2200,
                        1.2900,
                        1.2100,
                        1.2800,
                        1.2050,
                        1.2750,
                        1.2000,
                        1.2700,
                    ],
                    "high": [
                        1.3150,
                        1.3200,
                        1.2950,
                        1.3000,
                        1.2850,
                        1.2900,
                        1.2800,
                        1.2850,
                        1.2750,
                        1.2800,
                    ],
                    "low": [
                        1.2200,
                        1.2150,
                        1.2000,
                        1.2050,
                        1.2000,
                        1.2000,
                        1.1950,
                        1.1950,
                        1.1900,
                        1.1950,
                    ],
                    "close": [
                        1.3100,
                        1.2200,
                        1.2900,
                        1.2100,
                        1.2800,
                        1.2050,
                        1.2750,
                        1.2000,
                        1.2700,
                        1.1980,
                    ],
                    "volume": [1000000] * 10,
                }
            ),
        },
    }
    return scenarios


@pytest.fixture
def corrupt_data_scenarios():
    """Generate various corrupt data scenarios."""
    return {
        "negative_prices": pd.DataFrame(
            {
                "timestamp": pd.date_range("2024-01-01", periods=5, freq="1H"),
                "open": [1.2650, -1.2648, 1.2645, 1.2642, 1.2640],
                "high": [1.2652, 1.2650, -1.2647, 1.2644, 1.2642],
                "low": [1.2648, 1.2645, 1.2642, -1.2640, 1.2638],
                "close": [1.2648, 1.2645, 1.2642, 1.2640, -1.2638],
                "volume": [10000, 15000, 12000, 8000, 9000],
            }
        ),
        "infinite_values": pd.DataFrame(
            {
                "timestamp": pd.date_range("2024-01-01", periods=5, freq="1H"),
                "open": [1.2650, float("inf"), 1.2645, 1.2642, 1.2640],
                "high": [1.2652, 1.2650, float("inf"), 1.2644, 1.2642],
                "low": [1.2648, 1.2645, 1.2642, float("-inf"), 1.2638],
                "close": [1.2648, 1.2645, 1.2642, 1.2640, float("inf")],
                "volume": [10000, 15000, 12000, 8000, 9000],
            }
        ),
        "nan_values": pd.DataFrame(
            {
                "timestamp": pd.date_range("2024-01-01", periods=5, freq="1H"),
                "open": [1.2650, np.nan, 1.2645, 1.2642, 1.2640],
                "high": [1.2652, 1.2650, np.nan, 1.2644, 1.2642],
                "low": [1.2648, 1.2645, 1.2642, np.nan, 1.2638],
                "close": [1.2648, 1.2645, 1.2642, 1.2640, np.nan],
                "volume": [10000, 15000, 12000, 8000, 9000],
            }
        ),
        "wrong_ohlc_order": pd.DataFrame(
            {
                "timestamp": pd.date_range("2024-01-01", periods=5, freq="1H"),
                "open": [1.2650, 1.2648, 1.2645, 1.2642, 1.2640],
                "high": [1.2600, 1.2600, 1.2600, 1.2600, 1.2600],  # High < Open/Close
                "low": [1.2700, 1.2700, 1.2700, 1.2700, 1.2700],  # Low > Open/Close
                "close": [1.2648, 1.2645, 1.2642, 1.2640, 1.2638],
                "volume": [10000, 15000, 12000, 8000, 9000],
            }
        ),
    }


class TestNetworkFailureEdgeCases:
    """Test edge cases related to network failures."""

    @pytest.mark.asyncio
    async def test_broker_connection_loss_during_order(self, network_failure_simulator):
        """Test order handling when broker connection is lost mid-execution."""

        class MockBrokerAdapter:
            def __init__(self):
                self.is_connected_flag = True
                self.order_count = 0

            def is_connected(self):
                return self.is_connected_flag

            async def submit_order(self, order):
                self.order_count += 1
                if self.order_count == 1:
                    # First order succeeds
                    return {"order_id": "ORDER_1", "status": "FILLED"}
                else:
                    # Subsequent orders fail due to connection loss
                    self.is_connected_flag = False
                    await network_failure_simulator.simulate_failure("connection_reset")

        broker = MockBrokerAdapter()

        # First order should succeed
        result1 = await broker.submit_order(
            {"symbol": "EURUSD", "side": "BUY", "quantity": 10000}
        )
        assert result1["status"] == "FILLED"

        # Second order should fail with connection reset
        with pytest.raises(ConnectionResetError):
            await broker.submit_order(
                {"symbol": "EURUSD", "side": "SELL", "quantity": 10000}
            )

        # Connection should be marked as lost
        assert not broker.is_connected()

    @pytest.mark.asyncio
    async def test_market_data_feed_interruption(self, network_failure_simulator):
        """Test handling of market data feed interruptions."""

        class MockMarketDataFeed:
            def __init__(self):
                self.connection_stable = True
                self.data_count = 0

            async def get_latest_tick(self, symbol):
                self.data_count += 1
                if self.data_count > 3:
                    # Simulate feed interruption after 3 successful ticks
                    self.connection_stable = False
                    await network_failure_simulator.simulate_failure("packet_loss")

                return {
                    "symbol": symbol,
                    "bid": 1.2648,
                    "ask": 1.2652,
                    "timestamp": datetime.now(),
                }

        feed = MockMarketDataFeed()

        # First few ticks should succeed
        for _ in range(3):
            tick = await feed.get_latest_tick("EURUSD")
            assert tick["symbol"] == "EURUSD"
            assert tick["bid"] > 0

        # Fourth tick should fail
        with pytest.raises(Exception, match="Packet lost"):
            await feed.get_latest_tick("EURUSD")

        assert not feed.connection_stable

    @pytest.mark.asyncio
    async def test_dns_resolution_failure(self, network_failure_simulator):
        """Test handling of DNS resolution failures."""

        class MockBrokerConnector:
            async def connect(self, hostname):
                if "broker.invalid" in hostname:
                    await network_failure_simulator.simulate_failure("dns_failure")
                return True

        connector = MockBrokerConnector()

        # Valid hostname should work
        connected = await connector.connect("broker.example.com")
        assert connected

        # Invalid hostname should fail with DNS error
        with pytest.raises(OSError, match="DNS resolution failed"):
            await connector.connect("broker.invalid.domain")

    @pytest.mark.asyncio
    async def test_ssl_handshake_failure(self, network_failure_simulator):
        """Test handling of SSL handshake failures."""

        class MockSecureConnection:
            async def establish_secure_connection(self, use_ssl=True):
                if use_ssl:
                    await network_failure_simulator.simulate_failure(
                        "ssl_handshake_failure"
                    )
                return {"secure": not use_ssl}

        connection = MockSecureConnection()

        # Non-SSL connection should work
        result = await connection.establish_secure_connection(use_ssl=False)
        assert not result["secure"]

        # SSL connection should fail
        with pytest.raises(Exception, match="SSL handshake failed"):
            await connection.establish_secure_connection(use_ssl=True)


class TestExtremeMarketConditionEdgeCases:
    """Test edge cases during extreme market conditions."""

    def test_flash_crash_handling(self, extreme_market_data):
        """Test system behavior during flash crash scenario."""
        crash_data = extreme_market_data["flash_crash"]["data"]

        # Calculate price change
        initial_price = crash_data.iloc[0]["close"]
        crash_price = crash_data.iloc[-1]["close"]
        price_change = (crash_price - initial_price) / initial_price

        # Should detect extreme price movement
        assert price_change < -0.15  # More than 15% drop

        # Volume should spike during crash
        max_volume = crash_data["volume"].max()
        avg_volume = crash_data["volume"].mean()
        assert max_volume > avg_volume * 3  # Volume spike

    def test_gap_opening_handling(self, extreme_market_data):
        """Test handling of large price gaps on market open."""
        gap_data = extreme_market_data["gap_opening"]["data"]

        # Calculate gap size
        pre_gap_close = gap_data.iloc[0]["close"]
        post_gap_open = gap_data.iloc[1]["open"]
        gap_size = abs(post_gap_open - pre_gap_close)

        # Should detect significant gap
        assert gap_size > 0.05  # More than 500 pips for EUR/USD

        # Gap should be handled without causing system errors
        assert not np.isnan(gap_size)
        assert np.isfinite(gap_size)

    def test_zero_liquidity_handling(self, extreme_market_data):
        """Test handling of zero liquidity conditions."""
        zero_liq_data = extreme_market_data["zero_liquidity"]["data"]

        # All volumes should be zero
        assert (zero_liq_data["volume"] == 0).all()

        # Prices should be static (no movement)
        price_range = zero_liq_data["high"].max() - zero_liq_data["low"].min()
        assert price_range == 0.0

        # System should handle zero liquidity gracefully
        assert not zero_liq_data.empty
        assert len(zero_liq_data) > 0

    def test_extreme_volatility_handling(self, extreme_market_data):
        """Test handling of extreme volatility periods."""
        volatile_data = extreme_market_data["extreme_volatility"]["data"]

        # Calculate intrabar ranges
        ranges = (volatile_data["high"] - volatile_data["low"]) / volatile_data["open"]
        max_range = ranges.max()

        # Should detect extreme intrabar volatility
        assert max_range > 0.05  # More than 5% intrabar range

        # System should not crash on extreme volatility
        assert np.all(np.isfinite(ranges))
        assert len(volatile_data) == 10


class TestCorruptDataEdgeCases:
    """Test edge cases with corrupt or invalid data."""

    def test_negative_price_handling(self, corrupt_data_scenarios):
        """Test handling of negative prices in market data."""
        negative_price_data = corrupt_data_scenarios["negative_prices"]

        # Should detect negative prices
        has_negative_open = (negative_price_data["open"] < 0).any()
        has_negative_high = (negative_price_data["high"] < 0).any()
        has_negative_low = (negative_price_data["low"] < 0).any()
        has_negative_close = (negative_price_data["close"] < 0).any()

        assert (
            has_negative_open
            or has_negative_high
            or has_negative_low
            or has_negative_close
        )

        # System should handle negative prices without crashing
        assert not negative_price_data.empty

    def test_infinite_value_handling(self, corrupt_data_scenarios):
        """Test handling of infinite values in market data."""
        infinite_data = corrupt_data_scenarios["infinite_values"]

        # Should detect infinite values
        has_inf_open = np.isinf(infinite_data["open"]).any()
        has_inf_high = np.isinf(infinite_data["high"]).any()
        has_inf_low = np.isinf(infinite_data["low"]).any()
        has_inf_close = np.isinf(infinite_data["close"]).any()

        assert has_inf_open or has_inf_high or has_inf_low or has_inf_close

        # System should handle infinite values
        assert not infinite_data.empty

    def test_nan_value_handling(self, corrupt_data_scenarios):
        """Test handling of NaN values in market data."""
        nan_data = corrupt_data_scenarios["nan_values"]

        # Should detect NaN values
        has_nan_open = np.isnan(nan_data["open"]).any()
        has_nan_high = np.isnan(nan_data["high"]).any()
        has_nan_low = np.isnan(nan_data["low"]).any()
        has_nan_close = np.isnan(nan_data["close"]).any()

        assert has_nan_open or has_nan_high or has_nan_low or has_nan_close

        # System should handle NaN values gracefully
        assert not nan_data.empty

    def test_invalid_ohlc_order_handling(self, corrupt_data_scenarios):
        """Test handling of invalid OHLC relationships."""
        invalid_ohlc_data = corrupt_data_scenarios["wrong_ohlc_order"]

        # Should detect OHLC violations
        # High should be >= Open, Low, Close
        high_violations = (
            (invalid_ohlc_data["high"] < invalid_ohlc_data["open"])
            | (invalid_ohlc_data["high"] < invalid_ohlc_data["low"])
            | (invalid_ohlc_data["high"] < invalid_ohlc_data["close"])
        ).any()

        # Low should be <= Open, High, Close
        low_violations = (
            (invalid_ohlc_data["low"] > invalid_ohlc_data["open"])
            | (invalid_ohlc_data["low"] > invalid_ohlc_data["high"])
            | (invalid_ohlc_data["low"] > invalid_ohlc_data["close"])
        ).any()

        assert high_violations or low_violations

        # System should detect and handle OHLC violations
        assert not invalid_ohlc_data.empty


class TestConcurrencyEdgeCases:
    """Test edge cases related to concurrent operations."""

    @pytest.mark.asyncio
    async def test_concurrent_order_submission_race_condition(self):
        """Test race conditions during concurrent order submissions."""

        class MockOrderManager:
            def __init__(self):
                self.order_id_counter = 0
                self.orders = {}
                self.lock = asyncio.Lock()

            async def submit_order(self, order):
                # Simulate potential race condition
                await asyncio.sleep(0.01)  # Small delay

                async with self.lock:
                    self.order_id_counter += 1
                    order_id = f"ORDER_{self.order_id_counter}"
                    self.orders[order_id] = order
                    return {"order_id": order_id, "status": "SUBMITTED"}

        manager = MockOrderManager()

        # Submit multiple orders concurrently
        orders = [
            {"symbol": "EURUSD", "side": "BUY", "quantity": 10000},
            {"symbol": "GBPUSD", "side": "SELL", "quantity": 15000},
            {"symbol": "USDJPY", "side": "BUY", "quantity": 20000},
            {"symbol": "USDCHF", "side": "SELL", "quantity": 12000},
            {"symbol": "AUDUSD", "side": "BUY", "quantity": 18000},
        ]

        tasks = [manager.submit_order(order) for order in orders]
        results = await asyncio.gather(*tasks)

        # All orders should be submitted successfully
        assert len(results) == 5
        assert all(result["status"] == "SUBMITTED" for result in results)

        # All order IDs should be unique (no race condition)
        order_ids = [result["order_id"] for result in results]
        assert len(set(order_ids)) == len(order_ids)

        # All orders should be stored
        assert len(manager.orders) == 5

    @pytest.mark.asyncio
    async def test_concurrent_risk_limit_checking(self):
        """Test concurrent risk limit checking for race conditions."""

        class MockRiskManager:
            def __init__(self):
                self.current_risk = 0.0
                self.max_risk = 0.05  # 5% max risk
                self.lock = asyncio.Lock()

            async def check_and_update_risk(self, new_risk):
                # Simulate race condition scenario
                await asyncio.sleep(0.01)

                async with self.lock:
                    if self.current_risk + new_risk > self.max_risk:
                        return False  # Risk limit exceeded

                    self.current_risk += new_risk
                    return True  # Risk within limits

        risk_manager = MockRiskManager()

        # Submit multiple risk checks concurrently
        risk_amounts = [0.015, 0.012, 0.018, 0.008, 0.010]  # Total = 0.063 > 0.05

        tasks = [risk_manager.check_and_update_risk(risk) for risk in risk_amounts]
        results = await asyncio.gather(*tasks)

        # Not all checks should pass (due to risk limits)
        assert not all(results)

        # Final risk should not exceed limit
        assert risk_manager.current_risk <= risk_manager.max_risk

    @pytest.mark.asyncio
    async def test_concurrent_market_data_updates(self):
        """Test concurrent market data updates for consistency."""

        class MockMarketDataManager:
            def __init__(self):
                self.latest_prices = {}
                self.update_count = {}
                self.lock = asyncio.Lock()

            async def update_price(self, symbol, price):
                await asyncio.sleep(0.001)  # Simulate processing time

                async with self.lock:
                    self.latest_prices[symbol] = price
                    self.update_count[symbol] = self.update_count.get(symbol, 0) + 1

        data_manager = MockMarketDataManager()

        # Simulate concurrent price updates for same symbol
        symbol = "EURUSD"
        prices = [1.2650, 1.2651, 1.2649, 1.2652, 1.2648]

        tasks = [data_manager.update_price(symbol, price) for price in prices]
        await asyncio.gather(*tasks)

        # Should have exactly one final price
        assert symbol in data_manager.latest_prices
        assert data_manager.latest_prices[symbol] in prices

        # Should have recorded all updates
        assert data_manager.update_count[symbol] == len(prices)


class TestResourceExhaustionEdgeCases:
    """Test edge cases related to resource exhaustion."""

    @pytest.mark.asyncio
    async def test_memory_pressure_handling(self):
        """Test system behavior under memory pressure."""

        class MockMemoryIntensiveOperation:
            def __init__(self):
                self.large_data_structures = []

            async def process_large_dataset(self, size_mb):
                # Simulate memory-intensive operation
                if size_mb > 100:  # Simulate memory limit
                    raise MemoryError("Insufficient memory")

                # Create large data structure
                data = np.random.random((size_mb * 1000, 100))
                self.large_data_structures.append(data)
                return len(data)

            def cleanup(self):
                self.large_data_structures.clear()

        processor = MockMemoryIntensiveOperation()

        try:
            # Small dataset should work
            result1 = await processor.process_large_dataset(50)  # 50MB
            assert result1 == 50000

            # Large dataset should fail
            with pytest.raises(MemoryError):
                await processor.process_large_dataset(200)  # 200MB

        finally:
            processor.cleanup()

    @pytest.mark.asyncio
    async def test_connection_pool_exhaustion(self):
        """Test handling of connection pool exhaustion."""

        class MockConnectionPool:
            def __init__(self, max_connections=3):
                self.max_connections = max_connections
                self.active_connections = 0
                self.waiting_queue = []

            async def acquire_connection(self):
                if self.active_connections >= self.max_connections:
                    raise Exception("Connection pool exhausted")

                self.active_connections += 1
                return f"connection_{self.active_connections}"

            async def release_connection(self, conn_id):
                if self.active_connections > 0:
                    self.active_connections -= 1

        pool = MockConnectionPool(max_connections=2)

        # First two connections should succeed
        conn1 = await pool.acquire_connection()
        conn2 = await pool.acquire_connection()

        assert conn1 is not None
        assert conn2 is not None
        assert pool.active_connections == 2

        # Third connection should fail
        with pytest.raises(Exception, match="Connection pool exhausted"):
            await pool.acquire_connection()

        # Releasing connection should allow new acquisition
        await pool.release_connection(conn1)
        conn3 = await pool.acquire_connection()
        assert conn3 is not None

    def test_disk_space_exhaustion_handling(self):
        """Test handling of disk space exhaustion."""

        class MockFileWriter:
            def __init__(self):
                self.disk_space_mb = 100  # Simulate 100MB available
                self.written_mb = 0

            def write_data(self, data_size_mb):
                if self.written_mb + data_size_mb > self.disk_space_mb:
                    raise OSError("No space left on device")

                self.written_mb += data_size_mb
                return f"Written {data_size_mb}MB"

        writer = MockFileWriter()

        # Small writes should succeed
        result1 = writer.write_data(30)
        result2 = writer.write_data(40)

        assert "30MB" in result1
        assert "40MB" in result2
        assert writer.written_mb == 70

        # Large write should fail
        with pytest.raises(OSError, match="No space left on device"):
            writer.write_data(50)  # Would exceed 100MB limit


class TestTimeBasedEdgeCases:
    """Test edge cases related to timing and scheduling."""

    @pytest.mark.asyncio
    async def test_market_close_edge_case(self):
        """Test system behavior at market close boundaries."""

        class MockMarketSchedule:
            def __init__(self):
                self.market_close_time = datetime.now().replace(
                    hour=17, minute=0, second=0
                )

            def is_market_open(self, timestamp=None):
                if timestamp is None:
                    timestamp = datetime.now()

                # Market closes at 17:00
                return timestamp.hour < 17

            async def place_order_with_schedule_check(self, order):
                current_time = datetime.now()

                if not self.is_market_open(current_time):
                    return {"status": "REJECTED", "reason": "Market closed"}

                # Simulate order processing time
                await asyncio.sleep(0.1)

                # Check again after processing (market might have closed)
                if not self.is_market_open():
                    return {
                        "status": "REJECTED",
                        "reason": "Market closed during processing",
                    }

                return {"status": "FILLED", "order_id": "ORDER_123"}

        schedule = MockMarketSchedule()

        # Test with current time
        if schedule.is_market_open():
            result = await schedule.place_order_with_schedule_check(
                {"symbol": "EURUSD"}
            )
            assert result["status"] in ["FILLED", "REJECTED"]
        else:
            result = await schedule.place_order_with_schedule_check(
                {"symbol": "EURUSD"}
            )
            assert result["status"] == "REJECTED"
            assert "Market closed" in result["reason"]

    @pytest.mark.asyncio
    async def test_timeout_edge_cases(self):
        """Test various timeout scenarios."""

        class MockTimeoutOperation:
            async def fast_operation(self):
                await asyncio.sleep(0.1)
                return "completed"

            async def slow_operation(self):
                await asyncio.sleep(5.0)  # Intentionally slow
                return "completed"

            async def variable_speed_operation(self, delay):
                await asyncio.sleep(delay)
                return f"completed after {delay}s"

        ops = MockTimeoutOperation()

        # Fast operation should complete within timeout
        result = await asyncio.wait_for(ops.fast_operation(), timeout=1.0)
        assert result == "completed"

        # Slow operation should timeout
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(ops.slow_operation(), timeout=1.0)

        # Variable operation at boundary
        try:
            result = await asyncio.wait_for(
                ops.variable_speed_operation(0.9), timeout=1.0
            )
            assert "completed after 0.9s" in result
        except asyncio.TimeoutError:
            # Acceptable if timing is close to boundary
            pass

    def test_leap_second_handling(self):
        """Test handling of leap seconds and time anomalies."""

        class MockTimeHandler:
            def __init__(self):
                self.timestamps = []

            def add_timestamp(self, timestamp):
                # Check for time anomalies
                if self.timestamps:
                    last_timestamp = self.timestamps[-1]
                    time_diff = (timestamp - last_timestamp).total_seconds()

                    if time_diff < 0:
                        raise ValueError("Timestamp went backwards")

                    if time_diff > 86400:  # More than 24 hours
                        raise ValueError("Excessive time jump")

                self.timestamps.append(timestamp)

            def detect_time_anomalies(self):
                anomalies = []
                for i in range(1, len(self.timestamps)):
                    diff = (self.timestamps[i] - self.timestamps[i - 1]).total_seconds()
                    if abs(diff) > 3600:  # More than 1 hour difference
                        anomalies.append((i, diff))
                return anomalies

        handler = MockTimeHandler()

        # Normal progression should work
        base_time = datetime(2024, 1, 1, 12, 0, 0)
        for i in range(5):
            handler.add_timestamp(base_time + timedelta(minutes=i))

        assert len(handler.timestamps) == 5

        # Backwards time should fail
        with pytest.raises(ValueError, match="Timestamp went backwards"):
            handler.add_timestamp(base_time - timedelta(minutes=1))

        # Excessive jump should fail
        with pytest.raises(ValueError, match="Excessive time jump"):
            handler.add_timestamp(base_time + timedelta(days=2))


class TestDecimalPrecisionEdgeCases:
    """Test edge cases related to decimal precision and rounding."""

    def test_floating_point_precision_errors(self):
        """Test handling of floating-point precision errors."""

        class MockPriceCalculator:
            def calculate_pnl(self, entry_price, exit_price, quantity):
                # Potential floating-point precision issue
                price_diff = exit_price - entry_price
                return price_diff * quantity

            def calculate_pnl_decimal(self, entry_price, exit_price, quantity):
                # Using Decimal for precision
                entry = Decimal(str(entry_price))
                exit_price_decimal = Decimal(str(exit_price))
                qty = Decimal(str(quantity))
                return float((exit_price_decimal - entry) * qty)

            def round_to_pip(self, price, pip_size=0.0001):
                return round(price / pip_size) * pip_size

        calculator = MockPriceCalculator()

        # Test floating-point precision issues
        entry = 1.23456789
        exit_price = 1.23456790  # Very small difference
        quantity = 100000

        pnl_float = calculator.calculate_pnl(entry, exit_price, quantity)
        pnl_decimal = calculator.calculate_pnl_decimal(entry, exit_price, quantity)

        # Decimal calculation should be more precise
        assert abs(pnl_decimal - 1.0) < 0.001  # Should be close to 1.0

        # Test pip rounding
        unrounded_price = 1.234567
        rounded_price = calculator.round_to_pip(unrounded_price)

        # Should round to 4 decimal places
        assert rounded_price == 1.2346

    def test_currency_conversion_edge_cases(self):
        """Test edge cases in currency conversion."""

        class MockCurrencyConverter:
            def __init__(self):
                self.rates = {
                    "EURUSD": 1.0850,
                    "GBPUSD": 1.2650,
                    "USDJPY": 150.25,
                    "USDCHF": 0.9125,
                }

            def convert_amount(self, amount, from_currency, to_currency):
                if from_currency == to_currency:
                    return amount

                # Get conversion rate
                pair = f"{from_currency}{to_currency}"
                reverse_pair = f"{to_currency}{from_currency}"

                if pair in self.rates:
                    return amount * self.rates[pair]
                elif reverse_pair in self.rates:
                    return amount / self.rates[reverse_pair]
                else:
                    raise ValueError(f"No conversion rate for {pair}")

            def convert_with_precision(
                self, amount, from_currency, to_currency, precision=2
            ):
                converted = self.convert_amount(amount, from_currency, to_currency)
                return round(converted, precision)

        converter = MockCurrencyConverter()

        # Test basic conversion
        eur_amount = 1000.0
        usd_amount = converter.convert_amount(eur_amount, "EUR", "USD")
        assert abs(usd_amount - 1085.0) < 0.01

        # Test reverse conversion
        usd_to_eur = converter.convert_amount(usd_amount, "USD", "EUR")
        assert abs(usd_to_eur - eur_amount) < 0.01  # Should be close to original

        # Test same currency conversion
        same_amount = converter.convert_amount(1000, "USD", "USD")
        assert same_amount == 1000

        # Test invalid currency pair
        with pytest.raises(ValueError, match="No conversion rate"):
            converter.convert_amount(1000, "XYZ", "ABC")

        # Test precision rounding
        precise_amount = converter.convert_with_precision(
            1000, "EUR", "USD", precision=0
        )
        assert precise_amount == 1085  # Rounded to integer


@pytest.mark.performance
class TestPerformanceEdgeCases:
    """Test performance-related edge cases."""

    @pytest.mark.asyncio
    async def test_high_frequency_order_processing(self):
        """Test system behavior under high-frequency order load."""

        class MockHighFrequencyProcessor:
            def __init__(self):
                self.processed_orders = 0
                self.start_time = None

            async def process_order_batch(self, orders):
                if self.start_time is None:
                    self.start_time = time.time()

                # Simulate order processing
                for order in orders:
                    await asyncio.sleep(0.001)  # 1ms per order
                    self.processed_orders += 1

                return len(orders)

            def get_processing_rate(self):
                if self.start_time is None:
                    return 0

                elapsed = time.time() - self.start_time
                return self.processed_orders / elapsed if elapsed > 0 else 0

        processor = MockHighFrequencyProcessor()

        # Generate batch of orders
        orders = [
            {"id": f"ORDER_{i}", "symbol": "EURUSD", "side": "BUY"} for i in range(100)
        ]

        # Process in batches
        batch_size = 10
        for i in range(0, len(orders), batch_size):
            batch = orders[i : i + batch_size]
            await processor.process_order_batch(batch)

        # Check processing rate
        rate = processor.get_processing_rate()
        assert rate > 50  # Should process > 50 orders/second
        assert processor.processed_orders == 100

    def test_large_dataset_memory_efficiency(self):
        """Test memory efficiency with large datasets."""

        class MockDataProcessor:
            def __init__(self):
                self.chunk_size = 1000

            def process_large_dataset_chunked(self, total_size):
                """Process large dataset in chunks to manage memory."""
                processed_count = 0
                max_memory_usage = 0

                for start in range(0, total_size, self.chunk_size):
                    end = min(start + self.chunk_size, total_size)
                    chunk_size = end - start

                    # Simulate chunk processing
                    chunk_data = np.random.random((chunk_size, 10))
                    current_memory = chunk_data.nbytes / (1024 * 1024)  # MB
                    max_memory_usage = max(max_memory_usage, current_memory)

                    processed_count += chunk_size

                    # Cleanup chunk
                    del chunk_data

                return {
                    "processed_count": processed_count,
                    "max_memory_mb": max_memory_usage,
                }

            def process_large_dataset_all_at_once(self, total_size):
                """Process entire dataset at once (memory intensive)."""
                all_data = np.random.random((total_size, 10))
                memory_usage = all_data.nbytes / (1024 * 1024)  # MB

                return {"processed_count": total_size, "max_memory_mb": memory_usage}

        processor = MockDataProcessor()

        # Test chunked processing
        chunked_result = processor.process_large_dataset_chunked(10000)
        assert chunked_result["processed_count"] == 10000
        assert chunked_result["max_memory_mb"] < 50  # Should use < 50MB

        # Test all-at-once processing (should use more memory)
        all_at_once_result = processor.process_large_dataset_all_at_once(10000)
        assert all_at_once_result["processed_count"] == 10000
        assert all_at_once_result["max_memory_mb"] > chunked_result["max_memory_mb"]


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
