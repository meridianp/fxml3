# FXML4 Signal Generator

Trading signal generation service for FXML4.

## Features

- Technical indicator-based signals
- Machine learning signal generation
- Elliott Wave pattern signals
- Multi-timeframe signal aggregation
- Signal confidence scoring
- Risk-adjusted signal filtering

## Installation

```bash
poetry install
```

## Usage

```python
from fxml4_signals import SignalGenerator, TechnicalSignals, MLSignals

# Create signal generator
generator = SignalGenerator()

# Add signal sources
generator.add_source(TechnicalSignals())
generator.add_source(MLSignals(model_path="path/to/model"))

# Generate signals
signals = generator.generate(market_data)

# Filter high-confidence signals
high_confidence = signals[signals.confidence > 0.7]
```

## Signal Types

### Technical Signals
- Moving average crossovers
- RSI oversold/overbought
- MACD divergences
- Bollinger Band breakouts
- Support/resistance levels

### ML Signals
- Prediction-based signals
- Feature importance weighting
- Ensemble signal generation

### Elliott Wave Signals
- Wave pattern completion
- Fibonacci retracement levels
- Wave degree confluence

## Development

```bash
# Run tests
poetry run pytest

# Format code
poetry run black src tests
poetry run isort src tests

# Type checking
poetry run mypy src
```