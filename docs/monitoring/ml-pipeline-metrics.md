# ML Trading Pipeline Performance Metrics & Monitoring

## Overview

This document provides comprehensive guidance on monitoring and measuring the performance of the ML Trading Pipeline. It covers key performance indicators (KPIs), monitoring infrastructure, alerting strategies, and performance optimization techniques.

## Key Performance Indicators (KPIs)

### Trading Performance Metrics

#### Signal Quality Metrics

**Signal Generation Rate**
- **Metric**: Signals per hour/day
- **Target**: 5-15 signals per symbol per day
- **Measurement**: Count of signals generated with confidence > threshold
- **Alert Threshold**: < 2 signals/day or > 30 signals/day

```python
signal_generation_rate = total_signals / time_period_hours
```

**Signal Accuracy**
- **Metric**: Percentage of profitable signals
- **Target**: > 55% accuracy
- **Measurement**: (Profitable signals / Total signals) * 100
- **Alert Threshold**: < 50% over 24-hour period

```python
signal_accuracy = profitable_signals / total_signals * 100
```

**Signal Confidence Distribution**
- **Metric**: Average confidence score
- **Target**: 0.75-0.85 average confidence
- **Measurement**: Mean confidence of generated signals
- **Alert Threshold**: < 0.7 average confidence

```python
avg_confidence = sum(confidence_scores) / len(confidence_scores)
```

#### Risk-Adjusted Returns

**Sharpe Ratio**
- **Metric**: Risk-adjusted return measure
- **Target**: > 1.5
- **Calculation**: (Return - Risk_free_rate) / Volatility
- **Frequency**: Daily, Weekly, Monthly

```python
sharpe_ratio = (portfolio_return - risk_free_rate) / portfolio_volatility
```

**Maximum Drawdown**
- **Metric**: Largest peak-to-trough decline
- **Target**: < 5%
- **Measurement**: Max decline from peak equity
- **Alert Threshold**: > 3%

```python
max_drawdown = (peak_value - trough_value) / peak_value * 100
```

**Profit Factor**
- **Metric**: Gross profit / Gross loss
- **Target**: > 1.3
- **Calculation**: Total winning trades / Total losing trades
- **Alert Threshold**: < 1.1

```python
profit_factor = total_gross_profit / total_gross_loss
```

### Technical Performance Metrics

#### Latency Metrics

**End-to-End Processing Latency**
- **Metric**: Time from data input to signal output
- **Target**: < 10ms (P99)
- **Components**: Feature extraction + Model prediction + Signal generation
- **Alert Threshold**: > 50ms (P95)

**Component-Level Latency**
```python
latency_metrics = {
    'feature_extraction': 2-5,    # milliseconds
    'model_prediction': 1-3,      # milliseconds
    'signal_generation': 0.5-1,   # milliseconds
    'database_write': 1-2,        # milliseconds
    'websocket_broadcast': 1-3    # milliseconds
}
```

**Data Feed Latency**
- **Metric**: Time from market event to data availability
- **Target**: < 100ms
- **Measurement**: Timestamp difference analysis
- **Alert Threshold**: > 500ms

#### Throughput Metrics

**Market Data Processing Rate**
- **Metric**: Data points processed per second
- **Target**: > 1000 updates/second
- **Measurement**: Count of processed data points
- **Alert Threshold**: < 500 updates/second

**Concurrent Symbol Support**
- **Metric**: Number of symbols processed simultaneously
- **Target**: 50+ currency pairs
- **Measurement**: Active symbol count
- **Alert Threshold**: Processing delays on > 10 symbols

#### Resource Utilization

**Memory Usage**
- **Metric**: RAM consumption by component
- **Target**: < 500MB total pipeline
- **Components**: Features (100MB), Models (200MB), Cache (100MB)
- **Alert Threshold**: > 1GB total usage

```python
memory_allocation = {
    'feature_cache': 100,      # MB
    'model_memory': 200,       # MB
    'prediction_cache': 50,    # MB
    'websocket_buffers': 50,   # MB
    'database_pool': 50,       # MB
    'overhead': 50            # MB
}
```

