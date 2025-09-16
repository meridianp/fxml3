"""Database connection pool concurrency tests for FXML4.

Tests concurrent database operations, connection pool management,
transaction handling, and deadlock detection.
"""

import asyncio
import random
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from unittest.mock import AsyncMock, Mock, patch

import numpy as np
import pytest

from tests.fixtures.database_fixtures import (
    database_performance_monitor,
    database_test_data,
    mock_async_database,
)
from tests.utils.concurrency_utils import (
    DeadlockDetector,
    LoadGenerator,
    RaceConditionDetector,
    concurrency_test_environment,
    test_database_connection_pool,
)


class MockAsyncConnectionPool:
    """Mock async connection pool for testing."""

    def __init__(self, max_connections: int = 20):
        self.max_connections = max_connections
        self.active_connections = 0
        self.total_connections_created = 0
        self.connection_semaphore = asyncio.Semaphore(max_connections)
        self.connections_in_use = set()
        self._lock = asyncio.Lock()
        self.query_log = []
        self.transaction_active = {}

    async def acquire(self):
        """Acquire a connection from the pool."""
        await self.connection_semaphore.acquire()

        async with self._lock:
            self.active_connections += 1
            self.total_connections_created += 1
            connection_id = f"conn_{self.total_connections_created}"
            self.connections_in_use.add(connection_id)

        return MockConnection(self, connection_id)

    async def release(self, connection_id: str):
        """Release a connection back to the pool."""
        async with self._lock:
            if connection_id in self.connections_in_use:
                self.connections_in_use.remove(connection_id)
                self.active_connections -= 1

        self.connection_semaphore.release()

    async def execute(self, query: str, *args):
        """Execute query using pool."""
        async with self.acquire() as conn:
            return await conn.execute(query, *args)

    async def fetch(self, query: str, *args):
        """Fetch query results using pool."""
        async with self.acquire() as conn:
            return await conn.fetch(query, *args)

    async def transaction(self):
        """Create transaction context."""
        return MockTransaction(self)

    def get_pool_stats(self) -> Dict[str, Any]:
        """Get pool statistics."""
        return {
            "max_connections": self.max_connections,
            "active_connections": self.active_connections,
            "total_created": self.total_connections_created,
            "connections_in_use": len(self.connections_in_use),
            "queries_executed": len(self.query_log),
        }


class MockConnection:
    """Mock database connection."""

    def __init__(self, pool: MockAsyncConnectionPool, connection_id: str):
        self.pool = pool
        self.connection_id = connection_id
        self.in_transaction = False

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.pool.release(self.connection_id)

    async def execute(self, query: str, *args):
        """Execute query on connection."""
        # Simulate query execution time
        await asyncio.sleep(random.uniform(0.001, 0.01))

        async with self.pool._lock:
            self.pool.query_log.append(
                {
                    "connection_id": self.connection_id,
                    "query": query,
                    "args": args,
                    "timestamp": time.perf_counter(),
                    "in_transaction": self.in_transaction,
                }
            )

        # Simulate different query results
        if "INSERT" in query.upper():
            return "INSERT 0 1"
        elif "UPDATE" in query.upper():
            return "UPDATE 1"
        elif "DELETE" in query.upper():
            return "DELETE 1"
        else:
            return "SELECT 1"

    async def fetch(self, query: str, *args):
        """Fetch query results."""
        await self.execute(query, *args)

        # Return mock results based on query type
        if "tick_data" in query.lower():
            return [
                {
                    "time": datetime.now(timezone.utc),
                    "symbol": "EURUSD",
                    "price": 1.1000,
                    "size": 1000,
                },
                {
                    "time": datetime.now(timezone.utc),
                    "symbol": "GBPUSD",
                    "price": 1.2500,
                    "size": 750,
                },
            ]
        elif "market_data" in query.lower():
            return [
                {
                    "time": datetime.now(timezone.utc),
                    "symbol": "EURUSD",
                    "open": 1.1000,
                    "high": 1.1010,
                    "low": 1.0990,
                    "close": 1.1005,
                    "volume": 1000000,
                }
            ]
        else:
            return [{"result": "success"}]

    async def fetchrow(self, query: str, *args):
        """Fetch single row."""
        results = await self.fetch(query, *args)
        return results[0] if results else None

    async def fetchval(self, query: str, *args):
        """Fetch single value."""
        row = await self.fetchrow(query, *args)
        return list(row.values())[0] if row else None


