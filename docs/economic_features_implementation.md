# Economic Feature Engineering Implementation

This document describes the implementation of economic data feature engineering for FXML4, which enables the use of exogenous economic indicators to enhance trading strategies and machine learning models.

## Overview

Economic indicators provide valuable context for financial markets and can help identify different market regimes (growth, recession, inflation, etc.) that may require different trading approaches.

The implementation includes:

1. **Feature Engineering**: A dedicated module for creating features from economic data
2. **Regime Classification**: Identification of economic regimes based on multiple indicators
3. **Signal Adjustment**: Framework for adjusting trading signals based on economic regimes
4. **ML Integration**: Integration with existing ML feature pipeline

## Key Components

### 1. Economic Feature Engineer

The `EconomicFeatureEngineer` class in `fxml4/ml/economic_features.py` provides:

- Feature creation based on economic indicators
- Automatic detection of data frequency (daily, weekly, monthly, quarterly)
- Creation of derived features (rate of change, z-scores, relationships between indicators)
- Economic regime classification
- Signal adjustment framework

### 2. ML Feature Integration

The standard feature engineering pipeline in `fxml4/ml/features.py` has been enhanced to:

- Accept economic data as an optional input
- Properly align economic data with market data (handling different frequencies)
- Add economic features and regime classifications to market data
- Enable/disable economic features via configuration

### 3. Example Usage

Two example scripts demonstrate the usage of economic features:

- `docs/examples/exogenous_data_strategy_example.py`: Shows how to use economic regimes to adapt a simple trading strategy
- `docs/examples/ml_economic_integration.py`: Demonstrates how to integrate economic data with ML models

### 4. Testing

Unit tests in `tests/test_economic_features.py` validate:

- Economic feature creation functionality
- Regime detection logic
- Signal adjustment based on regimes
- Configuration customization

## Feature Types

The economic feature engineering creates several types of features:

1. **Change Rates**: Percentage changes over time periods appropriate for each indicator's frequency
   - Examples: GDP_4q_change, CPIAUCSL_12m_change, UNRATE_1m_change

2. **Z-Scores**: Standardized values showing deviation from recent history
   - Examples: GDP_zscore, CPIAUCSL_zscore, UNRATE_zscore

3. **Relationship Features**: Features derived from relationships between different indicators
   - Examples: real_interest_rate (FEDFUNDS - CPIAUCSL_12m_change), unemployment_gap (UNRATE - NROU)

4. **Regime Classifications**: Economic regime classifications as categorical and dummy variables
   - Values: normal, growth, inflation, recession_risk, recession, stagflation
   - Also provided as dummy variables: regime_growth, regime_inflation, etc.

## Economic Regimes

The system detects the following economic regimes:

1. **Normal**: Default regime when no special conditions are detected
2. **Growth**: Strong GDP growth above threshold
3. **Inflation**: High inflation above threshold
4. **Recession Risk**: Yield curve inversion or other leading indicators
5. **Recession**: High unemployment combined with negative GDP growth
6. **Stagflation**: Combination of high inflation with recession conditions

## Configuration

The economic feature engineering is highly configurable through a configuration dictionary:

```python
config = {
    "economic_features": {
        "indicator_thresholds": {
            "UNRATE": {"high_threshold": 6.0},
            "CPIAUCSL": {"high_threshold": 0.04},
            "GDP": {"high_threshold": 0.03},
            "T10Y2Y": {"inversion_threshold": -0.001}
        },
        "regime_adjustment_factors": {
            "normal": 1.0,
            "growth": 1.2,
            "inflation": 0.7,
            "recession_risk": 0.5,
            "recession": 0.3,
            "stagflation": 0.2
        }
    }
}
```

## Usage Examples

### Basic Usage

```python
from fxml4.ml.economic_features import create_economic_features, detect_regime

# Create economic features
features = create_economic_features(economic_data)

# Detect economic regimes
regimes = detect_regime(features)
```

### ML Integration

```python
from fxml4.ml.features import create_ml_features

# Create ML features with economic data
config = {"features": {"economic_features": True}}
features = create_ml_features(market_data, economic_data, config)
```

### Signal Adjustment

```python
from fxml4.ml.economic_features import adjust_signals

# Define adjustment factors
adjustment_factors = {
    "normal": 1.0,
    "growth": 1.2,
    "inflation": 0.7,
    "recession_risk": 0.5,
    "recession": 0.3,
    "stagflation": 0.2
}

# Adjust trading signals based on economic regime
adjusted_signals = adjust_signals(signals, economic_regime, adjustment_factors)
```

## Next Steps

1. **More Indicators**: Add support for more economic indicators and their relationships
2. **Advanced Regime Detection**: Implement more sophisticated regime detection using ML models
3. **Specialized Strategies**: Create regime-specific strategies optimized for different economic conditions
4. **Leading Indicators**: Focus on leading economic indicators for better predictive power
5. **Global Indicators**: Add support for international economic indicators for multi-market strategies
