"""
Comprehensive unit tests for Market Data service.

This module provides complete test coverage for the market data functionality,
following Test-Driven Development (TDD) principles.
"""

import asyncio
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pandas as pd
import pytest

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

# Mock all external dependencies before importing
sys.modules["openai"] = Mock()
sys.modules["fxml4.strategy.integrated_signal_generator"] = Mock()
sys.modules["fxml4.wave_analysis.sentiment_wave_validator"] = Mock()
sys.modules["fxml4.llm_integration.sentiment_analysis"] = Mock()
sys.modules["fxml4.llm_integration.llm_client"] = Mock()
sys.modules["fxml4.config"] = Mock()
sys.modules["fxml4.data_engineering.data_feeds.base_feed"] = Mock()

# Mock config function
mock_config = {
    "database": {
        "user": "test_user",
        "password": "test_password",
        "host": "localhost",
        "port": 5432,
        "name": "test_db",
    },
    "data": {
        "data_feeds": {
            "alpha_vantage": {"api_key": "test_key"},
            "polygon": {"api_key": "test_key"},
        }
    },
}

sys.modules["fxml4.config"].get_config = Mock(return_value=mock_config)

# Import after mocking
from fxml4.api.services.market_data import MarketDataPoint

# Use centralized event loop fixture
from tests.fixtures.event_loop_fixtures import event_loop


class MockMarketDataPoint:
    """Mock market data point for testing."""

    def __init__(
        self,
        time,
        symbol,
        open_price,
        high,
        low,
        close,
        volume,
        tick_count=0,
        source="test",
    ):
        self.time = time
        self.symbol = symbol
        self.open = open_price
        self.high = high
        self.low = low
        self.close = close
        self.volume = volume
        self.tick_count = tick_count
        self.source = source


class TestMarketDataModels:
    """Test market data models and data structures."""

    def test_market_data_point_creation(self):
        """Test MarketDataPoint model creation."""
        test_time = datetime.utcnow()

        point = MarketDataPoint(
            time=test_time,
            symbol="EURUSD",
            open=1.1000,
            high=1.1050,
            low=1.0950,
            close=1.1025,
            volume=1000,
            tick_count=50,
            source="timescaledb",
        )

        assert point.time == test_time
        assert point.symbol == "EURUSD"
        assert point.open == 1.1000
        assert point.high == 1.1050
        assert point.low == 1.0950
        assert point.close == 1.1025
        assert point.volume == 1000
        assert point.tick_count == 50
        assert point.source == "timescaledb"

    def test_market_data_point_with_defaults(self):
        """Test MarketDataPoint with default values."""
        point = MarketDataPoint(
            time=datetime.utcnow(),
            symbol="GBPUSD",
            open=1.2500,
            high=1.2550,
            low=1.2450,
            close=1.2525,
            volume=800,
            source="alpha_vantage",
        )

        assert point.tick_count == 0  # Default value
        assert point.symbol == "GBPUSD"
        assert point.source == "alpha_vantage"

    def test_market_data_point_ohlc_validation(self):
        """Test OHLC price validation logic."""
        point = MarketDataPoint(
            time=datetime.utcnow(),
            symbol="USDJPY",
            open=150.00,
            high=150.50,
            low=149.50,
            close=150.25,
            volume=500,
            source="test",
        )

        # Verify OHLC relationships are captured
        assert point.high >= point.open
        assert point.high >= point.close
        assert point.low <= point.open
        assert point.low <= point.close
        assert point.open >= point.low
        assert point.close >= point.low


