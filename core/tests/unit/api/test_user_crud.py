"""
TDD Tests for User CRUD Operations with RBAC

Tests comprehensive user management functionality including role-based access control.
Following Red-Green-Refactor methodology.
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch
from typing import List, Optional

from core.api.auth.models import User, UserRole, Permission
from core.api.auth.exceptions import (
    InsufficientPermissionsError,
    InvalidCredentialsError,
    AuthenticationError,
)


@pytest.mark.tdd
@pytest.mark.red
class TestUserCrudService:
    """
    RED Phase: Test user CRUD service that doesn't exist yet.

    This will drive the implementation of our user management service.
    """

    def test_user_crud_service_import(self):
        """RED: Test that UserCrudService can be imported."""
        from core.api.auth.user_service import UserCrudService

        service = UserCrudService()
        assert service is not None

    def test_create_user_admin_permission(self):
        """RED: Test user creation requires admin permission."""
        from core.api.auth.user_service import UserCrudService

        # Mock admin user
        admin_user = User(
            user_id="admin_123",
            username="admin",
            email="admin@fxml4.com",
            role=UserRole.ADMIN,
            is_active=True
        )

        # New user data
        new_user_data = {
            "username": "newtrader",
            "email": "trader@fxml4.com",
            "role": UserRole.TRADER,
            "password": "SecurePass123!"  # pragma: allowlist secret
        }

        mock_session = MagicMock()
        service = UserCrudService(db_session=mock_session)

        # Mock successful user creation
        mock_session.query().filter_by().first.return_value = None  # User doesn't exist
        mock_session.add.return_value = None
        mock_session.commit.return_value = None

        with patch("bcrypt.hashpw") as mock_hash:
            mock_hash.return_value = b"hashed_password"

            result = service.create_user(admin_user, new_user_data)

            assert result["user_id"] is not None
            assert result["username"] == "newtrader"
            assert result["email"] == "trader@fxml4.com"
            assert result["role"] == UserRole.TRADER
            assert result["is_active"] is True

    def test_create_user_non_admin_permission_denied(self):
        """RED: Test user creation denied for non-admin users."""
        from core.api.auth.user_service import UserCrudService

        # Mock trader user (non-admin)
        trader_user = User(
            user_id="trader_123",
            username="trader",
            email="trader@fxml4.com",
            role=UserRole.TRADER,
            is_active=True
        )

        new_user_data = {
            "username": "newuser",
            "email": "newuser@fxml4.com",
            "role": UserRole.VIEWER,
            "password": "SecurePass123!"  # pragma: allowlist secret
        }

        service = UserCrudService()

        with pytest.raises(InsufficientPermissionsError):
            service.create_user(trader_user, new_user_data)

    def test_create_user_duplicate_username(self):
        """RED: Test user creation fails with duplicate username."""
        from core.api.auth.user_service import UserCrudService

        admin_user = User(
            user_id="admin_123",
            username="admin",
            email="admin@fxml4.com",
            role=UserRole.ADMIN,
            is_active=True
        )

        new_user_data = {
            "username": "existinguser",
            "email": "new@fxml4.com",
            "role": UserRole.TRADER,
            "password": "SecurePass123!"  # pragma: allowlist secret
        }

        mock_session = MagicMock()
        service = UserCrudService(db_session=mock_session)

        # Mock existing user
        mock_session.query().filter_by().first.return_value = User(
            user_id="existing_123",
            username="existinguser",
            email="existing@fxml4.com",
            role=UserRole.TRADER
        )

        with pytest.raises(AuthenticationError) as exc_info:
            service.create_user(admin_user, new_user_data)

        assert "already exists" in str(exc_info.value)

    def test_get_user_by_id_success(self):
        """RED: Test successful user retrieval by ID."""
        from core.api.auth.user_service import UserCrudService

        admin_user = User(
            user_id="admin_123",
            username="admin",
            email="admin@fxml4.com",
            role=UserRole.ADMIN,
            is_active=True
        )

        target_user = User(
            user_id="target_123",
            username="targetuser",
            email="target@fxml4.com",
            role=UserRole.TRADER,
            is_active=True,
            created_at=datetime.utcnow()
        )

        mock_session = MagicMock()
        service = UserCrudService(db_session=mock_session)

        # Mock user found
        mock_session.query().filter_by().first.return_value = target_user

        result = service.get_user_by_id(admin_user, "target_123")

        assert result["user_id"] == "target_123"
        assert result["username"] == "targetuser"
        assert result["email"] == "target@fxml4.com"
        assert result["role"] == UserRole.TRADER
        assert "password_hash" not in result  # Should not expose password

    def test_get_user_by_id_permission_denied(self):
        """RED: Test user retrieval denied for insufficient permissions."""
        from core.api.auth.user_service import UserCrudService

        viewer_user = User(
            user_id="viewer_123",
            username="viewer",
            email="viewer@fxml4.com",
            role=UserRole.VIEWER,
            is_active=True
        )

        service = UserCrudService()

        with pytest.raises(InsufficientPermissionsError):
            service.get_user_by_id(viewer_user, "target_123")

    def test_list_users_admin_permission(self):
        """RED: Test user listing with admin permissions."""
        from core.api.auth.user_service import UserCrudService

        admin_user = User(
            user_id="admin_123",
            username="admin",
            email="admin@fxml4.com",
            role=UserRole.ADMIN,
            is_active=True
        )

        mock_users = [
            User(user_id="user1", username="trader1", email="trader1@fxml4.com", role=UserRole.TRADER),
            User(user_id="user2", username="trader2", email="trader2@fxml4.com", role=UserRole.TRADER),
            User(user_id="user3", username="viewer1", email="viewer1@fxml4.com", role=UserRole.VIEWER),
        ]

        # Use service without database session to test mock behavior
        service = UserCrudService(db_session=None)

        result = service.list_users(admin_user, limit=10, offset=0, role_filter=None)

        assert result["total"] == 3
        assert len(result["users"]) == 3
        assert result["users"][0]["username"] == "trader1"
        assert result["users"][1]["username"] == "trader2"
        assert result["users"][2]["username"] == "viewer1"

    def test_list_users_with_role_filter(self):
        """RED: Test user listing with role filtering."""
        from core.api.auth.user_service import UserCrudService

        admin_user = User(
            user_id="admin_123",
            username="admin",
            email="admin@fxml4.com",
            role=UserRole.ADMIN,
            is_active=True
        )

        mock_traders = [
            User(user_id="user1", username="trader1", email="trader1@fxml4.com", role=UserRole.TRADER),
            User(user_id="user2", username="trader2", email="trader2@fxml4.com", role=UserRole.TRADER),
        ]

        # Use service without database session to test mock behavior
        service = UserCrudService(db_session=None)

        result = service.list_users(admin_user, limit=10, offset=0, role_filter=UserRole.TRADER)

        assert result["total"] == 2
        assert len(result["users"]) == 2
        assert all(user["role"] == UserRole.TRADER for user in result["users"])

    def test_update_user_admin_permission(self):
        """RED: Test user update with admin permissions."""
        from core.api.auth.user_service import UserCrudService

        admin_user = User(
            user_id="admin_123",
            username="admin",
            email="admin@fxml4.com",
            role=UserRole.ADMIN,
            is_active=True
        )

        existing_user = User(
            user_id="target_123",
            username="oldname",
            email="old@fxml4.com",
            role=UserRole.TRADER,
            is_active=True
        )

        update_data = {
            "email": "newemail@fxml4.com",
            "role": UserRole.COMPLIANCE,
            "is_active": False
        }

        mock_session = MagicMock()
        service = UserCrudService(db_session=mock_session)

        # Mock user found
        mock_session.query().filter_by().first.return_value = existing_user
        mock_session.commit.return_value = None

        result = service.update_user(admin_user, "target_123", update_data)

        assert result["user_id"] == "target_123"
        assert result["email"] == "newemail@fxml4.com"
        assert result["role"] == UserRole.COMPLIANCE
        assert result["is_active"] is False

    def test_update_user_self_allowed(self):
        """RED: Test users can update their own profile (limited fields)."""
        from core.api.auth.user_service import UserCrudService

        user = User(
            user_id="trader_123",
            username="trader",
            email="trader@fxml4.com",
            role=UserRole.TRADER,
            is_active=True
        )

        update_data = {
            "email": "newemail@fxml4.com"
        }

        mock_session = MagicMock()
        service = UserCrudService(db_session=mock_session)

        # Mock user found (self)
        mock_session.query().filter_by().first.return_value = user
        mock_session.commit.return_value = None

        result = service.update_user(user, "trader_123", update_data)

        assert result["user_id"] == "trader_123"
        assert result["email"] == "newemail@fxml4.com"
        assert result["role"] == UserRole.TRADER  # Role should not change

    def test_update_user_role_requires_admin(self):
        """RED: Test role changes require admin permissions."""
        from core.api.auth.user_service import UserCrudService

        trader_user = User(
            user_id="trader_123",
            username="trader",
            email="trader@fxml4.com",
            role=UserRole.TRADER,
            is_active=True
        )

        update_data = {
            "role": UserRole.ADMIN  # Trying to elevate privileges
        }

        service = UserCrudService()

        with pytest.raises(InsufficientPermissionsError):
            service.update_user(trader_user, "trader_123", update_data)

    def test_delete_user_admin_permission(self):
        """RED: Test user deletion with admin permissions."""
        from core.api.auth.user_service import UserCrudService

        admin_user = User(
            user_id="admin_123",
            username="admin",
            email="admin@fxml4.com",
            role=UserRole.ADMIN,
            is_active=True
        )

        target_user = User(
            user_id="target_123",
            username="target",
            email="target@fxml4.com",
            role=UserRole.TRADER,
            is_active=True
        )

        mock_session = MagicMock()
        service = UserCrudService(db_session=mock_session)

        # Mock user found
        mock_session.query().filter_by().first.return_value = target_user
        mock_session.delete.return_value = None
        mock_session.commit.return_value = None

        result = service.delete_user(admin_user, "target_123")

        assert result["deleted"] is True
        assert result["user_id"] == "target_123"

    def test_delete_user_permission_denied(self):
        """RED: Test user deletion denied for non-admin users."""
        from core.api.auth.user_service import UserCrudService

        trader_user = User(
            user_id="trader_123",
            username="trader",
            email="trader@fxml4.com",
            role=UserRole.TRADER,
            is_active=True
        )

        service = UserCrudService()

        with pytest.raises(InsufficientPermissionsError):
            service.delete_user(trader_user, "target_123")

    def test_delete_user_not_found(self):
        """RED: Test user deletion fails when user not found."""
        from core.api.auth.user_service import UserCrudService

        admin_user = User(
            user_id="admin_123",
            username="admin",
            email="admin@fxml4.com",
            role=UserRole.ADMIN,
            is_active=True
        )

        mock_session = MagicMock()
        service = UserCrudService(db_session=mock_session)

        # Mock user not found
        mock_session.query().filter_by().first.return_value = None

        with pytest.raises(AuthenticationError) as exc_info:
            service.delete_user(admin_user, "nonexistent_123")

        assert "not found" in str(exc_info.value)

    def test_activate_deactivate_user(self):
        """RED: Test user activation/deactivation."""
        from core.api.auth.user_service import UserCrudService

        admin_user = User(
            user_id="admin_123",
            username="admin",
            email="admin@fxml4.com",
            role=UserRole.ADMIN,
            is_active=True
        )

        target_user = User(
            user_id="target_123",
            username="target",
            email="target@fxml4.com",
            role=UserRole.TRADER,
            is_active=True
        )

        mock_session = MagicMock()
        service = UserCrudService(db_session=mock_session)

        # Mock user found
        mock_session.query().filter_by().first.return_value = target_user
        mock_session.commit.return_value = None

        # Test deactivation
        result = service.set_user_active_status(admin_user, "target_123", False)

        assert result["user_id"] == "target_123"
        assert result["is_active"] is False

        # Test activation
        result = service.set_user_active_status(admin_user, "target_123", True)

        assert result["user_id"] == "target_123"
        assert result["is_active"] is True

    def test_change_user_password_admin(self):
        """RED: Test password change by admin."""
        from core.api.auth.user_service import UserCrudService

        admin_user = User(
            user_id="admin_123",
            username="admin",
            email="admin@fxml4.com",
            role=UserRole.ADMIN,
            is_active=True
        )

        target_user = User(
            user_id="target_123",
            username="target",
            email="target@fxml4.com",
            role=UserRole.TRADER,
            is_active=True
        )

        new_password = "NewSecurePass123!"  # pragma: allowlist secret

        mock_session = MagicMock()
        service = UserCrudService(db_session=mock_session)

        # Mock user found
        mock_session.query().filter_by().first.return_value = target_user
        mock_session.commit.return_value = None

        with patch("bcrypt.hashpw") as mock_hash:
            mock_hash.return_value = b"new_hashed_password"

            result = service.change_user_password(admin_user, "target_123", new_password)

            assert result["password_changed"] is True
            assert result["user_id"] == "target_123"

    def test_get_user_permissions(self):
        """RED: Test retrieving user permissions."""
        from core.api.auth.user_service import UserCrudService

        admin_user = User(
            user_id="admin_123",
            username="admin",
            email="admin@fxml4.com",
            role=UserRole.ADMIN,
            is_active=True
        )

        trader_user = User(
            user_id="trader_123",
            username="trader",
            email="trader@fxml4.com",
            role=UserRole.TRADER,
            is_active=True
        )

        mock_session = MagicMock()
        service = UserCrudService(db_session=mock_session)

        # Mock user found
        mock_session.query().filter_by().first.return_value = trader_user

        result = service.get_user_permissions(admin_user, "trader_123")

        assert "permissions" in result
        assert Permission.TRADE_EXECUTE in result["permissions"]
        assert Permission.TRADE_VIEW in result["permissions"]
        assert Permission.ACCOUNT_VIEW in result["permissions"]
        # Should not have admin permissions
        assert Permission.USER_CREATE not in result["permissions"]

    def test_check_user_permission(self):
        """RED: Test checking specific user permission."""
        from core.api.auth.user_service import UserCrudService

        admin_user = User(
            user_id="admin_123",
            username="admin",
            email="admin@fxml4.com",
            role=UserRole.ADMIN,
            is_active=True
        )

        trader_user = User(
            user_id="trader_123",
            username="trader",
            email="trader@fxml4.com",
            role=UserRole.TRADER,
            is_active=True
        )

        mock_session = MagicMock()
        service = UserCrudService(db_session=mock_session)

        # Mock user found
        mock_session.query().filter_by().first.return_value = trader_user

        # Test trader has trade permission
        result = service.check_user_permission(admin_user, "trader_123", Permission.TRADE_EXECUTE)
        assert result["has_permission"] is True
        assert result["permission"] == Permission.TRADE_EXECUTE

        # Test trader doesn't have admin permission
        result = service.check_user_permission(admin_user, "trader_123", Permission.USER_CREATE)
        assert result["has_permission"] is False
        assert result["permission"] == Permission.USER_CREATE