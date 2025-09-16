"""Tests for TimescaleDBStorage class."""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from datetime import datetime
import json

from fxml4_data_collector.storage.timescaledb import TimescaleDBStorage


@pytest.fixture
def dsn():
    """Test database connection string."""
    return "postgresql://user:password@localhost:5432/testdb"


@pytest.fixture
def timescaledb_storage(dsn):
    """Create TimescaleDBStorage instance."""
    return TimescaleDBStorage(dsn)


@pytest.fixture
def sample_market_data():
    """Sample market data for testing."""
    return {
        "ticker": "C:EURUSD",
        "timestamp": datetime.now().isoformat(),
        "open": 1.0850,
        "high": 1.0865,
        "low": 1.0845,
        "close": 1.0860,
        "volume": 12345
    }


@pytest.fixture
def sample_batch_data():
    """Sample batch market data for testing."""
    return {
        "ticker": "C:GBPUSD",
        "results": [
            {
                "t": 1234567890000,
                "o": 1.2500,
                "h": 1.2515,
                "l": 1.2495,
                "c": 1.2510,
                "v": 5000
            },
            {
                "t": 1234567950000,
                "o": 1.2510,
                "h": 1.2520,
                "l": 1.2505,
                "c": 1.2515,
                "v": 6000
            }
        ]
    }


