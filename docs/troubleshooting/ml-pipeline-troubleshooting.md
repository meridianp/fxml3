# ML Trading Pipeline Troubleshooting Guide

## Overview

This comprehensive troubleshooting guide covers common issues, diagnostic procedures, and solutions for the ML Trading Pipeline. The guide is organized by component and symptom to help quickly identify and resolve problems.

## Quick Diagnostic Checklist

### Initial Health Check

Before diving into specific issues, run this quick diagnostic checklist:

```bash
# 1. Check ML pipeline status
curl -X GET http://localhost:8080/api/ml/health

# 2. Verify environment variables
env | grep ML_

# 3. Check log files
tail -f /app/logs/ml_pipeline.log

# 4. Verify database connectivity
psql -h localhost -U ml_user -d fxml4_ml -c "SELECT COUNT(*) FROM ml_signals;"

# 5. Check model files
ls -la /app/models/

# 6. Test WebSocket connection
wscat -c ws://localhost:8080/ws/ml
```

### System Requirements Verification

```python
# system_check.py
import psutil
import platform
import sys

def check_system_requirements():
    """Verify system meets ML pipeline requirements."""
    checks = {}

    # Python version
    checks['python_version'] = sys.version_info >= (3, 9)

    # Memory
    memory_gb = psutil.virtual_memory().total / (1024**3)
    checks['memory'] = memory_gb >= 8

    # CPU cores
    checks['cpu_cores'] = psutil.cpu_count() >= 4

    # Disk space
    disk_gb = psutil.disk_usage('/').free / (1024**3)
    checks['disk_space'] = disk_gb >= 10

    return checks

if __name__ == "__main__":
    results = check_system_requirements()
    for check, passed in results.items():
        status = "✓" if passed else "✗"
        print(f"{status} {check}: {passed}")
```

## Common Issues and Solutions

### 1. Pipeline Startup Issues

#### Issue: ML Pipeline Fails to Start

**Symptoms:**
- Error: "MLTradingPipeline initialization failed"
- No signals generated
- WebSocket connection refused

**Diagnostic Steps:**

```bash
# Check if ML is enabled
echo $ML_ENABLED

# Verify configuration
python -c "
from core.config.ml_config import MLConfig
config = MLConfig()
print(config.ml_config)
"

# Check for missing dependencies
pip check

# Verify model files exist
ls -la $ML_MODEL_PATH/
```

**Common Causes and Solutions:**

1. **Missing Environment Variables**
   ```bash
   # Solution: Set required variables
   export ML_ENABLED=true
   export ML_MODELS=random_forest,xgboost
   export ML_CONFIDENCE_THRESHOLD=0.7
   ```

2. **Missing Model Files**
   ```bash
   # Solution: Download or train models
   python scripts/download_models.py
   # Or train new models
   python scripts/train_models.py
   ```

3. **Database Connection Issues**
   ```bash
   # Solution: Check database connectivity
   psql -h $ML_DB_HOST -U $ML_DB_USER -d $ML_DB_NAME -c "\dt"

   # Create missing tables
   python scripts/create_ml_tables.py
   ```

4. **Port Conflicts**
   ```bash
   # Solution: Check and change ports
   netstat -tulpn | grep :8080
   export ML_WEBSOCKET_PORT=8081
   ```

#### Issue: ImportError for ML Dependencies

**Symptoms:**
- "ModuleNotFoundError: No module named 'sklearn'"
- "ImportError: cannot import name 'XGBClassifier'"

**Solution:**
```bash
# Install missing dependencies
pip install -r requirements-ml.txt

# For conda environments
conda install scikit-learn xgboost tensorflow

# Verify installations
python -c "import sklearn, xgboost, tensorflow; print('All ML libraries installed')"
```

### 2. Feature Extraction Issues

#### Issue: Feature Extraction Takes Too Long

**Symptoms:**
- Processing latency > 50ms
- Timeout errors in logs
- Memory usage spikes

**Diagnostic Steps:**

```python
# Profile feature extraction
import time
import cProfile

def profile_feature_extraction():
    from core.ml.feature_extractor import FeatureExtractor
    import pandas as pd
    import numpy as np

    # Create test data
    data = pd.DataFrame({
        'open': np.random.uniform(1.08, 1.10, 1000),
        'high': np.random.uniform(1.09, 1.11, 1000),
        'low': np.random.uniform(1.07, 1.09, 1000),
        'close': np.random.uniform(1.08, 1.10, 1000),
        'volume': np.random.randint(1000, 10000, 1000)
    })

    extractor = FeatureExtractor()

    start_time = time.perf_counter()
    features = extractor.extract_technical_features(data)
    end_time = time.perf_counter()

    print(f"Feature extraction took: {(end_time - start_time) * 1000:.2f}ms")
    print(f"Features extracted: {len(features.columns)}")

    return features

# Run profiling
cProfile.run('profile_feature_extraction()')
```

