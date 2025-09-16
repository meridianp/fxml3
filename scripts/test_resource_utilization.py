#!/usr/bin/env python3
"""
Resource utilization validation under trading load for FXML4.
Targets: CPU <70%, Memory <4GB, Storage I/O <80%
"""

import asyncio
import json
import logging
import os
import statistics
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import psutil
import requests

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ResourceMonitor:
    """Comprehensive system resource monitoring during trading load."""

    def __init__(self):
        self.monitoring = False
        self.resource_data = []
        self.start_time = None
        self.monitor_thread = None

    def start_monitoring(self, interval: float = 0.5):
        """Start continuous resource monitoring."""
        self.monitoring = True
        self.start_time = time.perf_counter()
        self.resource_data = []
        self.monitor_thread = threading.Thread(
            target=self._monitor_loop, args=(interval,)
        )
        self.monitor_thread.daemon = True
        self.monitor_thread.start()
        logger.info("Resource monitoring started")

    def stop_monitoring(self):
        """Stop resource monitoring."""
        self.monitoring = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=2.0)
        logger.info(
            f"Resource monitoring stopped. Collected {len(self.resource_data)} data points"
        )

    def _monitor_loop(self, interval: float):
        """Continuous monitoring loop."""
        while self.monitoring:
            try:
                timestamp = time.perf_counter() - self.start_time

                # CPU metrics
                cpu_percent = psutil.cpu_percent(interval=None)
                cpu_count = psutil.cpu_count()
                load_avg = (
                    psutil.getloadavg()[0] if hasattr(psutil, "getloadavg") else 0
                )

                # Memory metrics
                memory = psutil.virtual_memory()
                memory_gb = memory.used / (1024**3)
                memory_percent = memory.percent

                # Disk I/O metrics
                disk_io = psutil.disk_io_counters()
                disk_usage = psutil.disk_usage("/")
                disk_io_percent = (
                    (disk_usage.used / disk_usage.total) * 100
                    if disk_usage.total > 0
                    else 0
                )

                # Network I/O metrics
                network_io = psutil.net_io_counters()

                # Process-specific metrics
                process = psutil.Process()
                process_memory = process.memory_info().rss / (1024**3)  # GB
                process_cpu = process.cpu_percent()

                data_point = {
                    "timestamp": timestamp,
                    "datetime": datetime.utcnow().isoformat(),
                    "cpu": {
                        "percent": cpu_percent,
                        "count": cpu_count,
                        "load_avg": load_avg,
                        "process_cpu": process_cpu,
                    },
                    "memory": {
                        "total_gb": memory.total / (1024**3),
                        "used_gb": memory_gb,
                        "percent": memory_percent,
                        "available_gb": memory.available / (1024**3),
                        "process_memory_gb": process_memory,
                    },
                    "disk": {
                        "io_percent": disk_io_percent,
                        "read_bytes": disk_io.read_bytes if disk_io else 0,
                        "write_bytes": disk_io.write_bytes if disk_io else 0,
                        "read_count": disk_io.read_count if disk_io else 0,
                        "write_count": disk_io.write_count if disk_io else 0,
                    },
                    "network": {
                        "bytes_sent": network_io.bytes_sent if network_io else 0,
                        "bytes_recv": network_io.bytes_recv if network_io else 0,
                        "packets_sent": network_io.packets_sent if network_io else 0,
                        "packets_recv": network_io.packets_recv if network_io else 0,
                    },
                }

                self.resource_data.append(data_point)

            except Exception as e:
                logger.warning(f"Resource monitoring error: {e}")

            time.sleep(interval)

    def get_statistics(self) -> Dict[str, Any]:
        """Calculate resource utilization statistics."""
        if not self.resource_data:
            return {}

        cpu_percentages = [d["cpu"]["percent"] for d in self.resource_data]
        memory_gb = [d["memory"]["used_gb"] for d in self.resource_data]
        memory_percentages = [d["memory"]["percent"] for d in self.resource_data]
        disk_percentages = [d["disk"]["io_percent"] for d in self.resource_data]
        process_memory = [d["memory"]["process_memory_gb"] for d in self.resource_data]
        process_cpu = [d["cpu"]["process_cpu"] for d in self.resource_data]

        return {
            "duration": time.perf_counter() - self.start_time if self.start_time else 0,
            "data_points": len(self.resource_data),
            "cpu": {
                "avg_percent": statistics.mean(cpu_percentages),
                "max_percent": max(cpu_percentages),
                "min_percent": min(cpu_percentages),
                "p95_percent": (
                    sorted(cpu_percentages)[int(len(cpu_percentages) * 0.95)]
                    if cpu_percentages
                    else 0
                ),
                "sustained_high": sum(1 for x in cpu_percentages if x > 70)
                / len(cpu_percentages)
                * 100,
            },
            "memory": {
                "avg_gb": statistics.mean(memory_gb),
                "max_gb": max(memory_gb),
                "min_gb": min(memory_gb),
                "p95_gb": (
                    sorted(memory_gb)[int(len(memory_gb) * 0.95)] if memory_gb else 0
                ),
                "avg_percent": statistics.mean(memory_percentages),
                "max_percent": max(memory_percentages),
            },
            "disk": {
                "avg_percent": statistics.mean(disk_percentages),
                "max_percent": max(disk_percentages),
                "min_percent": min(disk_percentages),
                "p95_percent": (
                    sorted(disk_percentages)[int(len(disk_percentages) * 0.95)]
                    if disk_percentages
                    else 0
                ),
            },
            "process": {
                "avg_memory_gb": statistics.mean(process_memory),
                "max_memory_gb": max(process_memory),
                "avg_cpu_percent": statistics.mean(process_cpu),
                "max_cpu_percent": max(process_cpu),
            },
        }


