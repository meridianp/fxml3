"""
User Management API Router for FXML4.

This module provides comprehensive user management endpoints for administrators,
including CRUD operations, role management, and bulk operations.
"""

import csv
import io
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import and_, desc, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from fxml4.api.auth.audit_logger import AuditEventType, auth_audit_logger
from fxml4.api.auth.database import get_db
from fxml4.api.auth.models import DEFAULT_ROLES, APIKey, AuthAuditLog, Role, User
from fxml4.api.auth.permissions import (
    PermissionLevel,
    check_admin_access,
    check_risk_manager_access,
    permission_checker,
)
from fxml4.api.auth.service import AuthenticationService, PasswordPolicyError

router = APIRouter(
    prefix="/api/v1/admin",
    tags=["user_management"],
    dependencies=[Depends(check_admin_access)],  # All endpoints require admin access
    responses={404: {"description": "Not found"}},
)


# Pydantic models for requests/responses
class UserCreateRequest(BaseModel):
    """Request model for creating a new user."""

    username: str = Field(..., min_length=3, max_length=50)
    email: EmailStr
    password: str = Field(..., min_length=8)
    full_name: Optional[str] = Field(None, max_length=255)
    role_names: Optional[List[str]] = Field(default=["viewer"])
    is_active: bool = Field(default=True)
    must_change_password: bool = Field(default=True)


class UserUpdateRequest(BaseModel):
    """Request model for updating a user."""

    email: Optional[EmailStr] = None
    full_name: Optional[str] = Field(None, max_length=255)
    is_active: Optional[bool] = None
    is_verified: Optional[bool] = None
    must_change_password: Optional[bool] = None


class UserResponse(BaseModel):
    """Response model for user information."""

    id: str
    username: str
    email: str
    full_name: Optional[str]
    is_active: bool
    is_verified: bool
    is_locked: bool
    must_change_password: bool
    totp_enabled: bool
    failed_login_attempts: int
    last_login: Optional[datetime]
    last_activity: Optional[datetime]
    password_changed_at: Optional[datetime]
    created_at: datetime
    updated_at: Optional[datetime]
    roles: List[str]
    effective_permissions: List[str]

    class Config:
        from_attributes = True


class UserListResponse(BaseModel):
    """Response model for user list."""

    users: List[UserResponse]
    total_count: int
    page: int
    page_size: int
    total_pages: int


class RoleAssignmentRequest(BaseModel):
    """Request model for role assignment."""

    role_names: List[str] = Field(..., min_items=1)


class BulkUserCreateRequest(BaseModel):
    """Request model for bulk user creation."""

    users: List[UserCreateRequest] = Field(..., max_items=100)  # Limit bulk operations


class BulkUserUpdateRequest(BaseModel):
    """Request model for bulk user updates."""

    user_ids: List[str] = Field(..., max_items=100)
    update_data: UserUpdateRequest


class BulkRoleAssignmentRequest(BaseModel):
    """Request model for bulk role assignment."""

    user_ids: List[str] = Field(..., max_items=100)
    role_names: List[str] = Field(..., min_items=1)


class UserStatsResponse(BaseModel):
    """Response model for user statistics."""

    total_users: int
    active_users: int
    inactive_users: int
    locked_users: int
    users_with_2fa: int
    users_by_role: Dict[str, int]
    recent_logins: int  # Last 24 hours
    pending_verification: int


# ===== USER CRUD OPERATIONS =====


