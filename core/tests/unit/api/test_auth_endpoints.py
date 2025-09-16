"""
TDD Tests for Authentication API Endpoints

Tests the FastAPI endpoints that integrate with our TDD-validated
AuthenticationService. Following Red-Green-Refactor methodology.
"""

import os

# Import directly to avoid legacy imports
import sys
from unittest.mock import MagicMock, patch

import pytest
from fastapi import status
from fastapi.testclient import TestClient

# Import the router to test (avoid legacy auth import issues)
sys.path.append(os.path.join(os.path.dirname(__file__), "../../.."))

# Create test client
from fastapi import FastAPI

from core.api.auth.exceptions import (
    AuthenticationError,
    InvalidCredentialsError,
    TokenExpiredError,
    TwoFactorRequiredError,
)

# Import router directly from file to avoid legacy dependencies
from core.api.routers.auth_tdd import router

app = FastAPI()
app.include_router(router)
client = TestClient(app)


@pytest.mark.tdd
@pytest.mark.api
class TestAuthenticationEndpoints:
    """
    Test suite for authentication API endpoints.

    Tests HTTP layer integration with TDD-validated authentication service.
    """

    @pytest.mark.red
    def test_login_endpoint_success(self):
        """
        RED: Test successful login via API endpoint.
        """
        # Arrange
        login_data = {
            "username": "trader1",
            "password": "SecurePass123!",  # pragma: allowlist secret
        }

        expected_response = {
            "user_id": "user_123",
            "access_token": "mock_access_token",
            "refresh_token": "mock_refresh_token",
            "token_type": "Bearer",
            "expires_in": 3600,
        }

        with patch("core.api.routers.auth_tdd.auth_service.authenticate") as mock_auth:
            mock_auth.return_value = expected_response

            # Act
            response = client.post("/api/v1/auth/token", data=login_data)

            # Assert
            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["access_token"] == "mock_access_token"
            assert data["refresh_token"] == "mock_refresh_token"
            assert data["token_type"] == "Bearer"
            assert data["user_id"] == "user_123"

    @pytest.mark.red
    def test_login_endpoint_invalid_credentials(self):
        """
        RED: Test login failure with invalid credentials.
        """
        # Arrange
        login_data = {
            "username": "trader1",
            "password": "WrongPassword!",  # pragma: allowlist secret
        }

        with patch("core.api.routers.auth_tdd.auth_service.authenticate") as mock_auth:
            mock_auth.side_effect = InvalidCredentialsError(
                "Invalid username or password"
            )

            # Act
            response = client.post("/api/v1/auth/token", data=login_data)

            # Assert
            assert response.status_code == status.HTTP_401_UNAUTHORIZED
            data = response.json()
            assert "Invalid username or password" in str(data)

    @pytest.mark.red
    def test_login_endpoint_2fa_required(self):
        """
        RED: Test login with 2FA requirement.
        """
        # Arrange
        login_data = {
            "username": "trader1",
            "password": "SecurePass123!",  # pragma: allowlist secret
        }

        with patch("core.api.routers.auth_tdd.auth_service.authenticate") as mock_auth:
            mock_auth.side_effect = TwoFactorRequiredError(
                "Two-factor authentication required", temp_token="temp_token_123"
            )

            # Act
            response = client.post("/api/v1/auth/token", data=login_data)

            # Assert
            assert response.status_code == status.HTTP_423_LOCKED
            data = response.json()
            assert "2fa_pending" in str(data) or "temp_token" in str(data)

    @pytest.mark.red
    def test_2fa_verification_success(self):
        """
        RED: Test successful 2FA verification.
        """
        # Arrange
        verify_data = {"temp_token": "temp_token_123", "code": "123456"}

        expected_response = {
            "access_token": "final_access_token",
            "refresh_token": "final_refresh_token",
            "token_type": "Bearer",
            "expires_in": 3600,
        }

        with (
            patch("core.api.routers.auth_tdd.auth_service.verify_2fa") as mock_2fa,
            patch("core.api.routers.auth_tdd.auth_service.verify_token") as mock_verify,
        ):

            mock_2fa.return_value = expected_response
            mock_verify.return_value = "user_123"

            # Act
            response = client.post("/api/v1/auth/token/2fa", json=verify_data)

            # Assert
            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["access_token"] == "final_access_token"
            assert data["user_id"] == "user_123"

    @pytest.mark.red
    def test_2fa_verification_invalid_code(self):
        """
        RED: Test 2FA verification with invalid code.
        """
        # Arrange
        verify_data = {"temp_token": "temp_token_123", "code": "000000"}

        with patch("core.api.routers.auth_tdd.auth_service.verify_2fa") as mock_2fa:
            mock_2fa.side_effect = InvalidCredentialsError("Invalid 2FA code")

            # Act
            response = client.post("/api/v1/auth/token/2fa", json=verify_data)

            # Assert
            assert response.status_code == status.HTTP_401_UNAUTHORIZED
            data = response.json()
            assert "Invalid 2FA code" in str(data)

    @pytest.mark.red
    def test_token_refresh_success(self):
        """
        RED: Test successful token refresh.
        """
        # Arrange
        refresh_data = {"refresh_token": "valid_refresh_token"}

        expected_response = {
            "access_token": "new_access_token",
            "refresh_token": "new_refresh_token",
            "token_type": "Bearer",
            "expires_in": 3600,
        }

        with (
            patch(
                "core.api.routers.auth_tdd.auth_service.refresh_tokens"
            ) as mock_refresh,
            patch("core.api.routers.auth_tdd.auth_service.verify_token") as mock_verify,
        ):

            mock_refresh.return_value = expected_response
            mock_verify.return_value = "user_123"

            # Act
            response = client.post("/api/v1/auth/refresh", json=refresh_data)

            # Assert
            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["access_token"] == "new_access_token"
            assert data["user_id"] == "user_123"

    @pytest.mark.red
    def test_token_refresh_expired(self):
        """
        RED: Test token refresh with expired token.
        """
        # Arrange
        refresh_data = {"refresh_token": "expired_refresh_token"}

        with patch(
            "core.api.routers.auth_tdd.auth_service.refresh_tokens"
        ) as mock_refresh:
            mock_refresh.side_effect = TokenExpiredError("Refresh token has expired")

            # Act
            response = client.post("/api/v1/auth/refresh", json=refresh_data)

            # Assert
            assert response.status_code == status.HTTP_401_UNAUTHORIZED
            data = response.json()
            assert "expired" in str(data).lower()

    @pytest.mark.red
    def test_logout_success(self):
        """
        RED: Test successful logout.
        """
        # Arrange
        headers = {"Authorization": "Bearer valid_access_token"}

        with patch("core.api.routers.auth_tdd.auth_service.logout") as mock_logout:
            mock_logout.return_value = None

            # Act
            response = client.post("/api/v1/auth/logout", headers=headers)

            # Assert
            assert response.status_code == status.HTTP_204_NO_CONTENT
            mock_logout.assert_called_once_with("valid_access_token")

    @pytest.mark.red
    def test_logout_invalid_token(self):
        """
        RED: Test logout with invalid token.
        """
        # Arrange
        headers = {"Authorization": "Bearer invalid_token"}

        with patch("core.api.routers.auth_tdd.auth_service.logout") as mock_logout:
            mock_logout.side_effect = InvalidCredentialsError("Invalid token")

            # Act
            response = client.post("/api/v1/auth/logout", headers=headers)

            # Assert
            assert response.status_code == status.HTTP_401_UNAUTHORIZED

    @pytest.mark.red
    def test_verify_token_success(self):
        """
        RED: Test successful token verification.
        """
        # Arrange
        headers = {"Authorization": "Bearer valid_token"}

        with patch(
            "core.api.routers.auth_tdd.auth_service.verify_token"
        ) as mock_verify:
            mock_verify.return_value = "user_123"

            # Act
            response = client.get("/api/v1/auth/verify", headers=headers)

            # Assert
            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["valid"] is True
            assert data["user_id"] == "user_123"
            assert "verified_at" in data

    @pytest.mark.red
    def test_verify_token_invalid(self):
        """
        RED: Test token verification with invalid token.
        """
        # Arrange
        headers = {"Authorization": "Bearer invalid_token"}

        with patch(
            "core.api.routers.auth_tdd.auth_service.verify_token"
        ) as mock_verify:
            mock_verify.side_effect = InvalidCredentialsError("Invalid token")

            # Act
            response = client.get("/api/v1/auth/verify", headers=headers)

            # Assert
            assert response.status_code == status.HTTP_401_UNAUTHORIZED

    @pytest.mark.red
    def test_password_validation_success(self):
        """
        RED: Test password validation with valid password.
        """
        # Arrange
        password_data = {"password": "StrongPassword123!@#"}  # pragma: allowlist secret

        with patch(
            "core.api.routers.auth_tdd.auth_service.validate_password"
        ) as mock_validate:
            mock_validate.return_value = (True, "Password is valid")

            # Act
            response = client.post("/api/v1/auth/validate-password", json=password_data)

            # Assert
            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["is_valid"] is True
            assert data["message"] == "Password is valid"

    @pytest.mark.red
    def test_password_validation_weak(self):
        """
        RED: Test password validation with weak password.
        """
        # Arrange
        password_data = {"password": "weak"}  # pragma: allowlist secret

        with patch(
            "core.api.routers.auth_tdd.auth_service.validate_password"
        ) as mock_validate:
            mock_validate.return_value = (
                False,
                "Password must be at least 12 characters",  # pragma: allowlist secret
            )

            # Act
            response = client.post("/api/v1/auth/validate-password", json=password_data)

            # Assert
            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["is_valid"] is False
            assert "12 characters" in data["message"]

    @pytest.mark.red
    def test_create_session_success(self):
        """
        RED: Test successful session creation.
        """
        # Arrange
        headers = {"Authorization": "Bearer valid_token"}

        with (
            patch("core.api.routers.auth_tdd.auth_service.verify_token") as mock_verify,
            patch(
                "core.api.routers.auth_tdd.auth_service.create_session"
            ) as mock_create,
            patch(
                "core.api.routers.auth_tdd.auth_service.get_active_sessions"
            ) as mock_sessions,
        ):

            mock_verify.return_value = "user_123"
            mock_create.return_value = "session_456"
            mock_sessions.return_value = [
                {
                    "session_id": "session_456",
                    "user_id": "user_123",
                    "ip_address": "192.168.1.1",
                    "user_agent": "TestAgent/1.0",
                    "created_at": "2025-09-16T18:00:00",
                    "last_activity": "2025-09-16T18:00:00",
                }
            ]

            # Act
            response = client.post("/api/v1/auth/sessions", headers=headers)

            # Assert
            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["session_id"] == "session_456"
            assert data["user_id"] == "user_123"

    @pytest.mark.red
    def test_list_sessions_success(self):
        """
        RED: Test successful session listing.
        """
        # Arrange
        headers = {"Authorization": "Bearer valid_token"}

        with (
            patch("core.api.routers.auth_tdd.auth_service.verify_token") as mock_verify,
            patch(
                "core.api.routers.auth_tdd.auth_service.get_active_sessions"
            ) as mock_sessions,
        ):

            mock_verify.return_value = "user_123"
            mock_sessions.return_value = [
                {
                    "session_id": "session_1",
                    "user_id": "user_123",
                    "ip_address": "192.168.1.1",
                    "user_agent": "Browser/1.0",
                    "created_at": "2025-09-16T18:00:00",
                    "last_activity": "2025-09-16T18:00:00",
                },
                {
                    "session_id": "session_2",
                    "user_id": "user_123",
                    "ip_address": "192.168.1.2",
                    "user_agent": "Mobile/1.0",
                    "created_at": "2025-09-16T17:30:00",
                    "last_activity": "2025-09-16T17:45:00",
                },
            ]

            # Act
            response = client.get("/api/v1/auth/sessions", headers=headers)

            # Assert
            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert len(data) == 2
            assert data[0]["session_id"] == "session_1"
            assert data[1]["session_id"] == "session_2"

    @pytest.mark.red
    def test_health_check_endpoint(self):
        """
        RED: Test authentication service health check.
        """
        # Act
        response = client.get("/api/v1/auth/health")

        # Assert
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["status"] == "healthy"
        assert data["service"] == "authentication-tdd"
        assert data["tdd_validated"] is True
        assert "test_coverage" in data
        assert "timestamp" in data

    @pytest.mark.red
    def test_session_limit_exceeded(self):
        """
        RED: Test session creation when limit is exceeded.
        """
        # Arrange
        headers = {"Authorization": "Bearer valid_token"}

        with (
            patch("core.api.routers.auth_tdd.auth_service.verify_token") as mock_verify,
            patch(
                "core.api.routers.auth_tdd.auth_service.create_session"
            ) as mock_create,
        ):

            mock_verify.return_value = "user_123"
            mock_create.side_effect = AuthenticationError("Too many active sessions")

            # Act
            response = client.post("/api/v1/auth/sessions", headers=headers)

            # Assert
            assert response.status_code == status.HTTP_400_BAD_REQUEST
            data = response.json()
            assert "Too many active sessions" in str(data)


