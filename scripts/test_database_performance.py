#!/usr/bin/env python3
"""
Database performance testing for TimescaleDB query optimization.
Performance targets: <100ms market data, <500ms features, <30s backtest queries
"""

import asyncio
import statistics
import time
from datetime import datetime, timedelta
from typing import Any, Dict, List

import asyncpg


async def test_database_performance():
    """Test TimescaleDB query performance and validate SLA targets."""

    print("🔧 Testing TimescaleDB Query Performance")
    print("=" * 60)

    # Connection parameters
    conn_params = {
        "host": "localhost",
        "port": 5432,
        "user": "postgres",
        "password": "postgres",
        "database": "fxml4",
    }

    # Performance targets
    targets = {
        "market_data": 0.100,  # 100ms
        "features": 0.500,  # 500ms
        "backtest": 30.0,  # 30s
    }

    results = {}

    try:
        # Create connection pool
        pool = await asyncpg.create_pool(**conn_params, min_size=2, max_size=10)

        # Test 1: Market Data Query Performance
        print("\n📊 Testing Market Data Query Performance...")
        market_data_times = []

        for i in range(10):
            start_time = time.perf_counter()
            async with pool.acquire() as conn:
                # Test get_ohlcv function performance
                rows = await conn.fetch(
                    """
                    SELECT * FROM get_ohlcv('GBPUSD', '1h', $1, $2, 100)
                """,
                    datetime.utcnow() - timedelta(days=7),
                    datetime.utcnow(),
                )

            end_time = time.perf_counter()
            query_time = end_time - start_time
            market_data_times.append(query_time)
            print(f"   Query {i+1}: {query_time:.3f}s ({len(rows)} rows)")

        market_data_p95 = sorted(market_data_times)[int(len(market_data_times) * 0.95)]
        market_data_avg = statistics.mean(market_data_times)

        results["market_data"] = {
            "avg_time": market_data_avg,
            "p95_time": market_data_p95,
            "target": targets["market_data"],
            "pass": market_data_p95 <= targets["market_data"],
        }

        status = "✅ PASS" if results["market_data"]["pass"] else "❌ FAIL"
        print(
            f"   {status} - P95: {market_data_p95:.3f}s, Avg: {market_data_avg:.3f}s (Target: {targets['market_data']:.3f}s)"
        )

        # Test 2: Feature Query Performance
        print("\n📊 Testing Feature Query Performance...")
        feature_times = []

        for i in range(5):
            start_time = time.perf_counter()
            async with pool.acquire() as conn:
                # Test complex feature calculation query
                rows = await conn.fetch(
                    """
                    SELECT
                        symbol,
                        timestamp,
                        COUNT(*) as feature_count,
                        AVG(close) as avg_close,
                        STDDEV(close) as stddev_close,
                        MAX(high) - MIN(low) as range_hl
                    FROM market_data_candles
                    WHERE symbol = 'GBPUSD'
                        AND timestamp >= $1
                        AND timestamp <= $2
                    GROUP BY symbol, timestamp
                    ORDER BY timestamp DESC
                    LIMIT 200
                """,
                    datetime.utcnow() - timedelta(days=30),
                    datetime.utcnow(),
                )

            end_time = time.perf_counter()
            query_time = end_time - start_time
            feature_times.append(query_time)
            print(f"   Feature query {i+1}: {query_time:.3f}s ({len(rows)} rows)")

        feature_p95 = (
            sorted(feature_times)[int(len(feature_times) * 0.95)]
            if feature_times
            else 0
        )
        feature_avg = statistics.mean(feature_times) if feature_times else 0

        results["features"] = {
            "avg_time": feature_avg,
            "p95_time": feature_p95,
            "target": targets["features"],
            "pass": feature_p95 <= targets["features"],
        }

        status = "✅ PASS" if results["features"]["pass"] else "❌ FAIL"
        print(
            f"   {status} - P95: {feature_p95:.3f}s, Avg: {feature_avg:.3f}s (Target: {targets['features']:.3f}s)"
        )

        # Test 3: Backtest Query Performance
        print("\n📊 Testing Backtest Query Performance...")
        backtest_times = []

        for i in range(3):
            start_time = time.perf_counter()
            async with pool.acquire() as conn:
                # Test large data set query for backtesting
                rows = await conn.fetch(
                    """
                    SELECT
                        timestamp,
                        symbol,
                        open,
                        high,
                        low,
                        close,
                        volume
                    FROM market_data_candles
                    WHERE symbol = 'GBPUSD'
                        AND timestamp >= $1
                        AND timestamp <= $2
                    ORDER BY timestamp ASC
                """,
                    datetime.utcnow() - timedelta(days=60),
                    datetime.utcnow(),
                )

            end_time = time.perf_counter()
            query_time = end_time - start_time
            backtest_times.append(query_time)
            print(f"   Backtest query {i+1}: {query_time:.3f}s ({len(rows)} rows)")

        backtest_p95 = (
            sorted(backtest_times)[int(len(backtest_times) * 0.95)]
            if backtest_times
            else 0
        )
        backtest_avg = statistics.mean(backtest_times) if backtest_times else 0

        results["backtest"] = {
            "avg_time": backtest_avg,
            "p95_time": backtest_p95,
            "target": targets["backtest"],
            "pass": backtest_p95 <= targets["backtest"],
        }

        status = "✅ PASS" if results["backtest"]["pass"] else "❌ FAIL"
        print(
            f"   {status} - P95: {backtest_p95:.3f}s, Avg: {backtest_avg:.3f}s (Target: {targets['backtest']:.3f}s)"
        )

        # Test 4: Connection Pool Performance
        print("\n📊 Testing Connection Pool Performance...")
        pool_times = []

        for i in range(20):
            start_time = time.perf_counter()
            async with pool.acquire() as conn:
                await conn.fetchrow("SELECT version()")
            end_time = time.perf_counter()
            pool_times.append(end_time - start_time)

        pool_avg = statistics.mean(pool_times)
        print(f"   Connection acquisition avg: {pool_avg:.4f}s")
        print(f"   Pool stats: size={pool.get_size()}, idle={pool.get_idle_size()}")

        await pool.close()

    except Exception as e:
        print(f"❌ Database connection error: {e}")
        return False

    # Summary
    print("\n" + "=" * 60)
    print("📊 TIMESCALEDB PERFORMANCE SUMMARY")
    print("=" * 60)
    print(f"{'Query Type':<15} {'P95 Time':<10} {'Target':<10} {'Status':<8}")
    print("-" * 50)

    overall_pass = True
    for query_type, result in results.items():
        status = "✅ PASS" if result["pass"] else "❌ FAIL"
        print(
            f"{query_type:<15} {result['p95_time']:<10.3f}s {result['target']:<10.3f}s {status:<8}"
        )
        overall_pass = overall_pass and result["pass"]

    overall_status = "✅ PASS" if overall_pass else "❌ FAIL"
    passed_tests = sum(1 for r in results.values() if r["pass"])
    print(f"\nOverall: {overall_status} ({passed_tests}/{len(results)} targets met)")

    return overall_pass


async def main():
    """Run database performance tests."""
    success = await test_database_performance()
    return success


if __name__ == "__main__":
    success = asyncio.run(main())
    exit(0 if success else 1)
