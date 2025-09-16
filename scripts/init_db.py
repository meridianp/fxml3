#!/usr/bin/env python3
"""
Database initialization script for FXML4.

This script creates the necessary database schema for FXML4,
migrates data from FXML2 and FXML3 databases, and sets up
initial configurations.
"""

import argparse
import os
import sys
from pathlib import Path

import psycopg2
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


def get_connection(db_name="postgres"):
    """Get a connection to the PostgreSQL database."""
    return psycopg2.connect(
        host=os.getenv("FXML4_DATABASE_HOST", "localhost"),
        port=os.getenv("FXML4_DATABASE_PORT", "5432"),
        user=os.getenv("FXML4_DATABASE_USER", "postgres"),
        password=os.getenv("FXML4_DATABASE_PASSWORD", ""),
        database=db_name,
    )


def create_database():
    """Create the FXML4 database if it doesn't exist."""
    db_name = os.getenv("FXML4_DATABASE_NAME", "fxml4")

    # Connect to postgres database
    conn = get_connection()
    conn.autocommit = True
    cursor = conn.cursor()

    # Check if database exists
    cursor.execute(f"SELECT 1 FROM pg_database WHERE datname = '{db_name}'")
    exists = cursor.fetchone()

    if not exists:
        print(f"Creating database {db_name}")
        cursor.execute(f"CREATE DATABASE {db_name}")
        print(f"Database {db_name} created successfully")
    else:
        print(f"Database {db_name} already exists")

    cursor.close()
    conn.close()


def apply_migrations():
    """Apply database migrations."""
    db_name = os.getenv("FXML4_DATABASE_NAME", "fxml4")

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


def migrate_data_from_fxml2():
    """Migrate data from FXML2 database."""
    # Check if FXML2 database exists
    fxml2_db = os.getenv("FXML2_DATABASE_NAME")
    if not fxml2_db:
        print("FXML2_DATABASE_NAME not set, skipping FXML2 data migration")
        return True

    try:
        # Connect to FXML2 database
        fxml2_conn = get_connection(fxml2_db)
        fxml2_cursor = fxml2_conn.cursor()

        # Connect to FXML4 database
        fxml4_db = os.getenv("FXML4_DATABASE_NAME", "fxml4")
        fxml4_conn = get_connection(fxml4_db)
        fxml4_cursor = fxml4_conn.cursor()

        # Migrate models data
        print("Migrating models from FXML2...")
        fxml2_cursor.execute("SELECT * FROM models")
        models = fxml2_cursor.fetchall()

        for model in models:
            # Adapt this to match your FXML2 schema
            name = model[1]
            version = model[2]
            model_type = model[3]

            # Get symbol and timeframe IDs
            symbol_name = model[4]
            timeframe_name = model[5]

            fxml4_cursor.execute(
                "SELECT id FROM symbols WHERE name = %s", (symbol_name,)
            )
            symbol_id = fxml4_cursor.fetchone()[0]

            fxml4_cursor.execute(
                "SELECT id FROM timeframes WHERE name = %s", (timeframe_name,)
            )
            timeframe_id = fxml4_cursor.fetchone()[0]

            # Insert into FXML4 database
            fxml4_cursor.execute(
                """
            INSERT INTO models (name, version, model_type, symbol_id, timeframe_id, metadata, file_path, is_active)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (name, version) DO NOTHING
            """,
                (name, version, model_type, symbol_id, timeframe_id, {}, "", True),
            )

        fxml4_conn.commit()
        print(f"Migrated {len(models)} models from FXML2")

        # Close connections
        fxml2_cursor.close()
        fxml2_conn.close()
        fxml4_cursor.close()
        fxml4_conn.close()

        return True
    except Exception as e:
        print(f"Error migrating data from FXML2: {e}")
        return False


