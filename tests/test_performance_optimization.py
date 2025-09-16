"""
Phase 11 TDD Test Suite: Performance Optimization & Scaling

Comprehensive test coverage for high-frequency trading performance optimizations:
- HFT engine components with sub-millisecond requirements
- Horizontal scaling architecture validation
- Multi-level caching performance verification
- Load balancing and auto-scaling functionality
- Real-time data processing pipeline testing
"""

import asyncio
import random
import threading
import time
from typing import Any, Dict, List
from unittest.mock import MagicMock, Mock, patch

import pytest

# Caching imports
from fxml4.caching.multilevel_cache import LRUCache, MultiLevelCache, RedisCache

# Performance optimization imports
from fxml4.performance.hft_engine import (
    HighFrequencyTradingEngine,
    MemoryMappedMarketData,
    OrderExecutionEngine,
)
from fxml4.performance.latency_monitor import LatencyMonitor, MicrosecondTimer
from fxml4.performance.lockfree_queue import LockFreeQueue, MPMCQueue, SPSCQueue
from fxml4.performance.memory_pool import AlignedMemoryAllocator, MemoryPool, RingBuffer
from fxml4.performance.zero_copy_io import MemoryMappedBuffer, ZeroCopyBuffer
from fxml4.scaling.auto_scaler import (
    AutoScaler,
    ScalingMetrics,
    ScalingPolicy,
    ScalingRule,
    ScalingTrigger,
)

# Scaling imports
from fxml4.scaling.cluster_manager import ClusterManager, NodeInfo, NodeStatus, NodeType
from fxml4.scaling.load_balancer import LatencyAwareLoadBalancer, LoadBalancingStrategy
from fxml4.scaling.node_discovery import (
    HealthCheckConfig,
    HealthChecker,
    HealthCheckType,
    NodeDiscovery,
)

# Streaming imports
from fxml4.streaming.tick_processor import TickData, TickProcessor, TickType

# Performance testing imports
from tests.performance.load_testing_framework import (
    LoadTestConfig,
    LoadTestFramework,
    LoadTestType,
)


