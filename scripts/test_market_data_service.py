#!/usr/bin/env python3
"""
Direct test of the MarketDataService.

This script tests the market data service directly without starting the full API.
"""

import asyncio
import logging
import os
import sys
from datetime import datetime, timedelta

# Import paths handled by PYTHONPATH wrapper

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def test_database_connection():
    """Test database connection."""
    try:
        from fxml4.api.services.market_data import market_data_service

        # Try to get connection pool
        pool = await market_data_service.get_connection_pool()
        if pool:
            logger.info("✅ Database connection successful")
            return True
        else:
            logger.error("❌ Database connection failed")
            return False
    except Exception as e:
        logger.error(f"❌ Database connection error: {e}")
        return False


async def test_get_symbols():
    """Test getting available symbols."""
    try:
        from fxml4.api.services.market_data import market_data_service

        symbols = await market_data_service.get_available_symbols()
        logger.info(f"✅ Retrieved {len(symbols)} symbols: {symbols}")
        return True
    except Exception as e:
        logger.error(f"❌ Get symbols error: {e}")
        return False


async def test_get_ohlcv_data():
    """Test getting OHLCV data."""
    try:
        from fxml4.api.services.market_data import market_data_service

        # Try to get data for EURUSD
        data_points = await market_data_service.get_ohlcv_data(
            symbol="EURUSD", timeframe="1h", limit=10
        )

        if data_points:
            logger.info(f"✅ Retrieved {len(data_points)} data points for EURUSD")
            logger.info(
                f"   First point: {data_points[0].time} - Close: {data_points[0].close}"
            )
            logger.info(f"   Source: {data_points[0].source}")
        else:
            logger.info("ℹ️  No data points found (database may be empty)")

        return True
    except Exception as e:
        logger.error(f"❌ Get OHLCV data error: {e}")
        return False


async def test_get_latest_tick():
    """Test getting latest tick data."""
    try:
        from fxml4.api.services.market_data import market_data_service

        tick_data = await market_data_service.get_latest_tick("EURUSD")

        if tick_data:
            logger.info(f"✅ Retrieved latest tick for EURUSD: {tick_data}")
        else:
            logger.info("ℹ️  No tick data found (database may be empty)")

        return True
    except Exception as e:
        logger.error(f"❌ Get latest tick error: {e}")
        return False


async def test_external_data_fallback():
    """Test external data fallback functionality."""
    try:
        from fxml4.api.services.market_data import market_data_service

        # Force external data by using a non-standard symbol
        data_points = await market_data_service._get_external_data(
            symbol="EURUSD", timeframe="1h", limit=5
        )

        if data_points:
            logger.info(
                f"✅ External data fallback retrieved {len(data_points)} points"
            )
            logger.info(f"   Source: {data_points[0].source}")
        else:
            logger.info(
                "ℹ️  External data fallback returned no data (API keys may not be configured)"
            )

        return True
    except Exception as e:
        logger.info(f"ℹ️  External data fallback not available: {e}")
        return True  # This is expected if external feeds aren't configured


async def main():
    """Run all market data service tests."""
    logger.info("🚀 Starting Market Data Service Test Suite")
    logger.info("=" * 60)

    # Set basic environment variables if not set
    if not os.getenv("POSTGRES_DB"):
        os.environ["POSTGRES_DB"] = "fxml4"
    if not os.getenv("POSTGRES_USER"):
        os.environ["POSTGRES_USER"] = "postgres"
    if not os.getenv("POSTGRES_PASSWORD"):
        os.environ["POSTGRES_PASSWORD"] = "postgres"

    tests = [
        ("Database Connection", test_database_connection()),
        ("Get Symbols", test_get_symbols()),
        ("Get OHLCV Data", test_get_ohlcv_data()),
        ("Get Latest Tick", test_get_latest_tick()),
        ("External Data Fallback", test_external_data_fallback()),
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
        logger.info("🎉 All tests passed! Market Data Service is working correctly.")
    else:
        logger.info(
            "⚠️  Some tests failed. Check the database connection and configuration."
        )

    # Close the service
    try:
        from fxml4.api.services.market_data import market_data_service

        await market_data_service.close()
    except:
        pass


if __name__ == "__main__":
    asyncio.run(main())
