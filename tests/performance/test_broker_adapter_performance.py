"""Performance Benchmarking Tests for Broker Adapter Infrastructure.

This module provides comprehensive performance testing for the broker adapter
infrastructure, measuring latency, throughput, resource usage, and scalability
under various load conditions.
"""

import asyncio
import statistics
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Tuple
from unittest.mock import AsyncMock, MagicMock, patch

import psutil
import pytest

from fxml4.brokers.adapters.base import AdapterConfig, ConnectionStatus
from fxml4.brokers.adapters.fix_rabbitmq_adapter import FixRabbitMQAdapter
from fxml4.brokers.adapters.fxcm_rabbitmq_adapter import FXCMRabbitMQAdapter
from fxml4.brokers.adapters.ib_rabbitmq_adapter import IBRabbitMQAdapter
from fxml4.brokers.adapters.manager import BrokerAdapterManager
from fxml4.fix.messages.base import ExecType, OrdStatus, OrdType, Side
from fxml4.fix.messages.orders import ExecutionReport, NewOrderSingle


@dataclass
class PerformanceMetrics:
    """Performance measurement results."""

    latency_ms: float
    throughput_ops_sec: float
    memory_usage_mb: float
    cpu_usage_percent: float
    success_rate: float
    error_count: int
    total_operations: int
    duration_seconds: float


@dataclass
class LoadTestConfig:
    """Load test configuration."""

    concurrent_users: int
    operations_per_user: int
    ramp_up_seconds: int
    test_duration_seconds: int
    target_throughput: int
    order_size_range: Tuple[int, int]


class PerformanceBenchmark:
    """Performance benchmarking utility."""

    def __init__(self):
        self.process = psutil.Process()
        self.start_time = None
        self.start_memory = None
        self.start_cpu = None

    def start_monitoring(self):
        """Start performance monitoring."""
        self.start_time = time.time()
        self.start_memory = self.process.memory_info().rss / 1024 / 1024  # MB
        self.start_cpu = self.process.cpu_percent()

    def get_metrics(
        self, total_operations: int, error_count: int
    ) -> PerformanceMetrics:
        """Get current performance metrics."""
        end_time = time.time()
        duration = end_time - self.start_time
        end_memory = self.process.memory_info().rss / 1024 / 1024  # MB
        end_cpu = self.process.cpu_percent()

        return PerformanceMetrics(
            latency_ms=0.0,  # Will be calculated separately
            throughput_ops_sec=total_operations / duration if duration > 0 else 0,
            memory_usage_mb=end_memory - self.start_memory,
            cpu_usage_percent=end_cpu,
            success_rate=(
                (total_operations - error_count) / total_operations * 100
                if total_operations > 0
                else 0
            ),
            error_count=error_count,
            total_operations=total_operations,
            duration_seconds=duration,
        )


@pytest.fixture
def performance_config():
    """Create performance test configuration."""
    return AdapterConfig(
        adapter_type="ib",
        connection_params={
            "host": "localhost",
            "port": 7497,
            "client_id": 100,
            "features": {
                "mock_mode": True,
                "fast_execution": True,
                "batch_processing": True,
            },
        },
    )


@pytest.fixture
async def mock_fast_adapter(performance_config):
    """Create mock adapter optimized for performance testing."""
    with patch(
        "fxml4.brokers.adapters.rabbitmq_base.create_rabbitmq_manager"
    ) as mock_manager:
        mock_rabbitmq = AsyncMock()
        mock_rabbitmq.connected = True
        mock_rabbitmq.connect.return_value = True
        mock_rabbitmq.publish_order_event.return_value = True
        mock_manager.return_value = mock_rabbitmq

        adapter = IBRabbitMQAdapter(performance_config)

        # Mock for fast execution
        adapter.submit_order = AsyncMock(
            side_effect=lambda order: f"PERF_{order.cl_ord_id}_{int(time.time() * 1000000)}"
        )
        adapter.cancel_order = AsyncMock(return_value=True)
        adapter.get_order_status = AsyncMock(return_value={"status": "NEW"})

        # Simulate network latency
        async def add_latency(original_func):
            async def wrapper(*args, **kwargs):
                await asyncio.sleep(0.001)  # 1ms simulated latency
                return await original_func(*args, **kwargs)

            return wrapper

        adapter.submit_order = add_latency(adapter.submit_order)

        await adapter.connect()
        return adapter


