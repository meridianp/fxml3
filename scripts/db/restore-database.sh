#!/bin/bash

# FXML4 Production Database Restore Script
# Supports TimescaleDB restoration with proper extension setup
# Usage: ./restore-database.sh [environment] [backup_file] [restore_options]

set -euo pipefail

# Configuration
ENVIRONMENT="${1:-production}"
BACKUP_FILE="${2:-latest}"
RESTORE_OPTIONS="${3:-}"  # clean, create, data-only, schema-only

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Logging functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Environment-specific configuration
case $ENVIRONMENT in
    "production")
        DB_HOST="${FXML4_DB_HOST:-timescaledb-primary}"
        DB_PORT="${FXML4_DB_PORT:-5432}"
        DB_NAME="${FXML4_DB_NAME:-fxml4_production}"
        DB_USER="${FXML4_DB_USER:-fxml4_user}"
        BACKUP_BUCKET="${FXML4_BACKUP_BUCKET:-fxml4-production-backups}"
        ;;
    "staging")
        DB_HOST="${FXML4_STAGING_DB_HOST:-timescaledb-staging}"
        DB_PORT="${FXML4_STAGING_DB_PORT:-5432}"
        DB_NAME="${FXML4_STAGING_DB_NAME:-fxml4_staging}"
        DB_USER="${FXML4_STAGING_DB_USER:-fxml4_user}"
        BACKUP_BUCKET="${FXML4_STAGING_BACKUP_BUCKET:-fxml4-staging-backups}"
        ;;
    *)
        log_error "Unknown environment: $ENVIRONMENT"
        exit 1
        ;;
esac

# Backup and restore paths
LOCAL_BACKUP_DIR="/opt/fxml4/backups/${ENVIRONMENT}"
RESTORE_LOG_DIR="/opt/fxml4/logs/restore"

# Ensure directories exist
mkdir -p "$LOCAL_BACKUP_DIR" "$RESTORE_LOG_DIR"

# Function to check database connectivity
check_db_connection() {
    log_info "Checking database connectivity..."

    if PGPASSWORD="$PGPASSWORD" psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "postgres" -c '\q' 2>/dev/null; then
        log_success "Database server connection successful"
        return 0
    else
        log_error "Failed to connect to database server"
        return 1
    fi
}

# Function to find latest backup
find_latest_backup() {
    local backup_pattern="$1"
    local latest_backup=""

    log_info "Looking for latest backup matching pattern: $backup_pattern"

    # Check local backups first
    if [ -d "$LOCAL_BACKUP_DIR" ]; then
        latest_backup=$(find "$LOCAL_BACKUP_DIR" -name "*${backup_pattern}*" -type f -exec ls -t {} + | head -n 1)
    fi

    # If no local backup found, try to download from cloud
    if [ -z "$latest_backup" ] && command -v aws &> /dev/null; then
        log_info "No local backup found, checking cloud storage..."

        local cloud_backup
        cloud_backup=$(aws s3 ls "s3://${BACKUP_BUCKET}/${ENVIRONMENT}/" --recursive | \
                      grep "$backup_pattern" | \
                      sort -k1,1 -k2,2 | \
                      tail -n 1 | \
                      awk '{print $4}')

        if [ -n "$cloud_backup" ]; then
            local local_file="${LOCAL_BACKUP_DIR}/$(basename "$cloud_backup")"
            log_info "Downloading backup from cloud: $cloud_backup"
            aws s3 cp "s3://${BACKUP_BUCKET}/$cloud_backup" "$local_file"
            latest_backup="$local_file"
        fi
    fi

    echo "$latest_backup"
}

# Function to validate backup file
validate_backup_file() {
    local backup_file="$1"

    log_info "Validating backup file: $backup_file"

    if [ ! -f "$backup_file" ]; then
        log_error "Backup file not found: $backup_file"
        return 1
    fi

    # Check if file is compressed
    if [[ "$backup_file" == *.gz ]]; then
        if ! gzip -t "$backup_file" 2>/dev/null; then
            log_error "Backup file appears to be corrupted"
            return 1
        fi
        log_info "Compressed backup file validated"
    fi

    # Check if it's a PostgreSQL dump
    if [[ "$backup_file" == *.sql* ]]; then
        if zgrep -q "PostgreSQL database dump" "$backup_file" 2>/dev/null || grep -q "PostgreSQL database dump" "$backup_file" 2>/dev/null; then
            log_success "Valid PostgreSQL dump file detected"
        else
            log_warning "File doesn't appear to be a standard PostgreSQL dump"
        fi
    fi

    local file_size
    file_size=$(du -sh "$backup_file" | cut -f1)
    log_info "Backup file size: $file_size"

    return 0
}

