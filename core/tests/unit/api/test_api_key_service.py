"""
TDD Tests for API Key Generation and Encryption Service

Tests comprehensive API key management functionality with encryption and security.
Following Red-Green-Refactor methodology.
"""

import base64
import secrets
from datetime import datetime, timedelta
from typing import List, Optional
from unittest.mock import MagicMock, patch

import pytest

from core.api.auth.exceptions import (
    AuthenticationError,
    InsufficientPermissionsError,
    InvalidCredentialsError,
)
from core.api.auth.models import Permission, User, UserRole


@pytest.mark.tdd
@pytest.mark.red
class TestApiKeyService:
    """
    RED Phase: Test API key service that doesn't exist yet.

    This will drive the implementation of our API key management service.
    """

    def test_api_key_service_import(self):
        """RED: Test that ApiKeyService can be imported."""
        from core.api.auth.api_key_service import ApiKeyService

        service = ApiKeyService()
        assert service is not None

    def test_generate_api_key_success(self):
        """RED: Test successful API key generation."""
        from core.api.auth.api_key_service import ApiKeyService

        user = User(
            user_id="trader_123",
            username="trader",
            email="trader@fxml4.com",
            role=UserRole.TRADER,
            is_active=True,
        )

        key_data = {
            "name": "Trading Bot Key",
            "description": "API key for automated trading",
            "permissions": [Permission.TRADE_EXECUTE, Permission.TRADE_VIEW],
            "expires_days": 30,
        }

        mock_session = MagicMock()
        service = ApiKeyService(db_session=mock_session)

        # Mock the database query chain for checking existing keys
        mock_session.query().filter_by().filter().count.return_value = (
            2  # Less than limit
        )

        with (
            patch("secrets.token_urlsafe") as mock_token,
            patch("core.api.auth.api_key_service.encrypt_api_key") as mock_encrypt,
        ):

            mock_token.return_value = "test_api_key_raw"
            mock_encrypt.return_value = "encrypted_api_key_data"

            result = service.generate_api_key(user, key_data)

            assert result["api_key_id"] is not None
            assert result["name"] == "Trading Bot Key"
            assert (
                result["api_key"] == "fxml4_test_api_key_raw"
            )  # Raw key returned once with prefix
            assert result["key_prefix"] == "fxml4_"
            assert result["permissions"] == [
                Permission.TRADE_EXECUTE,
                Permission.TRADE_VIEW,
            ]
            assert result["expires_at"] is not None
            assert result["is_active"] is True

    def test_generate_api_key_invalid_permissions(self):
        """RED: Test API key generation with invalid permissions."""
        from core.api.auth.api_key_service import ApiKeyService

        trader_user = User(
            user_id="trader_123",
            username="trader",
            email="trader@fxml4.com",
            role=UserRole.TRADER,
            is_active=True,
        )

        key_data = {
            "name": "Admin Key",
            "description": "Trying to get admin permissions",
            "permissions": [
                Permission.USER_CREATE,
                Permission.SYSTEM_CONFIG,
            ],  # Admin only
            "expires_days": 30,
        }

        service = ApiKeyService()

        with pytest.raises(InsufficientPermissionsError) as exc_info:
            service.generate_api_key(trader_user, key_data)

        assert "permissions exceed user role" in str(exc_info.value).lower()

    def test_generate_api_key_viewer_cannot_trade(self):
        """RED: Test viewer role cannot generate trading API keys."""
        from core.api.auth.api_key_service import ApiKeyService

        viewer_user = User(
            user_id="viewer_123",
            username="viewer",
            email="viewer@fxml4.com",
            role=UserRole.VIEWER,
            is_active=True,
        )

        key_data = {
            "name": "Trading Key",
            "description": "Trying to get trading permissions",
            "permissions": [Permission.TRADE_EXECUTE],
            "expires_days": 30,
        }

        service = ApiKeyService()

        with pytest.raises(InsufficientPermissionsError):
            service.generate_api_key(viewer_user, key_data)

    def test_list_user_api_keys(self):
        """RED: Test listing user's API keys."""
        from core.api.auth.api_key_service import ApiKeyService

        user = User(
            user_id="trader_123",
            username="trader",
            email="trader@fxml4.com",
            role=UserRole.TRADER,
            is_active=True,
        )

        mock_keys = [
            {
                "api_key_id": "key_1",
                "name": "Trading Bot",
                "key_prefix": "fxml4_abc123",
                "permissions": [Permission.TRADE_EXECUTE, Permission.TRADE_VIEW],
                "created_at": datetime.utcnow(),
                "expires_at": datetime.utcnow() + timedelta(days=30),
                "last_used_at": None,
                "is_active": True,
            },
            {
                "api_key_id": "key_2",
                "name": "Data Access",
                "key_prefix": "fxml4_def456",
                "permissions": [Permission.TRADE_VIEW, Permission.ACCOUNT_VIEW],
                "created_at": datetime.utcnow() - timedelta(days=5),
                "expires_at": datetime.utcnow() + timedelta(days=25),
                "last_used_at": datetime.utcnow() - timedelta(hours=2),
                "is_active": True,
            },
        ]

        mock_session = MagicMock()
        service = ApiKeyService(db_session=mock_session)

        # Mock database query
        mock_session.query().filter_by().all.return_value = mock_keys

        result = service.list_user_api_keys(user)

        assert result["total"] == 2
        assert len(result["api_keys"]) == 2
        assert result["api_keys"][0]["name"] == "Trading Bot"
        assert result["api_keys"][1]["name"] == "Data Access"
        # Should not expose the actual API key
        assert "api_key" not in result["api_keys"][0]

    def test_get_api_key_by_id(self):
        """RED: Test retrieving API key by ID."""
        from core.api.auth.api_key_service import ApiKeyService

        user = User(
            user_id="trader_123",
            username="trader",
            email="trader@fxml4.com",
            role=UserRole.TRADER,
            is_active=True,
        )

        mock_key = {
            "api_key_id": "key_123",
            "user_id": "trader_123",
            "name": "Trading Bot",
            "key_prefix": "fxml4_abc123",
            "permissions": [Permission.TRADE_EXECUTE, Permission.TRADE_VIEW],
            "created_at": datetime.utcnow(),
            "expires_at": datetime.utcnow() + timedelta(days=30),
            "last_used_at": None,
            "is_active": True,
        }

        mock_session = MagicMock()
        service = ApiKeyService(db_session=mock_session)

        # Mock database query
        mock_session.query().filter_by().first.return_value = mock_key

        result = service.get_api_key_by_id(user, "key_123")

        assert result["api_key_id"] == "key_123"
        assert result["name"] == "Trading Bot"
        assert result["key_prefix"] == "fxml4_abc123"
        assert result["permissions"] == [
            Permission.TRADE_EXECUTE,
            Permission.TRADE_VIEW,
        ]

    def test_get_api_key_by_id_not_owned(self):
        """RED: Test getting API key that doesn't belong to user."""
        from core.api.auth.api_key_service import ApiKeyService

        user = User(
            user_id="trader_123",
            username="trader",
            email="trader@fxml4.com",
            role=UserRole.TRADER,
            is_active=True,
        )

        mock_key = {
            "api_key_id": "key_123",
            "user_id": "other_user_456",  # Different user
            "name": "Other User's Key",
            "key_prefix": "fxml4_xyz789",
            "permissions": [Permission.TRADE_EXECUTE],
            "created_at": datetime.utcnow(),
            "expires_at": datetime.utcnow() + timedelta(days=30),
            "is_active": True,
        }

        mock_session = MagicMock()
        service = ApiKeyService(db_session=mock_session)

        # Mock database query returns key owned by different user
        mock_session.query().filter_by().first.return_value = mock_key

        with pytest.raises(AuthenticationError) as exc_info:
            service.get_api_key_by_id(user, "key_123")

        assert "not authorized" in str(exc_info.value).lower()

    def test_revoke_api_key_success(self):
        """RED: Test successful API key revocation."""
        from core.api.auth.api_key_service import ApiKeyService

        user = User(
            user_id="trader_123",
            username="trader",
            email="trader@fxml4.com",
            role=UserRole.TRADER,
            is_active=True,
        )

        mock_key = {
            "api_key_id": "key_123",
            "user_id": "trader_123",
            "name": "Trading Bot",
            "is_active": True,
        }

        mock_session = MagicMock()
        service = ApiKeyService(db_session=mock_session)

        # Mock database query and update
        mock_session.query().filter_by().first.return_value = mock_key
        mock_session.commit.return_value = None

        result = service.revoke_api_key(user, "key_123")

        assert result["revoked"] is True
        assert result["api_key_id"] == "key_123"
        assert result["revoked_at"] is not None

    def test_revoke_api_key_not_found(self):
        """RED: Test revoking non-existent API key."""
        from core.api.auth.api_key_service import ApiKeyService

        user = User(
            user_id="trader_123",
            username="trader",
            email="trader@fxml4.com",
            role=UserRole.TRADER,
            is_active=True,
        )

        mock_session = MagicMock()
        service = ApiKeyService(db_session=mock_session)

        # Mock database query returns None
        mock_session.query().filter_by().first.return_value = None

        with pytest.raises(AuthenticationError) as exc_info:
            service.revoke_api_key(user, "nonexistent_key")

        assert "not found" in str(exc_info.value).lower()

    def test_verify_api_key_success(self):
        """RED: Test successful API key verification."""
        from core.api.auth.api_key_service import ApiKeyService

        api_key = "fxml4_abc123def456"

        mock_key_data = {
            "api_key_id": "key_123",
            "user_id": "trader_123",
            "permissions": [Permission.TRADE_EXECUTE, Permission.TRADE_VIEW],
            "expires_at": datetime.utcnow() + timedelta(days=15),
            "is_active": True,
            "encrypted_key": "encrypted_data",
        }

        mock_session = MagicMock()
        service = ApiKeyService(db_session=mock_session)

        # Mock database query
        mock_session.query().filter().first.return_value = mock_key_data

        with patch("core.api.auth.api_key_service.verify_api_key_hash") as mock_verify:
            mock_verify.return_value = True

            result = service.verify_api_key(api_key)

            assert result["valid"] is True
            assert result["user_id"] == "trader_123"
            assert result["permissions"] == [
                Permission.TRADE_EXECUTE,
                Permission.TRADE_VIEW,
            ]
            assert result["api_key_id"] == "key_123"

    def test_verify_api_key_expired(self):
        """RED: Test verification of expired API key."""
        from core.api.auth.api_key_service import ApiKeyService

        api_key = "fxml4_abc123def456"

        mock_key_data = {
            "api_key_id": "key_123",
            "user_id": "trader_123",
            "permissions": [Permission.TRADE_EXECUTE],
            "expires_at": datetime.utcnow() - timedelta(days=1),  # Expired
            "is_active": True,
            "encrypted_key": "encrypted_data",
        }

        mock_session = MagicMock()
        service = ApiKeyService(db_session=mock_session)

        # Mock database query
        mock_session.query().filter().first.return_value = mock_key_data

        with patch("core.api.auth.api_key_service.verify_api_key_hash") as mock_verify:
            mock_verify.return_value = True

            result = service.verify_api_key(api_key)

            assert result["valid"] is False
            assert result["error"] == "API key has expired"

    def test_verify_api_key_invalid_format(self):
        """RED: Test verification of malformed API key."""
        from core.api.auth.api_key_service import ApiKeyService

        service = ApiKeyService()

        # Test various invalid formats
        invalid_keys = [
            "invalid_format",
            "fxml4_",  # Too short
            "wrong_prefix_abc123",
            "",
            None,
        ]

        for invalid_key in invalid_keys:
            result = service.verify_api_key(invalid_key)
            assert result["valid"] is False
            assert (
                "invalid" in result["error"].lower()
                and "format" in result["error"].lower()
            )

    def test_update_api_key_last_used(self):
        """RED: Test updating API key last used timestamp."""
        from core.api.auth.api_key_service import ApiKeyService

        mock_session = MagicMock()
        service = ApiKeyService(db_session=mock_session)

        # Mock database update
        mock_session.query().filter_by().update.return_value = 1
        mock_session.commit.return_value = None

        result = service.update_api_key_last_used("key_123")

        assert result["updated"] is True
        assert result["api_key_id"] == "key_123"
        assert result["last_used_at"] is not None

    def test_encrypt_decrypt_api_key(self):
        """RED: Test API key encryption and decryption."""
        from core.api.auth.api_key_service import decrypt_api_key, encrypt_api_key

        original_key = "fxml4_test_api_key_123456789"

        # Test encryption
        encrypted_data = encrypt_api_key(original_key)
        assert encrypted_data != original_key
        assert len(encrypted_data) > len(original_key)

        # Test decryption
        decrypted_key = decrypt_api_key(encrypted_data)
        assert decrypted_key == original_key

    def test_verify_api_key_hash(self):
        """RED: Test API key hash verification."""
        from core.api.auth.api_key_service import hash_api_key, verify_api_key_hash

        api_key = "fxml4_test_key_123"

        # Test hashing
        hashed_key = hash_api_key(api_key)
        assert hashed_key != api_key
        assert len(hashed_key) > 0

        # Test verification
        is_valid = verify_api_key_hash(api_key, hashed_key)
        assert is_valid is True

        # Test invalid verification
        is_invalid = verify_api_key_hash("wrong_key", hashed_key)
        assert is_invalid is False

    def test_admin_list_all_api_keys(self):
        """RED: Test admin listing all API keys across users."""
        from core.api.auth.api_key_service import ApiKeyService

        admin_user = User(
            user_id="admin_123",
            username="admin",
            email="admin@fxml4.com",
            role=UserRole.ADMIN,
            is_active=True,
        )

        mock_keys = [
            {
                "api_key_id": "key_1",
                "user_id": "trader_123",
                "name": "Trader Bot",
                "key_prefix": "fxml4_abc123",
                "created_at": datetime.utcnow(),
                "is_active": True,
            },
            {
                "api_key_id": "key_2",
                "user_id": "trader_456",
                "name": "Data Access",
                "key_prefix": "fxml4_def456",
                "created_at": datetime.utcnow(),
                "is_active": True,
            },
        ]

        mock_session = MagicMock()
        service = ApiKeyService(db_session=mock_session)

        # Mock database query for all keys
        mock_session.query().all.return_value = mock_keys

        result = service.list_all_api_keys(admin_user, limit=10, offset=0)

        assert result["total"] == 2
        assert len(result["api_keys"]) == 2
        assert result["api_keys"][0]["user_id"] == "trader_123"
        assert result["api_keys"][1]["user_id"] == "trader_456"

    def test_admin_revoke_any_api_key(self):
        """RED: Test admin can revoke any user's API key."""
        from core.api.auth.api_key_service import ApiKeyService

        admin_user = User(
            user_id="admin_123",
            username="admin",
            email="admin@fxml4.com",
            role=UserRole.ADMIN,
            is_active=True,
        )

        mock_key = {
            "api_key_id": "key_123",
            "user_id": "trader_456",  # Different user
            "name": "Trader's Key",
            "is_active": True,
        }

        mock_session = MagicMock()
        service = ApiKeyService(db_session=mock_session)

        # Mock database query and update
        mock_session.query().filter_by().first.return_value = mock_key
        mock_session.commit.return_value = None

        result = service.admin_revoke_api_key(admin_user, "key_123")

        assert result["revoked"] is True
        assert result["api_key_id"] == "key_123"
        assert result["revoked_by"] == "admin_123"

    def test_non_admin_cannot_admin_revoke(self):
        """RED: Test non-admin cannot use admin revoke function."""
        from core.api.auth.api_key_service import ApiKeyService

        trader_user = User(
            user_id="trader_123",
            username="trader",
            email="trader@fxml4.com",
            role=UserRole.TRADER,
            is_active=True,
        )

        service = ApiKeyService()

        with pytest.raises(InsufficientPermissionsError):
            service.admin_revoke_api_key(trader_user, "key_123")

    def test_generate_api_key_limits(self):
        """RED: Test API key generation limits per user."""
        from core.api.auth.api_key_service import ApiKeyService

        user = User(
            user_id="trader_123",
            username="trader",
            email="trader@fxml4.com",
            role=UserRole.TRADER,
            is_active=True,
        )

        # Mock user already has 5 active keys (limit is 5)
        mock_existing_keys = [{"api_key_id": f"key_{i}"} for i in range(5)]

        mock_session = MagicMock()
        service = ApiKeyService(db_session=mock_session)

        # Mock database query for existing keys
        mock_session.query().filter_by().filter().count.return_value = 5

        key_data = {
            "name": "Sixth Key",
            "description": "Should fail due to limit",
            "permissions": [Permission.TRADE_VIEW],
            "expires_days": 30,
        }

        with pytest.raises(AuthenticationError) as exc_info:
            service.generate_api_key(user, key_data)

        assert "limit exceeded" in str(exc_info.value).lower()
