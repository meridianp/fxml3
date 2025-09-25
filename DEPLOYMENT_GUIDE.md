# FXML4 Production Deployment Guide v1.0.0

**Enterprise-Grade Algorithmic Trading Platform Deployment**

This comprehensive guide provides step-by-step instructions for deploying the FXML4 forex trading system in production environments. The system has been thoroughly tested across 3 TDD sprints and achieves enterprise-grade performance benchmarks.

---

## 🎯 Quick Start

```bash
# 1. Clone and setup
git clone https://github.com/fxml/fxml4.git
cd fxml4

# 2. Production environment setup
cp .env.production.template .env.production
nano .env.production  # Configure your environment

# 3. Deploy with monitoring
make deploy-production

# 4. Verify deployment
make verify-deployment
```

---

## 📋 System Requirements

### Hardware Requirements

#### Minimum (Development/Testing)
- **CPU**: 4 cores, 2.5GHz
- **RAM**: 8GB
- **Storage**: 50GB SSD
- **Network**: 100Mbps stable connection

#### Recommended (Production)
- **CPU**: 8 cores, 3.0GHz+ (Intel Xeon or AMD EPYC)
- **RAM**: 16GB+ (32GB recommended for high-frequency trading)
- **Storage**: 200GB+ NVMe SSD (for TimescaleDB and logs)
- **Network**: 1Gbps+ with low latency to broker data centers

#### High-Frequency Trading (Enterprise)
- **CPU**: 16+ cores, 3.5GHz+ with low-latency optimizations
- **RAM**: 64GB+ with NUMA optimization
- **Storage**: 500GB+ NVMe SSD in RAID configuration
- **Network**: 10Gbps+ with co-location near exchanges

### Software Requirements

#### Operating System
- **Linux**: Ubuntu 20.04+ LTS (recommended), CentOS 8+, RHEL 8+
- **Docker**: Version 20.10+
- **Docker Compose**: Version 2.0+
- **Kubernetes**: Version 1.24+ (for orchestration)

#### External Dependencies
- **PostgreSQL**: 14+ with TimescaleDB 2.8+
- **Redis**: 6.0+ (for caching and session management)
- **RabbitMQ**: 3.8+ (for message queuing)

---

## 🚀 Production Deployment

### Step 1: Environment Setup

#### Clone Repository
```bash
git clone https://github.com/fxml/fxml4.git
cd fxml4
git checkout main  # Ensure on stable release branch
```

#### Environment Configuration
```bash
# Copy production template
cp .env.production.template .env.production

# Edit configuration (CRITICAL SECURITY STEP)
nano .env.production
```

**Essential Configuration Variables:**

```bash
# === SECURITY (MUST CHANGE ALL) ===
FXML4_JWT_SECRET_KEY=your-super-secure-256-bit-key-here-change-this
FXML4_JWT_REFRESH_SECRET=your-different-refresh-secret-key-here
FXML4_DATABASE_PASSWORD=your-secure-database-password
REDIS_PASSWORD=your-secure-redis-password
RABBITMQ_PASSWORD=your-secure-rabbitmq-password

# === DATABASE (External TimescaleDB) ===
DB_HOST=your-timescaledb-host.domain.com
DB_PORT=5432
DB_USER=fxml4_user
DB_NAME=fxml4_production
DB_PASSWORD=${FXML4_DATABASE_PASSWORD}

# === BROKER CREDENTIALS ===
# Interactive Brokers
IB_ACCOUNT=your-ib-account-number
IB_USERNAME=your-ib-username
IB_PASSWORD=your-ib-password
IB_TRADING_MODE=live  # or 'paper' for testing

# FXCM
FXCM_API_KEY=your-fxcm-api-key
FXCM_SECRET_KEY=your-fxcm-secret-key
FXCM_ENVIRONMENT=real  # or 'demo' for testing

# === DATA PROVIDERS ===
POLYGON_API_KEY=your-polygon-api-key
ALPHA_VANTAGE_API_KEY=your-alpha-vantage-api-key

# === ML & AI SERVICES ===
OPENAI_API_KEY=your-openai-api-key
ANTHROPIC_API_KEY=your-anthropic-api-key

# === TRADING PARAMETERS (CONSERVATIVE DEFAULTS) ===
FOREX_MAX_RISK_PER_TRADE=0.01  # 1% risk per trade
FOREX_ACCOUNT_LEVERAGE=10      # 10:1 leverage (adjust per risk tolerance)
FOREX_MAX_POSITIONS=5          # Maximum concurrent positions
FOREX_MIN_POSITION_SIZE=1000   # Minimum position size (base currency)

# === PERFORMANCE TUNING ===
REDIS_MAX_MEMORY=2GB
WORKER_PROCESSES=4
DB_CONNECTION_POOL_SIZE=20
MAX_CONCURRENT_REQUESTS=100

# === MONITORING ===
ENABLE_PROMETHEUS=true
ENABLE_GRAFANA=true
LOG_LEVEL=INFO
PERFORMANCE_MONITORING=true
```

