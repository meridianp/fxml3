"""
JWT Authentication Service for FXML4
====================================

Enterprise-grade JWT authentication service with:
- Access and refresh token generation
- Secure key rotation
- Token revocation
- Comprehensive validation
- Security features (JTI, audience, issuer, etc.)
"""

import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Dict, Optional, Set

import jwt

from .models import (
    InvalidTokenError,
    TokenExpiredError,
    TokenPair,
    TokenValidationResult,
    User,
)


class JWTService:
    """JWT authentication service with enterprise security features."""

    SUPPORTED_ALGORITHMS = ["HS256", "HS384", "HS512", "RS256", "RS384", "RS512"]
    DEFAULT_ALGORITHM = "HS256"
    DEFAULT_ACCESS_TOKEN_EXPIRE_MINUTES = 15
    DEFAULT_REFRESH_TOKEN_EXPIRE_DAYS = 7
    KEY_ROTATION_GRACE_PERIOD_HOURS = 24

    def __init__(
        self,
        secret_key: str,
        algorithm: str = DEFAULT_ALGORITHM,
        access_token_expire_minutes: int = DEFAULT_ACCESS_TOKEN_EXPIRE_MINUTES,
        refresh_token_expire_days: int = DEFAULT_REFRESH_TOKEN_EXPIRE_DAYS,
        issuer: str = "fxml4-auth-service",
        audience: str = "fxml4-trading-system",
    ):
        """
        Initialize JWT service.

        Args:
            secret_key: Secret key for signing tokens
            algorithm: JWT signing algorithm
            access_token_expire_minutes: Access token expiry in minutes
            refresh_token_expire_days: Refresh token expiry in days
            issuer: JWT issuer claim
            audience: JWT audience claim
        """
        if not secret_key:
            raise ValueError("Secret key cannot be empty")

        if algorithm not in self.SUPPORTED_ALGORITHMS:
            raise ValueError(
                f"Unsupported algorithm: {algorithm}. "
                f"Supported: {self.SUPPORTED_ALGORITHMS}"
            )

        self.current_key = secret_key
        self.algorithm = algorithm
        self.access_token_expire_minutes = access_token_expire_minutes
        self.refresh_token_expire_days = refresh_token_expire_days
        self.issuer = issuer
        self.audience = audience

        # Key rotation support
        self._old_keys: Dict[str, datetime] = {}  # key -> expiry_time

        # Token revocation support
        self._revoked_tokens: Set[str] = set()  # JTI of revoked tokens
        self._revoked_users: Set[str] = set()  # User IDs with revoked tokens

    def generate_access_token(self, user: User) -> str:
        """
        Generate access token for user.

        Args:
            user: User to generate token for

        Returns:
            Encoded JWT access token
        """
        now = datetime.now(timezone.utc)
        expires_delta = timedelta(minutes=self.access_token_expire_minutes)

        payload = {
            # Standard claims
            "sub": user.user_id,  # Subject
            "iss": self.issuer,  # Issuer
            "aud": self.audience,  # Audience
            "iat": now,  # Issued at
            "exp": now + expires_delta,  # Expires
            "nbf": now,  # Not before
            "jti": str(uuid.uuid4()),  # JWT ID
            # Custom claims
            "username": user.username,
            "role": user.role.value,
            "type": "access",
            "is_active": user.is_active,
            "is_verified": user.is_verified,
        }

        # Add permissions if available
        if user.permissions:
            payload["permissions"] = [p.value for p in user.permissions]

        return jwt.encode(payload, self.current_key, algorithm=self.algorithm)

    def generate_refresh_token(self, user: User) -> str:
        """
        Generate refresh token for user.

        Args:
            user: User to generate token for

        Returns:
            Encoded JWT refresh token
        """
        now = datetime.now(timezone.utc)
        expires_delta = timedelta(days=self.refresh_token_expire_days)

        payload = {
            # Standard claims
            "sub": user.user_id,
            "iss": self.issuer,
            "aud": self.audience,
            "iat": now,
            "exp": now + expires_delta,
            "nbf": now,
            "jti": str(uuid.uuid4()),
            # Custom claims
            "username": user.username,
            "role": user.role.value,  # Include role in refresh token
            "type": "refresh",
        }

        return jwt.encode(payload, self.current_key, algorithm=self.algorithm)

    def generate_token_pair(self, user: User) -> TokenPair:
        """
        Generate access and refresh token pair.

        Args:
            user: User to generate tokens for

        Returns:
            TokenPair with access and refresh tokens
        """
        access_token = self.generate_access_token(user)
        refresh_token = self.generate_refresh_token(user)

        return TokenPair(
            access_token=access_token,
            refresh_token=refresh_token,
            token_type="Bearer",
            expires_in=self.access_token_expire_minutes * 60,  # Convert to seconds
        )

    def decode_token(self, token: str) -> Dict:
        """
        Decode JWT token without validation.

        Args:
            token: JWT token to decode

        Returns:
            Token payload

        Raises:
            InvalidTokenError: If token is malformed
        """
        try:
            return jwt.decode(token, options={"verify_signature": False})
        except jwt.DecodeError as e:
            raise InvalidTokenError(f"Malformed token: {e}")

    def validate_token(
        self,
        token: str,
        verify_not_before: bool = False,
        required_type: Optional[str] = None,
    ) -> TokenValidationResult:
        """
        Validate JWT token.

        Args:
            token: JWT token to validate
            verify_not_before: Whether to verify nbf claim
            required_type: Required token type (access/refresh)

        Returns:
            TokenValidationResult with validation details
        """
        try:
            # Try current key first
            payload = self._decode_with_validation(
                token, self.current_key, verify_not_before
            )
        except (TokenExpiredError, InvalidTokenError):
            # Try old keys during grace period
            payload = None
            for old_key, expiry in self._old_keys.items():
                if datetime.now(timezone.utc) < expiry:
                    try:
                        payload = self._decode_with_validation(
                            token, old_key, verify_not_before
                        )
                        break
                    except (TokenExpiredError, InvalidTokenError):
                        continue

            if payload is None:
                # Try to determine the specific error type
                try:
                    # Try to decode without any verification to check basic structure
                    payload_no_verify = jwt.decode(
                        token, options={"verify_signature": False, "verify_exp": False}
                    )

                    # Check if token is expired
                    exp = payload_no_verify.get("exp")
                    if exp and datetime.fromtimestamp(exp, timezone.utc) < datetime.now(
                        timezone.utc
                    ):
                        return TokenValidationResult(
                            is_valid=False,
                            error=TokenExpiredError("Token has expired"),
                        )

                    # If not expired, it's likely a signature issue
                    return TokenValidationResult(
                        is_valid=False,
                        error=InvalidTokenError("Invalid token signature"),
                    )
                except jwt.DecodeError:
                    # If we can't decode at all, it's malformed
                    return TokenValidationResult(
                        is_valid=False,
                        error=InvalidTokenError("Malformed token"),
                    )
        except Exception as e:
            return TokenValidationResult(
                is_valid=False,
                error=InvalidTokenError(f"Token validation failed: {e}"),
            )

        # Check if token is revoked
        jti = payload.get("jti")
        user_id = payload.get("sub")

        if jti in self._revoked_tokens:
            return TokenValidationResult(
                is_valid=False,
                error=InvalidTokenError("Token has been revoked"),
            )

        if user_id in self._revoked_users:
            return TokenValidationResult(
                is_valid=False,
                error=InvalidTokenError("All user tokens have been revoked"),
            )

        # Check token type if required
        if required_type and payload.get("type") != required_type:
            return TokenValidationResult(
                is_valid=False,
                error=InvalidTokenError(
                    f"Expected {required_type} token, got {payload.get('type')}"
                ),
            )

        return TokenValidationResult(
            is_valid=True,
            user_id=payload.get("sub"),
            username=payload.get("username"),
            role=payload.get("role"),
            permissions=payload.get("permissions", []),
            expires_at=datetime.fromtimestamp(payload["exp"], timezone.utc),
        )

    def _decode_with_validation(
        self, token: str, key: str, verify_not_before: bool
    ) -> Dict:
        """Decode token with full validation using specific key."""
        options = {"verify_nbf": verify_not_before}

        try:
            return jwt.decode(
                token,
                key,
                algorithms=[self.algorithm],
                issuer=self.issuer,
                audience=self.audience,
                options=options,
            )
        except jwt.ExpiredSignatureError:
            raise TokenExpiredError("Token has expired")
        except jwt.InvalidTokenError as e:
            raise InvalidTokenError(f"Invalid token: {e}")

    def refresh_tokens(self, refresh_token: str) -> TokenPair:
        """
        Generate new token pair using refresh token.

        Args:
            refresh_token: Valid refresh token

        Returns:
            New TokenPair

        Raises:
            InvalidTokenError: If refresh token is invalid
            TokenExpiredError: If refresh token is expired
        """
        # Validate refresh token
        result = self.validate_token(refresh_token, required_type="refresh")

        if not result.is_valid:
            if isinstance(result.error, TokenExpiredError):
                raise result.error
            else:
                raise InvalidTokenError("Refresh token required for token refresh")

        # Create user object from token claims
        from .models import UserRole

        user = User(
            user_id=result.user_id,
            username=result.username,
            email="",  # Not stored in token
            role=UserRole(result.role),  # Convert string back to enum
        )

        # Revoke old refresh token
        old_payload = self.decode_token(refresh_token)
        self._revoked_tokens.add(old_payload.get("jti"))

        return self.generate_token_pair(user)

    def revoke_token(self, token: str) -> None:
        """
        Revoke specific token.

        Args:
            token: Token to revoke
        """
        payload = self.decode_token(token)
        jti = payload.get("jti")
        if jti:
            self._revoked_tokens.add(jti)

    def revoke_user_tokens(self, user_id: str) -> None:
        """
        Revoke all tokens for a user.

        Args:
            user_id: User ID to revoke tokens for
        """
        self._revoked_users.add(user_id)

    def generate_new_key(self) -> str:
        """
        Generate new cryptographically secure key.

        Returns:
            New secret key
        """
        new_key = secrets.token_urlsafe(64)  # 512-bit key
        self.current_key = new_key
        return new_key

    def rotate_keys(self) -> None:
        """
        Rotate signing keys with grace period.
        """
        # Move current key to old keys with grace period
        grace_period = timedelta(hours=self.KEY_ROTATION_GRACE_PERIOD_HOURS)
        expiry_time = datetime.now(timezone.utc) + grace_period
        self._old_keys[self.current_key] = expiry_time

        # Generate new key
        self.generate_new_key()

        # Clean up expired old keys
        self._cleanup_expired_keys()

    def _cleanup_expired_keys(self) -> None:
        """Remove expired old keys."""
        now = datetime.now(timezone.utc)
        expired_keys = [key for key, expiry in self._old_keys.items() if now >= expiry]

        for key in expired_keys:
            del self._old_keys[key]

    def _expire_old_keys(self) -> None:
        """Force expiry of all old keys (for testing)."""
        self._old_keys.clear()

    def get_key_status(self) -> Dict:
        """
        Get key rotation status.

        Returns:
            Dictionary with key status information
        """
        self._cleanup_expired_keys()

        return {
            "current_key_age": "N/A",  # Would need key creation tracking
            "old_keys_count": len(self._old_keys),
            "revoked_tokens_count": len(self._revoked_tokens),
            "revoked_users_count": len(self._revoked_users),
        }
