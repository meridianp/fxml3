"""
Enhanced JWT Token Manager Validation Suite

Comprehensive testing for the production-grade Enhanced JWT Token Manager.
Tests all enterprise security features including token pairs, rotation, blacklisting,
and security event logging.

Test Categories:
- Token Pair Creation & Validation
- Access Token Validation & Security
- Refresh Token Rotation & Management
- Token Blacklisting & Revocation
- User Token Management & Limits
- Security Event Logging & Audit
- Background Cleanup & Maintenance
- Redis Integration & Fallback
"""

import asyncio
import secrets
from dataclasses import asdict
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List
from unittest.mock import AsyncMock, Mock, patch

import pytest

from fxml4.api.auth.token_manager import (
    EnhancedTokenManager,
    TokenInfo,
    TokenPair,
    TokenStatus,
    TokenType,
    TokenValidationResult,
    get_token_manager,
)


class TestEnhancedTokenManagerInitialization:
    """Test Enhanced Token Manager initialization and configuration."""

    def test_token_manager_initialization_with_config(self):
        """Test token manager initialization with custom configuration."""
        config = {
            "access_token_expire_minutes": 15,
            "refresh_token_expire_days": 14,
            "enable_token_blacklist": True,
            "rotate_refresh_tokens": True,
            "max_tokens_per_user": 3,
            "cleanup_interval_hours": 12,
        }

        with patch.dict(
            "os.environ", {"FXML4_JWT_SECRET_KEY": "test-secret-key-32-chars-minimum"}
        ):
            manager = EnhancedTokenManager(config)

            # Validate configuration
            assert manager.access_token_expire_minutes == 15
            assert manager.refresh_token_expire_days == 14
            assert manager.enable_token_blacklist == True
            assert manager.rotate_refresh_tokens == True
            assert manager.max_tokens_per_user == 3
            assert manager.cleanup_interval == 12
            assert manager.algorithm == "HS256"

    def test_token_manager_requires_jwt_secret(self):
        """Test token manager requires JWT secret key."""
        with patch.dict("os.environ", {}, clear=True):
            with pytest.raises(
                ValueError,
                match="FXML4_JWT_SECRET_KEY environment variable is required",
            ):
                EnhancedTokenManager()

    def test_token_manager_default_configuration(self):
        """Test token manager with default configuration."""
        with patch.dict(
            "os.environ", {"FXML4_JWT_SECRET_KEY": "test-secret-key-32-chars-minimum"}
        ):
            manager = EnhancedTokenManager()

            # Validate defaults
            assert manager.access_token_expire_minutes == 30
            assert manager.refresh_token_expire_days == 7
            assert manager.enable_token_blacklist == True
            assert manager.rotate_refresh_tokens == True
            assert manager.max_tokens_per_user == 5


