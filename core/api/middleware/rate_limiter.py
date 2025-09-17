"""Rate limiting middleware for FXML4 API.

This module provides rate limiting functionality for the FXML4 API.
"""

import time
from collections import defaultdict
from typing import Callable, Dict, List, Optional

from fastapi import FastAPI, Request, Response, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp


class RateLimiter(BaseHTTPMiddleware):
    """Rate limiting middleware for FXML4 API."""

    def __init__(
        self,
        app: ASGIApp,
        rate_limit_per_minute: int = 60,
        exempted_routes: Optional[list] = None,
        key_func: Optional[Callable] = None,
    ):
        """Initialize the rate limiter.

        Args:
            app: ASGI app
            rate_limit_per_minute: Maximum number of requests per minute
            exempted_routes: List of routes exempt from rate limiting
            key_func: Function to generate rate limit key
        """
        super().__init__(app)
        self.rate_limit_per_minute = rate_limit_per_minute
        self.window_size = 60  # window size in seconds
        self.exempted_routes = exempted_routes or []
        self.key_func = key_func or self._default_key_func
        self.requests: Dict[str, Dict] = {}

    @staticmethod
    def _default_key_func(request: Request) -> str:
        """Default function to generate rate limit key.

        Args:
            request: FastAPI request

        Returns:
            Rate limit key
        """
        # Use IP address as default key
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            return forwarded.split(",")[0].strip()
        return request.client.host if request.client else "unknown"

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process the request and apply rate limiting.

        Args:
            request: FastAPI request
            call_next: Function to call the next middleware

        Returns:
            FastAPI response
        """
        # Check if the route is exempted
        path = request.url.path
        for exempted_route in self.exempted_routes:
            if path.startswith(exempted_route):
                return await call_next(request)

        # Get the key for this request
        key = self.key_func(request)

        # Get the current timestamp
        now = time.time()

        # Create or update request record
        if key not in self.requests:
            self.requests[key] = {"count": 0, "window_start": now}

        # Reset if outside the window
        if now - self.requests[key]["window_start"] >= self.window_size:
            self.requests[key] = {"count": 0, "window_start": now}

        # Check if rate limit exceeded
        if self.requests[key]["count"] >= self.rate_limit_per_minute:
            # Cleanup old records periodically
            self._cleanup_old_records(now)

            # Return 429 Too Many Requests
            return Response(
                content="Rate limit exceeded. Please try again later.",
                status_code=429,
                headers={"Retry-After": str(self.window_size)},
            )

        # Increment the request count
        self.requests[key]["count"] += 1

        # Cleanup old records periodically
        if self.requests[key]["count"] % 10 == 0:
            self._cleanup_old_records(now)

        # Process the request
        return await call_next(request)

    def _cleanup_old_records(self, now: float) -> None:
        """Clean up expired rate limit records.

        Args:
            now: Current timestamp
        """
        # Delete records older than the window size
        keys_to_delete = []
        for key, record in self.requests.items():
            if now - record["window_start"] >= self.window_size:
                keys_to_delete.append(key)

        for key in keys_to_delete:
            del self.requests[key]


class RateLimitingMiddleware(BaseHTTPMiddleware):
    """Enhanced rate limiting middleware with Redis support."""

    def __init__(
        self,
        app: ASGIApp,
        requests_per_minute: int = 60,
        requests_per_hour: int = 1000,
        whitelisted_ips: List[str] = None,
        endpoint_limits: Dict[str, int] = None,
        redis_client: Optional[any] = None,
    ):
        """Initialize enhanced rate limiting middleware."""
        super().__init__(app)
        self.requests_per_minute = requests_per_minute
        self.requests_per_hour = requests_per_hour
        self.whitelisted_ips = whitelisted_ips or []
        self.endpoint_limits = endpoint_limits or {}
        self.redis_client = redis_client

        # In-memory storage for rate limiting (when Redis not available)
        self.request_counts = defaultdict(lambda: {"count": 0, "reset_time": time.time()})
        self.hourly_counts = defaultdict(lambda: {"count": 0, "reset_time": time.time()})

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request through rate limiting."""
        # Get client identifier (IP or user ID)
        client_ip = request.client.host if request.client else "unknown"

        # Check if IP is whitelisted
        if client_ip in self.whitelisted_ips:
            response = await call_next(request)
            return response

        # Get rate limit for this endpoint
        endpoint = request.url.path
        limit = self.endpoint_limits.get(endpoint, self.requests_per_minute)

        # Check if user is authenticated (higher limits)
        is_authenticated = "Authorization" in request.headers
        if is_authenticated and hasattr(request, "state") and hasattr(request.state, "user"):
            limit = min(limit * 2, 100)  # Authenticated users get double limit (max 100)

        # Use Redis if available, otherwise in-memory
        if self.redis_client:
            is_limited = await self._check_rate_limit_redis(client_ip, endpoint, limit)
        else:
            is_limited = self._check_rate_limit_memory(client_ip, endpoint, limit)

        if is_limited:
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={"detail": "Rate limit exceeded. Please try again later."},
                headers={
                    "X-Rate-Limit-Message": "Rate limit exceeded",
                    "Retry-After": "60",
                },
            )

        # Process request
        response = await call_next(request)

        # Add rate limit headers
        remaining = limit - self._get_current_count(client_ip, endpoint)
        response.headers["X-Rate-Limit-Limit"] = str(limit)
        response.headers["X-Rate-Limit-Remaining"] = str(max(0, remaining - 1))
        response.headers["X-Rate-Limit-Reset"] = str(int(time.time()) + 60)

        return response

    async def _check_rate_limit_redis(
        self, client_id: str, endpoint: str, limit: int
    ) -> bool:
        """Check rate limit using Redis backend."""
        key = f"rate_limit:{client_id}:{endpoint}"

        try:
            # Increment counter
            count = self.redis_client.incr(key)

            # Set expiry on first request
            if count == 1:
                self.redis_client.expire(key, 60)

            return count > limit
        except Exception:
            # Fallback to memory if Redis fails
            return self._check_rate_limit_memory(client_id, endpoint, limit)

    def _check_rate_limit_memory(
        self, client_id: str, endpoint: str, limit: int
    ) -> bool:
        """Check rate limit using in-memory storage."""
        current_time = time.time()
        key = f"{client_id}:{endpoint}"

        # Check minute limit
        if current_time - self.request_counts[key]["reset_time"] > 60:
            self.request_counts[key] = {"count": 0, "reset_time": current_time}

        self.request_counts[key]["count"] += 1

        # Check hour limit
        hour_key = f"{client_id}:hourly"
        if current_time - self.hourly_counts[hour_key]["reset_time"] > 3600:
            self.hourly_counts[hour_key] = {"count": 0, "reset_time": current_time}

        self.hourly_counts[hour_key]["count"] += 1

        # Check if limits exceeded
        if self.request_counts[key]["count"] > limit:
            return True

        if self.hourly_counts[hour_key]["count"] > self.requests_per_hour:
            return True

        return False

    def _get_current_count(self, client_id: str, endpoint: str) -> int:
        """Get current request count for client."""
        if self.redis_client:
            try:
                key = f"rate_limit:{client_id}:{endpoint}"
                count = self.redis_client.get(key)
                return int(count) if count else 0
            except Exception:
                pass

        # Fallback to memory
        key = f"{client_id}:{endpoint}"
        return self.request_counts[key]["count"]


def add_rate_limiter(app: FastAPI) -> None:
    """Add rate limiter middleware to the app.

    Args:
        app: FastAPI app
    """
    try:
        from fxml4.config import get_config
        rate_limit = int(get_config().get("api.rate_limit.requests_per_minute", 60))
        exempted_routes = get_config().get(
            "api.rate_limit.exempted_routes", ["/health", "/docs", "/openapi.json"]
        )
    except ImportError:
        # Default values if config not available
        rate_limit = 60
        exempted_routes = ["/health", "/docs", "/openapi.json"]

    app.add_middleware(
        RateLimiter, rate_limit_per_minute=rate_limit, exempted_routes=exempted_routes
    )
