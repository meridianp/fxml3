#!/bin/bash
set -e

# FXML4 Database Backup and Restore Script
# This script handles backup and restore operations for the external PostgreSQL database

# Database connection parameters
DB_HOST="${DB_HOST:-postgres01.tailb381ec.ts.net}"
DB_PORT="${DB_PORT:-5432}"
DB_USER="${DB_USER:-postgres}"
DB_NAME="${DB_NAME:-fxml4}"

# Backup configuration
BACKUP_DIR="${BACKUP_DIR:-./backups}"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

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

# Show usage
usage() {
    echo "FXML4 Database Backup and Restore"
    echo "================================="
    echo ""
    echo "Usage: $0 [command] [options]"
    echo ""
    echo "Commands:"
    echo "  backup    Create a backup of the database"
    echo "  restore   Restore database from a backup file"
    echo "  list      List available backups"
    echo "  export    Export specific tables to CSV"
    echo "  import    Import data from CSV files"
    echo ""
    echo "Options:"
    echo "  -f FILE   Backup file to restore from"
    echo "  -t TABLE  Specific table to export/import"
    echo "  -d DIR    Directory for backups (default: ./backups)"
    echo ""
    echo "Examples:"
    echo "  $0 backup"
    echo "  $0 restore -f backups/fxml4_20240101_120000.sql.gz"
    echo "  $0 export -t market_data_1m"
    echo "  $0 import -t symbols -f data/symbols.csv"
    exit 1
}

# Get database password
get_password() {
    if [ -z "$DB_PASSWORD" ]; then
        echo -n "Enter database password for $DB_USER: "
        read -s DB_PASSWORD
        echo ""
    fi
    export PGPASSWORD="$DB_PASSWORD"
}

# Create backup directory
create_backup_dir() {
    if [ ! -d "$BACKUP_DIR" ]; then
        mkdir -p "$BACKUP_DIR"
        print_status "Created backup directory: $BACKUP_DIR"
    fi
}

# Backup database
backup_database() {
    echo "🔄 Creating database backup..."
    echo "============================"

    get_password
    create_backup_dir

    local backup_file="$BACKUP_DIR/fxml4_${TIMESTAMP}.sql.gz"

    echo "Backing up to: $backup_file"
    echo "This may take a while for large databases..."

    # Create backup with compression
    if pg_dump -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" \
        --verbose --no-owner --no-acl \
        --exclude-table-data='tick_data' \
        --exclude-table-data='market_data_1m' | gzip > "$backup_file"; then

        local size=$(ls -lh "$backup_file" | awk '{print $5}')
        print_status "Backup completed successfully"
        echo "File: $backup_file"
        echo "Size: $size"

        # Also backup data tables separately for faster restoration
        echo -e "\nBacking up data tables separately..."

        # Backup market data with COPY for better performance
        if psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" \
            -c "\COPY (SELECT * FROM market_data_1m ORDER BY time) TO STDOUT WITH CSV HEADER" | \
            gzip > "$BACKUP_DIR/market_data_1m_${TIMESTAMP}.csv.gz" 2>/dev/null; then
            print_status "Market data exported"
        fi

    else
        print_error "Backup failed"
        exit 1
    fi
}

# Restore database
restore_database() {
    echo "🔄 Restoring database from backup..."
    echo "==================================="

    if [ -z "$RESTORE_FILE" ]; then
        print_error "No backup file specified. Use -f option."
        exit 1
    fi

    if [ ! -f "$RESTORE_FILE" ]; then
        print_error "Backup file not found: $RESTORE_FILE"
        exit 1
    fi

    get_password

    print_warning "This will overwrite the existing database!"
    echo -n "Are you sure you want to continue? (y/N): "
    read -r response

    if [[ ! "$response" =~ ^[Yy]$ ]]; then
        echo "Restore cancelled"
        exit 0
    fi

    echo "Restoring from: $RESTORE_FILE"

    # Drop and recreate database
    print_info "Recreating database..."
    psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d postgres <<EOF
DROP DATABASE IF EXISTS $DB_NAME;
CREATE DATABASE $DB_NAME;
EOF

    # Enable TimescaleDB
    psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -c "CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;"

    # Restore backup
    if [[ "$RESTORE_FILE" == *.gz ]]; then
        gunzip -c "$RESTORE_FILE" | psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME"
    else
        psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" < "$RESTORE_FILE"
    fi

    if [ $? -eq 0 ]; then
        print_status "Database restored successfully"

        # Check for separate data files
        local data_file="${RESTORE_FILE%.sql.gz}_market_data.csv.gz"
        if [ -f "$data_file" ]; then
            echo -e "\nRestoring market data..."
            gunzip -c "$data_file" | psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" \
                -c "\COPY market_data_1m FROM STDIN WITH CSV HEADER"
            print_status "Market data restored"
        fi
    else
        print_error "Restore failed"
        exit 1
    fi
}

