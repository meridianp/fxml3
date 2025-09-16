"""
Comprehensive tests for FXML4 authentication and authorization.

This module tests JWT token handling, user authentication,
password verification, scope-based authorization, and security features.
"""

import os
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock, patch

import pytest
from fastapi import HTTPException, status
from jose import JWTError, jwt

from fxml4.api.auth.auth import (
    ACCESS_TOKEN_EXPIRE_MINUTES,
    ALGORITHM,
    SECRET_KEY,
    USERS_DB,
    Token,
    TokenData,
    User,
    UserInDB,
    _get_demo_users_db,
    authenticate_user,
    create_access_token,
    get_current_active_user,
    get_current_user,
    get_password_hash,
    get_user,
    has_scope,
    verify_password,
)


class TestPasswordUtils:
    """Test password hashing and verification utilities."""

    def test_password_hashing_and_verification(self):
        """Test password hashing and verification."""
        password = "test_password_123"

        # Hash password
        hashed = get_password_hash(password)

        # Verify it's hashed (not plain text)
        assert hashed != password
        assert len(hashed) > 50  # bcrypt hashes are long
        assert hashed.startswith("$2b$")  # bcrypt format

        # Verify correct password
        assert verify_password(password, hashed) is True

        # Verify incorrect password
        assert verify_password("wrong_password", hashed) is False

    def test_password_hash_uniqueness(self):
        """Test that same password produces different hashes (salt)."""
        password = "same_password"

        hash1 = get_password_hash(password)
        hash2 = get_password_hash(password)

        # Should be different due to salt
        assert hash1 != hash2

        # But both should verify correctly
        assert verify_password(password, hash1) is True
        assert verify_password(password, hash2) is True

    def test_verify_password_empty_inputs(self):
        """Test password verification with empty inputs."""
        # Empty password
        assert verify_password("", get_password_hash("test")) is False

        # Empty hash (should not crash)
        assert verify_password("test", "") is False

    def test_verify_password_invalid_hash(self):
        """Test password verification with invalid hash format."""
        # Invalid hash format should return False, not crash
        assert verify_password("test", "invalid_hash") is False
        assert verify_password("test", "not_a_bcrypt_hash") is False


class TestUserManagement:
    """Test user management functions."""

    def setup_method(self):
        """Set up test database."""
        self.test_db = {
            "testuser": {
                "username": "testuser",
                "full_name": "Test User",
                "email": "test@example.com",
                "hashed_password": get_password_hash("password123"),
                "disabled": False,
                "scopes": ["user", "read"],
            },
            "disableduser": {
                "username": "disableduser",
                "full_name": "Disabled User",
                "email": "disabled@example.com",
                "hashed_password": get_password_hash("password123"),
                "disabled": True,
                "scopes": ["user", "read"],
            },
        }

    def test_get_user_existing(self):
        """Test getting existing user."""
        user = get_user(self.test_db, "testuser")

        assert user is not None
        assert isinstance(user, UserInDB)
        assert user.username == "testuser"
        assert user.full_name == "Test User"
        assert user.email == "test@example.com"
        assert user.disabled is False
        assert user.scopes == ["user", "read"]
        assert user.hashed_password is not None

    def test_get_user_nonexistent(self):
        """Test getting nonexistent user."""
        user = get_user(self.test_db, "nonexistent")
        assert user is None

    def test_get_user_empty_database(self):
        """Test getting user from empty database."""
        user = get_user({}, "testuser")
        assert user is None

    def test_authenticate_user_valid_credentials(self):
        """Test user authentication with valid credentials."""
        user = authenticate_user(self.test_db, "testuser", "password123")

        assert user is not False
        assert isinstance(user, UserInDB)
        assert user.username == "testuser"

    def test_authenticate_user_invalid_password(self):
        """Test user authentication with invalid password."""
        user = authenticate_user(self.test_db, "testuser", "wrong_password")
        assert user is False

    def test_authenticate_user_nonexistent_user(self):
        """Test user authentication with nonexistent user."""
        user = authenticate_user(self.test_db, "nonexistent", "password123")
        assert user is False

    def test_authenticate_user_disabled_user(self):
        """Test authentication of disabled user (should still authenticate but flag as disabled)."""
        # Authentication should succeed even for disabled users
        # Disabled check happens in get_current_active_user
        user = authenticate_user(self.test_db, "disableduser", "password123")

        assert user is not False
        assert isinstance(user, UserInDB)
        assert user.disabled is True


