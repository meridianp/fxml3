"""Real-time data streaming concurrency tests for FXML4.

Tests concurrent real-time data processing, streaming operations,
callback coordination, and performance under high-frequency conditions.
"""

import asyncio
import random
import threading
import time
from collections import deque
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Dict, List, Optional
from unittest.mock import AsyncMock, Mock, patch

import numpy as np
import pytest

from tests.utils.concurrency_utils import (
    LoadGenerator,
    RaceConditionDetector,
    ThreadConcurrencyTester,
    concurrency_test_environment,
)


class MockMarketDataStream:
    """Mock market data streaming source."""

    def __init__(self, symbols: List[str], tick_rate_hz: int = 100):
        self.symbols = symbols
        self.tick_rate_hz = tick_rate_hz
        self.subscribers = {}
        self.streaming = False
        self.stream_task = None
        self.tick_counter = 0
        self._lock = asyncio.Lock()

    async def subscribe(self, symbol: str, callback: Callable):
        """Subscribe to market data for symbol."""
        async with self._lock:
            if symbol not in self.subscribers:
                self.subscribers[symbol] = []
            self.subscribers[symbol].append(callback)

        if not self.streaming:
            await self.start_streaming()

    async def unsubscribe(self, symbol: str, callback: Callable):
        """Unsubscribe from market data."""
        async with self._lock:
            if symbol in self.subscribers:
                try:
                    self.subscribers[symbol].remove(callback)
                    if not self.subscribers[symbol]:
                        del self.subscribers[symbol]
                except ValueError:
                    pass

    async def start_streaming(self):
        """Start market data streaming."""
        if self.streaming:
            return

        self.streaming = True
        self.stream_task = asyncio.create_task(self._stream_data())

    async def stop_streaming(self):
        """Stop market data streaming."""
        self.streaming = False
        if self.stream_task:
            self.stream_task.cancel()
            try:
                await self.stream_task
            except asyncio.CancelledError:
                pass

    async def _stream_data(self):
        """Stream market data to subscribers."""
        try:
            while self.streaming:
                # Generate tick for each symbol
                for symbol in self.symbols:
                    if symbol in self.subscribers:
                        tick_data = self._generate_tick(symbol)

                        # Notify all subscribers concurrently
                        callbacks = self.subscribers[symbol].copy()
                        if callbacks:
                            await asyncio.gather(
                                *[
                                    self._safe_callback(cb, tick_data)
                                    for cb in callbacks
                                ],
                                return_exceptions=True,
                            )

                # Control tick rate
                await asyncio.sleep(1.0 / self.tick_rate_hz)

        except asyncio.CancelledError:
            pass

    async def _safe_callback(self, callback: Callable, data: Dict[str, Any]):
        """Safely execute callback with error handling."""
        try:
            if asyncio.iscoroutinefunction(callback):
                await callback(data)
            else:
                callback(data)
        except Exception as e:
            # Log error but continue streaming
            print(f"Callback error: {e}")

    def _generate_tick(self, symbol: str) -> Dict[str, Any]:
        """Generate realistic tick data."""
        self.tick_counter += 1

        # Base prices for different symbols
        base_prices = {
            "EURUSD": 1.1000,
            "GBPUSD": 1.2500,
            "USDJPY": 110.00,
            "USDCHF": 0.9200,
        }

        base_price = base_prices.get(symbol, 1.0000)
        price_change = random.uniform(-0.0001, 0.0001)

        return {
            "symbol": symbol,
            "timestamp": datetime.now(timezone.utc),
            "price": base_price + price_change,
            "size": random.randint(1000, 10000),
            "tick_id": self.tick_counter,
            "bid": base_price + price_change - 0.0001,
            "ask": base_price + price_change + 0.0001,
        }


