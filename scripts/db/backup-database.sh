#!/bin/bash

# FXML4 Production Database Backup Script
# Supports TimescaleDB with compression and continuous aggregates
# Usage: ./backup-database.sh [environment] [backup_type] [retention_days]

set -euo pipefail

# Configuration
ENVIRONMENT="${1:-production}"
BACKUP_TYPE="${2:-full}"  # full, incremental, schema-only
RETENTION_DAYS="${3:-30}"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")

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

# Backup paths
LOCAL_BACKUP_DIR="/opt/fxml4/backups/${ENVIRONMENT}"
BACKUP_FILENAME="${DB_NAME}_${BACKUP_TYPE}_${TIMESTAMP}"

# Ensure backup directory exists
mkdir -p "$LOCAL_BACKUP_DIR"

# Function to check database connectivity
check_db_connection() {
    log_info "Checking database connectivity..."

    if PGPASSWORD="$PGPASSWORD" psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -c '\q' 2>/dev/null; then
        log_success "Database connection successful"
        return 0
    else
        log_error "Failed to connect to database"
        return 1
    fi
}

# Function to get database size
get_db_size() {
    local size_query="SELECT pg_size_pretty(pg_database_size('$DB_NAME')) AS size;"
    local db_size

    db_size=$(PGPASSWORD="$PGPASSWORD" psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -t -c "$size_query" | xargs)
    echo "$db_size"
}

# Function to create schema-only backup
backup_schema_only() {
    local backup_file="${LOCAL_BACKUP_DIR}/${BACKUP_FILENAME}_schema.sql"

    log_info "Creating schema-only backup..."

    PGPASSWORD="$PGPASSWORD" pg_dump \
        -h "$DB_HOST" \
        -p "$DB_PORT" \
        -U "$DB_USER" \
        -d "$DB_NAME" \
        --schema-only \
        --no-owner \
        --no-privileges \
        --verbose \
        --file="$backup_file"

    if [ $? -eq 0 ]; then
        log_success "Schema backup completed: $backup_file"
        echo "$backup_file"
    else
        log_error "Schema backup failed"
        return 1
    fi
}

# Function to create full backup with compression
backup_full() {
    local backup_file="${LOCAL_BACKUP_DIR}/${BACKUP_FILENAME}_full.sql.gz"

    log_info "Creating full database backup with compression..."
    log_info "Database size: $(get_db_size)"

    PGPASSWORD="$PGPASSWORD" pg_dump \
        -h "$DB_HOST" \
        -p "$DB_PORT" \
        -U "$DB_USER" \
        -d "$DB_NAME" \
        --verbose \
        --no-owner \
        --no-privileges \
        --exclude-table-data='audit_logs' \
        --exclude-table-data='raw_market_data' \
        | gzip > "$backup_file"

    if [ $? -eq 0 ]; then
        local backup_size
        backup_size=$(du -sh "$backup_file" | cut -f1)
        log_success "Full backup completed: $backup_file (Size: $backup_size)"
        echo "$backup_file"
    else
        log_error "Full backup failed"
        return 1
    fi
}

# Function to create incremental backup using WAL files
backup_incremental() {
    local backup_dir="${LOCAL_BACKUP_DIR}/incremental_${TIMESTAMP}"

    log_info "Creating incremental backup using WAL archiving..."

    mkdir -p "$backup_dir"

    # Create base backup if it doesn't exist
    local base_backup_dir="${LOCAL_BACKUP_DIR}/base_backup"
    if [ ! -d "$base_backup_dir" ]; then
        log_info "Creating base backup for incremental strategy..."
        PGPASSWORD="$PGPASSWORD" pg_basebackup \
            -h "$DB_HOST" \
            -p "$DB_PORT" \
            -U "$DB_USER" \
            -D "$base_backup_dir" \
            -Ft \
            -z \
            -P \
            -W
    fi

    # Archive current WAL files
    PGPASSWORD="$PGPASSWORD" psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -c "SELECT pg_switch_wal();" > /dev/null

    log_success "Incremental backup setup completed: $backup_dir"
    echo "$backup_dir"
}