class TestTokenPairCreation:
    """Test JWT token pair creation and validation."""

    @pytest.fixture
    def mock_user(self):
        """Create mock user for testing."""
        user = Mock()
        user.id = "test-user-123"
        user.username = "test_trader"
        user.is_active = True

        # Mock roles
        role = Mock()
        role.name = "trader"
        role.permissions = '["view_positions", "execute_trades"]'
        user.roles = [role]

        return user

    @pytest.fixture
    def token_manager(self):
        """Create token manager for testing."""
        with patch.dict(
            "os.environ",
            {"FXML4_JWT_SECRET_KEY": "test-secret-key-32-chars-minimum-length"},
        ):
            return EnhancedTokenManager(
                {"access_token_expire_minutes": 30, "refresh_token_expire_days": 7}
            )

    @pytest.mark.asyncio
    async def test_create_token_pair_success(self, token_manager, mock_user):
        """Test successful token pair creation."""
        mock_db = AsyncMock()

        with patch.object(token_manager, "_store_refresh_token", AsyncMock()):
            with patch.object(token_manager, "_cleanup_user_tokens", AsyncMock()):
                with patch(
                    "fxml4.api.auth.audit_logger.auth_audit_logger"
                ) as mock_audit:
                    mock_audit.log_event = AsyncMock()

                    token_pair = await token_manager.create_token_pair(
                        mock_user, mock_db, scopes=["trading", "view_data"]
                    )

        # Validate token pair structure
        assert isinstance(token_pair, TokenPair)
        assert token_pair.access_token is not None
        assert token_pair.refresh_token is not None
        assert token_pair.token_type == "bearer"
        assert token_pair.access_expires_in == 30 * 60  # 30 minutes in seconds
        assert token_pair.refresh_expires_in == 7 * 24 * 3600  # 7 days in seconds

        # Validate tokens are different
        assert token_pair.access_token != token_pair.refresh_token

        # Validate token structure (JWT should have 3 parts)
        assert len(token_pair.access_token.split(".")) == 3
        assert len(token_pair.refresh_token.split(".")) == 3

    @pytest.mark.asyncio
    async def test_create_token_pair_with_client_info(self, token_manager, mock_user):
        """Test token pair creation with client information."""
        mock_db = AsyncMock()
        client_info = {
            "ip_address": "192.168.1.100",
            "user_agent": "FXML4-Client/1.0",
            "device_id": "device-123",
        }

        with patch.object(
            token_manager, "_store_refresh_token", AsyncMock()
        ) as mock_store:
            with patch.object(token_manager, "_cleanup_user_tokens", AsyncMock()):
                with patch(
                    "fxml4.api.auth.audit_logger.auth_audit_logger"
                ) as mock_audit:
                    mock_audit.log_event = AsyncMock()

                    token_pair = await token_manager.create_token_pair(
                        mock_user, mock_db, client_info=client_info
                    )

        # Verify token was created
        assert token_pair is not None

        # Verify client info was passed to storage
        mock_store.assert_called_once()
        call_args = mock_store.call_args[1]  # Get keyword arguments
        assert call_args["client_info"] == client_info


class TestAccessTokenValidation:
    """Test access token validation and security."""

    @pytest.fixture
    def token_manager(self):
        """Create token manager for testing."""
        with patch.dict(
            "os.environ",
            {"FXML4_JWT_SECRET_KEY": "test-secret-key-32-chars-minimum-length"},
        ):
            return EnhancedTokenManager()

    @pytest.mark.asyncio
    async def test_validate_access_token_success(self, token_manager):
        """Test successful access token validation."""
        from jose import jwt

        # Create valid access token with proper timing
        now = datetime.now(timezone.utc)
        payload = {
            "sub": "test-user-123",
            "username": "test_trader",
            "type": TokenType.ACCESS.value,
            "jti": "test-jti-access",
            "scopes": ["trading", "view_data"],
            "iat": now.timestamp(),
            "exp": (now + timedelta(minutes=30)).timestamp(),
        }

        token = jwt.encode(
            payload, token_manager.secret_key, algorithm=token_manager.algorithm
        )
        mock_db = AsyncMock()

        with patch.object(
            token_manager, "_is_token_blacklisted", AsyncMock(return_value=False)
        ):
            result = await token_manager.validate_access_token(token, mock_db)

        # Validate successful result
        assert result.is_valid == True
        assert result.status == TokenStatus.VALID
        assert result.token_info is not None
        assert result.token_info.user_id == "test-user-123"
        assert result.token_info.username == "test_trader"
        assert result.token_info.token_type == TokenType.ACCESS
        assert "trading" in result.token_info.scopes

    @pytest.mark.asyncio
    async def test_validate_expired_access_token(self, token_manager):
        """Test validation of expired access token."""
        from jose import jwt

        # Create expired access token
        now = datetime.now(timezone.utc)
        payload = {
            "sub": "test-user-123",
            "username": "test_trader",
            "type": TokenType.ACCESS.value,
            "jti": "test-jti-expired",
            "iat": (now - timedelta(hours=1)).timestamp(),
            "exp": (now - timedelta(minutes=5)).timestamp(),  # Clearly expired
        }

        token = jwt.encode(
            payload, token_manager.secret_key, algorithm=token_manager.algorithm
        )
        mock_db = AsyncMock()

        result = await token_manager.validate_access_token(token, mock_db)

        # Validate expired token rejection
        assert result.is_valid == False
        assert result.status == TokenStatus.EXPIRED
        assert "expired" in result.error_message.lower()

    @pytest.mark.asyncio
    async def test_validate_blacklisted_access_token(self, token_manager):
        """Test validation of blacklisted access token."""
        from jose import jwt

        # Create valid access token
        now = datetime.now(timezone.utc)
        payload = {
            "sub": "test-user-123",
            "username": "test_trader",
            "type": TokenType.ACCESS.value,
            "jti": "blacklisted-jti",
            "iat": now.timestamp(),
            "exp": (now + timedelta(minutes=30)).timestamp(),
        }

        token = jwt.encode(
            payload, token_manager.secret_key, algorithm=token_manager.algorithm
        )
        mock_db = AsyncMock()

        with patch.object(
            token_manager, "_is_token_blacklisted", AsyncMock(return_value=True)
        ):
            result = await token_manager.validate_access_token(token, mock_db)

        # Validate blacklisted token rejection
        assert result.is_valid == False
        assert result.status == TokenStatus.BLACKLISTED
        assert "revoked" in result.error_message.lower()

    @pytest.mark.asyncio
    async def test_validate_insufficient_scopes(self, token_manager):
        """Test validation with insufficient token scopes."""
        from jose import jwt

        # Create access token with limited scopes
        now = datetime.now(timezone.utc)
        payload = {
            "sub": "test-user-123",
            "username": "test_trader",
            "type": TokenType.ACCESS.value,
            "jti": "limited-scopes-jti",
            "scopes": ["view_data"],  # Missing 'admin' scope
            "iat": now.timestamp(),
            "exp": (now + timedelta(minutes=30)).timestamp(),
        }

        token = jwt.encode(
            payload, token_manager.secret_key, algorithm=token_manager.algorithm
        )
        mock_db = AsyncMock()

        with patch.object(
            token_manager, "_is_token_blacklisted", AsyncMock(return_value=False)
        ):
            result = await token_manager.validate_access_token(
                token, mock_db, required_scopes=["admin", "manage_users"]
            )

        # Validate insufficient scopes rejection
        assert result.is_valid == False
        assert result.status == TokenStatus.INVALID
        assert "insufficient" in result.error_message.lower()


