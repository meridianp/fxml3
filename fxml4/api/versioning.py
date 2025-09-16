"""API versioning support for FXML4.

This module provides version negotiation, deprecation warnings, and routing for different API versions.
"""

import logging
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Tuple

from fastapi import HTTPException, Request, Response, status
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)


class APIVersion(str, Enum):
    """Supported API versions."""

    V1 = "v1"
    V2 = "v2"


class VersionStatus(str, Enum):
    """Version lifecycle status."""

    ACTIVE = "active"
    DEPRECATED = "deprecated"
    SUNSET = "sunset"
    RETIRED = "retired"


# Version configuration
VERSION_CONFIG = {
    APIVersion.V1: {
        "status": VersionStatus.DEPRECATED,
        "deprecated_date": "2024-01-01",
        "sunset_date": "2024-07-01",
        "retirement_date": "2025-01-01",
        "successor": APIVersion.V2,
        "changes": [
            "Improved rate limiting",
            "Enhanced error responses",
            "New authentication scopes",
            "Standardized pagination",
        ],
    },
    APIVersion.V2: {
        "status": VersionStatus.ACTIVE,
        "release_date": "2024-01-01",
        "changes": [
            "WebSocket support for real-time data",
            "GraphQL endpoint",
            "Improved performance metrics",
            "Advanced filtering options",
        ],
    },
}

# Default version
DEFAULT_VERSION = APIVersion.V2
SUPPORTED_VERSIONS = [APIVersion.V1, APIVersion.V2]


def get_version_from_request(request: Request) -> APIVersion:
    """Extract API version from request.

    Version can be specified via:
    1. URL path (e.g., /api/v1/data)
    2. Accept header (e.g., Accept: application/vnd.fxml4.v1+json)
    3. Query parameter (e.g., ?version=v1)

    Args:
        request: FastAPI request object

    Returns:
        API version
    """
    # Check URL path
    path_parts = request.url.path.split("/")
    for part in path_parts:
        if part in [v.value for v in APIVersion]:
            return APIVersion(part)

    # Check Accept header
    accept_header = request.headers.get("accept", "")
    for version in APIVersion:
        if f"vnd.fxml4.{version.value}" in accept_header:
            return version

    # Check query parameter
    version_param = request.query_params.get("version")
    if version_param and version_param in [v.value for v in APIVersion]:
        return APIVersion(version_param)

    # Return default version
    return DEFAULT_VERSION


def validate_version(version: APIVersion) -> Tuple[bool, Optional[str]]:
    """Validate if a version is acceptable.

    Args:
        version: API version to validate

    Returns:
        Tuple of (is_valid, error_message)
    """
    if version not in SUPPORTED_VERSIONS:
        return False, f"Version {version.value} is not supported"

    version_info = VERSION_CONFIG.get(version, {})
    status = version_info.get("status", VersionStatus.ACTIVE)

    if status == VersionStatus.RETIRED:
        retirement_date = version_info.get("retirement_date", "unknown")
        return False, f"Version {version.value} was retired on {retirement_date}"

    if status == VersionStatus.SUNSET:
        sunset_date = version_info.get("sunset_date", "unknown")
        if datetime.now().date() > datetime.fromisoformat(sunset_date).date():
            return False, f"Version {version.value} reached sunset on {sunset_date}"

    return True, None


def add_version_headers(response: Response, version: APIVersion) -> None:
    """Add version-related headers to response.

    Args:
        response: FastAPI response object
        version: API version being used
    """
    # Add current version header
    response.headers["X-API-Version"] = version.value

    # Add supported versions header
    response.headers["X-API-Versions"] = ", ".join(
        [v.value for v in SUPPORTED_VERSIONS]
    )

    # Add deprecation headers if applicable
    version_info = VERSION_CONFIG.get(version, {})
    status = version_info.get("status", VersionStatus.ACTIVE)

    if status == VersionStatus.DEPRECATED:
        response.headers["X-API-Deprecated"] = "true"

        if "sunset_date" in version_info:
            response.headers["X-API-Sunset-Date"] = version_info["sunset_date"]

        if "successor" in version_info:
            response.headers["X-API-Successor-Version"] = version_info[
                "successor"
            ].value

        # Add deprecation warning
        deprecation_msg = f"API version {version.value} is deprecated"
        if "sunset_date" in version_info:
            deprecation_msg += f" and will be sunset on {version_info['sunset_date']}"
        if "successor" in version_info:
            deprecation_msg += f". Please migrate to {version_info['successor'].value}"

        response.headers["X-API-Warning"] = deprecation_msg


async def version_middleware(request: Request, call_next):
    """Middleware to handle API versioning.

    Args:
        request: FastAPI request object
        call_next: Next middleware or handler

    Returns:
        Response with version headers
    """
    # Skip versioning for non-API paths
    if not request.url.path.startswith("/api/") and request.url.path not in [
        "/data",
        "/signals",
        "/backtest",
    ]:
        return await call_next(request)

    # Get requested version
    version = get_version_from_request(request)

    # Validate version
    is_valid, error_msg = validate_version(version)
    if not is_valid:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "error": "Invalid API version",
                "message": error_msg,
                "supported_versions": [v.value for v in SUPPORTED_VERSIONS],
                "default_version": DEFAULT_VERSION.value,
            },
        )

    # Store version in request state for use in handlers
    request.state.api_version = version

    # Process request
    response = await call_next(request)

    # Add version headers to response
    add_version_headers(response, version)

    return response


def get_version_info() -> Dict:
    """Get information about all API versions.

    Returns:
        Dictionary with version information
    """
    versions = {}

    for version in APIVersion:
        info = VERSION_CONFIG.get(version, {})
        versions[version.value] = {
            "status": info.get("status", VersionStatus.ACTIVE).value,
            "release_date": info.get("release_date"),
            "deprecated_date": info.get("deprecated_date"),
            "sunset_date": info.get("sunset_date"),
            "retirement_date": info.get("retirement_date"),
            "successor": (
                info.get("successor", {}).value if "successor" in info else None
            ),
            "changes": info.get("changes", []),
        }

    return {
        "current_version": DEFAULT_VERSION.value,
        "supported_versions": [v.value for v in SUPPORTED_VERSIONS],
        "versions": versions,
    }


def create_version_router():
    """Create a router for version-related endpoints.

    Returns:
        FastAPI router
    """
    from fastapi import APIRouter

    router = APIRouter(prefix="/api", tags=["versioning"])

    @router.get("/versions")
    async def get_versions():
        """Get API version information."""
        return get_version_info()

    @router.get("/version")
    async def get_current_version(request: Request):
        """Get current API version being used."""
        version = get_version_from_request(request)
        return {
            "version": version.value,
            "status": VERSION_CONFIG.get(version, {})
            .get("status", VersionStatus.ACTIVE)
            .value,
        }

    return router
