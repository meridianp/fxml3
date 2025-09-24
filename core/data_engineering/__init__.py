"""Data engineering package for FXML4.

This package provides modules for data acquisition, processing, and storage.
"""

# New async components
from .async_timescaledb import AsyncTimescaleDBClient

# Try importing database_pools if available
try:
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
except ImportError:
    # Provide defaults if module doesn't exist
    PRESETS = {}
    AsyncConnectionPool = None
    ConnectionPool = None
    PoolConfig = None
    PoolMetrics = None
    add_pool_config = None
    get_pool_config = None
    get_preset_config = None

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

# Import optimized pipeline components
try:
    from .completeness_monitor import CompletenessMonitor
    from .data_validator import DataValidator, ValidationSeverity
    from .optimized_pipeline import OptimizedDataPipeline
    from .optimized_pool import OptimizedConnectionPool
    from .performance_monitor import (
        PerformanceMonitor,
        PipelineMetrics,
        ResourceMonitor,
    )
    from .query_optimizer import QueryOptimizer
    from .redis_cache import RedisDataCache
except ImportError:
    # Provide None if modules don't exist yet
    OptimizedConnectionPool = None
    QueryOptimizer = None
    RedisDataCache = None
    PerformanceMonitor = None
    PipelineMetrics = None
    ResourceMonitor = None
    DataValidator = None
    ValidationSeverity = None
    CompletenessMonitor = None
    OptimizedDataPipeline = None

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
    # Optimized pipeline components
    "OptimizedConnectionPool",
    "QueryOptimizer",
    "RedisDataCache",
    "PerformanceMonitor",
    "PipelineMetrics",
    "ResourceMonitor",
    "DataValidator",
    "ValidationSeverity",
    "CompletenessMonitor",
    "OptimizedDataPipeline",
]
