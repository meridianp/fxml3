#!/usr/bin/env python3
"""Test Redis cache functionality directly."""

import asyncio
import os
import sys
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from fxml4.api.services.redis_cache import redis_cache_service


async def test_redis_cache():
    """Test Redis cache basic functionality."""
    print("🧪 Testing Redis Cache Service")
    print("=" * 40)

    # Test health check
    print("1. Testing health check...")
    healthy = await redis_cache_service.health_check()
    print(f"   Health check: {'✅ PASS' if healthy else '❌ FAIL'}")

    if not healthy:
        print("   Redis health check failed - cache won't work")
        return False

    # Test basic set/get
    print("\n2. Testing basic set/get...")
    test_params = {"test": "value", "number": 123}
    test_data = {"message": "Hello Redis!", "timestamp": "2025-08-26T12:00:00"}

    # Set data
    set_result = await redis_cache_service.set("test", test_params, test_data, ttl=60)
    print(f"   Set result: {'✅ PASS' if set_result else '❌ FAIL'}")

    # Get data
    retrieved_data = await redis_cache_service.get("test", test_params)
    print(f"   Get result: {'✅ PASS' if retrieved_data else '❌ FAIL'}")

    if retrieved_data:
        print(f"   Retrieved data: {retrieved_data}")
        match = retrieved_data == test_data
        print(f"   Data match: {'✅ PASS' if match else '❌ FAIL'}")

    # Test cache stats
    print("\n3. Testing cache stats...")
    stats = await redis_cache_service.get_stats()
    print(f"   Stats: {stats}")

    # Test market data cache specifically
    print("\n4. Testing market data cache params...")
    market_params = {
        "symbol": "GBPUSD",
        "timeframe": "1h",
        "start_time": "2025-08-19T12:00:00",
        "end_time": "2025-08-26T12:00:00",
        "limit": 10,
    }

    market_data = [
        {
            "time": "2025-08-26T10:00:00",
            "symbol": "GBPUSD",
            "open": 1.2700,
            "high": 1.2720,
            "low": 1.2690,
            "close": 1.2710,
            "volume": 1000,
            "tick_count": 100,
            "source": "test",
        }
    ]

    # Cache market data
    market_set_result = await redis_cache_service.set(
        "market_data", market_params, market_data, ttl=30
    )
    print(f"   Market data set: {'✅ PASS' if market_set_result else '❌ FAIL'}")

    # Retrieve market data
    market_get_result = await redis_cache_service.get("market_data", market_params)
    print(f"   Market data get: {'✅ PASS' if market_get_result else '❌ FAIL'}")

    if market_get_result:
        print(f"   Market data length: {len(market_get_result)}")
        print(f"   First entry: {market_get_result[0]}")

    await redis_cache_service.close()

    return healthy and set_result and retrieved_data is not None


if __name__ == "__main__":
    try:
        success = asyncio.run(test_redis_cache())
        print(f"\n🏁 Overall result: {'✅ SUCCESS' if success else '❌ FAILURE'}")
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n💥 Test failed with error: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
