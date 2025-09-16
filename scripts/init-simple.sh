#!/bin/bash
set -e

# Simple database initialization without complex password handling
echo "🚀 FXML4 Database Initialization (Simple)"

# Database connection parameters
DB_HOST="postgres01.tailb381ec.ts.net"
DB_PORT="5432"
DB_USER="postgres"
DB_NAME="fxml4"

# Set password directly - this works as we tested
export PGPASSWORD='0ctavian!'

echo "Testing connection..."
if psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d postgres -c 'SELECT 1;' > /dev/null 2>&1; then
    echo "✓ Connection successful"
else
    echo "✗ Connection failed"
    exit 1
fi

echo "Checking if database '$DB_NAME' exists..."
db_exists=$(psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d postgres -tAc "SELECT 1 FROM pg_database WHERE datname='$DB_NAME';")

if [ "$db_exists" = "1" ]; then
    echo "⚠ Database '$DB_NAME' already exists"
    echo -n "Continue with existing database? (y/N): "
    read -r response
    if [[ ! "$response" =~ ^[Yy]$ ]]; then
        echo "Exiting..."
        exit 0
    fi
else
    echo "Creating database '$DB_NAME'..."
    if psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d postgres -c "CREATE DATABASE $DB_NAME;"; then
        echo "✓ Database created"
    else
        echo "✗ Failed to create database"
        exit 1
    fi
fi

echo "Enabling TimescaleDB extension..."
if psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -c "CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;"; then
    echo "✓ TimescaleDB enabled"
else
    echo "✗ Failed to enable TimescaleDB"
    exit 1
fi

echo "✅ Database initialization completed!"
echo "Connection: postgresql://$DB_USER:****@$DB_HOST:$DB_PORT/$DB_NAME"