class TestHFTEngineComponents:
    """Test high-frequency trading engine components"""

    @pytest.fixture
    def hft_engine(self):
        """Create HFT engine instance"""
        return HighFrequencyTradingEngine()

    @pytest.fixture
    def memory_mapped_data(self):
        """Create memory-mapped market data instance"""
        return MemoryMappedMarketData(max_ticks=1000)

    def test_memory_mapped_market_data_creation(self, memory_mapped_data):
        """Test memory-mapped market data initialization"""
        # Given: A memory-mapped market data instance
        # When: Initialized
        # Then: Should be properly configured
        assert memory_mapped_data.max_ticks == 1000
        assert memory_mapped_data.buffer is not None
        assert memory_mapped_data.write_index == 0
        assert memory_mapped_data.read_index == 0

    def test_memory_mapped_tick_writing_and_reading(self, memory_mapped_data):
        """Test zero-copy tick writing and reading"""
        # Given: Memory-mapped market data
        symbol = "EURUSD"
        bid = 1.1000
        ask = 1.1001

        # When: Writing a tick
        success = memory_mapped_data.write_tick(symbol, bid, ask, 1000000, 1000000)

        # Then: Should write successfully
        assert success is True
        assert memory_mapped_data.write_index == 1

        # When: Reading the tick
        tick = memory_mapped_data.read_tick(0)

        # Then: Should read correctly
        assert tick is not None
        assert tick.bid == bid
        assert tick.ask == ask
        assert memory_mapped_data.id_to_symbol[tick.symbol_id] == symbol

    def test_order_execution_engine_performance(self):
        """Test order execution engine performance requirements"""
        # Given: An order execution engine
        latency_monitor = LatencyMonitor()
        engine = OrderExecutionEngine(latency_monitor)

        # When: Submitting multiple orders rapidly
        start_time = time.time()
        order_ids = []

        for i in range(1000):
            order_id = engine.submit_order("EURUSD", "BUY", 10000, 1.1000 + i * 0.0001)
            order_ids.append(order_id)

        submission_time = time.time() - start_time

        # Then: Should achieve high throughput
        submission_rate = 1000 / submission_time
        assert submission_rate > 10000  # >10K orders/second

        # When: Processing orders
        start_time = time.time()
        processed = engine.process_orders()
        processing_time = time.time() - start_time

        # Then: Should process efficiently
        assert processed > 0
        processing_rate = (
            processed / processing_time if processing_time > 0 else float("inf")
        )
        assert processing_rate > 5000  # >5K orders/second processing

    def test_hft_engine_latency_requirements(self, hft_engine):
        """Test HFT engine meets latency requirements"""
        # Given: HFT engine is started
        asyncio.run(hft_engine.start())

        try:
            # When: Processing market ticks
            latencies = []
            for i in range(100):
                start_time = time.time_ns()
                success = hft_engine.process_market_tick(
                    "EURUSD", 1.1000 + i * 0.0001, 1.1001 + i * 0.0001, 1000000, 1000000
                )
                latency_ns = time.time_ns() - start_time
                latencies.append(latency_ns)
                assert success is True

            # Then: Should meet sub-millisecond requirements
            avg_latency_ns = sum(latencies) / len(latencies)
            max_latency_ns = max(latencies)

            assert avg_latency_ns < 100_000  # <100 microseconds average
            assert max_latency_ns < 1_000_000  # <1 millisecond max

        finally:
            asyncio.run(hft_engine.stop())

    def test_benchmark_hft_performance(self, hft_engine):
        """Benchmark HFT engine performance"""
        # Given: HFT engine
        asyncio.run(hft_engine.start())

        try:
            # When: Running performance benchmark
            results = hft_engine.benchmark_performance(num_orders=1000, num_ticks=10000)

            # Then: Should meet performance targets
            assert results["ticks_per_second"] > 100_000  # >100K ticks/second
            assert results["orders_per_second"] > 10_000  # >10K orders/second
            assert results["tick_processing_latency_us"] < 50  # <50μs per tick
            assert results["order_processing_latency_us"] < 100  # <100μs per order

        finally:
            asyncio.run(hft_engine.stop())


class TestMemoryPoolAndAllocator:
    """Test memory pool and aligned allocator components"""

    @pytest.fixture
    def memory_pool(self):
        """Create memory pool for testing"""

        class TestObject:
            def __init__(self):
                self.value = 0

            def reset(self):
                self.value = 0

        return MemoryPool(TestObject, initial_size=100)

    @pytest.fixture
    def aligned_allocator(self):
        """Create aligned memory allocator"""
        return AlignedMemoryAllocator(size=1024 * 1024, alignment=64)

    def test_memory_pool_allocation_performance(self, memory_pool):
        """Test memory pool allocation performance"""
        # Given: A memory pool
        # When: Allocating objects rapidly
        start_time = time.time()
        objects = []

        for _ in range(10000):
            obj = memory_pool.acquire()
            objects.append(obj)

        allocation_time = time.time() - start_time

        # Then: Should achieve high allocation rate
        allocation_rate = 10000 / allocation_time
        assert allocation_rate > 100_000  # >100K allocations/second

        # When: Releasing objects
        start_time = time.time()

        for obj in objects:
            memory_pool.release(obj)

        release_time = time.time() - start_time

        # Then: Should achieve high release rate
        release_rate = 10000 / release_time
        assert release_rate > 100_000  # >100K releases/second

    def test_aligned_allocator_cache_alignment(self, aligned_allocator):
        """Test aligned memory allocator ensures cache alignment"""
        # Given: Aligned memory allocator
        # When: Allocating multiple blocks
        offsets = []
        for _ in range(10):
            offset = aligned_allocator.allocate(64)
            assert offset is not None
            offsets.append(offset)

        # Then: All allocations should be cache-line aligned
        for offset in offsets:
            assert offset % 64 == 0  # 64-byte cache line alignment

    def test_ring_buffer_performance(self):
        """Test ring buffer zero-copy performance"""
        # Given: Ring buffer
        buffer = RingBuffer(size=1024, element_size=64)
        test_data = b"x" * 64

        # When: Writing data rapidly
        start_time = time.time()
        writes = 0

        for _ in range(10000):
            if buffer.write(test_data):
                writes += 1
                # Read to make space
                buffer.read()

        write_time = time.time() - start_time

        # Then: Should achieve high throughput
        write_rate = writes / write_time
        assert write_rate > 1_000_000  # >1M operations/second