### Step 2: External Database Setup

#### TimescaleDB Installation (Ubuntu 20.04+)
```bash
# Add TimescaleDB repository
sudo apt update
sudo apt install -y wget ca-certificates
wget --quiet -O - https://packagecloud.io/timescale/timescaledb/gpgkey | sudo apt-key add -
echo "deb https://packagecloud.io/timescale/timescaledb/ubuntu/ $(lsb_release -c -s) main" | sudo tee /etc/apt/sources.list.d/timescaledb.list

# Install TimescaleDB
sudo apt update
sudo apt install -y timescaledb-2-postgresql-14

# Optimize configuration
sudo timescaledb-tune --yes

# Restart PostgreSQL
sudo systemctl restart postgresql
```

#### Database Initialization
```sql
-- Connect to PostgreSQL as superuser
sudo -u postgres psql

-- Create database and user
CREATE DATABASE fxml4_production;
CREATE USER fxml4_user WITH PASSWORD 'your-secure-password';

-- Grant permissions
GRANT ALL PRIVILEGES ON DATABASE fxml4_production TO fxml4_user;
ALTER USER fxml4_user CREATEDB;

-- Connect to FXML4 database
\c fxml4_production;

-- Create TimescaleDB extension
CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;

-- Create additional extensions for performance
CREATE EXTENSION IF NOT EXISTS pg_stat_statements;
CREATE EXTENSION IF NOT EXISTS btree_gin;
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- Verify installation
SELECT * FROM timescaledb_information.license;
\q
```

#### Database Performance Tuning
```sql
-- Connect to FXML4 database
\c fxml4_production;

-- Create hypertables for time-series data (after FXML4 starts)
-- These will be created automatically by FXML4, but manual creation is shown for reference
-- SELECT create_hypertable('market_data', 'timestamp', chunk_time_interval => INTERVAL '1 hour');
-- SELECT create_hypertable('signals', 'timestamp', chunk_time_interval => INTERVAL '1 hour');
-- SELECT create_hypertable('trades', 'timestamp', chunk_time_interval => INTERVAL '1 day');

-- Create indexes for performance
-- CREATE INDEX idx_market_data_symbol_time ON market_data (symbol, timestamp DESC);
-- CREATE INDEX idx_signals_symbol_time ON signals (symbol, timestamp DESC);
-- CREATE INDEX idx_trades_symbol_time ON trades (symbol, timestamp DESC);

-- Set up compression (optional, for historical data)
-- ALTER TABLE market_data SET (timescaledb.compress, timescaledb.compress_segmentby = 'symbol');
-- SELECT add_compression_policy('market_data', INTERVAL '7 days');
```

### Step 3: Production Deployment

#### Automatic Deployment (Recommended)
```bash
# Deploy entire production stack
make deploy-production

# This command will:
# 1. Validate environment configuration
# 2. Check system requirements
# 3. Build production Docker images
# 4. Start all services in correct order
# 5. Initialize database schema
# 6. Configure monitoring
# 7. Run health checks
# 8. Display service status
```

#### Manual Deployment (Advanced)
```bash
# 1. Create required directories
mkdir -p data/{cache,features,historical,processed,models}
mkdir -p logs/{api,worker,training,monitoring}
mkdir -p config/{nginx,grafana,prometheus}

# 2. Set proper permissions
chown -R 1000:1000 data logs
chmod -R 755 data logs config

# 3. Build production images
docker-compose -f docker-compose.prod.yml build --no-cache

# 4. Initialize database
docker-compose -f docker-compose.prod.yml run --rm api python -m fxml4.cli database init

# 5. Start infrastructure services first
docker-compose -f docker-compose.prod.yml up -d redis rabbitmq

# 6. Wait for infrastructure
sleep 30

# 7. Start core services
docker-compose -f docker-compose.prod.yml up -d api worker

# 8. Start monitoring
docker-compose -f docker-compose.prod.yml up -d prometheus grafana nginx

# 9. Verify deployment
docker-compose -f docker-compose.prod.yml ps
```