**CPU Usage**
- **Metric**: CPU utilization percentage
- **Target**: < 70% average usage
- **Measurement**: System CPU monitoring
- **Alert Threshold**: > 85% sustained usage

**GPU Usage** (if applicable)
- **Metric**: GPU utilization for LSTM models
- **Target**: 60-80% during training
- **Measurement**: nvidia-smi or equivalent
- **Alert Threshold**: > 95% or < 10% utilization

### Model Performance Metrics

#### Accuracy Metrics

**Individual Model Accuracy**
- **Random Forest**: Target > 60%
- **XGBoost**: Target > 65%
- **LSTM**: Target > 58%

**Ensemble Accuracy**
- **Metric**: Combined model accuracy
- **Target**: > 65%
- **Measurement**: Ensemble prediction accuracy
- **Alert Threshold**: < 55%

**Model Agreement Score**
- **Metric**: Agreement between models
- **Target**: 70-90%
- **Calculation**: Percentage of predictions where models agree
- **Alert Threshold**: < 60% or > 95%

```python
model_agreement = (
    len(predictions_where_models_agree) /
    total_predictions * 100
)
```

#### Prediction Quality

**Confidence Calibration**
- **Metric**: How well confidence scores match actual accuracy
- **Target**: Confidence ≈ Accuracy ± 5%
- **Measurement**: Brier score or reliability diagram
- **Alert Threshold**: Difference > 10%

**Prediction Stability**
- **Metric**: Consistency of predictions over time
- **Target**: < 10% prediction variance for same inputs
- **Measurement**: Standard deviation of repeated predictions
- **Alert Threshold**: > 15% variance

#### Model Drift Detection

**Data Drift Score**
- **Metric**: Statistical difference between training and live data
- **Target**: < 0.1 (Kolmogorov-Smirnov statistic)
- **Measurement**: KS test between distributions
- **Alert Threshold**: > 0.3

**Concept Drift Score**
- **Metric**: Change in prediction patterns
- **Target**: < 0.05 drift per week
- **Measurement**: Population Stability Index (PSI)
- **Alert Threshold**: > 0.25

```python
# Population Stability Index calculation
def calculate_psi(expected, actual, buckets=10):
    expected_percents = pd.cut(expected, buckets).value_counts() / len(expected)
    actual_percents = pd.cut(actual, buckets).value_counts() / len(actual)

    psi = sum((actual_percents - expected_percents) *
              np.log(actual_percents / expected_percents))
    return psi
```

## Monitoring Infrastructure

### Prometheus Metrics

#### Custom ML Metrics

```python
from prometheus_client import Counter, Histogram, Gauge

# Signal generation metrics
ml_signals_generated = Counter(
    'ml_signals_generated_total',
    'Total number of ML signals generated',
    ['symbol', 'signal_type', 'model']
)

ml_signal_confidence = Histogram(
    'ml_signal_confidence',
    'ML signal confidence scores',
    ['symbol', 'model'],
    buckets=[0.5, 0.6, 0.7, 0.8, 0.9, 1.0]
)

# Performance metrics
ml_processing_latency = Histogram(
    'ml_processing_latency_seconds',
    'ML pipeline processing latency',
    ['component', 'symbol'],
    buckets=[0.001, 0.005, 0.01, 0.05, 0.1, 0.5]
)

ml_model_accuracy = Gauge(
    'ml_model_accuracy',
    'Current model accuracy',
    ['model', 'symbol', 'timeframe']
)

# Resource utilization
ml_memory_usage = Gauge(
    'ml_memory_usage_bytes',
    'ML pipeline memory usage',
    ['component']
)

ml_cpu_usage = Gauge(
    'ml_cpu_usage_percent',
    'ML pipeline CPU usage',
    ['component']
)

# Error metrics
ml_errors_total = Counter(
    'ml_errors_total',
    'Total ML pipeline errors',
    ['component', 'error_type']
)

ml_model_drift_score = Gauge(
    'ml_model_drift_score',
    'Model drift detection score',
    ['model', 'symbol']
)
```

#### System Metrics Integration

