"""
TDD Tests for Security Middleware with Rate Limiting

Tests comprehensive security middleware functionality including rate limiting,
security headers, and request validation.
Following Red-Green-Refactor methodology.
"""

import time
from datetime import datetime, timedelta
from typing import Dict, Optional
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI, Request, Response
from fastapi.testclient import TestClient
from starlette.middleware.base import BaseHTTPMiddleware

from core.api.auth.models import User, UserRole


@pytest.mark.tdd
@pytest.mark.red
class TestRateLimitingMiddleware:
    """
    RED Phase: Test rate limiting middleware that doesn't exist yet.

    Tests cover rate limiting by IP, user, and endpoint.
    """

    def test_rate_limiter_import(self):
        """RED: Test that we can import the rate limiter middleware."""
        from core.api.middleware.rate_limiter import RateLimitingMiddleware

        middleware = RateLimitingMiddleware(app=None)
        assert middleware is not None

    @pytest.mark.asyncio
    async def test_rate_limit_by_ip(self):
        """RED: Test rate limiting by IP address."""
        from core.api.middleware.rate_limiter import RateLimitingMiddleware

        app = FastAPI()
        middleware = RateLimitingMiddleware(
            app=app,
            requests_per_minute=60,
            requests_per_hour=1000,
        )

        # Create mock request
        request = MagicMock(spec=Request)
        request.client.host = "192.168.1.100"
        request.url.path = "/api/v1/test"
        request.method = "GET"
        request.headers = {}

        # Simulate requests within rate limit
        for i in range(60):
            call_next = AsyncMock(return_value=Response(content="OK"))
            response = await middleware.dispatch(request, call_next)
            assert response.status_code == 200

        # 61st request should be rate limited
        call_next = AsyncMock(return_value=Response(content="OK"))
        response = await middleware.dispatch(request, call_next)
        assert response.status_code == 429
        assert "Rate limit exceeded" in response.headers.get("X-Rate-Limit-Message", "")

    @pytest.mark.asyncio
    async def test_rate_limit_by_user(self):
        """RED: Test rate limiting by authenticated user."""
        from core.api.middleware.rate_limiter import RateLimitingMiddleware

        app = FastAPI()
        middleware = RateLimitingMiddleware(
            app=app,
            requests_per_minute=100,  # Higher limit for authenticated users
            requests_per_hour=2000,
        )

        # Create mock authenticated request
        request = MagicMock(spec=Request)
        request.client.host = "192.168.1.100"
        request.url.path = "/api/v1/test"
        request.method = "GET"
        request.headers = {"Authorization": "Bearer valid_token"}
        request.state.user = User(
            user_id="trader_123",
            username="trader",
            email="trader@fxml4.com",
            role=UserRole.TRADER,
            is_active=True,
        )

        # Authenticated users get higher limits
        for i in range(100):
            call_next = AsyncMock(return_value=Response(content="OK"))
            response = await middleware.dispatch(request, call_next)
            assert response.status_code == 200

        # 101st request should be rate limited
        call_next = AsyncMock(return_value=Response(content="OK"))
        response = await middleware.dispatch(request, call_next)
        assert response.status_code == 429

    @pytest.mark.asyncio
    async def test_rate_limit_headers(self):
        """RED: Test rate limit headers in response."""
        from core.api.middleware.rate_limiter import RateLimitingMiddleware

        app = FastAPI()
        middleware = RateLimitingMiddleware(
            app=app,
            requests_per_minute=60,
        )

        request = MagicMock(spec=Request)
        request.client.host = "192.168.1.100"
        request.url.path = "/api/v1/test"
        request.method = "GET"
        request.headers = {}

        call_next = AsyncMock(return_value=Response(content="OK"))
        response = await middleware.dispatch(request, call_next)

        # Check rate limit headers
        assert "X-Rate-Limit-Limit" in response.headers
        assert "X-Rate-Limit-Remaining" in response.headers
        assert "X-Rate-Limit-Reset" in response.headers

        limit = int(response.headers["X-Rate-Limit-Limit"])
        remaining = int(response.headers["X-Rate-Limit-Remaining"])
        assert limit == 60
        assert remaining == 58  # After one request (count starts at 1, so 60 - 1 - 1 = 58)

    @pytest.mark.asyncio
    async def test_rate_limit_whitelist(self):
        """RED: Test whitelisted IPs bypass rate limiting."""
        from core.api.middleware.rate_limiter import RateLimitingMiddleware

        app = FastAPI()
        middleware = RateLimitingMiddleware(
            app=app,
            requests_per_minute=1,  # Very low limit
            whitelisted_ips=["127.0.0.1", "192.168.1.200"],
        )

        # Whitelisted IP
        request = MagicMock(spec=Request)
        request.client.host = "127.0.0.1"
        request.url.path = "/api/v1/test"
        request.method = "GET"
        request.headers = {}

        # Should not be rate limited even with many requests
        for i in range(100):
            call_next = AsyncMock(return_value=Response(content="OK"))
            response = await middleware.dispatch(request, call_next)
            assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_rate_limit_endpoint_specific(self):
        """RED: Test endpoint-specific rate limits."""
        from core.api.middleware.rate_limiter import RateLimitingMiddleware

        app = FastAPI()
        middleware = RateLimitingMiddleware(
            app=app,
            requests_per_minute=60,
            endpoint_limits={
                "/api/v1/auth/login": 5,  # Strict limit for login
                "/api/v1/auth/register": 3,  # Even stricter for registration
            },
        )

        # Test login endpoint with strict limit
        request = MagicMock(spec=Request)
        request.client.host = "192.168.1.100"
        request.url.path = "/api/v1/auth/login"
        request.method = "POST"
        request.headers = {}

        # Should allow 5 requests
        for i in range(5):
            call_next = AsyncMock(return_value=Response(content="OK"))
            response = await middleware.dispatch(request, call_next)
            assert response.status_code == 200

        # 6th request should be rate limited
        call_next = AsyncMock(return_value=Response(content="OK"))
        response = await middleware.dispatch(request, call_next)
        assert response.status_code == 429

    @pytest.mark.asyncio
    async def test_rate_limit_redis_backend(self):
        """RED: Test rate limiting with Redis backend for distributed systems."""
        from core.api.middleware.rate_limiter import RateLimitingMiddleware

        app = FastAPI()

        # Mock Redis client
        mock_redis = MagicMock()
        mock_redis.incr.return_value = 1
        mock_redis.expire.return_value = True
        mock_redis.ttl.return_value = 60

        middleware = RateLimitingMiddleware(
            app=app,
            requests_per_minute=60,
            redis_client=mock_redis,
        )

        request = MagicMock(spec=Request)
        request.client.host = "192.168.1.100"
        request.url.path = "/api/v1/test"
        request.method = "GET"
        request.headers = {}

        call_next = AsyncMock(return_value=Response(content="OK"))
        response = await middleware.dispatch(request, call_next)

        # Verify Redis was used
        mock_redis.incr.assert_called()
        mock_redis.expire.assert_called()
        assert response.status_code == 200


