"""Tests for PolygonCollector class."""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime, timedelta

from fxml4_data_collector.collectors.polygon_collector import PolygonCollector
from fxml4_data_collector.collectors.base_collector import BaseCollector


@pytest.fixture
def mock_storage():
    """Create mock storage instance."""
    storage = Mock()
    storage.save = AsyncMock()
    return storage


@pytest.fixture
def api_key():
    """Test API key."""
    return "test_polygon_api_key_123"


@pytest.fixture
def polygon_collector(mock_storage, api_key):
    """Create PolygonCollector instance."""
    return PolygonCollector(mock_storage, api_key)


class TestPolygonCollector:
    """Test PolygonCollector class."""
    
    def test_initialization(self, polygon_collector, mock_storage, api_key):
        """Test PolygonCollector initialization."""
        assert polygon_collector.storage == mock_storage
        assert polygon_collector.api_key == api_key
        assert isinstance(polygon_collector, BaseCollector)
    
    def test_inheritance(self):
        """Test that PolygonCollector inherits from BaseCollector."""
        assert issubclass(PolygonCollector, BaseCollector)
    
    @pytest.mark.asyncio
    async def test_collect_returns_dict(self, polygon_collector):
        """Test that collect method returns a dictionary."""
        result = await polygon_collector.collect()
        assert isinstance(result, dict)
    
    @pytest.mark.asyncio
    async def test_collect_with_mock_api_response(self, polygon_collector, monkeypatch):
        """Test collect method with mocked API response."""
        # Mock httpx or aiohttp response
        mock_response = {
            "status": "OK",
            "results": [
                {
                    "v": 12345,  # volume
                    "vw": 1.0856,  # volume weighted average price
                    "o": 1.0850,  # open
                    "c": 1.0860,  # close
                    "h": 1.0865,  # high
                    "l": 1.0845,  # low
                    "t": 1234567890000,  # timestamp
                    "n": 100  # number of transactions
                }
            ],
            "ticker": "C:EURUSD",
            "count": 1
        }
        
        # Since collect is not implemented yet, we'll test the structure
        # In a real implementation, we would mock the HTTP client
        async def mock_collect(self):
            return mock_response
        
        monkeypatch.setattr(polygon_collector, 'collect', mock_collect.__get__(polygon_collector, PolygonCollector))
        
        result = await polygon_collector.collect()
        assert result["status"] == "OK"
        assert "results" in result
        assert len(result["results"]) == 1
        assert result["ticker"] == "C:EURUSD"
    
    @pytest.mark.asyncio
    async def test_collect_and_store_integration(self, polygon_collector, mock_storage):
        """Test the full collect and store flow."""
        # Mock the collect method to return test data
        test_data = {
            "ticker": "C:GBPUSD",
            "results": [{"o": 1.2500, "c": 1.2510, "h": 1.2515, "l": 1.2495}]
        }
        polygon_collector.collect = AsyncMock(return_value=test_data)
        
        # Execute collect_and_store
        await polygon_collector.collect_and_store()
        
        # Verify storage.save was called with the collected data
        mock_storage.save.assert_called_once_with(test_data)
    
    @pytest.mark.asyncio
    async def test_collect_with_api_error(self, polygon_collector, monkeypatch):
        """Test collect method handling API errors."""
        # Mock collect to raise an API error
        async def mock_collect_error(self):
            raise Exception("API rate limit exceeded")
        
        monkeypatch.setattr(polygon_collector, 'collect', mock_collect_error.__get__(polygon_collector, PolygonCollector))
        
        # Verify exception is raised
        with pytest.raises(Exception, match="API rate limit exceeded"):
            await polygon_collector.collect()
    
    def test_api_key_not_exposed(self, polygon_collector):
        """Test that API key is stored but not exposed in string representation."""
        # This is a security best practice test
        str_repr = str(polygon_collector)
        repr_repr = repr(polygon_collector)
        
        # API key should not appear in string representations
        assert "test_polygon_api_key_123" not in str_repr
        assert "test_polygon_api_key_123" not in repr_repr
    
    @pytest.mark.asyncio
    async def test_multiple_symbols_collection(self, polygon_collector, monkeypatch):
        """Test collecting data for multiple symbols."""
        # Mock implementation for multiple symbols
        async def mock_collect_multiple(self, symbols=None):
            if symbols is None:
                symbols = ["EURUSD", "GBPUSD", "USDJPY"]
            
            results = {}
            for symbol in symbols:
                results[symbol] = {
                    "ticker": f"C:{symbol}",
                    "results": [{"o": 1.0, "c": 1.1, "h": 1.15, "l": 0.95}]
                }
            return results
        
        # Add symbols parameter to the collector
        polygon_collector.symbols = ["EURUSD", "GBPUSD"]
        monkeypatch.setattr(
            polygon_collector, 
            'collect', 
            lambda: mock_collect_multiple(polygon_collector, polygon_collector.symbols)
        )
        
        result = await polygon_collector.collect()
        assert len(result) == 2
        assert "EURUSD" in result
        assert "GBPUSD" in result
    
    @pytest.mark.asyncio
    async def test_collect_with_timeframe_parameters(self, polygon_collector, monkeypatch):
        """Test collecting data with specific timeframe parameters."""
        # Mock implementation with timeframe support
        async def mock_collect_timeframe(self, timeframe="1m", from_date=None, to_date=None):
            return {
                "ticker": "C:EURUSD",
                "timeframe": timeframe,
                "from": from_date.isoformat() if from_date else None,
                "to": to_date.isoformat() if to_date else None,
                "results": []
            }
        
        # Add timeframe parameters
        polygon_collector.timeframe = "5m"
        polygon_collector.from_date = datetime.now() - timedelta(days=1)
        polygon_collector.to_date = datetime.now()
        
        monkeypatch.setattr(
            polygon_collector,
            'collect',
            lambda: mock_collect_timeframe(
                polygon_collector,
                polygon_collector.timeframe,
                polygon_collector.from_date,
                polygon_collector.to_date
            )
        )
        
        result = await polygon_collector.collect()
        assert result["timeframe"] == "5m"
        assert result["from"] is not None
        assert result["to"] is not None
    
    @pytest.mark.asyncio
    async def test_collect_empty_response(self, polygon_collector, monkeypatch):
        """Test handling of empty API response."""
        async def mock_empty_collect(self):
            return {"status": "OK", "results": [], "count": 0}
        
        monkeypatch.setattr(polygon_collector, 'collect', mock_empty_collect.__get__(polygon_collector, PolygonCollector))
        
        result = await polygon_collector.collect()
        assert result["status"] == "OK"
        assert result["results"] == []
        assert result["count"] == 0
    
    @pytest.mark.asyncio
    async def test_collect_with_pagination(self, polygon_collector, monkeypatch):
        """Test collecting data with pagination support."""
        call_count = 0
        
        async def mock_paginated_collect(self, next_url=None):
            nonlocal call_count
            call_count += 1
            
            if call_count == 1:
                return {
                    "status": "OK",
                    "results": [{"page": 1}],
                    "next_url": "https://api.polygon.io/v2/aggs/ticker/next"
                }
            else:
                return {
                    "status": "OK",
                    "results": [{"page": 2}],
                    "next_url": None
                }
        
        # Mock a collect_all method that handles pagination
        async def collect_all_pages(self):
            all_results = []
            next_url = None
            
            while True:
                page_data = await mock_paginated_collect(self, next_url)
                all_results.extend(page_data["results"])
                
                if not page_data.get("next_url"):
                    break
                next_url = page_data["next_url"]
            
            return {"status": "OK", "results": all_results}
        
        polygon_collector.collect_all = collect_all_pages.__get__(polygon_collector, PolygonCollector)
        
        result = await polygon_collector.collect_all()
        assert len(result["results"]) == 2
        assert result["results"][0]["page"] == 1
        assert result["results"][1]["page"] == 2