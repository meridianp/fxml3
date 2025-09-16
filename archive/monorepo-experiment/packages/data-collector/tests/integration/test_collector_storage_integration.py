"""Integration tests for collector and storage components."""

import pytest
import pytest_asyncio
import asyncio
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime, timedelta
import os

from fxml4_data_collector.collectors.polygon_collector import PolygonCollector
from fxml4_data_collector.storage.timescaledb import TimescaleDBStorage


@pytest.fixture
def test_dsn():
    """Test database connection string."""
    return os.environ.get(
        "TEST_TIMESCALEDB_DSN",
        "postgresql://postgres:postgres@localhost:5433/fxml4_test"
    )


@pytest.fixture
def test_api_key():
    """Test API key for Polygon."""
    return os.environ.get("TEST_POLYGON_API_KEY", "test_api_key_123")


@pytest_asyncio.fixture
async def storage(test_dsn):
    """Create TimescaleDBStorage instance for integration tests."""
    return TimescaleDBStorage(test_dsn)


@pytest_asyncio.fixture
async def collector(storage, test_api_key):
    """Create PolygonCollector instance for integration tests."""
    return PolygonCollector(storage, test_api_key)


@pytest.mark.integration
class TestCollectorStorageIntegration:
    """Integration tests for collector and storage components."""
    
    @pytest.mark.asyncio
    async def test_collect_and_store_flow(self, collector, storage, monkeypatch):
        """Test the complete flow from collection to storage."""
        # Mock the Polygon API response
        mock_api_data = {
            "status": "OK",
            "ticker": "C:EURUSD",
            "results": [
                {
                    "t": int(datetime.now().timestamp() * 1000),
                    "o": 1.0850,
                    "h": 1.0865,
                    "l": 1.0845,
                    "c": 1.0860,
                    "v": 12345,
                    "vw": 1.0855,
                    "n": 100
                }
            ],
            "count": 1
        }
        
        # Mock the collector's collect method
        collector.collect = AsyncMock(return_value=mock_api_data)
        
        # Mock the storage's save method
        saved_data = []
        
        async def mock_save(data):
            saved_data.append(data)
            return True
        
        storage.save = mock_save
        
        # Execute the flow
        await collector.collect_and_store()
        
        # Verify data was collected and stored
        assert len(saved_data) == 1
        assert saved_data[0]["ticker"] == "C:EURUSD"
        assert saved_data[0]["status"] == "OK"
        assert len(saved_data[0]["results"]) == 1
    
    @pytest.mark.asyncio
    async def test_multiple_symbol_collection(self, storage, test_api_key, monkeypatch):
        """Test collecting and storing data for multiple symbols."""
        symbols = ["EURUSD", "GBPUSD", "USDJPY"]
        collectors = []
        
        for symbol in symbols:
            collector = PolygonCollector(storage, test_api_key)
            collector.symbol = symbol
            collectors.append(collector)
        
        # Mock collect method for each collector
        for i, collector in enumerate(collectors):
            mock_data = {
                "status": "OK",
                "ticker": f"C:{symbols[i]}",
                "results": [
                    {
                        "t": int((datetime.now() - timedelta(minutes=j)).timestamp() * 1000),
                        "o": 1.0 + i * 0.1 + j * 0.001,
                        "h": 1.0 + i * 0.1 + j * 0.001 + 0.0005,
                        "l": 1.0 + i * 0.1 + j * 0.001 - 0.0005,
                        "c": 1.0 + i * 0.1 + j * 0.001 + 0.0002,
                        "v": 1000 * (j + 1)
                    }
                    for j in range(5)  # 5 bars per symbol
                ]
            }
            collector.collect = AsyncMock(return_value=mock_data)
        
        # Mock storage save
        all_saved_data = []
        
        async def mock_save(data):
            all_saved_data.append(data)
            return True
        
        storage.save = mock_save
        
        # Collect and store for all symbols
        tasks = [collector.collect_and_store() for collector in collectors]
        await asyncio.gather(*tasks)
        
        # Verify all data was saved
        assert len(all_saved_data) == 3
        assert all(data["status"] == "OK" for data in all_saved_data)
        assert sum(len(data["results"]) for data in all_saved_data) == 15  # 5 bars * 3 symbols
    
    @pytest.mark.asyncio
    async def test_error_handling_and_recovery(self, collector, storage, monkeypatch):
        """Test error handling and recovery mechanisms."""
        call_count = 0
        
        async def mock_collect_with_errors():
            nonlocal call_count
            call_count += 1
            
            if call_count == 1:
                # First call fails
                raise ConnectionError("API temporarily unavailable")
            elif call_count == 2:
                # Second call returns partial data
                return {
                    "status": "ERROR",
                    "error": "Partial data available",
                    "results": []
                }
            else:
                # Third call succeeds
                return {
                    "status": "OK",
                    "ticker": "C:EURUSD",
                    "results": [{"t": 123456789, "o": 1.08, "h": 1.09, "l": 1.07, "c": 1.085}]
                }
        
        collector.collect = mock_collect_with_errors
        
        # Mock storage to track saves
        save_attempts = []
        
        async def mock_save(data):
            save_attempts.append(data)
            return True
        
        storage.save = mock_save
        
        # First attempt should fail
        with pytest.raises(ConnectionError):
            await collector.collect_and_store()
        
        # Second attempt should save error data
        await collector.collect_and_store()
        assert len(save_attempts) == 1
        assert save_attempts[0]["status"] == "ERROR"
        
        # Third attempt should succeed
        await collector.collect_and_store()
        assert len(save_attempts) == 2
        assert save_attempts[1]["status"] == "OK"
        assert len(save_attempts[1]["results"]) == 1
    
    @pytest.mark.asyncio
    async def test_batch_processing(self, storage, test_api_key):
        """Test batch processing of historical data."""
        collector = PolygonCollector(storage, test_api_key)
        
        # Generate mock historical data
        start_date = datetime.now() - timedelta(days=7)
        batch_data = []
        
        for day in range(7):
            date = start_date + timedelta(days=day)
            daily_data = {
                "date": date.isoformat(),
                "ticker": "C:EURUSD",
                "results": []
            }
            
            # Generate hourly bars for each day
            for hour in range(24):
                timestamp = date.replace(hour=hour)
                bar = {
                    "t": int(timestamp.timestamp() * 1000),
                    "o": 1.08 + (day * 0.001) + (hour * 0.0001),
                    "h": 1.08 + (day * 0.001) + (hour * 0.0001) + 0.0005,
                    "l": 1.08 + (day * 0.001) + (hour * 0.0001) - 0.0005,
                    "c": 1.08 + (day * 0.001) + (hour * 0.0001) + 0.0002,
                    "v": 1000 + hour * 100
                }
                daily_data["results"].append(bar)
            
            batch_data.append(daily_data)
        
        # Mock batch collection
        async def mock_collect_batch():
            return {"status": "OK", "batches": batch_data}
        
        collector.collect_batch = mock_collect_batch
        
        # Mock batch storage
        stored_batches = []
        
        async def mock_save_batch(data):
            if "batches" in data:
                stored_batches.extend(data["batches"])
            else:
                stored_batches.append(data)
            return True
        
        storage.save = mock_save_batch
        
        # Process batch
        batch_result = await collector.collect_batch()
        await storage.save(batch_result)
        
        # Verify batch processing
        assert len(stored_batches) == 7  # 7 days
        total_bars = sum(len(batch["results"]) for batch in stored_batches)
        assert total_bars == 168  # 24 hours * 7 days
    
    @pytest.mark.asyncio
    async def test_concurrent_collectors(self, storage, test_api_key):
        """Test multiple collectors running concurrently."""
        # Create collectors for different symbols and timeframes
        configurations = [
            {"symbol": "EURUSD", "timeframe": "1m"},
            {"symbol": "EURUSD", "timeframe": "5m"},
            {"symbol": "GBPUSD", "timeframe": "1m"},
            {"symbol": "GBPUSD", "timeframe": "5m"},
            {"symbol": "USDJPY", "timeframe": "1m"},
        ]
        
        collectors = []
        for config in configurations:
            collector = PolygonCollector(storage, test_api_key)
            collector.symbol = config["symbol"]
            collector.timeframe = config["timeframe"]
            
            # Mock collect for each configuration
            async def mock_collect(symbol=config["symbol"], timeframe=config["timeframe"]):
                await asyncio.sleep(0.01)  # Simulate API delay
                return {
                    "status": "OK",
                    "ticker": f"C:{symbol}",
                    "timeframe": timeframe,
                    "results": [
                        {
                            "t": int(datetime.now().timestamp() * 1000),
                            "o": 1.0,
                            "h": 1.1,
                            "l": 0.9,
                            "c": 1.05,
                            "v": 1000
                        }
                    ]
                }
            
            collector.collect = mock_collect
            collectors.append(collector)
        
        # Track concurrent saves
        save_order = []
        save_lock = asyncio.Lock()
        
        async def mock_save_concurrent(data):
            async with save_lock:
                save_order.append({
                    "ticker": data["ticker"],
                    "timeframe": data.get("timeframe", "unknown"),
                    "timestamp": datetime.now()
                })
            await asyncio.sleep(0.005)  # Simulate save delay
            return True
        
        storage.save = mock_save_concurrent
        
        # Run all collectors concurrently
        start_time = datetime.now()
        tasks = [collector.collect_and_store() for collector in collectors]
        await asyncio.gather(*tasks)
        end_time = datetime.now()
        
        # Verify concurrent execution
        assert len(save_order) == 5
        
        # Check that execution was concurrent (should be faster than sequential)
        total_time = (end_time - start_time).total_seconds()
        assert total_time < 0.1  # Should complete quickly due to concurrency
        
        # Verify all configurations were processed
        saved_configs = {(item["ticker"], item["timeframe"]) for item in save_order}
        expected_configs = {(f"C:{cfg['symbol']}", cfg["timeframe"]) for cfg in configurations}
        assert saved_configs == expected_configs
    
    @pytest.mark.asyncio
    async def test_data_validation_pipeline(self, collector, storage):
        """Test data validation in the collection pipeline."""
        # Add validation to collector
        def validate_market_data(data):
            """Validate market data structure and values."""
            errors = []
            
            # Check required fields
            required_fields = ["ticker", "results"]
            for field in required_fields:
                if field not in data:
                    errors.append(f"Missing required field: {field}")
            
            # Validate results if present
            if "results" in data and isinstance(data["results"], list):
                for i, bar in enumerate(data["results"]):
                    # Check OHLC relationship
                    if "h" in bar and "l" in bar:
                        if bar["h"] < bar["l"]:
                            errors.append(f"Bar {i}: High < Low")
                    
                    if all(k in bar for k in ["o", "h", "l", "c"]):
                        if bar["h"] < max(bar["o"], bar["c"]):
                            errors.append(f"Bar {i}: High < Open or Close")
                        if bar["l"] > min(bar["o"], bar["c"]):
                            errors.append(f"Bar {i}: Low > Open or Close")
                    
                    # Check volume
                    if "v" in bar and bar["v"] < 0:
                        errors.append(f"Bar {i}: Negative volume")
            
            return errors
        
        # Mock collect with various data scenarios
        test_scenarios = [
            # Valid data
            {
                "ticker": "C:EURUSD",
                "results": [{"t": 123, "o": 1.08, "h": 1.09, "l": 1.07, "c": 1.085, "v": 1000}]
            },
            # Invalid OHLC relationship
            {
                "ticker": "C:GBPUSD",
                "results": [{"t": 124, "o": 1.25, "h": 1.24, "l": 1.26, "c": 1.25, "v": 500}]
            },
            # Missing required field
            {
                "results": [{"t": 125, "o": 1.0, "h": 1.1, "l": 0.9, "c": 1.05}]
            },
            # Negative volume
            {
                "ticker": "C:USDJPY",
                "results": [{"t": 126, "o": 110, "h": 111, "l": 109, "c": 110.5, "v": -100}]
            }
        ]
        
        validation_results = []
        
        for scenario in test_scenarios:
            collector.collect = AsyncMock(return_value=scenario)
            
            # Wrap storage.save to include validation
            async def validating_save(data):
                errors = validate_market_data(data)
                validation_results.append({
                    "data": data,
                    "errors": errors,
                    "valid": len(errors) == 0
                })
                if errors:
                    raise ValueError(f"Validation failed: {errors}")
                return True
            
            storage.save = validating_save
            
            try:
                await collector.collect_and_store()
            except ValueError:
                pass  # Expected for invalid data
        
        # Check validation results
        assert len(validation_results) == 4
        assert validation_results[0]["valid"] is True
        assert validation_results[1]["valid"] is False
        assert "High < Low" in str(validation_results[1]["errors"])
        assert validation_results[2]["valid"] is False
        assert "Missing required field: ticker" in str(validation_results[2]["errors"])
        assert validation_results[3]["valid"] is False
        assert "Negative volume" in str(validation_results[3]["errors"])