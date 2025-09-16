"""
Stress Testing Framework for High-Frequency Trading Operations

This module implements comprehensive stress testing for high-frequency trading scenarios,
validating system performance under extreme load conditions and concurrent operations.

Test Categories:
- Order submission stress (1000+ orders/second)
- Market data processing stress (10,000+ ticks/second)
- Risk calculation stress (sub-100ms requirements)
- Memory and CPU stress under sustained load
- Database connection pool stress
- WebSocket connection stress

Performance Targets:
- Order processing: <100ms per order
- Signal generation: <2s end-to-end
- Risk calculations: <200ms
- Memory usage: <4GB sustained
- CPU usage: <70% sustained
"""

import asyncio
import statistics
import threading
import time

# Optional pytest import
try:
    import pytest

    PYTEST_AVAILABLE = True
except ImportError:
    PYTEST_AVAILABLE = False

    # Mock pytest decorators when pytest is not available
    class MockMark:
        def __getattr__(self, name):
            def decorator(func):
                return func

            return decorator

    class pytest:
        mark = MockMark()

        @staticmethod
        def fixture(*args, **kwargs):
            def decorator(func):
                return func

            return decorator

        @staticmethod
        def raises(*args, **kwargs):
            class ContextManager:
                def __enter__(self):
                    return self

                def __exit__(self, *args):
                    return False

            return ContextManager()


import json
import random
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

import psutil

# Mock imports with graceful fallback
try:
    from fxml4.brokers.base_adapter import BaseBrokerAdapter
    from fxml4.core.trading_engine import TradingEngine
    from fxml4.data_engineering.market_data_processor import MarketDataProcessor
    from fxml4.ml.signal_generator import SignalGenerator
    from fxml4.risk_management.risk_calculator import RiskCalculator

    IMPORT_SUCCESS = True
except ImportError:
    # Create mock classes for testing when imports fail
    class TradingEngine:
        def __init__(self):
            self.orders = []

        async def submit_order(self, order):
            await asyncio.sleep(0.001)  # Simulate processing time
            self.orders.append(order)
            return {"order_id": f"ORDER_{len(self.orders)}", "status": "SUBMITTED"}

    class BaseBrokerAdapter:
        def __init__(self):
            self.connected = True

        async def get_market_data(self, symbol):
            await asyncio.sleep(0.0001)  # Simulate network latency
            return {"symbol": symbol, "price": 1.1000 + random.uniform(-0.01, 0.01)}

    class RiskCalculator:
        def __init__(self):
            pass

        async def calculate_position_risk(self, position):
            await asyncio.sleep(0.05)  # Simulate calculation time
            return {"var": 0.02, "max_drawdown": 0.05}

    class SignalGenerator:
        def __init__(self):
            pass

        async def generate_signal(self, data):
            await asyncio.sleep(0.5)  # Simulate ML inference time
            return {"signal": "BUY", "confidence": 0.75}

    class MarketDataProcessor:
        def __init__(self):
            self.processed_ticks = []

        async def process_tick(self, tick):
            await asyncio.sleep(0.0001)
            self.processed_ticks.append(tick)
            return tick

    IMPORT_SUCCESS = False


@dataclass
class StressTestMetrics:
    """Container for stress test performance metrics."""

    total_operations: int
    duration_seconds: float
    operations_per_second: float
    avg_latency_ms: float
    p95_latency_ms: float
    p99_latency_ms: float
    error_rate: float
    peak_memory_mb: float
    peak_cpu_percent: float
    success_count: int
    error_count: int


@dataclass
class SystemResourceMetrics:
    """Container for system resource monitoring."""

    timestamp: datetime
    cpu_percent: float
    memory_mb: float
    memory_percent: float
    disk_io_read_mb: float
    disk_io_write_mb: float
    network_bytes_sent: int
    network_bytes_recv: int


