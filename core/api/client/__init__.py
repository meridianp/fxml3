"""FXML4 API Client SDK.

A Python client library for interacting with the FXML4 API.
"""

from .async_client import AsyncFXML4Client
from .client import FXML4Client
from .exceptions import (
    AuthenticationError,
    FXML4Error,
    RateLimitError,
    ServerError,
    ValidationError,
)

# Note: models.py does not exist - removing wildcard import

__version__ = "2.0.0"
__all__ = [
    "FXML4Client",
    "AsyncFXML4Client",
    "FXML4Error",
    "AuthenticationError",
    "RateLimitError",
    "ValidationError",
    "ServerError",
]
