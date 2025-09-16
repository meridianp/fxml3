#!/usr/bin/env python3
"""
Example of using async database connection pooling in FXML4.

This script demonstrates:
1. Setting up async connection pool
2. Performing various database operations
3. Monitoring pool health
4. Handling concurrent operations
"""

import asyncio
import logging
import random
from datetime import datetime, timedelta

from fxml4.data_engineering.async_pool import close_pool, get_pool
from fxml4.data_engineering.async_timescaledb import AsyncTimescaleDBClient
from fxml4.data_engineering.pool_config import get_preset_config
from fxml4.data_engineering.pool_monitor import PoolMonitor

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


async def example_basic_operations():
    """Example of basic async database operations."""
    logger.info("=== Basic Operations Example ===")

    # Use async client with context manager
    async with AsyncTimescaleDBClient() as client:
        # Store a single tick
        success = await client.store_tick(
            symbol="EURUSD",
            timestamp=datetime.now(),
            price=1.0850 + random.random() * 0.001,
            size=1000000,
        )
        logger.info(f"Stored tick: {success}")

        # Store multiple ticks
        ticks = []
        base_time = datetime.now() - timedelta(minutes=10)
        for i in range(10):
            ticks.append(
                {
                    "symbol": "EURUSD",
                    "timestamp": base_time + timedelta(seconds=i),
                    "price": 1.0850 + random.random() * 0.001,
                    "size": random.randint(100000, 1000000),
                    "tick_type": "trade",
                    "source": "example",
                }
            )

        count = await client.store_ticks(ticks)
        logger.info(f"Stored {count} ticks")

        # Get latest tick
        latest = await client.get_latest_tick("EURUSD")
        logger.info(f"Latest tick: {latest}")

        # Get tick count
        tick_count = await client.get_tick_count("EURUSD")
        logger.info(f"Total ticks for EURUSD: {tick_count}")


async def example_concurrent_operations():
    """Example of concurrent database operations."""
    logger.info("=== Concurrent Operations Example ===")

    async with AsyncTimescaleDBClient() as client:
        # Define symbols to query
        symbols = ["EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCAD"]

        # Create tasks for concurrent execution
        tasks = []
        for symbol in symbols:
            # Simulate different operations
            tasks.append(client.get_latest_tick(symbol))
            tasks.append(client.get_tick_count(symbol))
            tasks.append(client.get_latest_candle(symbol, "1m"))

        # Execute all tasks concurrently
        start_time = asyncio.get_event_loop().time()
        results = await asyncio.gather(*tasks, return_exceptions=True)
        end_time = asyncio.get_event_loop().time()

        logger.info(
            f"Executed {len(tasks)} queries in {end_time - start_time:.2f} seconds"
        )

        # Process results
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"Task {i} failed: {result}")
            else:
                logger.debug(f"Task {i} result: {result}")


async def example_transaction():
    """Example of using transactions."""
    logger.info("=== Transaction Example ===")

    async with AsyncTimescaleDBClient() as client:
        try:
            # Start transaction
            async with client.transaction():
                # Insert test data
                await client.execute_query(
                    """
                    INSERT INTO tick_data (time, symbol, price, size, tick_type, source)
                    VALUES ($1, $2, $3, $4, $5, $6)
                    """,
                    datetime.now(),
                    "TESTEUR",
                    1.0900,
                    1000000,
                    "trade",
                    "test",
                )

                # Verify insertion
                count = await client.fetchval_query(
                    "SELECT COUNT(*) FROM tick_data WHERE symbol = $1", "TESTEUR"
                )
                logger.info(f"Inserted records in transaction: {count}")

                # Simulate error (uncomment to test rollback)
                # raise Exception("Simulated error")

            logger.info("Transaction committed successfully")

        except Exception as e:
            logger.error(f"Transaction rolled back: {e}")


