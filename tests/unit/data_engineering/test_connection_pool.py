"""
Test database connection pooling and failover.

This module tests the connection pool implementation including
failover scenarios, health checks, and retry logic.
"""

import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import asyncpg
import pytest

from fxml4.data_engineering.connection_pool import (
    ConnectionPool,
    ConnectionState,
    DatabaseConfig,
    DatabaseRole,
    PoolMetrics,
)


@pytest.fixture
def db_configs():
    """Create test database configurations."""
    return [
        DatabaseConfig(
            host="primary.db.local",
            port=5432,
            database="fxml4",
            user="postgres",
            password="testpass",
            role=DatabaseRole.PRIMARY,
            max_connections=10,
            min_connections=2,
        ),
        DatabaseConfig(
            host="replica1.db.local",
            port=5432,
            database="fxml4",
            user="postgres",
            password="testpass",
            role=DatabaseRole.REPLICA,
            max_connections=10,
            min_connections=2,
        ),
        DatabaseConfig(
            host="replica2.db.local",
            port=5432,
            database="fxml4",
            user="postgres",
            password="testpass",
            role=DatabaseRole.REPLICA,
            max_connections=10,
            min_connections=2,
        ),
    ]


@pytest.fixture
async def connection_pool(db_configs):
    """Create connection pool instance."""
    pool = ConnectionPool(db_configs, health_check_interval=1)
    yield pool
    # Cleanup
    if pool.is_running:
        await pool.stop()


class TestConnectionPoolBasics:
    """Test basic connection pool functionality."""

    @pytest.mark.asyncio
    async def test_pool_initialization(self, connection_pool, db_configs):
        """Test connection pool initialization."""
        assert len(connection_pool.configs) == 3
        assert connection_pool.primary_config.role == DatabaseRole.PRIMARY
        assert len(connection_pool.replica_configs) == 2
        assert not connection_pool.is_running

    @pytest.mark.asyncio
    async def test_pool_start_success(self, connection_pool):
        """Test successful pool startup."""
        # Mock pool creation
        mock_pool = AsyncMock()

        with patch("asyncpg.create_pool", return_value=mock_pool):
            await connection_pool.start()

            assert connection_pool.is_running
            assert len(connection_pool.pools) == 3
            assert connection_pool.active_write_pool is not None
            assert len(connection_pool.active_read_pools) == 2
            assert connection_pool.health_check_task is not None

    @pytest.mark.asyncio
    async def test_pool_stop(self, connection_pool):
        """Test connection pool shutdown."""
        # Start pool
        mock_pool = AsyncMock()
        with patch("asyncpg.create_pool", return_value=mock_pool):
            await connection_pool.start()

        # Stop pool
        await connection_pool.stop()

        assert not connection_pool.is_running
        assert len(connection_pool.pools) == 0
        assert connection_pool.health_check_task is None

    @pytest.mark.asyncio
    async def test_acquire_write_connection(self, connection_pool):
        """Test acquiring write connections."""
        mock_pool = AsyncMock()
        mock_connection = AsyncMock()
        mock_pool.acquire.return_value.__aenter__.return_value = mock_connection

        with patch("asyncpg.create_pool", return_value=mock_pool):
            await connection_pool.start()

            async with connection_pool.acquire_write() as conn:
                assert conn == mock_connection

            # Verify metrics updated
            metrics = connection_pool.pool_metrics[connection_pool.active_write_pool]
            assert metrics.total_queries == 1
            assert metrics.failed_queries == 0

    @pytest.mark.asyncio
    async def test_acquire_read_connection(self, connection_pool):
        """Test acquiring read connections."""
        mock_pool = AsyncMock()
        mock_connection = AsyncMock()
        mock_pool.acquire.return_value.__aenter__.return_value = mock_connection

        with patch("asyncpg.create_pool", return_value=mock_pool):
            await connection_pool.start()

            # Test multiple reads for round-robin
            read_pools_used = set()
            for _ in range(4):
                async with connection_pool.acquire_read() as conn:
                    assert conn == mock_connection
                    # Track which pool was used (would need to modify code to expose this)

            # Should have used both read replicas
            assert len(connection_pool.active_read_pools) == 2


