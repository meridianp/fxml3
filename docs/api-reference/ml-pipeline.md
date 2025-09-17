# ML Trading Pipeline API Reference

## Overview

This document provides comprehensive API documentation for all ML Trading Pipeline components. Each class and method includes detailed parameter descriptions, return types, usage examples, and error handling information.

## Core Components

### MLTradingPipeline

The main orchestration class that coordinates feature extraction, model prediction, and signal generation.

#### Class Definition

```python
class MLTradingPipeline:
    """Unified ML trading pipeline for market analysis and signal generation."""
```

#### Constructor

```python
def __init__(self, config: Optional[Dict[str, Any]] = None)
```

**Parameters:**
- `config` (Dict[str, Any], optional): Configuration dictionary containing pipeline settings

**Configuration Options:**
```python
{
    'models': List[str] = ['random_forest', 'xgboost', 'lstm'],
    'features': List[str] = ['sma', 'rsi', 'macd', 'volume_profile'],
    'lookback_period': int = 50,
    'prediction_horizon': int = 5,
    'confidence_threshold': float = 0.7,
    'max_position_size': float = 0.05,
    'stop_loss_pct': float = 0.02,
    'take_profit_pct': float = 0.04
}
```

#### Methods

##### process_market_data

```python
async def process_market_data(self, market_data: pd.DataFrame) -> Optional[Dict[str, Any]]
```

Processes market data through the complete ML pipeline and returns trading signals.

**Parameters:**
- `market_data` (pd.DataFrame): Market data with required columns: ['open', 'high', 'low', 'close', 'volume']

**Required DataFrame Columns:**
- `timestamp` (datetime): Timestamp for each data point
- `open` (float): Opening price
- `high` (float): Highest price in period
- `low` (float): Lowest price in period
- `close` (float): Closing price
- `volume` (int): Trading volume
- `symbol` (str, optional): Trading symbol (defaults to 'EUR/USD')

**Returns:**
- `Dict[str, Any]`: Trading signal with the following structure:

```python
{
    'symbol': str,              # Trading symbol
    'signal': str,              # 'BUY', 'SELL', or 'HOLD'
    'confidence': float,        # Confidence level (0.0-1.0)
    'position_size': float,     # Recommended position size
    'entry_price': float,       # Current/entry price
    'stop_loss': float,         # Stop loss price
    'take_profit': float,       # Take profit price
    'timestamp': str,           # ISO format timestamp
    'features': List[str],      # List of features used
    'models_used': List[str],   # List of models used
    'prediction_details': Dict  # Detailed prediction information
}
```

**Example Usage:**

```python
import pandas as pd
from core.ml.ml_trading_pipeline import MLTradingPipeline

# Initialize pipeline
pipeline = MLTradingPipeline({
    'models': ['random_forest', 'xgboost'],
    'confidence_threshold': 0.75
})

# Prepare market data
market_data = pd.DataFrame({
    'timestamp': pd.date_range('2024-01-01', periods=100, freq='1h'),
    'open': [1.0850] * 100,
    'high': [1.0870] * 100,
    'low': [1.0830] * 100,
    'close': [1.0860] * 100,
    'volume': [1000] * 100,
    'symbol': ['EUR/USD'] * 100
})

# Process data
signal = await pipeline.process_market_data(market_data)

if signal:
    print(f"Signal: {signal['signal']} for {signal['symbol']}")
    print(f"Confidence: {signal['confidence']:.2f}")
    print(f"Position Size: {signal['position_size']:.3f}")
```

**Error Handling:**
- Returns `None` if market_data is empty
- Handles missing columns gracefully with default values
- Logs errors and continues processing when possible

##### connect_websocket

```python
def connect_websocket(self, websocket_server) -> None
```

Connects the pipeline to a WebSocket server for real-time signal broadcasting.

**Parameters:**
- `websocket_server`: WebSocket server instance with `broadcast` method

**Example Usage:**

