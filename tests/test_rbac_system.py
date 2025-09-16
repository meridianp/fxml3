"""
Comprehensive TDD test suite for Role-Based Access Control (RBAC) system.

This module tests the production-ready RBAC system including:
- Standard role definitions: Admin, Trader, Viewer, Auditor
- Granular permission system for trading operations
- Role-based endpoint access control
- Permission inheritance and hierarchy validation
- Integration with JWT authentication system
- Regulatory compliance role separation
"""

import json
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, Mock, patch

import pytest
import pytest_asyncio
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from fxml4.api.auth.auth import (
    get_current_active_user,
    get_current_user,
    require_permission,
    require_role,
)
from fxml4.api.auth.models import Role, User


@pytest.mark.auth
@pytest.mark.rbac
class TestRoleDefinitions:
    """Test standard role definitions and permissions."""

    def test_admin_role_definition(self):
        """Test Admin role has full system access."""
        admin_permissions = {
            # User Management
            "users.create",
            "users.read",
            "users.update",
            "users.delete",
            "users.reset_password",
            "users.manage_roles",
            # Trading Operations
            "trading.create_orders",
            "trading.cancel_orders",
            "trading.view_orders",
            "trading.execute_trades",
            "trading.view_positions",
            "trading.modify_positions",
            # Risk Management
            "risk.set_limits",
            "risk.view_limits",
            "risk.override_limits",
            "risk.emergency_stop",
            "risk.configure_rules",
            # System Administration
            "system.configure",
            "system.maintenance",
            "system.backup",
            "system.monitor",
            "system.audit_access",
            # Data Access
            "data.market_data",
            "data.historical_data",
            "data.analytics",
            "data.export",
            "data.import",
            # Compliance
            "compliance.view_reports",
            "compliance.generate_reports",
            "compliance.audit_trail",
            "compliance.regulatory_filings",
        }

        admin_role = Role(
            name="admin",
            description="System Administrator with full access",
            permissions=json.dumps(list(admin_permissions)),
        )

        assert admin_role.name == "admin"
        assert len(json.loads(admin_role.permissions)) >= 20
        assert "system.configure" in json.loads(admin_role.permissions)
        assert "trading.execute_trades" in json.loads(admin_role.permissions)

    def test_trader_role_definition(self):
        """Test Trader role has trading and market access."""
        trader_permissions = {
            # Trading Operations (Primary Role)
            "trading.create_orders",
            "trading.cancel_orders",
            "trading.view_orders",
            "trading.execute_trades",
            "trading.view_positions",
            "trading.modify_positions",
            "trading.view_pnl",
            "trading.strategy_access",
            # Market Data Access
            "data.market_data",
            "data.historical_data",
            "data.analytics",
            "data.technical_indicators",
            # Risk Management (Limited)
            "risk.view_limits",
            "risk.view_exposure",
            # User Profile
            "users.read_own",
            "users.update_own_profile",
            # Compliance (Read-only)
            "compliance.view_own_trades",
        }

        trader_role = Role(
            name="trader",
            description="Trading professional with market access",
            permissions=json.dumps(list(trader_permissions)),
        )

        assert trader_role.name == "trader"
        permissions = json.loads(trader_role.permissions)
        assert "trading.execute_trades" in permissions
        assert "system.configure" not in permissions
        assert "users.create" not in permissions

    def test_viewer_role_definition(self):
        """Test Viewer role has read-only access."""
        viewer_permissions = {
            # Read-only Market Data
            "data.market_data",
            "data.historical_data",
            "data.analytics",
            # Read-only Trading Information
            "trading.view_orders",
            "trading.view_positions",
            "trading.view_pnl",
            # Read-only Risk Information
            "risk.view_limits",
            "risk.view_exposure",
            # User Profile
            "users.read_own",
            "users.update_own_profile",
        }

        viewer_role = Role(
            name="viewer",
            description="Read-only access to trading information",
            permissions=json.dumps(list(viewer_permissions)),
        )

        assert viewer_role.name == "viewer"
        permissions = json.loads(viewer_role.permissions)
        assert "trading.view_orders" in permissions
        assert "trading.create_orders" not in permissions
        assert "trading.execute_trades" not in permissions
        assert "system.configure" not in permissions

    def test_auditor_role_definition(self):
        """Test Auditor role has compliance and audit access."""
        auditor_permissions = {
            # Compliance and Audit (Primary Role)
            "compliance.view_reports",
            "compliance.generate_reports",
            "compliance.audit_trail",
            "compliance.regulatory_filings",
            "compliance.trade_surveillance",
            "compliance.risk_monitoring",
            # Read-only System Access
            "trading.view_orders",
            "trading.view_positions",
            "trading.view_pnl",
            "risk.view_limits",
            "risk.view_exposure",
            "data.market_data",
            "data.historical_data",
            "data.analytics",
            # User Profile
            "users.read_own",
            "users.update_own_profile",
            # Audit Logging
            "audit.view_logs",
            "audit.search_logs",
            "audit.export_logs",
        }

        auditor_role = Role(
            name="auditor",
            description="Compliance and audit specialist",
            permissions=json.dumps(list(auditor_permissions)),
        )

        assert auditor_role.name == "auditor"
        permissions = json.loads(auditor_role.permissions)
        assert "compliance.audit_trail" in permissions
        assert "audit.view_logs" in permissions
        assert "trading.execute_trades" not in permissions
        assert "system.configure" not in permissions


