# FXML4 Operational Runbooks

## Table of Contents

1. [System Health](#system-health)
2. [Trading Operations](#trading-operations)
3. [Emergency Procedures](#emergency-procedures)
4. [Data Management](#data-management)
5. [Infrastructure Management](#infrastructure-management)
6. [Security Incidents](#security-incidents)
7. [Performance Issues](#performance-issues)
8. [Deployment Operations](#deployment-operations)

---

## System Health

### System Down

**Alert:** `SystemDown`
**Severity:** Critical
**Component:** All services

#### Immediate Actions (0-5 minutes)
1. **Verify the alert**
   ```bash
   kubectl get pods -n default
   kubectl get services -n default
   ```

2. **Check system status**
   ```bash
   # Check if API is responding
   curl -f https://api.fxml4.com/health || echo "API DOWN"

   # Check database connectivity
   kubectl exec -it deployment/fxml4-api -- python -c "
   from fxml4.data_engineering.timescaledb import TimescaleDBManager
   db = TimescaleDBManager()
   print('DB:', 'UP' if db.test_connection() else 'DOWN')
   "
   ```

3. **Check resource availability**
   ```bash
   kubectl top nodes
   kubectl top pods
   ```

#### Recovery Procedures
1. **If pods are failing:**
   ```bash
   # Check pod logs
   kubectl logs -f deployment/fxml4-api --tail=100

   # Check events
   kubectl get events --sort-by=.metadata.creationTimestamp

   # Restart if needed
   kubectl rollout restart deployment/fxml4-api
   ```

2. **If nodes are down:**
   ```bash
   # Check node status
   kubectl describe nodes

   # Drain and reschedule if needed
   kubectl drain <node-name> --ignore-daemonsets
   ```

3. **If database is down:**
   - See [Database Recovery](#database-recovery) section

#### Escalation
- **Immediate:** Page on-call engineer
- **15 minutes:** Notify CTO and Head of Trading
- **30 minutes:** Activate disaster recovery

---

### Database Down

**Alert:** `DatabaseDown`
**Severity:** Critical
**Component:** TimescaleDB

#### Immediate Actions
1. **Check database status**
   ```bash
   # Check if DB pods are running
   kubectl get pods -l app=timescaledb

   # Check DB logs
   kubectl logs -f deployment/timescaledb --tail=100
   ```

2. **Test connectivity**
   ```bash
   # Try to connect
   kubectl exec -it deployment/timescaledb -- psql -U postgres -d fxml4 -c "SELECT NOW();"
   ```

#### Recovery Procedures
1. **Database restart**
   ```bash
   kubectl rollout restart deployment/timescaledb

   # Wait for readiness
   kubectl rollout status deployment/timescaledb --timeout=300s
   ```

2. **Connection pool reset**
   ```bash
   # Reset application connection pools
   kubectl rollout restart deployment/fxml4-api
   kubectl rollout restart deployment/fxml4-data-collector
   ```

3. **Failover to replica (if configured)**
   ```bash
   # Promote read replica
   kubectl patch service timescaledb-primary -p '{"spec":{"selector":{"role":"replica"}}}'
   ```

#### Data Integrity Check
```bash
# Check for corruption
kubectl exec -it deployment/timescaledb -- psql -U postgres -d fxml4 -c "
SELECT schemaname, tablename, n_dead_tup, n_live_tup
FROM pg_stat_user_tables
WHERE n_dead_tup > 1000;
"

# Run vacuum if needed
kubectl exec -it deployment/timescaledb -- psql -U postgres -d fxml4 -c "VACUUM ANALYZE;"
```

---

## Trading Operations

### Trading Halted

**Alert:** `TradingHalted`
**Severity:** Critical
**Component:** Trading Engine

#### Immediate Actions
1. **Confirm halt status**
   ```bash
   # Check circuit breaker status
   kubectl exec -it deployment/fxml4-trading-engine -- python -c "
   from fxml4.trading.circuit_breaker import CircuitBreaker
   cb = CircuitBreaker()
   print('Status:', cb.get_status())
   print('Reason:', cb.get_trigger_reason())
   "
   ```

2. **Assess current positions**
   ```bash
   # Get current positions
   kubectl exec -it deployment/fxml4-trading-engine -- python -c "
   from fxml4.trading.position_manager import PositionManager
   pm = PositionManager()
   positions = pm.get_open_positions()
   print(f'Open positions: {len(positions)}')
   for pos in positions:
       print(f'{pos.symbol}: {pos.size} @ {pos.entry_price}')
   "
   ```

#### Investigation
1. **Check trigger reason**
   - Consecutive losses
   - High error rate
   - Excessive drawdown
   - Manual trigger

2. **Review recent trades**
   ```bash
   # Get recent trade history
   kubectl exec -it deployment/fxml4-api -- curl -s "http://localhost:8000/api/v1/trades/recent?limit=10"
   ```

3. **Check system metrics**
   - Navigate to Risk Monitoring dashboard
   - Review P&L and drawdown charts
   - Check error rates and latency

#### Recovery Decision Matrix

| Trigger Reason | Auto Recovery | Manual Review Required |
|----------------|---------------|------------------------|
| Consecutive Losses (3+) | ❌ | ✅ Head of Trading |
| High Error Rate (>10%) | ❌ | ✅ Tech Lead |
| Excessive Drawdown (>5%) | ❌ | ✅ Risk Manager |
| Manual Trigger | ❌ | ✅ Original Triggerer |

#### Recovery Procedure
1. **Address root cause**
2. **Get appropriate approval**
3. **Reset circuit breaker**
   ```bash
   kubectl exec -it deployment/fxml4-trading-engine -- python -c "
   from fxml4.trading.circuit_breaker import CircuitBreaker
   cb = CircuitBreaker()
   cb.reset(authorized_by='<approver-name>')
   print('Circuit breaker reset')
   "
   ```

---

### Excessive Drawdown

**Alert:** `ExcessiveDrawdown`
**Severity:** Critical
**Component:** Risk Management

#### Immediate Actions
1. **Verify drawdown calculation**
   ```bash
   # Get current P&L and drawdown
   kubectl exec -it deployment/fxml4-api -- curl -s "http://localhost:8000/api/v1/portfolio/status"
   ```

2. **Check position exposure**
   ```bash
   # Get total exposure
   kubectl exec -it deployment/fxml4-trading-engine -- python -c "
   from fxml4.trading.portfolio import Portfolio
   portfolio = Portfolio()
   print(f'Total exposure: ${portfolio.get_total_exposure():,.2f}')
   print(f'Current P&L: ${portfolio.get_total_pnl():,.2f}')
   print(f'Drawdown: {portfolio.get_current_drawdown():.2f}%')
   "
   ```

#### Risk Assessment
1. **Analyze contributing factors**
   - Market volatility
   - Position concentration
   - Model performance
   - Execution issues

2. **Check correlations**
   ```bash
   # Get position correlations
   kubectl exec -it deployment/fxml4-api -- curl -s "http://localhost:8000/api/v1/risk/correlations"
   ```

#### Mitigation Options
1. **Reduce position sizes**
   ```bash
   # Scale down all positions by 50%
   kubectl exec -it deployment/fxml4-trading-engine -- python -c "
   from fxml4.trading.position_manager import PositionManager
   pm = PositionManager()
   pm.scale_all_positions(0.5, reason='drawdown_mitigation')
   "
   ```

2. **Close high-risk positions**
   ```bash
   # Close positions with high volatility
   kubectl exec -it deployment/fxml4-trading-engine -- python -c "
   from fxml4.trading.risk_manager import RiskManager
   rm = RiskManager()
   rm.close_high_risk_positions(volatility_threshold=0.02)
   "
   ```

3. **Pause new signal generation**
   ```bash
   kubectl patch configmap trading-config -p '{"data":{"signal_generation_enabled":"false"}}'
   kubectl rollout restart deployment/fxml4-trading-engine
   ```

---

## Emergency Procedures

### Emergency Trading Halt

**When to Use:** Immediate halt required due to:
- Market manipulation suspicion
- System compromise
- Regulatory requirement
- Extreme market conditions

#### Immediate Actions (30 seconds)
```bash
# Emergency stop all trading
kubectl exec -it deployment/fxml4-trading-engine -- python -c "
from fxml4.trading.emergency import EmergencyStop
emergency = EmergencyStop()
emergency.halt_all_trading(reason='EMERGENCY_HALT', operator='<your-name>')
print('Emergency halt activated')
"
```

#### Position Management
1. **Assess positions**
   ```bash
   # Get all open positions
   kubectl exec -it deployment/fxml4-api -- curl -s "http://localhost:8000/api/v1/positions/open"
   ```

2. **Close positions if required**
   ```bash
   # Close all positions (use with extreme caution)
   kubectl exec -it deployment/fxml4-trading-engine -- python -c "
   from fxml4.trading.emergency import EmergencyStop
   emergency = EmergencyStop()
   emergency.close_all_positions(reason='EMERGENCY_CLOSURE', operator='<your-name>')
   "
   ```

#### Communication
1. **Notify stakeholders immediately**
   - CTO
   - Head of Trading
   - Risk Manager
   - Compliance Officer

2. **Document incident**
   - Time of halt
   - Reason for halt
   - Actions taken
   - Positions affected

---

### Disaster Recovery

**Triggers:**
- Complete data center failure
- Database corruption
- Kubernetes cluster failure
- Network isolation

#### Recovery Steps
1. **Activate DR site**
   ```bash
   # Switch to DR cluster
   kubectl config use-context fxml4-dr

   # Verify DR services
   kubectl get pods -A
   ```

2. **Restore data**
   ```bash
   # Restore from latest backup
   kubectl apply -f deployment/dr/restore-job.yaml

   # Monitor restore progress
   kubectl logs -f job/database-restore
   ```

3. **Validate system**
   ```bash
   # Run health checks
   kubectl apply -f deployment/dr/health-check-job.yaml

   # Verify trading capabilities
   kubectl exec -it deployment/fxml4-api -- python scripts/validate_system.py
   ```

4. **Update DNS**
   ```bash
   # Point traffic to DR site
   # This would be done through your DNS provider
   ```

#### RTO/RPO Targets
- **Recovery Time Objective (RTO):** 15 minutes
- **Recovery Point Objective (RPO):** 5 minutes

---

## Data Management

### Stale Data

**Alert:** `StaleData`
**Severity:** High
**Component:** Data Feed

#### Investigation
1. **Check data feed status**
   ```bash
   # Check all data sources
   kubectl exec -it deployment/fxml4-data-collector -- python -c "
   from fxml4.data_feeds.manager import DataFeedManager
   manager = DataFeedManager()
   for source in manager.get_sources():
       status = manager.get_source_status(source)
       print(f'{source}: {status}')
   "
   ```

2. **Check last update times**
   ```bash
   # Query last tick timestamp
   kubectl exec -it deployment/timescaledb -- psql -U postgres -d fxml4 -c "
   SELECT symbol, MAX(timestamp) as last_update,
          EXTRACT(EPOCH FROM NOW() - MAX(timestamp)) as seconds_ago
   FROM ticks
   GROUP BY symbol
   ORDER BY seconds_ago DESC;
   "
   ```

#### Recovery Actions
1. **Restart data collector**
   ```bash
   kubectl rollout restart deployment/fxml4-data-collector
   ```

2. **Switch to backup feed**
   ```bash
   kubectl patch configmap data-feed-config -p '{"data":{"primary_source":"backup"}}'
   ```

3. **Backfill missing data**
   ```bash
   kubectl create job data-backfill-$(date +%s) --from=cronjob/data-backfill
   ```

---

## Infrastructure Management

### High CPU Usage

**Alert:** `HighCPUUsage`
**Severity:** Medium
**Component:** Infrastructure

#### Investigation
1. **Identify high CPU pods**
   ```bash
   kubectl top pods --sort-by=cpu
   ```

2. **Check resource limits**
   ```bash
   kubectl describe pod <pod-name> | grep -A 5 "Limits:"
   ```

3. **Analyze CPU usage patterns**
   ```bash
   # Check CPU usage over time in Grafana
   # Look for spikes or gradual increases
   ```

#### Mitigation
1. **Scale horizontally**
   ```bash
   kubectl scale deployment fxml4-api --replicas=5
   ```

2. **Increase resource limits**
   ```bash
   kubectl patch deployment fxml4-api -p '
   {
     "spec": {
       "template": {
         "spec": {
           "containers": [{
             "name": "api",
             "resources": {
               "limits": {"cpu": "2000m"}
             }
           }]
         }
       }
     }
   }'
   ```

---

### High Memory Usage

**Alert:** `HighMemoryUsage`
**Severity:** Medium
**Component:** Infrastructure

#### Investigation
1. **Check memory usage**
   ```bash
   kubectl top pods --sort-by=memory
   ```

2. **Check for memory leaks**
   ```bash
   # Get memory usage over time from Grafana
   # Look for steadily increasing memory
   ```

#### Actions
1. **Restart affected pods**
   ```bash
   kubectl delete pod <pod-name>
   ```

2. **Increase memory limits**
   ```bash
   kubectl patch deployment fxml4-api -p '
   {
     "spec": {
       "template": {
         "spec": {
           "containers": [{
             "name": "api",
             "resources": {
               "limits": {"memory": "4Gi"}
             }
           }]
         }
       }
     }
   }'
   ```

---

## Security Incidents

### Unauthorized Access

**Alert:** `UnauthorizedAccess`
**Severity:** High
**Component:** Authentication

#### Immediate Actions
1. **Block suspicious IPs**
   ```bash
   # Add IP to firewall rules
   kubectl patch networkpolicy api-ingress -p '
   {
     "spec": {
       "podSelector": {},
       "policyTypes": ["Ingress"],
       "ingress": [{
         "from": [{
           "ipBlock": {
             "cidr": "0.0.0.0/0",
             "except": ["<suspicious-ip>/32"]
           }
         }]
       }]
     }
   }'
   ```

2. **Review access logs**
   ```bash
   # Check recent access attempts
   kubectl logs deployment/fxml4-api | grep "401\|403" | tail -20
   ```

3. **Validate session tokens**
   ```bash
   # Invalidate all active sessions if needed
   kubectl exec -it deployment/fxml4-api -- python -c "
   from fxml4.auth.session_manager import SessionManager
   sm = SessionManager()
   sm.invalidate_all_sessions()
   print('All sessions invalidated')
   "
   ```

#### Investigation
1. **Analyze attack patterns**
2. **Check for privilege escalation**
3. **Review user accounts**
4. **Audit configuration changes**

---

## Performance Issues

### High Latency

**Alert:** `HighLatency`
**Severity:** High
**Component:** API

#### Investigation
1. **Identify slow endpoints**
   ```bash
   # Check endpoint latencies in Grafana
   # Look at P99 latency by endpoint
   ```

2. **Check database performance**
   ```bash
   kubectl exec -it deployment/timescaledb -- psql -U postgres -d fxml4 -c "
   SELECT query, mean_time, calls
   FROM pg_stat_statements
   ORDER BY mean_time DESC
   LIMIT 10;
   "
   ```

3. **Review application logs**
   ```bash
   kubectl logs deployment/fxml4-api | grep -i "slow\|timeout\|error"
   ```

#### Optimization
1. **Database optimization**
   ```bash
   # Analyze and vacuum
   kubectl exec -it deployment/timescaledb -- psql -U postgres -d fxml4 -c "
   ANALYZE;
   VACUUM ANALYZE;
   "
   ```

2. **Application scaling**
   ```bash
   kubectl scale deployment fxml4-api --replicas=5
   ```

3. **Connection pool tuning**
   ```bash
   kubectl patch configmap db-config -p '{"data":{"max_connections":"20"}}'
   ```

---

## Deployment Operations

### Deployment Rollback

**When:** Deployment issues detected after release

#### Quick Rollback
```bash
# Rollback to previous version
kubectl rollout undo deployment/fxml4-api

# Check rollback status
kubectl rollout status deployment/fxml4-api
```

#### Targeted Rollback
```bash
# Rollback to specific revision
kubectl rollout history deployment/fxml4-api
kubectl rollout undo deployment/fxml4-api --to-revision=3
```

#### Validation
```bash
# Run smoke tests
python tests/smoke/smoke_tests.py --endpoint https://api.fxml4.com

# Check system health
kubectl get pods
curl https://api.fxml4.com/health
```

---

### Blue-Green Deployment Switch

#### Pre-switch Validation
```bash
# Validate green environment
curl -f https://green.api.fxml4.com/health
python tests/smoke/smoke_tests.py --endpoint https://green.api.fxml4.com
```

#### Traffic Switch
```bash
# Update ingress to green
kubectl patch ingress fxml4-ingress -p '
{
  "spec": {
    "rules": [{
      "http": {
        "paths": [{
          "backend": {
            "serviceName": "fxml4-api-green",
            "servicePort": 80
          }
        }]
      }
    }]
  }
}'
```

#### Monitoring
```bash
# Monitor error rates during switch
# Watch key metrics in Grafana
# Prepare for quick rollback if needed
```

---

## Escalation Procedures

### Severity Levels

| Severity | Response Time | Escalation |
|----------|---------------|------------|
| Critical | 5 minutes | Immediate page + CTO notification |
| High | 30 minutes | Page on-call + team notification |
| Medium | 4 hours | Business hours notification |
| Low | Next business day | Ticket creation |

### Contact Information

| Role | Primary | Secondary |
|------|---------|-----------|
| On-call Engineer | PagerDuty | Slack #ops-alerts |
| Tech Lead | email@company.com | +1-555-0001 |
| CTO | cto@company.com | +1-555-0002 |
| Head of Trading | trading@company.com | +1-555-0003 |
| Risk Manager | risk@company.com | +1-555-0004 |

### Communication Channels

- **Slack:** #fxml4-alerts, #trading-team, #ops-team
- **Email:** ops@company.com, trading@company.com
- **PagerDuty:** Critical alerts only
- **Phone:** Emergency escalation only

---

## Documentation and Updates

This runbook should be:
- Reviewed monthly
- Updated after each incident
- Tested during disaster recovery drills
- Accessible to all team members

Last updated: [DATE]
Next review: [DATE + 1 month]
