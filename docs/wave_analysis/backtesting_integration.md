# Elliott Wave Analysis Backtesting Integration

This document details the integration of the Elliott Wave analysis components with the FXML4 backtesting framework.

## Overview

The integration provides a comprehensive approach to backtesting trading strategies that leverage Elliott Wave patterns combined with sentiment analysis and machine learning models. This multi-source signal approach allows for more robust trading decisions based on technical patterns, market sentiment, and statistical models.

## Architecture

The integration connects several components:

1. **Enhanced Wave Signal Generator**: Identifies Elliott Wave patterns enhanced with sentiment analysis
2. **Combined Signal Generator**: Combines signals from ML, sentiment, and Elliott Wave analysis
3. **Combined Strategy**: Implements the backtesting strategy with position management and risk controls
4. **Event-Driven Backtesting Engine**: Executes the backtests with realistic market simulation

![Architecture Diagram](../assets/wave_backtesting_architecture.png)

## Key Components

### Enhanced Wave Signal Generator

The `EnhancedWaveSignalGenerator` analyzes price data to detect Elliott Wave patterns with sentiment validation:

- Identifies impulse waves, corrections, diagonals, and triangles
- Validates patterns using sentiment analysis correlation
- Calculates confidence scores for each pattern
- Generates entry and exit signals with specific risk parameters
- Provides detailed stop loss and take profit levels

### Combined Signal Generator

The `CombinedSignalGenerator` merges signals from multiple sources:

- Integrates ML predictions, sentiment signals, and wave patterns
- Uses configurable weights for each signal source
- Adapts weights based on market regimes (trending, ranging, volatile)
- Requires consensus between multiple signal sources
- Provides confidence scoring and weighted signal strength

### Combined Strategy

The `CombinedStrategy` class leverages the combined signals for backtesting:

- Converts signals to backtesting events
- Manages positions with trailing stops and take profits
- Implements signal cooldown periods to prevent overtrading
- Controls risk with position sizing rules
- Handles entry/exit rules with signal threshold filtering

## Signal Flow

1. **Pattern Recognition**: Elliott Wave patterns are detected in price data
2. **Sentiment Validation**: Patterns are validated against sentiment data
3. **Signal Generation**: Wave patterns generate trading signals with confidence scores
4. **Signal Combination**: ML, sentiment, and wave signals are combined using weighted approach
5. **Strategy Implementation**: Combined signals are converted to trading actions
6. **Backtesting Execution**: The event-driven engine processes the trading events

## Integration Benefits

- **Improved Signal Quality**: Multiple validation sources reduce false signals
- **Enhanced Risk Management**: Pattern-specific stop loss placement
- **Adaptive Trading**: Different market regimes use different signal weights
- **Sentiment Correlation**: Pattern validation with news sentiment
- **Confidence-Based Position Sizing**: Higher confidence signals receive larger positions

## Usage Example

Here's a simple example demonstrating the integration:

```python
# Create signal generators
ml_signal_generator = MLSignalGenerator(model=ml_model, config=ml_config)
sentiment_signal_generator = SentimentSignalGenerator(sentiment_analyzer=sentiment_analyzer)
wave_signal_generator = EnhancedWaveSignalGenerator(wave_validator=wave_validator)

# Create combined signal generator
combined_signal_generator = CombinedSignalGenerator(
    ml_signal_generator=ml_signal_generator,
    sentiment_signal_generator=sentiment_signal_generator,
    wave_signal_generator=wave_signal_generator,
    config={
        "weights": {
            "ml": 0.4,
            "sentiment": 0.2,
            "wave": 0.4,
        },
        "min_confidence": 0.6,
        "require_consensus": True,
    }
)

# Create backtesting strategy
strategy = CombinedStrategy(
    signal_generator=combined_signal_generator,
    config={
        "use_dynamic_stops": True,
        "use_wave_stops": True,
        "position_size_pct": 2.0,
        "max_risk_pct": 2.0,
    }
)

# Run backtest with event-driven engine
engine = EventDrivenEngine(
    strategy=strategy_adapter,
    initial_capital=10000.0
)
engine.load_data(data)
results = engine.run()
```

See the full example in `examples/wave_backtest_example.py`.

## Performance Metrics

The backtesting system provides comprehensive performance analytics:

- Standard metrics (returns, drawdowns, win rate)
- Trade analysis (profitable vs. unprofitable trades)
- Pattern-specific performance
- Risk-adjusted metrics (Sharpe, Sortino ratios)

## Configuration Options

The integration provides numerous configuration options:

### Wave Signal Generator Options

| Parameter | Description | Default |
|-----------|-------------|---------|
| `threshold` | Minimum signal strength threshold | 0.65 |
| `max_stop_loss_pct` | Maximum stop loss as percentage | 2.0 |
| `stop_loss_confidence_scaling` | Scale stop loss by confidence | True |
| `take_profit_levels` | Risk-reward ratios for targets | Conservative: 1.5, Moderate: 2.0, Aggressive: 3.0 |
| `use_news_sentiment` | Use news for sentiment analysis | True |

### Combined Signal Generator Options

| Parameter | Description | Default |
|-----------|-------------|---------|
| `method` | Signal combination method (weighted, voting, priority) | weighted |
| `weights` | Weights for each signal source | ML: 0.4, Sentiment: 0.2, Wave: 0.4 |
| `min_confidence` | Minimum combined confidence | 0.6 |
| `min_agreement` | Minimum number of agreeing signals | 2 |
| `require_consensus` | Require multiple signals to agree | True |
| `use_adaptive_weights` | Adapt weights to market regimes | False |

### Combined Strategy Options

| Parameter | Description | Default |
|-----------|-------------|---------|
| `use_dynamic_stops` | Use dynamic stop loss levels | True |
| `use_wave_stops` | Use wave pattern for stop placement | True |
| `position_size_pct` | Position size as percentage of equity | 2.0 |
| `max_risk_pct` | Maximum risk percentage per trade | 2.0 |
| `adjustable_stops` | Enable trailing stops | True |
| `signal_cooldown` | Hours between signals | 0 |

## Future Improvements

- Reinforcement learning optimization of signal weights
- Pattern-specific parameter optimization
- Integration with real-time signal generation
- Advanced market regime detection
- Enhanced visualization of pattern-based signals