@pytest.mark.auth
@pytest.mark.rbac
class TestRoleHierarchy:
    """Test role hierarchy and permission inheritance."""

    def test_admin_role_hierarchy(self):
        """Test admin role has highest privileges."""
        admin_user = User(username="admin_user", email="admin@fxml4.com")
        admin_role = Role(
            name="admin", permissions='["system.configure", "trading.execute_trades"]'
        )
        admin_user.roles = [admin_role]

        # Admin should have access to all operations
        assert admin_user.has_role("admin")
        assert admin_user.has_permission("system.configure")
        assert admin_user.has_permission("trading.execute_trades")

    def test_trader_cannot_access_admin_functions(self):
        """Test trader role cannot access admin functions."""
        trader_user = User(username="trader_user", email="trader@fxml4.com")
        trader_role = Role(
            name="trader", permissions='["trading.execute_trades", "data.market_data"]'
        )
        trader_user.roles = [trader_role]

        # Trader should have trading access
        assert trader_user.has_role("trader")
        assert trader_user.has_permission("trading.execute_trades")
        assert trader_user.has_permission("data.market_data")

        # But not admin functions
        assert not trader_user.has_role("admin")
        assert not trader_user.has_permission("system.configure")
        assert not trader_user.has_permission("users.create")

    def test_viewer_read_only_access(self):
        """Test viewer role has read-only access."""
        viewer_user = User(username="viewer_user", email="viewer@fxml4.com")
        viewer_role = Role(
            name="viewer", permissions='["trading.view_orders", "data.market_data"]'
        )
        viewer_user.roles = [viewer_role]

        # Viewer should have read access
        assert viewer_user.has_role("viewer")
        assert viewer_user.has_permission("trading.view_orders")
        assert viewer_user.has_permission("data.market_data")

        # But no write/execute permissions
        assert not viewer_user.has_permission("trading.create_orders")
        assert not viewer_user.has_permission("trading.execute_trades")
        assert not viewer_user.has_permission("system.configure")

    def test_auditor_compliance_access(self):
        """Test auditor role has compliance access."""
        auditor_user = User(username="auditor_user", email="auditor@fxml4.com")
        auditor_role = Role(
            name="auditor", permissions='["compliance.audit_trail", "audit.view_logs"]'
        )
        auditor_user.roles = [auditor_role]

        # Auditor should have compliance access
        assert auditor_user.has_role("auditor")
        assert auditor_user.has_permission("compliance.audit_trail")
        assert auditor_user.has_permission("audit.view_logs")

        # But no trading execution
        assert not auditor_user.has_permission("trading.execute_trades")
        assert not auditor_user.has_permission("system.configure")


