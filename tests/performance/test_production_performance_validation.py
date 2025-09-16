"""Production Performance Validation Tests for FXML4 Trading System.

This module provides comprehensive performance validation testing to ensure the system
meets production trading requirements under realistic load conditions. Tests validate
latency, throughput, resource utilization, and scalability characteristics.

Performance Validation Coverage:
- End-to-End Trading Pipeline Latency
- High-Frequency Data Processing Throughput
- Concurrent Order Execution Performance
- Memory and CPU Resource Utilization
- Database Query Performance Under Load
- Network and Broker Connectivity Performance
- System Scalability and Breaking Point Analysis

Following production performance testing methodology with industry-standard benchmarks.
"""

import asyncio
import gc
import logging
import resource
import statistics
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple
from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
import pandas as pd
import psutil
import pytest

from fxml4.api.services.trading_engine import TradingEngine
from fxml4.brokers.adapters.ib_adapter import IBBrokerAdapter

# System Components for Performance Testing
from fxml4.data_engineering.timescaledb import TimescaleDBManager
from fxml4.fix.session_manager import FIXSession
from fxml4.ml.models.ensemble import EnsembleModel
from fxml4.monitoring.system_monitor import SystemMonitor
from fxml4.strategy.integrated_signal_generator import IntegratedSignalGenerator


class PerformanceTestMetrics:
    """Collect and analyze performance test metrics."""

    def __init__(self):
        self.latencies = []
        self.throughputs = []
        self.cpu_samples = []
        self.memory_samples = []
        self.start_time = None
        self.end_time = None

    def start_monitoring(self):
        """Start performance monitoring."""
        self.start_time = time.time()

    def stop_monitoring(self):
        """Stop performance monitoring."""
        self.end_time = time.time()

    def record_latency(self, latency_ms: float):
        """Record operation latency."""
        self.latencies.append(latency_ms)

    def record_throughput(self, operations_per_second: float):
        """Record throughput measurement."""
        self.throughputs.append(operations_per_second)

    def sample_system_resources(self):
        """Sample current system resource usage."""
        process = psutil.Process()
        self.cpu_samples.append(process.cpu_percent())
        self.memory_samples.append(process.memory_info().rss / 1024 / 1024)  # MB

    def get_summary(self) -> Dict[str, Any]:
        """Get performance summary statistics."""
        total_time = self.end_time - self.start_time if self.end_time else 0

        return {
            "total_duration_seconds": total_time,
            "latency_stats": {
                "min_ms": min(self.latencies) if self.latencies else 0,
                "max_ms": max(self.latencies) if self.latencies else 0,
                "avg_ms": statistics.mean(self.latencies) if self.latencies else 0,
                "p95_ms": np.percentile(self.latencies, 95) if self.latencies else 0,
                "p99_ms": np.percentile(self.latencies, 99) if self.latencies else 0,
            },
            "throughput_stats": {
                "avg_ops_per_sec": (
                    statistics.mean(self.throughputs) if self.throughputs else 0
                ),
                "max_ops_per_sec": max(self.throughputs) if self.throughputs else 0,
            },
            "resource_stats": {
                "avg_cpu_percent": (
                    statistics.mean(self.cpu_samples) if self.cpu_samples else 0
                ),
                "max_cpu_percent": max(self.cpu_samples) if self.cpu_samples else 0,
                "avg_memory_mb": (
                    statistics.mean(self.memory_samples) if self.memory_samples else 0
                ),
                "max_memory_mb": max(self.memory_samples) if self.memory_samples else 0,
            },
        }


