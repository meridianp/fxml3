"""
API middleware package for FXML4.

This package contains middleware for security, authentication, rate limiting,
and other cross-cutting concerns.
"""

from .security import SecurityMiddleware

__all__ = ["SecurityMiddleware"]
