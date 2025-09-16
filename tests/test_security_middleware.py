"""
Comprehensive TDD test suite for Security Middleware Integration.

This module tests the production-ready security middleware including:
- JWT Authentication and API Key validation
- Role-Based Access Control (RBAC) integration
- Rate limiting and DDoS protection
- Security headers and CORS configuration
- Audit logging for all requests
- Input validation and sanitization
- Performance monitoring and metrics
- Path-based authorization rules
"""

import json
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest
import pytest_asyncio
from fastapi import FastAPI, HTTPException, Request, status
from fastapi.testclient import TestClient
from httpx import AsyncClient

from fxml4.api.auth.models import Role, User
from fxml4.api.middleware.security_middleware import (
    SecurityConfig,
    SecurityMiddleware,
    TrustedProxyMiddleware,
    setup_security_middleware,
)


@pytest.mark.auth
@pytest.mark.security
@pytest.mark.middleware
class TestSecurityConfig:
    """Test security configuration management."""

    def test_default_security_config(self):
        """Test default security configuration values."""
        config = SecurityConfig()

        # Security headers
        assert "X-Content-Type-Options" in config.security_headers
        assert "X-Frame-Options" in config.security_headers
        assert "Strict-Transport-Security" in config.security_headers
        assert config.security_headers["X-Content-Type-Options"] == "nosniff"
        assert config.security_headers["X-Frame-Options"] == "DENY"

        # CORS origins
        assert "http://localhost:3000" in config.cors_origins
        assert len(config.cors_origins) >= 2

        # Path configurations
        assert "/health" in config.public_paths
        assert "/api/v1/auth/login" in config.public_paths
        assert "/api/v1/orders" in config.trading_paths
        assert "/api/v1/users" in config.admin_paths

        # Performance settings
        assert config.slow_request_threshold == 1000
        assert config.enable_performance_monitoring is True
        assert config.max_body_size == 10000

    def test_custom_security_config(self):
        """Test custom security configuration."""
        config = SecurityConfig()

        # Modify configuration
        config.slow_request_threshold = 500
        config.cors_origins.append("https://custom-domain.com")
        config.security_headers["Custom-Header"] = "CustomValue"

        assert config.slow_request_threshold == 500
        assert "https://custom-domain.com" in config.cors_origins
        assert config.security_headers["Custom-Header"] == "CustomValue"


