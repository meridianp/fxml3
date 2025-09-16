#!/bin/bash
set -e

# FXML4 External Database Initialization Script
# This script initializes the external PostgreSQL database with TimescaleDB

echo "🚀 FXML4 External Database Initialization"
echo "========================================"

# Database connection parameters
DB_HOST="${DB_HOST:-postgres01.tailb381ec.ts.net}"
DB_PORT="${DB_PORT:-5432}"
DB_USER="${DB_USER:-postgres}"
DB_NAME="${DB_NAME:-fxml4}"

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${GREEN}✓${NC} $1"
}

print_error() {
    echo -e "${RED}✗${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}⚠${NC} $1"
}

print_info() {
    echo -e "${BLUE}ℹ${NC} $1"
}

# Check prerequisites
check_prerequisites() {
    echo "Checking prerequisites..."

    # Check psql
    if ! command -v psql &> /dev/null; then
        print_error "psql not found. Please install PostgreSQL client."
        echo "Install with: apt-get install postgresql-client"
        exit 1
    fi
    print_status "psql found"

    # Get database password
    if [ -z "$DB_PASSWORD" ]; then
        echo -n "Enter database password for $DB_USER: "
        read -s DB_PASSWORD
        echo ""
    fi

    # Export password for all subsequent commands
    export PGPASSWORD="$DB_PASSWORD"
}

# Test database connection
test_connection() {
    echo -e "\nTesting database connection..."

    if psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d postgres -c 'SELECT 1;' > /dev/null 2>&1; then
        print_status "Successfully connected to database server"
    else
        print_error "Failed to connect to database server"
        echo "Please check your connection parameters:"
        echo "  Host: $DB_HOST"
        echo "  Port: $DB_PORT"
        echo "  User: $DB_USER"
        exit 1
    fi
}

# Check TimescaleDB extension
check_timescaledb() {
    echo -e "\nChecking TimescaleDB extension..."

    # Check if TimescaleDB is available
    local has_timescale=$(psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d postgres -tAc "SELECT COUNT(*) FROM pg_available_extensions WHERE name='timescaledb';")

    if [ "$has_timescale" -eq "1" ]; then
        print_status "TimescaleDB extension is available"
    else
        print_error "TimescaleDB extension is not available on this server"
        echo "Please install TimescaleDB on your PostgreSQL server"
        echo "Visit: https://docs.timescale.com/install/"
        exit 1
    fi
}

# Create database
create_database() {
    echo -e "\nCreating database..."

    # Check if database exists
    local db_exists=$(psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d postgres -tAc "SELECT 1 FROM pg_database WHERE datname='$DB_NAME';")

    if [ "$db_exists" = "1" ]; then
        print_warning "Database '$DB_NAME' already exists"
        echo -n "Do you want to continue with existing database? (y/N): "
        read -r response
        if [[ ! "$response" =~ ^[Yy]$ ]]; then
            echo "Exiting..."
            exit 0
        fi
    else
        # Create database
        if psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d postgres -c "CREATE DATABASE $DB_NAME;"; then
            print_status "Database '$DB_NAME' created successfully"
        else
            print_error "Failed to create database '$DB_NAME'"
            exit 1
        fi
    fi
}

# Enable TimescaleDB extension
enable_timescaledb() {
    echo -e "\nEnabling TimescaleDB extension..."

    if psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -c "CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;"; then
        print_status "TimescaleDB extension enabled"
    else
        print_error "Failed to enable TimescaleDB extension"
        exit 1
    fi
}

# Run migrations
run_migrations() {
    echo -e "\nRunning database migrations..."

    # Get migration files
    MIGRATION_DIR="$(dirname "$0")/../db/migrations"

    if [ ! -d "$MIGRATION_DIR" ]; then
        print_error "Migration directory not found: $MIGRATION_DIR"
        exit 1
    fi

    # Run each migration in order
    for migration in $(ls "$MIGRATION_DIR"/*.sql | sort); do
        migration_name=$(basename "$migration")
        echo -n "Running $migration_name... "

        if psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -f "$migration" &> /tmp/migration_error.log; then
            print_status "completed"
        else
            print_error "failed"
            echo "Error details:"
            cat /tmp/migration_error.log
            exit 1
        fi
    done
}

# Insert default data
insert_default_data() {
    echo -e "\nInserting default data..."

    # Insert default symbols
    psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" <<EOF
-- Insert default forex symbols
INSERT INTO symbols (name, display_name, asset_class) VALUES
    ('EURUSD', 'EUR/USD', 'forex'),
    ('GBPUSD', 'GBP/USD', 'forex'),
    ('USDJPY', 'USD/JPY', 'forex'),
    ('USDCHF', 'USD/CHF', 'forex')
ON CONFLICT (name) DO NOTHING;

-- Insert default timeframes
INSERT INTO timeframes (name, minutes, display_name) VALUES
    ('1m', 1, '1 Minute'),
    ('5m', 5, '5 Minutes'),
    ('15m', 15, '15 Minutes'),
    ('30m', 30, '30 Minutes'),
    ('1h', 60, '1 Hour'),
    ('4h', 240, '4 Hours'),
    ('1d', 1440, '1 Day')
ON CONFLICT (name) DO NOTHING;
EOF

    print_status "Default data inserted"
}

# Display connection info
display_info() {
    echo -e "\n${GREEN}✅ Database initialization completed successfully!${NC}"
    echo -e "\nConnection Information:"
    echo "======================"
    echo "Host: $DB_HOST"
    echo "Port: $DB_PORT"
    echo "Database: $DB_NAME"
    echo "User: $DB_USER"
    echo ""
    echo "Connection string:"
    echo "postgresql://$DB_USER:****@$DB_HOST:$DB_PORT/$DB_NAME"
    echo ""
    echo "To test the connection:"
    echo "psql -h $DB_HOST -p $DB_PORT -U $DB_USER -d $DB_NAME"
    echo ""
    print_info "Remember to update your GitHub secrets with these values!"
    print_info "Run: ./scripts/setup-github-secrets.sh"
}

# Main execution
main() {
    check_prerequisites
    test_connection
    check_timescaledb
    create_database
    enable_timescaledb
    run_migrations
    insert_default_data
    display_info
}

# Run main function
main
