# ML Trading Pipeline Configuration Reference

## Overview

This document provides comprehensive configuration options for the ML Trading Pipeline. All configurations can be set through environment variables, configuration files, or programmatically through the API.

## Configuration Hierarchy

The ML pipeline follows a hierarchical configuration approach:

1. **Environment Variables** (highest priority)
2. **Configuration Files** (medium priority)
3. **Default Values** (lowest priority)

## Core Configuration

### Environment Variables

All ML pipeline configurations can be set via environment variables with the `ML_` prefix:

```bash
# Core Pipeline Settings
ML_ENABLED=true                          # Enable/disable ML pipeline
ML_MODELS=random_forest,xgboost,lstm     # Comma-separated list of models
ML_CONFIDENCE_THRESHOLD=0.7              # Minimum confidence for signal generation
ML_LOOKBACK_PERIOD=50                    # Number of historical data points
ML_PREDICTION_HORIZON=5                  # Prediction time horizon (minutes)

# Feature Engineering
ML_FEATURES=sma,rsi,macd,volume_profile  # Comma-separated feature list
ML_FEATURE_NORMALIZATION=true            # Enable feature normalization
ML_SMA_PERIODS=20,50,200                 # SMA calculation periods
ML_RSI_PERIOD=14                         # RSI calculation period
ML_MACD_FAST=12                          # MACD fast EMA period
ML_MACD_SLOW=26                          # MACD slow EMA period
ML_MACD_SIGNAL=9                         # MACD signal line period

# Model Configuration
ML_MODEL_PATH=/app/models                # Path to model files
ML_MODEL_REGISTRY_URL=http://localhost:5000/api/models  # Model registry URL
ML_AUTO_RETRAIN=false                    # Enable automatic model retraining
ML_MODEL_UPDATE_INTERVAL=86400           # Model update interval (seconds)
ML_ENSEMBLE_METHOD=weighted_voting       # Ensemble aggregation method

# Performance Settings
ML_BATCH_SIZE=100                        # Batch processing size
ML_MAX_WORKERS=4                         # Maximum worker threads
ML_CACHE_TTL=60                          # Cache time-to-live (seconds)
ML_UPDATE_FREQUENCY=1000                 # Update frequency (milliseconds)
ML_ASYNC_PROCESSING=true                 # Enable async processing

# Risk Management
ML_MAX_POSITION_SIZE=0.05                # Maximum position size (5%)
ML_STOP_LOSS_PCT=0.02                    # Stop loss percentage (2%)
ML_TAKE_PROFIT_PCT=0.04                  # Take profit percentage (4%)
ML_RISK_FREE_RATE=0.02                   # Risk-free rate for calculations
ML_VOLATILITY_LOOKBACK=20                # Volatility calculation period

# WebSocket Configuration
ML_WEBSOCKET_ENABLED=true                # Enable WebSocket broadcasting
ML_WEBSOCKET_PORT=8080                   # WebSocket server port
ML_WEBSOCKET_HOST=0.0.0.0                # WebSocket bind address
ML_MAX_WEBSOCKET_CONNECTIONS=1000        # Maximum concurrent connections

# Database Configuration
ML_DB_HOST=localhost                     # Database host
ML_DB_PORT=5432                          # Database port
ML_DB_NAME=fxml4_ml                      # Database name
ML_DB_USER=ml_user                       # Database user
ML_DB_PASSWORD=ml_password               # Database password
ML_DB_POOL_SIZE=20                       # Connection pool size

# Monitoring and Logging
ML_METRICS_ENABLED=true                  # Enable Prometheus metrics
ML_METRICS_PORT=9090                     # Metrics server port
ML_LOG_LEVEL=INFO                        # Logging level
ML_LOG_FORMAT=json                       # Log format (json/text)
ML_PERFORMANCE_TRACKING=true             # Enable performance tracking
```

### Configuration File Format

Create a `ml_config.yaml` file for structured configuration:

