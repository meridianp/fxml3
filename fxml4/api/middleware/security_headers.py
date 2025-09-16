"""Security headers middleware for FastAPI."""

import logging
from typing import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Middleware to add security headers to all responses."""

    def __init__(self, app, config: dict = None):
        """Initialize security headers middleware.

        Args:
            app: FastAPI application
            config: Security configuration
        """
        super().__init__(app)
        self.config = config or {}

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Add security headers to response.

        Args:
            request: HTTP request
            call_next: Next middleware/handler

        Returns:
            Response with security headers
        """
        response = await call_next(request)

        # Add security headers
        security_headers = {
            # Prevent clickjacking
            "X-Frame-Options": "DENY",
            # Prevent content-type sniffing
            "X-Content-Type-Options": "nosniff",
            # Enable XSS protection
            "X-XSS-Protection": "1; mode=block",
            # Referrer policy
            "Referrer-Policy": "strict-origin-when-cross-origin",
            # Content Security Policy
            "Content-Security-Policy": (
                "default-src 'self'; "
                "script-src 'self' 'unsafe-inline' 'unsafe-eval' https://cdn.jsdelivr.net; "
                "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
                "font-src 'self' https://fonts.gstatic.com; "
                "img-src 'self' data: https:; "
                "connect-src 'self' wss: ws:; "
                "object-src 'none'; "
                "base-uri 'self'; "
                "frame-ancestors 'none';"
            ),
            # Remove server information
            "Server": "FXML4",
            # Permissions Policy (formerly Feature Policy)
            "Permissions-Policy": (
                "geolocation=(), "
                "microphone=(), "
                "camera=(), "
                "payment=(), "
                "usb=(), "
                "magnetometer=(), "
                "gyroscope=(), "
                "accelerometer=()"
            ),
        }

        # Add HSTS only for HTTPS
        if request.url.scheme == "https":
            security_headers["Strict-Transport-Security"] = (
                "max-age=31536000; includeSubDomains; preload"
            )

        # Allow custom headers from config
        custom_headers = self.config.get("custom_headers", {})
        security_headers.update(custom_headers)

        # Apply headers to response
        for header, value in security_headers.items():
            response.headers[header] = value

        return response


class RequestSizeLimitMiddleware(BaseHTTPMiddleware):
    """Middleware to limit request size for security."""

    def __init__(self, app, max_size: int = 10 * 1024 * 1024):  # 10MB default
        """Initialize request size limit middleware.

        Args:
            app: FastAPI application
            max_size: Maximum request size in bytes
        """
        super().__init__(app)
        self.max_size = max_size

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Check request size before processing.

        Args:
            request: HTTP request
            call_next: Next middleware/handler

        Returns:
            Response or error if request too large
        """
        # Check Content-Length header
        content_length = request.headers.get("content-length")
        if content_length and int(content_length) > self.max_size:
            logger.warning(
                "Request size %s exceeds limit %s from %s",
                content_length,
                self.max_size,
                request.client.host,
            )
            return Response(
                content="Request entity too large",
                status_code=413,
                headers={"Content-Type": "text/plain"},
            )

        return await call_next(request)


class TrustedHostMiddleware(BaseHTTPMiddleware):
    """Middleware to validate Host header against allowed hosts."""

    def __init__(self, app, allowed_hosts: list = None):
        """Initialize trusted host middleware.

        Args:
            app: FastAPI application
            allowed_hosts: List of allowed hostnames
        """
        super().__init__(app)
        self.allowed_hosts = allowed_hosts or ["localhost", "127.0.0.1"]

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Validate Host header.

        Args:
            request: HTTP request
            call_next: Next middleware/handler

        Returns:
            Response or error if host not allowed
        """
        host = request.headers.get("host", "").split(":")[0]  # Remove port

        # Check if host is allowed
        if self.allowed_hosts and host not in self.allowed_hosts:
            # Check for wildcard matches
            allowed = False
            for allowed_host in self.allowed_hosts:
                if allowed_host.startswith("*") and host.endswith(allowed_host[1:]):
                    allowed = True
                    break

            if not allowed:
                logger.warning("Disallowed host %s from %s", host, request.client.host)
                return Response(
                    content="Disallowed host",
                    status_code=400,
                    headers={"Content-Type": "text/plain"},
                )

        return await call_next(request)


def add_security_middleware(app, config: dict = None):
    """Add all security middleware to the app.

    Args:
        app: FastAPI application
        config: Security configuration
    """
    security_config = config or {}

    # Add security headers middleware
    app.add_middleware(SecurityHeadersMiddleware, config=security_config)

    # Add request size limit middleware
    max_request_size = security_config.get("max_request_size", 10 * 1024 * 1024)
    app.add_middleware(RequestSizeLimitMiddleware, max_size=max_request_size)

    # Add trusted host middleware
    allowed_hosts = security_config.get("allowed_hosts", ["localhost", "127.0.0.1"])
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=allowed_hosts)

    logger.info("Security middleware added to application")
