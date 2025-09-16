"""Exception classes for FXML4 API client."""

from typing import Any, Dict, Optional


class FXML4Error(Exception):
    """Base exception for FXML4 API errors."""

    def __init__(
        self,
        message: str,
        status_code: Optional[int] = None,
        response: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.response = response or {}


class AuthenticationError(FXML4Error):
    """Raised when authentication fails."""

    pass


class RateLimitError(FXML4Error):
    """Raised when rate limit is exceeded."""

    def __init__(self, message: str, retry_after: Optional[int] = None, **kwargs):
        super().__init__(message, **kwargs)
        self.retry_after = retry_after


class ValidationError(FXML4Error):
    """Raised when request validation fails."""

    def __init__(self, message: str, errors: Optional[list] = None, **kwargs):
        super().__init__(message, **kwargs)
        self.errors = errors or []


class ServerError(FXML4Error):
    """Raised when server returns 5xx error."""

    pass


class VersionError(FXML4Error):
    """Raised when API version is not supported."""

    pass
