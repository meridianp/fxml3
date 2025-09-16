"""
Test-Driven Development for JWT Authentication Service
=====================================================

RED → GREEN → REFACTOR cycle for implementing enterprise-grade JWT authentication
with refresh tokens, secure key rotation, and comprehensive security features.

Phase 4A: Core Authentication System
"""

import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, Mock, patch

import jwt
import pytest
from jose import JWTError

# Test-driven imports - these will guide implementation
from fxml4.api.auth.jwt_service import (
    AuthenticationError,
    InvalidTokenError,
    JWTService,
    KeyRotationError,
    TokenExpiredError,
    TokenPair,
    TokenValidationResult,
)
from fxml4.api.auth.models import User, UserRole


@pytest.fixture
def jwt_service():
    """Create JWT service instance for testing."""
    return JWTService(
        secret_key="test-secret-key-for-phase4",  # pragma: allowlist secret
        algorithm="HS256",
        access_token_expire_minutes=15,
        refresh_token_expire_days=7,
    )


@pytest.fixture
def sample_user():
    """Create sample user for testing."""
    return User(
        user_id="test-user-123",
        username="test_trader",
        email="trader@test.com",
        role=UserRole.TRADER,
        is_active=True,
        is_verified=True,
    )


class TestJWTServiceInitialization:
    """Test JWT service initialization and configuration."""

    def test_jwt_service_creation(self):
        """Test JWT service can be created with valid configuration."""
        # RED: This will fail because JWTService doesn't exist yet
        service = JWTService(
            secret_key="test-key",  # pragma: allowlist secret
            algorithm="HS256",
            access_token_expire_minutes=15,
            refresh_token_expire_days=7,
        )

        assert service.algorithm == "HS256"
        assert service.access_token_expire_minutes == 15
        assert service.refresh_token_expire_days == 7

    def test_jwt_service_requires_secret_key(self):
        """Test JWT service requires a secret key."""
        with pytest.raises(ValueError) as exc_info:
            JWTService(secret_key="", algorithm="HS256")  # Empty secret key should fail

        assert "Secret key cannot be empty" in str(exc_info.value)

    def test_jwt_service_validates_algorithm(self):
        """Test JWT service validates supported algorithms."""
        with pytest.raises(ValueError) as exc_info:
            JWTService(
                secret_key="test-key",  # pragma: allowlist secret
                algorithm="INVALID_ALGO",
            )

        assert "Unsupported algorithm" in str(exc_info.value)


class TestTokenGeneration:
    """Test JWT token generation functionality."""

    def test_generate_access_token(self, jwt_service, sample_user):
        """Test access token generation with user claims."""
        token = jwt_service.generate_access_token(sample_user)

        assert isinstance(token, str)
        assert len(token) > 0

        # Decode token to verify claims
        payload = jwt_service.decode_token(token)
        assert payload["sub"] == sample_user.user_id
        assert payload["username"] == sample_user.username
        assert payload["role"] == sample_user.role.value
        assert payload["type"] == "access"
        assert "exp" in payload
        assert "iat" in payload

    def test_generate_refresh_token(self, jwt_service, sample_user):
        """Test refresh token generation."""
        token = jwt_service.generate_refresh_token(sample_user)

        assert isinstance(token, str)
        assert len(token) > 0

        # Refresh tokens should have longer expiry
        payload = jwt_service.decode_token(token)
        assert payload["sub"] == sample_user.user_id
        assert payload["type"] == "refresh"

        # Verify expiry is longer than access token
        exp_time = datetime.fromtimestamp(payload["exp"], timezone.utc)
        now = datetime.now(timezone.utc)
        assert exp_time > now + timedelta(days=6)  # Should be ~7 days

    def test_generate_token_pair(self, jwt_service, sample_user):
        """Test generation of access and refresh token pair."""
        token_pair = jwt_service.generate_token_pair(sample_user)

        assert isinstance(token_pair, TokenPair)
        assert token_pair.access_token is not None
        assert token_pair.refresh_token is not None
        assert token_pair.token_type == "Bearer"
        assert token_pair.expires_in > 0

        # Verify both tokens are valid
        access_payload = jwt_service.decode_token(token_pair.access_token)
        refresh_payload = jwt_service.decode_token(token_pair.refresh_token)

        assert access_payload["type"] == "access"
        assert refresh_payload["type"] == "refresh"
        assert access_payload["sub"] == refresh_payload["sub"]


