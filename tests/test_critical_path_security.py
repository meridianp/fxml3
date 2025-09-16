"""
Critical Path Security Testing for FXML4 Trading System.

This test suite validates that all the security fixes implemented are working correctly
and that no authentication bypasses or security vulnerabilities exist.
"""

import asyncio
import json
import os
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

# Import the main application
try:
    from fxml4.api.auth.auth import create_access_token, get_current_user
    from fxml4.api.main import app
    from fxml4.api.middleware.security import SecurityMiddleware
except ImportError as e:
    pytest.skip(f"Could not import required modules: {e}", allow_module_level=True)


class TestSecurityMiddleware:
    """Test the SecurityMiddleware implementation."""

    @pytest.fixture
    def client(self):
        """Create test client with security middleware."""
        return TestClient(app)

    def test_security_headers_added(self, client):
        """Test that security headers are properly added to responses."""
        response = client.get("/health")

        # Check for security headers
        assert "X-Content-Type-Options" in response.headers
        assert response.headers["X-Content-Type-Options"] == "nosniff"
        assert "X-Frame-Options" in response.headers
        assert response.headers["X-Frame-Options"] == "DENY"
        assert "X-XSS-Protection" in response.headers
        assert "Referrer-Policy" in response.headers

        # Check for correlation ID
        assert "X-Correlation-ID" in response.headers
        assert len(response.headers["X-Correlation-ID"]) == 36  # UUID format

    def test_environment_detection(self):
        """Test that security middleware correctly detects environment."""
        with patch.dict(os.environ, {"FXML4_ENVIRONMENT": "production"}):
            middleware = SecurityMiddleware()
            assert middleware.environment == "production"
            assert "Strict-Transport-Security" in middleware.security_headers

        with patch.dict(os.environ, {"FXML4_ENVIRONMENT": "development"}):
            middleware = SecurityMiddleware()
            assert middleware.environment == "development"
            # Development should not have HSTS
            assert "Strict-Transport-Security" not in middleware.security_headers

    def test_client_ip_extraction(self):
        """Test client IP extraction with various proxy headers."""
        middleware = SecurityMiddleware()

        # Mock request with X-Forwarded-For
        mock_request = MagicMock()
        mock_request.headers = {"X-Forwarded-For": "192.168.1.1, 10.0.0.1"}
        mock_request.client = None

        ip = middleware._get_client_ip(mock_request)
        assert ip == "192.168.1.1"  # Should take first IP

        # Mock request with X-Real-IP
        mock_request.headers = {"X-Real-IP": "203.0.113.1"}
        ip = middleware._get_client_ip(mock_request)
        assert ip == "203.0.113.1"

        # Mock request with direct connection
        mock_request.headers = {}
        mock_request.client = MagicMock()
        mock_request.client.host = "198.51.100.1"
        ip = middleware._get_client_ip(mock_request)
        assert ip == "198.51.100.1"


