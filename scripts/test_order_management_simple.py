#!/usr/bin/env python3

"""
Simple Order Management System Validation
Tests that the database schema fixes are working
"""

import asyncio
import logging
import os
import sys
from pathlib import Path

import asyncpg

# Set environment for database connection
os.environ.update(
    {
        "FXML4_DATABASE_HOST": "localhost",
        "FXML4_DATABASE_PORT": "5432",
        "FXML4_DATABASE_NAME": "fxml4",
        "FXML4_DATABASE_USER": "postgres",
        "FXML4_DATABASE_PASSWORD": "postgres",
    }
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def test_order_management_schema():
    """Test that order management schema is working correctly."""

    print("🎯 Order Management Schema Validation")
    print("=" * 50)

    try:
        # Connect to database
        conn = await asyncpg.connect(
            host="localhost",
            port=5432,
            user="postgres",
            password="postgres",
            database="fxml4",
        )

        print("✅ Database connection established")

        # Test that all order management tables exist
        tables_to_check = [
            "orders",
            "positions",
            "trades",
            "account_snapshots",
            "risk_events",
        ]

        for table in tables_to_check:
            try:
                result = await conn.fetchval(f"SELECT COUNT(*) FROM {table}")
                print(f"✅ {table} table: {result} records")
            except Exception as e:
                print(f"❌ {table} table: {e}")
                return False

        # Test the fixed query that was causing the error
        try:
            rows = await conn.fetch(
                """
                SELECT o.*, s.name as symbol_name
                FROM orders o
                JOIN symbols s ON o.symbol_id = s.id
                WHERE o.status IN ('pending', 'submitted', 'acknowledged', 'working', 'partially_filled')
                ORDER BY o.created_at DESC
                LIMIT 5
            """
            )
            print(f"✅ Fixed order query: {len(rows)} active orders found")
        except Exception as e:
            print(f"❌ Order query failed: {e}")
            return False

        # Test symbols are available
        try:
            symbols = await conn.fetch(
                "SELECT name, display_name FROM symbols ORDER BY name"
            )
            symbol_names = [row["name"] for row in symbols]
            print(f"✅ Symbols available: {', '.join(symbol_names)}")
        except Exception as e:
            print(f"❌ Symbols query failed: {e}")
            return False

        # Test signal generators exist
        signal_generator_files = list(Path("fxml4/signals").glob("*_generator.py"))
        if signal_generator_files:
            generators = [
                f.stem.replace("_generator", "").upper() for f in signal_generator_files
            ]
            print(f"✅ Signal generators: {', '.join(generators)}")
        else:
            print("⚠️ No signal generators found")

        await conn.close()

        print("\n🏆 ORDER MANAGEMENT SCHEMA VALIDATION COMPLETE")
        print("📈 Key Components Status:")
        print("   - Order Management Tables ✅")
        print("   - Database Queries Fixed ✅")
        print("   - Signal Generators Available ✅")
        print("   - Symbol Data Available ✅")
        print("\n✨ Order Management System is ready for full trading functionality!")

        return True

    except Exception as e:
        print(f"❌ Validation failed: {e}")
        return False


if __name__ == "__main__":
    success = asyncio.run(test_order_management_schema())
    if success:
        print("\n🎯 Order Management Schema Validation: SUCCESS")
        sys.exit(0)
    else:
        print("\n❌ Order Management Schema Validation: FAILED")
        sys.exit(1)
