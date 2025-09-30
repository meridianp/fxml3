"""
Database Security Utilities
Prevents SQL injection and validates database identifiers
"""

import re
from typing import List, Pattern
import logging

logger = logging.getLogger(__name__)

# Allowed table patterns for ANALYZE and VACUUM operations
ALLOWED_TABLE_PATTERNS: List[str] = [
    r'^market_data_[a-z_]+$',
    r'^order_[a-z_]+$',
    r'^trade_[a-z_]+$',
    r'^risk_[a-z_]+$',
    r'^performance_[a-z_]+$',
    r'^analytics\.[a-z_]+$',
]

# Explicit whitelist of allowed tables for maintenance operations
ALLOWED_TABLES: List[str] = [
    # Market data tables
    "market_data_ticks",
    "market_data_candles",
    "market_data",

    # Order tables
    "order_executions",
    "orders",

    # Trade tables
    "trade_fills",
    "trades",

    # Risk tables
    "risk_events",

    # Performance tables
    "performance_metrics",

    # Analytics schema tables
    "analytics.fact_trades",
    "analytics.dim_symbols",
    "analytics.dim_accounts",
    "analytics.fact_orders",
    "analytics.fact_performance",
    "analytics.fact_risk_metrics",
    "analytics.fact_market_data",
]

# Compiled regex patterns for validation
_TABLE_NAME_PATTERN: Pattern = re.compile(r'^[a-zA-Z_][a-zA-Z0-9_]*$')
_QUALIFIED_TABLE_PATTERN: Pattern = re.compile(r'^[a-zA-Z_][a-zA-Z0-9_]*\.[a-zA-Z_][a-zA-Z0-9_]*$')


def validate_table_name(table: str) -> str:
    """
    Validate and sanitize table name to prevent SQL injection.

    This function ensures that table names:
    1. Match expected patterns (alphanumeric + underscores)
    2. Are in the whitelist or match allowed patterns
    3. Don't contain SQL injection attempts

    Args:
        table: Table name to validate

    Returns:
        Validated table name (unchanged if valid)

    Raises:
        ValueError: If table name is invalid or contains malicious patterns

    Examples:
        >>> validate_table_name("market_data_ticks")
        'market_data_ticks'
        >>> validate_table_name("users; DROP TABLE")
        ValueError: Invalid table name
    """
    if not table:
        raise ValueError("Table name cannot be empty")

    # Check length
    if len(table) > 128:
        raise ValueError(f"Table name too long: {len(table)} characters (max 128)")

    # Remove leading/trailing whitespace
    table = table.strip()

    # Check for SQL injection patterns
    # These are literal characters that should never appear in table names
    forbidden_chars = [
        ';',      # SQL statement separator
        '--',     # SQL comment
        '/*',     # SQL comment start
        '*/',     # SQL comment end
        "'",      # String delimiter
        '"',      # String delimiter (but allowed for escaping in another function)
        '`',      # Identifier delimiter
        '\\',     # Escape character
        '/',      # Path separator
        '..',     # Path traversal
    ]

    for char in forbidden_chars:
        if char in table:
            logger.warning(f"SQL injection attempt detected in table name: {table}")
            raise ValueError(
                f"Invalid table name: contains forbidden character '{char}'"
            )

    # Check for SQL keywords as separate words (using regex word boundaries)
    # Only flag if they appear as complete words in uppercase
    sql_keywords_pattern = re.compile(
        r'\b(DROP|DELETE|INSERT|UPDATE|EXEC|UNION|xp_|sp_)\b',
        re.IGNORECASE
    )
    if sql_keywords_pattern.search(table):
        logger.warning(f"SQL injection attempt detected in table name: {table}")
        raise ValueError(
            f"Invalid table name: contains SQL keyword"
        )

    # Check if it's a qualified name (schema.table)
    if '.' in table:
        if not _QUALIFIED_TABLE_PATTERN.match(table):
            raise ValueError(
                f"Invalid qualified table name format: {table}"
            )
        schema, table_part = table.split('.', 1)

        # Only allow analytics schema for qualified names
        if schema != 'analytics':
            raise ValueError(
                f"Schema '{schema}' not allowed. Only 'analytics' schema is permitted."
            )
    else:
        # Simple table name validation
        if not _TABLE_NAME_PATTERN.match(table):
            raise ValueError(
                f"Invalid table name format: {table}. "
                "Must start with letter/underscore and contain only alphanumeric/underscores."
            )

    # Check against whitelist
    if table in ALLOWED_TABLES:
        return table

    # Check against allowed patterns
    for pattern in ALLOWED_TABLE_PATTERNS:
        if re.match(pattern, table):
            return table

    # If we get here, table is not in whitelist
    logger.warning(
        f"Table '{table}' not in whitelist. "
        f"Allowed tables: {', '.join(ALLOWED_TABLES[:5])}..."
    )
    raise ValueError(
        f"Table '{table}' not in allowed tables list. "
        "Contact administrator to add table to whitelist."
    )


def escape_identifier(identifier: str) -> str:
    """
    Escape SQL identifier (table or column name) for safe use in queries.

    Uses PostgreSQL identifier escaping rules:
    - Wraps identifier in double quotes
    - Escapes any double quotes within the identifier

    Args:
        identifier: SQL identifier to escape

    Returns:
        Escaped identifier safe for use in SQL

    Examples:
        >>> escape_identifier("market_data")
        '"market_data"'
        >>> escape_identifier('table"name')
        '"table""name"'
    """
    if not identifier:
        raise ValueError("Identifier cannot be empty")

    # First validate the identifier format
    if not (_TABLE_NAME_PATTERN.match(identifier) or _QUALIFIED_TABLE_PATTERN.match(identifier)):
        raise ValueError(f"Invalid identifier format: {identifier}")

    # Escape double quotes by doubling them
    escaped = identifier.replace('"', '""')

    # Wrap in double quotes for PostgreSQL identifier quoting
    return f'"{escaped}"'


def build_analyze_query(table: str) -> str:
    """
    Build a safe ANALYZE query with validated table name.

    Args:
        table: Table name to analyze

    Returns:
        Safe SQL query string

    Raises:
        ValueError: If table name is invalid
    """
    validated_table = validate_table_name(table)
    # Use identifier escaping for extra safety
    escaped_table = escape_identifier(validated_table)
    return f"ANALYZE {escaped_table}"


def build_vacuum_query(table: str) -> str:
    """
    Build a safe VACUUM ANALYZE query with validated table name.

    Args:
        table: Table name to vacuum

    Returns:
        Safe SQL query string

    Raises:
        ValueError: If table name is invalid
    """
    validated_table = validate_table_name(table)
    escaped_table = escape_identifier(validated_table)
    return f"VACUUM ANALYZE {escaped_table}"


def is_table_allowed(table: str) -> bool:
    """
    Check if a table name is in the allowed list without raising exceptions.

    Args:
        table: Table name to check

    Returns:
        True if table is allowed, False otherwise
    """
    try:
        validate_table_name(table)
        return True
    except ValueError:
        return False
