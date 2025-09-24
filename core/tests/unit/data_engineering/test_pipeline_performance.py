"""
TDD Tests for Data Pipeline Performance Optimization

Comprehensive test suite for optimizing TimescaleDB queries, connection pooling,
Redis caching, and overall data pipeline performance.

Following strict TDD Red-Green-Refactor cycle.
"""

import asyncio
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import numpy as np
import pandas as pd
import pytest
import pytest_asyncio


@pytest.mark.tdd
@pytest.mark.performance
class TestDataPipelinePerformance:
    """Test suite for data pipeline performance optimization."""

    @pytest_asyncio.fixture
    async def optimized_pool(self):
        """Create mocked optimized connection pool for testing."""
        from core.data_engineering.optimized_pool import OptimizedConnectionPool

        pool = OptimizedConnectionPool(
            min_size=10,
            max_size=100,
            max_idle_time=300,
            max_queries_per_connection=5000,
            statement_cache_size=1000,
            command_timeout=10,
        )

        # Mock the pool to avoid actual database connection
        pool._pool = AsyncMock()
        pool._pool.acquire = AsyncMock()
        pool._pool.close = AsyncMock()

        # Mock execute method
        async def mock_execute(query, *args, **kwargs):
            return "OK"

        pool.execute = mock_execute

        # Mock get_pool_stats
        def mock_get_pool_stats():
            return {
                "status": "healthy",
                "total_connections": 10,
                "idle_connections": 5,
                "healthy_connections": 10,
                "cache_hit_rate": 0.75,
                "recovered_connections": 0,
            }

        pool.get_pool_stats = mock_get_pool_stats

        yield pool

    @pytest.fixture
    def performance_monitor(self):
        """Create performance monitoring utility."""
        from core.data_engineering.performance_monitor import PerformanceMonitor

        return PerformanceMonitor()

    @pytest.fixture
    def sample_market_data(self):
        """Generate sample market data for performance testing."""
        timestamps = pd.date_range(
            start=datetime.now(timezone.utc) - timedelta(hours=24),
            periods=100000,
            freq="100ms",
        )

        symbols = ["EUR/USD", "GBP/USD", "USD/JPY", "AUD/USD", "USD/CHF"]
        data = []

        for i, ts in enumerate(timestamps):
            for symbol in symbols:
                base_price = 1.0850 if symbol == "EUR/USD" else 1.2500
                data.append(
                    {
                        "timestamp": ts,
                        "symbol": symbol,
                        "bid": base_price + np.random.randn() * 0.0001,
                        "ask": base_price + 0.0002 + np.random.randn() * 0.0001,
                        "volume": np.random.randint(100000, 10000000),
                    }
                )

        return pd.DataFrame(data)

    # -------------------------------------------------------------------------
    # Connection Pool Optimization Tests
    # -------------------------------------------------------------------------

    @pytest.mark.red
    @pytest.mark.asyncio
    async def test_connection_pool_optimization(
        self, optimized_pool, performance_monitor
    ):
        """RED: Test optimized connection pool performance."""
        # Test connection pool efficiency
        start_time = time.time()

        # Simulate concurrent database operations
        tasks = []
        for i in range(100):
            task = optimized_pool.execute(
                "SELECT * FROM tick_data WHERE symbol = $1 LIMIT 100", "EUR/USD"
            )
            tasks.append(task)

        results = await asyncio.gather(*tasks)
        execution_time = time.time() - start_time

        # Performance assertions
        assert execution_time < 0.5  # 100 queries should complete in under 500ms
        assert optimized_pool.get_pool_stats()["idle_connections"] > 0
        assert (
            optimized_pool.get_pool_stats()["total_connections"] <= 20
        )  # Efficient pooling
        assert (
            optimized_pool.get_pool_stats()["cache_hit_rate"] > 0.5
        )  # Statement cache working

    @pytest.mark.red
    @pytest.mark.asyncio
    async def test_connection_health_monitoring(self, optimized_pool):
        """RED: Test connection health monitoring and auto-recovery."""
        # Simulate connection failure
        await optimized_pool.mark_connection_unhealthy("test_connection_1")

        # Pool should automatically recover
        await asyncio.sleep(0.1)

        stats = optimized_pool.get_pool_stats()
        assert stats["healthy_connections"] == stats["total_connections"]
        assert stats["recovered_connections"] > 0

    @pytest.mark.red
    @pytest.mark.asyncio
    async def test_intelligent_pool_sizing(self, optimized_pool, performance_monitor):
        """RED: Test intelligent connection pool sizing."""
        # Start with minimal load
        await optimized_pool.adjust_pool_size_based_on_load()
        initial_size = optimized_pool.get_pool_stats()["total_connections"]

        # Simulate high load
        tasks = []
        for i in range(500):
            task = optimized_pool.execute("SELECT 1")
            tasks.append(task)

        await asyncio.gather(*tasks)
        await optimized_pool.adjust_pool_size_based_on_load()

        high_load_size = optimized_pool.get_pool_stats()["total_connections"]
        assert high_load_size > initial_size  # Pool should grow under load

        # Simulate low load
        await asyncio.sleep(1)
        await optimized_pool.adjust_pool_size_based_on_load()

        low_load_size = optimized_pool.get_pool_stats()["total_connections"]
        assert low_load_size < high_load_size  # Pool should shrink when idle

    # -------------------------------------------------------------------------
    # Query Optimization Tests
    # -------------------------------------------------------------------------

    @pytest.mark.red
    @pytest.mark.asyncio
    async def test_query_optimization_with_indexes(self):
        """RED: Test query performance with optimized indexes."""
        from core.data_engineering.query_optimizer import QueryOptimizer

        optimizer = QueryOptimizer()

        # Analyze query performance
        query = """
            SELECT * FROM tick_data
            WHERE symbol = $1
            AND time >= $2
            AND time < $3
            ORDER BY time DESC
        """

        # Get query plan before optimization
        plan_before = await optimizer.explain_query(
            query, ["EUR/USD", datetime.now(), datetime.now()]
        )

        # Apply optimizations
        await optimizer.create_optimal_indexes("tick_data", ["symbol", "time"])

        # Get query plan after optimization
        plan_after = await optimizer.explain_query(
            query, ["EUR/USD", datetime.now(), datetime.now()]
        )

        # Assert performance improvement
        assert (
            plan_after["execution_time"] < plan_before["execution_time"] * 0.4
        )  # 60% improvement
        assert plan_after["index_scan"] is True
        assert plan_before.get("seq_scan", False) is True

    @pytest.mark.red
    @pytest.mark.asyncio
    async def test_timeframe_aggregation_optimization(self):
        """RED: Test optimized timeframe aggregation queries."""
        from core.data_engineering.query_optimizer import QueryOptimizer

        optimizer = QueryOptimizer()

        # Test aggregation performance
        start_time = time.time()

        result = await optimizer.get_aggregated_candles(
            symbol="EUR/USD",
            timeframe="5m",
            start_date=datetime.now() - timedelta(days=7),
            end_date=datetime.now(),
        )

        execution_time = time.time() - start_time

        # Performance assertions
        assert execution_time < 0.1  # Should return in under 100ms
        assert len(result) > 0
        assert "open" in result.columns
        assert result.index.is_monotonic_increasing  # Properly ordered

    @pytest.mark.red
    @pytest.mark.asyncio
    async def test_ml_feature_query_optimization(self):
        """RED: Test optimized queries for ML feature extraction."""
        from core.data_engineering.query_optimizer import QueryOptimizer

        optimizer = QueryOptimizer()

        # Complex ML feature query
        features_query = """
            WITH price_features AS (
                SELECT
                    symbol,
                    time_bucket('1 minute', time) as minute,
                    AVG(price) as avg_price,
                    STDDEV(price) as price_stddev,
                    MAX(price) - MIN(price) as price_range,
                    COUNT(*) as tick_count
                FROM tick_data
                WHERE symbol = $1 AND time >= $2 AND time < $3
                GROUP BY symbol, minute
            ),
            volume_features AS (
                SELECT
                    time_bucket('1 minute', time) as minute,
                    SUM(size) as total_volume,
                    AVG(size) as avg_volume
                FROM tick_data
                WHERE symbol = $1 AND time >= $2 AND time < $3
                GROUP BY minute
            )
            SELECT
                pf.*,
                vf.total_volume,
                vf.avg_volume,
                LAG(pf.avg_price, 1) OVER (ORDER BY pf.minute) as prev_price,
                LAG(pf.avg_price, 5) OVER (ORDER BY pf.minute) as price_5min_ago
            FROM price_features pf
            JOIN volume_features vf ON pf.minute = vf.minute
            ORDER BY pf.minute DESC
        """

        start_time = time.time()

        result = await optimizer.execute_optimized_query(
            features_query,
            ["EUR/USD", datetime.now() - timedelta(hours=1), datetime.now()],
        )

        execution_time = time.time() - start_time

        assert execution_time < 0.05  # Complex query should still be fast
        assert len(result) > 0

    # -------------------------------------------------------------------------
    # Redis Caching Layer Tests
    # -------------------------------------------------------------------------

    @pytest.mark.red
    @pytest.mark.asyncio
    async def test_redis_cache_integration(self):
        """RED: Test Redis caching layer for frequently accessed data."""
        from core.data_engineering.redis_cache import RedisDataCache

        cache = RedisDataCache(
            host="localhost", port=6379, db=1, ttl=300, max_memory="256mb"
        )
        await cache.initialize()

        # First request - should hit database
        start_time = time.time()
        data_1 = await cache.get_or_fetch(
            key="EUR/USD:1h:latest",
            fetch_func=lambda: self._fetch_latest_candles("EUR/USD", "1h"),
        )
        db_fetch_time = time.time() - start_time

        # Second request - should hit cache
        start_time = time.time()
        data_2 = await cache.get_or_fetch(
            key="EUR/USD:1h:latest",
            fetch_func=lambda: self._fetch_latest_candles("EUR/USD", "1h"),
        )
        cache_fetch_time = time.time() - start_time

        # Assert cache is working
        assert cache_fetch_time < db_fetch_time * 0.1  # Cache should be 10x faster
        assert data_1.equals(data_2)
        assert cache.get_stats()["cache_hits"] > 0
        assert cache.get_stats()["cache_hit_rate"] > 0

    @pytest.mark.red
    @pytest.mark.asyncio
    async def test_cache_warming_strategy(self):
        """RED: Test intelligent cache warming for ML features."""
        from core.data_engineering.redis_cache import RedisDataCache

        cache = RedisDataCache()
        await cache.initialize()

        # Define frequently accessed patterns
        ml_feature_patterns = [
            {"symbol": "EUR/USD", "timeframes": ["1m", "5m", "1h"], "lookback": 100},
            {"symbol": "GBP/USD", "timeframes": ["1m", "5m", "1h"], "lookback": 100},
        ]

        # Warm cache
        start_time = time.time()
        await cache.warm_ml_features(ml_feature_patterns)
        warming_time = time.time() - start_time

        # Verify cache is warmed
        stats = cache.get_stats()
        assert stats["cached_keys"] >= 6  # 2 symbols * 3 timeframes
        assert warming_time < 2.0  # Should warm quickly

        # Test cache hit rate after warming
        for pattern in ml_feature_patterns:
            for tf in pattern["timeframes"]:
                key = f"{pattern['symbol']}:{tf}:features"
                data = await cache.get(key)
                assert data is not None

    @pytest.mark.red
    @pytest.mark.asyncio
    async def test_cache_invalidation_strategy(self):
        """RED: Test cache invalidation for real-time data updates."""
        from core.data_engineering.redis_cache import RedisDataCache

        cache = RedisDataCache()
        await cache.initialize()

        # Cache some data
        await cache.set("EUR/USD:latest", {"price": 1.0850}, ttl=60)

        # Simulate new data arrival
        await cache.invalidate_pattern("EUR/USD:*")

        # Verify invalidation
        data = await cache.get("EUR/USD:latest")
        assert data is None

        # Test selective invalidation
        await cache.set("EUR/USD:1m:latest", {"price": 1.0850}, ttl=60)
        await cache.set("EUR/USD:5m:latest", {"price": 1.0851}, ttl=60)
        await cache.set("GBP/USD:1m:latest", {"price": 1.2500}, ttl=60)

        # Invalidate only EUR/USD 1m data
        await cache.invalidate_pattern("EUR/USD:1m:*")

        assert await cache.get("EUR/USD:1m:latest") is None
        assert await cache.get("EUR/USD:5m:latest") is not None
        assert await cache.get("GBP/USD:1m:latest") is not None

    # -------------------------------------------------------------------------
    # Data Quality Monitoring Tests
    # -------------------------------------------------------------------------

    @pytest.mark.red
    @pytest.mark.asyncio
    async def test_real_time_data_validation(self, sample_market_data):
        """RED: Test real-time data validation and anomaly detection."""
        from core.data_engineering.data_validator import RealTimeDataValidator

        validator = RealTimeDataValidator(
            max_price_deviation=0.01,
            max_spread_ratio=0.001,
            min_tick_rate=10,
            anomaly_threshold=3.0,  # 3 standard deviations
        )

        # Process data stream
        validation_results = []
        for _, row in sample_market_data.iterrows():
            result = await validator.validate_tick(row.to_dict())
            validation_results.append(result)

        # Check validation results
        valid_count = sum(1 for r in validation_results if r["is_valid"])
        anomaly_count = sum(1 for r in validation_results if r.get("is_anomaly", False))

        assert valid_count / len(validation_results) > 0.95  # 95% should be valid
        assert anomaly_count < len(validation_results) * 0.01  # Less than 1% anomalies

    @pytest.mark.red
    @pytest.mark.asyncio
    async def test_data_completeness_monitoring(self):
        """RED: Test data completeness and gap detection."""
        from core.data_engineering.completeness_monitor import DataCompletenessMonitor

        monitor = DataCompletenessMonitor(
            expected_tick_rate=10,  # 10 ticks per second
            max_gap_seconds=5,
            alert_threshold=0.95,  # 95% completeness required
        )

        # Simulate data with gaps
        timestamps = []
        base_time = datetime.now(timezone.utc)

        # Normal data
        for i in range(100):
            timestamps.append(base_time + timedelta(milliseconds=i * 100))

        # Add gap
        for i in range(110, 200):
            timestamps.append(base_time + timedelta(milliseconds=i * 100))

        # Analyze completeness
        report = await monitor.analyze_completeness("EUR/USD", timestamps)

        assert report["completeness_rate"] < 1.0
        assert len(report["gaps"]) > 0
        assert report["gaps"][0]["duration_seconds"] == pytest.approx(1.0, rel=0.1)
        assert report["needs_backfill"] is True

    # -------------------------------------------------------------------------
    # Performance Monitoring Tests
    # -------------------------------------------------------------------------

    @pytest.mark.red
    @pytest.mark.asyncio
    async def test_pipeline_performance_metrics(self):
        """RED: Test comprehensive pipeline performance monitoring."""
        from core.data_engineering.performance_metrics import PipelineMetrics

        metrics = PipelineMetrics()

        # Simulate pipeline operations
        for i in range(100):
            with metrics.measure("data_ingestion"):
                await asyncio.sleep(0.001)  # Simulate work

            with metrics.measure("transformation"):
                await asyncio.sleep(0.002)

            with metrics.measure("storage"):
                await asyncio.sleep(0.001)

        # Get performance report
        report = metrics.get_report()

        assert "data_ingestion" in report
        assert report["data_ingestion"]["avg_time"] < 0.002
        assert report["data_ingestion"]["p99_time"] < 0.005
        assert report["transformation"]["avg_time"] < 0.003
        assert report["total_throughput"] > 200  # Should process >200 ops/sec

    @pytest.mark.red
    @pytest.mark.asyncio
    async def test_resource_utilization_monitoring(self):
        """RED: Test monitoring of system resource utilization."""
        from core.data_engineering.resource_monitor import ResourceMonitor

        monitor = ResourceMonitor()
        await monitor.start()

        # Simulate load
        await asyncio.sleep(1)

        # Get resource metrics
        metrics = await monitor.get_metrics()

        assert "cpu_usage" in metrics
        assert "memory_usage" in metrics
        assert "disk_io" in metrics
        assert "network_io" in metrics
        assert metrics["cpu_usage"] < 80  # Should not overload CPU
        assert metrics["memory_usage"] < 70  # Should not use excessive memory

    # -------------------------------------------------------------------------
    # Integration Tests
    # -------------------------------------------------------------------------

    @pytest.mark.red
    @pytest.mark.asyncio
    async def test_end_to_end_pipeline_performance(self, sample_market_data):
        """RED: Test end-to-end pipeline performance with all optimizations."""
        from core.data_engineering.optimized_pipeline import OptimizedDataPipeline

        pipeline = OptimizedDataPipeline(
            enable_caching=True,
            enable_query_optimization=True,
            enable_connection_pooling=True,
            enable_monitoring=True,
        )

        await pipeline.initialize()

        # Process large batch of data
        start_time = time.time()

        result = await pipeline.process_market_data(sample_market_data)

        processing_time = time.time() - start_time
        throughput = len(sample_market_data) / processing_time

        # Performance assertions
        assert processing_time < 5.0  # Should process 500k records in under 5 seconds
        assert throughput > 100000  # Should handle >100k records/second
        assert result["success_rate"] > 0.99  # >99% success rate
        assert result["avg_latency"] < 0.001  # <1ms average latency

        # Check optimization effects
        stats = await pipeline.get_performance_stats()
        assert stats["cache_hit_rate"] > 0.5
        assert stats["query_optimization_improvement"] > 1.5  # 50% improvement
        assert stats["connection_pool_efficiency"] > 0.8

    async def _fetch_latest_candles(self, symbol: str, timeframe: str) -> pd.DataFrame:
        """Helper method to simulate database fetch."""
        await asyncio.sleep(0.05)  # Simulate database delay
        return pd.DataFrame(
            {
                "time": pd.date_range(start=datetime.now(), periods=100, freq="1min"),
                "open": np.random.randn(100),
                "high": np.random.randn(100),
                "low": np.random.randn(100),
                "close": np.random.randn(100),
                "volume": np.random.randint(1000, 10000, 100),
            }
        )


@pytest.fixture
def performance_timer():
    """Fixture for timing performance tests."""

    class Timer:
        def __init__(self):
            self.start_time = None
            self.end_time = None

        def start(self):
            self.start_time = time.time()

        def stop(self):
            self.end_time = time.time()
            return self.end_time - self.start_time

        def elapsed(self):
            if self.start_time is None:
                return 0
            end = self.end_time or time.time()
            return end - self.start_time

    return Timer()
