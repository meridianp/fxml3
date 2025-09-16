"""Core utilities and exceptions for FXML4.

This module provides core functionality used across the FXML4 system,
including common exceptions, utilities, and base classes.
"""

from .exceptions import ConfigurationError, FXMLError, ValidationError

__all__ = ["FXMLError", "ConfigurationError", "ValidationError"]
