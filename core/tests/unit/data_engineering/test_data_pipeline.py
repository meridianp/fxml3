"""
TDD Tests for Data Engineering Pipeline

Comprehensive tests for data ingestion, transformation, quality checks,
and real-time processing pipelines.
"""

import asyncio
from datetime import datetime, timedelta
from typing import Dict, List
from unittest.mock import AsyncMock, Mock, patch

import numpy as np
import pandas as pd
import pytest


@pytest.mark.tdd
@pytest.mark.data_engineering
class TestDataIngestionPipeline:
    """
    Test suite for data ingestion and processing pipeline.

    Tests data quality, transformations, aggregations, and
    real-time streaming capabilities.
    """

    @pytest.fixture
    def raw_tick_data(self):
        """Generate raw tick data for testing."""
        timestamps = pd.date_range(
            start="2024-01-01 09:00:00", periods=10000, freq="100ms"
        )
        np.random.seed(42)

        return pd.DataFrame(
            {
                "timestamp": timestamps,
                "symbol": "EUR/USD",
                "bid": 1.0850 + np.random.randn(10000) * 0.0001,
                "ask": 1.0852 + np.random.randn(10000) * 0.0001,
                "bid_size": np.random.randint(100000, 10000000, 10000),
                "ask_size": np.random.randint(100000, 10000000, 10000),
            }
        )

    @pytest.fixture
    def mock_data_source(self):
        """Mock external data source."""
        source = Mock()
        source.connect = AsyncMock(return_value=True)
        source.subscribe = AsyncMock()
        source.get_historical = AsyncMock()
        return source

    @pytest.fixture
    def data_pipeline(self):
        """Create data pipeline instance."""
        from core.data_engineering.unified_pipeline import UnifiedDataPipeline

        return UnifiedDataPipeline(
            config={
                "buffer_size": 10000,
                "quality_checks": True,
                "enable_streaming": True,
            }
        )

    # -------------------------------------------------------------------------
    # Data Quality Tests
    # -------------------------------------------------------------------------

    @pytest.mark.red
    def test_data_quality_validation(self, data_pipeline, raw_tick_data):
        """RED: Test data quality validation checks."""
        # Introduce data quality issues
        dirty_data = raw_tick_data.copy()
        dirty_data.loc[0:10, "bid"] = np.nan  # Missing values
        dirty_data.loc[20:30, "bid"] = -1  # Invalid negative prices
        dirty_data.loc[40:50, "bid"] = 1000  # Outliers
        dirty_data.loc[60:70, "timestamp"] = pd.NaT  # Missing timestamps
        dirty_data.loc[80:90, "bid"] = (
            dirty_data.loc[80:90, "ask"] + 0.001
        )  # Inverted spread

        # Run quality checks
        cleaned_data, quality_report = data_pipeline.validate_and_clean(dirty_data)

        # Verify issues detected
        assert quality_report["missing_values"] > 0
        assert quality_report["outliers"] > 0
        assert quality_report["invalid_spreads"] > 0

        # Verify data cleaned
        assert not cleaned_data["bid"].isnull().any()
        assert (cleaned_data["bid"] > 0).all()
        assert (cleaned_data["ask"] > cleaned_data["bid"]).all()
        assert not cleaned_data["timestamp"].isnull().any()

    @pytest.mark.red
    def test_duplicate_detection(self, data_pipeline, raw_tick_data):
        """RED: Test duplicate tick detection and handling."""
        # Create duplicates
        duplicated_data = pd.concat([raw_tick_data, raw_tick_data.iloc[0:100]])

        # Process with duplicate removal
        processed_data = data_pipeline.remove_duplicates(duplicated_data)

        # Verify duplicates removed
        assert len(processed_data) == len(raw_tick_data)
        assert not processed_data.duplicated(subset=["timestamp", "symbol"]).any()

    @pytest.mark.red
    def test_timestamp_validation(self, data_pipeline):
        """RED: Test timestamp validation and alignment."""
        # Create data with timestamp issues
        data = pd.DataFrame(
            {
                "timestamp": [
                    "2024-01-01 09:00:00",  # String timestamp
                    datetime(2024, 1, 1, 9, 0, 1),  # Datetime object
                    1704099602000,  # Unix timestamp (ms)
                    None,  # Missing
                    "2024-01-01 09:00:03",
                ],
                "price": [1.0850, 1.0851, 1.0852, 1.0853, 1.0854],
            }
        )

        # Validate and normalize timestamps
        normalized_data = data_pipeline.normalize_timestamps(data)

        # All timestamps should be datetime objects
        assert normalized_data["timestamp"].dtype == "datetime64[ns]"
        assert not normalized_data["timestamp"].isnull().any()

        # Timestamps should be in order
        assert normalized_data["timestamp"].is_monotonic_increasing

    # -------------------------------------------------------------------------
    # Data Transformation Tests
    # -------------------------------------------------------------------------

    @pytest.mark.red
    def test_tick_to_ohlcv_aggregation(self, data_pipeline, raw_tick_data):
        """RED: Test tick data to OHLCV aggregation."""
        # Aggregate to 1-minute bars
        ohlcv = data_pipeline.aggregate_to_ohlcv(
            raw_tick_data, timeframe="1min", price_column="bid"
        )

        # Verify OHLCV structure
        expected_columns = ["timestamp", "open", "high", "low", "close", "volume"]
        assert all(col in ohlcv.columns for col in expected_columns)

        # Verify aggregation logic
        assert len(ohlcv) < len(raw_tick_data)  # Should be aggregated
        assert (ohlcv["high"] >= ohlcv["low"]).all()
        assert (ohlcv["high"] >= ohlcv["open"]).all()
        assert (ohlcv["high"] >= ohlcv["close"]).all()
        assert (ohlcv["volume"] > 0).all()

        # Verify time alignment
        assert ohlcv["timestamp"].dt.second.eq(0).all()  # Aligned to minutes

    @pytest.mark.red
    def test_multi_timeframe_generation(self, data_pipeline, raw_tick_data):
        """RED: Test multi-timeframe data generation."""
        timeframes = ["1min", "5min", "15min", "1H", "4H", "1D"]

        multi_tf_data = data_pipeline.generate_multi_timeframes(
            raw_tick_data, timeframes=timeframes
        )

        # Verify all timeframes generated
        assert set(multi_tf_data.keys()) == set(timeframes)

        # Verify data consistency across timeframes
        for tf in timeframes[1:]:  # Skip 1min
            assert len(multi_tf_data[tf]) < len(multi_tf_data["1min"])

        # Verify aggregation relationships
        # 5 x 1min bars should roughly equal 1 x 5min bar
        min1_volume = multi_tf_data["1min"]["volume"].iloc[0:5].sum()
        min5_volume = multi_tf_data["5min"]["volume"].iloc[0]
        assert abs(min1_volume - min5_volume) < 1000  # Allow small difference

    @pytest.mark.red
    def test_feature_engineering_pipeline(self, data_pipeline):
        """RED: Test feature engineering transformations."""
        # Create OHLCV data
        ohlcv = pd.DataFrame(
            {
                "timestamp": pd.date_range(start="2024-01-01", periods=100, freq="1H"),
                "open": 1.0850 + np.random.randn(100) * 0.001,
                "high": 1.0860 + np.random.randn(100) * 0.001,
                "low": 1.0840 + np.random.randn(100) * 0.001,
                "close": 1.0851 + np.random.randn(100) * 0.001,
                "volume": np.random.randint(100000, 1000000, 100),
            }
        )

        # Apply feature engineering
        features = data_pipeline.engineer_features(ohlcv)

        # Verify technical indicators added
        expected_features = [
            "returns",
            "log_returns",
            "volatility_20",
            "volume_ma_20",
            "price_ma_20",
            "price_ma_50",
            "upper_band",
            "lower_band",
            "rsi",
            "macd",
            "signal",
        ]

        for feature in expected_features:
            assert feature in features.columns

        # Verify feature values are valid
        assert not features["returns"].iloc[1:].isnull().any()
        assert (features["volatility_20"].iloc[20:] > 0).all()
        assert (features["rsi"].dropna() >= 0).all()
        assert (features["rsi"].dropna() <= 100).all()

    # -------------------------------------------------------------------------
    # Real-time Streaming Tests
    # -------------------------------------------------------------------------

    @pytest.mark.red
    async def test_streaming_data_ingestion(self, data_pipeline, mock_data_source):
        """RED: Test real-time streaming data ingestion."""

        # Mock streaming data
        async def mock_stream():
            for i in range(10):
                yield {
                    "timestamp": datetime.now(),
                    "symbol": "EUR/USD",
                    "bid": 1.0850 + i * 0.0001,
                    "ask": 1.0852 + i * 0.0001,
                }
                await asyncio.sleep(0.01)

        mock_data_source.stream = mock_stream

        # Process streaming data
        received_ticks = []

        async def collect_ticks():
            async for tick in data_pipeline.process_stream(mock_data_source):
                received_ticks.append(tick)
                if len(received_ticks) >= 10:
                    break

        await collect_ticks()

        # Verify all ticks processed
        assert len(received_ticks) == 10
        assert all("timestamp" in tick for tick in received_ticks)
        assert all(tick["symbol"] == "EUR/USD" for tick in received_ticks)

    @pytest.mark.red
    async def test_streaming_aggregation(self, data_pipeline):
        """RED: Test real-time aggregation of streaming data."""
        # Stream tick data and aggregate to bars
        bar_aggregator = data_pipeline.create_bar_aggregator(
            timeframe="1min", callback=None
        )

        # Send ticks
        for i in range(100):
            tick = {
                "timestamp": datetime.now() + timedelta(seconds=i),
                "price": 1.0850 + i * 0.00001,
                "volume": 100000,
            }
            bar_aggregator.add_tick(tick)

        # Get completed bars
        completed_bars = bar_aggregator.get_completed_bars()

        # Should have at least one completed minute bar
        assert len(completed_bars) > 0
        assert "open" in completed_bars[0]
        assert "close" in completed_bars[0]

    @pytest.mark.red
    async def test_backpressure_handling(self, data_pipeline):
        """RED: Test backpressure handling in streaming pipeline."""
        # Create slow consumer
        processed_count = 0

        async def slow_processor(data):
            nonlocal processed_count
            await asyncio.sleep(0.1)  # Simulate slow processing
            processed_count += 1

        # Generate fast data stream
        async def fast_generator():
            for i in range(100):
                yield {"tick": i}
                await asyncio.sleep(0.001)  # Fast generation

        # Process with backpressure control
        await data_pipeline.process_with_backpressure(
            fast_generator(), slow_processor, max_buffer_size=10
        )

        # Should handle all data without overwhelming system
        assert processed_count <= 100
        # Buffer should prevent memory issues
        assert data_pipeline.get_buffer_size() <= 10

    # -------------------------------------------------------------------------
    # Data Storage and Retrieval Tests
    # -------------------------------------------------------------------------

    @pytest.mark.red
    def test_timeseries_storage_optimization(self, data_pipeline):
        """RED: Test optimized timeseries data storage."""
        # Create large dataset
        large_data = pd.DataFrame(
            {
                "timestamp": pd.date_range(
                    start="2024-01-01", periods=1000000, freq="100ms"
                ),
                "value": np.random.randn(1000000),
            }
        )

        # Store with compression
        storage_info = data_pipeline.store_timeseries(
            large_data, compression="parquet", partition_by="day"
        )

        # Verify compression
        assert storage_info["compression_ratio"] > 2  # At least 2x compression
        assert storage_info["partitions"] > 1  # Data partitioned

        # Test efficient retrieval
        retrieved = data_pipeline.retrieve_timeseries(
            start_time="2024-01-01 12:00:00", end_time="2024-01-01 13:00:00"
        )

        # Should only load relevant partition
        assert len(retrieved) < len(large_data)
        assert retrieved["timestamp"].min() >= pd.Timestamp("2024-01-01 12:00:00")

    @pytest.mark.red
    def test_data_versioning(self, data_pipeline):
        """RED: Test data versioning and lineage tracking."""
        # Create versioned dataset
        data_v1 = pd.DataFrame({"value": [1, 2, 3]})

        version_id = data_pipeline.save_version(
            data_v1, metadata={"source": "test", "version": "1.0"}
        )

        # Modify and create new version
        data_v2 = pd.DataFrame({"value": [1, 2, 3, 4]})

        version_id_2 = data_pipeline.save_version(
            data_v2,
            metadata={"source": "test", "version": "2.0"},
            parent_version=version_id,
        )

        # Retrieve specific version
        retrieved_v1 = data_pipeline.get_version(version_id)
        assert len(retrieved_v1) == 3

        # Get version history
        history = data_pipeline.get_version_history("test")
        assert len(history) == 2
        assert history[1]["parent"] == version_id

    # -------------------------------------------------------------------------
    # Performance and Optimization Tests
    # -------------------------------------------------------------------------

    @pytest.mark.red
    def test_batch_processing_performance(self, data_pipeline, performance_timer):
        """RED: Test batch processing performance."""
        # Create large dataset
        large_batch = pd.DataFrame(
            {
                "timestamp": pd.date_range(
                    start="2024-01-01", periods=100000, freq="100ms"
                ),
                "value": np.random.randn(100000),
            }
        )

        # Process batch
        performance_timer.start()
        processed = data_pipeline.process_batch(large_batch)
        elapsed = performance_timer.stop()

        # Should process 100k records quickly
        assert elapsed < 1.0  # Less than 1 second
        records_per_second = len(large_batch) / elapsed
        assert records_per_second > 100000  # At least 100k records/sec

    @pytest.mark.red
    def test_parallel_processing(self, data_pipeline):
        """RED: Test parallel data processing capabilities."""
        # Create dataset for parallel processing
        data_chunks = [
            pd.DataFrame({"value": np.random.randn(10000)}) for _ in range(10)
        ]

        # Process in parallel
        results = data_pipeline.process_parallel(data_chunks, num_workers=4)

        # Verify all chunks processed
        assert len(results) == 10
        assert all(len(r) == 10000 for r in results)

    @pytest.mark.red
    def test_memory_efficient_processing(self, data_pipeline):
        """RED: Test memory-efficient processing of large datasets."""

        # Create generator for large dataset
        def data_generator():
            for i in range(1000):
                yield pd.DataFrame(
                    {
                        "timestamp": pd.date_range(
                            start=f"2024-01-{(i%30)+1:02d}", periods=1000, freq="1min"
                        ),
                        "value": np.random.randn(1000),
                    }
                )

        # Process with memory constraints
        result = data_pipeline.process_chunked(
            data_generator(), chunk_processor=lambda x: x.mean(), max_memory_mb=100
        )

        # Should complete without memory issues
        assert result is not None
        # Memory usage should stay within limits
        assert data_pipeline.get_peak_memory_usage() < 100 * 1024 * 1024  # 100MB

    # -------------------------------------------------------------------------
    # Error Recovery Tests
    # -------------------------------------------------------------------------

    @pytest.mark.red
    async def test_connection_failure_recovery(self, data_pipeline, mock_data_source):
        """RED: Test recovery from data source connection failures."""
        # Simulate connection failures
        mock_data_source.connect.side_effect = [
            Exception("Connection failed"),
            Exception("Still failing"),
            True,  # Success on third attempt
        ]

        # Attempt connection with retry
        connected = await data_pipeline.connect_with_retry(
            mock_data_source, max_retries=3, backoff_factor=0.1
        )

        assert connected is True
        assert mock_data_source.connect.call_count == 3

    @pytest.mark.red
    def test_corrupt_data_handling(self, data_pipeline):
        """RED: Test handling of corrupted data."""
        # Create corrupted data
        corrupted_data = pd.DataFrame(
            {
                "timestamp": ["2024-01-01", "CORRUPT", None, "2024-01-01 09:00:03"],
                "value": [1.0, "STRING", np.inf, -np.inf],
            }
        )

        # Process with error handling
        processed, errors = data_pipeline.process_with_error_handling(corrupted_data)

        # Should handle corrupt records
        assert len(processed) < len(corrupted_data)
        assert len(errors) > 0
        assert not processed["value"].isin([np.inf, -np.inf]).any()

    @pytest.mark.red
    def test_checkpoint_and_recovery(self, data_pipeline):
        """RED: Test checkpointing and recovery for long-running processes."""
        # Start long process with checkpointing
        checkpoint_id = data_pipeline.create_checkpoint()

        # Process some data
        for i in range(100):
            data_pipeline.process_record({"id": i})
            if i % 10 == 0:
                data_pipeline.save_checkpoint(checkpoint_id)

        # Simulate failure at record 50
        data_pipeline.simulate_failure()

        # Recover from checkpoint
        recovered_state = data_pipeline.recover_from_checkpoint(checkpoint_id)

        # Should recover from last checkpoint
        assert recovered_state["last_processed_id"] >= 40
        assert recovered_state["last_processed_id"] < 50