class TestJWTTokenHandling:
    """Test JWT token creation and validation."""

    def test_create_access_token_basic(self):
        """Test creating basic access token."""
        data = {"sub": "testuser", "scopes": ["user", "read"]}
        token = create_access_token(data)

        assert isinstance(token, str)
        assert len(token) > 50  # JWT tokens are long

        # Verify token can be decoded
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        assert payload["sub"] == "testuser"
        assert payload["scopes"] == ["user", "read"]
        assert "exp" in payload

    def test_create_access_token_custom_expiry(self):
        """Test creating token with custom expiry."""
        data = {"sub": "testuser"}
        custom_delta = timedelta(minutes=60)
        token = create_access_token(data, expires_delta=custom_delta)

        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])

        # Check expiry is approximately 60 minutes from now
        exp_time = datetime.fromtimestamp(payload["exp"])
        expected_time = datetime.now(timezone.utc) + custom_delta

        # Allow 5 second tolerance for test execution time
        assert abs((exp_time - expected_time).total_seconds()) < 5

    def test_create_access_token_default_expiry(self):
        """Test creating token with default expiry."""
        data = {"sub": "testuser"}
        token = create_access_token(data)

        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])

        # Check expiry is approximately ACCESS_TOKEN_EXPIRE_MINUTES from now
        exp_time = datetime.fromtimestamp(payload["exp"])
        expected_time = datetime.now(timezone.utc) + timedelta(
            minutes=ACCESS_TOKEN_EXPIRE_MINUTES
        )

        # Allow 5 second tolerance
        assert abs((exp_time - expected_time).total_seconds()) < 5

    def test_token_with_empty_data(self):
        """Test creating token with empty data."""
        token = create_access_token({})

        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        assert "exp" in payload
        # Should not crash, but won't have useful user data

    def test_token_with_special_characters(self):
        """Test creating token with special characters in data."""
        data = {
            "sub": "user@domain.com",
            "name": "User with spaces & symbols!",
            "scopes": ["read:special/resource"],
        }
        token = create_access_token(data)

        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        assert payload["sub"] == "user@domain.com"
        assert payload["name"] == "User with spaces & symbols!"
        assert payload["scopes"] == ["read:special/resource"]


class TestGetCurrentUser:
    """Test current user extraction from tokens."""

    def setup_method(self):
        """Set up test environment."""
        self.test_user = {
            "username": "testuser",
            "full_name": "Test User",
            "email": "test@example.com",
            "hashed_password": get_password_hash("password123"),
            "disabled": False,
            "scopes": ["user", "read"],
        }

    @pytest.mark.asyncio
    async def test_get_current_user_valid_token(self):
        """Test getting current user with valid token."""
        # Create valid token
        token_data = {"sub": "testuser", "scopes": ["user", "read"]}
        token = create_access_token(token_data)

        with patch("fxml4.api.auth.auth.USERS_DB", {"testuser": self.test_user}):
            user = await get_current_user(token)

        assert isinstance(user, UserInDB)
        assert user.username == "testuser"
        assert user.scopes == ["user", "read"]

    @pytest.mark.asyncio
    async def test_get_current_user_invalid_token(self):
        """Test getting current user with invalid token."""
        with pytest.raises(HTTPException) as exc_info:
            await get_current_user("invalid_token")

        assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
        assert "Could not validate credentials" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_get_current_user_expired_token(self):
        """Test getting current user with expired token."""
        # Create expired token
        token_data = {"sub": "testuser", "scopes": ["user", "read"]}
        expired_delta = timedelta(minutes=-10)  # 10 minutes ago
        token = create_access_token(token_data, expires_delta=expired_delta)

        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(token)

        assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED

    @pytest.mark.asyncio
    async def test_get_current_user_malformed_token(self):
        """Test getting current user with malformed token."""
        malformed_tokens = [
            "not.a.jwt",
            "header.payload",  # Missing signature
            "",
            "Bearer invalid_token",  # Should not include Bearer prefix
        ]

        for token in malformed_tokens:
            with pytest.raises(HTTPException) as exc_info:
                await get_current_user(token)

            assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED

    @pytest.mark.asyncio
    async def test_get_current_user_no_subject(self):
        """Test getting current user with token missing subject."""
        # Create token without 'sub' field
        token_data = {"scopes": ["user", "read"]}
        token = create_access_token(token_data)

        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(token)

        assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED

    @pytest.mark.asyncio
    async def test_get_current_user_nonexistent_user(self):
        """Test getting current user when user doesn't exist in database."""
        token_data = {"sub": "nonexistent_user", "scopes": ["user", "read"]}
        token = create_access_token(token_data)

        with patch("fxml4.api.auth.auth.USERS_DB", {}):
            with pytest.raises(HTTPException) as exc_info:
                await get_current_user(token)

        assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED

    @pytest.mark.asyncio
    async def test_get_current_user_token_with_missing_scopes(self):
        """Test getting current user with token missing scopes."""
        token_data = {"sub": "testuser"}  # No scopes
        token = create_access_token(token_data)

        with patch("fxml4.api.auth.auth.USERS_DB", {"testuser": self.test_user}):
            user = await get_current_user(token)

        # Should work, scopes will be empty list
        assert isinstance(user, UserInDB)
        assert user.username == "testuser"