# Function to backup specific TimescaleDB components
backup_timescale_specific() {
    local backup_file="${LOCAL_BACKUP_DIR}/${BACKUP_FILENAME}_timescale.sql.gz"

    log_info "Creating TimescaleDB-specific backup (hypertables, continuous aggregates)..."

    # Custom query to backup TimescaleDB metadata and configurations
    local timescale_query="
        -- Export hypertable configurations
        SELECT 'CREATE HYPERTABLE ' || quote_ident(schema_name) || '.' || quote_ident(table_name) ||
               '(' || quote_literal(dimension_column) || ', chunk_time_interval => INTERVAL ' ||
               quote_literal(chunk_time_interval::text) || ');'
        FROM timescaledb_information.hypertables;

        -- Export continuous aggregates
        SELECT 'CREATE MATERIALIZED VIEW ' || quote_ident(materialization_hypertable_schema) || '.' ||
               quote_ident(materialization_hypertable_name) || ' WITH (timescaledb.continuous) AS ' ||
               view_definition || ';'
        FROM timescaledb_information.continuous_aggregates;

        -- Export compression policies
        SELECT 'SELECT add_compression_policy(' || quote_literal(hypertable_schema || '.' || hypertable_name) ||
               ', INTERVAL ' || quote_literal(compress_after::text) || ');'
        FROM timescaledb_information.compression_settings;
    "

    (
        echo "-- TimescaleDB Configuration Backup"
        echo "-- Generated on $(date)"
        echo ""
        PGPASSWORD="$PGPASSWORD" psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -t -c "$timescale_query"
        echo ""
        echo "-- Data Backup"
        PGPASSWORD="$PGPASSWORD" pg_dump \
            -h "$DB_HOST" \
            -p "$DB_PORT" \
            -U "$DB_USER" \
            -d "$DB_NAME" \
            --data-only \
            --no-owner \
            --no-privileges \
            --table='market_data' \
            --table='features' \
            --table='signals' \
            --table='trades'
    ) | gzip > "$backup_file"

    if [ $? -eq 0 ]; then
        log_success "TimescaleDB backup completed: $backup_file"
        echo "$backup_file"
    else
        log_error "TimescaleDB backup failed"
        return 1
    fi
}

# Function to upload backup to cloud storage
upload_to_cloud() {
    local backup_file="$1"
    local cloud_path="${BACKUP_BUCKET}/${ENVIRONMENT}/$(basename "$backup_file")"

    log_info "Uploading backup to cloud storage: $cloud_path"

    if command -v aws &> /dev/null; then
        aws s3 cp "$backup_file" "s3://$cloud_path" --storage-class STANDARD_IA
        if [ $? -eq 0 ]; then
            log_success "Upload to S3 completed"
        else
            log_error "S3 upload failed"
            return 1
        fi
    elif command -v gsutil &> /dev/null; then
        gsutil cp "$backup_file" "gs://$cloud_path"
        if [ $? -eq 0 ]; then
            log_success "Upload to GCS completed"
        else
            log_error "GCS upload failed"
            return 1
        fi
    else
        log_warning "No cloud storage CLI found, backup remains local only"
    fi
}

# Function to verify backup integrity
verify_backup() {
    local backup_file="$1"

    log_info "Verifying backup integrity..."

    if [[ "$backup_file" == *.gz ]]; then
        if gzip -t "$backup_file" 2>/dev/null; then
            log_success "Backup file integrity verified"
        else
            log_error "Backup file is corrupted"
            return 1
        fi
    else
        if [ -s "$backup_file" ]; then
            log_success "Backup file exists and is not empty"
        else
            log_error "Backup file is empty or doesn't exist"
            return 1
        fi
    fi

    # Additional verification for SQL files
    if [[ "$backup_file" == *.sql* ]]; then
        if grep -q "PostgreSQL database dump" "$backup_file" 2>/dev/null || zgrep -q "PostgreSQL database dump" "$backup_file" 2>/dev/null; then
            log_success "Backup appears to be a valid PostgreSQL dump"
        else
            log_warning "Could not verify PostgreSQL dump format"
        fi
    fi
}