def generate_test_orders(
    count: int, size_range: Tuple[int, int] = (10000, 100000)
) -> List[NewOrderSingle]:
    """Generate test orders for performance testing."""
    orders = []
    symbols = ["EUR/USD", "GBP/USD", "USD/JPY", "AUD/USD", "USD/CHF"]

    for i in range(count):
        orders.append(
            NewOrderSingle(
                cl_ord_id=f"PERF_ORDER_{i:06d}",
                symbol=symbols[i % len(symbols)],
                side=Side.BUY if i % 2 == 0 else Side.SELL,
                order_qty=size_range[0] + (i % (size_range[1] - size_range[0])),
                ord_type=OrdType.MARKET if i % 3 == 0 else OrdType.LIMIT,
                price=1.0000 + (i * 0.0001) if i % 3 != 0 else None,
            )
        )

    return orders


class TestBrokerAdapterPerformance:
    """Performance tests for broker adapter infrastructure."""

    @pytest.mark.asyncio
    @pytest.mark.performance
    async def test_single_adapter_latency(self, mock_fast_adapter):
        """Test single order latency for individual adapter."""
        benchmark = PerformanceBenchmark()
        latencies = []

        # Test single order latency
        test_orders = generate_test_orders(100)

        for order in test_orders:
            start_time = time.time()
            execution_id = await mock_fast_adapter.submit_order(order)
            end_time = time.time()

            latency_ms = (end_time - start_time) * 1000
            latencies.append(latency_ms)
            assert execution_id.startswith("PERF_")

        # Analyze latency statistics
        avg_latency = statistics.mean(latencies)
        p95_latency = statistics.quantiles(latencies, n=20)[18]  # 95th percentile
        p99_latency = statistics.quantiles(latencies, n=100)[98]  # 99th percentile

        print(f"\nLatency Statistics:")
        print(f"Average: {avg_latency:.2f}ms")
        print(f"95th percentile: {p95_latency:.2f}ms")
        print(f"99th percentile: {p99_latency:.2f}ms")

        # Performance assertions
        assert avg_latency < 10.0  # Average latency under 10ms
        assert p95_latency < 20.0  # 95th percentile under 20ms
        assert p99_latency < 50.0  # 99th percentile under 50ms

    @pytest.mark.asyncio
    @pytest.mark.performance
    async def test_concurrent_order_throughput(self, mock_fast_adapter):
        """Test concurrent order processing throughput."""
        benchmark = PerformanceBenchmark()
        benchmark.start_monitoring()

        concurrent_orders = 1000
        concurrent_batches = 10
        batch_size = concurrent_orders // concurrent_batches

        test_orders = generate_test_orders(concurrent_orders)
        error_count = 0

        async def process_batch(orders_batch):
            """Process a batch of orders concurrently."""
            tasks = [mock_fast_adapter.submit_order(order) for order in orders_batch]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            batch_errors = sum(1 for result in results if isinstance(result, Exception))
            return batch_errors

        # Process orders in batches
        batch_tasks = []
        for i in range(concurrent_batches):
            start_idx = i * batch_size
            end_idx = start_idx + batch_size
            batch_orders = test_orders[start_idx:end_idx]
            batch_tasks.append(process_batch(batch_orders))

        batch_results = await asyncio.gather(*batch_tasks)
        error_count = sum(batch_results)

        metrics = benchmark.get_metrics(concurrent_orders, error_count)

        print(f"\nThroughput Test Results:")
        print(f"Total orders: {metrics.total_operations}")
        print(f"Duration: {metrics.duration_seconds:.2f}s")
        print(f"Throughput: {metrics.throughput_ops_sec:.0f} orders/sec")
        print(f"Success rate: {metrics.success_rate:.1f}%")
        print(f"Memory usage: {metrics.memory_usage_mb:.1f}MB")
        print(f"CPU usage: {metrics.cpu_usage_percent:.1f}%")

        # Performance assertions
        assert metrics.throughput_ops_sec > 500  # At least 500 orders/sec
        assert metrics.success_rate > 99.0  # 99%+ success rate
        assert metrics.memory_usage_mb < 100  # Memory usage under 100MB

    @pytest.mark.asyncio
    @pytest.mark.performance
    async def test_sustained_load_performance(self, mock_fast_adapter):
        """Test sustained load performance over time."""
        benchmark = PerformanceBenchmark()
        benchmark.start_monitoring()

        test_duration = 30  # 30 seconds
        target_rate = 100  # 100 orders/sec
        interval = 1.0 / target_rate

        total_orders = 0
        error_count = 0
        start_time = time.time()

        while time.time() - start_time < test_duration:
            order = NewOrderSingle(
                cl_ord_id=f"SUSTAINED_{total_orders:06d}",
                symbol="EUR/USD",
                side=Side.BUY,
                order_qty=100000,
                ord_type=OrdType.MARKET,
            )

            try:
                await mock_fast_adapter.submit_order(order)
                total_orders += 1
            except Exception:
                error_count += 1

            # Rate limiting
            await asyncio.sleep(interval)

        metrics = benchmark.get_metrics(total_orders, error_count)

        print(f"\nSustained Load Test Results:")
        print(f"Test duration: {test_duration}s")
        print(f"Target rate: {target_rate} orders/sec")
        print(f"Actual rate: {metrics.throughput_ops_sec:.1f} orders/sec")
        print(f"Success rate: {metrics.success_rate:.1f}%")

        # Performance assertions
        assert metrics.throughput_ops_sec >= target_rate * 0.95  # Within 5% of target
        assert metrics.success_rate > 99.0

    @pytest.mark.asyncio
    @pytest.mark.performance
    async def test_memory_usage_under_load(self, mock_fast_adapter):
        """Test memory usage patterns under various loads."""
        process = psutil.Process()
        memory_samples = []

        # Baseline memory
        baseline_memory = process.memory_info().rss / 1024 / 1024
        memory_samples.append(baseline_memory)

        # Progressive load test
        load_levels = [100, 500, 1000, 2000]

        for load_level in load_levels:
            orders = generate_test_orders(load_level)

            # Submit orders
            tasks = [mock_fast_adapter.submit_order(order) for order in orders]
            await asyncio.gather(*tasks, return_exceptions=True)

            # Measure memory
            current_memory = process.memory_info().rss / 1024 / 1024
            memory_samples.append(current_memory)

            print(f"Load level {load_level}: {current_memory:.1f}MB")

            # Allow garbage collection
            await asyncio.sleep(0.1)

        # Analyze memory growth
        max_memory = max(memory_samples)
        memory_growth = max_memory - baseline_memory

        print(f"\nMemory Usage Analysis:")
        print(f"Baseline: {baseline_memory:.1f}MB")
        print(f"Peak: {max_memory:.1f}MB")
        print(f"Growth: {memory_growth:.1f}MB")

        # Memory assertions
        assert memory_growth < 200  # Memory growth under 200MB
        assert max_memory < 500  # Peak memory under 500MB

    @pytest.mark.asyncio
    @pytest.mark.performance
    async def test_multi_adapter_performance(self, performance_config):
        """Test performance with multiple adapters running concurrently."""
        with patch(
            "fxml4.brokers.adapters.rabbitmq_base.create_rabbitmq_manager"
        ) as mock_manager:
            mock_rabbitmq = AsyncMock()
            mock_rabbitmq.connected = True
            mock_rabbitmq.connect.return_value = True
            mock_manager.return_value = mock_rabbitmq

            # Create multiple adapters
            adapters = []
            for i in range(4):
                config = AdapterConfig(
                    adapter_type=f"test_{i}",
                    connection_params=performance_config.connection_params,
                )
                adapter = IBRabbitMQAdapter(config)
                adapter.submit_order = AsyncMock(
                    side_effect=lambda order: f"MULTI_{i}_{order.cl_ord_id}"
                )
                await adapter.connect()
                adapters.append(adapter)

            benchmark = PerformanceBenchmark()
            benchmark.start_monitoring()

            # Distribute orders across adapters
            total_orders = 1000
            orders_per_adapter = total_orders // len(adapters)

            async def adapter_workload(adapter, adapter_id):
                """Workload for a single adapter."""
                orders = generate_test_orders(orders_per_adapter)
                tasks = [adapter.submit_order(order) for order in orders]
                results = await asyncio.gather(*tasks, return_exceptions=True)
                errors = sum(1 for result in results if isinstance(result, Exception))
                return len(results), errors

            # Run workloads concurrently
            adapter_tasks = [
                adapter_workload(adapter, i) for i, adapter in enumerate(adapters)
            ]

            results = await asyncio.gather(*adapter_tasks)

            total_processed = sum(result[0] for result in results)
            total_errors = sum(result[1] for result in results)

            metrics = benchmark.get_metrics(total_processed, total_errors)

            print(f"\nMulti-Adapter Performance:")
            print(f"Adapters: {len(adapters)}")
            print(f"Total throughput: {metrics.throughput_ops_sec:.0f} orders/sec")
            print(
                f"Per-adapter avg: {metrics.throughput_ops_sec/len(adapters):.0f} orders/sec"
            )
            print(f"Success rate: {metrics.success_rate:.1f}%")

            # Performance assertions
            assert metrics.throughput_ops_sec > 1000  # Combined throughput
            assert metrics.success_rate > 99.0