class TestGetCurrentActiveUser:
    """Test active user validation."""

    def setup_method(self):
        """Set up test users."""
        self.active_user = UserInDB(
            username="active",
            hashed_password="hash",
            disabled=False,
            scopes=["user", "read"],
        )

        self.disabled_user = UserInDB(
            username="disabled",
            hashed_password="hash",
            disabled=True,
            scopes=["user", "read"],
        )

    @pytest.mark.asyncio
    async def test_get_current_active_user_active(self):
        """Test getting active user."""
        user = await get_current_active_user(self.active_user)
        assert user == self.active_user

    @pytest.mark.asyncio
    async def test_get_current_active_user_disabled(self):
        """Test getting disabled user (should raise exception)."""
        with pytest.raises(HTTPException) as exc_info:
            await get_current_active_user(self.disabled_user)

        assert exc_info.value.status_code == 400
        assert "Inactive user" in exc_info.value.detail


class TestScopeBasedAuthorization:
    """Test scope-based authorization."""

    def setup_method(self):
        """Set up test users with different scopes."""
        self.admin_user = User(
            username="admin", scopes=["admin", "user", "read", "write"]
        )

        self.regular_user = User(username="user", scopes=["user", "read"])

        self.read_only_user = User(username="readonly", scopes=["read"])

    @pytest.mark.asyncio
    async def test_has_scope_user_has_required_scope(self):
        """Test scope check when user has required scope."""
        scope_checker = has_scope(["read"])

        # Should pass for all users (they all have 'read')
        result = await scope_checker(self.admin_user)
        assert result is True

        result = await scope_checker(self.regular_user)
        assert result is True

        result = await scope_checker(self.read_only_user)
        assert result is True

    @pytest.mark.asyncio
    async def test_has_scope_user_missing_required_scope(self):
        """Test scope check when user missing required scope."""
        scope_checker = has_scope(["admin"])

        # Should pass for admin
        result = await scope_checker(self.admin_user)
        assert result is True

        # Should fail for regular user
        with pytest.raises(HTTPException) as exc_info:
            await scope_checker(self.regular_user)

        assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN
        assert "Not enough permissions" in exc_info.value.detail
        assert "admin" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_has_scope_multiple_required_scopes(self):
        """Test scope check with multiple required scopes."""
        scope_checker = has_scope(["user", "write"])

        # Should pass for admin (has both)
        result = await scope_checker(self.admin_user)
        assert result is True

        # Should fail for regular user (missing 'write')
        with pytest.raises(HTTPException) as exc_info:
            await scope_checker(self.regular_user)

        assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN

    @pytest.mark.asyncio
    async def test_has_scope_empty_required_scopes(self):
        """Test scope check with no required scopes."""
        scope_checker = has_scope([])

        # Should pass for all users
        result = await scope_checker(self.admin_user)
        assert result is True

        result = await scope_checker(self.regular_user)
        assert result is True


