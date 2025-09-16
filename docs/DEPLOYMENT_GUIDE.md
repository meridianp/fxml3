# FXML4 Full-Stack Audit Fixes - Deployment Guide

## Overview

This guide covers deployment of the enterprise-grade reliability fixes implemented during the comprehensive full-stack audit. All changes are production-ready with 11/11 tests passing.

## Pre-Deployment Validation

### 1. Verify Test Suite Results
```bash
# Run comprehensive validation
cd /home/cnross/code/fxml4
python test_risk_metrics_endpoint.py
python test_race_condition_prevention.py
python test_message_replay_functionality.py
python test_account_endpoint.py

# Expected output: All tests should show "PASSED! 🎉"
```

### 2. Environment Setup
```bash
# Ensure environment variables are set
export FXML4_JWT_SECRET_KEY="your-production-secret"
export FXML4_DATABASE_URL="postgresql://user:pass@db:5432/fxml4"
export REDIS_URL="redis://redis:6379/0"
export RABBITMQ_URL="amqp://user:pass@rabbitmq:5672/"

# Verify environment
echo "Environment check:"
echo "JWT Secret: ${FXML4_JWT_SECRET_KEY:0:10}..."
echo "Database: ${FXML4_DATABASE_URL}"
```

## Deployment Steps

### Phase 1: Backend API Deployment

#### 1.1 Deploy Risk Management Router
```bash
# Verify the risk metrics endpoint exists
grep -n "get_risk_metrics" fxml4/api/routers/risk_management.py

# Expected: Should find the function at line ~413
```

#### 1.2 Deploy Trading Router
```bash
# Verify the account endpoint exists
grep -n "get_account_info" fxml4/api/routers/trading.py

# Expected: Should find the function at line ~97
```

#### 1.3 Deploy Trading Engine Service
```bash
# Verify the trading engine method exists
grep -n "def get_account_info" fxml4/api/services/trading_engine.py

# Expected: Should find the method at line ~725
```

### Phase 2: Frontend Deployment

#### 2.1 Deploy Enhanced Type Definitions
```bash
cd fxml4-ui

# Verify Order interface enhancements
grep -A5 "sequence_number" src/types/index.ts
grep -A5 "source.*api.*websocket" src/types/index.ts

# Expected: Should show the new optimistic locking fields
```

#### 2.2 Deploy Trading Store Updates
```bash
# Verify race condition prevention logic
grep -A10 "sequence_number.*updates.sequence_number" src/stores/useTradingStore.ts

# Expected: Should show conflict resolution logic
```

#### 2.3 Deploy WebSocket Service Updates
```bash
# Verify message queue infrastructure
grep -A5 "messageQueue.*QueuedMessage" src/services/websocket.ts
grep -A10 "requestMessageReplay" src/services/websocket.ts

# Expected: Should show queue and replay functionality
```

#### 2.4 Deploy Risk Dashboard Updates
```bash
# Verify API integration
grep -A10 "fetch.*risk.*metrics" src/components/trading/RiskDashboard.tsx

# Expected: Should show real API calls instead of mock data
```

### Phase 3: Service Restart and Validation

#### 3.1 Backend Services
```bash
# If using Docker Compose
docker-compose restart api
docker-compose logs -f api

# If using Kubernetes
kubectl rollout restart deployment/fxml4-api
kubectl rollout status deployment/fxml4-api
```

#### 3.2 Frontend Services
```bash
# If using Docker Compose
docker-compose restart frontend
docker-compose logs -f frontend

# If using Kubernetes
kubectl rollout restart deployment/fxml4-frontend
kubectl rollout status deployment/fxml4-frontend
```

#### 3.3 WebSocket Services
```bash
# Restart WebSocket service if separate
docker-compose restart websocket
# or
kubectl rollout restart deployment/fxml4-websocket
```

## Post-Deployment Validation

### 1. API Endpoint Health Checks
```bash
# Test risk metrics endpoint
curl -H "Authorization: Bearer $JWT_TOKEN" \
     http://localhost:8001/risk/metrics | jq '.portfolio_value'

# Expected: Should return numeric portfolio value

# Test account endpoint
curl -H "Authorization: Bearer $JWT_TOKEN" \
     http://localhost:8001/trading/account | jq '.balance,.equity'

# Expected: Should return both balance and equity fields
```

### 2. WebSocket Connection Test
```bash
# Test WebSocket connectivity
wscat -c ws://localhost:8001/socket.io/

# Send test message:
{"type": "subscribe", "channels": ["orders", "positions"]}

# Expected: Should receive connection confirmation
```

### 3. Frontend Integration Test
```bash
# Open browser to application
open http://localhost:3000

# Navigate to Risk Dashboard
# Expected: Should show real metrics, not "Loading..." or errors

# Navigate to Trading Console
# Expected: Should show account balance and equity
```

### 4. Race Condition Test
```bash
# Simulate concurrent order updates (for testing environments only)
# This requires your testing framework
python scripts/test_concurrent_orders.py

# Expected: No state corruption, all updates processed correctly
```