**Solutions:**

1. **Optimize Data Size**
   ```python
   # Reduce lookback period
   config = {
       'lookback_period': 50,  # Instead of 100+
       'features': ['sma', 'rsi']  # Only essential features
   }
   ```

2. **Enable Caching**
   ```python
   # Enable feature caching
   export ML_CACHE_TTL=300  # 5 minutes
   export ML_FEATURE_CACHE_ENABLED=true
   ```

3. **Parallel Processing**
   ```python
   # Enable parallel feature extraction
   feature_config = {
       'parallel_processing': True,
       'max_workers': 2
   }
   ```

#### Issue: NaN Values in Features

**Symptoms:**
- "ValueError: Input contains NaN"
- Model prediction failures
- Inconsistent signal generation

**Diagnostic Steps:**

```python
# Check for NaN values
def diagnose_nan_features(market_data):
    from core.ml.feature_extractor import FeatureExtractor

    extractor = FeatureExtractor()
    features = extractor.extract_technical_features(market_data)

    # Check for NaN values
    nan_columns = features.columns[features.isnull().any()].tolist()

    if nan_columns:
        print(f"NaN values found in columns: {nan_columns}")
        for col in nan_columns:
            nan_count = features[col].isnull().sum()
            print(f"  {col}: {nan_count} NaN values")
    else:
        print("No NaN values found")

    return features
```

**Solutions:**

1. **Insufficient Data**
   ```python
   # Ensure minimum data points
   if len(market_data) < 50:
       # Wait for more data or use fallback
       return None
   ```

2. **Division by Zero**
   ```python
   # Safe division in feature calculations
   features['volume_ratio'] = market_data['volume'] / features['volume_sma'].replace(0, 1)
   ```

3. **Forward Fill Strategy**
   ```python
   # Improve NaN handling
   features.ffill(inplace=True)
   features.fillna(method='bfill', inplace=True)
   features.fillna(0, inplace=True)  # Final fallback
   ```

### 3. Model Prediction Issues

#### Issue: Model Loading Failures

**Symptoms:**
- "FileNotFoundError: Model file not found"
- "Model failed to load"
- Ensemble prediction returns None

**Diagnostic Steps:**

```bash
# Check model directory
ls -la $ML_MODEL_PATH/

# Verify model file integrity
python -c "
import pickle
import os

model_path = os.environ.get('ML_MODEL_PATH', '/app/models')
for model_file in os.listdir(model_path):
    if model_file.endswith('.pkl'):
        try:
            with open(os.path.join(model_path, model_file), 'rb') as f:
                model = pickle.load(f)
            print(f'✓ {model_file}: OK')
        except Exception as e:
            print(f'✗ {model_file}: {e}')
"
```

**Solutions:**

1. **Download/Retrain Models**
   ```bash
   # Download pre-trained models
   python scripts/download_models.py

   # Or retrain from scratch
   python scripts/train_models.py --all
   ```

2. **Fix Model Paths**
   ```bash
   # Ensure correct model path
   export ML_MODEL_PATH=/app/models
   mkdir -p $ML_MODEL_PATH
   ```

3. **Model Compatibility**
   ```python
   # Check sklearn version compatibility
   import sklearn
   print(f"scikit-learn version: {sklearn.__version__}")

   # Retrain with current sklearn version if needed
   ```

#### Issue: Prediction Timeout

**Symptoms:**
- "Prediction timeout after 5 seconds"
- High CPU usage during prediction
- Memory leaks

**Diagnostic Steps:**

```python
# Profile model prediction
import time
import psutil
import os

def profile_model_prediction():
    from core.ml.model_predictor import ModelPredictor
    import numpy as np

    predictor = ModelPredictor()
    features = np.random.random((1, 10))

    # Monitor resources
    process = psutil.Process(os.getpid())
    start_memory = process.memory_info().rss / 1024 / 1024
    start_time = time.perf_counter()

    try:
        prediction = predictor.predict_ensemble(features)
        success = True
    except Exception as e:
        print(f"Prediction failed: {e}")
        success = False

    end_time = time.perf_counter()
    end_memory = process.memory_info().rss / 1024 / 1024

    print(f"Prediction time: {(end_time - start_time) * 1000:.2f}ms")
    print(f"Memory usage: {end_memory - start_memory:.2f}MB")
    print(f"Success: {success}")

profile_model_prediction()
```