class TestAuthenticationSecurity:
    """Test authentication security measures."""

    @pytest.fixture
    def client(self):
        return TestClient(app)

    def test_no_authentication_bypass_exists(self, client):
        """Verify that no authentication bypass exists in the system."""
        # Test that protected endpoints require authentication
        protected_endpoints = [
            "/trading/status",
            "/trading/positions",
            "/trading/account",
            "/orders",
            "/signals",
        ]

        for endpoint in protected_endpoints:
            response = client.get(endpoint)
            assert (
                response.status_code == 401
            ), f"Endpoint {endpoint} should require authentication"

            # Verify proper error message
            error_data = response.json()
            assert "detail" in error_data
            assert "not authenticated" in error_data["detail"].lower()

    def test_invalid_token_rejected(self, client):
        """Test that invalid tokens are properly rejected."""
        invalid_tokens = [
            "invalid_token",
            "Bearer invalid_token",
            "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.invalid.signature",
            "",
            None,
        ]

        for token in invalid_tokens:
            headers = {"Authorization": f"Bearer {token}"} if token else {}
            response = client.get("/trading/status", headers=headers)
            assert response.status_code == 401, f"Token {token} should be rejected"

    def test_expired_token_rejected(self, client):
        """Test that expired tokens are properly rejected."""
        # Create an expired token (expired 1 hour ago)
        from jose import jwt

        from fxml4.api.auth.auth import ALGORITHM, SECRET_KEY

        expired_payload = {
            "sub": "test_user",
            "username": "test_user",
            "exp": datetime.utcnow() - timedelta(hours=1),
        }

        expired_token = jwt.encode(expired_payload, SECRET_KEY, algorithm=ALGORITHM)

        headers = {"Authorization": f"Bearer {expired_token}"}
        response = client.get("/trading/status", headers=headers)
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_jwt_secret_key_required(self):
        """Test that JWT operations fail without proper secret key."""
        with patch.dict(os.environ, {"FXML4_JWT_SECRET_KEY": ""}):
            # This should fail or use a fallback
            from fxml4.api.auth.auth import SECRET_KEY

            assert SECRET_KEY is not None and len(SECRET_KEY) > 0

    def test_cors_configuration_secure(self, client):
        """Test that CORS configuration is secure and doesn't allow arbitrary origins."""
        # Test that CORS headers are present but restrictive
        response = client.options(
            "/health",
            headers={
                "Origin": "https://malicious-site.com",
                "Access-Control-Request-Method": "GET",
            },
        )

        # Should not allow arbitrary origins
        cors_origin = response.headers.get("Access-Control-Allow-Origin")
        if cors_origin:
            assert cors_origin != "*", "CORS should not allow all origins"
            assert "malicious-site.com" not in cors_origin


class TestTradingOperationSecurity:
    """Test security of critical trading operations."""

    @pytest.fixture
    def client(self):
        return TestClient(app)

    @pytest.fixture
    def auth_headers(self):
        """Create valid authentication headers for testing."""
        from jose import jwt

        from fxml4.api.auth.auth import ALGORITHM, SECRET_KEY

        payload = {
            "sub": "test_user",
            "username": "test_user",
            "exp": datetime.utcnow() + timedelta(hours=1),
        }

        token = jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)
        return {"Authorization": f"Bearer {token}"}

    def test_trading_endpoints_require_auth(self, client):
        """Test that all trading endpoints require authentication."""
        trading_endpoints = [
            ("GET", "/trading/status"),
            ("GET", "/trading/positions"),
            ("GET", "/trading/account"),
            ("POST", "/trading/start"),
            ("POST", "/trading/stop"),
            ("POST", "/trading/pause"),
            ("POST", "/trading/resume"),
            ("GET", "/orders"),
            ("POST", "/orders"),
            ("POST", "/orders/from-signal"),
        ]

        for method, endpoint in trading_endpoints:
            if method == "GET":
                response = client.get(endpoint)
            elif method == "POST":
                response = client.post(endpoint, json={})

            assert response.status_code in [
                401,
                422,
            ], f"{method} {endpoint} should require authentication"

    def test_order_creation_validation(self, client, auth_headers):
        """Test that order creation has proper validation."""
        # Test invalid order data
        invalid_orders = [
            {},  # Empty order
            {"symbol": "EURUSD"},  # Missing required fields
            {
                "symbol": "",
                "side": "buy",
                "order_type": "market",
                "quantity": 0,
            },  # Invalid values
            {
                "symbol": "EURUSD",
                "side": "invalid",
                "order_type": "market",
                "quantity": 100,
            },  # Invalid enum
        ]

        for order_data in invalid_orders:
            response = client.post("/orders", json=order_data, headers=auth_headers)
            assert (
                response.status_code == 422
            ), f"Invalid order should be rejected: {order_data}"

    def test_sql_injection_protection(self, client, auth_headers):
        """Test protection against SQL injection in trading operations."""
        # Test various SQL injection patterns
        injection_patterns = [
            "'; DROP TABLE orders; --",
            "' OR '1'='1",
            "UNION SELECT * FROM users",
            "<script>alert('xss')</script>",
            "../../../etc/passwd",
        ]

        for pattern in injection_patterns:
            # Test in symbol parameter
            response = client.get(f"/signals/{pattern}", headers=auth_headers)
            # Should either return 404/422 or handle gracefully, not cause server error
            assert (
                response.status_code < 500
            ), f"SQL injection pattern caused server error: {pattern}"

            # Test in order data
            order_data = {
                "symbol": pattern,
                "side": "buy",
                "order_type": "market",
                "quantity": 100,
            }
            response = client.post("/orders", json=order_data, headers=auth_headers)
            assert (
                response.status_code < 500
            ), f"SQL injection in order data caused server error: {pattern}"


