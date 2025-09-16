"""
Comprehensive tests for security middleware components.

This module tests SecurityHeadersMiddleware, RequestSizeLimitMiddleware,
TrustedHostMiddleware, and related security features.
"""

from unittest.mock import AsyncMock, Mock, patch

import pytest
from fastapi import FastAPI, Request, Response
from fastapi.testclient import TestClient
from starlette.responses import JSONResponse

from fxml4.api.middleware.security_headers import (
    RequestSizeLimitMiddleware,
    SecurityHeadersMiddleware,
    TrustedHostMiddleware,
    add_security_middleware,
)


class TestSecurityHeadersMiddleware:
    """Test cases for SecurityHeadersMiddleware."""

    def setup_method(self):
        """Set up test environment."""
        self.app = FastAPI()
        self.mock_request = Mock(spec=Request)
        self.mock_response = Mock(spec=Response)
        self.mock_response.headers = {}

    @pytest.mark.asyncio
    async def test_security_headers_added(self):
        """Test that security headers are added to responses."""
        middleware = SecurityHeadersMiddleware(self.app)

        async def mock_call_next(request):
            return self.mock_response

        result = await middleware.dispatch(self.mock_request, mock_call_next)

        # Verify security headers are present
        expected_headers = [
            "X-Frame-Options",
            "X-Content-Type-Options",
            "X-XSS-Protection",
            "Referrer-Policy",
            "Content-Security-Policy",
            "Server",
            "Permissions-Policy",
        ]

        for header in expected_headers:
            assert header in result.headers

        # Verify specific header values
        assert result.headers["X-Frame-Options"] == "DENY"
        assert result.headers["X-Content-Type-Options"] == "nosniff"
        assert result.headers["X-XSS-Protection"] == "1; mode=block"
        assert result.headers["Server"] == "FXML4"

    @pytest.mark.asyncio
    async def test_hsts_header_https_only(self):
        """Test that HSTS header is only added for HTTPS requests."""
        middleware = SecurityHeadersMiddleware(self.app)

        # Test HTTPS request
        https_request = Mock(spec=Request)
        https_request.url.scheme = "https"

        async def mock_call_next(request):
            return self.mock_response

        result = await middleware.dispatch(https_request, mock_call_next)
        assert "Strict-Transport-Security" in result.headers
        assert "max-age=31536000" in result.headers["Strict-Transport-Security"]

        # Test HTTP request
        http_request = Mock(spec=Request)
        http_request.url.scheme = "http"

        result = await middleware.dispatch(http_request, mock_call_next)
        assert "Strict-Transport-Security" not in result.headers

    @pytest.mark.asyncio
    async def test_custom_headers_from_config(self):
        """Test custom headers from configuration."""
        config = {
            "custom_headers": {
                "Custom-Header": "custom-value",
                "X-Frame-Options": "SAMEORIGIN",  # Override default
            }
        }

        middleware = SecurityHeadersMiddleware(self.app, config)

        async def mock_call_next(request):
            return self.mock_response

        result = await middleware.dispatch(self.mock_request, mock_call_next)

        # Verify custom headers
        assert result.headers["Custom-Header"] == "custom-value"
        # Verify override works
        assert result.headers["X-Frame-Options"] == "SAMEORIGIN"

    @pytest.mark.asyncio
    async def test_content_security_policy(self):
        """Test Content Security Policy header content."""
        middleware = SecurityHeadersMiddleware(self.app)

        async def mock_call_next(request):
            return self.mock_response

        result = await middleware.dispatch(self.mock_request, mock_call_next)

        csp = result.headers["Content-Security-Policy"]

        # Verify key CSP directives
        assert "default-src 'self'" in csp
        assert "script-src 'self'" in csp
        assert "object-src 'none'" in csp
        assert "frame-ancestors 'none'" in csp

    def test_middleware_integration(self):
        """Test middleware integration with FastAPI app."""
        app = FastAPI()

        @app.get("/test")
        async def test_endpoint():
            return {"message": "test"}

        # Add security middleware
        app.add_middleware(SecurityHeadersMiddleware)

        client = TestClient(app)
        response = client.get("/test")

        # Verify response is successful
        assert response.status_code == 200

        # Verify security headers are present
        assert "X-Frame-Options" in response.headers
        assert "X-Content-Type-Options" in response.headers
        assert response.headers["X-Frame-Options"] == "DENY"