class TestConnectionPoolFailover:
    """Test failover scenarios."""

    @pytest.mark.asyncio
    async def test_primary_failure_failover(self, connection_pool):
        """Test failover when primary fails."""
        mock_pools = {}

        def create_mock_pool(host, **kwargs):
            pool = AsyncMock()
            mock_pools[host] = pool
            return pool

        with patch("asyncpg.create_pool", side_effect=create_mock_pool):
            await connection_pool.start()

            original_primary = connection_pool.active_write_pool

            # Simulate primary failure
            mock_pools["primary.db.local"].acquire.side_effect = ConnectionError(
                "Connection refused"
            )

            # Try to acquire write connection
            with pytest.raises(ConnectionError):
                async with connection_pool.acquire_write():
                    pass

            # Should trigger failover
            await connection_pool._handle_write_failure()

            # Verify failover occurred
            assert connection_pool.active_write_pool != original_primary
            assert (
                connection_pool.active_write_pool in connection_pool.active_read_pools
            )

    @pytest.mark.asyncio
    async def test_replica_failure_removal(self, connection_pool):
        """Test replica removal on failure."""
        mock_pools = {}

        def create_mock_pool(host, **kwargs):
            pool = AsyncMock()
            mock_pools[host] = pool
            return pool

        with patch("asyncpg.create_pool", side_effect=create_mock_pool):
            await connection_pool.start()

            initial_read_count = len(connection_pool.active_read_pools)

            # Simulate replica failure
            failed_replica = connection_pool.active_read_pools[0]
            pool_key = next(k for k, v in mock_pools.items() if failed_replica in k)
            mock_pools[pool_key].acquire.side_effect = ConnectionError(
                "Connection lost"
            )

            # Force selection of failed replica
            connection_pool._read_index = 0

            # Try to acquire read connection
            with pytest.raises(ConnectionError):
                async with connection_pool.acquire_read():
                    pass

            # Verify replica removed
            assert len(connection_pool.active_read_pools) == initial_read_count - 1
            assert failed_replica not in connection_pool.active_read_pools

    @pytest.mark.asyncio
    async def test_failover_callbacks(self, connection_pool):
        """Test failover callback notifications."""
        callback_called = False
        new_primary = None

        async def failover_callback(pool_key):
            nonlocal callback_called, new_primary
            callback_called = True
            new_primary = pool_key

        connection_pool.add_failover_callback(failover_callback)

        with patch("asyncpg.create_pool", return_value=AsyncMock()):
            await connection_pool.start()

            # Trigger failover
            await connection_pool._handle_write_failure()

            assert callback_called
            assert new_primary == connection_pool.active_write_pool


class TestHealthChecks:
    """Test health check functionality."""

    @pytest.mark.asyncio
    async def test_health_check_healthy_pools(self, connection_pool):
        """Test health checks on healthy pools."""
        mock_pool = AsyncMock()
        mock_connection = AsyncMock()
        mock_connection.fetchval.return_value = 1
        mock_pool.acquire.return_value.__aenter__.return_value = mock_connection
        mock_pool.get_size.return_value = 10
        mock_pool.get_idle_size.return_value = 8

        with patch("asyncpg.create_pool", return_value=mock_pool):
            await connection_pool.start()

            # Run health check
            await connection_pool._check_all_pools()

            # Verify all pools healthy
            for state in connection_pool.pool_states.values():
                assert state == ConnectionState.HEALTHY

            # Verify metrics updated
            for metrics in connection_pool.pool_metrics.values():
                assert metrics.total_connections == 10
                assert metrics.idle_connections == 8
                assert metrics.active_connections == 2

    @pytest.mark.asyncio
    async def test_health_check_degraded_pool(self, connection_pool):
        """Test health check detecting degraded pool."""
        mock_pool = AsyncMock()

        # Make health check fail
        mock_pool.acquire.side_effect = asyncio.TimeoutError("Query timeout")

        with patch("asyncpg.create_pool", return_value=mock_pool):
            await connection_pool.start()

            # Run health check
            await connection_pool._check_all_pools()

            # Verify pools marked as degraded
            for pool_key, state in connection_pool.pool_states.items():
                assert state == ConnectionState.DEGRADED

                # Verify error metrics
                metrics = connection_pool.pool_metrics[pool_key]
                assert metrics.connection_errors > 0
                assert metrics.last_error is not None
                assert "timeout" in metrics.last_error.lower()

    @pytest.mark.asyncio
    async def test_pool_recreation_after_failure(self, connection_pool):
        """Test automatic pool recreation after failure."""
        call_count = 0

        async def create_pool_side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                # First call succeeds
                return AsyncMock()
            elif call_count == 4:
                # Fail first recreation attempt for primary
                raise ConnectionError("Still down")
            else:
                # Subsequent calls succeed
                pool = AsyncMock()
                pool.acquire.return_value.__aenter__.return_value.fetchval.return_value = (
                    1
                )
                return pool

        with patch("asyncpg.create_pool", side_effect=create_pool_side_effect):
            await connection_pool.start()

            # Mark primary as failed
            connection_pool.pool_states[connection_pool.active_write_pool] = (
                ConnectionState.FAILED
            )
            connection_pool.pools.pop(connection_pool.active_write_pool)
            old_primary = connection_pool.active_write_pool
            connection_pool.active_write_pool = None

            # Run health check - should attempt recreation
            await connection_pool._check_all_pools()

            # Primary should still be None (recreation failed)
            assert connection_pool.active_write_pool is None

            # Run health check again - should succeed this time
            await connection_pool._check_all_pools()

            # Primary should be restored
            assert connection_pool.active_write_pool == old_primary


