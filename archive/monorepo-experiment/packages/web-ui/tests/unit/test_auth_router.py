"""Tests for authentication router."""

import pytest
from datetime import datetime, timedelta, timezone
from fastapi import HTTPException, status
from fastapi.testclient import TestClient
from unittest.mock import Mock, patch, MagicMock
from jose import jwt, JWTError

from fxml4_web.api.routers.auth import (
    router, Token, TokenData, User, UserInDB,
    verify_password, get_password_hash, get_user, authenticate_user,
    create_access_token, get_current_user, get_current_active_user,
    SECRET_KEY, ALGORITHM, ACCESS_TOKEN_EXPIRE_MINUTES
)


@pytest.fixture
def test_user():
    """Create test user data."""
    return {
        "username": "testuser",
        "email": "test@example.com",
        "full_name": "Test User",
        "hashed_password": get_password_hash("testpass123"),
        "disabled": False
    }


@pytest.fixture
def test_user_db(test_user):
    """Create test user in DB format."""
    return UserInDB(**test_user)


@pytest.fixture
def valid_token(test_user):
    """Create valid JWT token."""
    return create_access_token(
        data={"sub": test_user["username"]},
        expires_delta=timedelta(minutes=30)
    )


@pytest.fixture
def expired_token(test_user):
    """Create expired JWT token."""
    return create_access_token(
        data={"sub": test_user["username"]},
        expires_delta=timedelta(minutes=-1)  # Already expired
    )


class TestPasswordUtils:
    """Test password utility functions."""
    
    def test_get_password_hash(self):
        """Test password hashing."""
        password = "testpassword123"
        hashed = get_password_hash(password)
        
        # Should return a hash
        assert hashed != password
        assert len(hashed) > 20
        assert "$" in hashed  # bcrypt format
    
    def test_verify_password_correct(self):
        """Test verifying correct password."""
        password = "correctpassword"
        hashed = get_password_hash(password)
        
        assert verify_password(password, hashed) is True
    
    def test_verify_password_incorrect(self):
        """Test verifying incorrect password."""
        password = "correctpassword"
        hashed = get_password_hash(password)
        
        assert verify_password("wrongpassword", hashed) is False
    
    def test_password_hash_uniqueness(self):
        """Test that same password generates different hashes."""
        password = "samepassword"
        hash1 = get_password_hash(password)
        hash2 = get_password_hash(password)
        
        # Should generate different hashes due to salt
        assert hash1 != hash2
        
        # But both should verify correctly
        assert verify_password(password, hash1) is True
        assert verify_password(password, hash2) is True


class TestUserFunctions:
    """Test user-related functions."""
    
    def test_get_user_exists(self, test_user):
        """Test getting existing user."""
        with patch('fxml4_web.api.routers.auth.fake_users_db', {test_user["username"]: test_user}):
            user = get_user(test_user["username"])
            
            assert user is not None
            assert isinstance(user, UserInDB)
            assert user.username == test_user["username"]
            assert user.email == test_user["email"]
    
    def test_get_user_not_exists(self):
        """Test getting non-existent user."""
        with patch('fxml4_web.api.routers.auth.fake_users_db', {}):
            user = get_user("nonexistent")
            assert user is None
    
    def test_authenticate_user_success(self, test_user):
        """Test successful user authentication."""
        with patch('fxml4_web.api.routers.auth.fake_users_db', {test_user["username"]: test_user}):
            user = authenticate_user(test_user["username"], "testpass123")
            
            assert user is not False
            assert isinstance(user, UserInDB)
            assert user.username == test_user["username"]
    
    def test_authenticate_user_wrong_password(self, test_user):
        """Test authentication with wrong password."""
        with patch('fxml4_web.api.routers.auth.fake_users_db', {test_user["username"]: test_user}):
            user = authenticate_user(test_user["username"], "wrongpassword")
            assert user is False
    
    def test_authenticate_user_not_exists(self):
        """Test authentication with non-existent user."""
        with patch('fxml4_web.api.routers.auth.fake_users_db', {}):
            user = authenticate_user("nonexistent", "anypassword")
            assert user is False