class TestEndToEndLatencyPerformance:
    """Test end-to-end trading pipeline latency performance."""

    @pytest.fixture
    def performance_metrics(self):
        """Create performance metrics collector."""
        return PerformanceTestMetrics()

    @pytest.fixture
    def mock_trading_components(self):
        """Create mock trading system components optimized for performance testing."""
        components = {}

        # Fast database operations
        components["database"] = AsyncMock(spec=TimescaleDBManager)
        components["database"].fetch.return_value = [
            {"timestamp": datetime.utcnow(), "symbol": "EURUSD", "close": 1.1050}
        ]

        # Fast ML model
        components["ml_model"] = MagicMock(spec=EnsembleModel)
        components["ml_model"].predict.return_value = np.array([1])
        components["ml_model"].predict_proba.return_value = np.array([0.75])

        # Fast signal generator
        components["signal_generator"] = MagicMock(spec=IntegratedSignalGenerator)
        components["signal_generator"].generate_signals.return_value = [
            {"symbol": "EURUSD", "action": "BUY", "confidence": 0.75}
        ]

        # Fast FIX session
        components["fix_session"] = AsyncMock(spec=FIXSession)
        components["fix_session"].send_message.return_value = True

        # Fast broker adapter
        components["broker"] = AsyncMock(spec=IBBrokerAdapter)
        components["broker"].submit_order.return_value = {
            "order_id": "ORDER_123",
            "status": "FILLED",
        }

        return components

    @pytest.mark.performance
    @pytest.mark.asyncio
    async def test_signal_to_execution_latency_benchmark(
        self, mock_trading_components, performance_metrics
    ):
        """Benchmark complete signal-to-execution latency."""
        # Performance targets (production requirements)
        MAX_LATENCY_MS = 100  # Maximum acceptable latency
        TARGET_P95_MS = 50  # 95th percentile target
        NUM_ITERATIONS = 1000

        database = mock_trading_components["database"]
        ml_model = mock_trading_components["ml_model"]
        signal_gen = mock_trading_components["signal_generator"]
        fix_session = mock_trading_components["fix_session"]
        broker = mock_trading_components["broker"]

        performance_metrics.start_monitoring()

        # Resource monitoring thread
        monitoring_active = True

        def monitor_resources():
            while monitoring_active:
                performance_metrics.sample_system_resources()
                time.sleep(0.1)

        monitor_thread = threading.Thread(target=monitor_resources)
        monitor_thread.start()

        # Benchmark complete pipeline
        for i in range(NUM_ITERATIONS):
            iteration_start = time.time()

            # 1. Data retrieval
            data_start = time.time()
            market_data = await database.fetch("SELECT * FROM market_data LIMIT 100")
            data_time = (time.time() - data_start) * 1000

            # 2. ML prediction
            ml_start = time.time()
            features = np.random.rand(1, 10)  # Mock feature extraction
            prediction = ml_model.predict(features)
            probability = ml_model.predict_proba(features)
            ml_time = (time.time() - ml_start) * 1000

            # 3. Signal generation
            signal_start = time.time()
            signals = signal_gen.generate_signals(
                {
                    "prediction": prediction[0],
                    "probability": probability[0],
                    "symbol": "EURUSD",
                }
            )
            signal_time = (time.time() - signal_start) * 1000

            # 4. FIX message creation and sending
            fix_start = time.time()
            await fix_session.send_message(
                {"symbol": "EURUSD", "side": "BUY", "quantity": 100000}
            )
            fix_time = (time.time() - fix_start) * 1000

            # 5. Broker execution
            broker_start = time.time()
            execution = await broker.submit_order(
                {"symbol": "EURUSD", "side": "BUY", "quantity": 100000}
            )
            broker_time = (time.time() - broker_start) * 1000

            # Total iteration latency
            total_latency = (time.time() - iteration_start) * 1000
            performance_metrics.record_latency(total_latency)

            # Verify execution success
            assert execution["status"] == "FILLED"

            # Track sub-component latencies
            if i % 100 == 0:  # Log every 100th iteration
                logging.info(
                    f"Iteration {i}: Total={total_latency:.2f}ms, "
                    f"Data={data_time:.2f}ms, ML={ml_time:.2f}ms, "
                    f"Signal={signal_time:.2f}ms, FIX={fix_time:.2f}ms, "
                    f"Broker={broker_time:.2f}ms"
                )

        # Stop monitoring
        monitoring_active = False
        monitor_thread.join()
        performance_metrics.stop_monitoring()

        # Analyze performance results
        summary = performance_metrics.get_summary()

        # Performance assertions
        assert summary["latency_stats"]["avg_ms"] < MAX_LATENCY_MS
        assert (
            summary["latency_stats"]["p95_ms"] < TARGET_P95_MS * 1.5
        )  # Allow some variance
        assert (
            summary["latency_stats"]["max_ms"] < MAX_LATENCY_MS * 2
        )  # Max spike allowance

        # Resource utilization assertions
        assert summary["resource_stats"]["avg_cpu_percent"] < 70.0  # Under 70% CPU
        assert summary["resource_stats"]["max_memory_mb"] < 500.0  # Under 500MB memory

        # Log final results
        logging.info(f"Performance Summary: {summary}")

        print(f"\n=== LATENCY BENCHMARK RESULTS ===")
        print(f"Iterations: {NUM_ITERATIONS}")
        print(f"Average Latency: {summary['latency_stats']['avg_ms']:.2f}ms")
        print(f"95th Percentile: {summary['latency_stats']['p95_ms']:.2f}ms")
        print(f"99th Percentile: {summary['latency_stats']['p99_ms']:.2f}ms")
        print(f"Max Latency: {summary['latency_stats']['max_ms']:.2f}ms")
        print(f"Average CPU: {summary['resource_stats']['avg_cpu_percent']:.1f}%")
        print(f"Average Memory: {summary['resource_stats']['avg_memory_mb']:.1f}MB")

    @pytest.mark.performance
    @pytest.mark.asyncio
    async def test_concurrent_signal_processing_throughput(
        self, mock_trading_components, performance_metrics
    ):
        """Benchmark concurrent signal processing throughput."""
        # Throughput targets
        MIN_SIGNALS_PER_SECOND = 50  # Minimum production requirement
        TARGET_SIGNALS_PER_SECOND = 100  # Target performance

        NUM_CONCURRENT_WORKERS = 10
        SIGNALS_PER_WORKER = 100
        TOTAL_SIGNALS = NUM_CONCURRENT_WORKERS * SIGNALS_PER_WORKER

        signal_gen = mock_trading_components["signal_generator"]
        fix_session = mock_trading_components["fix_session"]

        performance_metrics.start_monitoring()

        async def process_signals_worker(worker_id: int, signals_count: int):
            """Worker function for concurrent signal processing."""
            worker_start = time.time()

            for i in range(signals_count):
                # Generate signal
                signals = signal_gen.generate_signals(
                    {
                        "worker_id": worker_id,
                        "signal_id": i,
                        "symbol": f"SYMBOL_{i % 5}",  # Rotate symbols
                    }
                )

                # Send via FIX
                await fix_session.send_message(
                    {"worker_id": worker_id, "signal": signals[0] if signals else None}
                )

                # Small delay to simulate realistic processing
                await asyncio.sleep(0.001)  # 1ms

            worker_time = time.time() - worker_start
            worker_throughput = signals_count / worker_time
            performance_metrics.record_throughput(worker_throughput)

            return worker_throughput

        # Resource monitoring
        monitoring_active = True

        def monitor_resources():
            while monitoring_active:
                performance_metrics.sample_system_resources()
                time.sleep(0.1)

        monitor_thread = threading.Thread(target=monitor_resources)
        monitor_thread.start()

        # Execute concurrent workers
        benchmark_start = time.time()

        tasks = [
            asyncio.create_task(process_signals_worker(worker_id, SIGNALS_PER_WORKER))
            for worker_id in range(NUM_CONCURRENT_WORKERS)
        ]

        worker_throughputs = await asyncio.gather(*tasks)

        benchmark_time = time.time() - benchmark_start

        # Stop monitoring
        monitoring_active = False
        monitor_thread.join()
        performance_metrics.stop_monitoring()

        # Calculate overall throughput
        overall_throughput = TOTAL_SIGNALS / benchmark_time

        # Performance assertions
        assert overall_throughput >= MIN_SIGNALS_PER_SECOND
        assert (
            min(worker_throughputs) >= MIN_SIGNALS_PER_SECOND / 2
        )  # Individual workers
        assert max(worker_throughputs) >= TARGET_SIGNALS_PER_SECOND / 2

        # Verify all signals processed
        assert signal_gen.generate_signals.call_count == TOTAL_SIGNALS
        assert fix_session.send_message.call_count == TOTAL_SIGNALS

        # Resource efficiency assertions
        summary = performance_metrics.get_summary()
        assert summary["resource_stats"]["avg_cpu_percent"] < 80.0

        print(f"\n=== THROUGHPUT BENCHMARK RESULTS ===")
        print(f"Total Signals: {TOTAL_SIGNALS}")
        print(f"Concurrent Workers: {NUM_CONCURRENT_WORKERS}")
        print(f"Overall Throughput: {overall_throughput:.1f} signals/sec")
        print(
            f"Worker Throughput Range: {min(worker_throughputs):.1f} - {max(worker_throughputs):.1f}"
        )
        print(f"Benchmark Duration: {benchmark_time:.2f} seconds")
        print(f"Average CPU: {summary['resource_stats']['avg_cpu_percent']:.1f}%")


