"""TDD Tests for OHLC Bar Aggregation.

Tests the conversion of tick data into OHLC (Open, High, Low, Close) bars
for different timeframes following TDD methodology.
"""

import asyncio
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any, Dict, List, Optional

import pytest

from fxml4.api.ohlc_aggregation import OHLCBar, OHLCBarAggregator, TickData, TimeFrame


@pytest.fixture
def ohlc_aggregator():
    """Create OHLC bar aggregator for testing."""
    return OHLCBarAggregator()


@pytest.fixture
def sample_tick_data_1min():
    """Generate sample tick data spanning 1 minute for testing."""
    base_time = datetime(2024, 1, 1, 10, 0, 0)  # Start at exact minute
    ticks = []

    # Generate 60 ticks over 1 minute with varying prices
    prices = [
        1.1000,
        1.1010,
        1.1020,
        1.1015,
        1.1005,
        1.0995,
        1.1025,
        1.1030,
        1.1020,
        1.1010,
    ]

    for i in range(60):
        price = prices[i % len(prices)] + (i * 0.0001)  # Add slight variation
        ticks.append(
            TickData(
                symbol="EURUSD",
                bid=price - 0.0001,
                ask=price + 0.0001,
                timestamp=base_time + timedelta(seconds=i),
            )
        )

    return ticks


@pytest.fixture
def sample_tick_data_5min():
    """Generate sample tick data spanning 5 minutes for testing."""
    base_time = datetime(2024, 1, 1, 10, 0, 0)
    ticks = []

    # Generate 300 ticks over 5 minutes
    for i in range(300):
        minute = i // 60
        price = 1.1000 + (minute * 0.0010) + ((i % 60) * 0.00001)
        ticks.append(
            TickData(
                symbol="EURUSD",
                bid=price - 0.0001,
                ask=price + 0.0001,
                timestamp=base_time + timedelta(seconds=i),
            )
        )

    return ticks


@pytest.fixture
def sample_mixed_symbol_ticks():
    """Generate tick data for multiple symbols."""
    base_time = datetime(2024, 1, 1, 10, 0, 0)
    ticks = []

    symbols_data = {
        "EURUSD": {"base_price": 1.1000, "increment": 0.0001},
        "GBPUSD": {"base_price": 1.2500, "increment": 0.0002},
        "USDJPY": {"base_price": 110.00, "increment": 0.01},
    }

    # Generate interleaved tick data for multiple symbols
    for i in range(180):  # 3 minutes of data
        for symbol, data in symbols_data.items():
            price = data["base_price"] + (i * data["increment"])
            ticks.append(
                TickData(
                    symbol=symbol,
                    bid=price - data["increment"],
                    ask=price + data["increment"],
                    timestamp=base_time + timedelta(seconds=i),
                )
            )

    return ticks


