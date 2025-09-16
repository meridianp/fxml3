"""
Role Management System for FXML4 Trading Platform.

This module provides utilities for managing roles and permissions in the RBAC system.
It includes standard role definitions, role initialization, and permission validation.

Standard Roles:
- Admin: Full system access and configuration
- Trader: Trading operations and market data access
- Viewer: Read-only access to trading information
- Auditor: Compliance and audit access

Permission Categories:
- users.*: User management operations
- trading.*: Trading operations and order management
- risk.*: Risk management and limit controls
- system.*: System administration and configuration
- data.*: Market data and analytics access
- compliance.*: Regulatory compliance and reporting
- audit.*: Audit log access and management
"""

import json
import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional, Set, Tuple

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from .models import Role, User

# Configure logging
logger = logging.getLogger(__name__)


class RoleDefinitions:
    """Standard role definitions with permissions."""

    @staticmethod
    def get_admin_permissions() -> Set[str]:
        """Get permissions for Admin role - full system access."""
        return {
            # User Management - Full Control
            "users.create",
            "users.read",
            "users.update",
            "users.delete",
            "users.reset_password",
            "users.manage_roles",
            "users.manage_api_keys",
            # Trading Operations - Full Control
            "trading.create_orders",
            "trading.cancel_orders",
            "trading.view_orders",
            "trading.execute_trades",
            "trading.view_positions",
            "trading.modify_positions",
            "trading.view_pnl",
            "trading.strategy_access",
            "trading.manual_override",
            # Risk Management - Full Control
            "risk.set_limits",
            "risk.view_limits",
            "risk.override_limits",
            "risk.emergency_stop",
            "risk.configure_rules",
            "risk.view_exposure",
            "risk.modify_exposure",
            "risk.stress_testing",
            # System Administration - Full Control
            "system.configure",
            "system.maintenance",
            "system.backup",
            "system.monitor",
            "system.audit_access",
            "system.database_access",
            "system.infrastructure",
            "system.security_config",
            # Data Access - Full Control
            "data.market_data",
            "data.historical_data",
            "data.analytics",
            "data.export",
            "data.import",
            "data.technical_indicators",
            "data.fundamental_data",
            "data.research",
            # Compliance - Full Control
            "compliance.view_reports",
            "compliance.generate_reports",
            "compliance.audit_trail",
            "compliance.regulatory_filings",
            "compliance.trade_surveillance",
            "compliance.risk_monitoring",
            "compliance.policy_management",
            # Audit - Full Control
            "audit.view_logs",
            "audit.search_logs",
            "audit.export_logs",
            "audit.configure_retention",
            "audit.manage_access",
        }

    @staticmethod
    def get_trader_permissions() -> Set[str]:
        """Get permissions for Trader role - trading and market access."""
        return {
            # Trading Operations - Full Trading Access
            "trading.create_orders",
            "trading.cancel_orders",
            "trading.view_orders",
            "trading.execute_trades",
            "trading.view_positions",
            "trading.modify_positions",
            "trading.view_pnl",
            "trading.strategy_access",
            # Market Data Access - Full Read Access
            "data.market_data",
            "data.historical_data",
            "data.analytics",
            "data.technical_indicators",
            "data.fundamental_data",
            # Risk Management - View Only
            "risk.view_limits",
            "risk.view_exposure",
            # User Profile - Own Profile Only
            "users.read_own",
            "users.update_own_profile",
            "users.change_own_password",
            # Compliance - Own Trades Only
            "compliance.view_own_trades",
            "compliance.view_own_reports",
        }

    @staticmethod
    def get_viewer_permissions() -> Set[str]:
        """Get permissions for Viewer role - read-only access."""
        return {
            # Read-only Market Data
            "data.market_data",
            "data.historical_data",
            "data.analytics",
            "data.technical_indicators",
            # Read-only Trading Information
            "trading.view_orders",
            "trading.view_positions",
            "trading.view_pnl",
            # Read-only Risk Information
            "risk.view_limits",
            "risk.view_exposure",
            # User Profile - Own Profile Only
            "users.read_own",
            "users.update_own_profile",
            "users.change_own_password",
        }

    @staticmethod
    def get_auditor_permissions() -> Set[str]:
        """Get permissions for Auditor role - compliance and audit access."""
        return {
            # Compliance and Audit - Primary Role
            "compliance.view_reports",
            "compliance.generate_reports",
            "compliance.audit_trail",
            "compliance.regulatory_filings",
            "compliance.trade_surveillance",
            "compliance.risk_monitoring",
            # Audit Logging - Full Access
            "audit.view_logs",
            "audit.search_logs",
            "audit.export_logs",
            # Read-only System Access for Audit
            "trading.view_orders",
            "trading.view_positions",
            "trading.view_pnl",
            "risk.view_limits",
            "risk.view_exposure",
            "data.market_data",
            "data.historical_data",
            "data.analytics",
            # User Profile - Own Profile Only
            "users.read_own",
            "users.update_own_profile",
            "users.change_own_password",
        }

    @classmethod
    def get_all_standard_roles(cls) -> Dict[str, Dict[str, any]]:
        """Get all standard role definitions."""
        return {
            "admin": {
                "description": "System Administrator with full access to all functions",
                "permissions": cls.get_admin_permissions(),
            },
            "trader": {
                "description": "Trading professional with market access and order execution",
                "permissions": cls.get_trader_permissions(),
            },
            "viewer": {
                "description": "Read-only access to trading information and market data",
                "permissions": cls.get_viewer_permissions(),
            },
            "auditor": {
                "description": "Compliance and audit specialist with regulatory access",
                "permissions": cls.get_auditor_permissions(),
            },
        }


