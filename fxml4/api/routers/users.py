"""
User management API endpoints.

This module provides REST API endpoints for user management operations.
"""

import json
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel, EmailStr, Field, validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from fxml4.api.auth.auth import get_current_user, require_role
from fxml4.api.auth.database import get_db
from fxml4.api.auth.models import Role, User
from fxml4.api.auth.service import AuthenticationService, PasswordPolicyError

router = APIRouter(
    prefix="/api/v1/users",
    tags=["users"],
    responses={404: {"description": "Not found"}},
)


# Pydantic models
class UserCreate(BaseModel):
    """User creation request."""

    username: str = Field(..., min_length=3, max_length=50, regex="^[a-zA-Z0-9_-]+$")
    email: EmailStr
    password: str = Field(..., min_length=8)
    full_name: Optional[str] = Field(None, max_length=255)
    roles: Optional[List[str]] = Field(default_factory=list)

    @validator("username")
    def username_valid(cls, v):
        if v.lower() in ["admin", "root", "system"]:
            raise ValueError("Reserved username")
        return v


class UserUpdate(BaseModel):
    """User update request."""

    email: Optional[EmailStr] = None
    full_name: Optional[str] = Field(None, max_length=255)
    is_active: Optional[bool] = None
    roles: Optional[List[str]] = None


class UserResponse(BaseModel):
    """User response model."""

    id: str
    username: str
    email: str
    full_name: Optional[str]
    is_active: bool
    is_verified: bool
    totp_enabled: bool
    roles: List[str]
    created_at: datetime
    last_login: Optional[datetime]

    class Config:
        from_attributes = True


class PasswordChange(BaseModel):
    """Password change request."""

    current_password: str
    new_password: str = Field(..., min_length=8)


class APIKeyCreate(BaseModel):
    """API key creation request."""

    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=255)
    permissions: Optional[List[str]] = Field(default_factory=list)
    expires_in_days: Optional[int] = Field(None, ge=1, le=365)


class APIKeyResponse(BaseModel):
    """API key response model."""

    id: str
    name: str
    description: Optional[str]
    permissions: List[str]
    is_active: bool
    expires_at: Optional[datetime]
    created_at: datetime
    last_used_at: Optional[datetime]
    key: Optional[str] = None  # Only returned on creation

    class Config:
        from_attributes = True


class TwoFactorSetupResponse(BaseModel):
    """2FA setup response."""

    provisioning_uri: str
    backup_codes: List[str]


class TwoFactorVerifyRequest(BaseModel):
    """2FA verification request."""

    token: str = Field(..., min_length=6, max_length=6)


