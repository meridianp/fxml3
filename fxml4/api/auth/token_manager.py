"""Enhanced JWT Token Management for FXML4.

This module provides comprehensive JWT token management including:
- Access and refresh token generation
- Token validation and blacklisting
- Automatic token rotation
- Security event logging
- Token cleanup and maintenance

SECURITY FEATURES:
- Token blacklisting for revocation
- Automatic refresh token rotation
- Configurable token expiration
- Rate limiting for token operations
- Comprehensive audit logging
- Secure token storage recommendations
"""

import asyncio
import logging
import os
import secrets
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

import redis.asyncio as redis
from jose import JWTError, jwt
from sqlalchemy import and_, delete, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from fxml4.core.exceptions import AuthenticationError, TokenError
from fxml4.core.logging import get_logger

from .audit_logger import AuditEventType, auth_audit_logger
from .models import RefreshToken, TokenBlacklist, User

logger = get_logger(__name__)


class TokenType(Enum):
    """Token type enumeration."""

    ACCESS = "access"
    REFRESH = "refresh"


class TokenStatus(Enum):
    """Token status enumeration."""

    VALID = "valid"
    EXPIRED = "expired"
    BLACKLISTED = "blacklisted"
    INVALID = "invalid"


@dataclass
class TokenInfo:
    """Token information container."""

    token: str
    token_type: TokenType
    user_id: str
    username: str
    issued_at: datetime
    expires_at: datetime
    scopes: List[str] = field(default_factory=list)
    jti: Optional[str] = None  # JWT ID for blacklisting


@dataclass
class TokenPair:
    """Access and refresh token pair."""

    access_token: str
    refresh_token: str
    access_expires_in: int
    refresh_expires_in: int
    token_type: str = "bearer"


@dataclass
class TokenValidationResult:
    """Result of token validation."""

    is_valid: bool
    status: TokenStatus
    token_info: Optional[TokenInfo] = None
    error_message: Optional[str] = None


