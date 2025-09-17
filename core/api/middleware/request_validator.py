"""
Request Validation Middleware

TDD-driven implementation of request validation for security.
Following Green phase - minimal implementation to pass tests.
"""

import re
import uuid
from typing import Callable, List, Optional

from fastapi import FastAPI, Request, Response, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp


class RequestValidationMiddleware(BaseHTTPMiddleware):
    """Middleware for validating and sanitizing requests."""

    def __init__(
        self,
        app: ASGIApp,
        max_body_size: int = 10 * 1024 * 1024,  # 10MB default
        allowed_content_types: List[str] = None,
        enable_sql_injection_detection: bool = False,
        enable_xss_detection: bool = False,
        inject_request_id: bool = True,
    ):
        """Initialize request validation middleware."""
        super().__init__(app)
        self.max_body_size = max_body_size
        self.allowed_content_types = allowed_content_types or [
            "application/json",
            "application/x-www-form-urlencoded",
            "multipart/form-data",
            "text/plain",
            "text/html",
        ]
        self.enable_sql_injection_detection = enable_sql_injection_detection
        self.enable_xss_detection = enable_xss_detection
        self.inject_request_id = inject_request_id

        # SQL injection patterns
        self.sql_patterns = [
            r"(\b(SELECT|INSERT|UPDATE|DELETE|DROP|CREATE|ALTER|EXEC|EXECUTE|UNION|FROM|WHERE)\b)",
            r"(--|\||;|\/\*|\*\/)",
            r"(\bOR\b\s*\d+\s*=\s*\d+)",
            r"(\bAND\b\s*\d+\s*=\s*\d+)",
        ]

        # XSS patterns
        self.xss_patterns = [
            r"<script[^>]*>.*?</script>",
            r"javascript:",
            r"on\w+\s*=",
            r"<iframe[^>]*>",
            r"<embed[^>]*>",
            r"<object[^>]*>",
        ]

    def _check_sql_injection(self, text: str) -> bool:
        """Check for SQL injection patterns."""
        if not text:
            return False

        text_upper = text.upper()
        for pattern in self.sql_patterns:
            if re.search(pattern, text_upper, re.IGNORECASE):
                return True
        return False

    def _check_xss(self, text: str) -> bool:
        """Check for XSS patterns."""
        if not text:
            return False

        for pattern in self.xss_patterns:
            if re.search(pattern, text, re.IGNORECASE):
                return True
        return False

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request through validation."""
        # Inject request ID for tracing
        if self.inject_request_id:
            request_id = str(uuid.uuid4())
            request.state.request_id = request_id

        # Check request body size
        content_length = request.headers.get("Content-Length")
        if content_length and int(content_length) > self.max_body_size:
            response = JSONResponse(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                content={"detail": "Request body too large"},
            )
            if self.inject_request_id:
                response.headers["X-Request-ID"] = request_id
            return response

        # Check content type for POST/PUT requests
        if request.method in ["POST", "PUT"]:
            content_type = request.headers.get("Content-Type", "").split(";")[0]
            if (
                content_type
                and self.allowed_content_types
                and content_type not in self.allowed_content_types
            ):
                response = JSONResponse(
                    status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                    content={"detail": f"Unsupported content type: {content_type}"},
                )
                if self.inject_request_id:
                    response.headers["X-Request-ID"] = request_id
                return response

        # Check for SQL injection in query parameters
        if self.enable_sql_injection_detection and request.url.query:
            if self._check_sql_injection(request.url.query):
                response = JSONResponse(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    content={"detail": "Potentially malicious request detected"},
                )
                if self.inject_request_id:
                    response.headers["X-Request-ID"] = request_id
                return response

        # Check for XSS in query parameters
        if self.enable_xss_detection and request.url.query:
            if self._check_xss(request.url.query):
                response = JSONResponse(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    content={"detail": "Potentially malicious request detected"},
                )
                if self.inject_request_id:
                    response.headers["X-Request-ID"] = request_id
                return response

        # Process request
        response = await call_next(request)

        # Add request ID to response headers
        if self.inject_request_id:
            response.headers["X-Request-ID"] = request_id

        return response