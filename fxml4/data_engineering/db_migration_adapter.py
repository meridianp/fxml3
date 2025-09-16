"""
Database Migration Adapter for FXML4.

This module provides a compatibility layer to help migrate from
synchronous psycopg2 code to async asyncpg code.
"""

import asyncio
import logging
from contextlib import contextmanager
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Union

import pandas as pd

from .async_pool import close_pool, get_pool
from .async_timescaledb import AsyncTimescaleDBClient
from .timescaledb import TimescaleDBClient

logger = logging.getLogger(__name__)


class SyncToAsyncAdapter:
    """
    Adapter that provides a synchronous interface to async database operations.

    This allows gradual migration from sync to async code by wrapping
    async operations in a sync interface.
    """

    def __init__(self, async_client: AsyncTimescaleDBClient):
        """
        Initialize the adapter.

        Args:
            async_client: The async client to wrap
        """
        self.async_client = async_client
        self._loop = None

    def _get_loop(self) -> asyncio.AbstractEventLoop:
        """Get or create an event loop."""
        if self._loop is None or self._loop.is_closed():
            try:
                self._loop = asyncio.get_running_loop()
            except RuntimeError:
                # No running loop, create a new one
                self._loop = asyncio.new_event_loop()
                asyncio.set_event_loop(self._loop)
        return self._loop

    def _run_async(self, coro):
        """Run an async coroutine and return the result."""
        loop = self._get_loop()

        # If we're already in an async context, use create_task
        if asyncio.iscoroutinefunction(coro) or asyncio.iscoroutine(coro):
            if loop.is_running():
                # We're in an async context, schedule the coroutine
                future = asyncio.ensure_future(coro, loop=loop)
                # This is a simplified approach - in production you might want
                # to use a thread pool executor
                import concurrent.futures

                with concurrent.futures.ThreadPoolExecutor() as executor:
                    return executor.submit(asyncio.run, coro).result()
            else:
                # We're in a sync context, run the coroutine
                return loop.run_until_complete(coro)
        return coro

    def store_tick(
        self,
        symbol: str,
        timestamp: datetime,
        price: float,
        size: Optional[int] = None,
        tick_type: str = "trade",
        source: str = "ib",
    ) -> bool:
        """Store a tick (sync wrapper)."""
        return self._run_async(
            self.async_client.store_tick(
                symbol, timestamp, price, size, tick_type, source
            )
        )

    def store_ticks(self, ticks: List[Dict[str, Any]]) -> int:
        """Store multiple ticks (sync wrapper)."""
        return self._run_async(self.async_client.store_ticks(ticks))

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
        """Store a candle (sync wrapper)."""
        return self._run_async(
            self.async_client.store_candle(
                symbol,
                timestamp,
                open_price,
                high_price,
                low_price,
                close_price,
                volume,
                tick_count,
                source,
            )
        )

    def store_candles(self, candles: List[Dict[str, Any]]) -> int:
        """Store multiple candles (sync wrapper)."""
        return self._run_async(self.async_client.store_candles(candles))

    def get_latest_tick(
        self, symbol: str, tick_type: str = "trade"
    ) -> Optional[Dict[str, Any]]:
        """Get latest tick (sync wrapper)."""
        return self._run_async(self.async_client.get_latest_tick(symbol, tick_type))

    def get_ohlcv_data(
        self, symbol: str, timeframe: str, start_time: datetime, end_time: datetime
    ) -> pd.DataFrame:
        """Get OHLCV data (sync wrapper)."""
        return self._run_async(
            self.async_client.get_ohlcv_data(symbol, timeframe, start_time, end_time)
        )

    def get_latest_candle(
        self, symbol: str, timeframe: str
    ) -> Optional[Dict[str, Any]]:
        """Get latest candle (sync wrapper)."""
        return self._run_async(self.async_client.get_latest_candle(symbol, timeframe))

    def get_tick_count(
        self,
        symbol: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
    ) -> int:
        """Get tick count (sync wrapper)."""
        return self._run_async(
            self.async_client.get_tick_count(symbol, start_time, end_time)
        )

    def get_candle_count(
        self,
        timeframe: str,
        symbol: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
    ) -> int:
        """Get candle count (sync wrapper)."""
        return self._run_async(
            self.async_client.get_candle_count(timeframe, symbol, start_time, end_time)
        )


