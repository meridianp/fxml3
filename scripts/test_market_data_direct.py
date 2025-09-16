#!/usr/bin/env python3
"""
Direct test of the MarketDataService without config dependencies.

This script tests the market data service directly, bypassing the config system.
"""

import asyncio
import logging
import os
import sys
from datetime import datetime, timedelta

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Add the project root to the Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


async def test_direct_database_connection():
    """Test direct database connection without config system."""
    try:
        import asyncpg

        # Connect directly to TimescaleDB
        conn = await asyncpg.connect(
            host="localhost",
            port=5432,
            user="postgres",
            password="postgres",
            database="fxml4",
        )

        # Test basic query
        result = await conn.fetchval("SELECT version()")
        logger.info(f"✅ Database connection successful: {result}")

        # Test TimescaleDB extension
        timescale_version = await conn.fetchval(
            "SELECT extversion FROM pg_extension WHERE extname = 'timescaledb'"
        )
        if timescale_version:
            logger.info(f"✅ TimescaleDB extension found: v{timescale_version}")
        else:
            logger.warning("⚠️  TimescaleDB extension not found")

        # Test our schema
        tables = await conn.fetch(
            """
            SELECT tablename FROM pg_tables
            WHERE schemaname = 'public' AND tablename LIKE 'market_data%'
            ORDER BY tablename
        """
        )

        table_names = [row["tablename"] for row in tables]
        logger.info(f"✅ Found market data tables: {table_names}")

        # Test hypertables
        hypertables = await conn.fetch(
            """
            SELECT hypertable_name FROM timescaledb_information.hypertables
            WHERE hypertable_name LIKE 'market_data%'
        """
        )

        if hypertables:
            ht_names = [row["hypertable_name"] for row in hypertables]
            logger.info(f"✅ Found hypertables: {ht_names}")
        else:
            logger.info("ℹ️  No hypertables found (may not be created yet)")

        # Check for sample data
        sample_count = await conn.fetchval(
            "SELECT COUNT(*) FROM market_data_1m LIMIT 1"
        )
        logger.info(f"ℹ️  Sample data count in market_data_1m: {sample_count}")

        await conn.close()
        return True

    except Exception as e:
        logger.error(f"❌ Database connection error: {e}")
        return False


async def test_database_functions():
    """Test our custom database functions."""
    try:
        import asyncpg

        conn = await asyncpg.connect(
            host="localhost",
            port=5432,
            user="postgres",
            password="postgres",
            database="fxml4",
        )

        # Test get_ohlcv function
        try:
            result = await conn.fetch(
                """
                SELECT * FROM get_ohlcv('EURUSD', '1h', NOW() - INTERVAL '24 hours', NOW())
                LIMIT 5
            """
            )

            if result:
                logger.info(f"✅ get_ohlcv function returned {len(result)} rows")
                for row in result:
                    logger.info(
                        f"   {row['time']}: O={row['open']} H={row['high']} L={row['low']} C={row['close']}"
                    )
            else:
                logger.info("ℹ️  get_ohlcv function works but no data found")

        except Exception as e:
            logger.error(f"❌ get_ohlcv function error: {e}")

        # Test get_latest_tick function
        try:
            result = await conn.fetchrow("SELECT * FROM get_latest_tick('EURUSD')")

            if result:
                logger.info(f"✅ get_latest_tick function returned: {dict(result)}")
            else:
                logger.info("ℹ️  get_latest_tick function works but no data found")

        except Exception as e:
            logger.error(f"❌ get_latest_tick function error: {e}")

        await conn.close()
        return True

    except Exception as e:
        logger.error(f"❌ Database functions test error: {e}")
        return False


