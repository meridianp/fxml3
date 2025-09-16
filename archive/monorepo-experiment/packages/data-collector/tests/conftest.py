"""Shared fixtures and configuration for data-collector tests."""

import pytest
import asyncio
from datetime import datetime, timedelta
from unittest.mock import Mock, AsyncMock


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def mock_async_context_manager():
    """Create a mock async context manager."""
    class AsyncContextManager:
        async def __aenter__(self):
            return self
        
        async def __aexit__(self, exc_type, exc_val, exc_tb):
            pass
    
    return AsyncContextManager()


@pytest.fixture
def sample_forex_data():
    """Generate sample forex market data."""
    def _generate_data(symbol="EURUSD", num_bars=10, timeframe="1m"):
        base_time = datetime.now()
        base_price = 1.0850 if symbol == "EURUSD" else 1.2500
        
        bars = []
        for i in range(num_bars):
            timestamp = base_time - timedelta(minutes=i * (1 if timeframe == "1m" else 5))
            
            # Generate realistic OHLC data
            open_price = base_price + (i * 0.0001)
            high_price = open_price + 0.0005
            low_price = open_price - 0.0003
            close_price = open_price + 0.0002
            volume = 1000 + (i * 100)
            
            bars.append({
                "t": int(timestamp.timestamp() * 1000),
                "o": round(open_price, 5),
                "h": round(high_price, 5),
                "l": round(low_price, 5),
                "c": round(close_price, 5),
                "v": volume,
                "vw": round((open_price + close_price) / 2, 5),
                "n": 50 + i
            })
        
        return {
            "status": "OK",
            "ticker": f"C:{symbol}",
            "queryCount": num_bars,
            "resultsCount": num_bars,
            "adjusted": True,
            "results": bars
        }
    
    return _generate_data


@pytest.fixture
def mock_polygon_api_response():
    """Mock Polygon API responses."""
    def _mock_response(status_code=200, data=None, error=None):
        response = Mock()
        response.status_code = status_code
        
        if error:
            response.json = Mock(return_value={"status": "ERROR", "error": error})
        else:
            response.json = Mock(return_value=data or {"status": "OK"})
        
        return response
    
    return _mock_response


@pytest.fixture
def mock_timescaledb_connection():
    """Mock TimescaleDB connection."""
    conn = AsyncMock()
    conn.execute = AsyncMock()
    conn.executemany = AsyncMock()
    conn.fetch = AsyncMock(return_value=[])
    conn.fetchrow = AsyncMock(return_value=None)
    conn.close = AsyncMock()
    
    # Add transaction support
    conn.transaction = Mock(return_value=mock_async_context_manager())
    
    return conn


@pytest.fixture
def performance_metrics():
    """Track performance metrics during tests."""
    class PerformanceTracker:
        def __init__(self):
            self.metrics = {
                "api_calls": 0,
                "db_saves": 0,
                "errors": 0,
                "total_bars": 0,
                "start_time": None,
                "end_time": None
            }
        
        def start(self):
            self.metrics["start_time"] = datetime.now()
        
        def end(self):
            self.metrics["end_time"] = datetime.now()
        
        def record_api_call(self):
            self.metrics["api_calls"] += 1
        
        def record_db_save(self, num_bars=1):
            self.metrics["db_saves"] += 1
            self.metrics["total_bars"] += num_bars
        
        def record_error(self):
            self.metrics["errors"] += 1
        
        def get_duration(self):
            if self.metrics["start_time"] and self.metrics["end_time"]:
                return (self.metrics["end_time"] - self.metrics["start_time"]).total_seconds()
            return None
        
        def get_summary(self):
            return {
                **self.metrics,
                "duration_seconds": self.get_duration(),
                "bars_per_second": (
                    self.metrics["total_bars"] / self.get_duration() 
                    if self.get_duration() else 0
                )
            }
    
    return PerformanceTracker()


@pytest.fixture
def market_hours_checker():
    """Check if current time is within market hours."""
    def _is_market_open(symbol="EURUSD"):
        now = datetime.now()
        weekday = now.weekday()
        
        # Forex market is closed on weekends
        if weekday >= 5:  # Saturday = 5, Sunday = 6
            return False
        
        # Simplified market hours (actual hours vary by symbol)
        # Forex market opens Sunday 5 PM EST and closes Friday 5 PM EST
        if weekday == 0 and now.hour < 17:  # Monday before 5 PM
            return False
        if weekday == 4 and now.hour >= 17:  # Friday after 5 PM
            return False
        
        return True
    
    return _is_market_open


# Markers for different test types
pytest.mark.integration = pytest.mark.integration
pytest.mark.unit = pytest.mark.unit
pytest.mark.slow = pytest.mark.slow
pytest.mark.requires_api_key = pytest.mark.requires_api_key
pytest.mark.requires_db = pytest.mark.requires_db