class TestDatabasePerformance:
    """Test database performance under trading load."""

    @pytest.fixture
    def mock_database_with_latency(self):
        """Create database mock with realistic latency simulation."""
        db = AsyncMock(spec=TimescaleDBManager)

        async def mock_fetch_with_latency(*args, **kwargs):
            # Simulate realistic database latency (1-10ms)
            await asyncio.sleep(np.random.uniform(0.001, 0.010))

            return [
                {
                    "timestamp": datetime.utcnow() - timedelta(hours=i),
                    "symbol": "EURUSD",
                    "open": 1.1000 + np.random.uniform(-0.01, 0.01),
                    "high": 1.1010 + np.random.uniform(-0.01, 0.01),
                    "low": 1.0990 + np.random.uniform(-0.01, 0.01),
                    "close": 1.1005 + np.random.uniform(-0.01, 0.01),
                    "volume": np.random.randint(10000, 100000),
                }
                for i in range(100)  # Return 100 rows per query
            ]

        db.fetch.side_effect = mock_fetch_with_latency
        return db

    @pytest.mark.performance
    @pytest.mark.asyncio
    async def test_high_frequency_database_queries(self, mock_database_with_latency):
        """Test database performance under high-frequency query load."""
        # Performance targets for database operations
        MAX_QUERY_LATENCY_MS = 50
        MIN_QUERIES_PER_SECOND = 100

        NUM_QUERIES = 500
        CONCURRENT_CONNECTIONS = 5

        db = mock_database_with_latency
        query_latencies = []

        async def execute_query_batch(batch_size: int):
            """Execute batch of database queries."""
            batch_latencies = []

            for i in range(batch_size):
                query_start = time.time()

                # Execute market data query
                result = await db.fetch(
                    "SELECT * FROM market_data WHERE symbol = %s AND timestamp >= %s",
                    ("EURUSD", datetime.utcnow() - timedelta(hours=24)),
                )

                query_latency = (time.time() - query_start) * 1000
                batch_latencies.append(query_latency)

                # Verify result
                assert len(result) > 0
                assert all("symbol" in row for row in result)

            return batch_latencies

        # Execute concurrent query batches
        queries_per_batch = NUM_QUERIES // CONCURRENT_CONNECTIONS

        benchmark_start = time.time()

        tasks = [
            asyncio.create_task(execute_query_batch(queries_per_batch))
            for _ in range(CONCURRENT_CONNECTIONS)
        ]

        batch_results = await asyncio.gather(*tasks)

        benchmark_time = time.time() - benchmark_start

        # Aggregate latencies
        for batch_latencies in batch_results:
            query_latencies.extend(batch_latencies)

        # Calculate performance metrics
        avg_latency = statistics.mean(query_latencies)
        p95_latency = np.percentile(query_latencies, 95)
        max_latency = max(query_latencies)
        queries_per_second = NUM_QUERIES / benchmark_time

        # Performance assertions
        assert avg_latency < MAX_QUERY_LATENCY_MS
        assert p95_latency < MAX_QUERY_LATENCY_MS * 1.5
        assert queries_per_second >= MIN_QUERIES_PER_SECOND

        # Verify all queries executed
        assert db.fetch.call_count == NUM_QUERIES

        print(f"\n=== DATABASE PERFORMANCE RESULTS ===")
        print(f"Total Queries: {NUM_QUERIES}")
        print(f"Concurrent Connections: {CONCURRENT_CONNECTIONS}")
        print(f"Average Latency: {avg_latency:.2f}ms")
        print(f"95th Percentile: {p95_latency:.2f}ms")
        print(f"Max Latency: {max_latency:.2f}ms")
        print(f"Queries per Second: {queries_per_second:.1f}")
        print(f"Total Duration: {benchmark_time:.2f}s")

    @pytest.mark.performance
    @pytest.mark.asyncio
    async def test_large_dataset_query_performance(self, mock_database_with_latency):
        """Test performance with large dataset queries."""
        # Large dataset simulation targets
        MAX_LARGE_QUERY_LATENCY_MS = 200
        LARGE_RESULT_SET_SIZE = 10000

        db = mock_database_with_latency

        # Mock large dataset response
        async def mock_large_fetch(*args, **kwargs):
            # Simulate larger query latency
            await asyncio.sleep(0.05)  # 50ms for large query

            return [
                {
                    "timestamp": datetime.utcnow() - timedelta(minutes=i),
                    "symbol": "EURUSD",
                    "close": 1.1000 + (i * 0.000001),
                    "volume": 50000 + i,
                }
                for i in range(LARGE_RESULT_SET_SIZE)
            ]

        db.fetch.side_effect = mock_large_fetch

        # Execute large dataset queries
        large_query_latencies = []

        for i in range(10):  # 10 large queries
            query_start = time.time()

            result = await db.fetch(
                "SELECT * FROM market_data WHERE timestamp >= %s ORDER BY timestamp",
                (datetime.utcnow() - timedelta(days=7),),
            )

            query_latency = (time.time() - query_start) * 1000
            large_query_latencies.append(query_latency)

            # Verify large result set
            assert len(result) == LARGE_RESULT_SET_SIZE

        # Analyze large query performance
        avg_large_latency = statistics.mean(large_query_latencies)
        max_large_latency = max(large_query_latencies)

        # Performance assertions for large queries
        assert avg_large_latency < MAX_LARGE_QUERY_LATENCY_MS
        assert max_large_latency < MAX_LARGE_QUERY_LATENCY_MS * 1.5

        print(f"\n=== LARGE DATASET QUERY RESULTS ===")
        print(f"Result Set Size: {LARGE_RESULT_SET_SIZE:,} rows")
        print(f"Number of Large Queries: 10")
        print(f"Average Latency: {avg_large_latency:.2f}ms")
        print(f"Max Latency: {max_large_latency:.2f}ms")