class TestLockFreeQueues:
    """Test lock-free queue implementations"""

    def test_spsc_queue_performance(self):
        """Test SPSC queue performance"""
        # Given: SPSC queue
        queue = SPSCQueue(capacity=1024)

        # When: Single producer, single consumer
        def producer():
            for i in range(100000):
                while not queue.enqueue(i):
                    pass  # Retry until successful

        def consumer():
            consumed = []
            while len(consumed) < 100000:
                item = queue.dequeue()
                if item is not None:
                    consumed.append(item)
            return consumed

        start_time = time.time()

        producer_thread = threading.Thread(target=producer)
        consumer_thread = threading.Thread(target=consumer)

        producer_thread.start()
        consumer_thread.start()

        producer_thread.join()
        consumer_thread.join()

        duration = time.time() - start_time

        # Then: Should achieve high throughput
        throughput = 100000 / duration
        assert throughput > 1_000_000  # >1M operations/second

    def test_mpmc_queue_thread_safety(self):
        """Test MPMC queue thread safety"""
        # Given: MPMC queue
        queue = MPMCQueue(capacity=1000)

        # When: Multiple producers and consumers
        def producer(start_val):
            for i in range(start_val, start_val + 1000):
                while not queue.enqueue(i):
                    time.sleep(0.001)

        def consumer():
            items = []
            while len(items) < 1000:
                item = queue.dequeue()
                if item is not None:
                    items.append(item)
                else:
                    time.sleep(0.001)
            return items

        # Start multiple producers and consumers
        threads = []

        for i in range(4):  # 4 producers
            t = threading.Thread(target=producer, args=(i * 1000,))
            threads.append(t)
            t.start()

        consumer_results = []
        for i in range(4):  # 4 consumers
            t = threading.Thread(target=consumer)
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

        # Then: All items should be processed without corruption
        stats = queue.get_stats()
        assert stats["enqueues"] == 4000  # All items enqueued

    def test_lock_free_queue_adaptive_behavior(self):
        """Test adaptive queue behavior"""
        # Given: Adaptive lock-free queue
        queue = LockFreeQueue(capacity=1000)

        # When: Using with single thread (should detect SPSC)
        for i in range(100):
            queue.enqueue(i)

        for i in range(100):
            item = queue.dequeue()
            assert item == i

        # Then: Should maintain performance
        stats = queue.get_stats()
        assert stats["queue_type"] == "SPSC"


