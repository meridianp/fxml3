"""
Security Headers Middleware

TDD-driven implementation of security headers for production hardening.
Following Green phase - minimal implementation to pass tests.
"""

from typing import Callable, Dict, List, Optional

from fastapi import FastAPI, Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Middleware for adding security headers to responses."""

    def __init__(
        self,
        app: ASGIApp,
        allowed_origins: List[str] = None,
        csp_directives: Dict[str, str] = None,
        permissions_policy: Dict[str, str] = None,
    ):
        """Initialize security headers middleware."""
        super().__init__(app)
        self.allowed_origins = allowed_origins or []
        self.csp_directives = csp_directives or self._get_default_csp()
        self.permissions_policy = permissions_policy or self._get_default_permissions()

    def _get_default_csp(self) -> Dict[str, str]:
        """Get default Content Security Policy directives."""
        return {
            "default-src": "'self'",
            "script-src": "'self' 'unsafe-inline'",
            "style-src": "'self' 'unsafe-inline'",
            "img-src": "'self' data: https:",
            "connect-src": "'self'",
            "font-src": "'self' data:",
            "object-src": "'none'",
            "base-uri": "'self'",
            "form-action": "'self'",
        }

    def _get_default_permissions(self) -> Dict[str, str]:
        """Get default Permissions Policy."""
        return {
            "camera": "none",
            "microphone": "none",
            "geolocation": "self",
            "payment": "none",
            "usb": "none",
        }

    def _build_csp_header(self) -> str:
        """Build Content Security Policy header value."""
        directives = []
        for key, value in self.csp_directives.items():
            directives.append(f"{key} {value}")
        return "; ".join(directives)

    def _build_permissions_header(self) -> str:
        """Build Permissions Policy header value."""
        policies = []
        for key, value in self.permissions_policy.items():
            if value == "none":
                policies.append(f"{key}=()")
            elif value == "self":
                policies.append(f"{key}=(self)")
            else:
                policies.append(f"{key}=({value})")
        return ", ".join(policies)

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request and add security headers."""
        # Handle CORS preflight requests
        if request.method == "OPTIONS":
            origin = request.headers.get("Origin")
            if origin in self.allowed_origins:
                return Response(
                    content="",
                    status_code=200,
                    headers={
                        "Access-Control-Allow-Origin": origin,
                        "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS",
                        "Access-Control-Allow-Headers": request.headers.get(
                            "Access-Control-Request-Headers", "*"
                        ),
                        "Access-Control-Max-Age": "3600",
                        "Access-Control-Allow-Credentials": "true",
                    },
                )

        # Process request
        response = await call_next(request)

        # Add security headers
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

        # Add HSTS for HTTPS connections
        if request.url.scheme == "https":
            response.headers["Strict-Transport-Security"] = (
                "max-age=31536000; includeSubDomains"
            )

        # Add Content Security Policy
        response.headers["Content-Security-Policy"] = self._build_csp_header()

        # Add Permissions Policy
        response.headers["Permissions-Policy"] = self._build_permissions_header()

        # Add CORS headers if origin is allowed
        origin = request.headers.get("Origin")
        if origin in self.allowed_origins:
            response.headers["Access-Control-Allow-Origin"] = origin
            response.headers["Access-Control-Allow-Credentials"] = "true"

        return response