class RoleManager:
    """Manager class for role operations."""

    def __init__(self):
        self.role_definitions = RoleDefinitions()

    async def initialize_standard_roles(self, db: AsyncSession) -> Dict[str, bool]:
        """
        Initialize standard roles in the database.

        Returns:
            Dictionary with role names and creation status
        """
        results = {}
        standard_roles = self.role_definitions.get_all_standard_roles()

        for role_name, role_config in standard_roles.items():
            try:
                # Check if role already exists
                result = await db.execute(select(Role).where(Role.name == role_name))
                existing_role = result.scalar_one_or_none()

                if existing_role:
                    # Update permissions if they've changed
                    current_permissions = set(
                        json.loads(existing_role.permissions or "[]")
                    )
                    new_permissions = role_config["permissions"]

                    if current_permissions != new_permissions:
                        existing_role.permissions = json.dumps(list(new_permissions))
                        existing_role.description = role_config["description"]
                        logger.info(f"Updated permissions for role: {role_name}")
                        results[role_name] = True
                    else:
                        logger.info(f"Role already up to date: {role_name}")
                        results[role_name] = True
                else:
                    # Create new role
                    new_role = Role(
                        name=role_name,
                        description=role_config["description"],
                        permissions=json.dumps(list(role_config["permissions"])),
                    )
                    db.add(new_role)
                    logger.info(f"Created new role: {role_name}")
                    results[role_name] = True

            except Exception as e:
                logger.error(f"Failed to initialize role {role_name}: {e}")
                results[role_name] = False

        # Commit all changes
        try:
            await db.commit()
            logger.info("Successfully initialized all standard roles")
        except Exception as e:
            await db.rollback()
            logger.error(f"Failed to commit role initialization: {e}")
            # Mark all as failed
            for role_name in results:
                results[role_name] = False

        return results

    async def validate_user_roles(
        self, db: AsyncSession, user_id: str
    ) -> Dict[str, any]:
        """
        Validate user roles and permissions.

        Returns:
            Validation report with role and permission details
        """
        # Get user with roles
        result = await db.execute(
            select(User).options(selectinload(User.roles)).where(User.id == user_id)
        )
        user = result.scalar_one_or_none()

        if not user:
            return {"error": "User not found", "valid": False}

        validation_report = {
            "user_id": user_id,
            "username": user.username,
            "is_active": user.is_active,
            "roles": [],
            "total_permissions": set(),
            "role_conflicts": [],
            "valid": True,
        }

        # Analyze each role
        for role in user.roles:
            role_info = {
                "name": role.name,
                "description": role.description,
                "permissions": json.loads(role.permissions or "[]"),
            }

            # Check if it's a standard role
            standard_roles = self.role_definitions.get_all_standard_roles()
            if role.name in standard_roles:
                expected_permissions = standard_roles[role.name]["permissions"]
                actual_permissions = set(role_info["permissions"])

                if actual_permissions != expected_permissions:
                    role_info["permission_drift"] = {
                        "missing": list(expected_permissions - actual_permissions),
                        "extra": list(actual_permissions - expected_permissions),
                    }

            validation_report["roles"].append(role_info)
            validation_report["total_permissions"].update(role_info["permissions"])

        # Convert permissions set to list for JSON serialization
        validation_report["total_permissions"] = list(
            validation_report["total_permissions"]
        )

        # Check for common role conflicts
        role_names = [role.name for role in user.roles]
        if "trader" in role_names and "auditor" in role_names:
            validation_report["role_conflicts"].append(
                "Trader and Auditor roles should be separated for regulatory compliance"
            )

        return validation_report

    async def assign_role_to_user(
        self, db: AsyncSession, user_id: str, role_name: str
    ) -> Tuple[bool, str]:
        """
        Assign a role to a user.

        Returns:
            Tuple of (success, message)
        """
        try:
            # Get user and role
            user_result = await db.execute(
                select(User).options(selectinload(User.roles)).where(User.id == user_id)
            )
            user = user_result.scalar_one_or_none()

            if not user:
                return False, "User not found"

            role_result = await db.execute(select(Role).where(Role.name == role_name))
            role = role_result.scalar_one_or_none()

            if not role:
                return False, f"Role '{role_name}' not found"

            # Check if user already has this role
            if any(r.name == role_name for r in user.roles):
                return True, f"User already has role '{role_name}'"

            # Add role to user
            user.roles.append(role)
            await db.commit()

            logger.info(f"Assigned role '{role_name}' to user '{user.username}'")
            return True, f"Successfully assigned role '{role_name}'"

        except Exception as e:
            await db.rollback()
            logger.error(f"Failed to assign role: {e}")
            return False, f"Error assigning role: {str(e)}"

    async def remove_role_from_user(
        self, db: AsyncSession, user_id: str, role_name: str
    ) -> Tuple[bool, str]:
        """
        Remove a role from a user.

        Returns:
            Tuple of (success, message)
        """
        try:
            # Get user and role
            user_result = await db.execute(
                select(User).options(selectinload(User.roles)).where(User.id == user_id)
            )
            user = user_result.scalar_one_or_none()

            if not user:
                return False, "User not found"

            # Find role in user's roles
            role_to_remove = None
            for role in user.roles:
                if role.name == role_name:
                    role_to_remove = role
                    break

            if not role_to_remove:
                return False, f"User does not have role '{role_name}'"

            # Remove role from user
            user.roles.remove(role_to_remove)
            await db.commit()

            logger.info(f"Removed role '{role_name}' from user '{user.username}'")
            return True, f"Successfully removed role '{role_name}'"

        except Exception as e:
            await db.rollback()
            logger.error(f"Failed to remove role: {e}")
            return False, f"Error removing role: {str(e)}"

    async def get_permission_summary(self, db: AsyncSession) -> Dict[str, any]:
        """
        Get a summary of all permissions across roles.

        Returns:
            Permission analysis summary
        """
        # Get all roles
        result = await db.execute(select(Role))
        roles = result.scalars().all()

        summary = {
            "total_roles": len(roles),
            "roles": {},
            "all_permissions": set(),
            "permission_categories": {},
            "coverage_analysis": {},
        }

        # Analyze each role
        for role in roles:
            permissions = json.loads(role.permissions or "[]")
            summary["roles"][role.name] = {
                "description": role.description,
                "permission_count": len(permissions),
                "permissions": permissions,
            }

            summary["all_permissions"].update(permissions)

            # Categorize permissions
            for permission in permissions:
                category = permission.split(".")[0]
                if category not in summary["permission_categories"]:
                    summary["permission_categories"][category] = set()
                summary["permission_categories"][category].add(permission)

        # Convert sets to lists for JSON serialization
        summary["all_permissions"] = list(summary["all_permissions"])
        for category in summary["permission_categories"]:
            summary["permission_categories"][category] = list(
                summary["permission_categories"][category]
            )

        # Coverage analysis
        standard_roles = self.role_definitions.get_all_standard_roles()
        for role_name, role_config in standard_roles.items():
            if role_name in summary["roles"]:
                actual_permissions = set(summary["roles"][role_name]["permissions"])
                expected_permissions = role_config["permissions"]

                summary["coverage_analysis"][role_name] = {
                    "has_all_expected": actual_permissions >= expected_permissions,
                    "missing_permissions": list(
                        expected_permissions - actual_permissions
                    ),
                    "extra_permissions": list(
                        actual_permissions - expected_permissions
                    ),
                }

        return summary


# Global role manager instance
role_manager = RoleManager()


async def initialize_roles(db: AsyncSession) -> Dict[str, bool]:
    """Convenience function to initialize standard roles."""
    return await role_manager.initialize_standard_roles(db)
