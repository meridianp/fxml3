"""Tests for BaseCollector class."""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch
from abc import ABC

from fxml4_data_collector.collectors.base_collector import BaseCollector


class ConcreteCollector(BaseCollector):
    """Concrete implementation of BaseCollector for testing."""
    
    async def collect(self):
        """Mock implementation of collect method."""
        return {"test": "data"}


@pytest.fixture
def mock_storage():
    """Create mock storage instance."""
    storage = Mock()
    storage.save = AsyncMock()
    return storage


@pytest.fixture
def collector(mock_storage):
    """Create collector instance with mock storage."""
    return ConcreteCollector(mock_storage)


class TestBaseCollector:
    """Test BaseCollector abstract class."""
    
    def test_base_collector_is_abstract(self):
        """Test that BaseCollector cannot be instantiated directly."""
        with pytest.raises(TypeError, match="Can't instantiate abstract class"):
            BaseCollector(Mock())
    
    def test_initialization(self, collector, mock_storage):
        """Test collector initialization with storage."""
        assert collector.storage == mock_storage
    
    def test_has_abstract_collect_method(self):
        """Test that collect method is abstract."""
        assert hasattr(BaseCollector, 'collect')
        assert getattr(BaseCollector.collect, '__isabstractmethod__', False)
    
    @pytest.mark.asyncio
    async def test_collect_and_store_success(self, collector, mock_storage):
        """Test successful collect and store operation."""
        # Override collect method to return test data
        test_data = {"symbol": "EURUSD", "price": 1.0850}
        collector.collect = AsyncMock(return_value=test_data)
        
        # Execute collect_and_store
        await collector.collect_and_store()
        
        # Verify collect was called
        collector.collect.assert_called_once()
        
        # Verify storage.save was called with collected data
        mock_storage.save.assert_called_once_with(test_data)
    
    @pytest.mark.asyncio
    async def test_collect_and_store_with_collect_error(self, collector, mock_storage):
        """Test collect_and_store when collect raises an error."""
        # Make collect raise an exception
        error_msg = "API connection failed"
        collector.collect = AsyncMock(side_effect=Exception(error_msg))
        
        # Verify exception is propagated
        with pytest.raises(Exception, match=error_msg):
            await collector.collect_and_store()
        
        # Verify storage.save was not called
        mock_storage.save.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_collect_and_store_with_storage_error(self, collector, mock_storage):
        """Test collect_and_store when storage.save raises an error."""
        # Set up successful collect
        test_data = {"symbol": "GBPUSD", "price": 1.2500}
        collector.collect = AsyncMock(return_value=test_data)
        
        # Make storage.save raise an exception
        error_msg = "Database connection failed"
        mock_storage.save.side_effect = Exception(error_msg)
        
        # Verify exception is propagated
        with pytest.raises(Exception, match=error_msg):
            await collector.collect_and_store()
        
        # Verify collect was called
        collector.collect.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_collect_and_store_with_empty_data(self, collector, mock_storage):
        """Test collect_and_store with empty data."""
        # Return empty data from collect
        collector.collect = AsyncMock(return_value={})
        
        # Execute collect_and_store
        await collector.collect_and_store()
        
        # Verify both methods were called
        collector.collect.assert_called_once()
        mock_storage.save.assert_called_once_with({})
    
    @pytest.mark.asyncio
    async def test_collect_and_store_with_none_data(self, collector, mock_storage):
        """Test collect_and_store when collect returns None."""
        # Return None from collect
        collector.collect = AsyncMock(return_value=None)
        
        # Execute collect_and_store
        await collector.collect_and_store()
        
        # Verify storage.save was called with None
        mock_storage.save.assert_called_once_with(None)
    
    def test_inheritance_structure(self):
        """Test that BaseCollector properly inherits from ABC."""
        assert issubclass(BaseCollector, ABC)
    
    @pytest.mark.asyncio
    async def test_multiple_collect_and_store_calls(self, collector, mock_storage):
        """Test multiple calls to collect_and_store."""
        # Set up different data for each call
        data_sequence = [
            {"call": 1, "data": "first"},
            {"call": 2, "data": "second"},
            {"call": 3, "data": "third"}
        ]
        collector.collect = AsyncMock(side_effect=data_sequence)
        
        # Execute multiple collect_and_store calls
        for _ in range(3):
            await collector.collect_and_store()
        
        # Verify correct number of calls
        assert collector.collect.call_count == 3
        assert mock_storage.save.call_count == 3
        
        # Verify each call with correct data
        for i, call in enumerate(mock_storage.save.call_args_list):
            assert call[0][0] == data_sequence[i]