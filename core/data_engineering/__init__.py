"""Data engineering package for FXML4.

This package provides modules for data acquisition, processing, and storage.
"""

# New async components
from .async_timescaledb import AsyncTimescaleDBClient
from .database_pools import (
    PRESETS,
    AsyncConnectionPool,
    ConnectionPool,
    PoolConfig,
    PoolMetrics,
    add_pool_config,
    get_pool_config,
    get_preset_config,
)

# Legacy synchronous client
from .timescaledb import TimescaleDBClient

# Legacy pool imports (for backwards compatibility)
try:
    from .async_pool import (
        ConnectionPoolError,
        PoolNotInitializedError,
        close_pool,
        get_pool,
    )
    from .pool_monitor import PoolMonitor
except ImportError:
    # If old files are removed, create dummy compatibility layers
    get_pool = None
    close_pool = None
    ConnectionPoolError = Exception
    PoolNotInitializedError = Exception
    PoolMonitor = None
from .db_migration_adapter import (
    MigrationHelper,
    SyncToAsyncAdapter,
    get_async_db_client,
    get_db_connection,
)

__all__ = [
    # Legacy
    "TimescaleDBClient",
    # Async client
    "AsyncTimescaleDBClient",
    # Connection pool
    "AsyncConnectionPool",
    "ConnectionPool",
    "PoolConfig",
    "PoolMetrics",
    "get_pool_config",
    "add_pool_config",
    "get_preset_config",
    "PRESETS",
    # Legacy pool support
    "get_pool",
    "close_pool",
    "ConnectionPoolError",
    "PoolNotInitializedError",
    "PoolMonitor",
    # Migration helpers
    "SyncToAsyncAdapter",
    "MigrationHelper",
    "get_db_connection",
    "get_async_db_client",
]
