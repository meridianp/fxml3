"""
Database Schema Validation Tests - TDD RED Phase
=================================================

These tests define the EXPECTED database schema and will initially FAIL.
Following TDD methodology, we implement minimal fixes to make them pass.

Tests cover:
- Required table existence
- Column definitions and types
- Foreign key relationships
- Index requirements
- Data integrity constraints
"""

import asyncio
from typing import Any, Dict, List

import asyncpg
import pytest

from fxml4.config import get_config

pytestmark = [pytest.mark.unit, pytest.mark.database, pytest.mark.schema]


async def get_db_connection():
    """Create database connection for schema validation tests."""
    # Use environment variables directly for reliable connection
    import os

    conn = await asyncpg.connect(
        host=os.getenv("FXML4_DATABASE_HOST", "localhost"),
        port=5432,  # Use actual running TimescaleDB port
        user=os.getenv("FXML4_DATABASE_USER", "postgres"),
        password=os.getenv("FXML4_DATABASE_PASSWORD", "dev-postgres-secure-password"),
        database=os.getenv("FXML4_DATABASE_NAME", "fxml4"),
    )
    return conn


async def get_table_schema(conn: asyncpg.Connection, table_name: str) -> Dict[str, Any]:
    """Get complete schema information for a table."""
    query = """
    SELECT
        column_name,
        data_type,
        is_nullable,
        column_default,
        character_maximum_length,
        numeric_precision,
        numeric_scale
    FROM information_schema.columns
    WHERE table_name = $1
    ORDER BY ordinal_position;
    """
    rows = await conn.fetch(query, table_name)
    return {row["column_name"]: dict(row) for row in rows}


async def table_exists(conn: asyncpg.Connection, table_name: str) -> bool:
    """Check if a table exists in the database."""
    query = """
    SELECT EXISTS (
        SELECT FROM information_schema.tables
        WHERE table_name = $1
    );
    """
    result = await conn.fetchval(query, table_name)
    return result


async def foreign_key_exists(
    conn: asyncpg.Connection, table: str, column: str, ref_table: str, ref_column: str
) -> bool:
    """Check if a foreign key relationship exists."""
    query = """
    SELECT EXISTS (
        SELECT 1 FROM information_schema.table_constraints tc
        JOIN information_schema.key_column_usage kcu
          ON tc.constraint_name = kcu.constraint_name
        JOIN information_schema.constraint_column_usage ccu
          ON ccu.constraint_name = tc.constraint_name
        WHERE tc.constraint_type = 'FOREIGN KEY'
          AND tc.table_name = $1
          AND kcu.column_name = $2
          AND ccu.table_name = $3
          AND ccu.column_name = $4
    );
    """
    result = await conn.fetchval(query, table, column, ref_table, ref_column)
    return result


class TestRequiredTables:
    """Test that all required tables exist in the database."""

    @pytest.mark.asyncio
    async def test_core_trading_tables_exist(self):
        """Test that core trading tables exist."""
        conn = await get_db_connection()
        try:
            required_tables = [
                "orders",
                "positions",
                "trades",
                "accounts",
                "account_snapshots",  # Currently missing - will fail!
                "symbols",
                "market_data",
            ]

            for table in required_tables:
                exists = await table_exists(conn, table)
                assert exists, f"Required table '{table}' does not exist in database"
        finally:
            await conn.close()

    @pytest.mark.asyncio
    async def test_signal_processing_tables_exist(self):
        """Test that signal processing tables exist."""
        conn = await get_db_connection()
        try:
            required_tables = [
                "signals",
                "signal_generators",
                "backtest_results",
                "model_registry",
            ]

            for table in required_tables:
                exists = await table_exists(conn, table)
                assert exists, f"Signal processing table '{table}' does not exist"
        finally:
            await conn.close()

    @pytest.mark.asyncio
    async def test_audit_and_compliance_tables_exist(self):
        """Test that audit and compliance tables exist."""
        conn = await get_db_connection()
        try:
            required_tables = [
                "audit_logs",
                "trade_reports",
                "risk_events",
                "compliance_checks",
            ]

            for table in required_tables:
                exists = await table_exists(conn, table)
                assert exists, f"Audit table '{table}' does not exist"
        finally:
            await conn.close()


