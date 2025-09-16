"""Shared fixtures and configuration for web-ui tests."""

import pytest
import asyncio
from datetime import datetime, timedelta
from fastapi import FastAPI
from fastapi.testclient import TestClient
from unittest.mock import Mock, AsyncMock
import jwt

from fxml4_web.api.main import APIConfig
from fxml4_web.api.routers.auth import (
    get_password_hash, create_access_token,
    SECRET_KEY, ALGORITHM
)


@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def api_config():
    """Default API configuration for tests."""
    return APIConfig(
        api_title="FXML4 Test API",
        api_version="1.0.0-test",
        api_description="Test API",
        cors_origins=["http://localhost:3000", "http://testhost:8080"],
        secret_key="test-secret-key-for-testing-only",
        database_url="postgresql://test:test@localhost:5432/fxml4_test",
        redis_url="redis://localhost:6379/15"
    )


@pytest.fixture
def test_users_db():
    """Test users database."""
    return {
        "testuser": {
            "username": "testuser",
            "email": "test@example.com",
            "full_name": "Test User",
            "hashed_password": get_password_hash("testpass123"),
            "disabled": False
        },
        "admin": {
            "username": "admin",
            "email": "admin@example.com",
            "full_name": "Admin User",
            "hashed_password": get_password_hash("adminpass456"),
            "disabled": False,
            "role": "admin"
        },
        "disabled_user": {
            "username": "disabled",
            "email": "disabled@example.com",
            "full_name": "Disabled User",
            "hashed_password": get_password_hash("disabled789"),
            "disabled": True
        }
    }


@pytest.fixture
def auth_token(test_users_db):
    """Generate valid auth token for testuser."""
    return create_access_token(
        data={"sub": "testuser"},
        expires_delta=timedelta(hours=1)
    )


@pytest.fixture
def admin_token(test_users_db):
    """Generate valid auth token for admin."""
    return create_access_token(
        data={"sub": "admin", "role": "admin"},
        expires_delta=timedelta(hours=1)
    )


@pytest.fixture
def expired_token():
    """Generate expired auth token."""
    return create_access_token(
        data={"sub": "testuser"},
        expires_delta=timedelta(hours=-1)
    )


@pytest.fixture
def auth_headers(auth_token):
    """Authorization headers with valid token."""
    return {"Authorization": f"Bearer {auth_token}"}


@pytest.fixture
def admin_headers(admin_token):
    """Authorization headers with admin token."""
    return {"Authorization": f"Bearer {admin_token}"}


@pytest.fixture
def mock_database():
    """Mock database connection."""
    db = Mock()
    db.execute = AsyncMock()
    db.fetch = AsyncMock()
    db.fetchrow = AsyncMock()
    db.fetchval = AsyncMock()
    return db


@pytest.fixture
def mock_redis():
    """Mock Redis connection."""
    redis = Mock()
    redis.get = AsyncMock()
    redis.set = AsyncMock()
    redis.delete = AsyncMock()
    redis.exists = AsyncMock()
    redis.expire = AsyncMock()
    return redis


@pytest.fixture
def sample_market_data():
    """Sample market data for testing."""
    return {
        "EURUSD": {
            "symbol": "EURUSD",
            "bid": 1.0850,
            "ask": 1.0851,
            "last": 1.08505,
            "timestamp": datetime.now().isoformat(),
            "volume": 125000
        },
        "GBPUSD": {
            "symbol": "GBPUSD",
            "bid": 1.2500,
            "ask": 1.2501,
            "last": 1.25005,
            "timestamp": datetime.now().isoformat(),
            "volume": 98000
        },
        "USDJPY": {
            "symbol": "USDJPY",
            "bid": 110.50,
            "ask": 110.51,
            "last": 110.505,
            "timestamp": datetime.now().isoformat(),
            "volume": 210000
        }
    }


@pytest.fixture
def sample_positions():
    """Sample trading positions."""
    return [
        {
            "id": "pos_001",
            "symbol": "EURUSD",
            "side": "BUY",
            "quantity": 10000,
            "entry_price": 1.0845,
            "current_price": 1.0855,
            "unrealized_pnl": 10.0,
            "realized_pnl": 0.0,
            "status": "OPEN",
            "opened_at": (datetime.now() - timedelta(hours=2)).isoformat()
        },
        {
            "id": "pos_002",
            "symbol": "GBPUSD",
            "side": "SELL",
            "quantity": 5000,
            "entry_price": 1.2510,
            "current_price": 1.2500,
            "unrealized_pnl": 5.0,
            "realized_pnl": 0.0,
            "status": "OPEN",
            "opened_at": (datetime.now() - timedelta(hours=1)).isoformat()
        }
    ]


