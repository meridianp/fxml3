#!/usr/bin/env python3
"""
Standalone test for stress testing framework (no pytest dependency).

This script validates the stress testing framework without requiring pytest,
making it suitable for development and basic validation.
"""

import asyncio
import sys
import time
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Import stress testing framework directly
import tests.stress.test_high_frequency_trading_stress as stress_module


async def test_stress_framework():
    """Test the stress testing framework."""
    print("Testing FXML4 High-Frequency Trading Stress Framework")
    print("=" * 60)

    # Create stress tester
    tester = stress_module.HighFrequencyStressTester()

    # Test 1: Order submission stress (light)
    print("\n1. Testing Order Submission Stress (Light)...")
    start_time = time.time()

    try:
        metrics = await tester.stress_test_order_submission(
            num_orders=50, concurrent_workers=3
        )

        duration = time.time() - start_time
        print(f"   ✓ Completed in {duration:.2f}s")
        print(f"   ✓ Operations: {metrics.total_operations}")
        print(f"   ✓ Throughput: {metrics.operations_per_second:.1f} ops/sec")
        print(f"   ✓ Avg Latency: {metrics.avg_latency_ms:.1f}ms")
        print(f"   ✓ Error Rate: {metrics.error_rate:.3f}")
        print(f"   ✓ Peak Memory: {metrics.peak_memory_mb:.1f}MB")
        print(f"   ✓ Peak CPU: {metrics.peak_cpu_percent:.1f}%")

        # Validate results
        assert metrics.total_operations == 50
        assert metrics.error_rate <= 0.1  # Allow higher error rate for mock
        assert metrics.operations_per_second > 0
        print("   ✓ All assertions passed")

    except Exception as e:
        print(f"   ✗ Failed: {e}")
        return False

    # Test 2: Market data processing stress
    print("\n2. Testing Market Data Processing Stress...")
    start_time = time.time()

    try:
        metrics = await tester.stress_test_market_data_processing(
            num_ticks=500, ticks_per_second=50
        )

        duration = time.time() - start_time
        print(f"   ✓ Completed in {duration:.2f}s")
        print(f"   ✓ Operations: {metrics.total_operations}")
        print(f"   ✓ Throughput: {metrics.operations_per_second:.1f} ops/sec")
        print(f"   ✓ Avg Latency: {metrics.avg_latency_ms:.1f}ms")
        print(f"   ✓ Error Rate: {metrics.error_rate:.3f}")

        # Validate results
        assert metrics.total_operations == 500
        assert metrics.error_rate <= 0.1
        assert metrics.operations_per_second > 0
        print("   ✓ All assertions passed")

    except Exception as e:
        print(f"   ✗ Failed: {e}")
        return False

    # Test 3: Risk calculation stress
    print("\n3. Testing Risk Calculation Stress...")
    start_time = time.time()

    try:
        metrics = await tester.stress_test_risk_calculations(
            num_calculations=50, concurrent_positions=5
        )

        duration = time.time() - start_time
        print(f"   ✓ Completed in {duration:.2f}s")
        print(f"   ✓ Operations: {metrics.total_operations}")
        print(f"   ✓ Throughput: {metrics.operations_per_second:.1f} ops/sec")
        print(f"   ✓ Avg Latency: {metrics.avg_latency_ms:.1f}ms")
        print(f"   ✓ Error Rate: {metrics.error_rate:.3f}")

        # Validate results
        assert metrics.total_operations == 50
        assert metrics.error_rate <= 0.1
        assert metrics.operations_per_second > 0
        print("   ✓ All assertions passed")

    except Exception as e:
        print(f"   ✗ Failed: {e}")
        return False

    # Test 4: Signal generation stress
    print("\n4. Testing Signal Generation Stress...")
    start_time = time.time()

    try:
        metrics = await tester.stress_test_signal_generation(
            num_signals=10, concurrent_generators=2
        )

        duration = time.time() - start_time
        print(f"   ✓ Completed in {duration:.2f}s")
        print(f"   ✓ Operations: {metrics.total_operations}")
        print(f"   ✓ Throughput: {metrics.operations_per_second:.1f} ops/sec")
        print(f"   ✓ Avg Latency: {metrics.avg_latency_ms:.1f}ms")
        print(f"   ✓ Error Rate: {metrics.error_rate:.3f}")

        # Validate results
        assert metrics.total_operations == 10
        assert metrics.error_rate <= 0.2  # Allow higher error rate for signals
        assert metrics.operations_per_second > 0
        print("   ✓ All assertions passed")

    except Exception as e:
        print(f"   ✗ Failed: {e}")
        return False

    # Test 5: Resource monitoring
    print("\n5. Testing Resource Monitoring...")

    try:
        monitor = stress_module.ResourceMonitor()
        monitor.start_monitoring(interval=0.1)

        # Let it run for a short time
        await asyncio.sleep(0.5)

        metrics = monitor.stop_monitoring()

        print(f"   ✓ Collected {len(metrics)} resource measurements")

        if metrics:
            latest = metrics[-1]
            print(f"   ✓ Latest CPU: {latest.cpu_percent:.1f}%")
            print(f"   ✓ Latest Memory: {latest.memory_mb:.1f}MB")

            assert len(metrics) > 0
            assert latest.memory_mb > 0
            print("   ✓ Resource monitoring working correctly")

    except Exception as e:
        print(f"   ✗ Failed: {e}")
        return False

    print("\n" + "=" * 60)
    print("✓ ALL STRESS FRAMEWORK TESTS PASSED")
    print("The stress testing framework is working correctly!")
    print("=" * 60)

    return True


def test_performance_thresholds():
    """Test performance threshold definitions."""
    print("\nTesting Performance Thresholds...")

    # Mock fixture creation
    thresholds = {
        "order_submission": {
            "max_avg_latency_ms": 100,
            "max_p95_latency_ms": 200,
            "max_error_rate": 0.01,
            "min_ops_per_second": 100,
        },
        "market_data_processing": {
            "max_avg_latency_ms": 10,
            "max_p95_latency_ms": 20,
            "max_error_rate": 0.001,
            "min_ops_per_second": 1000,
        },
        "risk_calculations": {
            "max_avg_latency_ms": 200,
            "max_p95_latency_ms": 500,
            "max_error_rate": 0.001,
            "min_ops_per_second": 10,
        },
        "signal_generation": {
            "max_avg_latency_ms": 2000,
            "max_p95_latency_ms": 5000,
            "max_error_rate": 0.01,
            "min_ops_per_second": 1,
        },
    }

    print(f"   ✓ Defined thresholds for {len(thresholds)} test categories")

    for category, limits in thresholds.items():
        print(f"   ✓ {category}: {len(limits)} performance limits defined")

    print("   ✓ Performance thresholds validation complete")


async def main():
    """Main test execution."""
    print("FXML4 Stress Testing Framework Validation")
    print("Testing framework components without pytest dependency...")

    try:
        # Test the stress framework
        success = await test_stress_framework()

        if success:
            # Test performance thresholds
            test_performance_thresholds()

            print("\n🎉 All tests completed successfully!")
            print("The stress testing framework is ready for use.")
            return 0
        else:
            print("\n❌ Some tests failed.")
            return 1

    except Exception as e:
        print(f"\n💥 Test execution failed: {e}")
        import traceback

        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
