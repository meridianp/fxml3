"""
API routers package.

This package contains all the API route handlers organized by functionality.
"""

from .core import router as core_router
from .legacy_auth import router as legacy_auth_router

# Import TDD-validated authentication router
try:
    from .auth_tdd import router as auth_tdd_router
except ImportError:
    auth_tdd_router = None

# Import TDD-validated user CRUD router
try:
    from .user_crud_tdd import router as user_crud_tdd_router
except ImportError:
    user_crud_tdd_router = None

# Import other routers conditionally to avoid import errors during development
try:
    from .data import router as data_router
except ImportError:
    data_router = None

try:
    from .signals import router as signals_router
except ImportError:
    signals_router = None

try:
    from .backtest import router as backtest_router
except ImportError:
    backtest_router = None

try:
    from .performance import router as performance_router
except ImportError:
    performance_router = None

__all__ = [
    "core_router",
    "data_router",
    "signals_router",
    "backtest_router",
    "performance_router",
    "legacy_auth_router",
    "auth_tdd_router",
    "user_crud_tdd_router",
]