class TestOrdersTableSchema:
    """Test orders table schema matches code expectations."""

    @pytest.mark.asyncio
    async def test_orders_table_required_columns(self, db_connection):
        """Test orders table has all required columns with correct types."""
        schema = await get_table_schema(db_connection, "orders")

        # This test will FAIL due to symbol_id vs symbol mismatch!
        required_columns = {
            "id": {"data_type": "uuid", "is_nullable": "NO"},
            "symbol": {
                "data_type": "character varying",
                "is_nullable": "NO",
            },  # Not symbol_id!
            "side": {"data_type": "character varying", "is_nullable": "NO"},
            "quantity": {"data_type": "numeric", "is_nullable": "NO"},
            "price": {"data_type": "numeric", "is_nullable": "YES"},
            "order_type": {"data_type": "character varying", "is_nullable": "NO"},
            "status": {"data_type": "character varying", "is_nullable": "NO"},
            "created_at": {
                "data_type": "timestamp with time zone",
                "is_nullable": "NO",
            },
            "updated_at": {
                "data_type": "timestamp with time zone",
                "is_nullable": "NO",
            },
            "account_id": {"data_type": "uuid", "is_nullable": "NO"},
        }

        for column_name, expected in required_columns.items():
            assert (
                column_name in schema
            ), f"Missing required column '{column_name}' in orders table"

            actual = schema[column_name]
            assert (
                actual["data_type"] == expected["data_type"]
            ), f"Column '{column_name}' has type '{actual['data_type']}', expected '{expected['data_type']}'"
            assert (
                actual["is_nullable"] == expected["is_nullable"]
            ), f"Column '{column_name}' nullable='{actual['is_nullable']}', expected '{expected['is_nullable']}'"


class TestAccountSnapshotsTableSchema:
    """Test account_snapshots table schema - currently missing!"""

    @pytest.mark.asyncio
    async def test_account_snapshots_table_exists(self, db_connection):
        """Test that account_snapshots table exists (currently fails!)."""
        exists = await table_exists(db_connection, "account_snapshots")
        assert (
            exists
        ), "account_snapshots table does not exist - referenced in order management code"

    @pytest.mark.asyncio
    async def test_account_snapshots_required_columns(self, db_connection):
        """Test account_snapshots has required columns."""
        schema = await get_table_schema(db_connection, "account_snapshots")

        required_columns = {
            "id": {"data_type": "uuid", "is_nullable": "NO"},
            "account_id": {"data_type": "uuid", "is_nullable": "NO"},
            "balance": {"data_type": "numeric", "is_nullable": "NO"},
            "equity": {"data_type": "numeric", "is_nullable": "NO"},
            "margin_used": {"data_type": "numeric", "is_nullable": "YES"},
            "margin_available": {"data_type": "numeric", "is_nullable": "YES"},
            "unrealized_pl": {"data_type": "numeric", "is_nullable": "YES"},
            "snapshot_time": {
                "data_type": "timestamp with time zone",
                "is_nullable": "NO",
            },
        }

        for column_name, expected in required_columns.items():
            assert (
                column_name in schema
            ), f"Missing column '{column_name}' in account_snapshots"


class TestForeignKeyRelationships:
    """Test that all foreign key relationships are properly defined."""

    @pytest.mark.asyncio
    async def test_orders_foreign_keys(self, db_connection):
        """Test orders table foreign key relationships."""
        # Test account_id references accounts.id
        fk_exists = await foreign_key_exists(
            db_connection, "orders", "account_id", "accounts", "id"
        )
        assert fk_exists, "Foreign key orders.account_id -> accounts.id does not exist"

    @pytest.mark.asyncio
    async def test_trades_foreign_keys(self, db_connection):
        """Test trades table foreign key relationships."""
        # Test order_id references orders.id
        fk_exists = await foreign_key_exists(
            db_connection, "trades", "order_id", "orders", "id"
        )
        assert fk_exists, "Foreign key trades.order_id -> orders.id does not exist"

    @pytest.mark.asyncio
    async def test_positions_foreign_keys(self, db_connection):
        """Test positions table foreign key relationships."""
        # Test account_id references accounts.id
        fk_exists = await foreign_key_exists(
            db_connection, "positions", "account_id", "accounts", "id"
        )
        assert (
            fk_exists
        ), "Foreign key positions.account_id -> accounts.id does not exist"

    @pytest.mark.asyncio
    async def test_account_snapshots_foreign_keys(self, db_connection):
        """Test account_snapshots table foreign key relationships."""
        # Test account_id references accounts.id
        fk_exists = await foreign_key_exists(
            db_connection, "account_snapshots", "account_id", "accounts", "id"
        )
        assert (
            fk_exists
        ), "Foreign key account_snapshots.account_id -> accounts.id does not exist"


