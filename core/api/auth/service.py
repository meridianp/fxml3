"""
Authentication service for production-ready user management.

This module provides the core authentication logic including:
- User registration and management
- Password policies
- Two-factor authentication
- Session management
- API key generation
"""

import json
import os
import re
import secrets
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Tuple

import pyotp
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from fxml4.config import get_config

from .database import get_db
from .models import APIKey, AuthAuditLog, Role, User

# Configuration
config = get_config()
SECRET_KEY = os.environ.get("FXML4_JWT_SECRET_KEY", config.get("api.auth.secret_key"))
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = config.get("api.auth.token_expire_minutes", 30)
REFRESH_TOKEN_EXPIRE_DAYS = 7

# Password configuration
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
PASSWORD_MIN_LENGTH = 12
PASSWORD_REQUIRE_UPPERCASE = True
PASSWORD_REQUIRE_LOWERCASE = True
PASSWORD_REQUIRE_DIGIT = True
PASSWORD_REQUIRE_SPECIAL = True
PASSWORD_HISTORY_COUNT = 5
PASSWORD_EXPIRY_DAYS = 90
MAX_LOGIN_ATTEMPTS = 5
LOCKOUT_DURATION_MINUTES = 30

# Session configuration
SESSION_TIMEOUT_MINUTES = 30
SESSION_ABSOLUTE_TIMEOUT_HOURS = 12


class PasswordPolicyError(Exception):
    """Raised when password doesn't meet policy requirements."""

    pass