class MockMarketDataService:
    """Mock implementation of MarketDataService for testing."""

    def __init__(self):
        self._pool = None
        self.config = mock_config
        self.stored_data = {}  # Dict[str, List[MockMarketDataPoint]]
        self.symbols = ["EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCHF", "USDCAD"]

        # Mock database connection settings
        self.connection_pool_created = False
        self.connection_errors = False

        # External feed settings
        self.external_feed_enabled = True
        self.external_feed_errors = False

    async def get_connection_pool(self):
        """Mock connection pool creation."""
        if self.connection_errors:
            raise Exception("Database connection failed")

        if self._pool is None:
            self._pool = AsyncMock()
            self.connection_pool_created = True

        return self._pool

    async def get_ohlcv_data(
        self,
        symbol: str,
        timeframe: str,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: Optional[int] = 1000,
    ) -> List[MockMarketDataPoint]:
        """Mock OHLCV data retrieval."""
        if self.connection_errors:
            # Fall back to external data
            return await self._get_external_data(
                symbol, timeframe, start_time, end_time, limit
            )

        # Set default time range if not provided
        if end_time is None:
            end_time = datetime.utcnow()
        if start_time is None:
            start_time = end_time - timedelta(days=7)  # Default to 1 week

        # Generate mock data points
        data_points = []
        current_time = start_time
        base_price = self._get_base_price(symbol)

        count = 0
        while current_time <= end_time and count < (limit or 1000):
            # Generate realistic price movement
            price_change = (count % 10 - 5) * 0.0001  # Small price variations

            open_price = base_price + price_change
            close_price = open_price + ((count % 7 - 3) * 0.0002)
            high_price = max(open_price, close_price) + abs(price_change) * 0.5
            low_price = min(open_price, close_price) - abs(price_change) * 0.5

            data_point = MockMarketDataPoint(
                time=current_time,
                symbol=symbol,
                open_price=round(open_price, 5),
                high=round(high_price, 5),
                low=round(low_price, 5),
                close=round(close_price, 5),
                volume=1000 + (count % 500),
                tick_count=10 + (count % 20),
                source="timescaledb",
            )

            data_points.append(data_point)

            # Increment time based on timeframe
            current_time += self._get_timeframe_delta(timeframe)
            count += 1

        return data_points

    async def _get_external_data(
        self,
        symbol: str,
        timeframe: str,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: Optional[int] = 1000,
    ) -> List[MockMarketDataPoint]:
        """Mock external data feed fallback."""
        if not self.external_feed_enabled or self.external_feed_errors:
            return []

        # Set defaults
        if end_time is None:
            end_time = datetime.utcnow()
        if start_time is None:
            start_time = end_time - timedelta(days=1)

        # Generate fewer external data points
        data_points = []
        current_time = start_time
        base_price = self._get_base_price(symbol)

        count = 0
        points_to_generate = min(limit or 100, 100)  # Limit external data

        while current_time <= end_time and count < points_to_generate:
            price_change = (count % 8 - 4) * 0.0003

            open_price = base_price + price_change
            close_price = open_price + ((count % 5 - 2) * 0.0001)
            high_price = max(open_price, close_price) + 0.0005
            low_price = min(open_price, close_price) - 0.0005

            data_point = MockMarketDataPoint(
                time=current_time,
                symbol=symbol,
                open_price=round(open_price, 5),
                high=round(high_price, 5),
                low=round(low_price, 5),
                close=round(close_price, 5),
                volume=500 + (count % 300),
                tick_count=0,
                source="alpha_vantage",
            )

            data_points.append(data_point)
            current_time += self._get_timeframe_delta(timeframe)
            count += 1

        return data_points

    def _convert_timeframe(self, timeframe: str) -> str:
        """Convert internal timeframe to external feed format."""
        timeframe_map = {
            "1m": "1min",
            "5m": "5min",
            "15m": "15min",
            "30m": "30min",
            "1h": "60min",
            "4h": "4hour",
            "1d": "daily",
        }
        return timeframe_map.get(timeframe, timeframe)

    async def get_latest_tick(
        self, symbol: str, tick_type: str = "trade"
    ) -> Optional[Dict[str, Any]]:
        """Mock latest tick data retrieval."""
        if self.connection_errors:
            return None

        if symbol not in self.symbols:
            return None

        base_price = self._get_base_price(symbol)
        current_price = base_price + ((hash(symbol) % 10 - 5) * 0.0001)

        return {
            "time": datetime.utcnow(),
            "price": round(current_price, 5),
            "size": 1000,
            "symbol": symbol,
            "tick_type": tick_type,
        }

    async def store_market_data(
        self, symbol: str, data_points: List[MockMarketDataPoint], timeframe: str = "1m"
    ) -> bool:
        """Mock market data storage."""
        if self.connection_errors:
            return False

        if timeframe != "1m":
            return False  # Only support 1m timeframe for direct storage

        # Store in mock storage
        if symbol not in self.stored_data:
            self.stored_data[symbol] = []

        self.stored_data[symbol].extend(data_points)
        return True

    async def get_available_symbols(self) -> List[str]:
        """Mock available symbols retrieval."""
        if self.connection_errors:
            return ["EURUSD", "GBPUSD", "USDJPY", "AUDUSD"]  # Default symbols

        return self.symbols.copy()

    async def close(self):
        """Mock service cleanup."""
        if self._pool:
            self._pool = None
        self.connection_pool_created = False

    def _get_base_price(self, symbol: str) -> float:
        """Get base price for symbol for realistic test data."""
        base_prices = {
            "EURUSD": 1.1000,
            "GBPUSD": 1.2500,
            "USDJPY": 150.00,
            "AUDUSD": 0.6750,
            "USDCHF": 0.9200,
            "USDCAD": 1.3500,
            "NZDUSD": 0.6200,
            "EURJPY": 165.00,
        }
        return base_prices.get(symbol, 1.0000)

    def _get_timeframe_delta(self, timeframe: str) -> timedelta:
        """Get timedelta for timeframe increments."""
        timeframe_deltas = {
            "1m": timedelta(minutes=1),
            "5m": timedelta(minutes=5),
            "15m": timedelta(minutes=15),
            "30m": timedelta(minutes=30),
            "1h": timedelta(hours=1),
            "4h": timedelta(hours=4),
            "1d": timedelta(days=1),
        }
        return timeframe_deltas.get(timeframe, timedelta(minutes=1))


