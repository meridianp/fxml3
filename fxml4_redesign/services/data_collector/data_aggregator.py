"""Data aggregation utilities for market data."""

from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any, Dict, List

import pandas as pd


class DataAggregator:
    """Aggregate tick data into time-based bars."""

    def aggregate_ticks_to_seconds(self, ticks: List[Dict[str, Any]]) -> List[tuple]:
        """Aggregate ticks into 1-second bars.

        Args:
            ticks: List of tick data

        Returns:
            List of tuples for database insertion
        """
        if not ticks:
            return []

        # Convert to DataFrame
        df = pd.DataFrame(ticks)

        # Convert time to pandas datetime if it's not already
        if "time" in df.columns:
            df["time"] = pd.to_datetime(df["time"])
            df.set_index("time", inplace=True)

        # Group by second
        grouped = df.groupby(pd.Grouper(freq="1S"))

        bars = []
        for time_bucket, group in grouped:
            if group.empty:
                continue

            # Get symbol (should be same for all ticks in group)
            symbol = group["symbol"].iloc[0]

            # Calculate OHLC
            prices = group["price"].astype(float)
            open_price = prices.iloc[0]
            high_price = prices.max()
            low_price = prices.min()
            close_price = prices.iloc[-1]

            # Calculate volume and tick count
            volume = group["size"].sum() if "size" in group.columns else len(group)
            tick_count = len(group)

            bars.append(
                (
                    time_bucket,  # time
                    symbol,  # symbol
                    open_price,  # open
                    high_price,  # high
                    low_price,  # low
                    close_price,  # close
                    volume,  # volume
                    tick_count,  # tick_count
                )
            )

        return bars

    def aggregate_to_timeframe(
        self, data: pd.DataFrame, timeframe: str
    ) -> pd.DataFrame:
        """Aggregate data to specific timeframe.

        Args:
            data: OHLCV DataFrame with datetime index
            timeframe: Target timeframe ('1m', '5m', '15m', '1h', '4h', '1d')

        Returns:
            Aggregated DataFrame
        """
        # Map timeframes to pandas frequency strings
        freq_map = {
            "1m": "1min",
            "5m": "5min",
            "15m": "15min",
            "30m": "30min",
            "1h": "1H",
            "4h": "4H",
            "1d": "1D",
            "1w": "1W",
        }

        if timeframe not in freq_map:
            raise ValueError(f"Unsupported timeframe: {timeframe}")

        freq = freq_map[timeframe]

        # Ensure index is datetime
        if not isinstance(data.index, pd.DatetimeIndex):
            data.index = pd.to_datetime(data.index)

        # Aggregate
        agg_dict = {"open": "first", "high": "max", "low": "min", "close": "last"}

        # Add volume if present
        if "volume" in data.columns:
            agg_dict["volume"] = "sum"

        # Add tick_count if present
        if "tick_count" in data.columns:
            agg_dict["tick_count"] = "sum"

        # Resample
        resampled = data.resample(freq).agg(agg_dict)

        # Drop NaN rows
        resampled = resampled.dropna()

        return resampled

    def calculate_vwap(self, data: pd.DataFrame) -> pd.Series:
        """Calculate Volume Weighted Average Price.

        Args:
            data: OHLCV DataFrame

        Returns:
            VWAP Series
        """
        if "volume" not in data.columns:
            # Use simple average of high, low, close
            return (data["high"] + data["low"] + data["close"]) / 3

        # Typical price
        typical_price = (data["high"] + data["low"] + data["close"]) / 3

        # VWAP calculation
        cumsum_tp_vol = (typical_price * data["volume"]).cumsum()
        cumsum_vol = data["volume"].cumsum()

        vwap = cumsum_tp_vol / cumsum_vol

        return vwap

    def calculate_typical_price(self, data: pd.DataFrame) -> pd.Series:
        """Calculate typical price (HLC/3).

        Args:
            data: OHLC DataFrame

        Returns:
            Typical price Series
        """
        return (data["high"] + data["low"] + data["close"]) / 3

    def detect_gaps(
        self, data: pd.DataFrame, threshold: float = 0.001
    ) -> List[Dict[str, Any]]:
        """Detect price gaps in the data.

        Args:
            data: OHLC DataFrame
            threshold: Minimum gap size as percentage

        Returns:
            List of detected gaps
        """
        gaps = []

        for i in range(1, len(data)):
            prev_close = data["close"].iloc[i - 1]
            curr_open = data["open"].iloc[i]

            gap_size = abs(curr_open - prev_close) / prev_close

            if gap_size > threshold:
                gaps.append(
                    {
                        "time": data.index[i],
                        "prev_close": float(prev_close),
                        "curr_open": float(curr_open),
                        "gap_size": float(gap_size),
                        "gap_type": "up" if curr_open > prev_close else "down",
                    }
                )

        return gaps

    def validate_data_quality(self, data: pd.DataFrame) -> Dict[str, Any]:
        """Validate data quality and return metrics.

        Args:
            data: OHLC DataFrame

        Returns:
            Data quality metrics
        """
        quality = {
            "total_bars": len(data),
            "missing_bars": 0,
            "invalid_bars": 0,
            "zero_volume_bars": 0,
            "wide_spreads": 0,
            "quality_score": 1.0,
        }

        if data.empty:
            quality["quality_score"] = 0.0
            return quality

        # Check for invalid OHLC relationships
        invalid_mask = (
            (data["high"] < data["low"])
            | (data["high"] < data["open"])
            | (data["high"] < data["close"])
            | (data["low"] > data["open"])
            | (data["low"] > data["close"])
        )
        quality["invalid_bars"] = invalid_mask.sum()

        # Check for zero volume (if volume column exists)
        if "volume" in data.columns:
            quality["zero_volume_bars"] = (data["volume"] == 0).sum()

        # Check for wide spreads (potential data errors)
        spread = (data["high"] - data["low"]) / data["close"]
        wide_spread_threshold = 0.01  # 1%
        quality["wide_spreads"] = (spread > wide_spread_threshold).sum()

        # Calculate quality score
        total_issues = (
            quality["invalid_bars"]
            + quality["zero_volume_bars"]
            + quality["wide_spreads"]
        )

        if quality["total_bars"] > 0:
            quality["quality_score"] = max(
                0.0, 1.0 - (total_issues / quality["total_bars"])
            )

        return quality
