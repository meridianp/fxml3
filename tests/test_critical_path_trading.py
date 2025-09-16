"""
Critical Path Trading System Testing for FXML4.

This test suite validates the core trading system functionality including
timeout handling, circuit breakers, and proper error recovery.
"""

import asyncio
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

try:
    from fxml4.api.main import app
    from fxml4.api.services.trading_engine import (
        TradingEngine,
        TradingEngineConfig,
        TradingEngineMetrics,
        TradingEngineState,
        TradingMode,
    )
except ImportError as e:
    pytest.skip(f"Could not import required modules: {e}", allow_module_level=True)


class TestTradingEngineTimeout:
    """Test trading engine timeout functionality."""

    @pytest.fixture
    def trading_engine(self):
        """Create a trading engine instance for testing."""
        engine = TradingEngine()
        engine.config = TradingEngineConfig()
        engine.metrics = TradingEngineMetrics()
        return engine

    @pytest.mark.asyncio
    async def test_signal_processing_timeout(self, trading_engine):
        """Test that signal processing has proper timeout handling."""
        # Mock the signal processing service to simulate timeout
        with patch(
            "fxml4.api.services.trading_engine.signal_processing_service"
        ) as mock_service:
            # Make get_recent_signals hang
            mock_service.get_recent_signals = AsyncMock()
            mock_service.get_recent_signals.side_effect = asyncio.TimeoutError()

            # Set enabled symbols
            trading_engine.config.enabled_symbols = {"EURUSD"}

            # This should not hang due to timeout handling
            await trading_engine._process_signals()

            # Verify error was recorded
            assert trading_engine.metrics.errors > 0

    @pytest.mark.asyncio
    async def test_order_management_timeout(self, trading_engine):
        """Test that order management has proper timeout handling."""
        with patch(
            "fxml4.api.services.trading_engine.order_management_service"
        ) as mock_service:
            # Make get_orders hang
            mock_service.get_orders = AsyncMock()
            mock_service.get_orders.side_effect = asyncio.TimeoutError()

            # This should not hang due to timeout handling
            await trading_engine._manage_orders()

            # Should complete without hanging
            # Verify timeout handling completed successfully
            end_time = time.time()
            assert (
                end_time - start_time < 5.0
            ), "Operation should complete within timeout"
            assert result is not None, "Operation should return a result"

    @pytest.mark.asyncio
    async def test_market_data_timeout(self, trading_engine):
        """Test that market data retrieval has proper timeout handling."""
        with patch(
            "fxml4.api.services.trading_engine.market_data_service"
        ) as mock_service:
            # Make get_latest_tick hang
            mock_service.get_latest_tick = AsyncMock()
            mock_service.get_latest_tick.side_effect = asyncio.TimeoutError()

            # Set enabled symbols
            trading_engine.config.enabled_symbols = {"EURUSD"}

            # This should not hang due to timeout handling
            await trading_engine._update_positions()

            # Should complete without hanging
            # Verify async operation completed
            assert len(processed_items) > 0, "Should have processed at least one item"
            assert all(
                item.get("status") == "completed" for item in processed_items
            ), "All items should be completed"

    @pytest.mark.asyncio
    async def test_order_cancellation_timeout(self, trading_engine):
        """Test that order cancellation has proper timeout handling."""
        with patch(
            "fxml4.api.services.trading_engine.order_management_service"
        ) as mock_service:
            # Mock get_orders to return a timeout order
            old_order = MagicMock()
            old_order.id = "test_order"
            old_order.status = "pending"
            old_order.created_at = datetime.utcnow() - timedelta(
                minutes=20
            )  # Old order
            old_order.symbol = "EURUSD"

            mock_service.get_orders = AsyncMock(return_value=[old_order])

            # Make cancel_order timeout
            mock_service.cancel_order = AsyncMock()
            mock_service.cancel_order.side_effect = asyncio.TimeoutError()

            # Set enabled symbols
            trading_engine.config.enabled_symbols = {"EURUSD"}

            # This should handle timeout gracefully
            await trading_engine._manage_orders()

            # Verify cancel_order was called
            mock_service.cancel_order.assert_called_once()


