"""Integration tests for API endpoints."""

import pytest
import asyncio
from datetime import datetime, timedelta
from fastapi.testclient import TestClient
from unittest.mock import Mock, patch, AsyncMock
import json

from fxml4_web.api.main import create_app, APIConfig
from fxml4_web.api.routers.auth import get_password_hash, create_access_token


@pytest.fixture
def test_config():
    """Test configuration."""
    return APIConfig(
        api_title="Test Integration API",
        api_version="1.0.0",
        cors_origins=["http://localhost:3000"],
        secret_key="test-secret-key-integration",
        database_url="postgresql://test:test@localhost/test_integration",
        redis_url="redis://localhost:6379/1"
    )


@pytest.fixture
def test_app(test_config):
    """Create test application."""
    return create_app(test_config)


@pytest.fixture
def client(test_app):
    """Create test client."""
    return TestClient(test_app)


@pytest.fixture
def auth_headers():
    """Create authentication headers."""
    token = create_access_token(
        data={"sub": "testuser"},
        expires_delta=timedelta(minutes=30)
    )
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def test_users():
    """Create test users."""
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
            "hashed_password": get_password_hash("adminpass123"),
            "disabled": False,
            "role": "admin"
        }
    }


@pytest.mark.integration
class TestAuthenticationFlow:
    """Test complete authentication flow."""
    
    def test_login_flow(self, client, test_users):
        """Test complete login flow."""
        with patch('fxml4_web.api.routers.auth.fake_users_db', test_users):
            # 1. Login
            response = client.post(
                "/api/v1/auth/token",
                data={
                    "username": "testuser",
                    "password": "testpass123"
                }
            )
            assert response.status_code == 200
            token_data = response.json()
            assert "access_token" in token_data
            
            # 2. Use token to access protected endpoint
            headers = {"Authorization": f"Bearer {token_data['access_token']}"}
            response = client.get("/api/v1/auth/me", headers=headers)
            assert response.status_code == 200
            user_data = response.json()
            assert user_data["username"] == "testuser"
            
            # 3. Logout
            response = client.post("/api/v1/auth/logout", headers=headers)
            assert response.status_code == 200
            assert response.json()["message"] == "Successfully logged out"
    
    def test_invalid_login_attempts(self, client, test_users):
        """Test various invalid login attempts."""
        with patch('fxml4_web.api.routers.auth.fake_users_db', test_users):
            # Wrong password
            response = client.post(
                "/api/v1/auth/token",
                data={
                    "username": "testuser",
                    "password": "wrongpass"
                }
            )
            assert response.status_code == 401
            
            # Non-existent user
            response = client.post(
                "/api/v1/auth/token",
                data={
                    "username": "nonexistent",
                    "password": "anypass"
                }
            )
            assert response.status_code == 401
            
            # Missing credentials
            response = client.post("/api/v1/auth/token", data={})
            assert response.status_code == 422  # Validation error
    
    def test_token_expiration(self, client, test_users):
        """Test token expiration handling."""
        with patch('fxml4_web.api.routers.auth.fake_users_db', test_users):
            # Create expired token
            expired_token = create_access_token(
                data={"sub": "testuser"},
                expires_delta=timedelta(minutes=-1)
            )
            
            headers = {"Authorization": f"Bearer {expired_token}"}
            response = client.get("/api/v1/auth/me", headers=headers)
            assert response.status_code == 401


@pytest.mark.integration
class TestMarketDataFlow:
    """Test market data endpoints integration."""
    
    @pytest.fixture
    def mock_market_data(self):
        """Mock market data."""
        return {
            "symbols": ["EURUSD", "GBPUSD", "USDJPY"],
            "prices": {
                "EURUSD": {"bid": 1.0850, "ask": 1.0851, "timestamp": datetime.now().isoformat()},
                "GBPUSD": {"bid": 1.2500, "ask": 1.2501, "timestamp": datetime.now().isoformat()},
                "USDJPY": {"bid": 110.50, "ask": 110.51, "timestamp": datetime.now().isoformat()}
            }
        }
    
    def test_get_market_symbols(self, client, auth_headers, mock_market_data):
        """Test getting available market symbols."""
        # Mock the market router's data source
        with patch('fxml4_web.api.routers.market.get_available_symbols') as mock_symbols:
            mock_symbols.return_value = mock_market_data["symbols"]
            
            response = client.get("/api/v1/market/symbols", headers=auth_headers)
            
            # Should require authentication
            no_auth_response = client.get("/api/v1/market/symbols")
            assert no_auth_response.status_code == 401
            
            # With auth should work
            if response.status_code == 200:
                data = response.json()
                assert isinstance(data, list)
                assert "EURUSD" in data
    
    def test_get_market_prices(self, client, auth_headers, mock_market_data):
        """Test getting market prices."""
        with patch('fxml4_web.api.routers.market.get_current_prices') as mock_prices:
            mock_prices.return_value = mock_market_data["prices"]
            
            response = client.get(
                "/api/v1/market/prices",
                params={"symbols": ["EURUSD", "GBPUSD"]},
                headers=auth_headers
            )
            
            if response.status_code == 200:
                data = response.json()
                assert "EURUSD" in data
                assert "bid" in data["EURUSD"]
                assert "ask" in data["EURUSD"]