```python
from core.websocket import WebSocketServer

websocket_server = WebSocketServer()
pipeline.connect_websocket(websocket_server)
```

##### start_real_time_processing

```python
async def start_real_time_processing(self, data_feed) -> None
```

Starts continuous real-time market data processing with automatic signal broadcasting.

**Parameters:**
- `data_feed`: Data feed object with `get_latest_data()` async method

**Example Usage:**

```python
from core.data.market_data_feed import MarketDataFeed

data_feed = MarketDataFeed('EUR/USD')
await pipeline.start_real_time_processing(data_feed)
```

##### stop

```python
def stop() -> None
```

Stops the real-time processing loop and disconnects WebSocket.

---

### FeatureExtractor

Extracts technical indicators, price patterns, and microstructure features from market data.

#### Class Definition

```python
class FeatureExtractor:
    """Extract features from market data for ML models."""
```

#### Constructor

```python
def __init__(self, config: Optional[Dict[str, Any]] = None)
```

**Parameters:**
- `config` (Dict[str, Any], optional): Configuration for feature extraction

**Configuration Options:**
```python
{
    'features': List[str] = ['sma', 'rsi', 'macd', 'volume_profile'],
    'lookback_period': int = 50,
    'sma_periods': List[int] = [20, 50, 200],
    'rsi_period': int = 14,
    'macd_fast': int = 12,
    'macd_slow': int = 26,
    'macd_signal': int = 9
}
```

#### Methods

##### extract_technical_features

```python
def extract_technical_features(self, market_data: pd.DataFrame) -> pd.DataFrame
```

Extracts comprehensive technical indicator features from market data.

**Parameters:**
- `market_data` (pd.DataFrame): Market data with OHLCV columns

**Returns:**
- `pd.DataFrame`: DataFrame with technical indicator columns

**Generated Features:**
- `sma_20`, `sma_50`: Simple Moving Averages
- `rsi_14`: Relative Strength Index
- `macd_line`, `macd_signal`, `macd_histogram`: MACD components
- `volume_sma`, `volume_ratio`: Volume-based features
- `high_low_ratio`, `close_open_ratio`: Price relationship features

**Example Usage:**

```python
from core.ml.feature_extractor import FeatureExtractor

extractor = FeatureExtractor()
features = extractor.extract_technical_features(market_data)

print(f"Generated {len(features.columns)} features:")
print(features.columns.tolist())
```

##### extract_price_patterns

```python
def extract_price_patterns(self, market_data: pd.DataFrame) -> Dict[str, bool]
```

Detects candlestick patterns in market data.

**Parameters:**
- `market_data` (pd.DataFrame): Market data with OHLC columns

**Returns:**
- `Dict[str, bool]`: Dictionary of detected patterns

**Detected Patterns:**
- `bullish_engulfing`: Bullish engulfing candlestick pattern
- `bearish_engulfing`: Bearish engulfing candlestick pattern
- `doji`: Doji candlestick pattern (indecision)

**Example Usage:**

```python
patterns = extractor.extract_price_patterns(market_data)

if patterns['bullish_engulfing']:
    print("Bullish engulfing pattern detected!")
```

##### extract_microstructure_features

```python
def extract_microstructure_features(self, market_data: pd.DataFrame) -> Dict[str, float]
```

Extracts market microstructure features related to order flow and liquidity.

**Parameters:**
- `market_data` (pd.DataFrame): Market data with volume information

**Returns:**
- `Dict[str, float]`: Dictionary of microstructure features

**Generated Features:**
- `bid_ask_spread`: Estimated bid-ask spread
- `order_flow_imbalance`: Order flow imbalance measure
- `volume_weighted_price`: Volume Weighted Average Price (VWAP)

**Example Usage:**

```python
microstructure = extractor.extract_microstructure_features(market_data)

print(f"VWAP: {microstructure['volume_weighted_price']:.5f}")
print(f"Order Flow: {microstructure['order_flow_imbalance']:.3f}")
```

##### normalize_features

