"""Logging utilities for FXML4.

This module provides centralized logging configuration and utilities
for the FXML4 trading system.
"""

import logging
import sys
from typing import Optional


def get_logger(name: Optional[str] = None) -> logging.Logger:
    """Get a logger with the given name.

    Args:
        name: Logger name. If None, uses the calling module's name.

    Returns:
        Logger instance configured for FXML4.
    """
    if name is None:
        # Get the calling module's name
        frame = sys._getframe(1)
        module = frame.f_globals.get("__name__", "unknown")
        name = module

    logger = logging.getLogger(name)

    # Set up basic configuration if not already configured
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)

    return logger


def configure_logging(level: str = "INFO", format_string: Optional[str] = None) -> None:
    """Configure logging for the entire FXML4 system.

    Args:
        level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL).
        format_string: Custom format string for log messages.
    """
    numeric_level = getattr(logging, level.upper(), logging.INFO)

    if format_string is None:
        format_string = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

    logging.basicConfig(level=numeric_level, format=format_string, stream=sys.stdout)
