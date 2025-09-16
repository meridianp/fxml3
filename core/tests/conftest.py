"""
Shared pytest fixtures and configuration for FXML4 core tests.

This module provides reusable test fixtures following TDD best practices.
"""

import asyncio
import os
from datetime import datetime, timedelta
from typing import Any, AsyncGenerator, Dict
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from faker import Faker

# Initialize Faker for test data generation
fake = Faker()


# -----------------------------------------------------------------------------
# Database Fixtures
# -----------------------------------------------------------------------------


@pytest.fixture
def mock_db_session():
    """Mock database session for unit tests."""
    session = MagicMock()
    session.query = MagicMock()
    session.add = MagicMock()
    session.commit = MagicMock()
    session.rollback = MagicMock()
    session.close = MagicMock()
    return session


@pytest_asyncio.fixture
async def async_db_session():
    """Async mock database session."""
    session = AsyncMock()
    session.execute = AsyncMock()
    session.add = AsyncMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.close = AsyncMock()
    yield session
    await session.close()


# -----------------------------------------------------------------------------
# Market Data Fixtures
# -----------------------------------------------------------------------------


@pytest.fixture
def sample_market_data() -> Dict[str, Any]:
    """Generate sample market data for testing."""
    return {
        "symbol": "EUR/USD",
        "bid": 1.0850,
        "ask": 1.0852,
        "last": 1.0851,
        "volume": fake.random_int(min=1000, max=100000),
        "timestamp": datetime.utcnow().isoformat(),
        "open": 1.0845,
        "high": 1.0860,
        "low": 1.0840,
        "close": 1.0851,
    }


@pytest.fixture
def sample_ohlcv_data():
    """Generate sample OHLCV candlestick data."""
    base_time = datetime.utcnow()
    return [
        {
            "timestamp": (base_time - timedelta(minutes=i)).isoformat(),
            "open": 1.0850 + (fake.random_int(-10, 10) / 10000),
            "high": 1.0860 + (fake.random_int(0, 10) / 10000),
            "low": 1.0840 - (fake.random_int(0, 10) / 10000),
            "close": 1.0851 + (fake.random_int(-10, 10) / 10000),
            "volume": fake.random_int(min=1000, max=100000),
        }
        for i in range(100)
    ]


# -----------------------------------------------------------------------------
# Broker Fixtures
# -----------------------------------------------------------------------------


@pytest.fixture
def mock_broker_client():
    """Mock broker client for testing trading operations."""
    client = MagicMock()
    client.connect = AsyncMock(return_value=True)
    client.disconnect = AsyncMock()
    client.place_order = AsyncMock(
        return_value={
            "order_id": fake.uuid4(),
            "status": "PENDING",
            "symbol": "EUR/USD",
            "quantity": 100000,
            "side": "BUY",
        }
    )
    client.cancel_order = AsyncMock(return_value={"status": "CANCELLED"})
    client.get_positions = AsyncMock(return_value=[])
    client.get_account_info = AsyncMock(
        return_value={
            "balance": 100000.0,
            "equity": 100000.0,
            "margin_used": 0.0,
            "margin_available": 100000.0,
        }
    )
    return client


@pytest.fixture
def mock_ib_client():
    """Mock Interactive Brokers client."""
    with patch("core.brokers.ib_adapter.IBApi") as mock_ib:
        client = mock_ib.return_value
        client.connect = MagicMock(return_value=True)
        client.reqMarketDataType = MagicMock()
        client.reqMktData = MagicMock()
        client.placeOrder = MagicMock()
        yield client


@pytest.fixture
def mock_fxcm_client():
    """Mock FXCM client."""
    client = MagicMock()
    client.connect = AsyncMock(return_value=True)
    client.get_model = MagicMock()
    client.create_market_buy_order = AsyncMock()
    client.create_market_sell_order = AsyncMock()
    return client


# -----------------------------------------------------------------------------
# API Request/Response Fixtures
# -----------------------------------------------------------------------------


@pytest.fixture
def sample_auth_request():
    """Sample authentication request payload."""
    return {
        "username": fake.user_name(),
        "password": fake.password(length=12, special_chars=True),
        "two_factor_code": fake.random_number(digits=6, fix_len=True),
    }


