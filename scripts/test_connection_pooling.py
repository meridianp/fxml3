#!/usr/bin/env python3
"""
Connection pooling performance test for FXML4.
Performance target: <20 active DB connections for 100+ concurrent requests
"""

import asyncio
import logging
import statistics
import time
from datetime import datetime, timedelta
from typing import Any, Dict, List

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def test_connection_pooling_performance():
    """Test connection pooling under high concurrent load."""

    print("🔧 Testing Connection Pooling Performance")
    print("=" * 60)
    print("Target: <20 active DB connections for 100+ concurrent requests")
    print()

    # Import after logging setup
    from fxml4.core.database_pool import DatabasePoolManager

    # Initialize pool manager with optimized settings
    pool_manager = DatabasePoolManager(
        min_size=5,
        max_size=15,  # Target: <20 connections
        timeout=10.0,
        command_timeout=5.0,
    )

    try:
        await pool_manager.initialize()

        # Test scenarios with increasing concurrent load
        test_scenarios = [
            {
                "concurrent_requests": 50,
                "total_requests": 200,
                "description": "Moderate Load",
            },
            {
                "concurrent_requests": 100,
                "total_requests": 500,
                "description": "High Load",
            },
            {
                "concurrent_requests": 150,
                "total_requests": 750,
                "description": "Peak Load",
            },
        ]

        results = {}

        for scenario in test_scenarios:
            concurrent = scenario["concurrent_requests"]
            total = scenario["total_requests"]
            desc = scenario["description"]

            print(
                f"\n📊 Testing {desc}: {concurrent} concurrent, {total} total requests"
            )
            print("-" * 50)

            # Run load test
            start_time = time.perf_counter()

            # Create batches of concurrent requests
            batch_size = concurrent
            num_batches = total // batch_size

            batch_results = []
            max_active_connections = 0

            for batch in range(num_batches):
                batch_start = time.perf_counter()

                # Create concurrent tasks for this batch
                tasks = []
                for i in range(batch_size):
                    task = asyncio.create_task(
                        perform_database_operation(
                            pool_manager, f"batch_{batch}_req_{i}"
                        )
                    )
                    tasks.append(task)

                # Wait for all tasks in this batch to complete
                batch_responses = await asyncio.gather(*tasks, return_exceptions=True)

                batch_end = time.perf_counter()
                batch_duration = batch_end - batch_start

                # Check pool statistics during peak load
                stats = pool_manager.get_stats()
                current_active = stats.acquired
                if current_active > max_active_connections:
                    max_active_connections = current_active

                # Count successful operations
                successful = sum(
                    1 for r in batch_responses if not isinstance(r, Exception)
                )
                failed = len(batch_responses) - successful

                batch_results.append(
                    {
                        "batch": batch,
                        "duration": batch_duration,
                        "successful": successful,
                        "failed": failed,
                        "active_connections": current_active,
                        "pool_size": stats.size,
                        "idle_connections": stats.idle,
                    }
                )

                print(
                    f"   Batch {batch+1}/{num_batches}: {successful}/{batch_size} success, "
                    f"{current_active} active conns, {batch_duration:.3f}s"
                )

            end_time = time.perf_counter()
            total_duration = end_time - start_time

            # Calculate final statistics
            final_stats = pool_manager.get_stats()
            total_successful = sum(b["successful"] for b in batch_results)
            total_failed = sum(b["failed"] for b in batch_results)
            avg_response_time = sum(b["duration"] for b in batch_results) / len(
                batch_results
            )

            # Connection pooling validation
            connection_target_met = max_active_connections < 20
            success_rate = (total_successful / total) * 100

            results[desc] = {
                "concurrent_requests": concurrent,
                "total_requests": total,
                "total_successful": total_successful,
                "total_failed": total_failed,
                "success_rate": success_rate,
                "total_duration": total_duration,
                "avg_response_time": avg_response_time,
                "requests_per_second": total / total_duration,
                "max_active_connections": max_active_connections,
                "connection_target_met": connection_target_met,
                "final_pool_size": final_stats.size,
                "peak_usage": final_stats.peak_usage,
                "avg_acquisition_time": final_stats.avg_acquisition_time,
                "connection_timeouts": final_stats.connection_timeouts,
            }

            # Status indicator
            status = (
                "✅ PASS" if connection_target_met and success_rate > 95 else "❌ FAIL"
            )
            print(
                f"\n   {status} - Max Active Connections: {max_active_connections} < 20"
            )
            print(f"   Success Rate: {success_rate:.1f}% ({total_successful}/{total})")
            print(f"   Avg Response Time: {avg_response_time:.3f}s")
            print(f"   Requests/Second: {total/total_duration:.1f}")

        # Advanced connection pool stress test
        print(f"\n🚀 Advanced Stress Test: 200 concurrent requests")
        print("-" * 50)

        stress_start = time.perf_counter()
        stress_tasks = []

        # Create 200 concurrent requests
        for i in range(200):
            task = asyncio.create_task(
                perform_complex_database_operation(pool_manager, f"stress_{i}")
            )
            stress_tasks.append(task)

        # Execute all stress test tasks
        stress_responses = await asyncio.gather(*stress_tasks, return_exceptions=True)
        stress_end = time.perf_counter()
        stress_duration = stress_end - stress_start

        stress_successful = sum(
            1 for r in stress_responses if not isinstance(r, Exception)
        )
        stress_failed = len(stress_responses) - stress_successful
        stress_success_rate = (stress_successful / 200) * 100

        # Final pool statistics
        final_stats = pool_manager.get_stats()

        print(f"   Completed 200 concurrent requests in {stress_duration:.2f}s")
        print(f"   Success: {stress_successful}/200 ({stress_success_rate:.1f}%)")
        print(f"   Peak Active Connections: {final_stats.peak_usage}")
        print(f"   Connection Timeouts: {final_stats.connection_timeouts}")
        print(f"   Avg Acquisition Time: {final_stats.avg_acquisition_time:.4f}s")

        # Overall assessment
        print("\n" + "=" * 60)
        print("📊 CONNECTION POOLING PERFORMANCE SUMMARY")
        print("=" * 60)
        print(
            f"{'Test Scenario':<15} {'Max Conns':<10} {'Target':<10} {'Success%':<10} {'Status':<8}"
        )
        print("-" * 58)

        overall_pass = True
        for desc, result in results.items():
            status = (
                "✅ PASS"
                if result["connection_target_met"] and result["success_rate"] > 95
                else "❌ FAIL"
            )
            print(
                f"{desc:<15} {result['max_active_connections']:<10} {'<20':<10} {result['success_rate']:<10.1f}% {status:<8}"
            )
            overall_pass = (
                overall_pass
                and result["connection_target_met"]
                and result["success_rate"] > 95
            )

        # Stress test result
        stress_pass = final_stats.peak_usage < 20 and stress_success_rate > 95
        stress_status = "✅ PASS" if stress_pass else "❌ FAIL"
        print(
            f"{'Stress Test':<15} {final_stats.peak_usage:<10} {'<20':<10} {stress_success_rate:<10.1f}% {stress_status:<8}"
        )
        overall_pass = overall_pass and stress_pass

        overall_status = "✅ PASS" if overall_pass else "❌ FAIL"
        print(f"\nOverall Connection Pooling: {overall_status}")

        # Performance insights
        print(f"\n💡 PERFORMANCE INSIGHTS")
        print(
            f"Pool Configuration: min={pool_manager.min_size}, max={pool_manager.max_size}"
        )
        print(f"Total Requests Processed: {final_stats.total_requests}")
        print(
            f"Average Connection Acquisition: {final_stats.avg_acquisition_time:.4f}s"
        )
        print(
            f"Connection Pool Efficiency: {((final_stats.total_requests / final_stats.peak_usage) if final_stats.peak_usage > 0 else 0):.1f} req/conn"
        )

        return overall_pass

    except Exception as e:
        logger.error(f"Connection pooling test failed: {e}")
        return False
    finally:
        await pool_manager.close()


