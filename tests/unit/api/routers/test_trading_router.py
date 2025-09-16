"""Tests for trading API router."""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


# Mock the trading engine service and dependencies
@pytest.fixture(autouse=True)
def mock_dependencies():
    """Mock external dependencies."""
    with patch("fxml4.api.services.trading_engine_service") as mock_service:
        with patch("fxml4.api.auth.auth.get_current_active_user") as mock_auth:
            # Configure mock user
            mock_user = MagicMock()
            mock_user.id = "test_user_id"
            mock_user.username = "test_user"
            mock_user.is_active = True
            mock_auth.return_value = mock_user

            # Configure mock trading service
            mock_service.get_status.return_value = {
                "state": "RUNNING",
                "mode": "LIVE",
                "active_symbols": ["EURUSD", "GBPUSD"],
                "total_signals": 10,
                "executed_trades": 5,
            }
            mock_service.start.return_value = {"status": "started"}
            mock_service.stop.return_value = {"status": "stopped"}

            yield {
                "trading_service": mock_service,
                "auth": mock_auth,
                "user": mock_user,
            }


@pytest.fixture
def app():
    """Create FastAPI app with trading router."""
    app = FastAPI()

    # Import router after mocking dependencies
    from fxml4.api.routers.trading import router

    app.include_router(router)
    return app


@pytest.fixture
def client(app):
    """Create test client."""
    return TestClient(app)


class TestTradingRouter:
    """Test trading API router endpoints."""

    def test_get_trading_status_success(self, client, mock_dependencies):
        """Test getting trading engine status."""
        response = client.get("/trading/status")

        assert response.status_code == 200
        data = response.json()

        assert "status" in data
        assert "timestamp" in data
        assert data["status"]["state"] == "RUNNING"
        assert data["status"]["mode"] == "LIVE"
        assert "active_symbols" in data["status"]

        # Verify service was called
        mock_dependencies["trading_service"].get_status.assert_called_once()

    def test_get_trading_status_service_error(self, client, mock_dependencies):
        """Test trading status endpoint with service error."""
        # Configure service to raise exception
        mock_dependencies["trading_service"].get_status.side_effect = Exception(
            "Service unavailable"
        )

        response = client.get("/trading/status")

        assert response.status_code == 500
        assert "Service unavailable" in response.json()["detail"]

    def test_start_trading_engine_success(self, client, mock_dependencies):
        """Test starting trading engine."""
        request_data = {
            "symbols": ["EURUSD", "GBPUSD"],
            "trading_mode": "LIVE",
            "min_confidence": 0.8,
        }

        response = client.post("/trading/start", json=request_data)

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "started"

        # Verify service was called with correct parameters
        mock_dependencies["trading_service"].start.assert_called_once()

    def test_start_trading_engine_validation_error(self, client, mock_dependencies):
        """Test starting trading engine with invalid data."""
        request_data = {
            "symbols": [],  # Empty symbols list
            "min_confidence": 1.5,  # Invalid confidence > 1.0
        }

        response = client.post("/trading/start", json=request_data)

        # Should handle validation error appropriately
        assert response.status_code in [400, 422]  # Bad Request or Unprocessable Entity

    def test_stop_trading_engine_success(self, client, mock_dependencies):
        """Test stopping trading engine."""
        response = client.post("/trading/stop")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "stopped"

        # Verify service was called
        mock_dependencies["trading_service"].stop.assert_called_once()

    def test_update_trading_config_success(self, client, mock_dependencies):
        """Test updating trading configuration."""
        config_data = {
            "trading_mode": "PAPER",
            "enabled_symbols": ["EURUSD"],
            "min_signal_confidence": 0.7,
            "max_position_size": 0.02,
        }

        mock_dependencies["trading_service"].update_config.return_value = {
            "status": "updated"
        }

        response = client.put("/trading/config", json=config_data)

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "updated"

    def test_get_trading_metrics_success(self, client, mock_dependencies):
        """Test getting trading metrics."""
        mock_metrics = {
            "total_trades": 25,
            "winning_trades": 15,
            "losing_trades": 10,
            "win_rate": 0.6,
            "total_pnl": 1250.50,
            "average_trade_duration": "2h 15m",
        }

        mock_dependencies["trading_service"].get_metrics.return_value = mock_metrics

        response = client.get("/trading/metrics")

        assert response.status_code == 200
        data = response.json()

        assert data["total_trades"] == 25
        assert data["win_rate"] == 0.6
        assert data["total_pnl"] == 1250.50

    def test_get_active_positions_success(self, client, mock_dependencies):
        """Test getting active positions."""
        mock_positions = [
            {
                "id": "pos_1",
                "symbol": "EURUSD",
                "side": "BUY",
                "size": 10000,
                "entry_price": 1.1000,
                "current_price": 1.1050,
                "pnl": 50.0,
                "entry_time": "2023-01-01T10:00:00Z",
            },
            {
                "id": "pos_2",
                "symbol": "GBPUSD",
                "side": "SELL",
                "size": 5000,
                "entry_price": 1.3000,
                "current_price": 1.2980,
                "pnl": 10.0,
                "entry_time": "2023-01-01T11:00:00Z",
            },
        ]

        mock_dependencies["trading_service"].get_active_positions.return_value = (
            mock_positions
        )

        response = client.get("/trading/positions")

        assert response.status_code == 200
        data = response.json()

        assert len(data) == 2
        assert data[0]["symbol"] == "EURUSD"
        assert data[0]["pnl"] == 50.0
        assert data[1]["symbol"] == "GBPUSD"

    def test_authentication_required(self, client):
        """Test that authentication is required for all endpoints."""
        # Mock authentication to fail
        with patch("fxml4.api.auth.auth.get_current_active_user") as mock_auth:
            from fastapi import HTTPException

            mock_auth.side_effect = HTTPException(
                status_code=401, detail="Not authenticated"
            )

            # Test various endpoints
            endpoints = [
                ("GET", "/trading/status"),
                ("POST", "/trading/start"),
                ("POST", "/trading/stop"),
                ("GET", "/trading/metrics"),
                ("GET", "/trading/positions"),
            ]

            for method, endpoint in endpoints:
                if method == "GET":
                    response = client.get(endpoint)
                else:
                    response = client.post(endpoint, json={})

                assert response.status_code == 401
                assert "Not authenticated" in response.json()["detail"]

    def test_request_validation(self, client, mock_dependencies):
        """Test request validation for various endpoints."""
        # Test start engine with invalid request
        invalid_requests = [
            {"symbols": "not_a_list"},  # Should be list
            {"min_confidence": "invalid"},  # Should be float
            {"trading_mode": "INVALID_MODE"},  # Invalid enum value
        ]

        for invalid_request in invalid_requests:
            response = client.post("/trading/start", json=invalid_request)
            assert response.status_code in [400, 422]  # Validation error

    def test_error_handling_edge_cases(self, client, mock_dependencies):
        """Test error handling for edge cases."""
        # Test service timeout
        mock_dependencies["trading_service"].get_status.side_effect = TimeoutError(
            "Service timeout"
        )

        response = client.get("/trading/status")
        assert response.status_code == 500

        # Test service returning None
        mock_dependencies["trading_service"].get_status.side_effect = None
        mock_dependencies["trading_service"].get_status.return_value = None

        response = client.get("/trading/status")
        # Should handle None response gracefully
        assert response.status_code in [200, 500]