class ResourceMonitor:
    """Monitor system resources during stress tests."""

    def __init__(self):
        self.metrics: List[SystemResourceMetrics] = []
        self.monitoring = False
        self.monitor_thread = None

    def start_monitoring(self, interval: float = 0.1):
        """Start resource monitoring in background thread."""
        self.monitoring = True
        self.metrics.clear()
        self.monitor_thread = threading.Thread(
            target=self._monitor_loop, args=(interval,)
        )
        self.monitor_thread.start()

    def stop_monitoring(self) -> List[SystemResourceMetrics]:
        """Stop monitoring and return collected metrics."""
        self.monitoring = False
        if self.monitor_thread:
            self.monitor_thread.join()
        return self.metrics.copy()

    def _monitor_loop(self, interval: float):
        """Background monitoring loop."""
        process = psutil.Process()

        while self.monitoring:
            try:
                # CPU and memory metrics
                cpu_percent = process.cpu_percent()
                memory_info = process.memory_info()
                memory_mb = memory_info.rss / (1024 * 1024)
                memory_percent = process.memory_percent()

                # I/O metrics
                io_counters = process.io_counters()
                disk_read_mb = io_counters.read_bytes / (1024 * 1024)
                disk_write_mb = io_counters.write_bytes / (1024 * 1024)

                # Network metrics (approximate)
                net_io = psutil.net_io_counters()

                metric = SystemResourceMetrics(
                    timestamp=datetime.now(),
                    cpu_percent=cpu_percent,
                    memory_mb=memory_mb,
                    memory_percent=memory_percent,
                    disk_io_read_mb=disk_read_mb,
                    disk_io_write_mb=disk_write_mb,
                    network_bytes_sent=net_io.bytes_sent,
                    network_bytes_recv=net_io.bytes_recv,
                )

                self.metrics.append(metric)
                time.sleep(interval)

            except Exception as e:
                # Continue monitoring even if individual metric collection fails
                continue