```yaml
# ml_config.yaml
ml_pipeline:
  # Core Settings
  enabled: true
  models:
    - random_forest
    - xgboost
    - lstm
  confidence_threshold: 0.7
  lookback_period: 50
  prediction_horizon: 5

  # Feature Engineering
  features:
    enabled:
      - sma
      - rsi
      - macd
      - volume_profile
      - price_patterns
      - microstructure

    normalization:
      enabled: true
      method: "minmax"  # minmax, zscore, robust
      range: [-1, 1]

    technical_indicators:
      sma:
        periods: [20, 50, 200]
      rsi:
        period: 14
        overbought: 70
        oversold: 30
      macd:
        fast: 12
        slow: 26
        signal: 9
      bollinger_bands:
        period: 20
        std_dev: 2

  # Model Configuration
  models_config:
    random_forest:
      n_estimators: 100
      max_depth: 10
      min_samples_split: 5
      random_state: 42

    xgboost:
      n_estimators: 100
      max_depth: 6
      learning_rate: 0.1
      subsample: 0.8

    lstm:
      layers: [64, 32]
      dropout: 0.2
      epochs: 100
      batch_size: 32

  # Ensemble Configuration
  ensemble:
    method: "weighted_voting"  # majority_voting, weighted_voting, stacking
    weights:
      random_forest: 0.4
      xgboost: 0.4
      lstm: 0.2
    confidence_calculation: "variance"  # variance, entropy, agreement

  # Risk Management
  risk_management:
    max_position_size: 0.05
    position_sizing_method: "confidence_based"  # fixed, confidence_based, kelly
    stop_loss:
      method: "percentage"  # percentage, atr, volatility
      percentage: 0.02
      atr_multiplier: 2.0
    take_profit:
      method: "percentage"
      percentage: 0.04
      risk_reward_ratio: 2.0

  # Performance Settings
  performance:
    batch_size: 100
    max_workers: 4
    cache_settings:
      enabled: true
      ttl: 60
      max_size_mb: 100
    memory_limit_mb: 500
    cpu_limit_percent: 80

  # Data Sources
  data_sources:
    primary: "market_data_feed"
    backup: "cached_data"
    real_time: true
    symbols:
      - "EUR/USD"
      - "GBP/USD"
      - "USD/JPY"
      - "AUD/USD"

  # Monitoring
  monitoring:
    metrics:
      enabled: true
      port: 9090
      update_interval: 30
    logging:
      level: "INFO"
      format: "json"
      file: "/app/logs/ml_pipeline.log"
      max_size_mb: 100
      backup_count: 5
    alerting:
      enabled: true
      thresholds:
        accuracy_drop: 0.1
        drift_score: 0.3
        error_rate: 0.05

  # Development Settings
  development:
    debug_mode: false
    mock_data: false
    test_symbols: ["EUR/USD"]
    profiling_enabled: false
```

## Feature Configuration

### Technical Indicators

Configure technical indicators with specific parameters:

```python
feature_config = {
    'technical_indicators': {
        'moving_averages': {
            'sma_periods': [5, 10, 20, 50, 100, 200],
            'ema_periods': [12, 26, 50],
            'wma_periods': [10, 20]
        },
        'momentum': {
            'rsi': {'period': 14, 'overbought': 70, 'oversold': 30},
            'stoch': {'k_period': 14, 'd_period': 3},
            'williams_r': {'period': 14}
        },
        'volatility': {
            'bollinger': {'period': 20, 'std_dev': 2},
            'atr': {'period': 14},
            'vix_like': {'period': 30}
        },
        'volume': {
            'volume_sma': {'period': 20},
            'obv': {'enabled': True},
            'mfi': {'period': 14}
        }
    }
}
```

### Price Pattern Recognition

Configure candlestick pattern detection:

```python
pattern_config = {
    'candlestick_patterns': {
        'enabled': True,
        'patterns': [
            'bullish_engulfing',
            'bearish_engulfing',
            'doji',
            'hammer',
            'shooting_star',
            'morning_star',
            'evening_star'
        ],
        'sensitivity': 0.1,  # Pattern detection sensitivity
        'confirmation_periods': 2  # Periods to confirm pattern
    },
    'price_action': {
        'support_resistance': {
            'enabled': True,
            'lookback': 50,
            'strength_threshold': 3
        },
        'trend_lines': {
            'enabled': True,
            'min_touches': 2,
            'angle_threshold': 15
        }
    }
}
```

