#!/usr/bin/env python3
"""
Performance Benchmarking Runner

This script runs comprehensive performance benchmarks with historical tracking
and regression detection.
"""

import argparse
import asyncio
import sys
from datetime import datetime, timedelta
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Import benchmarking framework
try:
    from tests.performance.test_performance_benchmarking import (
        BenchmarkCategory,
        PerformanceBenchmarker,
        run_comprehensive_benchmarks,
    )

    BENCHMARKING_AVAILABLE = True
except ImportError as e:
    print(f"Warning: Performance benchmarking framework not available: {e}")
    BENCHMARKING_AVAILABLE = False


async def run_continuous_benchmarks(interval_minutes: int = 60):
    """Run benchmarks continuously at specified interval."""
    benchmarker = PerformanceBenchmarker()

    while True:
        print(f"\n{'=' * 60}")
        print(f"Running scheduled benchmark at {datetime.now()}")
        print("=" * 60)

        results = await run_comprehensive_benchmarks()

        # Check for critical issues
        critical_count = sum(1 for r in results if r.status.value == "critical")

        if critical_count > 0:
            print(f"\n⚠️ ALERT: {critical_count} critical performance issues detected!")

        # Wait for next iteration
        print(f"\nNext benchmark scheduled in {interval_minutes} minutes...")
        await asyncio.sleep(interval_minutes * 60)


async def run_targeted_benchmark(category: str, iterations: int = 100):
    """Run targeted benchmark for specific category."""
    benchmarker = PerformanceBenchmarker()

    print(f"Running targeted benchmark for {category}")
    print("=" * 50)

    results = []

    if category == "api":
        results = await benchmarker.benchmark_api_endpoints()
    elif category == "database":
        results = benchmarker.benchmark_database_queries()
    elif category == "ml":
        results = benchmarker.benchmark_ml_inference()
    elif category == "order":
        results = [benchmarker.benchmark_order_processing()]
    elif category == "memory":
        results = [benchmarker.benchmark_memory_usage()]
    else:
        print(f"Unknown category: {category}")
        return

    # Save and report
    benchmarker.save_results(results)
    report = benchmarker.generate_performance_report(results)
    print(report)


async def analyze_historical_trends(days: int = 30):
    """Analyze performance trends over time."""
    benchmarker = PerformanceBenchmarker()

    print(f"Analyzing performance trends for last {days} days")
    print("=" * 50)

    # Load historical data
    history_dir = Path("benchmark_history")
    if not history_dir.exists():
        print("No historical data found")
        return

    cutoff_date = datetime.now() - timedelta(days=days)

    # Group by category and date
    trends = {}

    for history_file in history_dir.glob("*.json"):
        import json

        with open(history_file) as f:
            data = json.load(f)

        timestamp = datetime.fromisoformat(data["timestamp"])
        if timestamp < cutoff_date:
            continue

        category = data["category"]
        date_key = timestamp.date().isoformat()

        if category not in trends:
            trends[category] = {}
        if date_key not in trends[category]:
            trends[category][date_key] = []

        # Extract key metric (first one)
        if data["metrics"]:
            trends[category][date_key].append(data["metrics"][0]["value"])

    # Report trends
    print("\nPerformance Trends:")
    print("-" * 40)

    for category, dates in trends.items():
        print(f"\n{category.upper()}:")

        sorted_dates = sorted(dates.keys())
        if len(sorted_dates) >= 2:
            # Compare first and last
            first_date = sorted_dates[0]
            last_date = sorted_dates[-1]

            first_avg = sum(dates[first_date]) / len(dates[first_date])
            last_avg = sum(dates[last_date]) / len(dates[last_date])

            change_pct = ((last_avg - first_avg) / first_avg) * 100

            if change_pct > 10:
                print(f"  ⚠️ Performance degraded by {change_pct:.1f}%")
            elif change_pct < -10:
                print(f"  ✅ Performance improved by {abs(change_pct):.1f}%")
            else:
                print(f"  → Stable performance (±{abs(change_pct):.1f}%)")

            print(f"     {first_date}: {first_avg:.2f}ms")
            print(f"     {last_date}: {last_avg:.2f}ms")


async def main():
    """Main entry point for performance benchmarking."""
    parser = argparse.ArgumentParser(
        description="FXML4 Performance Benchmarking Runner"
    )

    parser.add_argument(
        "command",
        choices=["run", "continuous", "targeted", "trends", "update-baselines"],
        help="Benchmark command to execute",
    )

    parser.add_argument(
        "--category",
        choices=["api", "database", "ml", "order", "memory"],
        help="Category for targeted benchmarks",
    )

    parser.add_argument(
        "--interval",
        type=int,
        default=60,
        help="Interval in minutes for continuous benchmarking (default: 60)",
    )

    parser.add_argument(
        "--days",
        type=int,
        default=30,
        help="Number of days for trend analysis (default: 30)",
    )

    parser.add_argument(
        "--iterations",
        type=int,
        default=100,
        help="Number of iterations for benchmarks (default: 100)",
    )

    args = parser.parse_args()

    if not BENCHMARKING_AVAILABLE:
        print("❌ Performance benchmarking framework not available")
        return 1

    try:
        if args.command == "run":
            # Run comprehensive benchmarks once
            results = await run_comprehensive_benchmarks()
            print(f"\n✅ Completed {len(results)} benchmarks")

        elif args.command == "continuous":
            # Run benchmarks continuously
            await run_continuous_benchmarks(args.interval)

        elif args.command == "targeted":
            # Run targeted benchmark
            if not args.category:
                print("❌ --category required for targeted benchmarks")
                return 1
            await run_targeted_benchmark(args.category, args.iterations)

        elif args.command == "trends":
            # Analyze historical trends
            await analyze_historical_trends(args.days)

        elif args.command == "update-baselines":
            # Update performance baselines
            benchmarker = PerformanceBenchmarker()
            benchmarker.update_baselines()
            print("✅ Performance baselines updated")

        return 0

    except KeyboardInterrupt:
        print("\n⚠️ Benchmarking interrupted by user")
        return 0

    except Exception as e:
        print(f"💥 Benchmarking failed: {e}")
        import traceback

        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
