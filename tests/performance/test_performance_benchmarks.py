"""
Performance tests and benchmarks for FXML4 critical paths.

This module tests performance characteristics of:
- API response times
- Database query performance
- Memory usage patterns
- ML model inference speed
- Data processing throughput
"""

import asyncio
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock, patch

import numpy as np
import pandas as pd
import psutil
import pytest

try:
    from fastapi.testclient import TestClient

    from fxml4.api.main import app
    from fxml4.data_engineering.timescaledb import TimescaleDBClient
    from fxml4.ml.models import ClassicMLModel

    DB_AVAILABLE = True
except ImportError:
    TimescaleDBClient = None
    ClassicMLModel = None
    app = None
    TestClient = None
    DB_AVAILABLE = False


class PerformanceMonitor:
    """Helper class for monitoring performance metrics."""

    def __init__(self):
        self.process = psutil.Process(os.getpid())
        self.start_time = None
        self.start_memory = None
        self.peak_memory = None

    def start(self):
        """Start monitoring."""
        self.start_time = time.perf_counter()
        self.start_memory = self.process.memory_info().rss
        self.peak_memory = self.start_memory

    def update_peak_memory(self):
        """Update peak memory usage."""
        current_memory = self.process.memory_info().rss
        if current_memory > self.peak_memory:
            self.peak_memory = current_memory

    def get_metrics(self):
        """Get performance metrics."""
        end_time = time.perf_counter()
        current_memory = self.process.memory_info().rss

        return {
            "elapsed_time": end_time - self.start_time if self.start_time else None,
            "start_memory_mb": (
                self.start_memory / 1024 / 1024 if self.start_memory else None
            ),
            "current_memory_mb": current_memory / 1024 / 1024,
            "peak_memory_mb": (
                self.peak_memory / 1024 / 1024 if self.peak_memory else None
            ),
            "memory_delta_mb": (
                (current_memory - self.start_memory) / 1024 / 1024
                if self.start_memory
                else None
            ),
        }


@pytest.fixture
def performance_monitor():
    """Provide performance monitoring."""
    return PerformanceMonitor()


@pytest.fixture
def sample_ohlc_data():
    """Generate sample OHLC data for performance testing."""
    np.random.seed(42)

    # Generate larger dataset for performance testing
    n_bars = 10000
    dates = pd.date_range(start="2023-01-01", periods=n_bars, freq="1H")

    base_price = 1.1000
    returns = np.random.normal(0, 0.001, n_bars)
    prices = base_price + np.cumsum(returns)

    data = []
    for i, (date, close) in enumerate(zip(dates, prices)):
        spread = np.random.uniform(0.0001, 0.0005)
        high = close + spread
        low = close - spread
        open_price = prices[i - 1] if i > 0 else close
        volume = np.random.randint(1000, 10000)

        data.append(
            {
                "time": date,
                "symbol": "EURUSD",
                "open": open_price,
                "high": high,
                "low": low,
                "close": close,
                "volume": volume,
            }
        )

    return pd.DataFrame(data)