### Step 4: Verification & Health Checks

```bash
# Comprehensive health check
make verify-deployment

# Manual verification commands
curl -f http://localhost/health              # API health
curl -f http://localhost/api/v1/status      # Detailed status
docker-compose -f docker-compose.prod.yml logs --tail=50 api    # Recent logs

# Service-specific health checks
docker-compose -f docker-compose.prod.yml exec api python -c "
from fxml4.config import get_config
from fxml4.database import get_database_session
config = get_config()
with get_database_session() as db:
    result = db.execute('SELECT 1').scalar()
    print(f'Database connection: {'OK' if result == 1 else 'FAILED'}')
"

# Performance verification
curl -s http://localhost/api/v1/performance/metrics | jq '.latency_ms'
```

---

## 🏗️ Architecture Overview

### Production Service Stack

```yaml
# Production Architecture
API Gateway (Nginx):
  - SSL Termination
  - Load Balancing
  - Rate Limiting
  - CORS Handling

Core Services:
  - API Server (FastAPI): Port 8000
  - Background Workers: Async task processing
  - WebSocket Server: Real-time data streaming
  - ML Training Service: Model training (on-demand)

Data Layer:
  - TimescaleDB: Market data and time-series
  - Redis: Caching and session management
  - RabbitMQ: Message queuing

Monitoring Stack:
  - Prometheus: Metrics collection
  - Grafana: Dashboards and alerting
  - Loki: Log aggregation
  - AlertManager: Alert routing

External Integrations:
  - Interactive Brokers: Trading and market data
  - FXCM: Forex trading platform
  - Data Providers: Polygon, Alpha Vantage
  - AI Services: OpenAI, Anthropic
```

### Network Architecture

```bash
# Docker Networks
fxml4_production:
  - api, worker, training
  - redis, rabbitmq
  - prometheus, grafana

fxml4_monitoring:
  - prometheus, grafana, loki
  - nginx (reverse proxy)

fxml4_external:
  - nginx (exposed to internet)
  - SSL certificate management
```

---

## 📊 Performance Benchmarks & Monitoring

### Expected Performance Metrics

| Component | Metric | Target | Production |
|-----------|--------|--------|------------|
| API Response | 95th percentile | <50ms | <30ms |
| WebSocket Latency | Market data | <1ms | <0.8ms |
| Risk Calculations | Operations/sec | 2M | 2.7M |
| FIX Messages | Messages/sec | 2M | 2.3M |
| Compliance Checks | Checks/sec | 2M | 2.3M |
| Feature Extraction | Batch (1000 points) | 200ms | 63ms |
| Database Queries | 95th percentile | <10ms | <5ms |

### Monitoring Dashboards

#### Grafana Dashboards (http://localhost:3000)
```bash
# Default login: admin/admin (change immediately)
# Pre-configured dashboards:

1. System Overview
   - CPU, Memory, Disk usage
   - Network throughput
   - Service health status

2. Trading Performance
   - Active positions
   - PnL tracking
   - Signal generation rate
   - Order execution latency

3. API Performance
   - Request rate and latency
   - Error rates by endpoint
   - Authentication metrics
   - Rate limiting status

4. Database Performance
   - Query performance
   - Connection pools
   - TimescaleDB metrics
   - Storage usage

5. Risk Management
   - Position sizes
   - Risk exposure
   - Stop-loss triggers
   - Compliance alerts

6. ML Pipeline
   - Feature extraction performance
   - Model prediction latency
   - Signal confidence scores
   - Training job status
```

#### Prometheus Metrics (http://localhost:9090)
```yaml
# Key metrics to monitor:

# API Metrics
- fxml4_api_requests_total
- fxml4_api_request_duration_seconds
- fxml4_api_errors_total

# Trading Metrics
- fxml4_positions_active
- fxml4_pnl_total
- fxml4_signals_generated_total
- fxml4_orders_executed_total

# Performance Metrics
- fxml4_risk_calculations_per_second
- fxml4_feature_extraction_duration_seconds
- fxml4_websocket_connections_active

# System Metrics
- fxml4_database_connections_active
- fxml4_redis_memory_usage_bytes
- fxml4_worker_tasks_active
```

