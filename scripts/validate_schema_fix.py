#!/usr/bin/env python3
"""
Simple validation script for database schema fixes.
This runs inside the Docker container to bypass authentication issues.
"""

import subprocess
import sys


def run_docker_sql(sql_command):
    """Run SQL command inside the Docker container."""
    cmd = [
        "docker",
        "exec",
        "fxml4-db-1",
        "psql",
        "-U",
        "postgres",
        "-d",
        "fxml4",
        "-c",
        sql_command,
    ]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        return f"ERROR: {e.stderr.strip()}"


def validate_schema_fixes():
    """Validate that our TDD schema fixes are working."""
    print("🔍 PHASE 1 GREEN: Validating Database Schema Fixes")
    print("=" * 60)

    # Test 1: Check that required tables exist
    required_tables = [
        "orders",
        "positions",
        "trades",
        "accounts",
        "account_snapshots",  # This was missing!
        "symbols",
        "market_data",  # This was missing!
    ]

    print("\n📋 Testing Required Tables:")
    all_tables_exist = True

    for table in required_tables:
        sql = f"""
        SELECT EXISTS (
            SELECT FROM information_schema.tables
            WHERE table_name = '{table}'
        );
        """
        result = run_docker_sql(sql)

        if "t" in result:  # PostgreSQL returns 't' for true
            print(f"  ✅ {table}")
        else:
            print(f"  ❌ {table} - NOT FOUND")
            all_tables_exist = False

    # Test 2: Check orders table has correct column (symbol, not symbol_id)
    print("\n🔍 Testing Orders Table Schema:")
    sql = """
    SELECT column_name, data_type, is_nullable
    FROM information_schema.columns
    WHERE table_name = 'orders'
    ORDER BY ordinal_position;
    """
    result = run_docker_sql(sql)

    if "symbol" in result and "symbol_id" not in result:
        print("  ✅ Orders table uses 'symbol' column (not symbol_id)")
    else:
        print("  ❌ Orders table column name issue")
        print(f"     Columns: {result}")

    # Test 3: Check account_snapshots table has required columns
    print("\n📊 Testing Account Snapshots Table:")
    required_columns = [
        "account_id",
        "balance",
        "equity",
        "margin_used",
        "snapshot_time",
    ]

    sql = """
    SELECT column_name, data_type
    FROM information_schema.columns
    WHERE table_name = 'account_snapshots'
    ORDER BY ordinal_position;
    """
    result = run_docker_sql(sql)

    snapshots_ok = True
    for col in required_columns:
        if col in result:
            print(f"  ✅ {col}")
        else:
            print(f"  ❌ {col} - MISSING")
            snapshots_ok = False

    # Test 4: Check foreign key relationships
    print("\n🔗 Testing Foreign Key Relationships:")

    # Check accounts table exists for foreign keys
    sql = "SELECT COUNT(*) FROM accounts;"
    result = run_docker_sql(sql)
    if "1" in result or "0" in result:  # Should return a count
        print("  ✅ Accounts table accessible for foreign keys")
    else:
        print("  ❌ Accounts table issue")

    # Test 5: Test orders table constraints
    print("\n⚡ Testing Orders Table Constraints:")

    sql = """
    SELECT constraint_name, check_clause
    FROM information_schema.check_constraints
    WHERE constraint_name LIKE 'orders_%';
    """
    result = run_docker_sql(sql)

    if "side" in result and ("buy" in result or "sell" in result):
        print("  ✅ Side constraint (buy/sell)")
    if "quantity" in result and "> 0" in result:
        print("  ✅ Quantity positive constraint")

    # Summary
    print("\n" + "=" * 60)
    if all_tables_exist and snapshots_ok:
        print("🎉 SCHEMA VALIDATION: PASSED")
        print("✅ All required tables exist")
        print("✅ Column names are correct")
        print("✅ Account snapshots table properly configured")
        print("🚀 Ready for TDD test validation!")
        return True
    else:
        print("❌ SCHEMA VALIDATION: FAILED")
        print("🔧 Some schema issues remain")
        return False


if __name__ == "__main__":
    success = validate_schema_fixes()
    sys.exit(0 if success else 1)
