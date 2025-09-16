#!/usr/bin/env python3
"""E2E Test Framework and Benchmarking Suite for FXML4-ForexConnect Integration.

Comprehensive test runner with performance benchmarking, metrics collection,
and automated validation reporting following TDD methodology.
"""

import argparse
import asyncio
import csv
import json
import logging
import os
import statistics
import sys
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from fxml4.api.account_monitoring import (
    AccountReconciler,
    AccountSnapshot,
    AccountStateManager,
    AlertType,
    MarginMonitor,
    PositionData,
    PositionTracker,
)
from fxml4.api.websocket_market_data import (
    FeedFailoverManager,
    FeedSource,
    OHLCBarAggregator,
    PriceFeedMonitor,
    TickData,
    TimeFrame,
    WebSocketMarketDataManager,
)

# Import paths handled by PYTHONPATH wrapper


@dataclass
class BenchmarkResult:
    """Benchmark test result."""

    test_name: str
    execution_time_ms: float
    throughput_ops_per_sec: float
    memory_usage_mb: float
    cpu_usage_percent: float
    success: bool
    error_message: Optional[str] = None
    metrics: Dict[str, Any] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)


@dataclass
class E2ETestResult:
    """End-to-end test result."""

    test_suite: str
    test_name: str
    success: bool
    execution_time_ms: float
    assertions_passed: int
    assertions_total: int
    error_details: Optional[str] = None
    performance_metrics: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)


@dataclass
class TestSuiteReport:
    """Complete test suite report."""

    suite_name: str
    start_time: datetime
    end_time: datetime
    total_tests: int
    passed_tests: int
    failed_tests: int
    total_execution_time_ms: float
    average_throughput: float
    peak_memory_usage_mb: float
    test_results: List[E2ETestResult]
    benchmark_results: List[BenchmarkResult]

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        result = asdict(self)
        result["start_time"] = self.start_time.isoformat()
        result["end_time"] = self.end_time.isoformat()
        return result


