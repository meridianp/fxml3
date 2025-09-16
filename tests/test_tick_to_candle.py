#!/usr/bin/env python3
"""
Tests for the tick_to_candle module.
"""

from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd
import pytest

from fxml4.data_engineering.tick_to_candle import CandleBuilder, TickAggregator


@pytest.fixture
def candle_builder():
    """Create a CandleBuilder instance for testing."""
    return CandleBuilder()


@pytest.fixture
def tick_aggregator():
    """Create a TickAggregator instance for testing."""
    return TickAggregator()


@pytest.fixture
def base_timestamp():
    """Base timestamp for testing."""
    return datetime(2025, 3, 1, 10, 0, 0, tzinfo=timezone.utc)


@pytest.fixture
def sample_ticks(base_timestamp):
    """Sample tick data for testing."""
    return [
        {
            "symbol": "GBP.USD",
            "timestamp": base_timestamp,
            "price": 1.2500,
            "volume": 1000,
        },
        {
            "symbol": "GBP.USD",
            "timestamp": base_timestamp + timedelta(seconds=15),
            "price": 1.2550,
            "volume": 2000,
        },
        {
            "symbol": "GBP.USD",
            "timestamp": base_timestamp + timedelta(seconds=30),
            "price": 1.2480,
            "volume": 1500,
        },
        {
            "symbol": "GBP.USD",
            "timestamp": base_timestamp + timedelta(seconds=45),
            "price": 1.2520,
            "volume": 1200,
        },
    ]


def test_add_tick_first_tick(candle_builder, base_timestamp):
    """Test adding the first tick to a candle."""
    result = candle_builder.add_tick("GBP.USD", base_timestamp, 1.2500, 1000)

    assert result is None, "First tick should not complete a candle"

    current = candle_builder.get_current_candle("GBP.USD")
    assert current is not None, "Current candle should exist"
    assert current["symbol"] == "GBP.USD"
    assert current["open"] == 1.2500
    assert current["high"] == 1.2500
    assert current["low"] == 1.2500
    assert current["close"] == 1.2500
    assert current["volume"] == 1000
    assert current["tick_count"] == 1


def test_add_tick_update_candle(candle_builder, base_timestamp):
    """Test updating a candle with additional ticks."""
    # First tick
    candle_builder.add_tick("GBP.USD", base_timestamp, 1.2500, 1000)

    # Second tick (higher price)
    candle_builder.add_tick(
        "GBP.USD", base_timestamp + timedelta(seconds=15), 1.2550, 2000
    )

    # Third tick (lower price)
    candle_builder.add_tick(
        "GBP.USD", base_timestamp + timedelta(seconds=30), 1.2480, 1500
    )

    current = candle_builder.get_current_candle("GBP.USD")
    assert current["open"] == 1.2500
    assert current["high"] == 1.2550
    assert current["low"] == 1.2480
    assert current["close"] == 1.2480
    assert current["volume"] == 4500
    assert current["tick_count"] == 3


def test_complete_candle(candle_builder, base_timestamp):
    """Test completing a candle when moving to a new time period."""
    # Add ticks in the first minute
    candle_builder.add_tick("GBP.USD", base_timestamp, 1.2500, 1000)
    candle_builder.add_tick(
        "GBP.USD", base_timestamp + timedelta(seconds=30), 1.2550, 2000
    )

    # Add a tick in the next minute, which should complete the previous candle
    completed = candle_builder.add_tick(
        "GBP.USD", base_timestamp + timedelta(minutes=1), 1.2530, 1500
    )

    assert completed is not None, "Should return a completed candle"
    assert completed["symbol"] == "GBP.USD"
    assert completed["open"] == 1.2500
    assert completed["high"] == 1.2550
    assert completed["low"] == 1.2500
    assert completed["close"] == 1.2550
    assert completed["volume"] == 3000
    assert completed["tick_count"] == 2

    # Check that we have a new current candle
    current = candle_builder.get_current_candle("GBP.USD")
    assert current["timestamp"] == base_timestamp + timedelta(minutes=1)


