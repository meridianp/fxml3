"""Pytest configuration and fixtures for FXML4 tests."""

import asyncio

# Import for API testing
import os

# Import automatic cleanup fixtures
from tests.fixtures.cleanup_fixtures import (
    auto_cleanup_resources,
    monitor_asyncio_tasks,
    monitor_rabbitmq,
    monitor_redis,
    monitor_websockets,
    register_cleanup_fixtures,
)

# Register cleanup fixtures globally
_cleanup_fixtures = register_cleanup_fixtures()
import sqlite3
import tempfile
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Generator, Optional
from unittest.mock import MagicMock, Mock, patch

import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient

try:
    # Only import real app if environment is configured
    if os.getenv("FXML4_JWT_SECRET_KEY"):
        from fxml4.api.auth.auth import create_access_token, get_password_hash
        from fxml4.api.main import app
    else:
        # Create mock app for development testing
        app = MagicMock()
        app.title = "FXML4 API (Mock)"

        # Mock authentication functions for development
        def mock_create_access_token(data: dict) -> str:
            return "mock_jwt_token_for_testing"

        def mock_get_password_hash(password: str) -> str:
            return f"mock_hash_{password}"

        create_access_token = mock_create_access_token
        get_password_hash = mock_get_password_hash
except ImportError as e:
    app = None

    # Mock authentication functions when imports fail
    def mock_create_access_token(data: dict) -> str:
        return "mock_jwt_token_for_testing"

    def mock_get_password_hash(password: str) -> str:
        return f"mock_hash_{password}"

    create_access_token = mock_create_access_token
    get_password_hash = mock_get_password_hash


@pytest.fixture
def sample_ohlc_data():
    """Generate sample OHLC data for testing."""
    np.random.seed(42)

    # Generate 100 bars of sample data
    n_bars = 100
    dates = pd.date_range(start="2024-01-01", periods=n_bars, freq="1H")

    # Start with a base price and add random walk
    base_price = 1.1000
    returns = np.random.normal(0, 0.001, n_bars)
    prices = base_price + np.cumsum(returns)

    # Generate OHLC from close prices
    data = []
    for i, (date, close) in enumerate(zip(dates, prices)):
        # Add some realistic spread for OHLC
        spread = np.random.uniform(0.0001, 0.0005)
        high = close + spread
        low = close - spread
        open_price = prices[i - 1] if i > 0 else close
        volume = np.random.randint(1000, 10000)

        data.append(
            {
                "time": date,
                "open": open_price,
                "high": high,
                "low": low,
                "close": close,
                "volume": volume,
            }
        )

    return pd.DataFrame(data)


@pytest.fixture
def sample_config():
    """Sample configuration for testing."""
    return {
        "api": {"host": "0.0.0.0", "port": 8000, "debug": True},
        "database": {
            "host": "localhost",
            "port": 5433,
            "name": "fxml4_test",
            "user": "test_user",
            "password": "test_pass",
        },
        "backtesting": {
            "commission": 0.0002,
            "slippage": 0.0001,
            "initial_capital": 10000.0,
        },
        "ml": {
            "features": {
                "technical_indicators": True,
                "price_patterns": True,
                "volume_analysis": True,
                "session_features": False,
            }
        },
        "wave_analysis": {
            "min_wave_length": 5,
            "max_retracement": 0.618,
            "fibonacci_tolerance": 0.05,
        },
        "worker": {
            "name": "test-worker",
            "poll_interval": 10,
            "max_concurrent_tasks": 2,
        },
    }


@pytest.fixture
def mock_strategy_params():
    """Mock strategy parameters for testing."""
    return {
        "symbol": "EURUSD",
        "timeframe": "1h",
        "risk_pct": 0.02,
        "short_ma": 10,
        "long_ma": 20,
    }


@pytest.fixture
def sample_signals():
    """Sample trading signals for testing."""
    from fxml4.strategy.integrated_strategy import Signal, SignalSource, SignalType

    return [
        Signal(
            signal_type=SignalType.ENTRY_LONG,
            strength=0.8,
            source=SignalSource.ML,
            timestamp=pd.Timestamp("2024-01-01 10:00:00"),
            symbol="EURUSD",
            timeframe="1h",
            metadata={"model_confidence": 0.85},
        ),
        Signal(
            signal_type=SignalType.ENTRY_LONG,
            strength=0.6,
            source=SignalSource.WAVE,
            timestamp=pd.Timestamp("2024-01-01 10:00:00"),
            symbol="EURUSD",
            timeframe="1h",
            metadata={"wave_pattern": "impulse_wave_5"},
        ),
        Signal(
            signal_type=SignalType.EXIT_LONG,
            strength=0.7,
            source=SignalSource.TECHNICAL,
            timestamp=pd.Timestamp("2024-01-01 11:00:00"),
            symbol="EURUSD",
            timeframe="1h",
            metadata={"rsi": 75},
        ),
    ]


