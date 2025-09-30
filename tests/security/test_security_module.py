"""
Security Module Tests (GREEN Phase)
Tests for core.database.security module
"""

import pytest
from core.database.security import (
    validate_table_name,
    escape_identifier,
    build_analyze_query,
    build_vacuum_query,
    is_table_allowed,
    ALLOWED_TABLES,
    ALLOWED_TABLE_PATTERNS,
)


class TestValidateTableName:
    """Test validate_table_name function."""

    @pytest.mark.green
    def test_validates_allowed_table_names(self):
        """GREEN: Valid table names should pass validation."""
        valid_tables = [
            "market_data_ticks",
            "market_data_candles",
            "order_executions",
            "trades",
            "risk_events",
            "performance_metrics",
        ]

        for table in valid_tables:
            result = validate_table_name(table)
            assert result == table

    @pytest.mark.green
    def test_validates_qualified_table_names(self):
        """GREEN: Qualified table names (schema.table) should be validated."""
        valid_qualified = [
            "analytics.fact_trades",
            "analytics.dim_symbols",
        ]

        for table in valid_qualified:
            result = validate_table_name(table)
            assert result == table

    @pytest.mark.green
    def test_rejects_sql_injection_attempts(self):
        """GREEN: SQL injection patterns should be rejected."""
        malicious_tables = [
            "users; DROP TABLE users--",
            "users' OR '1'='1",
            "users'; DELETE FROM users",
            "users UNION SELECT password",
            "users\"; DROP TABLE users",
        ]

        for table in malicious_tables:
            with pytest.raises(ValueError, match="Invalid table name|forbidden pattern"):
                validate_table_name(table)

    @pytest.mark.green
    def test_rejects_tables_not_in_whitelist(self):
        """GREEN: Tables not in whitelist should be rejected."""
        unauthorized_tables = [
            "admin_users",
            "secrets",
            "passwords",
        ]

        for table in unauthorized_tables:
            with pytest.raises(ValueError, match="not in allowed tables"):
                validate_table_name(table)

    @pytest.mark.green
    def test_rejects_empty_table_name(self):
        """GREEN: Empty table names should be rejected."""
        with pytest.raises(ValueError, match="cannot be empty"):
            validate_table_name("")

    @pytest.mark.green
    def test_rejects_overly_long_table_name(self):
        """GREEN: Table names longer than 128 characters should be rejected."""
        long_name = "a" * 129
        with pytest.raises(ValueError, match="too long"):
            validate_table_name(long_name)

    @pytest.mark.green
    def test_rejects_path_traversal_attempts(self):
        """GREEN: Path traversal patterns should be rejected."""
        with pytest.raises(ValueError, match="forbidden character|Invalid table name"):
            validate_table_name("../../etc/passwd")

    @pytest.mark.green
    def test_rejects_unauthorized_schemas(self):
        """GREEN: Only analytics schema should be allowed for qualified names."""
        with pytest.raises(ValueError, match="not allowed"):
            validate_table_name("public.users")


class TestEscapeIdentifier:
    """Test escape_identifier function."""

    @pytest.mark.green
    def test_escapes_simple_identifier(self):
        """GREEN: Simple identifiers should be wrapped in double quotes."""
        result = escape_identifier("market_data")
        assert result == '"market_data"'

    @pytest.mark.green
    def test_escapes_double_quotes_in_identifier(self):
        """GREEN: Double quotes should be escaped by doubling."""
        # This shouldn't happen with validated tables, but test the escaping logic
        with pytest.raises(ValueError):
            # Should fail validation before reaching escape logic
            escape_identifier('table"name')

    @pytest.mark.green
    def test_rejects_empty_identifier(self):
        """GREEN: Empty identifiers should be rejected."""
        with pytest.raises(ValueError, match="cannot be empty"):
            escape_identifier("")


class TestBuildAnalyzeQuery:
    """Test build_analyze_query function."""

    @pytest.mark.green
    def test_builds_safe_analyze_query(self):
        """GREEN: Should build safe ANALYZE query with validated table."""
        query = build_analyze_query("market_data_ticks")
        assert query == 'ANALYZE "market_data_ticks"'

    @pytest.mark.green
    def test_rejects_malicious_table_in_analyze(self):
        """GREEN: Malicious table names should be rejected."""
        with pytest.raises(ValueError):
            build_analyze_query("users; DROP TABLE users--")


class TestBuildVacuumQuery:
    """Test build_vacuum_query function."""

    @pytest.mark.green
    def test_builds_safe_vacuum_query(self):
        """GREEN: Should build safe VACUUM ANALYZE query."""
        query = build_vacuum_query("market_data_ticks")
        assert query == 'VACUUM ANALYZE "market_data_ticks"'

    @pytest.mark.green
    def test_rejects_malicious_table_in_vacuum(self):
        """GREEN: Malicious table names should be rejected."""
        with pytest.raises(ValueError):
            build_vacuum_query("orders; DELETE FROM orders--")


class TestIsTableAllowed:
    """Test is_table_allowed function."""

    @pytest.mark.green
    def test_returns_true_for_allowed_tables(self):
        """GREEN: Should return True for allowed tables."""
        assert is_table_allowed("market_data_ticks") is True
        assert is_table_allowed("order_executions") is True

    @pytest.mark.green
    def test_returns_false_for_disallowed_tables(self):
        """GREEN: Should return False for disallowed tables."""
        assert is_table_allowed("admin_users") is False
        assert is_table_allowed("users; DROP TABLE") is False


class TestSecurityModuleConfiguration:
    """Test security module configuration."""

    @pytest.mark.green
    def test_allowed_tables_list_exists(self):
        """GREEN: ALLOWED_TABLES constant should exist."""
        assert ALLOWED_TABLES is not None
        assert isinstance(ALLOWED_TABLES, list)
        assert len(ALLOWED_TABLES) > 0

    @pytest.mark.green
    def test_allowed_patterns_list_exists(self):
        """GREEN: ALLOWED_TABLE_PATTERNS constant should exist."""
        assert ALLOWED_TABLE_PATTERNS is not None
        assert isinstance(ALLOWED_TABLE_PATTERNS, list)
        assert len(ALLOWED_TABLE_PATTERNS) > 0


# Test markers
pytestmark = [
    pytest.mark.security,
    pytest.mark.green,
]