```yaml
# prometheus.yml configuration
global:
  scrape_interval: 15s
  evaluation_interval: 15s

rule_files:
  - "ml_rules.yml"

scrape_configs:
  - job_name: 'ml-pipeline'
    static_configs:
      - targets: ['localhost:9090']
    scrape_interval: 5s
    metrics_path: /metrics

  - job_name: 'ml-websocket'
    static_configs:
      - targets: ['localhost:8080']
    metrics_path: /ws/metrics

alerting:
  alertmanagers:
    - static_configs:
        - targets:
          - alertmanager:9093
```

### Grafana Dashboards

#### ML Pipeline Overview Dashboard

```json
{
  "dashboard": {
    "title": "ML Trading Pipeline Overview",
    "panels": [
      {
        "title": "Signal Generation Rate",
        "type": "stat",
        "targets": [
          {
            "expr": "rate(ml_signals_generated_total[5m])",
            "legendFormat": "{{symbol}} - {{signal_type}}"
          }
        ]
      },
      {
        "title": "Processing Latency",
        "type": "graph",
        "targets": [
          {
            "expr": "histogram_quantile(0.95, ml_processing_latency_seconds)",
            "legendFormat": "P95 - {{component}}"
          }
        ]
      },
      {
        "title": "Model Accuracy",
        "type": "graph",
        "targets": [
          {
            "expr": "ml_model_accuracy",
            "legendFormat": "{{model}} - {{symbol}}"
          }
        ]
      },
      {
        "title": "Memory Usage",
        "type": "graph",
        "targets": [
          {
            "expr": "ml_memory_usage_bytes / 1024 / 1024",
            "legendFormat": "{{component}} (MB)"
          }
        ]
      }
    ]
  }
}
```

#### Model Performance Dashboard

```json
{
  "dashboard": {
    "title": "ML Model Performance",
    "panels": [
      {
        "title": "Model Accuracy Trend",
        "type": "graph",
        "targets": [
          {
            "expr": "ml_model_accuracy",
            "legendFormat": "{{model}}"
          }
        ],
        "yAxes": [
          {
            "min": 0.4,
            "max": 0.8,
            "unit": "percentunit"
          }
        ]
      },
      {
        "title": "Prediction Confidence Distribution",
        "type": "histogram",
        "targets": [
          {
            "expr": "ml_signal_confidence",
            "legendFormat": "Confidence Score"
          }
        ]
      },
      {
        "title": "Model Drift Score",
        "type": "graph",
        "targets": [
          {
            "expr": "ml_model_drift_score",
            "legendFormat": "{{model}} - {{symbol}}"
          }
        ],
        "alert": {
          "conditions": [
            {
              "query": {"queryType": "A"},
              "reducer": {"type": "last"},
              "evaluator": {"params": [0.3], "type": "gt"}
            }
          ]
        }
      }
    ]
  }
}
```

### Log Aggregation

#### Structured Logging Configuration

```python
import structlog

logger = structlog.get_logger("ml_pipeline")

# Signal generation logging
logger.info(
    "signal_generated",
    symbol="EUR/USD",
    signal="BUY",
    confidence=0.85,
    models_used=["random_forest", "xgboost"],
    processing_time_ms=7.2,
    features_count=15
)

# Error logging
logger.error(
    "model_prediction_failed",
    model="lstm",
    error="timeout",
    symbol="GBP/USD",
    retry_count=2,
    processing_time_ms=5000
)

# Performance logging
logger.info(
    "component_performance",
    component="feature_extractor",
    execution_time_ms=3.1,
    memory_usage_mb=45.2,
    features_extracted=12
)
```

#### ELK Stack Configuration

```yaml
# logstash.conf
input {
  beats {
    port => 5044
  }
}

filter {
  if [fields][service] == "ml-pipeline" {
    json {
      source => "message"
    }

    if [level] == "ERROR" {
      mutate {
        add_tag => ["ml_error"]
      }
    }

    if [event] == "signal_generated" {
      mutate {
        add_tag => ["ml_signal"]
      }
    }
  }
}

output {
  elasticsearch {
    hosts => ["elasticsearch:9200"]
    index => "ml-pipeline-%{+YYYY.MM.dd}"
  }
}
```