@router.get("/users", response_model=UserListResponse)
async def list_users(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(check_admin_access),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(50, ge=1, le=100, description="Page size"),
    search: Optional[str] = Query(
        None, description="Search by username, email, or full name"
    ),
    role_filter: Optional[str] = Query(None, description="Filter by role"),
    status_filter: Optional[str] = Query(
        None, description="Filter by status: active, inactive, locked"
    ),
    sort_by: str = Query("created_at", description="Sort field"),
    sort_order: str = Query("desc", description="Sort order: asc, desc"),
):
    """
    List users with pagination, search, and filtering.

    Requires admin access.
    """
    try:
        # Build base query
        query = select(User).options(selectinload(User.roles))

        # Apply search filter
        if search:
            search_term = f"%{search}%"
            query = query.where(
                or_(
                    User.username.ilike(search_term),
                    User.email.ilike(search_term),
                    User.full_name.ilike(search_term),
                )
            )

        # Apply role filter
        if role_filter:
            query = query.join(User.roles).where(Role.name == role_filter)

        # Apply status filter
        if status_filter:
            if status_filter == "active":
                query = query.where(User.is_active == True)
            elif status_filter == "inactive":
                query = query.where(User.is_active == False)
            elif status_filter == "locked":
                query = query.where(User.is_locked == True)

        # Apply sorting
        sort_field = getattr(User, sort_by, User.created_at)
        if sort_order.lower() == "desc":
            query = query.order_by(desc(sort_field))
        else:
            query = query.order_by(sort_field)

        # Get total count
        count_query = select(func.count()).select_from(query.subquery())
        total_result = await db.execute(count_query)
        total_count = total_result.scalar()

        # Apply pagination
        offset = (page - 1) * page_size
        query = query.offset(offset).limit(page_size)

        # Execute query
        result = await db.execute(query)
        users = result.scalars().all()

        # Convert to response format
        user_responses = []
        for user in users:
            effective_permissions = list(
                permission_checker.get_user_effective_permissions(user)
            )
            user_response = UserResponse(
                id=str(user.id),
                username=user.username,
                email=user.email,
                full_name=user.full_name,
                is_active=user.is_active,
                is_verified=user.is_verified,
                is_locked=user.is_locked,
                must_change_password=user.must_change_password or False,
                totp_enabled=user.totp_enabled or False,
                failed_login_attempts=user.failed_login_attempts or 0,
                last_login=user.last_login,
                last_activity=user.last_activity,
                password_changed_at=user.password_changed_at,
                created_at=user.created_at,
                updated_at=user.updated_at,
                roles=[role.name for role in user.roles],
                effective_permissions=effective_permissions,
            )
            user_responses.append(user_response)

        total_pages = (total_count + page_size - 1) // page_size

        # Log admin action
        auth_audit_logger.log_api_access(
            username=current_user.username,
            endpoint="/admin/users",
            method="GET",
            status_code=200,
            request=request,
            details={
                "search": search,
                "filters": {"role": role_filter, "status": status_filter},
                "results_count": len(user_responses),
            },
        )

        return UserListResponse(
            users=user_responses,
            total_count=total_count,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error listing users: {str(e)}",
        )


@router.post("/users", response_model=UserResponse)
async def create_user(
    request: Request,
    user_data: UserCreateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(check_admin_access),
):
    """
    Create a new user.

    Requires admin access.
    """
    try:
        # Create user using authentication service
        new_user = await AuthenticationService.create_user(
            db=db,
            username=user_data.username,
            email=user_data.email,
            password=user_data.password,
            full_name=user_data.full_name,
            role_names=user_data.role_names,
        )

        # Set additional attributes
        new_user.is_active = user_data.is_active
        new_user.must_change_password = user_data.must_change_password

        await db.commit()
        await db.refresh(new_user)

        # Get effective permissions
        effective_permissions = list(
            permission_checker.get_user_effective_permissions(new_user)
        )

        # Log user creation
        auth_audit_logger.log_api_access(
            username=current_user.username,
            endpoint="/admin/users",
            method="POST",
            status_code=201,
            request=request,
            details={
                "created_user_id": str(new_user.id),
                "created_username": new_user.username,
                "assigned_roles": user_data.role_names,
            },
        )

        return UserResponse(
            id=str(new_user.id),
            username=new_user.username,
            email=new_user.email,
            full_name=new_user.full_name,
            is_active=new_user.is_active,
            is_verified=new_user.is_verified,
            is_locked=new_user.is_locked,
            must_change_password=new_user.must_change_password or False,
            totp_enabled=new_user.totp_enabled or False,
            failed_login_attempts=new_user.failed_login_attempts or 0,
            last_login=new_user.last_login,
            last_activity=new_user.last_activity,
            password_changed_at=new_user.password_changed_at,
            created_at=new_user.created_at,
            updated_at=new_user.updated_at,
            roles=[role.name for role in new_user.roles],
            effective_permissions=effective_permissions,
        )

    except PasswordPolicyError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Password policy violation: {str(e)}",
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error creating user: {str(e)}",
        )