### Microstructure Features

Configure market microstructure analysis:

```python
microstructure_config = {
    'order_flow': {
        'enabled': True,
        'tick_size': 0.00001,
        'volume_buckets': 10
    },
    'liquidity_metrics': {
        'bid_ask_spread': True,
        'market_impact': True,
        'depth_imbalance': True
    },
    'timing_features': {
        'time_of_day': True,
        'day_of_week': True,
        'session_overlap': True
    }
}
```

## Model Configuration

### Individual Model Parameters

#### Random Forest Configuration

```python
random_forest_config = {
    'n_estimators': 100,           # Number of trees
    'max_depth': 10,               # Maximum tree depth
    'min_samples_split': 5,        # Minimum samples to split
    'min_samples_leaf': 2,         # Minimum samples in leaf
    'max_features': 'sqrt',        # Features per tree
    'random_state': 42,            # Random seed
    'n_jobs': -1,                  # Use all CPU cores
    'class_weight': 'balanced',    # Handle class imbalance
    'bootstrap': True,             # Bootstrap sampling
    'oob_score': True             # Out-of-bag scoring
}
```

#### XGBoost Configuration

```python
xgboost_config = {
    'n_estimators': 100,           # Number of boosting rounds
    'max_depth': 6,                # Maximum tree depth
    'learning_rate': 0.1,          # Learning rate
    'subsample': 0.8,              # Row sampling ratio
    'colsample_bytree': 0.8,       # Column sampling ratio
    'reg_alpha': 0.1,              # L1 regularization
    'reg_lambda': 0.1,             # L2 regularization
    'random_state': 42,            # Random seed
    'eval_metric': 'logloss',      # Evaluation metric
    'early_stopping_rounds': 10,   # Early stopping
    'use_label_encoder': False     # Disable label encoder warning
}
```

#### LSTM Configuration

```python
lstm_config = {
    'sequence_length': 50,         # Input sequence length
    'layers': [64, 32],           # Hidden layer sizes
    'dropout': 0.2,               # Dropout rate
    'recurrent_dropout': 0.2,     # Recurrent dropout
    'activation': 'tanh',         # Activation function
    'optimizer': 'adam',          # Optimizer
    'learning_rate': 0.001,       # Learning rate
    'batch_size': 32,             # Training batch size
    'epochs': 100,                # Training epochs
    'validation_split': 0.2,      # Validation split
    'early_stopping': {
        'monitor': 'val_loss',
        'patience': 10,
        'restore_best_weights': True
    }
}
```

### Ensemble Configuration

Configure how models are combined:

```python
ensemble_config = {
    'method': 'weighted_voting',   # Combination method
    'weights': {                   # Model weights
        'random_forest': 0.4,
        'xgboost': 0.4,
        'lstm': 0.2
    },
    'confidence_calculation': 'variance',  # Confidence method
    'min_models': 2,              # Minimum models for prediction
    'outlier_detection': {
        'enabled': True,
        'threshold': 2.0          # Standard deviations
    },
    'adaptive_weights': {
        'enabled': True,
        'update_frequency': 86400, # 24 hours
        'performance_window': 30   # Days to consider
    }
}
```

## Risk Management Configuration

### Position Sizing

```python
position_sizing_config = {
    'method': 'confidence_based',  # fixed, confidence_based, kelly
    'base_size': 0.02,            # Base position size (2%)
    'max_size': 0.05,             # Maximum position size (5%)
    'confidence_multiplier': 2.0,  # Confidence scaling factor
    'kelly_fraction': 0.25,       # Kelly criterion fraction
    'volatility_adjustment': {
        'enabled': True,
        'target_volatility': 0.02, # 2% daily volatility target
        'lookback_period': 20
    }
}
```

### Stop Loss Configuration

