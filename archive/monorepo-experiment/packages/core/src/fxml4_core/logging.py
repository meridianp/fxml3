"""Structured logging configuration using structlog."""

import logging
import sys
from typing import Any, Dict, Optional

import structlog
from structlog.processors import CallsiteParameter


def configure_logging(
    level: Optional[int] = None,
    format_as_json: bool = True,
    add_timestamp: bool = True,
) -> None:
    """
    Configure structlog for structured logging.
    
    Args:
        level: Logging level (defaults to INFO)
        format_as_json: Whether to output logs as JSON
        add_timestamp: Whether to add timestamps to logs
    """
    if level is None:
        level = logging.INFO
        
    # Configure Python's logging
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=level,
    )
    
    # Build processor list
    processors = [
        structlog.threadlocal.merge_threadlocal_context,
        structlog.processors.add_log_level,
        structlog.processors.CallsiteParameterAdder(
            parameters=[
                CallsiteParameter.FILENAME,
                CallsiteParameter.FUNC_NAME,
                CallsiteParameter.LINENO,
            ]
        ),
    ]
    
    if add_timestamp:
        processors.append(structlog.processors.TimeStamper(fmt="iso"))
    
    # Add final renderer
    if format_as_json:
        processors.append(structlog.processors.JSONRenderer())
    else:
        processors.append(structlog.dev.ConsoleRenderer())
    
    # Configure structlog
    structlog.configure(
        processors=processors,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )


def get_logger(name: Optional[str] = None, **kwargs: Any) -> structlog.BoundLogger:
    """
    Get a configured logger instance.
    
    Args:
        name: Logger name (defaults to module name)
        **kwargs: Additional context to bind to the logger
        
    Returns:
        Configured logger instance
    """
    logger = structlog.get_logger(name)
    if kwargs:
        logger = logger.bind(**kwargs)
    return logger


# Default logger instance
logger = get_logger()