# Endpoints
@router.post("/", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(
    user_data: UserCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
):
    """
    Create a new user (admin only).
    """
    try:
        user = await AuthenticationService.create_user(
            db=db,
            username=user_data.username,
            email=user_data.email,
            password=user_data.password,
            full_name=user_data.full_name,
            role_names=user_data.roles,
        )

        # Log event
        await AuthenticationService._log_auth_event(
            db,
            current_user.id,
            "user_created",
            True,
            {"created_user_id": str(user.id), "username": user.username},
            request.client.host if request.client else None,
            request.headers.get("user-agent"),
        )
        await db.commit()

        return UserResponse(
            id=str(user.id),
            username=user.username,
            email=user.email,
            full_name=user.full_name,
            is_active=user.is_active,
            is_verified=user.is_verified,
            totp_enabled=user.totp_enabled,
            roles=[role.name for role in user.roles],
            created_at=user.created_at,
            last_login=user.last_login,
        )

    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except PasswordPolicyError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/", response_model=List[UserResponse])
async def list_users(
    skip: int = 0,
    limit: int = 100,
    is_active: Optional[bool] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
):
    """
    List all users (admin only).
    """
    query = select(User)

    if is_active is not None:
        query = query.where(User.is_active == is_active)

    query = query.offset(skip).limit(limit)

    result = await db.execute(query)
    users = result.scalars().all()

    return [
        UserResponse(
            id=str(user.id),
            username=user.username,
            email=user.email,
            full_name=user.full_name,
            is_active=user.is_active,
            is_verified=user.is_verified,
            totp_enabled=user.totp_enabled,
            roles=[role.name for role in user.roles],
            created_at=user.created_at,
            last_login=user.last_login,
        )
        for user in users
    ]


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(current_user: User = Depends(get_current_user)):
    """
    Get current user information.
    """
    return UserResponse(
        id=str(current_user.id),
        username=current_user.username,
        email=current_user.email,
        full_name=current_user.full_name,
        is_active=current_user.is_active,
        is_verified=current_user.is_verified,
        totp_enabled=current_user.totp_enabled,
        roles=[role.name for role in current_user.roles],
        created_at=current_user.created_at,
        last_login=current_user.last_login,
    )


@router.get("/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
):
    """
    Get user by ID (admin only).
    """
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )

    return UserResponse(
        id=str(user.id),
        username=user.username,
        email=user.email,
        full_name=user.full_name,
        is_active=user.is_active,
        is_verified=user.is_verified,
        totp_enabled=user.totp_enabled,
        roles=[role.name for role in user.roles],
        created_at=user.created_at,
        last_login=user.last_login,
    )


@router.patch("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: str,
    user_update: UserUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
):
    """
    Update user (admin only).
    """
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )

    # Update fields
    if user_update.email is not None:
        user.email = user_update.email
    if user_update.full_name is not None:
        user.full_name = user_update.full_name
    if user_update.is_active is not None:
        user.is_active = user_update.is_active

    # Update roles
    if user_update.roles is not None:
        result = await db.execute(select(Role).where(Role.name.in_(user_update.roles)))
        roles = result.scalars().all()
        user.roles = roles

    user.updated_at = datetime.now(timezone.utc)

    # Log event
    await AuthenticationService._log_auth_event(
        db,
        current_user.id,
        "user_updated",
        True,
        {
            "updated_user_id": str(user.id),
            "updates": user_update.dict(exclude_unset=True),
        },
        request.client.host if request.client else None,
        request.headers.get("user-agent"),
    )

    await db.commit()
    await db.refresh(user)

    return UserResponse(
        id=str(user.id),
        username=user.username,
        email=user.email,
        full_name=user.full_name,
        is_active=user.is_active,
        is_verified=user.is_verified,
        totp_enabled=user.totp_enabled,
        roles=[role.name for role in user.roles],
        created_at=user.created_at,
        last_login=user.last_login,
    )


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
):
    """
    Delete user (admin only).
    """
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )

    # Prevent deleting self
    if str(user.id) == str(current_user.id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot delete self"
        )

    # Log event
    await AuthenticationService._log_auth_event(
        db,
        current_user.id,
        "user_deleted",
        True,
        {"deleted_user_id": str(user.id), "username": user.username},
        request.client.host if request.client else None,
        request.headers.get("user-agent"),
    )

    await db.delete(user)
    await db.commit()