## Alerting Configuration

### Alert Rules

#### Prometheus Alert Rules

```yaml
# ml_rules.yml
groups:
  - name: ml_pipeline_alerts
    rules:
      # Signal quality alerts
      - alert: LowSignalAccuracy
        expr: ml_model_accuracy < 0.5
        for: 10m
        labels:
          severity: warning
        annotations:
          summary: "ML model accuracy below threshold"
          description: "Model {{ $labels.model }} accuracy is {{ $value }} for {{ $labels.symbol }}"

      - alert: HighModelDriftScore
        expr: ml_model_drift_score > 0.3
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: "High model drift detected"
          description: "Model {{ $labels.model }} drift score is {{ $value }}"

      # Performance alerts
      - alert: HighProcessingLatency
        expr: histogram_quantile(0.95, ml_processing_latency_seconds) > 0.05
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "High ML processing latency"
          description: "P95 latency is {{ $value }}s for {{ $labels.component }}"

      - alert: MemoryUsageHigh
        expr: ml_memory_usage_bytes / 1024 / 1024 > 800
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "High memory usage in ML pipeline"
          description: "{{ $labels.component }} using {{ $value }}MB"

      # Error rate alerts
      - alert: HighErrorRate
        expr: rate(ml_errors_total[5m]) > 0.1
        for: 2m
        labels:
          severity: critical
        annotations:
          summary: "High error rate in ML pipeline"
          description: "Error rate is {{ $value }}/sec in {{ $labels.component }}"

      # Signal generation alerts
      - alert: NoSignalsGenerated
        expr: rate(ml_signals_generated_total[1h]) == 0
        for: 30m
        labels:
          severity: warning
        annotations:
          summary: "No ML signals generated"
          description: "No signals generated for {{ $labels.symbol }} in the last hour"

      - alert: TooManySignals
        expr: rate(ml_signals_generated_total[1h]) > 2
        for: 15m
        labels:
          severity: warning
        annotations:
          summary: "Too many ML signals generated"
          description: "{{ $value }} signals/hour for {{ $labels.symbol }}"
```

#### AlertManager Configuration

```yaml
# alertmanager.yml
global:
  smtp_smarthost: 'localhost:587'
  smtp_from: 'alertmanager@fxml4.com'

route:
  group_by: ['alertname']
  group_wait: 10s
  group_interval: 10s
  repeat_interval: 1h
  receiver: 'web.hook'
  routes:
    - match:
        severity: critical
      receiver: 'critical-alerts'
    - match:
        severity: warning
      receiver: 'warning-alerts'

receivers:
  - name: 'critical-alerts'
    email_configs:
      - to: 'admin@fxml4.com'
        subject: 'CRITICAL: ML Pipeline Alert'
        body: |
          Alert: {{ .GroupLabels.alertname }}
          Summary: {{ .CommonAnnotations.summary }}
          Description: {{ .CommonAnnotations.description }}

    slack_configs:
      - api_url: 'YOUR_SLACK_WEBHOOK_URL'
        channel: '#ml-alerts-critical'
        title: 'CRITICAL ML Alert'
        text: '{{ .CommonAnnotations.summary }}'

  - name: 'warning-alerts'
    email_configs:
      - to: 'team@fxml4.com'
        subject: 'WARNING: ML Pipeline Alert'
        body: |
          Alert: {{ .GroupLabels.alertname }}
          Description: {{ .CommonAnnotations.description }}
```

### Custom Alert Handlers