class TestRequestSizeLimitMiddleware:
    """Test cases for RequestSizeLimitMiddleware."""

    def setup_method(self):
        """Set up test environment."""
        self.app = FastAPI()

    @pytest.mark.asyncio
    async def test_request_within_size_limit(self):
        """Test request within size limit passes through."""
        middleware = RequestSizeLimitMiddleware(self.app, max_size=1024)

        mock_request = Mock(spec=Request)
        mock_request.headers = {"content-length": "512"}
        mock_request.client.host = "127.0.0.1"

        mock_response = Mock(spec=Response)

        async def mock_call_next(request):
            return mock_response

        result = await middleware.dispatch(mock_request, mock_call_next)

        # Should pass through unchanged
        assert result is mock_response

    @pytest.mark.asyncio
    async def test_request_exceeds_size_limit(self):
        """Test request exceeding size limit is rejected."""
        middleware = RequestSizeLimitMiddleware(self.app, max_size=1024)

        mock_request = Mock(spec=Request)
        mock_request.headers = {"content-length": "2048"}  # Exceeds limit
        mock_request.client.host = "127.0.0.1"

        async def mock_call_next(request):
            return Mock(spec=Response)

        with patch("fxml4.api.middleware.security_headers.logger") as mock_logger:
            result = await middleware.dispatch(mock_request, mock_call_next)

        # Should return 413 error
        assert result.status_code == 413
        assert b"Request entity too large" in result.body

        # Should log warning
        mock_logger.warning.assert_called_once()

    @pytest.mark.asyncio
    async def test_request_no_content_length(self):
        """Test request without content-length header passes through."""
        middleware = RequestSizeLimitMiddleware(self.app, max_size=1024)

        mock_request = Mock(spec=Request)
        mock_request.headers = {}  # No content-length

        mock_response = Mock(spec=Response)

        async def mock_call_next(request):
            return mock_response

        result = await middleware.dispatch(mock_request, mock_call_next)

        # Should pass through unchanged
        assert result is mock_response

    def test_middleware_integration(self):
        """Test middleware integration with FastAPI app."""
        app = FastAPI()

        @app.post("/test")
        async def test_endpoint(data: dict):
            return {"received": data}

        # Add middleware with small limit for testing
        app.add_middleware(RequestSizeLimitMiddleware, max_size=100)

        client = TestClient(app)

        # Test small request (should pass)
        small_data = {"key": "value"}
        response = client.post("/test", json=small_data)
        assert response.status_code == 200

        # Test large request (should be rejected)
        # Note: TestClient doesn't always send content-length for JSON,
        # so we test with explicit headers
        large_content = "x" * 1000
        response = client.post(
            "/test",
            content=large_content,
            headers={"content-length": "1000", "content-type": "text/plain"},
        )
        assert response.status_code == 413


class TestTrustedHostMiddleware:
    """Test cases for TrustedHostMiddleware."""

    def setup_method(self):
        """Set up test environment."""
        self.app = FastAPI()

    @pytest.mark.asyncio
    async def test_allowed_host(self):
        """Test request from allowed host passes through."""
        middleware = TrustedHostMiddleware(
            self.app, allowed_hosts=["localhost", "example.com"]
        )

        mock_request = Mock(spec=Request)
        mock_request.headers = {"host": "localhost:8000"}
        mock_request.client.host = "127.0.0.1"

        mock_response = Mock(spec=Response)

        async def mock_call_next(request):
            return mock_response

        result = await middleware.dispatch(mock_request, mock_call_next)

        # Should pass through unchanged
        assert result is mock_response

    @pytest.mark.asyncio
    async def test_disallowed_host(self):
        """Test request from disallowed host is rejected."""
        middleware = TrustedHostMiddleware(self.app, allowed_hosts=["localhost"])

        mock_request = Mock(spec=Request)
        mock_request.headers = {"host": "evil.com"}
        mock_request.client.host = "1.2.3.4"

        async def mock_call_next(request):
            return Mock(spec=Response)

        with patch("fxml4.api.middleware.security_headers.logger") as mock_logger:
            result = await middleware.dispatch(mock_request, mock_call_next)

        # Should return 400 error
        assert result.status_code == 400
        assert b"Disallowed host" in result.body

        # Should log warning
        mock_logger.warning.assert_called_once()

    @pytest.mark.asyncio
    async def test_wildcard_host_matching(self):
        """Test wildcard host matching."""
        middleware = TrustedHostMiddleware(self.app, allowed_hosts=["*.example.com"])

        # Test matching subdomain
        mock_request = Mock(spec=Request)
        mock_request.headers = {"host": "api.example.com"}
        mock_request.client.host = "127.0.0.1"

        mock_response = Mock(spec=Response)

        async def mock_call_next(request):
            return mock_response

        result = await middleware.dispatch(mock_request, mock_call_next)

        # Should pass through unchanged
        assert result is mock_response

    @pytest.mark.asyncio
    async def test_missing_host_header(self):
        """Test request without host header."""
        middleware = TrustedHostMiddleware(self.app, allowed_hosts=["localhost"])

        mock_request = Mock(spec=Request)
        mock_request.headers = {}  # No host header
        mock_request.client.host = "127.0.0.1"

        async def mock_call_next(request):
            return Mock(spec=Response)

        result = await middleware.dispatch(mock_request, mock_call_next)

        # Should be rejected (empty host not in allowed hosts)
        assert result.status_code == 400

    @pytest.mark.asyncio
    async def test_no_allowed_hosts_restriction(self):
        """Test behavior when no allowed hosts are specified."""
        middleware = TrustedHostMiddleware(self.app, allowed_hosts=None)

        mock_request = Mock(spec=Request)
        mock_request.headers = {"host": "any-host.com"}
        mock_request.client.host = "127.0.0.1"

        mock_response = Mock(spec=Response)

        async def mock_call_next(request):
            return mock_response

        result = await middleware.dispatch(mock_request, mock_call_next)

        # Should pass through when allowed_hosts is None
        assert result is mock_response

    def test_middleware_integration(self):
        """Test middleware integration with FastAPI app."""
        app = FastAPI()

        @app.get("/test")
        async def test_endpoint():
            return {"message": "test"}

        # Add middleware
        app.add_middleware(TrustedHostMiddleware, allowed_hosts=["testserver"])

        client = TestClient(app)

        # TestClient uses "testserver" as default host
        response = client.get("/test")
        assert response.status_code == 200

        # Test with custom host header (should be rejected)
        response = client.get("/test", headers={"host": "evil.com"})
        assert response.status_code == 400