```python
def normalize_features(self, features: pd.DataFrame) -> pd.DataFrame
```

Normalizes features to [-1, 1] range using min-max scaling.

**Parameters:**
- `features` (pd.DataFrame): Raw feature data

**Returns:**
- `pd.DataFrame`: Normalized features in [-1, 1] range

**Example Usage:**

```python
raw_features = extractor.extract_technical_features(market_data)
normalized = extractor.normalize_features(raw_features)

print(f"Feature range: [{normalized.min().min():.2f}, {normalized.max().max():.2f}]")
```

---

### ModelPredictor

Manages ensemble model predictions with uncertainty quantification.

#### Class Definition

```python
class ModelPredictor:
    """Handles ensemble model predictions with uncertainty quantification."""
```

#### Constructor

```python
def __init__(self, config: Optional[Dict[str, Any]] = None)
```

**Parameters:**
- `config` (Dict[str, Any], optional): Model configuration

**Configuration Options:**
```python
{
    'models': List[str] = ['random_forest', 'xgboost', 'lstm'],
    'model_weights': Dict[str, float] = {'random_forest': 0.4, 'xgboost': 0.4, 'lstm': 0.2},
    'confidence_method': str = 'variance',  # 'variance' or 'entropy'
    'prediction_threshold': float = 0.5
}
```

#### Methods

##### predict_ensemble

```python
def predict_ensemble(self, features: np.ndarray) -> Dict[str, Any]
```

Generates ensemble predictions with confidence metrics.

**Parameters:**
- `features` (np.ndarray): Feature array with shape (n_samples, n_features)

**Returns:**
- `Dict[str, Any]`: Prediction results with confidence metrics

```python
{
    'prediction': float,           # Primary prediction (0.0-1.0)
    'confidence': float,          # Ensemble confidence (0.0-1.0)
    'model_predictions': Dict,    # Individual model predictions
    'uncertainty': float,         # Prediction uncertainty
    'prediction_interval': List, # [lower_bound, upper_bound]
    'model_agreement': float,     # Inter-model agreement score
    'weights_used': Dict         # Model weights applied
}
```

**Example Usage:**

```python
from core.ml.model_predictor import ModelPredictor
import numpy as np

predictor = ModelPredictor({
    'models': ['random_forest', 'xgboost'],
    'confidence_method': 'variance'
})

# Prepare features (1 sample, 10 features)
features = np.random.random((1, 10))

prediction = predictor.predict_ensemble(features)

print(f"Prediction: {prediction['prediction']:.3f}")
print(f"Confidence: {prediction['confidence']:.3f}")
print(f"Uncertainty: {prediction['uncertainty']:.3f}")
```

##### load_models

```python
def load_models(self, model_directory: str) -> bool
```

Loads trained models from disk.

**Parameters:**
- `model_directory` (str): Directory containing saved model files

**Returns:**
- `bool`: True if models loaded successfully

**Expected File Structure:**
```
model_directory/
├── random_forest_model.pkl
├── xgboost_model.pkl
├── lstm_model.h5
└── model_metadata.json
```

##### save_models

```python
def save_models(self, model_directory: str) -> bool
```

Saves current models to disk.

**Parameters:**
- `model_directory` (str): Directory to save model files

**Returns:**
- `bool`: True if models saved successfully

---

### SignalGenerator

Converts model predictions into actionable trading signals with risk management.

#### Class Definition

```python
class SignalGenerator:
    """Generates trading signals with risk adjustments."""
```

#### Constructor

```python
def __init__(self, config: Optional[Dict[str, Any]] = None)
```

**Parameters:**
- `config` (Dict[str, Any], optional): Signal generation configuration

**Configuration Options:**
```python
{
    'confidence_threshold': float = 0.7,
    'max_position_size': float = 0.05,
    'stop_loss_pct': float = 0.02,
    'take_profit_pct': float = 0.04,
    'risk_free_rate': float = 0.02,
    'volatility_lookback': int = 20
}
```

#### Methods

