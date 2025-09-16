# FXML4 Performance Tuning Guide

This guide provides comprehensive recommendations for optimizing FXML4 performance across all components and deployment scenarios.

## Table of Contents

1. [Performance Overview](#performance-overview)
2. [Database Optimization](#database-optimization)
3. [API Performance Tuning](#api-performance-tuning)
4. [Application Optimization](#application-optimization)
5. [Infrastructure Scaling](#infrastructure-scaling)
6. [Caching Strategies](#caching-strategies)
7. [Memory Management](#memory-management)
8. [Network Optimization](#network-optimization)
9. [Monitoring and Profiling](#monitoring-and-profiling)
10. [Load Testing](#load-testing)

## Performance Overview

### Performance Targets

| Component | Metric | Target | Excellent |
|-----------|--------|---------|-----------|
| API Response Time | 95th percentile | < 500ms | < 200ms |
| Database Queries | 95th percentile | < 100ms | < 50ms |
| Backtest Execution | 1 year data | < 5 minutes | < 2 minutes |
| Memory Usage | Per instance | < 4GB | < 2GB |
| CPU Usage | Average | < 70% | < 50% |
| Throughput | Requests/second | > 100 | > 500 |

### Architecture Performance Considerations

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Load Balancer │────│     CDN         │────│   API Gateway   │
│   (nginx)       │    │   (CloudFlare)  │    │   (rate limit)  │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │
         ▼                       ▼                       ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   API Instances │    │   Redis Cache   │    │   Background    │
│   (horizontal)  │────│   (L2 cache)    │────│   Workers       │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │
         ▼                       ▼                       ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   PostgreSQL    │    │   TimescaleDB   │    │   External APIs │
│   (metadata)    │    │  (time series)  │    │ (rate limited)  │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

## Database Optimization

### PostgreSQL Configuration

#### Memory Settings

```postgresql
-- postgresql.conf optimizations
shared_buffers = '4GB'                    -- 25% of total RAM
effective_cache_size = '12GB'             -- 75% of total RAM
maintenance_work_mem = '512MB'            -- For maintenance operations
work_mem = '64MB'                         -- Per query operation
wal_buffers = '16MB'                      -- WAL buffer size
checkpoint_segments = 32                  -- Number of WAL segments
checkpoint_completion_target = 0.9        -- Spread checkpoints
```

#### Connection Optimization

```postgresql
-- Connection settings
max_connections = 200                     -- Adjust based on load
shared_preload_libraries = 'pg_stat_statements'
pg_stat_statements.max = 10000
pg_stat_statements.track = all
```

#### Query Optimization

1. **Essential Indexes**

```sql
-- Market data indexes
CREATE INDEX CONCURRENTLY idx_market_data_symbol_timestamp
ON market_data (symbol, timestamp DESC);

CREATE INDEX CONCURRENTLY idx_market_data_timestamp_symbol
ON market_data (timestamp DESC, symbol);

-- Signal indexes
CREATE INDEX CONCURRENTLY idx_signals_symbol_created
ON signals (symbol, created_at DESC);

CREATE INDEX CONCURRENTLY idx_signals_strategy_created
ON signals (strategy, created_at DESC);

-- Backtest indexes
CREATE INDEX CONCURRENTLY idx_backtests_user_created
ON backtests (user_id, created_at DESC);

CREATE INDEX CONCURRENTLY idx_backtest_trades_backtest_id
ON backtest_trades (backtest_id);
```

2. **Query Performance Analysis**

```sql
-- Find slow queries
SELECT
    query,
    calls,
    total_time,
    mean_time,
    stddev_time,
    (total_time/calls) as avg_time_ms
FROM pg_stat_statements
WHERE calls > 10
ORDER BY mean_time DESC
LIMIT 20;

-- Check index usage
SELECT
    schemaname,
    tablename,
    indexname,
    idx_scan,
    idx_tup_read,
    idx_tup_fetch
FROM pg_stat_user_indexes
ORDER BY idx_scan DESC;

-- Find unused indexes
SELECT
    schemaname,
    tablename,
    indexname,
    idx_scan
FROM pg_stat_user_indexes
WHERE idx_scan = 0
AND indexname NOT LIKE '%_pkey';
```

### TimescaleDB Optimization

#### Chunk Configuration

```sql
-- Optimize chunk intervals
SELECT set_chunk_time_interval('market_data', INTERVAL '1 day');
SELECT set_chunk_time_interval('signals', INTERVAL '1 week');

-- Enable compression for older data
SELECT add_compression_policy('market_data', INTERVAL '7 days');
SELECT add_compression_policy('signals', INTERVAL '30 days');

-- Set retention policies
SELECT add_retention_policy('market_data', INTERVAL '2 years');
SELECT add_retention_policy('signals', INTERVAL '1 year');
```

#### Query Optimization

```sql
-- Optimize time-series queries
-- Use time-based WHERE clauses
SELECT * FROM market_data
WHERE timestamp >= NOW() - INTERVAL '1 day'
AND symbol = 'EURUSD'
ORDER BY timestamp DESC;

-- Use time_bucket for aggregations
SELECT
    time_bucket('1 hour', timestamp) as time_bucket,
    symbol,
    first(open, timestamp) as open,
    max(high) as high,
    min(low) as low,
    last(close, timestamp) as close,
    sum(volume) as volume
FROM market_data
WHERE timestamp >= NOW() - INTERVAL '1 week'
GROUP BY time_bucket, symbol
ORDER BY time_bucket DESC;
```

### Connection Pooling

#### PgBouncer Configuration

```ini
# pgbouncer.ini
[databases]
fxml4 = host=postgres port=5432 dbname=fxml4

[pgbouncer]
pool_mode = transaction
listen_port = 6432
max_client_conn = 200
default_pool_size = 25
reserve_pool_size = 5
max_db_connections = 50
log_connections = 1
log_disconnections = 1
stats_period = 60
```

#### Application Connection Pool

```python
# Database connection configuration
DATABASE_CONFIG = {
    'pool_size': 20,           # Base pool size
    'max_overflow': 30,        # Additional connections
    'pool_timeout': 30,        # Connection timeout
    'pool_recycle': 3600,      # Recycle connections every hour
    'pool_pre_ping': True,     # Validate connections
    'echo': False,             # Disable SQL logging in production
}

# SQLAlchemy engine setup
engine = create_engine(
    DATABASE_URL,
    **DATABASE_CONFIG,
    connect_args={
        "sslmode": "require",
        "application_name": "fxml4-api"
    }
)
```

## API Performance Tuning

### FastAPI Optimization

#### Configuration Settings

```python
# main.py optimizations
app = FastAPI(
    title="FXML4 API",
    docs_url="/docs" if DEBUG else None,  # Disable docs in production
    redoc_url="/redoc" if DEBUG else None,
    openapi_url="/openapi.json" if DEBUG else None,
    debug=DEBUG
)

# Add performance middleware
@app.middleware("http")
async def add_performance_headers(request: Request, call_next):
    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time
    response.headers["X-Process-Time"] = str(process_time)
    return response
```

#### Response Optimization

```python
# Use appropriate response models
from pydantic import BaseModel
from typing import List, Optional

class OptimizedDataResponse(BaseModel):
    symbol: str
    count: int
    data: List[dict]  # Use dict instead of complex models for large datasets

    class Config:
        # Optimize JSON serialization
        json_encoders = {
            datetime: lambda v: v.isoformat(),
            Decimal: lambda v: float(v)
        }

# Implement pagination
@app.get("/data")
async def get_data(
    symbol: str,
    limit: int = Query(100, le=1000),  # Limit max results
    offset: int = Query(0, ge=0)
):
    # Implementation with LIMIT/OFFSET
    pass

# Use streaming for large responses
@app.get("/data/stream")
async def stream_data(symbol: str):
    def generate_data():
        # Yield data in chunks
        for chunk in get_data_chunks(symbol):
            yield json.dumps(chunk) + "\n"

    return StreamingResponse(
        generate_data(),
        media_type="application/x-ndjson"
    )
```

### Request Processing Optimization

#### Async Processing

```python
import asyncio
from concurrent.futures import ThreadPoolExecutor

# Use async for I/O bound operations
@app.post("/backtest")
async def run_backtest_async(request: BacktestRequest):
    # Run CPU-intensive backtesting in thread pool
    loop = asyncio.get_event_loop()
    with ThreadPoolExecutor(max_workers=4) as executor:
        result = await loop.run_in_executor(
            executor,
            run_backtest_sync,
            request
        )
    return result

# Batch API calls
@app.post("/data/batch")
async def get_data_batch(requests: List[DataRequest]):
    # Process multiple requests concurrently
    tasks = [get_data_async(req) for req in requests]
    results = await asyncio.gather(*tasks)
    return {"results": results}
```

#### Input Validation Optimization

```python
from pydantic import validator, Field

class OptimizedRequest(BaseModel):
    symbol: str = Field(..., regex=r'^[A-Z]{6}$')  # Precompiled regex
    timeframe: str = Field(..., regex=r'^(1m|5m|15m|30m|1h|4h|1d|1w|1M)$')

    @validator('symbol')
    def validate_symbol(cls, v):
        # Cache allowed symbols
        if v not in ALLOWED_SYMBOLS_CACHE:
            raise ValueError('Invalid symbol')
        return v

    class Config:
        # Validate assignment for better performance
        validate_assignment = False
        # Allow mutation for better memory usage
        allow_mutation = True
```

## Application Optimization

### Data Processing Optimization

#### Pandas Performance

```python
import pandas as pd
import numpy as np

# Optimize DataFrame operations
def optimize_dataframe_processing(df):
    # Use categorical data for repeated strings
    if 'symbol' in df.columns:
        df['symbol'] = df['symbol'].astype('category')

    # Use appropriate dtypes
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    df['open'] = df['open'].astype('float32')  # Use float32 instead of float64
    df['high'] = df['high'].astype('float32')
    df['low'] = df['low'].astype('float32')
    df['close'] = df['close'].astype('float32')
    df['volume'] = df['volume'].astype('int32')

    return df

# Use vectorized operations
def calculate_indicators_vectorized(df):
    # Vectorized SMA
    df['sma_20'] = df['close'].rolling(window=20).mean()

    # Vectorized RSI
    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    df['rsi'] = 100 - (100 / (1 + rs))

    return df

# Process data in chunks for large datasets
def process_large_dataset(file_path, chunk_size=10000):
    results = []
    for chunk in pd.read_csv(file_path, chunksize=chunk_size):
        processed_chunk = process_chunk(chunk)
        results.append(processed_chunk)
    return pd.concat(results, ignore_index=True)
```

#### NumPy Optimization

```python
import numpy as np
from numba import jit, prange

# Use Numba for performance-critical calculations
@jit(nopython=True)
def fast_moving_average(prices, window):
    n = len(prices)
    result = np.empty(n)
    result[:window-1] = np.nan

    for i in prange(window-1, n):
        result[i] = np.mean(prices[i-window+1:i+1])

    return result

@jit(nopython=True)
def fast_rsi(prices, window=14):
    n = len(prices)
    deltas = np.diff(prices)

    gains = np.where(deltas > 0, deltas, 0)
    losses = np.where(deltas < 0, -deltas, 0)

    avg_gains = np.empty(n-1)
    avg_losses = np.empty(n-1)

    avg_gains[window-1] = np.mean(gains[:window])
    avg_losses[window-1] = np.mean(losses[:window])

    for i in range(window, n-1):
        avg_gains[i] = (avg_gains[i-1] * (window-1) + gains[i]) / window
        avg_losses[i] = (avg_losses[i-1] * (window-1) + losses[i]) / window

    rs = avg_gains / avg_losses
    rsi = 100 - (100 / (1 + rs))

    return rsi
```

### Memory Management

#### Memory Profiling

```python
import tracemalloc
import psutil
import gc

class MemoryProfiler:
    def __init__(self):
        self.process = psutil.Process()
        tracemalloc.start()

    def get_memory_usage(self):
        return self.process.memory_info().rss / 1024 / 1024  # MB

    def get_memory_delta(self, snapshot1, snapshot2):
        top_stats = snapshot2.compare_to(snapshot1, 'lineno')
        return top_stats[:10]

    def force_gc(self):
        collected = gc.collect()
        return collected

# Usage example
profiler = MemoryProfiler()
snapshot1 = tracemalloc.take_snapshot()

# Your code here

snapshot2 = tracemalloc.take_snapshot()
delta = profiler.get_memory_delta(snapshot1, snapshot2)
```

#### Memory Optimization Strategies

```python
# Use generators for large datasets
def generate_market_data(symbol, start_date, end_date):
    query = """
    SELECT timestamp, open, high, low, close, volume
    FROM market_data
    WHERE symbol = %s AND timestamp BETWEEN %s AND %s
    ORDER BY timestamp
    """

    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(query, (symbol, start_date, end_date))

        while True:
            rows = cursor.fetchmany(1000)  # Fetch in batches
            if not rows:
                break
            yield rows

# Implement object pooling for expensive objects
class BacktestEnginePool:
    def __init__(self, pool_size=5):
        self.pool = []
        self.pool_size = pool_size
        self.in_use = set()

    def get_engine(self):
        if self.pool:
            engine = self.pool.pop()
        else:
            engine = BacktestEngine()

        self.in_use.add(id(engine))
        return engine

    def return_engine(self, engine):
        if id(engine) in self.in_use:
            engine.reset()  # Clean up state
            self.pool.append(engine)
            self.in_use.remove(id(engine))

# Use weak references for caches
import weakref

class WeakCache:
    def __init__(self):
        self._cache = weakref.WeakValueDictionary()

    def get(self, key):
        return self._cache.get(key)

    def set(self, key, value):
        self._cache[key] = value
```

## Infrastructure Scaling

### Kubernetes Optimization

#### Resource Configuration

```yaml
# deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: fxml4-api
spec:
  replicas: 3
  template:
    spec:
      containers:
      - name: api
        image: fxml4:latest
        resources:
          requests:
            memory: "1Gi"
            cpu: "500m"
          limits:
            memory: "4Gi"
            cpu: "2000m"
        readinessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 30
          periodSeconds: 10
          timeoutSeconds: 5
        livenessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 60
          periodSeconds: 30
          timeoutSeconds: 10
        env:
        - name: DB_POOL_SIZE
          value: "20"
        - name: WORKERS
          value: "4"
```

#### Horizontal Pod Autoscaler

```yaml
# hpa.yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: fxml4-api-hpa
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: fxml4-api
  minReplicas: 3
  maxReplicas: 20
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
  - type: Resource
    resource:
      name: memory
      target:
        type: Utilization
        averageUtilization: 80
  behavior:
    scaleUp:
      stabilizationWindowSeconds: 300
      policies:
      - type: Percent
        value: 100
        periodSeconds: 60
    scaleDown:
      stabilizationWindowSeconds: 300
      policies:
      - type: Percent
        value: 10
        periodSeconds: 60
```

### Load Balancing

#### Nginx Configuration

```nginx
# nginx.conf
upstream fxml4_api {
    least_conn;
    server api-1:8000 max_fails=3 fail_timeout=30s;
    server api-2:8000 max_fails=3 fail_timeout=30s;
    server api-3:8000 max_fails=3 fail_timeout=30s;
}

server {
    listen 80;
    listen 443 ssl http2;
    server_name api.fxml4.com;

    # SSL configuration
    ssl_certificate /etc/ssl/certs/fxml4.crt;
    ssl_certificate_key /etc/ssl/private/fxml4.key;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers ECDHE-RSA-AES256-GCM-SHA512:DHE-RSA-AES256-GCM-SHA512;

    # Performance settings
    client_max_body_size 10M;
    client_body_timeout 60s;
    client_header_timeout 60s;
    keepalive_timeout 65s;
    send_timeout 60s;

    # Compression
    gzip on;
    gzip_vary on;
    gzip_min_length 1024;
    gzip_types text/plain application/json application/javascript text/css;

    # Rate limiting
    limit_req_zone $binary_remote_addr zone=api:10m rate=10r/s;
    limit_req zone=api burst=20 nodelay;

    location / {
        proxy_pass http://fxml4_api;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # Timeouts
        proxy_connect_timeout 5s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;

        # Health checks
        proxy_next_upstream error timeout invalid_header http_500 http_502 http_503;
    }

    # Static file caching
    location /static/ {
        expires 1y;
        add_header Cache-Control "public, immutable";
    }
}
```

## Caching Strategies

### Redis Configuration

#### Redis Setup

```redis
# redis.conf
maxmemory 2gb
maxmemory-policy allkeys-lru
save 900 1
save 300 10
save 60 10000

# Performance settings
tcp-keepalive 300
tcp-backlog 511
timeout 300
```

#### Application Caching

```python
import redis
import json
import pickle
from functools import wraps
from typing import Optional, Any

class CacheManager:
    def __init__(self, redis_url: str):
        self.redis = redis.from_url(redis_url)

    def get(self, key: str) -> Optional[Any]:
        try:
            data = self.redis.get(key)
            if data:
                return pickle.loads(data)
        except Exception as e:
            logger.warning(f"Cache get error: {e}")
        return None

    def set(self, key: str, value: Any, ttl: int = 300):
        try:
            self.redis.setex(key, ttl, pickle.dumps(value))
        except Exception as e:
            logger.warning(f"Cache set error: {e}")

    def delete(self, key: str):
        try:
            self.redis.delete(key)
        except Exception as e:
            logger.warning(f"Cache delete error: {e}")

# Cache decorators
def cache_result(ttl: int = 300, key_prefix: str = ""):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Generate cache key
            key_parts = [key_prefix, func.__name__]
            key_parts.extend(str(arg) for arg in args)
            key_parts.extend(f"{k}={v}" for k, v in sorted(kwargs.items()))
            cache_key = ":".join(key_parts)

            # Try to get from cache
            cached_result = cache_manager.get(cache_key)
            if cached_result is not None:
                return cached_result

            # Execute function and cache result
            result = func(*args, **kwargs)
            cache_manager.set(cache_key, result, ttl)
            return result
        return wrapper
    return decorator

# Usage examples
@cache_result(ttl=300, key_prefix="market_data")
def get_market_data(symbol: str, timeframe: str, limit: int = 100):
    # Expensive database query
    return fetch_from_database(symbol, timeframe, limit)

@cache_result(ttl=60, key_prefix="signals")
def generate_signals(symbol: str, strategy: str, params: dict):
    # Expensive signal calculation
    return calculate_signals(symbol, strategy, params)
```

### Multi-Level Caching

```python
class MultiLevelCache:
    def __init__(self):
        self.l1_cache = {}  # In-memory cache
        self.l1_max_size = 1000
        self.l2_cache = redis.Redis()  # Redis cache

    def get(self, key: str) -> Optional[Any]:
        # Try L1 cache first
        if key in self.l1_cache:
            return self.l1_cache[key]

        # Try L2 cache
        try:
            data = self.l2_cache.get(key)
            if data:
                value = pickle.loads(data)
                # Promote to L1 cache
                self._set_l1(key, value)
                return value
        except Exception:
            pass

        return None

    def set(self, key: str, value: Any, ttl: int = 300):
        # Set in both caches
        self._set_l1(key, value)
        try:
            self.l2_cache.setex(key, ttl, pickle.dumps(value))
        except Exception:
            pass

    def _set_l1(self, key: str, value: Any):
        # Implement LRU eviction for L1 cache
        if len(self.l1_cache) >= self.l1_max_size:
            # Remove oldest item
            oldest_key = next(iter(self.l1_cache))
            del self.l1_cache[oldest_key]

        self.l1_cache[key] = value
```

## Network Optimization

### HTTP/2 and Compression

```python
# Enable HTTP/2 in Uvicorn
uvicorn.run(
    "fxml4.api.main:app",
    host="0.0.0.0",
    port=8000,
    http="h2",  # Enable HTTP/2
    ssl_keyfile="key.pem",
    ssl_certfile="cert.pem"
)

# Compression middleware
from fastapi.middleware.gzip import GZipMiddleware

app.add_middleware(GZipMiddleware, minimum_size=1000)
```

### Connection Pooling

```python
import aiohttp
import asyncio

class OptimizedHTTPClient:
    def __init__(self):
        self.session = None
        self.connector = aiohttp.TCPConnector(
            limit=100,              # Total connection pool size
            limit_per_host=30,      # Connections per host
            ttl_dns_cache=300,      # DNS cache TTL
            use_dns_cache=True,
            keepalive_timeout=30,
            enable_cleanup_closed=True
        )

    async def __aenter__(self):
        self.session = aiohttp.ClientSession(
            connector=self.connector,
            timeout=aiohttp.ClientTimeout(total=30),
            headers={'User-Agent': 'FXML4/1.0'}
        )
        return self.session

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.session.close()

# Usage
async def fetch_external_data():
    async with OptimizedHTTPClient() as session:
        async with session.get('https://api.example.com/data') as response:
            return await response.json()
```

## Monitoring and Profiling

### Application Metrics

```python
from prometheus_client import Counter, Histogram, Gauge, start_http_server
import time

# Define metrics
REQUEST_COUNT = Counter('http_requests_total', 'Total HTTP requests', ['method', 'endpoint', 'status'])
REQUEST_DURATION = Histogram('http_request_duration_seconds', 'HTTP request duration')
ACTIVE_CONNECTIONS = Gauge('active_database_connections', 'Active database connections')
MEMORY_USAGE = Gauge('memory_usage_bytes', 'Memory usage in bytes')

# Middleware for metrics collection
@app.middleware("http")
async def metrics_middleware(request: Request, call_next):
    start_time = time.time()

    response = await call_next(request)

    # Record metrics
    REQUEST_COUNT.labels(
        method=request.method,
        endpoint=request.url.path,
        status=response.status_code
    ).inc()

    REQUEST_DURATION.observe(time.time() - start_time)

    return response

# Background metrics collection
async def collect_system_metrics():
    while True:
        # Collect memory usage
        process = psutil.Process()
        MEMORY_USAGE.set(process.memory_info().rss)

        # Collect database connections
        async with get_db_connection() as conn:
            result = await conn.execute("SELECT count(*) FROM pg_stat_activity")
            ACTIVE_CONNECTIONS.set(result.scalar())

        await asyncio.sleep(10)  # Collect every 10 seconds
```

### Performance Profiling

```python
import cProfile
import pstats
import io
from functools import wraps

def profile_function(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        profiler = cProfile.Profile()
        profiler.enable()

        try:
            result = func(*args, **kwargs)
        finally:
            profiler.disable()

            # Analyze results
            s = io.StringIO()
            ps = pstats.Stats(profiler, stream=s)
            ps.sort_stats('cumulative')
            ps.print_stats(20)  # Top 20 functions

            # Log or save profiling results
            logger.info(f"Profile for {func.__name__}:\n{s.getvalue()}")

        return result
    return wrapper

# Usage
@profile_function
def expensive_backtest_operation(data):
    # Implementation
    pass
```

## Load Testing

### Test Scenarios

```python
# locustfile.py
from locust import HttpUser, task, between
import json
import random

class FXML4User(HttpUser):
    wait_time = between(1, 3)

    def on_start(self):
        # Login and get token
        response = self.client.post("/token", data={
            "username": "test_user",
            "password": "test_password"
        })
        self.token = response.json()["access_token"]
        self.headers = {"Authorization": f"Bearer {self.token}"}

    @task(3)
    def get_market_data(self):
        symbols = ["EURUSD", "GBPUSD", "USDCHF", "USDJPY"]
        timeframes = ["1h", "4h", "1d"]

        self.client.post("/data",
            headers=self.headers,
            json={
                "symbol": random.choice(symbols),
                "timeframe": random.choice(timeframes),
                "limit": random.randint(100, 1000)
            }
        )

    @task(2)
    def generate_signals(self):
        self.client.post("/signals",
            headers=self.headers,
            json={
                "symbol": "EURUSD",
                "timeframe": "4h",
                "strategy": "ml_strategy"
            }
        )

    @task(1)
    def run_backtest(self):
        self.client.post("/backtest",
            headers=self.headers,
            json={
                "symbol": "EURUSD",
                "timeframe": "1h",
                "strategy": "integrated_strategy",
                "start_date": "2023-01-01",
                "end_date": "2023-03-31",
                "initial_capital": 10000
            }
        )
```

### Load Testing Commands

```bash
# Run load test with increasing user load
locust -f locustfile.py --host=http://localhost:8000

# Automated load test
locust -f locustfile.py --host=http://localhost:8000 \
    --users 100 --spawn-rate 10 --run-time 5m --html report.html

# Distributed load testing
# Master node
locust -f locustfile.py --master --host=http://api.fxml4.com

# Worker nodes
locust -f locustfile.py --worker --master-host=<master-ip>
```

### Performance Benchmarking

```bash
#!/bin/bash
# benchmark.sh

echo "=== FXML4 Performance Benchmark ==="

# API endpoint response times
echo "Testing API endpoints..."
ab -n 1000 -c 10 -H "Authorization: Bearer $TOKEN" \
   http://localhost:8000/health

# Database query performance
echo "Testing database performance..."
psql -h localhost -U postgres -d fxml4 -c "\timing on" -c "
SELECT COUNT(*) FROM market_data WHERE timestamp > NOW() - INTERVAL '1 day';
"

# Memory usage under load
echo "Testing memory usage..."
docker stats --no-stream fxml4_api_1

# Concurrent backtest performance
echo "Testing concurrent backtests..."
for i in {1..5}; do
    curl -X POST http://localhost:8000/backtest \
         -H "Authorization: Bearer $TOKEN" \
         -H "Content-Type: application/json" \
         -d '{
           "symbol": "EURUSD",
           "timeframe": "1h",
           "strategy": "ml_strategy",
           "start_date": "2023-01-01",
           "end_date": "2023-03-31"
         }' &
done
wait

echo "Benchmark complete"
```

## Performance Monitoring Dashboard

### Grafana Dashboard Configuration

```json
{
  "dashboard": {
    "title": "FXML4 Performance Dashboard",
    "panels": [
      {
        "title": "API Response Times",
        "type": "graph",
        "targets": [
          {
            "expr": "histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m]))",
            "legendFormat": "95th percentile"
          }
        ]
      },
      {
        "title": "Database Performance",
        "type": "graph",
        "targets": [
          {
            "expr": "rate(pg_stat_database_tup_fetched[5m])",
            "legendFormat": "Tuples fetched/sec"
          }
        ]
      },
      {
        "title": "Memory Usage",
        "type": "graph",
        "targets": [
          {
            "expr": "process_resident_memory_bytes",
            "legendFormat": "RSS Memory"
          }
        ]
      }
    ]
  }
}
```

This comprehensive performance tuning guide provides strategies for optimizing every aspect of the FXML4 platform. Regular monitoring and iterative improvements based on these recommendations will ensure optimal performance in production environments.
