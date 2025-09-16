#!/usr/bin/env python3
"""
Database initialization script for FXML4 that connects to the Docker container.

This script initializes the PostgreSQL database running in Docker for FXML4.
"""

import os
import sys
from pathlib import Path

import psycopg2


def get_connection(db_name="postgres"):
    """Get a connection to the PostgreSQL database."""
    # SECURITY: Use environment variables for database credentials
    password = os.environ.get("POSTGRES_PASSWORD", "postgres")
    host = os.environ.get("POSTGRES_HOST", "localhost")
    port = os.environ.get("POSTGRES_PORT", "5432")
    user = os.environ.get("POSTGRES_USER", "postgres")

    return psycopg2.connect(
        host=host, port=port, user=user, password=password, database=db_name
    )


def apply_migrations():
    """Apply database migrations."""
    db_name = "fxml4"

    # Connect to the FXML4 database
    conn = get_connection(db_name)
    conn.autocommit = True
    cursor = conn.cursor()

    # Get migration files
    project_root = Path(__file__).parent.parent
    migrations_dir = project_root / "db" / "migrations"
    migration_files = sorted([f for f in migrations_dir.glob("*.sql")])

    # Create migrations table if it doesn't exist
    cursor.execute(
        """
    CREATE TABLE IF NOT EXISTS migrations (
        id SERIAL PRIMARY KEY,
        name VARCHAR(255) NOT NULL,
        applied_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
    )
    """
    )

    # Get applied migrations
    cursor.execute("SELECT name FROM migrations")
    applied_migrations = {row[0] for row in cursor.fetchall()}

    # Apply migrations
    for migration_file in migration_files:
        migration_name = migration_file.name

        if migration_name in applied_migrations:
            print(f"Migration {migration_name} already applied")
            continue

        print(f"Applying migration {migration_name}")

        # Read and execute migration
        with open(migration_file, "r") as f:
            migration_sql = f.read()
            cursor.execute(migration_sql)

        # Record migration
        cursor.execute("INSERT INTO migrations (name) VALUES (%s)", (migration_name,))

        print(f"Migration {migration_name} applied successfully")

    cursor.close()
    conn.close()


def main():
    """Main entry point."""
    try:
        print("Initializing FXML4 database...")
        apply_migrations()
        print("Database initialization completed successfully")
        return 0
    except Exception as e:
        print(f"Error initializing database: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