# Function to create database if it doesn't exist
ensure_database_exists() {
    local db_exists

    log_info "Checking if database $DB_NAME exists..."

    db_exists=$(PGPASSWORD="$PGPASSWORD" psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "postgres" -tAc "SELECT 1 FROM pg_database WHERE datname='$DB_NAME'")

    if [ -z "$db_exists" ]; then
        log_info "Creating database $DB_NAME..."
        PGPASSWORD="$PGPASSWORD" psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "postgres" -c "CREATE DATABASE $DB_NAME OWNER $DB_USER;"

        # Install TimescaleDB extension
        log_info "Installing TimescaleDB extension..."
        PGPASSWORD="$PGPASSWORD" psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -c "CREATE EXTENSION IF NOT EXISTS timescaledb;"

        log_success "Database created with TimescaleDB extension"
    else
        log_info "Database $DB_NAME already exists"
    fi
}

# Function to backup current database before restore
backup_current_database() {
    local backup_timestamp
    local current_backup_file

    backup_timestamp=$(date +"%Y%m%d_%H%M%S")
    current_backup_file="${LOCAL_BACKUP_DIR}/${DB_NAME}_pre_restore_${backup_timestamp}.sql.gz"

    log_info "Creating backup of current database before restore..."

    PGPASSWORD="$PGPASSWORD" pg_dump \
        -h "$DB_HOST" \
        -p "$DB_PORT" \
        -U "$DB_USER" \
        -d "$DB_NAME" \
        --verbose \
        --no-owner \
        --no-privileges \
        | gzip > "$current_backup_file"

    if [ $? -eq 0 ]; then
        log_success "Pre-restore backup created: $current_backup_file"
        echo "$current_backup_file"
    else
        log_error "Failed to create pre-restore backup"
        return 1
    fi
}

# Function to terminate active connections
terminate_connections() {
    log_info "Terminating active connections to database $DB_NAME..."

    PGPASSWORD="$PGPASSWORD" psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "postgres" -c "
        SELECT pg_terminate_backend(pid)
        FROM pg_stat_activity
        WHERE datname = '$DB_NAME'
          AND pid <> pg_backend_pid();
    " > /dev/null 2>&1

    log_info "Active connections terminated"
}

# Function to restore database from backup
restore_database() {
    local backup_file="$1"
    local restore_log="${RESTORE_LOG_DIR}/restore_$(date +"%Y%m%d_%H%M%S").log"
    local pg_restore_opts=""

    log_info "Starting database restore from: $backup_file"
    log_info "Restore log: $restore_log"

    # Configure restore options
    case "$RESTORE_OPTIONS" in
        *clean*)
            pg_restore_opts="$pg_restore_opts --clean"
            log_info "Using clean option (drop existing objects)"
            ;;
        *create*)
            pg_restore_opts="$pg_restore_opts --create"
            log_info "Using create option (create database)"
            ;;
        *data-only*)
            pg_restore_opts="$pg_restore_opts --data-only"
            log_info "Data-only restore"
            ;;
        *schema-only*)
            pg_restore_opts="$pg_restore_opts --schema-only"
            log_info "Schema-only restore"
            ;;
    esac

    # Terminate connections if doing clean restore
    if [[ "$RESTORE_OPTIONS" == *clean* ]]; then
        terminate_connections
    fi

    # Perform restore based on file type
    if [[ "$backup_file" == *.gz ]]; then
        log_info "Restoring from compressed SQL file..."

        {
            echo "-- Restore started at $(date)"
            echo "-- Backup file: $backup_file"
            echo "-- Environment: $ENVIRONMENT"
            echo ""

            zcat "$backup_file"
        } | PGPASSWORD="$PGPASSWORD" psql \
            -h "$DB_HOST" \
            -p "$DB_PORT" \
            -U "$DB_USER" \
            -d "$DB_NAME" \
            -v ON_ERROR_STOP=1 \
            --echo-errors \
            2>&1 | tee "$restore_log"

    elif [[ "$backup_file" == *.sql ]]; then
        log_info "Restoring from SQL file..."

        PGPASSWORD="$PGPASSWORD" psql \
            -h "$DB_HOST" \
            -p "$DB_PORT" \
            -U "$DB_USER" \
            -d "$DB_NAME" \
            -v ON_ERROR_STOP=1 \
            --echo-errors \
            -f "$backup_file" \
            2>&1 | tee "$restore_log"

    elif [[ "$backup_file" == *.dump ]] || [[ "$backup_file" == *.backup ]]; then
        log_info "Restoring from pg_dump custom format..."

        PGPASSWORD="$PGPASSWORD" pg_restore \
            -h "$DB_HOST" \
            -p "$DB_PORT" \
            -U "$DB_USER" \
            -d "$DB_NAME" \
            --verbose \
            --no-owner \
            --no-privileges \
            $pg_restore_opts \
            "$backup_file" \
            2>&1 | tee "$restore_log"

    else
        log_error "Unsupported backup file format"
        return 1
    fi

    local restore_status=${PIPESTATUS[0]}

    if [ $restore_status -eq 0 ]; then
        log_success "Database restore completed successfully"
        return 0
    else
        log_error "Database restore failed (exit code: $restore_status)"
        log_error "Check restore log for details: $restore_log"
        return 1
    fi
}