@pytest.mark.tdd
@pytest.mark.api
class TestAuthenticationEndpointSecurity:
    """
    Test suite for authentication endpoint security features.
    """

    @pytest.mark.red
    def test_missing_authorization_header(self):
        """
        RED: Test endpoints that require authentication without token.
        """
        # Test endpoints that require authentication
        endpoints = [
            ("/api/v1/auth/logout", "post"),
            ("/api/v1/auth/verify", "get"),
            ("/api/v1/auth/sessions", "post"),
            ("/api/v1/auth/sessions", "get"),
        ]

        for endpoint, method in endpoints:
            # Act
            if method == "get":
                response = client.get(endpoint)
            else:
                response = client.post(endpoint, json={})

            # Assert
            assert response.status_code == status.HTTP_401_UNAUTHORIZED

    @pytest.mark.red
    def test_malformed_authorization_header(self):
        """
        RED: Test with malformed authorization headers.
        """
        malformed_headers = [
            {"Authorization": "invalid_format"},
            {"Authorization": "Bearer"},  # Missing token
            {"Authorization": "Basic invalid"},  # Wrong scheme
        ]

        for headers in malformed_headers:
            # Act
            response = client.get("/api/v1/auth/verify", headers=headers)

            # Assert - Should return 422 for validation error or 401 for auth error
            assert response.status_code in [
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                status.HTTP_401_UNAUTHORIZED,
            ]

    @pytest.mark.red
    def test_invalid_request_data(self):
        """
        RED: Test endpoints with invalid request data.
        """
        # Test login with missing fields
        response = client.post("/api/v1/auth/token", data={})
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

        # Test 2FA with invalid data
        response = client.post("/api/v1/auth/token/2fa", json={"invalid": "data"})
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

        # Test refresh with missing token
        response = client.post("/api/v1/auth/refresh", json={})
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