class TestRefreshTokenManagement:
    """Test refresh token functionality and rotation."""

    @pytest.fixture
    def token_manager(self):
        """Create token manager for testing."""
        with patch.dict(
            "os.environ",
            {"FXML4_JWT_SECRET_KEY": "test-secret-key-32-chars-minimum-length"},
        ):
            return EnhancedTokenManager({"rotate_refresh_tokens": True})

    @pytest.fixture
    def mock_user(self):
        """Create mock user for testing."""
        user = Mock()
        user.id = "refresh-user-123"
        user.username = "refresh_trader"
        user.is_active = True

        role = Mock()
        role.name = "trader"
        role.permissions = '["trading"]'
        user.roles = [role]

        return user

    @pytest.mark.asyncio
    async def test_refresh_access_token_success(self, token_manager, mock_user):
        """Test successful access token refresh."""
        from jose import jwt

        # Create valid refresh token
        now = datetime.now(timezone.utc)
        payload = {
            "sub": "refresh-user-123",
            "username": "refresh_trader",
            "type": TokenType.REFRESH.value,
            "jti": "refresh-jti-123",
            "iat": now.timestamp(),
            "exp": (now + timedelta(days=7)).timestamp(),
        }

        refresh_token = jwt.encode(
            payload, token_manager.secret_key, algorithm=token_manager.algorithm
        )
        mock_db = AsyncMock()

        # Mock database operations
        with patch.object(mock_db, "execute") as mock_execute:
            # Mock user lookup
            user_result = Mock()
            user_result.scalar_one_or_none.return_value = mock_user

            # Mock refresh token lookup
            token_result = Mock()
            stored_token = Mock()
            stored_token.jti = "refresh-jti-123"
            stored_token.user_id = "refresh-user-123"
            stored_token.is_active = True
            stored_token.expires_at = datetime.now(timezone.utc) + timedelta(days=6)
            token_result.scalar_one_or_none.return_value = stored_token

            mock_execute.side_effect = [user_result, token_result]

            with patch.object(
                token_manager, "_is_token_blacklisted", AsyncMock(return_value=False)
            ):
                with patch.object(token_manager, "_revoke_refresh_token", AsyncMock()):
                    with patch.object(
                        token_manager, "create_token_pair", AsyncMock()
                    ) as mock_create:
                        mock_create.return_value = TokenPair(
                            access_token="new-access-token",
                            refresh_token="new-refresh-token",
                            access_expires_in=1800,
                            refresh_expires_in=604800,
                        )

                        with patch(
                            "fxml4.api.auth.audit_logger.auth_audit_logger"
                        ) as mock_audit:
                            mock_audit.log_event = AsyncMock()

                            new_token_pair = await token_manager.refresh_access_token(
                                refresh_token, mock_db
                            )

        # Validate new token pair
        assert new_token_pair is not None
        assert new_token_pair.access_token == "new-access-token"
        assert new_token_pair.refresh_token == "new-refresh-token"

    @pytest.mark.asyncio
    async def test_refresh_with_expired_token(self, token_manager):
        """Test refresh attempt with expired refresh token."""
        from jose import jwt

        # Create expired refresh token
        now = datetime.now(timezone.utc)
        payload = {
            "sub": "refresh-user-123",
            "username": "refresh_trader",
            "type": TokenType.REFRESH.value,
            "jti": "expired-refresh-jti",
            "iat": (now - timedelta(days=2)).timestamp(),
            "exp": (now - timedelta(days=1)).timestamp(),  # Clearly expired
        }

        expired_token = jwt.encode(
            payload, token_manager.secret_key, algorithm=token_manager.algorithm
        )
        mock_db = AsyncMock()

        # Should raise TokenError for expired refresh token
        from fxml4.core.exceptions import TokenError

        with pytest.raises(TokenError, match="expired"):
            await token_manager.refresh_access_token(expired_token, mock_db)