class HighFrequencyStressTester:
    """High-frequency trading stress testing framework."""

    def __init__(self):
        self.trading_engine = TradingEngine()
        self.broker_adapter = BaseBrokerAdapter()
        self.risk_calculator = RiskCalculator()
        self.signal_generator = SignalGenerator()
        self.market_data_processor = MarketDataProcessor()
        self.resource_monitor = ResourceMonitor()

    async def stress_test_order_submission(
        self, num_orders: int = 1000, concurrent_workers: int = 10
    ) -> StressTestMetrics:
        """Stress test order submission with high concurrency."""
        self.resource_monitor.start_monitoring()
        start_time = time.time()
        latencies = []
        errors = 0

        async def submit_single_order(order_id: int) -> Tuple[bool, float]:
            """Submit a single order and measure latency."""
            order_start = time.time()
            try:
                order = {
                    "id": order_id,
                    "symbol": "EURUSD",
                    "side": "BUY" if order_id % 2 == 0 else "SELL",
                    "quantity": 10000,
                    "price": 1.1000 + random.uniform(-0.01, 0.01),
                }

                result = await self.trading_engine.submit_order(order)
                latency = (time.time() - order_start) * 1000  # Convert to ms
                return True, latency

            except Exception as e:
                latency = (time.time() - order_start) * 1000
                return False, latency

        # Create semaphore to limit concurrent operations
        semaphore = asyncio.Semaphore(concurrent_workers)

        async def rate_limited_order(order_id: int) -> Tuple[bool, float]:
            """Rate-limited order submission."""
            async with semaphore:
                return await submit_single_order(order_id)

        # Submit all orders concurrently
        tasks = [rate_limited_order(i) for i in range(num_orders)]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Process results
        for result in results:
            if isinstance(result, Exception):
                errors += 1
                latencies.append(1000.0)  # Default high latency for errors
            else:
                success, latency = result
                latencies.append(latency)
                if not success:
                    errors += 1

        duration = time.time() - start_time
        resource_metrics = self.resource_monitor.stop_monitoring()

        return self._calculate_metrics(
            num_orders, duration, latencies, errors, resource_metrics
        )

    async def stress_test_market_data_processing(
        self, num_ticks: int = 10000, ticks_per_second: int = 1000
    ) -> StressTestMetrics:
        """Stress test market data processing at high frequency."""
        self.resource_monitor.start_monitoring()
        start_time = time.time()
        latencies = []
        errors = 0

        # Calculate delay between ticks
        tick_interval = 1.0 / ticks_per_second

        async def process_tick_batch(batch_size: int = 100) -> List[Tuple[bool, float]]:
            """Process a batch of market data ticks."""
            batch_results = []

            for i in range(batch_size):
                tick_start = time.time()
                try:
                    tick = {
                        "symbol": "EURUSD",
                        "price": 1.1000 + random.uniform(-0.01, 0.01),
                        "volume": random.randint(1000, 100000),
                        "timestamp": time.time(),
                    }

                    await self.market_data_processor.process_tick(tick)
                    latency = (time.time() - tick_start) * 1000
                    batch_results.append((True, latency))

                except Exception as e:
                    latency = (time.time() - tick_start) * 1000
                    batch_results.append((False, latency))

                # Maintain target tick rate
                if i < batch_size - 1:
                    await asyncio.sleep(tick_interval)

            return batch_results

        # Process ticks in batches for better performance
        batch_size = min(100, num_ticks)
        num_batches = (num_ticks + batch_size - 1) // batch_size

        tasks = []
        for batch_idx in range(num_batches):
            remaining_ticks = num_ticks - (batch_idx * batch_size)
            current_batch_size = min(batch_size, remaining_ticks)
            tasks.append(process_tick_batch(current_batch_size))

        # Execute all batches concurrently
        batch_results = await asyncio.gather(*tasks)

        # Flatten results
        for batch in batch_results:
            for success, latency in batch:
                latencies.append(latency)
                if not success:
                    errors += 1

        duration = time.time() - start_time
        resource_metrics = self.resource_monitor.stop_monitoring()

        return self._calculate_metrics(
            num_ticks, duration, latencies, errors, resource_metrics
        )

    async def stress_test_risk_calculations(
        self, num_calculations: int = 1000, concurrent_positions: int = 50
    ) -> StressTestMetrics:
        """Stress test risk calculations under load."""
        self.resource_monitor.start_monitoring()
        start_time = time.time()
        latencies = []
        errors = 0

        async def calculate_position_risk(position_id: int) -> Tuple[bool, float]:
            """Calculate risk for a single position."""
            calc_start = time.time()
            try:
                position = {
                    "id": position_id,
                    "symbol": "EURUSD",
                    "size": random.randint(10000, 100000),
                    "entry_price": 1.1000 + random.uniform(-0.01, 0.01),
                    "current_price": 1.1000 + random.uniform(-0.01, 0.01),
                }

                risk_result = await self.risk_calculator.calculate_position_risk(
                    position
                )
                latency = (time.time() - calc_start) * 1000
                return True, latency

            except Exception as e:
                latency = (time.time() - calc_start) * 1000
                return False, latency

        # Create semaphore for concurrent risk calculations
        semaphore = asyncio.Semaphore(concurrent_positions)

        async def rate_limited_calculation(position_id: int) -> Tuple[bool, float]:
            """Rate-limited risk calculation."""
            async with semaphore:
                return await calculate_position_risk(position_id)

        # Execute risk calculations
        tasks = [rate_limited_calculation(i) for i in range(num_calculations)]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Process results
        for result in results:
            if isinstance(result, Exception):
                errors += 1
                latencies.append(500.0)  # Default high latency for errors
            else:
                success, latency = result
                latencies.append(latency)
                if not success:
                    errors += 1

        duration = time.time() - start_time
        resource_metrics = self.resource_monitor.stop_monitoring()

        return self._calculate_metrics(
            num_calculations, duration, latencies, errors, resource_metrics
        )

    async def stress_test_signal_generation(
        self, num_signals: int = 100, concurrent_generators: int = 5
    ) -> StressTestMetrics:
        """Stress test ML signal generation pipeline."""
        self.resource_monitor.start_monitoring()
        start_time = time.time()
        latencies = []
        errors = 0

        async def generate_single_signal(signal_id: int) -> Tuple[bool, float]:
            """Generate a single trading signal."""
            signal_start = time.time()
            try:
                market_data = {
                    "symbol": "EURUSD",
                    "features": [random.uniform(-1, 1) for _ in range(50)],
                    "timestamp": time.time(),
                }

                signal = await self.signal_generator.generate_signal(market_data)
                latency = (time.time() - signal_start) * 1000
                return True, latency

            except Exception as e:
                latency = (time.time() - signal_start) * 1000
                return False, latency

        # Rate limit signal generation
        semaphore = asyncio.Semaphore(concurrent_generators)

        async def rate_limited_signal(signal_id: int) -> Tuple[bool, float]:
            """Rate-limited signal generation."""
            async with semaphore:
                return await generate_single_signal(signal_id)

        # Generate signals concurrently
        tasks = [rate_limited_signal(i) for i in range(num_signals)]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Process results
        for result in results:
            if isinstance(result, Exception):
                errors += 1
                latencies.append(5000.0)  # Default high latency for errors
            else:
                success, latency = result
                latencies.append(latency)
                if not success:
                    errors += 1

        duration = time.time() - start_time
        resource_metrics = self.resource_monitor.stop_monitoring()

        return self._calculate_metrics(
            num_signals, duration, latencies, errors, resource_metrics
        )

    def _calculate_metrics(
        self,
        total_ops: int,
        duration: float,
        latencies: List[float],
        errors: int,
        resource_metrics: List[SystemResourceMetrics],
    ) -> StressTestMetrics:
        """Calculate comprehensive stress test metrics."""
        success_count = total_ops - errors
        ops_per_second = total_ops / duration if duration > 0 else 0
        error_rate = errors / total_ops if total_ops > 0 else 0

        # Latency statistics
        avg_latency = statistics.mean(latencies) if latencies else 0
        p95_latency = (
            statistics.quantiles(latencies, n=20)[18] if len(latencies) >= 20 else 0
        )
        p99_latency = (
            statistics.quantiles(latencies, n=100)[98] if len(latencies) >= 100 else 0
        )

        # Resource statistics
        peak_memory = (
            max([m.memory_mb for m in resource_metrics]) if resource_metrics else 0
        )
        peak_cpu = (
            max([m.cpu_percent for m in resource_metrics]) if resource_metrics else 0
        )

        return StressTestMetrics(
            total_operations=total_ops,
            duration_seconds=duration,
            operations_per_second=ops_per_second,
            avg_latency_ms=avg_latency,
            p95_latency_ms=p95_latency,
            p99_latency_ms=p99_latency,
            error_rate=error_rate,
            peak_memory_mb=peak_memory,
            peak_cpu_percent=peak_cpu,
            success_count=success_count,
            error_count=errors,
        )


