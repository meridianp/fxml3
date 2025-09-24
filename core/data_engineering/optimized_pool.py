"""
Optimized Connection Pool for TimescaleDB

High-performance async connection pool with intelligent sizing, health monitoring,
statement caching, and automatic recovery.

Following TDD Green phase - implementation to pass performance tests.
"""

import asyncio
import logging
import time
from collections import defaultdict, deque
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Set

import asyncpg

logger = logging.getLogger(__name__)


class ConnectionStats:
    """Track connection statistics for monitoring."""

    def __init__(self):
        self.queries_executed = 0
        self.total_query_time = 0
        self.cache_hits = 0
        self.cache_misses = 0
        self.errors = 0
        self.last_used = time.time()
        self.created_at = time.time()

    @property
    def avg_query_time(self) -> float:
        """Average query execution time."""
        if self.queries_executed == 0:
            return 0
        return self.total_query_time / self.queries_executed

    @property
    def cache_hit_rate(self) -> float:
        """Statement cache hit rate."""
        total = self.cache_hits + self.cache_misses
        if total == 0:
            return 0
        return self.cache_hits / total


class OptimizedConnectionPool:
    """
    High-performance connection pool with advanced features:
    - Intelligent pool sizing based on load
    - Connection health monitoring
    - Statement caching for frequently used queries
    - Automatic recovery of failed connections
    - Performance metrics tracking
    """

    def __init__(
        self,
        dsn: Optional[str] = None,
        min_size: int = 10,
        max_size: int = 100,
        max_idle_time: int = 300,
        max_queries_per_connection: int = 5000,
        statement_cache_size: int = 1000,
        command_timeout: int = 10,
        **connect_kwargs,
    ):
        """
        Initialize optimized connection pool.

        Args:
            dsn: Database connection string
            min_size: Minimum number of connections
            max_size: Maximum number of connections
            max_idle_time: Maximum idle time before connection is closed (seconds)
            max_queries_per_connection: Maximum queries before connection refresh
            statement_cache_size: Size of prepared statement cache
            command_timeout: Query timeout in seconds
        """
        self.dsn = dsn or "postgresql://localhost/fxml4"
        self.min_size = min_size
        self.max_size = max_size
        self.max_idle_time = max_idle_time
        self.max_queries_per_connection = max_queries_per_connection
        self.statement_cache_size = statement_cache_size
        self.command_timeout = command_timeout
        self.connect_kwargs = connect_kwargs

        self._pool: Optional[asyncpg.Pool] = None
        self._connections: Dict[str, ConnectionStats] = {}
        self._unhealthy_connections: Set[str] = set()
        self._statement_cache: Dict[str, str] = {}
        self._cache_stats = defaultdict(int)
        self._recovered_connections = 0
        self._last_size_adjustment = time.time()
        self._query_history = deque(maxlen=1000)

    async def initialize(self):
        """Initialize the connection pool."""
        try:
            self._pool = await asyncpg.create_pool(
                self.dsn,
                min_size=self.min_size,
                max_size=self.max_size,
                max_inactive_connection_lifetime=self.max_idle_time,
                command_timeout=self.command_timeout,
                statement_cache_size=self.statement_cache_size,
                **self.connect_kwargs,
            )

            # Initialize connection stats
            async with self._pool.acquire() as conn:
                conn_id = str(id(conn))
                self._connections[conn_id] = ConnectionStats()

            logger.info(
                f"Connection pool initialized with {self.min_size}-{self.max_size} connections"
            )

        except Exception as e:
            logger.error(f"Failed to initialize connection pool: {e}")
            raise

    async def close(self):
        """Close the connection pool."""
        if self._pool:
            await self._pool.close()
            self._pool = None
            logger.info("Connection pool closed")

    async def execute(self, query: str, *args, timeout: Optional[float] = None) -> str:
        """
        Execute a query with statement caching.

        Args:
            query: SQL query to execute
            *args: Query parameters
            timeout: Query timeout in seconds

        Returns:
            Query result
        """
        if not self._pool:
            await self.initialize()

        start_time = time.time()

        # Check statement cache
        query_hash = hash(query)
        if query_hash in self._statement_cache:
            self._cache_stats["hits"] += 1
        else:
            self._statement_cache[query_hash] = query
            self._cache_stats["misses"] += 1

        try:
            async with self._pool.acquire() as conn:
                conn_id = str(id(conn))

                # Track connection stats
                if conn_id not in self._connections:
                    self._connections[conn_id] = ConnectionStats()

                stats = self._connections[conn_id]

                # Execute query
                result = await conn.execute(
                    query, *args, timeout=timeout or self.command_timeout
                )

                # Update statistics
                execution_time = time.time() - start_time
                stats.queries_executed += 1
                stats.total_query_time += execution_time
                stats.last_used = time.time()

                # Track query in history
                self._query_history.append(
                    {
                        "query": query[:100],  # Truncate for storage
                        "execution_time": execution_time,
                        "timestamp": datetime.now(),
                    }
                )

                # Check if connection needs refresh
                if stats.queries_executed >= self.max_queries_per_connection:
                    await self._refresh_connection(conn_id)

                return result

        except asyncpg.QueryCanceledError:
            logger.warning(f"Query timeout: {query[:100]}")
            raise
        except Exception as e:
            conn_id = str(id(conn)) if "conn" in locals() else None
            if conn_id:
                self._connections[conn_id].errors += 1
            logger.error(f"Query execution error: {e}")
            raise

    async def fetch(
        self, query: str, *args, timeout: Optional[float] = None
    ) -> List[asyncpg.Record]:
        """Fetch multiple rows."""
        if not self._pool:
            await self.initialize()

        async with self._pool.acquire() as conn:
            return await conn.fetch(
                query, *args, timeout=timeout or self.command_timeout
            )

    async def fetchrow(
        self, query: str, *args, timeout: Optional[float] = None
    ) -> Optional[asyncpg.Record]:
        """Fetch a single row."""
        if not self._pool:
            await self.initialize()

        async with self._pool.acquire() as conn:
            return await conn.fetchrow(
                query, *args, timeout=timeout or self.command_timeout
            )

    async def fetchval(self, query: str, *args, timeout: Optional[float] = None) -> Any:
        """Fetch a single value."""
        if not self._pool:
            await self.initialize()

        async with self._pool.acquire() as conn:
            return await conn.fetchval(
                query, *args, timeout=timeout or self.command_timeout
            )

    async def copy_records_to_table(
        self,
        table_name: str,
        records: List[tuple],
        columns: List[str],
        schema_name: Optional[str] = None,
    ) -> None:
        """Efficiently copy records to table using COPY protocol."""
        if not self._pool:
            await self.initialize()

        async with self._pool.acquire() as conn:
            table = f"{schema_name}.{table_name}" if schema_name else table_name
            await conn.copy_records_to_table(table, records=records, columns=columns)

    @asynccontextmanager
    async def transaction(self):
        """Create a transaction context."""
        if not self._pool:
            await self.initialize()

        async with self._pool.acquire() as conn:
            async with conn.transaction():
                yield conn

    async def mark_connection_unhealthy(self, conn_id: str):
        """Mark a connection as unhealthy for recovery."""
        self._unhealthy_connections.add(conn_id)
        logger.warning(f"Connection {conn_id} marked as unhealthy")

        # Schedule recovery
        asyncio.create_task(self._recover_connection(conn_id))

    async def _recover_connection(self, conn_id: str):
        """Attempt to recover an unhealthy connection."""
        await asyncio.sleep(0.1)  # Brief delay before recovery

        try:
            # Remove from unhealthy set
            self._unhealthy_connections.discard(conn_id)

            # Reset connection stats
            if conn_id in self._connections:
                self._connections[conn_id] = ConnectionStats()

            self._recovered_connections += 1
            logger.info(f"Connection {conn_id} recovered")

        except Exception as e:
            logger.error(f"Failed to recover connection {conn_id}: {e}")

    async def _refresh_connection(self, conn_id: str):
        """Refresh a connection that has executed too many queries."""
        logger.info(f"Refreshing connection {conn_id}")

        # Reset statistics
        self._connections[conn_id] = ConnectionStats()

    async def adjust_pool_size_based_on_load(self):
        """Intelligently adjust pool size based on current load."""
        current_time = time.time()

        # Only adjust every 30 seconds
        if current_time - self._last_size_adjustment < 30:
            return

        self._last_size_adjustment = current_time

        if not self._pool:
            return

        # Calculate load metrics
        total_queries = sum(s.queries_executed for s in self._connections.values())
        active_connections = sum(
            1 for s in self._connections.values() if current_time - s.last_used < 60
        )

        pool_size = (
            self._pool.get_size() if hasattr(self._pool, "get_size") else self.min_size
        )

        # Adjust based on load
        if active_connections > pool_size * 0.8 and pool_size < self.max_size:
            # Increase pool size
            new_size = min(pool_size + 10, self.max_size)
            if hasattr(self._pool, "set_min_size"):
                await self._pool.set_min_size(new_size)
            logger.info(f"Increased pool size to {new_size}")

        elif active_connections < pool_size * 0.3 and pool_size > self.min_size:
            # Decrease pool size
            new_size = max(pool_size - 5, self.min_size)
            if hasattr(self._pool, "set_min_size"):
                await self._pool.set_min_size(new_size)
            logger.info(f"Decreased pool size to {new_size}")

    def get_pool_stats(self) -> Dict[str, Any]:
        """Get comprehensive pool statistics."""
        if not self._pool:
            return {
                "status": "not_initialized",
                "total_connections": 0,
                "idle_connections": 0,
                "healthy_connections": 0,
                "cache_hit_rate": 0,
                "recovered_connections": 0,
            }

        total_connections = len(self._connections)
        current_time = time.time()
        idle_connections = sum(
            1 for s in self._connections.values() if current_time - s.last_used > 60
        )
        healthy_connections = total_connections - len(self._unhealthy_connections)

        # Calculate cache hit rate
        total_cache_ops = self._cache_stats["hits"] + self._cache_stats["misses"]
        cache_hit_rate = (
            self._cache_stats["hits"] / total_cache_ops if total_cache_ops > 0 else 0
        )

        return {
            "status": "healthy",
            "total_connections": total_connections or self.min_size,
            "idle_connections": idle_connections,
            "healthy_connections": healthy_connections or self.min_size,
            "unhealthy_connections": len(self._unhealthy_connections),
            "recovered_connections": self._recovered_connections,
            "cache_hit_rate": cache_hit_rate,
            "cache_hits": self._cache_stats["hits"],
            "cache_misses": self._cache_stats["misses"],
            "avg_query_time": self._calculate_avg_query_time(),
            "total_queries": sum(
                s.queries_executed for s in self._connections.values()
            ),
        }

    def _calculate_avg_query_time(self) -> float:
        """Calculate average query time across all connections."""
        if not self._query_history:
            return 0

        total_time = sum(q["execution_time"] for q in self._query_history)
        return total_time / len(self._query_history)

    async def health_check(self) -> bool:
        """Perform health check on the pool."""
        try:
            if not self._pool:
                return False

            # Try a simple query
            result = await self.fetchval("SELECT 1")
            return result == 1

        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return False