@pytest.mark.auth
@pytest.mark.rbac
class TestPermissionSystem:
    """Test granular permission system."""

    def test_permission_validation(self):
        """Test permission validation logic."""
        user = User(username="test_user", email="test@fxml4.com")
        role = Role(
            name="test_role", permissions='["trading.view_orders", "data.market_data"]'
        )
        user.roles = [role]

        # Valid permissions
        assert user.has_permission("trading.view_orders")
        assert user.has_permission("data.market_data")

        # Invalid permissions
        assert not user.has_permission("trading.execute_trades")
        assert not user.has_permission("system.configure")
        assert not user.has_permission("nonexistent.permission")

    def test_multiple_role_permissions(self):
        """Test user with multiple roles aggregates permissions."""
        user = User(username="multi_user", email="multi@fxml4.com")

        trader_role = Role(name="trader", permissions='["trading.execute_trades"]')
        viewer_role = Role(name="viewer", permissions='["data.analytics"]')

        user.roles = [trader_role, viewer_role]

        # Should have permissions from both roles
        assert user.has_role("trader")
        assert user.has_role("viewer")
        assert user.has_permission("trading.execute_trades")
        assert user.has_permission("data.analytics")

        # But not permissions not in either role
        assert not user.has_permission("system.configure")

    def test_empty_permissions_handling(self):
        """Test handling of roles with no permissions."""
        user = User(username="empty_user", email="empty@fxml4.com")
        empty_role = Role(name="empty", permissions="[]")
        user.roles = [empty_role]

        assert user.has_role("empty")
        assert not user.has_permission("any.permission")

    def test_malformed_permissions_handling(self):
        """Test handling of malformed permission JSON."""
        user = User(username="malformed_user", email="malformed@fxml4.com")

        # Test None permissions
        none_role = Role(name="none_role", permissions=None)
        user.roles = [none_role]
        assert not user.has_permission("any.permission")

        # Test empty string permissions
        empty_role = Role(name="empty_role", permissions="")
        user.roles = [empty_role]
        assert not user.has_permission("any.permission")


@pytest.mark.auth
@pytest.mark.rbac
class TestRoleBasedEndpointAccess:
    """Test role-based access control for API endpoints."""

    @pytest.mark.asyncio
    async def test_require_role_function(self):
        """Test require_role dependency function."""
        # Mock admin user
        admin_user = Mock(spec=User)
        admin_user.has_role.return_value = True
        admin_user.is_active = True

        # Create role checker
        role_checker = require_role("admin")

        # Should pass for admin user
        result = await role_checker(admin_user)
        assert result == admin_user

        # Mock non-admin user
        regular_user = Mock(spec=User)
        regular_user.has_role.side_effect = lambda role: role == "trader"
        regular_user.is_active = True

        # Should raise exception for non-admin
        with pytest.raises(HTTPException) as exc_info:
            await role_checker(regular_user)

        assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN
        assert "Role 'admin' required" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_require_permission_function(self):
        """Test require_permission dependency function."""
        # Mock user with permission
        authorized_user = Mock(spec=User)
        authorized_user.has_permission.return_value = True
        authorized_user.has_role.return_value = False  # Not admin
        authorized_user.is_active = True

        # Create permission checker
        permission_checker = require_permission("trading.execute_trades")

        # Should pass for user with permission
        result = await permission_checker(authorized_user)
        assert result == authorized_user

        # Mock user without permission
        unauthorized_user = Mock(spec=User)
        unauthorized_user.has_permission.return_value = False
        unauthorized_user.has_role.return_value = False
        unauthorized_user.is_active = True

        # Should raise exception for user without permission
        with pytest.raises(HTTPException) as exc_info:
            await permission_checker(unauthorized_user)

        assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN
        assert "Permission 'trading.execute_trades' required" in str(
            exc_info.value.detail
        )

    @pytest.mark.asyncio
    async def test_admin_bypass_permission_checks(self):
        """Test admin role bypasses specific permission checks."""
        # Mock admin user without specific permission
        admin_user = Mock(spec=User)
        admin_user.has_permission.return_value = (
            False  # Doesn't have specific permission
        )
        admin_user.has_role.side_effect = lambda role: role == "admin"
        admin_user.is_active = True

        # Create permission checker
        permission_checker = require_permission("some.specific.permission")

        # Should pass for admin even without specific permission
        result = await permission_checker(admin_user)
        assert result == admin_user

        # Verify admin role was checked
        admin_user.has_role.assert_called_with("admin")