class TestClusterManagement:
    """Test horizontal scaling cluster management"""

    @pytest.fixture
    def cluster_manager(self):
        """Create cluster manager"""
        return ClusterManager("test-cluster")

    @pytest.fixture
    def sample_nodes(self):
        """Create sample nodes for testing"""
        return [
            NodeInfo(
                node_id=f"api-{i}",
                node_type=NodeType.API,
                host=f"10.0.1.{i+10}",
                port=8000 + i,
                cpu_cores=8,
                memory_gb=16,
            )
            for i in range(5)
        ]

    def test_cluster_manager_node_registration(self, cluster_manager, sample_nodes):
        """Test node registration and management"""
        # Given: Cluster manager
        cluster_manager.start()

        try:
            # When: Registering nodes
            for node in sample_nodes:
                success = cluster_manager.register_node(node)
                assert success is True

            # Then: All nodes should be registered
            assert len(cluster_manager.nodes) == 5

            # When: Getting nodes by type
            api_nodes = cluster_manager.get_nodes_by_type(NodeType.API)

            # Then: Should return correct nodes
            assert len(api_nodes) == 5

        finally:
            cluster_manager.stop()

    def test_cluster_stats_calculation(self, cluster_manager, sample_nodes):
        """Test cluster statistics calculation"""
        # Given: Cluster with nodes
        cluster_manager.start()

        try:
            for node in sample_nodes:
                cluster_manager.register_node(node)
                # Simulate metrics update
                metrics = {
                    "cpu_usage": random.uniform(20, 80),
                    "memory_usage": random.uniform(30, 70),
                    "requests_per_second": random.uniform(100, 1000),
                }
                cluster_manager.update_node_metrics(node.node_id, metrics)

            # When: Getting cluster stats
            stats = cluster_manager.get_cluster_stats()

            # Then: Should calculate correctly
            assert stats.total_nodes == 5
            assert stats.healthy_nodes >= 0
            assert stats.total_cpu_cores == 5 * 8  # 5 nodes × 8 cores
            assert stats.total_memory_gb == 5 * 16  # 5 nodes × 16GB

        finally:
            cluster_manager.stop()

    def test_best_node_selection(self, cluster_manager, sample_nodes):
        """Test best node selection algorithm"""
        # Given: Cluster with nodes having different loads
        cluster_manager.start()

        try:
            for i, node in enumerate(sample_nodes):
                cluster_manager.register_node(node)
                # Create different load levels
                cpu_usage = 20 + (i * 15)  # 20%, 35%, 50%, 65%, 80%
                metrics = {
                    "cpu_usage": cpu_usage,
                    "memory_usage": cpu_usage * 0.8,
                    "average_latency_ms": 5 + i * 2,
                }
                cluster_manager.update_node_metrics(node.node_id, metrics)

            # When: Getting best node
            best_node = cluster_manager.get_best_node_for_work(NodeType.API)

            # Then: Should select least loaded node
            assert best_node is not None
            assert best_node.node_id == "api-0"  # First node has lowest load

        finally:
            cluster_manager.stop()


class TestLoadBalancer:
    """Test load balancer functionality"""

    @pytest.fixture
    def load_balancer(self):
        """Create load balancer"""
        return LatencyAwareLoadBalancer(LoadBalancingStrategy.LEAST_LATENCY)

    @pytest.fixture
    def sample_nodes(self):
        """Create sample nodes with different performance characteristics"""
        nodes = []
        for i in range(3):
            node = NodeInfo(
                node_id=f"node-{i}",
                node_type=NodeType.API,
                host=f"10.0.1.{i+10}",
                port=8000 + i,
                status=NodeStatus.HEALTHY,
            )
            # Different performance characteristics
            node.average_latency_ms = 10 + i * 5  # 10ms, 15ms, 20ms
            node.active_connections = 100 + i * 50  # 100, 150, 200
            node.cpu_usage = 50 + i * 10  # 50%, 60%, 70%
            nodes.append(node)
        return nodes

    def test_latency_aware_selection(self, load_balancer, sample_nodes):
        """Test latency-aware node selection"""
        # Given: Load balancer with nodes
        load_balancer.update_nodes(sample_nodes)

        # When: Selecting nodes multiple times
        selections = []
        for _ in range(100):
            node = load_balancer.select_node()
            if node:
                selections.append(node.node_id)

        # Then: Should favor lower latency nodes
        node_0_count = selections.count("node-0")  # Lowest latency
        node_2_count = selections.count("node-2")  # Highest latency

        assert node_0_count > node_2_count  # Should favor lower latency

    def test_session_affinity(self, load_balancer, sample_nodes):
        """Test session affinity functionality"""
        # Given: Load balancer with nodes
        load_balancer.update_nodes(sample_nodes)
        session_id = "test-session-123"

        # When: Making requests with same session ID
        selected_nodes = []
        for _ in range(10):
            node = load_balancer.select_node(session_id)
            if node:
                selected_nodes.append(node.node_id)
                # Record successful request
                load_balancer.record_request_result(node.node_id, True, 50.0)

        # Then: Should maintain session affinity
        unique_nodes = set(selected_nodes)
        assert len(unique_nodes) == 1  # All requests to same node

    def test_circuit_breaker_functionality(self, load_balancer, sample_nodes):
        """Test circuit breaker functionality"""
        # Given: Load balancer with nodes
        load_balancer.update_nodes(sample_nodes)
        failing_node_id = "node-0"

        # When: Recording multiple failures for a node
        for _ in range(10):  # Trigger circuit breaker
            load_balancer.record_request_result(failing_node_id, False, 1000.0)

        # When: Selecting nodes
        selections = []
        for _ in range(50):
            node = load_balancer.select_node()
            if node:
                selections.append(node.node_id)

        # Then: Should avoid failing node
        failing_node_selections = selections.count(failing_node_id)
        assert failing_node_selections < 10  # Should be significantly reduced