```python
stop_loss_config = {
    'method': 'atr',              # percentage, atr, volatility
    'percentage': 0.02,           # 2% stop loss
    'atr_multiplier': 2.0,        # ATR multiplier
    'volatility_multiplier': 1.5, # Volatility multiplier
    'minimum_distance': 0.0010,   # Minimum stop distance
    'trailing_stop': {
        'enabled': True,
        'trigger_percent': 0.01,   # Trigger at 1% profit
        'trail_percent': 0.005     # Trail by 0.5%
    }
}
```

### Take Profit Configuration

```python
take_profit_config = {
    'method': 'risk_reward',      # percentage, risk_reward, volatility
    'percentage': 0.04,           # 4% take profit
    'risk_reward_ratio': 2.0,     # 2:1 risk/reward
    'partial_profits': {
        'enabled': True,
        'levels': [
            {'percent': 50, 'at_ratio': 1.0},  # 50% at 1:1
            {'percent': 30, 'at_ratio': 1.5},  # 30% at 1.5:1
            {'percent': 20, 'at_ratio': 2.0}   # 20% at 2:1
        ]
    }
}
```

## Performance Configuration

### Caching Settings

```python
cache_config = {
    'feature_cache': {
        'enabled': True,
        'ttl': 300,                # 5 minutes
        'max_size_mb': 100,
        'compression': True
    },
    'prediction_cache': {
        'enabled': True,
        'ttl': 60,                 # 1 minute
        'max_size_mb': 50
    },
    'model_cache': {
        'enabled': True,
        'ttl': 3600,               # 1 hour
        'max_size_mb': 200
    }
}
```

### Parallel Processing

```python
parallel_config = {
    'feature_extraction': {
        'enabled': True,
        'max_workers': 4,
        'batch_size': 100
    },
    'model_prediction': {
        'enabled': True,
        'max_workers': 3,          # One per model type
        'timeout': 5.0             # Seconds
    },
    'signal_generation': {
        'enabled': False,          # Keep sequential for consistency
        'max_workers': 1
    }
}
```

### Memory Management

```python
memory_config = {
    'limits': {
        'total_mb': 1000,          # Total memory limit
        'feature_extraction_mb': 200,
        'model_prediction_mb': 500,
        'cache_mb': 200,
        'buffer_mb': 100
    },
    'garbage_collection': {
        'enabled': True,
        'frequency': 300,          # Every 5 minutes
        'threshold': 0.8          # 80% memory usage
    },
    'data_retention': {
        'features_hours': 24,      # Keep features for 24 hours
        'predictions_hours': 168,  # Keep predictions for 1 week
        'signals_days': 30        # Keep signals for 30 days
    }
}
```

## Database Configuration

### Connection Settings

```python
database_config = {
    'connection': {
        'host': 'localhost',
        'port': 5432,
        'database': 'fxml4_ml',
        'user': 'ml_user',
        'password': 'ml_password',
        'sslmode': 'require'
    },
    'pool': {
        'min_connections': 5,
        'max_connections': 20,
        'max_overflow': 30,
        'pool_timeout': 30,
        'pool_recycle': 3600
    },
    'timeouts': {
        'connection': 30,
        'query': 60,
        'transaction': 300
    }
}
```

### Table Configuration

```python
table_config = {
    'ml_signals': {
        'partition_by': 'created_at',
        'partition_interval': 'monthly',
        'retention_days': 365,
        'indexes': [
            'symbol_created_idx',
            'status_idx',
            'confidence_idx'
        ]
    },
    'ml_model_performance': {
        'partition_by': 'timestamp',
        'partition_interval': 'weekly',
        'retention_days': 90,
        'compression': True
    }
}
```

## Monitoring Configuration

### Metrics Collection

```python
metrics_config = {
    'prometheus': {
        'enabled': True,
        'port': 9090,
        'host': '0.0.0.0',
        'update_interval': 30
    },
    'custom_metrics': {
        'signal_generation_rate': True,
        'model_accuracy': True,
        'prediction_confidence': True,
        'processing_latency': True,
        'error_rates': True
    },
    'retention': {
        'high_resolution': '1h',   # 15s for 1 hour
        'medium_resolution': '6h', # 60s for 6 hours
        'low_resolution': '24h'    # 300s for 24 hours
    }
}
```