class TestScalabilityBenchmarks:
    """Scalability and stress testing."""

    @pytest.mark.asyncio
    @pytest.mark.performance
    @pytest.mark.stress
    async def test_order_volume_scalability(self, mock_fast_adapter):
        """Test scalability with increasing order volumes."""
        volume_levels = [100, 500, 1000, 2500, 5000]
        performance_results = []

        for volume in volume_levels:
            benchmark = PerformanceBenchmark()
            benchmark.start_monitoring()

            orders = generate_test_orders(volume)

            # Submit orders in batches to avoid overwhelming the system
            batch_size = 100
            error_count = 0

            for i in range(0, len(orders), batch_size):
                batch = orders[i : i + batch_size]
                tasks = [mock_fast_adapter.submit_order(order) for order in batch]
                results = await asyncio.gather(*tasks, return_exceptions=True)
                error_count += sum(
                    1 for result in results if isinstance(result, Exception)
                )

            metrics = benchmark.get_metrics(volume, error_count)
            performance_results.append((volume, metrics))

            print(
                f"Volume {volume}: {metrics.throughput_ops_sec:.0f} ops/sec, "
                f"{metrics.success_rate:.1f}% success"
            )

        # Analyze scalability
        throughputs = [result[1].throughput_ops_sec for result in performance_results]

        # Check if throughput scales reasonably
        min_throughput = min(throughputs)
        max_throughput = max(throughputs)

        assert (
            max_throughput > min_throughput * 0.8
        )  # Performance shouldn't degrade too much

    @pytest.mark.asyncio
    @pytest.mark.performance
    @pytest.mark.stress
    async def test_connection_pool_stress(self, performance_config):
        """Test connection pooling under stress."""
        with patch(
            "fxml4.brokers.adapters.rabbitmq_base.create_rabbitmq_manager"
        ) as mock_manager:
            mock_rabbitmq = AsyncMock()
            mock_rabbitmq.connected = True
            mock_manager.return_value = mock_rabbitmq

            # Create many adapters to stress connection pooling
            num_adapters = 20
            adapters = []

            for i in range(num_adapters):
                adapter = IBRabbitMQAdapter(performance_config)
                adapter.submit_order = AsyncMock(return_value=f"POOL_{i}")
                adapters.append(adapter)

            # Connect all adapters simultaneously
            connect_tasks = [adapter.connect() for adapter in adapters]
            connect_results = await asyncio.gather(
                *connect_tasks, return_exceptions=True
            )

            successful_connections = sum(
                1 for result in connect_results if result is True
            )

            print(f"\nConnection Pool Stress Test:")
            print(f"Attempted connections: {num_adapters}")
            print(f"Successful connections: {successful_connections}")
            print(f"Success rate: {successful_connections/num_adapters*100:.1f}%")

            # All connections should succeed
            assert successful_connections >= num_adapters * 0.95  # 95% success rate

    @pytest.mark.asyncio
    @pytest.mark.performance
    async def test_error_handling_performance(self, mock_fast_adapter):
        """Test performance impact of error handling."""
        benchmark = PerformanceBenchmark()
        benchmark.start_monitoring()

        # Mix of successful and failing orders
        total_orders = 1000
        error_rate = 0.1  # 10% error rate

        success_count = 0
        error_count = 0

        for i in range(total_orders):
            order = NewOrderSingle(
                cl_ord_id=f"ERROR_TEST_{i:06d}",
                symbol="EUR/USD",
                side=Side.BUY,
                order_qty=100000,
                ord_type=OrdType.MARKET,
            )

            # Simulate errors
            if i % int(1 / error_rate) == 0:
                mock_fast_adapter.submit_order.side_effect = Exception(
                    "Simulated error"
                )
                try:
                    await mock_fast_adapter.submit_order(order)
                except Exception:
                    error_count += 1
                # Reset to success
                mock_fast_adapter.submit_order.side_effect = None
                mock_fast_adapter.submit_order.return_value = f"SUCCESS_{i}"
            else:
                await mock_fast_adapter.submit_order(order)
                success_count += 1

        metrics = benchmark.get_metrics(total_orders, error_count)

        print(f"\nError Handling Performance:")
        print(f"Total orders: {total_orders}")
        print(f"Errors: {error_count}")
        print(f"Success rate: {metrics.success_rate:.1f}%")
        print(f"Throughput: {metrics.throughput_ops_sec:.0f} orders/sec")

        # Performance should remain reasonable even with errors
        assert metrics.throughput_ops_sec > 200  # Still decent throughput
        assert abs(metrics.success_rate - 90.0) < 5.0  # Close to expected error rate