class TestTokenValidation:
    """Test JWT token validation functionality."""

    def test_validate_valid_token(self, jwt_service, sample_user):
        """Test validation of valid tokens."""
        token = jwt_service.generate_access_token(sample_user)

        result = jwt_service.validate_token(token)

        assert isinstance(result, TokenValidationResult)
        assert result.is_valid is True
        assert result.user_id == sample_user.user_id
        assert result.username == sample_user.username
        assert result.role == sample_user.role.value
        assert result.error is None

    def test_validate_expired_token(self, jwt_service, sample_user):
        """Test validation of expired tokens."""
        # Create service with very short expiry
        short_service = JWTService(
            secret_key="test-key",  # pragma: allowlist secret
            algorithm="HS256",
            access_token_expire_minutes=-1,  # Already expired
        )

        token = short_service.generate_access_token(sample_user)

        result = short_service.validate_token(token)

        assert result.is_valid is False
        assert isinstance(result.error, TokenExpiredError)
        assert "expired" in str(result.error).lower()

    def test_validate_invalid_signature(self, jwt_service, sample_user):
        """Test validation of tokens with invalid signatures."""
        token = jwt_service.generate_access_token(sample_user)

        # Create different service with different key
        other_service = JWTService(
            secret_key="different-key", algorithm="HS256"  # pragma: allowlist secret
        )

        result = other_service.validate_token(token)

        assert result.is_valid is False
        assert isinstance(result.error, InvalidTokenError)

    def test_validate_malformed_token(self, jwt_service):
        """Test validation of malformed tokens."""
        malformed_tokens = [
            "not.a.token",
            "invalid_token_format",
            "",
            "header.payload",  # Missing signature
            "too.many.parts.here.extra",  # Too many parts
        ]

        for malformed_token in malformed_tokens:
            result = jwt_service.validate_token(malformed_token)

            assert result.is_valid is False
            assert isinstance(result.error, InvalidTokenError)


class TestTokenRefresh:
    """Test token refresh functionality."""

    def test_refresh_valid_token(self, jwt_service, sample_user):
        """Test refreshing with valid refresh token."""
        token_pair = jwt_service.generate_token_pair(sample_user)

        new_token_pair = jwt_service.refresh_tokens(token_pair.refresh_token)

        assert isinstance(new_token_pair, TokenPair)
        assert new_token_pair.access_token != token_pair.access_token
        assert new_token_pair.refresh_token != token_pair.refresh_token

        # Verify new tokens are valid
        result = jwt_service.validate_token(new_token_pair.access_token)
        assert result.is_valid is True
        assert result.user_id == sample_user.user_id

    def test_refresh_with_access_token_fails(self, jwt_service, sample_user):
        """Test that refresh fails when using access token."""
        token_pair = jwt_service.generate_token_pair(sample_user)

        with pytest.raises(InvalidTokenError) as exc_info:
            jwt_service.refresh_tokens(token_pair.access_token)

        assert "refresh token required" in str(exc_info.value).lower()

    def test_refresh_expired_token(self, jwt_service, sample_user):
        """Test refreshing with expired refresh token."""
        # Create service with very short refresh expiry
        short_service = JWTService(
            secret_key="test-key",  # pragma: allowlist secret
            algorithm="HS256",
            refresh_token_expire_days=-1,  # Already expired
        )

        token_pair = short_service.generate_token_pair(sample_user)

        with pytest.raises(TokenExpiredError):
            short_service.refresh_tokens(token_pair.refresh_token)


class TestTokenRevocation:
    """Test token revocation functionality."""

    def test_revoke_token(self, jwt_service, sample_user):
        """Test token revocation functionality."""
        token = jwt_service.generate_access_token(sample_user)

        # Token should be valid before revocation
        result = jwt_service.validate_token(token)
        assert result.is_valid is True

        # Revoke token
        jwt_service.revoke_token(token)

        # Token should be invalid after revocation
        result = jwt_service.validate_token(token)
        assert result.is_valid is False
        assert "revoked" in str(result.error).lower()

    def test_revoke_all_user_tokens(self, jwt_service, sample_user):
        """Test revoking all tokens for a user."""
        tokens = []
        for _ in range(3):
            token = jwt_service.generate_access_token(sample_user)
            tokens.append(token)

        # All tokens should be valid
        for token in tokens:
            result = jwt_service.validate_token(token)
            assert result.is_valid is True

        # Revoke all user tokens
        jwt_service.revoke_user_tokens(sample_user.user_id)

        # All tokens should now be invalid
        for token in tokens:
            result = jwt_service.validate_token(token)
            assert result.is_valid is False