```python
# core/monitoring/alert_handler.py
import asyncio
import aiohttp
from typing import Dict, Any

class MLAlertHandler:
    """Custom alert handler for ML pipeline events."""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.alert_thresholds = config.get('alert_thresholds', {})

    async def check_model_performance(self, model_metrics: Dict[str, Any]):
        """Check model performance and trigger alerts if needed."""

        for model_name, metrics in model_metrics.items():
            accuracy = metrics.get('accuracy', 0)

            if accuracy < self.alert_thresholds.get('min_accuracy', 0.5):
                await self.send_alert({
                    'type': 'model_performance',
                    'severity': 'warning',
                    'model': model_name,
                    'accuracy': accuracy,
                    'message': f'Model {model_name} accuracy dropped to {accuracy:.2%}'
                })

    async def check_signal_quality(self, signal_stats: Dict[str, Any]):
        """Check signal quality metrics."""

        signal_rate = signal_stats.get('signals_per_hour', 0)
        confidence_avg = signal_stats.get('avg_confidence', 0)

        if signal_rate == 0:
            await self.send_alert({
                'type': 'signal_generation',
                'severity': 'warning',
                'message': 'No signals generated in the last hour'
            })
        elif signal_rate > 30:
            await self.send_alert({
                'type': 'signal_generation',
                'severity': 'warning',
                'message': f'High signal rate: {signal_rate} signals/hour'
            })

        if confidence_avg < 0.7:
            await self.send_alert({
                'type': 'signal_quality',
                'severity': 'warning',
                'message': f'Low average confidence: {confidence_avg:.2%}'
            })

    async def send_alert(self, alert_data: Dict[str, Any]):
        """Send alert to configured channels."""

        # Send to Slack
        if self.config.get('slack', {}).get('enabled'):
            await self._send_slack_alert(alert_data)

        # Send to email
        if self.config.get('email', {}).get('enabled'):
            await self._send_email_alert(alert_data)

        # Send to webhook
        if self.config.get('webhook', {}).get('enabled'):
            await self._send_webhook_alert(alert_data)

    async def _send_slack_alert(self, alert_data: Dict[str, Any]):
        """Send alert to Slack."""
        webhook_url = self.config['slack']['webhook_url']

        payload = {
            'text': f"ML Pipeline Alert: {alert_data['message']}",
            'username': 'ML Pipeline Bot',
            'icon_emoji': ':warning:' if alert_data['severity'] == 'warning' else ':rotating_light:'
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(webhook_url, json=payload) as response:
                if response.status != 200:
                    print(f"Failed to send Slack alert: {response.status}")
```

## Performance Benchmarks

### Baseline Performance Targets

#### Latency Benchmarks (P95)

```python
latency_targets = {
    'feature_extraction': {
        'target_ms': 5,
        'max_acceptable_ms': 15,
        'test_data_points': 100
    },
    'model_prediction': {
        'random_forest': {'target_ms': 2, 'max_ms': 8},
        'xgboost': {'target_ms': 3, 'max_ms': 10},
        'lstm': {'target_ms': 5, 'max_ms': 15}
    },
    'signal_generation': {
        'target_ms': 1,
        'max_acceptable_ms': 5
    },
    'end_to_end': {
        'target_ms': 10,
        'max_acceptable_ms': 30
    }
}
```

#### Throughput Benchmarks

```python
throughput_targets = {
    'market_data_processing': {
        'target_per_sec': 1000,
        'min_acceptable': 500
    },
    'signal_generation': {
        'target_per_min': 60,
        'max_sustainable': 300
    },
    'concurrent_symbols': {
        'target_count': 50,
        'max_tested': 100
    }
}
```

#### Accuracy Benchmarks

```python
accuracy_targets = {
    'individual_models': {
        'random_forest': {'min': 0.55, 'target': 0.60},
        'xgboost': {'min': 0.58, 'target': 0.65},
        'lstm': {'min': 0.53, 'target': 0.58}
    },
    'ensemble': {
        'min': 0.60,
        'target': 0.68,
        'excellent': 0.75
    },
    'risk_adjusted_returns': {
        'min_sharpe': 1.0,
        'target_sharpe': 1.5,
        'max_drawdown': 0.05
    }
}
```

### Performance Testing Suite

