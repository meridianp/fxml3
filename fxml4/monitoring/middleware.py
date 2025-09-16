"""
FastAPI middleware for automatic metrics collection.

Provides transparent performance monitoring for all API requests
without requiring changes to existing route handlers.
"""

import logging
import time
from typing import Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from .metrics import increment_counter, set_gauge, track_api_request

logger = logging.getLogger(__name__)


class PerformanceMiddleware(BaseHTTPMiddleware):
    """Middleware to automatically track API performance metrics."""

    def __init__(self, app, track_detailed_metrics: bool = True):
        """Initialize performance middleware.

        Args:
            app: FastAPI application instance
            track_detailed_metrics: Whether to track detailed per-endpoint metrics
        """
        super().__init__(app)
        self.track_detailed_metrics = track_detailed_metrics
        self._active_requests = 0

        logger.info("PerformanceMiddleware initialized")

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request and collect performance metrics."""
        # Track active requests
        self._active_requests += 1
        set_gauge("api_active_requests", self._active_requests)

        # Record request start
        start_time = time.time()
        method = request.method
        path = str(request.url.path)

        try:
            # Process request
            response = await call_next(request)
            status_code = response.status_code

        except Exception as e:
            # Handle errors
            logger.error(f"Request failed: {method} {path} - {str(e)}")
            status_code = 500

            # Create error response
            from starlette.responses import JSONResponse

            response = JSONResponse(
                status_code=500, content={"detail": "Internal server error"}
            )

        finally:
            # Calculate duration
            duration = time.time() - start_time

            # Update active requests counter
            self._active_requests -= 1
            set_gauge("api_active_requests", self._active_requests)

            # Track request metrics
            if self.track_detailed_metrics:
                # Clean path for better grouping (remove IDs, etc.)
                clean_path = self._clean_path(path)
                track_api_request(method, clean_path, status_code, duration)

            # Track general API metrics
            increment_counter("http_requests_total")

            if status_code >= 400:
                increment_counter("http_requests_errors_total")

            # Track slow requests
            if duration > 1.0:  # Requests taking more than 1 second
                increment_counter("http_requests_slow_total")
                logger.warning(f"Slow request: {method} {path} took {duration:.2f}s")

        return response

    def _clean_path(self, path: str) -> str:
        """Clean API path for better metric grouping."""
        # Common patterns to replace with placeholders
        import re

        # Replace UUIDs and common ID patterns
        path = re.sub(
            r"/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",
            "/{uuid}",
            path,
        )
        path = re.sub(r"/\d+", "/{id}", path)

        # Replace common query parameters
        if "?" in path:
            path = path.split("?")[0] + "?{query}"

        return path


class PrometheusMiddleware(BaseHTTPMiddleware):
    """Middleware to provide Prometheus-compatible metrics endpoint."""

    def __init__(self, app, metrics_path: str = "/metrics"):
        """Initialize Prometheus middleware.

        Args:
            app: FastAPI application instance
            metrics_path: Path to serve metrics on
        """
        super().__init__(app)
        self.metrics_path = metrics_path

        logger.info(f"PrometheusMiddleware initialized on {metrics_path}")

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Handle metrics endpoint or pass through to next middleware."""
        if request.url.path == self.metrics_path:
            return await self._serve_metrics()

        return await call_next(request)

    async def _serve_metrics(self) -> Response:
        """Serve metrics in Prometheus format."""
        from .metrics import get_metrics_collector

        try:
            collector = get_metrics_collector()
            prometheus_format = collector.get_prometheus_format()

            from starlette.responses import Response

            return Response(
                content=prometheus_format,
                media_type="text/plain; version=0.0.4; charset=utf-8",
            )

        except Exception as e:
            logger.error(f"Error serving metrics: {str(e)}")
            from starlette.responses import JSONResponse

            return JSONResponse(
                status_code=500, content={"error": "Failed to generate metrics"}
            )


class HealthCheckMiddleware(BaseHTTPMiddleware):
    """Middleware to provide health check endpoint with metrics."""

    def __init__(self, app, health_path: str = "/health"):
        """Initialize health check middleware.

        Args:
            app: FastAPI application instance
            health_path: Path to serve health check on
        """
        super().__init__(app)
        self.health_path = health_path
        self._start_time = time.time()

        logger.info(f"HealthCheckMiddleware initialized on {health_path}")

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Handle health check endpoint or pass through to next middleware."""
        if request.url.path == self.health_path:
            return await self._serve_health_check()

        return await call_next(request)

    async def _serve_health_check(self) -> Response:
        """Serve health check with system metrics."""
        from .metrics import get_metrics_collector

        try:
            collector = get_metrics_collector()
            metrics_summary = collector.get_metrics_summary()

            # Build health check response
            health_data = {
                "status": "healthy",
                "timestamp": time.time(),
                "uptime_seconds": time.time() - self._start_time,
                "version": "2.0.0",
                "metrics": {
                    "total_requests": metrics_summary.get("counters", {}).get(
                        "http_requests_total", 0
                    ),
                    "error_requests": metrics_summary.get("counters", {}).get(
                        "http_requests_errors_total", 0
                    ),
                    "active_requests": metrics_summary.get("gauges", {}).get(
                        "api_active_requests", 0
                    ),
                    "metrics_collected": metrics_summary.get("system", {}).get(
                        "metrics_collected", 0
                    ),
                },
            }

            from starlette.responses import JSONResponse

            return JSONResponse(content=health_data)

        except Exception as e:
            logger.error(f"Error serving health check: {str(e)}")
            from starlette.responses import JSONResponse

            return JSONResponse(
                status_code=500,
                content={
                    "status": "unhealthy",
                    "error": str(e),
                    "timestamp": time.time(),
                },
            )


def setup_monitoring_middleware(
    app, enable_prometheus: bool = True, enable_health: bool = True
):
    """Setup all monitoring middleware for FastAPI app.

    Args:
        app: FastAPI application instance
        enable_prometheus: Whether to enable Prometheus metrics endpoint
        enable_health: Whether to enable enhanced health check endpoint
    """
    # Add performance monitoring (should be first)
    app.add_middleware(PerformanceMiddleware, track_detailed_metrics=True)

    # Add Prometheus metrics endpoint
    if enable_prometheus:
        app.add_middleware(PrometheusMiddleware, metrics_path="/metrics")

    # Add enhanced health check
    if enable_health:
        app.add_middleware(HealthCheckMiddleware, health_path="/health")

    logger.info("Monitoring middleware setup complete")

    return app
