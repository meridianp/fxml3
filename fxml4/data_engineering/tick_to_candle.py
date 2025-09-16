"""Tick data to candle conversion module.

This module provides classes and utilities for converting tick data to OHLC candles
of different timeframes, with a focus on 1-minute candles.
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


class CandleBuilder:
    """Builds OHLC candles from tick data."""

    def __init__(self, timeframe_minutes: int = 1):
        """Initialize the candle builder.

        Args:
            timeframe_minutes: Candle timeframe in minutes (default: 1 for 1-minute candles)
        """
        self.timeframe_minutes = timeframe_minutes
        self.timeframe_delta = timedelta(minutes=timeframe_minutes)

        # Current candle data
        self.current_candle: Dict[str, Any] = {}

        # Completed candles storage
        self.completed_candles: List[Dict[str, Any]] = []

        # Symbol tracking
        self.symbols: Dict[str, Dict[str, Any]] = {}

        logger.info(
            f"Initialized CandleBuilder with timeframe: {timeframe_minutes} minutes"
        )

    def add_tick(
        self, symbol: str, timestamp: datetime, price: float, size: float
    ) -> Optional[Dict[str, Any]]:
        """Add a tick to the candle builder and potentially complete a candle.

        Args:
            symbol: Symbol of the tick (e.g., "GBP.USD")
            timestamp: Timestamp of the tick
            price: Price of the tick
            size: Size/volume of the tick

        Returns:
            Completed candle dict if a candle is completed, None otherwise
        """
        # Ensure timestamp is in UTC
        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=timezone.utc)

        # Calculate candle start time (floor to the nearest timeframe_minutes)
        candle_start = timestamp.replace(
            second=0,
            microsecond=0,
            minute=(timestamp.minute // self.timeframe_minutes)
            * self.timeframe_minutes,
        )

        # Check if this is a new symbol or a new candle period
        if (
            symbol not in self.symbols
            or "candle_start" not in self.symbols[symbol]
            or candle_start != self.symbols[symbol]["candle_start"]
        ):
            # We have a new candle starting
            if symbol in self.symbols and "candle_start" in self.symbols[symbol]:
                # Complete the previous candle
                completed_candle = self._complete_candle(symbol)

            # Initialize new candle for this symbol
            self.symbols[symbol] = {
                "candle_start": candle_start,
                "open": price,
                "high": price,
                "low": price,
                "close": price,
                "volume": size if not np.isnan(size) else 0.0,
                "tick_count": 1,
            }

            # Return the completed candle if we had one
            if "completed_candle" in locals():
                return completed_candle

            return None

        # Update the current candle
        candle = self.symbols[symbol]
        candle["high"] = max(candle["high"], price)
        candle["low"] = min(candle["low"], price)
        candle["close"] = price
        candle["volume"] += size if not np.isnan(size) else 0.0
        candle["tick_count"] += 1

        return None

    def _complete_candle(self, symbol: str) -> Dict[str, Any]:
        """Complete the current candle for a symbol.

        Args:
            symbol: Symbol to complete the candle for

        Returns:
            The completed candle
        """
        candle = self.symbols[symbol]

        completed = {
            "symbol": symbol,
            "timestamp": candle["candle_start"],
            "open": candle["open"],
            "high": candle["high"],
            "low": candle["low"],
            "close": candle["close"],
            "volume": candle["volume"],
            "tick_count": candle["tick_count"],
        }

        # Add to completed candles list
        self.completed_candles.append(completed)

        logger.debug(
            f"Completed candle for {symbol} at {candle['candle_start']}: "
            + f"O:{candle['open']:.5f} H:{candle['high']:.5f} L:{candle['low']:.5f} "
            + f"C:{candle['close']:.5f} V:{candle['volume']:.2f}"
        )

        return completed

    def get_current_candle(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Get the current in-progress candle for a symbol.

        Args:
            symbol: Symbol to get the current candle for

        Returns:
            The current candle or None if no candle exists for the symbol
        """
        if symbol not in self.symbols:
            return None

        candle = self.symbols[symbol]
        return {
            "symbol": symbol,
            "timestamp": candle["candle_start"],
            "open": candle["open"],
            "high": candle["high"],
            "low": candle["low"],
            "close": candle["close"],
            "volume": candle["volume"],
            "tick_count": candle["tick_count"],
            "is_complete": False,
        }

    def get_latest_completed_candle(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Get the latest completed candle for a symbol.

        Args:
            symbol: Symbol to get the latest completed candle for

        Returns:
            The latest completed candle or None if no completed candles exist for the symbol
        """
        # Filter candles for the symbol and sort by timestamp (newest first)
        symbol_candles = [c for c in self.completed_candles if c["symbol"] == symbol]

        if not symbol_candles:
            return None

        # Return the most recent candle
        return sorted(symbol_candles, key=lambda x: x["timestamp"], reverse=True)[0]

    def get_completed_candles(
        self, symbol: str, limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Get completed candles for a symbol.

        Args:
            symbol: Symbol to get completed candles for
            limit: Maximum number of candles to return (default: 100)

        Returns:
            List of completed candles, newest first
        """
        # Filter candles for the symbol
        symbol_candles = [c for c in self.completed_candles if c["symbol"] == symbol]

        # Sort by timestamp (newest first) and limit
        return sorted(symbol_candles, key=lambda x: x["timestamp"], reverse=True)[
            :limit
        ]

    def get_completed_candles_as_dataframe(
        self, symbol: str, limit: int = 100
    ) -> pd.DataFrame:
        """Get completed candles for a symbol as a pandas DataFrame.

        Args:
            symbol: Symbol to get completed candles for
            limit: Maximum number of candles to return (default: 100)

        Returns:
            DataFrame of completed candles with timestamp as index
        """
        candles = self.get_completed_candles(symbol, limit)

        if not candles:
            # Return empty DataFrame with correct columns
            return pd.DataFrame(
                columns=[
                    "symbol",
                    "timestamp",
                    "open",
                    "high",
                    "low",
                    "close",
                    "volume",
                    "tick_count",
                ]
            )

        df = pd.DataFrame(candles)
        df = df.set_index("timestamp")
        df = df.sort_index()  # Sort from oldest to newest for time series analysis
        return df

    def clear_candles(self, older_than: Optional[datetime] = None):
        """Clear completed candles, optionally only those older than a specified time.

        Args:
            older_than: If provided, only clear candles older than this time
        """
        if older_than is None:
            self.completed_candles = []
            return

        # Ensure timestamp is in UTC
        if older_than.tzinfo is None:
            older_than = older_than.replace(tzinfo=timezone.utc)

        # Keep only candles newer than the specified time
        self.completed_candles = [
            c for c in self.completed_candles if c["timestamp"] > older_than
        ]

    def force_complete_candles(self) -> List[Dict[str, Any]]:
        """Force completion of all current candles.

        This is useful when the market closes or when we want to ensure all candles are completed.

        Returns:
            List of completed candles
        """
        completed = []

        for symbol in list(self.symbols.keys()):
            completed_candle = self._complete_candle(symbol)
            completed.append(completed_candle)

            # Clear the symbol entry to start fresh
            del self.symbols[symbol]

        return completed


class TickAggregator:
    """Aggregates ticks from different sources and builds candles."""

    def __init__(self, timeframes: List[int] = [1, 5, 15, 60, 240]):
        """Initialize the tick aggregator.

        Args:
            timeframes: List of timeframes in minutes to build candles for
                       (default: [1, 5, 15, 60, 240] for 1m, 5m, 15m, 1h, 4h)
        """
        self.timeframes = timeframes
        # Create a candle builder for each timeframe
        self.candle_builders = {tf: CandleBuilder(tf) for tf in timeframes}

        # Track the last tick time for each symbol
        self.last_tick_time: Dict[str, datetime] = {}

        # Counter for total ticks processed
        self.tick_count = 0

        logger.info(f"Initialized TickAggregator with timeframes: {timeframes} minutes")

    def process_tick(
        self,
        symbol: str,
        timestamp: datetime,
        price: float,
        size: float = np.nan,
        tick_type: str = "trade",
        source: str = "ib",
        store_in_db: bool = False,
    ) -> Dict[int, Optional[Dict[str, Any]]]:
        """Process a tick and update all candle builders.

        Args:
            symbol: Symbol of the tick
            timestamp: Timestamp of the tick
            price: Price of the tick
            size: Size/volume of the tick (default: NaN for price-only ticks)
            tick_type: Type of the tick (default: "trade")
            source: Source of the tick (default: "ib")
            store_in_db: Whether to store the tick in TimescaleDB

        Returns:
            Dictionary mapping timeframe to completed candle (if any)
        """
        self.tick_count += 1

        # Update last tick time
        self.last_tick_time[symbol] = timestamp

        # Store the tick in TimescaleDB if requested
        if store_in_db:
            try:
                from fxml4.config import get_config
                from fxml4.data_engineering.timescaledb import TimescaleDBClient

                # Initialize TimescaleDB client if not already done
                if not hasattr(self, "_timescaledb_client"):
                    # Get TimescaleDB configuration
                    config = get_config()
                    db_config = config.get("database", {})

                    self._timescaledb_client = TimescaleDBClient(
                        host=db_config.get("host", "localhost"),
                        port=db_config.get("port", 5433),
                        dbname=db_config.get("name", "fxml4"),
                        user=db_config.get("user", "postgres"),
                        password=db_config.get("password", "postgres"),
                    )

                # Store the tick
                self._timescaledb_client.store_tick(
                    symbol=symbol,
                    timestamp=timestamp,
                    price=price,
                    size=None if np.isnan(size) else int(size),
                    tick_type=tick_type,
                    source=source,
                )
            except Exception as e:
                logger.error(f"Error storing tick in TimescaleDB: {e}")

        # Process the tick for each timeframe
        completed_candles = {}
        for timeframe, builder in self.candle_builders.items():
            completed_candle = builder.add_tick(symbol, timestamp, price, size)
            if completed_candle:
                completed_candles[timeframe] = completed_candle

        # Log every 1000 ticks
        if self.tick_count % 1000 == 0:
            logger.info(
                f"Processed {self.tick_count} ticks, last symbol: {symbol}, time: {timestamp}"
            )

        return completed_candles

    def get_latest_candle(
        self, symbol: str, timeframe: int = 1, include_current: bool = False
    ) -> Optional[Dict[str, Any]]:
        """Get the latest candle for a symbol and timeframe.

        Args:
            symbol: Symbol to get the latest candle for
            timeframe: Timeframe in minutes
            include_current: Whether to include the current in-progress candle if no completed candle is available

        Returns:
            The latest candle or None if no candle exists
        """
        if timeframe not in self.candle_builders:
            logger.warning(f"Timeframe {timeframe} not found in candle builders")
            return None

        builder = self.candle_builders[timeframe]
        latest = builder.get_latest_completed_candle(symbol)

        if latest is None and include_current:
            return builder.get_current_candle(symbol)

        return latest

    def get_candles(
        self, symbol: str, timeframe: int = 1, limit: int = 100
    ) -> pd.DataFrame:
        """Get candles for a symbol and timeframe.

        Args:
            symbol: Symbol to get candles for
            timeframe: Timeframe in minutes
            limit: Maximum number of candles to return

        Returns:
            DataFrame of candles with timestamp as index
        """
        if timeframe not in self.candle_builders:
            logger.warning(f"Timeframe {timeframe} not found in candle builders")
            return pd.DataFrame()

        return self.candle_builders[timeframe].get_completed_candles_as_dataframe(
            symbol, limit
        )

    def force_complete_all_candles(self) -> Dict[int, List[Dict[str, Any]]]:
        """Force completion of all current candles across all timeframes.

        Returns:
            Dictionary mapping timeframe to list of completed candles
        """
        result = {}
        for timeframe, builder in self.candle_builders.items():
            result[timeframe] = builder.force_complete_candles()

        return result

    def clear_old_candles(self, older_than: datetime):
        """Clear completed candles older than a specified time across all timeframes.

        Args:
            older_than: Clear candles older than this time
        """
        for builder in self.candle_builders.values():
            builder.clear_candles(older_than)

    def get_statistics(self) -> Dict[str, Any]:
        """Get statistics about the tick aggregator.

        Returns:
            Dictionary of statistics
        """
        stats = {
            "total_ticks_processed": self.tick_count,
            "symbols_tracked": list(self.last_tick_time.keys()),
            "timeframes": self.timeframes,
            "candles_per_timeframe": {},
        }

        for timeframe, builder in self.candle_builders.items():
            symbol_counts = {}
            for symbol in stats["symbols_tracked"]:
                candles = builder.get_completed_candles(symbol)
                symbol_counts[symbol] = len(candles)

            stats["candles_per_timeframe"][timeframe] = symbol_counts

        return stats
