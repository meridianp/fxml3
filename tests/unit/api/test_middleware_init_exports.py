"""Tests for fxml4.api.middleware package __init__ exports.

These tests verify that the package exposes the correct public API via
__all__ and star imports, and that reloading honors patched dependencies.
"""

import importlib
from types import ModuleType
from unittest.mock import MagicMock

import pytest

# Star import as per requested structure for validation of __all__ behavior
from fxml4.api.middleware.__init__ import *  # noqa: F401,F403 - intentional star import for export testing


# Test fixtures
@pytest.fixture
def sample_data():
    """Mock data fixture representing minimal ML-like structure.

    While the target module is not ML-specific, this fixture provides a
    consistent shape used across FXML4 tests for potential future expansion.
    """
    return {
        "features": [[1.0, 2.0, 3.0], [0.0, -1.0, 5.0]],
        "labels": [1, 0],
        "metadata": {"symbol": "EURUSD", "window": 3},
    }


@pytest.mark.unit
@pytest.mark.api
@pytest.mark.ml
@pytest.mark.fast
def test_module_exports_when_star_import_then_security_middleware_available():
    """Ensure star import exposes only the intended public symbol.

    Given the package uses __all__ to re-export symbols,
    When importing via star import,
    Then SecurityMiddleware is available as a public symbol.
    """
    # SecurityMiddleware is imported via the star import at module import time
    assert (
        "SecurityMiddleware" in globals()
    ), "SecurityMiddleware should be exported via __all__"
    assert isinstance(
        SecurityMiddleware, type
    ), "Exported SecurityMiddleware should be a class"


@pytest.mark.unit
@pytest.mark.api
@pytest.mark.fast
def test_dunder_all_when_import_module_then_contains_only_security_middleware():
    """Verify __all__ contains exactly the expected export(s)."""
    init_mod = importlib.import_module("fxml4.api.middleware.__init__")
    assert hasattr(init_mod, "__all__") and isinstance(init_mod.__all__, list)
    assert init_mod.__all__ == [
        "SecurityMiddleware"
    ], "__all__ must only expose SecurityMiddleware"


@pytest.mark.unit
@pytest.mark.api
@pytest.mark.fast
def test_star_import_when_access_non_exported_then_name_error():
    """Accessing non-exported objects via star import should fail with NameError."""
    # DevelopmentSecurityMiddleware exists in sibling module but should not be exported here
    with pytest.raises(NameError):
        eval("DevelopmentSecurityMiddleware")


@pytest.mark.unit
@pytest.mark.api
@pytest.mark.fast
def test_module_docstring_when_loaded_then_contains_expected_keywords():
    """Package docstring should be present and mention API middleware scope."""
    init_mod = importlib.import_module("fxml4.api.middleware.__init__")
    assert isinstance(init_mod.__doc__, str) and len(init_mod.__doc__) > 0
    assert "API middleware" in init_mod.__doc__
    assert "FXML4" in init_mod.__doc__


@pytest.mark.unit
@pytest.mark.api
@pytest.mark.fast
def test_reexport_binding_when_security_middleware_mocked_then_reload_exposes_mock(
    monkeypatch,
):
    """Reload should rebind exported symbol from the underlying module.

    Given SecurityMiddleware is provided by fxml4.api.middleware.security,
    When that attribute is monkeypatched and __init__ is reloaded,
    Then the exported SecurityMiddleware reference should point to the mocked object.
    """
    # Arrange: patch the underlying provider module
    security_mod = importlib.import_module("fxml4.api.middleware.security")

    class FakeSecurityMiddleware:
        pass

    monkeypatch.setattr(
        security_mod, "SecurityMiddleware", FakeSecurityMiddleware, raising=False
    )

    # Act: reload the package __init__ to rebind the export
    init_mod = importlib.import_module("fxml4.api.middleware.__init__")
    reloaded = importlib.reload(init_mod)

    # Assert: exported binding now references the fake implementation
    assert getattr(reloaded, "SecurityMiddleware") is FakeSecurityMiddleware


@pytest.mark.unit
@pytest.mark.api
@pytest.mark.fast
def test_no_unintended_public_symbols_when_inspecting_dir_then_only_expected_present():
    """Ensure the package namespace does not leak unintended public attributes."""
    init_mod = importlib.import_module("fxml4.api.middleware.__init__")
    public_symbols = [name for name in dir(init_mod) if not name.startswith("_")]
    # Only SecurityMiddleware should be public (module attributes like annotations omitted)
    assert public_symbols == [
        "SecurityMiddleware"
    ], f"Unexpected public symbols: {public_symbols}"
