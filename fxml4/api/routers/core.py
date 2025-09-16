"""
Core routes for FXML4 API.

This module provides basic API routes including health checks, dashboard,
and root endpoints.
"""

import os

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

# Create router
router = APIRouter()


@router.get("/", tags=["core"])
async def root():
    """Root endpoint."""
    return {"message": "FXML4 API running"}


@router.get("/health", tags=["core"])
async def health_check():
    """Health check endpoint."""
    from datetime import datetime

    return {
        "status": "healthy",  # Changed from "ok" to match frontend expectation
        "version": "2.0.0",
        "timestamp": datetime.utcnow().isoformat(),
        "services": {
            "api": "healthy",
            "database": "unknown",  # Will be updated when DB health checks are implemented
            "redis": "unknown",
        },
    }


@router.get("/dashboard", tags=["core"])
async def monitoring_dashboard():
    """Serve the monitoring dashboard."""
    static_dir = os.path.join(os.path.dirname(__file__), "..", "static")
    dashboard_path = os.path.join(static_dir, "monitoring_dashboard.html")
    if os.path.exists(dashboard_path):
        return FileResponse(dashboard_path, media_type="text/html")
    else:
        raise HTTPException(status_code=404, detail="Dashboard not found")


@router.get("/manual", tags=["core"])
async def manual_execution():
    """Serve the manual execution interface."""
    static_dir = os.path.join(os.path.dirname(__file__), "..", "static")
    manual_path = os.path.join(static_dir, "manual_execution.html")
    if os.path.exists(manual_path):
        return FileResponse(manual_path, media_type="text/html")
    else:
        raise HTTPException(
            status_code=404, detail="Manual execution interface not found"
        )