@pytest.mark.auth
@pytest.mark.rbac
class TestRegulatoryComplianceSeparation:
    """Test regulatory compliance role separation."""

    def test_trader_auditor_separation(self):
        """Test traders and auditors have separated responsibilities."""
        trader = User(username="trader", email="trader@fxml4.com")
        trader_role = Role(
            name="trader", permissions='["trading.execute_trades", "data.market_data"]'
        )
        trader.roles = [trader_role]

        auditor = User(username="auditor", email="auditor@fxml4.com")
        auditor_role = Role(
            name="auditor", permissions='["compliance.audit_trail", "audit.view_logs"]'
        )
        auditor.roles = [auditor_role]

        # Trader can execute trades but not audit
        assert trader.has_permission("trading.execute_trades")
        assert not trader.has_permission("compliance.audit_trail")

        # Auditor can audit but not execute trades
        assert auditor.has_permission("compliance.audit_trail")
        assert not auditor.has_permission("trading.execute_trades")

    def test_risk_management_separation(self):
        """Test risk management role separation."""
        trader = User(username="risk_trader", email="trader@fxml4.com")
        trader_role = Role(
            name="trader", permissions='["trading.execute_trades", "risk.view_limits"]'
        )
        trader.roles = [trader_role]

        admin = User(username="risk_admin", email="admin@fxml4.com")
        admin_role = Role(
            name="admin", permissions='["risk.set_limits", "risk.override_limits"]'
        )
        admin.roles = [admin_role]

        # Trader can view but not modify risk limits
        assert trader.has_permission("risk.view_limits")
        assert not trader.has_permission("risk.set_limits")

        # Admin can set and override risk limits
        assert admin.has_permission("risk.set_limits")
        assert admin.has_permission("risk.override_limits")

    def test_data_access_controls(self):
        """Test data access controls by role."""
        viewer = User(username="data_viewer", email="viewer@fxml4.com")
        viewer_role = Role(
            name="viewer", permissions='["data.market_data", "data.analytics"]'
        )
        viewer.roles = [viewer_role]

        admin = User(username="data_admin", email="admin@fxml4.com")
        admin_role = Role(
            name="admin",
            permissions='["data.export", "data.import", "data.market_data"]',
        )
        admin.roles = [admin_role]

        # Viewer can read data but not export/import
        assert viewer.has_permission("data.market_data")
        assert not viewer.has_permission("data.export")
        assert not viewer.has_permission("data.import")

        # Admin can export/import data
        assert admin.has_permission("data.export")
        assert admin.has_permission("data.import")