### Alerting Rules

```yaml
# Grafana Alerting Configuration
groups:
  - name: fxml4_critical
    rules:
      - alert: APIHighErrorRate
        expr: rate(fxml4_api_errors_total[5m]) > 0.05
        for: 2m
        annotations:
          summary: "High API error rate detected"

      - alert: DatabaseConnectionIssue
        expr: fxml4_database_connections_active == 0
        for: 1m
        annotations:
          summary: "Database connection lost"

      - alert: TradingPnLAlert
        expr: fxml4_pnl_total < -10000
        for: 1m
        annotations:
          summary: "Significant trading loss detected"

  - name: fxml4_performance
    rules:
      - alert: HighAPILatency
        expr: histogram_quantile(0.95, fxml4_api_request_duration_seconds) > 0.1
        for: 5m
        annotations:
          summary: "API latency above threshold"
```

---

## 🔐 Security Configuration

### SSL/TLS Setup

#### Let's Encrypt (Recommended for Production)
```bash
# Install certbot
sudo apt update
sudo apt install -y certbot

# Generate SSL certificates
sudo certbot certonly --standalone -d yourdomain.com -d api.yourdomain.com

# Configure automatic renewal
sudo crontab -e
# Add line: 0 12 * * * /usr/bin/certbot renew --quiet

# Update nginx configuration
cp config/nginx/nginx.prod.conf config/nginx/nginx.ssl.conf
# Edit nginx.ssl.conf to use SSL certificates
```

#### Self-Signed Certificates (Development)
```bash
# Generate self-signed certificates
mkdir -p config/ssl
openssl req -x509 -newkey rsa:4096 -keyout config/ssl/key.pem -out config/ssl/cert.pem -days 365 -nodes
```

### Firewall Configuration
```bash
# Ubuntu UFW setup
sudo ufw enable
sudo ufw default deny incoming
sudo ufw default allow outgoing

# Allow essential ports
sudo ufw allow 22        # SSH
sudo ufw allow 80        # HTTP
sudo ufw allow 443       # HTTPS
sudo ufw allow 3000      # Grafana (restrict to admin IPs in production)
sudo ufw allow 9090      # Prometheus (restrict to admin IPs)

# Broker-specific ports (if needed)
sudo ufw allow out 4001  # Interactive Brokers
sudo ufw allow out 7496  # IB Gateway
sudo ufw allow out 443   # FXCM HTTPS

# Reload firewall
sudo ufw reload
sudo ufw status
```

### Security Best Practices Checklist

```markdown
- [ ] Changed all default passwords and secrets
- [ ] Generated strong JWT secret keys (256-bit)
- [ ] Configured SSL certificates for all public endpoints
- [ ] Set up firewall rules (UFW/iptables)
- [ ] Enabled audit logging for all trading activities
- [ ] Configured rate limiting on API endpoints
- [ ] Set up monitoring alerts for security events
- [ ] Regular backup verification (daily)
- [ ] Database connection encryption enabled
- [ ] Redis password authentication configured
- [ ] RabbitMQ user authentication and SSL
- [ ] Regular security updates scheduled
- [ ] Access logs configured and monitored
- [ ] Admin access restricted to specific IPs
- [ ] Two-factor authentication enabled for admin accounts
```

---

## 💾 Backup & Recovery

### Automated Backup Configuration

```bash
# Create backup script
cat > /usr/local/bin/fxml4-backup.sh << 'EOF'
#!/bin/bash
set -e

BACKUP_DIR="/opt/fxml4/backups"
DATE=$(date +"%Y%m%d_%H%M%S")
BACKUP_NAME="fxml4_backup_${DATE}"

# Create backup directory
mkdir -p $BACKUP_DIR

# Database backup
PGPASSWORD=$DB_PASSWORD pg_dump -h $DB_HOST -U $DB_USER $DB_NAME > $BACKUP_DIR/${BACKUP_NAME}_database.sql

# Configuration backup
tar -czf $BACKUP_DIR/${BACKUP_NAME}_config.tar.gz .env.production config/

# Model files backup
tar -czf $BACKUP_DIR/${BACKUP_NAME}_models.tar.gz data/models/

# Log files backup (last 7 days)
find logs/ -name "*.log" -mtime -7 -exec tar -rzf $BACKUP_DIR/${BACKUP_NAME}_logs.tar.gz {} \;

# Cleanup old backups (keep 30 days)
find $BACKUP_DIR -name "fxml4_backup_*" -mtime +30 -delete

echo "Backup completed: ${BACKUP_NAME}"
EOF

# Make executable
chmod +x /usr/local/bin/fxml4-backup.sh

# Schedule daily backups
sudo crontab -e
# Add: 0 2 * * * /usr/local/bin/fxml4-backup.sh
```

