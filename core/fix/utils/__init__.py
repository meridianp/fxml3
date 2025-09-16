"""FIX Protocol Utilities Module.

This module provides utility functions and classes for FIX protocol operations,
including message parsing, validation, and formatting.

Performance note: Use fast_* functions for high-frequency trading operations.
"""

from .builder import (
    FIXBuilder,
    FIXBuildError,
    FIXMessageBuilder,
    build_fix_from_dict,
    build_fix_message,
)
from .fast_builder import (
    FastFIXBuilder,
    build_fix_message_fast,
    build_heartbeat_fast,
    build_new_order_fast,
    fast_build_fix,
    validate_message_fast,
)

# Performance-optimized implementations
from .fast_parser import (
    FastFIXParser,
    fast_parse_fix,
    get_message_type,
    is_admin_message,
    is_order_message,
    parse_fix_message_fast,
)
from .parser import FIXParseError, FIXParser, parse_fix_message, parse_fix_messages

__all__ = [
    # Standard implementations
    "FIXParser",
    "FIXParseError",
    "parse_fix_message",
    "parse_fix_messages",
    "FIXBuilder",
    "FIXBuildError",
    "FIXMessageBuilder",  # Backward compatibility alias
    "build_fix_message",
    "build_fix_from_dict",
    # Fast implementations for high-performance operations
    "FastFIXParser",
    "fast_parse_fix",
    "get_message_type",
    "is_order_message",
    "is_admin_message",
    "parse_fix_message_fast",
    "FastFIXBuilder",
    "fast_build_fix",
    "build_heartbeat_fast",
    "build_new_order_fast",
    "build_fix_message_fast",
    "validate_message_fast",
]
