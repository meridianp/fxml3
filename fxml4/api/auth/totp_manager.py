"""
Two-Factor Authentication (2FA) Manager for FXML4.

This module provides comprehensive 2FA management including:
- TOTP setup and verification
- QR code generation
- Backup code management
- Session management for 2FA flows
- Redis-based session storage for production
"""

import base64
import json
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
from io import BytesIO
from typing import Any, Dict, List, Optional, Tuple

import pyotp
import qrcode
import qrcode.image.svg
import redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from fxml4.api.auth.audit_logger import AuditEventType, auth_audit_logger
from fxml4.api.auth.models import User
from fxml4.api.auth.service import AuthenticationService
from fxml4.config import get_config


class TwoFactorMethod(Enum):
    """2FA methods supported."""

    TOTP = "totp"
    BACKUP_CODE = "backup_code"


@dataclass
class TwoFactorSetupResult:
    """Result of 2FA setup operation."""

    secret: str
    qr_code_svg: str
    qr_code_data_url: str
    backup_codes: List[str]
    provisioning_uri: str


@dataclass
class TwoFactorStatus:
    """2FA status for user."""

    enabled: bool
    setup_complete: bool
    backup_codes_remaining: int
    last_used: Optional[datetime]
    method_used: Optional[TwoFactorMethod]