class RealTimeDataProcessor:
    """Real-time data processor with concurrent processing."""

    def __init__(self, buffer_size: int = 1000):
        self.buffer_size = buffer_size
        self.tick_buffer = deque(maxlen=buffer_size)
        self.feature_buffer = deque(maxlen=buffer_size)
        self.processing_stats = {
            "ticks_received": 0,
            "ticks_processed": 0,
            "features_generated": 0,
            "processing_errors": 0,
        }
        self._lock = asyncio.Lock()
        self.processing_task = None
        self.running = False

    async def start_processing(self):
        """Start real-time processing."""
        if self.running:
            return

        self.running = True
        self.processing_task = asyncio.create_task(self._process_data())

    async def stop_processing(self):
        """Stop real-time processing."""
        self.running = False
        if self.processing_task:
            self.processing_task.cancel()
            try:
                await self.processing_task
            except asyncio.CancelledError:
                pass

    async def on_tick_received(self, tick_data: Dict[str, Any]):
        """Handle incoming tick data."""
        async with self._lock:
            self.tick_buffer.append(tick_data)
            self.processing_stats["ticks_received"] += 1

    async def _process_data(self):
        """Process buffered tick data."""
        try:
            while self.running:
                # Process available ticks
                ticks_to_process = []

                async with self._lock:
                    while self.tick_buffer and len(ticks_to_process) < 10:
                        ticks_to_process.append(self.tick_buffer.popleft())

                if ticks_to_process:
                    try:
                        await self._process_tick_batch(ticks_to_process)
                    except Exception as e:
                        async with self._lock:
                            self.processing_stats["processing_errors"] += 1

                # Small delay to prevent busy waiting
                await asyncio.sleep(0.001)

        except asyncio.CancelledError:
            pass

    async def _process_tick_batch(self, ticks: List[Dict[str, Any]]):
        """Process batch of ticks and generate features."""
        # Simulate feature generation processing time
        await asyncio.sleep(len(ticks) * 0.0001)

        features = []
        for tick in ticks:
            # Generate mock features
            feature = {
                "symbol": tick["symbol"],
                "timestamp": tick["timestamp"],
                "price": tick["price"],
                "moving_avg": tick["price"] * random.uniform(0.999, 1.001),
                "volatility": random.uniform(0.0001, 0.001),
                "volume_weighted_price": tick["price"]
                * (1 + random.uniform(-0.0001, 0.0001)),
            }
            features.append(feature)

        async with self._lock:
            self.feature_buffer.extend(features)
            self.processing_stats["ticks_processed"] += len(ticks)
            self.processing_stats["features_generated"] += len(features)

    def get_stats(self) -> Dict[str, Any]:
        """Get processing statistics."""
        return self.processing_stats.copy()


