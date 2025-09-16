"""
Security middleware for FXML4 API.

This middleware provides:
- Environment-based security configuration
- Request logging and correlation IDs
- Security headers
- Rate limiting support
- Proper authentication flow without bypasses

SECURITY: This middleware replaces the dangerous development authentication bypass
with proper environment-aware security controls.
"""

import logging
import os
import uuid
from typing import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

logger = logging.getLogger(__name__)


class SecurityMiddleware(BaseHTTPMiddleware):
    """
    Security middleware that provides environment-aware security controls.

    This middleware:
    - Adds security headers
    - Generates correlation IDs for request tracing
    - Provides environment-based configuration
    - Logs security events
    - Does NOT provide authentication bypasses
    """

    def __init__(self):
        """Initialize security middleware with environment-based config."""
        self.environment = os.getenv("FXML4_ENVIRONMENT", "development").lower()
        self.debug_mode = os.getenv("FXML4_DEBUG", "false").lower() == "true"

        # Security settings based on environment
        self.security_headers = self._get_security_headers()

        logger.info(
            f"SecurityMiddleware initialized for environment: {self.environment}"
        )

        if self.environment == "development" and self.debug_mode:
            logger.warning(
                "Running in development mode with debug enabled. "
                "Ensure this is not used in production!"
            )

    def _get_security_headers(self) -> dict:
        """Get security headers based on environment."""
        base_headers = {
            "X-Content-Type-Options": "nosniff",
            "X-Frame-Options": "DENY",
            "X-XSS-Protection": "1; mode=block",
            "Referrer-Policy": "strict-origin-when-cross-origin",
        }

        if self.environment == "production":
            # Production-only security headers
            base_headers.update(
                {
                    "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
                    "Content-Security-Policy": (
                        "default-src 'self'; script-src 'self' 'unsafe-inline'; "
                        "style-src 'self' 'unsafe-inline'"
                    ),
                }
            )

        return base_headers

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """
        Process request with security controls.

        This method:
        1. Generates correlation ID for tracing
        2. Logs request information
        3. Adds security headers to response
        4. Does NOT bypass authentication
        """
        # Generate correlation ID for request tracing
        correlation_id = str(uuid.uuid4())
        request.state.correlation_id = correlation_id

        # Get client information for logging
        client_ip = self._get_client_ip(request)
        user_agent = request.headers.get("user-agent", "unknown")

        # Log request (in debug mode or for security events)
        if self.debug_mode or self._is_security_relevant_path(request.url.path):
            logger.info(
                f"Request: {request.method} {request.url.path} "
                f"from {client_ip} (correlation_id: {correlation_id})"
            )

        # Store security context for downstream use
        request.state.client_ip = client_ip
        request.state.user_agent = user_agent
        request.state.environment = self.environment

        # Process request
        try:
            response = await call_next(request)
        except Exception as e:
            # Log security-relevant exceptions
            logger.error(
                f"Request failed: {request.method} {request.url.path} "
                f"from {client_ip} - Error: {str(e)} "
                f"(correlation_id: {correlation_id})"
            )

            # Return generic error in production
            if self.environment == "production":
                return JSONResponse(
                    status_code=500,
                    content={
                        "error": "Internal server error",
                        "correlation_id": correlation_id,
                    },
                )
            else:
                # Re-raise in development for debugging
                raise

        # Add security headers
        for header_name, header_value in self.security_headers.items():
            response.headers[header_name] = header_value

        # Add correlation ID to response
        response.headers["X-Correlation-ID"] = correlation_id

        # Log response status for security monitoring
        if response.status_code >= 400:
            logger.warning(
                f"HTTP {response.status_code}: {request.method} {request.url.path} "
                f"from {client_ip} (correlation_id: {correlation_id})"
            )

        return response

    def _get_client_ip(self, request: Request) -> str:
        """
        Get the real client IP address, considering proxy headers.

        This is important for security logging and rate limiting.
        """
        # Check for proxy headers (in order of preference)
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            # X-Forwarded-For can contain multiple IPs, take the first (original client)
            return forwarded_for.split(",")[0].strip()

        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip.strip()

        # Fallback to direct connection IP
        if request.client:
            return request.client.host

        return "unknown"

    def _is_security_relevant_path(self, path: str) -> bool:
        """
        Check if a path is security-relevant and should be logged.

        Security-relevant paths include authentication, trading, and admin endpoints.
        """
        security_paths = [
            "/auth/",
            "/trading/",
            "/admin/",
            "/api/v1/auth/",
            "/api/v1/trading/",
            "/api/v1/admin/",
        ]

        return any(security_path in path for security_path in security_paths)


class DevelopmentSecurityMiddleware(SecurityMiddleware):
    """
    Development-specific security middleware.

    This provides additional development conveniences while maintaining security.
    IMPORTANT: This should NEVER be used in production.
    """

    def __init__(self):
        super().__init__()

        if self.environment != "development":
            raise ValueError(
                "DevelopmentSecurityMiddleware can only be used in development "
                f"environment. Current environment: {self.environment}"
            )

        logger.warning(
            "DevelopmentSecurityMiddleware active. This provides development "
            "conveniences but should NEVER be used in production."
        )

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """
        Development dispatch with additional logging.

        Note: This does NOT provide authentication bypasses for security reasons.
        """
        # Add development-specific context
        request.state.development_mode = True

        # Enhanced logging in development
        logger.debug(
            f"DEV: Processing {request.method} {request.url.path} "
            f"from {self._get_client_ip(request)}"
        )

        # Call parent dispatch (maintains all security controls)
        response = await super().dispatch(request, call_next)

        # Development-specific response headers
        response.headers["X-Development-Mode"] = "true"

        return response


# Factory function to create appropriate middleware based on environment
def create_security_middleware() -> SecurityMiddleware:
    """
    Create appropriate security middleware based on environment.

    Returns:
        SecurityMiddleware: Standard security middleware for production/staging
        DevelopmentSecurityMiddleware: Enhanced logging for development
    """
    environment = os.getenv("FXML4_ENVIRONMENT", "development").lower()

    if environment == "development":
        # Note: Even in development, we use standard security middleware
        # The DevelopmentSecurityMiddleware is available but not used by default
        # to prevent accidental security bypasses
        return SecurityMiddleware()
    else:
        return SecurityMiddleware()