@pytest.fixture
def sample_order_request():
    """Sample order request payload."""
    return {
        "symbol": "EUR/USD",
        "side": fake.random_element(["BUY", "SELL"]),
        "quantity": fake.random_int(min=1000, max=100000, step=1000),
        "order_type": fake.random_element(["MARKET", "LIMIT", "STOP"]),
        "price": 1.0850 if fake.boolean() else None,
        "stop_loss": 1.0820 if fake.boolean() else None,
        "take_profit": 1.0880 if fake.boolean() else None,
    }


@pytest.fixture
def mock_jwt_token():
    """Mock JWT token for authentication testing."""
    return "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJ0ZXN0X3VzZXIiLCJleHAiOjE3MjYxNjE2MDB9.test_signature"  # pragma: allowlist secret


# -----------------------------------------------------------------------------
# Machine Learning Fixtures
# -----------------------------------------------------------------------------


@pytest.fixture
def sample_feature_vector():
    """Generate sample feature vector for ML testing."""
    import numpy as np

    return np.random.randn(1, 50)  # 50 features


@pytest.fixture
def mock_ml_model():
    """Mock machine learning model."""
    model = MagicMock()
    model.predict = MagicMock(return_value=np.array([0.65]))  # Bullish signal
    model.predict_proba = MagicMock(return_value=np.array([[0.35, 0.65]]))
    model.fit = MagicMock()
    return model


# -----------------------------------------------------------------------------
# WebSocket Fixtures
# -----------------------------------------------------------------------------


@pytest.fixture
def mock_websocket():
    """Mock WebSocket connection."""
    ws = AsyncMock()
    ws.send = AsyncMock()
    ws.recv = AsyncMock()
    ws.close = AsyncMock()
    ws.closed = False
    return ws


# -----------------------------------------------------------------------------
# Utility Fixtures
# -----------------------------------------------------------------------------


@pytest.fixture
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(autouse=True)
def reset_environment():
    """Reset environment variables before each test."""
    original_env = os.environ.copy()
    yield
    os.environ.clear()
    os.environ.update(original_env)


@pytest.fixture
def performance_timer():
    """Timer fixture for performance testing."""
    import time

    class Timer:
        def __init__(self):
            self.start_time = None
            self.elapsed = 0

        def start(self):
            self.start_time = time.perf_counter()

        def stop(self):
            if self.start_time:
                self.elapsed = time.perf_counter() - self.start_time
                return self.elapsed
            return 0

    return Timer()


# -----------------------------------------------------------------------------
# Test Data Factories
# -----------------------------------------------------------------------------


@pytest.fixture
def trade_factory():
    """Factory for creating test trade objects."""

    def create_trade(**kwargs):
        defaults = {
            "id": fake.uuid4(),
            "symbol": "EUR/USD",
            "side": "BUY",
            "quantity": 100000,
            "entry_price": 1.0850,
            "current_price": 1.0860,
            "profit_loss": 100.0,
            "status": "OPEN",
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
        }
        defaults.update(kwargs)
        return defaults

    return create_trade


@pytest.fixture
def user_factory():
    """Factory for creating test user objects."""

    def create_user(**kwargs):
        defaults = {
            "id": fake.uuid4(),
            "username": fake.user_name(),
            "email": fake.email(),
            "is_active": True,
            "is_verified": True,
            "created_at": datetime.utcnow(),
            "last_login": datetime.utcnow(),
        }
        defaults.update(kwargs)
        return defaults

    return create_user


# -----------------------------------------------------------------------------
# Pytest Configuration
# -----------------------------------------------------------------------------


def pytest_configure(config):
    """Configure pytest with custom markers."""
    config.addinivalue_line("markers", "tdd: marks tests as following TDD methodology")
    config.addinivalue_line(
        "markers", "red: marks tests in RED phase (should fail initially)"
    )
    config.addinivalue_line(
        "markers", "green: marks tests in GREEN phase (minimal passing code)"
    )
    config.addinivalue_line("markers", "refactor: marks tests in REFACTOR phase")
