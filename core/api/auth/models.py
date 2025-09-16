"""
Authentication models for FXML4.

Defines data models for users, roles, permissions, and authentication-related entities.
"""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import List, Optional


class UserRole(Enum):
    """User roles for role-based access control."""

    ADMIN = "admin"
    TRADER = "trader"
    COMPLIANCE = "compliance"
    VIEWER = "viewer"
    API_USER = "api_user"


class Permission(Enum):
    """System permissions."""

    # Trading permissions
    TRADE_EXECUTE = "trade:execute"
    TRADE_VIEW = "trade:view"
    TRADE_CANCEL = "trade:cancel"

    # Account permissions
    ACCOUNT_VIEW = "account:view"
    ACCOUNT_MANAGE = "account:manage"

    # User management permissions
    USER_CREATE = "user:create"
    USER_VIEW = "user:view"
    USER_UPDATE = "user:update"
    USER_DELETE = "user:delete"

    # Compliance permissions
    AUDIT_VIEW = "audit:view"
    COMPLIANCE_REPORT = "compliance:report"
    RISK_MONITOR = "risk:monitor"

    # System permissions
    SYSTEM_CONFIG = "system:config"
    SYSTEM_MONITOR = "system:monitor"


@dataclass
class User:
    """User model for authentication."""

    user_id: str
    username: str
    email: str
    role: UserRole
    is_active: bool = True
    is_verified: bool = False
    permissions: Optional[List[Permission]] = None
    created_at: Optional[datetime] = None
    last_login: Optional[datetime] = None
    failed_login_attempts: int = 0
    locked_until: Optional[datetime] = None

    def has_permission(self, permission: Permission) -> bool:
        """Check if user has specific permission."""
        if self.permissions:
            return permission in self.permissions

        # Default permissions by role
        role_permissions = {
            UserRole.ADMIN: list(Permission),
            UserRole.TRADER: [
                Permission.TRADE_EXECUTE,
                Permission.TRADE_VIEW,
                Permission.TRADE_CANCEL,
                Permission.ACCOUNT_VIEW,
            ],
            UserRole.COMPLIANCE: [
                Permission.TRADE_VIEW,
                Permission.AUDIT_VIEW,
                Permission.COMPLIANCE_REPORT,
                Permission.RISK_MONITOR,
            ],
            UserRole.VIEWER: [
                Permission.TRADE_VIEW,
                Permission.ACCOUNT_VIEW,
            ],
            UserRole.API_USER: [
                Permission.TRADE_EXECUTE,
                Permission.TRADE_VIEW,
                Permission.ACCOUNT_VIEW,
            ],
        }

        return permission in role_permissions.get(self.role, [])

    def is_locked(self) -> bool:
        """Check if user account is locked."""
        if self.locked_until:
            return datetime.utcnow() < self.locked_until
        return False


@dataclass
class TokenPair:
    """Access and refresh token pair."""

    access_token: str
    refresh_token: str
    token_type: str = "Bearer"
    expires_in: int = 900  # 15 minutes in seconds

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON response."""
        return {
            "access_token": self.access_token,
            "refresh_token": self.refresh_token,
            "token_type": self.token_type,
            "expires_in": self.expires_in,
        }


@dataclass
class TokenValidationResult:
    """Result of token validation."""

    is_valid: bool
    user_id: Optional[str] = None
    username: Optional[str] = None
    role: Optional[str] = None
    permissions: Optional[List[str]] = None
    error: Optional[Exception] = None
    expires_at: Optional[datetime] = None


@dataclass
class PasswordValidationResult:
    """Result of password validation."""

    is_valid: bool
    errors: List[str] = None
    strength_score: int = 0

    def __post_init__(self):
        if self.errors is None:
            self.errors = []


# Custom exceptions
class AuthenticationError(Exception):
    """Base authentication error."""

    pass


class TokenExpiredError(AuthenticationError):
    """Token has expired."""

    pass


class InvalidTokenError(AuthenticationError):
    """Token is invalid or malformed."""

    pass


class KeyRotationError(Exception):
    """Error during key rotation."""

    pass


class UserLockedError(AuthenticationError):
    """User account is locked."""

    pass


class InsufficientPermissionsError(AuthenticationError):
    """User lacks required permissions."""

    pass


class WeakPasswordError(AuthenticationError):
    """Password does not meet complexity requirements."""

    pass


class PasswordReuseError(AuthenticationError):
    """Password was used recently and cannot be reused."""

    pass


class PasswordExpiredError(AuthenticationError):
    """Password has expired and must be changed."""

    pass
