#!/usr/bin/env python3
"""
Tests for the timeframe conversion module.
"""

from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd
import pytest

from fxml4.data_engineering.timeframe_conversion import (
    TimeframeConverter,
    combine_timeframes,
    convert_timeframe,
    convert_to_pandas_freq,
    resample_ohlcv,
)


@pytest.fixture
def one_min_df():
    """Create sample 1-minute OHLCV data for testing."""
    # Create sample 1-minute OHLCV data
    start_time = datetime(2025, 3, 1, 10, 0, 0, tzinfo=timezone.utc)

    # Create 60 minutes (1 hour) of 1-minute data
    times = [start_time + timedelta(minutes=i) for i in range(60)]

    # Create price data with some volatility
    closes = [100.0]
    for i in range(1, 60):
        # Random walk with some mean reversion
        step = np.random.normal(0, 0.1)
        mean_reversion = 0.1 * (100.0 - closes[-1])
        closes.append(closes[-1] + step + mean_reversion)

    # Create OHLCV data
    data = []
    for i, time in enumerate(times):
        price = closes[i]
        data.append(
            {
                "timestamp": time,
                "open": price - 0.05,
                "high": price + 0.1,
                "low": price - 0.1,
                "close": price,
                "volume": np.random.randint(100, 1000),
            }
        )

    # Create DataFrame
    df = pd.DataFrame(data)
    df.set_index("timestamp", inplace=True)
    return df


class TestTimeframeConversion:
    """Test the timeframe conversion functions."""

    @pytest.mark.parametrize(
        "input_freq,expected",
        [
            # Minute conversions
            ("1m", "1T"),
            ("5m", "5T"),
            ("15m", "15T"),
            # Hour conversions
            ("1h", "1H"),
            ("4h", "4H"),
            # Day conversions
            ("1d", "1D"),
            # Already pandas format
            ("1T", "1T"),
            ("1H", "1H"),
            ("1D", "1D"),
            # Alternative formats
            ("1min", "1T"),
            ("1hour", "1H"),
            ("1day", "1D"),
        ],
    )
    def test_convert_to_pandas_freq(self, input_freq, expected):
        """Test conversion of timeframe strings to pandas frequency strings."""
        assert convert_to_pandas_freq(input_freq) == expected

    def test_resample_ohlcv(self, one_min_df):
        """Test resampling OHLCV data."""
        # Resample to 5-minute data
        five_min_df = resample_ohlcv(one_min_df, "5T")

        # Check shape
        expected_rows = 60 // 5
        assert len(five_min_df) == expected_rows

        # Check that columns are preserved
        assert list(five_min_df.columns) == ["open", "high", "low", "close", "volume"]

        # Check that first open is same as original first open
        assert five_min_df.iloc[0]["open"] == one_min_df.iloc[0]["open"]

        # Check that high is the max of the period
        for i in range(expected_rows):
            original_slice = one_min_df.iloc[i * 5 : (i + 1) * 5]
            max_high = original_slice["high"].max()
            resampled_high = five_min_df.iloc[i]["high"]
            assert resampled_high == max_high

            # Check volume is sum
            sum_volume = original_slice["volume"].sum()
            resampled_volume = five_min_df.iloc[i]["volume"]
            assert resampled_volume == sum_volume

    def test_convert_timeframe(self, one_min_df):
        """Test converting data between timeframes."""
        # Upsample from 1-minute to 5-minute
        five_min_df = convert_timeframe(one_min_df, "1m", "5m")

        # Check shape
        expected_rows = 60 // 5
        assert len(five_min_df) == expected_rows

        # Downsample from 5-minute to 1-minute
        # Note: This is mostly for testing the function, in practice downsampling
        # isn't as useful for OHLC data
        one_min_from_five = convert_timeframe(five_min_df, "5m", "1m")

        # Should match the original date range but with some interpolated values
        assert len(one_min_from_five) >= 55  # At least 55 rows (orig - 5)

    def test_timeframe_converter_init(self):
        """Test initialization of TimeframeConverter."""
        # Test with default timeframes
        converter = TimeframeConverter()
        assert converter.base_timeframe == "1m"
        assert converter.derived_timeframes == ["5m", "15m", "1h", "4h", "1d"]

        # Test with custom timeframes
        custom_tfs = ["5m", "30m", "2h"]
        converter = TimeframeConverter(
            base_timeframe="1m", derived_timeframes=custom_tfs
        )
        assert converter.base_timeframe == "1m"
        assert converter.derived_timeframes == custom_tfs

    def test_timeframe_converter_update_data(self, one_min_df):
        """Test updating data in the TimeframeConverter."""
        converter = TimeframeConverter(
            base_timeframe="1m", derived_timeframes=["5m", "15m"]
        )

        # Update with 1-minute data
        result = converter.update_data("EURUSD", one_min_df)

        # Should have entries for all timeframes
        assert "1T" in result
        assert "5T" in result
        assert "15T" in result

        # Check that the data was stored in cache
        assert "EURUSD" in converter.cache
        assert "1T" in converter.cache["EURUSD"]
        assert "5T" in converter.cache["EURUSD"]
        assert "15T" in converter.cache["EURUSD"]

        # Check that the derived data has the right shapes
        # 60 minutes of 1m data should give:
        # 60 rows for 1m
        # 12 rows for 5m
        # 4 rows for 15m
        assert len(converter.cache["EURUSD"]["1T"]) == 60
        assert len(converter.cache["EURUSD"]["5T"]) == 12
        assert len(converter.cache["EURUSD"]["15T"]) == 4

    def test_timeframe_converter_get_data(self, one_min_df):
        """Test retrieving data from the TimeframeConverter."""
        converter = TimeframeConverter(
            base_timeframe="1m", derived_timeframes=["5m", "15m"]
        )

        # Add data
        converter.update_data("EURUSD", one_min_df)

        # Get data
        one_min = converter.get_data("EURUSD", "1m")
        five_min = converter.get_data("EURUSD", "5m")
        fifteen_min = converter.get_data("EURUSD", "15m")

        # Check shapes
        assert len(one_min) == 60
        assert len(five_min) == 12
        assert len(fifteen_min) == 4

        # Test time filtering
        start_time = one_min_df.index[10]
        filtered = converter.get_data("EURUSD", "1m", start_time=start_time)
        assert len(filtered) == 50  # 60 - 10

        end_time = one_min_df.index[30]
        filtered = converter.get_data(
            "EURUSD", "1m", start_time=start_time, end_time=end_time
        )
        assert len(filtered) == 21  # 31 - 10

    def test_combine_timeframes(self, one_min_df):
        """Test combining data from multiple timeframes."""
        # Create DataFrames for multiple timeframes
        one_min = one_min_df.copy()

        # Create 5-minute and 15-minute data by resampling
        five_min = resample_ohlcv(one_min, "5T")
        fifteen_min = resample_ohlcv(one_min, "15T")

        # Combine timeframes
        dataframes = {"1m": one_min, "5m": five_min, "15m": fifteen_min}

        result = combine_timeframes("EURUSD", dataframes)

        # Check that we have a combined DataFrame for the base timeframe
        assert "1m" in result

        # Check that the combined DataFrame has columns from all timeframes
        combined_df = result["1m"]
        assert "open" in combined_df.columns  # Base columns
        assert "open_5m" in combined_df.columns  # 5m columns
        assert "open_15m" in combined_df.columns  # 15m columns

        # Check that the combined DataFrame has the same number of rows as the base
        assert len(combined_df) == len(one_min)


# Pytest markers for test categorization
pytestmark = [pytest.mark.unit, pytest.mark.fast]
