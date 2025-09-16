#!/usr/bin/env python3
"""Test a single data endpoint call to debug caching."""

import json
import sys
import time
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

import asyncio

import aiohttp

from fxml4.api.auth.uat_auth import create_uat_token


async def test_data_endpoint():
    """Test single data endpoint call with timing."""
    print("🧪 Testing Data Endpoint Performance")
    print("=" * 40)

    # Generate auth token
    auth_token = create_uat_token("data_tester", scopes=["read", "write", "admin"])

    headers = {
        "Authorization": f"Bearer {auth_token}",
        "Content-Type": "application/json",
    }

    # Data request payload
    payload = {"symbol": "GBPUSD", "timeframe": "1h", "limit": 10}

    url = "http://localhost:8001/data"

    async with aiohttp.ClientSession(
        headers=headers, timeout=aiohttp.ClientTimeout(total=30)
    ) as session:

        print("1. First call (cache miss expected)...")
        start_time = time.perf_counter()

        async with session.post(url, json=payload) as response:
            result = await response.json()
            end_time = time.perf_counter()

            response_time = end_time - start_time
            print(f"   Status: {response.status}")
            print(f"   Response time: {response_time:.3f}s")

            if response.status == 200:
                print(f"   Data points: {result.get('count', 0)}")
                print(f"   Source: {result.get('source', 'unknown')}")
            else:
                print(f"   Error: {result}")

        print("\n2. Second call (cache hit expected)...")
        start_time = time.perf_counter()

        async with session.post(url, json=payload) as response:
            result = await response.json()
            end_time = time.perf_counter()

            response_time = end_time - start_time
            print(f"   Status: {response.status}")
            print(f"   Response time: {response_time:.3f}s")

            if response.status == 200:
                print(f"   Data points: {result.get('count', 0)}")
                print(f"   Source: {result.get('source', 'unknown')}")
            else:
                print(f"   Error: {result}")

        print("\n3. Third call (should still be cache hit)...")
        start_time = time.perf_counter()

        async with session.post(url, json=payload) as response:
            result = await response.json()
            end_time = time.perf_counter()

            response_time = end_time - start_time
            print(f"   Status: {response.status}")
            print(f"   Response time: {response_time:.3f}s")

            if response.status == 200:
                print(f"   Data points: {result.get('count', 0)}")
                print(f"   Source: {result.get('source', 'unknown')}")
            else:
                print(f"   Error: {result}")


if __name__ == "__main__":
    try:
        asyncio.run(test_data_endpoint())
    except Exception as e:
        print(f"💥 Test failed: {e}")
        import traceback

        traceback.print_exc()