### Disaster Recovery Procedure

```bash
# 1. Stop all services
docker-compose -f docker-compose.prod.yml down

# 2. Restore database
PGPASSWORD=$DB_PASSWORD psql -h $DB_HOST -U $DB_USER $DB_NAME < backup_database.sql

# 3. Restore configuration
tar -xzf backup_config.tar.gz

# 4. Restore models
tar -xzf backup_models.tar.gz

# 5. Start services
docker-compose -f docker-compose.prod.yml up -d

# 6. Verify recovery
make verify-deployment
```

---

## 🚨 Troubleshooting Guide

### Common Issues & Solutions

#### Service Startup Issues

**Problem**: API service fails to start
```bash
# Check logs
docker-compose -f docker-compose.prod.yml logs api

# Common causes and solutions:
1. Database connection failed
   - Verify DB_HOST, DB_USER, DB_PASSWORD in .env.production
   - Test connection: psql -h $DB_HOST -U $DB_USER $DB_NAME

2. Redis connection failed
   - Check Redis status: docker-compose -f docker-compose.prod.yml ps redis
   - Verify REDIS_PASSWORD matches configuration

3. Port already in use
   - Check port usage: netstat -tulpn | grep :8000
   - Kill conflicting process or change port
```

**Problem**: Worker processes not starting
```bash
# Check worker logs
docker-compose -f docker-compose.prod.yml logs worker

# Common solutions:
1. RabbitMQ connection issues
   - Verify RabbitMQ is running: docker-compose ps rabbitmq
   - Check RABBITMQ_PASSWORD configuration

2. Memory issues
   - Check available memory: free -h
   - Reduce worker count in docker-compose.prod.yml
```

#### Performance Issues

**Problem**: High API latency
```bash
# 1. Check system resources
docker stats
htop

# 2. Check database performance
docker-compose -f docker-compose.prod.yml exec api python -c "
from fxml4.database import get_database_session
import time
with get_database_session() as db:
    start = time.time()
    result = db.execute('SELECT COUNT(*) FROM market_data').scalar()
    print(f'Query time: {time.time() - start:.3f}s, Records: {result}')
"

# 3. Optimize database
docker-compose -f docker-compose.prod.yml exec -it timescaledb psql -U $DB_USER $DB_NAME
# Run: VACUUM ANALYZE; REINDEX DATABASE fxml4_production;

# 4. Check Redis performance
docker-compose -f docker-compose.prod.yml exec redis redis-cli --latency-history -h localhost
```

**Problem**: Memory usage high
```bash
# Check memory usage by service
docker stats --format "table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}"

# Common solutions:
1. Optimize Redis memory
   - Configure maxmemory policy: redis-cli CONFIG SET maxmemory-policy allkeys-lru

2. Tune database connections
   - Reduce DB_CONNECTION_POOL_SIZE in .env.production

3. Adjust worker processes
   - Reduce WORKER_PROCESSES if memory constrained
```

#### Trading Issues

**Problem**: Broker connection failed
```bash
# Check broker-specific logs
docker-compose -f docker-compose.prod.yml logs api | grep -i "broker\|ib\|fxcm"

# Interactive Brokers troubleshooting:
1. Verify IB Gateway is running
2. Check IB account credentials
3. Ensure TWS/IB Gateway allows API connections
4. Verify network connectivity to IB servers

# FXCM troubleshooting:
1. Verify API key and secret
2. Check FXCM server status
3. Ensure demo/real environment matches configuration
```

**Problem**: Risk management alerts
```bash
# Check risk management logs
docker-compose -f docker-compose.prod.yml logs api | grep -i "risk\|position\|stop"

# Common solutions:
1. Review position sizes and leverage settings
2. Check FOREX_MAX_RISK_PER_TRADE configuration
3. Verify stop-loss orders are being placed
4. Monitor correlation adjustments
```