async def perform_database_operation(pool_manager, operation_id: str) -> Dict[str, Any]:
    """Perform a standard database operation for load testing."""
    try:
        # Simulate typical API database operations
        start_time = time.perf_counter()

        # Test OHLCV data retrieval (common operation)
        result = await pool_manager.fetchrow(
            """
            SELECT * FROM get_ohlcv('GBPUSD', '1h', NOW() - INTERVAL '1 hour', NOW(), 10)
            LIMIT 1
        """
        )

        # Test a simple aggregation (simulating feature calculation)
        count_result = await pool_manager.fetchrow(
            """
            SELECT COUNT(*) as count, MAX(timestamp) as latest
            FROM market_data_candles
            WHERE symbol = 'GBPUSD'
        """
        )

        end_time = time.perf_counter()
        duration = end_time - start_time

        return {
            "operation_id": operation_id,
            "success": True,
            "duration": duration,
            "data_points": 1 if result else 0,
            "count": count_result["count"] if count_result else 0,
        }

    except Exception as e:
        return {
            "operation_id": operation_id,
            "success": False,
            "error": str(e),
            "duration": 0,
        }


async def perform_complex_database_operation(
    pool_manager, operation_id: str
) -> Dict[str, Any]:
    """Perform a more complex database operation for stress testing."""
    try:
        start_time = time.perf_counter()

        # Complex query combining multiple operations
        result = await pool_manager.execute(
            """
            WITH recent_data AS (
                SELECT timestamp, symbol, close, volume
                FROM market_data_candles
                WHERE symbol = 'GBPUSD'
                    AND timestamp >= NOW() - INTERVAL '24 hours'
                ORDER BY timestamp DESC
                LIMIT 100
            ),
            stats AS (
                SELECT
                    COUNT(*) as count,
                    AVG(close) as avg_close,
                    STDDEV(close) as stddev_close,
                    SUM(volume) as total_volume
                FROM recent_data
            )
            SELECT * FROM stats
        """
        )

        end_time = time.perf_counter()
        duration = end_time - start_time

        return {
            "operation_id": operation_id,
            "success": True,
            "duration": duration,
            "results": len(result) if result else 0,
        }

    except Exception as e:
        return {
            "operation_id": operation_id,
            "success": False,
            "error": str(e),
            "duration": 0,
        }


async def main():
    """Run connection pooling performance tests."""
    success = await test_connection_pooling_performance()
    return success


if __name__ == "__main__":
    success = asyncio.run(main())
    exit(0 if success else 1)