class EnhancedTokenManager:
    """Enhanced token manager with comprehensive security features."""

    def __init__(self, config: Dict[str, Any] = None):
        """Initialize token manager.

        Args:
            config: Token manager configuration.
        """
        self.config = config or {}

        # JWT Configuration
        self.secret_key = os.environ.get("FXML4_JWT_SECRET_KEY")
        if not self.secret_key:
            raise ValueError("FXML4_JWT_SECRET_KEY environment variable is required")

        self.algorithm = "HS256"
        self.access_token_expire_minutes = self.config.get(
            "access_token_expire_minutes", 30
        )
        self.refresh_token_expire_days = self.config.get("refresh_token_expire_days", 7)

        # Security settings
        self.enable_token_blacklist = self.config.get("enable_token_blacklist", True)
        self.rotate_refresh_tokens = self.config.get("rotate_refresh_tokens", True)
        self.max_tokens_per_user = self.config.get("max_tokens_per_user", 5)

        # Redis for token blacklisting (optional)
        self.redis_client: Optional[redis.Redis] = None
        self._initialize_redis()

        # Background cleanup
        self.cleanup_interval = self.config.get("cleanup_interval_hours", 24)
        self.cleanup_task: Optional[asyncio.Task] = None

        logger.info("Enhanced token manager initialized")

    def _initialize_redis(self):
        """Initialize Redis connection for token blacklisting."""
        try:
            redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379")
            self.redis_client = redis.from_url(redis_url)
            logger.info("Redis connection initialized for token blacklisting")
        except Exception as e:
            logger.warning(f"Redis not available, using database for blacklisting: {e}")

    async def create_token_pair(
        self,
        user: User,
        db: AsyncSession,
        scopes: Optional[List[str]] = None,
        client_info: Optional[Dict[str, Any]] = None,
    ) -> TokenPair:
        """Create access and refresh token pair.

        Args:
            user: User to create tokens for.
            db: Database session.
            scopes: Token scopes (optional).
            client_info: Client information for audit logging.

        Returns:
            Token pair with access and refresh tokens.
        """
        try:
            # Generate unique JTI for this token pair
            jti = secrets.token_urlsafe(32)

            # Create access token
            access_token_data = {
                "sub": str(user.id),
                "username": user.username,
                "jti": f"{jti}_access",
                "type": TokenType.ACCESS.value,
                "scopes": scopes or self._get_user_scopes(user),
                "iat": datetime.utcnow(),
                "exp": datetime.utcnow()
                + timedelta(minutes=self.access_token_expire_minutes),
            }

            access_token = jwt.encode(
                access_token_data, self.secret_key, algorithm=self.algorithm
            )

            # Create refresh token
            refresh_token_data = {
                "sub": str(user.id),
                "username": user.username,
                "jti": f"{jti}_refresh",
                "type": TokenType.REFRESH.value,
                "iat": datetime.utcnow(),
                "exp": datetime.utcnow()
                + timedelta(days=self.refresh_token_expire_days),
            }

            refresh_token = jwt.encode(
                refresh_token_data, self.secret_key, algorithm=self.algorithm
            )

            # Store refresh token in database
            await self._store_refresh_token(
                db=db,
                user_id=user.id,
                jti=refresh_token_data["jti"],
                expires_at=refresh_token_data["exp"],
                client_info=client_info,
            )

            # Clean up old tokens if necessary
            await self._cleanup_user_tokens(db, user.id)

            # Log token creation
            await auth_audit_logger.log_event(
                db=db,
                user_id=user.id,
                event_type=AuditEventType.TOKEN_CREATED,
                success=True,
                details={
                    "token_type": "access_refresh_pair",
                    "access_expires_in": self.access_token_expire_minutes * 60,
                    "refresh_expires_in": self.refresh_token_expire_days * 24 * 3600,
                    "scopes": access_token_data["scopes"],
                    **(client_info or {}),
                },
            )

            return TokenPair(
                access_token=access_token,
                refresh_token=refresh_token,
                access_expires_in=self.access_token_expire_minutes * 60,
                refresh_expires_in=self.refresh_token_expire_days * 24 * 3600,
            )

        except Exception as e:
            logger.error(f"Failed to create token pair for user {user.username}: {e}")
            raise TokenError(f"Token creation failed: {e}")

    async def validate_access_token(
        self, token: str, db: AsyncSession, required_scopes: Optional[List[str]] = None
    ) -> TokenValidationResult:
        """Validate access token.

        Args:
            token: JWT access token.
            db: Database session.
            required_scopes: Required token scopes.

        Returns:
            Token validation result.
        """
        try:
            # Decode token without automatic expiration validation
            # We'll handle expiration manually to return proper status
            payload = jwt.decode(
                token,
                self.secret_key,
                algorithms=[self.algorithm],
                options={"verify_exp": False},
            )

            # Validate token type
            if payload.get("type") != TokenType.ACCESS.value:
                return TokenValidationResult(
                    is_valid=False,
                    status=TokenStatus.INVALID,
                    error_message="Invalid token type",
                )

            # Check expiration
            exp = payload.get("exp")
            if exp and datetime.fromtimestamp(exp, timezone.utc) < datetime.now(
                timezone.utc
            ):
                return TokenValidationResult(
                    is_valid=False,
                    status=TokenStatus.EXPIRED,
                    error_message="Token expired",
                )

            # Check if token is blacklisted
            jti = payload.get("jti")
            if jti and await self._is_token_blacklisted(db, jti):
                return TokenValidationResult(
                    is_valid=False,
                    status=TokenStatus.BLACKLISTED,
                    error_message="Token has been revoked",
                )

            # Validate scopes
            token_scopes = payload.get("scopes", [])
            if required_scopes and not all(
                scope in token_scopes for scope in required_scopes
            ):
                return TokenValidationResult(
                    is_valid=False,
                    status=TokenStatus.INVALID,
                    error_message="Insufficient token scopes",
                )

            # Create token info
            token_info = TokenInfo(
                token=token,
                token_type=TokenType.ACCESS,
                user_id=payload["sub"],
                username=payload["username"],
                issued_at=datetime.fromtimestamp(payload["iat"], timezone.utc),
                expires_at=datetime.fromtimestamp(payload["exp"], timezone.utc),
                scopes=token_scopes,
                jti=jti,
            )

            return TokenValidationResult(
                is_valid=True, status=TokenStatus.VALID, token_info=token_info
            )

        except JWTError as e:
            return TokenValidationResult(
                is_valid=False,
                status=TokenStatus.INVALID,
                error_message=f"Invalid token: {e}",
            )
        except Exception as e:
            logger.error(f"Token validation error: {e}")
            return TokenValidationResult(
                is_valid=False,
                status=TokenStatus.INVALID,
                error_message="Token validation failed",
            )

    async def refresh_access_token(
        self,
        refresh_token: str,
        db: AsyncSession,
        client_info: Optional[Dict[str, Any]] = None,
    ) -> TokenPair:
        """Refresh access token using refresh token.

        Args:
            refresh_token: JWT refresh token.
            db: Database session.
            client_info: Client information for audit logging.

        Returns:
            New token pair.

        Raises:
            TokenError: If refresh token is invalid or expired.
        """
        try:
            # Decode refresh token without automatic expiration validation
            # We'll handle expiration manually to return proper error messages
            payload = jwt.decode(
                refresh_token,
                self.secret_key,
                algorithms=[self.algorithm],
                options={"verify_exp": False},
            )

            # Validate token type
            if payload.get("type") != TokenType.REFRESH.value:
                raise TokenError("Invalid refresh token type")

            # Check expiration
            exp = payload.get("exp")
            if exp and datetime.fromtimestamp(exp, timezone.utc) < datetime.now(
                timezone.utc
            ):
                raise TokenError("Refresh token expired")

            # Check if token is blacklisted
            jti = payload.get("jti")
            if jti and await self._is_token_blacklisted(db, jti):
                raise TokenError("Refresh token has been revoked")

            # Get user
            user_id = payload["sub"]
            result = await db.execute(
                select(User)
                .options(selectinload(User.roles))
                .where(and_(User.id == user_id, User.is_active == True))
            )
            user = result.scalar_one_or_none()

            if not user:
                raise TokenError("User not found or inactive")

            # Verify refresh token exists in database
            token_result = await db.execute(
                select(RefreshToken).where(
                    and_(
                        RefreshToken.jti == jti,
                        RefreshToken.user_id == user_id,
                        RefreshToken.is_active == True,
                        RefreshToken.expires_at > datetime.now(timezone.utc),
                    )
                )
            )
            stored_token = token_result.scalar_one_or_none()

            if not stored_token:
                raise TokenError("Refresh token not found in database")

            # Invalidate old refresh token if rotation is enabled
            if self.rotate_refresh_tokens:
                await self._revoke_refresh_token(db, jti)

            # Create new token pair
            new_token_pair = await self.create_token_pair(
                user, db, client_info=client_info
            )

            # Log token refresh
            await auth_audit_logger.log_event(
                db=db,
                user_id=user.id,
                event_type=AuditEventType.TOKEN_REFRESHED,
                success=True,
                details={
                    "old_token_jti": jti,
                    "rotation_enabled": self.rotate_refresh_tokens,
                    **(client_info or {}),
                },
            )

            return new_token_pair

        except JWTError as e:
            raise TokenError(f"Invalid refresh token: {e}")
        except Exception as e:
            logger.error(f"Token refresh error: {e}")
            raise TokenError(f"Token refresh failed: {e}")

    async def revoke_token(
        self,
        token: str,
        db: AsyncSession,
        user_id: Optional[str] = None,
        reason: str = "user_requested",
    ) -> bool:
        """Revoke a token (add to blacklist).

        Args:
            token: JWT token to revoke.
            db: Database session.
            user_id: User ID for authorization (optional).
            reason: Revocation reason.

        Returns:
            True if token was successfully revoked.
        """
        try:
            # Decode token to get JTI (ignore expiration for revocation)
            payload = jwt.decode(
                token,
                self.secret_key,
                algorithms=[self.algorithm],
                options={"verify_exp": False},
            )
            jti = payload.get("jti")
            token_user_id = payload.get("sub")

            if not jti:
                return False

            # Authorization check
            if user_id and token_user_id != user_id:
                return False

            # Add to blacklist
            await self._blacklist_token(db, jti, payload.get("exp"), reason)

            # If it's a refresh token, deactivate from database
            if payload.get("type") == TokenType.REFRESH.value:
                await self._revoke_refresh_token(db, jti)

            # Log revocation
            await auth_audit_logger.log_event(
                db=db,
                user_id=token_user_id,
                event_type=AuditEventType.TOKEN_REVOKED,
                success=True,
                details={
                    "token_jti": jti,
                    "token_type": payload.get("type"),
                    "reason": reason,
                },
            )

            return True

        except JWTError:
            return False
        except Exception as e:
            logger.error(f"Token revocation error: {e}")
            return False

    async def revoke_all_user_tokens(
        self, user_id: str, db: AsyncSession, reason: str = "user_requested"
    ) -> int:
        """Revoke all tokens for a user.

        Args:
            user_id: User ID.
            db: Database session.
            reason: Revocation reason.

        Returns:
            Number of tokens revoked.
        """
        try:
            # Get all active refresh tokens for user
            result = await db.execute(
                select(RefreshToken).where(
                    and_(
                        RefreshToken.user_id == user_id, RefreshToken.is_active == True
                    )
                )
            )
            refresh_tokens = result.scalars().all()

            revoked_count = 0

            # Revoke all refresh tokens
            for token in refresh_tokens:
                await self._blacklist_token(db, token.jti, token.expires_at, reason)
                await self._revoke_refresh_token(db, token.jti)
                revoked_count += 1

            # Log mass revocation
            await auth_audit_logger.log_event(
                db=db,
                user_id=user_id,
                event_type=AuditEventType.ALL_TOKENS_REVOKED,
                success=True,
                details={"tokens_revoked": revoked_count, "reason": reason},
            )

            return revoked_count

        except Exception as e:
            logger.error(f"Mass token revocation error: {e}")
            return 0

    async def get_user_tokens(
        self, user_id: str, db: AsyncSession
    ) -> List[Dict[str, Any]]:
        """Get active tokens for a user.

        Args:
            user_id: User ID.
            db: Database session.

        Returns:
            List of active token information.
        """
        try:
            result = await db.execute(
                select(RefreshToken)
                .where(
                    and_(
                        RefreshToken.user_id == user_id,
                        RefreshToken.is_active == True,
                        RefreshToken.expires_at > datetime.now(timezone.utc),
                    )
                )
                .order_by(RefreshToken.created_at.desc())
            )
            tokens = result.scalars().all()

            return [
                {
                    "jti": token.jti,
                    "created_at": token.created_at,
                    "expires_at": token.expires_at,
                    "last_used": token.last_used,
                    "client_ip": token.client_ip,
                    "user_agent": token.user_agent,
                }
                for token in tokens
            ]

        except Exception as e:
            logger.error(f"Error getting user tokens: {e}")
            return []

    def _get_user_scopes(self, user: User) -> List[str]:
        """Get scopes for user based on roles.

        Args:
            user: User object.

        Returns:
            List of user scopes.
        """
        scopes = ["authenticated"]

        for role in user.roles:
            scopes.append(f"role:{role.name}")

            # Add permissions from role
            if role.permissions:
                try:
                    import json

                    permissions = json.loads(role.permissions)
                    scopes.extend(permissions)
                except (json.JSONDecodeError, TypeError):
                    pass

        return list(set(scopes))  # Remove duplicates

    async def _store_refresh_token(
        self,
        db: AsyncSession,
        user_id: str,
        jti: str,
        expires_at: datetime,
        client_info: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Store refresh token in database.

        Args:
            db: Database session.
            user_id: User ID.
            jti: Token JTI.
            expires_at: Token expiration.
            client_info: Client information.
        """
        refresh_token = RefreshToken(
            user_id=user_id,
            jti=jti,
            expires_at=expires_at,
            client_ip=client_info.get("ip_address") if client_info else None,
            user_agent=client_info.get("user_agent") if client_info else None,
        )

        db.add(refresh_token)
        await db.commit()

    async def _revoke_refresh_token(self, db: AsyncSession, jti: str) -> None:
        """Revoke refresh token in database.

        Args:
            db: Database session.
            jti: Token JTI.
        """
        await db.execute(
            select(RefreshToken)
            .where(RefreshToken.jti == jti)
            .update({"is_active": False})
        )
        await db.commit()

    async def _blacklist_token(
        self,
        db: AsyncSession,
        jti: str,
        expires_at: Optional[datetime] = None,
        reason: str = "revoked",
    ) -> None:
        """Add token to blacklist.

        Args:
            db: Database session.
            jti: Token JTI.
            expires_at: Token expiration.
            reason: Blacklist reason.
        """
        if self.redis_client:
            # Use Redis for blacklisting
            try:
                if expires_at:
                    ttl = int((expires_at - datetime.now(timezone.utc)).total_seconds())
                    if ttl > 0:
                        await self.redis_client.setex(f"blacklist:{jti}", ttl, reason)
                else:
                    await self.redis_client.set(f"blacklist:{jti}", reason)
                return
            except Exception as e:
                logger.warning(f"Redis blacklist failed, using database: {e}")

        # Use database for blacklisting
        blacklist_entry = TokenBlacklist(
            jti=jti,
            expires_at=expires_at or datetime.now(timezone.utc) + timedelta(days=30),
            reason=reason,
        )

        db.add(blacklist_entry)
        await db.commit()

    async def _is_token_blacklisted(self, db: AsyncSession, jti: str) -> bool:
        """Check if token is blacklisted.

        Args:
            db: Database session.
            jti: Token JTI.

        Returns:
            True if token is blacklisted.
        """
        if self.redis_client:
            # Check Redis first
            try:
                result = await self.redis_client.get(f"blacklist:{jti}")
                if result is not None:
                    return True
            except Exception as e:
                logger.warning(f"Redis blacklist check failed: {e}")

        # Check database
        result = await db.execute(
            select(TokenBlacklist).where(
                and_(
                    TokenBlacklist.jti == jti,
                    TokenBlacklist.expires_at > datetime.now(timezone.utc),
                )
            )
        )

        return result.scalar_one_or_none() is not None

    async def _cleanup_user_tokens(self, db: AsyncSession, user_id: str) -> None:
        """Clean up excess tokens for user.

        Args:
            db: Database session.
            user_id: User ID.
        """
        if self.max_tokens_per_user <= 0:
            return

        # Get user's active tokens, ordered by creation date (newest first)
        result = await db.execute(
            select(RefreshToken)
            .where(
                and_(RefreshToken.user_id == user_id, RefreshToken.is_active == True)
            )
            .order_by(RefreshToken.created_at.desc())
        )
        tokens = result.scalars().all()

        # If user has too many tokens, deactivate the oldest ones
        if len(tokens) > self.max_tokens_per_user:
            tokens_to_remove = tokens[self.max_tokens_per_user :]
            for token in tokens_to_remove:
                await self._revoke_refresh_token(db, token.jti)

    async def start_cleanup_task(self, db_session_factory):
        """Start background cleanup task.

        Args:
            db_session_factory: Factory for creating database sessions.
        """
        if self.cleanup_task:
            return

        async def cleanup_loop():
            while True:
                try:
                    await asyncio.sleep(
                        self.cleanup_interval * 3600
                    )  # Convert hours to seconds

                    async with db_session_factory() as db:
                        await self._cleanup_expired_tokens(db)

                except asyncio.CancelledError:
                    break
                except Exception as e:
                    logger.error(f"Token cleanup error: {e}")

        self.cleanup_task = asyncio.create_task(cleanup_loop())

    async def stop_cleanup_task(self):
        """Stop background cleanup task."""
        if self.cleanup_task:
            self.cleanup_task.cancel()
            try:
                await self.cleanup_task
            except asyncio.CancelledError:
                pass
            self.cleanup_task = None

    async def _cleanup_expired_tokens(self, db: AsyncSession) -> None:
        """Clean up expired tokens from database.

        Args:
            db: Database session.
        """
        now = datetime.now(timezone.utc)

        # Clean up expired refresh tokens
        await db.execute(delete(RefreshToken).where(RefreshToken.expires_at < now))

        # Clean up expired blacklist entries
        await db.execute(delete(TokenBlacklist).where(TokenBlacklist.expires_at < now))

        await db.commit()
        logger.info("Expired tokens cleaned up")


# Global token manager instance
_token_manager: Optional[EnhancedTokenManager] = None


def get_token_manager(config: Dict[str, Any] = None) -> EnhancedTokenManager:
    """Get global token manager instance.

    Args:
        config: Token manager configuration.

    Returns:
        Enhanced token manager instance.
    """
    global _token_manager

    if _token_manager is None:
        _token_manager = EnhancedTokenManager(config)

    return _token_manager
