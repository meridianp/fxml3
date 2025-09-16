"""
Authentication and authorization module for FXML4.

This module provides:
- JWT-based authentication with refresh tokens
- Role-based access control (RBAC)
- Two-factor authentication (2FA)
- Password management and validation
- Session management
- Security audit logging
"""

from .jwt_service import JWTService
from .models import (
    AuthenticationError,
    InsufficientPermissionsError,
    InvalidTokenError,
    KeyRotationError,
    PasswordExpiredError,
    PasswordReuseError,
    PasswordValidationResult,
    Permission,
    TokenExpiredError,
    TokenPair,
    TokenValidationResult,
    User,
    UserLockedError,
    UserRole,
    WeakPasswordError,
)
from .password_service import PasswordService

__all__ = [
    "User",
    "UserRole",
    "Permission",
    "TokenPair",
    "TokenValidationResult",
    "PasswordValidationResult",
    "AuthenticationError",
    "TokenExpiredError",
    "InvalidTokenError",
    "KeyRotationError",
    "UserLockedError",
    "InsufficientPermissionsError",
    "WeakPasswordError",
    "PasswordReuseError",
    "PasswordExpiredError",
    "JWTService",
    "PasswordService",
]