@pytest.mark.auth
@pytest.mark.security
@pytest.mark.middleware
class TestSecurityMiddleware:
    """Test security middleware functionality."""

    @pytest.fixture
    def security_config(self):
        """Create test security configuration."""
        return SecurityConfig()

    @pytest.fixture
    def mock_app(self):
        """Create mock FastAPI application."""
        app = FastAPI()

        @app.get("/health")
        async def health():
            return {"status": "ok"}

        @app.get("/api/v1/data")
        async def get_data():
            return {"data": "test"}

        @app.post("/api/v1/orders")
        async def create_order():
            return {"order_id": "123"}

        @app.get("/api/v1/admin/users")
        async def admin_users():
            return {"users": []}

        return app

    @pytest.fixture
    def mock_user(self):
        """Create mock user for testing."""
        user = Mock()
        user.id = "user-123"
        user.username = "test_trader"
        user.is_active = True
        user.roles = [Mock(name="trader")]
        user.has_role = Mock(
            side_effect=lambda role: (
                role in ["trader", "admin"] if role == "admin" else role == "trader"
            )
        )
        user.has_permission = Mock(return_value=True)
        return user

    @pytest.fixture
    def mock_admin_user(self):
        """Create mock admin user for testing."""
        user = Mock()
        user.id = "admin-123"
        user.username = "admin_user"
        user.is_active = True
        user.roles = [Mock(name="admin")]
        user.has_role = Mock(side_effect=lambda role: role == "admin")
        user.has_permission = Mock(return_value=True)
        return user

    @pytest.fixture
    def mock_viewer_user(self):
        """Create mock viewer user for testing."""
        user = Mock()
        user.id = "viewer-123"
        user.username = "viewer_user"
        user.is_active = True
        user.roles = [Mock(name="viewer")]
        user.has_role = Mock(side_effect=lambda role: role == "viewer")
        user.has_permission = Mock(return_value=True)
        return user

    def test_security_middleware_initialization(self, mock_app, security_config):
        """Test security middleware initialization."""
        middleware = SecurityMiddleware(mock_app, security_config)

        assert middleware.config == security_config
        assert hasattr(middleware, "rate_limiter")
        assert hasattr(middleware, "audit_logger")
        assert middleware.request_count == 0
        assert middleware.total_processing_time == 0.0

    @pytest.mark.asyncio
    async def test_public_path_access(self, mock_app, security_config):
        """Test access to public paths without authentication."""
        middleware = SecurityMiddleware(mock_app, security_config)
        mock_app.add_middleware(lambda app: middleware)

        async with AsyncClient(app=mock_app, base_url="http://test") as client:
            # Health endpoint should be accessible
            with patch.object(middleware, "audit_logger") as mock_audit:
                mock_audit.log_system_event = AsyncMock()
                response = await client.get("/health")
                assert response.status_code == 200
                assert response.json() == {"status": "ok"}

    @pytest.mark.asyncio
    async def test_authentication_required(self, mock_app, security_config):
        """Test that protected paths require authentication."""
        middleware = SecurityMiddleware(mock_app, security_config)

        # Mock the call_next to return a successful response
        async def mock_call_next(request):
            from fastapi.responses import JSONResponse

            return JSONResponse({"data": "test"})

        # Create a mock request without authentication
        request = Mock()
        request.url = Mock()
        request.url.path = "/api/v1/data"
        request.url.query = None
        request.method = "GET"
        request.headers = {}
        request.client = Mock()
        request.client.host = "127.0.0.1"
        request.state = Mock()

        # Mock authentication to return None (no user)
        with patch.object(middleware, "_authenticate_request", return_value=None):
            with pytest.raises(HTTPException) as exc_info:
                await middleware._process_request_with_security(request, mock_call_next)

            assert exc_info.value.status_code == 401
            assert "Authentication required" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_role_based_authorization_trading(
        self, mock_app, security_config, mock_user
    ):
        """Test role-based authorization for trading endpoints."""
        middleware = SecurityMiddleware(mock_app, security_config)

        # Create mock request for trading endpoint
        request = Mock()
        request.url = Mock()
        request.url.path = "/api/v1/orders"
        request.method = "POST"
        request.state = Mock()

        # Test trader access (should succeed)
        mock_user.has_role.return_value = True
        await middleware._authorize_request(request, mock_user)

        # Test viewer access (should fail)
        mock_viewer = Mock()
        mock_viewer.username = "viewer"
        mock_viewer.has_role = Mock(return_value=False)

        with patch.object(middleware, "_log_security_event", new_callable=AsyncMock):
            with pytest.raises(HTTPException) as exc_info:
                await middleware._authorize_request(request, mock_viewer)

            assert exc_info.value.status_code == 403
            assert "Trading privileges required" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_role_based_authorization_admin(
        self, mock_app, security_config, mock_admin_user
    ):
        """Test role-based authorization for admin endpoints."""
        middleware = SecurityMiddleware(mock_app, security_config)

        # Create mock request for admin endpoint
        request = Mock()
        request.url = Mock()
        request.url.path = "/api/v1/admin/users"
        request.method = "GET"
        request.state = Mock()

        # Test admin access (should succeed)
        await middleware._authorize_request(request, mock_admin_user)

        # Test non-admin access (should fail)
        mock_trader = Mock()
        mock_trader.username = "trader"
        mock_trader.has_role = Mock(return_value=False)

        with patch.object(middleware, "_log_security_event", new_callable=AsyncMock):
            with pytest.raises(HTTPException) as exc_info:
                await middleware._authorize_request(request, mock_trader)

            assert exc_info.value.status_code == 403
            assert "Administrator privileges required" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_viewer_write_operation_denied(
        self, mock_app, security_config, mock_viewer_user
    ):
        """Test that viewer role cannot perform write operations."""
        middleware = SecurityMiddleware(mock_app, security_config)

        # Create mock request for write operation
        request = Mock()
        request.url = Mock()
        request.url.path = "/api/v1/data"
        request.method = "POST"
        request.state = Mock()

        with patch.object(middleware, "_log_security_event", new_callable=AsyncMock):
            with pytest.raises(HTTPException) as exc_info:
                await middleware._authorize_request(request, mock_viewer_user)

            assert exc_info.value.status_code == 403
            assert "Read-only access" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_rate_limiting_check(self, mock_app, security_config):
        """Test rate limiting functionality."""
        middleware = SecurityMiddleware(mock_app, security_config)

        # Mock rate limiter to return exceeded result
        mock_rate_result = Mock()
        mock_rate_result.is_exceeded.return_value = True

        with patch.object(
            middleware.rate_limiter,
            "check_ip_rate_limit",
            return_value=mock_rate_result,
        ):
            with patch.object(
                middleware, "_log_security_event", new_callable=AsyncMock
            ):
                request = Mock()
                request.client = Mock()
                request.client.host = "192.168.1.100"
                request.state = Mock()

                with pytest.raises(HTTPException) as exc_info:
                    await middleware._check_rate_limits(request)

                assert exc_info.value.status_code == 429
                assert "Rate limit exceeded" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_input_validation_sql_injection(self, mock_app, security_config):
        """Test input validation for SQL injection attempts."""
        middleware = SecurityMiddleware(mock_app, security_config)

        # Create request with SQL injection attempt
        request = Mock()
        request.url = Mock()
        request.url.path = "/api/v1/data?id=1' OR '1'='1"
        request.url.query = "id=1' OR '1'='1"
        request.headers = {"content-length": "100"}
        request.state = Mock()

        with patch.object(
            middleware, "_log_security_event", new_callable=AsyncMock
        ) as mock_log:
            await middleware._validate_and_sanitize_input(request)

            # Should log security violation but not block
            mock_log.assert_called()
            call_args = mock_log.call_args[1]
            assert "SQL injection" in call_args["message"]

    @pytest.mark.asyncio
    async def test_input_validation_xss(self, mock_app, security_config):
        """Test input validation for XSS attempts."""
        middleware = SecurityMiddleware(mock_app, security_config)

        # Create request with XSS attempt
        request = Mock()
        request.url = Mock()
        request.url.path = "/api/v1/data"
        request.url.query = "data=<script>alert('xss')</script>"
        request.headers = {"content-length": "200"}
        request.state = Mock()

        with patch.object(
            middleware, "_log_security_event", new_callable=AsyncMock
        ) as mock_log:
            await middleware._validate_and_sanitize_input(request)

            # Should log security violation
            mock_log.assert_called()
            call_args = mock_log.call_args[1]
            assert "XSS attempt" in call_args["message"]

    @pytest.mark.asyncio
    async def test_content_length_validation(self, mock_app, security_config):
        """Test content length validation."""
        middleware = SecurityMiddleware(mock_app, security_config)

        # Create request with excessive content length
        request = Mock()
        request.url = Mock()
        request.url.path = "/api/v1/data"
        request.url.query = ""
        request.headers = {"content-length": "15000000"}  # 15MB
        request.state = Mock()

        with pytest.raises(HTTPException) as exc_info:
            await middleware._validate_and_sanitize_input(request)

        assert exc_info.value.status_code == 413
        assert "Request too large" in str(exc_info.value.detail)

    def test_security_headers_added(self, mock_app, security_config):
        """Test that security headers are added to responses."""
        middleware = SecurityMiddleware(mock_app, security_config)

        # Create mock response
        from fastapi.responses import JSONResponse

        response = JSONResponse({"test": "data"})

        # Add security headers
        middleware._add_security_headers(response)

        # Check headers
        assert response.headers["X-Content-Type-Options"] == "nosniff"
        assert response.headers["X-Frame-Options"] == "DENY"
        assert response.headers["X-XSS-Protection"] == "1; mode=block"
        assert "max-age=31536000" in response.headers["Strict-Transport-Security"]
        assert response.headers["Server"] == "FXML4-API/1.0"

    def test_performance_metrics_tracking(self, mock_app, security_config):
        """Test performance metrics tracking."""
        middleware = SecurityMiddleware(mock_app, security_config)

        # Initial metrics should be zero
        metrics = middleware.get_metrics()
        assert metrics["total_requests"] == 0
        assert metrics["avg_response_time"] == 0
        assert metrics["slow_requests"] == 0

        # Simulate some requests
        middleware.request_count = 100
        middleware.total_processing_time = 5000.0  # 50ms average
        middleware.slow_requests = 5

        metrics = middleware.get_metrics()
        assert metrics["total_requests"] == 100
        assert metrics["avg_response_time"] == 50.0
        assert metrics["slow_requests"] == 5
        assert metrics["slow_request_percentage"] == 5.0