@router.get("/users/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(check_admin_access),
):
    """
    Get user details by ID.

    Requires admin access.
    """
    try:
        # Get user with roles
        query = select(User).options(selectinload(User.roles)).where(User.id == user_id)
        result = await db.execute(query)
        user = result.scalar_one_or_none()

        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
            )

        # Get effective permissions
        effective_permissions = list(
            permission_checker.get_user_effective_permissions(user)
        )

        return UserResponse(
            id=str(user.id),
            username=user.username,
            email=user.email,
            full_name=user.full_name,
            is_active=user.is_active,
            is_verified=user.is_verified,
            is_locked=user.is_locked,
            must_change_password=user.must_change_password or False,
            totp_enabled=user.totp_enabled or False,
            failed_login_attempts=user.failed_login_attempts or 0,
            last_login=user.last_login,
            last_activity=user.last_activity,
            password_changed_at=user.password_changed_at,
            created_at=user.created_at,
            updated_at=user.updated_at,
            roles=[role.name for role in user.roles],
            effective_permissions=effective_permissions,
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving user: {str(e)}",
        )


@router.put("/users/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: str,
    user_data: UserUpdateRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(check_admin_access),
):
    """
    Update user information.

    Requires admin access.
    """
    try:
        # Get user
        query = select(User).options(selectinload(User.roles)).where(User.id == user_id)
        result = await db.execute(query)
        user = result.scalar_one_or_none()

        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
            )

        # Update fields
        update_fields = {}
        if user_data.email is not None:
            user.email = user_data.email
            update_fields["email"] = user_data.email
        if user_data.full_name is not None:
            user.full_name = user_data.full_name
            update_fields["full_name"] = user_data.full_name
        if user_data.is_active is not None:
            user.is_active = user_data.is_active
            update_fields["is_active"] = user_data.is_active
        if user_data.is_verified is not None:
            user.is_verified = user_data.is_verified
            update_fields["is_verified"] = user_data.is_verified
        if user_data.must_change_password is not None:
            user.must_change_password = user_data.must_change_password
            update_fields["must_change_password"] = user_data.must_change_password

        user.updated_at = datetime.now(timezone.utc)

        await db.commit()
        await db.refresh(user)

        # Get effective permissions
        effective_permissions = list(
            permission_checker.get_user_effective_permissions(user)
        )

        # Log user update
        auth_audit_logger.log_api_access(
            username=current_user.username,
            endpoint=f"/admin/users/{user_id}",
            method="PUT",
            status_code=200,
            request=request,
            details={
                "updated_user_id": user_id,
                "updated_username": user.username,
                "updated_fields": update_fields,
            },
        )

        return UserResponse(
            id=str(user.id),
            username=user.username,
            email=user.email,
            full_name=user.full_name,
            is_active=user.is_active,
            is_verified=user.is_verified,
            is_locked=user.is_locked,
            must_change_password=user.must_change_password or False,
            totp_enabled=user.totp_enabled or False,
            failed_login_attempts=user.failed_login_attempts or 0,
            last_login=user.last_login,
            last_activity=user.last_activity,
            password_changed_at=user.password_changed_at,
            created_at=user.created_at,
            updated_at=user.updated_at,
            roles=[role.name for role in user.roles],
            effective_permissions=effective_permissions,
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error updating user: {str(e)}",
        )


@router.delete("/users/{user_id}")
async def delete_user(
    user_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(check_admin_access),
):
    """
    Delete user (soft delete by deactivating).

    Requires admin access.
    """
    try:
        # Prevent self-deletion
        if str(current_user.id) == user_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot delete your own account",
            )

        # Get user
        query = select(User).where(User.id == user_id)
        result = await db.execute(query)
        user = result.scalar_one_or_none()

        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
            )

        # Soft delete by deactivating
        user.is_active = False
        user.updated_at = datetime.now(timezone.utc)

        await db.commit()

        # Log user deletion
        auth_audit_logger.log_api_access(
            username=current_user.username,
            endpoint=f"/admin/users/{user_id}",
            method="DELETE",
            status_code=200,
            request=request,
            details={
                "deleted_user_id": user_id,
                "deleted_username": user.username,
                "action": "soft_delete",
            },
        )

        return {"message": "User deactivated successfully"}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error deleting user: {str(e)}",
        )


