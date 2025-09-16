"""
Database connection pool manager for FXML4.
Performance target: <20 active DB connections for 100+ concurrent requests
"""

import asyncio
import logging
import time
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, Optional

import asyncpg

logger = logging.getLogger(__name__)


@dataclass
class PoolStats:
    """Connection pool statistics."""

    size: int
    idle: int
    acquiring: int
    acquired: int
    max_size: int
    min_size: int
    total_requests: int
    avg_acquisition_time: float
    peak_usage: int
    connection_timeouts: int


class DatabasePoolManager:
    """
    High-performance database connection pool manager.

    Manages connection pooling with monitoring, health checks, and optimization
    for high-concurrency trading system workloads.
    """

    def __init__(
        self,
        host: str = "localhost",
        port: int = 5432,
        database: str = "fxml4",
        user: str = "postgres",
        password: str = "postgres",
        min_size: int = 5,
        max_size: int = 20,
        max_queries: int = 50000,
        max_inactive_connection_lifetime: float = 300.0,
        timeout: float = 10.0,
        command_timeout: float = 30.0,
    ):

        self.connection_params = {
            "host": host,
            "port": port,
            "database": database,
            "user": user,
            "password": password,
        }

        self.min_size = min_size
        self.max_size = max_size
        self.max_queries = max_queries
        self.max_inactive_connection_lifetime = max_inactive_connection_lifetime
        self.timeout = timeout
        self.command_timeout = command_timeout

        self._pool: Optional[asyncpg.Pool] = None
        self._stats = {
            "total_requests": 0,
            "acquisition_times": [],
            "peak_usage": 0,
            "connection_timeouts": 0,
            "created_at": datetime.utcnow(),
        }

    async def initialize(self) -> None:
        """Initialize the connection pool."""
        try:
            logger.info(
                f"Initializing database pool: min={self.min_size}, max={self.max_size}"
            )

            self._pool = await asyncpg.create_pool(
                **self.connection_params,
                min_size=self.min_size,
                max_size=self.max_size,
                max_queries=self.max_queries,
                max_inactive_connection_lifetime=self.max_inactive_connection_lifetime,
                timeout=self.timeout,
                command_timeout=self.command_timeout,
                init=self._init_connection,
                setup=self._setup_connection,
            )

            logger.info("Database pool initialized successfully")
            await self.health_check()

        except Exception as e:
            logger.error(f"Failed to initialize database pool: {e}")
            raise

    async def _init_connection(self, conn: asyncpg.Connection) -> None:
        """Initialize individual connection settings."""
        # Set connection-specific settings for optimal performance
        await conn.execute("SET timezone TO 'UTC'")
        await conn.execute("SET statement_timeout TO '30s'")
        await conn.execute("SET lock_timeout TO '10s'")
        await conn.execute("SET idle_in_transaction_session_timeout TO '60s'")

    async def _setup_connection(self, conn: asyncpg.Connection) -> None:
        """Set up connection with custom type codecs if needed."""
        # Add any custom type mappings here
        pass

    @asynccontextmanager
    async def acquire(self):
        """
        Acquire a connection from the pool with performance monitoring.

        Tracks acquisition time and connection usage for optimization.
        """
        if not self._pool:
            await self.initialize()

        start_time = time.perf_counter()
        connection = None

        try:
            # Acquire connection with timeout handling
            connection = await asyncio.wait_for(
                self._pool.acquire(), timeout=self.timeout
            )

            # Track statistics
            acquisition_time = time.perf_counter() - start_time
            self._stats["total_requests"] += 1
            self._stats["acquisition_times"].append(acquisition_time)

            # Keep only recent acquisition times for moving average
            if len(self._stats["acquisition_times"]) > 1000:
                self._stats["acquisition_times"] = self._stats["acquisition_times"][
                    -500:
                ]

            # Track peak usage
            current_usage = self.get_pool_size() - self.get_idle_size()
            if current_usage > self._stats["peak_usage"]:
                self._stats["peak_usage"] = current_usage

            yield connection

        except asyncio.TimeoutError:
            self._stats["connection_timeouts"] += 1
            logger.warning(f"Connection acquisition timed out after {self.timeout}s")
            raise
        except Exception as e:
            logger.error(f"Error acquiring connection: {e}")
            raise
        finally:
            if connection:
                try:
                    await self._pool.release(connection)
                except Exception as e:
                    logger.warning(f"Error releasing connection: {e}")

    async def execute(self, query: str, *args) -> Any:
        """Execute a query with automatic connection management."""
        async with self.acquire() as conn:
            return await conn.fetch(query, *args)

    async def fetchrow(self, query: str, *args) -> Optional[asyncpg.Record]:
        """Fetch a single row with automatic connection management."""
        async with self.acquire() as conn:
            return await conn.fetchrow(query, *args)

    async def execute_many(self, query: str, args_list) -> None:
        """Execute multiple queries in batch with automatic connection management."""
        async with self.acquire() as conn:
            return await conn.executemany(query, args_list)

    def get_pool_size(self) -> int:
        """Get current pool size."""
        return self._pool.get_size() if self._pool else 0

    def get_idle_size(self) -> int:
        """Get current idle connection count."""
        return self._pool.get_idle_size() if self._pool else 0

    def get_stats(self) -> PoolStats:
        """Get comprehensive pool statistics."""
        if not self._pool:
            return PoolStats(0, 0, 0, 0, self.max_size, self.min_size, 0, 0.0, 0, 0)

        avg_acquisition_time = (
            sum(self._stats["acquisition_times"])
            / len(self._stats["acquisition_times"])
            if self._stats["acquisition_times"]
            else 0.0
        )

        return PoolStats(
            size=self._pool.get_size(),
            idle=self._pool.get_idle_size(),
            acquiring=0,  # asyncpg doesn't expose this directly
            acquired=self._pool.get_size() - self._pool.get_idle_size(),
            max_size=self.max_size,
            min_size=self.min_size,
            total_requests=self._stats["total_requests"],
            avg_acquisition_time=avg_acquisition_time,
            peak_usage=self._stats["peak_usage"],
            connection_timeouts=self._stats["connection_timeouts"],
        )

    async def health_check(self) -> bool:
        """Perform health check on the connection pool."""
        try:
            async with self.acquire() as conn:
                result = await conn.fetchrow(
                    "SELECT 1 as health_check, NOW() as timestamp"
                )
                logger.info(f"Database health check: OK - {result['timestamp']}")
                return True
        except Exception as e:
            logger.error(f"Database health check failed: {e}")
            return False

    async def close(self) -> None:
        """Close the connection pool gracefully."""
        if self._pool:
            logger.info("Closing database connection pool...")
            await self._pool.close()
            self._pool = None
            logger.info("Database connection pool closed")


# Global pool manager instance
_pool_manager: Optional[DatabasePoolManager] = None


async def get_pool_manager() -> DatabasePoolManager:
    """Get or create the global pool manager instance."""
    global _pool_manager
    if _pool_manager is None:
        _pool_manager = DatabasePoolManager()
        await _pool_manager.initialize()
    return _pool_manager


async def close_pool_manager() -> None:
    """Close the global pool manager."""
    global _pool_manager
    if _pool_manager:
        await _pool_manager.close()
        _pool_manager = None