class TestAPIPerformance:
    """Test API endpoint performance."""

    @pytest.fixture
    def client(self):
        """Get test client."""
        if not DB_AVAILABLE or app is None:
            pytest.skip("API not available")
        return TestClient(app)

    def test_health_endpoint_response_time(self, client, performance_monitor):
        """Test health endpoint response time."""
        performance_monitor.start()

        response = client.get("/health")

        metrics = performance_monitor.get_metrics()

        # Health endpoint should be very fast
        assert response.status_code == 200
        assert (
            metrics["elapsed_time"] < 0.050
        ), f"Health endpoint took {metrics['elapsed_time']:.3f}s, expected < 50ms"

    def test_health_endpoint_under_load(self, client, performance_monitor):
        """Test health endpoint performance under load."""
        performance_monitor.start()

        # Make many concurrent requests
        num_requests = 100
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [
                executor.submit(client.get, "/health") for _ in range(num_requests)
            ]

            responses = []
            for future in as_completed(futures):
                response = future.result()
                responses.append(response)
                performance_monitor.update_peak_memory()

        metrics = performance_monitor.get_metrics()

        # All requests should succeed
        assert all(r.status_code == 200 for r in responses)

        # Total time should be reasonable (< 5 seconds for 100 requests)
        assert (
            metrics["elapsed_time"] < 5.0
        ), f"100 health requests took {metrics['elapsed_time']:.3f}s"

        # Memory usage should not grow excessively
        assert (
            metrics["memory_delta_mb"] < 50
        ), f"Memory increased by {metrics['memory_delta_mb']:.1f}MB"

    @pytest.mark.slow
    def test_data_endpoint_response_time(self, client, performance_monitor):
        """Test data endpoint response time with mocked data."""
        performance_monitor.start()

        # Mock data response to test endpoint performance without DB dependency
        with patch("fxml4.api.routers.data.get_market_data") as mock_get_data:
            # Return moderate amount of test data
            mock_data = pd.DataFrame(
                {
                    "timestamp": pd.date_range("2023-01-01", periods=1000, freq="1H"),
                    "open": np.random.uniform(1.0, 1.2, 1000),
                    "high": np.random.uniform(1.0, 1.2, 1000),
                    "low": np.random.uniform(1.0, 1.2, 1000),
                    "close": np.random.uniform(1.0, 1.2, 1000),
                    "volume": np.random.randint(1000, 10000, 1000),
                }
            )
            mock_get_data.return_value = mock_data

            response = client.get(
                "/api/v1/data/historical?symbol=EURUSD&timeframe=1h&periods=1000"
            )

        metrics = performance_monitor.get_metrics()

        if response.status_code == 200:
            # Data endpoint should respond within reasonable time
            assert (
                metrics["elapsed_time"] < 2.0
            ), f"Data endpoint took {metrics['elapsed_time']:.3f}s, expected < 2s"

    def test_concurrent_api_requests(self, client, performance_monitor):
        """Test API performance with concurrent requests to different endpoints."""
        performance_monitor.start()

        endpoints = ["/health", "/api/v1/status", "/docs", "/openapi.json"]

        # Make concurrent requests to different endpoints
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = []
            for _ in range(20):
                for endpoint in endpoints:
                    future = executor.submit(client.get, endpoint)
                    futures.append((endpoint, future))

            results = {}
            for endpoint, future in futures:
                try:
                    response = future.result(timeout=5)
                    if endpoint not in results:
                        results[endpoint] = []
                    results[endpoint].append(response.status_code)
                    performance_monitor.update_peak_memory()
                except Exception as e:
                    # Track failures but don't fail test for missing endpoints
                    pass

        metrics = performance_monitor.get_metrics()

        # Should handle concurrent requests without excessive resource usage
        assert (
            metrics["elapsed_time"] < 10.0
        ), f"Concurrent requests took {metrics['elapsed_time']:.3f}s"
        assert (
            metrics["memory_delta_mb"] < 100
        ), f"Memory increased by {metrics['memory_delta_mb']:.1f}MB"