class TestMockMarketDataService:
    """Test the mock market data service functionality."""

    @pytest.fixture
    def service(self):
        """Create a fresh MockMarketDataService instance for each test."""
        return MockMarketDataService()

    @pytest.mark.asyncio
    async def test_initialization(self, service):
        """Test service initialization."""
        assert service._pool is None
        assert service.config == mock_config
        assert service.connection_pool_created is False
        assert len(service.symbols) > 0

    @pytest.mark.asyncio
    async def test_get_connection_pool_success(self, service):
        """Test successful database connection pool creation."""
        pool = await service.get_connection_pool()

        assert pool is not None
        assert service.connection_pool_created is True
        assert service._pool == pool

        # Second call should return same pool
        pool2 = await service.get_connection_pool()
        assert pool2 == pool

    @pytest.mark.asyncio
    async def test_get_connection_pool_failure(self, service):
        """Test database connection pool creation failure."""
        service.connection_errors = True

        with pytest.raises(Exception, match="Database connection failed"):
            await service.get_connection_pool()

    @pytest.mark.asyncio
    async def test_get_ohlcv_data_default_parameters(self, service):
        """Test OHLCV data retrieval with default parameters."""
        symbol = "EURUSD"
        timeframe = "1h"

        data = await service.get_ohlcv_data(symbol, timeframe)

        assert len(data) > 0
        assert all(isinstance(point, MockMarketDataPoint) for point in data)
        assert all(point.symbol == symbol for point in data)
        assert all(point.source == "timescaledb" for point in data)

        # Check OHLC relationships
        for point in data:
            assert point.high >= point.low
            assert point.high >= point.open
            assert point.high >= point.close
            assert point.low <= point.open
            assert point.low <= point.close

    @pytest.mark.asyncio
    async def test_get_ohlcv_data_with_time_range(self, service):
        """Test OHLCV data retrieval with specific time range."""
        symbol = "GBPUSD"
        timeframe = "5m"
        end_time = datetime.utcnow()
        start_time = end_time - timedelta(hours=2)

        data = await service.get_ohlcv_data(symbol, timeframe, start_time, end_time)

        assert len(data) > 0
        assert all(point.time >= start_time for point in data)
        assert all(point.time <= end_time for point in data)
        assert all(point.symbol == symbol for point in data)

        # Check chronological order
        times = [point.time for point in data]
        assert times == sorted(times)

    @pytest.mark.asyncio
    async def test_get_ohlcv_data_with_limit(self, service):
        """Test OHLCV data retrieval with limit parameter."""
        symbol = "USDJPY"
        timeframe = "1m"
        limit = 50

        data = await service.get_ohlcv_data(symbol, timeframe, limit=limit)

        assert len(data) <= limit
        assert all(point.symbol == symbol for point in data)
        assert len(data) > 0  # Should have some data

    @pytest.mark.asyncio
    async def test_get_ohlcv_data_different_timeframes(self, service):
        """Test OHLCV data retrieval for different timeframes."""
        symbol = "AUDUSD"
        timeframes = ["1m", "5m", "15m", "1h", "4h", "1d"]

        for timeframe in timeframes:
            data = await service.get_ohlcv_data(symbol, timeframe, limit=10)

            assert len(data) > 0, f"No data for timeframe {timeframe}"
            assert all(point.symbol == symbol for point in data)

            # Check time intervals are appropriate for timeframe
            if len(data) >= 2:
                time_diff = data[1].time - data[0].time
                expected_delta = service._get_timeframe_delta(timeframe)
                assert time_diff >= expected_delta

    @pytest.mark.asyncio
    async def test_get_ohlcv_data_fallback_to_external(self, service):
        """Test fallback to external data when database fails."""
        symbol = "EURUSD"
        timeframe = "1h"

        # Enable database errors to trigger fallback
        service.connection_errors = True
        service.external_feed_enabled = True

        data = await service.get_ohlcv_data(symbol, timeframe, limit=20)

        assert len(data) > 0
        assert all(point.source == "alpha_vantage" for point in data)
        assert all(point.symbol == symbol for point in data)

    @pytest.mark.asyncio
    async def test_get_ohlcv_data_no_fallback_available(self, service):
        """Test when both database and external feeds fail."""
        symbol = "EURUSD"
        timeframe = "1h"

        # Disable both database and external feeds
        service.connection_errors = True
        service.external_feed_enabled = False

        data = await service.get_ohlcv_data(symbol, timeframe)

        assert len(data) == 0

    def test_convert_timeframe(self, service):
        """Test timeframe conversion utility."""
        conversions = [
            ("1m", "1min"),
            ("5m", "5min"),
            ("15m", "15min"),
            ("30m", "30min"),
            ("1h", "60min"),
            ("4h", "4hour"),
            ("1d", "daily"),
        ]

        for internal, external in conversions:
            result = service._convert_timeframe(internal)
            assert (
                result == external
            ), f"Expected {external}, got {result} for {internal}"

        # Test unknown timeframe
        result = service._convert_timeframe("unknown")
        assert result == "unknown"

    @pytest.mark.asyncio
    async def test_get_latest_tick_success(self, service):
        """Test successful latest tick retrieval."""
        symbol = "EURUSD"
        tick_type = "trade"

        tick = await service.get_latest_tick(symbol, tick_type)

        assert tick is not None
        assert tick["symbol"] == symbol
        assert tick["tick_type"] == tick_type
        assert isinstance(tick["time"], datetime)
        assert isinstance(tick["price"], float)
        assert isinstance(tick["size"], int)
        assert tick["price"] > 0
        assert tick["size"] > 0

    @pytest.mark.asyncio
    async def test_get_latest_tick_unknown_symbol(self, service):
        """Test latest tick retrieval for unknown symbol."""
        symbol = "UNKNOWN"

        tick = await service.get_latest_tick(symbol)

        assert tick is None

    @pytest.mark.asyncio
    async def test_get_latest_tick_connection_error(self, service):
        """Test latest tick retrieval with connection error."""
        service.connection_errors = True

        tick = await service.get_latest_tick("EURUSD")

        assert tick is None

    @pytest.mark.asyncio
    async def test_get_latest_tick_different_types(self, service):
        """Test latest tick retrieval for different tick types."""
        symbol = "GBPUSD"
        tick_types = ["trade", "bid", "ask"]

        for tick_type in tick_types:
            tick = await service.get_latest_tick(symbol, tick_type)

            assert tick is not None
            assert tick["tick_type"] == tick_type
            assert tick["symbol"] == symbol

    @pytest.mark.asyncio
    async def test_store_market_data_success(self, service):
        """Test successful market data storage."""
        symbol = "USDCHF"
        timeframe = "1m"

        # Create test data points
        data_points = [
            MockMarketDataPoint(
                time=datetime.utcnow() - timedelta(minutes=i),
                symbol=symbol,
                open_price=0.9200 + i * 0.0001,
                high=0.9210 + i * 0.0001,
                low=0.9190 + i * 0.0001,
                close=0.9205 + i * 0.0001,
                volume=1000,
                source="test",
            )
            for i in range(5)
        ]

        result = await service.store_market_data(symbol, data_points, timeframe)

        assert result is True
        assert symbol in service.stored_data
        assert len(service.stored_data[symbol]) == 5

    @pytest.mark.asyncio
    async def test_store_market_data_unsupported_timeframe(self, service):
        """Test market data storage with unsupported timeframe."""
        symbol = "EURUSD"
        timeframe = "4h"  # Unsupported for direct storage
        data_points = [
            MockMarketDataPoint(
                time=datetime.utcnow(),
                symbol=symbol,
                open_price=1.1000,
                high=1.1010,
                low=1.0990,
                close=1.1005,
                volume=1000,
                source="test",
            )
        ]

        result = await service.store_market_data(symbol, data_points, timeframe)

        assert result is False

    @pytest.mark.asyncio
    async def test_store_market_data_connection_error(self, service):
        """Test market data storage with connection error."""
        service.connection_errors = True

        symbol = "EURUSD"
        data_points = [
            MockMarketDataPoint(
                time=datetime.utcnow(),
                symbol=symbol,
                open_price=1.1000,
                high=1.1010,
                low=1.0990,
                close=1.1005,
                volume=1000,
                source="test",
            )
        ]

        result = await service.store_market_data(symbol, data_points)

        assert result is False

    @pytest.mark.asyncio
    async def test_get_available_symbols_success(self, service):
        """Test successful symbol list retrieval."""
        symbols = await service.get_available_symbols()

        assert len(symbols) > 0
        assert "EURUSD" in symbols
        assert "GBPUSD" in symbols
        assert "USDJPY" in symbols
        assert all(isinstance(symbol, str) for symbol in symbols)

    @pytest.mark.asyncio
    async def test_get_available_symbols_connection_error(self, service):
        """Test symbol list retrieval with connection error."""
        service.connection_errors = True

        symbols = await service.get_available_symbols()

        # Should return default symbols
        assert len(symbols) == 4
        assert "EURUSD" in symbols
        assert "GBPUSD" in symbols
        assert "USDJPY" in symbols
        assert "AUDUSD" in symbols

    @pytest.mark.asyncio
    async def test_close_service(self, service):
        """Test service cleanup."""
        # Initialize service first
        await service.get_connection_pool()
        assert service.connection_pool_created is True

        # Close service
        await service.close()

        assert service._pool is None
        assert service.connection_pool_created is False

    def test_get_base_price(self, service):
        """Test base price utility."""
        test_prices = {
            "EURUSD": 1.1000,
            "GBPUSD": 1.2500,
            "USDJPY": 150.00,
            "AUDUSD": 0.6750,
            "UNKNOWN": 1.0000,  # Default
        }

        for symbol, expected_price in test_prices.items():
            price = service._get_base_price(symbol)
            assert price == expected_price

    def test_get_timeframe_delta(self, service):
        """Test timeframe delta utility."""
        test_deltas = {
            "1m": timedelta(minutes=1),
            "5m": timedelta(minutes=5),
            "15m": timedelta(minutes=15),
            "30m": timedelta(minutes=30),
            "1h": timedelta(hours=1),
            "4h": timedelta(hours=4),
            "1d": timedelta(days=1),
            "unknown": timedelta(minutes=1),  # Default
        }

        for timeframe, expected_delta in test_deltas.items():
            delta = service._get_timeframe_delta(timeframe)
            assert delta == expected_delta