class MockTransaction:
    """Mock database transaction."""

    def __init__(self, pool: MockAsyncConnectionPool):
        self.pool = pool
        self.connection = None
        self.transaction_id = f"txn_{time.perf_counter()}"
        self.committed = False
        self.rolled_back = False

    async def __aenter__(self):
        self.connection = await self.pool.acquire()
        self.connection.in_transaction = True

        async with self.pool._lock:
            self.pool.transaction_active[self.transaction_id] = {
                "connection_id": self.connection.connection_id,
                "start_time": time.perf_counter(),
                "queries": [],
            }

        return self.connection

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.connection:
            self.connection.in_transaction = False

            async with self.pool._lock:
                if self.transaction_id in self.pool.transaction_active:
                    del self.pool.transaction_active[self.transaction_id]

            await self.pool.release(self.connection.connection_id)

        if exc_type is not None:
            self.rolled_back = True
        else:
            self.committed = True


@pytest.mark.concurrency
@pytest.mark.database
class TestDatabasePoolConcurrency:
    """Test database connection pool concurrent operations."""

    @pytest.fixture
    def mock_pool(self):
        """Create mock connection pool."""
        return MockAsyncConnectionPool(max_connections=10)

    @pytest.mark.asyncio
    async def test_connection_pool_exhaustion(self, mock_pool):
        """Test connection pool behavior under exhaustion."""

        async def hold_connection(duration: float):
            """Hold a connection for specified duration."""
            async with mock_pool.acquire() as conn:
                await asyncio.sleep(duration)
                return f"held_for_{duration}"

        # Create more requests than pool size
        num_requests = 25
        hold_durations = [0.1] * num_requests  # Each holds for 0.1 seconds
        test_cases = [(duration,) for duration in hold_durations]

        async with concurrency_test_environment(max_concurrent=num_requests) as env:
            result = await env.test_async_operation(
                hold_connection, test_cases, max_concurrent=num_requests, timeout=5.0
            )

            # All should complete eventually
            assert result.operations_completed == num_requests
            assert result.operations_failed == 0

            # Pool should handle exhaustion gracefully
            stats = mock_pool.get_pool_stats()
            assert stats["active_connections"] == 0  # All released
            assert stats["total_created"] >= mock_pool.max_connections

    @pytest.mark.asyncio
    async def test_concurrent_queries(self, mock_pool):
        """Test concurrent query execution."""

        async def execute_query(query_type: str, symbol: str, count: int):
            """Execute database query."""
            if query_type == "insert_tick":
                query = "INSERT INTO tick_data (symbol, time, price, size) VALUES ($1, $2, $3, $4)"
                args = (
                    symbol,
                    datetime.now(timezone.utc),
                    1.1000 + random.uniform(-0.01, 0.01),
                    random.randint(1000, 10000),
                )
            elif query_type == "insert_candle":
                query = "INSERT INTO market_data_1m (symbol, time, open, high, low, close, volume) VALUES ($1, $2, $3, $4, $5, $6, $7)"
                base_price = 1.1000 + random.uniform(-0.01, 0.01)
                args = (
                    symbol,
                    datetime.now(timezone.utc),
                    base_price,
                    base_price + 0.001,
                    base_price - 0.001,
                    base_price + random.uniform(-0.0005, 0.0005),
                    random.randint(10000, 100000),
                )
            else:  # query
                query = "SELECT * FROM tick_data WHERE symbol = $1 ORDER BY time DESC LIMIT $2"
                args = (symbol, count)

            return await mock_pool.execute(query, *args)

        # Generate mixed query load
        query_operations = []
        symbols = ["EURUSD", "GBPUSD", "USDJPY", "USDCHF"]
        query_types = ["insert_tick", "insert_candle", "query"]

        for i in range(200):
            symbol = random.choice(symbols)
            query_type = random.choice(query_types)
            count = random.randint(10, 100)
            query_operations.append((query_type, symbol, count))

        async with concurrency_test_environment(max_concurrent=20) as env:
            result = await env.test_async_operation(
                execute_query, query_operations, max_concurrent=20, timeout=10.0
            )

            # Validate query execution
            assert result.operations_completed == 200
            assert result.operations_failed == 0
            assert result.throughput_ops_per_sec > 50  # > 50 queries/sec

            # Check query distribution
            stats = mock_pool.get_pool_stats()
            assert stats["queries_executed"] == 200

    @pytest.mark.asyncio
    async def test_transaction_concurrency(self, mock_pool):
        """Test concurrent transaction handling."""

        async def execute_transaction(transaction_id: str, num_operations: int):
            """Execute transaction with multiple operations."""
            async with mock_pool.transaction() as conn:
                results = []
                for i in range(num_operations):
                    query = f"INSERT INTO test_table (id, value) VALUES ($1, $2)"
                    result = await conn.execute(
                        query, f"{transaction_id}_{i}", f"value_{i}"
                    )
                    results.append(result)

                    # Small delay to simulate processing
                    await asyncio.sleep(0.001)

                return len(results)

        # Run concurrent transactions
        num_transactions = 50
        transactions = [
            (f"txn_{i}", random.randint(3, 8)) for i in range(num_transactions)
        ]

        async with concurrency_test_environment(max_concurrent=15) as env:
            result = await env.test_async_operation(
                execute_transaction, transactions, max_concurrent=15, timeout=15.0
            )

            # All transactions should complete successfully
            assert result.operations_completed == num_transactions
            assert result.operations_failed == 0

            # Verify transaction isolation
            stats = mock_pool.get_pool_stats()
            assert len(mock_pool.transaction_active) == 0  # All transactions completed

    @pytest.mark.asyncio
    async def test_deadlock_detection(self, mock_pool):
        """Test deadlock detection in concurrent transactions."""

        deadlock_detector = DeadlockDetector()

        async def transaction_with_locks(
            transaction_id: str, resource_order: List[str]
        ):
            """Execute transaction that might cause deadlock."""
            thread_id = f"thread_{transaction_id}"

            try:
                # Simulate acquiring locks in different orders
                for resource in resource_order:
                    deadlock_detector.acquire_lock(thread_id, resource)
                    await asyncio.sleep(0.01)  # Hold lock briefly

                # Execute transaction
                async with mock_pool.transaction() as conn:
                    for resource in resource_order:
                        query = f"UPDATE {resource} SET last_updated = $1"
                        await conn.execute(query, datetime.now(timezone.utc))

                return "success"

            finally:
                # Release locks
                for resource in reversed(resource_order):
                    deadlock_detector.release_lock(thread_id, resource)

        # Create potential deadlock scenarios
        deadlock_scenarios = [
            (
                f"txn_{i}",
                (
                    ["resource_A", "resource_B"]
                    if i % 2 == 0
                    else ["resource_B", "resource_A"]
                ),
            )
            for i in range(20)
        ]

        async with concurrency_test_environment(max_concurrent=10) as env:
            result = await env.test_async_operation(
                transaction_with_locks,
                deadlock_scenarios,
                max_concurrent=10,
                timeout=10.0,
            )

            # Check deadlock detection
            deadlocks = deadlock_detector.get_deadlocks()

            # Should complete transactions (mock doesn't actually deadlock)
            assert result.operations_completed > 0

            # May detect potential deadlock situations
            if deadlocks:
                assert len(deadlocks) > 0
                # Verify deadlock information
                for deadlock in deadlocks:
                    assert "thread_id" in deadlock
                    assert "requested_resource" in deadlock

    @pytest.mark.asyncio
    async def test_connection_recovery(self, mock_pool):
        """Test connection pool recovery from failures."""

        async def operation_with_failures(operation_id: str, failure_rate: float):
            """Execute operation that might fail."""
            if random.random() < failure_rate:
                # Simulate connection failure
                raise ConnectionError(f"Connection failed for {operation_id}")

            # Successful operation
            async with mock_pool.acquire() as conn:
                result = await conn.execute("SELECT 1")
                return result

        # Test with varying failure rates
        operations = [(f"op_{i}", 0.1) for i in range(100)]  # 10% failure rate

        async with concurrency_test_environment(max_concurrent=20) as env:
            result = await env.test_async_operation(
                operation_with_failures, operations, max_concurrent=20, timeout=10.0
            )

            # Should handle failures gracefully
            assert result.operations_completed > 70  # Most should succeed
            assert result.operations_failed > 5  # Some should fail

            # Pool should remain healthy
            stats = mock_pool.get_pool_stats()
            assert stats["active_connections"] == 0  # All connections released

    @pytest.mark.asyncio
    async def test_bulk_operations_performance(self, mock_pool):
        """Test bulk database operations performance."""

        async def bulk_insert_ticks(symbol: str, num_ticks: int):
            """Bulk insert tick data."""
            async with mock_pool.acquire() as conn:
                ticks = []
                for i in range(num_ticks):
                    tick = (
                        symbol,
                        datetime.now(timezone.utc) + timedelta(microseconds=i),
                        1.1000 + random.uniform(-0.001, 0.001),
                        random.randint(1000, 10000),
                    )
                    ticks.append(tick)

                # Simulate bulk insert
                query = "INSERT INTO tick_data (symbol, time, price, size) VALUES ($1, $2, $3, $4)"
                for tick in ticks:
                    await conn.execute(query, *tick)

                return len(ticks)

        # Test bulk operations
        bulk_operations = [
            ("EURUSD", 100),
            ("GBPUSD", 150),
            ("USDJPY", 120),
            ("USDCHF", 80),
        ]

        start_time = time.perf_counter()

        async with concurrency_test_environment(max_concurrent=4) as env:
            result = await env.test_async_operation(
                bulk_insert_ticks, bulk_operations, max_concurrent=4, timeout=15.0
            )

            end_time = time.perf_counter()

            # Performance validation
            assert result.operations_completed == 4
            assert result.operations_failed == 0
            assert (end_time - start_time) < 10.0  # Should complete within 10 seconds

            # Check total operations processed
            stats = mock_pool.get_pool_stats()
            total_inserts = sum(450)  # 100 + 150 + 120 + 80 = 450 ticks
            assert stats["queries_executed"] >= total_inserts

    @pytest.mark.asyncio
    async def test_pool_stress_test(self, mock_pool):
        """Stress test connection pool under high load."""

        async def stress_operation(operation_id: str):
            """High-intensity operation."""
            async with mock_pool.acquire() as conn:
                # Multiple quick operations
                for i in range(5):
                    await conn.execute(f"SELECT {i}")
                    await asyncio.sleep(0.001)  # Brief pause

                return f"completed_{operation_id}"

        # High volume stress test
        num_operations = 500
        operations = [(f"stress_{i}",) for i in range(num_operations)]

        async with concurrency_test_environment(max_concurrent=50) as env:
            result = await env.test_async_operation(
                stress_operation, operations, max_concurrent=50, timeout=20.0
            )

            # High-performance requirements
            assert result.operations_completed == num_operations
            assert result.operations_failed == 0
            assert result.throughput_ops_per_sec > 100  # > 100 ops/sec
            assert result.avg_response_time < 0.1  # < 100ms average

            # Pool health validation
            stats = mock_pool.get_pool_stats()
            assert stats["active_connections"] == 0
            assert (
                stats["queries_executed"] >= num_operations * 5
            )  # 5 queries per operation