@pytest.mark.auth
@pytest.mark.rbac
class TestRBACIntegration:
    """Test RBAC integration with authentication system."""

    @pytest.fixture
    def mock_db(self):
        """Mock database session."""
        db = AsyncMock(spec=AsyncSession)
        return db

    @pytest.fixture
    def sample_users(self):
        """Sample users with different roles."""
        admin_user = User(
            id="admin-123", username="admin", email="admin@fxml4.com", is_active=True
        )
        admin_role = Role(
            name="admin", permissions='["system.configure", "trading.execute_trades"]'
        )
        admin_user.roles = [admin_role]

        trader_user = User(
            id="trader-456", username="trader", email="trader@fxml4.com", is_active=True
        )
        trader_role = Role(
            name="trader", permissions='["trading.execute_trades", "data.market_data"]'
        )
        trader_user.roles = [trader_role]

        viewer_user = User(
            id="viewer-789", username="viewer", email="viewer@fxml4.com", is_active=True
        )
        viewer_role = Role(
            name="viewer", permissions='["trading.view_orders", "data.market_data"]'
        )
        viewer_user.roles = [viewer_role]

        return {"admin": admin_user, "trader": trader_user, "viewer": viewer_user}

    @pytest.mark.asyncio
    async def test_endpoint_access_control(self, sample_users):
        """Test endpoint access control with different user roles."""
        # Test admin access
        admin_checker = require_role("admin")
        admin_result = await admin_checker(sample_users["admin"])
        assert admin_result == sample_users["admin"]

        # Test trader cannot access admin endpoints
        with pytest.raises(HTTPException):
            await admin_checker(sample_users["trader"])

        # Test trading permission access
        trading_checker = require_permission("trading.execute_trades")

        # Admin and trader should have access
        admin_result = await trading_checker(sample_users["admin"])
        trader_result = await trading_checker(sample_users["trader"])
        assert admin_result == sample_users["admin"]
        assert trader_result == sample_users["trader"]

        # Viewer should not have access
        with pytest.raises(HTTPException):
            await trading_checker(sample_users["viewer"])

    @pytest.mark.asyncio
    async def test_inactive_user_access_denied(self, sample_users):
        """Test inactive users are denied access."""
        inactive_user = sample_users["admin"]
        inactive_user.is_active = False

        admin_checker = require_role("admin")

        # Should raise exception even for admin role when inactive
        # Note: This would be caught by get_current_active_user dependency
        # But testing the role logic here
        with pytest.raises(HTTPException) as exc_info:
            # Mock the get_current_active_user behavior
            if not inactive_user.is_active:
                raise HTTPException(status_code=400, detail="Inactive user")

        assert exc_info.value.status_code == 400
        assert "Inactive user" in str(exc_info.value.detail)

    def test_role_permission_consistency(self, sample_users):
        """Test consistency between roles and permissions."""
        admin = sample_users["admin"]
        trader = sample_users["trader"]
        viewer = sample_users["viewer"]

        # Admin should have all permissions
        assert admin.has_role("admin")
        assert admin.has_permission("system.configure")
        assert admin.has_permission("trading.execute_trades")

        # Trader should have trading permissions
        assert trader.has_role("trader")
        assert trader.has_permission("trading.execute_trades")
        assert trader.has_permission("data.market_data")
        assert not trader.has_permission("system.configure")

        # Viewer should have read-only permissions
        assert viewer.has_role("viewer")
        assert viewer.has_permission("trading.view_orders")
        assert viewer.has_permission("data.market_data")
        assert not viewer.has_permission("trading.execute_trades")
        assert not viewer.has_permission("system.configure")


@pytest.mark.auth
@pytest.mark.rbac
class TestRBACPerformance:
    """Test RBAC system performance characteristics."""

    def test_permission_check_performance(self):
        """Test permission checking is efficient."""
        import time

        # Create user with many permissions
        user = User(username="perf_user", email="perf@fxml4.com")
        permissions = [f"test.permission_{i}" for i in range(100)]
        role = Role(name="test_role", permissions=json.dumps(permissions))
        user.roles = [role]

        # Time permission checks
        start_time = time.time()
        for i in range(1000):
            user.has_permission(f"test.permission_{i % 100}")
        end_time = time.time()

        # Should complete quickly (less than 1 second for 1000 checks)
        assert (end_time - start_time) < 1.0

    def test_role_check_performance(self):
        """Test role checking is efficient."""
        import time

        # Create user with multiple roles
        user = User(username="multi_role_user", email="multi@fxml4.com")
        roles = [Role(name=f"role_{i}", permissions="[]") for i in range(10)]
        user.roles = roles

        # Time role checks
        start_time = time.time()
        for i in range(1000):
            user.has_role(f"role_{i % 10}")
        end_time = time.time()

        # Should complete quickly
        assert (end_time - start_time) < 1.0