**Solutions:**

1. **Reduce Model Complexity**
   ```python
   # Use fewer ensemble models
   config = {
       'models': ['random_forest'],  # Instead of all three
       'timeout': 10.0  # Increase timeout
   }
   ```

2. **Optimize Model Parameters**
   ```python
   # Reduce model complexity
   rf_config = {
       'n_estimators': 50,  # Instead of 100
       'max_depth': 5       # Instead of 10
   }
   ```

3. **Enable Model Caching**
   ```python
   # Cache predictions
   export ML_PREDICTION_CACHE_ENABLED=true
   export ML_PREDICTION_CACHE_TTL=60
   ```

#### Issue: Inconsistent Predictions

**Symptoms:**
- Large prediction variance for same input
- Model agreement score < 60%
- Confidence scores fluctuate wildly

**Diagnostic Steps:**

```python
# Test prediction consistency
def test_prediction_consistency():
    from core.ml.model_predictor import ModelPredictor
    import numpy as np

    predictor = ModelPredictor()
    features = np.random.random((1, 10))

    predictions = []
    for i in range(10):
        pred = predictor.predict_ensemble(features)
        predictions.append(pred['prediction'])

    variance = np.var(predictions)
    print(f"Prediction variance: {variance:.6f}")
    print(f"Predictions: {predictions}")

    if variance > 0.01:
        print("⚠️  High prediction variance detected")
    else:
        print("✓ Predictions are consistent")

test_prediction_consistency()
```

**Solutions:**

1. **Set Random Seeds**
   ```python
   # Ensure reproducible predictions
   model_config = {
       'random_forest': {'random_state': 42},
       'xgboost': {'random_state': 42}
   }
   ```

2. **Check Model Training**
   ```python
   # Retrain models with more data
   python scripts/train_models.py --data-size 10000
   ```

3. **Feature Standardization**
   ```python
   # Ensure consistent feature scaling
   features = extractor.normalize_features(features)
   ```

### 4. Signal Generation Issues

#### Issue: No Signals Generated

**Symptoms:**
- Signal count = 0 for extended periods
- All signals marked as "HOLD"
- Confidence scores below threshold

**Diagnostic Steps:**

```python
# Debug signal generation
def debug_signal_generation():
    from core.ml.ml_trading_pipeline import MLTradingPipeline
    import pandas as pd
    import numpy as np

    # Create test data
    market_data = pd.DataFrame({
        'timestamp': pd.date_range('2024-01-01', periods=100, freq='1h'),
        'open': [1.0850] * 100,
        'high': [1.0870] * 100,
        'low': [1.0830] * 100,
        'close': [1.0860] * 100,
        'volume': [1000] * 100,
        'symbol': ['EUR/USD'] * 100
    })

    pipeline = MLTradingPipeline({
        'confidence_threshold': 0.5  # Lower threshold for testing
    })

    # Step by step debugging
    print("1. Extracting features...")
    features = pipeline.feature_extractor.extract_technical_features(market_data)
    print(f"   Features shape: {features.shape}")
    print(f"   Feature columns: {list(features.columns)}")

    print("2. Making predictions...")
    features_array = features.fillna(0).values[-1].reshape(1, -1)
    prediction = pipeline.model_predictor.predict_ensemble(features_array)
    print(f"   Prediction: {prediction}")

    print("3. Generating signal...")
    signal = pipeline.signal_generator.generate_signal(
        symbol='EUR/USD',
        prediction=prediction,
        current_price=1.0860
    )
    print(f"   Signal: {signal}")

debug_signal_generation()
```

**Solutions:**

1. **Lower Confidence Threshold**
   ```bash
   # Temporarily lower threshold for testing
   export ML_CONFIDENCE_THRESHOLD=0.5
   ```

2. **Check Signal Logic**
   ```python
   # Review signal generation criteria
   if prediction['prediction'] > 0.7 and prediction['confidence'] > 0.7:
       signal_type = 'BUY'
   elif prediction['prediction'] < 0.3 and prediction['confidence'] > 0.7:
       signal_type = 'SELL'
   else:
       signal_type = 'HOLD'
   ```