##### generate_signal

```python
def generate_signal(
    self,
    symbol: str,
    prediction: Dict[str, Any],
    current_price: float,
    market_data: Optional[pd.DataFrame] = None
) -> Dict[str, Any]
```

Generates trading signal from model prediction with comprehensive risk management.

**Parameters:**
- `symbol` (str): Trading symbol (e.g., 'EUR/USD')
- `prediction` (Dict[str, Any]): Output from ModelPredictor.predict_ensemble()
- `current_price` (float): Current market price
- `market_data` (pd.DataFrame, optional): Historical data for volatility calculation

**Returns:**
- `Dict[str, Any]`: Complete trading signal

```python
{
    'symbol': str,                    # Trading symbol
    'signal': str,                    # 'BUY', 'SELL', or 'HOLD'
    'confidence': float,              # Signal confidence (0.0-1.0)
    'position_size': float,           # Recommended position size
    'entry_price': float,             # Entry price
    'stop_loss': float,               # Stop loss price
    'take_profit': float,             # Take profit price
    'risk_reward_ratio': float,       # Risk/reward ratio
    'volatility': float,              # Estimated volatility
    'max_loss': float,                # Maximum potential loss
    'expected_return': float,         # Expected return
    'timestamp': str,                 # Signal generation timestamp
    'prediction_details': Dict,       # Original prediction data
    'risk_metrics': Dict             # Additional risk metrics
}
```

**Signal Logic:**
- **BUY**: prediction > 0.7 AND confidence > threshold
- **SELL**: prediction < 0.3 AND confidence > threshold
- **HOLD**: All other conditions

**Example Usage:**

```python
from core.ml.signal_generator import SignalGenerator

generator = SignalGenerator({
    'confidence_threshold': 0.75,
    'max_position_size': 0.03
})

prediction = {
    'prediction': 0.85,
    'confidence': 0.82,
    'uncertainty': 0.15
}

signal = generator.generate_signal(
    symbol='EUR/USD',
    prediction=prediction,
    current_price=1.0850,
    market_data=historical_data
)

print(f"Signal: {signal['signal']}")
print(f"Position Size: {signal['position_size']:.3f}")
print(f"Stop Loss: {signal['stop_loss']:.5f}")
print(f"Take Profit: {signal['take_profit']:.5f}")
```

---

## Supporting Components

### SignalAggregator

Combines multiple trading signals using sophisticated voting mechanisms.

#### Class Definition

```python
class SignalAggregator:
    """Aggregates multiple signals using voting mechanisms."""
```

#### Methods

##### aggregate_signals

```python
def aggregate_signals(
    self,
    signals: List[Dict[str, Any]],
    method: str = 'weighted_voting'
) -> Dict[str, Any]
```

Aggregates multiple signals into a single consensus signal.

**Parameters:**
- `signals` (List[Dict[str, Any]]): List of trading signals
- `method` (str): Aggregation method ('majority_voting', 'weighted_voting', 'confidence_weighted')

**Returns:**
- `Dict[str, Any]`: Aggregated signal

**Aggregation Methods:**
- `majority_voting`: Simple majority vote
- `weighted_voting`: Weighted by signal confidence
- `confidence_weighted`: Weighted by model confidence scores

**Example Usage:**

```python
from core.ml.signal_aggregator import SignalAggregator

aggregator = SignalAggregator()

signals = [
    {'signal': 'BUY', 'confidence': 0.8, 'symbol': 'EUR/USD'},
    {'signal': 'BUY', 'confidence': 0.7, 'symbol': 'EUR/USD'},
    {'signal': 'HOLD', 'confidence': 0.6, 'symbol': 'EUR/USD'}
]

aggregated = aggregator.aggregate_signals(signals, 'weighted_voting')
print(f"Consensus: {aggregated['signal']}")
```

---

### ConfidenceScorer

Calculates ensemble confidence scores and prediction intervals.

#### Class Definition

```python
class ConfidenceScorer:
    """Calculates ensemble confidence scores."""
```