### Alerting Configuration

```python
alerting_config = {
    'channels': {
        'email': {
            'enabled': True,
            'recipients': ['admin@fxml4.com'],
            'smtp_server': 'smtp.gmail.com',
            'smtp_port': 587
        },
        'slack': {
            'enabled': True,
            'webhook_url': 'https://hooks.slack.com/...',
            'channel': '#ml-alerts'
        },
        'webhook': {
            'enabled': False,
            'url': 'https://api.fxml4.com/alerts'
        }
    },
    'rules': {
        'model_accuracy_drop': {
            'threshold': 0.1,        # 10% accuracy drop
            'window': '1h',
            'severity': 'warning'
        },
        'prediction_errors': {
            'threshold': 0.05,       # 5% error rate
            'window': '5m',
            'severity': 'critical'
        },
        'high_latency': {
            'threshold': 10.0,       # 10 seconds
            'window': '5m',
            'severity': 'warning'
        }
    }
}
```

## Development Configuration

### Debug Settings

```python
debug_config = {
    'enabled': False,
    'log_level': 'DEBUG',
    'profiling': {
        'enabled': False,
        'output_dir': '/app/profiling',
        'profile_memory': True,
        'profile_cpu': True
    },
    'feature_inspection': {
        'enabled': False,
        'save_features': True,
        'output_dir': '/app/debug/features'
    },
    'model_inspection': {
        'enabled': False,
        'save_predictions': True,
        'output_dir': '/app/debug/predictions'
    }
}
```

### Testing Configuration

```python
test_config = {
    'mock_data': {
        'enabled': False,
        'symbols': ['EUR/USD', 'GBP/USD'],
        'data_points': 1000,
        'noise_level': 0.1
    },
    'unit_tests': {
        'coverage_threshold': 0.8,
        'fail_fast': True,
        'parallel': True
    },
    'integration_tests': {
        'test_db': 'fxml4_ml_test',
        'cleanup_after': True,
        'timeout': 300
    }
}
```

## Configuration Validation

### Schema Validation

The ML pipeline includes built-in configuration validation:

```python
from core.ml.config_validator import ConfigValidator

validator = ConfigValidator()

# Validate configuration
is_valid, errors = validator.validate_config(config)

if not is_valid:
    for error in errors:
        print(f"Configuration error: {error}")
```

### Required vs Optional Settings

**Required Settings:**
- `ML_ENABLED`: Must be set to activate pipeline
- `ML_MODELS`: At least one model must be specified
- `ML_CONFIDENCE_THRESHOLD`: Must be between 0.0 and 1.0

**Optional Settings:**
- All feature configurations (have sensible defaults)
- Performance tuning parameters (auto-detected)
- Monitoring settings (can be disabled)

### Configuration Examples

#### Minimal Configuration

```bash
# Minimal viable configuration
ML_ENABLED=true
ML_MODELS=random_forest
ML_CONFIDENCE_THRESHOLD=0.7
```

#### Production Configuration

```bash
# Production-ready configuration
ML_ENABLED=true
ML_MODELS=random_forest,xgboost,lstm
ML_CONFIDENCE_THRESHOLD=0.75
ML_LOOKBACK_PERIOD=100
ML_FEATURES=sma,rsi,macd,volume_profile,price_patterns
ML_MAX_POSITION_SIZE=0.03
ML_STOP_LOSS_PCT=0.015
ML_TAKE_PROFIT_PCT=0.035
ML_METRICS_ENABLED=true
ML_CACHE_TTL=300
ML_MAX_WORKERS=8
```

#### Development Configuration

```bash
# Development configuration
ML_ENABLED=true
ML_MODELS=random_forest
ML_CONFIDENCE_THRESHOLD=0.6
ML_LOG_LEVEL=DEBUG
ML_CACHE_TTL=10
ML_UPDATE_FREQUENCY=5000
ML_MOCK_DATA=true
```

This comprehensive configuration reference provides all the options needed to fine-tune the ML Trading Pipeline for your specific requirements and deployment environment.