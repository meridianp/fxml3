"""
Unit tests for fxml4.api.auth.models covering core auth dataclasses and methods.

Focus:
- Critical business logic: permission checks, account lock status, token serialization
- Error handling and boundary conditions
- Integration shape: enums and dataclass field semantics

Markers follow FXML4 conventions.
"""

from datetime import datetime, timedelta
from unittest.mock import MagicMock, Mock, patch

import pytest

from fxml4.api.auth.models import (
    Permission,
    TokenPair,
    TokenValidationResult,
    User,
    UserRole,
)

# Apply common markers used in FXML4 tests
pytestmark = [pytest.mark.unit, pytest.mark.machine_learning]


# Test fixtures
@pytest.fixture
def sample_data():
    """Provide generic sample data to be reused in tests."""
    return {
        "user_id": "user_123",
        "username": "alice",
        "email": "alice@example.com",
        "access_token": "access.token.value",
        "refresh_token": "refresh.token.value",
    }


@pytest.fixture
def user_factory(sample_data):
    """Factory fixture to create users with flexible attributes."""

    def _factory(
        role: UserRole = UserRole.VIEWER,
        is_active: bool = True,
        is_verified: bool = False,
        permissions=None,
        failed_login_attempts: int = 0,
        locked_until=None,
    ) -> User:
        return User(
            user_id=sample_data["user_id"],
            username=sample_data["username"],
            email=sample_data["email"],
            role=role,
            is_active=is_active,
            is_verified=is_verified,
            permissions=permissions,
            created_at=datetime.utcnow(),
            last_login=None,
            failed_login_attempts=failed_login_attempts,
            locked_until=locked_until,
        )

    return _factory


@pytest.fixture
def token_pair(sample_data) -> TokenPair:
    """Create a sample TokenPair for serialization tests."""
    return TokenPair(
        access_token=sample_data["access_token"],
        refresh_token=sample_data["refresh_token"],
    )


class TestUserRoleAndPermissionEnums:
    """Validate UserRole and Permission enumerations for integrity and values."""

    def test_user_role_enum_values_when_compared_then_expected_strings(self):
        """Ensure enum values match the expected lowercase strings."""
        assert UserRole.ADMIN.value == "admin"
        assert UserRole.TRADER.value == "trader"
        assert UserRole.COMPLIANCE.value == "compliance"
        assert UserRole.VIEWER.value == "viewer"
        assert UserRole.API_USER.value == "api_user"

    def test_permission_enum_membership_when_iterated_then_contains_expected(self):
        """Ensure a subset of critical permissions exists in the enum set."""
        perms = {p.value for p in Permission}
        assert {
            "trade:execute",
            "trade:view",
            "account:view",
            "system:config",
            "audit:view",
        }.issubset(perms)


class TestUserHasPermission:
    """Test permission evaluation logic for various roles and configurations."""

    def test_has_permission_when_user_has_explicit_permissions_then_overrides_role_defaults(
        self, user_factory
    ):
        """Explicit permissions list takes precedence over role defaults."""
        user = user_factory(
            role=UserRole.VIEWER,
            permissions=[Permission.SYSTEM_CONFIG, Permission.ACCOUNT_VIEW],
        )

        assert user.has_permission(Permission.SYSTEM_CONFIG) is True
        assert user.has_permission(Permission.ACCOUNT_VIEW) is True
        # Not present in explicit list
        assert user.has_permission(Permission.TRADE_VIEW) is False

    def test_has_permission_when_permissions_is_empty_list_then_fall_back_to_role_defaults(
        self, user_factory
    ):
        """Empty list should not be treated as explicit permissions; fallback to role mapping."""
        user = user_factory(role=UserRole.VIEWER, permissions=[])

        assert user.has_permission(Permission.TRADE_VIEW) is True  # viewer default
        assert user.has_permission(Permission.ACCOUNT_VIEW) is True  # viewer default
        assert (
            user.has_permission(Permission.TRADE_EXECUTE) is False
        )  # not allowed for viewer

    def test_has_permission_when_role_admin_then_all_permissions_allowed(
        self, user_factory
    ):
        """Admins should be granted all permissions by default when no explicit list is provided."""
        user = user_factory(role=UserRole.ADMIN, permissions=None)

        for perm in Permission:
            assert user.has_permission(perm) is True

    def test_has_permission_when_role_trader_then_expected_subset_only(
        self, user_factory
    ):
        """Trader default permissions include trade and account view but exclude system config."""
        user = user_factory(role=UserRole.TRADER, permissions=None)

        assert user.has_permission(Permission.TRADE_EXECUTE) is True
        assert user.has_permission(Permission.TRADE_VIEW) is True
        assert user.has_permission(Permission.TRADE_CANCEL) is True
        assert user.has_permission(Permission.ACCOUNT_VIEW) is True
        assert user.has_permission(Permission.SYSTEM_CONFIG) is False

    def test_has_permission_when_wrong_type_passed_then_returns_false(
        self, user_factory
    ):
        """Boundary: if a non-enum value is passed, result should be False without errors."""
        user = user_factory(role=UserRole.API_USER, permissions=None)
        assert user.has_permission("trade:execute") is False  # type: ignore[arg-type]