@pytest.mark.concurrency
@pytest.mark.streaming
class TestRealTimeDataStreaming:
    """Test real-time data streaming concurrent operations."""

    @pytest.fixture
    def market_stream(self):
        """Create market data stream."""
        symbols = ["EURUSD", "GBPUSD", "USDJPY", "USDCHF"]
        stream = MockMarketDataStream(symbols, tick_rate_hz=200)  # 200 Hz
        yield stream

        # Cleanup
        asyncio.create_task(stream.stop_streaming())

    @pytest.fixture
    def data_processor(self):
        """Create data processor."""
        processor = RealTimeDataProcessor(buffer_size=2000)
        yield processor

        # Cleanup
        asyncio.create_task(processor.stop_processing())

    @pytest.mark.asyncio
    async def test_concurrent_subscription_management(self, market_stream):
        """Test concurrent subscription/unsubscription operations."""

        received_ticks = {}
        callback_locks = {}

        async def create_subscriber(subscriber_id: str, symbol: str):
            """Create subscriber and collect ticks."""
            received_ticks[subscriber_id] = []
            callback_locks[subscriber_id] = asyncio.Lock()

            async def tick_callback(tick_data):
                async with callback_locks[subscriber_id]:
                    received_ticks[subscriber_id].append(tick_data)

            # Subscribe
            await market_stream.subscribe(symbol, tick_callback)

            # Stay subscribed for a period
            await asyncio.sleep(0.5)

            # Unsubscribe
            await market_stream.unsubscribe(symbol, tick_callback)

            return len(received_ticks[subscriber_id])

        # Create multiple concurrent subscribers
        symbols = ["EURUSD", "GBPUSD", "USDJPY"]
        subscription_tasks = []

        for i in range(20):
            symbol = symbols[i % len(symbols)]
            subscriber_id = f"subscriber_{i}"
            subscription_tasks.append((subscriber_id, symbol))

        async with concurrency_test_environment(max_concurrent=20) as env:
            result = await env.test_async_operation(
                create_subscriber, subscription_tasks, max_concurrent=20, timeout=5.0
            )

            # All subscriptions should complete successfully
            assert result.operations_completed == 20
            assert result.operations_failed == 0

            # Verify tick reception
            total_ticks_received = sum(len(ticks) for ticks in received_ticks.values())
            assert total_ticks_received > 0

            # Check for race conditions in subscription management
            assert result.race_conditions_detected == 0

    @pytest.mark.asyncio
    async def test_high_frequency_data_processing(self, market_stream, data_processor):
        """Test high-frequency data processing under load."""

        # Start processing
        await data_processor.start_processing()

        # Subscribe to multiple symbols
        symbols = ["EURUSD", "GBPUSD", "USDJPY", "USDCHF"]
        for symbol in symbols:
            await market_stream.subscribe(symbol, data_processor.on_tick_received)

        # Let it run for a period to generate high-frequency data
        await asyncio.sleep(2.0)

        # Stop processing
        await data_processor.stop_processing()
        await market_stream.stop_streaming()

        # Check processing statistics
        stats = data_processor.get_stats()

        # Should have processed significant amount of data
        assert stats["ticks_received"] > 1000  # At least 1000 ticks in 2 seconds
        assert stats["ticks_processed"] > 0
        assert stats["features_generated"] > 0
        assert stats["processing_errors"] == 0  # No processing errors

        # Processing efficiency
        processing_ratio = stats["ticks_processed"] / stats["ticks_received"]
        assert processing_ratio > 0.8  # At least 80% processing efficiency

    @pytest.mark.asyncio
    async def test_callback_coordination_under_load(self, market_stream):
        """Test callback coordination under high load."""

        callback_stats = {}
        race_detector = RaceConditionDetector()

        async def stress_callback(callback_id: str, tick_data: Dict[str, Any]):
            """Callback that simulates processing load."""
            # Record access to shared resource
            race_detector.access_shared_resource(
                f"callback_stats_{tick_data['symbol']}", "write", callback_id
            )

            if callback_id not in callback_stats:
                callback_stats[callback_id] = {
                    "calls": 0,
                    "symbols": set(),
                    "total_processing_time": 0,
                }

            start_time = time.perf_counter()

            # Simulate processing
            await asyncio.sleep(random.uniform(0.0001, 0.001))

            end_time = time.perf_counter()

            callback_stats[callback_id]["calls"] += 1
            callback_stats[callback_id]["symbols"].add(tick_data["symbol"])
            callback_stats[callback_id]["total_processing_time"] += (
                end_time - start_time
            )

        # Create multiple callbacks for each symbol
        symbols = ["EURUSD", "GBPUSD"]
        callbacks_per_symbol = 10

        for symbol in symbols:
            for i in range(callbacks_per_symbol):
                callback_id = f"{symbol}_callback_{i}"
                callback_func = lambda tick, cb_id=callback_id: asyncio.create_task(
                    stress_callback(cb_id, tick)
                )
                await market_stream.subscribe(symbol, callback_func)

        # Run high-frequency streaming
        await asyncio.sleep(1.0)
        await market_stream.stop_streaming()

        # Wait for all callbacks to complete
        await asyncio.sleep(0.1)

        # Analyze callback performance
        total_callbacks = len(callback_stats)
        assert total_callbacks == len(symbols) * callbacks_per_symbol

        # Check for race conditions
        race_conditions = race_detector.get_race_conditions()
        assert len(race_conditions) == 0  # Should handle concurrency safely

        # Verify callback distribution
        for callback_id, stats in callback_stats.items():
            assert stats["calls"] > 0  # Each callback should be invoked
            assert len(stats["symbols"]) == 1  # Each callback handles one symbol

    @pytest.mark.asyncio
    async def test_streaming_performance_under_load(self, market_stream):
        """Test streaming performance under heavy subscriber load."""

        performance_metrics = {
            "tick_latencies": [],
            "callback_counts": {},
            "processing_times": [],
        }

        async def performance_callback(subscriber_id: str, tick_data: Dict[str, Any]):
            """Callback that measures performance."""
            receive_time = time.perf_counter()
            tick_time = tick_data["timestamp"].timestamp()

            # Measure latency (approximate)
            latency = receive_time - tick_time
            performance_metrics["tick_latencies"].append(latency)

            # Count callbacks
            if subscriber_id not in performance_metrics["callback_counts"]:
                performance_metrics["callback_counts"][subscriber_id] = 0
            performance_metrics["callback_counts"][subscriber_id] += 1

            # Simulate processing time
            process_start = time.perf_counter()
            await asyncio.sleep(0.0001)  # 0.1ms processing
            process_end = time.perf_counter()

            performance_metrics["processing_times"].append(process_end - process_start)

        # Create many subscribers
        num_subscribers = 50
        symbols = ["EURUSD", "GBPUSD", "USDJPY"]

        for i in range(num_subscribers):
            symbol = symbols[i % len(symbols)]
            subscriber_id = f"perf_subscriber_{i}"
            callback_func = lambda tick, sub_id=subscriber_id: asyncio.create_task(
                performance_callback(sub_id, tick)
            )
            await market_stream.subscribe(symbol, callback_func)

        # Run performance test
        test_start = time.perf_counter()
        await asyncio.sleep(1.0)  # 1 second of streaming
        test_end = time.perf_counter()

        await market_stream.stop_streaming()

        # Wait for callbacks to complete
        await asyncio.sleep(0.2)

        # Analyze performance
        test_duration = test_end - test_start
        total_callbacks = sum(performance_metrics["callback_counts"].values())

        # Performance requirements
        callbacks_per_second = total_callbacks / test_duration
        assert callbacks_per_second > 1000  # > 1000 callbacks/second

        # Latency requirements
        if performance_metrics["tick_latencies"]:
            avg_latency = np.mean(performance_metrics["tick_latencies"])
            assert avg_latency < 0.01  # < 10ms average latency

        # Processing time consistency
        if performance_metrics["processing_times"]:
            avg_processing_time = np.mean(performance_metrics["processing_times"])
            assert avg_processing_time < 0.001  # < 1ms average processing

    @pytest.mark.asyncio
    async def test_stream_recovery_from_failures(self, market_stream):
        """Test stream recovery from callback failures."""

        failure_stats = {
            "callback_failures": 0,
            "successful_callbacks": 0,
            "recovery_time": 0,
        }

        async def failing_callback(tick_data: Dict[str, Any]):
            """Callback that sometimes fails."""
            if random.random() < 0.1:  # 10% failure rate
                failure_stats["callback_failures"] += 1
                raise Exception(f"Simulated callback failure for {tick_data['symbol']}")
            else:
                failure_stats["successful_callbacks"] += 1

        async def reliable_callback(tick_data: Dict[str, Any]):
            """Callback that never fails."""
            failure_stats["successful_callbacks"] += 1

        # Subscribe with mix of reliable and failing callbacks
        symbols = ["EURUSD", "GBPUSD"]

        for symbol in symbols:
            # Add failing callback
            await market_stream.subscribe(symbol, failing_callback)
            # Add reliable callback
            await market_stream.subscribe(symbol, reliable_callback)

        # Run with failures
        failure_start = time.perf_counter()
        await asyncio.sleep(1.0)
        failure_end = time.perf_counter()

        await market_stream.stop_streaming()

        # Stream should continue despite callback failures
        assert failure_stats["callback_failures"] > 0  # Some failures occurred
        assert (
            failure_stats["successful_callbacks"] > failure_stats["callback_failures"]
        )  # More successes

        # Recovery time should be minimal
        recovery_time = failure_end - failure_start
        assert recovery_time < 1.5  # Should not significantly impact performance

    @pytest.mark.asyncio
    async def test_memory_efficiency_under_streaming(
        self, market_stream, data_processor
    ):
        """Test memory efficiency during prolonged streaming."""

        # Start memory monitoring
        initial_buffer_size = len(data_processor.tick_buffer)

        # Subscribe to data processing
        await data_processor.start_processing()
        await market_stream.subscribe("EURUSD", data_processor.on_tick_received)

        # Run for extended period
        test_duration = 2.0
        memory_samples = []

        start_time = time.perf_counter()
        while time.perf_counter() - start_time < test_duration:
            # Sample memory usage
            buffer_size = len(data_processor.tick_buffer)
            feature_buffer_size = len(data_processor.feature_buffer)
            memory_samples.append(
                {
                    "time": time.perf_counter() - start_time,
                    "tick_buffer_size": buffer_size,
                    "feature_buffer_size": feature_buffer_size,
                }
            )

            await asyncio.sleep(0.1)  # Sample every 100ms

        await market_stream.stop_streaming()
        await data_processor.stop_processing()

        # Analyze memory usage
        max_tick_buffer = max(sample["tick_buffer_size"] for sample in memory_samples)
        max_feature_buffer = max(
            sample["feature_buffer_size"] for sample in memory_samples
        )

        # Memory should be bounded by buffer limits
        assert max_tick_buffer <= data_processor.buffer_size
        assert max_feature_buffer <= data_processor.buffer_size

        # Buffers should be actively processed (not just growing)
        final_buffer_size = memory_samples[-1]["tick_buffer_size"]
        assert final_buffer_size < data_processor.buffer_size * 0.9  # < 90% full


