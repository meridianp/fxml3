"""
Unit tests for JWT Token Management.

Tests comprehensive JWT authentication functionality including:
- Token generation and validation
- Token refresh mechanisms
- User session management
- Token blacklisting and revocation
- Security features (expiration, claims, etc.)
- Multi-device session handling
- Rate limiting for authentication
"""

import json
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import jwt
import pytest
from freezegun import freeze_time

from core.authentication.jwt_manager import JWTManager
from core.exceptions import (
    AuthenticationError,
    InvalidTokenError,
    RateLimitError,
    TokenExpiredError,
)


class TestJWTManager:
    """Test suite for JWT token management."""

    @pytest.fixture
    def jwt_manager(self):
        """Create JWT manager instance for testing."""
        config = {
            "secret_key": "test_secret_key_12345",  # pragma: allowlist secret
            "algorithm": "HS256",
            "access_token_expire": 15,  # minutes
            "refresh_token_expire": 7,  # days
            "issuer": "fxml4-system",
            "max_login_attempts": 5,
            "rate_limit_window": 300,  # 5 minutes
        }
        return JWTManager(config)

    @pytest.fixture
    def sample_user(self):
        """Sample user data for testing."""
        return {
            "user_id": "user123",
            "username": "trader1",
            "email": "trader1@example.com",
            "roles": ["trader", "analyst"],
            "permissions": ["trade", "view_portfolio", "analyze_market"],
        }

    def test_generates_access_token(self, jwt_manager, sample_user):
        """Test access token generation with proper claims."""
        token = jwt_manager.generate_access_token(sample_user)

        # Decode and verify token structure
        decoded = jwt.decode(
            token, jwt_manager.secret_key, algorithms=[jwt_manager.algorithm]
        )

        assert decoded["sub"] == sample_user["user_id"]
        assert decoded["username"] == sample_user["username"]
        assert decoded["email"] == sample_user["email"]
        assert decoded["roles"] == sample_user["roles"]
        assert decoded["permissions"] == sample_user["permissions"]
        assert decoded["iss"] == "fxml4-system"
        assert decoded["type"] == "access"
        assert "iat" in decoded
        assert "exp" in decoded
        assert "jti" in decoded  # JWT ID for tracking

    def test_generates_refresh_token(self, jwt_manager, sample_user):
        """Test refresh token generation with limited claims."""
        token = jwt_manager.generate_refresh_token(sample_user)

        decoded = jwt.decode(
            token, jwt_manager.secret_key, algorithms=[jwt_manager.algorithm]
        )

        assert decoded["sub"] == sample_user["user_id"]
        assert decoded["username"] == sample_user["username"]
        assert decoded["type"] == "refresh"
        assert decoded["iss"] == "fxml4-system"
        assert "roles" not in decoded  # Refresh tokens have minimal claims
        assert "permissions" not in decoded
        assert "iat" in decoded
        assert "exp" in decoded
        assert "jti" in decoded

    def test_validates_access_token(self, jwt_manager, sample_user):
        """Test access token validation returns user data."""
        token = jwt_manager.generate_access_token(sample_user)

        result = jwt_manager.validate_token(token)

        assert result["valid"] is True
        assert result["user_id"] == sample_user["user_id"]
        assert result["username"] == sample_user["username"]
        assert result["roles"] == sample_user["roles"]
        assert result["permissions"] == sample_user["permissions"]
        assert result["token_type"] == "access"

    def test_validates_refresh_token(self, jwt_manager, sample_user):
        """Test refresh token validation."""
        token = jwt_manager.generate_refresh_token(sample_user)

        result = jwt_manager.validate_token(token)

        assert result["valid"] is True
        assert result["user_id"] == sample_user["user_id"]
        assert result["username"] == sample_user["username"]
        assert result["token_type"] == "refresh"

    def test_rejects_expired_token(self, jwt_manager, sample_user):
        """Test expired token rejection."""
        # Generate token with very short expiration
        with patch.object(jwt_manager, "access_token_expire", 0):  # Expire immediately
            token = jwt_manager.generate_access_token(sample_user)

        # Wait for expiration
        import time

        time.sleep(1)

        with pytest.raises(TokenExpiredError) as exc_info:
            jwt_manager.validate_token(token)

        assert "Token has expired" in str(exc_info.value)

    def test_rejects_invalid_signature(self, jwt_manager, sample_user):
        """Test rejection of tokens with invalid signatures."""
        token = jwt_manager.generate_access_token(sample_user)

        # Modify token to invalidate signature
        corrupted_token = token[:-10] + "corrupted!"

        with pytest.raises(InvalidTokenError) as exc_info:
            jwt_manager.validate_token(corrupted_token)

        assert "Invalid token signature" in str(exc_info.value)

    def test_refreshes_access_token(self, jwt_manager, sample_user):
        """Test refreshing access token using refresh token."""
        refresh_token = jwt_manager.generate_refresh_token(sample_user)

        new_access_token = jwt_manager.refresh_access_token(refresh_token)

        # Validate new access token
        result = jwt_manager.validate_token(new_access_token)
        assert result["valid"] is True
        assert result["user_id"] == sample_user["user_id"]
        assert result["token_type"] == "access"

    def test_rejects_refresh_with_access_token(self, jwt_manager, sample_user):
        """Test rejection when trying to refresh with access token."""
        access_token = jwt_manager.generate_access_token(sample_user)

        with pytest.raises(AuthenticationError) as exc_info:
            jwt_manager.refresh_access_token(access_token)

        assert "Invalid token type for refresh" in str(exc_info.value)

    def test_blacklists_token(self, jwt_manager, sample_user):
        """Test token blacklisting for logout functionality."""
        token = jwt_manager.generate_access_token(sample_user)

        # Validate token works initially
        result = jwt_manager.validate_token(token)
        assert result["valid"] is True

        # Blacklist token
        jwt_manager.blacklist_token(token)

        # Validate token is now rejected
        with pytest.raises(InvalidTokenError) as exc_info:
            jwt_manager.validate_token(token)

        assert "Token has been revoked" in str(exc_info.value)

    def test_revokes_all_user_tokens(self, jwt_manager, sample_user):
        """Test revoking all tokens for a user."""
        token1 = jwt_manager.generate_access_token(sample_user)
        token2 = jwt_manager.generate_refresh_token(sample_user)

        # Both tokens should work initially
        result1 = jwt_manager.validate_token(token1)
        result2 = jwt_manager.validate_token(token2)
        assert result1["valid"] is True
        assert result2["valid"] is True

        # Revoke all user tokens
        jwt_manager.revoke_user_tokens(sample_user["user_id"])

        # Both tokens should now be rejected
        with pytest.raises(InvalidTokenError):
            jwt_manager.validate_token(token1)

        with pytest.raises(InvalidTokenError):
            jwt_manager.validate_token(token2)

    def test_handles_multiple_device_sessions(self, jwt_manager, sample_user):
        """Test managing multiple concurrent sessions per user."""
        # Generate tokens for different devices
        device1_access = jwt_manager.generate_access_token(
            sample_user, device_id="device1"
        )
        device1_refresh = jwt_manager.generate_refresh_token(
            sample_user, device_id="device1"
        )

        device2_access = jwt_manager.generate_access_token(
            sample_user, device_id="device2"
        )
        device2_refresh = jwt_manager.generate_refresh_token(
            sample_user, device_id="device2"
        )

        # All tokens should be valid
        assert jwt_manager.validate_token(device1_access)["valid"] is True
        assert jwt_manager.validate_token(device1_refresh)["valid"] is True
        assert jwt_manager.validate_token(device2_access)["valid"] is True
        assert jwt_manager.validate_token(device2_refresh)["valid"] is True

        # Revoke only device1 sessions
        jwt_manager.revoke_device_tokens(sample_user["user_id"], "device1")

        # Device1 tokens should be rejected
        with pytest.raises(InvalidTokenError):
            jwt_manager.validate_token(device1_access)
        with pytest.raises(InvalidTokenError):
            jwt_manager.validate_token(device1_refresh)

        # Device2 tokens should still work
        assert jwt_manager.validate_token(device2_access)["valid"] is True
        assert jwt_manager.validate_token(device2_refresh)["valid"] is True

    def test_enforces_rate_limiting(self, jwt_manager):
        """Test rate limiting for token generation."""
        user_id = "rate_limit_test"

        # Generate tokens up to the limit
        for i in range(jwt_manager.max_login_attempts):
            try:
                jwt_manager.check_rate_limit(user_id)
            except RateLimitError:
                pytest.fail(f"Rate limit triggered prematurely at attempt {i+1}")

        # Next attempt should trigger rate limit
        with pytest.raises(RateLimitError) as exc_info:
            jwt_manager.check_rate_limit(user_id)

        assert "Rate limit exceeded" in str(exc_info.value)
        assert "Try again in" in str(exc_info.value)

    def test_extracts_user_permissions(self, jwt_manager, sample_user):
        """Test extracting user permissions from token."""
        token = jwt_manager.generate_access_token(sample_user)

        permissions = jwt_manager.get_token_permissions(token)

        assert permissions == sample_user["permissions"]

    def test_checks_permission_authorization(self, jwt_manager, sample_user):
        """Test checking if token has specific permission."""
        token = jwt_manager.generate_access_token(sample_user)

        # Should have trading permission
        assert jwt_manager.has_permission(token, "trade") is True

        # Should not have admin permission
        assert jwt_manager.has_permission(token, "admin") is False

    def test_checks_role_authorization(self, jwt_manager, sample_user):
        """Test checking if token has specific role."""
        token = jwt_manager.generate_access_token(sample_user)

        # Should have trader role
        assert jwt_manager.has_role(token, "trader") is True

        # Should not have admin role
        assert jwt_manager.has_role(token, "admin") is False

    def test_gets_token_metadata(self, jwt_manager, sample_user):
        """Test extracting comprehensive token metadata."""
        with freeze_time("2025-01-01 12:00:00") as frozen_time:
            token = jwt_manager.generate_access_token(sample_user)

            metadata = jwt_manager.get_token_metadata(token)

            assert metadata["user_id"] == sample_user["user_id"]
            assert metadata["username"] == sample_user["username"]
            assert metadata["token_type"] == "access"
            assert metadata["issued_at"] is not None
            assert metadata["expires_at"] is not None
            assert metadata["issuer"] == "fxml4-system"
            assert "jti" in metadata  # JWT ID
            assert metadata["time_to_expire"] > 0

    @patch("time.time")
    def test_handles_token_cleanup(self, mock_time, jwt_manager):
        """Test automatic cleanup of expired blacklisted tokens."""
        # Mock current time
        mock_time.return_value = 1704110400  # 2025-01-01 12:00:00

        # Add some expired tokens to blacklist
        expired_tokens = ["expired1", "expired2", "expired3"]
        for token in expired_tokens:
            jwt_manager.blacklist_token(token)

        # Move time forward past expiration
        mock_time.return_value = 1704196800  # 2025-01-02 12:00:00

        # Trigger cleanup
        jwt_manager.cleanup_expired_tokens()

        # Blacklist should be cleaned up
        assert len(jwt_manager._blacklisted_tokens) == 0

    def test_validates_token_claims_structure(self, jwt_manager):
        """Test validation of token claims structure."""
        # Create malformed token with missing required claims
        malformed_payload = {
            "sub": "user123",
            # Missing required claims like 'iss', 'type', etc.
        }

        malformed_token = jwt.encode(
            malformed_payload, jwt_manager.secret_key, algorithm=jwt_manager.algorithm
        )

        with pytest.raises(InvalidTokenError) as exc_info:
            jwt_manager.validate_token(malformed_token)

        assert "Token missing required claims" in str(exc_info.value)

    def test_prevents_token_replay_attacks(self, jwt_manager, sample_user):
        """Test prevention of token replay attacks using JTI tracking."""
        token = jwt_manager.generate_access_token(sample_user)

        # First validation should work
        result1 = jwt_manager.validate_token(token, track_usage=True)
        assert result1["valid"] is True

        # Enable replay protection
        jwt_manager.enable_replay_protection()

        # Second validation of same token should fail
        with pytest.raises(InvalidTokenError) as exc_info:
            jwt_manager.validate_token(token, track_usage=True)

        assert "Token has already been used" in str(exc_info.value)
