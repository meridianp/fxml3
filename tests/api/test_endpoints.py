"""Test FXML4 API endpoints.

This module tests the FXML4 API endpoints for data, signals, backtesting, etc.
"""

import json
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from fxml4.api.auth.auth import create_access_token
from fxml4.api.main import app

client = TestClient(app)


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


def test_root_endpoint():
    """Test the root endpoint."""
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == {"message": "FXML4 API running"}


def test_health_endpoint():
    """Test the health check endpoint."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_data_endpoint_authenticated(user_token):
    """Test the data endpoint with authentication."""
    # Mock the data feed to avoid actual API calls
    with patch(
        "fxml4.data_engineering.data_feeds.base_feed.DataFeedFactory.create"
    ) as mock_create:
        # Setup mock feed and mock data
        mock_feed = MagicMock()
        mock_data = pd.DataFrame(
            {
                "open": [1.0, 1.1],
                "high": [1.1, 1.2],
                "low": [0.9, 1.0],
                "close": [1.0, 1.1],
                "volume": [100, 200],
            }
        )
        mock_data.index = pd.date_range(start="2023-01-01", periods=2, freq="1h")
        mock_feed.fetch_data.return_value = mock_data
        mock_create.return_value = mock_feed

        # Test the endpoint
        response = client.post(
            "/data",
            headers={"Authorization": f"Bearer {user_token}"},
            json={"symbol": "GBPUSD", "timeframe": "1h", "limit": 100},
        )

        assert response.status_code == 200
        response_data = response.json()
        assert response_data["symbol"] == "GBPUSD"
        assert response_data["timeframe"] == "1h"
        assert len(response_data["data"]) == 2


def test_data_endpoint_unauthenticated():
    """Test the data endpoint without authentication."""
    response = client.post(
        "/data", json={"symbol": "GBPUSD", "timeframe": "1h", "limit": 100}
    )
    assert response.status_code == 401
    assert "detail" in response.json()


def test_signals_endpoint_authenticated(user_token):
    """Test the signals endpoint with authentication."""
    # For simplicity, we're not implementing a mock for the signal generation
    # just testing that the endpoint responds correctly to valid input
    response = client.post(
        "/signals",
        headers={"Authorization": f"Bearer {user_token}"},
        json={"symbol": "GBPUSD", "timeframe": "1h", "strategy": "integrated_strategy"},
    )

    # The current implementation just returns a placeholder empty signals list
    assert response.status_code == 200
    assert response.json()["symbol"] == "GBPUSD"
    assert response.json()["timeframe"] == "1h"
    assert response.json()["strategy"] == "integrated_strategy"
    assert "signals" in response.json()


def test_backtest_endpoint_authenticated(user_token):
    """Test the backtest endpoint with authentication."""
    # Mock the necessary functions to avoid actual processing
    with (
        patch("fxml4.data_engineering.data_feeds.base_feed.DataFeedFactory.create"),
        patch("fxml4.api.main.run_backtest") as mock_run_backtest,
    ):

        # Setup mock backtest result
        mock_result = MagicMock()
        mock_result.final_capital = 12000.0
        mock_result.total_return = 2000.0
        mock_result.total_return_pct = 20.0
        mock_result.max_drawdown = 500.0
        mock_result.max_drawdown_pct = 5.0
        mock_result.sharpe_ratio = 1.5
        mock_result.sortino_ratio = 2.0
        mock_result.win_rate = 0.6
        mock_result.profit_factor = 1.8
        mock_result.trades = []
        mock_result.generate_report.return_value = "/path/to/report.html"

        mock_run_backtest.return_value = mock_result

        # Test the endpoint
        response = client.post(
            "/backtest",
            headers={"Authorization": f"Bearer {user_token}"},
            json={
                "symbol": "GBPUSD",
                "timeframe": "1h",
                "strategy": "integrated_strategy",
                "start_date": "2023-01-01",
                "end_date": "2023-12-31",
                "initial_capital": 10000.0,
            },
        )

        assert response.status_code == 200
        result = response.json()
        assert result["symbol"] == "GBPUSD"
        assert result["timeframe"] == "1h"
        assert result["strategy"] == "integrated_strategy"
        assert result["total_return_pct"] == 20.0
        assert result["sharpe_ratio"] == 1.5
        assert "backtest_id" in result


def test_rate_limiting():
    """Test rate limiting functionality."""
    # This is a basic test - in a real test, you'd make many requests
    # and check that after X requests you get a 429 response
    # For now, we'll just verify the endpoint works
    responses = []

    # Make a few requests to the health endpoint
    for _ in range(5):
        response = client.get("/health")
        responses.append(response.status_code)

    # All responses should be 200
    assert all(code == 200 for code in responses)

    # In a real test, you'd make more requests than the rate limit allows
    # and check for a 429 response
