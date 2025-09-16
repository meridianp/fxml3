"""Tests for exceptions module."""

import pytest
from fxml4_core.exceptions import (
    Fxml4CoreException,
    ConfigError,
    ValidationError,
    NotFoundError,
    AuthenticationError,
    AuthorizationError,
)


def test_base_exception():
    """Test base exception."""
    exc = Fxml4CoreException("Test error", error_code="TEST_ERROR", details={"key": "value"})
    assert str(exc) == "Test error"
    assert exc.error_code == "TEST_ERROR"
    assert exc.details == {"key": "value"}


def test_config_error():
    """Test configuration error."""
    exc = ConfigError("Invalid config", field="database_url")
    assert str(exc) == "Invalid config"
    assert exc.error_code == "CONFIG_ERROR"
    assert exc.details["field"] == "database_url"


def test_validation_error():
    """Test validation error."""
    errors = {"field1": "required", "field2": "invalid format"}
    exc = ValidationError("Validation failed", errors=errors)
    assert exc.error_code == "VALIDATION_ERROR"
    assert exc.details["errors"] == errors


def test_not_found_error():
    """Test not found error."""
    exc = NotFoundError("User", 123)
    assert str(exc) == "User not found: 123"
    assert exc.error_code == "NOT_FOUND"
    assert exc.details["resource_type"] == "User"
    assert exc.details["identifier"] == 123


def test_authentication_error():
    """Test authentication error."""
    exc = AuthenticationError()
    assert str(exc) == "Authentication failed"
    assert exc.error_code == "AUTHENTICATION_ERROR"


def test_authorization_error():
    """Test authorization error."""
    exc = AuthorizationError("Insufficient permissions")
    assert str(exc) == "Insufficient permissions"
    assert exc.error_code == "AUTHORIZATION_ERROR"