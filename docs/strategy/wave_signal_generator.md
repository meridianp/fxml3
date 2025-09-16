# Wave Signal Generator

This document describes the EnhancedWaveSignalGenerator class, which integrates sentiment-enhanced Elliott Wave analysis for generating trading signals.

## Overview

The EnhancedWaveSignalGenerator leverages the sentiment-enhanced Elliott Wave pattern detection and validation to generate actionable trading signals. It combines traditional pattern-based signals with sentiment analysis and risk management parameters for a complete trading signal solution.

## Key Components

1. **Sentiment-Enhanced Wave Analysis**:
   - Uses SentimentWaveValidator for pattern detection and validation
   - Combines Elliott Wave patterns with market sentiment
   - Utilizes RAG system for knowledge-backed validation

2. **Signal Generation Logic**:
   - Determines signal types based on wave patterns and positions
   - Implements strength scoring based on confidence and position
   - Generates both entry and exit signals

3. **Risk Management**:
   - Calculates optimal stop loss levels based on wave structure
   - Implements confidence-based stop loss adjustment
   - Creates multiple take profit levels based on risk-reward ratios

4. **Pattern-Specific Signals**:
   - Impulse pattern completions generate short signals and exit long signals
   - Correction completions generate long signals and exit short signals
   - Diagonal and triangle patterns generate signals based on market sentiment

## Signal Generation Process

1. **Pattern Analysis**:
   - Detect Elliott Wave patterns in price data
   - Validate patterns using sentiment and RAG system
   - Filter patterns based on confidence thresholds

2. **Signal Type Determination**:
   - Different wave patterns and positions generate different signals
   - End of impulse wave 5 → Short entry & Long exit
   - End of correction wave C → Long entry & Short exit
   - Diagonal and triangle signals depend on current sentiment

3. **Signal Strength Calculation**:
   - Base strength from pattern confidence
   - Position weights for different wave positions
   - Combined strength determines signal importance

4. **Risk Level Determination**:
   - Stop loss levels based on wave structure
   - Tighter stops for higher confidence patterns
   - Take profit levels at multiple risk-reward ratios

## Signal Metadata

Each signal includes comprehensive metadata:
- Wave pattern type and position
- Pattern confidence and sentiment score
- Stop loss level with dynamic adjustment
- Multiple take profit targets
- Detailed wave pattern information
- RAG-based validation details

## Example Usage

```python
# Create components
wave_analyzer = ElliottWaveAnalyzer()
sentiment_analyzer = MarketSentimentAnalyzer()
rag = RAG()

# Create validator
wave_validator = SentimentWaveValidator(
    wave_analyzer=wave_analyzer,
    sentiment_analyzer=sentiment_analyzer,
    rag=rag
)

# Create signal generator
signal_generator = EnhancedWaveSignalGenerator(
    wave_validator=wave_validator,
    config={
        "threshold": 0.6,
        "min_confidence": 0.6,
        "max_stop_loss_pct": 2.0,
        "stop_loss_confidence_scaling": True,
        "take_profit_levels": {
            "conservative": 1.5,
            "moderate": 2.0,
            "aggressive": 3.0
        }
    }
)

# Generate signals
signals = signal_generator.generate_signals(
    data=price_data,
    news_data=news_data,  # Optional
    symbol="GBPUSD",
    timeframe="1H"
)
```

## Benefits

1. **Enhanced Accuracy**:
   - Combines multiple sources of validation
   - Reduces false positives through sentiment alignment
   - Uses knowledge-backed validation with RAG system

2. **Complete Trading Signals**:
   - Includes both entry and exit signals
   - Provides stop loss and take profit levels
   - Includes confidence metrics

3. **Risk Management Integration**:
   - Dynamic stop loss sizing based on confidence
   - Structure-based stop loss placement
   - Multiple take profit targets with risk-reward ratios

4. **Decision Support**:
   - Rich metadata for trader decision making
   - Confidence scores for signal importance
   - Detailed pattern information for reference

## Example Signals

![Impulse Signal Example](/docs/strategy/impulse_signals.png)
![Correction Signal Example](/docs/strategy/correction_signals.png)
![Diagonal Signal Example](/docs/strategy/diagonal_signals.png)

## Integration with Trading Systems

The EnhancedWaveSignalGenerator can be integrated with:
- Backtesting engine for historical performance evaluation
- Automated trading systems for execution
- Combined with ML and fundamental signals
- Risk management systems for position sizing

## Future Enhancements

1. **Market Regime Integration**:
   - Adjust signal parameters based on market regimes
   - Filter signals during unfavorable regimes
   - Optimize risk parameters for different market conditions

2. **Multi-Timeframe Signal Confirmation**:
   - Require confirmation from multiple timeframes
   - Higher confidence for aligned signals across timeframes
   - Resolution of conflicting signals from different timeframes

3. **Performance-Based Parameter Optimization**:
   - Backtest-driven parameter optimization
   - Adaptation of weights based on historical performance
   - Pattern-specific parameter tuning
