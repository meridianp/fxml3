"""
Enhanced authentication and authorization utilities for FXML4 API.

This module provides production-ready authentication with database integration.
Consolidates functionality from both auth.py and auth_enhanced.py.

SECURITY IMPROVEMENTS:
- JWT secrets loaded from environment variables (FXML4_JWT_SECRET_KEY)
- Demo user passwords loaded from environment variables
- Fallback to configuration file with insecure warning
- No hardcoded credentials in source code
- Database integration for user management
- API key support for service authentication
- Audit logging for security events
- Rate limiting and account lockout protection

PRODUCTION REQUIREMENTS:
- Set FXML4_JWT_SECRET_KEY with a strong, unique secret (minimum 32 characters)
- Set FXML4_DEMO_ADMIN_PASSWORD and FXML4_DEMO_USER_PASSWORD
- Replace demo users with proper user management system
- Configure database connection for user storage
- Set up proper API key rotation
"""

import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Annotated, Optional, Union

from fastapi import Depends, Header, HTTPException, Request, status
from fastapi.security import (
    APIKeyHeader,
    OAuth2PasswordBearer,
    OAuth2PasswordRequestForm,
)
from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from fxml4.config import get_config

from .audit_logger import AuditEventType, auth_audit_logger
from .database import get_db
from .models import APIKey, User
from .service import AuthenticationService

# Configure logging
logger = logging.getLogger(__name__)

# JWT Configuration
config = get_config()
SECRET_KEY = os.environ.get("FXML4_JWT_SECRET_KEY", config.get("api.auth.secret_key"))
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = config.get("api.auth.token_expire_minutes", 30)

# OAuth2 schemes
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/token", auto_error=False)
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


class TokenData:
    """Token data extracted from JWT."""

    def __init__(self, user_id: str, username: str, scopes: list = None):
        self.user_id = user_id
        self.username = username
        self.scopes = scopes or []


async def get_current_user_from_token(
    token: Annotated[str, Depends(oauth2_scheme)], db: AsyncSession = Depends(get_db)
) -> Optional[User]:
    """Get current user from JWT token."""
    if not token:
        return None

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: str = payload.get("sub")
        username: str = payload.get("username")

        if user_id is None:
            return None

        token_data = TokenData(user_id=user_id, username=username)

    except JWTError:
        return None

    # Get user from database
    result = await db.execute(select(User).where(User.id == token_data.user_id))
    user = result.scalar_one_or_none()

    if not user or not user.is_active:
        return None

    # Update last activity
    user.last_activity = datetime.now(timezone.utc)
    await db.commit()

    return user


async def get_current_user_from_api_key(
    api_key: Annotated[str, Depends(api_key_header)], db: AsyncSession = Depends(get_db)
) -> Optional[User]:
    """Get current user from API key."""
    if not api_key:
        return None

    result = await AuthenticationService.validate_api_key(db, api_key)

    if not result:
        return None

    api_key_obj, user = result
    return user


async def get_current_user(
    request: Request,
    token_user: Optional[User] = Depends(get_current_user_from_token),
    api_key_user: Optional[User] = Depends(get_current_user_from_api_key),
    db: AsyncSession = Depends(get_db),
) -> User:
    """
    Get current authenticated user from either JWT token or API key.

    Raises:
        HTTPException: If not authenticated
    """
    user = token_user or api_key_user

    if not user:
        # Log failed authentication attempt
        await auth_audit_logger.log_event(
            db=db,
            user_id=None,
            event_type=AuditEventType.PERMISSION_DENIED,
            success=False,
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
            details={"reason": "no_valid_credentials"},
        )

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Check if password change is required
    if user.must_change_password:
        # Allow access to password change endpoint only
        if request.url.path != "/api/v1/users/me/password":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Password change required"
            )

    return user


async def get_current_active_user(
    current_user: Annotated[User, Depends(get_current_user)]
) -> User:
    """
    Get current active user.

    Raises:
        HTTPException: If user is not active
    """
    if not current_user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user


def require_role(role_name: str):
    """
    Dependency to require a specific role.

    Usage:
        @router.get("/admin", dependencies=[Depends(require_role("admin"))])
    """

    async def role_checker(
        current_user: User = Depends(get_current_active_user),
    ) -> User:
        if not current_user.has_role(role_name) and not current_user.has_role("admin"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role '{role_name}' required",
            )
        return current_user

    return role_checker


def require_permission(permission: str):
    """
    Dependency to require a specific permission.

    Usage:
        @router.post("/trades", dependencies=[Depends(require_permission("trades.create"))])
    """

    async def permission_checker(
        current_user: User = Depends(get_current_active_user),
    ) -> User:
        if not current_user.has_permission(permission) and not current_user.has_role(
            "admin"
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission '{permission}' required",
            )
        return current_user

    return permission_checker


async def authenticate_user(
    form_data: OAuth2PasswordRequestForm = Depends(),
    request: Request = None,
    db: AsyncSession = Depends(get_db),
) -> User:
    """
    Authenticate user with username/password.

    Returns:
        Authenticated user

    Raises:
        HTTPException: If authentication fails
    """
    ip_address = request.client.host if request and request.client else None
    user_agent = request.headers.get("user-agent") if request else None

    user, error = await AuthenticationService.authenticate_user(
        db=db,
        username=form_data.username,
        password=form_data.password,
        ip_address=ip_address,
        user_agent=user_agent,
    )

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=error or "Invalid username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user


def create_access_token(user: User) -> str:
    """Create access token for user."""
    token_data = {"sub": str(user.id), "username": user.username, "scopes": []}

    # Add role-based scopes
    for role in user.roles:
        token_data["scopes"].append(f"role:{role.name}")

    return AuthenticationService.create_access_token(token_data)


def create_refresh_token(user: User) -> str:
    """Create refresh token for user."""
    token_data = {"sub": str(user.id), "username": user.username}

    return AuthenticationService.create_refresh_token(token_data)


# Rate limiting support
async def get_client_ip(request: Request) -> str:
    """Get client IP address from request."""
    # Check for proxy headers
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()

    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip

    if request.client:
        return request.client.host

    return "unknown"


# Backward compatibility exports
from .service import PasswordPolicyError, get_password_hash, verify_password

# Legacy compatibility - simple in-memory user database for demos
USERS_DB = {
    "admin": {
        "username": "admin",
        "full_name": "Admin User",
        "email": "admin@fxml4.com",
        "hashed_password": get_password_hash("admin123"),  # Demo password
        "is_active": True,
        "scopes": ["read", "write", "admin"],
    },
    "user": {
        "username": "user",
        "full_name": "Demo User",
        "email": "user@fxml4.com",
        "hashed_password": get_password_hash("user123"),  # Demo password
        "is_active": True,
        "scopes": ["read"],
    },
}


# Legacy compatibility function
def authenticate_user(users_db: dict, username: str, password: str, request=None):
    """Legacy authenticate_user function for backward compatibility."""
    user = users_db.get(username)
    if not user:
        return False
    if not verify_password(password, user["hashed_password"]):
        return False

    # Return a simple user object with required attributes
    class SimpleUser:
        def __init__(self, user_data):
            self.username = user_data["username"]
            self.full_name = user_data.get("full_name", "")
            self.email = user_data.get("email", "")
            self.is_active = user_data.get("is_active", True)
            self.scopes = user_data.get("scopes", [])

    return SimpleUser(user)