class TestAutoScaler:
    """Test auto-scaling functionality"""

    @pytest.fixture
    def auto_scaler(self):
        """Create auto scaler"""
        return AutoScaler()

    @pytest.fixture
    def scaling_policy(self):
        """Create test scaling policy"""
        from fxml4.scaling.auto_scaler import ScalingPolicy, ScalingRule

        rules = [
            ScalingRule(
                name="High CPU",
                trigger=ScalingTrigger.CPU_UTILIZATION,
                node_type=NodeType.API,
                scale_up_threshold=80.0,
                scale_down_threshold=30.0,
                min_instances=2,
                max_instances=10,
            )
        ]

        return ScalingPolicy(name="Test Policy", rules=rules)

    def test_scaling_decision_logic(self, auto_scaler, scaling_policy):
        """Test scaling decision logic"""
        # Given: Auto scaler with policy
        auto_scaler.add_scaling_policy(scaling_policy)
        auto_scaler.set_active_policy("Test Policy")
        auto_scaler.update_instance_counts({NodeType.API: 3})

        # When: High CPU utilization
        high_cpu_metrics = ScalingMetrics(
            cpu_utilization=85.0,  # Above scale-up threshold
            memory_utilization=60.0,
            request_rate=1000.0,
        )

        for _ in range(3):  # Need multiple measurements for evaluation
            auto_scaler.update_metrics(high_cpu_metrics)

        # When: Evaluating scaling needs
        decisions = auto_scaler.evaluate_scaling_needs()

        # Then: Should decide to scale up
        assert len(decisions) > 0
        api_decision = next((d for d in decisions if d.node_type == NodeType.API), None)
        assert api_decision is not None
        assert api_decision.direction.value == "scale_up"

    def test_scaling_constraints(self, auto_scaler, scaling_policy):
        """Test scaling constraints are applied"""
        # Given: Auto scaler at maximum instances
        auto_scaler.add_scaling_policy(scaling_policy)
        auto_scaler.set_active_policy("Test Policy")
        auto_scaler.update_instance_counts({NodeType.API: 10})  # At max

        # When: High load metrics
        high_load_metrics = ScalingMetrics(cpu_utilization=95.0)

        for _ in range(3):
            auto_scaler.update_metrics(high_load_metrics)

        decisions = auto_scaler.evaluate_scaling_needs()

        # Then: Should respect max constraints
        api_decision = next((d for d in decisions if d.node_type == NodeType.API), None)
        if api_decision:
            assert api_decision.target_instances <= 10  # Respect max instances