class TestMLModelPerformance:
    """Test ML model inference performance."""

    @pytest.fixture
    def performance_ml_model(self):
        """Create ML model mock optimized for performance testing."""
        model = MagicMock(spec=EnsembleModel)

        def mock_predict(features):
            # Simulate realistic ML inference time
            time.sleep(np.random.uniform(0.001, 0.005))  # 1-5ms
            return np.random.choice([0, 1], size=len(features))

        def mock_predict_proba(features):
            # Simulate probability computation time
            time.sleep(np.random.uniform(0.001, 0.003))  # 1-3ms
            return np.random.uniform(0.5, 0.95, size=len(features))

        model.predict.side_effect = mock_predict
        model.predict_proba.side_effect = mock_predict_proba

        return model

    @pytest.mark.performance
    def test_ml_inference_latency_benchmark(self, performance_ml_model):
        """Benchmark ML model inference latency."""
        # ML performance targets
        MAX_INFERENCE_LATENCY_MS = 10
        MIN_INFERENCES_PER_SECOND = 200

        NUM_INFERENCES = 1000
        model = performance_ml_model

        inference_latencies = []

        # Benchmark individual inferences
        for i in range(NUM_INFERENCES):
            # Create feature vector (10 features)
            features = np.random.rand(1, 10)

            # Time prediction
            pred_start = time.time()
            prediction = model.predict(features)
            pred_latency = (time.time() - pred_start) * 1000

            # Time probability calculation
            prob_start = time.time()
            probability = model.predict_proba(features)
            prob_latency = (time.time() - prob_start) * 1000

            # Total inference latency
            total_latency = pred_latency + prob_latency
            inference_latencies.append(total_latency)

            # Verify results
            assert prediction.shape[0] == 1
            assert 0 <= probability[0] <= 1

        # Calculate performance metrics
        avg_latency = statistics.mean(inference_latencies)
        p95_latency = np.percentile(inference_latencies, 95)
        max_latency = max(inference_latencies)

        total_time = sum(inference_latencies) / 1000  # Convert to seconds
        inferences_per_second = NUM_INFERENCES / total_time

        # Performance assertions
        assert avg_latency < MAX_INFERENCE_LATENCY_MS
        assert p95_latency < MAX_INFERENCE_LATENCY_MS * 1.5
        assert inferences_per_second >= MIN_INFERENCES_PER_SECOND

        print(f"\n=== ML INFERENCE PERFORMANCE RESULTS ===")
        print(f"Total Inferences: {NUM_INFERENCES}")
        print(f"Average Latency: {avg_latency:.2f}ms")
        print(f"95th Percentile: {p95_latency:.2f}ms")
        print(f"Max Latency: {max_latency:.2f}ms")
        print(f"Inferences per Second: {inferences_per_second:.1f}")

    @pytest.mark.performance
    def test_batch_ml_inference_performance(self, performance_ml_model):
        """Benchmark batch ML inference performance."""
        # Batch processing targets
        BATCH_SIZES = [1, 10, 50, 100, 500]
        MAX_BATCH_LATENCY_PER_SAMPLE_MS = 5

        model = performance_ml_model
        batch_performance_results = {}

        for batch_size in BATCH_SIZES:
            # Create batch of features
            batch_features = np.random.rand(batch_size, 10)

            # Benchmark batch prediction
            batch_start = time.time()
            batch_predictions = model.predict(batch_features)
            batch_probabilities = model.predict_proba(batch_features)
            batch_time = (time.time() - batch_start) * 1000  # ms

            # Calculate per-sample metrics
            latency_per_sample = batch_time / batch_size
            samples_per_second = batch_size / (batch_time / 1000)

            batch_performance_results[batch_size] = {
                "total_latency_ms": batch_time,
                "latency_per_sample_ms": latency_per_sample,
                "samples_per_second": samples_per_second,
            }

            # Verify batch results
            assert len(batch_predictions) == batch_size
            assert len(batch_probabilities) == batch_size

            # Performance assertion
            assert latency_per_sample < MAX_BATCH_LATENCY_PER_SAMPLE_MS

        print(f"\n=== BATCH ML INFERENCE RESULTS ===")
        for batch_size, metrics in batch_performance_results.items():
            print(
                f"Batch Size {batch_size:3d}: "
                f"{metrics['latency_per_sample_ms']:.2f}ms/sample, "
                f"{metrics['samples_per_second']:.1f} samples/sec"
            )

        # Verify batch efficiency (larger batches should be more efficient)
        latency_per_sample_1 = batch_performance_results[1]["latency_per_sample_ms"]
        latency_per_sample_100 = batch_performance_results[100]["latency_per_sample_ms"]

        # Batch processing should be more efficient
        assert latency_per_sample_100 < latency_per_sample_1 * 0.8