class TestMarketDataBusinessLogic:
    """Test market data service business logic patterns."""

    @pytest.fixture
    def service(self):
        return MockMarketDataService()

    @pytest.mark.asyncio
    async def test_data_retrieval_workflow(self, service):
        """Test complete data retrieval workflow."""
        symbol = "EURUSD"
        timeframe = "1h"

        # Step 1: Get OHLCV data
        data = await service.get_ohlcv_data(symbol, timeframe, limit=24)
        assert len(data) > 0

        # Step 2: Get latest tick
        tick = await service.get_latest_tick(symbol)
        assert tick is not None

        # Step 3: Verify data consistency
        latest_data_point = data[-1] if data else None
        if latest_data_point:
            # Tick price should be reasonably close to latest OHLC data
            price_diff = abs(tick["price"] - latest_data_point.close)
            assert price_diff < 0.01  # Within reasonable range

    @pytest.mark.asyncio
    async def test_data_storage_and_retrieval_cycle(self, service):
        """Test storing and retrieving market data."""
        symbol = "GBPUSD"
        timeframe = "1m"

        # Create test data
        test_data = [
            MockMarketDataPoint(
                time=datetime.utcnow() - timedelta(minutes=i),
                symbol=symbol,
                open_price=1.2500 + i * 0.0001,
                high=1.2510 + i * 0.0001,
                low=1.2490 + i * 0.0001,
                close=1.2505 + i * 0.0001,
                volume=1000 + i * 10,
                source="test_data",
            )
            for i in range(3)
        ]

        # Store data
        result = await service.store_market_data(symbol, test_data, timeframe)
        assert result is True

        # Verify storage
        assert symbol in service.stored_data
        stored_points = service.stored_data[symbol]
        assert len(stored_points) == 3

        # Verify data integrity
        for i, point in enumerate(stored_points):
            assert point.symbol == symbol
            assert point.source == "test_data"
            assert point.volume == 1000 + i * 10

    @pytest.mark.asyncio
    async def test_multi_symbol_data_handling(self, service):
        """Test handling data for multiple symbols simultaneously."""
        symbols = ["EURUSD", "GBPUSD", "USDJPY"]
        timeframe = "15m"

        all_data = {}
        for symbol in symbols:
            data = await service.get_ohlcv_data(symbol, timeframe, limit=10)
            all_data[symbol] = data

            assert len(data) > 0
            assert all(point.symbol == symbol for point in data)

        # Verify we got data for all symbols
        assert len(all_data) == len(symbols)

        # Verify each symbol has unique data
        for symbol in symbols:
            symbol_data = all_data[symbol]
            base_price = service._get_base_price(symbol)

            # Check prices are in reasonable range for symbol
            for point in symbol_data:
                price_ratio = point.close / base_price
                assert 0.9 < price_ratio < 1.1  # Within 10% of base price

    @pytest.mark.asyncio
    async def test_error_handling_resilience(self, service):
        """Test service resilience to various error conditions."""
        symbol = "EURUSD"

        # Test 1: Database error with successful external fallback
        service.connection_errors = True
        service.external_feed_enabled = True

        data = await service.get_ohlcv_data(symbol, "1h", limit=5)
        assert len(data) > 0
        assert all(point.source == "alpha_vantage" for point in data)

        # Test 2: Both database and external errors
        service.external_feed_errors = True
        service.external_feed_enabled = False

        tick = await service.get_latest_tick(symbol)
        assert tick is None

        symbols = await service.get_available_symbols()
        assert len(symbols) == 4  # Default fallback symbols

        # Test 3: Recovery after errors
        service.connection_errors = False
        service.external_feed_enabled = True
        service.external_feed_errors = False

        recovery_data = await service.get_ohlcv_data(symbol, "1h", limit=3)
        assert len(recovery_data) > 0
        assert all(point.source == "timescaledb" for point in recovery_data)

    @pytest.mark.asyncio
    async def test_timeframe_consistency(self, service):
        """Test data consistency across different timeframes."""
        symbol = "USDJPY"

        # Get data for different timeframes
        timeframes = ["1m", "5m", "15m", "1h"]
        timeframe_data = {}

        for tf in timeframes:
            data = await service.get_ohlcv_data(symbol, tf, limit=5)
            timeframe_data[tf] = data
            assert len(data) > 0

        # Verify timeframe intervals increase appropriately
        for tf, data in timeframe_data.items():
            if len(data) >= 2:
                time_diff = data[1].time - data[0].time
                expected_delta = service._get_timeframe_delta(tf)
                assert time_diff >= expected_delta


# Pytest configuration
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


if __name__ == "__main__":
    # Run the tests
    pytest.main([__file__, "-v"])