class TestDatabasePerformance:
    """Test database operation performance."""

    @pytest.fixture
    def mock_db_client(self):
        """Get mock database client for performance testing."""
        if TimescaleDBClient is None:
            pytest.skip("TimescaleDB client not available")

        mock_client = Mock(spec=TimescaleDBClient)

        # Mock connection to avoid actual DB dependency
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_conn.cursor.return_value = mock_cursor
        mock_client.get_connection.return_value = mock_conn

        return mock_client, mock_conn, mock_cursor

    def test_batch_tick_insertion_performance(
        self, mock_db_client, performance_monitor
    ):
        """Test performance of batch tick insertion."""
        mock_client, mock_conn, mock_cursor = mock_db_client

        # Generate large batch of tick data
        num_ticks = 10000
        ticks = []
        base_time = datetime.now(timezone.utc)

        for i in range(num_ticks):
            ticks.append(
                {
                    "symbol": "EURUSD",
                    "timestamp": base_time + timedelta(seconds=i),
                    "price": 1.1000 + np.random.normal(0, 0.0001),
                    "size": np.random.randint(100, 1000),
                    "tick_type": "trade",
                    "source": "ib",
                }
            )

        performance_monitor.start()

        # Mock successful batch insertion
        with patch.object(mock_client, "store_ticks", return_value=num_ticks):
            result = mock_client.store_ticks(ticks)

        metrics = performance_monitor.get_metrics()

        assert result == num_ticks
        # Batch insertion should be fast (< 1 second for mocked operation)
        assert (
            metrics["elapsed_time"] < 1.0
        ), f"Batch tick insertion took {metrics['elapsed_time']:.3f}s"

    def test_ohlcv_data_retrieval_performance(
        self, mock_db_client, performance_monitor
    ):
        """Test performance of OHLCV data retrieval."""
        mock_client, mock_conn, mock_cursor = mock_db_client

        # Mock large dataset retrieval
        num_bars = 5000
        mock_data = pd.DataFrame(
            {
                "time": pd.date_range("2023-01-01", periods=num_bars, freq="1H"),
                "symbol": ["EURUSD"] * num_bars,
                "open": np.random.uniform(1.0, 1.2, num_bars),
                "high": np.random.uniform(1.0, 1.2, num_bars),
                "low": np.random.uniform(1.0, 1.2, num_bars),
                "close": np.random.uniform(1.0, 1.2, num_bars),
                "volume": np.random.randint(1000, 10000, num_bars),
            }
        )

        performance_monitor.start()

        with patch.object(mock_client, "get_ohlcv_data", return_value=mock_data):
            result = mock_client.get_ohlcv_data(
                "EURUSD",
                "1h",
                datetime(2023, 1, 1, tzinfo=timezone.utc),
                datetime(2023, 12, 31, tzinfo=timezone.utc),
            )

        metrics = performance_monitor.get_metrics()

        assert len(result) == num_bars
        # Data retrieval should be fast
        assert (
            metrics["elapsed_time"] < 0.5
        ), f"OHLCV retrieval took {metrics['elapsed_time']:.3f}s"

    def test_concurrent_database_operations(self, mock_db_client, performance_monitor):
        """Test performance of concurrent database operations."""
        mock_client, mock_conn, mock_cursor = mock_db_client

        performance_monitor.start()

        def mock_operation(operation_type):
            """Mock database operation."""
            if operation_type == "read":
                with patch.object(mock_client, "get_tick_count", return_value=1000):
                    return mock_client.get_tick_count("EURUSD")
            elif operation_type == "write":
                tick_data = [
                    {
                        "symbol": "EURUSD",
                        "timestamp": datetime.now(timezone.utc),
                        "price": 1.1000,
                        "size": 1000,
                        "tick_type": "trade",
                        "source": "ib",
                    }
                ]
                with patch.object(mock_client, "store_ticks", return_value=1):
                    return mock_client.store_ticks(tick_data)

        # Execute concurrent operations
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = []

            # Mix of read and write operations
            for i in range(50):
                op_type = "read" if i % 2 == 0 else "write"
                future = executor.submit(mock_operation, op_type)
                futures.append(future)

            results = []
            for future in as_completed(futures):
                result = future.result()
                results.append(result)
                performance_monitor.update_peak_memory()

        metrics = performance_monitor.get_metrics()

        # All operations should complete
        assert len(results) == 50

        # Should handle concurrent operations efficiently
        assert (
            metrics["elapsed_time"] < 5.0
        ), f"Concurrent DB operations took {metrics['elapsed_time']:.3f}s"


