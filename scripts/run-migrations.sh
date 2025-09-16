#!/bin/bash
set -e

# Run database migrations
echo "🔄 Running FXML4 Database Migrations"

# Database connection parameters
DB_HOST="postgres01.tailb381ec.ts.net"
DB_PORT="5432"
DB_USER="postgres"
DB_NAME="fxml4"

# Set password directly
export PGPASSWORD='0ctavian!'

echo "Running migrations on $DB_NAME database..."

# Migration directory
MIGRATION_DIR="db/migrations"

if [ ! -d "$MIGRATION_DIR" ]; then
    echo "❌ Migration directory not found: $MIGRATION_DIR"
    exit 1
fi

# Run each migration in order
for migration in $(ls "$MIGRATION_DIR"/*.sql | sort); do
    migration_name=$(basename "$migration")
    echo -n "Running $migration_name... "

    if psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -f "$migration" > /tmp/migration.log 2>&1; then
        echo "✓ completed"
    else
        echo "✗ failed"
        echo "Error details:"
        cat /tmp/migration.log
        exit 1
    fi
done

echo "✅ All migrations completed successfully!"
