"""
Database Connection Pool Management for FXML4.

This module consolidates all database connection pool functionality including
configuration, monitoring, async pools, and connection management.
"""

import asyncio
import json
import logging
import os
import time
from collections import deque
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, List, Optional, Union

import asyncpg
import psycopg2
import yaml
from psycopg2 import pool as sync_pool

from fxml4.config import Config

logger = logging.getLogger(__name__)


@dataclass
class PoolConfig:
    """Configuration for database connection pool."""

    # Connection parameters
    host: str = "localhost"
    port: int = 5432
    database: str = "fxml4"
    user: str = "postgres"
    password: str = "postgres"

    # Pool parameters
    min_connections: int = 5
    max_connections: int = 20
    connection_timeout: float = 10.0
    command_timeout: float = 60.0
    max_queries: int = 50000
    max_inactive_connection_lifetime: float = 300.0

    # Retry parameters
    retry_count: int = 3
    retry_delay: float = 1.0

    # Health check parameters
    health_check_interval: float = 30.0
    health_check_timeout: float = 5.0

    # Performance parameters
    statement_cache_size: int = 100
    max_cached_statement_lifetime: float = 300.0

    @classmethod
    def from_dict(cls, config_dict: Dict[str, Any]) -> "PoolConfig":
        """Create PoolConfig from dictionary."""
        return cls(
            **{k: v for k, v in config_dict.items() if k in cls.__dataclass_fields__}
        )

    @classmethod
    def from_fxml4_config(cls, config: Optional[Config] = None) -> "PoolConfig":
        """Create PoolConfig from FXML4 configuration."""
        if config is None:
            config = Config()

        db_config = config.database

        return cls(
            host=db_config.host,
            port=db_config.port,
            database=db_config.name,
            user=db_config.user,
            password=db_config.password,
            min_connections=max(1, db_config.connection_count // 4),
            max_connections=db_config.connection_count,
        )

    @classmethod
    def from_env(cls) -> "PoolConfig":
        """Create PoolConfig from environment variables."""
        return cls(
            host=os.getenv("FXML4_DB_HOST", "localhost"),
            port=int(os.getenv("FXML4_DB_PORT", "5432")),
            database=os.getenv("FXML4_DB_NAME", "fxml4"),
            user=os.getenv("FXML4_DB_USER", "postgres"),
            password=os.getenv("FXML4_DB_PASSWORD", "postgres"),
            min_connections=int(os.getenv("FXML4_DB_MIN_CONNECTIONS", "5")),
            max_connections=int(os.getenv("FXML4_DB_MAX_CONNECTIONS", "20")),
            connection_timeout=float(os.getenv("FXML4_DB_CONNECTION_TIMEOUT", "10.0")),
            command_timeout=float(os.getenv("FXML4_DB_COMMAND_TIMEOUT", "60.0")),
            retry_count=int(os.getenv("FXML4_DB_RETRY_COUNT", "3")),
            retry_delay=float(os.getenv("FXML4_DB_RETRY_DELAY", "1.0")),
            health_check_interval=float(
                os.getenv("FXML4_DB_HEALTH_CHECK_INTERVAL", "30.0")
            ),
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for AsyncConnectionPool initialization."""
        return {
            "host": self.host,
            "port": self.port,
            "database": self.database,
            "user": self.user,
            "password": self.password,
            "min_connections": self.min_connections,
            "max_connections": self.max_connections,
            "connection_timeout": self.connection_timeout,
            "command_timeout": self.command_timeout,
            "max_queries": self.max_queries,
            "max_inactive_connection_lifetime": self.max_inactive_connection_lifetime,
            "retry_count": self.retry_count,
            "retry_delay": self.retry_delay,
            "health_check_interval": self.health_check_interval,
        }

    def validate(self) -> None:
        """Validate configuration parameters."""
        if self.min_connections < 1:
            raise ValueError("min_connections must be at least 1")

        if self.max_connections < self.min_connections:
            raise ValueError("max_connections must be >= min_connections")

        if self.connection_timeout <= 0:
            raise ValueError("connection_timeout must be positive")

        if self.command_timeout <= 0:
            raise ValueError("command_timeout must be positive")

        if self.retry_count < 0:
            raise ValueError("retry_count must be non-negative")

        if self.retry_delay < 0:
            raise ValueError("retry_delay must be non-negative")

        if self.health_check_interval <= 0:
            raise ValueError("health_check_interval must be positive")


class PoolMetrics:
    """Collect and analyze connection pool metrics."""

    def __init__(self, window_size: int = 1000):
        """
        Initialize metrics collector.

        Args:
            window_size: Size of sliding window for metrics
        """
        self.window_size = window_size

        # Metrics storage
        self.connection_wait_times = deque(maxlen=window_size)
        self.query_execution_times = deque(maxlen=window_size)
        self.connection_lifetimes = deque(maxlen=window_size)
        self.error_timestamps = deque(maxlen=window_size)

        # Counters
        self.total_connections = 0
        self.total_queries = 0
        self.total_errors = 0
        self.connection_timeouts = 0
        self.query_timeouts = 0

        # Current state
        self.current_pool_size = 0
        self.current_active_connections = 0
        self.current_idle_connections = 0
        self.current_waiting_requests = 0

        # Performance tracking
        self.last_reset = datetime.utcnow()

    def record_connection_wait(self, wait_time: float) -> None:
        """Record connection wait time."""
        self.connection_wait_times.append(wait_time)

    def record_query_execution(self, execution_time: float) -> None:
        """Record query execution time."""
        self.query_execution_times.append(execution_time)
        self.total_queries += 1

    def record_connection_lifetime(self, lifetime: float) -> None:
        """Record connection lifetime."""
        self.connection_lifetimes.append(lifetime)

    def record_error(self, error_type: str = "general") -> None:
        """Record an error occurrence."""
        self.error_timestamps.append(datetime.utcnow())
        self.total_errors += 1

        if error_type == "connection_timeout":
            self.connection_timeouts += 1
        elif error_type == "query_timeout":
            self.query_timeouts += 1

    def update_pool_state(
        self, pool_size: int, active: int, idle: int, waiting: int
    ) -> None:
        """Update current pool state."""
        self.current_pool_size = pool_size
        self.current_active_connections = active
        self.current_idle_connections = idle
        self.current_waiting_requests = waiting

    def get_summary(self) -> Dict[str, Any]:
        """Get metrics summary."""
        now = datetime.utcnow()
        uptime = (now - self.last_reset).total_seconds()

        # Calculate averages
        avg_wait_time = (
            sum(self.connection_wait_times) / len(self.connection_wait_times)
            if self.connection_wait_times
            else 0
        )
        avg_query_time = (
            sum(self.query_execution_times) / len(self.query_execution_times)
            if self.query_execution_times
            else 0
        )
        avg_connection_lifetime = (
            sum(self.connection_lifetimes) / len(self.connection_lifetimes)
            if self.connection_lifetimes
            else 0
        )

        # Calculate error rates
        error_rate = self.total_errors / uptime if uptime > 0 else 0

        return {
            "uptime_seconds": uptime,
            "pool_state": {
                "pool_size": self.current_pool_size,
                "active_connections": self.current_active_connections,
                "idle_connections": self.current_idle_connections,
                "waiting_requests": self.current_waiting_requests,
            },
            "performance": {
                "avg_connection_wait_time": avg_wait_time,
                "avg_query_execution_time": avg_query_time,
                "avg_connection_lifetime": avg_connection_lifetime,
                "queries_per_second": self.total_queries / uptime if uptime > 0 else 0,
            },
            "counters": {
                "total_connections": self.total_connections,
                "total_queries": self.total_queries,
                "total_errors": self.total_errors,
                "connection_timeouts": self.connection_timeouts,
                "query_timeouts": self.query_timeouts,
                "error_rate": error_rate,
            },
        }

    def reset(self) -> None:
        """Reset all metrics."""
        self.connection_wait_times.clear()
        self.query_execution_times.clear()
        self.connection_lifetimes.clear()
        self.error_timestamps.clear()

        self.total_connections = 0
        self.total_queries = 0
        self.total_errors = 0
        self.connection_timeouts = 0
        self.query_timeouts = 0

        self.last_reset = datetime.utcnow()


class AsyncConnectionPool:
    """High-performance async connection pool for PostgreSQL."""

    def __init__(self, config: PoolConfig):
        """
        Initialize async connection pool.

        Args:
            config: Pool configuration
        """
        self.config = config
        self.config.validate()

        self._pool: Optional[asyncpg.Pool] = None
        self._metrics = PoolMetrics()
        self._health_check_task: Optional[asyncio.Task] = None
        self._monitor_task: Optional[asyncio.Task] = None
        self._is_healthy = False
        self._startup_time = datetime.utcnow()

    async def initialize(self) -> None:
        """Initialize the connection pool."""
        try:
            logger.info(
                f"Initializing connection pool: {self.config.host}:{self.config.port}/{self.config.database}"
            )

            # Create connection pool
            self._pool = await asyncpg.create_pool(
                host=self.config.host,
                port=self.config.port,
                database=self.config.database,
                user=self.config.user,
                password=self.config.password,
                min_size=self.config.min_connections,
                max_size=self.config.max_connections,
                max_queries=self.config.max_queries,
                max_inactive_connection_lifetime=self.config.max_inactive_connection_lifetime,
                command_timeout=self.config.command_timeout,
                server_settings={
                    "statement_cache_size": str(self.config.statement_cache_size),
                    "prepared_statement_cache_size": str(
                        self.config.statement_cache_size
                    ),
                },
            )

            # Test connection
            async with self._pool.acquire() as conn:
                await conn.execute("SELECT 1")

            self._is_healthy = True
            logger.info("Connection pool initialized successfully")

            # Start background tasks
            self._health_check_task = asyncio.create_task(self._health_check_loop())
            self._monitor_task = asyncio.create_task(self._monitor_loop())

        except Exception as e:
            logger.error(f"Failed to initialize connection pool: {e}")
            self._is_healthy = False
            raise

    async def close(self) -> None:
        """Close the connection pool."""
        logger.info("Closing connection pool")

        # Cancel background tasks
        if self._health_check_task:
            self._health_check_task.cancel()
            try:
                await self._health_check_task
            except asyncio.CancelledError:
                pass

        if self._monitor_task:
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass

        # Close pool
        if self._pool:
            await self._pool.close()

        self._is_healthy = False
        logger.info("Connection pool closed")

    @asynccontextmanager
    async def acquire(self):
        """Acquire a connection from the pool."""
        if not self._pool:
            raise RuntimeError("Connection pool not initialized")

        start_time = time.time()
        conn = None

        try:
            # Acquire connection with timeout
            conn = await asyncio.wait_for(
                self._pool.acquire(), timeout=self.config.connection_timeout
            )

            wait_time = time.time() - start_time
            self._metrics.record_connection_wait(wait_time)

            yield conn

        except asyncio.TimeoutError:
            self._metrics.record_error("connection_timeout")
            raise
        except Exception as e:
            self._metrics.record_error()
            raise
        finally:
            if conn:
                await self._pool.release(conn)

    async def execute(self, query: str, *args) -> Any:
        """Execute a query."""
        start_time = time.time()

        try:
            async with self.acquire() as conn:
                result = await conn.execute(query, *args)

            execution_time = time.time() - start_time
            self._metrics.record_query_execution(execution_time)

            return result

        except asyncio.TimeoutError:
            self._metrics.record_error("query_timeout")
            raise
        except Exception as e:
            self._metrics.record_error()
            raise

    async def fetch(self, query: str, *args) -> List[Dict]:
        """Fetch query results."""
        start_time = time.time()

        try:
            async with self.acquire() as conn:
                result = await conn.fetch(query, *args)

            execution_time = time.time() - start_time
            self._metrics.record_query_execution(execution_time)

            return [dict(row) for row in result]

        except asyncio.TimeoutError:
            self._metrics.record_error("query_timeout")
            raise
        except Exception as e:
            self._metrics.record_error()
            raise

    async def fetchrow(self, query: str, *args) -> Optional[Dict]:
        """Fetch single row."""
        start_time = time.time()

        try:
            async with self.acquire() as conn:
                result = await conn.fetchrow(query, *args)

            execution_time = time.time() - start_time
            self._metrics.record_query_execution(execution_time)

            return dict(result) if result else None

        except asyncio.TimeoutError:
            self._metrics.record_error("query_timeout")
            raise
        except Exception as e:
            self._metrics.record_error()
            raise

    async def _health_check_loop(self) -> None:
        """Background health check loop."""
        while True:
            try:
                await asyncio.sleep(self.config.health_check_interval)

                # Perform health check
                async with self.acquire() as conn:
                    await asyncio.wait_for(
                        conn.execute("SELECT 1"),
                        timeout=self.config.health_check_timeout,
                    )

                self._is_healthy = True

            except Exception as e:
                logger.warning(f"Health check failed: {e}")
                self._is_healthy = False
                self._metrics.record_error()

    async def _monitor_loop(self) -> None:
        """Background monitoring loop."""
        while True:
            try:
                await asyncio.sleep(10)  # Monitor every 10 seconds

                if self._pool:
                    # Update pool state in metrics
                    self._metrics.update_pool_state(
                        pool_size=self._pool.get_size(),
                        active=self._pool.get_size() - self._pool.get_idle_size(),
                        idle=self._pool.get_idle_size(),
                        waiting=0,  # asyncpg doesn't expose waiting count
                    )

            except Exception as e:
                logger.warning(f"Monitor loop error: {e}")

    @property
    def is_healthy(self) -> bool:
        """Check if pool is healthy."""
        return self._is_healthy

    @property
    def metrics(self) -> PoolMetrics:
        """Get pool metrics."""
        return self._metrics

    def get_stats(self) -> Dict[str, Any]:
        """Get pool statistics."""
        stats = {
            "config": self.config.to_dict(),
            "healthy": self._is_healthy,
            "uptime_seconds": (datetime.utcnow() - self._startup_time).total_seconds(),
        }

        if self._pool:
            stats.update(
                {
                    "pool_size": self._pool.get_size(),
                    "idle_connections": self._pool.get_idle_size(),
                    "active_connections": self._pool.get_size()
                    - self._pool.get_idle_size(),
                }
            )

        stats.update(self._metrics.get_summary())

        return stats


class ConnectionPool:
    """Synchronous connection pool for PostgreSQL."""

    def __init__(self, config: PoolConfig):
        """
        Initialize synchronous connection pool.

        Args:
            config: Pool configuration
        """
        self.config = config
        self.config.validate()

        self._pool: Optional[sync_pool.ThreadedConnectionPool] = None
        self._metrics = PoolMetrics()
        self._is_healthy = False
        self._startup_time = datetime.utcnow()

    def initialize(self) -> None:
        """Initialize the connection pool."""
        try:
            logger.info(
                f"Initializing sync connection pool: {self.config.host}:{self.config.port}/{self.config.database}"
            )

            # Create connection pool
            self._pool = sync_pool.ThreadedConnectionPool(
                minconn=self.config.min_connections,
                maxconn=self.config.max_connections,
                host=self.config.host,
                port=self.config.port,
                database=self.config.database,
                user=self.config.user,
                password=self.config.password,
            )

            # Test connection
            conn = self._pool.getconn()
            try:
                cursor = conn.cursor()
                cursor.execute("SELECT 1")
                cursor.close()
            finally:
                self._pool.putconn(conn)

            self._is_healthy = True
            logger.info("Sync connection pool initialized successfully")

        except Exception as e:
            logger.error(f"Failed to initialize sync connection pool: {e}")
            self._is_healthy = False
            raise

    def close(self) -> None:
        """Close the connection pool."""
        logger.info("Closing sync connection pool")

        if self._pool:
            self._pool.closeall()

        self._is_healthy = False
        logger.info("Sync connection pool closed")

    def get_connection(self):
        """Get a connection from the pool."""
        if not self._pool:
            raise RuntimeError("Connection pool not initialized")

        start_time = time.time()

        try:
            conn = self._pool.getconn()
            wait_time = time.time() - start_time
            self._metrics.record_connection_wait(wait_time)
            return conn

        except Exception as e:
            self._metrics.record_error()
            raise

    def return_connection(self, conn) -> None:
        """Return a connection to the pool."""
        if self._pool:
            self._pool.putconn(conn)

    @property
    def is_healthy(self) -> bool:
        """Check if pool is healthy."""
        return self._is_healthy

    @property
    def metrics(self) -> PoolMetrics:
        """Get pool metrics."""
        return self._metrics


class PoolConfigManager:
    """Manage connection pool configurations."""

    def __init__(self):
        self._configs: Dict[str, PoolConfig] = {}
        self._default_config: Optional[PoolConfig] = None

    def add_config(self, name: str, config: PoolConfig) -> None:
        """Add a named configuration."""
        config.validate()
        self._configs[name] = config

    def get_config(self, name: Optional[str] = None) -> PoolConfig:
        """Get a configuration by name or return default."""
        if name and name in self._configs:
            return self._configs[name]

        if self._default_config is None:
            self._default_config = PoolConfig.from_fxml4_config()

        return self._default_config

    def load_from_file(self, filepath: str) -> None:
        """Load configurations from YAML file."""
        with open(filepath, "r") as f:
            data = yaml.safe_load(f)

        if "pools" in data:
            for name, config_dict in data["pools"].items():
                config = PoolConfig.from_dict(config_dict)
                self.add_config(name, config)

        if "default" in data:
            self._default_config = PoolConfig.from_dict(data["default"])

    def save_to_file(self, filepath: str) -> None:
        """Save configurations to YAML file."""
        data = {}

        if self._default_config:
            data["default"] = self._default_config.to_dict()

        if self._configs:
            data["pools"] = {
                name: config.to_dict() for name, config in self._configs.items()
            }

        with open(filepath, "w") as f:
            yaml.dump(data, f, default_flow_style=False)


# Global configuration manager
_config_manager = PoolConfigManager()


def get_pool_config(name: Optional[str] = None) -> PoolConfig:
    """Get a pool configuration."""
    return _config_manager.get_config(name)


def add_pool_config(name: str, config: PoolConfig) -> None:
    """Add a named pool configuration."""
    _config_manager.add_config(name, config)


# Preset configurations for common scenarios
PRESETS = {
    "development": PoolConfig(
        min_connections=2, max_connections=10, health_check_interval=60.0
    ),
    "testing": PoolConfig(
        min_connections=1,
        max_connections=5,
        health_check_interval=120.0,
        command_timeout=30.0,
    ),
    "production": PoolConfig(
        min_connections=10,
        max_connections=50,
        health_check_interval=15.0,
        connection_timeout=5.0,
        retry_count=5,
        retry_delay=0.5,
    ),
    "high_performance": PoolConfig(
        min_connections=20,
        max_connections=100,
        health_check_interval=10.0,
        connection_timeout=3.0,
        command_timeout=30.0,
        statement_cache_size=200,
        max_queries=100000,
    ),
}


def get_preset_config(preset: str) -> PoolConfig:
    """Get a preset configuration."""
    if preset not in PRESETS:
        raise ValueError(f"Unknown preset: {preset}. Available: {list(PRESETS.keys())}")

    # Start with preset and override with environment/config
    base_config = PRESETS[preset]
    env_config = PoolConfig.from_fxml4_config()

    # Merge configurations (env_config takes precedence)
    merged = PoolConfig(
        host=env_config.host,
        port=env_config.port,
        database=env_config.database,
        user=env_config.user,
        password=env_config.password,
        min_connections=base_config.min_connections,
        max_connections=base_config.max_connections,
        connection_timeout=base_config.connection_timeout,
        command_timeout=base_config.command_timeout,
        max_queries=base_config.max_queries,
        max_inactive_connection_lifetime=base_config.max_inactive_connection_lifetime,
        retry_count=base_config.retry_count,
        retry_delay=base_config.retry_delay,
        health_check_interval=base_config.health_check_interval,
        health_check_timeout=base_config.health_check_timeout,
        statement_cache_size=base_config.statement_cache_size,
        max_cached_statement_lifetime=base_config.max_cached_statement_lifetime,
    )

    return merged


__all__ = [
    "PoolConfig",
    "PoolMetrics",
    "AsyncConnectionPool",
    "ConnectionPool",
    "PoolConfigManager",
    "get_pool_config",
    "add_pool_config",
    "get_preset_config",
    "PRESETS",
]
