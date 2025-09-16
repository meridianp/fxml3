"""
TDD Test Suite for Authentication API Endpoints

Following strict TDD methodology:
1. RED: Write failing tests first
2. GREEN: Implement minimal code to pass
3. REFACTOR: Improve while keeping tests green

This test file demonstrates the TDD approach for critical authentication endpoints.
"""

from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import jwt
import pytest

from core.api.auth.exceptions import (
    AuthenticationError,
    InvalidCredentialsError,
    TokenExpiredError,
    TwoFactorRequiredError,
)
from core.api.auth.models import User, UserSession

# These imports will fail initially (RED phase) - that's expected in TDD!
# We'll implement these modules to make tests pass (GREEN phase)
from core.api.auth.service import AuthenticationService


@pytest.mark.tdd
@pytest.mark.red
class TestAuthenticationService:
    """
    TDD tests for authentication service.
    These tests are written BEFORE the implementation (RED phase).
    """

    @pytest.fixture
    def auth_service(self, mock_db_session):
        """Create authentication service instance with mocked dependencies."""
        return AuthenticationService(db_session=mock_db_session)

    @pytest.fixture
    def valid_user(self, user_factory):
        """Create a valid test user."""
        return user_factory(
            username="trader1",
            email="trader1@fxml4.com",
            password_hash="$2b$12$hashed_password_here",
            is_active=True,
            requires_2fa=False,
        )

    # -------------------------------------------------------------------------
    # RED Phase Tests - These should fail initially
    # -------------------------------------------------------------------------

    @pytest.mark.red
    def test_authenticate_user_with_valid_credentials(
        self, auth_service, valid_user, mock_db_session
    ):
        """
        RED: Test successful authentication with valid credentials.
        This test should fail initially as AuthenticationService doesn't exist yet.
        """
        # Arrange
        username = "trader1"
        password = "SecurePass123!"  # pragma: allowlist secret

        mock_db_session.query().filter_by().first.return_value = valid_user

        with patch("bcrypt.checkpw", return_value=True):
            # Act
            result = auth_service.authenticate(username, password)

            # Assert
            assert result is not None
            assert result["user_id"] == valid_user["id"]
            assert "access_token" in result
            assert "refresh_token" in result
            assert result["token_type"] == "Bearer"

    @pytest.mark.red
    def test_authenticate_fails_with_invalid_password(
        self, auth_service, valid_user, mock_db_session
    ):
        """
        RED: Test authentication failure with wrong password.
        """
        # Arrange
        username = "trader1"
        wrong_password = "WrongPassword123!"  # pragma: allowlist secret

        mock_db_session.query().filter_by().first.return_value = valid_user

        with patch("bcrypt.checkpw", return_value=False):
            # Act & Assert
            with pytest.raises(InvalidCredentialsError) as exc_info:
                auth_service.authenticate(username, wrong_password)

            assert "Invalid username or password" in str(exc_info.value)

    @pytest.mark.red
    def test_authenticate_fails_with_nonexistent_user(
        self, auth_service, mock_db_session
    ):
        """
        RED: Test authentication failure with non-existent user.
        """
        # Arrange
        username = "nonexistent"
        password = "AnyPassword123!"  # pragma: allowlist secret

        mock_db_session.query().filter_by().first.return_value = None

        # Act & Assert
        with pytest.raises(InvalidCredentialsError) as exc_info:
            auth_service.authenticate(username, password)

        assert "Invalid username or password" in str(exc_info.value)

    @pytest.mark.red
    def test_authenticate_fails_with_inactive_user(
        self, auth_service, user_factory, mock_db_session
    ):
        """
        RED: Test authentication failure with inactive account.
        """
        # Arrange
        inactive_user = user_factory(is_active=False)
        mock_db_session.query().filter_by().first.return_value = inactive_user

        with patch("bcrypt.checkpw", return_value=True):
            # Act & Assert
            with pytest.raises(AuthenticationError) as exc_info:
                auth_service.authenticate("trader1", "ValidPassword123!")

            assert "Account is disabled" in str(exc_info.value)

    @pytest.mark.red
    def test_authenticate_requires_2fa_when_enabled(
        self, auth_service, user_factory, mock_db_session
    ):
        """
        RED: Test that 2FA is required when user has it enabled.
        """
        # Arrange
        user_with_2fa = user_factory(requires_2fa=True)
        mock_db_session.query().filter_by().first.return_value = user_with_2fa

        with patch("bcrypt.checkpw", return_value=True):
            # Act & Assert
            with pytest.raises(TwoFactorRequiredError) as exc_info:
                auth_service.authenticate("trader1", "ValidPassword123!")

            assert exc_info.value.temp_token is not None
            assert "Two-factor authentication required" in str(exc_info.value)

    @pytest.mark.red
    def test_verify_2fa_code_success(self, auth_service, user_factory, mock_db_session):
        """
        RED: Test successful 2FA verification.
        """
        # Arrange
        user_with_2fa = user_factory(requires_2fa=True, totp_secret="JBSWY3DPEHPK3PXP")
        temp_token = "temp_token_123"
        valid_code = "123456"

        with patch("pyotp.TOTP") as mock_totp:
            mock_totp.return_value.verify.return_value = True

            # Act
            result = auth_service.verify_2fa(temp_token, valid_code)

            # Assert
            assert result is not None
            assert "access_token" in result
            assert "refresh_token" in result

    @pytest.mark.red
    def test_generate_jwt_tokens(self, auth_service):
        """
        RED: Test JWT token generation.
        """
        # Arrange
        user_id = "user_123"

        # Act
        tokens = auth_service.generate_tokens(user_id)

        # Assert
        assert "access_token" in tokens
        assert "refresh_token" in tokens
        assert tokens["token_type"] == "Bearer"
        assert tokens["expires_in"] == 3600  # 1 hour

        # Verify token can be decoded
        decoded = jwt.decode(
            tokens["access_token"], options={"verify_signature": False}
        )
        assert decoded["sub"] == user_id
        assert "exp" in decoded
        assert "iat" in decoded

    @pytest.mark.red
    def test_verify_access_token_valid(self, auth_service):
        """
        RED: Test verification of valid access token.
        """
        # Arrange
        user_id = "user_123"
        tokens = auth_service.generate_tokens(user_id)

        # Act
        decoded_user_id = auth_service.verify_token(tokens["access_token"])

        # Assert
        assert decoded_user_id == user_id

    @pytest.mark.red
    def test_verify_access_token_expired(self, auth_service):
        """
        RED: Test verification of expired access token.
        """
        # Arrange
        expired_token = jwt.encode(
            {
                "sub": "user_123",
                "exp": datetime.utcnow() - timedelta(hours=1),
                "iat": datetime.utcnow() - timedelta(hours=2),
            },
            "secret_key",
            algorithm="HS256",
        )

        # Act & Assert
        with pytest.raises(TokenExpiredError) as exc_info:
            auth_service.verify_token(expired_token)

        assert "Token has expired" in str(exc_info.value)

    @pytest.mark.red
    def test_refresh_token_success(self, auth_service, mock_db_session):
        """
        RED: Test successful token refresh.
        """
        # Arrange
        user_id = "user_123"
        tokens = auth_service.generate_tokens(user_id)

        # Act
        new_tokens = auth_service.refresh_tokens(tokens["refresh_token"])

        # Assert
        assert new_tokens["access_token"] != tokens["access_token"]
        assert new_tokens["refresh_token"] != tokens["refresh_token"]
        assert new_tokens["token_type"] == "Bearer"

    @pytest.mark.red
    def test_logout_invalidates_tokens(self, auth_service, mock_db_session):
        """
        RED: Test that logout properly invalidates tokens.
        """
        # Arrange
        user_id = "user_123"
        access_token = "valid_token_123"

        # Act
        auth_service.logout(access_token)

        # Assert
        mock_db_session.add.assert_called_once()
        mock_db_session.commit.assert_called_once()

        # Verify token is now invalid
        with pytest.raises(AuthenticationError):
            auth_service.verify_token(access_token)

    @pytest.mark.red
    def test_rate_limiting_prevents_brute_force(self, auth_service, mock_db_session):
        """
        RED: Test rate limiting prevents brute force attacks.
        """
        # Arrange
        username = "trader1"
        mock_db_session.query().filter_by().first.return_value = None

        # Act & Assert
        for i in range(5):
            with pytest.raises(InvalidCredentialsError):
                auth_service.authenticate(username, f"wrong_pass_{i}")

        # 6th attempt should be rate limited
        with pytest.raises(AuthenticationError) as exc_info:
            auth_service.authenticate(username, "another_wrong")

        assert "Too many failed attempts" in str(exc_info.value)

    @pytest.mark.red
    def test_password_complexity_validation(self, auth_service):
        """
        RED: Test password complexity requirements.
        """
        # Arrange
        weak_passwords = [
            "short",  # Too short
            "nouppercase123!",  # No uppercase
            "NOLOWERCASE123!",  # No lowercase
            "NoNumbers!",  # No numbers
            "NoSpecialChar1",  # No special characters
        ]

        # Act & Assert
        for password in weak_passwords:
            is_valid, message = auth_service.validate_password(password)
            assert is_valid is False
            assert message is not None

        # Strong password should pass
        strong_password = "SecurePass123!@#"  # pragma: allowlist secret
        is_valid, message = auth_service.validate_password(strong_password)
        assert is_valid is True
        assert message is None

    @pytest.mark.red
    def test_session_management_tracks_active_sessions(
        self, auth_service, mock_db_session
    ):
        """
        RED: Test that active sessions are properly tracked.
        """
        # Arrange
        user_id = "user_123"

        # Act
        session_1 = auth_service.create_session(user_id, "192.168.1.1", "Chrome/120")
        session_2 = auth_service.create_session(user_id, "192.168.1.2", "Firefox/115")

        # Assert
        active_sessions = auth_service.get_active_sessions(user_id)
        assert len(active_sessions) == 2
        assert session_1["id"] in [s["id"] for s in active_sessions]
        assert session_2["id"] in [s["id"] for s in active_sessions]

    @pytest.mark.red
    def test_concurrent_session_limit_enforced(self, auth_service, mock_db_session):
        """
        RED: Test that concurrent session limits are enforced.
        """
        # Arrange
        user_id = "user_123"
        max_sessions = 3

        # Create max sessions
        for i in range(max_sessions):
            auth_service.create_session(user_id, f"192.168.1.{i}", "Chrome")

        # Act & Assert
        with pytest.raises(AuthenticationError) as exc_info:
            auth_service.create_session(user_id, "192.168.1.99", "Chrome")

        assert "Maximum concurrent sessions exceeded" in str(exc_info.value)


