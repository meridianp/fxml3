"""
Core package for fxml4.
"""

__version__ = "0.1.0"

from .config import BaseConfig
from .exceptions import ConfigError, Fxml4CoreException
from .logging import configure_logging, logger
from .types import JSONType, PathLike

__all__ = [
    "BaseConfig",
    "ConfigError", 
    "Fxml4CoreException",
    "configure_logging",
    "logger",
    "JSONType",
    "PathLike",
]