class TradingLoadSimulator:
    """Simulate realistic trading system load."""

    def __init__(self, api_base_url: str = "http://localhost:8001"):
        self.api_base_url = api_base_url
        self.session = requests.Session()
        # Generate JWT token for API access
        self.token = self._generate_test_token()
        if self.token:
            self.session.headers.update(
                {
                    "Authorization": f"Bearer {self.token}",
                    "Content-Type": "application/json",
                }
            )

    def _generate_test_token(self) -> Optional[str]:
        """Generate a test JWT token."""
        try:
            sys.path.insert(0, "/home/cnross/code/fxml4")
            from scripts.generate_test_token import main as generate_token

            return generate_token()
        except Exception as e:
            logger.warning(f"Could not generate test token: {e}")
            return None

    def simulate_market_data_requests(
        self, duration: int, requests_per_second: int = 10
    ):
        """Simulate high-frequency market data requests."""
        logger.info(
            f"Starting market data simulation: {requests_per_second} req/s for {duration}s"
        )

        end_time = time.time() + duration
        request_count = 0

        while time.time() < end_time:
            try:
                # Market data request
                response = self.session.get(
                    f"{self.api_base_url}/api/data/market_data",
                    params={"symbol": "GBPUSD", "timeframe": "1m", "limit": 100},
                    timeout=5.0,
                )

                request_count += 1
                if request_count % 50 == 0:
                    logger.info(f"Market data requests: {request_count}")

                # Control request rate
                time.sleep(1.0 / requests_per_second)

            except Exception as e:
                logger.warning(f"Market data request error: {e}")

    def simulate_signal_requests(self, duration: int, requests_per_second: int = 2):
        """Simulate ML signal generation requests."""
        logger.info(
            f"Starting signal simulation: {requests_per_second} req/s for {duration}s"
        )

        end_time = time.time() + duration
        request_count = 0

        while time.time() < end_time:
            try:
                # Signal generation request
                response = self.session.post(
                    f"{self.api_base_url}/api/signals/generate",
                    json={
                        "symbol": "GBPUSD",
                        "timeframe": "1h",
                        "strategy": "ml_ensemble",
                    },
                    timeout=10.0,
                )

                request_count += 1
                if request_count % 10 == 0:
                    logger.info(f"Signal requests: {request_count}")

                # Control request rate
                time.sleep(1.0 / requests_per_second)

            except Exception as e:
                logger.warning(f"Signal request error: {e}")

    def simulate_backtest_requests(self, duration: int, concurrent_backtests: int = 2):
        """Simulate CPU/memory intensive backtest requests."""
        logger.info(
            f"Starting backtest simulation: {concurrent_backtests} concurrent for {duration}s"
        )

        def run_backtest(backtest_id: int):
            try:
                response = self.session.post(
                    f"{self.api_base_url}/api/backtest",
                    json={
                        "symbol": "GBPUSD",
                        "timeframe": "1h",
                        "strategy": "ml_ensemble",
                        "start_date": "2024-01-01",
                        "end_date": "2024-02-01",
                        "initial_capital": 10000.0,
                    },
                    timeout=300.0,
                )

                logger.info(f"Backtest {backtest_id} completed")

            except Exception as e:
                logger.warning(f"Backtest {backtest_id} error: {e}")

        with ThreadPoolExecutor(max_workers=concurrent_backtests) as executor:
            futures = []
            end_time = time.time() + duration
            backtest_id = 0

            while time.time() < end_time:
                if len(futures) < concurrent_backtests:
                    future = executor.submit(run_backtest, backtest_id)
                    futures.append(future)
                    backtest_id += 1

                # Clean up completed futures
                futures = [f for f in futures if not f.done()]
                time.sleep(10)  # Space out backtest starts

    def simulate_database_operations(
        self, duration: int, operations_per_second: int = 5
    ):
        """Simulate I/O intensive database operations."""
        logger.info(
            f"Starting database simulation: {operations_per_second} ops/s for {duration}s"
        )

        try:
            sys.path.insert(0, "/home/cnross/code/fxml4")
            from fxml4.core.database_pool import get_pool_manager

            async def database_load():
                pool_manager = await get_pool_manager()
                end_time = time.time() + duration
                operation_count = 0

                while time.time() < end_time:
                    try:
                        # Heavy database operations
                        await pool_manager.execute(
                            """
                            SELECT
                                COUNT(*) as count,
                                AVG(close) as avg_close,
                                STDDEV(close) as stddev_close,
                                MAX(high) - MIN(low) as range_hl
                            FROM market_data_candles
                            WHERE symbol = 'GBPUSD'
                                AND timestamp >= NOW() - INTERVAL '24 hours'
                        """
                        )

                        operation_count += 1
                        if operation_count % 25 == 0:
                            logger.info(f"Database operations: {operation_count}")

                        await asyncio.sleep(1.0 / operations_per_second)

                    except Exception as e:
                        logger.warning(f"Database operation error: {e}")

            # Run async database operations
            asyncio.run(database_load())

        except Exception as e:
            logger.warning(f"Database simulation error: {e}")