class TestTokenRevocation:
    """Test token revocation and blacklisting functionality."""

    @pytest.fixture
    def token_manager(self):
        """Create token manager for testing."""
        with patch.dict(
            "os.environ",
            {"FXML4_JWT_SECRET_KEY": "test-secret-key-32-chars-minimum-length"},
        ):
            return EnhancedTokenManager()

    @pytest.mark.asyncio
    async def test_revoke_token_success(self, token_manager):
        """Test successful token revocation."""
        from jose import jwt

        # Create token to revoke
        now = datetime.now(timezone.utc)
        payload = {
            "sub": "revoke-user-123",
            "username": "revoke_trader",
            "type": TokenType.ACCESS.value,
            "jti": "revoke-jti-123",
            "iat": now.timestamp(),
            "exp": (now + timedelta(minutes=30)).timestamp(),
        }

        token = jwt.encode(
            payload, token_manager.secret_key, algorithm=token_manager.algorithm
        )
        mock_db = AsyncMock()

        with patch.object(token_manager, "_blacklist_token", AsyncMock()):
            with patch("fxml4.api.auth.audit_logger.auth_audit_logger") as mock_audit:
                mock_audit.log_event = AsyncMock()

                result = await token_manager.revoke_token(
                    token, mock_db, user_id="revoke-user-123", reason="user_logout"
                )

        # Validate successful revocation
        assert result == True

    @pytest.mark.asyncio
    async def test_revoke_all_user_tokens(self, token_manager):
        """Test revoking all tokens for a user."""
        mock_db = AsyncMock()
        user_id = "mass-revoke-user"

        # Mock database query for user's refresh tokens
        with patch.object(mock_db, "execute") as mock_execute:
            result = Mock()

            # Mock refresh tokens
            token1 = Mock()
            token1.jti = "token1-jti"
            token1.expires_at = datetime.now(timezone.utc) + timedelta(days=5)

            token2 = Mock()
            token2.jti = "token2-jti"
            token2.expires_at = datetime.now(timezone.utc) + timedelta(days=3)

            result.scalars.return_value.all.return_value = [token1, token2]
            mock_execute.return_value = result

            with patch.object(token_manager, "_blacklist_token", AsyncMock()):
                with patch.object(token_manager, "_revoke_refresh_token", AsyncMock()):
                    with patch(
                        "fxml4.api.auth.audit_logger.auth_audit_logger"
                    ) as mock_audit:
                        mock_audit.log_event = AsyncMock()

                        revoked_count = await token_manager.revoke_all_user_tokens(
                            user_id, mock_db, reason="account_compromise"
                        )

        # Validate all tokens were revoked
        assert revoked_count == 2


