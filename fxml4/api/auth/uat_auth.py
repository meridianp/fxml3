"""
UAT Authentication Module - Database-free authentication for testing.

This module provides simplified authentication that validates JWT tokens
without requiring database connections, perfect for UAT environments.
"""

import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Annotated, Optional

from fastapi import Depends, Header, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt

logger = logging.getLogger(__name__)

# JWT Configuration for UAT
SECRET_KEY = os.environ.get(
    "FXML4_JWT_SECRET_KEY", "dev-secret-key-not-for-production-32-chars"
)
ALGORITHM = "HS256"

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/token", auto_error=False)


class UATUser:
    """Mock user for UAT testing."""

    def __init__(self, user_id: str, username: str, scopes: list = None):
        self.id = user_id
        self.user_id = user_id
        self.username = username
        self.scopes = scopes or []
        self.is_active = True
        self.email = f"{username}@uat.fxml4.com"
        self.full_name = f"UAT {username.title()}"
        self.last_activity = datetime.now(timezone.utc)


async def get_current_user_uat(
    token: Annotated[str, Depends(oauth2_scheme)]
) -> Optional[UATUser]:
    """Get current user from JWT token without database."""
    if not token:
        return None

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: str = payload.get("sub")
        username: str = payload.get("username") or user_id
        scopes: list = payload.get("scopes", [])

        if user_id is None:
            return None

        return UATUser(user_id=user_id, username=username, scopes=scopes)

    except JWTError as e:
        logger.warning(f"JWT validation failed: {e}")
        return None


async def get_current_active_user_uat(
    current_user: UATUser = Depends(get_current_user_uat),
) -> UATUser:
    """Get current active user, raise exception if not authenticated."""
    if not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Inactive user"
        )

    return current_user


def create_uat_token(username: str, scopes: list = None) -> str:
    """Create a UAT token for testing."""
    scopes = scopes or ["read", "write"]

    payload = {
        "sub": username,
        "username": username,
        "scopes": scopes,
        "exp": datetime.utcnow() + timedelta(hours=24),
        "iat": datetime.utcnow(),
        "type": "access",
    }

    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)
