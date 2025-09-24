"""
Optimized Data Pipeline

Integrates all optimization components for high-performance data processing
with validation, caching, and monitoring.

Following TDD Green phase - implementation to pass integration tests.
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

from .completeness_monitor import CompletenessMonitor
from .data_validator import (
    DataValidator,
    RangeValidationRule,
    SpreadValidationRule,
    ValidationSeverity,
)
from .optimized_pool import OptimizedConnectionPool
from .performance_monitor import PerformanceMonitor, PipelineMetrics, ResourceMonitor
from .query_optimizer import QueryOptimizer
from .redis_cache import RedisDataCache

logger = logging.getLogger(__name__)


class OptimizedDataPipeline:
    """
    High-performance data pipeline with all optimizations integrated.

    Features:
    - Optimized connection pooling
    - Query optimization with indexing
    - Redis caching layer
    - Real-time data validation
    - Completeness monitoring
    - Performance metrics tracking
    """

    def __init__(self):
        """Initialize optimized data pipeline."""
        # Core components
        self.pool = OptimizedConnectionPool()
        self.query_optimizer = QueryOptimizer(self.pool)
        self.cache = RedisDataCache()

        # Monitoring components
        self.performance_monitor = PerformanceMonitor()
        self.pipeline_metrics = PipelineMetrics()
        self.resource_monitor = ResourceMonitor()

        # Validation components
        self.validator = DataValidator()
        self.completeness_monitor = CompletenessMonitor()

        # Pipeline state
        self._initialized = False
        self._processing_stats = {
            "ticks_processed": 0,
            "candles_processed": 0,
            "cache_operations": 0,
            "validation_errors": 0,
        }

    async def initialize(self):
        """Initialize all pipeline components."""
        if self._initialized:
            return

        logger.info("Initializing optimized data pipeline...")

        # Initialize connection pool
        await self.pool.initialize()

        # Initialize query optimizer
        await self.query_optimizer.initialize()

        # Initialize cache
        await self.cache.initialize()

        # Start monitoring
        await self.resource_monitor.start()
        await self.completeness_monitor.start_monitoring()

        # Setup validation rules
        self._setup_validation_rules()

        # Create optimal indexes for common queries
        await self._create_indexes()

        self._initialized = True
        logger.info("Data pipeline initialized successfully")

    async def shutdown(self):
        """Shutdown pipeline components."""
        logger.info("Shutting down data pipeline...")

        # Stop monitoring
        await self.resource_monitor.stop()
        await self.completeness_monitor.stop_monitoring()

        # Close connections
        await self.cache.close()
        await self.pool.close()

        self._initialized = False
        logger.info("Data pipeline shutdown complete")

    def _setup_validation_rules(self):
        """Setup data validation rules."""
        # Tick data rules
        self.validator.add_rule(
            "tick",
            RangeValidationRule(
                "bid_range", "bid", 0.0001, 10000.0, ValidationSeverity.ERROR
            ),
        )
        self.validator.add_rule(
            "tick",
            RangeValidationRule(
                "ask_range", "ask", 0.0001, 10000.0, ValidationSeverity.ERROR
            ),
        )
        self.validator.add_rule(
            "tick",
            SpreadValidationRule(
                "spread_check", max_spread_pips=20, severity=ValidationSeverity.WARNING
            ),
        )

        # Candle data rules
        self.validator.add_rule(
            "candle",
            RangeValidationRule(
                "volume_range", "volume", 0, 1e12, ValidationSeverity.WARNING
            ),
        )

        logger.info("Validation rules configured")

    async def _create_indexes(self):
        """Create optimal indexes for common queries."""
        # Market data indexes
        await self.query_optimizer.create_optimal_indexes(
            "market_data_1m", ["symbol", "time", "volume"]
        )

        # Tick data indexes
        await self.query_optimizer.create_optimal_indexes(
            "tick_data", ["symbol", "timestamp", "bid", "ask"]
        )

        logger.info("Database indexes created")

    async def process_tick(self, tick_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process single tick with full optimization pipeline.

        Args:
            tick_data: Tick data to process

        Returns:
            Processed tick with metrics
        """
        with self.performance_monitor.measure("tick_processing"):
            # Validate tick
            validation_result = await self.validator.validate_tick(tick_data)
            if not validation_result["is_valid"]:
                self._processing_stats["validation_errors"] += 1
                logger.warning(f"Invalid tick: {validation_result['violations']}")

            # Record for completeness monitoring
            await self.completeness_monitor.record_tick(
                tick_data["symbol"], tick_data.get("timestamp", datetime.now())
            )

            # Check cache first
            cache_key = f"{tick_data['symbol']}:latest_tick"
            cached = await self.cache.get(cache_key)

            if cached is None:
                # Store in database
                with self.pipeline_metrics.measure("tick_insert"):
                    await self._insert_tick(tick_data)

                # Update cache
                await self.cache.set(cache_key, tick_data, ttl=60)
                self._processing_stats["cache_operations"] += 1

            self._processing_stats["ticks_processed"] += 1

            return {
                "tick": tick_data,
                "validation": validation_result,
                "cached": cached is not None,
                "quality_score": validation_result["quality_score"],
            }

    async def process_tick_batch(self, ticks: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Process batch of ticks with optimization.

        Args:
            ticks: List of tick data

        Returns:
            Processing summary
        """
        with self.performance_monitor.measure("batch_processing"):
            # Validate batch
            validation_results = await self.validator.validate_batch(ticks, "tick")

            # Filter valid ticks
            valid_ticks = [
                tick
                for tick, result in zip(ticks, validation_results["results"])
                if result["is_valid"]
            ]

            if valid_ticks:
                # Bulk insert to database
                with self.pipeline_metrics.measure("batch_insert"):
                    await self._bulk_insert_ticks(valid_ticks)

                # Update completeness tracking
                if ticks:
                    first_tick = ticks[0]
                    last_tick = ticks[-1]
                    await self.completeness_monitor.record_batch(
                        first_tick["symbol"],
                        first_tick.get("timestamp", datetime.now()),
                        last_tick.get("timestamp", datetime.now()),
                        len(valid_ticks),
                    )

            return {
                "total_ticks": len(ticks),
                "valid_ticks": len(valid_ticks),
                "validation_rate": validation_results["validation_rate"],
                "avg_quality": validation_results["avg_quality_score"],
                "processing_time": (
                    self.performance_monitor._metrics["batch_processing"]["times"][-1]
                    if self.performance_monitor._metrics["batch_processing"]["times"]
                    else 0
                ),
            }

    async def get_market_data(
        self,
        symbol: str,
        timeframe: str,
        start_date: datetime,
        end_date: datetime,
        use_cache: bool = True,
    ) -> pd.DataFrame:
        """
        Get market data with caching and optimization.

        Args:
            symbol: Trading symbol
            timeframe: Data timeframe
            start_date: Start date
            end_date: End date
            use_cache: Whether to use cache

        Returns:
            DataFrame with market data
        """
        cache_key = f"{symbol}:{timeframe}:{start_date.date()}:{end_date.date()}"

        # Check cache
        if use_cache:
            cached_data = await self.cache.get(cache_key)
            if cached_data is not None:
                self._processing_stats["cache_operations"] += 1
                return cached_data

        # Get from database with optimization
        with self.pipeline_metrics.measure("data_retrieval"):
            df = await self.query_optimizer.get_aggregated_candles(
                symbol, timeframe, start_date, end_date
            )

        # Cache the result
        if use_cache and not df.empty:
            await self.cache.set(cache_key, df, ttl=300)
            self._processing_stats["cache_operations"] += 1

        return df

    async def warm_cache(
        self, symbols: List[str], timeframes: List[str], lookback_hours: int = 24
    ):
        """
        Warm cache with frequently accessed data.

        Args:
            symbols: Symbols to warm
            timeframes: Timeframes to warm
            lookback_hours: Hours of historical data
        """
        logger.info(f"Warming cache for {len(symbols)} symbols")

        end_date = datetime.now()
        start_date = end_date - timedelta(hours=lookback_hours)

        warming_tasks = []
        for symbol in symbols:
            for timeframe in timeframes:
                task = self.get_market_data(
                    symbol, timeframe, start_date, end_date, use_cache=True
                )
                warming_tasks.append(task)

        await asyncio.gather(*warming_tasks)

        # Warm ML features
        patterns = [
            {"symbol": symbol, "timeframes": timeframes, "lookback": 100}
            for symbol in symbols
        ]
        await self.cache.warm_ml_features(patterns)

        logger.info("Cache warming complete")

    async def _insert_tick(self, tick_data: Dict[str, Any]):
        """Insert single tick to database."""
        query = """
            INSERT INTO tick_data (symbol, timestamp, bid, ask, volume)
            VALUES ($1, $2, $3, $4, $5)
            ON CONFLICT (symbol, timestamp) DO NOTHING
        """
        await self.pool.execute(
            query,
            tick_data["symbol"],
            tick_data.get("timestamp", datetime.now()),
            tick_data["bid"],
            tick_data["ask"],
            tick_data.get("volume", 0),
        )

    async def _bulk_insert_ticks(self, ticks: List[Dict[str, Any]]):
        """Bulk insert ticks to database."""
        records = [
            (
                tick["symbol"],
                tick.get("timestamp", datetime.now()),
                tick["bid"],
                tick["ask"],
                tick.get("volume", 0),
            )
            for tick in ticks
        ]

        await self.pool.copy_records_to_table(
            "tick_data",
            records=records,
            columns=["symbol", "timestamp", "bid", "ask", "volume"],
        )

    async def get_pipeline_metrics(self) -> Dict[str, Any]:
        """
        Get comprehensive pipeline metrics.

        Returns:
            Pipeline performance and health metrics
        """
        # Get metrics from all components
        pool_stats = self.pool.get_pool_stats()
        cache_stats = self.cache.get_stats()
        performance_report = self.performance_monitor.get_report()
        resource_metrics = await self.resource_monitor.get_metrics()
        quality_metrics = self.validator.get_quality_metrics()
        completeness_report = self.completeness_monitor.get_completeness_report()

        return {
            "pipeline_stats": self._processing_stats,
            "connection_pool": pool_stats,
            "cache": cache_stats,
            "performance": performance_report,
            "resources": resource_metrics,
            "data_quality": quality_metrics,
            "completeness": completeness_report,
            "health": await self._check_health(),
        }

    async def _check_health(self) -> Dict[str, Any]:
        """Check overall pipeline health."""
        pool_healthy = await self.pool.health_check()
        completeness_health = await self.completeness_monitor.check_health()

        all_healthy = (
            pool_healthy
            and completeness_health["status"] == "healthy"
            and self._initialized
        )

        return {
            "status": "healthy" if all_healthy else "degraded",
            "pool_healthy": pool_healthy,
            "completeness_healthy": completeness_health["status"] == "healthy",
            "pipeline_initialized": self._initialized,
            "timestamp": datetime.now(),
        }

    async def optimize_for_production(self):
        """Apply production optimizations."""
        logger.info("Applying production optimizations...")

        # Adjust pool size based on load
        await self.pool.adjust_pool_size_based_on_load()

        # Create materialized views for common queries
        await self.query_optimizer.create_materialized_view(
            "mv_hourly_candles",
            """
            SELECT
                time_bucket('1 hour', time) AS time,
                symbol,
                FIRST(open, time) AS open,
                MAX(high) AS high,
                MIN(low) AS low,
                LAST(close, time) AS close,
                SUM(volume) AS volume
            FROM market_data_1m
            WHERE time > NOW() - INTERVAL '7 days'
            GROUP BY time_bucket('1 hour', time), symbol
            """,
            refresh_interval=3600,  # Refresh hourly
        )

        # Analyze tables for query optimization
        await self.query_optimizer.analyze_table_statistics("market_data_1m")
        await self.query_optimizer.analyze_table_statistics("tick_data")

        logger.info("Production optimizations applied")