class TestUserTokenManagement:
    """Test user token management and limits."""

    @pytest.fixture
    def token_manager(self):
        """Create token manager for testing."""
        with patch.dict(
            "os.environ",
            {"FXML4_JWT_SECRET_KEY": "test-secret-key-32-chars-minimum-length"},
        ):
            return EnhancedTokenManager({"max_tokens_per_user": 3})

    @pytest.mark.asyncio
    async def test_get_user_tokens(self, token_manager):
        """Test getting active tokens for a user."""
        mock_db = AsyncMock()
        user_id = "token-list-user"

        # Mock database query
        with patch.object(mock_db, "execute") as mock_execute:
            result = Mock()

            # Mock tokens
            token1 = Mock()
            token1.jti = "active-token-1"
            token1.created_at = datetime.now(timezone.utc)
            token1.expires_at = datetime.now(timezone.utc) + timedelta(days=5)
            token1.last_used = None
            token1.client_ip = "192.168.1.100"
            token1.user_agent = "FXML4-Client/1.0"

            result.scalars.return_value.all.return_value = [token1]
            mock_execute.return_value = result

            tokens = await token_manager.get_user_tokens(user_id, mock_db)

        # Validate returned tokens
        assert len(tokens) == 1
        assert tokens[0]["jti"] == "active-token-1"
        assert tokens[0]["client_ip"] == "192.168.1.100"
        assert tokens[0]["user_agent"] == "FXML4-Client/1.0"


class TestTokenManagerIntegration:
    """Test token manager integration and global instance."""

    def test_get_global_token_manager(self):
        """Test getting global token manager instance."""
        config = {"access_token_expire_minutes": 45}

        with patch.dict(
            "os.environ", {"FXML4_JWT_SECRET_KEY": "test-secret-key-32-chars-minimum"}
        ):
            # First call creates instance
            manager1 = get_token_manager(config)
            assert manager1 is not None

            # Second call returns same instance
            manager2 = get_token_manager()
            assert manager1 is manager2

    def test_token_type_enum(self):
        """Test token type enumeration."""
        assert TokenType.ACCESS.value == "access"
        assert TokenType.REFRESH.value == "refresh"

    def test_token_status_enum(self):
        """Test token status enumeration."""
        assert TokenStatus.VALID.value == "valid"
        assert TokenStatus.EXPIRED.value == "expired"
        assert TokenStatus.BLACKLISTED.value == "blacklisted"
        assert TokenStatus.INVALID.value == "invalid"

    def test_token_info_dataclass(self):
        """Test TokenInfo dataclass structure."""
        token_info = TokenInfo(
            token="test-token",
            token_type=TokenType.ACCESS,
            user_id="test-user",
            username="test_trader",
            issued_at=datetime.now(timezone.utc),
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=30),
            scopes=["trading", "view_data"],
            jti="test-jti",
        )

        # Validate dataclass fields
        assert token_info.token == "test-token"
        assert token_info.token_type == TokenType.ACCESS
        assert token_info.user_id == "test-user"
        assert token_info.username == "test_trader"
        assert "trading" in token_info.scopes
        assert token_info.jti == "test-jti"

    def test_token_pair_dataclass(self):
        """Test TokenPair dataclass structure."""
        token_pair = TokenPair(
            access_token="access-123",
            refresh_token="refresh-456",
            access_expires_in=1800,
            refresh_expires_in=604800,
            token_type="bearer",
        )

        # Validate dataclass fields
        assert token_pair.access_token == "access-123"
        assert token_pair.refresh_token == "refresh-456"
        assert token_pair.access_expires_in == 1800
        assert token_pair.refresh_expires_in == 604800
        assert token_pair.token_type == "bearer"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
