# FXML4 Scripts Directory

This directory contains various scripts for managing the FXML4 trading system.

## Database Management

### External Database Setup
- **`quick-setup-external-db.sh`** - Quick setup for external PostgreSQL database secrets
- **`init-external-db.sh`** - Initialize external database with schema and migrations
- **`check-db-health.sh`** - Check database health and statistics
- **`db-backup-restore.sh`** - Backup and restore database operations

### GitHub Integration
- **`setup-github-secrets.sh`** - Interactive setup for all GitHub repository secrets

## Deployment Scripts

Located in `deploy/` subdirectory:
- **`deploy.sh`** - Deploy FXML4 to Kubernetes cluster
- **`rollback.sh`** - Rollback deployments to previous versions
- **`check-deployment.sh`** - Check deployment health and status

## Data Management
- **`download_10year_forex_data.py`** - Download historical forex data
- **`load_polygon_data.py`** - Load data from Polygon.io API
- **`import_to_timescaledb.py`** - Import data into TimescaleDB

## Machine Learning
- **`train_*.py`** - Various model training scripts
- **`backtest_*.py`** - Backtesting scripts for different strategies
- **`test_ml_*.py`** - ML workflow testing scripts

## API and Services
- **`start_fxml4_api.py`** - Start the FXML4 API server
- **`test_api_backtest.py`** - Test API endpoints

## Quick Start Examples

### 1. Set up external database:
```bash
./scripts/quick-setup-external-db.sh
./scripts/init-external-db.sh
```

### 2. Configure all secrets:
```bash
./scripts/setup-github-secrets.sh
```

### 3. Deploy to Kubernetes:
```bash
./scripts/deploy/deploy.sh
```

### 4. Check deployment:
```bash
./scripts/deploy/check-deployment.sh
```

### 5. Backup database:
```bash
./scripts/db-backup-restore.sh backup
```
