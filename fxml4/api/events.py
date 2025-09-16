"""
Application lifecycle events for FXML4 API.

This module handles startup and shutdown events for the FastAPI application.
"""

import logging

from fastapi import FastAPI

from fxml4.api.dependencies import cleanup_dependencies, init_dependencies

logger = logging.getLogger(__name__)


def setup_events(app: FastAPI) -> None:
    """Setup application lifecycle events.

    Args:
        app: FastAPI application instance
    """

    @app.on_event("startup")
    async def startup_event():
        """Initialize dependencies on startup."""
        logger.info("Starting FXML4 API application...")
        init_dependencies()

    @app.on_event("shutdown")
    async def shutdown_event():
        """Cleanup dependencies on shutdown."""
        logger.info("Shutting down FXML4 API application...")
        cleanup_dependencies()
