# External Database Setup Guide

This guide covers configuring FXML4 to use an external PostgreSQL database with TimescaleDB extension.

## Overview

FXML4 is configured to use an external PostgreSQL database hosted at:
- **Host**: postgres01.tailb381ec.ts.net
- **Port**: 5432
- **Database**: fxml4

This setup provides better performance, reliability, and separation of concerns compared to running the database in Kubernetes.

## Prerequisites

1. **PostgreSQL 15+** with **TimescaleDB extension** installed
2. Network connectivity from Kubernetes cluster to the database (via Tailscale)
3. Database credentials with appropriate permissions
4. `psql` client installed locally for initialization

## Initial Setup

### 1. Set GitHub Secrets

First, configure the database connection secrets:

```bash
# Run the interactive setup script
./scripts/setup-github-secrets.sh
```

Enter the following values when prompted:
- **DB_HOST**: postgres01.tailb381ec.ts.net
- **DB_PORT**: 5432
- **DB_USER**: postgres
- **DB_PASSWORD**: Your secure password
- **DB_NAME**: fxml4

### 2. Initialize the Database

Run the initialization script to create the database schema:

```bash
# Set environment variables (optional)
export DB_PASSWORD='your_password'

# Run initialization
./scripts/init-external-db.sh
```

This script will:
- Create the `fxml4` database (if it doesn't exist)
- Enable TimescaleDB extension
- Run all migration files in order
- Create hypertables for time-series data
- Insert default symbols and timeframes

### 3. Verify Database Health

Check that the database is properly configured:

```bash
./scripts/check-db-health.sh
```

This will show:
- Connection status
- TimescaleDB version
- Table count and structure
- Data statistics
- Performance indicators

## Configuration Details

### Connection String

The application uses the following connection string format:
```
postgresql://postgres:password@postgres01.tailb381ec.ts.net:5432/fxml4
```

### Environment Variables

The following environment variables configure the database connection:
- `DB_HOST`: Database hostname
- `DB_PORT`: Database port
- `DB_USER`: Database username
- `DB_PASSWORD`: Database password
- `DB_NAME`: Database name

### Kubernetes Configuration

The external database configuration is stored in:
- **ConfigMap**: `k8s/configmaps/app-config.yaml` - Contains host/port/database info
- **Secret**: `k8s/secrets/app-secrets-template.yaml` - Contains credentials

## Database Schema

### Core Tables

| Table | Type | Description |
|-------|------|-------------|
| users | Regular | User accounts and authentication |
| symbols | Regular | Trading symbols (EURUSD, etc.) |
| timeframes | Regular | Time intervals (1m, 5m, etc.) |
| models | Regular | ML model metadata |
| signals | Regular | Generated trading signals |
| backtests | Regular | Backtest results |
| trades | Regular | Executed trades |

### Time-Series Tables (Hypertables)

| Table | Type | Description |
|-------|------|-------------|
| tick_data | Hypertable | Raw tick-level data |
| market_data_1m | Hypertable | 1-minute OHLCV candles |
| features | Hypertable | Computed technical indicators |
| economic_data | Hypertable | Economic indicators |

### TimescaleDB Features Used

- **Hypertables**: Automatic partitioning for time-series data
- **Compression**: Reduces storage for historical data
- **Continuous Aggregates**: Pre-computed views for faster queries
- **Retention Policies**: Automatic data cleanup

## Backup and Recovery

### Creating Backups

```bash
# Full backup (excludes large data tables)
./scripts/db-backup-restore.sh backup

# Export specific table
./scripts/db-backup-restore.sh export -t symbols
```

Backups are stored in `./backups/` directory.

### Restoring from Backup

```bash
# List available backups
./scripts/db-backup-restore.sh list

# Restore from specific backup
./scripts/db-backup-restore.sh restore -f backups/fxml4_20240101_120000.sql.gz
```

### Scheduled Backups

For production, set up a cron job:

```bash
# Daily backup at 2 AM
0 2 * * * /path/to/fxml4/scripts/db-backup-restore.sh backup
```

## Performance Optimization

### Connection Pooling

The application uses connection pooling with these defaults:
- Min connections: 5
- Max connections: 20
- Connection timeout: 30s

### Query Optimization

1. **Indexes**: Created automatically by migrations
2. **Partitioning**: Handled by TimescaleDB
3. **Compression**: Enable for older data:
   ```sql
   ALTER TABLE market_data_1m SET (
     timescaledb.compress,
     timescaledb.compress_segmentby = 'symbol_id'
   );
   ```

### Monitoring

Monitor database performance with:
```bash
# Check slow queries
./scripts/check-db-health.sh

# Connect directly for analysis
psql -h postgres01.tailb381ec.ts.net -p 5431 -U postgres -d fxml4
```

## Troubleshooting

### Connection Issues

1. **Check network connectivity**:
   ```bash
   ping postgres01.tailb381ec.ts.net
   telnet postgres01.tailb381ec.ts.net 5432
   ```

2. **Verify credentials**:
   ```bash
   psql -h postgres01.tailb381ec.ts.net -p 5432 -U postgres -d fxml4 -c "SELECT 1;"
   ```

3. **Check Kubernetes secret**:
   ```bash
   kubectl get secret fxml4-secrets -n fxml4 -o yaml
   ```

### Performance Issues

1. **Check active connections**:
   ```sql
   SELECT count(*) FROM pg_stat_activity WHERE datname='fxml4';
   ```

2. **Analyze slow queries**:
   ```sql
   SELECT query, mean_exec_time, calls
   FROM pg_stat_statements
   ORDER BY mean_exec_time DESC
   LIMIT 10;
   ```

3. **Check table sizes**:
   ```sql
   SELECT hypertable_name,
          pg_size_pretty(hypertable_size(hypertable_name::regclass))
   FROM timescaledb_information.hypertables;
   ```

### Data Issues

1. **Check data ranges**:
   ```sql
   SELECT symbol_id, MIN(time), MAX(time), COUNT(*)
   FROM market_data_1m
   GROUP BY symbol_id;
   ```

2. **Verify hypertable chunks**:
   ```sql
   SELECT show_chunks('market_data_1m');
   ```

## Security Best Practices

1. **Use strong passwords** for database access
2. **Limit network access** via firewall rules
3. **Enable SSL/TLS** for connections
4. **Regular backups** with offsite storage
5. **Monitor access logs** for suspicious activity
6. **Rotate credentials** regularly

## Migration from Internal Database

If migrating from an internal TimescaleDB:

1. **Export data**:
   ```bash
   kubectl exec -it timescaledb-pod -n fxml4 -- pg_dump -U fxml4 fxml4 > backup.sql
   ```

2. **Import to external database**:
   ```bash
   psql -h postgres01.tailb381ec.ts.net -p 5432 -U postgres -d fxml4 < backup.sql
   ```

3. **Update application configuration** and redeploy

## Support

For database-related issues:
1. Check the health status: `./scripts/check-db-health.sh`
2. Review application logs: `kubectl logs -n fxml4 deployment/fxml4-api`
3. Check database logs on the PostgreSQL server
4. Ensure TimescaleDB extension is properly installed and configured
