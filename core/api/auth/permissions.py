"""
Role-Based Access Control (RBAC) and Permission Management for FXML4.

This module provides comprehensive permission checking, role-based access control,
and authorization decorators for protecting API endpoints.
"""

import json
from functools import wraps
from typing import Any, Callable, Dict, List, Optional, Set

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from fxml4.api.auth.audit_logger import AuditEventType, auth_audit_logger
from fxml4.api.auth.auth import get_current_user
from fxml4.api.auth.database import get_db
from fxml4.api.auth.models import Role, User
from fxml4.config import get_config


class PermissionLevel:
    """Permission levels for hierarchical access control."""

    VIEWER = "viewer"
    TRADER = "trader"
    RISK_MANAGER = "risk_manager"
    ADMIN = "admin"

    # Hierarchy definition (higher number = more permissions)
    HIERARCHY = {VIEWER: 1, TRADER: 2, RISK_MANAGER: 3, ADMIN: 4}


class PermissionChecker:
    """Advanced permission checking system."""

    def __init__(self):
        """Initialize permission checker."""
        self.config = get_config()
        self.enable_audit_logging = self.config.get(
            "api.auth.permissions.audit_enabled", True
        )

        # Permission mappings for different operations
        self.resource_permissions = {
            # User management
            "users.create": [PermissionLevel.ADMIN],
            "users.read": [PermissionLevel.ADMIN, PermissionLevel.RISK_MANAGER],
            "users.update": [PermissionLevel.ADMIN],
            "users.delete": [PermissionLevel.ADMIN],
            "users.manage_roles": [PermissionLevel.ADMIN],
            # Trading operations
            "orders.create": [PermissionLevel.ADMIN, PermissionLevel.TRADER],
            "orders.read": [
                PermissionLevel.ADMIN,
                PermissionLevel.TRADER,
                PermissionLevel.RISK_MANAGER,
                PermissionLevel.VIEWER,
            ],
            "orders.update": [PermissionLevel.ADMIN, PermissionLevel.TRADER],
            "orders.cancel": [
                PermissionLevel.ADMIN,
                PermissionLevel.TRADER,
                PermissionLevel.RISK_MANAGER,
            ],
            # Risk management
            "risk.read": [
                PermissionLevel.ADMIN,
                PermissionLevel.RISK_MANAGER,
                PermissionLevel.TRADER,
            ],
            "risk.update": [PermissionLevel.ADMIN, PermissionLevel.RISK_MANAGER],
            "risk.override": [PermissionLevel.ADMIN, PermissionLevel.RISK_MANAGER],
            # Analytics and reports
            "reports.read": [
                PermissionLevel.ADMIN,
                PermissionLevel.RISK_MANAGER,
                PermissionLevel.VIEWER,
            ],
            "reports.create": [PermissionLevel.ADMIN, PermissionLevel.RISK_MANAGER],
            "analytics.read": [
                PermissionLevel.ADMIN,
                PermissionLevel.RISK_MANAGER,
                PermissionLevel.TRADER,
                PermissionLevel.VIEWER,
            ],
            # System administration
            "system.admin": [PermissionLevel.ADMIN],
            "system.config": [PermissionLevel.ADMIN],
            "system.monitoring": [PermissionLevel.ADMIN, PermissionLevel.RISK_MANAGER],
        }

    def get_user_effective_permissions(self, user: User) -> Set[str]:
        """Get all effective permissions for a user based on their roles.

        Args:
            user: User to check permissions for

        Returns:
            Set of permission strings
        """
        permissions = set()

        for role in user.roles:
            # Parse role permissions (stored as JSON string)
            if role.permissions:
                try:
                    role_perms = (
                        json.loads(role.permissions)
                        if isinstance(role.permissions, str)
                        else role.permissions
                    )
                    if isinstance(role_perms, list):
                        permissions.update(role_perms)
                    elif role_perms == ["*"] or role_perms == "*":
                        # Admin wildcard - return all permissions
                        all_permissions = set()
                        for resource, _ in self.resource_permissions.items():
                            all_permissions.add(resource)
                        return all_permissions
                except (json.JSONDecodeError, TypeError):
                    # Fallback: treat as individual permission string
                    permissions.add(role.permissions)

        return permissions

    def get_user_highest_role_level(self, user: User) -> int:
        """Get the highest permission level for a user.

        Args:
            user: User to check

        Returns:
            Highest permission level (integer)
        """
        max_level = 0

        for role in user.roles:
            role_level = PermissionLevel.HIERARCHY.get(role.name, 0)
            max_level = max(max_level, role_level)

        return max_level

    def check_permission(self, user: User, required_permission: str) -> bool:
        """Check if user has specific permission.

        Args:
            user: User to check
            required_permission: Permission string to check

        Returns:
            True if user has permission
        """
        user_permissions = self.get_user_effective_permissions(user)

        # Check for exact permission match
        if required_permission in user_permissions:
            return True

        # Check for wildcard admin permissions
        if "*" in user_permissions:
            return True

        # Check resource-based permissions
        if required_permission in self.resource_permissions:
            required_roles = self.resource_permissions[required_permission]
            user_level = self.get_user_highest_role_level(user)

            for required_role in required_roles:
                required_level = PermissionLevel.HIERARCHY.get(required_role, 0)
                if user_level >= required_level:
                    return True

        return False

    def check_role_hierarchy(self, user: User, minimum_role: str) -> bool:
        """Check if user has minimum role level.

        Args:
            user: User to check
            minimum_role: Minimum required role

        Returns:
            True if user meets minimum role requirement
        """
        user_level = self.get_user_highest_role_level(user)
        required_level = PermissionLevel.HIERARCHY.get(minimum_role, 0)

        return user_level >= required_level

    def check_resource_access(
        self,
        user: User,
        resource_type: str,
        action: str,
        resource_owner_id: Optional[str] = None,
    ) -> bool:
        """Check if user can perform action on resource type.

        Args:
            user: User to check
            resource_type: Type of resource (users, orders, etc.)
            action: Action to perform (read, create, update, delete)
            resource_owner_id: ID of resource owner (for ownership checks)

        Returns:
            True if user has access
        """
        permission_key = f"{resource_type}.{action}"

        # Check basic permission
        if self.check_permission(user, permission_key):
            return True

        # Check ownership for certain resources
        if resource_owner_id and str(user.id) == str(resource_owner_id):
            # Users can usually read/update their own resources
            if action in ["read", "update"] and resource_type in [
                "users",
                "profiles",
                "settings",
            ]:
                return True

        return False


