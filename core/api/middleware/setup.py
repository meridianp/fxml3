"""
Middleware setup for FXML4 API.

This module configures all middleware for the FastAPI application.
"""

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from fxml4.config import get_config

from .rate_limiter import add_rate_limiter
from .security_headers import add_security_middleware

logger = logging.getLogger(__name__)


def setup_middleware(app: FastAPI) -> None:
    """Setup all middleware for the FastAPI application.

    Args:
        app: FastAPI application instance
    """
    # Configure CORS
    cors_origins = get_config().get(
        "api.cors_origins", ["http://localhost:3000", "http://localhost:8501"]
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["Content-Type", "Authorization", "Accept", "X-Requested-With"],
    )

    # Add rate limiting middleware
    add_rate_limiter(app)

    # Add security headers and other security middleware
    security_config = get_config().get("api.security", {})
    add_security_middleware(app, security_config)

    # Add versioning middleware
    from fxml4.api.versioning import version_middleware

    app.middleware("http")(version_middleware)

    logger.info("Middleware setup completed")
