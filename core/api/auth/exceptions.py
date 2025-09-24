"""
Authentication exceptions for FXML4.

Minimal implementation to satisfy TDD tests (GREEN phase).
"""

# Import from models to avoid duplication
from core.api.auth.models import AuthenticationError
from core.api.auth.models import InvalidTokenError as InvalidCredentialsError
from core.api.auth.models import TokenExpiredError


class TwoFactorRequiredError(AuthenticationError):
    """Raised when two-factor authentication is required."""

    def __init__(self, message="Two-factor authentication required", temp_token=None):
        super().__init__(message)
        self.temp_token = temp_token


# Add alias for compatibility
class InvalidCredentialsError(AuthenticationError):
    """Raised when credentials are invalid."""

    pass


class InsufficientPermissionsError(AuthenticationError):
    """Raised when user lacks required permissions."""

    pass


class SessionError(AuthenticationError):
    """Raised when there are session-related errors."""

    pass


class TokenRotationError(AuthenticationError):
    """Raised when token rotation fails."""

    pass


class SecurityAuditError(AuthenticationError):
    """Raised when security audit operations fail."""

    pass