## Monitoring Setup

### 1. Key Metrics to Monitor
```bash
# Add these to your monitoring dashboard:

# API Performance
- /risk/metrics response time (target: <2s)
- /trading/account response time (target: <500ms)
- WebSocket connection count
- Message replay frequency

# Error Rates
- 4xx/5xx errors on new endpoints
- WebSocket disconnection rate
- Order sequence number gaps
```

### 2. Alert Configuration
```yaml
# Example Prometheus alerts
groups:
  - name: fxml4-audit-fixes
    rules:
      - alert: RiskMetricsHighLatency
        expr: histogram_quantile(0.95, http_request_duration_seconds_bucket{endpoint="/risk/metrics"}) > 2
        for: 2m

      - alert: HighMessageReplayRate
        expr: websocket_message_replays_per_hour > 10
        for: 5m

      - alert: OrderSequenceGaps
        expr: order_sequence_gaps_per_hour > 5
        for: 1m
```

## Rollback Procedures

### If Issues Are Detected

#### 1. Immediate Rollback
```bash
# Docker Compose
docker-compose down
git checkout HEAD~1  # Or specific commit before changes
docker-compose up -d

# Kubernetes
kubectl rollout undo deployment/fxml4-api
kubectl rollout undo deployment/fxml4-frontend
```

#### 2. Database Rollback
```bash
# If any database changes were made (none in this release)
# This is for future reference
docker exec -i timescaledb psql -U postgres -d fxml4 < db/rollbacks/version.sql
```

#### 3. Cache Clearing
```bash
# Clear Redis cache to prevent stale data issues
redis-cli FLUSHALL

# Clear browser cache instructions for users
echo "Users should hard refresh: Ctrl+Shift+R (Chrome/Firefox)"
```

## Verification Checklist

Post-deployment, verify these items:

### Backend Verification
- [ ] `/health` endpoint responds with 200 OK
- [ ] `/risk/metrics` returns 15 metrics with proper values
- [ ] `/trading/account` returns both balance and equity fields
- [ ] All endpoints require authentication (401 without token)
- [ ] WebSocket connections accept and process messages

### Frontend Verification
- [ ] Risk Dashboard loads without errors
- [ ] Risk Dashboard shows real data (not mock/loading states)
- [ ] Trading Console displays account information
- [ ] Order updates appear in real-time via WebSocket
- [ ] No console errors related to sequence numbers or message replay

### Integration Verification
- [ ] Frontend successfully calls new backend endpoints
- [ ] WebSocket message replay works after simulated disconnection
- [ ] Order state remains consistent under rapid updates
- [ ] Risk calculations match expected values
- [ ] All authentication flows work correctly

## Performance Validation

### Expected Response Times
```bash
# Measure response times
time curl -H "Authorization: Bearer $JWT_TOKEN" http://localhost:8001/risk/metrics
# Target: <2 seconds

time curl -H "Authorization: Bearer $JWT_TOKEN" http://localhost:8001/trading/account
# Target: <500ms

# WebSocket message latency
# Target: <100ms for order updates
```

### Load Testing (Optional)
```bash
# Simple load test for new endpoints
ab -n 100 -c 10 -H "Authorization: Bearer $JWT_TOKEN" \
   http://localhost:8001/risk/metrics

# Expected: No errors, response times within targets
```

## Troubleshooting

### Common Issues

#### "Risk metrics endpoint not found"
```bash
# Check if API server restarted properly
docker-compose logs api | grep "risk.*metrics"
# Should show endpoint registration

# Check file exists
ls -la fxml4/api/routers/risk_management.py
grep -n "get_risk_metrics" fxml4/api/routers/risk_management.py
```

#### "Account endpoint returns 500 error"
```bash
# Check TradingEngine service
docker-compose logs api | grep -i "trading.*engine"
# Look for initialization errors

# Verify method exists
grep -n "def get_account_info" fxml4/api/services/trading_engine.py
```

#### "WebSocket messages lost"
```bash
# Check WebSocket service logs
docker-compose logs websocket | grep -i "replay\|queue"

# Verify client-side queue
# Check browser console for WebSocket connection status
```

#### "Frontend shows old mock data"
```bash
# Clear browser cache completely
# Check Network tab in browser dev tools
# Verify API calls are being made to correct endpoints

# Check for old cached JavaScript
ls -la fxml4-ui/.next/static/
# May need to clear build cache
```

## Success Criteria

Deployment is successful when:

✅ All 4 audit fixes are deployed and functional
✅ No critical errors in logs for 30 minutes post-deployment
✅ Risk Dashboard shows real-time data
✅ Trading Console displays account information
✅ WebSocket connections stable with message replay working
✅ API response times within SLA targets
✅ No race conditions detected in order processing

---

**Contact**: Development Team Lead
**Escalation**: On-call Engineer
**Documentation**: See FULL_STACK_AUDIT_SOLUTIONS.md for technical details
