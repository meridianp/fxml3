"""Custom exception classes for fxml4."""

from typing import Any, Dict, Optional


class Fxml4CoreException(Exception):
    """
    Base exception for fxml4 core package.
    
    All custom exceptions should inherit from this class.
    """
    
    def __init__(
        self,
        message: str,
        error_code: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(message)
        self.message = message
        self.error_code = error_code
        self.details = details or {}


class ConfigError(Fxml4CoreException):
    """Exception raised for configuration errors."""
    
    def __init__(self, message: str, field: Optional[str] = None):
        super().__init__(
            message=message,
            error_code="CONFIG_ERROR",
            details={"field": field} if field else {},
        )


class ValidationError(Fxml4CoreException):
    """Exception raised for validation errors."""
    
    def __init__(self, message: str, errors: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=message,
            error_code="VALIDATION_ERROR",
            details={"errors": errors} if errors else {},
        )


class NotFoundError(Fxml4CoreException):
    """Exception raised when a resource is not found."""
    
    def __init__(self, resource_type: str, identifier: Any):
        super().__init__(
            message=f"{resource_type} not found: {identifier}",
            error_code="NOT_FOUND",
            details={"resource_type": resource_type, "identifier": identifier},
        )


class AuthenticationError(Fxml4CoreException):
    """Exception raised for authentication failures."""
    
    def __init__(self, message: str = "Authentication failed"):
        super().__init__(
            message=message,
            error_code="AUTHENTICATION_ERROR",
        )


class AuthorizationError(Fxml4CoreException):
    """Exception raised for authorization failures."""
    
    def __init__(self, message: str = "Access denied"):
        super().__init__(
            message=message,
            error_code="AUTHORIZATION_ERROR",
        )