# Function to cleanup old backups
cleanup_old_backups() {
    log_info "Cleaning up backups older than $RETENTION_DAYS days..."

    local deleted_count=0

    # Local cleanup
    if [ -d "$LOCAL_BACKUP_DIR" ]; then
        deleted_count=$(find "$LOCAL_BACKUP_DIR" -name "*.sql*" -mtime +$RETENTION_DAYS -delete -print | wc -l)
        log_info "Deleted $deleted_count local backup files"
    fi

    # Cloud cleanup (if supported)
    if command -v aws &> /dev/null; then
        aws s3 ls "s3://${BACKUP_BUCKET}/${ENVIRONMENT}/" --recursive | \
        awk -v date="$(date -d "$RETENTION_DAYS days ago" +%Y-%m-%d)" '$1 < date {print $4}' | \
        while read -r file; do
            aws s3 rm "s3://${BACKUP_BUCKET}/$file"
            ((deleted_count++))
        done
        log_info "Deleted $deleted_count cloud backup files"
    fi
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

        local backup_size=""
        if [ -f "$backup_file" ]; then
            backup_size="Size: $(du -sh "$backup_file" | cut -f1)"
        fi

        curl -X POST -H 'Content-type: application/json' \
            --data "{
                \"attachments\": [{
                    \"color\": \"$color\",
                    \"title\": \"FXML4 Database Backup - $ENVIRONMENT\",
                    \"fields\": [
                        {\"title\": \"Status\", \"value\": \"$status\", \"short\": true},
                        {\"title\": \"Type\", \"value\": \"$BACKUP_TYPE\", \"short\": true},
                        {\"title\": \"Message\", \"value\": \"$message\", \"short\": false},
                        {\"title\": \"Details\", \"value\": \"$backup_size\", \"short\": true}
                    ],
                    \"footer\": \"FXML4 Backup System\",
                    \"ts\": $(date +%s)
                }]
            }" \
            "$SLACK_WEBHOOK_URL" > /dev/null 2>&1
    fi

    # Email notification (if configured)
    if [ -n "${BACKUP_EMAIL:-}" ] && command -v mail &> /dev/null; then
        echo "$message" | mail -s "FXML4 Database Backup - $status" "$BACKUP_EMAIL"
    fi
}

# Main execution function
main() {
    local backup_file=""
    local start_time
    local end_time
    local duration

    start_time=$(date +%s)

    echo "=============================================="
    echo "FXML4 Database Backup - $ENVIRONMENT"
    echo "Type: $BACKUP_TYPE"
    echo "Timestamp: $(date)"
    echo "=============================================="

    # Check environment variables
    if [ -z "${PGPASSWORD:-}" ]; then
        log_error "PGPASSWORD environment variable is required"
        exit 1
    fi

    # Check prerequisites
    if ! command -v pg_dump &> /dev/null; then
        log_error "pg_dump is required but not installed"
        exit 1
    fi

    # Check database connection
    if ! check_db_connection; then
        send_notification "error" "Failed to connect to database" ""
        exit 1
    fi

    # Execute backup based on type
    case $BACKUP_TYPE in
        "full")
            backup_file=$(backup_full)
            ;;
        "schema-only")
            backup_file=$(backup_schema_only)
            ;;
        "incremental")
            backup_file=$(backup_incremental)
            ;;
        "timescale")
            backup_file=$(backup_timescale_specific)
            ;;
        *)
            log_error "Unknown backup type: $BACKUP_TYPE"
            send_notification "error" "Unknown backup type: $BACKUP_TYPE" ""
            exit 1
            ;;
    esac

    # Verify backup
    if [ -n "$backup_file" ] && verify_backup "$backup_file"; then
        # Upload to cloud storage
        upload_to_cloud "$backup_file"

        # Cleanup old backups
        cleanup_old_backups

        end_time=$(date +%s)
        duration=$((end_time - start_time))

        local success_message="Backup completed successfully in ${duration}s"
        log_success "$success_message"
        send_notification "success" "$success_message" "$backup_file"

        echo "=============================================="
        echo "Backup Details:"
        echo "File: $backup_file"
        echo "Size: $(du -sh "$backup_file" | cut -f1)"
        echo "Duration: ${duration}s"
        echo "=============================================="

    else
        local error_message="Backup failed or verification failed"
        log_error "$error_message"
        send_notification "error" "$error_message" "$backup_file"
        exit 1
    fi
}

# Show usage if no arguments provided
if [ $# -eq 0 ]; then
    echo "Usage: $0 [environment] [backup_type] [retention_days]"
    echo ""
    echo "Environment: production, staging"
    echo "Backup Type: full, schema-only, incremental, timescale"
    echo "Retention: Number of days to keep backups (default: 30)"
    echo ""
    echo "Environment Variables:"
    echo "  PGPASSWORD - Database password (required)"
    echo "  SLACK_WEBHOOK_URL - Slack webhook for notifications (optional)"
    echo "  BACKUP_EMAIL - Email for notifications (optional)"
    echo ""
    exit 1
fi

# Run main function
main "$@"