```python
# tests/performance/test_ml_pipeline_performance.py
import pytest
import time
import asyncio
import pandas as pd
from concurrent.futures import ThreadPoolExecutor

from core.ml.ml_trading_pipeline import MLTradingPipeline

class TestMLPipelinePerformance:
    """Performance tests for ML pipeline components."""

    @pytest.fixture
    def large_market_data(self):
        """Generate large dataset for performance testing."""
        return pd.DataFrame({
            'timestamp': pd.date_range('2024-01-01', periods=10000, freq='1min'),
            'open': np.random.uniform(1.08, 1.10, 10000),
            'high': np.random.uniform(1.09, 1.11, 10000),
            'low': np.random.uniform(1.07, 1.09, 10000),
            'close': np.random.uniform(1.08, 1.10, 10000),
            'volume': np.random.randint(1000, 10000, 10000),
            'symbol': ['EUR/USD'] * 10000
        })

    @pytest.mark.performance
    async def test_end_to_end_latency(self, large_market_data):
        """Test end-to-end processing latency."""
        pipeline = MLTradingPipeline({
            'models': ['random_forest', 'xgboost'],
            'confidence_threshold': 0.7
        })

        # Warm up
        await pipeline.process_market_data(large_market_data.head(100))

        # Measure latency
        start_time = time.perf_counter()
        signal = await pipeline.process_market_data(large_market_data.head(100))
        end_time = time.perf_counter()

        latency_ms = (end_time - start_time) * 1000

        assert signal is not None
        assert latency_ms < 30, f"Latency {latency_ms:.2f}ms exceeds 30ms target"

    @pytest.mark.performance
    async def test_throughput_concurrent_symbols(self):
        """Test throughput with multiple symbols."""
        pipeline = MLTradingPipeline({
            'models': ['random_forest'],
            'confidence_threshold': 0.7
        })

        symbols = ['EUR/USD', 'GBP/USD', 'USD/JPY', 'AUD/USD', 'USD/CHF']

        async def process_symbol(symbol):
            data = self._generate_symbol_data(symbol)
            return await pipeline.process_market_data(data)

        start_time = time.perf_counter()

        # Process symbols concurrently
        tasks = [process_symbol(symbol) for symbol in symbols]
        results = await asyncio.gather(*tasks)

        end_time = time.perf_counter()

        processing_time = end_time - start_time
        throughput = len(symbols) / processing_time

        assert all(result is not None for result in results)
        assert throughput > 2, f"Throughput {throughput:.2f} symbols/sec below target"

    @pytest.mark.performance
    def test_memory_usage(self, large_market_data):
        """Test memory usage under load."""
        import psutil
        import os

        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB

        pipeline = MLTradingPipeline({
            'models': ['random_forest', 'xgboost', 'lstm'],
            'confidence_threshold': 0.7
        })

        # Process data multiple times
        for i in range(10):
            asyncio.run(pipeline.process_market_data(large_market_data.head(500)))

        final_memory = process.memory_info().rss / 1024 / 1024  # MB
        memory_increase = final_memory - initial_memory

        assert memory_increase < 100, f"Memory increase {memory_increase:.1f}MB exceeds 100MB limit"

    def _generate_symbol_data(self, symbol):
        """Generate test data for a symbol."""
        return pd.DataFrame({
            'timestamp': pd.date_range('2024-01-01', periods=100, freq='1h'),
            'open': np.random.uniform(1.08, 1.10, 100),
            'high': np.random.uniform(1.09, 1.11, 100),
            'low': np.random.uniform(1.07, 1.09, 100),
            'close': np.random.uniform(1.08, 1.10, 100),
            'volume': np.random.randint(1000, 10000, 100),
            'symbol': [symbol] * 100
        })
```

## Performance Optimization Strategies

### Caching Optimization