class TestTokenFunctions:
    """Test token-related functions."""
    
    def test_create_access_token_default_expiry(self):
        """Test creating token with default expiry."""
        data = {"sub": "testuser"}
        token = create_access_token(data)
        
        # Decode and verify
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        assert payload["sub"] == "testuser"
        assert "exp" in payload
        
        # Check expiry is in future (approximately 15 minutes)
        exp_time = datetime.fromtimestamp(payload["exp"], tz=timezone.utc)
        time_diff = exp_time - datetime.now(timezone.utc)
        assert 14 <= time_diff.total_seconds() / 60 <= 16
    
    def test_create_access_token_custom_expiry(self):
        """Test creating token with custom expiry."""
        data = {"sub": "testuser"}
        expires_delta = timedelta(hours=1)
        token = create_access_token(data, expires_delta)
        
        # Decode and verify
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        
        # Check expiry is approximately 1 hour
        exp_time = datetime.fromtimestamp(payload["exp"], tz=timezone.utc)
        time_diff = exp_time - datetime.now(timezone.utc)
        assert 59 <= time_diff.total_seconds() / 60 <= 61
    
    def test_create_access_token_additional_data(self):
        """Test creating token with additional data."""
        data = {
            "sub": "testuser",
            "scopes": ["read", "write"],
            "role": "admin"
        }
        token = create_access_token(data)
        
        # Decode and verify all data is preserved
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        assert payload["sub"] == "testuser"
        assert payload["scopes"] == ["read", "write"]
        assert payload["role"] == "admin"


class TestGetCurrentUser:
    """Test get_current_user dependency."""
    
    @pytest.mark.asyncio
    async def test_get_current_user_valid_token(self, valid_token, test_user):
        """Test getting current user with valid token."""
        with patch('fxml4_web.api.routers.auth.fake_users_db', {test_user["username"]: test_user}):
            user = await get_current_user(valid_token)
            
            assert isinstance(user, UserInDB)
            assert user.username == test_user["username"]
    
    @pytest.mark.asyncio
    async def test_get_current_user_invalid_token(self):
        """Test getting current user with invalid token."""
        with pytest.raises(HTTPException) as exc_info:
            await get_current_user("invalid-token")
        
        assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
        assert exc_info.value.detail == "Could not validate credentials"
    
    @pytest.mark.asyncio
    async def test_get_current_user_expired_token(self, expired_token):
        """Test getting current user with expired token."""
        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(expired_token)
        
        assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
    
    @pytest.mark.asyncio
    async def test_get_current_user_no_username_in_token(self):
        """Test token without username."""
        token = create_access_token(data={"different_field": "value"})
        
        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(token)
        
        assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
    
    @pytest.mark.asyncio
    async def test_get_current_user_nonexistent_user(self):
        """Test token for non-existent user."""
        token = create_access_token(data={"sub": "nonexistent"})
        
        with patch('fxml4_web.api.routers.auth.fake_users_db', {}):
            with pytest.raises(HTTPException) as exc_info:
                await get_current_user(token)
            
            assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED


class TestGetCurrentActiveUser:
    """Test get_current_active_user dependency."""
    
    @pytest.mark.asyncio
    async def test_get_current_active_user_active(self, test_user_db):
        """Test getting active user."""
        test_user_db.disabled = False
        user = await get_current_active_user(test_user_db)
        
        assert user == test_user_db
    
    @pytest.mark.asyncio
    async def test_get_current_active_user_disabled(self, test_user_db):
        """Test getting disabled user."""
        test_user_db.disabled = True
        
        with pytest.raises(HTTPException) as exc_info:
            await get_current_active_user(test_user_db)
        
        assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST
        assert exc_info.value.detail == "Inactive user"