# Global permission checker instance
permission_checker = PermissionChecker()


# Permission decorator functions
def require_permission(required_permission: str):
    """Decorator to require specific permission for endpoint access.

    Args:
        required_permission: Permission string required

    Returns:
        Decorator function
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Extract user from dependency injection
            current_user = None
            request = None

            # Find current_user and request in kwargs
            for key, value in kwargs.items():
                if isinstance(value, User):
                    current_user = value
                elif hasattr(value, "client") and hasattr(
                    value, "method"
                ):  # Request-like object
                    request = value

            if not current_user:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Authentication required",
                )

            # Check permission
            if not permission_checker.check_permission(
                current_user, required_permission
            ):
                # Log permission denial
                if permission_checker.enable_audit_logging:
                    auth_audit_logger.log_permission_check(
                        username=current_user.username,
                        required_scopes=[required_permission],
                        user_scopes=list(
                            permission_checker.get_user_effective_permissions(
                                current_user
                            )
                        ),
                        success=False,
                        request=request,
                        details={"endpoint": func.__name__},
                    )

                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Insufficient permissions. Required: {required_permission}",
                )

            # Log successful permission check
            if permission_checker.enable_audit_logging:
                auth_audit_logger.log_permission_check(
                    username=current_user.username,
                    required_scopes=[required_permission],
                    user_scopes=list(
                        permission_checker.get_user_effective_permissions(current_user)
                    ),
                    success=True,
                    request=request,
                    details={"endpoint": func.__name__},
                )

            return await func(*args, **kwargs)

        return wrapper

    return decorator


def require_role(minimum_role: str):
    """Decorator to require minimum role level for endpoint access.

    Args:
        minimum_role: Minimum role level required

    Returns:
        Decorator function
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            current_user = None
            request = None

            # Find current_user and request in kwargs
            for key, value in kwargs.items():
                if isinstance(value, User):
                    current_user = value
                elif hasattr(value, "client") and hasattr(value, "method"):
                    request = value

            if not current_user:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Authentication required",
                )

            # Check role hierarchy
            if not permission_checker.check_role_hierarchy(current_user, minimum_role):
                # Log permission denial
                if permission_checker.enable_audit_logging:
                    user_roles = [role.name for role in current_user.roles]
                    auth_audit_logger.log_permission_check(
                        username=current_user.username,
                        required_scopes=[f"role:{minimum_role}"],
                        user_scopes=[f"role:{role}" for role in user_roles],
                        success=False,
                        request=request,
                        details={"endpoint": func.__name__},
                    )

                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Insufficient role level. Required: {minimum_role} or higher",
                )

            return await func(*args, **kwargs)

        return wrapper

    return decorator


def require_admin(func: Callable) -> Callable:
    """Decorator to require admin role for endpoint access."""
    return require_role(PermissionLevel.ADMIN)(func)


def require_trader_or_above(func: Callable) -> Callable:
    """Decorator to require trader role or higher for endpoint access."""
    return require_role(PermissionLevel.TRADER)(func)


def require_risk_manager_or_above(func: Callable) -> Callable:
    """Decorator to require risk manager role or higher for endpoint access."""
    return require_role(PermissionLevel.RISK_MANAGER)(func)


# Dependency injection functions for FastAPI
async def check_admin_access(
    current_user: User = Depends(get_current_user), request: Request = None
) -> User:
    """Dependency to check admin access.

    Args:
        current_user: Current authenticated user
        request: HTTP request

    Returns:
        User if admin access granted

    Raises:
        HTTPException: If insufficient permissions
    """
    if not permission_checker.check_role_hierarchy(current_user, PermissionLevel.ADMIN):
        # Log permission denial
        if permission_checker.enable_audit_logging and request:
            user_roles = [role.name for role in current_user.roles]
            auth_audit_logger.log_permission_check(
                username=current_user.username,
                required_scopes=["role:admin"],
                user_scopes=[f"role:{role}" for role in user_roles],
                success=False,
                request=request,
            )

        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required"
        )

    return current_user


async def check_trader_access(
    current_user: User = Depends(get_current_user), request: Request = None
) -> User:
    """Dependency to check trader access."""
    if not permission_checker.check_role_hierarchy(
        current_user, PermissionLevel.TRADER
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Trader access or higher required",
        )

    return current_user


async def check_risk_manager_access(
    current_user: User = Depends(get_current_user), request: Request = None
) -> User:
    """Dependency to check risk manager access."""
    if not permission_checker.check_role_hierarchy(
        current_user, PermissionLevel.RISK_MANAGER
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Risk manager access or higher required",
        )

    return current_user


def get_permission_checker() -> PermissionChecker:
    """Get the global permission checker instance."""
    return permission_checker