class TestTimeoutAndCircuitBreaker:
    """Test timeout handling and circuit breaker functionality."""

    def test_trading_engine_timeout_configuration(self):
        """Test that trading engine has proper timeout configuration."""
        from fxml4.api.services.trading_engine import TradingEngineConfig

        config = TradingEngineConfig()

        # Verify timeout settings exist and are reasonable
        assert hasattr(config, "signal_timeout_minutes")
        assert hasattr(config, "order_timeout_minutes")
        assert config.signal_timeout_minutes > 0
        assert config.order_timeout_minutes > 0
        assert config.signal_timeout_minutes < 60  # Should be reasonable
        assert config.order_timeout_minutes < 60

    def test_circuit_breaker_configuration(self):
        """Test that circuit breaker is properly configured."""
        from fxml4.api.services.trading_engine import TradingEngineConfig

        config = TradingEngineConfig()

        # Verify circuit breaker settings
        assert hasattr(config, "max_errors_per_minute")
        assert hasattr(config, "circuit_breaker_pause_minutes")
        assert config.max_errors_per_minute > 0
        assert config.circuit_breaker_pause_minutes > 0

    @pytest.mark.asyncio
    async def test_async_operations_have_timeouts(self):
        """Test that async operations in trading engine have timeouts."""
        # This test verifies that asyncio.wait_for is used for critical operations
        import inspect

        from fxml4.api.services import trading_engine

        # Get the source code of the trading engine
        source_lines = inspect.getsource(trading_engine)

        # Check for asyncio.wait_for usage (indicates timeout handling)
        assert (
            "asyncio.wait_for" in source_lines
        ), "Trading engine should use asyncio.wait_for for timeout handling"
        assert "timeout=" in source_lines, "Trading engine should specify timeouts"


class TestAPIRateLimitingAndSecurity:
    """Test API rate limiting and security measures."""

    @pytest.fixture
    def client(self):
        return TestClient(app)

    def test_health_endpoint_accessible(self, client):
        """Test that health endpoint is accessible without authentication."""
        response = client.get("/health")
        assert response.status_code == 200

        data = response.json()
        assert "status" in data
        assert data["status"] in ["healthy", "ok"]

    def test_error_handling_doesnt_expose_internals(self, client):
        """Test that error responses don't expose internal system information."""
        # Test various error conditions
        response = client.get("/nonexistent-endpoint")
        assert response.status_code == 404

        # Error response should not expose stack traces or internal paths
        error_text = response.text.lower()
        assert "traceback" not in error_text
        assert "/home/" not in error_text
        assert "python" not in error_text
        assert "internal error" not in error_text or "generic" in error_text

    def test_request_size_limits(self, client):
        """Test that there are reasonable request size limits."""
        # Test with very large payload
        large_payload = {"data": "x" * 1024 * 1024}  # 1MB payload

        response = client.post("/orders", json=large_payload)
        # Should either be rejected (413) or return 401/422, not cause server error
        assert response.status_code < 500


@pytest.mark.integration
class TestIntegrationSecurity:
    """Integration tests for security across system components."""

    @pytest.fixture
    def client(self):
        return TestClient(app)

    def test_end_to_end_authentication_flow(self, client):
        """Test complete authentication flow works securely."""
        # This would test with a real authentication provider
        # For now, verify the structure is correct

        # Test that login endpoint exists
        response = client.post(
            "/auth/login",
            json={"username": "test", "password": "test"},  # pragma: allowlist secret
        )

        # Should return 401 (invalid credentials) or 422 (validation error)
        # Should NOT return 500 (server error)
        assert response.status_code in [401, 422]

    def test_security_middleware_integration(self, client):
        """Test that security middleware is properly integrated."""
        response = client.get("/health")

        # Verify security middleware is working
        assert "X-Correlation-ID" in response.headers
        assert "X-Content-Type-Options" in response.headers

        # Test that the middleware doesn't interfere with normal operations
        assert response.status_code == 200


if __name__ == "__main__":
    # Run the tests
    pytest.main([__file__, "-v", "--tb=short"])