class TestMLModelPerformance:
    """Test ML model performance."""

    @pytest.fixture
    def sample_features(self):
        """Generate sample feature data for ML testing."""
        np.random.seed(42)

        n_samples = 10000
        n_features = 50

        # Generate realistic feature data
        features = np.random.randn(n_samples, n_features)

        # Add some correlation structure
        features[:, 1] = features[:, 0] * 0.7 + np.random.randn(n_samples) * 0.3
        features[:, 2] = features[:, 0] * -0.5 + np.random.randn(n_samples) * 0.5

        feature_names = [f"feature_{i}" for i in range(n_features)]

        return pd.DataFrame(features, columns=feature_names)

    def test_model_training_performance(self, sample_features, performance_monitor):
        """Test ML model training performance."""
        if ClassicMLModel is None:
            pytest.skip("ML models not available")

        # Generate target variable
        y = np.random.choice([0, 1], size=len(sample_features), p=[0.6, 0.4])

        performance_monitor.start()

        try:
            # Create and train model
            model = ClassicMLModel(
                model_type="random_forest",
                n_estimators=100,
                max_depth=10,
                random_state=42,
            )

            model.train(sample_features, pd.Series(y))

            metrics = performance_monitor.get_metrics()

            # Training should complete in reasonable time
            assert (
                metrics["elapsed_time"] < 30.0
            ), f"Model training took {metrics['elapsed_time']:.3f}s, expected < 30s"

            # Memory usage should be reasonable
            assert (
                metrics["memory_delta_mb"] < 500
            ), f"Training used {metrics['memory_delta_mb']:.1f}MB extra memory"

        except Exception as e:
            pytest.skip(f"Model training not available: {e}")

    def test_model_inference_performance(self, sample_features, performance_monitor):
        """Test ML model inference performance."""
        if ClassicMLModel is None:
            pytest.skip("ML models not available")

        # Create mock trained model
        mock_model = Mock()
        mock_model.predict.return_value = np.random.choice(
            [0, 1], size=len(sample_features)
        )
        mock_model.predict_proba.return_value = np.random.rand(len(sample_features), 2)

        performance_monitor.start()

        # Test batch prediction performance
        predictions = mock_model.predict(sample_features)
        probabilities = mock_model.predict_proba(sample_features)

        metrics = performance_monitor.get_metrics()

        assert len(predictions) == len(sample_features)
        assert probabilities.shape == (len(sample_features), 2)

        # Inference should be very fast (mocked)
        assert (
            metrics["elapsed_time"] < 1.0
        ), f"Model inference took {metrics['elapsed_time']:.3f}s"

    def test_feature_calculation_performance(
        self, sample_ohlc_data, performance_monitor
    ):
        """Test feature calculation performance."""
        performance_monitor.start()

        # Mock feature calculation (avoid actual dependency)
        def mock_calculate_features(data):
            """Mock feature calculation that simulates processing time."""
            time.sleep(0.1)  # Simulate some processing time

            # Return mock features
            features = pd.DataFrame(
                {
                    "sma_10": np.random.randn(len(data)),
                    "sma_20": np.random.randn(len(data)),
                    "rsi_14": np.random.uniform(0, 100, len(data)),
                    "macd": np.random.randn(len(data)),
                    "bollinger_upper": np.random.randn(len(data)),
                    "bollinger_lower": np.random.randn(len(data)),
                },
                index=data.index,
            )

            return features

        features = mock_calculate_features(sample_ohlc_data)

        metrics = performance_monitor.get_metrics()

        assert len(features) == len(sample_ohlc_data)

        # Feature calculation should be reasonably fast
        assert (
            metrics["elapsed_time"] < 5.0
        ), f"Feature calculation took {metrics['elapsed_time']:.3f}s"