@pytest.mark.auth
@pytest.mark.security
@pytest.mark.middleware
class TestTrustedProxyMiddleware:
    """Test trusted proxy middleware functionality."""

    def test_trusted_proxy_initialization(self):
        """Test trusted proxy middleware initialization."""
        app = FastAPI()
        trusted_proxies = ["127.0.0.1", "10.0.0.1"]
        middleware = TrustedProxyMiddleware(app, trusted_proxies)

        assert "127.0.0.1" in middleware.trusted_proxies
        assert "10.0.0.1" in middleware.trusted_proxies
        assert (
            "::1" not in middleware.trusted_proxies
        )  # Default not included when custom provided

    def test_default_trusted_proxies(self):
        """Test default trusted proxy configuration."""
        app = FastAPI()
        middleware = TrustedProxyMiddleware(app)

        assert "127.0.0.1" in middleware.trusted_proxies
        assert "::1" in middleware.trusted_proxies

    @pytest.mark.asyncio
    async def test_real_ip_extraction(self):
        """Test real IP extraction from proxy headers."""
        app = FastAPI()
        middleware = TrustedProxyMiddleware(app, ["127.0.0.1"])

        # Mock request from trusted proxy
        request = Mock()
        request.client = Mock()
        request.client.host = "127.0.0.1"  # Trusted proxy
        request.headers = {
            "x-forwarded-for": "192.168.1.100,10.0.0.1",  # Multiple IPs
            "x-real-ip": "192.168.1.100",
        }
        request.state = Mock()

        async def mock_call_next(req):
            from fastapi.responses import JSONResponse

            return JSONResponse({"test": "ok"})

        await middleware.dispatch(request, mock_call_next)

        # Should extract first IP from X-Forwarded-For
        assert request.state.real_client_ip == "192.168.1.100"

    @pytest.mark.asyncio
    async def test_untrusted_proxy_no_extraction(self):
        """Test that untrusted proxies don't trigger IP extraction."""
        app = FastAPI()
        middleware = TrustedProxyMiddleware(app, ["127.0.0.1"])

        # Mock request from untrusted proxy
        request = Mock()
        request.client = Mock()
        request.client.host = "192.168.1.50"  # Untrusted
        request.headers = {"x-forwarded-for": "192.168.1.100"}
        request.state = Mock()

        async def mock_call_next(req):
            from fastapi.responses import JSONResponse

            return JSONResponse({"test": "ok"})

        await middleware.dispatch(request, mock_call_next)

        # Should not have real_client_ip attribute
        assert not hasattr(request.state, "real_client_ip")