#### Methods

##### calculate_ensemble_confidence

```python
def calculate_ensemble_confidence(
    self,
    predictions: Dict[str, float],
    method: str = 'variance'
) -> float
```

Calculates confidence score for ensemble predictions.

**Parameters:**
- `predictions` (Dict[str, float]): Individual model predictions
- `method` (str): Confidence calculation method ('variance', 'entropy', 'agreement')

**Returns:**
- `float`: Confidence score (0.0-1.0)

**Example Usage:**

```python
from core.ml.confidence_scorer import ConfidenceScorer

scorer = ConfidenceScorer()

predictions = {
    'random_forest': 0.75,
    'xgboost': 0.78,
    'lstm': 0.72
}

confidence = scorer.calculate_ensemble_confidence(predictions, 'variance')
print(f"Ensemble confidence: {confidence:.3f}")
```

---

### ModelPerformanceTracker

Tracks model accuracy and performance metrics in real-time.

#### Class Definition

```python
class ModelPerformanceTracker:
    """Tracks model accuracy and performance metrics."""
```

#### Methods

##### update_performance

```python
def update_performance(
    self,
    model_name: str,
    prediction: float,
    actual: float,
    timestamp: datetime
) -> None
```

Updates performance metrics for a specific model.

**Parameters:**
- `model_name` (str): Name of the model
- `prediction` (float): Model prediction
- `actual` (float): Actual outcome
- `timestamp` (datetime): Timestamp of the prediction

##### get_performance_metrics

```python
def get_performance_metrics(
    self,
    model_name: str,
    period_days: int = 30
) -> Dict[str, float]
```

Retrieves performance metrics for a model over specified period.

**Parameters:**
- `model_name` (str): Name of the model
- `period_days` (int): Number of days to calculate metrics over

**Returns:**
- `Dict[str, float]`: Performance metrics

```python
{
    'accuracy': float,           # Classification accuracy
    'precision': float,          # Precision score
    'recall': float,            # Recall score
    'f1_score': float,          # F1 score
    'auc_roc': float,           # Area under ROC curve
    'profit_factor': float,     # Trading profit factor
    'max_drawdown': float,      # Maximum drawdown
    'sharpe_ratio': float,      # Risk-adjusted returns
    'total_signals': int,       # Total number of signals
    'successful_signals': int   # Number of successful signals
}
```

---

### ModelDriftDetector

Detects model degradation using statistical tests.

#### Class Definition

```python
class ModelDriftDetector:
    """Detects model drift using statistical tests."""
```

#### Methods

##### detect_drift

```python
def detect_drift(
    self,
    reference_data: np.ndarray,
    current_data: np.ndarray,
    method: str = 'ks_test'
) -> Dict[str, Any]
```

Detects statistical drift between reference and current data.

**Parameters:**
- `reference_data` (np.ndarray): Reference/training data
- `current_data` (np.ndarray): Current/production data
- `method` (str): Drift detection method ('ks_test', 'psi', 'wasserstein')

**Returns:**
- `Dict[str, Any]`: Drift detection results

```python
{
    'drift_detected': bool,      # Whether drift was detected
    'drift_score': float,        # Drift magnitude score
    'p_value': float,           # Statistical significance
    'method_used': str,         # Detection method
    'threshold': float,         # Detection threshold
    'recommendation': str       # Recommended action
}
```

**Detection Methods:**
- `ks_test`: Kolmogorov-Smirnov test
- `psi`: Population Stability Index
- `wasserstein`: Wasserstein distance

---

### ModelManager

Handles model versioning, deployment, and rollback capabilities.

#### Class Definition

```python
class ModelManager:
    """Handles model versioning and deployment."""
```

#### Methods

##### deploy_model

```python
def deploy_model(
    self,
    model_name: str,
    model_path: str,
    version: str,
    metadata: Optional[Dict[str, Any]] = None
) -> bool
```

Deploys a new model version.

