# FXML4 Troubleshooting Guide

This comprehensive guide covers common issues, diagnostic procedures, and solutions for the FXML4 trading platform.

## Table of Contents

1. [Quick Diagnostic Steps](#quick-diagnostic-steps)
2. [API Issues](#api-issues)
3. [Database Problems](#database-problems)
4. [Authentication Issues](#authentication-issues)
5. [Data Feed Problems](#data-feed-problems)
6. [Backtesting Issues](#backtesting-issues)
7. [Performance Problems](#performance-problems)
8. [Deployment Issues](#deployment-issues)
9. [External Service Issues](#external-service-issues)
10. [Log Analysis](#log-analysis)

## Quick Diagnostic Steps

### System Health Check

```bash
# 1. Check all services are running
kubectl get pods -n fxml4-prod
docker-compose ps  # For docker-compose deployments

# 2. Verify API accessibility
curl -f https://api.fxml4.com/health || echo "API health check failed"

# 3. Check database connectivity
kubectl exec -it postgres-0 -n fxml4-prod -- psql -U postgres -c "SELECT 1" 2>/dev/null && echo "DB OK" || echo "DB FAIL"

# 4. Verify external API access
curl -s "https://www.alphavantage.co/query?function=TIME_SERIES_INTRADAY&symbol=IBM&interval=1min&apikey=$ALPHA_VANTAGE_API_KEY" | jq '.["Meta Data"]' && echo "Alpha Vantage OK" || echo "Alpha Vantage FAIL"

# 5. Check recent errors
kubectl logs --since=1h -l app=fxml4-api -n fxml4-prod | grep -i error | tail -10
```

### Quick Status Dashboard

```bash
#!/bin/bash
# quick-status.sh
echo "=== FXML4 System Status ==="
echo "Timestamp: $(date)"
echo

# Service status
echo "--- Service Status ---"
kubectl get pods -n fxml4-prod --no-headers | awk '{print $1 ": " $3}'

# Resource usage
echo -e "\n--- Resource Usage ---"
kubectl top pods -n fxml4-prod --no-headers | head -5

# API response time
echo -e "\n--- API Performance ---"
RESPONSE_TIME=$(curl -w "%{time_total}" -s -o /dev/null https://api.fxml4.com/health)
echo "Health endpoint: ${RESPONSE_TIME}s"

# Database connections
echo -e "\n--- Database ---"
DB_CONNECTIONS=$(kubectl exec postgres-0 -n fxml4-prod -- psql -U postgres -t -c "SELECT count(*) FROM pg_stat_activity;")
echo "Active connections: $DB_CONNECTIONS"

# Recent errors
echo -e "\n--- Recent Errors (last hour) ---"
ERROR_COUNT=$(kubectl logs --since=1h -l app=fxml4-api -n fxml4-prod | grep -c -i error)
echo "Error count: $ERROR_COUNT"
```

## API Issues

### Problem: API Returns 500 Internal Server Error

**Symptoms:**
- Clients receive HTTP 500 responses
- API health check fails
- Error messages in application logs

**Diagnostic Steps:**

1. **Check application logs:**
   ```bash
   kubectl logs -l app=fxml4-api -n fxml4-prod --tail=100
   ```

2. **Verify database connectivity:**
   ```bash
   kubectl exec -it deployment/fxml4-api -n fxml4-prod -- \
     python -c "from fxml4.config import get_db_connection; print(get_db_connection().execute('SELECT 1').fetchone())"
   ```

3. **Check resource limits:**
   ```bash
   kubectl describe pod -l app=fxml4-api -n fxml4-prod | grep -A 5 -B 5 "Limits\|Requests"
   ```

**Common Solutions:**

1. **Database connection pool exhausted:**
   ```bash
   # Increase pool size
   kubectl patch deployment fxml4-api -n fxml4-prod -p \
     '{"spec":{"template":{"spec":{"containers":[{"name":"api","env":[{"name":"DB_POOL_SIZE","value":"30"}]}]}}}}'
   ```

2. **Memory limit reached:**
   ```bash
   # Increase memory limit
   kubectl patch deployment fxml4-api -n fxml4-prod -p \
     '{"spec":{"template":{"spec":{"containers":[{"name":"api","resources":{"limits":{"memory":"4Gi"}}}]}}}}'
   ```

3. **Application restart:**
   ```bash
   kubectl rollout restart deployment/fxml4-api -n fxml4-prod
   ```

### Problem: API Response Times Are Slow

**Symptoms:**
- High response times (>2 seconds)
- Timeout errors
- Poor user experience

**Diagnostic Steps:**

1. **Measure response times:**
   ```bash
   # Test various endpoints
   curl -w "@curl-format.txt" -s -o /dev/null https://api.fxml4.com/health
   curl -w "@curl-format.txt" -s -o /dev/null https://api.fxml4.com/data -X POST -H "Content-Type: application/json" -d '{"symbol":"EURUSD","timeframe":"1h"}'
   ```

2. **Check database query performance:**
   ```sql
   -- Check slow queries
   SELECT query, mean_time, calls
   FROM pg_stat_statements
   WHERE mean_time > 1000
   ORDER BY mean_time DESC;
   ```

3. **Analyze application metrics:**
   ```bash
   curl https://api.fxml4.com/metrics | grep -E "(request_duration|db_query_duration)"
   ```

**Solutions:**

1. **Add database indexes:**
   ```sql
   -- Example: Add index for common queries
   CREATE INDEX CONCURRENTLY idx_market_data_symbol_timestamp
   ON market_data (symbol, timestamp DESC);
   ```

2. **Enable caching:**
   ```python
   # Add Redis caching for frequently accessed data
   @cache.memoize(timeout=300)
   def get_market_data(symbol, timeframe):
       # Implementation
   ```

3. **Scale API instances:**
   ```bash
   kubectl scale deployment fxml4-api --replicas=5 -n fxml4-prod
   ```

### Problem: API Rate Limiting Issues

**Symptoms:**
- HTTP 429 responses
- "Rate limit exceeded" errors
- Legitimate requests being blocked

**Diagnostic Steps:**

1. **Check rate limiter configuration:**
   ```bash
   kubectl get configmap rate-limiter-config -n fxml4-prod -o yaml
   ```

2. **Analyze request patterns:**
   ```bash
   kubectl logs -l app=fxml4-api -n fxml4-prod | grep "rate limit" | tail -20
   ```

**Solutions:**

1. **Adjust rate limits:**
   ```yaml
   # Update rate limiter configuration
   apiVersion: v1
   kind: ConfigMap
   metadata:
     name: rate-limiter-config
   data:
     requests_per_minute: "200"
     burst_size: "50"
   ```

2. **Implement user-specific limits:**
   ```python
   # Different limits for different user tiers
   RATE_LIMITS = {
       'free': {'requests_per_minute': 100},
       'premium': {'requests_per_minute': 500},
       'enterprise': {'requests_per_minute': 2000}
   }
   ```

## Database Problems

### Problem: Database Connection Errors

**Symptoms:**
- "Connection refused" errors
- "Connection pool exhausted" messages
- Database timeouts

**Diagnostic Steps:**

1. **Check PostgreSQL status:**
   ```bash
   kubectl get pods -l app=postgres -n fxml4-prod
   kubectl logs postgres-0 -n fxml4-prod --tail=50
   ```

2. **Verify connection parameters:**
   ```bash
   kubectl exec -it postgres-0 -n fxml4-prod -- \
     psql -U postgres -c "SHOW max_connections;"
   ```

3. **Check active connections:**
   ```sql
   SELECT count(*), state FROM pg_stat_activity GROUP BY state;
   ```

**Solutions:**

1. **Increase connection limits:**
   ```sql
   ALTER SYSTEM SET max_connections = 200;
   SELECT pg_reload_conf();
   ```

2. **Optimize connection pooling:**
   ```yaml
   # PgBouncer configuration
   databases:
     fxml4:
       host: postgres
       port: 5432
       pool_size: 20
       reserve_pool_size: 5
   ```

3. **Kill idle connections:**
   ```sql
   SELECT pg_terminate_backend(pid)
   FROM pg_stat_activity
   WHERE state = 'idle' AND query_start < now() - interval '10 minutes';
   ```

### Problem: Slow Database Queries

**Symptoms:**
- Query timeouts
- High database CPU usage
- Slow application responses

**Diagnostic Steps:**

1. **Identify slow queries:**
   ```sql
   SELECT query, mean_time, calls, total_time
   FROM pg_stat_statements
   ORDER BY mean_time DESC
   LIMIT 10;
   ```

2. **Check for missing indexes:**
   ```sql
   SELECT schemaname, tablename, attname, n_distinct, correlation
   FROM pg_stats
   WHERE tablename IN ('market_data', 'signals', 'backtests');
   ```

3. **Analyze query plans:**
   ```sql
   EXPLAIN (ANALYZE, BUFFERS)
   SELECT * FROM market_data
   WHERE symbol = 'EURUSD' AND timestamp > '2023-12-01'
   ORDER BY timestamp DESC;
   ```

**Solutions:**

1. **Add appropriate indexes:**
   ```sql
   -- For time-series queries
   CREATE INDEX CONCURRENTLY idx_market_data_symbol_time
   ON market_data (symbol, timestamp DESC);

   -- For signal queries
   CREATE INDEX CONCURRENTLY idx_signals_symbol_created
   ON signals (symbol, created_at DESC);
   ```

2. **Update table statistics:**
   ```sql
   ANALYZE market_data;
   ANALYZE signals;
   ```

3. **Optimize queries:**
   ```sql
   -- Instead of SELECT *
   SELECT timestamp, close FROM market_data
   WHERE symbol = 'EURUSD' AND timestamp > '2023-12-01'
   ORDER BY timestamp DESC
   LIMIT 1000;
   ```

### Problem: TimescaleDB Chunk Issues

**Symptoms:**
- Poor query performance on time-series data
- Uneven data distribution
- Disk space issues

**Diagnostic Steps:**

1. **Check chunk information:**
   ```sql
   SELECT chunk_name, range_start, range_end, chunk_size
   FROM timescaledb_information.chunks
   WHERE hypertable_name = 'market_data'
   ORDER BY range_start DESC
   LIMIT 10;
   ```

2. **Analyze chunk sizes:**
   ```sql
   SELECT
     chunk_name,
     pg_size_pretty(pg_total_relation_size(format('%I.%I', chunk_schema, chunk_name))) as size
   FROM timescaledb_information.chunks
   WHERE hypertable_name = 'market_data';
   ```

**Solutions:**

1. **Adjust chunk intervals:**
   ```sql
   SELECT set_chunk_time_interval('market_data', INTERVAL '1 day');
   ```

2. **Compress old chunks:**
   ```sql
   SELECT add_compression_policy('market_data', INTERVAL '7 days');
   ```

3. **Drop old chunks:**
   ```sql
   SELECT drop_chunks('market_data', INTERVAL '1 year');
   ```

## Authentication Issues

### Problem: JWT Token Validation Errors

**Symptoms:**
- "Invalid token" errors
- Authentication failures
- Token expiration issues

**Diagnostic Steps:**

1. **Verify token structure:**
   ```bash
   # Decode JWT token (without verification)
   echo "$JWT_TOKEN" | cut -d. -f2 | base64 -d | jq .
   ```

2. **Check token expiration:**
   ```python
   import jwt
   from datetime import datetime

   payload = jwt.decode(token, options={"verify_signature": False})
   exp_time = datetime.fromtimestamp(payload['exp'])
   print(f"Token expires: {exp_time}")
   ```

3. **Verify secret key configuration:**
   ```bash
   kubectl get secret fxml4-secrets -n fxml4-prod -o jsonpath='{.data.jwt-secret}' | base64 -d
   ```

**Solutions:**

1. **Regenerate token:**
   ```bash
   curl -X POST https://api.fxml4.com/token \
     -H "Content-Type: application/x-www-form-urlencoded" \
     -d "username=your_username&password=your_password"
   ```

2. **Update secret key:**
   ```bash
   kubectl patch secret fxml4-secrets -n fxml4-prod -p \
     '{"data":{"jwt-secret":"'$(echo -n "new-secret-key" | base64)'"}}'
   ```

3. **Increase token expiration:**
   ```python
   # In configuration
   ACCESS_TOKEN_EXPIRE_MINUTES = 60  # Increase from 30 to 60 minutes
   ```

### Problem: User Authentication Failures

**Symptoms:**
- Login failures with correct credentials
- "User not found" errors
- Permission denied errors

**Diagnostic Steps:**

1. **Check user database:**
   ```sql
   SELECT username, email, disabled, scopes
   FROM users
   WHERE username = 'problematic_user';
   ```

2. **Verify password hashing:**
   ```python
   from passlib.context import CryptContext

   pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
   print(pwd_context.verify("plain_password", "hashed_password"))
   ```

**Solutions:**

1. **Reset user password:**
   ```sql
   UPDATE users
   SET password_hash = '$2b$12$new_hashed_password'
   WHERE username = 'user';
   ```

2. **Enable disabled user:**
   ```sql
   UPDATE users SET disabled = false WHERE username = 'user';
   ```

3. **Update user scopes:**
   ```sql
   UPDATE users SET scopes = '["user", "admin"]' WHERE username = 'user';
   ```

## Data Feed Problems

### Problem: Alpha Vantage API Errors

**Symptoms:**
- "API call frequency" error messages
- Empty data responses
- Rate limit errors

**Diagnostic Steps:**

1. **Test API directly:**
   ```bash
   curl "https://www.alphavantage.co/query?function=TIME_SERIES_INTRADAY&symbol=IBM&interval=1min&apikey=$ALPHA_VANTAGE_API_KEY"
   ```

2. **Check API usage:**
   ```bash
   # Count API calls in logs
   kubectl logs -l app=fxml4-worker -n fxml4-prod --since=1h | grep -c "alphavantage"
   ```

**Solutions:**

1. **Implement exponential backoff:**
   ```python
   import time
   import random

   def retry_with_backoff(func, max_retries=5):
       for attempt in range(max_retries):
           try:
               return func()
           except RateLimitError:
               wait_time = (2 ** attempt) + random.uniform(0, 1)
               time.sleep(wait_time)
       raise Exception("Max retries exceeded")
   ```

2. **Use multiple API keys:**
   ```python
   API_KEYS = [
       "key1",
       "key2",
       "key3"
   ]

   def get_next_api_key():
       # Round-robin or random selection
       return random.choice(API_KEYS)
   ```

3. **Cache API responses:**
   ```python
   @cache.memoize(timeout=300)  # Cache for 5 minutes
   def fetch_market_data(symbol, interval):
       # API call implementation
   ```

### Problem: Interactive Brokers Connection Issues

**Symptoms:**
- TWS connection failures
- Authentication errors
- Data not updating

**Diagnostic Steps:**

1. **Check IB Gateway status:**
   ```bash
   # If running in container
   docker logs ib-gateway-container

   # Check TWS API connection
   telnet localhost 7497
   ```

2. **Verify IB credentials:**
   ```python
   from ibapi.client import EClient
   from ibapi.wrapper import EWrapper

   # Test connection
   app = TestApp()
   app.connect("127.0.0.1", 7497, clientId=1)
   ```

**Solutions:**

1. **Restart IB Gateway:**
   ```bash
   docker restart ib-gateway-container
   ```

2. **Update IB credentials:**
   ```bash
   kubectl patch secret ib-credentials -n fxml4-prod -p \
     '{"data":{"username":"'$(echo -n "new_username" | base64)'"}}'
   ```

3. **Configure paper trading:**
   ```python
   # Use paper trading account
   IB_CONFIG = {
       'host': 'localhost',
       'port': 7497,  # Paper trading port
       'client_id': 1
   }
   ```

## Backtesting Issues

### Problem: Backtest Execution Failures

**Symptoms:**
- Backtest jobs fail to complete
- "Insufficient data" errors
- Memory errors during execution

**Diagnostic Steps:**

1. **Check backtest logs:**
   ```bash
   kubectl logs -l app=fxml4-worker -n fxml4-prod | grep -A 10 -B 10 "backtest_id"
   ```

2. **Verify data availability:**
   ```sql
   SELECT symbol, min(timestamp), max(timestamp), count(*)
   FROM market_data
   WHERE symbol = 'EURUSD'
   GROUP BY symbol;
   ```

3. **Check memory usage:**
   ```bash
   kubectl top pods -l app=fxml4-worker -n fxml4-prod
   ```

**Solutions:**

1. **Increase worker memory:**
   ```bash
   kubectl patch deployment fxml4-worker -n fxml4-prod -p \
     '{"spec":{"template":{"spec":{"containers":[{"name":"worker","resources":{"limits":{"memory":"8Gi"}}}]}}}}'
   ```

2. **Process data in chunks:**
   ```python
   def run_backtest_chunked(data, chunk_size=10000):
       results = []
       for i in range(0, len(data), chunk_size):
           chunk = data[i:i+chunk_size]
           result = process_chunk(chunk)
           results.append(result)
       return combine_results(results)
   ```

3. **Optimize data loading:**
   ```python
   # Use specific columns only
   columns = ['timestamp', 'open', 'high', 'low', 'close', 'volume']
   data = pd.read_sql(query, connection, columns=columns)
   ```

### Problem: Incorrect Backtest Results

**Symptoms:**
- Unrealistic returns
- Negative Sharpe ratios when expected positive
- Trade count mismatches

**Diagnostic Steps:**

1. **Verify data quality:**
   ```sql
   SELECT symbol, count(*) as records,
          count(DISTINCT DATE(timestamp)) as trading_days,
          min(timestamp), max(timestamp)
   FROM market_data
   WHERE symbol = 'EURUSD'
   GROUP BY symbol;
   ```

2. **Check for data gaps:**
   ```sql
   WITH gaps AS (
     SELECT timestamp,
            LAG(timestamp) OVER (ORDER BY timestamp) as prev_timestamp,
            timestamp - LAG(timestamp) OVER (ORDER BY timestamp) as gap
     FROM market_data
     WHERE symbol = 'EURUSD'
   )
   SELECT * FROM gaps WHERE gap > INTERVAL '1 hour';
   ```

3. **Validate strategy logic:**
   ```python
   # Add debug logging to strategy
   def strategy_function(data, index, params):
       signals = {}
       # Add logging for debugging
       logger.debug(f"Processing bar {index}: {data.iloc[index]}")
       # Strategy logic
       return signals
   ```

**Solutions:**

1. **Fill data gaps:**
   ```python
   # Forward fill missing data
   data = data.resample('1H').ffill()
   ```

2. **Adjust commission/slippage:**
   ```python
   BACKTEST_CONFIG = {
       'commission': 0.0002,  # 2 pips
       'slippage': 0.0001,    # 1 pip
   }
   ```

3. **Validate trade execution:**
   ```python
   def validate_trade(entry_price, exit_price, side):
       if side == 'buy' and exit_price <= entry_price:
           logger.warning("Suspicious buy trade: exit <= entry")
       elif side == 'sell' and exit_price >= entry_price:
           logger.warning("Suspicious sell trade: exit >= entry")
   ```

## Performance Problems

### Problem: High Memory Usage

**Symptoms:**
- Out of memory errors
- Pod restarts due to memory limits
- Slow garbage collection

**Diagnostic Steps:**

1. **Check memory usage:**
   ```bash
   kubectl top pods -n fxml4-prod
   kubectl describe pod <pod-name> -n fxml4-prod | grep -A 5 "Memory"
   ```

2. **Profile memory usage:**
   ```python
   import psutil
   import gc

   process = psutil.Process()
   print(f"Memory usage: {process.memory_info().rss / 1024 / 1024:.2f} MB")

   # Force garbage collection
   gc.collect()
   ```

**Solutions:**

1. **Increase memory limits:**
   ```bash
   kubectl patch deployment fxml4-api -n fxml4-prod -p \
     '{"spec":{"template":{"spec":{"containers":[{"name":"api","resources":{"limits":{"memory":"4Gi"}}}]}}}}'
   ```

2. **Optimize data processing:**
   ```python
   # Process data in chunks
   for chunk in pd.read_csv('large_file.csv', chunksize=10000):
       process_chunk(chunk)
       del chunk  # Explicit cleanup
   ```

3. **Implement data cleanup:**
   ```python
   # Regular cleanup of large objects
   def cleanup_large_objects():
       global large_data_cache
       large_data_cache.clear()
       gc.collect()
   ```

### Problem: High CPU Usage

**Symptoms:**
- Slow response times
- CPU throttling
- High load averages

**Diagnostic Steps:**

1. **Check CPU usage:**
   ```bash
   kubectl top pods -n fxml4-prod
   kubectl top nodes
   ```

2. **Profile CPU usage:**
   ```python
   import cProfile
   import pstats

   profiler = cProfile.Profile()
   profiler.enable()
   # Your code here
   profiler.disable()
   stats = pstats.Stats(profiler)
   stats.sort_stats('cumulative').print_stats(10)
   ```

**Solutions:**

1. **Scale horizontally:**
   ```bash
   kubectl scale deployment fxml4-api --replicas=5 -n fxml4-prod
   ```

2. **Optimize algorithms:**
   ```python
   # Use vectorized operations instead of loops
   # Before: slow loop
   results = []
   for i in range(len(data)):
       results.append(calculate_indicator(data[i]))

   # After: vectorized
   results = calculate_indicator_vectorized(data)
   ```

3. **Add caching:**
   ```python
   from functools import lru_cache

   @lru_cache(maxsize=1000)
   def expensive_calculation(symbol, timeframe):
       # Expensive operation
       return result
   ```

## Deployment Issues

### Problem: Container Image Pull Failures

**Symptoms:**
- "ImagePullBackOff" status
- "Failed to pull image" errors
- Pods stuck in pending state

**Diagnostic Steps:**

1. **Check image exists:**
   ```bash
   docker pull fxml4:latest
   # or
   gcloud container images list --repository=gcr.io/fxml4-prod
   ```

2. **Verify registry credentials:**
   ```bash
   kubectl get secret regcred -n fxml4-prod -o jsonpath='{.data.\.dockerconfigjson}' | base64 -d
   ```

**Solutions:**

1. **Update image pull secret:**
   ```bash
   kubectl create secret docker-registry regcred \
     --docker-server=gcr.io \
     --docker-username=_json_key \
     --docker-password="$(cat key.json)" \
     --namespace=fxml4-prod
   ```

2. **Use correct image tag:**
   ```yaml
   containers:
   - name: api
     image: gcr.io/fxml4-prod/fxml4:v1.2.0  # Specific version
   ```

### Problem: ConfigMap/Secret Issues

**Symptoms:**
- Environment variables not set
- Configuration not loading
- Secret values incorrect

**Diagnostic Steps:**

1. **Check ConfigMap contents:**
   ```bash
   kubectl get configmap app-config -n fxml4-prod -o yaml
   ```

2. **Verify Secret values:**
   ```bash
   kubectl get secret app-secrets -n fxml4-prod -o jsonpath='{.data.api-key}' | base64 -d
   ```

**Solutions:**

1. **Update ConfigMap:**
   ```bash
   kubectl patch configmap app-config -n fxml4-prod --patch \
     '{"data":{"DATABASE_URL":"new-database-url"}}'
   ```

2. **Recreate Secret:**
   ```bash
   kubectl delete secret app-secrets -n fxml4-prod
   kubectl create secret generic app-secrets \
     --from-literal=api-key=new-api-key \
     --namespace=fxml4-prod
   ```

## External Service Issues

### Problem: Google Cloud Vertex AI Errors

**Symptoms:**
- "Permission denied" errors
- "Quota exceeded" messages
- ML model prediction failures

**Diagnostic Steps:**

1. **Check service account permissions:**
   ```bash
   gcloud projects get-iam-policy fxml4-prod --flatten="bindings[].members" --filter="bindings.members:serviceAccount"
   ```

2. **Verify API quotas:**
   ```bash
   gcloud compute project-info describe --format="table(quotas.metric,quotas.usage,quotas.limit)"
   ```

**Solutions:**

1. **Update service account permissions:**
   ```bash
   gcloud projects add-iam-policy-binding fxml4-prod \
     --member="serviceAccount:fxml4-sa@fxml4-prod.iam.gserviceaccount.com" \
     --role="roles/aiplatform.user"
   ```

2. **Request quota increase:**
   ```bash
   # Submit quota increase request through Google Cloud Console
   ```

### Problem: OpenAI API Issues

**Symptoms:**
- "Rate limit exceeded" errors
- "Invalid API key" errors
- Empty responses from GPT models

**Diagnostic Steps:**

1. **Test API key:**
   ```bash
   curl https://api.openai.com/v1/models \
     -H "Authorization: Bearer $OPENAI_API_KEY"
   ```

2. **Check usage limits:**
   ```bash
   curl https://api.openai.com/v1/usage \
     -H "Authorization: Bearer $OPENAI_API_KEY"
   ```

**Solutions:**

1. **Implement retry logic:**
   ```python
   import openai
   from tenacity import retry, stop_after_attempt, wait_exponential

   @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
   def call_openai_api(prompt):
       return openai.Completion.create(
           engine="text-davinci-003",
           prompt=prompt,
           max_tokens=150
       )
   ```

2. **Use fallback models:**
   ```python
   MODELS = ["gpt-4", "gpt-3.5-turbo", "text-davinci-003"]

   def get_completion(prompt):
       for model in MODELS:
           try:
               return openai.ChatCompletion.create(model=model, messages=prompt)
           except Exception as e:
               logger.warning(f"Model {model} failed: {e}")
               continue
       raise Exception("All models failed")
   ```

## Log Analysis

### Centralized Logging

```bash
# View all application logs
kubectl logs -l app=fxml4 -n fxml4-prod --all-containers --since=1h

# Filter for specific error types
kubectl logs -l app=fxml4-api -n fxml4-prod | grep -E "(ERROR|CRITICAL|FATAL)"

# Search for specific patterns
kubectl logs -l app=fxml4-worker -n fxml4-prod | grep -i "database"
```

### Log Analysis Patterns

1. **Authentication Errors:**
   ```bash
   kubectl logs -l app=ftml4-api -n fxml4-prod | grep -E "(401|403|authentication|authorization)"
   ```

2. **Database Errors:**
   ```bash
   kubectl logs -l app=fxml4 -n fxml4-prod | grep -E "(connection.*refused|pool.*exhausted|timeout.*database)"
   ```

3. **External API Errors:**
   ```bash
   kubectl logs -l app=fxml4-worker -n fxml4-prod | grep -E "(rate.*limit|api.*key|quota.*exceeded)"
   ```

### Performance Metrics

```bash
# Response time analysis
kubectl logs -l app=fxml4-api -n fxml4-prod | grep "request_duration" | awk '{print $NF}' | sort -n | tail -10

# Error rate calculation
TOTAL_REQUESTS=$(kubectl logs -l app=fxml4-api -n fxml4-prod --since=1h | grep -c "HTTP")
ERROR_REQUESTS=$(kubectl logs -l app=fxml4-api -n fxml4-prod --since=1h | grep -c "HTTP.*[45][0-9][0-9]")
ERROR_RATE=$(echo "scale=4; $ERROR_REQUESTS / $TOTAL_REQUESTS * 100" | bc)
echo "Error Rate: $ERROR_RATE%"
```

---

*For additional support, contact the operations team or refer to the [Operational Runbook](operational-runbook.md)*
