"""
Async TimescaleDB Client for FXML4.

This module provides an async version of the TimescaleDB client
using asyncpg and connection pooling.
"""

import logging
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np
import pandas as pd

from .async_pool import AsyncConnectionPool, get_pool

logger = logging.getLogger(__name__)


class AsyncTimescaleDBClient:
    """Async client for interacting with TimescaleDB."""

    def __init__(self, pool: Optional[AsyncConnectionPool] = None):
        """
        Initialize the async TimescaleDB client.

        Args:
            pool: Optional connection pool instance. If not provided,
                  will use the global pool.
        """
        self._pool = pool
        self._own_pool = pool is None

    async def __aenter__(self):
        """Async context manager entry."""
        if self._pool is None:
            self._pool = await get_pool()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        # Don't close the pool if we didn't create it
        pass

    @property
    async def pool(self) -> AsyncConnectionPool:
        """Get the connection pool."""
        if self._pool is None:
            self._pool = await get_pool()
        return self._pool

    async def store_tick(
        self,
        symbol: str,
        timestamp: datetime,
        price: float,
        size: Optional[int] = None,
        tick_type: str = "trade",
        source: str = "ib",
    ) -> bool:
        """
        Store a tick in the database.

        Args:
            symbol: Trading symbol
            timestamp: Timestamp of the tick
            price: Price of the tick
            size: Size/volume of the tick (optional)
            tick_type: Type of the tick (default: "trade")
            source: Source of the tick (default: "ib")

        Returns:
            True if successful, False otherwise
        """
        try:
            pool = await self.pool

            # Ensure timestamp is timezone-aware
            if timestamp.tzinfo is None:
                timestamp = timestamp.replace(tzinfo=timezone.utc)

            await pool.execute(
                """
                INSERT INTO tick_data (time, symbol, price, size, tick_type, source)
                VALUES ($1, $2, $3, $4, $5, $6)
                ON CONFLICT (time, symbol, tick_type) DO UPDATE
                SET price = EXCLUDED.price, size = EXCLUDED.size, source = EXCLUDED.source
                """,
                timestamp,
                symbol,
                price,
                size,
                tick_type,
                source,
            )

            return True

        except Exception as e:
            logger.error(f"Error storing tick: {e}")
            return False

    async def store_ticks(self, ticks: List[Dict[str, Any]]) -> int:
        """
        Store multiple ticks in the database.

        Args:
            ticks: List of tick dictionaries with keys:
                  symbol, timestamp, price, size (optional), tick_type, source

        Returns:
            Number of ticks stored successfully
        """
        if not ticks:
            return 0

        try:
            pool = await self.pool

            # Prepare data for batch insertion
            data = []
            for tick in ticks:
                # Ensure timestamp is timezone-aware
                timestamp = tick["timestamp"]
                if timestamp.tzinfo is None:
                    timestamp = timestamp.replace(tzinfo=timezone.utc)

                data.append(
                    (
                        timestamp,
                        tick["symbol"],
                        tick["price"],
                        tick.get("size"),
                        tick.get("tick_type", "trade"),
                        tick.get("source", "ib"),
                    )
                )

            # Use copy_records_to_table for efficient batch insertion
            await pool.copy_records_to_table(
                "tick_data",
                records=data,
                columns=["time", "symbol", "price", "size", "tick_type", "source"],
            )

            return len(ticks)

        except Exception as e:
            logger.error(f"Error storing ticks: {e}")
            return 0

    async def store_candle(
        self,
        symbol: str,
        timestamp: datetime,
        open_price: float,
        high_price: float,
        low_price: float,
        close_price: float,
        volume: int,
        tick_count: int = 0,
        source: str = "ib",
    ) -> bool:
        """
        Store a 1-minute candle in the database.

        Args:
            symbol: Trading symbol
            timestamp: Timestamp of the candle (start of the 1-minute period)
            open_price: Opening price
            high_price: Highest price
            low_price: Lowest price
            close_price: Closing price
            volume: Volume
            tick_count: Number of ticks in the candle (default: 0)
            source: Source of the candle (default: "ib")

        Returns:
            True if successful, False otherwise
        """
        try:
            pool = await self.pool

            # Ensure timestamp is timezone-aware
            if timestamp.tzinfo is None:
                timestamp = timestamp.replace(tzinfo=timezone.utc)

            # Round timestamp to the start of the minute
            timestamp = timestamp.replace(second=0, microsecond=0)

            await pool.execute(
                """
                INSERT INTO market_data_1m (time, symbol, open, high, low, close, volume, tick_count, source)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                ON CONFLICT (time, symbol) DO UPDATE
                SET open = EXCLUDED.open,
                    high = EXCLUDED.high,
                    low = EXCLUDED.low,
                    close = EXCLUDED.close,
                    volume = EXCLUDED.volume,
                    tick_count = EXCLUDED.tick_count,
                    source = EXCLUDED.source
                """,
                timestamp,
                symbol,
                open_price,
                high_price,
                low_price,
                close_price,
                volume,
                tick_count,
                source,
            )

            return True

        except Exception as e:
            logger.error(f"Error storing candle: {e}")
            return False

    async def store_candles(self, candles: List[Dict[str, Any]]) -> int:
        """
        Store multiple 1-minute candles in the database.

        Args:
            candles: List of candle dictionaries with keys:
                    symbol, timestamp, open, high, low, close, volume,
                    tick_count (optional), source (optional)

        Returns:
            Number of candles stored successfully
        """
        if not candles:
            return 0

        try:
            pool = await self.pool

            # Prepare data for batch insertion
            data = []
            for candle in candles:
                # Ensure timestamp is timezone-aware
                timestamp = candle["timestamp"]
                if timestamp.tzinfo is None:
                    timestamp = timestamp.replace(tzinfo=timezone.utc)

                # Round timestamp to the start of the minute
                timestamp = timestamp.replace(second=0, microsecond=0)

                data.append(
                    (
                        timestamp,
                        candle["symbol"],
                        candle["open"],
                        candle["high"],
                        candle["low"],
                        candle["close"],
                        candle["volume"],
                        candle.get("tick_count", 0),
                        candle.get("source", "ib"),
                    )
                )

            # Use copy_records_to_table for efficient batch insertion
            await pool.copy_records_to_table(
                "market_data_1m",
                records=data,
                columns=[
                    "time",
                    "symbol",
                    "open",
                    "high",
                    "low",
                    "close",
                    "volume",
                    "tick_count",
                    "source",
                ],
            )

            return len(candles)

        except Exception as e:
            logger.error(f"Error storing candles: {e}")
            return 0

    async def get_latest_tick(
        self, symbol: str, tick_type: str = "trade"
    ) -> Optional[Dict[str, Any]]:
        """
        Get the latest tick for a symbol.

        Args:
            symbol: Trading symbol
            tick_type: Type of the tick (default: "trade")

        Returns:
            Dictionary with tick data or None if not found
        """
        try:
            pool = await self.pool

            # Use the get_latest_tick function
            result = await pool.fetchrow(
                "SELECT * FROM get_latest_tick($1, $2)", symbol, tick_type
            )

            if result:
                return dict(result)

            return None

        except Exception as e:
            logger.error(f"Error getting latest tick: {e}")
            return None

    async def get_ohlcv_data(
        self, symbol: str, timeframe: str, start_time: datetime, end_time: datetime
    ) -> pd.DataFrame:
        """
        Get OHLCV data for a symbol and timeframe.

        Args:
            symbol: Trading symbol
            timeframe: Timeframe (e.g., "1m", "5m", "15m", "1h", "4h", "1d")
            start_time: Start time
            end_time: End time

        Returns:
            DataFrame with OHLCV data
        """
        try:
            pool = await self.pool

            # Ensure timestamps are timezone-aware
            if start_time.tzinfo is None:
                start_time = start_time.replace(tzinfo=timezone.utc)
            if end_time.tzinfo is None:
                end_time = end_time.replace(tzinfo=timezone.utc)

            # Use the get_ohlcv function
            rows = await pool.fetch(
                "SELECT * FROM get_ohlcv($1, $2, $3, $4)",
                symbol,
                timeframe,
                start_time,
                end_time,
            )

            # Convert to DataFrame
            if rows:
                df = pd.DataFrame([dict(row) for row in rows])

                # Set timestamp as index
                df.set_index("time", inplace=True)

                # Sort by timestamp
                df = df.sort_index()
            else:
                df = pd.DataFrame()

            return df

        except Exception as e:
            logger.error(f"Error getting OHLCV data: {e}")
            return pd.DataFrame()

    async def get_latest_candle(
        self, symbol: str, timeframe: str
    ) -> Optional[Dict[str, Any]]:
        """
        Get the latest candle for a symbol and timeframe.

        Args:
            symbol: Trading symbol
            timeframe: Timeframe (e.g., "1m", "5m", "15m", "1h", "4h", "1d")

        Returns:
            Dictionary with candle data or None if not found
        """
        try:
            pool = await self.pool

            # Determine the table name based on the timeframe
            table_name = f"market_data_{timeframe}"

            # For views, the time column is called 'bucket'
            time_column = "time" if timeframe == "1m" else "bucket"

            # Get the latest candle
            query = f"""
            SELECT * FROM {table_name}
            WHERE symbol = $1
            ORDER BY {time_column} DESC
            LIMIT 1
            """

            result = await pool.fetchrow(query, symbol)

            if result:
                return dict(result)

            return None

        except Exception as e:
            logger.error(f"Error getting latest candle: {e}")
            return None

    async def get_tick_count(
        self,
        symbol: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
    ) -> int:
        """
        Get the count of ticks in the database.

        Args:
            symbol: Trading symbol (optional, filters by symbol if provided)
            start_time: Start time (optional, filters by time if provided)
            end_time: End time (optional, filters by time if provided)

        Returns:
            Count of ticks
        """
        try:
            pool = await self.pool

            # Build the query
            query = "SELECT COUNT(*) FROM tick_data"
            params = []

            conditions = []
            if symbol:
                conditions.append(f"symbol = ${len(params) + 1}")
                params.append(symbol)

            if start_time:
                # Ensure timestamp is timezone-aware
                if start_time.tzinfo is None:
                    start_time = start_time.replace(tzinfo=timezone.utc)
                conditions.append(f"time >= ${len(params) + 1}")
                params.append(start_time)

            if end_time:
                # Ensure timestamp is timezone-aware
                if end_time.tzinfo is None:
                    end_time = end_time.replace(tzinfo=timezone.utc)
                conditions.append(f"time <= ${len(params) + 1}")
                params.append(end_time)

            if conditions:
                query += " WHERE " + " AND ".join(conditions)

            # Execute the query
            count = await pool.fetchval(query, *params)

            return count or 0

        except Exception as e:
            logger.error(f"Error getting tick count: {e}")
            return 0

    async def get_candle_count(
        self,
        timeframe: str,
        symbol: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
    ) -> int:
        """
        Get the count of candles in the database.

        Args:
            timeframe: Timeframe (e.g., "1m", "5m", "15m", "1h", "4h", "1d")
            symbol: Trading symbol (optional, filters by symbol if provided)
            start_time: Start time (optional, filters by time if provided)
            end_time: End time (optional, filters by time if provided)

        Returns:
            Count of candles
        """
        try:
            pool = await self.pool

            # Determine the table name based on the timeframe
            table_name = f"market_data_{timeframe}"

            # For views, the time column is called 'bucket'
            time_column = "time" if timeframe == "1m" else "bucket"

            # Build the query
            query = f"SELECT COUNT(*) FROM {table_name}"
            params = []

            conditions = []
            if symbol:
                conditions.append(f"symbol = ${len(params) + 1}")
                params.append(symbol)

            if start_time:
                # Ensure timestamp is timezone-aware
                if start_time.tzinfo is None:
                    start_time = start_time.replace(tzinfo=timezone.utc)
                conditions.append(f"{time_column} >= ${len(params) + 1}")
                params.append(start_time)

            if end_time:
                # Ensure timestamp is timezone-aware
                if end_time.tzinfo is None:
                    end_time = end_time.replace(tzinfo=timezone.utc)
                conditions.append(f"{time_column} <= ${len(params) + 1}")
                params.append(end_time)

            if conditions:
                query += " WHERE " + " AND ".join(conditions)

            # Execute the query
            count = await pool.fetchval(query, *params)

            return count or 0

        except Exception as e:
            logger.error(f"Error getting candle count: {e}")
            return 0

    async def execute_query(self, query: str, *args) -> Any:
        """Execute a custom query."""
        pool = await self.pool
        return await pool.execute(query, *args)

    async def fetch_query(self, query: str, *args) -> List[Dict[str, Any]]:
        """Fetch results from a custom query."""
        pool = await self.pool
        rows = await pool.fetch(query, *args)
        return [dict(row) for row in rows]

    async def fetchrow_query(self, query: str, *args) -> Optional[Dict[str, Any]]:
        """Fetch a single row from a custom query."""
        pool = await self.pool
        row = await pool.fetchrow(query, *args)
        return dict(row) if row else None

    async def fetchval_query(self, query: str, *args) -> Any:
        """Fetch a single value from a custom query."""
        pool = await self.pool
        return await pool.fetchval(query, *args)

    @asynccontextmanager
    async def transaction(self):
        """Create a transaction context."""
        pool = await self.pool
        async with pool.transaction():
            yield self