@router.post("/me/password", status_code=status.HTTP_204_NO_CONTENT)
async def change_password(
    password_data: PasswordChange,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Change current user's password.
    """
    # Verify current password
    if not AuthenticationService.verify_password(
        password_data.current_password, current_user.hashed_password
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect",
        )

    # Validate new password
    try:
        AuthenticationService.validate_password_policy(
            password_data.new_password, current_user.username
        )
    except PasswordPolicyError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    # Check password history
    if current_user.password_history:
        history = json.loads(current_user.password_history)
        for old_hash in history[-PASSWORD_HISTORY_COUNT:]:
            if AuthenticationService.verify_password(
                password_data.new_password, old_hash
            ):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Password has been used recently",
                )

    # Update password
    new_hash = AuthenticationService.get_password_hash(password_data.new_password)
    current_user.hashed_password = new_hash
    current_user.password_changed_at = datetime.now(timezone.utc)
    current_user.must_change_password = False

    # Update password history
    if current_user.password_history:
        history = json.loads(current_user.password_history)
    else:
        history = []
    history.append(new_hash)
    current_user.password_history = json.dumps(history[-PASSWORD_HISTORY_COUNT:])

    # Log event
    await AuthenticationService._log_auth_event(
        db,
        current_user.id,
        "password_changed",
        True,
        {},
        request.client.host if request.client else None,
        request.headers.get("user-agent"),
    )

    await db.commit()


@router.post("/me/2fa/setup", response_model=TwoFactorSetupResponse)
async def setup_2fa(
    db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)
):
    """
    Set up two-factor authentication.
    """
    if current_user.totp_enabled:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="2FA already enabled"
        )

    provisioning_uri, backup_codes = await AuthenticationService.setup_2fa(
        db, str(current_user.id)
    )

    return TwoFactorSetupResponse(
        provisioning_uri=provisioning_uri, backup_codes=backup_codes
    )


@router.post("/me/2fa/verify", status_code=status.HTTP_204_NO_CONTENT)
async def verify_2fa(
    verification: TwoFactorVerifyRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Verify and enable two-factor authentication.
    """
    if not current_user.totp_secret:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="2FA not set up"
        )

    if not await AuthenticationService.verify_2fa(
        db, str(current_user.id), verification.token
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid verification code"
        )


@router.post(
    "/me/api-keys", response_model=APIKeyResponse, status_code=status.HTTP_201_CREATED
)
async def create_api_key(
    api_key_data: APIKeyCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Create API key for current user.
    """
    # Verify user has necessary permissions
    user_permissions = []
    for role in current_user.roles:
        if role.permissions:
            perms = json.loads(role.permissions)
            user_permissions.extend(perms)

    # Check if requested permissions are subset of user permissions
    if api_key_data.permissions:
        for perm in api_key_data.permissions:
            if perm not in user_permissions and "*" not in user_permissions:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"User does not have permission: {perm}",
                )

    raw_key, api_key = await AuthenticationService.create_api_key(
        db=db,
        user_id=str(current_user.id),
        name=api_key_data.name,
        description=api_key_data.description,
        permissions=api_key_data.permissions,
        expires_in_days=api_key_data.expires_in_days,
    )

    return APIKeyResponse(
        id=str(api_key.id),
        name=api_key.name,
        description=api_key.description,
        permissions=json.loads(api_key.permissions) if api_key.permissions else [],
        is_active=api_key.is_active,
        expires_at=api_key.expires_at,
        created_at=api_key.created_at,
        last_used_at=api_key.last_used_at,
        key=raw_key,  # Only returned on creation
    )


@router.get("/me/api-keys", response_model=List[APIKeyResponse])
async def list_api_keys(
    db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)
):
    """
    List current user's API keys.
    """
    result = await db.execute(select(APIKey).where(APIKey.user_id == current_user.id))
    api_keys = result.scalars().all()

    return [
        APIKeyResponse(
            id=str(api_key.id),
            name=api_key.name,
            description=api_key.description,
            permissions=json.loads(api_key.permissions) if api_key.permissions else [],
            is_active=api_key.is_active,
            expires_at=api_key.expires_at,
            created_at=api_key.created_at,
            last_used_at=api_key.last_used_at,
        )
        for api_key in api_keys
    ]


@router.delete("/me/api-keys/{key_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_api_key(
    key_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Delete API key.
    """
    result = await db.execute(
        select(APIKey).where(
            and_(APIKey.id == key_id, APIKey.user_id == current_user.id)
        )
    )
    api_key = result.scalar_one_or_none()

    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="API key not found"
        )

    await db.delete(api_key)
    await db.commit()


# Import constants from service module
from fxml4.api.auth.service import PASSWORD_HISTORY_COUNT