@pytest.mark.concurrency
@pytest.mark.streaming
@pytest.mark.performance
class TestStreamingPerformanceBenchmarks:
    """Performance benchmarks for streaming operations."""

    @pytest.mark.asyncio
    async def test_maximum_throughput_benchmark(self):
        """Benchmark maximum streaming throughput."""

        throughput_metrics = {
            "ticks_generated": 0,
            "ticks_processed": 0,
            "start_time": 0,
            "end_time": 0,
        }

        async def high_throughput_callback(tick_data: Dict[str, Any]):
            """High-performance callback."""
            throughput_metrics["ticks_processed"] += 1

        # Create high-frequency stream
        symbols = ["EURUSD"]
        stream = MockMarketDataStream(symbols, tick_rate_hz=1000)  # 1000 Hz

        await stream.subscribe("EURUSD", high_throughput_callback)

        # Benchmark period
        throughput_metrics["start_time"] = time.perf_counter()
        await asyncio.sleep(1.0)  # 1 second benchmark
        throughput_metrics["end_time"] = time.perf_counter()

        await stream.stop_streaming()

        # Calculate throughput
        test_duration = (
            throughput_metrics["end_time"] - throughput_metrics["start_time"]
        )
        actual_throughput = throughput_metrics["ticks_processed"] / test_duration

        # High-performance requirements
        assert actual_throughput > 500  # > 500 ticks/second processed

        # Efficiency ratio
        efficiency = throughput_metrics["ticks_processed"] / stream.tick_counter
        assert efficiency > 0.9  # > 90% processing efficiency

    @pytest.mark.asyncio
    async def test_latency_benchmark(self):
        """Benchmark callback latency under load."""

        latency_measurements = []

        async def latency_callback(tick_data: Dict[str, Any]):
            """Measure callback latency."""
            callback_time = time.perf_counter()
            tick_timestamp = tick_data["timestamp"].timestamp()

            # Approximate latency calculation
            latency = callback_time - tick_timestamp
            latency_measurements.append(latency)

        # Test with multiple symbols and subscribers
        symbols = ["EURUSD", "GBPUSD", "USDJPY"]
        stream = MockMarketDataStream(symbols, tick_rate_hz=500)

        # Subscribe multiple callbacks per symbol
        for symbol in symbols:
            for i in range(5):  # 5 callbacks per symbol
                await stream.subscribe(symbol, latency_callback)

        # Run latency test
        await asyncio.sleep(1.0)
        await stream.stop_streaming()

        # Analyze latency
        if latency_measurements:
            avg_latency = np.mean(latency_measurements)
            p95_latency = np.percentile(latency_measurements, 95)
            p99_latency = np.percentile(latency_measurements, 99)

            # Latency requirements
            assert avg_latency < 0.005  # < 5ms average latency
            assert p95_latency < 0.010  # < 10ms 95th percentile
            assert p99_latency < 0.020  # < 20ms 99th percentile

    @pytest.mark.asyncio
    async def test_scalability_benchmark(self):
        """Benchmark system scalability with increasing load."""

        scalability_results = []

        async def scalability_callback(callback_id: str, tick_data: Dict[str, Any]):
            """Callback for scalability testing."""
            pass  # Minimal processing

        # Test with increasing number of subscribers
        subscriber_counts = [10, 25, 50, 100, 200]

        for num_subscribers in subscriber_counts:
            stream = MockMarketDataStream(["EURUSD"], tick_rate_hz=200)

            # Create subscribers
            for i in range(num_subscribers):
                callback_id = f"subscriber_{i}"
                callback_func = lambda tick, cb_id=callback_id: asyncio.create_task(
                    scalability_callback(cb_id, tick)
                )
                await stream.subscribe("EURUSD", callback_func)

            # Measure performance
            start_time = time.perf_counter()
            await asyncio.sleep(0.5)  # 500ms test
            end_time = time.perf_counter()

            await stream.stop_streaming()

            test_duration = end_time - start_time
            scalability_results.append(
                {
                    "subscribers": num_subscribers,
                    "duration": test_duration,
                    "ticks_generated": stream.tick_counter,
                    "throughput": stream.tick_counter / test_duration,
                }
            )

        # Analyze scalability
        for result in scalability_results:
            # Throughput should remain reasonable even with many subscribers
            assert result["throughput"] > 100  # > 100 ticks/second

            # Duration should not increase significantly with more subscribers
            assert result["duration"] < 0.7  # < 700ms for 500ms test (40% overhead max)