3. **Verify Market Conditions**
   ```python
   # Check if market data is realistic
   # Ensure sufficient volatility for signal generation
   volatility = market_data['close'].pct_change().std()
   print(f"Market volatility: {volatility:.6f}")
   ```

#### Issue: Too Many Signals Generated

**Symptoms:**
- Signal rate > 30 per hour
- Many low-confidence signals
- Risk management blocking signals

**Solutions:**

1. **Increase Confidence Threshold**
   ```bash
   export ML_CONFIDENCE_THRESHOLD=0.8
   ```

2. **Add Signal Filtering**
   ```python
   # Add minimum time between signals
   signal_config = {
       'min_time_between_signals': 300,  # 5 minutes
       'max_signals_per_hour': 10
   }
   ```

3. **Improve Risk Management**
   ```python
   # Reduce position sizes
   export ML_MAX_POSITION_SIZE=0.02  # 2% instead of 5%
   ```

### 5. WebSocket Connection Issues

#### Issue: WebSocket Connection Drops

**Symptoms:**
- "WebSocket connection closed"
- Clients disconnecting frequently
- No real-time signal updates

**Diagnostic Steps:**

```bash
# Test WebSocket connectivity
wscat -c ws://localhost:8080/ws/ml

# Check WebSocket server logs
grep -i websocket /app/logs/ml_pipeline.log

# Test with curl
curl -i -N -H "Connection: Upgrade" \
     -H "Upgrade: websocket" \
     -H "Sec-WebSocket-Key: test" \
     -H "Sec-WebSocket-Version: 13" \
     http://localhost:8080/ws/ml
```

**Solutions:**

1. **Check Network Configuration**
   ```bash
   # Verify firewall settings
   sudo ufw status

   # Check if port is open
   netstat -tulpn | grep :8080
   ```

2. **Increase Connection Limits**
   ```bash
   export ML_MAX_WEBSOCKET_CONNECTIONS=1000
   export ML_WEBSOCKET_TIMEOUT=300
   ```

3. **Enable Keep-Alive**
   ```python
   # WebSocket keep-alive configuration
   websocket_config = {
       'ping_interval': 30,
       'ping_timeout': 10,
       'max_message_size': 1024 * 1024  # 1MB
   }
   ```

#### Issue: Authentication Failures

**Symptoms:**
- "401 Unauthorized" errors
- JWT token validation failures
- Connection rejected

**Solutions:**

1. **Check JWT Configuration**
   ```bash
   # Verify JWT secret
   echo $JWT_SECRET_KEY

   # Test token generation
   python -c "
   from core.auth.jwt_manager import JWTManager
   jwt_manager = JWTManager()
   token = jwt_manager.generate_token({'user_id': 'test'})
   print(f'Test token: {token}')
   "
   ```

2. **Update Client Authentication**
   ```javascript
   // Ensure client sends proper authentication
   const ws = new WebSocket('ws://localhost:8080/ws/ml', [], {
     headers: {
       'Authorization': `Bearer ${jwt_token}`
     }
   });
   ```

### 6. Database Issues

#### Issue: Database Connection Failures

**Symptoms:**
- "Connection to database failed"
- "Too many connections"
- Slow query performance

**Diagnostic Steps:**

```bash
# Test database connectivity
psql -h $ML_DB_HOST -U $ML_DB_USER -d $ML_DB_NAME -c "SELECT version();"

# Check connection pool
psql -h $ML_DB_HOST -U $ML_DB_USER -d $ML_DB_NAME -c "
SELECT count(*) as connections, state
FROM pg_stat_activity
WHERE datname = '$ML_DB_NAME'
GROUP BY state;
"

# Check table sizes
psql -h $ML_DB_HOST -U $ML_DB_USER -d $ML_DB_NAME -c "
SELECT schemaname, tablename,
       pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) as size
FROM pg_tables
WHERE tablename LIKE 'ml_%'
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;
"
```

**Solutions:**

1. **Optimize Connection Pool**
   ```bash
   export ML_DB_POOL_SIZE=10
   export ML_DB_MAX_OVERFLOW=20
   export ML_DB_POOL_TIMEOUT=30
   ```

2. **Add Database Indexes**
   ```sql
   -- Add missing indexes
   CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_ml_signals_symbol_created
   ON ml_signals(symbol, created_at);

   CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_ml_signals_confidence
   ON ml_signals(confidence) WHERE confidence > 0.7;
   ```