class TestAuthEndpoints:
    """Test authentication endpoints."""
    
    @pytest.fixture
    def client(self):
        """Create test client."""
        from fastapi import FastAPI
        app = FastAPI()
        app.include_router(router)
        return TestClient(app)
    
    def test_login_success(self, client, test_user):
        """Test successful login."""
        with patch('fxml4_web.api.routers.auth.fake_users_db', {test_user["username"]: test_user}):
            response = client.post(
                "/token",
                data={
                    "username": test_user["username"],
                    "password": "testpass123"
                }
            )
            
            assert response.status_code == 200
            data = response.json()
            assert "access_token" in data
            assert data["token_type"] == "bearer"
            assert data["expires_in"] == ACCESS_TOKEN_EXPIRE_MINUTES * 60
    
    def test_login_wrong_password(self, client, test_user):
        """Test login with wrong password."""
        with patch('fxml4_web.api.routers.auth.fake_users_db', {test_user["username"]: test_user}):
            response = client.post(
                "/token",
                data={
                    "username": test_user["username"],
                    "password": "wrongpassword"
                }
            )
            
            assert response.status_code == 401
            assert response.json()["detail"] == "Incorrect username or password"
    
    def test_login_nonexistent_user(self, client):
        """Test login with non-existent user."""
        with patch('fxml4_web.api.routers.auth.fake_users_db', {}):
            response = client.post(
                "/token",
                data={
                    "username": "nonexistent",
                    "password": "anypassword"
                }
            )
            
            assert response.status_code == 401
            assert response.json()["detail"] == "Incorrect username or password"
    
    def test_get_me_authenticated(self, client, test_user, valid_token):
        """Test getting current user info when authenticated."""
        with patch('fxml4_web.api.routers.auth.fake_users_db', {test_user["username"]: test_user}):
            response = client.get(
                "/me",
                headers={"Authorization": f"Bearer {valid_token}"}
            )
            
            assert response.status_code == 200
            data = response.json()
            assert data["username"] == test_user["username"]
            assert data["email"] == test_user["email"]
            assert "hashed_password" not in data  # Should not expose password
    
    def test_get_me_unauthenticated(self, client):
        """Test getting current user info without authentication."""
        response = client.get("/me")
        assert response.status_code == 401
        assert response.json()["detail"] == "Not authenticated"
    
    def test_get_me_invalid_token(self, client):
        """Test getting current user info with invalid token."""
        response = client.get(
            "/me",
            headers={"Authorization": "Bearer invalid-token"}
        )
        assert response.status_code == 401
        assert response.json()["detail"] == "Could not validate credentials"


class TestModels:
    """Test Pydantic models."""
    
    def test_token_model(self):
        """Test Token model."""
        token = Token(
            access_token="test-token",
            token_type="bearer",
            expires_in=1800
        )
        
        assert token.access_token == "test-token"
        assert token.token_type == "bearer"
        assert token.expires_in == 1800
    
    def test_token_data_model(self):
        """Test TokenData model."""
        # With username
        token_data = TokenData(username="testuser")
        assert token_data.username == "testuser"
        
        # Without username (optional)
        token_data = TokenData()
        assert token_data.username is None
    
    def test_user_model(self):
        """Test User model."""
        user = User(
            username="testuser",
            email="test@example.com",
            full_name="Test User",
            disabled=False
        )
        
        assert user.username == "testuser"
        assert user.email == "test@example.com"
        assert user.full_name == "Test User"
        assert user.disabled is False
        
        # Test with minimal data
        user = User(username="minimal")
        assert user.username == "minimal"
        assert user.email is None
        assert user.full_name is None
        assert user.disabled is None
    
    def test_user_in_db_model(self):
        """Test UserInDB model."""
        user_db = UserInDB(
            username="testuser",
            email="test@example.com",
            full_name="Test User",
            disabled=False,
            hashed_password="$2b$12$hashedpassword"
        )
        
        assert user_db.username == "testuser"
        assert user_db.hashed_password == "$2b$12$hashedpassword"
        assert isinstance(user_db, User)  # Should inherit from User