"""
TimescaleDB integration for FXML4.

This module provides functionality for interacting with TimescaleDB
for storing and retrieving market data at different timeframes.
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np
import pandas as pd
import psycopg2
from psycopg2.extensions import connection as PgConnection
from psycopg2.extras import DictCursor, execute_values

logger = logging.getLogger(__name__)


class TimescaleDBClient:
    """Client for interacting with TimescaleDB."""

    def __init__(
        self,
        host: str = "localhost",
        port: int = 5432,
        dbname: str = "fxml4",
        user: str = "postgres",
        password: str = "postgres",
        autocommit: bool = False,
        pool_size: int = 5,
    ):
        """
        Initialize the TimescaleDB client.

        Args:
            host: Database host
            port: Database port
            dbname: Database name
            user: Database user
            password: Database password
            autocommit: Whether to enable autocommit
            pool_size: Connection pool size
        """
        self.host = host
        self.port = port
        self.dbname = dbname
        self.user = user
        self.password = password
        self.autocommit = autocommit

        # Connection parameters
        self.conn_params = {
            "host": host,
            "port": port,
            "dbname": dbname,
            "user": user,
            "password": password,
        }

        # Connection pool (lazy initialization)
        self._pool = None
        self.pool_size = pool_size

        logger.info(f"Initialized TimescaleDB client for {dbname} at {host}:{port}")

    def get_connection(self) -> PgConnection:
        """
        Get a database connection.

        Returns:
            Database connection
        """
        # For simplicity, create a new connection each time
        # In a production environment, you would use a connection pool
        conn = psycopg2.connect(**self.conn_params)

        if self.autocommit:
            conn.set_session(autocommit=True)

        return conn

    def store_tick(
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
            conn = self.get_connection()
            cursor = conn.cursor()

            # Ensure timestamp is timezone-aware
            if timestamp.tzinfo is None:
                timestamp = timestamp.replace(tzinfo=timezone.utc)

            # Insert the tick
            cursor.execute(
                """
                INSERT INTO tick_data (time, symbol, price, size, tick_type, source)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (time, symbol, tick_type) DO UPDATE
                SET price = EXCLUDED.price, size = EXCLUDED.size, source = EXCLUDED.source
                """,
                (timestamp, symbol, price, size, tick_type, source),
            )

            conn.commit()
            cursor.close()
            conn.close()

            return True

        except Exception as e:
            logger.error(f"Error storing tick: {e}")
            return False

    def store_ticks(self, ticks: List[Dict[str, Any]]) -> int:
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
            conn = self.get_connection()
            cursor = conn.cursor()

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
                        tick.get("size"),  # Optional
                        tick.get("tick_type", "trade"),
                        tick.get("source", "ib"),
                    )
                )

            # Use execute_values for efficient batch insertion
            execute_values(
                cursor,
                """
                INSERT INTO tick_data (time, symbol, price, size, tick_type, source)
                VALUES %s
                ON CONFLICT (time, symbol, tick_type) DO UPDATE
                SET price = EXCLUDED.price, size = EXCLUDED.size, source = EXCLUDED.source
                """,
                data,
            )

            conn.commit()
            cursor.close()
            conn.close()

            return len(ticks)

        except Exception as e:
            logger.error(f"Error storing ticks: {e}")
            return 0

    def store_candle(
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
            conn = self.get_connection()
            cursor = conn.cursor()

            # Ensure timestamp is timezone-aware
            if timestamp.tzinfo is None:
                timestamp = timestamp.replace(tzinfo=timezone.utc)

            # Round timestamp to the start of the minute
            timestamp = timestamp.replace(second=0, microsecond=0)

            # Insert the candle
            cursor.execute(
                """
                INSERT INTO market_data_1m (time, symbol, open, high, low, close, volume, tick_count, source)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (time, symbol) DO UPDATE
                SET open = EXCLUDED.open,
                    high = EXCLUDED.high,
                    low = EXCLUDED.low,
                    close = EXCLUDED.close,
                    volume = EXCLUDED.volume,
                    tick_count = EXCLUDED.tick_count,
                    source = EXCLUDED.source
                """,
                (
                    timestamp,
                    symbol,
                    open_price,
                    high_price,
                    low_price,
                    close_price,
                    volume,
                    tick_count,
                    source,
                ),
            )

            conn.commit()
            cursor.close()
            conn.close()

            return True

        except Exception as e:
            logger.error(f"Error storing candle: {e}")
            return False

    def store_candles(self, candles: List[Dict[str, Any]]) -> int:
        """
        Store multiple 1-minute candles in the database.

        Args:
            candles: List of candle dictionaries with keys:
                    symbol, timestamp, open, high, low, close, volume, tick_count (optional), source (optional)

        Returns:
            Number of candles stored successfully
        """
        if not candles:
            return 0

        try:
            conn = self.get_connection()
            cursor = conn.cursor()

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

            # Use execute_values for efficient batch insertion
            execute_values(
                cursor,
                """
                INSERT INTO market_data_1m (time, symbol, open, high, low, close, volume, tick_count, source)
                VALUES %s
                ON CONFLICT (time, symbol) DO UPDATE
                SET open = EXCLUDED.open,
                    high = EXCLUDED.high,
                    low = EXCLUDED.low,
                    close = EXCLUDED.close,
                    volume = EXCLUDED.volume,
                    tick_count = EXCLUDED.tick_count,
                    source = EXCLUDED.source
                """,
                data,
            )

            conn.commit()
            cursor.close()
            conn.close()

            return len(candles)

        except Exception as e:
            logger.error(f"Error storing candles: {e}")
            return 0

    def get_latest_tick(
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
            conn = self.get_connection()
            cursor = conn.cursor(cursor_factory=DictCursor)

            # Use the get_latest_tick function
            cursor.execute("SELECT * FROM get_latest_tick(%s, %s)", (symbol, tick_type))

            result = cursor.fetchone()
            cursor.close()
            conn.close()

            if result:
                return dict(result)

            return None

        except Exception as e:
            logger.error(f"Error getting latest tick: {e}")
            return None

    def get_ohlcv_data(
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
            conn = self.get_connection()
            cursor = conn.cursor()

            # Ensure timestamps are timezone-aware
            if start_time.tzinfo is None:
                start_time = start_time.replace(tzinfo=timezone.utc)
            if end_time.tzinfo is None:
                end_time = end_time.replace(tzinfo=timezone.utc)

            # Use the get_ohlcv function
            cursor.execute(
                "SELECT * FROM get_ohlcv(%s, %s, %s, %s)",
                (symbol, timeframe, start_time, end_time),
            )

            # Fetch results
            columns = [desc[0] for desc in cursor.description]
            data = cursor.fetchall()

            cursor.close()
            conn.close()

            # Convert to DataFrame
            df = pd.DataFrame(data, columns=columns)

            if not df.empty:
                # Set timestamp as index
                df.set_index("time", inplace=True)

                # Sort by timestamp
                df = df.sort_index()

            return df

        except Exception as e:
            logger.error(f"Error getting OHLCV data: {e}")
            return pd.DataFrame()

    def get_latest_candle(
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
            conn = self.get_connection()

            # Determine the table name based on the timeframe
            table_name = f"market_data_{timeframe}"

            # For views, the time column is called 'bucket'
            time_column = "time" if timeframe == "1m" else "bucket"

            with conn.cursor(cursor_factory=DictCursor) as cursor:
                # Get the latest candle
                query = f"""
                SELECT * FROM {table_name}
                WHERE symbol = %s
                ORDER BY {time_column} DESC
                LIMIT 1
                """

                cursor.execute(query, (symbol,))
                result = cursor.fetchone()

            conn.close()

            if result:
                return dict(result)

            return None

        except Exception as e:
            logger.error(f"Error getting latest candle: {e}")
            return None

    def get_tick_count(
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
            conn = self.get_connection()
            cursor = conn.cursor()

            # Build the query
            query = "SELECT COUNT(*) FROM tick_data"
            params = []

            conditions = []
            if symbol:
                conditions.append("symbol = %s")
                params.append(symbol)

            if start_time:
                # Ensure timestamp is timezone-aware
                if start_time.tzinfo is None:
                    start_time = start_time.replace(tzinfo=timezone.utc)
                conditions.append("time >= %s")
                params.append(start_time)

            if end_time:
                # Ensure timestamp is timezone-aware
                if end_time.tzinfo is None:
                    end_time = end_time.replace(tzinfo=timezone.utc)
                conditions.append("time <= %s")
                params.append(end_time)

            if conditions:
                query += " WHERE " + " AND ".join(conditions)

            # Execute the query
            cursor.execute(query, params)
            count = cursor.fetchone()[0]

            cursor.close()
            conn.close()

            return count

        except Exception as e:
            logger.error(f"Error getting tick count: {e}")
            return 0

    def get_candle_count(
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
            conn = self.get_connection()
            cursor = conn.cursor()

            # Determine the table name based on the timeframe
            table_name = f"market_data_{timeframe}"

            # For views, the time column is called 'bucket'
            time_column = "time" if timeframe == "1m" else "bucket"

            # Build the query
            query = f"SELECT COUNT(*) FROM {table_name}"
            params = []

            conditions = []
            if symbol:
                conditions.append("symbol = %s")
                params.append(symbol)

            if start_time:
                # Ensure timestamp is timezone-aware
                if start_time.tzinfo is None:
                    start_time = start_time.replace(tzinfo=timezone.utc)
                conditions.append(f"{time_column} >= %s")
                params.append(start_time)

            if end_time:
                # Ensure timestamp is timezone-aware
                if end_time.tzinfo is None:
                    end_time = end_time.replace(tzinfo=timezone.utc)
                conditions.append(f"{time_column} <= %s")
                params.append(end_time)

            if conditions:
                query += " WHERE " + " AND ".join(conditions)

            # Execute the query
            cursor.execute(query, params)
            count = cursor.fetchone()[0]

            cursor.close()
            conn.close()

            return count

        except Exception as e:
            logger.error(f"Error getting candle count: {e}")
            return 0
