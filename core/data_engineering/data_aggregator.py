"""Data aggregation utilities for FXML4.

This module provides functionality for aggregating market data across
different timeframes and sources.
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Union

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


class DataAggregator:
    """Handles aggregation of market data across timeframes and sources."""

    def __init__(self):
        """Initialize the data aggregator."""
        self.timeframe_mapping = {
            "1m": timedelta(minutes=1),
            "5m": timedelta(minutes=5),
            "15m": timedelta(minutes=15),
            "30m": timedelta(minutes=30),
            "1h": timedelta(hours=1),
            "4h": timedelta(hours=4),
            "1d": timedelta(days=1),
            "1w": timedelta(weeks=1),
            "1M": timedelta(days=30),  # Approximate
        }

    def aggregate_ohlcv(
        self,
        data: pd.DataFrame,
        source_timeframe: str,
        target_timeframe: str,
        method: str = "standard",
    ) -> pd.DataFrame:
        """Aggregate OHLCV data from one timeframe to another.

        Args:
            data: DataFrame with OHLCV data and datetime index
            source_timeframe: Source timeframe (e.g., '1m')
            target_timeframe: Target timeframe (e.g., '1h')
            method: Aggregation method ('standard', 'weighted')

        Returns:
            Aggregated DataFrame
        """
        logger.info(
            "Aggregating data from %s to %s using %s method",
            source_timeframe,
            target_timeframe,
            method,
        )

        if source_timeframe not in self.timeframe_mapping:
            raise ValueError(f"Unsupported source timeframe: {source_timeframe}")
        if target_timeframe not in self.timeframe_mapping:
            raise ValueError(f"Unsupported target timeframe: {target_timeframe}")

        source_delta = self.timeframe_mapping[source_timeframe]
        target_delta = self.timeframe_mapping[target_timeframe]

        if source_delta >= target_delta:
            raise ValueError("Target timeframe must be larger than source timeframe")

        # Ensure datetime index
        if not isinstance(data.index, pd.DatetimeIndex):
            data = data.copy()
            data.index = pd.to_datetime(data.index)

        # Resample based on target timeframe
        resampler = data.resample(self._get_resample_rule(target_timeframe))

        if method == "standard":
            aggregated = resampler.agg(
                {
                    "open": "first",
                    "high": "max",
                    "low": "min",
                    "close": "last",
                    "volume": "sum",
                }
            ).dropna()
        elif method == "weighted":
            # Volume-weighted aggregation
            aggregated = self._volume_weighted_aggregation(data, resampler)
        else:
            raise ValueError(f"Unsupported aggregation method: {method}")

        logger.info("Aggregated %d candles to %d candles", len(data), len(aggregated))

        return aggregated

    def merge_data_sources(
        self,
        sources: Dict[str, pd.DataFrame],
        priority_order: Optional[List[str]] = None,
        method: str = "priority",
    ) -> pd.DataFrame:
        """Merge data from multiple sources.

        Args:
            sources: Dictionary mapping source names to DataFrames
            priority_order: List of source names in priority order
            method: Merge method ('priority', 'average', 'weighted')

        Returns:
            Merged DataFrame
        """
        if not sources:
            raise ValueError("No data sources provided")

        logger.info("Merging %d data sources using %s method", len(sources), method)

        # Default priority order
        if priority_order is None:
            priority_order = list(sources.keys())

        # Validate priority order
        for source in priority_order:
            if source not in sources:
                raise ValueError(f"Source '{source}' not found in provided data")

        if method == "priority":
            return self._merge_by_priority(sources, priority_order)
        elif method == "average":
            return self._merge_by_average(sources)
        elif method == "weighted":
            return self._merge_by_weighted_average(sources)
        else:
            raise ValueError(f"Unsupported merge method: {method}")

    def calculate_vwap(
        self, data: pd.DataFrame, period: Optional[int] = None
    ) -> pd.Series:
        """Calculate Volume-Weighted Average Price (VWAP).

        Args:
            data: DataFrame with OHLCV data
            period: Number of periods for rolling VWAP (None for cumulative)

        Returns:
            VWAP series
        """
        typical_price = (data["high"] + data["low"] + data["close"]) / 3
        volume = data["volume"]

        if period is None:
            # Cumulative VWAP
            cumulative_volume = volume.cumsum()
            cumulative_pv = (typical_price * volume).cumsum()
            vwap = cumulative_pv / cumulative_volume
        else:
            # Rolling VWAP
            rolling_volume = volume.rolling(window=period).sum()
            rolling_pv = (typical_price * volume).rolling(window=period).sum()
            vwap = rolling_pv / rolling_volume

        return vwap

    def aggregate_tick_data(
        self,
        ticks: pd.DataFrame,
        timeframe: str,
        price_column: str = "price",
        volume_column: str = "size",
    ) -> pd.DataFrame:
        """Aggregate tick data into OHLCV candles.

        Args:
            ticks: DataFrame with tick data
            timeframe: Target timeframe
            price_column: Name of price column
            volume_column: Name of volume column

        Returns:
            OHLCV DataFrame
        """
        if timeframe not in self.timeframe_mapping:
            raise ValueError(f"Unsupported timeframe: {timeframe}")

        # Ensure datetime index
        if not isinstance(ticks.index, pd.DatetimeIndex):
            ticks = ticks.copy()
            ticks.index = pd.to_datetime(ticks.index)

        # Resample ticks
        rule = self._get_resample_rule(timeframe)
        resampler = ticks.resample(rule)

        ohlcv = pd.DataFrame(
            {
                "open": resampler[price_column].first(),
                "high": resampler[price_column].max(),
                "low": resampler[price_column].min(),
                "close": resampler[price_column].last(),
                "volume": resampler[volume_column].sum(),
            }
        ).dropna()

        return ohlcv

    def _get_resample_rule(self, timeframe: str) -> str:
        """Convert timeframe to pandas resample rule."""
        mapping = {
            "1m": "1T",
            "5m": "5T",
            "15m": "15T",
            "30m": "30T",
            "1h": "1H",
            "4h": "4H",
            "1d": "1D",
            "1w": "1W",
            "1M": "1M",
        }
        return mapping.get(timeframe, timeframe)

    def _volume_weighted_aggregation(
        self, data: pd.DataFrame, resampler
    ) -> pd.DataFrame:
        """Perform volume-weighted aggregation."""

        def vwap_agg(group):
            if len(group) == 0 or group["volume"].sum() == 0:
                return pd.Series(
                    {
                        "open": np.nan,
                        "high": np.nan,
                        "low": np.nan,
                        "close": np.nan,
                        "volume": 0,
                    }
                )

            total_volume = group["volume"].sum()
            vwap = (group["close"] * group["volume"]).sum() / total_volume

            return pd.Series(
                {
                    "open": group["open"].iloc[0],
                    "high": group["high"].max(),
                    "low": group["low"].min(),
                    "close": vwap,  # Use VWAP as close
                    "volume": total_volume,
                }
            )

        return resampler.apply(vwap_agg).dropna()

    def _merge_by_priority(
        self, sources: Dict[str, pd.DataFrame], priority_order: List[str]
    ) -> pd.DataFrame:
        """Merge data sources by priority, filling gaps from lower priority sources."""
        result = sources[priority_order[0]].copy()

        for source_name in priority_order[1:]:
            source_data = sources[source_name]
            # Fill missing values with data from lower priority source
            for column in ["open", "high", "low", "close", "volume"]:
                if column in result.columns and column in source_data.columns:
                    result[column] = result[column].fillna(source_data[column])

        return result

    def _merge_by_average(self, sources: Dict[str, pd.DataFrame]) -> pd.DataFrame:
        """Merge data sources by averaging values."""
        # Align all dataframes to common index
        aligned_data = {}
        all_indices = pd.Index([])

        for name, df in sources.items():
            all_indices = all_indices.union(df.index)

        for name, df in sources.items():
            aligned_data[name] = df.reindex(all_indices)

        # Calculate average for each column
        result = pd.DataFrame(index=all_indices)

        for column in ["open", "high", "low", "close", "volume"]:
            column_data = []
            for name, df in aligned_data.items():
                if column in df.columns:
                    column_data.append(df[column])

            if column_data:
                result[column] = pd.concat(column_data, axis=1).mean(axis=1)

        return result.dropna()

    def _merge_by_weighted_average(
        self,
        sources: Dict[str, pd.DataFrame],
        weights: Optional[Dict[str, float]] = None,
    ) -> pd.DataFrame:
        """Merge data sources using weighted average."""
        if weights is None:
            # Equal weights
            weights = {name: 1.0 / len(sources) for name in sources}

        # Normalize weights
        total_weight = sum(weights.values())
        weights = {k: v / total_weight for k, v in weights.items()}

        # Align all dataframes
        aligned_data = {}
        all_indices = pd.Index([])

        for name, df in sources.items():
            all_indices = all_indices.union(df.index)

        for name, df in sources.items():
            aligned_data[name] = df.reindex(all_indices)

        # Calculate weighted average
        result = pd.DataFrame(index=all_indices)

        for column in ["open", "high", "low", "close", "volume"]:
            weighted_sum = pd.Series(0, index=all_indices, dtype=float)
            weight_sum = pd.Series(0, index=all_indices, dtype=float)

            for name, df in aligned_data.items():
                if column in df.columns and name in weights:
                    mask = ~df[column].isna()
                    weighted_sum[mask] += df[column][mask] * weights[name]
                    weight_sum[mask] += weights[name]

            result[column] = weighted_sum / weight_sum.replace(0, np.nan)

        return result.dropna()