class TestUserLockStatus:
    """Test account lock status evaluation based on locked_until timestamp."""

    def test_is_locked_when_locked_until_in_future_then_true(self, user_factory):
        """User is locked if current time is before locked_until."""
        future = datetime.utcnow() + timedelta(seconds=2)
        user = user_factory(locked_until=future)
        assert user.is_locked() is True

    def test_is_locked_when_locked_until_in_past_then_false(self, user_factory):
        """User is not locked if locked_until is in the past."""
        past = datetime.utcnow() - timedelta(seconds=2)
        user = user_factory(locked_until=past)
        assert user.is_locked() is False

    def test_is_locked_boundary_when_locked_until_exact_now_then_false(
        self, user_factory
    ):
        """Boundary condition: equality should not be considered locked (strictly < check)."""
        now_exact = datetime.utcnow()
        user = user_factory(locked_until=now_exact)
        assert user.is_locked() is False


class TestTokenPairToDict:
    """Test TokenPair serialization to dictionary for API responses."""

    def test_to_dict_when_using_defaults_then_expected_fields_present(self, token_pair):
        """Default token_type and expires_in should be included in the serialized output."""
        payload = token_pair.to_dict()

        assert payload["access_token"] == token_pair.access_token
        assert payload["refresh_token"] == token_pair.refresh_token
        assert payload["token_type"] == "Bearer"
        assert payload["expires_in"] == 900

    def test_to_dict_when_custom_values_then_reflect_in_output(self, sample_data):
        """Custom token_type and expiry should be preserved in the dict."""
        tp = TokenPair(
            access_token=sample_data["access_token"],
            refresh_token=sample_data["refresh_token"],
            token_type="JWT",
            expires_in=60,
        )
        payload = tp.to_dict()
        assert payload == {
            "access_token": sample_data["access_token"],
            "refresh_token": sample_data["refresh_token"],
            "token_type": "JWT",
            "expires_in": 60,
        }


class TestTokenValidationResult:
    """Validate TokenValidationResult dataclass construction and typical usage fields."""

    def test_token_validation_result_when_valid_then_contains_user_details(
        self, sample_data
    ):
        """A valid result may include user identity, role, and permissions."""
        result = TokenValidationResult(
            is_valid=True,
            user_id=sample_data["user_id"],
            username=sample_data["username"],
            role=UserRole.TRADER.value,
            permissions=[
                p.value for p in (Permission.TRADE_VIEW, Permission.ACCOUNT_VIEW)
            ],
            error=None,
            expires_at=datetime.utcnow() + timedelta(minutes=10),
        )

        assert result.is_valid is True
        assert result.user_id == sample_data["user_id"]
        assert result.username == sample_data["username"]
        assert result.role == "trader"
        assert set(result.permissions or []) == {"trade:view", "account:view"}
        assert result.error is None

    def test_token_validation_result_when_invalid_then_carries_error_and_no_user(self):
        """Invalid result should capture the error and may lack identity fields."""
        err = ValueError("invalid token")
        result = TokenValidationResult(is_valid=False, error=err)

        assert result.is_valid is False
        assert result.user_id is None
        assert result.username is None
        assert isinstance(result.error, ValueError)


# NOTE: Special ML considerations are not applicable to this auth module;
# however, tests are marked appropriately and remain isolated, deterministic,
# and free of external dependencies by design.