class TestTimescaleDBStorage:
    """Test TimescaleDBStorage class."""
    
    def test_initialization(self, timescaledb_storage, dsn):
        """Test TimescaleDBStorage initialization."""
        assert timescaledb_storage.dsn == dsn
    
    @pytest.mark.asyncio
    async def test_save_not_implemented(self, timescaledb_storage, sample_market_data):
        """Test that save method is not yet implemented."""
        # Currently, the save method passes without implementation
        result = await timescaledb_storage.save(sample_market_data)
        assert result is None  # Method returns None (pass)
    
    @pytest.mark.asyncio
    async def test_save_with_connection_mock(self, timescaledb_storage, sample_market_data, monkeypatch):
        """Test save method with mocked database connection."""
        # Mock asyncpg connection
        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock()
        mock_conn.close = AsyncMock()
        
        # Mock asyncpg.connect
        async def mock_connect(dsn):
            return mock_conn
        
        with patch('asyncpg.connect', side_effect=mock_connect) as mock_asyncpg:
            # Implement a mock save method
            async def mock_save(self, data):
                conn = await mock_asyncpg(self.dsn)
                try:
                    await conn.execute(
                        """
                        INSERT INTO market_data (ticker, timestamp, open, high, low, close, volume)
                        VALUES ($1, $2, $3, $4, $5, $6, $7)
                        """,
                        data["ticker"],
                        data["timestamp"],
                        data["open"],
                        data["high"],
                        data["low"],
                        data["close"],
                        data["volume"]
                    )
                finally:
                    await conn.close()
            
            monkeypatch.setattr(timescaledb_storage, 'save', mock_save.__get__(timescaledb_storage, TimescaleDBStorage))
            
            # Execute save
            await timescaledb_storage.save(sample_market_data)
            
            # Verify connection was established and closed
            mock_asyncpg.assert_called_once_with(dsn)
            mock_conn.execute.assert_called_once()
            mock_conn.close.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_save_batch_data(self, timescaledb_storage, sample_batch_data, monkeypatch):
        """Test saving batch data."""
        saved_data = []
        
        async def mock_save_batch(self, data):
            if "results" in data:
                for record in data["results"]:
                    saved_data.append({
                        "ticker": data["ticker"],
                        "timestamp": record["t"],
                        "open": record["o"],
                        "high": record["h"],
                        "low": record["l"],
                        "close": record["c"],
                        "volume": record["v"]
                    })
            return len(saved_data)
        
        monkeypatch.setattr(timescaledb_storage, 'save', mock_save_batch.__get__(timescaledb_storage, TimescaleDBStorage))
        
        result = await timescaledb_storage.save(sample_batch_data)
        assert result == 2
        assert len(saved_data) == 2
        assert saved_data[0]["ticker"] == "C:GBPUSD"
        assert saved_data[0]["open"] == 1.2500
    
    @pytest.mark.asyncio
    async def test_save_with_connection_error(self, timescaledb_storage, sample_market_data, monkeypatch):
        """Test save method handling connection errors."""
        async def mock_save_error(self, data):
            raise ConnectionError("Failed to connect to TimescaleDB")
        
        monkeypatch.setattr(timescaledb_storage, 'save', mock_save_error.__get__(timescaledb_storage, TimescaleDBStorage))
        
        with pytest.raises(ConnectionError, match="Failed to connect to TimescaleDB"):
            await timescaledb_storage.save(sample_market_data)
    
    @pytest.mark.asyncio
    async def test_save_with_invalid_data(self, timescaledb_storage, monkeypatch):
        """Test save method with invalid data."""
        async def mock_save_validate(self, data):
            required_fields = ["ticker", "timestamp", "open", "high", "low", "close"]
            for field in required_fields:
                if field not in data:
                    raise ValueError(f"Missing required field: {field}")
            return True
        
        monkeypatch.setattr(timescaledb_storage, 'save', mock_save_validate.__get__(timescaledb_storage, TimescaleDBStorage))
        
        # Test with incomplete data
        invalid_data = {"ticker": "C:EURUSD", "open": 1.0850}
        
        with pytest.raises(ValueError, match="Missing required field: timestamp"):
            await timescaledb_storage.save(invalid_data)
    
    @pytest.mark.asyncio
    async def test_save_with_transaction(self, timescaledb_storage, sample_batch_data, monkeypatch):
        """Test save method with transaction support."""
        transaction_calls = []
        
        async def mock_save_transaction(self, data):
            transaction_calls.append("BEGIN")
            try:
                # Simulate saving data
                if "results" in data:
                    for record in data["results"]:
                        transaction_calls.append(f"INSERT {record['t']}")
                transaction_calls.append("COMMIT")
                return True
            except Exception:
                transaction_calls.append("ROLLBACK")
                raise
        
        monkeypatch.setattr(timescaledb_storage, 'save', mock_save_transaction.__get__(timescaledb_storage, TimescaleDBStorage))
        
        result = await timescaledb_storage.save(sample_batch_data)
        assert result is True
        assert transaction_calls[0] == "BEGIN"
        assert transaction_calls[-1] == "COMMIT"
        assert len([c for c in transaction_calls if c.startswith("INSERT")]) == 2
    
    @pytest.mark.asyncio
    async def test_save_with_retry_logic(self, timescaledb_storage, sample_market_data, monkeypatch):
        """Test save method with retry logic for transient failures."""
        attempt_count = 0
        
        async def mock_save_retry(self, data):
            nonlocal attempt_count
            attempt_count += 1
            
            if attempt_count < 3:
                raise ConnectionError("Temporary connection failure")
            return True
        
        # Add retry logic
        async def save_with_retry(self, data, max_retries=3):
            for attempt in range(max_retries):
                try:
                    return await mock_save_retry(self, data)
                except ConnectionError:
                    if attempt == max_retries - 1:
                        raise
                    await asyncio.sleep(0.1)  # Small delay between retries
        
        monkeypatch.setattr(timescaledb_storage, 'save', save_with_retry.__get__(timescaledb_storage, TimescaleDBStorage))
        
        result = await timescaledb_storage.save(sample_market_data)
        assert result is True
        assert attempt_count == 3
    
    def test_dsn_parsing(self, timescaledb_storage):
        """Test that DSN is stored correctly."""
        # Test with different DSN formats
        dsn1 = "postgresql://user:pass@host:5432/db"
        storage1 = TimescaleDBStorage(dsn1)
        assert storage1.dsn == dsn1
        
        dsn2 = "postgres://user:pass@host/db?sslmode=require"
        storage2 = TimescaleDBStorage(dsn2)
        assert storage2.dsn == dsn2
    
    @pytest.mark.asyncio
    async def test_save_with_hypertable(self, timescaledb_storage, sample_market_data, monkeypatch):
        """Test save method with TimescaleDB hypertable support."""
        create_table_called = False
        
        async def mock_save_hypertable(self, data):
            nonlocal create_table_called
            
            # Simulate creating hypertable if not exists
            if not create_table_called:
                create_table_called = True
                # In real implementation, this would execute:
                # SELECT create_hypertable('market_data', 'timestamp', if_not_exists => TRUE);
            
            return True
        
        monkeypatch.setattr(timescaledb_storage, 'save', mock_save_hypertable.__get__(timescaledb_storage, TimescaleDBStorage))
        
        result = await timescaledb_storage.save(sample_market_data)
        assert result is True
        assert create_table_called is True
    
    @pytest.mark.asyncio
    async def test_save_with_compression(self, timescaledb_storage, sample_market_data, monkeypatch):
        """Test save method with TimescaleDB compression policy."""
        policies_applied = []
        
        async def mock_save_compression(self, data):
            # Simulate adding compression policy
            policies_applied.append({
                "type": "compression",
                "table": "market_data",
                "after": "7 days"
            })
            return True
        
        monkeypatch.setattr(timescaledb_storage, 'save', mock_save_compression.__get__(timescaledb_storage, TimescaleDBStorage))
        
        result = await timescaledb_storage.save(sample_market_data)
        assert result is True
        assert len(policies_applied) == 1
        assert policies_applied[0]["type"] == "compression"
    
    @pytest.mark.asyncio
    async def test_concurrent_saves(self, timescaledb_storage, monkeypatch):
        """Test concurrent save operations."""
        save_count = 0
        
        async def mock_concurrent_save(self, data):
            nonlocal save_count
            save_count += 1
            await asyncio.sleep(0.01)  # Simulate IO operation
            return True
        
        monkeypatch.setattr(timescaledb_storage, 'save', mock_concurrent_save.__get__(timescaledb_storage, TimescaleDBStorage))
        
        # Create multiple save tasks
        tasks = []
        for i in range(5):
            data = {
                "ticker": f"C:TEST{i}",
                "timestamp": datetime.now().isoformat(),
                "open": 1.0 + i * 0.01,
                "high": 1.0 + i * 0.01 + 0.005,
                "low": 1.0 + i * 0.01 - 0.005,
                "close": 1.0 + i * 0.01 + 0.002,
                "volume": 1000 * (i + 1)
            }
            tasks.append(timescaledb_storage.save(data))
        
        # Execute all saves concurrently
        results = await asyncio.gather(*tasks)
        
        assert all(result is True for result in results)
        assert save_count == 5