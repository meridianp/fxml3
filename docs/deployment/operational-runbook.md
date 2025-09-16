# FXML4 Operational Runbook

This runbook provides step-by-step procedures for operating and maintaining the FXML4 trading platform in production.

## Table of Contents

1. [System Overview](#system-overview)
2. [Daily Operations](#daily-operations)
3. [Monitoring and Alerting](#monitoring-and-alerting)
4. [Backup and Recovery](#backup-and-recovery)
5. [Performance Tuning](#performance-tuning)
6. [Incident Response](#incident-response)
7. [Maintenance Procedures](#maintenance-procedures)
8. [Emergency Procedures](#emergency-procedures)

## System Overview

### Architecture Components

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Load Balancer │────│   API Gateway   │────│   FXML4 API     │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                                                        │
                       ┌─────────────────┐              │
                       │   Background    │──────────────┘
                       │   Worker        │
                       └─────────────────┘
                                │
    ┌─────────────────┐        │        ┌─────────────────┐
    │   PostgreSQL    │────────┼────────│   TimescaleDB   │
    │   (Metadata)    │        │        │   (Time Series) │
    └─────────────────┘        │        └─────────────────┘
                               │
                       ┌─────────────────┐
                       │     Redis       │
                       │   (Caching)     │
                       └─────────────────┘
```

### Service Dependencies

- **API Service**: Depends on PostgreSQL, TimescaleDB, Redis
- **Worker Service**: Depends on PostgreSQL, TimescaleDB, External APIs
- **Dashboard**: Depends on API Service
- **External APIs**: Alpha Vantage, OpenAI, Google Cloud Vertex AI

## Daily Operations

### Morning Checklist (9:00 AM UTC)

1. **System Health Check**
   ```bash
   # Check all services are running
   kubectl get pods -n fxml4-prod

   # Verify API health
   curl https://api.fxml4.com/health

   # Check dashboard accessibility
   curl https://dashboard.fxml4.com
   ```

2. **Database Health**
   ```bash
   # Check database connections
   kubectl exec -it postgres-0 -n fxml4-prod -- \
     psql -U postgres -c "SELECT count(*) FROM pg_stat_activity;"

   # Check TimescaleDB chunks
   kubectl exec -it timescaledb-0 -n fxml4-prod -- \
     psql -U postgres -d fxml4 -c "SELECT chunk_name, range_start, range_end FROM timescaledb_information.chunks WHERE hypertable_name = 'market_data' ORDER BY range_start DESC LIMIT 10;"
   ```

3. **Performance Metrics Review**
   ```bash
   # Check resource utilization
   kubectl top nodes
   kubectl top pods -n fxml4-prod

   # Review application metrics
   curl https://api.fxml4.com/metrics | grep -E "(request_duration|error_rate)"
   ```

4. **Log Review**
   ```bash
   # Check for errors in the last 24 hours
   kubectl logs --since=24h -l app=fxml4-api -n fxml4-prod | grep -i error

   # Check worker logs
   kubectl logs --since=24h -l app=fxml4-worker -n fxml4-prod | grep -i error
   ```

### Evening Checklist (6:00 PM UTC)

1. **Daily Backup Verification**
   ```bash
   # Check backup completion
   kubectl logs -l app=backup-job -n fxml4-prod --since=24h

   # Verify backup files
   gsutil ls gs://fxml4-backups/$(date +%Y/%m/%d)/
   ```

2. **Data Pipeline Health**
   ```bash
   # Check latest data ingestion
   psql -h timescaledb.fxml4.com -U readonly -d fxml4 -c \
     "SELECT symbol, max(timestamp) as latest_data FROM market_data GROUP BY symbol ORDER BY symbol;"
   ```

3. **External API Quotas**
   ```bash
   # Check Alpha Vantage usage
   curl "https://www.alphavantage.co/query?function=TIME_SERIES_INTRADAY&symbol=IBM&interval=1min&apikey=$ALPHA_VANTAGE_API_KEY" | \
     grep -o '"Information":[^}]*' | grep -o 'call frequency\|per minute'
   ```

### Weekly Operations (Monday 10:00 AM UTC)

1. **Security Updates**
   ```bash
   # Check for security updates
   kubectl get nodes -o json | jq '.items[].status.nodeInfo.kubeletVersion'

   # Review security scan results
   trivy image fxml4:latest
   ```

2. **Performance Analysis**
   ```bash
   # Generate weekly performance report
   python scripts/generate_weekly_report.py --start-date=$(date -d "7 days ago" +%Y-%m-%d)
   ```

3. **Cleanup Operations**
   ```bash
   # Clean old backup files (older than 30 days)
   gsutil -m rm -r gs://fxml4-backups/$(date -d "30 days ago" +%Y/%m/%d)/

   # Clean old application logs
   kubectl delete pods -l app=log-retention -n fxml4-prod
   ```

## Monitoring and Alerting

### Key Metrics to Monitor

1. **Application Metrics**
   - API response times (95th percentile < 500ms)
   - Error rates (< 1% for 5xx errors)
   - Request throughput
   - Authentication success rate

2. **Infrastructure Metrics**
   - CPU utilization (< 80%)
   - Memory utilization (< 85%)
   - Disk space (< 90%)
   - Network I/O

3. **Business Metrics**
   - Data ingestion rates
   - Backtest completion rates
   - Signal generation latency
   - User activity levels

### Alert Configuration

```yaml
# prometheus-alerts.yaml
groups:
  - name: fxml4-critical
    rules:
      - alert: APIDown
        expr: up{job="fxml4-api"} == 0
        for: 1m
        labels:
          severity: critical
        annotations:
          summary: "FXML4 API is down"
          description: "API has been down for more than 1 minute"

      - alert: HighErrorRate
        expr: rate(http_requests_total{status=~"5.."}[5m]) > 0.05
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "High error rate detected"

      - alert: DatabaseConnectionsHigh
        expr: pg_stat_activity_count / pg_settings_max_connections > 0.8
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "Database connection usage is high"
```

### Alert Response Procedures

#### Critical Alerts (Immediate Response Required)

1. **API Down**
   - Check pod status: `kubectl get pods -n fxml4-prod`
   - Check logs: `kubectl logs -l app=fxml4-api -n fxml4-prod --tail=100`
   - Restart if necessary: `kubectl rollout restart deployment/fxml4-api -n fxml4-prod`

2. **Database Down**
   - Check database status: `kubectl get pods -l app=postgres -n fxml4-prod`
   - Check disk space: `kubectl exec -it postgres-0 -n fxml4-prod -- df -h`
   - Escalate to DBA if persistent

#### Warning Alerts (Response within 30 minutes)

1. **High Error Rate**
   - Investigate logs for error patterns
   - Check external API availability
   - Monitor for auto-recovery

2. **Resource Usage High**
   - Check specific resource consumption
   - Scale deployment if needed
   - Plan capacity expansion

## Backup and Recovery

### Backup Schedule

- **Database**: Daily at 2:00 AM UTC
- **Configuration**: Daily at 2:30 AM UTC
- **Application Data**: Weekly on Sunday at 3:00 AM UTC
- **Logs**: Continuous to centralized logging

### Backup Procedures

1. **Database Backup**
   ```bash
   # Create PostgreSQL backup
   kubectl exec postgres-0 -n fxml4-prod -- \
     pg_dump -U postgres fxml4 | \
     gzip > fxml4_backup_$(date +%Y%m%d_%H%M%S).sql.gz

   # Upload to cloud storage
   gsutil cp fxml4_backup_*.sql.gz gs://fxml4-backups/$(date +%Y/%m/%d)/
   ```

2. **TimescaleDB Backup**
   ```bash
   # Backup TimescaleDB with compression
   kubectl exec timescaledb-0 -n fxml4-prod -- \
     pg_dump -U postgres -Fc fxml4 > timescaledb_backup_$(date +%Y%m%d_%H%M%S).dump

   # Upload to cloud storage
   gsutil cp timescaledb_backup_*.dump gs://ftml4-timescale-backups/$(date +%Y/%m/%d)/
   ```

### Recovery Procedures

1. **Database Recovery**
   ```bash
   # Stop application to prevent writes
   kubectl scale deployment fxml4-api --replicas=0 -n fxml4-prod

   # Download backup
   gsutil cp gs://fxml4-backups/2023/12/01/fxml4_backup_20231201_020000.sql.gz .

   # Restore database
   gunzip fxml4_backup_20231201_020000.sql.gz
   kubectl exec -i postgres-0 -n fxml4-prod -- \
     psql -U postgres fxml4 < fxml4_backup_20231201_020000.sql

   # Restart application
   kubectl scale deployment fxml4-api --replicas=3 -n fxml4-prod
   ```

2. **Point-in-Time Recovery**
   ```bash
   # Enable point-in-time recovery
   kubectl exec postgres-0 -n fxml4-prod -- \
     psql -U postgres -c "SELECT pg_start_backup('recovery_point');"

   # Restore to specific timestamp
   kubectl exec postgres-0 -n fxml4-prod -- \
     pg_pitr_restore --target-time="2023-12-01 14:30:00"
   ```

## Performance Tuning

### Database Optimization

1. **Query Performance**
   ```sql
   -- Identify slow queries
   SELECT query, mean_time, calls, total_time
   FROM pg_stat_statements
   ORDER BY mean_time DESC
   LIMIT 10;

   -- Check index usage
   SELECT schemaname, tablename, attname, n_distinct, correlation
   FROM pg_stats
   WHERE tablename = 'market_data';
   ```

2. **Connection Pooling**
   ```yaml
   # pgbouncer configuration
   database:
     pool_mode: transaction
     max_client_conn: 100
     default_pool_size: 20
     reserve_pool_size: 5
   ```

### Application Optimization

1. **Memory Tuning**
   ```yaml
   # Kubernetes resource limits
   resources:
     requests:
       memory: "2Gi"
       cpu: "1000m"
     limits:
       memory: "4Gi"
       cpu: "2000m"
   ```

2. **Caching Strategy**
   ```python
   # Redis cache configuration
   CACHE_CONFIG = {
       'market_data': {'ttl': 300},  # 5 minutes
       'signals': {'ttl': 60},       # 1 minute
       'user_sessions': {'ttl': 3600}  # 1 hour
   }
   ```

## Incident Response

### Incident Classification

1. **Critical (P1)**: Complete service outage
2. **High (P2)**: Major functionality impaired
3. **Medium (P3)**: Minor functionality affected
4. **Low (P4)**: Cosmetic issues

### Response Timeline

- **P1**: Immediate response, 15-minute updates
- **P2**: 30-minute response, hourly updates
- **P3**: 4-hour response, daily updates
- **P4**: Next business day response

### Incident Response Playbook

1. **Initial Response**
   - Acknowledge incident
   - Assess impact and severity
   - Begin investigation
   - Notify stakeholders

2. **Investigation**
   - Gather relevant logs and metrics
   - Identify root cause
   - Implement temporary fix if needed
   - Document findings

3. **Resolution**
   - Implement permanent fix
   - Verify resolution
   - Update monitoring if needed
   - Conduct post-incident review

### Common Incident Scenarios

#### Scenario 1: Database Connection Exhaustion

**Symptoms**: API returns 500 errors, "connection pool exhausted" in logs

**Investigation Steps**:
```bash
# Check active connections
kubectl exec postgres-0 -n fxml4-prod -- \
  psql -U postgres -c "SELECT count(*) FROM pg_stat_activity;"

# Check connection pool status
kubectl logs -l app=fxml4-api -n fxml4-prod | grep "connection pool"
```

**Resolution**:
```bash
# Increase connection pool size
kubectl patch deployment fxml4-api -n fxml4-prod -p \
  '{"spec":{"template":{"spec":{"containers":[{"name":"api","env":[{"name":"DB_POOL_SIZE","value":"30"}]}]}}}}'

# Restart deployment
kubectl rollout restart deployment/fxml4-api -n fxml4-prod
```

#### Scenario 2: External API Rate Limiting

**Symptoms**: Alpha Vantage errors, empty data responses

**Investigation Steps**:
```bash
# Check Alpha Vantage response
curl "https://www.alphavantage.co/query?function=TIME_SERIES_INTRADAY&symbol=IBM&interval=1min&apikey=$API_KEY"

# Check application logs for rate limit errors
kubectl logs -l app=fxml4-worker -n fxml4-prod | grep -i "rate limit"
```

**Resolution**:
```bash
# Implement exponential backoff
kubectl patch configmap worker-config -n fxml4-prod --patch \
  '{"data":{"RATE_LIMIT_BACKOFF":"true","BACKOFF_MULTIPLIER":"2"}}'

# Restart worker
kubectl rollout restart deployment/fxml4-worker -n fxml4-prod
```

## Maintenance Procedures

### Planned Maintenance Windows

- **Weekly**: Sunday 2:00-4:00 AM UTC (minor updates)
- **Monthly**: First Sunday 1:00-5:00 AM UTC (major updates)
- **Quarterly**: Security patches and major upgrades

### Pre-Maintenance Checklist

1. **Notification**
   - Notify users 48 hours in advance
   - Update status page
   - Schedule maintenance window

2. **Preparation**
   - Test deployment in staging
   - Prepare rollback plan
   - Verify backup availability

3. **Execution**
   - Follow deployment procedures
   - Monitor during deployment
   - Verify functionality post-deployment

### Post-Maintenance Verification

```bash
# Health check script
#!/bin/bash
echo "Starting post-maintenance verification..."

# API health
API_STATUS=$(curl -s https://api.fxml4.com/health | jq -r '.status')
echo "API Status: $API_STATUS"

# Database connectivity
DB_STATUS=$(kubectl exec postgres-0 -n fxml4-prod -- psql -U postgres -c "SELECT 1" 2>/dev/null && echo "OK" || echo "FAIL")
echo "Database Status: $DB_STATUS"

# Sample data retrieval
DATA_STATUS=$(curl -s -X POST https://api.fxml4.com/data -H "Authorization: Bearer $TOKEN" -d '{"symbol":"EURUSD","timeframe":"1h"}' | jq -r '.count')
echo "Data Retrieval: $DATA_STATUS records"

# Performance test
RESPONSE_TIME=$(curl -w "%{time_total}" -s -o /dev/null https://api.fxml4.com/health)
echo "Response Time: ${RESPONSE_TIME}s"

echo "Post-maintenance verification complete"
```

## Emergency Procedures

### Service Degradation Response

1. **Immediate Actions**
   - Scale up replicas: `kubectl scale deployment fxml4-api --replicas=6 -n fxml4-prod`
   - Enable circuit breakers
   - Activate caching layer

2. **Communication**
   - Update status page
   - Notify operations team
   - Prepare customer communication

### Data Loss Response

1. **Assessment**
   - Determine scope of data loss
   - Identify last known good backup
   - Estimate recovery time

2. **Recovery**
   - Stop all write operations
   - Restore from latest backup
   - Replay transaction logs if available
   - Verify data integrity

### Security Incident Response

1. **Immediate Containment**
   - Isolate affected systems
   - Change all passwords and API keys
   - Review access logs

2. **Investigation**
   - Preserve evidence
   - Determine attack vector
   - Assess data exposure

3. **Recovery**
   - Apply security patches
   - Update security policies
   - Conduct security audit

## Contact Information

### On-Call Rotation

- **Primary**: ops-primary@fxml4.com
- **Secondary**: ops-secondary@fxml4.com
- **Escalation**: engineering-lead@fxml4.com

### External Vendors

- **Google Cloud Support**: [Support Console](https://cloud.google.com/support)
- **Alpha Vantage Support**: support@alphavantage.co
- **Database Vendor**: support@timescale.com

### Emergency Escalation

1. **Business Hours**: Slack #fxml4-ops
2. **After Hours**: PagerDuty escalation
3. **Critical Issues**: Direct phone to engineering lead

---

*This runbook should be reviewed and updated quarterly. Last updated: [Current Date]*