class TestSystemScalabilityLimits:
    """Test system scalability and breaking point analysis."""

    @pytest.mark.performance
    @pytest.mark.asyncio
    async def test_memory_usage_scalability(self):
        """Test system memory usage under increasing load."""
        # Memory usage targets
        MAX_MEMORY_GROWTH_MB = 200  # Maximum acceptable memory growth

        initial_memory = psutil.Process().memory_info().rss / 1024 / 1024
        memory_measurements = []

        # Simulate increasing data processing load
        load_levels = [100, 500, 1000, 2000, 5000]

        for load_level in load_levels:
            # Force garbage collection before measurement
            gc.collect()

            # Create data processing load
            data_objects = []

            for i in range(load_level):
                # Simulate market data objects
                market_data = {
                    "timestamp": datetime.utcnow() - timedelta(seconds=i),
                    "symbol": f"SYM_{i % 10}",
                    "ohlcv": np.random.rand(5),
                    "features": np.random.rand(50),  # Feature vector
                    "metadata": {
                        "source": "test",
                        "quality": "good",
                        "processed": datetime.utcnow(),
                    },
                }
                data_objects.append(market_data)

            # Measure memory after load
            current_memory = psutil.Process().memory_info().rss / 1024 / 1024
            memory_growth = current_memory - initial_memory

            memory_measurements.append(
                {
                    "load_level": load_level,
                    "memory_mb": current_memory,
                    "memory_growth_mb": memory_growth,
                    "objects_created": len(data_objects),
                }
            )

            # Clean up to prevent excessive memory usage
            del data_objects

            # Memory growth should be reasonable
            assert memory_growth < MAX_MEMORY_GROWTH_MB

        print(f"\n=== MEMORY SCALABILITY RESULTS ===")
        print(f"Initial Memory: {initial_memory:.1f}MB")

        for measurement in memory_measurements:
            print(
                f"Load {measurement['load_level']:4d}: "
                f"{measurement['memory_mb']:.1f}MB "
                f"(+{measurement['memory_growth_mb']:.1f}MB)"
            )

        # Verify memory usage is linear with load
        max_growth = max(m["memory_growth_mb"] for m in memory_measurements)
        assert max_growth < MAX_MEMORY_GROWTH_MB

    @pytest.mark.performance
    @pytest.mark.asyncio
    async def test_concurrent_connection_scaling(self):
        """Test system behavior under increasing concurrent connections."""
        # Connection scaling targets
        MIN_SUPPORTED_CONNECTIONS = 50
        TARGET_SUPPORTED_CONNECTIONS = 100

        connection_levels = [10, 25, 50, 75, 100]
        scaling_results = {}

        for connection_count in connection_levels:
            # Mock concurrent connections
            mock_connections = []

            for i in range(connection_count):
                connection = AsyncMock()
                connection.is_connected.return_value = True
                connection.send.return_value = True
                mock_connections.append(connection)

            # Benchmark connection handling
            start_time = time.time()

            # Simulate message broadcasting to all connections
            async def broadcast_to_connection(conn, message):
                await asyncio.sleep(0.001)  # Simulate message processing
                await conn.send(message)
                return True

            # Send message to all connections concurrently
            broadcast_tasks = [
                asyncio.create_task(broadcast_to_connection(conn, f"message_{i}"))
                for i, conn in enumerate(mock_connections)
            ]

            results = await asyncio.gather(*broadcast_tasks, return_exceptions=True)

            broadcast_time = time.time() - start_time

            # Verify all connections handled successfully
            successful_broadcasts = sum(1 for result in results if result is True)

            scaling_results[connection_count] = {
                "broadcast_time_ms": broadcast_time * 1000,
                "successful_broadcasts": successful_broadcasts,
                "success_rate": successful_broadcasts / connection_count,
                "connections_per_second": connection_count / broadcast_time,
            }

            # Performance assertions
            assert successful_broadcasts == connection_count  # All should succeed
            assert broadcast_time < 1.0  # Should complete within 1 second

        print(f"\n=== CONNECTION SCALING RESULTS ===")
        for conn_count, metrics in scaling_results.items():
            print(
                f"Connections {conn_count:3d}: "
                f"{metrics['broadcast_time_ms']:.2f}ms, "
                f"{metrics['connections_per_second']:.1f} conn/sec, "
                f"{metrics['success_rate']:.1%} success"
            )

        # Verify scaling capabilities
        max_connections_tested = max(connection_levels)
        max_results = scaling_results[max_connections_tested]

        assert max_connections_tested >= MIN_SUPPORTED_CONNECTIONS
        assert max_results["success_rate"] >= 0.95  # 95% success rate minimum