**Parameters:**
- `model_name` (str): Name of the model
- `model_path` (str): Path to model files
- `version` (str): Model version identifier
- `metadata` (Dict[str, Any], optional): Model metadata

**Returns:**
- `bool`: True if deployment successful

##### rollback_model

```python
def rollback_model(self, model_name: str, target_version: str) -> bool
```

Rolls back model to a previous version.

**Parameters:**
- `model_name` (str): Name of the model
- `target_version` (str): Target version to rollback to

**Returns:**
- `bool`: True if rollback successful

##### list_model_versions

```python
def list_model_versions(self, model_name: str) -> List[Dict[str, Any]]
```

Lists all available versions of a model.

**Parameters:**
- `model_name` (str): Name of the model

**Returns:**
- `List[Dict[str, Any]]`: List of model versions with metadata

---

## Error Handling

All API methods include comprehensive error handling with specific exception types:

### Exception Types

```python
class MLPipelineError(Exception):
    """Base exception for ML pipeline errors."""

class FeatureExtractionError(MLPipelineError):
    """Raised when feature extraction fails."""

class ModelPredictionError(MLPipelineError):
    """Raised when model prediction fails."""

class SignalGenerationError(MLPipelineError):
    """Raised when signal generation fails."""

class ConfigurationError(MLPipelineError):
    """Raised when configuration is invalid."""

class DataValidationError(MLPipelineError):
    """Raised when input data validation fails."""
```

### Error Response Format

```python
{
    'error': str,                    # Error type
    'message': str,                  # Detailed error message
    'timestamp': str,                # Error timestamp
    'component': str,                # Component that failed
    'traceback': str,               # Full traceback (debug mode)
    'suggestions': List[str]        # Suggested fixes
}
```

### Example Error Handling

```python
try:
    signal = await pipeline.process_market_data(market_data)
except FeatureExtractionError as e:
    logger.error(f"Feature extraction failed: {e.message}")
    # Implement fallback strategy
except ModelPredictionError as e:
    logger.error(f"Model prediction failed: {e.message}")
    # Use backup model or skip prediction
except Exception as e:
    logger.error(f"Unexpected error: {str(e)}")
    # General error handling
```

## Rate Limiting and Performance

### Rate Limits

- **process_market_data**: 1000 calls/minute per instance
- **WebSocket broadcasting**: No limit (handled by WebSocket server)
- **Model loading/saving**: 10 operations/minute

### Performance Guidelines

- **Batch Processing**: Process multiple data points together for better throughput
- **Caching**: Features and predictions are cached for 1 minute by default
- **Memory Management**: Automatic cleanup of old data to prevent memory leaks
- **Concurrent Processing**: Thread-safe for multiple currency pairs

### Optimization Tips

```python
# Batch processing for better performance
pipeline_config = {
    'batch_size': 100,           # Process 100 data points at once
    'cache_features': True,      # Cache extracted features
    'parallel_models': True,     # Run models in parallel
    'memory_limit_mb': 500       # Limit memory usage
}

pipeline = MLTradingPipeline(pipeline_config)
```

## Testing and Validation

### Test Coverage

The ML Pipeline includes comprehensive test coverage:

- **Unit Tests**: 22/22 tests passing (100% coverage)
- **Integration Tests**: End-to-end workflow testing
- **Performance Tests**: Latency and throughput benchmarks
- **Error Handling Tests**: Exception scenarios and recovery

### Validation Examples

```python
# Validate pipeline configuration
def validate_config(config: Dict[str, Any]) -> bool:
    required_fields = ['models', 'features', 'confidence_threshold']
    return all(field in config for field in required_fields)

# Validate market data format
def validate_market_data(data: pd.DataFrame) -> bool:
    required_columns = ['open', 'high', 'low', 'close', 'volume']
    return all(col in data.columns for col in required_columns)
```

This comprehensive API reference provides all the information needed to integrate and use the ML Trading Pipeline components effectively. For integration examples and troubleshooting guides, see the additional documentation sections.