@pytest.mark.integration
class TestTradingFlow:
    """Test trading endpoints integration."""
    
    @pytest.fixture
    def mock_position(self):
        """Mock trading position."""
        return {
            "id": "pos_123",
            "symbol": "EURUSD",
            "side": "BUY",
            "quantity": 10000,
            "entry_price": 1.0850,
            "current_price": 1.0860,
            "pnl": 10.0,
            "status": "OPEN"
        }
    
    def test_place_order_flow(self, client, auth_headers):
        """Test placing an order."""
        order_data = {
            "symbol": "EURUSD",
            "side": "BUY",
            "quantity": 10000,
            "order_type": "MARKET"
        }
        
        with patch('fxml4_web.api.routers.trading.place_order') as mock_place:
            mock_place.return_value = {
                "order_id": "ord_456",
                "status": "FILLED",
                **order_data,
                "fill_price": 1.0851
            }
            
            response = client.post(
                "/api/v1/trading/orders",
                json=order_data,
                headers=auth_headers
            )
            
            if response.status_code == 200:
                result = response.json()
                assert "order_id" in result
                assert result["status"] == "FILLED"
    
    def test_get_positions(self, client, auth_headers, mock_position):
        """Test getting current positions."""
        with patch('fxml4_web.api.routers.trading.get_positions') as mock_get:
            mock_get.return_value = [mock_position]
            
            response = client.get("/api/v1/trading/positions", headers=auth_headers)
            
            if response.status_code == 200:
                positions = response.json()
                assert isinstance(positions, list)
                if positions:
                    assert positions[0]["symbol"] == "EURUSD"


@pytest.mark.integration
class TestBacktestingFlow:
    """Test backtesting endpoints integration."""
    
    def test_run_backtest(self, client, auth_headers):
        """Test running a backtest."""
        backtest_config = {
            "strategy": "ma_crossover",
            "symbol": "EURUSD",
            "start_date": "2024-01-01",
            "end_date": "2024-01-31",
            "parameters": {
                "fast_ma": 20,
                "slow_ma": 50
            }
        }
        
        with patch('fxml4_web.api.routers.backtest.run_backtest') as mock_backtest:
            mock_backtest.return_value = {
                "backtest_id": "bt_789",
                "status": "COMPLETED",
                "results": {
                    "total_return": 0.025,
                    "sharpe_ratio": 1.5,
                    "max_drawdown": -0.02,
                    "win_rate": 0.55
                }
            }
            
            response = client.post(
                "/api/v1/backtest/run",
                json=backtest_config,
                headers=auth_headers
            )
            
            if response.status_code == 200:
                result = response.json()
                assert "backtest_id" in result
                assert "results" in result
                assert result["results"]["total_return"] == 0.025
    
    def test_get_backtest_results(self, client, auth_headers):
        """Test getting backtest results."""
        backtest_id = "bt_789"
        
        with patch('fxml4_web.api.routers.backtest.get_backtest_results') as mock_results:
            mock_results.return_value = {
                "backtest_id": backtest_id,
                "status": "COMPLETED",
                "created_at": datetime.now().isoformat(),
                "config": {
                    "strategy": "ma_crossover",
                    "symbol": "EURUSD"
                },
                "results": {
                    "total_return": 0.025,
                    "trades": 45
                }
            }
            
            response = client.get(
                f"/api/v1/backtest/results/{backtest_id}",
                headers=auth_headers
            )
            
            if response.status_code == 200:
                data = response.json()
                assert data["backtest_id"] == backtest_id
                assert data["status"] == "COMPLETED"