class TestCaching:
    """Test multi-level caching system"""

    @pytest.fixture
    def multi_level_cache(self):
        """Create multi-level cache"""
        return MultiLevelCache(l1_size=1000, redis_url="redis://localhost:6379")

    @pytest.fixture
    def lru_cache(self):
        """Create LRU cache"""
        return LRUCache(max_size=1000)

    def test_lru_cache_performance(self, lru_cache):
        """Test LRU cache performance"""
        # Given: LRU cache
        # When: Setting values rapidly
        start_time = time.time()

        for i in range(10000):
            key = f"key_{i % 100}"  # Reuse keys to test eviction
            value = f"value_{i}"
            lru_cache.set(key, value)

        set_time = time.time() - start_time

        # When: Getting values rapidly
        start_time = time.time()

        for i in range(10000):
            key = f"key_{i % 100}"
            value = lru_cache.get(key)

        get_time = time.time() - start_time

        # Then: Should achieve high performance
        set_rate = 10000 / set_time
        get_rate = 10000 / get_time

        assert set_rate > 100_000  # >100K sets/second
        assert get_rate > 1_000_000  # >1M gets/second

    def test_cache_hit_rate(self, lru_cache):
        """Test cache hit rate"""
        # Given: LRU cache with data
        for i in range(100):
            lru_cache.set(f"key_{i}", f"value_{i}")

        # When: Accessing cached data
        hits = 0
        total = 200

        for i in range(total):
            key = f"key_{i % 150}"  # Mix of existing and new keys
            value = lru_cache.get(key)
            if value is not None:
                hits += 1

        # Then: Should achieve reasonable hit rate
        hit_rate = hits / total
        assert hit_rate > 0.5  # >50% hit rate

    @pytest.mark.asyncio
    async def test_multi_level_cache_promotion(self, multi_level_cache):
        """Test cache level promotion logic"""
        # Given: Multi-level cache
        test_key = "hot_data_key"
        test_value = "hot_data_value"

        # When: Setting data in L2/L3
        await multi_level_cache.set(test_key, test_value, force_level=None)

        # When: Accessing frequently (should promote to L1)
        for _ in range(5):
            value = await multi_level_cache.get(test_key)
            assert value == test_value

        # Then: Should be promoted to L1
        l1_value = multi_level_cache.l1_cache.get(test_key)
        assert l1_value == test_value  # Should be in L1 now


class TestStreamProcessing:
    """Test streaming data processing"""

    @pytest.fixture
    def tick_processor(self):
        """Create tick processor"""
        return TickProcessor(max_queue_size=10000, num_workers=2)

    def test_tick_processing_throughput(self, tick_processor):
        """Test tick processing throughput"""
        # Given: Tick processor
        processed_ticks = []

        def test_handler(tick: TickData):
            processed_ticks.append(tick)

        tick_processor.add_handler(TickType.BID_ASK, test_handler)
        tick_processor.start()

        try:
            # When: Processing many ticks
            start_time = time.time()

            for i in range(1000):
                tick = TickData(
                    symbol="EURUSD",
                    timestamp_ns=time.time_ns(),
                    tick_type=TickType.BID_ASK,
                    bid=1.1000 + i * 0.0001,
                    ask=1.1001 + i * 0.0001,
                )
                tick_processor.process_tick(tick)

            # Wait for processing to complete
            time.sleep(2.0)
            processing_time = time.time() - start_time

            # Then: Should achieve high throughput
            throughput = len(processed_ticks) / processing_time
            assert throughput > 1000  # >1K ticks/second

            # And: Should maintain low latency
            stats = tick_processor.get_stats()
            assert stats.average_latency_us < 1000  # <1ms average latency

        finally:
            tick_processor.stop()

    def test_tick_processor_backpressure(self, tick_processor):
        """Test backpressure handling"""

        # Given: Tick processor with slow handler
        def slow_handler(tick: TickData):
            time.sleep(0.01)  # 10ms delay

        tick_processor.add_handler(TickType.BID_ASK, slow_handler)
        tick_processor.start()

        try:
            # When: Overwhelming with ticks
            rejected_count = 0

            for i in range(1000):
                tick = tick_processor.generate_test_tick()
                if not tick_processor.process_tick(tick):
                    rejected_count += 1

            # Then: Should activate backpressure
            health_status = tick_processor.get_health_status()

            # Should eventually reject some ticks or activate backpressure
            assert rejected_count > 0 or health_status["backpressure_active"]

        finally:
            tick_processor.stop()