@pytest.mark.asyncio
class TestOHLCBarAggregator:
    """TDD tests for OHLC bar aggregation functionality."""

    async def test_aggregator_initialization(self, ohlc_aggregator):
        """Test OHLC aggregator initializes correctly."""
        assert ohlc_aggregator is not None
        assert len(ohlc_aggregator.active_bars) == 0
        assert len(ohlc_aggregator.completed_bars) == 0

    async def test_single_tick_creates_ohlc_bar(self, ohlc_aggregator):
        """Test single tick data creates a proper OHLC bar."""
        tick = TickData(
            symbol="EURUSD",
            bid=1.1234,
            ask=1.1236,
            timestamp=datetime(2024, 1, 1, 10, 0, 30),  # 30 seconds into minute
        )

        # Process tick for 1-minute bars
        bars = await ohlc_aggregator.process_tick(tick, TimeFrame.ONE_MINUTE)

        # Should create one active bar (not completed yet)
        assert len(bars) == 0  # No completed bars yet
        assert len(ohlc_aggregator.active_bars) == 1

        # Get the active bar
        active_bar_key = (
            "EURUSD",
            TimeFrame.ONE_MINUTE,
            datetime(2024, 1, 1, 10, 0, 0),
        )
        active_bar = ohlc_aggregator.active_bars[active_bar_key]

        # Verify OHLC values (using mid price: (bid + ask) / 2)
        mid_price = (tick.bid + tick.ask) / 2
        assert active_bar.open == mid_price
        assert active_bar.high == mid_price
        assert active_bar.low == mid_price
        assert active_bar.close == mid_price
        assert active_bar.volume == 1

    async def test_multiple_ticks_same_minute_update_ohlc(self, ohlc_aggregator):
        """Test multiple ticks within same minute update OHLC correctly."""
        base_time = datetime(2024, 1, 1, 10, 0, 0)

        # Create ticks with different prices within same minute
        ticks = [
            TickData(
                "EURUSD", 1.1000, 1.1002, base_time + timedelta(seconds=10)
            ),  # Open
            TickData(
                "EURUSD", 1.1020, 1.1022, base_time + timedelta(seconds=20)
            ),  # High
            TickData(
                "EURUSD", 1.0990, 1.0992, base_time + timedelta(seconds=30)
            ),  # Low
            TickData(
                "EURUSD", 1.1010, 1.1012, base_time + timedelta(seconds=50)
            ),  # Close
        ]

        # Process all ticks
        completed_bars = []
        for tick in ticks:
            bars = await ohlc_aggregator.process_tick(tick, TimeFrame.ONE_MINUTE)
            completed_bars.extend(bars)

        # Should still have active bar (minute not complete)
        assert len(completed_bars) == 0
        assert len(ohlc_aggregator.active_bars) == 1

        # Get active bar and verify OHLC values
        active_bar_key = ("EURUSD", TimeFrame.ONE_MINUTE, base_time)
        active_bar = ohlc_aggregator.active_bars[active_bar_key]

        assert active_bar.open == 1.1001  # Mid of first tick
        assert active_bar.high == 1.1021  # Mid of highest tick
        assert active_bar.low == 1.0991  # Mid of lowest tick
        assert active_bar.close == 1.1011  # Mid of last tick
        assert active_bar.volume == 4

    async def test_minute_boundary_completes_bar(self, ohlc_aggregator):
        """Test crossing minute boundary completes the previous bar."""
        # Tick in first minute
        tick1 = TickData("EURUSD", 1.1000, 1.1002, datetime(2024, 1, 1, 10, 0, 30))
        await ohlc_aggregator.process_tick(tick1, TimeFrame.ONE_MINUTE)

        # Tick in next minute should complete previous bar
        tick2 = TickData("EURUSD", 1.1010, 1.1012, datetime(2024, 1, 1, 10, 1, 15))
        completed_bars = await ohlc_aggregator.process_tick(tick2, TimeFrame.ONE_MINUTE)

        # Should complete one bar
        assert len(completed_bars) == 1
        completed_bar = completed_bars[0]

        # Verify completed bar properties
        assert completed_bar.symbol == "EURUSD"
        assert completed_bar.timeframe == TimeFrame.ONE_MINUTE
        assert completed_bar.timestamp == datetime(2024, 1, 1, 10, 0, 0)
        assert completed_bar.open == 1.1001
        assert completed_bar.close == 1.1001
        assert completed_bar.volume == 1

        # Should have new active bar for current minute
        assert len(ohlc_aggregator.active_bars) == 1
        new_bar_key = ("EURUSD", TimeFrame.ONE_MINUTE, datetime(2024, 1, 1, 10, 1, 0))
        assert new_bar_key in ohlc_aggregator.active_bars

    async def test_different_timeframes_simultaneously(self, ohlc_aggregator):
        """Test aggregator can handle different timeframes for same symbol."""
        tick = TickData("EURUSD", 1.1000, 1.1002, datetime(2024, 1, 1, 10, 0, 30))

        # Process same tick for different timeframes
        await ohlc_aggregator.process_tick(tick, TimeFrame.ONE_MINUTE)
        await ohlc_aggregator.process_tick(tick, TimeFrame.FIVE_MINUTE)
        await ohlc_aggregator.process_tick(tick, TimeFrame.ONE_HOUR)

        # Should have active bars for all timeframes
        assert len(ohlc_aggregator.active_bars) == 3

        # Verify all timeframes have bars
        expected_keys = [
            ("EURUSD", TimeFrame.ONE_MINUTE, datetime(2024, 1, 1, 10, 0, 0)),
            ("EURUSD", TimeFrame.FIVE_MINUTE, datetime(2024, 1, 1, 10, 0, 0)),
            ("EURUSD", TimeFrame.ONE_HOUR, datetime(2024, 1, 1, 10, 0, 0)),
        ]

        for key in expected_keys:
            assert key in ohlc_aggregator.active_bars

    async def test_multiple_symbols_handled_separately(
        self, ohlc_aggregator, sample_mixed_symbol_ticks
    ):
        """Test aggregator handles multiple symbols independently."""
        # Process mixed symbol tick data
        for tick in sample_mixed_symbol_ticks:
            await ohlc_aggregator.process_tick(tick, TimeFrame.ONE_MINUTE)

        # Should have separate active bars for each symbol
        symbols_found = set()
        for key in ohlc_aggregator.active_bars.keys():
            symbols_found.add(key[0])  # First element is symbol

        expected_symbols = {"EURUSD", "GBPUSD", "USDJPY"}
        assert symbols_found == expected_symbols

        # Each symbol should have its own bar data
        for symbol in expected_symbols:
            symbol_keys = [
                key for key in ohlc_aggregator.active_bars.keys() if key[0] == symbol
            ]
            assert len(symbol_keys) > 0

    async def test_five_minute_bar_aggregation(
        self, ohlc_aggregator, sample_tick_data_5min
    ):
        """Test 5-minute bar aggregation works correctly."""
        completed_bars = []

        # Process 5 minutes of tick data
        for tick in sample_tick_data_5min:
            bars = await ohlc_aggregator.process_tick(tick, TimeFrame.FIVE_MINUTE)
            completed_bars.extend(bars)

        # Add one more tick to complete the 5-minute bar
        final_tick = TickData(
            "EURUSD",
            1.1500,
            1.1502,
            datetime(2024, 1, 1, 10, 5, 0),  # Start of next 5-minute period
        )
        bars = await ohlc_aggregator.process_tick(final_tick, TimeFrame.FIVE_MINUTE)
        completed_bars.extend(bars)

        # Should complete one 5-minute bar
        assert len(completed_bars) == 1
        bar = completed_bars[0]

        assert bar.timeframe == TimeFrame.FIVE_MINUTE
        assert bar.timestamp == datetime(2024, 1, 1, 10, 0, 0)
        assert bar.volume == 300  # All ticks in 5-minute period

    async def test_bar_timestamp_alignment(self, ohlc_aggregator):
        """Test bars are aligned to proper time boundaries."""
        test_cases = [
            # 1-minute bars should align to minute boundaries
            {
                "timeframe": TimeFrame.ONE_MINUTE,
                "tick_time": datetime(2024, 1, 1, 10, 15, 37),
                "expected_bar_time": datetime(2024, 1, 1, 10, 15, 0),
            },
            # 5-minute bars should align to 5-minute boundaries
            {
                "timeframe": TimeFrame.FIVE_MINUTE,
                "tick_time": datetime(2024, 1, 1, 10, 17, 22),
                "expected_bar_time": datetime(2024, 1, 1, 10, 15, 0),
            },
            # 1-hour bars should align to hour boundaries
            {
                "timeframe": TimeFrame.ONE_HOUR,
                "tick_time": datetime(2024, 1, 1, 10, 37, 44),
                "expected_bar_time": datetime(2024, 1, 1, 10, 0, 0),
            },
        ]

        for case in test_cases:
            aggregator = OHLCBarAggregator()  # Fresh aggregator for each test

            tick = TickData("EURUSD", 1.1000, 1.1002, case["tick_time"])
            await aggregator.process_tick(tick, case["timeframe"])

            # Find the active bar for this case
            bar_key = None
            for key in aggregator.active_bars.keys():
                if key[1] == case["timeframe"]:  # Match timeframe
                    bar_key = key
                    break

            assert bar_key is not None
            assert bar_key[2] == case["expected_bar_time"]  # Check timestamp alignment

    async def test_ohlc_bar_data_integrity(self, ohlc_aggregator):
        """Test OHLC bar data maintains mathematical consistency."""
        base_time = datetime(2024, 1, 1, 10, 0, 0)

        # Create ticks with known price progression
        tick_prices = [1.1000, 1.1050, 1.0950, 1.1075, 1.0925, 1.1025]  # Varied prices
        ticks = []

        for i, price in enumerate(tick_prices):
            ticks.append(
                TickData(
                    "EURUSD",
                    price - 0.0001,
                    price + 0.0001,
                    base_time + timedelta(seconds=i * 10),
                )
            )

        # Process ticks
        for tick in ticks:
            await ohlc_aggregator.process_tick(tick, TimeFrame.ONE_MINUTE)

        # Get active bar
        active_bar_key = ("EURUSD", TimeFrame.ONE_MINUTE, base_time)
        bar = ohlc_aggregator.active_bars[active_bar_key]

        # Verify OHLC mathematical consistency
        assert bar.high >= bar.open  # High >= Open
        assert bar.high >= bar.close  # High >= Close
        assert bar.low <= bar.open  # Low <= Open
        assert bar.low <= bar.close  # Low <= Close
        assert bar.high >= bar.low  # High >= Low

        # Verify specific values based on our test data
        expected_open = 1.1000  # First price
        expected_close = 1.1025  # Last price
        expected_high = 1.1075  # Highest price
        expected_low = 0.9925  # Lowest price (1.0925 - 0.0001 for bid)

        assert abs(bar.open - expected_open) < 0.0001
        assert abs(bar.close - expected_close) < 0.0001
        assert abs(bar.high - expected_high) < 0.0001

    async def test_volume_accumulation(self, ohlc_aggregator):
        """Test volume is accumulated correctly across ticks."""
        base_time = datetime(2024, 1, 1, 10, 0, 0)

        # Process 10 ticks in same minute
        for i in range(10):
            tick = TickData(
                "EURUSD",
                1.1000 + (i * 0.0001),
                1.1002 + (i * 0.0001),
                base_time + timedelta(seconds=i * 5),
            )
            await ohlc_aggregator.process_tick(tick, TimeFrame.ONE_MINUTE)

        # Check volume accumulation
        active_bar_key = ("EURUSD", TimeFrame.ONE_MINUTE, base_time)
        bar = ohlc_aggregator.active_bars[active_bar_key]

        assert bar.volume == 10  # Should have accumulated all 10 ticks

    async def test_get_completed_bars_by_timeframe(self, ohlc_aggregator):
        """Test retrieval of completed bars by timeframe."""
        # Create bars that will be completed immediately
        base_time = datetime(2024, 1, 1, 10, 0, 0)

        # Add tick in first minute
        tick1 = TickData("EURUSD", 1.1000, 1.1002, base_time + timedelta(seconds=30))
        await ohlc_aggregator.process_tick(tick1, TimeFrame.ONE_MINUTE)
        await ohlc_aggregator.process_tick(tick1, TimeFrame.FIVE_MINUTE)

        # Add tick in second minute to complete first minute bar
        tick2 = TickData(
            "EURUSD", 1.1010, 1.1012, base_time + timedelta(minutes=1, seconds=30)
        )
        bars_1min = await ohlc_aggregator.process_tick(tick2, TimeFrame.ONE_MINUTE)
        bars_5min = await ohlc_aggregator.process_tick(
            tick2, TimeFrame.FIVE_MINUTE
        )  # Won't complete yet

        # Should have completed 1-minute bar
        assert len(bars_1min) == 1
        assert len(bars_5min) == 0

        # Test retrieval methods
        completed_1min_bars = ohlc_aggregator.get_completed_bars(
            TimeFrame.ONE_MINUTE, "EURUSD"
        )
        completed_5min_bars = ohlc_aggregator.get_completed_bars(
            TimeFrame.FIVE_MINUTE, "EURUSD"
        )

        assert len(completed_1min_bars) == 1
        assert len(completed_5min_bars) == 0

        assert completed_1min_bars[0].timeframe == TimeFrame.ONE_MINUTE


if __name__ == "__main__":
    """Run OHLC bar aggregation tests."""
    pytest.main([__file__, "-v"])