```python
# core/ml/performance_optimizer.py
import asyncio
import time
from typing import Dict, Any, Optional
from functools import lru_cache
import redis

class MLPerformanceOptimizer:
    """Performance optimization utilities for ML pipeline."""

    def __init__(self, redis_client: Optional[redis.Redis] = None):
        self.redis_client = redis_client
        self.feature_cache = {}
        self.prediction_cache = {}

    @lru_cache(maxsize=1000)
    def cache_features(self, data_hash: str, features: str):
        """Cache computed features."""
        if self.redis_client:
            self.redis_client.setex(
                f"features:{data_hash}",
                300,  # 5 minutes TTL
                features
            )
        else:
            self.feature_cache[data_hash] = {
                'features': features,
                'timestamp': time.time()
            }

    def get_cached_features(self, data_hash: str) -> Optional[str]:
        """Retrieve cached features."""
        if self.redis_client:
            return self.redis_client.get(f"features:{data_hash}")
        else:
            cached = self.feature_cache.get(data_hash)
            if cached and (time.time() - cached['timestamp']) < 300:
                return cached['features']
        return None

    async def batch_process_symbols(self, symbols_data: Dict[str, Any]):
        """Process multiple symbols in batch for better performance."""

        # Group by similar processing requirements
        grouped_data = self._group_by_processing_type(symbols_data)

        results = {}
        for group_type, group_data in grouped_data.items():
            # Process each group concurrently
            group_results = await self._process_group_concurrent(group_data)
            results.update(group_results)

        return results

    def _group_by_processing_type(self, symbols_data: Dict[str, Any]) -> Dict[str, Dict]:
        """Group symbols by processing requirements."""
        groups = {
            'major_pairs': {},
            'minor_pairs': {},
            'exotic_pairs': {}
        }

        major_pairs = ['EUR/USD', 'GBP/USD', 'USD/JPY', 'USD/CHF']
        minor_pairs = ['EUR/GBP', 'EUR/JPY', 'GBP/JPY', 'AUD/USD']

        for symbol, data in symbols_data.items():
            if symbol in major_pairs:
                groups['major_pairs'][symbol] = data
            elif symbol in minor_pairs:
                groups['minor_pairs'][symbol] = data
            else:
                groups['exotic_pairs'][symbol] = data

        return groups

    async def _process_group_concurrent(self, group_data: Dict[str, Any]) -> Dict[str, Any]:
        """Process a group of symbols concurrently."""

        async def process_single(symbol, data):
            # Implement actual processing logic here
            await asyncio.sleep(0.01)  # Simulated processing
            return f"processed_{symbol}"

        tasks = [
            process_single(symbol, data)
            for symbol, data in group_data.items()
        ]

        results = await asyncio.gather(*tasks)

        return dict(zip(group_data.keys(), results))
```

### Database Query Optimization

```sql
-- Optimized queries for ML pipeline metrics

-- Efficient signal statistics query
CREATE OR REPLACE FUNCTION get_signal_statistics(
    p_symbol VARCHAR(20),
    p_hours INTEGER DEFAULT 24
) RETURNS TABLE (
    total_signals BIGINT,
    buy_signals BIGINT,
    sell_signals BIGINT,
    avg_confidence DECIMAL(5,4),
    max_confidence DECIMAL(5,4)
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        COUNT(*) as total_signals,
        COUNT(*) FILTER (WHERE signal_type = 'BUY') as buy_signals,
        COUNT(*) FILTER (WHERE signal_type = 'SELL') as sell_signals,
        AVG(confidence)::DECIMAL(5,4) as avg_confidence,
        MAX(confidence)::DECIMAL(5,4) as max_confidence
    FROM ml_signals
    WHERE symbol = p_symbol
    AND created_at >= NOW() - INTERVAL '%s hours', p_hours;
END;
$$ LANGUAGE plpgsql;

-- Optimized model performance query with indexes
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_ml_performance_composite
ON ml_model_performance (model_name, symbol, timestamp DESC);

-- Materialized view for frequently accessed metrics
CREATE MATERIALIZED VIEW ml_daily_metrics AS
SELECT
    DATE(created_at) as metric_date,
    symbol,
    COUNT(*) as total_signals,
    AVG(confidence) as avg_confidence,
    COUNT(*) FILTER (WHERE signal_type = 'BUY') as buy_signals,
    COUNT(*) FILTER (WHERE signal_type = 'SELL') as sell_signals
FROM ml_signals
WHERE created_at >= CURRENT_DATE - INTERVAL '30 days'
GROUP BY DATE(created_at), symbol;

-- Refresh materialized view daily
CREATE OR REPLACE FUNCTION refresh_ml_metrics()
RETURNS VOID AS $$
BEGIN
    REFRESH MATERIALIZED VIEW CONCURRENTLY ml_daily_metrics;
END;
$$ LANGUAGE plpgsql;
```

This comprehensive monitoring and performance documentation provides all the tools and strategies needed to maintain optimal ML Trading Pipeline performance in production environments.