@pytest.mark.unit
class TestTradingRouterIntegration:
    """Integration tests for trading router."""

    def test_complete_trading_workflow(self, client, mock_dependencies):
        """Test complete trading workflow."""
        # 1. Check initial status
        response = client.get("/trading/status")
        assert response.status_code == 200

        # 2. Start trading engine
        start_request = {
            "symbols": ["EURUSD", "GBPUSD"],
            "trading_mode": "PAPER",
            "min_confidence": 0.8,
        }

        response = client.post("/trading/start", json=start_request)
        assert response.status_code == 200

        # 3. Update configuration
        config_update = {"min_signal_confidence": 0.9, "max_position_size": 0.01}

        mock_dependencies["trading_service"].update_config.return_value = {
            "status": "updated"
        }
        response = client.put("/trading/config", json=config_update)
        assert response.status_code == 200

        # 4. Check metrics
        mock_dependencies["trading_service"].get_metrics.return_value = {
            "total_trades": 0
        }
        response = client.get("/trading/metrics")
        assert response.status_code == 200

        # 5. Stop trading engine
        response = client.post("/trading/stop")
        assert response.status_code == 200

    def test_concurrent_requests(self, client, mock_dependencies):
        """Test handling concurrent requests."""
        import concurrent.futures

        def make_request():
            return client.get("/trading/status")

        # Make concurrent requests
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(make_request) for _ in range(10)]
            results = [
                future.result() for future in concurrent.futures.as_completed(futures)
            ]

        # All requests should succeed
        assert all(result.status_code == 200 for result in results)

        # Service should have been called multiple times
        assert mock_dependencies["trading_service"].get_status.call_count == 10


@pytest.mark.performance
def test_trading_router_performance(client, mock_dependencies):
    """Test trading router performance."""
    import time

    # Test response times for status endpoint
    start_time = time.time()

    for _ in range(50):
        response = client.get("/trading/status")
        assert response.status_code == 200

    end_time = time.time()
    execution_time = end_time - start_time

    # Should handle 50 status requests efficiently
    assert execution_time < 3.0  # Less than 3 seconds

    # Test response time for more complex endpoint
    start_time = time.time()

    mock_dependencies["trading_service"].get_metrics.return_value = {
        "total_trades": 100,
        "win_rate": 0.65,
        "total_pnl": 2500.0,
    }

    response = client.get("/trading/metrics")
    end_time = time.time()

    assert response.status_code == 200
    assert (end_time - start_time) < 1.0  # Should respond within 1 second