# ============================================================================
# Enhanced Fixtures for Comprehensive Testing
# ============================================================================

# Import centralized event loop fixture to prevent conflicts
from tests.fixtures.event_loop_fixtures import (
    async_client,
    cleanup_tasks,
    event_loop,
    event_loop_policy,
    isolated_async_context,
)


@pytest.fixture
def mock_database_connection():
    """Mock database connection for testing."""
    mock_conn = Mock()
    mock_cursor = Mock()
    mock_conn.cursor.return_value = mock_cursor
    mock_conn.commit = Mock()
    mock_conn.rollback = Mock()
    mock_conn.close = Mock()

    # Common cursor methods
    mock_cursor.execute = Mock()
    mock_cursor.fetchone = Mock()
    mock_cursor.fetchall = Mock()
    mock_cursor.fetchmany = Mock()
    mock_cursor.close = Mock()

    return mock_conn


@pytest.fixture
def test_database():
    """Create a temporary SQLite database for testing."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name

    # Create connection and basic tables
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Create test tables
    cursor.execute(
        """
        CREATE TABLE test_market_data (
            id INTEGER PRIMARY KEY,
            symbol TEXT,
            timestamp TEXT,
            open_price REAL,
            high_price REAL,
            low_price REAL,
            close_price REAL,
            volume INTEGER
        )
    """
    )

    cursor.execute(
        """
        CREATE TABLE test_signals (
            id INTEGER PRIMARY KEY,
            symbol TEXT,
            timestamp TEXT,
            signal_type TEXT,
            strength REAL,
            source TEXT,
            metadata TEXT
        )
    """
    )

    conn.commit()

    yield {"path": db_path, "connection": conn}

    conn.close()
    import os

    os.unlink(db_path)


@pytest.fixture
def api_client():
    """FastAPI test client for API testing."""
    if app is None:
        pytest.skip("FastAPI app not available")

    with TestClient(app) as client:
        yield client


@pytest.fixture
def authenticated_api_client(api_client):
    """API client with authentication token."""
    # Create test token
    token_data = {"sub": "testuser", "scopes": ["user", "read", "write"]}
    token = create_access_token(token_data)

    # Add authorization header to client
    api_client.headers.update({"Authorization": f"Bearer {token}"})

    yield api_client


@pytest.fixture
def admin_api_client(api_client):
    """API client with admin authentication token."""
    # Create admin token
    token_data = {"sub": "admin", "scopes": ["admin", "user", "read", "write"]}
    token = create_access_token(token_data)

    # Add authorization header to client
    api_client.headers.update({"Authorization": f"Bearer {token}"})

    yield api_client


@pytest.fixture
def mock_timescaledb_client():
    """Mock TimescaleDB client for testing."""
    mock_client = Mock()

    # Mock methods with realistic return values
    mock_client.store_tick.return_value = True
    mock_client.store_ticks.return_value = 100
    mock_client.store_candle.return_value = True
    mock_client.store_candles.return_value = 50
    mock_client.get_latest_tick.return_value = {
        "time": datetime.now(timezone.utc),
        "symbol": "EURUSD",
        "price": 1.1000,
        "size": 1000,
        "tick_type": "trade",
        "source": "ib",
    }
    mock_client.get_tick_count.return_value = 1000
    mock_client.get_candle_count.return_value = 100

    return mock_client


@pytest.fixture
def sample_tick_data():
    """Generate sample tick data for testing."""
    np.random.seed(42)

    base_time = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    base_price = 1.1000

    ticks = []
    for i in range(100):
        tick_time = base_time + timedelta(seconds=i)
        price_change = np.random.normal(0, 0.0001)
        price = base_price + price_change
        size = np.random.randint(100, 1000)

        ticks.append(
            {
                "symbol": "EURUSD",
                "timestamp": tick_time,
                "price": price,
                "size": size,
                "tick_type": "trade",
                "source": "ib",
            }
        )

    return ticks


@pytest.fixture
def sample_candle_data():
    """Generate sample candle data for testing."""
    np.random.seed(42)

    base_time = datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    base_price = 1.1000

    candles = []
    current_price = base_price

    for i in range(24):  # 24 hours of data
        candle_time = base_time + timedelta(hours=i)

        # Generate OHLC for the hour
        open_price = current_price
        price_changes = np.random.normal(0, 0.001, 4)  # For high, low, close

        high_price = open_price + abs(price_changes[0])
        low_price = open_price - abs(price_changes[1])
        close_price = open_price + price_changes[2]

        # Ensure high >= open,close and low <= open,close
        high_price = max(high_price, open_price, close_price)
        low_price = min(low_price, open_price, close_price)

        volume = np.random.randint(5000, 20000)
        tick_count = np.random.randint(100, 500)

        candles.append(
            {
                "symbol": "EURUSD",
                "timestamp": candle_time,
                "open": open_price,
                "high": high_price,
                "low": low_price,
                "close": close_price,
                "volume": volume,
                "tick_count": tick_count,
                "source": "ib",
            }
        )

        current_price = close_price

    return candles


@pytest.fixture
def mock_ib_adapter():
    """Mock Interactive Brokers adapter for testing."""
    mock_adapter = Mock()

    # Mock connection methods
    mock_adapter.connect.return_value = True
    mock_adapter.disconnect.return_value = True
    mock_adapter.is_connected.return_value = True

    # Mock data methods
    mock_adapter.request_market_data.return_value = True
    mock_adapter.cancel_market_data.return_value = True

    # Mock trading methods
    mock_adapter.place_order.return_value = {"order_id": 12345, "status": "Submitted"}
    mock_adapter.cancel_order.return_value = True
    mock_adapter.get_positions.return_value = []
    mock_adapter.get_account_info.return_value = {"total_cash": 10000.0}

    return mock_adapter


@pytest.fixture
def mock_ml_model():
    """Mock ML model for testing."""
    mock_model = Mock()

    # Mock prediction methods
    mock_model.predict.return_value = np.array([0.75])  # Bullish signal
    mock_model.predict_proba.return_value = np.array(
        [[0.25, 0.75]]
    )  # [bearish, bullish]
    mock_model.score.return_value = 0.85

    # Mock training methods
    mock_model.fit.return_value = mock_model
    mock_model.feature_importances_ = np.array([0.3, 0.2, 0.15, 0.1, 0.25])

    return mock_model


@pytest.fixture
def sample_features_dataframe():
    """Generate sample features DataFrame for ML testing."""
    np.random.seed(42)

    n_samples = 1000
    dates = pd.date_range(start="2024-01-01", periods=n_samples, freq="1H")

    data = {
        "timestamp": dates,
        "symbol": ["EURUSD"] * n_samples,
        "sma_10": np.random.normal(1.1000, 0.01, n_samples),
        "sma_20": np.random.normal(1.1000, 0.01, n_samples),
        "rsi_14": np.random.uniform(20, 80, n_samples),
        "macd": np.random.normal(0, 0.001, n_samples),
        "bollinger_upper": np.random.normal(1.1050, 0.01, n_samples),
        "bollinger_lower": np.random.normal(1.0950, 0.01, n_samples),
        "volume_sma": np.random.randint(5000, 15000, n_samples),
        "price_change_1h": np.random.normal(0, 0.001, n_samples),
        "volatility_1h": np.random.uniform(0.0001, 0.001, n_samples),
        "target": np.random.choice(
            [0, 1], n_samples, p=[0.6, 0.4]
        ),  # 40% positive signals
    }

    return pd.DataFrame(data).set_index("timestamp")


@pytest.fixture
def mock_config():
    """Mock configuration for testing."""
    config = Mock()
    config.get.side_effect = lambda key, default=None: {
        "database.host": "localhost",
        "database.port": 5432,
        "database.name": "fxml4_test",
        "database.user": "test_user",
        "database.password": "test_pass",
        "api.host": "0.0.0.0",
        "api.port": 8000,
        "api.debug": True,
        "ml.models_dir": "/tmp/test_models",
        "backtesting.initial_capital": 10000.0,
        "backtesting.commission": 0.001,
        "interactive_brokers.host": "127.0.0.1",
        "interactive_brokers.port": 7497,
        "redis.host": "localhost",
        "redis.port": 6379,
    }.get(key, default)

    config.get_database_url.return_value = (
        "postgresql://test_user:test_pass@localhost:5432/fxml4_test"
    )
    config.to_dict.return_value = {}

    return config


@pytest.fixture
def sample_backtest_results():
    """Generate sample backtest results for testing."""
    return {
        "total_return": 0.15,
        "annual_return": 0.12,
        "max_drawdown": 0.08,
        "sharpe_ratio": 1.45,
        "sortino_ratio": 1.78,
        "win_rate": 0.58,
        "profit_factor": 1.35,
        "total_trades": 150,
        "winning_trades": 87,
        "losing_trades": 63,
        "avg_trade": 0.001,
        "avg_win": 0.0025,
        "avg_loss": -0.0015,
        "largest_win": 0.012,
        "largest_loss": -0.008,
        "start_date": "2024-01-01",
        "end_date": "2024-03-31",
        "duration_days": 90,
    }


@pytest.fixture
def performance_timer():
    """Timer fixture for performance testing."""
    import time

    class Timer:
        def __init__(self):
            self.start_time = None
            self.end_time = None

        def start(self):
            self.start_time = time.perf_counter()

        def stop(self):
            self.end_time = time.perf_counter()
            return self.elapsed

        @property
        def elapsed(self):
            if self.start_time is None:
                return None
            end = self.end_time or time.perf_counter()
            return end - self.start_time

    return Timer()


@pytest.fixture
def memory_monitor():
    """Memory monitoring fixture for performance testing."""
    import os

    import psutil

    process = psutil.Process(os.getpid())

    class MemoryMonitor:
        def __init__(self):
            self.initial_memory = None
            self.peak_memory = None

        def start(self):
            self.initial_memory = process.memory_info().rss
            self.peak_memory = self.initial_memory

        def update(self):
            current = process.memory_info().rss
            if current > self.peak_memory:
                self.peak_memory = current

        def get_usage(self):
            self.update()
            return {
                "initial_mb": self.initial_memory / 1024 / 1024,
                "current_mb": process.memory_info().rss / 1024 / 1024,
                "peak_mb": self.peak_memory / 1024 / 1024,
                "delta_mb": (self.peak_memory - self.initial_memory) / 1024 / 1024,
            }

    return MemoryMonitor()


@pytest.fixture
def test_user_db():
    """Test user database for authentication testing."""
    return {
        "testuser": {
            "username": "testuser",
            "full_name": "Test User",
            "email": "test@example.com",
            "hashed_password": get_password_hash("testpass123"),
            "disabled": False,
            "scopes": ["user", "read"],
        },
        "admin": {
            "username": "admin",
            "full_name": "Admin User",
            "email": "admin@example.com",
            "hashed_password": get_password_hash("adminpass123"),
            "disabled": False,
            "scopes": ["admin", "user", "read", "write"],
        },
        "disableduser": {
            "username": "disableduser",
            "full_name": "Disabled User",
            "email": "disabled@example.com",
            "hashed_password": get_password_hash("disabledpass123"),
            "disabled": True,
            "scopes": ["user", "read"],
        },
    }


@pytest.fixture
def mock_redis_client():
    """Mock Redis client for testing."""
    mock_redis = Mock()

    # Mock basic Redis operations
    mock_redis.get.return_value = None
    mock_redis.set.return_value = True
    mock_redis.delete.return_value = 1
    mock_redis.exists.return_value = False
    mock_redis.expire.return_value = True
    mock_redis.ping.return_value = True

    # Mock hash operations
    mock_redis.hget.return_value = None
    mock_redis.hset.return_value = True
    mock_redis.hdel.return_value = 1
    mock_redis.hgetall.return_value = {}

    # Mock list operations
    mock_redis.lpush.return_value = 1
    mock_redis.rpop.return_value = None
    mock_redis.llen.return_value = 0

    return mock_redis


# ============================================================================
# Test Data Factories
# ============================================================================


class DataFactory:
    """Factory class for generating test data."""

    @staticmethod
    def create_market_data(
        symbol: str = "EURUSD",
        start_time: Optional[datetime] = None,
        periods: int = 100,
        timeframe: str = "1H",
    ) -> pd.DataFrame:
        """Create realistic market data."""
        if start_time is None:
            start_time = datetime(2024, 1, 1, tzinfo=timezone.utc)

        dates = pd.date_range(start=start_time, periods=periods, freq=timeframe)

        # Generate realistic price data using geometric Brownian motion
        np.random.seed(42)
        returns = np.random.normal(
            0.0001, 0.01, periods
        )  # Small drift, realistic volatility
        log_prices = np.cumsum(returns)
        prices = 1.1000 * np.exp(log_prices)  # Start at 1.1000

        # Generate OHLC data
        data = []
        for i, (date, close) in enumerate(zip(dates, prices)):
            open_price = prices[i - 1] if i > 0 else close

            # Add intrabar volatility
            intrabar_range = np.random.uniform(0.0002, 0.001)
            high = max(open_price, close) + intrabar_range * np.random.uniform(0.3, 1.0)
            low = min(open_price, close) - intrabar_range * np.random.uniform(0.3, 1.0)

            volume = np.random.randint(5000, 25000)

            data.append(
                {
                    "time": date,
                    "symbol": symbol,
                    "open": open_price,
                    "high": high,
                    "low": low,
                    "close": close,
                    "volume": volume,
                }
            )

        return pd.DataFrame(data).set_index("time")

    @staticmethod
    def create_signals(
        symbol: str = "EURUSD", start_time: Optional[datetime] = None, count: int = 10
    ) -> list:
        """Create sample trading signals."""
        if start_time is None:
            start_time = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)

        signals = []
        for i in range(count):
            signal_time = start_time + timedelta(hours=i * 2)

            # Alternate between long and short signals
            signal_type = "ENTRY_LONG" if i % 2 == 0 else "ENTRY_SHORT"
            strength = np.random.uniform(0.6, 0.9)
            source = np.random.choice(["ML", "WAVE", "TECHNICAL"])

            signals.append(
                {
                    "timestamp": signal_time,
                    "symbol": symbol,
                    "signal_type": signal_type,
                    "strength": strength,
                    "source": source,
                    "metadata": {
                        "confidence": strength,
                        "features_used": ["sma", "rsi", "macd"],
                    },
                }
            )

        return signals


@pytest.fixture
def data_factory():
    """Provide access to DataFactory."""
    return DataFactory


# ============================================================================
# Assertion Helpers
# ============================================================================


class AssertionHelpers:
    """Helper methods for common test assertions."""

    @staticmethod
    def assert_valid_ohlc(df: pd.DataFrame):
        """Assert that OHLC data is valid."""
        assert not df.empty, "OHLC data should not be empty"
        assert all(
            col in df.columns for col in ["open", "high", "low", "close"]
        ), "Missing OHLC columns"

        # High should be >= open, close
        assert (df["high"] >= df["open"]).all(), "High should be >= open"
        assert (df["high"] >= df["close"]).all(), "High should be >= close"

        # Low should be <= open, close
        assert (df["low"] <= df["open"]).all(), "Low should be <= open"
        assert (df["low"] <= df["close"]).all(), "Low should be <= close"

        # No negative prices
        assert (
            (df[["open", "high", "low", "close"]] > 0).all().all()
        ), "Prices should be positive"

    @staticmethod
    def assert_response_time(elapsed_time: float, max_time: float):
        """Assert that operation completed within time limit."""
        assert (
            elapsed_time <= max_time
        ), f"Operation took {elapsed_time:.3f}s, expected <= {max_time}s"

    @staticmethod
    def assert_memory_usage(memory_delta: float, max_delta: float):
        """Assert that memory usage is within limits."""
        assert (
            memory_delta <= max_delta
        ), f"Memory usage increased by {memory_delta:.1f}MB, expected <= {max_delta}MB"

    @staticmethod
    def assert_api_response(
        response, expected_status: int = 200, required_fields: Optional[list] = None
    ):
        """Assert API response is valid."""
        assert (
            response.status_code == expected_status
        ), f"Expected status {expected_status}, got {response.status_code}"

        if expected_status == 200 and required_fields:
            data = response.json()
            for field in required_fields:
                assert field in data, f"Required field '{field}' missing from response"


@pytest.fixture
def assert_helpers():
    """Provide access to assertion helpers."""
    return AssertionHelpers


# ============================================================================
# Context Managers for Testing
# ============================================================================


@contextmanager
def does_not_raise():
    """Context manager for asserting that no exception is raised."""
    yield


@contextmanager
def temp_env_vars(**kwargs):
    """Temporarily set environment variables for testing."""
    import os

    old_vars = {}

    # Save old values
    for key, value in kwargs.items():
        old_vars[key] = os.environ.get(key)
        os.environ[key] = str(value)

    try:
        yield
    finally:
        # Restore old values
        for key, old_value in old_vars.items():
            if old_value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = old_value


@pytest.fixture
def temp_env():
    """Provide access to temporary environment variable context manager."""
    return temp_env_vars