@pytest.mark.auth
@pytest.mark.security
@pytest.mark.middleware
class TestSecurityMiddlewareIntegration:
    """Test complete security middleware integration."""

    @pytest.fixture
    def secured_app(self):
        """Create FastAPI app with security middleware."""
        app = FastAPI()

        @app.get("/health")
        async def health():
            return {"status": "healthy"}

        @app.get("/api/v1/protected")
        async def protected():
            return {"message": "protected data"}

        @app.post("/api/v1/orders")
        async def create_order():
            return {"order_id": "new-order-123"}

        @app.get("/api/v1/admin/settings")
        async def admin_settings():
            return {"settings": {}}

        # Setup security middleware
        setup_security_middleware(app)

        return app

    def test_middleware_setup(self, secured_app):
        """Test that security middleware is properly set up."""
        client = TestClient(secured_app)

        # Test public endpoint
        response = client.get("/health")
        assert response.status_code == 200

        # Check security headers are present
        assert "X-Content-Type-Options" in response.headers
        assert "X-Frame-Options" in response.headers
        assert "Server" in response.headers
        assert response.headers["Server"] == "FXML4-API/1.0"

    def test_cors_headers(self, secured_app):
        """Test CORS headers are properly configured."""
        client = TestClient(secured_app)

        # OPTIONS request should include CORS headers
        response = client.options(
            "/api/v1/protected", headers={"Origin": "http://localhost:3000"}
        )

        assert "Access-Control-Allow-Origin" in response.headers
        assert "Access-Control-Allow-Methods" in response.headers
        assert "Access-Control-Allow-Headers" in response.headers

    def test_protected_endpoint_without_auth(self, secured_app):
        """Test protected endpoint access without authentication."""
        client = TestClient(secured_app)

        # Should return 401 for protected endpoint
        response = client.get("/api/v1/protected")
        assert response.status_code == 401
        assert "Authentication required" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_performance_headers(self, secured_app):
        """Test performance monitoring headers."""
        async with AsyncClient(app=secured_app, base_url="http://test") as client:
            response = await client.get("/health")

            # Should have performance headers
            assert "X-Response-Time" in response.headers
            assert "X-Request-ID" in response.headers

            # Response time should be reasonable (less than 100ms in tests)
            response_time = response.headers["X-Response-Time"]
            assert "ms" in response_time
            time_value = float(response_time.replace("ms", ""))
            assert time_value < 1000  # Should be less than 1 second

    def test_security_middleware_metrics(self):
        """Test security middleware performance metrics."""
        app = FastAPI()
        config = SecurityConfig()
        middleware = SecurityMiddleware(app, config)

        # Test initial state
        metrics = middleware.get_metrics()
        assert metrics["total_requests"] == 0

        # Simulate request processing
        middleware.request_count = 50
        middleware.total_processing_time = 2500.0  # 50ms average
        middleware.slow_requests = 3

        metrics = middleware.get_metrics()
        assert metrics["total_requests"] == 50
        assert metrics["avg_response_time"] == 50.0
        assert metrics["slow_requests"] == 3
        assert metrics["slow_request_percentage"] == 6.0