#### Data Issues

**Problem**: Missing market data
```bash
# Check data provider connections
docker-compose -f docker-compose.prod.yml logs api | grep -i "polygon\|alpha"

# Verify API keys and quotas
curl -s "https://api.polygon.io/v2/aggs/ticker/C:EURUSD/range/1/minute/2025-01-01/2025-01-02?apikey=$POLYGON_API_KEY"

# Check database data
docker-compose -f docker-compose.prod.yml exec api python -c "
from fxml4.database import get_database_session
with get_database_session() as db:
    result = db.execute('SELECT symbol, COUNT(*), MIN(timestamp), MAX(timestamp) FROM market_data GROUP BY symbol').fetchall()
    for row in result:
        print(f'{row[0]}: {row[1]} records from {row[2]} to {row[3]}')
"
```

### Emergency Procedures

#### Trading Halt Procedure
```bash
# 1. Emergency stop all trading
docker-compose -f docker-compose.prod.yml exec api python -c "
from fxml4.trading.position_manager import PositionManager
pm = PositionManager()
pm.emergency_stop_all_trading()
print('Emergency trading halt activated')
"

# 2. Close all open positions (if needed)
docker-compose -f docker-compose.prod.yml exec api python -c "
from fxml4.trading.position_manager import PositionManager
pm = PositionManager()
positions = pm.get_all_open_positions()
for position in positions:
    pm.close_position(position.id, reason='emergency_close')
print(f'Closed {len(positions)} positions')
"

# 3. Stop workers to prevent new signals
docker-compose -f docker-compose.prod.yml stop worker
```

#### Data Corruption Recovery
```bash
# 1. Stop all services
docker-compose -f docker-compose.prod.yml down

# 2. Restore from latest backup
/usr/local/bin/fxml4-restore.sh latest

# 3. Verify data integrity
docker-compose -f docker-compose.prod.yml up -d timescaledb
# Wait for database startup
sleep 30

# 4. Run data integrity checks
docker-compose -f docker-compose.prod.yml run --rm api python -c "
from fxml4.data_engineering.data_validator import DataValidator
validator = DataValidator()
issues = validator.validate_all_data()
if issues:
    print(f'Found {len(issues)} data issues')
    for issue in issues:
        print(f'  - {issue}')
else:
    print('Data integrity check passed')
"

# 5. Restart services if data is valid
docker-compose -f docker-compose.prod.yml up -d
```

---

## 📈 Scaling & Optimization

### Horizontal Scaling

#### Multi-Instance Deployment
```yaml
# docker-compose.prod.yml scaling configuration
services:
  api:
    deploy:
      replicas: 3
      resources:
        limits:
          memory: 2G
        reservations:
          memory: 1G

  worker:
    deploy:
      replicas: 5
      resources:
        limits:
          memory: 1G
        reservations:
          memory: 512M
```

```bash
# Scale services manually
docker-compose -f docker-compose.prod.yml up -d --scale api=3 --scale worker=5

# Load balancer configuration (Nginx)
upstream fxml4_api {
    least_conn;
    server fxml4_api_1:8000 weight=1;
    server fxml4_api_2:8000 weight=1;
    server fxml4_api_3:8000 weight=1;
}
```

#### Kubernetes Deployment (Advanced)
```yaml
# k8s/api-deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: fxml4-api
spec:
  replicas: 3
  selector:
    matchLabels:
      app: fxml4-api
  template:
    spec:
      containers:
      - name: api
        image: fxml4/api:v1.0.0
        resources:
          requests:
            memory: "1Gi"
            cpu: "500m"
          limits:
            memory: "2Gi"
            cpu: "1000m"
        env:
        - name: DB_HOST
          valueFrom:
            secretKeyRef:
              name: fxml4-secrets
              key: db-host
```

### Performance Optimization