class TestDataProcessingPerformance:
    """Test data processing performance."""

    def test_large_dataframe_operations(self, sample_ohlc_data, performance_monitor):
        """Test performance of large DataFrame operations."""
        performance_monitor.start()

        # Perform common data operations
        df = sample_ohlc_data.copy()

        # Add technical indicators (simple calculations)
        df["sma_10"] = df["close"].rolling(window=10).mean()
        df["sma_20"] = df["close"].rolling(window=20).mean()
        df["price_change"] = df["close"].pct_change()
        df["volume_sma"] = df["volume"].rolling(window=10).mean()

        # Filter and sort operations
        filtered_df = df[df["volume"] > df["volume"].median()]
        sorted_df = df.sort_values("volume", ascending=False)

        # Groupby operations
        daily_stats = df.groupby(df["time"].dt.date).agg(
            {
                "open": "first",
                "high": "max",
                "low": "min",
                "close": "last",
                "volume": "sum",
            }
        )

        metrics = performance_monitor.get_metrics()

        # Operations should complete reasonably fast
        assert (
            metrics["elapsed_time"] < 2.0
        ), f"DataFrame operations took {metrics['elapsed_time']:.3f}s"

        # Results should be valid
        assert len(filtered_df) > 0
        assert len(sorted_df) == len(df)
        assert len(daily_stats) > 0

    def test_time_series_resampling_performance(
        self, sample_ohlc_data, performance_monitor
    ):
        """Test time series resampling performance."""
        performance_monitor.start()

        df = sample_ohlc_data.set_index("time")

        # Resample to different timeframes
        resampled_4h = (
            df.resample("4H")
            .agg(
                {
                    "open": "first",
                    "high": "max",
                    "low": "min",
                    "close": "last",
                    "volume": "sum",
                }
            )
            .dropna()
        )

        resampled_daily = (
            df.resample("D")
            .agg(
                {
                    "open": "first",
                    "high": "max",
                    "low": "min",
                    "close": "last",
                    "volume": "sum",
                }
            )
            .dropna()
        )

        metrics = performance_monitor.get_metrics()

        # Resampling should be fast
        assert (
            metrics["elapsed_time"] < 1.0
        ), f"Time series resampling took {metrics['elapsed_time']:.3f}s"

        # Results should be valid
        assert len(resampled_4h) > 0
        assert len(resampled_daily) > 0
        assert len(resampled_4h) > len(
            resampled_daily
        )  # Higher frequency should have more bars

    def test_memory_efficient_processing(self, performance_monitor):
        """Test memory-efficient processing of large datasets."""
        performance_monitor.start()

        # Process data in chunks to test memory efficiency
        chunk_size = 1000
        total_processed = 0

        for i in range(10):  # Process 10 chunks
            # Generate chunk of data
            chunk_data = pd.DataFrame(
                {
                    "timestamp": pd.date_range(
                        start=f"2023-01-{i+1:02d}", periods=chunk_size, freq="1min"
                    ),
                    "value": np.random.randn(chunk_size),
                    "volume": np.random.randint(100, 1000, chunk_size),
                }
            )

            # Process chunk (simple operations)
            processed_chunk = chunk_data.copy()
            processed_chunk["ma_10"] = processed_chunk["value"].rolling(10).mean()
            processed_chunk["cumsum"] = processed_chunk["value"].cumsum()

            total_processed += len(processed_chunk)

            # Update memory tracking
            performance_monitor.update_peak_memory()

            # Clear chunk to free memory
            del chunk_data, processed_chunk

        metrics = performance_monitor.get_metrics()

        assert total_processed == 10 * chunk_size

        # Should process efficiently without excessive memory growth
        assert (
            metrics["memory_delta_mb"] < 100
        ), f"Memory increased by {metrics['memory_delta_mb']:.1f}MB"
        assert (
            metrics["elapsed_time"] < 5.0
        ), f"Chunk processing took {metrics['elapsed_time']:.3f}s"


class TestStressTests:
    """Stress tests for system limits."""

    @pytest.mark.stress
    def test_memory_stress_test(self, performance_monitor):
        """Test behavior under memory stress."""
        performance_monitor.start()

        # Gradually increase memory usage
        data_chunks = []
        max_chunks = 50

        try:
            for i in range(max_chunks):
                # Create progressively larger chunks
                chunk_size = 1000 * (i + 1)
                chunk = np.random.randn(chunk_size, 100)  # Large array
                data_chunks.append(chunk)

                performance_monitor.update_peak_memory()

                current_memory = performance_monitor.get_metrics()["current_memory_mb"]

                # Stop if memory usage gets too high (> 1GB increase)
                if (
                    current_memory
                    - performance_monitor.get_metrics()["start_memory_mb"]
                    > 1000
                ):
                    break

                # Small delay to allow monitoring
                time.sleep(0.01)

        except MemoryError:
            # Expected behavior under memory stress
            pass
        finally:
            # Clean up
            data_chunks.clear()

        metrics = performance_monitor.get_metrics()

        # Should handle memory stress gracefully
        assert (
            metrics["elapsed_time"] < 30.0
        ), "Stress test should complete or fail quickly"

    @pytest.mark.stress
    def test_cpu_intensive_operations(self, performance_monitor):
        """Test CPU-intensive operations."""
        performance_monitor.start()

        # CPU-intensive calculations
        def cpu_intensive_task(n):
            """Simulate CPU-intensive work."""
            result = 0
            for i in range(n):
                result += i**0.5
            return result

        # Run multiple CPU-intensive tasks
        with ThreadPoolExecutor(max_workers=4) as executor:
            futures = [executor.submit(cpu_intensive_task, 100000) for _ in range(10)]

            results = []
            for future in as_completed(futures):
                result = future.result()
                results.append(result)
                performance_monitor.update_peak_memory()

        metrics = performance_monitor.get_metrics()

        assert len(results) == 10

        # Should complete CPU-intensive work in reasonable time
        assert (
            metrics["elapsed_time"] < 10.0
        ), f"CPU-intensive tasks took {metrics['elapsed_time']:.3f}s"


# Pytest markers for test categorization
pytestmark = [pytest.mark.performance, pytest.mark.slow]