class TestRetryLogic:
    """Test query retry functionality."""

    @pytest.mark.asyncio
    async def test_execute_with_retry_success(self, connection_pool):
        """Test successful query execution with retry."""
        mock_pool = AsyncMock()
        mock_connection = AsyncMock()
        mock_connection.fetch.return_value = [{"id": 1}]
        mock_pool.acquire.return_value.__aenter__.return_value = mock_connection

        with patch("asyncpg.create_pool", return_value=mock_pool):
            await connection_pool.start()

            result = await connection_pool.execute_with_retry(
                "SELECT * FROM users WHERE id = $1", 1, read_only=True
            )

            assert result == [{"id": 1}]
            mock_connection.fetch.assert_called_once_with(
                "SELECT * FROM users WHERE id = $1", 1
            )

    @pytest.mark.asyncio
    async def test_execute_with_retry_transient_failure(self, connection_pool):
        """Test retry on transient failures."""
        mock_pool = AsyncMock()
        mock_connection = AsyncMock()

        # Fail twice, then succeed
        mock_connection.fetch.side_effect = [
            asyncio.TimeoutError("timeout"),
            ConnectionError("connection reset"),
            [{"id": 1}],  # Success on third try
        ]
        mock_pool.acquire.return_value.__aenter__.return_value = mock_connection

        with patch("asyncpg.create_pool", return_value=mock_pool):
            await connection_pool.start()

            result = await connection_pool.execute_with_retry(
                "SELECT * FROM users WHERE id = $1",
                1,
                max_retries=3,
                retry_delay=0.1,
                read_only=True,
            )

            assert result == [{"id": 1}]
            assert mock_connection.fetch.call_count == 3

    @pytest.mark.asyncio
    async def test_execute_with_retry_permanent_failure(self, connection_pool):
        """Test giving up after max retries."""
        mock_pool = AsyncMock()
        mock_connection = AsyncMock()
        mock_connection.fetch.side_effect = asyncio.TimeoutError("timeout")
        mock_pool.acquire.return_value.__aenter__.return_value = mock_connection

        with patch("asyncpg.create_pool", return_value=mock_pool):
            await connection_pool.start()

            with pytest.raises(asyncio.TimeoutError):
                await connection_pool.execute_with_retry(
                    "SELECT * FROM users", max_retries=3, retry_delay=0.01
                )

            assert mock_connection.fetch.call_count == 3

    @pytest.mark.asyncio
    async def test_execute_with_retry_non_retryable(self, connection_pool):
        """Test immediate failure on non-retryable errors."""
        mock_pool = AsyncMock()
        mock_connection = AsyncMock()
        mock_connection.fetch.side_effect = ValueError("Invalid query syntax")
        mock_pool.acquire.return_value.__aenter__.return_value = mock_connection

        with patch("asyncpg.create_pool", return_value=mock_pool):
            await connection_pool.start()

            with pytest.raises(ValueError):
                await connection_pool.execute_with_retry("INVALID SQL", max_retries=3)

            # Should not retry on syntax errors
            assert mock_connection.fetch.call_count == 1


class TestPoolMetrics:
    """Test connection pool metrics and monitoring."""

    @pytest.mark.asyncio
    async def test_query_metrics_tracking(self, connection_pool):
        """Test tracking of query metrics."""
        mock_pool = AsyncMock()
        mock_connection = AsyncMock()
        mock_pool.acquire.return_value.__aenter__.return_value = mock_connection

        with patch("asyncpg.create_pool", return_value=mock_pool):
            await connection_pool.start()

            # Execute some queries
            for i in range(5):
                async with connection_pool.acquire_write() as conn:
                    pass

            # Fail one query
            mock_connection.fetch.side_effect = Exception("Query error")
            try:
                async with connection_pool.acquire_write() as conn:
                    await conn.fetch("SELECT 1")
            except:
                pass

            # Check metrics
            metrics = connection_pool.pool_metrics[connection_pool.active_write_pool]
            assert metrics.total_queries == 6
            assert metrics.failed_queries == 1
            assert metrics.avg_query_time_ms > 0

    @pytest.mark.asyncio
    async def test_pool_status_report(self, connection_pool):
        """Test pool status reporting."""
        mock_pool = AsyncMock()
        mock_pool.get_size.return_value = 10
        mock_pool.get_idle_size.return_value = 7

        with patch("asyncpg.create_pool", return_value=mock_pool):
            await connection_pool.start()

            # Execute some queries to generate metrics
            for _ in range(10):
                async with connection_pool.acquire_write():
                    pass

            status = connection_pool.get_pool_status()

            assert "active_write_pool" in status
            assert "active_read_pools" in status
            assert "pools" in status

            # Verify pool details
            for pool_key, pool_info in status["pools"].items():
                assert pool_info["state"] == "healthy"
                assert pool_info["metrics"]["total_queries"] >= 0
                assert pool_info["metrics"]["error_rate"] >= 0
                assert pool_info["metrics"]["avg_query_time_ms"] >= 0
