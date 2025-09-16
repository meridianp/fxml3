"""Test middleware components for FXML4 API.

This module tests the middleware components of the FXML4 API,
including rate limiting and CORS.
"""

import time
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from starlette.middleware.base import BaseHTTPMiddleware

from fxml4.api.main import app
from fxml4.api.middleware.rate_limiter import RateLimiter


def test_rate_limiter_middleware_init():
    """Test RateLimiter middleware initialization."""
    rate_limiter = RateLimiter(
        app=app, rate_limit_per_minute=60, exempted_routes=["/health"]
    )

    assert rate_limiter.rate_limit_per_minute == 60
    assert rate_limiter.window_size == 60
    assert rate_limiter.exempted_routes == ["/health"]


def test_rate_limiter_default_key_func():
    """Test RateLimiter default key function."""
    rate_limiter = RateLimiter(app=app)

    # Mock request
    mock_request = MagicMock()
    mock_request.client.host = "127.0.0.1"
    mock_request.headers = {}

    # Test default key function
    key = rate_limiter._default_key_func(mock_request)
    assert key == "127.0.0.1"

    # Test X-Forwarded-For header
    mock_request.headers = {"X-Forwarded-For": "192.168.1.1, 10.0.0.1"}
    key = rate_limiter._default_key_func(mock_request)
    assert key == "192.168.1.1"


def test_rate_limiter_exempt_route():
    """Test that exempted routes bypass rate limiting."""
    # Create a custom FastAPI app for testing
    from fastapi import FastAPI

    test_app = FastAPI()

    @test_app.get("/test")
    async def test_endpoint():
        return {"message": "test"}

    @test_app.get("/exempt")
    async def exempt_endpoint():
        return {"message": "exempt"}

    # Add rate limiter middleware with exempted route
    test_app.add_middleware(
        RateLimiter,
        rate_limit_per_minute=2,  # Low limit for testing
        exempted_routes=["/exempt"],
    )

    # Create test client
    client = TestClient(test_app)

    # The /test endpoint should be rate limited after 2 requests
    client.get("/test")
    client.get("/test")
    response = client.get("/test")
    assert response.status_code == 429

    # The /exempt endpoint should not be rate limited
    for _ in range(5):
        response = client.get("/exempt")
        assert response.status_code == 200


def test_rate_limiter_cleanup():
    """Test that old records are cleaned up."""
    rate_limiter = RateLimiter(app=app)

    # Add some test records
    now = time.time()
    rate_limiter.requests = {
        "ip1": {"count": 1, "window_start": now},
        "ip2": {"count": 2, "window_start": now - 70},  # Older than window size
        "ip3": {"count": 3, "window_start": now},
    }

    # Run cleanup
    rate_limiter._cleanup_old_records(now)

    # Only ip2 should be removed
    assert "ip1" in rate_limiter.requests
    assert "ip2" not in rate_limiter.requests
    assert "ip3" in rate_limiter.requests


def test_cors_middleware():
    """Test CORS middleware configuration."""
    response = TestClient(app).options(
        "/",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "Content-Type, Authorization",
        },
    )

    assert response.status_code == 200
    assert "access-control-allow-origin" in response.headers
    assert "access-control-allow-headers" in response.headers
    assert "access-control-allow-methods" in response.headers
    assert "access-control-allow-credentials" in response.headers

    # Test that methods are allowed
    assert "GET" in response.headers["access-control-allow-methods"]
    assert "POST" in response.headers["access-control-allow-methods"]

    # Test that headers are allowed
    assert "Content-Type" in response.headers["access-control-allow-headers"]
    assert "Authorization" in response.headers["access-control-allow-headers"]