class TestDemoUsersDatabase:
    """Test demo users database creation."""

    def test_demo_users_db_structure(self):
        """Test demo users database structure."""
        with patch.dict(
            os.environ,
            {
                "FXML4_DEMO_ADMIN_PASSWORD": "test_admin_pass",
                "FXML4_DEMO_USER_PASSWORD": "test_user_pass",
            },
        ):
            db = _get_demo_users_db()

        # Check admin user
        assert "admin" in db
        admin = db["admin"]
        assert admin["username"] == "admin"
        assert admin["scopes"] == ["admin", "user", "read", "write"]
        assert admin["disabled"] is False
        assert verify_password("test_admin_pass", admin["hashed_password"]) is True

        # Check regular user
        assert "user" in db
        user = db["user"]
        assert user["username"] == "user"
        assert user["scopes"] == ["user", "read"]
        assert user["disabled"] is False
        assert verify_password("test_user_pass", user["hashed_password"]) is True

    def test_demo_users_db_default_passwords(self):
        """Test demo users database with default passwords."""
        # Clear environment variables
        with patch.dict(os.environ, {}, clear=True):
            db = _get_demo_users_db()

        admin = db["admin"]
        user = db["user"]

        # Should use default passwords
        assert (
            verify_password("change-admin-password", admin["hashed_password"]) is True
        )
        assert verify_password("change-user-password", user["hashed_password"]) is True


class TestPydanticModels:
    """Test Pydantic model validation."""

    def test_token_model(self):
        """Test Token model."""
        token = Token(access_token="test_token", token_type="bearer")

        assert token.access_token == "test_token"
        assert token.token_type == "bearer"

    def test_token_data_model(self):
        """Test TokenData model."""
        # With all fields
        token_data = TokenData(username="testuser", scopes=["read", "write"])
        assert token_data.username == "testuser"
        assert token_data.scopes == ["read", "write"]

        # With optional fields as None
        token_data = TokenData()
        assert token_data.username is None
        assert token_data.scopes is None

    def test_user_model(self):
        """Test User model."""
        user = User(
            username="testuser",
            email="test@example.com",
            full_name="Test User",
            disabled=False,
            scopes=["user", "read"],
        )

        assert user.username == "testuser"
        assert user.email == "test@example.com"
        assert user.full_name == "Test User"
        assert user.disabled is False
        assert user.scopes == ["user", "read"]

    def test_user_in_db_model(self):
        """Test UserInDB model (inherits from User)."""
        user = UserInDB(
            username="testuser", hashed_password="hashed_pass", scopes=["user", "read"]
        )

        assert user.username == "testuser"
        assert user.hashed_password == "hashed_pass"
        assert user.scopes == ["user", "read"]
        # Optional fields should have defaults
        assert user.email is None
        assert user.disabled is None


class TestSecurityConfiguration:
    """Test security configuration and environment variables."""

    def test_jwt_secret_from_environment(self):
        """Test JWT secret loading from environment."""
        with patch.dict(os.environ, {"FXML4_JWT_SECRET_KEY": "env_secret_key"}):
            # Re-import to pick up environment variable
            from fxml4.api.auth.auth import SECRET_KEY

            # Note: This test may not work as expected due to module-level imports
            # In practice, this would require restarting the application

    def test_token_expire_from_environment(self):
        """Test token expiration loading from environment."""
        with patch.dict(os.environ, {"FXML4_JWT_TOKEN_EXPIRE_MINUTES": "60"}):
            # Re-import to pick up environment variable
            from fxml4.api.auth.auth import ACCESS_TOKEN_EXPIRE_MINUTES

            # Note: Same limitation as above test

    def test_configuration_security_warnings(self):
        """Test that appropriate warnings are logged for insecure configurations."""
        # This would test logging of security warnings
        # when default/insecure configurations are used
        pass


class TestAuthenticationEdgeCases:
    """Test edge cases and error conditions."""

    def test_very_long_username(self):
        """Test authentication with very long username."""
        long_username = "a" * 1000
        result = authenticate_user({}, long_username, "password")
        assert result is False

    def test_special_characters_in_username(self):
        """Test authentication with special characters in username."""
        special_usernames = [
            "user@domain.com",
            "user.name",
            "user-name",
            "user_name",
            "用户",  # Unicode characters
            "user with spaces",
        ]

        for username in special_usernames:
            # Should not crash
            result = authenticate_user({}, username, "password")
            assert result is False

    def test_very_long_password(self):
        """Test authentication with very long password."""
        long_password = "a" * 10000
        result = authenticate_user({}, "user", long_password)
        assert result is False

    def test_unicode_password(self):
        """Test authentication with Unicode password."""
        unicode_password = "пароль密码"
        hashed = get_password_hash(unicode_password)

        # Should work with Unicode
        assert verify_password(unicode_password, hashed) is True
        assert verify_password("wrong", hashed) is False


# Pytest markers for test categorization
pytestmark = [pytest.mark.unit, pytest.mark.auth, pytest.mark.security]