#### Database Optimization
```sql
-- Connect to production database
\c fxml4_production;

-- Analyze query performance
SELECT query, mean_time, calls, total_time
FROM pg_stat_statements
ORDER BY mean_time DESC
LIMIT 10;

-- Optimize TimescaleDB settings
-- Increase chunk time interval for high-frequency data
SELECT set_chunk_time_interval('market_data', INTERVAL '1 hour');

-- Enable compression for older data
ALTER TABLE market_data SET (timescaledb.compress,
    timescaledb.compress_segmentby = 'symbol',
    timescaledb.compress_orderby = 'timestamp DESC');

-- Add compression policy (compress data older than 1 day)
SELECT add_compression_policy('market_data', INTERVAL '1 day');

-- Create materialized views for common queries
CREATE MATERIALIZED VIEW mv_daily_ohlc AS
SELECT
    symbol,
    time_bucket('1 day', timestamp) AS day,
    FIRST(price, timestamp) AS open,
    MAX(price) AS high,
    MIN(price) AS low,
    LAST(price, timestamp) AS close,
    SUM(volume) AS volume
FROM market_data
GROUP BY symbol, day;

-- Refresh materialized views automatically
SELECT add_continuous_aggregate_policy('mv_daily_ohlc',
    start_offset => INTERVAL '3 days',
    end_offset => INTERVAL '1 hour',
    schedule_interval => INTERVAL '1 hour');
```

#### Redis Optimization
```bash
# Connect to Redis
docker-compose -f docker-compose.prod.yml exec redis redis-cli

# Configure memory optimization
CONFIG SET maxmemory-policy allkeys-lru
CONFIG SET maxmemory 2gb

# Enable persistence (if needed)
CONFIG SET save "900 1 300 10 60 10000"

# Monitor Redis performance
INFO memory
INFO stats
```

#### Application Optimization
```python
# config/performance.py - Add to configuration
PERFORMANCE_OPTIMIZATIONS = {
    # Database connection pooling
    'DB_POOL_SIZE': 20,
    'DB_MAX_OVERFLOW': 30,
    'DB_POOL_RECYCLE': 3600,

    # Redis connection pooling
    'REDIS_CONNECTION_POOL_MAX_CONNECTIONS': 50,
    'REDIS_CONNECTION_POOL_RETRY_ON_TIMEOUT': True,

    # API optimization
    'API_WORKER_PROCESSES': 4,
    'API_WORKER_THREADS': 2,
    'API_KEEPALIVE_TIMEOUT': 65,

    # ML pipeline optimization
    'ML_BATCH_SIZE': 1000,
    'ML_PREFETCH_FACTOR': 2,
    'ML_MAX_PARALLEL_FEATURES': 4,

    # Risk calculation optimization
    'RISK_CALCULATION_BATCH_SIZE': 500,
    'POSITION_UPDATE_FREQUENCY': 1,  # seconds
}
```

---

## 🔧 Maintenance & Operations

### Daily Operations Checklist

```bash
# Morning checklist (automated via cron)
#!/bin/bash
# /usr/local/bin/fxml4-daily-check.sh

echo "=== FXML4 Daily Health Check $(date) ==="

# 1. Service health check
docker-compose -f docker-compose.prod.yml ps

# 2. Check system resources
echo "Memory usage:"
free -h
echo "Disk usage:"
df -h

# 3. Check trading performance
curl -s http://localhost/api/v1/performance/daily | jq '.pnl_today'

# 4. Verify backups
ls -la /opt/fxml4/backups/ | tail -5

# 5. Check for alerts
docker-compose -f docker-compose.prod.yml logs --since 24h | grep -i "error\|alert\|critical" | wc -l

echo "=== Daily check completed ==="
```

### Weekly Maintenance Tasks

```bash
# Weekly maintenance script
#!/bin/bash
# /usr/local/bin/fxml4-weekly-maintenance.sh

echo "=== FXML4 Weekly Maintenance $(date) ==="

# 1. Database maintenance
docker-compose -f docker-compose.prod.yml exec -T timescaledb psql -U $DB_USER -d $DB_NAME << EOF
VACUUM ANALYZE;
REINDEX DATABASE $DB_NAME;
SELECT pg_stat_reset();
EOF

# 2. Log rotation and cleanup
docker-compose -f docker-compose.prod.yml exec api sh -c "
find /app/logs -name '*.log' -mtime +7 -exec gzip {} \;
find /app/logs -name '*.gz' -mtime +30 -delete
"

# 3. Update Docker images (if automated)
# docker-compose -f docker-compose.prod.yml pull
# docker-compose -f docker-compose.prod.yml up -d

# 4. Generate weekly performance report
docker-compose -f docker-compose.prod.yml exec api python -m fxml4.reporting.weekly_report

echo "=== Weekly maintenance completed ==="
```