# ===== USER STATUS MANAGEMENT =====


@router.post("/users/{user_id}/activate")
async def activate_user(
    user_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(check_admin_access),
):
    """Activate a deactivated user."""
    try:
        query = select(User).where(User.id == user_id)
        result = await db.execute(query)
        user = result.scalar_one_or_none()

        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
            )

        user.is_active = True
        user.updated_at = datetime.now(timezone.utc)

        await db.commit()

        # Log activation
        auth_audit_logger.log_api_access(
            username=current_user.username,
            endpoint=f"/admin/users/{user_id}/activate",
            method="POST",
            status_code=200,
            request=request,
            details={"activated_user_id": user_id, "activated_username": user.username},
        )

        return {"message": "User activated successfully"}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error activating user: {str(e)}",
        )


@router.post("/users/{user_id}/deactivate")
async def deactivate_user(
    user_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(check_admin_access),
):
    """Deactivate a user."""
    try:
        # Prevent self-deactivation
        if str(current_user.id) == user_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot deactivate your own account",
            )

        query = select(User).where(User.id == user_id)
        result = await db.execute(query)
        user = result.scalar_one_or_none()

        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
            )

        user.is_active = False
        user.updated_at = datetime.now(timezone.utc)

        await db.commit()

        return {"message": "User deactivated successfully"}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error deactivating user: {str(e)}",
        )


@router.post("/users/{user_id}/unlock")
async def unlock_user(
    user_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(check_admin_access),
):
    """Unlock a locked user account."""
    try:
        query = select(User).where(User.id == user_id)
        result = await db.execute(query)
        user = result.scalar_one_or_none()

        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
            )

        user.is_locked = False
        user.failed_login_attempts = 0
        user.last_failed_login = None
        user.updated_at = datetime.now(timezone.utc)

        await db.commit()

        # Log unlock
        auth_audit_logger.log_api_access(
            username=current_user.username,
            endpoint=f"/admin/users/{user_id}/unlock",
            method="POST",
            status_code=200,
            request=request,
            details={"unlocked_user_id": user_id, "unlocked_username": user.username},
        )

        return {"message": "User account unlocked successfully"}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error unlocking user: {str(e)}",
        )


# ===== ROLE MANAGEMENT =====


@router.get("/roles")
async def list_roles(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(check_admin_access),
):
    """List all available roles."""
    try:
        query = select(Role).order_by(Role.name)
        result = await db.execute(query)
        roles = result.scalars().all()

        roles_data = []
        for role in roles:
            permissions = []
            if role.permissions:
                try:
                    import json

                    permissions = (
                        json.loads(role.permissions)
                        if isinstance(role.permissions, str)
                        else role.permissions
                    )
                except (json.JSONDecodeError, TypeError):
                    permissions = [role.permissions] if role.permissions else []

            roles_data.append(
                {
                    "id": str(role.id),
                    "name": role.name,
                    "description": role.description,
                    "permissions": permissions,
                    "created_at": role.created_at,
                }
            )

        return {"roles": roles_data}

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error listing roles: {str(e)}",
        )


