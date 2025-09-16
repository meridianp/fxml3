"""Test authentication functionality for FXML4 API.

This module tests the authentication functionality of the FXML4 API.
"""

import pytest
from fastapi.testclient import TestClient
from jose import jwt

from fxml4.api.auth.auth import ALGORITHM, SECRET_KEY
from fxml4.api.main import app

client = TestClient(app)


def test_login_for_access_token_valid_credentials():
    """Test login with valid credentials."""
    response = client.post("/token", data={"username": "user", "password": "password"})
    assert response.status_code == 200
    token_data = response.json()
    assert "access_token" in token_data
    assert token_data["token_type"] == "bearer"

    # Verify the token is valid
    decoded = jwt.decode(token_data["access_token"], SECRET_KEY, algorithms=[ALGORITHM])
    assert decoded["sub"] == "user"
    assert "scopes" in decoded


def test_login_for_access_token_invalid_credentials():
    """Test login with invalid credentials."""
    response = client.post(
        "/token", data={"username": "user", "password": "wrong_password"}
    )
    assert response.status_code == 401
    assert "detail" in response.json()


def test_login_for_access_token_invalid_username():
    """Test login with invalid username."""
    response = client.post(
        "/token", data={"username": "nonexistent_user", "password": "password"}
    )
    assert response.status_code == 401
    assert "detail" in response.json()


def test_read_users_me_authenticated():
    """Test getting current user information with valid token."""
    # First, get a token
    token_response = client.post(
        "/token", data={"username": "user", "password": "password"}
    )
    token = token_response.json()["access_token"]

    # Then use it to get user info
    response = client.get("/users/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    assert response.json()["username"] == "user"
    assert "scopes" in response.json()


def test_read_users_me_unauthenticated():
    """Test getting current user information without token."""
    response = client.get("/users/me")
    assert response.status_code == 401
    assert "detail" in response.json()


def test_read_users_me_invalid_token():
    """Test getting current user information with invalid token."""
    response = client.get(
        "/users/me", headers={"Authorization": "Bearer invalid_token"}
    )
    assert response.status_code == 401
    assert "detail" in response.json()


def test_admin_token_has_correct_scopes():
    """Test that admin token has the correct scopes."""
    response = client.post("/token", data={"username": "admin", "password": "password"})
    token = response.json()["access_token"]

    # Decode token
    decoded = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    assert "scopes" in decoded
    assert "admin" in decoded["scopes"]
    assert "user" in decoded["scopes"]
    assert "read" in decoded["scopes"]
    assert "write" in decoded["scopes"]


def test_user_token_has_correct_scopes():
    """Test that user token has the correct scopes."""
    response = client.post("/token", data={"username": "user", "password": "password"})
    token = response.json()["access_token"]

    # Decode token
    decoded = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    assert "scopes" in decoded
    assert "admin" not in decoded["scopes"]
    assert "user" in decoded["scopes"]
    assert "read" in decoded["scopes"]


# Pytest markers for test categorization
pytestmark = [pytest.mark.unit, pytest.mark.api, pytest.mark.auth, pytest.mark.fast]