class TestLoadTestingFramework:
    """Test load testing framework"""

    @pytest.fixture
    def load_test_framework(self):
        """Create load test framework"""
        return LoadTestFramework()

    @pytest.fixture
    def test_config(self):
        """Create test configuration"""
        return LoadTestConfig(
            name="Unit Test Load",
            test_type=LoadTestType.LOAD,
            base_url="http://httpbin.org",  # Use httpbin for testing
            concurrent_users=5,
            requests_per_user=10,
            ramp_up_seconds=2.0,
            test_duration_seconds=10.0,
            ramp_down_seconds=2.0,
            max_response_time_ms=2000.0,  # Generous for external service
            max_error_rate_percent=10.0,
        )

    @pytest.mark.asyncio
    async def test_load_test_execution(self, load_test_framework, test_config):
        """Test load test execution"""
        # Given: Load test framework and configuration
        # When: Running load test
        with patch("aiohttp.ClientSession.request") as mock_request:
            # Mock successful responses
            mock_response = MagicMock()
            mock_response.status = 200
            mock_response.text = MagicMock(
                return_value=asyncio.coroutine(lambda: "OK")()
            )
            mock_response.__aenter__ = MagicMock(
                return_value=asyncio.coroutine(lambda: mock_response)()
            )
            mock_response.__aexit__ = MagicMock(
                return_value=asyncio.coroutine(lambda *args: None)()
            )
            mock_request.return_value = mock_response

            result = await load_test_framework.run_load_test(test_config)

        # Then: Should produce valid results
        assert result is not None
        assert result.total_requests > 0
        assert result.total_duration_seconds > 0

    def test_load_test_criteria_evaluation(self, load_test_framework):
        """Test load test pass/fail criteria"""
        # Given: Load test result
        from tests.performance.load_testing_framework import LoadTestResult

        config = LoadTestConfig(
            name="Criteria Test",
            test_type=LoadTestType.LOAD,
            base_url="http://test",
            max_response_time_ms=100.0,
            max_error_rate_percent=1.0,
        )

        result = LoadTestResult(
            config=config,
            start_time=time.time(),
            end_time=time.time() + 60,
            total_duration_seconds=60.0,
            total_requests=1000,
            successful_requests=990,
            failed_requests=10,
            average_response_time_ms=150.0,  # Exceeds limit
            error_rate_percent=1.0,
        )

        # When: Evaluating criteria
        passed = load_test_framework._evaluate_test_criteria(config, result)

        # Then: Should fail due to high response time
        assert passed is False
        assert len(result.failure_reasons) > 0
        assert any(
            "response time" in reason.lower() for reason in result.failure_reasons
        )