@router.post("/users/{user_id}/roles")
async def assign_roles_to_user(
    user_id: str,
    role_data: RoleAssignmentRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(check_admin_access),
):
    """Assign roles to user."""
    try:
        # Get user
        query = select(User).options(selectinload(User.roles)).where(User.id == user_id)
        result = await db.execute(query)
        user = result.scalar_one_or_none()

        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
            )

        # Get roles
        roles_query = select(Role).where(Role.name.in_(role_data.role_names))
        roles_result = await db.execute(roles_query)
        roles = roles_result.scalars().all()

        if len(roles) != len(role_data.role_names):
            found_role_names = [role.name for role in roles]
            missing_roles = set(role_data.role_names) - set(found_role_names)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Roles not found: {', '.join(missing_roles)}",
            )

        # Assign roles (replace existing)
        user.roles = roles
        user.updated_at = datetime.now(timezone.utc)

        await db.commit()

        # Log role assignment
        auth_audit_logger.log_api_access(
            username=current_user.username,
            endpoint=f"/admin/users/{user_id}/roles",
            method="POST",
            status_code=200,
            request=request,
            details={
                "target_user_id": user_id,
                "target_username": user.username,
                "assigned_roles": role_data.role_names,
            },
        )

        return {"message": f"Roles assigned successfully to user {user.username}"}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error assigning roles: {str(e)}",
        )


@router.delete("/users/{user_id}/roles/{role_id}")
async def remove_role_from_user(
    user_id: str,
    role_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(check_admin_access),
):
    """Remove specific role from user."""
    try:
        # Get user with roles
        query = select(User).options(selectinload(User.roles)).where(User.id == user_id)
        result = await db.execute(query)
        user = result.scalar_one_or_none()

        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
            )

        # Find and remove the role
        role_to_remove = None
        for role in user.roles:
            if str(role.id) == role_id:
                role_to_remove = role
                break

        if not role_to_remove:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Role not found for this user",
            )

        user.roles.remove(role_to_remove)
        user.updated_at = datetime.now(timezone.utc)

        await db.commit()

        # Log role removal
        auth_audit_logger.log_api_access(
            username=current_user.username,
            endpoint=f"/admin/users/{user_id}/roles/{role_id}",
            method="DELETE",
            status_code=200,
            request=request,
            details={
                "target_user_id": user_id,
                "target_username": user.username,
                "removed_role": role_to_remove.name,
            },
        )

        return {
            "message": f"Role {role_to_remove.name} removed from user {user.username}"
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error removing role: {str(e)}",
        )


@router.get("/users/{user_id}/permissions")
async def get_user_permissions(
    user_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(check_admin_access),
):
    """Get user's effective permissions."""
    try:
        # Get user with roles
        query = select(User).options(selectinload(User.roles)).where(User.id == user_id)
        result = await db.execute(query)
        user = result.scalar_one_or_none()

        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
            )

        effective_permissions = list(
            permission_checker.get_user_effective_permissions(user)
        )
        role_level = permission_checker.get_user_highest_role_level(user)

        return {
            "user_id": str(user.id),
            "username": user.username,
            "roles": [role.name for role in user.roles],
            "effective_permissions": effective_permissions,
            "permission_level": role_level,
            "is_admin": permission_checker.check_role_hierarchy(
                user, PermissionLevel.ADMIN
            ),
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving user permissions: {str(e)}",
        )


# ===== BULK OPERATIONS =====


@router.post("/users/bulk-create")
async def bulk_create_users(
    bulk_data: BulkUserCreateRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(check_admin_access),
):
    """Bulk create users."""
    try:
        created_users = []
        errors = []

        for i, user_data in enumerate(bulk_data.users):
            try:
                # Create user
                new_user = await AuthenticationService.create_user(
                    db=db,
                    username=user_data.username,
                    email=user_data.email,
                    password=user_data.password,
                    full_name=user_data.full_name,
                    role_names=user_data.role_names,
                )

                new_user.is_active = user_data.is_active
                new_user.must_change_password = user_data.must_change_password

                created_users.append(
                    {
                        "index": i,
                        "user_id": str(new_user.id),
                        "username": new_user.username,
                        "status": "created",
                    }
                )

            except Exception as e:
                errors.append(
                    {"index": i, "username": user_data.username, "error": str(e)}
                )

        await db.commit()

        # Log bulk creation
        auth_audit_logger.log_api_access(
            username=current_user.username,
            endpoint="/admin/users/bulk-create",
            method="POST",
            status_code=200,
            request=request,
            details={
                "total_requested": len(bulk_data.users),
                "successful_creations": len(created_users),
                "errors": len(errors),
            },
        )

        return {
            "message": f"Bulk user creation completed",
            "created": len(created_users),
            "errors": len(errors),
            "created_users": created_users,
            "errors_detail": errors,
        }

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error in bulk user creation: {str(e)}",
        )