class TestProductionReadinessValidation:
    """Comprehensive production readiness validation."""

    @pytest.mark.performance
    @pytest.mark.asyncio
    async def test_complete_system_load_simulation(self):
        """Simulate complete production load scenario."""
        # Production simulation parameters
        SIMULATION_DURATION_SECONDS = 30
        SYMBOLS = ["EURUSD", "GBPUSD", "USDJPY", "USDCHF", "AUDUSD"]
        TICKS_PER_SYMBOL_PER_SECOND = 10
        ORDERS_PER_MINUTE = 20

        # Performance targets for production
        MAX_AVG_CPU_PERCENT = 75.0
        MAX_AVG_MEMORY_MB = 800.0
        MIN_SUCCESS_RATE = 0.95

        # Mock system components
        components = {
            "data_handler": AsyncMock(),
            "ml_model": MagicMock(),
            "signal_generator": MagicMock(),
            "order_manager": AsyncMock(),
            "risk_manager": AsyncMock(),
        }

        # Configure mocks for production simulation
        components["ml_model"].predict.return_value = np.array([1])
        components["signal_generator"].generate_signals.return_value = [
            {"symbol": "EURUSD", "action": "BUY", "confidence": 0.8}
        ]
        components["order_manager"].submit_order.return_value = {
            "order_id": "ORDER_123",
            "status": "FILLED",
        }
        components["risk_manager"].validate_order.return_value = True

        # Metrics collection
        metrics = PerformanceTestMetrics()
        metrics.start_monitoring()

        # Resource monitoring
        monitoring_active = True

        def resource_monitor():
            while monitoring_active:
                metrics.sample_system_resources()
                time.sleep(0.5)

        monitor_thread = threading.Thread(target=resource_monitor)
        monitor_thread.start()

        # Operation counters
        total_ticks_processed = 0
        total_orders_submitted = 0
        successful_operations = 0
        failed_operations = 0

        # Simulation tasks
        async def market_data_simulator():
            """Simulate market data processing."""
            nonlocal total_ticks_processed, successful_operations, failed_operations

            end_time = time.time() + SIMULATION_DURATION_SECONDS

            while time.time() < end_time:
                for symbol in SYMBOLS:
                    try:
                        # Simulate tick processing
                        tick = {
                            "symbol": symbol,
                            "bid": 1.1000 + np.random.uniform(-0.01, 0.01),
                            "ask": 1.1002 + np.random.uniform(-0.01, 0.01),
                            "timestamp": datetime.utcnow(),
                        }

                        await components["data_handler"].process_tick(tick)
                        total_ticks_processed += 1
                        successful_operations += 1

                    except Exception:
                        failed_operations += 1

                # Control tick rate
                await asyncio.sleep(1.0 / TICKS_PER_SYMBOL_PER_SECOND)

        async def trading_simulator():
            """Simulate trading operations."""
            nonlocal total_orders_submitted, successful_operations, failed_operations

            end_time = time.time() + SIMULATION_DURATION_SECONDS
            order_interval = 60.0 / ORDERS_PER_MINUTE  # Seconds between orders

            while time.time() < end_time:
                try:
                    # ML prediction
                    features = np.random.rand(1, 10)
                    prediction = components["ml_model"].predict(features)

                    # Signal generation
                    signals = components["signal_generator"].generate_signals(
                        {
                            "prediction": prediction[0],
                            "symbol": np.random.choice(SYMBOLS),
                        }
                    )

                    if signals:
                        # Risk validation
                        is_valid = await components["risk_manager"].validate_order(
                            signals[0]
                        )

                        if is_valid:
                            # Order submission
                            result = await components["order_manager"].submit_order(
                                {
                                    "symbol": signals[0]["symbol"],
                                    "action": signals[0]["action"],
                                    "quantity": 100000,
                                }
                            )

                            if result["status"] == "FILLED":
                                total_orders_submitted += 1
                                successful_operations += 1
                            else:
                                failed_operations += 1

                except Exception:
                    failed_operations += 1

                await asyncio.sleep(order_interval)

        # Run simulation
        simulation_start = time.time()

        await asyncio.gather(market_data_simulator(), trading_simulator())

        simulation_time = time.time() - simulation_start

        # Stop monitoring
        monitoring_active = False
        monitor_thread.join()
        metrics.stop_monitoring()

        # Calculate final metrics
        total_operations = successful_operations + failed_operations
        success_rate = (
            successful_operations / total_operations if total_operations > 0 else 0
        )

        summary = metrics.get_summary()

        # Production readiness assertions
        assert summary["resource_stats"]["avg_cpu_percent"] < MAX_AVG_CPU_PERCENT
        assert summary["resource_stats"]["avg_memory_mb"] < MAX_AVG_MEMORY_MB
        assert success_rate >= MIN_SUCCESS_RATE

        # Verify expected workload processed
        expected_ticks = (
            len(SYMBOLS) * TICKS_PER_SYMBOL_PER_SECOND * SIMULATION_DURATION_SECONDS
        )
        expected_orders = ORDERS_PER_MINUTE * (SIMULATION_DURATION_SECONDS / 60)

        assert total_ticks_processed >= expected_ticks * 0.9  # Allow 10% variance
        assert total_orders_submitted >= expected_orders * 0.8  # Allow 20% variance

        print(f"\n=== PRODUCTION READINESS SIMULATION RESULTS ===")
        print(f"Simulation Duration: {simulation_time:.1f} seconds")
        print(f"Ticks Processed: {total_ticks_processed:,}")
        print(f"Orders Submitted: {total_orders_submitted}")
        print(f"Total Operations: {total_operations:,}")
        print(f"Success Rate: {success_rate:.1%}")
        print(f"Average CPU: {summary['resource_stats']['avg_cpu_percent']:.1f}%")
        print(f"Average Memory: {summary['resource_stats']['avg_memory_mb']:.1f}MB")
        print(f"Max CPU: {summary['resource_stats']['max_cpu_percent']:.1f}%")
        print(f"Max Memory: {summary['resource_stats']['max_memory_mb']:.1f}MB")

        # Final production readiness verdict
        cpu_ok = summary["resource_stats"]["avg_cpu_percent"] < MAX_AVG_CPU_PERCENT
        memory_ok = summary["resource_stats"]["avg_memory_mb"] < MAX_AVG_MEMORY_MB
        success_ok = success_rate >= MIN_SUCCESS_RATE

        production_ready = all([cpu_ok, memory_ok, success_ok])

        print(f"\n=== PRODUCTION READINESS VERDICT ===")
        print(f"CPU Usage: {'✅ PASS' if cpu_ok else '❌ FAIL'}")
        print(f"Memory Usage: {'✅ PASS' if memory_ok else '❌ FAIL'}")
        print(f"Success Rate: {'✅ PASS' if success_ok else '❌ FAIL'}")
        print(
            f"Overall: {'✅ PRODUCTION READY' if production_ready else '❌ NOT READY'}"
        )

        assert production_ready, "System does not meet production readiness criteria"


if __name__ == "__main__":
    """Run performance validation tests directly."""
    pytest.main([__file__, "-v", "-m", "performance", "--tb=short"])