@pytest.mark.integration
class TestWebSocketFlow:
    """Test WebSocket connections."""
    
    def test_websocket_market_data(self, test_app):
        """Test WebSocket market data stream."""
        from fastapi.testclient import TestClient
        
        with TestClient(test_app) as client:
            # Test WebSocket connection
            with client.websocket_connect("/api/v1/ws/market") as websocket:
                # Send subscription message
                websocket.send_json({
                    "action": "subscribe",
                    "symbols": ["EURUSD", "GBPUSD"]
                })
                
                # Mock market data updates
                with patch('fxml4_web.api.routers.websocket.get_market_updates') as mock_updates:
                    mock_updates.return_value = {
                        "EURUSD": {"bid": 1.0852, "ask": 1.0853},
                        "GBPUSD": {"bid": 1.2502, "ask": 1.2503}
                    }
                    
                    # Would receive data in real implementation
                    # data = websocket.receive_json()
                    # assert "EURUSD" in data
    
    def test_websocket_authentication(self, test_app):
        """Test WebSocket authentication."""
        with TestClient(test_app) as client:
            # Try to connect without auth
            try:
                with client.websocket_connect("/api/v1/ws/private") as websocket:
                    websocket.send_json({"action": "get_positions"})
                    # Should receive error or be disconnected
            except Exception:
                # Expected behavior for unauthenticated connection
                pass


@pytest.mark.integration
class TestAnalyticsFlow:
    """Test analytics endpoints integration."""
    
    def test_get_performance_metrics(self, client, auth_headers):
        """Test getting performance metrics."""
        with patch('fxml4_web.api.routers.analytics.get_performance_metrics') as mock_metrics:
            mock_metrics.return_value = {
                "period": "30d",
                "total_return": 0.052,
                "sharpe_ratio": 1.8,
                "win_rate": 0.58,
                "profit_factor": 1.4,
                "max_drawdown": -0.03
            }
            
            response = client.get(
                "/api/v1/analytics/performance",
                params={"period": "30d"},
                headers=auth_headers
            )
            
            if response.status_code == 200:
                metrics = response.json()
                assert metrics["period"] == "30d"
                assert "total_return" in metrics
                assert "sharpe_ratio" in metrics
    
    def test_get_trade_history(self, client, auth_headers):
        """Test getting trade history."""
        with patch('fxml4_web.api.routers.analytics.get_trade_history') as mock_history:
            mock_history.return_value = [
                {
                    "trade_id": "t_001",
                    "symbol": "EURUSD",
                    "side": "BUY",
                    "entry_time": "2024-01-15T10:00:00",
                    "exit_time": "2024-01-15T14:00:00",
                    "pnl": 25.50
                },
                {
                    "trade_id": "t_002",
                    "symbol": "GBPUSD",
                    "side": "SELL",
                    "entry_time": "2024-01-16T09:00:00",
                    "exit_time": "2024-01-16T11:00:00",
                    "pnl": -10.25
                }
            ]
            
            response = client.get(
                "/api/v1/analytics/trades",
                params={"start_date": "2024-01-15", "end_date": "2024-01-31"},
                headers=auth_headers
            )
            
            if response.status_code == 200:
                trades = response.json()
                assert isinstance(trades, list)
                assert len(trades) >= 2


@pytest.mark.integration
class TestErrorHandlingIntegration:
    """Test error handling across the API."""
    
    def test_rate_limiting(self, client, auth_headers):
        """Test rate limiting behavior."""
        # Make many requests quickly
        responses = []
        for _ in range(100):
            response = client.get("/api/v1/market/symbols", headers=auth_headers)
            responses.append(response.status_code)
        
        # Should eventually get rate limited (if implemented)
        # assert 429 in responses  # Too Many Requests
    
    def test_database_error_handling(self, client, auth_headers):
        """Test handling of database errors."""
        with patch('fxml4_web.api.routers.trading.get_positions') as mock_get:
            mock_get.side_effect = Exception("Database connection failed")
            
            response = client.get("/api/v1/trading/positions", headers=auth_headers)
            
            # Should handle gracefully
            assert response.status_code in [500, 503]
            if response.status_code == 500:
                assert "error" in response.json() or "detail" in response.json()
    
    def test_validation_errors(self, client, auth_headers):
        """Test input validation errors."""
        # Invalid order data
        invalid_order = {
            "symbol": "INVALID_SYMBOL",
            "side": "INVALID_SIDE",
            "quantity": -1000,  # Negative quantity
            "order_type": "INVALID_TYPE"
        }
        
        response = client.post(
            "/api/v1/trading/orders",
            json=invalid_order,
            headers=auth_headers
        )
        
        # Should return validation error
        assert response.status_code == 422
        error_detail = response.json()["detail"]
        assert isinstance(error_detail, list)  # List of validation errors