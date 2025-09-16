# FXML4 ML Models

Machine learning models for forex trading signal generation.

## Features

- Multiple model types (RandomForest, XGBoost, LightGBM)
- Time-series cross-validation
- Feature importance analysis
- Hyperparameter optimization with Optuna
- Model persistence and versioning
- Ensemble methods
- Walk-forward optimization

## Installation

```bash
poetry install
```

## Usage

```python
from fxml4_ml.models import MLModelFactory
from fxml4_ml.training import TimeSeriesTrainer
from fxml4_ml.validation import TimeSeriesCrossValidator

# Create model
model = MLModelFactory.create("xgboost", params={
    "n_estimators": 100,
    "max_depth": 5,
    "learning_rate": 0.01
})

# Train with time-series validation
trainer = TimeSeriesTrainer(model)
results = trainer.fit(X_train, y_train, validation_split=0.2)

# Evaluate with walk-forward analysis
validator = TimeSeriesCrossValidator(n_splits=5)
scores = validator.evaluate(model, X, y)
```

## Models

### Supported Algorithms
- Random Forest
- XGBoost
- LightGBM
- Neural Networks
- Ensemble Methods

### Feature Engineering
- Technical indicators
- Market microstructure features
- Sentiment features
- Multi-timeframe features

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