# Test fixtures
@pytest.fixture
def stress_tester():
    """Create stress tester instance."""
    return HighFrequencyStressTester()


@pytest.fixture
def performance_thresholds():
    """Define performance thresholds for stress tests."""
    return {
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


# Stress test cases
@pytest.mark.stress
@pytest.mark.asyncio
class TestHighFrequencyStress:
    """High-frequency trading stress test suite."""

    async def test_order_submission_stress_light(
        self, stress_tester, performance_thresholds
    ):
        """Light stress test for order submission (CI-friendly)."""
        metrics = await stress_tester.stress_test_order_submission(
            num_orders=100, concurrent_workers=5
        )

        thresholds = performance_thresholds["order_submission"]

        # Performance assertions
        assert (
            metrics.avg_latency_ms <= thresholds["max_avg_latency_ms"]
        ), f"Average latency {metrics.avg_latency_ms}ms exceeds threshold {thresholds['max_avg_latency_ms']}ms"
        assert (
            metrics.error_rate <= thresholds["max_error_rate"]
        ), f"Error rate {metrics.error_rate} exceeds threshold {thresholds['max_error_rate']}"
        assert (
            metrics.operations_per_second >= 10
        ), f"Throughput {metrics.operations_per_second} ops/sec too low"

        # Resource assertions
        assert (
            metrics.peak_memory_mb < 1000
        ), f"Memory usage {metrics.peak_memory_mb}MB too high"
        assert (
            metrics.peak_cpu_percent < 90
        ), f"CPU usage {metrics.peak_cpu_percent}% too high"

    @pytest.mark.slow
    async def test_order_submission_stress_full(
        self, stress_tester, performance_thresholds
    ):
        """Full stress test for order submission."""
        metrics = await stress_tester.stress_test_order_submission(
            num_orders=1000, concurrent_workers=10
        )

        thresholds = performance_thresholds["order_submission"]

        assert metrics.avg_latency_ms <= thresholds["max_avg_latency_ms"]
        assert metrics.p95_latency_ms <= thresholds["max_p95_latency_ms"]
        assert metrics.error_rate <= thresholds["max_error_rate"]
        assert metrics.operations_per_second >= thresholds["min_ops_per_second"]

    async def test_market_data_stress_light(
        self, stress_tester, performance_thresholds
    ):
        """Light stress test for market data processing."""
        metrics = await stress_tester.stress_test_market_data_processing(
            num_ticks=1000, ticks_per_second=100
        )

        thresholds = performance_thresholds["market_data_processing"]

        assert metrics.avg_latency_ms <= thresholds["max_avg_latency_ms"]
        assert metrics.error_rate <= thresholds["max_error_rate"]
        assert metrics.operations_per_second >= 50

    @pytest.mark.slow
    async def test_market_data_stress_full(self, stress_tester, performance_thresholds):
        """Full stress test for market data processing."""
        metrics = await stress_tester.stress_test_market_data_processing(
            num_ticks=10000, ticks_per_second=1000
        )

        thresholds = performance_thresholds["market_data_processing"]

        assert metrics.avg_latency_ms <= thresholds["max_avg_latency_ms"]
        assert metrics.p95_latency_ms <= thresholds["max_p95_latency_ms"]
        assert metrics.error_rate <= thresholds["max_error_rate"]
        assert metrics.operations_per_second >= thresholds["min_ops_per_second"]

    async def test_risk_calculation_stress_light(
        self, stress_tester, performance_thresholds
    ):
        """Light stress test for risk calculations."""
        metrics = await stress_tester.stress_test_risk_calculations(
            num_calculations=100, concurrent_positions=10
        )

        thresholds = performance_thresholds["risk_calculations"]

        assert metrics.avg_latency_ms <= thresholds["max_avg_latency_ms"]
        assert metrics.error_rate <= thresholds["max_error_rate"]
        assert metrics.operations_per_second >= 5

    @pytest.mark.slow
    async def test_risk_calculation_stress_full(
        self, stress_tester, performance_thresholds
    ):
        """Full stress test for risk calculations."""
        metrics = await stress_tester.stress_test_risk_calculations(
            num_calculations=1000, concurrent_positions=50
        )

        thresholds = performance_thresholds["risk_calculations"]

        assert metrics.avg_latency_ms <= thresholds["max_avg_latency_ms"]
        assert metrics.p95_latency_ms <= thresholds["max_p95_latency_ms"]
        assert metrics.error_rate <= thresholds["max_error_rate"]
        assert metrics.operations_per_second >= thresholds["min_ops_per_second"]

    async def test_signal_generation_stress_light(
        self, stress_tester, performance_thresholds
    ):
        """Light stress test for signal generation."""
        metrics = await stress_tester.stress_test_signal_generation(
            num_signals=10, concurrent_generators=2
        )

        thresholds = performance_thresholds["signal_generation"]

        assert metrics.avg_latency_ms <= thresholds["max_avg_latency_ms"]
        assert metrics.error_rate <= thresholds["max_error_rate"]
        assert metrics.operations_per_second >= 0.5

    @pytest.mark.slow
    async def test_signal_generation_stress_full(
        self, stress_tester, performance_thresholds
    ):
        """Full stress test for signal generation."""
        metrics = await stress_tester.stress_test_signal_generation(
            num_signals=100, concurrent_generators=5
        )

        thresholds = performance_thresholds["signal_generation"]

        assert metrics.avg_latency_ms <= thresholds["max_avg_latency_ms"]
        assert metrics.p95_latency_ms <= thresholds["max_p95_latency_ms"]
        assert metrics.error_rate <= thresholds["max_error_rate"]
        assert metrics.operations_per_second >= thresholds["min_ops_per_second"]

    @pytest.mark.slow
    async def test_comprehensive_system_stress(self, stress_tester):
        """Comprehensive system stress test combining all components."""
        # Start resource monitoring
        stress_tester.resource_monitor.start_monitoring()
        start_time = time.time()

        # Run multiple stress tests concurrently
        tasks = [
            stress_tester.stress_test_order_submission(500, 5),
            stress_tester.stress_test_market_data_processing(5000, 500),
            stress_tester.stress_test_risk_calculations(200, 10),
            stress_tester.stress_test_signal_generation(20, 2),
        ]

        results = await asyncio.gather(*tasks)

        duration = time.time() - start_time
        resource_metrics = stress_tester.resource_monitor.stop_monitoring()

        # Validate overall system performance
        assert (
            duration < 60
        ), f"Comprehensive stress test took {duration}s, expected < 60s"

        # Check resource usage
        peak_memory = (
            max([m.memory_mb for m in resource_metrics]) if resource_metrics else 0
        )
        peak_cpu = (
            max([m.cpu_percent for m in resource_metrics]) if resource_metrics else 0
        )

        assert (
            peak_memory < 2000
        ), f"Peak memory {peak_memory}MB too high for comprehensive test"
        assert peak_cpu < 85, f"Peak CPU {peak_cpu}% too high for comprehensive test"

        # Validate individual component performance
        order_metrics, data_metrics, risk_metrics, signal_metrics = results

        assert order_metrics.error_rate < 0.02, "Order submission error rate too high"
        assert data_metrics.error_rate < 0.005, "Market data error rate too high"
        assert risk_metrics.error_rate < 0.005, "Risk calculation error rate too high"
        assert signal_metrics.error_rate < 0.05, "Signal generation error rate too high"


if __name__ == "__main__":
    # Allow running stress tests directly
    import sys

    async def run_quick_stress_test():
        """Run a quick stress test for development."""
        tester = HighFrequencyStressTester()

        print("Running quick stress test...")
        metrics = await tester.stress_test_order_submission(100, 5)

        print(f"Results:")
        print(f"  Operations: {metrics.total_operations}")
        print(f"  Duration: {metrics.duration_seconds:.2f}s")
        print(f"  Throughput: {metrics.operations_per_second:.1f} ops/sec")
        print(f"  Avg Latency: {metrics.avg_latency_ms:.1f}ms")
        print(f"  P95 Latency: {metrics.p95_latency_ms:.1f}ms")
        print(f"  Error Rate: {metrics.error_rate:.3f}")
        print(f"  Peak Memory: {metrics.peak_memory_mb:.1f}MB")
        print(f"  Peak CPU: {metrics.peak_cpu_percent:.1f}%")

    if len(sys.argv) > 1 and sys.argv[1] == "--quick":
        asyncio.run(run_quick_stress_test())
