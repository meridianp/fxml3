"""Pytest configuration for API tests.

This module contains fixture definitions for API testing.
"""

from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from fxml4.api.auth.auth import USERS_DB, create_access_token, get_password_hash
from fxml4.api.main import app


@pytest.fixture
def test_client():
    """Create a test client for the FastAPI app."""
    return TestClient(app)


@pytest.fixture
def user_token():
    """Create a test user token."""
    access_token = create_access_token(
        data={"sub": "user", "scopes": ["user", "read"]},
        expires_delta=timedelta(minutes=30),
    )
    return access_token


@pytest.fixture
def admin_token():
    """Create a test admin token."""
    access_token = create_access_token(
        data={"sub": "admin", "scopes": ["admin", "user", "read", "write"]},
        expires_delta=timedelta(minutes=30),
    )
    return access_token


@pytest.fixture
def test_users():
    """Add test users to the USERS_DB for testing."""
    # Save original USERS_DB
    original_users = USERS_DB.copy()

    # Add test users
    USERS_DB["test_user"] = {
        "username": "test_user",
        "full_name": "Test User",
        "email": "test@example.com",
        "hashed_password": get_password_hash("test_password"),
        "disabled": False,
        "scopes": ["user", "read"],
    }

    yield USERS_DB

    # Restore original USERS_DB
    USERS_DB.clear()
    USERS_DB.update(original_users)


@pytest.fixture
def mock_backtest_data():
    """Create mock backtest data for testing."""
    return {
        "backtest_id": "BT-20230101-123456",
        "symbol": "GBPUSD",
        "timeframe": "1h",
        "strategy": "integrated_strategy",
        "start_date": "2023-01-01",
        "end_date": "2023-12-31",
        "initial_capital": 10000.0,
        "final_capital": 12000.0,
        "total_return": 2000.0,
        "total_return_pct": 20.0,
        "max_drawdown": 500.0,
        "max_drawdown_pct": 5.0,
        "sharpe_ratio": 1.5,
        "sortino_ratio": 2.0,
        "win_rate": 0.6,
        "profit_factor": 1.8,
        "trade_count": 50,
        "report_url": "/performance/report/BT-20230101-123456",
    }
