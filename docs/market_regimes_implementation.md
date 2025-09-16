# Market Regime Classification Implementation

This document describes the implementation of market regime classification in FXML4, which enables the detection and analysis of different market regimes using both market data and economic indicators.

## Overview

Markets exhibit different behaviors (regimes) over time, characterized by varying volatility, trends, volume patterns, and economic contexts. Detecting these regimes allows for adaptive trading strategies that can adjust parameters based on the current market conditions.

The implementation includes:

1. **Regime Detection**: Unsupervised learning to identify distinct market regimes
2. **Regime Analysis**: Tools to analyze and interpret regime characteristics
3. **Regime Shifts**: Detection of transitions between regimes
4. **Adaptive Trading**: Framework for adjusting strategy parameters based on the current regime

## Key Components

### 1. Market Regime Classifier

The `MarketRegimeClassifier` class in `fxml4/ml/market_regimes.py` provides:

- **Unsupervised Classification**: Uses K-means clustering to identify distinct market regimes
- **Feature Integration**: Combines market features with economic indicators
- **Dimensionality Reduction**: Optional PCA for improved clustering of high-dimensional data
- **Regime Interpretation**: Tools to analyze and describe detected regimes
- **Regime Shifts**: Detection of transitions between regimes

### 2. Feature Selection

The classifier uses a customizable set of features that can include:

- **Technical Indicators**: Volatility measures, momentum indicators, trend indicators
- **Price Patterns**: Return patterns, price position within ranges
- **Volume Analysis**: Volume relative to recent history, abnormal volume
- **Economic Indicators**: Inflation, unemployment, interest rates, yield curve, VIX

### 3. Regime Descriptions

The system automatically generates qualitative descriptions of each regime:

- **Volatility**: Low, medium, or high based on volatility measures
- **Trend**: Sideways, bullish, strong bullish, bearish, or strong bearish
- **Volume**: Low, average, or high relative to recent history
- **Momentum**: Overbought, positive, neutral, negative, or oversold
- **Economic Context**: Growth, inflation, interest rates, yield curve status

### 4. Adaptive Trading

The implementation includes a framework for adapting strategy parameters based on the current regime:

- **Parameter Sets**: Different parameter configurations for each regime
- **Strategy Adaptation**: Adjustment of entry/exit conditions, timeframes, and risk management
- **Performance Analysis**: Comparison of adaptive vs. standard strategies

## Technical Implementation

### Regime Detection

Regime detection uses a multi-step process:

1. **Feature Preparation**: Prepares market and economic features
2. **Feature Standardization**: Normalizes features to have equal weight
3. **Dimensionality Reduction**: Optional PCA to improve clustering
4. **K-means Clustering**: Identifies distinct regimes
5. **Regime Analysis**: Analyzes regime characteristics

```python
# Detect market regimes
regimes = classify_market_regimes(
    market_data=features,
    economic_data=economic_data,
    n_regimes=4
)

# Get regime descriptions
descriptions = get_regime_descriptions(features, regimes, economic_data)
```

### Regime Shifts

The system can detect regime shifts, which can be valuable for trading decisions:

```python
# Detect regime shifts
shifts = classifier.detect_regime_shifts(regimes, window=60)
```

### Adaptive Trading

The implementation supports regime-specific strategy parameters:

```python
# Define strategy parameters for each regime
regime_configs = {
    0: {"rsi_high": 70, "rsi_low": 30, "use_sma": True},
    1: {"rsi_high": 75, "rsi_low": 25, "use_sma": False},
    # Parameters for other regimes
}

# Create regime-adaptive signals
signals = create_signals_by_regime(features, regimes, regime_configs)
```

## Example Usage

A comprehensive example is provided in `docs/examples/market_regime_analysis.py` which demonstrates:

1. Loading market data and economic indicators
2. Detecting market regimes
3. Analyzing regime characteristics
4. Creating a regime-adaptive trading strategy
5. Comparing performance against a non-adaptive strategy
6. Visualizing results

## Integration with Economic Features

The market regime classifier integrates with the economic feature engineering module:

- Economic indicators provide context for market behaviors
- Economic regimes (inflation, recession, etc.) are incorporated into market regime descriptions
- Combined approach provides more meaningful regime classifications

## Visualization

The implementation includes visualization capabilities:

- Price charts with regime-colored backgrounds
- Equity curves for adaptive vs. standard strategies
- Trade performance by regime
- Regime shift indicators

## Configuration

The market regime classification system is highly configurable:

```python
config = {
    "market_regimes": {
        "n_regimes": 4,                # Number of regimes to detect
        "use_economic_data": True,      # Whether to include economic data
        "use_pca": True,                # Whether to use PCA
        "pca_components": 5,            # Number of PCA components to use
        "regime_window": 126,           # Window for detecting regime shifts
        "market_features": [            # Market features to use
            "volatility_20", "rsi_14", "bb_width", "return_20", "price_position_20"
        ],
        "economic_features": [          # Economic features to use
            "econ_VIXCLS", "econ_T10Y2Y", "econ_CPIAUCSL_12m_change"
        ]
    }
}
```

## Use Cases

The market regime classification can be used for:

1. **Adaptive Trading**: Adjust strategy parameters based on current regime
2. **Risk Management**: Modify position sizing and stop-loss levels by regime
3. **Strategy Evaluation**: Analyze which strategies work best in which regimes
4. **Market Analysis**: Understand current market conditions in historical context
5. **Regime Prediction**: Build models to predict upcoming regime shifts

## Future Enhancements

Potential future enhancements include:

1. **Alternative Clustering**: Test different clustering algorithms (DBSCAN, GMM, etc.)
2. **Regime Prediction**: Use machine learning to predict upcoming regime shifts
3. **Hierarchical Regimes**: Implement nested regimes (macro regime + micro regime)
4. **Dynamic Regime Count**: Automatically determine optimal number of regimes
5. **Online Learning**: Update regime models incrementally with new data