@pytest.mark.tdd
@pytest.mark.red
class TestAuthenticationAPI:
    """
    TDD tests for authentication API endpoints.
    Tests the HTTP layer of authentication.
    """

    @pytest.fixture
    def client(self):
        """Create test client for API testing."""
        # This will fail initially as the API doesn't exist yet
        from fastapi.testclient import TestClient

        from core.api.main import app

        return TestClient(app)

    @pytest.mark.red
    def test_login_endpoint_success(self, client, mock_jwt_token):
        """
        RED: Test successful login via API endpoint.
        """
        # Arrange
        login_data = {
            "username": "trader1",
            "password": "SecurePass123!",  # pragma: allowlist secret
        }

        with patch(
            "core.api.auth.service.AuthenticationService.authenticate"
        ) as mock_auth:
            mock_auth.return_value = {
                "user_id": "user_123",
                "access_token": mock_jwt_token,
                "refresh_token": "refresh_token_123",
                "token_type": "Bearer",
            }

            # Act
            response = client.post("/api/v1/auth/login", json=login_data)

            # Assert
            assert response.status_code == 200
            data = response.json()
            assert data["access_token"] == mock_jwt_token
            assert data["token_type"] == "Bearer"

    @pytest.mark.red
    def test_login_endpoint_invalid_credentials(self, client):
        """
        RED: Test login failure with invalid credentials.
        """
        # Arrange
        login_data = {
            "username": "trader1",
            "password": "WrongPassword!",  # pragma: allowlist secret
        }

        with patch(
            "core.api.auth.service.AuthenticationService.authenticate"
        ) as mock_auth:
            mock_auth.side_effect = InvalidCredentialsError(
                "Invalid username or password"
            )

            # Act
            response = client.post("/api/v1/auth/login", json=login_data)

            # Assert
            assert response.status_code == 401
            data = response.json()
            assert data["detail"] == "Invalid username or password"

    @pytest.mark.red
    def test_protected_endpoint_requires_auth(self, client):
        """
        RED: Test that protected endpoints require authentication.
        """
        # Act
        response = client.get("/api/v1/trading/positions")

        # Assert
        assert response.status_code == 401
        data = response.json()
        assert data["detail"] == "Not authenticated"

    @pytest.mark.red
    def test_protected_endpoint_with_valid_token(self, client, mock_jwt_token):
        """
        RED: Test accessing protected endpoint with valid token.
        """
        # Arrange
        headers = {"Authorization": f"Bearer {mock_jwt_token}"}

        with patch(
            "core.api.auth.service.AuthenticationService.verify_token"
        ) as mock_verify:
            mock_verify.return_value = "user_123"

            # Act
            response = client.get("/api/v1/trading/positions", headers=headers)

            # Assert
            assert response.status_code == 200