class TestCircuitBreaker:
    """Test circuit breaker functionality."""

    @pytest.fixture
    def trading_engine(self):
        engine = TradingEngine()
        engine.config = TradingEngineConfig()
        engine.metrics = TradingEngineMetrics()
        return engine

    def test_error_recording(self, trading_engine):
        """Test that errors are properly recorded for circuit breaker."""
        initial_count = trading_engine.metrics.errors

        # Record some errors
        trading_engine._record_error()
        trading_engine._record_error()
        trading_engine._record_error()

        # Verify errors were recorded
        assert trading_engine.metrics.errors == initial_count + 3
        assert len(trading_engine.metrics.recent_errors) == 3

    def test_circuit_breaker_triggering(self, trading_engine):
        """Test that circuit breaker triggers after too many errors."""
        # Set low threshold for testing
        trading_engine.config.max_errors_per_minute = 3

        # Record errors to trigger circuit breaker
        for _ in range(5):
            trading_engine._record_error()

        # Check circuit breaker should trigger
        assert trading_engine._check_circuit_breaker() == True
        assert trading_engine.metrics.circuit_breaker_triggered == True
        assert trading_engine.metrics.circuit_breaker_until is not None

    def test_circuit_breaker_reset(self, trading_engine):
        """Test that circuit breaker resets after pause period."""
        # Trigger circuit breaker
        trading_engine.config.max_errors_per_minute = 1
        trading_engine._record_error()
        trading_engine._record_error()

        # Manually trigger circuit breaker
        trading_engine.metrics.circuit_breaker_triggered = True
        trading_engine.metrics.circuit_breaker_until = datetime.utcnow() - timedelta(
            minutes=1
        )  # Past

        # Should reset now
        assert trading_engine._check_circuit_breaker() == False
        assert trading_engine.metrics.circuit_breaker_triggered == False

    def test_old_errors_cleaned_up(self, trading_engine):
        """Test that old errors are cleaned up from recent errors list."""
        # Record error from long ago
        old_time = datetime.utcnow() - timedelta(minutes=5)
        trading_engine.metrics.recent_errors = [old_time]

        # Record new error (triggers cleanup)
        trading_engine._record_error()

        # Old error should be cleaned up
        assert len(trading_engine.metrics.recent_errors) == 1
        assert trading_engine.metrics.recent_errors[0] > old_time


class TestTradingEngineIntegration:
    """Integration tests for trading engine."""

    @pytest.fixture
    def client(self):
        return TestClient(app)

    @pytest.fixture
    def auth_headers(self):
        """Create valid authentication headers."""
        from jose import jwt

        from fxml4.api.auth.auth import ALGORITHM, SECRET_KEY

        payload = {
            "sub": "test_user",
            "username": "test_user",
            "exp": datetime.utcnow() + timedelta(hours=1),
        }

        token = jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)
        return {"Authorization": f"Bearer {token}"}

    def test_trading_engine_status_endpoint(self, client, auth_headers):
        """Test trading engine status endpoint."""
        response = client.get("/trading/status", headers=auth_headers)

        # Should return valid status
        assert response.status_code == 200

        data = response.json()
        assert "status" in data
        assert "timestamp" in data

    def test_trading_engine_start_stop(self, client, auth_headers):
        """Test trading engine start/stop functionality."""
        # Test start
        start_data = {"symbols": ["EURUSD"], "trading_mode": "manual"}

        response = client.post("/trading/start", json=start_data, headers=auth_headers)
        # Should either succeed or fail gracefully (not server error)
        assert response.status_code < 500

        # Test stop
        response = client.post("/trading/stop", headers=auth_headers)
        assert response.status_code < 500

    def test_trading_engine_pause_resume(self, client, auth_headers):
        """Test trading engine pause/resume functionality."""
        # Test pause
        response = client.post("/trading/pause", headers=auth_headers)
        assert response.status_code < 500

        # Test resume
        response = client.post("/trading/resume", headers=auth_headers)
        assert response.status_code < 500

    def test_trading_config_update(self, client, auth_headers):
        """Test trading configuration update."""
        config_data = {
            "trading_mode": "manual",
            "enabled_symbols": ["EURUSD", "GBPUSD"],
            "min_signal_confidence": 0.7,
            "max_position_size": 10000,
        }

        response = client.put("/trading/config", json=config_data, headers=auth_headers)
        assert response.status_code < 500

        if response.status_code == 200:
            data = response.json()
            assert "config" in data

    def test_trading_metrics_endpoint(self, client, auth_headers):
        """Test trading metrics endpoint."""
        response = client.get("/trading/metrics", headers=auth_headers)
        assert response.status_code < 500

        if response.status_code == 200:
            data = response.json()
            assert "engine_metrics" in data
            assert "position_metrics" in data

    def test_trading_health_endpoint(self, client, auth_headers):
        """Test trading health endpoint."""
        response = client.get("/trading/health", headers=auth_headers)
        assert response.status_code < 500

        if response.status_code == 200:
            data = response.json()
            assert "healthy" in data
            assert "status" in data


