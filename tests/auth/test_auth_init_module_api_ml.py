"""
Machine-learning style unit tests for fxml4.api.auth package __init__ exports.

- Validates public API surface via __all__
- Ensures star-import behavior respects current exports
- Verifies reloading picks up submodule changes (mocked)
- Confirms exception hierarchy and error handling patterns

These are lightweight tests focusing on wiring, security exposure, and
boundary behaviors while avoiding any real broker/db/network interactions.
"""

import importlib
from types import ModuleType
from typing import Dict
from unittest.mock import MagicMock

import pytest

import fxml4.api.auth as auth_module

# Apply common markers to this module
pytestmark = [pytest.mark.unit, pytest.mark.machine_learning]


# Test fixtures
@pytest.fixture
def sample_data() -> Dict[str, str]:
    """Mock user-like data for tests following project conventions."""
    return {"user_id": "u-001", "username": "alice", "email": "a@example.com"}


def test_public_api_when_importing_package_then_names_match_dunder_all():
    """Ensure exported names are unique and present on the module."""
    assert isinstance(auth_module.__all__, list)

    # No duplicates in __all__
    assert len(auth_module.__all__) == len(set(auth_module.__all__))

    # Every name is a non-empty string and exists as an attribute
    for name in auth_module.__all__:
        assert isinstance(name, str) and name.strip() != ""
        assert hasattr(auth_module, name), f"Exported name missing: {name}"


def test_star_import_when_dunder_all_modified_then_star_respects_current_list(
    monkeypatch,
):
    """Star import should respect current __all__ contents at import time."""
    original_all = list(auth_module.__all__)
    try:
        reduced = original_all[:5]  # boundary: subset of exports
        monkeypatch.setattr(auth_module, "__all__", reduced, raising=True)

        ns: dict = {}
        exec("from fxml4.api.auth import *", {}, ns)

        # Only the reduced set should be imported
        assert set(ns.keys()).issuperset(set(reduced))
        # A name excluded from reduced list should not appear via star import
        if len(original_all) > len(reduced):
            excluded = original_all[-1]
            assert excluded not in ns
    finally:
        # Restore original __all__ to avoid cross-test contamination
        monkeypatch.setattr(auth_module, "__all__", original_all, raising=True)


def test_reload_when_jwtservice_replaced_then_export_updates(monkeypatch):
    """Reload auth package and verify exports update to patched submodule symbol."""
    # Import submodule directly so we can patch its class
    jwt_submod = importlib.import_module("fxml4.api.auth.jwt_service")

    # Keep originals for cleanup
    original_jwt_cls = getattr(jwt_submod, "JWTService")

    # Create a sentinel replacement class
    class SentinelJWTService:  # noqa: D401 - trivial sentinel
        """Sentinel for testing export wiring."""

        pass

    try:
        # Replace in submodule, then reload the package init to rebind
        monkeypatch.setattr(jwt_submod, "JWTService", SentinelJWTService, raising=True)
        importlib.reload(auth_module)  # rebinds from submodule

        # Export should now point to the sentinel
        assert auth_module.JWTService is SentinelJWTService
    finally:
        # Restore original, reload to rebind, keep environment clean
        monkeypatch.setattr(jwt_submod, "JWTService", original_jwt_cls, raising=True)
        importlib.reload(auth_module)


def test_exceptions_when_raised_then_catch_hierarchy_correctly():
    """Validate exception inheritance and message propagation for key exports."""
    # Import names through the package to validate bindings
    from fxml4.api.auth import AuthenticationError, InvalidTokenError, TokenExpiredError

    with pytest.raises(AuthenticationError):
        raise AuthenticationError("base auth error")

    with pytest.raises(AuthenticationError):
        # Subclass should be catchable by base
        raise InvalidTokenError("invalid token signature")

    # Specific subclass catch
    with pytest.raises(TokenExpiredError) as ei:
        raise TokenExpiredError("expired")
    assert "expired" in str(ei.value)


def test_namespace_when_dir_filtered_then_contains_all_exports_only():
    """dir(module) contains exports; no internal module names leaked via star-import."""
    names = set(dir(auth_module))
    exported = set(auth_module.__all__)

    # All exported names should appear in dir(module)
    assert exported.issubset(names)

    # Ensure internal submodule names are not in star-import results
    ns: dict = {}
    exec("from fxml4.api.auth import *", {}, ns)
    for internal in ("models", "jwt_service", "password_service"):
        assert internal not in ns
