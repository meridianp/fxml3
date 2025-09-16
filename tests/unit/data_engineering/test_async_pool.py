"""
Unit tests for async connection pool.
"""

import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock, Mock, patch

import pytest

from fxml4.data_engineering.async_pool import (
    AsyncConnectionPool,
    ConnectionPoolError,
    ConnectionPoolStats,
    PoolNotInitializedError,
    close_pool,
    get_pool,
)


@pytest.fixture
async def mock_pool():
    """Create a mock connection pool."""
    with patch("asyncpg.create_pool") as mock_create:
        mock_pool = AsyncMock()
        mock_pool.acquire = AsyncMock()
        mock_pool.release = AsyncMock()
        mock_pool.close = AsyncMock()
        mock_pool.get_size = Mock(return_value=10)
        mock_pool.get_idle_size = Mock(return_value=5)
        mock_pool.get_min_size = Mock(return_value=5)
        mock_pool.get_max_size = Mock(return_value=20)

        mock_create.return_value = mock_pool

        pool = AsyncConnectionPool(
            host="localhost",
            port=5432,
            database="test",
            min_connections=5,
            max_connections=20,
        )

        await pool.initialize()
        yield pool
        await pool.close()


@pytest.mark.asyncio
async def test_pool_initialization():
    """Test pool initialization."""
    with patch("asyncpg.create_pool") as mock_create:
        mock_create.return_value = AsyncMock()

        pool = AsyncConnectionPool()
        assert pool._pool is None

        await pool.initialize()
        assert pool._pool is not None
        mock_create.assert_called_once()

        # Test double initialization
        await pool.initialize()
        assert mock_create.call_count == 1  # Should not create again

        await pool.close()


@pytest.mark.asyncio
async def test_pool_context_manager():
    """Test pool as async context manager."""
    with patch("asyncpg.create_pool") as mock_create:
        mock_create.return_value = AsyncMock()

        async with AsyncConnectionPool() as pool:
            assert pool._pool is not None

        # Pool should be closed after context
        assert pool._is_closed


@pytest.mark.asyncio
async def test_acquire_connection(mock_pool):
    """Test acquiring connections from pool."""
    mock_conn = AsyncMock()
    mock_pool._pool.acquire.return_value = mock_conn

    async with mock_pool.acquire() as conn:
        assert conn == mock_conn

    mock_pool._pool.acquire.assert_called_once()
    mock_pool._pool.release.assert_called_once_with(mock_conn)

    # Check stats
    assert mock_pool._stats.connections_acquired == 1
    assert mock_pool._stats.connections_released == 1


@pytest.mark.asyncio
async def test_acquire_timeout(mock_pool):
    """Test connection acquisition timeout."""
    mock_pool._pool.acquire.side_effect = asyncio.TimeoutError()

    with pytest.raises(ConnectionPoolError) as exc_info:
        async with mock_pool.acquire():
            pass

    assert "Timeout acquiring connection" in str(exc_info.value)
    assert mock_pool._stats.connection_errors == 1


@pytest.mark.asyncio
async def test_pool_not_initialized():
    """Test operations on uninitialized pool."""
    pool = AsyncConnectionPool()

    with pytest.raises(PoolNotInitializedError):
        async with pool.acquire():
            pass


@pytest.mark.asyncio
async def test_execute_query(mock_pool):
    """Test executing queries."""
    mock_conn = AsyncMock()
    mock_conn.execute = AsyncMock(return_value="OK")
    mock_pool._pool.acquire.return_value = mock_conn

    result = await mock_pool.execute("INSERT INTO test VALUES ($1)", 1)
    assert result == "OK"

    mock_conn.execute.assert_called_once_with(
        "INSERT INTO test VALUES ($1)", 1, timeout=None
    )
    assert mock_pool._stats.queries_executed == 1


@pytest.mark.asyncio
async def test_fetch_query(mock_pool):
    """Test fetching query results."""
    mock_conn = AsyncMock()
    mock_records = [Mock(spec=["__getitem__"]), Mock(spec=["__getitem__"])]
    mock_conn.fetch = AsyncMock(return_value=mock_records)
    mock_pool._pool.acquire.return_value = mock_conn

    results = await mock_pool.fetch("SELECT * FROM test")
    assert results == mock_records
    assert mock_pool._stats.queries_executed == 1


@pytest.mark.asyncio
async def test_fetchrow_query(mock_pool):
    """Test fetching single row."""
    mock_conn = AsyncMock()
    mock_record = Mock(spec=["__getitem__"])
    mock_conn.fetchrow = AsyncMock(return_value=mock_record)
    mock_pool._pool.acquire.return_value = mock_conn

    result = await mock_pool.fetchrow("SELECT * FROM test WHERE id = $1", 1)
    assert result == mock_record
    assert mock_pool._stats.queries_executed == 1


@pytest.mark.asyncio
async def test_fetchval_query(mock_pool):
    """Test fetching single value."""
    mock_conn = AsyncMock()
    mock_conn.fetchval = AsyncMock(return_value=42)
    mock_pool._pool.acquire.return_value = mock_conn

    result = await mock_pool.fetchval("SELECT COUNT(*) FROM test")
    assert result == 42
    assert mock_pool._stats.queries_executed == 1