async def example_pool_monitoring():
    """Example of monitoring connection pool health."""
    logger.info("=== Pool Monitoring Example ===")

    # Get the pool
    pool = await get_pool()

    # Create monitor
    monitor = PoolMonitor(pool, metrics_interval=5.0)

    # Define alert handler
    def alert_handler(alert_type: str, details: dict):
        logger.warning(f"POOL ALERT - {alert_type}: {details}")

    monitor.alert_callback = alert_handler

    # Start monitoring
    await monitor.start()

    try:
        # Simulate some load
        async with AsyncTimescaleDBClient() as client:
            tasks = []
            for i in range(50):
                tasks.append(client.get_tick_count("EURUSD"))

            await asyncio.gather(*tasks, return_exceptions=True)

        # Get health status
        health = monitor.get_health_status()
        logger.info(f"Pool health: {health['status']}")
        logger.info(f"Pool metrics: {health['metrics']}")

        # Export metrics
        metrics_json = monitor.export_metrics("json")
        logger.info(f"Exported metrics: {metrics_json}")

    finally:
        # Stop monitoring
        await monitor.stop()


async def example_batch_operations():
    """Example of efficient batch operations."""
    logger.info("=== Batch Operations Example ===")

    async with AsyncTimescaleDBClient() as client:
        # Generate large dataset
        candles = []
        base_time = datetime.now() - timedelta(hours=24)

        for i in range(1440):  # 24 hours of 1-minute candles
            timestamp = base_time + timedelta(minutes=i)
            base_price = 1.0850 + (i % 100) * 0.00001

            candles.append(
                {
                    "symbol": "EURUSD",
                    "timestamp": timestamp,
                    "open": base_price,
                    "high": base_price + random.random() * 0.0005,
                    "low": base_price - random.random() * 0.0005,
                    "close": base_price + (random.random() - 0.5) * 0.0003,
                    "volume": random.randint(1000000, 5000000),
                    "tick_count": random.randint(10, 100),
                    "source": "batch_example",
                }
            )

        # Store in batches
        batch_size = 100
        total_stored = 0

        start_time = asyncio.get_event_loop().time()

        for i in range(0, len(candles), batch_size):
            batch = candles[i : i + batch_size]
            stored = await client.store_candles(batch)
            total_stored += stored

        end_time = asyncio.get_event_loop().time()

        logger.info(
            f"Stored {total_stored} candles in {end_time - start_time:.2f} seconds "
            f"({total_stored / (end_time - start_time):.0f} candles/second)"
        )


async def example_custom_queries():
    """Example of executing custom queries."""
    logger.info("=== Custom Queries Example ===")

    async with AsyncTimescaleDBClient() as client:
        # Fetch aggregated data
        query = """
        SELECT
            symbol,
            COUNT(*) as tick_count,
            MIN(price) as min_price,
            MAX(price) as max_price,
            AVG(price) as avg_price
        FROM tick_data
        WHERE time > NOW() - INTERVAL '1 hour'
        GROUP BY symbol
        ORDER BY tick_count DESC
        LIMIT 5
        """

        results = await client.fetch_query(query)

        logger.info("Hourly statistics by symbol:")
        for row in results:
            logger.info(
                f"  {row['symbol']}: {row['tick_count']} ticks, "
                f"price range [{row['min_price']:.5f} - {row['max_price']:.5f}], "
                f"avg: {row['avg_price']:.5f}"
            )


async def main():
    """Run all examples."""
    try:
        # Configure pool for examples
        config = get_preset_config("development")
        pool = await get_pool(config.to_dict())

        # Run examples
        await example_basic_operations()
        await asyncio.sleep(1)

        await example_concurrent_operations()
        await asyncio.sleep(1)

        await example_transaction()
        await asyncio.sleep(1)

        await example_batch_operations()
        await asyncio.sleep(1)

        await example_custom_queries()
        await asyncio.sleep(1)

        await example_pool_monitoring()

        # Show final pool stats
        stats = pool.get_stats()
        logger.info("=== Final Pool Statistics ===")
        for key, value in stats.items():
            logger.info(f"  {key}: {value}")

    finally:
        # Clean up
        await close_pool()
        logger.info("Pool closed successfully")


if __name__ == "__main__":
    # Run the examples
    asyncio.run(main())