@pytest.mark.tdd
@pytest.mark.red
class TestSecurityHeadersMiddleware:
    """
    RED Phase: Test security headers middleware that doesn't exist yet.

    Tests cover security headers for production hardening.
    """

    def test_security_headers_import(self):
        """RED: Test that we can import the security headers middleware."""
        from core.api.middleware.security_headers import SecurityHeadersMiddleware

        middleware = SecurityHeadersMiddleware(app=None)
        assert middleware is not None

    @pytest.mark.asyncio
    async def test_security_headers_added(self):
        """RED: Test that security headers are added to responses."""
        from core.api.middleware.security_headers import SecurityHeadersMiddleware

        app = FastAPI()
        middleware = SecurityHeadersMiddleware(app=app)

        request = MagicMock(spec=Request)
        request.url.scheme = "https"
        request.url.netloc = "api.fxml4.com"

        response = Response(content="OK")
        call_next = AsyncMock(return_value=response)

        response = await middleware.dispatch(request, call_next)

        # Check security headers
        assert response.headers["X-Content-Type-Options"] == "nosniff"
        assert response.headers["X-Frame-Options"] == "DENY"
        assert response.headers["X-XSS-Protection"] == "1; mode=block"
        assert response.headers["Strict-Transport-Security"] == "max-age=31536000; includeSubDomains"
        assert "Content-Security-Policy" in response.headers
        assert response.headers["Referrer-Policy"] == "strict-origin-when-cross-origin"

    @pytest.mark.asyncio
    async def test_cors_preflight_handling(self):
        """RED: Test CORS preflight request handling."""
        from core.api.middleware.security_headers import SecurityHeadersMiddleware

        app = FastAPI()
        middleware = SecurityHeadersMiddleware(
            app=app,
            allowed_origins=["https://app.fxml4.com", "https://localhost:3000"],
        )

        # Preflight request
        request = MagicMock(spec=Request)
        request.method = "OPTIONS"
        request.headers = {
            "Origin": "https://app.fxml4.com",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type,authorization",
        }

        call_next = AsyncMock(return_value=Response(content=""))
        response = await middleware.dispatch(request, call_next)

        # Check CORS headers
        assert response.status_code == 200
        assert response.headers["Access-Control-Allow-Origin"] == "https://app.fxml4.com"
        assert "POST" in response.headers["Access-Control-Allow-Methods"]
        assert "authorization" in response.headers["Access-Control-Allow-Headers"].lower()
        assert response.headers["Access-Control-Max-Age"] == "3600"

    @pytest.mark.asyncio
    async def test_content_security_policy(self):
        """RED: Test Content Security Policy configuration."""
        from core.api.middleware.security_headers import SecurityHeadersMiddleware

        app = FastAPI()
        middleware = SecurityHeadersMiddleware(
            app=app,
            csp_directives={
                "default-src": "'self'",
                "script-src": "'self' 'unsafe-inline' https://cdn.jsdelivr.net",
                "style-src": "'self' 'unsafe-inline'",
                "img-src": "'self' data: https:",
                "connect-src": "'self' wss://api.fxml4.com",
            },
        )

        request = MagicMock(spec=Request)
        response = Response(content="OK")
        call_next = AsyncMock(return_value=response)

        response = await middleware.dispatch(request, call_next)

        csp = response.headers["Content-Security-Policy"]
        assert "default-src 'self'" in csp
        assert "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net" in csp
        assert "connect-src 'self' wss://api.fxml4.com" in csp

    @pytest.mark.asyncio
    async def test_permissions_policy(self):
        """RED: Test Permissions Policy (Feature Policy) configuration."""
        from core.api.middleware.security_headers import SecurityHeadersMiddleware

        app = FastAPI()
        middleware = SecurityHeadersMiddleware(
            app=app,
            permissions_policy={
                "camera": "none",
                "microphone": "none",
                "geolocation": "self",
                "payment": "self",
            },
        )

        request = MagicMock(spec=Request)
        response = Response(content="OK")
        call_next = AsyncMock(return_value=response)

        response = await middleware.dispatch(request, call_next)

        pp = response.headers["Permissions-Policy"]
        assert "camera=()" in pp  # none format is ()
        assert "microphone=()" in pp
        assert "geolocation=(self)" in pp
        assert "payment=(self)" in pp