# ===== USER STATISTICS =====


@router.get("/users/stats", response_model=UserStatsResponse)
async def get_user_stats(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(check_admin_access),
):
    """Get user statistics for admin dashboard."""
    try:
        # Total users
        total_users_query = select(func.count(User.id))
        total_result = await db.execute(total_users_query)
        total_users = total_result.scalar()

        # Active users
        active_users_query = select(func.count(User.id)).where(User.is_active == True)
        active_result = await db.execute(active_users_query)
        active_users = active_result.scalar()

        # Inactive users
        inactive_users = total_users - active_users

        # Locked users
        locked_users_query = select(func.count(User.id)).where(User.is_locked == True)
        locked_result = await db.execute(locked_users_query)
        locked_users = locked_result.scalar()

        # Users with 2FA
        totp_users_query = select(func.count(User.id)).where(User.totp_enabled == True)
        totp_result = await db.execute(totp_users_query)
        users_with_2fa = totp_result.scalar()

        # Users by role
        role_stats_query = (
            select(Role.name, func.count(User.id))
            .select_from(
                Role.__table__.join(User.__table__.join(User.roles.property.secondary))
            )
            .group_by(Role.name)
        )
        role_result = await db.execute(role_stats_query)
        users_by_role = dict(role_result.all())

        # Recent logins (last 24 hours)
        from datetime import timedelta

        recent_login_cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
        recent_logins_query = select(func.count(User.id)).where(
            User.last_login >= recent_login_cutoff
        )
        recent_result = await db.execute(recent_logins_query)
        recent_logins = recent_result.scalar()

        # Pending verification
        pending_verification_query = select(func.count(User.id)).where(
            User.is_verified == False
        )
        pending_result = await db.execute(pending_verification_query)
        pending_verification = pending_result.scalar()

        return UserStatsResponse(
            total_users=total_users,
            active_users=active_users,
            inactive_users=inactive_users,
            locked_users=locked_users,
            users_with_2fa=users_with_2fa,
            users_by_role=users_by_role,
            recent_logins=recent_logins,
            pending_verification=pending_verification,
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving user statistics: {str(e)}",
        )


# ===== EXPORT FUNCTIONALITY =====


@router.get("/users/export")
async def export_users(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(check_admin_access),
    format: str = Query("csv", description="Export format: csv"),
):
    """Export user data to CSV."""
    try:
        # Get all users with roles
        query = select(User).options(selectinload(User.roles)).order_by(User.created_at)
        result = await db.execute(query)
        users = result.scalars().all()

        if format.lower() == "csv":
            # Create CSV
            output = io.StringIO()
            writer = csv.writer(output)

            # Write header
            writer.writerow(
                [
                    "ID",
                    "Username",
                    "Email",
                    "Full Name",
                    "Active",
                    "Verified",
                    "Locked",
                    "2FA Enabled",
                    "Roles",
                    "Created At",
                    "Last Login",
                ]
            )

            # Write data
            for user in users:
                writer.writerow(
                    [
                        str(user.id),
                        user.username,
                        user.email,
                        user.full_name or "",
                        user.is_active,
                        user.is_verified,
                        user.is_locked,
                        user.totp_enabled or False,
                        ", ".join([role.name for role in user.roles]),
                        user.created_at.isoformat() if user.created_at else "",
                        user.last_login.isoformat() if user.last_login else "",
                    ]
                )

            output.seek(0)

            # Log export
            auth_audit_logger.log_api_access(
                username=current_user.username,
                endpoint="/admin/users/export",
                method="GET",
                status_code=200,
                request=request,
                details={"format": format, "exported_count": len(users)},
            )

            return StreamingResponse(
                io.BytesIO(output.getvalue().encode()),
                media_type="text/csv",
                headers={
                    "Content-Disposition": "attachment; filename=users_export.csv"
                },
            )

        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Unsupported export format",
            )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error exporting users: {str(e)}",
        )