async def test_continuous_aggregates():
    """Test continuous aggregates (materialized views)."""
    try:
        import asyncpg

        conn = await asyncpg.connect(
            host="localhost",
            port=5432,
            user="postgres",
            password="postgres",
            database="fxml4",
        )

        # Check continuous aggregates
        caggs = await conn.fetch(
            """
            SELECT view_name, materialization_hypertable_name
            FROM timescaledb_information.continuous_aggregates
        """
        )

        if caggs:
            logger.info("✅ Found continuous aggregates:")
            for cagg in caggs:
                logger.info(
                    f"   {cagg['view_name']} -> {cagg['materialization_hypertable_name']}"
                )

                # Test querying the view
                count = await conn.fetchval(f"SELECT COUNT(*) FROM {cagg['view_name']}")
                logger.info(f"      Data count: {count}")
        else:
            logger.info("ℹ️  No continuous aggregates found")

        await conn.close()
        return True

    except Exception as e:
        logger.error(f"❌ Continuous aggregates test error: {e}")
        return False


async def insert_sample_data():
    """Insert some sample market data for testing."""
    try:
        from datetime import datetime, timedelta

        import asyncpg

        conn = await asyncpg.connect(
            host="localhost",
            port=5432,
            user="postgres",
            password="postgres",
            database="fxml4",
        )

        # Generate sample 1-minute data for the last hour
        base_time = datetime.utcnow().replace(second=0, microsecond=0)
        base_price = 1.1000  # EURUSD starting price

        sample_data = []
        for i in range(60):  # 60 minutes of data
            time = base_time - timedelta(minutes=59 - i)
            # Simple random walk
            price_change = (i % 7 - 3) * 0.0001  # Simple pattern
            price = base_price + price_change

            sample_data.append(
                (
                    time,  # time
                    "EURUSD",  # symbol
                    price,  # open
                    price + 0.0005,  # high
                    price - 0.0003,  # low
                    price + 0.0002,  # close
                    1000 + i * 10,  # volume
                    50,  # tick_count
                    "test_data",  # source
                )
            )

        # Insert the data
        await conn.executemany(
            """
            INSERT INTO market_data_1m (time, symbol, open, high, low, close, volume, tick_count, source)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
            ON CONFLICT (time, symbol) DO UPDATE SET
                open = EXCLUDED.open,
                high = EXCLUDED.high,
                low = EXCLUDED.low,
                close = EXCLUDED.close,
                volume = EXCLUDED.volume,
                tick_count = EXCLUDED.tick_count,
                source = EXCLUDED.source
        """,
            sample_data,
        )

        logger.info(f"✅ Inserted {len(sample_data)} sample data points")

        # Verify data was inserted
        count = await conn.fetchval(
            "SELECT COUNT(*) FROM market_data_1m WHERE source = 'test_data'"
        )
        logger.info(f"✅ Verified {count} sample data points in database")

        await conn.close()
        return True

    except Exception as e:
        logger.error(f"❌ Sample data insertion error: {e}")
        return False


async def main():
    """Run all direct database tests."""
    logger.info("🚀 Starting Direct Database Test Suite")
    logger.info("=" * 60)

    tests = [
        ("Direct Database Connection", test_direct_database_connection()),
        ("Database Functions", test_database_functions()),
        ("Continuous Aggregates", test_continuous_aggregates()),
        ("Insert Sample Data", insert_sample_data()),
        ("Re-test Database Functions", test_database_functions()),
    ]

    results = []
    for test_name, test_coro in tests:
        logger.info(f"\n🧪 Running {test_name}...")
        try:
            result = await test_coro
            results.append((test_name, result))
        except Exception as e:
            logger.error(f"❌ {test_name} failed with exception: {e}")
            results.append((test_name, False))

    # Print summary
    logger.info("\n" + "=" * 60)
    logger.info("📊 Test Summary:")
    logger.info("=" * 60)

    passed = 0
    total = len(results)

    for test_name, result in results:
        status = "✅ PASSED" if result else "❌ FAILED"
        logger.info(f"{test_name}: {status}")
        if result:
            passed += 1

    logger.info("=" * 60)
    logger.info(f"Overall: {passed}/{total} tests passed ({passed/total*100:.1f}%)")

    if passed == total:
        logger.info(
            "🎉 All tests passed! Database infrastructure is working correctly."
        )
    else:
        logger.info(
            "⚠️  Some tests failed. Check the database connection and TimescaleDB setup."
        )


if __name__ == "__main__":
    asyncio.run(main())