class TestResourceUtilizationBenchmarks:
    """Resource utilization and efficiency tests."""

    @pytest.mark.asyncio
    @pytest.mark.performance
    async def test_cpu_utilization_efficiency(self, mock_fast_adapter):
        """Test CPU utilization efficiency."""
        # Monitor CPU usage during load
        process = psutil.Process()
        cpu_samples = []

        # Background CPU monitoring
        async def monitor_cpu():
            for _ in range(10):  # 10 samples over test duration
                cpu_percent = process.cpu_percent(interval=0.1)
                cpu_samples.append(cpu_percent)
                await asyncio.sleep(0.5)

        # Order processing workload
        async def order_workload():
            orders = generate_test_orders(1000)
            tasks = [mock_fast_adapter.submit_order(order) for order in orders]
            await asyncio.gather(*tasks, return_exceptions=True)

        # Run monitoring and workload concurrently
        monitor_task = asyncio.create_task(monitor_cpu())
        workload_task = asyncio.create_task(order_workload())

        await asyncio.gather(monitor_task, workload_task)

        avg_cpu = statistics.mean(cpu_samples) if cpu_samples else 0
        max_cpu = max(cpu_samples) if cpu_samples else 0

        print(f"\nCPU Utilization:")
        print(f"Average: {avg_cpu:.1f}%")
        print(f"Peak: {max_cpu:.1f}%")

        # CPU usage should be reasonable
        assert avg_cpu < 80.0  # Average CPU under 80%
        assert max_cpu < 95.0  # Peak CPU under 95%

    @pytest.mark.asyncio
    @pytest.mark.performance
    async def test_gc_impact_measurement(self, mock_fast_adapter):
        """Test garbage collection impact on performance."""
        import gc

        # Disable automatic GC
        gc.disable()

        try:
            # Create many objects
            orders = generate_test_orders(2000)

            # Process without GC
            start_time = time.time()
            tasks = [mock_fast_adapter.submit_order(order) for order in orders]
            await asyncio.gather(*tasks, return_exceptions=True)
            no_gc_duration = time.time() - start_time

            # Force GC and measure time
            gc_start = time.time()
            gc.collect()
            gc_duration = time.time() - gc_start

            print(f"\nGC Impact Analysis:")
            print(f"Processing time (no GC): {no_gc_duration:.3f}s")
            print(f"GC time: {gc_duration:.3f}s")
            print(f"GC overhead: {gc_duration/no_gc_duration*100:.1f}%")

            # GC overhead should be minimal
            assert gc_duration / no_gc_duration < 0.1  # GC < 10% of processing time

        finally:
            gc.enable()


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-m", "performance"])