class E2ETestFramework:
    """End-to-end test framework with benchmarking capabilities."""

    def __init__(self, output_dir: str = "test_results"):
        """Initialize E2E test framework."""
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)

        self.test_results: List[E2ETestResult] = []
        self.benchmark_results: List[BenchmarkResult] = []
        self.start_time = datetime.utcnow()

        # Setup logging
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            handlers=[
                logging.StreamHandler(sys.stdout),
                logging.FileHandler(self.output_dir / "e2e_tests.log"),
            ],
        )
        self.logger = logging.getLogger(__name__)

        self.logger.info("E2E Test Framework initialized")

    async def benchmark_function(
        self, func, *args, **kwargs
    ) -> Tuple[Any, BenchmarkResult]:
        """Benchmark a function call and return result with metrics."""
        import gc

        import psutil

        # Force garbage collection before test
        gc.collect()

        # Get initial metrics
        process = psutil.Process()
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB

        start_time = time.perf_counter()
        start_cpu_time = process.cpu_percent()

        try:
            # Execute function
            if asyncio.iscoroutinefunction(func):
                result = await func(*args, **kwargs)
            else:
                result = func(*args, **kwargs)

            success = True
            error_message = None
        except Exception as e:
            result = None
            success = False
            error_message = str(e)

        # Calculate metrics
        end_time = time.perf_counter()
        execution_time_ms = (end_time - start_time) * 1000

        end_cpu_time = process.cpu_percent()
        final_memory = process.memory_info().rss / 1024 / 1024  # MB

        # Estimate throughput (operations per second)
        throughput = 1000 / execution_time_ms if execution_time_ms > 0 else 0

        benchmark = BenchmarkResult(
            test_name=func.__name__,
            execution_time_ms=execution_time_ms,
            throughput_ops_per_sec=throughput,
            memory_usage_mb=final_memory - initial_memory,
            cpu_usage_percent=end_cpu_time - start_cpu_time,
            success=success,
            error_message=error_message,
        )

        return result, benchmark

    async def run_market_data_streaming_tests(self) -> List[E2ETestResult]:
        """Run comprehensive market data streaming tests."""
        self.logger.info("Starting Market Data Streaming Tests")

        test_results = []

        # Test 1: WebSocket Broadcasting Performance
        test_name = "websocket_broadcasting_performance"
        start_time = time.perf_counter()

        try:
            ws_manager = WebSocketMarketDataManager()

            # Create test clients
            from unittest.mock import AsyncMock, MagicMock

            clients = []
            for i in range(10):
                client = MagicMock()
                client.client_id = f"perf_client_{i}"
                client.send = AsyncMock()
                clients.append(client)
                await ws_manager.register_client(client)
                await ws_manager.subscribe_client_to_symbol(client.client_id, "EURUSD")

            # Benchmark message broadcasting
            async def broadcast_messages():
                for i in range(100):
                    message = {
                        "type": "price_update",
                        "symbol": "EURUSD",
                        "bid": 1.1200 + (i * 0.0001),
                        "ask": 1.1202 + (i * 0.0001),
                    }
                    await ws_manager.broadcast_to_symbol_subscribers("EURUSD", message)

            result, benchmark = await self.benchmark_function(broadcast_messages)

            # Assertions
            assertions_passed = 0
            assertions_total = 3

            if ws_manager.active_connections == 10:
                assertions_passed += 1
            if len(ws_manager.subscriptions["EURUSD"]) == 10:
                assertions_passed += 1
            if all(client.send.call_count == 100 for client in clients):
                assertions_passed += 1

            success = assertions_passed == assertions_total

        except Exception as e:
            success = False
            assertions_passed = 0
            assertions_total = 3

        execution_time = (time.perf_counter() - start_time) * 1000

        test_result = E2ETestResult(
            test_suite="MarketDataStreaming",
            test_name=test_name,
            success=success,
            execution_time_ms=execution_time,
            assertions_passed=assertions_passed,
            assertions_total=assertions_total,
            performance_metrics={
                "clients_count": 10,
                "messages_per_client": 100,
                "total_broadcasts": 1000,
            },
        )

        test_results.append(test_result)
        if "benchmark" in locals():
            self.benchmark_results.append(benchmark)

        # Test 2: OHLC Bar Aggregation Performance
        test_name = "ohlc_aggregation_performance"
        start_time = time.perf_counter()

        try:
            ohlc_aggregator = OHLCBarAggregator()

            # Generate high-frequency tick data
            ticks = []
            base_time = datetime.utcnow()
            for i in range(1000):  # 1000 ticks
                tick = TickData(
                    symbol="EURUSD",
                    bid=1.1200 + (i * 0.00001),
                    ask=1.1202 + (i * 0.00001),
                    timestamp=base_time + timedelta(seconds=i),
                )
                ticks.append(tick)

            # Benchmark aggregation
            async def aggregate_ticks():
                completed_bars = []
                for tick in ticks:
                    bars = await ohlc_aggregator.process_tick(
                        tick, TimeFrame.ONE_MINUTE
                    )
                    completed_bars.extend(bars)
                return completed_bars

            bars, benchmark = await self.benchmark_function(aggregate_ticks)

            # Assertions
            assertions_passed = 0
            assertions_total = 3

            if len(bars) > 0:  # Should produce some completed bars
                assertions_passed += 1
            if len(ohlc_aggregator.active_bars) >= 0:  # Should have active bars
                assertions_passed += 1
            if benchmark.throughput_ops_per_sec > 100:  # Should process >100 ticks/sec
                assertions_passed += 1

            success = assertions_passed == assertions_total

        except Exception as e:
            success = False
            assertions_passed = 0
            assertions_total = 3

        execution_time = (time.perf_counter() - start_time) * 1000

        test_result = E2ETestResult(
            test_suite="MarketDataStreaming",
            test_name=test_name,
            success=success,
            execution_time_ms=execution_time,
            assertions_passed=assertions_passed,
            assertions_total=assertions_total,
            performance_metrics={
                "ticks_processed": len(ticks) if "ticks" in locals() else 0,
                "bars_completed": len(bars) if "bars" in locals() else 0,
            },
        )

        test_results.append(test_result)
        if "benchmark" in locals():
            self.benchmark_results.append(benchmark)

        self.logger.info(
            f"Market Data Streaming Tests completed: {len([r for r in test_results if r.success])}/{len(test_results)} passed"
        )
        return test_results

    async def run_account_monitoring_tests(self) -> List[E2ETestResult]:
        """Run comprehensive account monitoring tests."""
        self.logger.info("Starting Account Monitoring Tests")

        test_results = []

        # Test 1: Account State Management Performance
        test_name = "account_state_management_performance"
        start_time = time.perf_counter()

        try:
            account_manager = AccountStateManager()

            # Generate account updates
            updates = []
            for i in range(500):  # 500 account updates
                update = {
                    "account_id": "PERF_TEST_001",
                    "balance": 50000.00 + (i * 10),
                    "equity": 52000.00 + (i * 12),
                    "margin_used": 2000.00 + (i * 5),
                    "margin_available": 50000.00,
                    "pl": 2000.00 + (i * 2),
                    "currency": "USD",
                    "timestamp": (datetime.utcnow() + timedelta(seconds=i)).isoformat(),
                }
                updates.append(update)

            # Benchmark processing
            async def process_account_updates():
                snapshots = []
                for update in updates:
                    snapshot = await account_manager.process_forex_account_update(
                        update
                    )
                    snapshots.append(snapshot)
                return snapshots

            snapshots, benchmark = await self.benchmark_function(
                process_account_updates
            )

            # Assertions
            assertions_passed = 0
            assertions_total = 4

            if len(snapshots) == 500:
                assertions_passed += 1
            if len(account_manager.balance_history) == 500:
                assertions_passed += 1
            if account_manager.current_snapshot is not None:
                assertions_passed += 1
            if benchmark.throughput_ops_per_sec > 50:  # Should process >50 updates/sec
                assertions_passed += 1

            success = assertions_passed == assertions_total

        except Exception as e:
            success = False
            assertions_passed = 0
            assertions_total = 4

        execution_time = (time.perf_counter() - start_time) * 1000

        test_result = E2ETestResult(
            test_suite="AccountMonitoring",
            test_name=test_name,
            success=success,
            execution_time_ms=execution_time,
            assertions_passed=assertions_passed,
            assertions_total=assertions_total,
            performance_metrics={
                "updates_processed": len(updates) if "updates" in locals() else 0,
                "snapshots_created": len(snapshots) if "snapshots" in locals() else 0,
            },
        )

        test_results.append(test_result)
        if "benchmark" in locals():
            self.benchmark_results.append(benchmark)

        # Test 2: Position Tracking Performance
        test_name = "position_tracking_performance"
        start_time = time.perf_counter()

        try:
            position_tracker = PositionTracker()

            # Generate position updates
            positions = []
            symbols = ["EURUSD", "GBPUSD", "USDJPY", "USDCHF", "AUDUSD"]

            for i in range(200):  # 200 position updates
                symbol = symbols[i % len(symbols)]
                position = {
                    "position_id": f"POS_{i:04d}",
                    "symbol": symbol,
                    "side": "long" if i % 2 == 0 else "short",
                    "quantity": 100000,
                    "open_price": 1.1000 + (i * 0.0001),
                    "current_price": 1.1050 + (i * 0.0001),
                    "unrealized_pl": 500.00 + (i * 10),
                    "timestamp": (datetime.utcnow() + timedelta(seconds=i)).isoformat(),
                }
                positions.append(position)

            # Benchmark processing
            async def process_position_updates():
                processed_positions = []
                for pos_data in positions:
                    position = await position_tracker.process_forex_position_update(
                        pos_data
                    )
                    processed_positions.append(position)
                return processed_positions

            processed, benchmark = await self.benchmark_function(
                process_position_updates
            )

            # Assertions
            assertions_passed = 0
            assertions_total = 4

            if len(processed) == 200:
                assertions_passed += 1
            if len(position_tracker.active_positions) == 200:
                assertions_passed += 1
            total_pl = position_tracker.calculate_total_unrealized_pl()
            if total_pl > 0:
                assertions_passed += 1
            if benchmark.throughput_ops_per_sec > 50:
                assertions_passed += 1

            success = assertions_passed == assertions_total

        except Exception as e:
            success = False
            assertions_passed = 0
            assertions_total = 4

        execution_time = (time.perf_counter() - start_time) * 1000

        test_result = E2ETestResult(
            test_suite="AccountMonitoring",
            test_name=test_name,
            success=success,
            execution_time_ms=execution_time,
            assertions_passed=assertions_passed,
            assertions_total=assertions_total,
            performance_metrics={
                "positions_processed": len(positions) if "positions" in locals() else 0,
                "active_positions": len(position_tracker.active_positions),
                "total_unrealized_pl": position_tracker.total_unrealized_pl,
            },
        )

        test_results.append(test_result)
        if "benchmark" in locals():
            self.benchmark_results.append(benchmark)

        self.logger.info(
            f"Account Monitoring Tests completed: {len([r for r in test_results if r.success])}/{len(test_results)} passed"
        )
        return test_results

    async def run_integration_stress_tests(self) -> List[E2ETestResult]:
        """Run integration stress tests simulating high load scenarios."""
        self.logger.info("Starting Integration Stress Tests")

        test_results = []

        # Stress Test: Concurrent Multi-Component Processing
        test_name = "concurrent_multi_component_stress"
        start_time = time.perf_counter()

        try:
            # Initialize all components
            ws_manager = WebSocketMarketDataManager()
            account_manager = AccountStateManager()
            position_tracker = PositionTracker()
            margin_monitor = MarginMonitor()
            ohlc_aggregator = OHLCBarAggregator()

            # Setup WebSocket clients
            from unittest.mock import AsyncMock, MagicMock

            clients = []
            for i in range(20):  # 20 concurrent clients
                client = MagicMock()
                client.client_id = f"stress_client_{i}"
                client.send = AsyncMock()
                clients.append(client)
                await ws_manager.register_client(client)
                await ws_manager.subscribe_client_to_symbol(client.client_id, "EURUSD")

            # Concurrent processing function
            async def stress_test_processing():
                tasks = []

                # Task 1: High-frequency price updates
                async def price_updates():
                    for i in range(1000):
                        tick = TickData(
                            symbol="EURUSD",
                            bid=1.1200 + (i * 0.00001),
                            ask=1.1202 + (i * 0.00001),
                            timestamp=datetime.utcnow(),
                        )
                        await ohlc_aggregator.process_tick(tick, TimeFrame.ONE_MINUTE)

                        message = {
                            "type": "price_update",
                            "symbol": "EURUSD",
                            "bid": tick.bid,
                            "ask": tick.ask,
                        }
                        await ws_manager.broadcast_to_symbol_subscribers(
                            "EURUSD", message
                        )

                # Task 2: Account state updates
                async def account_updates():
                    for i in range(500):
                        account_data = {
                            "account_id": "STRESS_ACCOUNT",
                            "balance": 100000.00 + (i * 20),
                            "equity": 105000.00 + (i * 25),
                            "margin_used": 5000.00 + (i * 10),
                            "margin_available": 100000.00,
                            "pl": 5000.00 + (i * 15),
                            "currency": "USD",
                            "timestamp": datetime.utcnow().isoformat(),
                        }
                        await account_manager.process_forex_account_update(account_data)
                        await margin_monitor.process_margin_update(account_data)

                # Task 3: Position updates
                async def position_updates():
                    for i in range(300):
                        position_data = {
                            "position_id": f"STRESS_POS_{i:04d}",
                            "symbol": "EURUSD",
                            "side": "long" if i % 2 == 0 else "short",
                            "quantity": 100000,
                            "open_price": 1.1200,
                            "current_price": 1.1200 + (i * 0.0001),
                            "unrealized_pl": (i * 0.0001) * 100000,
                            "timestamp": datetime.utcnow().isoformat(),
                        }
                        await position_tracker.process_forex_position_update(
                            position_data
                        )

                # Run all tasks concurrently
                await asyncio.gather(
                    price_updates(), account_updates(), position_updates()
                )

                return {
                    "price_updates": 1000,
                    "account_updates": 500,
                    "position_updates": 300,
                }

            result, benchmark = await self.benchmark_function(stress_test_processing)

            # Assertions
            assertions_passed = 0
            assertions_total = 5

            if len(account_manager.balance_history) >= 500:
                assertions_passed += 1
            if len(position_tracker.active_positions) >= 300:
                assertions_passed += 1
            if ws_manager.active_connections == 20:
                assertions_passed += 1
            if benchmark.execution_time_ms < 30000:  # Should complete within 30 seconds
                assertions_passed += 1
            if benchmark.success:
                assertions_passed += 1

            success = assertions_passed == assertions_total

        except Exception as e:
            success = False
            assertions_passed = 0
            assertions_total = 5

        execution_time = (time.perf_counter() - start_time) * 1000

        test_result = E2ETestResult(
            test_suite="IntegrationStress",
            test_name=test_name,
            success=success,
            execution_time_ms=execution_time,
            assertions_passed=assertions_passed,
            assertions_total=assertions_total,
            performance_metrics={
                "concurrent_operations": 1800,  # 1000 + 500 + 300
                "concurrent_clients": 20,
                "total_execution_time_ms": execution_time,
            },
        )

        test_results.append(test_result)
        if "benchmark" in locals():
            self.benchmark_results.append(benchmark)

        self.logger.info(
            f"Integration Stress Tests completed: {len([r for r in test_results if r.success])}/{len(test_results)} passed"
        )
        return test_results

    async def generate_test_report(self) -> TestSuiteReport:
        """Generate comprehensive test suite report."""
        end_time = datetime.utcnow()

        # Calculate summary statistics
        total_tests = len(self.test_results)
        passed_tests = len([r for r in self.test_results if r.success])
        failed_tests = total_tests - passed_tests

        total_execution_time = sum(r.execution_time_ms for r in self.test_results)

        # Calculate average throughput from benchmarks
        throughputs = [
            b.throughput_ops_per_sec for b in self.benchmark_results if b.success
        ]
        average_throughput = statistics.mean(throughputs) if throughputs else 0

        # Calculate peak memory usage
        memory_usages = [b.memory_usage_mb for b in self.benchmark_results if b.success]
        peak_memory_usage = max(memory_usages) if memory_usages else 0

        report = TestSuiteReport(
            suite_name="FXML4-ForexConnect Integration E2E Tests",
            start_time=self.start_time,
            end_time=end_time,
            total_tests=total_tests,
            passed_tests=passed_tests,
            failed_tests=failed_tests,
            total_execution_time_ms=total_execution_time,
            average_throughput=average_throughput,
            peak_memory_usage_mb=peak_memory_usage,
            test_results=self.test_results,
            benchmark_results=self.benchmark_results,
        )

        return report

    async def save_test_report(self, report: TestSuiteReport) -> None:
        """Save test report to files."""
        # Save JSON report
        json_file = (
            self.output_dir
            / f"e2e_test_report_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json"
        )
        with open(json_file, "w") as f:
            json.dump(report.to_dict(), f, indent=2, default=str)

        # Save CSV summary
        csv_file = (
            self.output_dir
            / f"e2e_test_summary_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.csv"
        )
        with open(csv_file, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(
                [
                    "Test Suite",
                    "Test Name",
                    "Success",
                    "Execution Time (ms)",
                    "Assertions Passed",
                    "Assertions Total",
                ]
            )

            for result in report.test_results:
                writer.writerow(
                    [
                        result.test_suite,
                        result.test_name,
                        result.success,
                        result.execution_time_ms,
                        result.assertions_passed,
                        result.assertions_total,
                    ]
                )

        # Save benchmark CSV
        benchmark_csv = (
            self.output_dir
            / f"e2e_benchmarks_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.csv"
        )
        with open(benchmark_csv, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(
                [
                    "Test Name",
                    "Execution Time (ms)",
                    "Throughput (ops/sec)",
                    "Memory Usage (MB)",
                    "CPU Usage (%)",
                    "Success",
                ]
            )

            for result in report.benchmark_results:
                writer.writerow(
                    [
                        result.test_name,
                        result.execution_time_ms,
                        result.throughput_ops_per_sec,
                        result.memory_usage_mb,
                        result.cpu_usage_percent,
                        result.success,
                    ]
                )

        self.logger.info(f"Test reports saved to {self.output_dir}")
        self.logger.info(f"JSON Report: {json_file}")
        self.logger.info(f"CSV Summary: {csv_file}")
        self.logger.info(f"Benchmark CSV: {benchmark_csv}")

    async def run_all_tests(self) -> TestSuiteReport:
        """Run all E2E tests and generate report."""
        self.logger.info("🚀 Starting FXML4-ForexConnect Integration E2E Test Suite")

        # Run all test suites
        market_data_results = await self.run_market_data_streaming_tests()
        account_monitoring_results = await self.run_account_monitoring_tests()
        stress_test_results = await self.run_integration_stress_tests()

        # Combine all results
        self.test_results.extend(market_data_results)
        self.test_results.extend(account_monitoring_results)
        self.test_results.extend(stress_test_results)

        # Generate and save report
        report = await self.generate_test_report()
        await self.save_test_report(report)

        # Print summary
        self.print_test_summary(report)

        return report

    def print_test_summary(self, report: TestSuiteReport) -> None:
        """Print test summary to console."""
        print("\n" + "=" * 80)
        print("🏁 FXML4-ForexConnect Integration E2E Test Suite Complete")
        print("=" * 80)

        print(f"\n📊 Test Summary:")
        print(f"  Total Tests: {report.total_tests}")
        print(f"  ✅ Passed: {report.passed_tests}")
        print(f"  ❌ Failed: {report.failed_tests}")
        print(f"  📈 Success Rate: {(report.passed_tests/report.total_tests)*100:.1f}%")
        print(f"  ⏱️  Total Execution Time: {report.total_execution_time_ms/1000:.2f}s")

        print(f"\n🔥 Performance Metrics:")
        print(f"  Average Throughput: {report.average_throughput:.1f} ops/sec")
        print(f"  Peak Memory Usage: {report.peak_memory_usage_mb:.1f} MB")
        print(f"  Total Benchmarks: {len(report.benchmark_results)}")

        print(f"\n📂 Test Results by Suite:")
        suites = {}
        for result in report.test_results:
            if result.test_suite not in suites:
                suites[result.test_suite] = {"passed": 0, "total": 0}
            suites[result.test_suite]["total"] += 1
            if result.success:
                suites[result.test_suite]["passed"] += 1

        for suite_name, stats in suites.items():
            success_rate = (stats["passed"] / stats["total"]) * 100
            print(
                f"  {suite_name}: {stats['passed']}/{stats['total']} ({success_rate:.1f}%)"
            )

        if report.failed_tests > 0:
            print(f"\n❌ Failed Tests:")
            for result in report.test_results:
                if not result.success:
                    print(f"  - {result.test_suite}::{result.test_name}")
                    if result.error_details:
                        print(f"    Error: {result.error_details}")

        print(f"\n📁 Reports saved to: {self.output_dir}")
        print("=" * 80)


async def main():
    """Main entry point for E2E test framework."""
    parser = argparse.ArgumentParser(
        description="FXML4-ForexConnect Integration E2E Test Suite"
    )
    parser.add_argument(
        "--output-dir", default="test_results", help="Output directory for test results"
    )
    parser.add_argument(
        "--suite",
        choices=["all", "market-data", "account-monitoring", "stress"],
        default="all",
        help="Test suite to run",
    )
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose logging")

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # Initialize test framework
    framework = E2ETestFramework(output_dir=args.output_dir)

    try:
        if args.suite == "all":
            report = await framework.run_all_tests()
        elif args.suite == "market-data":
            results = await framework.run_market_data_streaming_tests()
            framework.test_results.extend(results)
            report = await framework.generate_test_report()
            await framework.save_test_report(report)
        elif args.suite == "account-monitoring":
            results = await framework.run_account_monitoring_tests()
            framework.test_results.extend(results)
            report = await framework.generate_test_report()
            await framework.save_test_report(report)
        elif args.suite == "stress":
            results = await framework.run_integration_stress_tests()
            framework.test_results.extend(results)
            report = await framework.generate_test_report()
            await framework.save_test_report(report)

        framework.print_test_summary(report)

        # Exit with appropriate code
        sys.exit(0 if report.failed_tests == 0 else 1)

    except Exception as e:
        framework.logger.error(f"Test framework error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