# List backups
list_backups() {
    echo "📋 Available backups:"
    echo "===================="

    if [ ! -d "$BACKUP_DIR" ]; then
        print_warning "No backup directory found"
        return
    fi

    local count=0
    for backup in $(ls -1t "$BACKUP_DIR"/*.sql.gz 2>/dev/null); do
        local filename=$(basename "$backup")
        local size=$(ls -lh "$backup" | awk '{print $5}')
        local date=$(stat -c %y "$backup" | cut -d' ' -f1)
        echo "$filename ($size) - $date"
        ((count++))
    done

    if [ $count -eq 0 ]; then
        print_info "No backups found in $BACKUP_DIR"
    else
        echo -e "\nTotal backups: $count"
    fi
}

# Export table to CSV
export_table() {
    echo "📤 Exporting table data..."
    echo "========================"

    if [ -z "$TABLE_NAME" ]; then
        print_error "No table specified. Use -t option."
        exit 1
    fi

    get_password
    create_backup_dir

    local export_file="$BACKUP_DIR/${TABLE_NAME}_${TIMESTAMP}.csv"

    echo "Exporting $TABLE_NAME to $export_file"

    if psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" \
        -c "\COPY $TABLE_NAME TO '$export_file' WITH CSV HEADER"; then

        # Compress the file
        gzip "$export_file"
        print_status "Export completed: ${export_file}.gz"
    else
        print_error "Export failed"
        exit 1
    fi
}

# Import table from CSV
import_table() {
    echo "📥 Importing table data..."
    echo "========================"

    if [ -z "$TABLE_NAME" ]; then
        print_error "No table specified. Use -t option."
        exit 1
    fi

    if [ -z "$IMPORT_FILE" ]; then
        print_error "No import file specified. Use -f option."
        exit 1
    fi

    if [ ! -f "$IMPORT_FILE" ]; then
        print_error "Import file not found: $IMPORT_FILE"
        exit 1
    fi

    get_password

    echo "Importing $TABLE_NAME from $IMPORT_FILE"

    # Handle compressed files
    if [[ "$IMPORT_FILE" == *.gz ]]; then
        gunzip -c "$IMPORT_FILE" | psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" \
            -c "\COPY $TABLE_NAME FROM STDIN WITH CSV HEADER"
    else
        psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" \
            -c "\COPY $TABLE_NAME FROM '$IMPORT_FILE' WITH CSV HEADER"
    fi

    if [ $? -eq 0 ]; then
        print_status "Import completed successfully"
    else
        print_error "Import failed"
        exit 1
    fi
}

# Parse command line arguments
COMMAND=""
RESTORE_FILE=""
TABLE_NAME=""
IMPORT_FILE=""

while [[ $# -gt 0 ]]; do
    case $1 in
        backup|restore|list|export|import)
            COMMAND=$1
            shift
            ;;
        -f|--file)
            if [ "$COMMAND" = "restore" ]; then
                RESTORE_FILE="$2"
            else
                IMPORT_FILE="$2"
            fi
            shift 2
            ;;
        -t|--table)
            TABLE_NAME="$2"
            shift 2
            ;;
        -d|--dir)
            BACKUP_DIR="$2"
            shift 2
            ;;
        -h|--help)
            usage
            ;;
        *)
            echo "Unknown option: $1"
            usage
            ;;
    esac
done

# Execute command
case $COMMAND in
    backup)
        backup_database
        ;;
    restore)
        restore_database
        ;;
    list)
        list_backups
        ;;
    export)
        export_table
        ;;
    import)
        import_table
        ;;
    *)
        usage
        ;;
esac