class TestKeyRotation:
    """Test JWT signing key rotation functionality."""

    def test_generate_new_key(self, jwt_service):
        """Test generation of new signing keys."""
        old_key = jwt_service.current_key

        new_key = jwt_service.generate_new_key()

        assert new_key != old_key
        assert len(new_key) >= 32  # Should be cryptographically secure
        assert jwt_service.current_key == new_key

    def test_rotate_keys(self, jwt_service, sample_user):
        """Test key rotation process."""
        # Generate token with current key
        old_token = jwt_service.generate_access_token(sample_user)
        old_key = jwt_service.current_key

        # Rotate keys
        jwt_service.rotate_keys()

        # New key should be different
        assert jwt_service.current_key != old_key

        # Old token should still be valid during grace period
        result = jwt_service.validate_token(old_token)
        assert result.is_valid is True

        # New tokens should use new key
        new_token = jwt_service.generate_access_token(sample_user)
        result = jwt_service.validate_token(new_token)
        assert result.is_valid is True

    def test_key_rotation_grace_period(self, jwt_service, sample_user):
        """Test that old keys work during grace period."""
        old_token = jwt_service.generate_access_token(sample_user)

        # Rotate keys
        jwt_service.rotate_keys()

        # Old token should still be valid
        result = jwt_service.validate_token(old_token)
        assert result.is_valid is True

        # After grace period expires, old token should be invalid
        jwt_service._expire_old_keys()  # Force expiry

        result = jwt_service.validate_token(old_token)
        assert result.is_valid is False


class TestSecurityFeatures:
    """Test additional security features."""

    def test_token_includes_jti(self, jwt_service, sample_user):
        """Test that tokens include unique JTI (JWT ID)."""
        token1 = jwt_service.generate_access_token(sample_user)
        token2 = jwt_service.generate_access_token(sample_user)

        payload1 = jwt_service.decode_token(token1)
        payload2 = jwt_service.decode_token(token2)

        assert "jti" in payload1
        assert "jti" in payload2
        assert payload1["jti"] != payload2["jti"]

    def test_token_includes_audience(self, jwt_service, sample_user):
        """Test that tokens include audience claim."""
        token = jwt_service.generate_access_token(sample_user)
        payload = jwt_service.decode_token(token)

        assert "aud" in payload
        assert payload["aud"] == "fxml4-trading-system"

    def test_token_includes_issuer(self, jwt_service, sample_user):
        """Test that tokens include issuer claim."""
        token = jwt_service.generate_access_token(sample_user)
        payload = jwt_service.decode_token(token)

        assert "iss" in payload
        assert payload["iss"] == "fxml4-auth-service"

    def test_token_not_valid_before_issue_time(self, jwt_service, sample_user):
        """Test that tokens are not valid before issue time."""
        # Create a token with future issue time by manipulating the payload manually
        now = datetime.now(timezone.utc)
        future_time = now + timedelta(hours=1)

        # Create payload with future 'nbf' (not before) time
        payload = {
            "sub": sample_user.user_id,
            "iss": jwt_service.issuer,
            "aud": jwt_service.audience,
            "iat": now,
            "exp": now + timedelta(minutes=jwt_service.access_token_expire_minutes),
            "nbf": future_time,  # Not valid before future time
            "jti": str(uuid.uuid4()),
            "username": sample_user.username,
            "role": sample_user.role.value,
            "type": "access",
            "is_active": sample_user.is_active,
            "is_verified": sample_user.is_verified,
        }

        # Create token manually with future nbf
        import jwt as jwt_lib

        token = jwt_lib.encode(
            payload, jwt_service.current_key, algorithm=jwt_service.algorithm
        )

        # Token should not be valid yet when verifying nbf
        result = jwt_service.validate_token(token, verify_not_before=True)
        assert result.is_valid is False


if __name__ == "__main__":
    """
    Run JWT service tests with pytest.

    Usage:
        python -m pytest tests/auth/test_jwt_service.py -v
    """
    pytest.main([__file__, "-v", "--tb=short"])