class AuthenticationService:
    """Service for handling authentication operations."""

    @staticmethod
    def verify_password(plain_password: str, hashed_password: str) -> bool:
        """Verify a password against its hash."""
        return pwd_context.verify(plain_password, hashed_password)

    @staticmethod
    def get_password_hash(password: str) -> str:
        """Hash a password."""
        return pwd_context.hash(password)

    @staticmethod
    def validate_password_policy(password: str, username: str = None) -> None:
        """
        Validate password against security policy.

        Raises:
            PasswordPolicyError: If password doesn't meet requirements
        """
        errors = []

        if len(password) < PASSWORD_MIN_LENGTH:
            errors.append(
                f"Password must be at least {PASSWORD_MIN_LENGTH} characters long"
            )

        if PASSWORD_REQUIRE_UPPERCASE and not re.search(r"[A-Z]", password):
            errors.append("Password must contain at least one uppercase letter")

        if PASSWORD_REQUIRE_LOWERCASE and not re.search(r"[a-z]", password):
            errors.append("Password must contain at least one lowercase letter")

        if PASSWORD_REQUIRE_DIGIT and not re.search(r"\d", password):
            errors.append("Password must contain at least one digit")

        if PASSWORD_REQUIRE_SPECIAL and not re.search(
            r"[!@#$%^&*(),.?\":{}|<>]", password
        ):
            errors.append("Password must contain at least one special character")

        # Check if password contains username
        if username and username.lower() in password.lower():
            errors.append("Password cannot contain username")

        # Check common passwords
        common_passwords = ["password", "12345678", "qwerty", "abc123", "password123"]
        if password.lower() in common_passwords:
            errors.append("Password is too common")

        if errors:
            raise PasswordPolicyError("; ".join(errors))

    @staticmethod
    async def create_user(
        db: AsyncSession,
        username: str,
        email: str,
        password: str,
        full_name: str = None,
        role_names: List[str] = None,
    ) -> User:
        """
        Create a new user.

        Args:
            db: Database session
            username: Username
            email: Email address
            password: Plain text password
            full_name: Full name
            role_names: List of role names to assign

        Returns:
            Created user

        Raises:
            ValueError: If user already exists
            PasswordPolicyError: If password doesn't meet policy
        """
        # Check if user exists
        result = await db.execute(
            select(User).where(or_(User.username == username, User.email == email))
        )
        if result.scalar_one_or_none():
            raise ValueError("User with this username or email already exists")

        # Validate password
        AuthenticationService.validate_password_policy(password, username)

        # Create user
        user = User(
            username=username,
            email=email,
            full_name=full_name,
            hashed_password=AuthenticationService.get_password_hash(password),
            password_changed_at=datetime.now(timezone.utc),
        )

        # Assign roles
        if role_names:
            result = await db.execute(select(Role).where(Role.name.in_(role_names)))
            roles = result.scalars().all()
            user.roles = roles

        db.add(user)
        await db.commit()
        await db.refresh(user)

        return user

    @staticmethod
    async def authenticate_user(
        db: AsyncSession,
        username: str,
        password: str,
        ip_address: str = None,
        user_agent: str = None,
    ) -> Tuple[Optional[User], Optional[str]]:
        """
        Authenticate a user.

        Args:
            db: Database session
            username: Username or email
            password: Plain text password
            ip_address: Client IP address
            user_agent: Client user agent

        Returns:
            Tuple of (User, error_message)
        """
        # Find user by username or email
        result = await db.execute(
            select(User).where(or_(User.username == username, User.email == email))
        )
        user = result.scalar_one_or_none()

        if not user:
            # Log failed attempt
            await AuthenticationService._log_auth_event(
                db,
                None,
                "login_failed",
                False,
                {"reason": "user_not_found", "username": username},
                ip_address,
                user_agent,
            )
            return None, "Invalid username or password"

        # Check if account is locked
        if user.is_locked:
            # Check if lockout period has expired
            if user.last_failed_login:
                lockout_end = user.last_failed_login + timedelta(
                    minutes=LOCKOUT_DURATION_MINUTES
                )
                if datetime.now(timezone.utc) < lockout_end:
                    await AuthenticationService._log_auth_event(
                        db,
                        user.id,
                        "login_failed",
                        False,
                        {"reason": "account_locked"},
                        ip_address,
                        user_agent,
                    )
                    return None, "Account is locked due to too many failed attempts"
                else:
                    # Unlock account
                    user.is_locked = False
                    user.failed_login_attempts = 0

        # Check if account is active
        if not user.is_active:
            await AuthenticationService._log_auth_event(
                db,
                user.id,
                "login_failed",
                False,
                {"reason": "account_inactive"},
                ip_address,
                user_agent,
            )
            return None, "Account is inactive"

        # Verify password
        if not AuthenticationService.verify_password(password, user.hashed_password):
            # Increment failed attempts
            user.failed_login_attempts += 1
            user.last_failed_login = datetime.now(timezone.utc)

            # Lock account if too many attempts
            if user.failed_login_attempts >= MAX_LOGIN_ATTEMPTS:
                user.is_locked = True

            await AuthenticationService._log_auth_event(
                db,
                user.id,
                "login_failed",
                False,
                {"reason": "invalid_password", "attempts": user.failed_login_attempts},
                ip_address,
                user_agent,
            )

            await db.commit()
            return None, "Invalid username or password"

        # Check if password has expired
        if user.password_changed_at:
            expiry_date = user.password_changed_at + timedelta(
                days=PASSWORD_EXPIRY_DAYS
            )
            if datetime.now(timezone.utc) > expiry_date:
                user.must_change_password = True

        # Successful login
        user.failed_login_attempts = 0
        user.last_login = datetime.now(timezone.utc)
        user.last_activity = datetime.now(timezone.utc)

        await AuthenticationService._log_auth_event(
            db,
            user.id,
            "login_success",
            True,
            {"2fa_required": user.totp_enabled},
            ip_address,
            user_agent,
        )

        await db.commit()
        return user, None

    @staticmethod
    async def setup_2fa(db: AsyncSession, user_id: str) -> str:
        """
        Set up two-factor authentication for user.

        Returns:
            TOTP provisioning URI
        """
        # Get user
        result = await db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()

        if not user:
            raise ValueError("User not found")

        # Generate TOTP secret
        secret = pyotp.random_base32()
        user.totp_secret = secret

        # Generate backup codes
        backup_codes = [secrets.token_hex(4) for _ in range(10)]
        user.backup_codes = json.dumps(
            [AuthenticationService.get_password_hash(code) for code in backup_codes]
        )

        await db.commit()

        # Return provisioning URI and backup codes
        totp = pyotp.TOTP(secret)
        provisioning_uri = totp.provisioning_uri(
            name=user.email, issuer_name="FXML4 Trading System"
        )

        return provisioning_uri, backup_codes

    @staticmethod
    async def verify_2fa(db: AsyncSession, user_id: str, token: str) -> bool:
        """Verify 2FA token."""
        try:
            result = await db.execute(select(User).where(User.id == user_id))
            user = result.scalar_one_or_none()

            if not user or not user.totp_secret:
                return False

            totp = pyotp.TOTP(user.totp_secret)

            # Check TOTP token
            if totp.verify(token, valid_window=1):
                user.totp_enabled = True
                await db.commit()
                return True

            # Check backup codes
            if user.backup_codes:
                backup_codes = json.loads(user.backup_codes)
                for i, hashed_code in enumerate(backup_codes):
                    if AuthenticationService.verify_password(token, hashed_code):
                        # Remove used backup code
                        backup_codes.pop(i)
                        user.backup_codes = json.dumps(backup_codes)
                        await db.commit()
                        return True

            return False
        except Exception:
            # Log error and return False for security
            return False

    @staticmethod
    def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
        """Create JWT access token."""
        to_encode = data.copy()

        if expires_delta:
            expire = datetime.now(timezone.utc) + expires_delta
        else:
            expire = datetime.now(timezone.utc) + timedelta(
                minutes=ACCESS_TOKEN_EXPIRE_MINUTES
            )

        to_encode.update(
            {"exp": expire, "iat": datetime.now(timezone.utc), "type": "access"}
        )

        return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

    @staticmethod
    def create_refresh_token(data: dict):
        """Create JWT refresh token."""
        to_encode = data.copy()
        expire = datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)

        to_encode.update(
            {"exp": expire, "iat": datetime.now(timezone.utc), "type": "refresh"}
        )

        return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

    @staticmethod
    async def create_api_key(
        db: AsyncSession,
        user_id: str,
        name: str,
        description: str = None,
        permissions: List[str] = None,
        expires_in_days: int = None,
    ) -> Tuple[str, APIKey]:
        """
        Create API key for user.

        Returns:
            Tuple of (raw_key, api_key_model)
        """
        # Generate secure API key
        raw_key = f"fxml4_{secrets.token_urlsafe(32)}"
        key_hash = AuthenticationService.get_password_hash(raw_key)

        # Calculate expiry
        expires_at = None
        if expires_in_days:
            expires_at = datetime.now(timezone.utc) + timedelta(days=expires_in_days)

        # Create API key
        api_key = APIKey(
            user_id=user_id,
            key_hash=key_hash,
            name=name,
            description=description,
            permissions=json.dumps(permissions or []),
            expires_at=expires_at,
        )

        db.add(api_key)
        await db.commit()
        await db.refresh(api_key)

        return raw_key, api_key

    @staticmethod
    async def validate_api_key(
        db: AsyncSession, raw_key: str
    ) -> Optional[Tuple[APIKey, User]]:
        """Validate API key and return associated user."""
        # Find all active API keys (we need to check each hash)
        result = await db.execute(
            select(APIKey).where(
                and_(
                    APIKey.is_active == True,
                    or_(
                        APIKey.expires_at == None,
                        APIKey.expires_at > datetime.now(timezone.utc),
                    ),
                )
            )
        )
        api_keys = result.scalars().all()

        # Check each API key
        for api_key in api_keys:
            if AuthenticationService.verify_password(raw_key, api_key.key_hash):
                # Update last used
                api_key.last_used_at = datetime.now(timezone.utc)

                # Get user
                result = await db.execute(
                    select(User).where(User.id == api_key.user_id)
                )
                user = result.scalar_one_or_none()

                if user and user.is_active:
                    await db.commit()
                    return api_key, user

        return None

    @staticmethod
    async def _log_auth_event(
        db: AsyncSession,
        user_id: Optional[str],
        event_type: str,
        success: bool,
        event_data: Dict = None,
        ip_address: str = None,
        user_agent: str = None,
    ):
        """Log authentication event."""
        log = AuthAuditLog(
            user_id=user_id,
            event_type=event_type,
            success=success,
            event_data=json.dumps(event_data or {}),
            ip_address=ip_address,
            user_agent=user_agent,
        )
        db.add(log)
        # Note: Caller is responsible for committing


# Convenience functions for backward compatibility
def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash."""
    return AuthenticationService.verify_password(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """Hash a password."""
    return AuthenticationService.get_password_hash(password)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    """Create JWT access token."""
    return AuthenticationService.create_access_token(data, expires_delta)