class TestIntegrationScenarios:
    """Integration tests for complete performance optimization scenarios"""

    @pytest.mark.asyncio
    async def test_hft_trading_scenario(self):
        """Test complete HFT trading scenario"""
        # Given: Complete HFT system components
        hft_engine = HighFrequencyTradingEngine()
        cluster_manager = ClusterManager("hft-cluster")

        await hft_engine.start()
        cluster_manager.start()

        try:
            # When: Simulating high-frequency trading
            # 1. Market data arrives
            symbols = ["EURUSD", "GBPUSD", "USDJPY"]
            orders_placed = 0

            for i in range(1000):
                symbol = random.choice(symbols)
                bid = 1.1000 + random.uniform(-0.01, 0.01)
                ask = bid + random.uniform(0.0001, 0.0005)

                # Process market tick
                success = hft_engine.process_market_tick(
                    symbol, bid, ask, 1000000, 1000000
                )
                assert success is True

                # Place order based on signal
                if i % 10 == 0:  # Place order every 10th tick
                    order_id = hft_engine.submit_order(symbol, "BUY", 10000)
                    assert order_id > 0
                    orders_placed += 1

            # Then: System should handle load efficiently
            stats = hft_engine.get_performance_stats()
            assert stats["ticks_processed"] == 1000
            assert stats["orders_executed"] == orders_placed

            # And: Latency should be within requirements
            assert stats["latency_measurements"] is not None

        finally:
            await hft_engine.stop()
            cluster_manager.stop()

    def test_scaling_under_load(self):
        """Test scaling behavior under load"""
        # Given: Auto scaler with realistic configuration
        auto_scaler = AutoScaler()

        from fxml4.scaling.auto_scaler import create_standard_trading_policy

        policy = create_standard_trading_policy()
        auto_scaler.add_scaling_policy(policy)
        auto_scaler.set_active_policy("Standard Trading")

        # Initial state
        auto_scaler.update_instance_counts({NodeType.API: 3, NodeType.TRADING: 2})

        # When: Simulating increasing load
        scale_up_triggered = False

        for load_level in [50, 70, 90, 95]:  # Increasing CPU load
            metrics = ScalingMetrics(
                cpu_utilization=load_level,
                memory_utilization=load_level * 0.8,
                request_rate=load_level * 20,
                trading_volume_usd=load_level * 10000,
            )

            # Update metrics multiple times for evaluation period
            for _ in range(4):
                auto_scaler.update_metrics(metrics)

            decisions = auto_scaler.evaluate_scaling_needs()

            if decisions and any(d.direction.value == "scale_up" for d in decisions):
                scale_up_triggered = True
                break

        # Then: Should trigger scale up under high load
        assert scale_up_triggered is True

    @pytest.mark.asyncio
    async def test_cache_performance_under_load(self):
        """Test cache performance under load"""
        # Given: Multi-level cache
        cache = MultiLevelCache(l1_size=1000)

        # When: High-frequency cache operations
        start_time = time.time()

        # Phase 1: Load cache
        for i in range(5000):
            key = f"market_data:{i % 100}"  # Realistic key pattern
            value = {
                "price": 1.1000 + i * 0.0001,
                "volume": random.randint(1000, 100000),
                "timestamp": time.time(),
            }
            await cache.set(key, value)

        # Phase 2: Heavy read load with some writes
        hits = 0
        total_ops = 0

        for i in range(10000):
            key = f"market_data:{random.randint(0, 150)}"  # Mix of hot and cold data

            if random.random() < 0.1:  # 10% writes
                await cache.set(key, {"updated": time.time()})
            else:  # 90% reads
                value = await cache.get(key)
                if value is not None:
                    hits += 1

            total_ops += 1

        duration = time.time() - start_time

        # Then: Should maintain high performance
        ops_per_second = total_ops / duration
        hit_rate = hits / (total_ops * 0.9)  # Only count read operations

        assert ops_per_second > 10000  # >10K ops/second
        assert hit_rate > 0.8  # >80% hit rate

        # And: Cache statistics should show good performance
        stats = cache.get_comprehensive_stats()
        assert stats["global"]["overall_hit_rate"] > 70  # >70% overall hit rate


if __name__ == "__main__":
    # Run tests with performance reporting
    pytest.main(
        [
            __file__,
            "-v",
            "--tb=short",
            "-x",  # Stop on first failure
            "--durations=10",  # Show 10 slowest tests
        ]
    )