3. **Database Cleanup**
   ```sql
   -- Clean old data
   DELETE FROM ml_signals
   WHERE created_at < NOW() - INTERVAL '30 days'
   AND status = 'COMPLETED';

   VACUUM ANALYZE ml_signals;
   ```

### 7. Performance Issues

#### Issue: High Memory Usage

**Symptoms:**
- Memory usage > 1GB
- OutOfMemory errors
- System becomes unresponsive

**Diagnostic Steps:**

```python
# Memory profiling
import tracemalloc
import psutil
import os

def profile_memory_usage():
    tracemalloc.start()

    # Your ML pipeline code here
    from core.ml.ml_trading_pipeline import MLTradingPipeline
    pipeline = MLTradingPipeline()

    # Process some data
    # ... pipeline operations ...

    current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    process = psutil.Process(os.getpid())
    system_memory = process.memory_info().rss / 1024 / 1024

    print(f"Traced memory - Current: {current / 1024 / 1024:.2f}MB, Peak: {peak / 1024 / 1024:.2f}MB")
    print(f"System memory: {system_memory:.2f}MB")

profile_memory_usage()
```

**Solutions:**

1. **Implement Memory Limits**
   ```bash
   export ML_MEMORY_LIMIT_MB=500
   export ML_CACHE_MAX_SIZE_MB=100
   ```

2. **Enable Garbage Collection**
   ```python
   import gc

   # Force garbage collection after processing
   gc.collect()
   ```

3. **Optimize Data Structures**
   ```python
   # Use more memory-efficient data types
   market_data = market_data.astype({
       'open': 'float32',
       'high': 'float32',
       'low': 'float32',
       'close': 'float32',
       'volume': 'int32'
   })
   ```

#### Issue: High CPU Usage

**Symptoms:**
- CPU usage > 90%
- Slow response times
- System lag

**Solutions:**

1. **Limit Worker Threads**
   ```bash
   export ML_MAX_WORKERS=2
   export ML_ASYNC_PROCESSING=false
   ```

2. **Optimize Model Complexity**
   ```python
   # Reduce model complexity
   model_config = {
       'random_forest': {'n_estimators': 50, 'n_jobs': 2},
       'xgboost': {'n_estimators': 50, 'nthread': 2}
   }
   ```

3. **Implement Rate Limiting**
   ```python
   # Add rate limiting
   import asyncio

   async def process_with_rate_limit():
       await asyncio.sleep(0.1)  # 100ms delay between operations
   ```

## Emergency Procedures

### Pipeline Recovery

```bash
#!/bin/bash
# emergency_recovery.sh

echo "Starting ML Pipeline Emergency Recovery..."

# 1. Stop pipeline
echo "Stopping ML pipeline..."
pkill -f "ml_trading_pipeline"

# 2. Clear cache
echo "Clearing cache..."
redis-cli FLUSHDB

# 3. Reset database connections
echo "Resetting database connections..."
psql -h $ML_DB_HOST -U $ML_DB_USER -d $ML_DB_NAME -c "
SELECT pg_terminate_backend(pid)
FROM pg_stat_activity
WHERE datname = '$ML_DB_NAME' AND pid <> pg_backend_pid();
"

# 4. Clean temporary files
echo "Cleaning temporary files..."
rm -rf /tmp/ml_*
rm -rf /app/cache/*

# 5. Restart with minimal configuration
echo "Restarting with minimal configuration..."
export ML_MODELS=random_forest
export ML_CONFIDENCE_THRESHOLD=0.8
export ML_MAX_WORKERS=1

python -m core.ml.ml_trading_pipeline &

echo "Recovery complete. Check logs for status."
```

### Data Corruption Recovery

```sql
-- data_recovery.sql

-- Check for data corruption
SELECT
    'ml_signals' as table_name,
    COUNT(*) as total_records,
    COUNT(*) FILTER (WHERE confidence IS NULL) as null_confidence,
    COUNT(*) FILTER (WHERE signal_type NOT IN ('BUY', 'SELL', 'HOLD')) as invalid_signals
FROM ml_signals

UNION ALL

SELECT
    'ml_model_performance',
    COUNT(*),
    COUNT(*) FILTER (WHERE accuracy IS NULL),
    COUNT(*) FILTER (WHERE accuracy < 0 OR accuracy > 1)
FROM ml_model_performance;

-- Clean corrupted data
DELETE FROM ml_signals
WHERE confidence IS NULL
   OR signal_type NOT IN ('BUY', 'SELL', 'HOLD')
   OR position_size < 0
   OR position_size > 1;

DELETE FROM ml_model_performance
WHERE accuracy IS NULL
   OR accuracy < 0
   OR accuracy > 1;

-- Rebuild indexes
REINDEX TABLE ml_signals;
REINDEX TABLE ml_model_performance;

-- Update statistics
ANALYZE ml_signals;
ANALYZE ml_model_performance;
```