async def test_resource_utilization():
    """Comprehensive resource utilization validation under trading load."""

    print("🔧 Testing Resource Utilization Under Trading Load")
    print("=" * 60)
    print("Targets: CPU <70%, Memory <4GB, Storage I/O <80%")
    print()

    # Resource utilization targets
    targets = {"cpu_percent": 70.0, "memory_gb": 4.0, "disk_io_percent": 80.0}

    # Initialize monitoring and simulation
    monitor = ResourceMonitor()
    simulator = TradingLoadSimulator()

    # Test scenarios with increasing load
    test_scenarios = [
        {
            "name": "Baseline Load",
            "duration": 30,
            "market_data_rps": 5,
            "signal_rps": 1,
            "concurrent_backtests": 1,
            "db_ops_rps": 2,
        },
        {
            "name": "Moderate Trading Load",
            "duration": 60,
            "market_data_rps": 15,
            "signal_rps": 3,
            "concurrent_backtests": 2,
            "db_ops_rps": 5,
        },
        {
            "name": "High Trading Load",
            "duration": 90,
            "market_data_rps": 25,
            "signal_rps": 5,
            "concurrent_backtests": 3,
            "db_ops_rps": 10,
        },
    ]

    results = {}

    for scenario in test_scenarios:
        scenario_name = scenario["name"]
        duration = scenario["duration"]

        print(f"\n📊 Testing {scenario_name} ({duration}s duration)")
        print("-" * 50)

        # Start resource monitoring
        monitor.start_monitoring(interval=0.5)

        # Run simulation workloads in parallel
        with ThreadPoolExecutor(max_workers=4) as executor:
            futures = [
                executor.submit(
                    simulator.simulate_market_data_requests,
                    duration,
                    scenario["market_data_rps"],
                ),
                executor.submit(
                    simulator.simulate_signal_requests, duration, scenario["signal_rps"]
                ),
                executor.submit(
                    simulator.simulate_backtest_requests,
                    duration,
                    scenario["concurrent_backtests"],
                ),
                executor.submit(
                    simulator.simulate_database_operations,
                    duration,
                    scenario["db_ops_rps"],
                ),
            ]

            # Wait for all workloads to complete
            for future in futures:
                try:
                    future.result()
                except Exception as e:
                    logger.warning(f"Workload error: {e}")

        # Stop monitoring and collect results
        monitor.stop_monitoring()
        stats = monitor.get_statistics()

        # Evaluate against targets
        cpu_pass = stats["cpu"]["p95_percent"] < targets["cpu_percent"]
        memory_pass = stats["memory"]["p95_gb"] < targets["memory_gb"]
        disk_pass = stats["disk"]["p95_percent"] < targets["disk_io_percent"]

        overall_pass = cpu_pass and memory_pass and disk_pass

        results[scenario_name] = {
            "stats": stats,
            "cpu_pass": cpu_pass,
            "memory_pass": memory_pass,
            "disk_pass": disk_pass,
            "overall_pass": overall_pass,
            "scenario_config": scenario,
        }

        # Display results
        status = "✅ PASS" if overall_pass else "❌ FAIL"
        print(
            f"   {status} - CPU: {stats['cpu']['p95_percent']:.1f}% (target <{targets['cpu_percent']}%)"
        )
        print(
            f"   {status} - Memory: {stats['memory']['p95_gb']:.1f}GB (target <{targets['memory_gb']}GB)"
        )
        print(
            f"   {status} - Disk I/O: {stats['disk']['p95_percent']:.1f}% (target <{targets['disk_io_percent']}%)"
        )
        print(
            f"   Duration: {stats['duration']:.1f}s, Data Points: {stats['data_points']}"
        )

        # Brief pause between scenarios
        if scenario != test_scenarios[-1]:
            print("   Cooling down...")
            time.sleep(10)

    # Overall assessment
    print("\n" + "=" * 60)
    print("📊 RESOURCE UTILIZATION SUMMARY")
    print("=" * 60)
    print(
        f"{'Scenario':<20} {'CPU P95':<10} {'Memory P95':<12} {'Disk I/O P95':<12} {'Status':<8}"
    )
    print("-" * 70)

    overall_system_pass = True
    for scenario_name, result in results.items():
        stats = result["stats"]
        status = "✅ PASS" if result["overall_pass"] else "❌ FAIL"
        print(
            f"{scenario_name:<20} {stats['cpu']['p95_percent']:<10.1f}% {stats['memory']['p95_gb']:<12.1f}GB {stats['disk']['p95_percent']:<12.1f}% {status:<8}"
        )
        overall_system_pass = overall_system_pass and result["overall_pass"]

    final_status = "✅ PASS" if overall_system_pass else "❌ FAIL"
    print(f"\nOverall Resource Utilization: {final_status}")

    # Detailed performance insights
    print(f"\n💡 PERFORMANCE INSIGHTS")
    for scenario_name, result in results.items():
        stats = result["stats"]
        config = result["scenario_config"]
        print(f"\n{scenario_name}:")
        print(
            f"  Load Config: {config['market_data_rps']} market req/s, {config['signal_rps']} signal req/s"
        )
        print(
            f"  Process Memory: Avg {stats['process']['avg_memory_gb']:.2f}GB, Max {stats['process']['max_memory_gb']:.2f}GB"
        )
        print(
            f"  Process CPU: Avg {stats['process']['avg_cpu_percent']:.1f}%, Max {stats['process']['max_cpu_percent']:.1f}%"
        )
        print(
            f"  System Sustained High CPU (>70%): {stats['cpu']['sustained_high']:.1f}% of time"
        )

    return overall_system_pass


async def main():
    """Run resource utilization validation tests."""
    success = await test_resource_utilization()
    return success


if __name__ == "__main__":
    success = asyncio.run(main())
    exit(0 if success else 1)