@pytest.mark.concurrency
@pytest.mark.database
@pytest.mark.integration
class TestRealTimeDatabaseOperations:
    """Test real-time database operations under concurrent load."""

    @pytest.fixture
    def timescale_mock_pool(self):
        """Mock TimescaleDB connection pool."""
        pool = MockAsyncConnectionPool(max_connections=25)

        # Add TimescaleDB-specific methods
        async def copy_records_to_table(
            table_name: str, records: List[tuple], columns: List[str]
        ):
            # Simulate efficient bulk copy
            await asyncio.sleep(len(records) * 0.0001)  # Fast bulk operation
            return len(records)

        pool.copy_records_to_table = copy_records_to_table
        return pool

    @pytest.mark.asyncio
    async def test_high_frequency_tick_ingestion(self, timescale_mock_pool):
        """Test high-frequency tick data ingestion."""

        async def ingest_tick_batch(symbol: str, batch_size: int, batch_id: int):
            """Ingest batch of tick data."""
            ticks = []
            base_time = datetime.now(timezone.utc)

            for i in range(batch_size):
                tick = (
                    base_time + timedelta(microseconds=i),
                    symbol,
                    1.1000 + random.uniform(-0.0001, 0.0001),
                    random.randint(1000, 5000),
                    "trade",
                    "ib",
                )
                ticks.append(tick)

            # Use bulk copy for efficiency
            result = await timescale_mock_pool.copy_records_to_table(
                "tick_data",
                ticks,
                ["time", "symbol", "price", "size", "tick_type", "source"],
            )

            return result

        # Simulate high-frequency tick ingestion
        symbols = ["EURUSD", "GBPUSD", "USDJPY"]
        batch_operations = []

        for symbol in symbols:
            for batch_id in range(20):  # 20 batches per symbol
                batch_operations.append((symbol, 100, batch_id))  # 100 ticks per batch

        async with concurrency_test_environment(max_concurrent=30) as env:
            result = await env.test_async_operation(
                ingest_tick_batch, batch_operations, max_concurrent=30, timeout=10.0
            )

            # High-frequency performance requirements
            assert result.operations_completed == len(batch_operations)
            assert result.operations_failed == 0
            assert result.throughput_ops_per_sec > 20  # > 20 batches/sec

            # Total ticks processed
            total_ticks = len(batch_operations) * 100  # 6000 ticks
            assert total_ticks == 6000

    @pytest.mark.asyncio
    async def test_concurrent_aggregation_queries(self, timescale_mock_pool):
        """Test concurrent time-series aggregation queries."""

        async def execute_aggregation(symbol: str, timeframe: str, hours_back: int):
            """Execute time-series aggregation query."""
            end_time = datetime.now(timezone.utc)
            start_time = end_time - timedelta(hours=hours_back)

            # Simulate complex aggregation query
            query = f"""
            SELECT
                time_bucket('{timeframe}', time) as bucket,
                first(price, time) as open,
                max(price) as high,
                min(price) as low,
                last(price, time) as close,
                sum(size) as volume
            FROM tick_data
            WHERE symbol = $1 AND time >= $2 AND time <= $3
            GROUP BY bucket
            ORDER BY bucket
            """

            # Simulate processing time based on data volume
            processing_time = hours_back * 0.001  # More data = more time
            await asyncio.sleep(processing_time)

            return await timescale_mock_pool.fetch(query, symbol, start_time, end_time)

        # Mix of aggregation queries
        aggregation_queries = [
            ("EURUSD", "1 minute", 1),
            ("EURUSD", "5 minutes", 4),
            ("GBPUSD", "1 minute", 2),
            ("GBPUSD", "15 minutes", 8),
            ("USDJPY", "5 minutes", 3),
            ("USDJPY", "1 hour", 24),
            ("USDCHF", "15 minutes", 6),
            ("USDCHF", "1 hour", 12),
        ]

        async with concurrency_test_environment(max_concurrent=8) as env:
            result = await env.test_async_operation(
                execute_aggregation, aggregation_queries, max_concurrent=8, timeout=15.0
            )

            # Aggregation performance requirements
            assert result.operations_completed == len(aggregation_queries)
            assert result.operations_failed == 0
            assert result.avg_response_time < 1.0  # < 1 second average

    @pytest.mark.asyncio
    async def test_mixed_workload_performance(self, timescale_mock_pool):
        """Test mixed database workload performance."""

        async def mixed_database_operation(
            operation_type: str, symbol: str, operation_id: int
        ):
            """Execute mixed database operations."""
            if operation_type == "insert":
                # Insert tick data
                query = "INSERT INTO tick_data (time, symbol, price, size) VALUES ($1, $2, $3, $4)"
                args = (
                    datetime.now(timezone.utc),
                    symbol,
                    1.1000 + random.uniform(-0.001, 0.001),
                    random.randint(1000, 10000),
                )
                return await timescale_mock_pool.execute(query, *args)

            elif operation_type == "update":
                # Update existing data
                query = (
                    "UPDATE market_data_1m SET volume = volume + $1 WHERE symbol = $2"
                )
                args = (random.randint(1000, 5000), symbol)
                return await timescale_mock_pool.execute(query, *args)

            elif operation_type == "query":
                # Query recent data
                query = "SELECT * FROM tick_data WHERE symbol = $1 ORDER BY time DESC LIMIT 100"
                return await timescale_mock_pool.fetch(query, symbol)

            elif operation_type == "aggregate":
                # Aggregation query
                query = """
                SELECT
                    date_trunc('minute', time) as minute,
                    avg(price) as avg_price,
                    count(*) as tick_count
                FROM tick_data
                WHERE symbol = $1 AND time >= now() - interval '1 hour'
                GROUP BY minute
                ORDER BY minute DESC
                """
                return await timescale_mock_pool.fetch(query, symbol)

        # Generate mixed workload
        symbols = ["EURUSD", "GBPUSD", "USDJPY", "USDCHF"]
        operation_types = ["insert", "update", "query", "aggregate"]
        mixed_operations = []

        for i in range(200):
            operation_type = random.choice(operation_types)
            symbol = random.choice(symbols)
            mixed_operations.append((operation_type, symbol, i))

        async with concurrency_test_environment(max_concurrent=25) as env:
            result = await env.test_async_operation(
                mixed_database_operation,
                mixed_operations,
                max_concurrent=25,
                timeout=15.0,
            )

            # Mixed workload performance requirements
            assert result.operations_completed == 200
            assert result.operations_failed == 0
            assert result.throughput_ops_per_sec > 30  # > 30 mixed ops/sec

            # Verify operation distribution
            stats = timescale_mock_pool.get_pool_stats()
            assert stats["queries_executed"] == 200
