# Pivot Point Analysis Integration

This document outlines the integration of pivot point analysis features from FXML2 into the FXML4 GBP/USD ML pipeline.

## Overview

Pivot points are significant price levels derived from previous trading periods. They are widely used by traders to identify potential support and resistance levels. By integrating pivot point analysis into our ML models, we aim to improve prediction accuracy by incorporating these key technical indicators.

## Implementation

We have implemented two main types of pivot point analysis:

1. **Weekly Pivot Points**: Calculate pivot points based on weekly high, low, and close prices
2. **Session/Daily Pivot Points**: Calculate pivot points based on daily trading sessions

Each implementation provides the following key levels:

- **PP (Pivot Point)**: The base pivot level
- **R1, R2, R3**: Resistance levels
- **S1, S2, S3**: Support levels

Additionally, we calculate distance features that measure the percentage distance from the current price to each pivot level.

## Features Added

The pivot point integration adds the following features to our ML pipeline:

| Feature Type | Description | Example Features |
|--------------|-------------|------------------|
| Base Pivot Levels | Raw pivot point values | `PP`, `R1`, `S1`, `R2`, `S2`, `R3`, `S3` |
| Distance Features | Distance from current price to pivot levels (%) | `distance_to_PP`, `distance_to_R1`, `distance_to_S1` |
| Breakout Indicators | Binary indicators for price breaks | `above_R1`, `below_S1`, `between_S1_R1` |
| Proximity Indicators | Binary indicators for price near pivots | `near_PP`, `near_R1`, `near_S1` |
| Historical Effectiveness | How often price reaches pivot levels | `hit_R1_12`, `hit_S1_12` |

## Code Structure

### Feature Engineering Module

The pivot point calculations are implemented in `fxml4/ml/features.py` with two main functions:

1. `calculate_weekly_pivot_points(df)`: Calculates weekly pivot points
2. `calculate_session_pivot_levels(df)`: Calculates session/daily pivot points

### GBP/USD Model Integration

The `GBPUSDModel` class in `fxml4/ml/gbpusd_model.py` has been updated to include pivot point features in the feature preparation process via the `prepare_features()` method.

## Usage Example

```python
from fxml4.ml.gbpusd_model import GBPUSDModel
import pandas as pd

# Load data
data = pd.read_parquet('input/gbpusd_4h.parquet')

# Create model
model = GBPUSDModel(model_type='random_forest')

# Prepare features with pivot points
features = model.prepare_features(
    data,
    target_horizon=12,
    add_pivot_points=True,
    create_target=True
)

# Train model
model.train(features, target_col='target_12')
```

## Evaluation

Initial testing shows that incorporating pivot point features can improve model accuracy for GBP/USD prediction. Specifically:

- Models with pivot point features show improved accuracy for predicting reversal points
- Distance-to-pivot features are often ranked in the top features by importance
- The "between_S1_R1" feature is particularly valuable for identifying consolidation periods

## Future Improvements

1. Implement full session detection to calculate more accurate session-specific pivot points
2. Add more advanced pivot point calculations (Camarilla, Woodie's, Fibonacci)
3. Incorporate pivot confluence with other technical indicators
4. Create specialized models for pivot breakout prediction

## References

The pivot point implementation is based on the following sources:

1. Code from FXML2's `etl-wpp-session.py` and `packages/trading_session_analysis.py`
2. Standard pivot point calculation formulas:
   - PP = (High + Low + Close) / 3
   - R1 = (2 × PP) - Low
   - S1 = (2 × PP) - High
   - R2 = PP + (High - Low)
   - S2 = PP - (High - Low)
   - R3 = High + 2 × (PP - Low)
   - S3 = Low - 2 × (High - PP)