@pytest.fixture
def sample_orders():
    """Sample trading orders."""
    return [
        {
            "id": "ord_001",
            "symbol": "EURUSD",
            "side": "BUY",
            "type": "LIMIT",
            "quantity": 10000,
            "price": 1.0840,
            "status": "PENDING",
            "created_at": datetime.now().isoformat()
        },
        {
            "id": "ord_002",
            "symbol": "GBPUSD",
            "side": "SELL",
            "type": "MARKET",
            "quantity": 5000,
            "status": "FILLED",
            "fill_price": 1.2500,
            "filled_at": (datetime.now() - timedelta(minutes=30)).isoformat()
        }
    ]


@pytest.fixture
def sample_backtest_config():
    """Sample backtest configuration."""
    return {
        "strategy": "moving_average_crossover",
        "symbols": ["EURUSD", "GBPUSD"],
        "start_date": "2024-01-01",
        "end_date": "2024-01-31",
        "initial_capital": 10000,
        "parameters": {
            "fast_period": 20,
            "slow_period": 50,
            "position_size": 0.1,
            "stop_loss": 0.02,
            "take_profit": 0.04
        }
    }


@pytest.fixture
def sample_backtest_results():
    """Sample backtest results."""
    return {
        "id": "bt_001",
        "status": "COMPLETED",
        "strategy": "moving_average_crossover",
        "period": "2024-01-01 to 2024-01-31",
        "metrics": {
            "total_return": 0.0523,
            "annualized_return": 0.6276,
            "sharpe_ratio": 1.85,
            "sortino_ratio": 2.10,
            "max_drawdown": -0.0287,
            "win_rate": 0.58,
            "profit_factor": 1.42,
            "total_trades": 45,
            "winning_trades": 26,
            "losing_trades": 19
        },
        "equity_curve": [10000, 10050, 10025, 10100, 10150, 10523],
        "trades": []  # Would contain detailed trade data
    }


@pytest.fixture
def mock_external_services():
    """Mock external service calls."""
    services = {
        "market_data_provider": Mock(),
        "broker_api": Mock(),
        "news_api": Mock(),
        "llm_api": Mock()
    }
    
    # Setup common responses
    services["market_data_provider"].get_prices = AsyncMock(
        return_value={"EURUSD": 1.0850, "GBPUSD": 1.2500}
    )
    services["broker_api"].place_order = AsyncMock(
        return_value={"order_id": "ord_123", "status": "FILLED"}
    )
    services["news_api"].get_latest = AsyncMock(
        return_value=[{"title": "Market Update", "sentiment": "neutral"}]
    )
    services["llm_api"].analyze = AsyncMock(
        return_value={"sentiment": "bullish", "confidence": 0.75}
    )
    
    return services


@pytest.fixture
def websocket_client(test_app):
    """Create WebSocket test client."""
    return TestClient(test_app)


@pytest.fixture
def mock_logger():
    """Mock logger for testing."""
    logger = Mock()
    logger.info = Mock()
    logger.warning = Mock()
    logger.error = Mock()
    logger.debug = Mock()
    return logger


# Test data generators
def generate_ohlc_data(periods=100, interval="5min"):
    """Generate OHLC price data."""
    import numpy as np
    import pandas as pd
    
    dates = pd.date_range(end=datetime.now(), periods=periods, freq=interval)
    base_price = 1.0850
    
    data = []
    for i, date in enumerate(dates):
        change = np.random.randn() * 0.0005
        open_price = base_price
        close_price = base_price + change
        high_price = max(open_price, close_price) + abs(np.random.randn() * 0.0002)
        low_price = min(open_price, close_price) - abs(np.random.randn() * 0.0002)
        volume = int(np.random.uniform(1000, 10000))
        
        data.append({
            "timestamp": date,
            "open": open_price,
            "high": high_price,
            "low": low_price,
            "close": close_price,
            "volume": volume
        })
        
        base_price = close_price
    
    return data


def generate_trade_signals(n=10):
    """Generate sample trade signals."""
    signals = []
    symbols = ["EURUSD", "GBPUSD", "USDJPY"]
    signal_types = ["BUY", "SELL"]
    
    for i in range(n):
        signals.append({
            "id": f"sig_{i:03d}",
            "timestamp": datetime.now() - timedelta(minutes=i*5),
            "symbol": symbols[i % len(symbols)],
            "signal": signal_types[i % len(signal_types)],
            "confidence": 0.5 + (i % 5) * 0.1,
            "source": "technical_analysis",
            "metadata": {
                "indicator": "ma_crossover",
                "timeframe": "5m"
            }
        })
    
    return signals


# Test markers
pytest.mark.unit = pytest.mark.unit
pytest.mark.integration = pytest.mark.integration
pytest.mark.slow = pytest.mark.slow
pytest.mark.asyncio = pytest.mark.asyncio