@pytest.mark.asyncio
async def test_execute_many(mock_pool):
    """Test executing many queries."""
    mock_conn = AsyncMock()
    mock_conn.executemany = AsyncMock()
    mock_pool._pool.acquire.return_value = mock_conn

    args = [(1, "a"), (2, "b"), (3, "c")]
    await mock_pool.execute_many("INSERT INTO test VALUES ($1, $2)", args)

    mock_conn.executemany.assert_called_once()
    assert mock_pool._stats.queries_executed == 3


@pytest.mark.asyncio
async def test_copy_records(mock_pool):
    """Test copying records to table."""
    mock_conn = AsyncMock()
    mock_conn.copy_records_to_table = AsyncMock()
    mock_pool._pool.acquire.return_value = mock_conn

    records = [(1, "a"), (2, "b")]
    result = await mock_pool.copy_records_to_table(
        "test_table", records, columns=["id", "name"]
    )

    assert result == 2
    assert mock_pool._stats.queries_executed == 1


@pytest.mark.asyncio
async def test_transaction(mock_pool):
    """Test transaction context."""
    mock_conn = AsyncMock()
    mock_trans = AsyncMock()
    mock_conn.transaction = Mock(return_value=mock_trans)
    mock_pool._pool.acquire.return_value = mock_conn

    async with mock_pool.transaction() as trans:
        assert trans == mock_conn

    mock_conn.transaction.assert_called_once_with(isolation="read_committed")


@pytest.mark.asyncio
async def test_health_check(mock_pool):
    """Test health check."""
    mock_conn = AsyncMock()
    mock_conn.fetchval = AsyncMock(return_value=1)
    mock_pool._pool.acquire.return_value = mock_conn

    result = await mock_pool.health_check()
    assert result is True

    # Test failed health check
    mock_conn.fetchval.side_effect = Exception("Connection error")
    result = await mock_pool.health_check()
    assert result is False


@pytest.mark.asyncio
async def test_get_stats(mock_pool):
    """Test getting pool statistics."""
    # Execute some operations to generate stats
    mock_conn = AsyncMock()
    mock_conn.execute = AsyncMock()
    mock_pool._pool.acquire.return_value = mock_conn

    await mock_pool.execute("SELECT 1")
    await mock_pool.execute("SELECT 2")

    stats = mock_pool.get_stats()

    assert stats["queries_executed"] == 2
    assert stats["pool_size"] == 10
    assert stats["pool_free_size"] == 5
    assert stats["pool_min_size"] == 5
    assert stats["pool_max_size"] == 20
    assert "uptime_seconds" in stats
    assert "queries_per_second" in stats


@pytest.mark.asyncio
async def test_connection_pool_stats():
    """Test ConnectionPoolStats class."""
    stats = ConnectionPoolStats()

    # Record some metrics
    stats.connections_created = 10
    stats.connections_acquired = 20
    stats.queries_executed = 100
    stats.query_errors = 2
    stats.total_query_time = 50.0

    metrics = stats.to_dict()

    assert metrics["connections_created"] == 10
    assert metrics["connections_acquired"] == 20
    assert metrics["queries_executed"] == 100
    assert metrics["query_errors"] == 2
    assert metrics["avg_query_time"] == 0.5
    assert "queries_per_second" in metrics
    assert "uptime_seconds" in metrics


@pytest.mark.asyncio
async def test_global_pool():
    """Test global pool management."""
    with patch("asyncpg.create_pool") as mock_create:
        mock_create.return_value = AsyncMock()

        # Get pool (should create it)
        pool1 = await get_pool()
        assert pool1 is not None

        # Get pool again (should return same instance)
        pool2 = await get_pool()
        assert pool1 is pool2

        # Close pool
        await close_pool()

        # Get pool again (should create new one)
        pool3 = await get_pool()
        assert pool3 is not pool1

        # Cleanup
        await close_pool()


@pytest.mark.asyncio
async def test_query_error_tracking(mock_pool):
    """Test that query errors are tracked."""
    mock_conn = AsyncMock()
    mock_conn.execute = AsyncMock(side_effect=Exception("Query failed"))
    mock_pool._pool.acquire.return_value = mock_conn

    with pytest.raises(Exception):
        await mock_pool.execute("SELECT * FROM nonexistent")

    assert mock_pool._stats.query_errors == 1
    assert mock_pool._stats.queries_executed == 0  # Failed queries don't count


@pytest.mark.asyncio
async def test_concurrent_operations(mock_pool):
    """Test concurrent pool operations."""
    mock_conn = AsyncMock()
    mock_conn.fetchval = AsyncMock(return_value=1)
    mock_pool._pool.acquire.return_value = mock_conn

    # Run multiple queries concurrently
    tasks = [mock_pool.fetchval(f"SELECT {i}") for i in range(10)]

    results = await asyncio.gather(*tasks)

    assert len(results) == 10
    assert all(r == 1 for r in results)
    assert mock_pool._stats.queries_executed == 10
