"""
Unit tests for Database and Caching System.

Tests comprehensive database functionality including:
- Connection pooling and management
- CRUD operations for all entities
- Query optimization
- Transaction management
- Data migrations
- Caching strategies (Redis)
- Cache invalidation
- Time-series data storage
- Sharding and partitioning
- Backup and recovery
"""

import asyncio
import uuid
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any, Dict, List
from unittest.mock import AsyncMock, MagicMock, patch

import pandas as pd
import pytest
from freezegun import freeze_time

from core.database.database_manager import (
    BackupManager,
    CacheManager,
    ConnectionPool,
    DatabaseManager,
    QueryOptimizer,
    TimeSeries,
)


class TestDatabaseManager:
    """Test suite for database and caching system."""

    @pytest.fixture
    def db_config(self):
        """Configuration for database manager."""
        return {
            "connections": {
                "primary": {
                    "host": "localhost",
                    "port": 5432,
                    "database": "fxml4_trading",
                    "user": "trader",
                    "password": "secure_pass",  # pragma: allowlist secret
                    "pool_size": 20,
                    "max_overflow": 10,
                },
                "replica": {
                    "host": "localhost",
                    "port": 5433,
                    "database": "fxml4_trading",
                    "user": "reader",
                    "password": "secure_pass",  # pragma: allowlist secret
                    "pool_size": 30,
                },
                "timeseries": {
                    "type": "timescaledb",
                    "host": "localhost",
                    "port": 5434,
                    "database": "fxml4_timeseries",
                    "compression": True,
                },
            },
            "cache": {
                "type": "redis",
                "host": "localhost",
                "port": 6379,
                "db": 0,
                "ttl_seconds": 300,
                "max_memory": "2gb",
                "eviction_policy": "lru",
            },
            "optimization": {
                "query_timeout_ms": 5000,
                "slow_query_threshold_ms": 100,
                "index_suggestions": True,
                "auto_vacuum": True,
            },
            "backup": {
                "enabled": True,
                "schedule": "0 2 * * *",  # Daily at 2 AM
                "retention_days": 30,
                "compression": "gzip",
            },
        }

    @pytest.fixture
    def sample_trade_data(self):
        """Generate sample trade data."""
        return {
            "trade_id": str(uuid.uuid4()),
            "symbol": "EUR/USD",
            "side": "BUY",
            "quantity": 100000,
            "price": Decimal("1.0500"),
            "timestamp": datetime.now(),
            "broker": "IB",
            "commission": Decimal("2.50"),
            "status": "EXECUTED",
        }

    @pytest.fixture
    def database_manager(self, db_config):
        """Create database manager for testing."""
        return DatabaseManager(config=db_config)

    @pytest.fixture
    def cache_manager(self, db_config):
        """Create cache manager for testing."""
        return CacheManager(config=db_config["cache"])

    @pytest.mark.asyncio
    async def test_connection_pool_management(self, database_manager):
        """Test database connection pooling."""
        # Get connection from pool
        conn = await database_manager.get_connection()

        assert conn is not None
        assert conn["status"] == "active"
        assert "connection_id" in conn

        # Check pool statistics
        pool_stats = await database_manager.get_pool_stats()

        assert "active_connections" in pool_stats
        assert "idle_connections" in pool_stats
        assert "total_connections" in pool_stats
        assert pool_stats["total_connections"] <= 30  # pool_size + max_overflow

        # Release connection
        await database_manager.release_connection(conn)

        # Check connection returned to pool
        pool_stats_after = await database_manager.get_pool_stats()
        assert pool_stats_after["idle_connections"] > pool_stats["idle_connections"]

    @pytest.mark.asyncio
    async def test_crud_operations_for_trades(
        self, database_manager, sample_trade_data
    ):
        """Test CRUD operations for trade entities."""
        # Create
        create_result = await database_manager.create_trade(sample_trade_data)
        assert create_result["status"] == "created"
        assert "trade_id" in create_result

        trade_id = create_result["trade_id"]

        # Read
        trade = await database_manager.get_trade(trade_id)
        assert trade is not None
        assert trade["symbol"] == "EUR/USD"
        assert trade["quantity"] == 100000

        # Update
        update_data = {"status": "SETTLED", "settlement_date": datetime.now()}
        update_result = await database_manager.update_trade(trade_id, update_data)
        assert update_result["status"] == "updated"

        # Verify update
        updated_trade = await database_manager.get_trade(trade_id)
        assert updated_trade["status"] == "SETTLED"

        # Delete
        delete_result = await database_manager.delete_trade(trade_id)
        assert delete_result["status"] == "deleted"

        # Verify deletion
        deleted_trade = await database_manager.get_trade(trade_id)
        assert deleted_trade is None

    @pytest.mark.asyncio
    async def test_batch_insert_operations(self, database_manager):
        """Test batch insert for high-volume data."""
        # Generate batch data
        trades = []
        for i in range(1000):
            trades.append(
                {
                    "trade_id": str(uuid.uuid4()),
                    "symbol": f"PAIR_{i % 10}",
                    "side": "BUY" if i % 2 == 0 else "SELL",
                    "quantity": 100000 * (i % 5 + 1),
                    "price": Decimal("1.0500") + Decimal(str(i * 0.0001)),
                    "timestamp": datetime.now() - timedelta(seconds=i),
                    "broker": "IB",
                    "commission": Decimal("2.50"),
                    "status": "EXECUTED",
                }
            )

        # Batch insert
        result = await database_manager.batch_insert_trades(trades)

        assert result["status"] == "inserted"
        assert result["count"] == 1000
        assert result["execution_time_ms"] < 1000  # Should be fast

    @pytest.mark.asyncio
    async def test_complex_query_with_joins(self, database_manager):
        """Test complex queries with multiple joins."""
        query = """
        SELECT
            t.symbol,
            COUNT(t.trade_id) as trade_count,
            SUM(t.quantity) as total_volume,
            AVG(t.price) as avg_price,
            SUM(t.commission) as total_commission
        FROM trades t
        JOIN accounts a ON t.account_id = a.account_id
        JOIN brokers b ON t.broker_id = b.broker_id
        WHERE
            t.timestamp >= %s
            AND t.status = %s
            AND a.active = true
        GROUP BY t.symbol
        ORDER BY total_volume DESC
        LIMIT 10
        """

        params = [datetime.now() - timedelta(days=7), "EXECUTED"]
        result = await database_manager.execute_query(query, params)

        assert "rows" in result
        assert "execution_time_ms" in result
        assert "row_count" in result

    @pytest.mark.asyncio
    async def test_transaction_management(self, database_manager):
        """Test database transaction with rollback."""
        # Start transaction
        tx = await database_manager.begin_transaction()

        try:
            # Insert trade
            trade1 = await database_manager.create_trade(
                {
                    "trade_id": str(uuid.uuid4()),
                    "symbol": "EUR/USD",
                    "quantity": 100000,
                    "price": Decimal("1.0500"),
                },
                transaction=tx,
            )

            # Insert another trade
            trade2 = await database_manager.create_trade(
                {
                    "trade_id": str(uuid.uuid4()),
                    "symbol": "GBP/USD",
                    "quantity": 200000,
                    "price": Decimal("1.2500"),
                },
                transaction=tx,
            )

            # Simulate error
            raise Exception("Simulated error")

        except Exception:
            # Rollback transaction
            await database_manager.rollback_transaction(tx)

            # Verify trades were not saved
            trade1_check = await database_manager.get_trade(trade1["trade_id"])
            trade2_check = await database_manager.get_trade(trade2["trade_id"])

            assert trade1_check is None
            assert trade2_check is None

    @pytest.mark.asyncio
    async def test_redis_caching_operations(self, cache_manager):
        """Test Redis caching functionality."""
        # Set cache
        key = "trade:12345"
        value = {
            "symbol": "EUR/USD",
            "price": "1.0500",
            "timestamp": datetime.now().isoformat(),
        }

        set_result = await cache_manager.set(key, value, ttl=60)
        assert set_result is True

        # Get from cache
        cached_value = await cache_manager.get(key)
        assert cached_value is not None
        assert cached_value["symbol"] == "EUR/USD"

        # Check TTL
        ttl = await cache_manager.get_ttl(key)
        assert 55 < ttl <= 60

        # Delete from cache
        delete_result = await cache_manager.delete(key)
        assert delete_result is True

        # Verify deletion
        deleted_value = await cache_manager.get(key)
        assert deleted_value is None

    @pytest.mark.asyncio
    async def test_cache_invalidation_strategies(self, cache_manager):
        """Test different cache invalidation strategies."""
        # Set multiple cache entries
        await cache_manager.set("market:EUR/USD", {"price": "1.0500"})
        await cache_manager.set("market:GBP/USD", {"price": "1.2500"})
        await cache_manager.set("order:123", {"status": "pending"})

        # Pattern-based invalidation
        invalidated = await cache_manager.invalidate_pattern("market:*")
        assert invalidated == 2

        # Verify market keys are deleted
        eur_value = await cache_manager.get("market:EUR/USD")
        gbp_value = await cache_manager.get("market:GBP/USD")
        order_value = await cache_manager.get("order:123")

        assert eur_value is None
        assert gbp_value is None
        assert order_value is not None  # Should still exist

    @pytest.mark.asyncio
    async def test_timeseries_data_storage(self, database_manager):
        """Test time-series data storage and retrieval."""
        # Insert time-series data
        tick_data = []
        base_time = datetime.now()

        for i in range(1000):
            tick_data.append(
                {
                    "symbol": "EUR/USD",
                    "timestamp": base_time + timedelta(milliseconds=i * 100),
                    "bid": Decimal("1.0500") + Decimal(str(i * 0.0001)),
                    "ask": Decimal("1.0502") + Decimal(str(i * 0.0001)),
                    "volume": 100000 * (i % 10 + 1),
                }
            )

        # Insert into TimescaleDB
        result = await database_manager.insert_timeseries(tick_data)
        assert result["status"] == "inserted"
        assert result["count"] == 1000

        # Query with time range
        query_result = await database_manager.query_timeseries(
            symbol="EUR/USD",
            start_time=base_time,
            end_time=base_time + timedelta(seconds=100),
            aggregation="1m",
        )

        assert "data" in query_result
        assert len(query_result["data"]) > 0
        assert "compression_ratio" in query_result

    @pytest.mark.asyncio
    async def test_database_sharding(self, database_manager):
        """Test database sharding for scalability."""
        # Configure sharding
        shard_config = {"strategy": "hash", "shard_key": "account_id", "shard_count": 4}

        sharding_result = await database_manager.configure_sharding(shard_config)
        assert sharding_result["status"] == "configured"

        # Test data distribution
        test_accounts = ["ACC001", "ACC002", "ACC003", "ACC004"]
        shard_distribution = {}

        for account_id in test_accounts:
            shard = await database_manager.get_shard(account_id)
            shard_distribution[account_id] = shard["shard_id"]

        # Verify distribution across shards
        unique_shards = set(shard_distribution.values())
        assert len(unique_shards) >= 2  # Data should be distributed

    @pytest.mark.asyncio
    async def test_query_optimization(self, database_manager):
        """Test query optimization and index suggestions."""
        # Analyze slow query
        slow_query = """
        SELECT * FROM trades
        WHERE symbol = 'EUR/USD'
        AND timestamp > '2024-01-01'
        ORDER BY timestamp DESC
        """

        analysis = await database_manager.analyze_query(slow_query)

        assert "execution_plan" in analysis
        assert "estimated_cost" in analysis
        assert "index_suggestions" in analysis

        # Check for index suggestions
        if analysis["index_suggestions"]:
            suggestion = analysis["index_suggestions"][0]
            assert "table" in suggestion
            assert "columns" in suggestion
            assert "type" in suggestion

        # Apply optimization
        optimization_result = await database_manager.optimize_query(slow_query)
        assert optimization_result["optimized_query"] is not None
        assert optimization_result["expected_speedup"] > 1.0

    @pytest.mark.asyncio
    async def test_database_backup_and_recovery(self, database_manager):
        """Test database backup and recovery procedures."""
        # Create backup
        backup_result = await database_manager.create_backup(
            backup_type="full", compression="gzip"
        )

        assert backup_result["status"] == "completed"
        assert "backup_id" in backup_result
        assert "size_mb" in backup_result
        assert "duration_seconds" in backup_result

        backup_id = backup_result["backup_id"]

        # List backups
        backups = await database_manager.list_backups()
        assert len(backups) > 0
        assert any(b["backup_id"] == backup_id for b in backups)

        # Test recovery (dry run)
        recovery_result = await database_manager.test_recovery(
            backup_id=backup_id, target_time=datetime.now()
        )

        assert recovery_result["status"] == "validated"
        assert recovery_result["estimated_recovery_time_seconds"] > 0

    @pytest.mark.asyncio
    async def test_connection_failover(self, database_manager):
        """Test automatic failover to replica."""
        # Simulate primary failure
        await database_manager.simulate_primary_failure()

        # Check connection status
        status = await database_manager.get_connection_status()

        assert status["primary_available"] is False
        assert status["using_replica"] is True
        assert status["replica_lag_seconds"] < 10

        # Test read operations work on replica
        read_result = await database_manager.get_trade("some_id")
        assert read_result is not None or read_result is None  # Should not error

    @pytest.mark.asyncio
    async def test_cache_warmup(self, cache_manager, database_manager):
        """Test cache warmup strategies."""
        # Define warmup queries
        warmup_config = {
            "queries": [
                "SELECT * FROM active_orders",
                "SELECT * FROM recent_trades LIMIT 100",
                "SELECT * FROM market_data WHERE symbol IN (SELECT DISTINCT symbol FROM positions)",
            ],
            "ttl": 3600,
        }

        # Execute warmup
        warmup_result = await cache_manager.warmup_cache(
            database_manager, warmup_config
        )

        assert warmup_result["status"] == "completed"
        assert warmup_result["entries_cached"] > 0
        assert warmup_result["duration_ms"] < 5000

    @pytest.mark.asyncio
    async def test_distributed_caching(self, cache_manager):
        """Test distributed caching with Redis cluster."""
        # Configure cluster
        cluster_config = {
            "nodes": [
                {"host": "localhost", "port": 6379},
                {"host": "localhost", "port": 6380},
                {"host": "localhost", "port": 6381},
            ],
            "replicas": 1,
        }

        cluster_result = await cache_manager.configure_cluster(cluster_config)
        assert cluster_result["status"] == "configured"
        assert cluster_result["total_slots"] == 16384

        # Test data distribution
        test_keys = [f"key_{i}" for i in range(100)]
        distribution = {}

        for key in test_keys:
            node = await cache_manager.get_node_for_key(key)
            distribution[node] = distribution.get(node, 0) + 1

        # Verify even distribution
        assert len(distribution) >= 2  # Data should be distributed

    @pytest.mark.asyncio
    async def test_data_migration(self, database_manager):
        """Test database schema migrations."""
        # Create migration
        migration = {
            "version": "2.0.0",
            "description": "Add new columns for ML predictions",
            "up_script": """
                ALTER TABLE trades ADD COLUMN ml_prediction DECIMAL(10,5);
                ALTER TABLE trades ADD COLUMN prediction_confidence FLOAT;
                CREATE INDEX idx_ml_prediction ON trades(ml_prediction);
            """,
            "down_script": """
                DROP INDEX idx_ml_prediction;
                ALTER TABLE trades DROP COLUMN prediction_confidence;
                ALTER TABLE trades DROP COLUMN ml_prediction;
            """,
        }

        # Apply migration
        migration_result = await database_manager.apply_migration(migration)

        assert migration_result["status"] == "applied"
        assert migration_result["version"] == "2.0.0"
        assert "execution_time_ms" in migration_result

        # Verify migration
        schema = await database_manager.get_table_schema("trades")
        assert "ml_prediction" in [col["name"] for col in schema["columns"]]

    @pytest.mark.asyncio
    async def test_database_monitoring(self, database_manager):
        """Test database performance monitoring."""
        # Get performance metrics
        metrics = await database_manager.get_performance_metrics()

        assert "queries_per_second" in metrics
        assert "average_query_time_ms" in metrics
        assert "cache_hit_ratio" in metrics
        assert "connection_pool_usage" in metrics
        assert "disk_usage_mb" in metrics
        assert "index_usage" in metrics

        # Check for slow queries
        slow_queries = await database_manager.get_slow_queries(
            threshold_ms=100, limit=10
        )

        if slow_queries:
            query = slow_queries[0]
            assert "query_text" in query
            assert "execution_time_ms" in query
            assert "timestamp" in query

    @pytest.mark.asyncio
    async def test_data_archival(self, database_manager):
        """Test data archival for old records."""
        # Configure archival
        archival_config = {
            "retention_days": 90,
            "archive_table": "trades_archive",
            "compression": True,
            "delete_after_archive": True,
        }

        # Run archival
        archival_result = await database_manager.archive_old_data(
            table="trades", config=archival_config
        )

        assert archival_result["status"] == "completed"
        assert "records_archived" in archival_result
        assert "space_saved_mb" in archival_result

    @pytest.mark.asyncio
    async def test_full_text_search(self, database_manager):
        """Test full-text search capabilities."""
        # Create search index
        index_result = await database_manager.create_search_index(
            table="trade_notes", columns=["description", "tags"]
        )
        assert index_result["status"] == "created"

        # Perform search
        search_result = await database_manager.search(
            query="elliott wave breakout", table="trade_notes", limit=10
        )

        assert "results" in search_result
        assert "total_matches" in search_result
        if search_result["results"]:
            result = search_result["results"][0]
            assert "score" in result
            assert "highlights" in result

    @pytest.mark.asyncio
    async def test_database_replication_lag(self, database_manager):
        """Test monitoring of replication lag."""
        lag_info = await database_manager.get_replication_lag()

        assert "lag_seconds" in lag_info
        assert "is_healthy" in lag_info
        assert lag_info["lag_seconds"] >= 0

        # Alert if lag is too high
        if lag_info["lag_seconds"] > 5:
            assert "alert" in lag_info
            assert lag_info["alert"]["severity"] in ["warning", "critical"]