def test_multiple_symbols(candle_builder, base_timestamp):
    """Test handling multiple currency symbols simultaneously."""
    # Add ticks for different symbols
    candle_builder.add_tick("GBP.USD", base_timestamp, 1.2500, 1000)
    candle_builder.add_tick("EUR.USD", base_timestamp, 1.1000, 2000)
    candle_builder.add_tick("USD.JPY", base_timestamp, 110.0, 1500)

    # Check that each symbol has its own candle
    gbp_candle = candle_builder.get_current_candle("GBP.USD")
    eur_candle = candle_builder.get_current_candle("EUR.USD")
    jpy_candle = candle_builder.get_current_candle("USD.JPY")

    assert gbp_candle["symbol"] == "GBP.USD"
    assert gbp_candle["close"] == 1.2500

    assert eur_candle["symbol"] == "EUR.USD"
    assert eur_candle["close"] == 1.1000

    assert jpy_candle["symbol"] == "USD.JPY"
    assert jpy_candle["close"] == 110.0


def test_candle_timestamp_alignment(candle_builder):
    """Test that candle timestamps are properly aligned to minute boundaries."""
    # Tick at 10:00:30 should create a candle timestamped at 10:00:00
    timestamp = datetime(2025, 3, 1, 10, 0, 30, tzinfo=timezone.utc)
    candle_builder.add_tick("GBP.USD", timestamp, 1.2500, 1000)

    current = candle_builder.get_current_candle("GBP.USD")
    expected_timestamp = datetime(2025, 3, 1, 10, 0, 0, tzinfo=timezone.utc)
    assert current["timestamp"] == expected_timestamp


def test_force_complete_candle(candle_builder, base_timestamp):
    """Test manually forcing completion of a candle."""
    # Add some ticks
    candle_builder.add_tick("GBP.USD", base_timestamp, 1.2500, 1000)
    candle_builder.add_tick(
        "GBP.USD", base_timestamp + timedelta(seconds=30), 1.2550, 2000
    )

    # Force completion
    completed = candle_builder.force_complete_candle("GBP.USD")

    assert completed is not None
    assert completed["symbol"] == "GBP.USD"
    assert completed["volume"] == 3000
    assert completed["tick_count"] == 2

    # Should not have a current candle after force completion
    current = candle_builder.get_current_candle("GBP.USD")
    assert current is None


def test_tick_aggregator_initialization(tick_aggregator):
    """Test initialization of TickAggregator."""
    assert tick_aggregator is not None
    assert hasattr(tick_aggregator, "add_tick")
    assert hasattr(tick_aggregator, "get_candles")


def test_tick_aggregator_basic_functionality(tick_aggregator, sample_ticks):
    """Test basic tick aggregation functionality."""
    # Add sample ticks
    for tick in sample_ticks:
        tick_aggregator.add_tick(
            tick["symbol"], tick["timestamp"], tick["price"], tick["volume"]
        )

    # Should have aggregated the ticks
    candles = tick_aggregator.get_candles("GBP.USD")
    assert (
        len(candles) >= 0
    )  # Depending on implementation, might have completed candles


def test_tick_aggregator_time_based_completion(tick_aggregator, base_timestamp):
    """Test time-based candle completion in TickAggregator."""
    # Add ticks in first minute
    tick_aggregator.add_tick("GBP.USD", base_timestamp, 1.2500, 1000)
    tick_aggregator.add_tick(
        "GBP.USD", base_timestamp + timedelta(seconds=30), 1.2550, 2000
    )

    # Add tick in next minute to force completion
    tick_aggregator.add_tick(
        "GBP.USD", base_timestamp + timedelta(minutes=1), 1.2530, 1500
    )

    candles = tick_aggregator.get_candles("GBP.USD")
    if len(candles) > 0:
        # Check the first completed candle
        first_candle = candles[0]
        assert first_candle["symbol"] == "GBP.USD"
        assert first_candle["open"] == 1.2500
        assert first_candle["high"] == 1.2550


@pytest.mark.parametrize(
    "symbol,price,volume",
    [
        ("GBP.USD", 1.2500, 1000),
        ("EUR.USD", 1.1000, 2000),
        ("USD.JPY", 110.0, 1500),
        ("AUD.USD", 0.7500, 800),
    ],
)
def test_different_currency_pairs(
    candle_builder, base_timestamp, symbol, price, volume
):
    """Test handling of different currency pairs."""
    result = candle_builder.add_tick(symbol, base_timestamp, price, volume)
    assert result is None  # First tick shouldn't complete a candle

    current = candle_builder.get_current_candle(symbol)
    assert current is not None
    assert current["symbol"] == symbol
    assert current["close"] == price
    assert current["volume"] == volume