## Monitoring and Alerting

### Health Check Script

```python
#!/usr/bin/env python3
# health_check.py

import asyncio
import aiohttp
import sys
from datetime import datetime, timedelta

async def health_check():
    """Comprehensive health check for ML pipeline."""

    checks = {
        'api_health': False,
        'websocket': False,
        'database': False,
        'signal_generation': False,
        'model_performance': False
    }

    try:
        # 1. API Health Check
        async with aiohttp.ClientSession() as session:
            async with session.get('http://localhost:8080/api/ml/health', timeout=5) as response:
                if response.status == 200:
                    checks['api_health'] = True

        # 2. WebSocket Check
        import websockets
        try:
            async with websockets.connect('ws://localhost:8080/ws/ml', timeout=5):
                checks['websocket'] = True
        except:
            pass

        # 3. Database Check
        import asyncpg
        try:
            conn = await asyncpg.connect(
                host='localhost',
                user='ml_user',
                password='ml_password',
                database='fxml4_ml'
            )
            await conn.execute('SELECT 1')
            await conn.close()
            checks['database'] = True
        except:
            pass

        # 4. Recent Signal Check
        if checks['database']:
            conn = await asyncpg.connect(
                host='localhost',
                user='ml_user',
                password='ml_password',
                database='fxml4_ml'
            )

            # Check for signals in last hour
            recent_signals = await conn.fetchval("""
                SELECT COUNT(*) FROM ml_signals
                WHERE created_at > NOW() - INTERVAL '1 hour'
            """)

            checks['signal_generation'] = recent_signals > 0

            # Check model performance
            avg_accuracy = await conn.fetchval("""
                SELECT AVG(accuracy) FROM ml_model_performance
                WHERE timestamp > NOW() - INTERVAL '24 hours'
            """)

            checks['model_performance'] = avg_accuracy and avg_accuracy > 0.5

            await conn.close()

    except Exception as e:
        print(f"Health check error: {e}")

    # Report results
    all_healthy = all(checks.values())

    print(f"ML Pipeline Health Check - {datetime.now()}")
    print("=" * 50)

    for check, status in checks.items():
        icon = "✓" if status else "✗"
        print(f"{icon} {check.replace('_', ' ').title()}: {'PASS' if status else 'FAIL'}")

    print("=" * 50)
    print(f"Overall Status: {'HEALTHY' if all_healthy else 'UNHEALTHY'}")

    return 0 if all_healthy else 1

if __name__ == "__main__":
    exit_code = asyncio.run(health_check())
    sys.exit(exit_code)
```

### Log Analysis Script

```bash
#!/bin/bash
# analyze_logs.sh

LOG_FILE="/app/logs/ml_pipeline.log"
HOURS=${1:-1}  # Default to last 1 hour

echo "Analyzing ML Pipeline logs for the last $HOURS hour(s)..."
echo "=================================================="

# Error analysis
echo -e "\n🔴 ERRORS:"
grep -i "error\|exception\|fail" "$LOG_FILE" | tail -20

# Performance analysis
echo -e "\n⚡ PERFORMANCE:"
echo "Average processing times:"
grep "processing_time_ms" "$LOG_FILE" | \
awk -F'processing_time_ms":' '{print $2}' | \
awk -F',' '{sum+=$1; count++} END {if(count>0) print "Average:", sum/count "ms"}'

# Signal analysis
echo -e "\n📊 SIGNALS:"
echo "Signals generated in last $HOURS hour(s):"
grep "signal_generated" "$LOG_FILE" | \
awk -F'"signal":"' '{print $2}' | \
awk -F'"' '{print $1}' | \
sort | uniq -c

# Model performance
echo -e "\n🤖 MODEL PERFORMANCE:"
echo "Model accuracy over time:"
grep "model_accuracy" "$LOG_FILE" | tail -10

echo -e "\n✅ Analysis complete"
```

This comprehensive troubleshooting guide provides solutions for the most common issues encountered with the ML Trading Pipeline. For issues not covered here, enable debug logging and examine the detailed error messages for specific guidance.