class MigrationHelper:
    """
    Helper class to facilitate migration from sync to async database code.
    """

    @staticmethod
    def create_compatible_client(
        use_async: bool = False, **kwargs
    ) -> Union[TimescaleDBClient, SyncToAsyncAdapter]:
        """
        Create a database client with sync interface.

        Args:
            use_async: If True, use async client with sync adapter.
                      If False, use original sync client.
            **kwargs: Arguments to pass to the client constructor

        Returns:
            Database client with synchronous interface
        """
        if use_async:
            # Create async client wrapped in sync adapter
            async_client = AsyncTimescaleDBClient()
            return SyncToAsyncAdapter(async_client)
        else:
            # Use original sync client
            return TimescaleDBClient(**kwargs)

    @staticmethod
    def migrate_connection_params(old_params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Convert old connection parameters to new format.

        Args:
            old_params: Old-style connection parameters

        Returns:
            New-style connection parameters
        """
        new_params = {
            "host": old_params.get("host", "localhost"),
            "port": old_params.get("port", 5432),
            "database": old_params.get("dbname", old_params.get("database", "fxml4")),
            "user": old_params.get("user", "postgres"),
            "password": old_params.get("password", "postgres"),
        }

        # Map pool_size to min/max connections
        pool_size = old_params.get("pool_size", 5)
        new_params["min_connections"] = max(1, pool_size // 2)
        new_params["max_connections"] = pool_size * 2

        return new_params

    @staticmethod
    async def migrate_to_async(sync_function: Callable, *args, **kwargs) -> Any:
        """
        Helper to run synchronous database code in an async context.

        Args:
            sync_function: Synchronous function to run
            *args: Positional arguments
            **kwargs: Keyword arguments

        Returns:
            Function result
        """
        # Run sync function in thread pool to avoid blocking
        import concurrent.futures

        loop = asyncio.get_event_loop()
        with concurrent.futures.ThreadPoolExecutor() as executor:
            result = await loop.run_in_executor(
                executor, sync_function, *args, **kwargs
            )
        return result


# Context manager for backward compatibility
@contextmanager
def get_db_connection(**kwargs):
    """
    Get a database connection using the appropriate client.

    This provides backward compatibility for code expecting
    a context manager that returns a connection.
    """
    # Check if we should use async
    use_async = kwargs.pop("use_async", False)

    if use_async:
        # For async, we need to handle this differently
        raise NotImplementedError(
            "Async connections require async context manager. "
            "Use 'async with get_async_db_client() as client:' instead."
        )
    else:
        # Use sync client
        client = TimescaleDBClient(**kwargs)
        conn = client.get_connection()
        try:
            yield conn
        finally:
            conn.close()


async def get_async_db_client(**kwargs) -> AsyncTimescaleDBClient:
    """
    Get an async database client.

    Args:
        **kwargs: Connection parameters (optional)

    Returns:
        AsyncTimescaleDBClient instance
    """
    pool = await get_pool(kwargs if kwargs else None)
    return AsyncTimescaleDBClient(pool)


# Example migration functions
def example_sync_code():
    """Example of original synchronous code."""
    client = TimescaleDBClient()

    # Store a tick
    client.store_tick(symbol="EURUSD", timestamp=datetime.now(), price=1.0850)

    # Get latest tick
    tick = client.get_latest_tick("EURUSD")
    print(f"Latest tick: {tick}")


async def example_async_code():
    """Example of migrated asynchronous code."""
    async with await get_async_db_client() as client:
        # Store a tick
        await client.store_tick(symbol="EURUSD", timestamp=datetime.now(), price=1.0850)

        # Get latest tick
        tick = await client.get_latest_tick("EURUSD")
        print(f"Latest tick: {tick}")


def example_compatible_code():
    """Example using compatibility layer."""
    # This works with both sync and async backends
    client = MigrationHelper.create_compatible_client(use_async=True)

    # Store a tick (looks synchronous but uses async internally)
    client.store_tick(symbol="EURUSD", timestamp=datetime.now(), price=1.0850)

    # Get latest tick
    tick = client.get_latest_tick("EURUSD")
    print(f"Latest tick: {tick}")