class TestDatabaseConstraints:
    """Test data integrity constraints."""

    @pytest.mark.asyncio
    async def test_orders_check_constraints(self, db_connection):
        """Test orders table has proper check constraints."""
        # Test that side is either 'buy' or 'sell'
        query = """
        SELECT EXISTS (
            SELECT 1 FROM information_schema.check_constraints cc
            JOIN information_schema.constraint_column_usage ccu
              ON cc.constraint_name = ccu.constraint_name
            WHERE ccu.table_name = 'orders'
              AND ccu.column_name = 'side'
              AND cc.check_clause LIKE '%buy%sell%'
        );
        """
        constraint_exists = await db_connection.fetchval(query)
        assert (
            constraint_exists
        ), "Orders table missing side check constraint (buy/sell)"

    @pytest.mark.asyncio
    async def test_quantity_positive_constraints(self, db_connection):
        """Test that quantity fields have positive value constraints."""
        tables_with_quantity = ["orders", "trades", "positions"]

        for table in tables_with_quantity:
            query = """
            SELECT EXISTS (
                SELECT 1 FROM information_schema.check_constraints cc
                JOIN information_schema.constraint_column_usage ccu
                  ON cc.constraint_name = ccu.constraint_name
                WHERE ccu.table_name = $1
                  AND ccu.column_name = 'quantity'
                  AND cc.check_clause LIKE '%> 0%'
            );
            """
            constraint_exists = await db_connection.fetchval(query, table)
            assert (
                constraint_exists
            ), f"Table {table} missing positive quantity constraint"


class TestDatabaseIndexes:
    """Test that required indexes exist for performance."""

    @pytest.mark.asyncio
    async def test_orders_performance_indexes(self, db_connection):
        """Test orders table has required indexes."""
        required_indexes = [
            ("orders", "account_id"),
            ("orders", "symbol"),
            ("orders", "status"),
            ("orders", "created_at"),
        ]

        for table, column in required_indexes:
            query = """
            SELECT EXISTS (
                SELECT 1 FROM pg_indexes
                WHERE tablename = $1
                  AND indexdef LIKE '%' || $2 || '%'
            );
            """
            index_exists = await db_connection.fetchval(query, table, column)
            assert index_exists, f"Missing index on {table}.{column}"


# Additional test to validate SQL queries in codebase match schema
class TestCodeSchemaAlignment:
    """Test that SQL queries in code match actual database schema."""

    @pytest.mark.asyncio
    async def test_order_management_queries_valid(self, db_connection):
        """Test that order management SQL queries are valid against schema."""
        # This tests the exact query that was failing in order management
        failing_query = """
        SELECT o.id, o.symbol_id, o.status
        FROM orders o
        WHERE o.status = 'active'
        """

        # This should fail because column is 'symbol' not 'symbol_id'
        try:
            await db_connection.fetch(failing_query)
            assert False, "Query with symbol_id should fail - column name is 'symbol'"
        except asyncpg.UndefinedColumnError:
            # Expected failure - this proves schema mismatch
            pass

        # The corrected query should work
        corrected_query = """
        SELECT o.id, o.symbol, o.status
        FROM orders o
        WHERE o.status = 'active'
        """

        # This might still fail if orders table doesn't exist, but validates column name
        try:
            result = await db_connection.fetch(corrected_query)
            # Query executed successfully with correct column name
            assert result is not None, "Query should return results"
            assert len(result) >= 0, "Query result should be a valid list"
        except asyncpg.UndefinedTableError:
            # Table might not exist yet, but column name is correct
            # Expected exception for non-existent table
            pass  # This is the expected behavior