def migrate_data_from_fxml3():
    """Migrate data from FXML3 database."""
    # Check if FXML3 database exists
    fxml3_db = os.getenv("FXML3_DATABASE_NAME")
    if not fxml3_db:
        print("FXML3_DATABASE_NAME not set, skipping FXML3 data migration")
        return True

    try:
        # Connect to FXML3 database
        fxml3_conn = get_connection(fxml3_db)
        fxml3_cursor = fxml3_conn.cursor()

        # Connect to FXML4 database
        fxml4_db = os.getenv("FXML4_DATABASE_NAME", "fxml4")
        fxml4_conn = get_connection(fxml4_db)
        fxml4_cursor = fxml4_conn.cursor()

        # Migrate wave patterns data
        print("Migrating wave patterns from FXML3...")
        fxml3_cursor.execute("SELECT * FROM wave_patterns")
        patterns = fxml3_cursor.fetchall()

        for pattern in patterns:
            # Adapt this to match your FXML3 schema
            symbol_name = pattern[1]
            timeframe_name = pattern[2]
            start_timestamp = pattern[3]
            end_timestamp = pattern[4]
            wave_type = pattern[5]
            direction = pattern[6]
            confidence = pattern[7]

            # Get symbol and timeframe IDs
            fxml4_cursor.execute(
                "SELECT id FROM symbols WHERE name = %s", (symbol_name,)
            )
            symbol_id = fxml4_cursor.fetchone()[0]

            fxml4_cursor.execute(
                "SELECT id FROM timeframes WHERE name = %s", (timeframe_name,)
            )
            timeframe_id = fxml4_cursor.fetchone()[0]

            # Insert into FXML4 database
            fxml4_cursor.execute(
                """
            INSERT INTO wave_patterns (symbol_id, timeframe_id, start_timestamp, end_timestamp,
                                       wave_type, direction, confidence, sub_waves, metadata)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
                (
                    symbol_id,
                    timeframe_id,
                    start_timestamp,
                    end_timestamp,
                    wave_type,
                    direction,
                    confidence,
                    {},
                    {},
                ),
            )

        fxml4_conn.commit()
        print(f"Migrated {len(patterns)} wave patterns from FXML3")

        # Migrate knowledge vectors data
        print("Migrating knowledge vectors from FXML3...")
        fxml3_cursor.execute("SELECT * FROM knowledge_vectors")
        vectors = fxml3_cursor.fetchall()

        for vector in vectors:
            # Adapt this to match your FXML3 schema
            content = vector[1]
            content_type = vector[2]
            category = vector[3]
            embedding = vector[4]

            # Insert into FXML4 database
            fxml4_cursor.execute(
                """
            INSERT INTO knowledge_vectors (content, content_type, category, embedding, metadata)
            VALUES (%s, %s, %s, %s, %s)
            """,
                (content, content_type, category, embedding, {}),
            )

        fxml4_conn.commit()
        print(f"Migrated {len(vectors)} knowledge vectors from FXML3")

        # Close connections
        fxml3_cursor.close()
        fxml3_conn.close()
        fxml4_cursor.close()
        fxml4_conn.close()

        return True
    except Exception as e:
        print(f"Error migrating data from FXML3: {e}")
        return False


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Initialize FXML4 database")
    parser.add_argument(
        "--skip-create", action="store_true", help="Skip database creation"
    )
    parser.add_argument(
        "--skip-migrations", action="store_true", help="Skip migrations"
    )
    parser.add_argument(
        "--skip-fxml2-migration", action="store_true", help="Skip FXML2 data migration"
    )
    parser.add_argument(
        "--skip-fxml3-migration", action="store_true", help="Skip FXML3 data migration"
    )
    args = parser.parse_args()

    try:
        if not args.skip_create:
            create_database()

        if not args.skip_migrations:
            apply_migrations()

        if not args.skip_fxml2_migration:
            migrate_data_from_fxml2()

        if not args.skip_fxml3_migration:
            migrate_data_from_fxml3()

        print("Database initialization completed successfully")
        return 0
    except Exception as e:
        print(f"Error initializing database: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