# Function to post-restore setup
post_restore_setup() {
    log_info "Running post-restore setup..."

    # Update statistics
    log_info "Updating database statistics..."
    PGPASSWORD="$PGPASSWORD" psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -c "ANALYZE;"

    # Reindex if necessary
    log_info "Reindexing database (if needed)..."
    PGPASSWORD="$PGPASSWORD" psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -c "REINDEX DATABASE $DB_NAME;" || log_warning "Reindex failed but continuing"

    # Refresh continuous aggregates (TimescaleDB specific)
    log_info "Refreshing continuous aggregates..."
    PGPASSWORD="$PGPASSWORD" psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -c "
        SELECT
            'SELECT ' || quote_literal('CALL refresh_continuous_aggregate(' || quote_literal(materialization_hypertable_schema || '.' || materialization_hypertable_name) || ', NULL, NULL);') as refresh_cmd
        FROM timescaledb_information.continuous_aggregates;
    " | grep -E '^CALL refresh' | while read -r cmd; do
        PGPASSWORD="$PGPASSWORD" psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -c "$cmd" || log_warning "Failed to refresh a continuous aggregate"
    done

    log_success "Post-restore setup completed"
}

# Function to validate restore
validate_restore() {
    log_info "Validating database restore..."

    # Check table counts
    local table_count
    table_count=$(PGPASSWORD="$PGPASSWORD" psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -tAc "
        SELECT COUNT(*)
        FROM information_schema.tables
        WHERE table_schema NOT IN ('information_schema', 'pg_catalog', 'timescaledb_information', 'timescaledb_experimental');
    ")

    log_info "Restored tables count: $table_count"

    # Check for key tables
    local key_tables=("market_data" "features" "signals" "trades" "models")
    local missing_tables=()

    for table in "${key_tables[@]}"; do
        local exists
        exists=$(PGPASSWORD="$PGPASSWORD" psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -tAc "
            SELECT 1 FROM information_schema.tables WHERE table_name = '$table';
        ")

        if [ -z "$exists" ]; then
            missing_tables+=("$table")
        fi
    done

    if [ ${#missing_tables[@]} -eq 0 ]; then
        log_success "All key tables are present"
    else
        log_warning "Missing tables: ${missing_tables[*]}"
    fi

    # Check TimescaleDB hypertables
    local hypertable_count
    hypertable_count=$(PGPASSWORD="$PGPASSWORD" psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -tAc "
        SELECT COUNT(*) FROM timescaledb_information.hypertables;
    " 2>/dev/null || echo "0")

    log_info "TimescaleDB hypertables count: $hypertable_count"

    # Test basic query
    log_info "Testing basic query..."
    local query_result
    query_result=$(PGPASSWORD="$PGPASSWORD" psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -tAc "SELECT 1;" 2>/dev/null)

    if [ "$query_result" = "1" ]; then
        log_success "Database is responding to queries"
    else
        log_error "Database is not responding properly"
        return 1
    fi

    log_success "Database restore validation completed"
}

# Function to send notification
send_notification() {
    local status="$1"
    local message="$2"
    local backup_file="$3"

    # Slack notification
    if [ -n "${SLACK_WEBHOOK_URL:-}" ]; then
        local color
        case $status in
            "success") color="good" ;;
            "error") color="danger" ;;
            *) color="warning" ;;
        esac

        curl -X POST -H 'Content-type: application/json' \
            --data "{
                \"attachments\": [{
                    \"color\": \"$color\",
                    \"title\": \"FXML4 Database Restore - $ENVIRONMENT\",
                    \"fields\": [
                        {\"title\": \"Status\", \"value\": \"$status\", \"short\": true},
                        {\"title\": \"Backup File\", \"value\": \"$(basename "$backup_file")\", \"short\": true},
                        {\"title\": \"Message\", \"value\": \"$message\", \"short\": false}
                    ],
                    \"footer\": \"FXML4 Restore System\",
                    \"ts\": $(date +%s)
                }]
            }" \
            "$SLACK_WEBHOOK_URL" > /dev/null 2>&1
    fi
}

# Main execution function
main() {
    local backup_file="$BACKUP_FILE"
    local pre_restore_backup=""
    local start_time
    local end_time
    local duration

    start_time=$(date +%s)

    echo "=============================================="
    echo "FXML4 Database Restore - $ENVIRONMENT"
    echo "Backup File: $backup_file"
    echo "Options: $RESTORE_OPTIONS"
    echo "Timestamp: $(date)"
    echo "=============================================="

    # Check environment variables
    if [ -z "${PGPASSWORD:-}" ]; then
        log_error "PGPASSWORD environment variable is required"
        exit 1
    fi

    # Check prerequisites
    if ! command -v psql &> /dev/null; then
        log_error "psql is required but not installed"
        exit 1
    fi

    if ! command -v pg_restore &> /dev/null; then
        log_error "pg_restore is required but not installed"
        exit 1
    fi

    # Check database connection
    if ! check_db_connection; then
        send_notification "error" "Failed to connect to database server" "$backup_file"
        exit 1
    fi

    # Find backup file if "latest" is specified
    if [ "$backup_file" = "latest" ]; then
        backup_file=$(find_latest_backup "")
        if [ -z "$backup_file" ]; then
            log_error "No backup file found"
            send_notification "error" "No backup file found" "$backup_file"
            exit 1
        fi
        log_info "Using latest backup: $backup_file"
    fi

    # Validate backup file
    if ! validate_backup_file "$backup_file"; then
        send_notification "error" "Backup file validation failed" "$backup_file"
        exit 1
    fi

    # Confirm restore if in production
    if [ "$ENVIRONMENT" = "production" ] && [ "${FORCE_RESTORE:-}" != "true" ]; then
        log_warning "This will restore the PRODUCTION database!"
        echo -n "Are you sure you want to continue? (yes/no): "
        read -r confirmation
        if [ "$confirmation" != "yes" ]; then
            log_info "Restore cancelled by user"
            exit 0
        fi
    fi

    # Ensure database exists
    ensure_database_exists

    # Create pre-restore backup
    if [ "${SKIP_PRE_BACKUP:-}" != "true" ]; then
        pre_restore_backup=$(backup_current_database) || {
            log_error "Failed to create pre-restore backup"
            send_notification "error" "Failed to create pre-restore backup" "$backup_file"
            exit 1
        }
    fi

    # Perform restore
    if restore_database "$backup_file"; then
        # Post-restore setup
        post_restore_setup

        # Validate restore
        validate_restore

        end_time=$(date +%s)
        duration=$((end_time - start_time))

        local success_message="Database restore completed successfully in ${duration}s"
        log_success "$success_message"
        send_notification "success" "$success_message" "$backup_file"

        echo "=============================================="
        echo "Restore Details:"
        echo "Source: $backup_file"
        echo "Pre-restore backup: ${pre_restore_backup:-N/A}"
        echo "Duration: ${duration}s"
        echo "=============================================="

    else
        local error_message="Database restore failed"
        log_error "$error_message"
        send_notification "error" "$error_message" "$backup_file"

        if [ -n "$pre_restore_backup" ]; then
            log_info "Pre-restore backup available at: $pre_restore_backup"
        fi

        exit 1
    fi
}

# Show usage if no arguments provided
if [ $# -eq 0 ]; then
    echo "Usage: $0 [environment] [backup_file] [restore_options]"
    echo ""
    echo "Environment: production, staging"
    echo "Backup File: Path to backup file or 'latest' for most recent"
    echo "Restore Options: clean, create, data-only, schema-only"
    echo ""
    echo "Environment Variables:"
    echo "  PGPASSWORD - Database password (required)"
    echo "  FORCE_RESTORE - Skip confirmation prompts (optional)"
    echo "  SKIP_PRE_BACKUP - Skip pre-restore backup (optional)"
    echo "  SLACK_WEBHOOK_URL - Slack webhook for notifications (optional)"
    echo ""
    echo "Examples:"
    echo "  $0 production latest clean"
    echo "  $0 staging /path/to/backup.sql.gz data-only"
    echo ""
    exit 1
fi

# Run main function
main "$@"
