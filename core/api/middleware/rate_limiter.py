"""Rate limiting middleware for FXML4 API.

This module provides rate limiting functionality for the FXML4 API.
"""

import time
from typing import Callable, Dict, Optional

from fastapi import FastAPI, Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from fxml4.config import get_config


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


def add_rate_limiter(app: FastAPI) -> None:
    """Add rate limiter middleware to the app.

    Args:
        app: FastAPI app
    """
    rate_limit = int(get_config().get("api.rate_limit.requests_per_minute", 60))
    exempted_routes = get_config().get(
        "api.rate_limit.exempted_routes", ["/health", "/docs", "/openapi.json"]
    )

    app.add_middleware(
        RateLimiter, rate_limit_per_minute=rate_limit, exempted_routes=exempted_routes
    )
