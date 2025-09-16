"""
Tests for fxml4.api.auth package exports.

- Verifies that __all__ accurately exposes public API symbols
- Ensures star-import imports only intended names
- Confirms exported names map to underlying implementations
- Uses mocking to simulate external dependencies without side effects

These are lightweight unit tests focused on security/auth export wiring.
"""

import importlib
import types
from unittest.mock import MagicMock, Mock, patch

import pytest

import fxml4.api.auth as auth_module
from fxml4.api.auth import *  # noqa: F401,F403 — validate star-import behavior

# Apply common markers to this module
pytestmark = [pytest.mark.unit, pytest.mark.machine_learning]


@pytest.fixture
def sample_data():
    """Provide minimal mock data for tests.

    While not directly used for ML here, this fixture conforms to
    project conventions and can be extended if auth exports evolve.
    """
    return {"user_id": "u1", "username": "tester", "email": "t@example.com"}


def test_exports_when_module_imported_then_expected_symbols_available():
    """Ensure fxml4.api.auth exposes the intended public API via __all__."""
    expected = {
        "User",
        "UserRole",
        "Permission",
        "TokenPair",
        "TokenValidationResult",
        "PasswordValidationResult",
        "AuthenticationError",
        "TokenExpiredError",
        "InvalidTokenError",
        "KeyRotationError",
        "UserLockedError",
        "InsufficientPermissionsError",
        "WeakPasswordError",
        "PasswordReuseError",
        "PasswordExpiredError",
        "JWTService",
        "PasswordService",
    }

    assert isinstance(auth_module.__all__, list)
    assert set(auth_module.__all__) == expected

    # All exported names should exist as attributes on the module
    for name in expected:
        assert hasattr(auth_module, name), f"Missing export: {name}"


def test_star_import_when_used_then_only_exports_in_namespace():
    """Validate that star-import brings only names listed in __all__."""
    namespace: dict[str, object] = {}
    exec("from fxml4.api.auth import *", {}, namespace)

    exported = set(auth_module.__all__)
    # All exported items should be present
    for name in exported:
        assert name in namespace, f"Star import missing: {name}"

    # A few non-exported candidates should not appear
    for name in ["models", "jwt", "jwt_service", "password_service", "__all__"]:
        assert name not in namespace, f"Unexpected name leaked via star import: {name}"


def test_export_identity_when_compared_with_source_modules_then_matches():
    """Verify exported objects are identical to their source definitions."""
    import fxml4.api.auth.jwt_service as js
    import fxml4.api.auth.models as models
    import fxml4.api.auth.password_service as ps

    # Classes from submodules
    assert auth_module.JWTService is js.JWTService
    assert auth_module.PasswordService is ps.PasswordService

    # Models and exceptions
    assert auth_module.User is models.User
    assert auth_module.UserRole is models.UserRole
    assert auth_module.Permission is models.Permission
    assert auth_module.TokenPair is models.TokenPair
    assert auth_module.TokenValidationResult is models.TokenValidationResult
    assert auth_module.PasswordValidationResult is models.PasswordValidationResult

    assert auth_module.AuthenticationError is models.AuthenticationError
    assert auth_module.TokenExpiredError is models.TokenExpiredError
    assert auth_module.InvalidTokenError is models.InvalidTokenError
    assert auth_module.KeyRotationError is models.KeyRotationError
    assert auth_module.UserLockedError is models.UserLockedError
    assert (
        auth_module.InsufficientPermissionsError is models.InsufficientPermissionsError
    )
    assert auth_module.WeakPasswordError is models.WeakPasswordError
    assert auth_module.PasswordReuseError is models.PasswordReuseError


def test_docstring_when_inspected_then_contains_auth_summary():
    """Basic sanity: module docstring highlights auth responsibilities."""
    assert isinstance(auth_module.__doc__, str)
    assert "Authentication and authorization module" in auth_module.__doc__


def test_negative_when_accessing_nonexistent_attribute_then_attribute_error():
    """Accessing non-exported, nonexistent attributes should fail predictably."""
    with pytest.raises(AttributeError):
        getattr(auth_module, "NonExistingClassOrFunction")
    assert "NonExistingClassOrFunction" not in getattr(auth_module, "__all__", [])


def test_star_import_with_mock_when_mocking_exported_class_then_used_in_namespace(
    monkeypatch,
):
    """Mock an exported class and verify star-import uses the mock.

    This demonstrates safe mocking of an external dependency without invoking
    real broker/network interactions.
    """
    original_jwt_service = auth_module.JWTService
    mock_jwt_service = MagicMock(name="MockJWTService")
    monkeypatch.setattr(auth_module, "JWTService", mock_jwt_service, raising=True)

    ns: dict[str, object] = {}
    exec("from fxml4.api.auth import *", {}, ns)
    try:
        assert ns["JWTService"] is mock_jwt_service
    finally:
        # Ensure no cross-test contamination
        monkeypatch.setattr(
            auth_module, "JWTService", original_jwt_service, raising=True
        )


def test_boundary_when_iterating_exports_then_no_empty_or_nonstring_names():
    """Boundary check: __all__ contains only non-empty strings."""
    for name in auth_module.__all__:
        assert isinstance(name, str)
        assert name.strip() != ""


def test_exceptions_when_instantiated_then_behave_like_exceptions():
    """Smoke test for exported exception classes and messages."""
    e = AuthenticationError("auth fail")
    assert isinstance(e, Exception)
    assert str(e) == "auth fail"

    e2 = InvalidTokenError("bad token")
    assert isinstance(e2, AuthenticationError)
    assert "bad token" in str(e2)