class TwoFactorSession:
    """Manages 2FA session state."""

    def __init__(
        self,
        user_id: str,
        session_token: str,
        expires_at: datetime,
        client_ip: str = None,
        user_agent: str = None,
    ):
        self.user_id = user_id
        self.session_token = session_token
        self.expires_at = expires_at
        self.client_ip = client_ip
        self.user_agent = user_agent
        self.created_at = datetime.now(timezone.utc)
        self.attempts = 0
        self.max_attempts = 3

    def to_dict(self) -> Dict[str, Any]:
        """Convert session to dictionary."""
        return {
            "user_id": self.user_id,
            "session_token": self.session_token,
            "expires_at": self.expires_at.isoformat(),
            "client_ip": self.client_ip,
            "user_agent": self.user_agent,
            "created_at": self.created_at.isoformat(),
            "attempts": self.attempts,
            "max_attempts": self.max_attempts,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TwoFactorSession":
        """Create session from dictionary."""
        session = cls(
            user_id=data["user_id"],
            session_token=data["session_token"],
            expires_at=datetime.fromisoformat(data["expires_at"]),
            client_ip=data.get("client_ip"),
            user_agent=data.get("user_agent"),
        )
        session.created_at = datetime.fromisoformat(data["created_at"])
        session.attempts = data.get("attempts", 0)
        session.max_attempts = data.get("max_attempts", 3)
        return session


class TwoFactorManager:
    """Manages Two-Factor Authentication operations."""

    def __init__(self):
        """Initialize 2FA manager."""
        self.config = get_config()
        self.session_timeout_minutes = self.config.get(
            "api.auth.2fa.session_timeout", 5
        )
        self.max_attempts = self.config.get("api.auth.2fa.max_attempts", 3)
        self.backup_codes_count = self.config.get("api.auth.2fa.backup_codes_count", 10)

        # Initialize Redis for production session storage
        self.redis_client = None
        try:
            redis_url = self.config.get("redis.url", "redis://localhost:6379/0")
            self.redis_client = redis.from_url(redis_url, decode_responses=True)
            self.use_redis = True
        except Exception:
            # Fallback to in-memory storage for development
            self.sessions = {}
            self.use_redis = False

    async def setup_totp(self, db: AsyncSession, user_id: str) -> TwoFactorSetupResult:
        """
        Set up TOTP 2FA for user.

        Args:
            db: Database session
            user_id: User ID

        Returns:
            2FA setup result with QR code and backup codes

        Raises:
            ValueError: If user not found or 2FA already enabled
        """
        # Get user
        result = await db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()

        if not user:
            raise ValueError("User not found")

        if user.totp_enabled:
            raise ValueError("2FA is already enabled for this user")

        # Generate TOTP secret
        secret = pyotp.random_base32()
        user.totp_secret = secret

        # Generate backup codes
        backup_codes = [
            secrets.token_hex(4).upper() for _ in range(self.backup_codes_count)
        ]
        user.backup_codes = json.dumps(
            [AuthenticationService.get_password_hash(code) for code in backup_codes]
        )

        # Create provisioning URI
        totp = pyotp.TOTP(secret)
        provisioning_uri = totp.provisioning_uri(
            name=user.email, issuer_name="FXML4 Trading System"
        )

        # Generate QR code as SVG
        qr = qrcode.QRCode(version=1, box_size=10, border=5)
        qr.add_data(provisioning_uri)
        qr.make(fit=True)

        # Create SVG image
        svg_img = qr.make_image(image_factory=qrcode.image.svg.SvgPathImage)
        svg_buffer = BytesIO()
        svg_img.save(svg_buffer)
        qr_code_svg = svg_buffer.getvalue().decode("utf-8")

        # Create data URL for easy embedding
        qr_code_data_url = f"data:image/svg+xml;base64,{base64.b64encode(qr_code_svg.encode()).decode()}"

        # Save to database (but don't enable yet)
        await db.commit()

        # Log setup initiation
        auth_audit_logger.log_token_operation(
            AuditEventType.TOKEN_CREATED,
            user.username,
            True,
            details={"operation": "2fa_setup_initiated", "method": "totp"},
        )

        return TwoFactorSetupResult(
            secret=secret,
            qr_code_svg=qr_code_svg,
            qr_code_data_url=qr_code_data_url,
            backup_codes=backup_codes,
            provisioning_uri=provisioning_uri,
        )

    async def verify_and_enable_totp(
        self, db: AsyncSession, user_id: str, token: str, client_ip: str = None
    ) -> bool:
        """
        Verify TOTP token and enable 2FA.

        Args:
            db: Database session
            user_id: User ID
            token: TOTP token to verify
            client_ip: Client IP address

        Returns:
            True if verification successful and 2FA enabled
        """
        # Get user
        result = await db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()

        if not user or not user.totp_secret:
            return False

        # Verify token
        totp = pyotp.TOTP(user.totp_secret)
        if totp.verify(token, valid_window=1):
            # Enable 2FA
            user.totp_enabled = True
            await db.commit()

            # Log successful enablement
            auth_audit_logger.log_token_operation(
                AuditEventType.TOKEN_VALIDATED,
                user.username,
                True,
                details={
                    "operation": "2fa_enabled",
                    "method": "totp",
                    "client_ip": client_ip,
                },
            )

            return True

        # Log failed verification
        auth_audit_logger.log_token_operation(
            AuditEventType.TOKEN_INVALID,
            user.username,
            False,
            details={
                "operation": "2fa_enable_failed",
                "method": "totp",
                "client_ip": client_ip,
            },
        )

        return False

    async def disable_totp(
        self, db: AsyncSession, user_id: str, client_ip: str = None
    ) -> bool:
        """
        Disable TOTP 2FA for user.

        Args:
            db: Database session
            user_id: User ID
            client_ip: Client IP address

        Returns:
            True if disabled successfully
        """
        # Get user
        result = await db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()

        if not user:
            return False

        # Disable 2FA and clear secrets
        user.totp_enabled = False
        user.totp_secret = None
        user.backup_codes = None

        await db.commit()

        # Log disablement
        auth_audit_logger.log_token_operation(
            AuditEventType.TOKEN_EXPIRED,
            user.username,
            True,
            details={
                "operation": "2fa_disabled",
                "method": "totp",
                "client_ip": client_ip,
            },
        )

        return True

    async def generate_new_backup_codes(
        self, db: AsyncSession, user_id: str
    ) -> List[str]:
        """
        Generate new backup codes for user.

        Args:
            db: Database session
            user_id: User ID

        Returns:
            List of new backup codes
        """
        # Get user
        result = await db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()

        if not user or not user.totp_enabled:
            raise ValueError("User not found or 2FA not enabled")

        # Generate new backup codes
        backup_codes = [
            secrets.token_hex(4).upper() for _ in range(self.backup_codes_count)
        ]
        user.backup_codes = json.dumps(
            [AuthenticationService.get_password_hash(code) for code in backup_codes]
        )

        await db.commit()

        # Log backup code generation
        auth_audit_logger.log_token_operation(
            AuditEventType.TOKEN_CREATED,
            user.username,
            True,
            details={
                "operation": "backup_codes_regenerated",
                "count": len(backup_codes),
            },
        )

        return backup_codes

    async def get_2fa_status(self, db: AsyncSession, user_id: str) -> TwoFactorStatus:
        """
        Get 2FA status for user.

        Args:
            db: Database session
            user_id: User ID

        Returns:
            2FA status information
        """
        # Get user
        result = await db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()

        if not user:
            return TwoFactorStatus(
                enabled=False,
                setup_complete=False,
                backup_codes_remaining=0,
                last_used=None,
                method_used=None,
            )

        # Count remaining backup codes
        backup_codes_remaining = 0
        if user.backup_codes:
            try:
                backup_codes = json.loads(user.backup_codes)
                backup_codes_remaining = len(backup_codes)
            except (json.JSONDecodeError, TypeError):
                backup_codes_remaining = 0

        return TwoFactorStatus(
            enabled=user.totp_enabled or False,
            setup_complete=bool(user.totp_secret),
            backup_codes_remaining=backup_codes_remaining,
            last_used=user.last_login,
            method_used=TwoFactorMethod.TOTP if user.totp_enabled else None,
        )

    async def verify_2fa_token(
        self, db: AsyncSession, user_id: str, token: str, client_ip: str = None
    ) -> Tuple[bool, TwoFactorMethod]:
        """
        Verify 2FA token (TOTP or backup code).

        Args:
            db: Database session
            user_id: User ID
            token: Token to verify
            client_ip: Client IP address

        Returns:
            Tuple of (success, method_used)
        """
        # Get user
        result = await db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()

        if not user or not user.totp_enabled:
            return False, None

        # Try TOTP first
        if user.totp_secret:
            totp = pyotp.TOTP(user.totp_secret)
            if totp.verify(token, valid_window=1):
                # Log successful verification
                auth_audit_logger.log_token_operation(
                    AuditEventType.TOKEN_VALIDATED,
                    user.username,
                    True,
                    details={
                        "operation": "2fa_verified",
                        "method": "totp",
                        "client_ip": client_ip,
                    },
                )
                return True, TwoFactorMethod.TOTP

        # Try backup codes
        if user.backup_codes:
            try:
                backup_codes = json.loads(user.backup_codes)
                for i, hashed_code in enumerate(backup_codes):
                    if AuthenticationService.verify_password(token, hashed_code):
                        # Remove used backup code
                        backup_codes.pop(i)
                        user.backup_codes = json.dumps(backup_codes)
                        await db.commit()

                        # Log successful backup code use
                        auth_audit_logger.log_token_operation(
                            AuditEventType.TOKEN_VALIDATED,
                            user.username,
                            True,
                            details={
                                "operation": "2fa_verified",
                                "method": "backup_code",
                                "remaining_codes": len(backup_codes),
                                "client_ip": client_ip,
                            },
                        )

                        return True, TwoFactorMethod.BACKUP_CODE
            except (json.JSONDecodeError, TypeError):
                pass

        # Log failed verification
        auth_audit_logger.log_token_operation(
            AuditEventType.TOKEN_INVALID,
            user.username,
            False,
            details={"operation": "2fa_verification_failed", "client_ip": client_ip},
        )

        return False, None

    def create_2fa_session(
        self, user_id: str, client_ip: str = None, user_agent: str = None
    ) -> str:
        """
        Create 2FA pending session.

        Args:
            user_id: User ID
            client_ip: Client IP address
            user_agent: User agent

        Returns:
            Session token
        """
        session_token = secrets.token_urlsafe(32)
        expires_at = datetime.now(timezone.utc) + timedelta(
            minutes=self.session_timeout_minutes
        )

        session = TwoFactorSession(
            user_id=user_id,
            session_token=session_token,
            expires_at=expires_at,
            client_ip=client_ip,
            user_agent=user_agent,
        )

        # Store session
        if self.use_redis:
            self.redis_client.setex(
                f"2fa_session:{session_token}",
                self.session_timeout_minutes * 60,
                json.dumps(session.to_dict()),
            )
        else:
            self.sessions[session_token] = session

        return session_token

    def get_2fa_session(self, session_token: str) -> Optional[TwoFactorSession]:
        """
        Get 2FA session by token.

        Args:
            session_token: Session token

        Returns:
            Session if valid, None otherwise
        """
        if self.use_redis:
            session_data = self.redis_client.get(f"2fa_session:{session_token}")
            if session_data:
                return TwoFactorSession.from_dict(json.loads(session_data))
        else:
            session = self.sessions.get(session_token)
            if session and datetime.now(timezone.utc) < session.expires_at:
                return session
            elif session:
                # Clean up expired session
                del self.sessions[session_token]

        return None

    def delete_2fa_session(self, session_token: str) -> bool:
        """
        Delete 2FA session.

        Args:
            session_token: Session token

        Returns:
            True if deleted
        """
        if self.use_redis:
            return bool(self.redis_client.delete(f"2fa_session:{session_token}"))
        else:
            return self.sessions.pop(session_token, None) is not None

    def increment_2fa_attempt(self, session_token: str) -> Optional[int]:
        """
        Increment 2FA attempt counter.

        Args:
            session_token: Session token

        Returns:
            Current attempt count or None if session not found
        """
        session = self.get_2fa_session(session_token)
        if not session:
            return None

        session.attempts += 1

        # Update session
        if self.use_redis:
            self.redis_client.setex(
                f"2fa_session:{session_token}",
                self.session_timeout_minutes * 60,
                json.dumps(session.to_dict()),
            )

        # Check if max attempts exceeded
        if session.attempts >= session.max_attempts:
            self.delete_2fa_session(session_token)
            return None

        return session.attempts


# Global 2FA manager instance
totp_manager = TwoFactorManager()