class TestOrderManagementSecurity:
    """Test order management security and validation."""

    @pytest.fixture
    def client(self):
        return TestClient(app)

    @pytest.fixture
    def auth_headers(self):
        from jose import jwt

        from fxml4.api.auth.auth import ALGORITHM, SECRET_KEY

        payload = {
            "sub": "test_user",
            "username": "test_user",
            "exp": datetime.utcnow() + timedelta(hours=1),
        }

        token = jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)
        return {"Authorization": f"Bearer {token}"}

    def test_order_creation_requires_auth(self, client):
        """Test that order creation requires authentication."""
        order_data = {
            "symbol": "EURUSD",
            "side": "buy",
            "order_type": "market",
            "quantity": 100,
        }

        response = client.post("/orders", json=order_data)
        assert response.status_code == 401

    def test_order_validation(self, client, auth_headers):
        """Test order data validation."""
        # Test valid order structure
        valid_order = {
            "symbol": "EURUSD",
            "side": "buy",
            "order_type": "market",
            "quantity": 100,
        }

        response = client.post("/orders", json=valid_order, headers=auth_headers)
        # Should either succeed or fail with validation error, not server error
        assert response.status_code < 500

        # Test invalid order data
        invalid_orders = [
            {"symbol": "EURUSD"},  # Missing required fields
            {
                "symbol": "",
                "side": "buy",
                "order_type": "market",
                "quantity": 100,
            },  # Empty symbol
            {
                "symbol": "EURUSD",
                "side": "invalid",
                "order_type": "market",
                "quantity": 100,
            },  # Invalid side
            {
                "symbol": "EURUSD",
                "side": "buy",
                "order_type": "invalid",
                "quantity": 100,
            },  # Invalid type
        ]

        for invalid_order in invalid_orders:
            response = client.post("/orders", json=invalid_order, headers=auth_headers)
            assert response.status_code == 422  # Validation error

    def test_orders_list_pagination(self, client, auth_headers):
        """Test orders listing with pagination."""
        response = client.get("/orders?limit=10", headers=auth_headers)
        assert response.status_code < 500

        if response.status_code == 200:
            data = response.json()
            assert "orders" in data
            assert "count" in data

    def test_order_cancellation(self, client, auth_headers):
        """Test order cancellation endpoint."""
        # Test cancelling non-existent order
        response = client.post("/orders/nonexistent/cancel", headers=auth_headers)
        assert response.status_code < 500  # Should handle gracefully

    def test_order_execution(self, client, auth_headers):
        """Test order execution endpoint."""
        # Test executing non-existent order
        response = client.post("/orders/nonexistent/execute", headers=auth_headers)
        assert response.status_code < 500  # Should handle gracefully


class TestSignalProcessingSecurity:
    """Test signal processing security and validation."""

    @pytest.fixture
    def client(self):
        return TestClient(app)

    @pytest.fixture
    def auth_headers(self):
        from jose import jwt

        from fxml4.api.auth.auth import ALGORITHM, SECRET_KEY

        payload = {
            "sub": "test_user",
            "username": "test_user",
            "exp": datetime.utcnow() + timedelta(hours=1),
        }

        token = jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)
        return {"Authorization": f"Bearer {token}"}

    def test_signal_generation_requires_auth(self, client):
        """Test that signal generation requires authentication."""
        signal_data = {"symbol": "EURUSD", "timeframe": "1h"}

        response = client.post("/signals", json=signal_data)
        assert response.status_code == 401

    def test_signal_generation_validation(self, client, auth_headers):
        """Test signal generation data validation."""
        valid_signal = {"symbol": "EURUSD", "timeframe": "1h"}

        response = client.post("/signals", json=valid_signal, headers=auth_headers)
        # Should either succeed or fail gracefully, not server error
        assert response.status_code < 500

    def test_recent_signals_retrieval(self, client, auth_headers):
        """Test recent signals retrieval."""
        response = client.get("/signals/EURUSD?limit=10", headers=auth_headers)
        assert response.status_code < 500

        if response.status_code == 200:
            data = response.json()
            assert "signals" in data
            assert "count" in data

    def test_signal_processing_start_stop(self, client, auth_headers):
        """Test signal processing start/stop."""
        # Test start
        response = client.post("/signals/start/EURUSD", headers=auth_headers)
        assert response.status_code < 500

        # Test stop
        response = client.post("/signals/stop/EURUSD", headers=auth_headers)
        assert response.status_code < 500

    def test_signal_processing_status(self, client, auth_headers):
        """Test signal processing status."""
        response = client.get("/signals/status", headers=auth_headers)
        assert response.status_code < 500

        if response.status_code == 200:
            data = response.json()
            assert "active_processing" in data
            assert "available_symbols" in data


if __name__ == "__main__":
    # Run the tests
    pytest.main([__file__, "-v", "--tb=short"])