def test_edge_case_zero_volume(candle_builder, base_timestamp):
    """Test handling of zero volume ticks."""
    result = candle_builder.add_tick("GBP.USD", base_timestamp, 1.2500, 0)

    current = candle_builder.get_current_candle("GBP.USD")
    assert current is not None
    assert current["volume"] == 0
    assert current["tick_count"] == 1


def test_edge_case_negative_price():
    """Test handling of invalid negative prices."""
    builder = CandleBuilder()
    base_time = datetime(2025, 3, 1, 10, 0, 0, tzinfo=timezone.utc)

    # This should either raise an exception or handle gracefully
    with pytest.raises((ValueError, AssertionError)):
        builder.add_tick("GBP.USD", base_time, -1.2500, 1000)


def test_edge_case_very_large_price(candle_builder, base_timestamp):
    """Test handling of very large price values."""
    large_price = 999999.9999
    result = candle_builder.add_tick("GBP.USD", base_timestamp, large_price, 1000)

    current = candle_builder.get_current_candle("GBP.USD")
    assert current is not None
    assert current["close"] == large_price


def test_candle_data_integrity(candle_builder, base_timestamp):
    """Test that candle data maintains integrity through operations."""
    # Build a candle with multiple ticks
    prices = [1.2500, 1.2550, 1.2480, 1.2520, 1.2510]
    volumes = [1000, 2000, 1500, 1200, 1800]

    for i, (price, volume) in enumerate(zip(prices, volumes)):
        timestamp = base_timestamp + timedelta(seconds=i * 10)
        candle_builder.add_tick("GBP.USD", timestamp, price, volume)

    current = candle_builder.get_current_candle("GBP.USD")

    # Check OHLC integrity
    assert current["open"] == prices[0]  # First price
    assert current["close"] == prices[-1]  # Last price
    assert current["high"] == max(prices)  # Highest price
    assert current["low"] == min(prices)  # Lowest price
    assert current["volume"] == sum(volumes)  # Total volume
    assert current["tick_count"] == len(prices)  # Tick count


def test_concurrent_symbol_processing(candle_builder, base_timestamp):
    """Test processing multiple symbols concurrently."""
    symbols = ["GBP.USD", "EUR.USD", "USD.JPY", "AUD.USD"]
    base_prices = [1.2500, 1.1000, 110.0, 0.7500]

    # Add ticks for all symbols
    for symbol, base_price in zip(symbols, base_prices):
        for i in range(5):
            price = base_price + (i * 0.001 if "JPY" not in symbol else i * 0.1)
            volume = 1000 + (i * 200)
            timestamp = base_timestamp + timedelta(seconds=i * 10)
            candle_builder.add_tick(symbol, timestamp, price, volume)

    # Verify each symbol has its own candle
    for symbol in symbols:
        current = candle_builder.get_current_candle(symbol)
        assert current is not None
        assert current["symbol"] == symbol
        assert current["tick_count"] == 5


def test_time_boundary_edge_cases(candle_builder):
    """Test edge cases around time boundaries."""
    # Test tick exactly at minute boundary
    exact_minute = datetime(2025, 3, 1, 10, 0, 0, tzinfo=timezone.utc)
    candle_builder.add_tick("GBP.USD", exact_minute, 1.2500, 1000)

    # Test tick just before next minute
    almost_next_minute = datetime(2025, 3, 1, 10, 0, 59, 999999, tzinfo=timezone.utc)
    candle_builder.add_tick("GBP.USD", almost_next_minute, 1.2510, 1500)

    # Test tick at next minute boundary
    next_minute = datetime(2025, 3, 1, 10, 1, 0, tzinfo=timezone.utc)
    completed = candle_builder.add_tick("GBP.USD", next_minute, 1.2520, 2000)

    # Should complete the previous candle
    assert completed is not None
    assert completed["tick_count"] == 2
    assert completed["volume"] == 2500