class TestSecurityMiddlewareIntegration:
    """Test integration of all security middleware together."""

    def test_add_security_middleware_function(self):
        """Test add_security_middleware helper function."""
        app = FastAPI()

        @app.get("/test")
        async def test_endpoint():
            return {"message": "test"}

        # Add all security middleware
        config = {
            "max_request_size": 1024,
            "allowed_hosts": ["testserver", "localhost"],
            "custom_headers": {"X-Custom-Header": "test-value"},
        }

        with patch("fxml4.api.middleware.security_headers.logger") as mock_logger:
            add_security_middleware(app, config)

        client = TestClient(app)
        response = client.get("/test")

        # Should be successful
        assert response.status_code == 200

        # Security headers should be present
        assert "X-Frame-Options" in response.headers
        assert "X-Custom-Header" in response.headers
        assert response.headers["X-Custom-Header"] == "test-value"

        # Should log successful addition
        mock_logger.info.assert_called_with("Security middleware added to application")

    def test_middleware_order_and_interaction(self):
        """Test that multiple security middleware work together correctly."""
        app = FastAPI()

        @app.post("/test")
        async def test_endpoint(data: dict):
            return {"received": data}

        # Add middleware in specific order
        app.add_middleware(SecurityHeadersMiddleware)
        app.add_middleware(RequestSizeLimitMiddleware, max_size=500)
        app.add_middleware(TrustedHostMiddleware, allowed_hosts=["testserver"])

        client = TestClient(app)

        # Test successful request
        response = client.post("/test", json={"key": "value"})
        assert response.status_code == 200

        # Should have security headers
        assert "X-Frame-Options" in response.headers

        # Test request size limit (middleware should reject before reaching endpoint)
        large_content = "x" * 1000
        response = client.post(
            "/test",
            content=large_content,
            headers={"content-length": "1000", "content-type": "text/plain"},
        )
        assert response.status_code == 413

    def test_security_middleware_error_handling(self):
        """Test error handling in security middleware."""
        app = FastAPI()

        @app.get("/test")
        async def test_endpoint():
            raise Exception("Endpoint error")

        # Add security middleware
        app.add_middleware(SecurityHeadersMiddleware)

        client = TestClient(app)

        # Even with endpoint error, security headers should be present
        response = client.get("/test")
        assert response.status_code == 500

        # Security headers should still be applied
        assert "X-Frame-Options" in response.headers


class TestSecurityConfiguration:
    """Test security configuration scenarios."""

    def test_default_security_configuration(self):
        """Test default security configuration."""
        app = FastAPI()

        @app.get("/test")
        async def test_endpoint():
            return {"message": "test"}

        # Add middleware with no config (should use defaults)
        add_security_middleware(app)

        client = TestClient(app)
        response = client.get("/test")

        assert response.status_code == 200
        assert "X-Frame-Options" in response.headers

    def test_empty_security_configuration(self):
        """Test behavior with empty security configuration."""
        app = FastAPI()

        @app.get("/test")
        async def test_endpoint():
            return {"message": "test"}

        add_security_middleware(app, {})

        client = TestClient(app)
        response = client.get("/test")

        assert response.status_code == 200
        assert "X-Frame-Options" in response.headers


# Pytest markers for test categorization
pytestmark = [pytest.mark.unit, pytest.mark.security]