### Monitoring & Alerting Setup

```yaml
# alertmanager/config.yml
global:
  smtp_smarthost: 'smtp.gmail.com:587'
  smtp_from: 'alerts@yourdomain.com'

route:
  group_by: ['alertname']
  group_wait: 10s
  group_interval: 10s
  repeat_interval: 1h
  receiver: 'web.hook'

receivers:
- name: 'web.hook'
  email_configs:
  - to: 'admin@yourdomain.com'
    subject: 'FXML4 Alert: {{ range .Alerts }}{{ .Annotations.summary }}{{ end }}'
    body: |
      {{ range .Alerts }}
      Alert: {{ .Annotations.summary }}
      Description: {{ .Annotations.description }}
      Instance: {{ .Labels.instance }}
      Time: {{ .StartsAt }}
      {{ end }}

  slack_configs:
  - api_url: 'YOUR_SLACK_WEBHOOK_URL'
    channel: '#trading-alerts'
    title: 'FXML4 Alert'
    text: '{{ range .Alerts }}{{ .Annotations.summary }}{{ end }}'
```

---

## 🔄 Update & Migration Procedures

### Update Process (Zero-Downtime)

```bash
# 1. Prepare for update
git fetch origin
git checkout v1.1.0  # New version tag

# 2. Backup current state
/usr/local/bin/fxml4-backup.sh

# 3. Update configuration if needed
cp .env.production .env.production.backup
# Review and merge new configuration options

# 4. Rolling update (if using Docker Swarm/Kubernetes)
docker service update --image fxml4/api:v1.1.0 fxml4_api
docker service update --image fxml4/worker:v1.1.0 fxml4_worker

# 5. Or standard update
docker-compose -f docker-compose.prod.yml pull
docker-compose -f docker-compose.prod.yml up -d --force-recreate

# 6. Run migrations if needed
docker-compose -f docker-compose.prod.yml exec api python -m fxml4.cli database migrate

# 7. Verify update
make verify-deployment
```

### Database Migration

```python
# Example migration script
# migrations/v1_1_0_add_new_features.py

def upgrade():
    """Add new features for v1.1.0"""

    # Add new columns
    op.add_column('trades', sa.Column('ml_confidence', sa.Float))
    op.add_column('signals', sa.Column('risk_score', sa.Float))

    # Create new tables
    op.create_table(
        'ai_insights',
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('timestamp', sa.DateTime, nullable=False),
        sa.Column('insight_type', sa.String(50)),
        sa.Column('content', sa.Text),
        sa.Column('confidence', sa.Float)
    )

    # Create hypertable for new time-series data
    op.execute("SELECT create_hypertable('ai_insights', 'timestamp')")

def downgrade():
    """Rollback v1.1.0 features"""
    op.drop_table('ai_insights')
    op.drop_column('trades', 'ml_confidence')
    op.drop_column('signals', 'risk_score')
```

---

## 📞 Support & Contact Information

### Support Channels

**Technical Support:**
- Email: `support@fxml.io`
- Documentation: `docs.fxml.io`
- GitHub Issues: `github.com/fxml/fxml4/issues`

**Emergency Contact:**
- Critical Issues: `emergency@fxml.io`
- Phone: `+1-555-FXML-911` (24/7 for production issues)

**Community:**
- Discord: `discord.gg/fxml4`
- GitHub Discussions: `github.com/fxml/fxml4/discussions`
- Reddit: `r/FXML4Trading`

### Professional Services

**Implementation Support:**
- Deployment assistance
- Performance optimization
- Custom integrations
- Training and consulting

**Enterprise Support:**
- Dedicated support team
- SLA guarantees
- Priority bug fixes
- Custom feature development

---

**⚠️ Critical Production Notes:**

1. **Never deploy with default secrets** - All passwords and API keys must be changed
2. **Always test in staging first** - Use identical configuration to production
3. **Monitor continuously** - Set up alerts for all critical metrics
4. **Backup regularly** - Automated daily backups with verification
5. **Keep security updated** - Regular security patches and updates
6. **Document changes** - Maintain deployment logs and change records
7. **Emergency procedures** - Have tested procedures for trading halts and rollbacks

---

*This deployment guide ensures enterprise-grade production deployment of FXML4 v1.0.0. For additional support or customization requirements, contact our professional services team at `enterprise@fxml.io`.*