@pytest.mark.tdd
@pytest.mark.red
class TestRequestValidationMiddleware:
    """
    RED Phase: Test request validation middleware that doesn't exist yet.

    Tests cover request size limits, content type validation, and input sanitization.
    """

    def test_request_validation_import(self):
        """RED: Test that we can import the request validation middleware."""
        from core.api.middleware.request_validator import RequestValidationMiddleware

        middleware = RequestValidationMiddleware(app=None)
        assert middleware is not None

    @pytest.mark.asyncio
    async def test_request_size_limit(self):
        """RED: Test request body size limit enforcement."""
        from core.api.middleware.request_validator import RequestValidationMiddleware

        app = FastAPI()
        middleware = RequestValidationMiddleware(
            app=app,
            max_body_size=1024 * 1024,  # 1MB limit
        )

        # Large request body
        request = MagicMock(spec=Request)
        request.headers = {
            "Content-Length": str(2 * 1024 * 1024),  # 2MB
            "Content-Type": "application/json",
        }

        call_next = AsyncMock(return_value=Response(content="OK"))
        response = await middleware.dispatch(request, call_next)

        assert response.status_code == 413  # Payload Too Large
        assert "Request body too large" in response.body.decode()

    @pytest.mark.asyncio
    async def test_content_type_validation(self):
        """RED: Test content type validation for API endpoints."""
        from core.api.middleware.request_validator import RequestValidationMiddleware

        app = FastAPI()
        middleware = RequestValidationMiddleware(
            app=app,
            allowed_content_types=["application/json", "multipart/form-data"],
        )

        # Invalid content type
        request = MagicMock(spec=Request)
        request.url.path = "/api/v1/data"
        request.method = "POST"
        request.headers = {
            "Content-Type": "text/plain",
        }

        call_next = AsyncMock(return_value=Response(content="OK"))
        response = await middleware.dispatch(request, call_next)

        assert response.status_code == 415  # Unsupported Media Type
        assert "Unsupported content type" in response.body.decode()

    @pytest.mark.asyncio
    async def test_sql_injection_detection(self):
        """RED: Test SQL injection pattern detection."""
        from core.api.middleware.request_validator import RequestValidationMiddleware

        app = FastAPI()
        middleware = RequestValidationMiddleware(
            app=app,
            enable_sql_injection_detection=True,
        )

        # Request with SQL injection attempt
        request = MagicMock(spec=Request)
        request.url.path = "/api/v1/users"
        request.url.query = "id=1; DROP TABLE users;--"
        request.method = "GET"

        call_next = AsyncMock(return_value=Response(content="OK"))
        response = await middleware.dispatch(request, call_next)

        assert response.status_code == 400  # Bad Request
        assert "Potentially malicious request detected" in response.body.decode()

    @pytest.mark.asyncio
    async def test_xss_detection(self):
        """RED: Test XSS pattern detection in request parameters."""
        from core.api.middleware.request_validator import RequestValidationMiddleware

        app = FastAPI()
        middleware = RequestValidationMiddleware(
            app=app,
            enable_xss_detection=True,
        )

        # Request with XSS attempt
        request = MagicMock(spec=Request)
        request.url.path = "/api/v1/profile"
        request.url.query = "name=<script>alert('XSS')</script>"
        request.method = "GET"

        call_next = AsyncMock(return_value=Response(content="OK"))
        response = await middleware.dispatch(request, call_next)

        assert response.status_code == 400  # Bad Request
        assert "Potentially malicious request detected" in response.body.decode()

    @pytest.mark.asyncio
    async def test_request_id_injection(self):
        """RED: Test request ID injection for tracing."""
        from core.api.middleware.request_validator import RequestValidationMiddleware

        app = FastAPI()
        middleware = RequestValidationMiddleware(
            app=app,
            inject_request_id=True,
        )

        request = MagicMock(spec=Request)
        request.headers = {}
        request.state = MagicMock()

        response = Response(content="OK")
        call_next = AsyncMock(return_value=response)

        response = await middleware.dispatch(request, call_next)

        # Check request ID was added
        assert "X-Request-ID" in response.headers
        assert len(response.headers["X-Request-ID"]) == 36  # UUID format